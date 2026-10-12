"""
Otopark veritabanı katmanı (SQLite, WAL modu).

Durum metinleri ('Boş', 'Dolu', 'İçeride', 'Çıkış Yaptı') Java paneliyle
uyumlu kalmak için değiştirilmemelidir.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import ayarlar

log = logging.getLogger("otopark.db")

ZAMAN_FORMATI = "%Y-%m-%d %H:%M:%S"
BOS, DOLU = "Boş", "Dolu"
ICERIDE, CIKTI = "İçeride", "Çıkış Yaptı"


@dataclass
class IslemSonucu:
    tur: str                     # 'giris' | 'cikis' | 'dolu'
    plaka: str
    zaman: datetime
    slot_id: int | None = None
    kat: int | None = None
    slot_etiketi: str | None = None
    giris_zamani: datetime | None = None
    sure_saniye: int | None = None
    ucret: float | None = None


def zaman_coz(metin: str | None) -> datetime | None:
    if not metin:
        return None
    try:
        return datetime.strptime(metin[:19], ZAMAN_FORMATI)
    except ValueError:
        return None


def sinyal_yaz():
    """Java paneline 'verileri yenile' sinyali bırakır (panel dosyayı görüp siler)."""
    try:
        ayarlar.SINYAL_DOSYASI.write_text(datetime.now().isoformat(), encoding="utf-8")
    except OSError as e:
        log.warning("Panel sinyali yazılamadı: %s", e)


class Veritabani:
    def __init__(self, yol: Path | str = ayarlar.DB_YOLU):
        self.yol = Path(yol)
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.yol, check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self._kilit = threading.RLock()
        self.sema_hazirla()

    def kapat(self):
        with self._kilit:
            self.conn.close()

    # ── Şema ─────────────────────────────────────────────────────────
    def _sutunlar(self, tablo: str) -> list[str]:
        return [r["name"] for r in self.conn.execute(f"PRAGMA table_info({tablo})")]

    def sema_hazirla(self):
        with self._kilit, self.conn:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS arac_kayitlari (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    plaka         TEXT NOT NULL,
                    giris_zamani  TEXT,
                    cikis_zamani  TEXT,
                    ucret         REAL DEFAULT 0.0,
                    durum         TEXT,
                    slot_no       INTEGER
                )
            """)
            if "slot_no" not in self._sutunlar("arac_kayitlari"):
                self.conn.execute("ALTER TABLE arac_kayitlari ADD COLUMN slot_no INTEGER")

            slot_sutunlari = self._sutunlar("otopark_slotlari")
            if slot_sutunlari and "kat" not in slot_sutunlari:
                log.warning("Eski slot tablosu (kat sütunu yok) bulundu, yeniden oluşturuluyor.")
                self.conn.execute("DROP TABLE otopark_slotlari")

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS otopark_slotlari (
                    slot_id         INTEGER PRIMARY KEY,
                    kat             INTEGER NOT NULL,
                    kat_slot_no     INTEGER NOT NULL,
                    slot_etiketi    TEXT NOT NULL,
                    durum           TEXT DEFAULT 'Boş',
                    park_eden_plaka TEXT
                )
            """)
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_arac_plaka_durum ON arac_kayitlari(plaka, durum)"
            )

            if self.conn.execute("SELECT COUNT(*) FROM otopark_slotlari").fetchone()[0] == 0:
                slotlar = [
                    ((kat - 1) * ayarlar.KAT_BASINA_SLOT + s, kat, s, f"K{kat}-S{s}")
                    for kat in range(1, ayarlar.KAT_SAYISI + 1)
                    for s in range(1, ayarlar.KAT_BASINA_SLOT + 1)
                ]
                self.conn.executemany(
                    "INSERT INTO otopark_slotlari (slot_id, kat, kat_slot_no, slot_etiketi, durum) "
                    "VALUES (?, ?, ?, ?, 'Boş')", slotlar,
                )
                log.info("%d kat × %d slot oluşturuldu.", ayarlar.KAT_SAYISI, ayarlar.KAT_BASINA_SLOT)

    # ── Giriş / çıkış ────────────────────────────────────────────────
    def arac_isle(self, plaka: str) -> IslemSonucu:
        """Araç içerideyse çıkış, değilse giriş yapar."""
        with self._kilit:
            icerde = self.conn.execute(
                "SELECT 1 FROM arac_kayitlari WHERE plaka=? AND durum=?", (plaka, ICERIDE)
            ).fetchone()
            park_halinde = self.conn.execute(
                "SELECT 1 FROM otopark_slotlari WHERE park_eden_plaka=?", (plaka,)
            ).fetchone()
            if icerde or park_halinde:
                return self.cikis_yap(plaka)
            return self.giris_yap(plaka)

    def giris_yap(self, plaka: str) -> IslemSonucu:
        su_an = datetime.now().replace(microsecond=0)
        with self._kilit, self.conn:
            slot = self.conn.execute(
                "SELECT slot_id, kat, slot_etiketi FROM otopark_slotlari "
                "WHERE durum=? ORDER BY RANDOM() LIMIT 1", (BOS,)
            ).fetchone()
            if slot is None:
                log.warning("OTOPARK DOLU — %s içeri alınmadı.", plaka)
                return IslemSonucu("dolu", plaka, su_an)

            self.conn.execute(
                "INSERT INTO arac_kayitlari (plaka, giris_zamani, durum, ucret, slot_no) "
                "VALUES (?, ?, ?, 0, ?)",
                (plaka, su_an.strftime(ZAMAN_FORMATI), ICERIDE, slot["slot_id"]),
            )
            self.conn.execute(
                "UPDATE otopark_slotlari SET durum=?, park_eden_plaka=? WHERE slot_id=?",
                (DOLU, plaka, slot["slot_id"]),
            )
        log.info("GİRİŞ  %s → %s (Kat %d)", plaka, slot["slot_etiketi"], slot["kat"])
        sinyal_yaz()
        return IslemSonucu("giris", plaka, su_an, slot["slot_id"], slot["kat"],
                           slot["slot_etiketi"], giris_zamani=su_an)

    def cikis_yap(self, plaka: str) -> IslemSonucu:
        su_an = datetime.now().replace(microsecond=0)
        with self._kilit, self.conn:
            kayit = self.conn.execute(
                "SELECT id, giris_zamani FROM arac_kayitlari WHERE plaka=? AND durum=? "
                "ORDER BY id DESC LIMIT 1", (plaka, ICERIDE)
            ).fetchone()
            slot = self.conn.execute(
                "SELECT slot_id, kat, slot_etiketi FROM otopark_slotlari WHERE park_eden_plaka=?",
                (plaka,)
            ).fetchone()

            giris = zaman_coz(kayit["giris_zamani"]) if kayit else None
            sure = int((su_an - giris).total_seconds()) if giris else 0
            ucret = ayarlar.ucret_hesapla(sure) if kayit else 0.0

            if kayit:
                self.conn.execute(
                    "UPDATE arac_kayitlari SET cikis_zamani=?, ucret=?, durum=? WHERE plaka=? AND durum=?",
                    (su_an.strftime(ZAMAN_FORMATI), ucret, CIKTI, plaka, ICERIDE),
                )
            self.conn.execute(
                "UPDATE otopark_slotlari SET durum=?, park_eden_plaka=NULL WHERE park_eden_plaka=?",
                (BOS, plaka),
            )
        log.info("ÇIKIŞ  %s | süre %d sn | ücret %.2f ₺", plaka, sure, ucret)
        sinyal_yaz()
        return IslemSonucu(
            "cikis", plaka, su_an,
            slot["slot_id"] if slot else None, slot["kat"] if slot else None,
            slot["slot_etiketi"] if slot else None, giris, sure, ucret,
        )

    # ── Sorgular ─────────────────────────────────────────────────────
    def plaka_konumu(self, plaka: str):
        with self._kilit:
            r = self.conn.execute(
                "SELECT kat, slot_etiketi FROM otopark_slotlari WHERE park_eden_plaka=? AND durum=?",
                (plaka, DOLU),
            ).fetchone()
        return (r["kat"], r["slot_etiketi"]) if r else (None, None)

    def slotlar(self) -> list[sqlite3.Row]:
        with self._kilit:
            return self.conn.execute("""
                SELECT s.slot_id, s.kat, s.kat_slot_no, s.slot_etiketi, s.durum,
                       s.park_eden_plaka,
                       (SELECT a.giris_zamani FROM arac_kayitlari a
                         WHERE a.plaka = s.park_eden_plaka AND a.durum = ?
                         ORDER BY a.id DESC LIMIT 1) AS giris_zamani
                FROM otopark_slotlari s
                ORDER BY s.kat, s.kat_slot_no
            """, (ICERIDE,)).fetchall()

    def kayitlar(self, arama: str = "", durum: str | None = None, limit: int = 500):
        sorgu = """
            SELECT a.id, a.plaka, a.giris_zamani, a.cikis_zamani, a.ucret, a.durum,
                   s.slot_etiketi
            FROM arac_kayitlari a
            LEFT JOIN otopark_slotlari s ON s.slot_id = a.slot_no
            WHERE a.plaka LIKE ?
        """
        params: list = [f"%{arama}%"]
        if durum:
            sorgu += " AND a.durum = ?"
            params.append(durum)
        sorgu += " ORDER BY a.id DESC LIMIT ?"
        params.append(limit)
        with self._kilit:
            return self.conn.execute(sorgu, params).fetchall()

    def istatistikler(self) -> dict:
        bugun = datetime.now().strftime("%Y-%m-%d") + "%"
        with self._kilit:
            c = self.conn
            return {
                "toplam_slot": c.execute("SELECT COUNT(*) FROM otopark_slotlari").fetchone()[0],
                "dolu_slot": c.execute(
                    "SELECT COUNT(*) FROM otopark_slotlari WHERE durum=?", (DOLU,)).fetchone()[0],
                "iceride": c.execute(
                    "SELECT COUNT(*) FROM arac_kayitlari WHERE durum=?", (ICERIDE,)).fetchone()[0],
                "bugun_giris": c.execute(
                    "SELECT COUNT(*) FROM arac_kayitlari WHERE giris_zamani LIKE ?", (bugun,)).fetchone()[0],
                "bugun_gelir": c.execute(
                    "SELECT COALESCE(SUM(ucret), 0) FROM arac_kayitlari "
                    "WHERE durum=? AND cikis_zamani LIKE ?", (CIKTI, bugun)).fetchone()[0],
            }

    def veri_surumu(self) -> int:
        """Başka bir bağlantı (ör. Java paneli) yazdığında değişen sayaç."""
        with self._kilit:
            return self.conn.execute("PRAGMA data_version").fetchone()[0]

    # ── Silme ────────────────────────────────────────────────────────
    def kayit_sil(self, kayit_id: int) -> bool:
        with self._kilit, self.conn:
            r = self.conn.execute(
                "SELECT plaka, durum FROM arac_kayitlari WHERE id=?", (kayit_id,)).fetchone()
            if r is None:
                return False
            if r["durum"] == ICERIDE:  # içerideki aracın kaydı silinirse slotu da boşalt
                self.conn.execute(
                    "UPDATE otopark_slotlari SET durum=?, park_eden_plaka=NULL WHERE park_eden_plaka=?",
                    (BOS, r["plaka"]),
                )
            self.conn.execute("DELETE FROM arac_kayitlari WHERE id=?", (kayit_id,))
        sinyal_yaz()
        return True

    def tumunu_temizle(self):
        """Tüm araç kayıtlarını siler, ID sayacını sıfırlar ve slotları boşaltır."""
        with self._kilit, self.conn:
            self.conn.execute("DELETE FROM arac_kayitlari")
            self.conn.execute("DELETE FROM sqlite_sequence WHERE name='arac_kayitlari'")
            self.conn.execute("UPDATE otopark_slotlari SET durum=?, park_eden_plaka=NULL", (BOS,))
        sinyal_yaz()
