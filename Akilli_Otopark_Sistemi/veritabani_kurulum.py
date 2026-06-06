import sqlite3
import os

# ──────────────────────────────────────────────────────────────────────
#  DÜZELTME 1: DB_YOLU tam yol olarak güncellendi.
#  Eski kodda "otopark.db" yazıyordu → script nerede çalıştırılırsa
#  oraya kaydediyordu, Java'nın baktığı Otopark klasörüne değil.
# ──────────────────────────────────────────────────────────────────────
DB_YOLU = r"C:\Users\Yavuz Gümüş\OneDrive\Masaüstü\Otopark\otopark.db"


def veritabani_olustur():

    # ── DÜZELTME 2: Klasör yoksa oluştur ──────────────────────────────
    # Klasör yokken sqlite3.connect() hata verir.
    klasor = os.path.dirname(DB_YOLU)
    if klasor and not os.path.exists(klasor):
        os.makedirs(klasor)
        print(f"📁 Klasör oluşturuldu: {klasor}")

    # ── DÜZELTME 3: Eski bozuk şemayı temizle ─────────────────────────
    # "no such column: kat" hatası, eski veritabanında kat sütunu
    # olmayan bir tablo kaldığı için oluşuyordu.
    # Mevcut otopark_slotlari tablosunu kontrol et; kat sütunu yoksa
    # tabloyu sil ve sıfırdan oluştur (araç kayıtlarına dokunma).
    if os.path.exists(DB_YOLU):
        kontrol = sqlite3.connect(DB_YOLU)
        try:
            sutunlar = [
                r[1] for r in
                kontrol.execute("PRAGMA table_info(otopark_slotlari)").fetchall()
            ]
            if sutunlar and "kat" not in sutunlar:
                kontrol.close()
                # Eski tabloyu bırak, aşağıda DROP + CREATE yapılacak
                eski_sema = True
                print("⚠️  Eski şema tespit edildi (kat sütunu yok) → tablo sıfırlanıyor.")
            else:
                kontrol.close()
                eski_sema = False
        except Exception:
            kontrol.close()
            eski_sema = False
    else:
        eski_sema = False

    baglanti = sqlite3.connect(DB_YOLU)
    imlec = baglanti.cursor()

    # WAL modu — eş zamanlı erişim için (Java + Python aynı anda bağlanabilir)
    imlec.execute("PRAGMA journal_mode=WAL;")

    # ── ARAÇ KAYITLARI TABLOSU ────────────────────────────────────────
    imlec.execute('''
        CREATE TABLE IF NOT EXISTS arac_kayitlari (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            plaka          TEXT NOT NULL,
            giris_zamani   TEXT DEFAULT (datetime('now','localtime')),
            cikis_zamani   TEXT,
            ucret          REAL DEFAULT 0.0,
            durum          TEXT DEFAULT 'İçeride'
        )
    ''')

    # ── OTOPARK SLOTLARI TABLOSU ──────────────────────────────────────
    # DÜZELTME 3 devamı: eski şema varsa tabloyu sıfırdan kur
    if eski_sema:
        imlec.execute("DROP TABLE IF EXISTS otopark_slotlari")
        print("🗑️  Eski otopark_slotlari tablosu silindi.")

    imlec.execute('''
        CREATE TABLE IF NOT EXISTS otopark_slotlari (
            slot_id          INTEGER PRIMARY KEY,
            kat              INTEGER NOT NULL,
            kat_slot_no      INTEGER NOT NULL,
            slot_etiketi     TEXT NOT NULL,
            durum            TEXT DEFAULT 'Boş',
            park_eden_plaka  TEXT
        )
    ''')

    # Slotları yalnızca tablo boşsa ekle
    imlec.execute("SELECT COUNT(*) FROM otopark_slotlari")
    if imlec.fetchone()[0] == 0:
        slot_id = 1
        for kat in range(1, 4):
            for s in range(1, 11):
                etiket = f"K{kat}-S{s}"
                imlec.execute(
                    "INSERT INTO otopark_slotlari "
                    "(slot_id, kat, kat_slot_no, slot_etiketi, durum) "
                    "VALUES (?, ?, ?, ?, 'Boş')",
                    (slot_id, kat, s, etiket)
                )
                slot_id += 1
        print("✅ 3 kat × 10 slot = 30 slot oluşturuldu.")
    else:
        print("ℹ️  Slotlar zaten mevcut, atlandı.")

    baglanti.commit()
    baglanti.close()
    print(f"✅ Veritabanı hazır: {DB_YOLU}")


if __name__ == "__main__":
    veritabani_olustur()