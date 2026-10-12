"""
Akıllı Otopark — masaüstü yönetim paneli (PyQt6).

Çalıştırma:  python src/otopark_arayuz.py

Kısayollar:
    Boşluk   → kameradaki plakayı oku
    Ctrl+F   → plaka ara
    F5       → verileri yenile
"""
from __future__ import annotations

import csv
import logging
import sys
import time
from datetime import datetime

import cv2
import numpy as np
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

import ayarlar
from plaka_okuma import OkumaSonucu, PlakaOkuyucu, kutu_ciz, plaka_formatla, plakayi_normalize_et, temizle
from veritabani import CIKTI, DOLU, ICERIDE, IslemSonucu, Veritabani, zaman_coz

log = logging.getLogger("otopark")

# ==============================================================
#  TEMA
# ==============================================================
R = {
    "bg": "#0e1217", "panel": "#151b23", "kart": "#1b232d", "kart2": "#212b37",
    "kenar": "#2a3542", "yazi": "#e6edf3", "soluk": "#8b98a5", "vurgu": "#4c8dff",
    "yesil": "#2fbf71", "kirmizi": "#ef5350", "turuncu": "#f5a524",
}

STIL = f"""
* {{ font-family: "Segoe UI", sans-serif; font-size: 10pt; color: {R['yazi']}; }}
QMainWindow, #kok {{ background: {R['bg']}; }}
QToolTip {{ background: {R['kart2']}; color: {R['yazi']}; border: 1px solid {R['kenar']}; padding: 6px; }}

#kart {{ background: {R['kart']}; border: 1px solid {R['kenar']}; border-radius: 12px; }}
#kartBaslik {{ color: {R['soluk']}; font-size: 9pt; font-weight: 600; letter-spacing: 0.5px; }}
#istatDeger {{ font-size: 20pt; font-weight: 700; }}
#istatAlt {{ color: {R['soluk']}; font-size: 9pt; }}
#baslik {{ font-size: 16pt; font-weight: 700; }}
#altBaslik {{ color: {R['soluk']}; }}
#saat {{ color: {R['soluk']}; font-size: 11pt; font-family: "Bahnschrift", "Segoe UI"; }}
#soluk {{ color: {R['soluk']}; }}

QPushButton {{
    background: {R['kart2']}; border: 1px solid {R['kenar']}; border-radius: 8px;
    padding: 8px 14px; font-weight: 600;
}}
QPushButton:hover {{ background: #2a3644; }}
QPushButton:pressed {{ background: #1a222c; }}
QPushButton:disabled {{ color: #5b6672; background: {R['kart']}; }}
QPushButton#birincil {{ background: {R['vurgu']}; border: none; color: white; }}
QPushButton#birincil:hover {{ background: #6aa1ff; }}
QPushButton#birincil:disabled {{ background: #2b3d5c; color: #8ea2c4; }}

QLineEdit, QComboBox {{
    background: {R['panel']}; border: 1px solid {R['kenar']}; border-radius: 8px; padding: 7px 10px;
    selection-background-color: {R['vurgu']};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {R['vurgu']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {R['kart2']}; border: 1px solid {R['kenar']};
    selection-background-color: {R['vurgu']}; outline: none; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; color: {R['soluk']}; padding: 8px 16px; margin-right: 4px;
    border-bottom: 2px solid transparent; font-weight: 600;
}}
QTabBar::tab:selected {{ color: {R['yazi']}; border-bottom-color: {R['vurgu']}; }}
QTabBar::tab:hover {{ color: {R['yazi']}; }}

QTableWidget {{
    background: {R['kart']}; border: 1px solid {R['kenar']}; border-radius: 12px;
    gridline-color: transparent; alternate-background-color: #1e2731;
    selection-background-color: #2c4870;
}}
QTableWidget::item {{ padding: 4px 8px; border: none; }}
QHeaderView::section {{
    background: {R['kart']}; color: {R['soluk']}; border: none; border-bottom: 1px solid {R['kenar']};
    padding: 8px; font-weight: 600; font-size: 9pt;
}}
QTableCornerButton::section {{ background: {R['kart']}; border: none; }}

QPlainTextEdit {{
    background: {R['kart']}; border: 1px solid {R['kenar']}; border-radius: 12px; padding: 8px;
    font-family: "Cascadia Mono", "Consolas", monospace; font-size: 9pt;
}}

QProgressBar {{ background: {R['panel']}; border: none; border-radius: 3px; height: 6px; }}
QProgressBar::chunk {{ background: {R['vurgu']}; border-radius: 3px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {R['kenar']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ height: 0; }}

QMenu {{ background: {R['kart2']}; border: 1px solid {R['kenar']}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: {R['vurgu']}; }}

QStatusBar {{ background: {R['panel']}; color: {R['soluk']}; border-top: 1px solid {R['kenar']}; }}
QStatusBar QLabel {{ color: {R['soluk']}; padding: 0 8px; }}
QSplitter::handle {{ background: transparent; }}

#slot {{ background: {R['kart2']}; border: 1px solid {R['kenar']}; border-radius: 10px; }}
#slot[durum="dolu"] {{ background: #2a1f24; border: 1px solid #5a2e33; }}
#slot[vurgu="true"] {{ border: 2px solid {R['vurgu']}; background: #1d2c45; }}
#slotEtiket {{ color: {R['soluk']}; font-size: 8pt; font-weight: 700; }}
#slotPlaka {{ font-family: "Bahnschrift", "Segoe UI"; font-size: 10pt; font-weight: 600; }}
#slotBos {{ color: {R['yesil']}; font-size: 9pt; }}


#plakaKutu {{ background: #f4f5f7; border: 2px solid #11151a; border-radius: 6px; }}
#plakaTR {{ background: #1f4fbf; color: white; font-weight: 700; font-size: 9pt;
            border-top-left-radius: 4px; border-bottom-left-radius: 4px; }}
#plakaYazi {{ color: #11151a; font-family: "Bahnschrift", "Segoe UI"; font-weight: 700; }}

#cip {{ border-radius: 10px; padding: 3px 10px; font-weight: 700; font-size: 9pt; }}
#buyukDeger {{ font-size: 18pt; font-weight: 700; font-family: "Bahnschrift", "Segoe UI"; }}
"""


def kart_olustur(yatay: bool = False) -> tuple[QFrame, QVBoxLayout | QHBoxLayout]:
    kart = QFrame(objectName="kart")
    yerlesim = QHBoxLayout(kart) if yatay else QVBoxLayout(kart)
    yerlesim.setContentsMargins(16, 14, 16, 14)
    yerlesim.setSpacing(10)
    return kart, yerlesim


def etiket(metin: str = "", ad: str | None = None) -> QLabel:
    lbl = QLabel(metin)
    if ad:
        lbl.setObjectName(ad)
    return lbl


def buton(metin: str, birincil: bool = False) -> QPushButton:
    b = QPushButton(metin)
    if birincil:
        b.setObjectName("birincil")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Boşluk tuşu butonu değil taramayı tetiklesin
    return b


def cip_stili(lbl: QLabel, renk: str):
    c = QColor(renk)
    lbl.setStyleSheet(
        f"background: rgba({c.red()},{c.green()},{c.blue()},40); color: {renk};"
        f" border: 1px solid rgba({c.red()},{c.green()},{c.blue()},110);"
    )


def sure_formatla(saniye: int | None) -> str:
    if saniye is None:
        return "—"
    saat, kalan = divmod(int(saniye), 3600)
    dakika, sn = divmod(kalan, 60)
    if saat:
        return f"{saat} sa {dakika:02d} dk"
    if dakika:
        return f"{dakika} dk {sn:02d} sn"
    return f"{sn} sn"


def para(tutar: float) -> str:
    return f"{tutar:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")


def kare_to_pixmap(kare: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(kare, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    return QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy())


# ==============================================================
#  ARKA PLAN İŞLERİ
# ==============================================================
class GunlukKoprusu(QObject):
    """logging kayıtlarını (her iş parçacığından) arayüze güvenle taşır."""
    mesaj = pyqtSignal(str, int)


class GunlukIsleyici(logging.Handler):
    def __init__(self, kopru: GunlukKoprusu):
        super().__init__()
        self.kopru = kopru
        self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, kayit):
        self.kopru.mesaj.emit(self.format(kayit), kayit.levelno)


class KameraIsi(QThread):
    kare = pyqtSignal(object)
    hata = pyqtSignal(str)

    def __init__(self, kamera_no: int):
        super().__init__()
        self.kamera_no = kamera_no
        self._calis = True

    def run(self):
        api = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.kamera_no, api)
        if not cap.isOpened():
            self.hata.emit(f"Kamera {self.kamera_no} açılamadı.")
            return
        hatali = 0
        while self._calis:
            ok, kare = cap.read()
            if not ok:
                hatali += 1
                if hatali > 50:
                    self.hata.emit("Kameradan görüntü alınamıyor.")
                    break
                self.msleep(50)
                continue
            hatali = 0
            self.kare.emit(kare)
            self.msleep(15)
        cap.release()

    def durdur(self):
        self._calis = False
        self.wait(2000)


class ModelYukleIsi(QThread):
    hazir = pyqtSignal()
    hata = pyqtSignal(str)

    def __init__(self, okuyucu: PlakaOkuyucu):
        super().__init__()
        self.okuyucu = okuyucu

    def run(self):
        try:
            self.okuyucu.yukle()
            self.hazir.emit()
        except Exception as e:  # noqa: BLE001 — her hatayı kullanıcıya göstermek istiyoruz
            self.hata.emit(str(e))


class TaramaIsi(QThread):
    bitti = pyqtSignal(object)  # OkumaSonucu | None
    hata = pyqtSignal(str)

    def __init__(self, okuyucu: PlakaOkuyucu, kare: np.ndarray):
        super().__init__()
        self.okuyucu = okuyucu
        self.kare_ = kare

    def run(self):
        try:
            self.bitti.emit(self.okuyucu.oku(self.kare_))
        except Exception as e:  # noqa: BLE001
            self.hata.emit(str(e))


# ==============================================================
#  BİLEŞENLER
# ==============================================================
class PlakaRozeti(QFrame):
    """Türk plakası görünümünde etiket."""

    def __init__(self, boyut: int = 22):
        super().__init__(objectName="plakaKutu")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        tr = etiket("TR", "plakaTR")
        tr.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        tr.setFixedWidth(int(boyut * 1.2))
        tr.setContentsMargins(0, 0, 0, 4)
        self.yazi = etiket("— — —", "plakaYazi")
        self.yazi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.yazi.setStyleSheet(f"font-size: {boyut}pt; padding: 2px 16px;")
        lay.addWidget(tr)
        lay.addWidget(self.yazi, 1)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def ayarla(self, plaka: str | None):
        self.yazi.setText(plaka_formatla(plaka) if plaka else "— — —")


class KameraGorunumu(QWidget):
    """Görüntüyü her zaman kendi alanına sığdırarak (oranı koruyarak) çizer."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._pixmap: QPixmap | None = None
        self._metin = ""

    def goster(self, pixmap: QPixmap):
        self._pixmap, self._metin = pixmap, ""
        self.update()

    def mesaj(self, metin: str):
        self._pixmap, self._metin = None, metin
        self.update()

    def paintEvent(self, _olay):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#07090c"))
        p.drawRoundedRect(self.rect(), 10, 10)
        if self._pixmap is not None and not self._pixmap.isNull():
            pm = self._pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((self.width() - pm.width()) // 2, (self.height() - pm.height()) // 2, pm)
        elif self._metin:
            p.setPen(QColor(R["soluk"]))
            p.drawText(self.rect().adjusted(20, 20, -20, -20),
                       Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._metin)
        p.end()


class IstatistikKarti(QFrame):
    def __init__(self, baslik: str, ilerleme: bool = False):
        super().__init__(objectName="kart")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        lay.addWidget(etiket(baslik.upper(), "kartBaslik"))
        self.deger = etiket("—", "istatDeger")
        lay.addWidget(self.deger)
        self.alt = etiket("", "istatAlt")
        lay.addWidget(self.alt)
        self.cubuk = None
        if ilerleme:
            self.cubuk = QProgressBar(textVisible=False)
            self.cubuk.setFixedHeight(6)
            lay.addSpacing(4)
            lay.addWidget(self.cubuk)

    def ayarla(self, deger: str, alt: str = "", oran: float | None = None):
        self.deger.setText(deger)
        self.alt.setText(alt)
        if self.cubuk is not None and oran is not None:
            self.cubuk.setValue(int(oran * 100))
            renk = R["kirmizi"] if oran >= 0.9 else R["turuncu"] if oran >= 0.7 else R["yesil"]
            self.cubuk.setStyleSheet(f"QProgressBar::chunk {{ background: {renk}; border-radius: 3px; }}")


class SlotKarti(QFrame):
    cikis_istendi = pyqtSignal(str)

    def __init__(self, etiket_metni: str):
        super().__init__(objectName="slot")
        self.setMinimumSize(96, 62)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.plaka: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        ust = QHBoxLayout()
        self.nokta = QLabel()
        self.nokta.setFixedSize(8, 8)
        ust.addWidget(etiket(etiket_metni, "slotEtiket"))
        ust.addStretch()
        ust.addWidget(self.nokta)
        lay.addLayout(ust)
        self.icerik = QLabel()
        lay.addWidget(self.icerik)
        lay.addStretch()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def ayarla(self, plaka: str | None, giris: str | None):
        self.plaka = plaka
        dolu = bool(plaka)
        self.setProperty("durum", "dolu" if dolu else "bos")
        self.nokta.setStyleSheet(
            f"background: {R['kirmizi'] if dolu else R['yesil']}; border-radius: 4px;")
        if dolu:
            self.icerik.setObjectName("slotPlaka")
            self.icerik.setText(plaka_formatla(plaka))
            g = zaman_coz(giris)
            sure = sure_formatla((datetime.now() - g).total_seconds()) if g else "?"
            self.setToolTip(f"<b>{plaka_formatla(plaka)}</b><br>Giriş: {giris or '?'}<br>"
                            f"Süre: {sure}<br><i>Sağ tık → çıkış yap</i>")
        else:
            self.icerik.setObjectName("slotBos")
            self.icerik.setText("Boş")
            self.setToolTip("")
        self._yenile_stil()

    def vurgula(self, acik: bool):
        if self.property("vurgu") != acik:
            self.setProperty("vurgu", acik)
            self._yenile_stil()

    def _yenile_stil(self):
        for w in (self, self.icerik):
            w.style().unpolish(w)
            w.style().polish(w)

    def _menu(self, konum):
        if not self.plaka:
            return
        menu = QMenu(self)
        eylem = QAction(f"{plaka_formatla(self.plaka)} için çıkış yap", menu)
        eylem.triggered.connect(lambda: self.cikis_istendi.emit(self.plaka))
        menu.addAction(eylem)
        menu.exec(self.mapToGlobal(konum))


class OtoparkHaritasi(QWidget):
    cikis_istendi = pyqtSignal(str)
    SUTUN = 5

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)
        self.kartlar: dict[int, SlotKarti] = {}
        self.kat_ozet: dict[int, QLabel] = {}
        self.kat_kutulari: dict[int, QGridLayout] = {}
        for kat in range(1, ayarlar.KAT_SAYISI + 1):
            kart, kl = kart_olustur()
            ust = QHBoxLayout()
            ust.addWidget(etiket(f"KAT {kat}", "kartBaslik"))
            ust.addStretch()
            self.kat_ozet[kat] = etiket("", "istatAlt")
            ust.addWidget(self.kat_ozet[kat])
            kl.addLayout(ust)
            izgara = QGridLayout()
            izgara.setSpacing(8)
            for s in range(1, ayarlar.KAT_BASINA_SLOT + 1):
                izgara.setColumnStretch((s - 1) % self.SUTUN, 1)
            self.kat_kutulari[kat] = izgara
            kl.addLayout(izgara)
            lay.addWidget(kart, 1)

        lejant = QHBoxLayout()
        for renk, ad in ((R["yesil"], "Boş"), (R["kirmizi"], "Dolu"), (R["vurgu"], "Arama sonucu")):
            n = QLabel()
            n.setFixedSize(10, 10)
            n.setStyleSheet(f"background: {renk}; border-radius: 5px;")
            lejant.addWidget(n)
            lejant.addWidget(etiket(ad, "soluk"))
            lejant.addSpacing(12)
        lejant.addStretch()
        lejant.addWidget(etiket("İpucu: dolu slota sağ tıklayarak manuel çıkış yapabilirsiniz.", "soluk"))
        lay.addLayout(lejant)

    def guncelle(self, slotlar):
        kat_dolu: dict[int, int] = {}
        kat_toplam: dict[int, int] = {}
        for s in slotlar:
            kart = self.kartlar.get(s["slot_id"])
            if kart is None:
                kart = SlotKarti(s["slot_etiketi"])
                kart.cikis_istendi.connect(self.cikis_istendi)
                izgara = self.kat_kutulari.get(s["kat"])
                if izgara is None:
                    continue
                i = s["kat_slot_no"] - 1
                izgara.addWidget(kart, i // self.SUTUN, i % self.SUTUN)
                self.kartlar[s["slot_id"]] = kart
            dolu = s["durum"] == DOLU and s["park_eden_plaka"]
            kart.ayarla(s["park_eden_plaka"] if dolu else None, s["giris_zamani"])
            kat_toplam[s["kat"]] = kat_toplam.get(s["kat"], 0) + 1
            kat_dolu[s["kat"]] = kat_dolu.get(s["kat"], 0) + (1 if dolu else 0)
        for kat, lbl in self.kat_ozet.items():
            t = kat_toplam.get(kat, 0)
            d = kat_dolu.get(kat, 0)
            lbl.setText(f"{d}/{t} dolu  ·  {t - d} boş")

    def ara(self, sorgu: str) -> list[SlotKarti]:
        eslesen = []
        for kart in self.kartlar.values():
            uygun = bool(sorgu) and bool(kart.plaka) and sorgu in kart.plaka
            kart.vurgula(uygun)
            if uygun:
                eslesen.append(kart)
        return eslesen


class SonIslemKarti(QFrame):
    def __init__(self):
        super().__init__(objectName="kart")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        ust = QHBoxLayout()
        ust.addWidget(etiket("SON İŞLEM", "kartBaslik"))
        ust.addStretch()
        self.cip = etiket("BEKLENİYOR", "cip")
        cip_stili(self.cip, R["soluk"])
        ust.addWidget(self.cip)
        lay.addLayout(ust)

        orta = QHBoxLayout()
        orta.setSpacing(14)
        self.kirpim = QLabel()
        self.kirpim.setFixedSize(150, 50)
        self.kirpim.setStyleSheet(f"background: {R['panel']}; border-radius: 6px;")
        self.kirpim.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.kirpim.hide()
        self.rozet = PlakaRozeti(20)
        orta.addWidget(self.rozet)
        orta.addStretch()
        orta.addWidget(self.kirpim)
        lay.addLayout(orta)

        self.aciklama = etiket("Kameradan plaka okutun veya manuel plaka girin.", "soluk")
        self.aciklama.setWordWrap(True)
        lay.addWidget(self.aciklama)

        izgara = QGridLayout()
        izgara.setHorizontalSpacing(18)
        izgara.setVerticalSpacing(0)
        self.degerler = {}
        for i, (anahtar, baslik) in enumerate(
                (("slot", "SLOT"), ("zaman", "ZAMAN"), ("sure", "SÜRE"), ("ucret", "ÜCRET"))):
            izgara.addWidget(etiket(baslik, "kartBaslik"), 0, i)
            d = etiket("—", "buyukDeger")
            izgara.addWidget(d, 1, i)
            self.degerler[anahtar] = d
        lay.addLayout(izgara)

    def _durum(self, metin: str, renk: str):
        self.cip.setText(metin)
        cip_stili(self.cip, renk)

    def _kirpim_goster(self, kirpim: np.ndarray | None):
        if kirpim is None or kirpim.size == 0:
            self.kirpim.clear()
            self.kirpim.hide()
            return
        self.kirpim.show()
        pm = kare_to_pixmap(kirpim).scaled(
            self.kirpim.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self.kirpim.setPixmap(pm)

    def _degerler(self, slot="—", zaman="—", sure="—", ucret="—"):
        for k, v in (("slot", slot), ("zaman", zaman), ("sure", sure), ("ucret", ucret)):
            self.degerler[k].setText(v)

    def islem_goster(self, s: IslemSonucu, kirpim: np.ndarray | None = None):
        self.rozet.ayarla(s.plaka)
        self._kirpim_goster(kirpim)
        saat = s.zaman.strftime("%H:%M:%S")
        if s.tur == "giris":
            self._durum("GİRİŞ", R["yesil"])
            self.aciklama.setText(f"Araç içeri alındı. Lütfen <b>Kat {s.kat}</b>, "
                                  f"<b>{s.slot_etiketi}</b> numaralı alana park edin.")
            self._degerler(s.slot_etiketi or "—", saat, "0 sn", "—")
        elif s.tur == "cikis":
            self._durum("ÇIKIŞ", R["turuncu"])
            giris = s.giris_zamani.strftime("%H:%M:%S") if s.giris_zamani else "?"
            self.aciklama.setText(f"Çıkış onaylandı. Giriş saati: {giris}. Ödeme alınarak bariyer açılabilir.")
            self._degerler(s.slot_etiketi or "—", saat, sure_formatla(s.sure_saniye), para(s.ucret or 0))
        else:  # dolu
            self._durum("OTOPARK DOLU", R["kirmizi"])
            self.aciklama.setText("Boş slot kalmadığı için araç içeri alınmadı.")
            self._degerler(zaman=saat)

    def uyari_goster(self, baslik: str, mesaj: str, plaka: str | None = None,
                     kirpim: np.ndarray | None = None, renk: str = R["soluk"]):
        self._durum(baslik, renk)
        self.rozet.ayarla(plaka)
        self._kirpim_goster(kirpim)
        self.aciklama.setText(mesaj)
        self._degerler(zaman=datetime.now().strftime("%H:%M:%S"))


# ==============================================================
#  ANA PENCERE
# ==============================================================
class AnaPencere(QMainWindow):
    TABLO_SUTUNLARI = ("#", "Plaka", "Slot", "Giriş", "Çıkış", "Süre", "Ücret", "Durum")

    def __init__(self, db: Veritabani, kopru: GunlukKoprusu):
        super().__init__()
        self.db = db
        self.okuyucu = PlakaOkuyucu()
        self.kamera: KameraIsi | None = None
        self.tarama: TaramaIsi | None = None
        self.model_isi: ModelYukleIsi | None = None
        self.son_kare: np.ndarray | None = None
        self.sabit_goruntu = False       # fotoğraftan okuma modunda kamerayı göstermeyiz
        self.cerceve: tuple | None = None  # (kutu, metin, renk, bitiş zamanı)
        self.son_okumalar: dict[str, float] = {}
        self._veri_surumu = -1

        self.setWindowTitle("Akıllı Otopark — Yönetim Paneli")
        self.resize(1440, 880)
        self.setMinimumSize(1180, 720)
        self._arayuz_kur()
        kopru.mesaj.connect(self._gunluk_ekle)

        self.saat_zamanlayici = QTimer(self, timeout=self._saat_guncelle, interval=1000)
        self.saat_zamanlayici.start()
        self._saat_guncelle()
        # Başka bir program (Java paneli vb.) veritabanını değiştirirse otomatik yenile
        self.db_zamanlayici = QTimer(self, timeout=self._dis_degisiklik_kontrol, interval=2000)
        self.db_zamanlayici.start()

        self.verileri_yenile()
        self.kamerayi_baslat()
        self.modelleri_yukle()

    # ── Arayüz kurulumu ─────────────────────────────────────────────
    def _arayuz_kur(self):
        kok = QWidget(objectName="kok")
        self.setCentralWidget(kok)
        ana = QVBoxLayout(kok)
        ana.setContentsMargins(20, 16, 20, 12)
        ana.setSpacing(14)

        # Üst çubuk
        ust = QHBoxLayout()
        logo = QLabel("P")
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(f"background: {R['vurgu']}; color: white; border-radius: 10px;"
                           f" font-size: 18pt; font-weight: 800;")
        ust.addWidget(logo)
        basliklar = QVBoxLayout()
        basliklar.setSpacing(0)
        basliklar.addWidget(etiket("Akıllı Otopark", "baslik"))
        basliklar.addWidget(etiket("Plaka tanıma ve yönetim paneli", "altBaslik"))
        ust.addLayout(basliklar)
        ust.addStretch()
        self.arama = QLineEdit(placeholderText="🔍  Plaka ara…  (Ctrl+F)")
        self.arama.setFixedWidth(280)
        self.arama.setClearButtonEnabled(True)
        self.arama.textChanged.connect(self._arama_degisti)
        self.arama.returnPressed.connect(self._arama_onayla)
        ust.addWidget(self.arama)
        ust.addSpacing(12)
        self.saat = etiket("", "saat")
        ust.addWidget(self.saat)
        ana.addLayout(ust)

        # İstatistik kartları
        istat = QHBoxLayout()
        istat.setSpacing(14)
        self.k_doluluk = IstatistikKarti("Doluluk", ilerleme=True)
        self.k_iceride = IstatistikKarti("İçerideki araç")
        self.k_giris = IstatistikKarti("Bugünkü giriş")
        self.k_gelir = IstatistikKarti("Bugünkü gelir")
        for k in (self.k_doluluk, self.k_iceride, self.k_giris, self.k_gelir):
            istat.addWidget(k, 1)
        ana.addLayout(istat)

        # Gövde
        bolucu = QSplitter(Qt.Orientation.Horizontal)
        bolucu.setHandleWidth(14)
        bolucu.addWidget(self._sol_panel())
        bolucu.addWidget(self._sag_panel())
        bolucu.setStretchFactor(0, 5)
        bolucu.setStretchFactor(1, 6)
        bolucu.setSizes([620, 760])
        ana.addWidget(bolucu, 1)

        # Durum çubuğu
        self.model_durumu = QLabel("● Model yükleniyor…")
        self.statusBar().addWidget(self.model_durumu)
        self.statusBar().addPermanentWidget(QLabel(f"Veritabanı: {self.db.yol}"))

        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.arama.setFocus(), self.arama.selectAll()))
        QShortcut(QKeySequence("F5"), self, activated=self.verileri_yenile)
        QShortcut(QKeySequence("Escape"), self, activated=self._odak_birak)
        # Metin kutuları boşluğu kendileri alır; diğer her yerde boşluk = plaka oku
        bosluk = QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self.plaka_oku)
        bosluk.setAutoRepeat(False)

    def _sol_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        # Kamera kartı
        kart, kl = kart_olustur()
        ust = QHBoxLayout()
        ust.addWidget(etiket("CANLI KAMERA", "kartBaslik"))
        ust.addStretch()
        self.kamera_durum = etiket("", "cip")
        ust.addWidget(self.kamera_durum)
        kl.addLayout(ust)

        self.goruntu = KameraGorunumu()
        self.goruntu.mesaj("Kamera başlatılıyor…")
        kl.addWidget(self.goruntu, 1)

        butonlar = QHBoxLayout()
        self.b_oku = buton("Plakayı Oku  (Boşluk)", birincil=True)
        self.b_oku.setEnabled(False)
        self.b_oku.clicked.connect(self.plaka_oku)
        self.b_kamera = buton("Kamerayı Durdur")
        self.b_kamera.clicked.connect(self._kamera_degistir)
        self.b_foto = buton("Fotoğraftan Oku…")
        self.b_foto.clicked.connect(self._fotograf_ac)
        butonlar.addWidget(self.b_oku, 2)
        butonlar.addWidget(self.b_kamera, 1)
        butonlar.addWidget(self.b_foto, 1)
        kl.addLayout(butonlar)
        lay.addWidget(kart, 1)

        # Manuel giriş
        kart, kl = kart_olustur()
        kl.addWidget(etiket("MANUEL İŞLEM", "kartBaslik"))
        satir = QHBoxLayout()
        self.manuel = QLineEdit(placeholderText="Plaka girin, ör. 34ABC123")
        self.manuel.setMaxLength(12)
        self.manuel.textEdited.connect(lambda t: self.manuel.setText(t.upper()))
        self.manuel.returnPressed.connect(self._manuel_isle)
        b = buton("Giriş / Çıkış İşle")
        b.clicked.connect(self._manuel_isle)
        satir.addWidget(self.manuel, 1)
        satir.addWidget(b)
        kl.addLayout(satir)
        lay.addWidget(kart)

        self.son_islem = SonIslemKarti()
        lay.addWidget(self.son_islem)
        return w

    def _sag_panel(self) -> QWidget:
        self.sekmeler = QTabWidget()
        self.harita = OtoparkHaritasi()
        self.harita.cikis_istendi.connect(self._manuel_cikis)
        self.sekmeler.addTab(self.harita, "Otopark Haritası")

        # Kayıtlar sekmesi
        kayit_w = QWidget()
        kl = QVBoxLayout(kayit_w)
        kl.setContentsMargins(0, 8, 0, 0)
        kl.setSpacing(10)
        filtre = QHBoxLayout()
        self.kayit_arama = QLineEdit(placeholderText="Plakaya göre filtrele")
        self.kayit_arama.textChanged.connect(self.kayitlari_yenile)
        self.durum_filtre = QComboBox()
        self.durum_filtre.addItems(["Tüm kayıtlar", ICERIDE, CIKTI])
        self.durum_filtre.currentIndexChanged.connect(self.kayitlari_yenile)
        b_csv = buton("CSV olarak dışa aktar")
        b_csv.clicked.connect(self._csv_aktar)
        filtre.addWidget(self.kayit_arama, 2)
        filtre.addWidget(self.durum_filtre, 1)
        filtre.addWidget(b_csv)
        kl.addLayout(filtre)

        self.tablo = QTableWidget(0, len(self.TABLO_SUTUNLARI))
        self.tablo.setHorizontalHeaderLabels(self.TABLO_SUTUNLARI)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.setShowGrid(False)
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tablo.verticalHeader().setDefaultSectionSize(34)
        baslik = self.tablo.horizontalHeader()
        baslik.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        baslik.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        baslik.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.tablo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tablo.customContextMenuRequested.connect(self._tablo_menu)
        kl.addWidget(self.tablo, 1)
        self.kayit_ozet = etiket("", "soluk")
        kl.addWidget(self.kayit_ozet)
        self.sekmeler.addTab(kayit_w, "Araç Kayıtları")

        # Günlük sekmesi
        self.gunluk = QPlainTextEdit(readOnly=True)
        self.gunluk.setMaximumBlockCount(1000)
        g = QWidget()
        gl = QVBoxLayout(g)
        gl.setContentsMargins(0, 8, 0, 0)
        gl.addWidget(self.gunluk)
        self.sekmeler.addTab(g, "Olay Günlüğü")
        return self.sekmeler

    # ── Veri ────────────────────────────────────────────────────────
    def verileri_yenile(self):
        try:
            ist = self.db.istatistikler()
            self.harita.guncelle(self.db.slotlar())
            self.kayitlari_yenile()
            self._veri_surumu = self.db.veri_surumu()
        except Exception as e:  # noqa: BLE001
            log.error("Veriler okunamadı: %s", e)
            return
        toplam, dolu = ist["toplam_slot"], ist["dolu_slot"]
        oran = dolu / toplam if toplam else 0
        self.k_doluluk.ayarla(f"{dolu} / {toplam}", f"%{oran * 100:.0f} dolu  ·  {toplam - dolu} boş yer", oran)
        self.k_iceride.ayarla(str(ist["iceride"]), "şu an otoparkta")
        self.k_giris.ayarla(str(ist["bugun_giris"]), datetime.now().strftime("%d.%m.%Y"))
        self.k_gelir.ayarla(para(ist["bugun_gelir"]), "tamamlanan çıkışlardan")
        self._arama_degisti(self.arama.text())

    def _dis_degisiklik_kontrol(self):
        try:
            if self.db.veri_surumu() != self._veri_surumu:
                self.verileri_yenile()
        except Exception:  # noqa: BLE001
            pass

    def kayitlari_yenile(self):
        durum = self.durum_filtre.currentText()
        satirlar = self.db.kayitlar(temizle(self.kayit_arama.text()),
                                    None if durum == "Tüm kayıtlar" else durum)
        self.tablo.setRowCount(len(satirlar))
        simdi = datetime.now()
        for i, r in enumerate(satirlar):
            giris, cikis = zaman_coz(r["giris_zamani"]), zaman_coz(r["cikis_zamani"])
            icerde = r["durum"] == ICERIDE
            sure = (simdi if icerde else cikis or simdi) - giris if giris else None
            hucreler = (
                str(r["id"]),
                plaka_formatla(r["plaka"]),
                r["slot_etiketi"] or "—",
                giris.strftime("%d.%m %H:%M:%S") if giris else "—",
                cikis.strftime("%d.%m %H:%M:%S") if cikis else "—",
                sure_formatla(sure.total_seconds()) if sure is not None else "—",
                "—" if icerde else para(r["ucret"] or 0),
                r["durum"] or "",
            )
            for j, metin in enumerate(hucreler):
                oge = QTableWidgetItem(metin)
                if j == 0:
                    oge.setData(Qt.ItemDataRole.UserRole, r["id"])
                    oge.setForeground(QColor(R["soluk"]))
                elif j == 1:
                    oge.setFont(QFont("Bahnschrift", 10, QFont.Weight.DemiBold))
                elif j == 7:
                    oge.setForeground(QColor(R["yesil"] if icerde else R["soluk"]))
                self.tablo.setItem(i, j, oge)
        self.kayit_ozet.setText(f"{len(satirlar)} kayıt gösteriliyor"
                                + ("  (en yeni 500)" if len(satirlar) == 500 else ""))

    # ── Kamera ──────────────────────────────────────────────────────
    def kamerayi_baslat(self):
        self.kamerayi_durdur()
        self.sabit_goruntu = False
        self.kamera = KameraIsi(ayarlar.KAMERA_NO)
        self.kamera.kare.connect(self._kare_geldi)
        self.kamera.hata.connect(self._kamera_hatasi)
        self.kamera.start()
        self.b_kamera.setText("Kamerayı Durdur")
        self._kamera_cip("CANLI", R["yesil"])

    def kamerayi_durdur(self):
        if self.kamera is not None:
            self.kamera.kare.disconnect()
            self.kamera.durdur()
            self.kamera = None
        self.b_kamera.setText("Kamerayı Başlat")
        self._kamera_cip("KAPALI", R["soluk"])

    def _kamera_degistir(self):
        if self.kamera is not None and not self.sabit_goruntu:
            self.kamerayi_durdur()
            self.son_kare = None
            self.goruntu.mesaj("Kamera durduruldu.")
            self._oku_butonu_guncelle()
        else:
            self.kamerayi_baslat()

    def _kamera_cip(self, metin: str, renk: str):
        self.kamera_durum.setText(f"● {metin}")
        cip_stili(self.kamera_durum, renk)

    def _kamera_hatasi(self, mesaj: str):
        log.error(mesaj)
        self.kamera = None
        self.son_kare = None
        self.goruntu.mesaj(f"📷  {mesaj}\n\nKamerayı kontrol edip “Kamerayı Başlat”a basın\n"
                             f"veya “Fotoğraftan Oku” ile bir görsel seçin.")
        self.b_kamera.setText("Kamerayı Başlat")
        self._kamera_cip("BAĞLANTI YOK", R["kirmizi"])
        self._oku_butonu_guncelle()

    def _kare_geldi(self, kare: np.ndarray):
        if self.sabit_goruntu:
            return
        ilk = self.son_kare is None
        self.son_kare = kare
        self._goruntuyu_ciz()
        if ilk:
            self._oku_butonu_guncelle()

    def _goruntuyu_ciz(self):
        if self.son_kare is None:
            return
        kare = self.son_kare
        if self.cerceve and (self.sabit_goruntu or time.monotonic() < self.cerceve[3]):
            kare = kare.copy()
            kutu_ciz(kare, *self.cerceve[:3])
        self.goruntu.goster(kare_to_pixmap(kare))

    def _fotograf_ac(self):
        yol, _ = QFileDialog.getOpenFileName(
            self, "Plaka fotoğrafı seç", str(ayarlar.PROJE_KLASORU),
            "Görseller (*.jpg *.jpeg *.png *.bmp *.webp)")
        if not yol:
            return
        # cv2.imread Türkçe karakterli yolları okuyamadığı için imdecode kullanılıyor
        kare = cv2.imdecode(np.fromfile(yol, dtype=np.uint8), cv2.IMREAD_COLOR)
        if kare is None:
            QMessageBox.warning(self, "Fotoğraf açılamadı", "Seçilen dosya okunamadı.")
            return
        self.kamerayi_durdur()
        self.sabit_goruntu = True
        self.cerceve = None
        self.son_kare = kare
        self._kamera_cip("FOTOĞRAF", R["vurgu"])
        self.b_kamera.setText("Kameraya Dön")
        self._goruntuyu_ciz()
        self._oku_butonu_guncelle()
        log.info("Fotoğraf yüklendi: %s", yol)
        if self.okuyucu.hazir:
            self.plaka_oku()

    # ── Plaka okuma ─────────────────────────────────────────────────
    def modelleri_yukle(self):
        self.model_isi = ModelYukleIsi(self.okuyucu)
        self.model_isi.hazir.connect(self._model_hazir)
        self.model_isi.hata.connect(self._model_hatasi)
        self.model_isi.start()

    def _model_hazir(self):
        self.model_durumu.setText("● Plaka tanıma hazır")
        self.model_durumu.setStyleSheet(f"color: {R['yesil']};")
        self._oku_butonu_guncelle()

    def _model_hatasi(self, mesaj: str):
        log.error("Model yüklenemedi: %s", mesaj)
        self.model_durumu.setText("● Plaka tanıma kullanılamıyor — manuel giriş yapılabilir")
        self.model_durumu.setStyleSheet(f"color: {R['kirmizi']};")

    def _oku_butonu_guncelle(self):
        mesgul = self.tarama is not None
        self.b_oku.setEnabled(self.okuyucu.hazir and self.son_kare is not None and not mesgul)
        self.b_oku.setText("Okunuyor…" if mesgul else "Plakayı Oku  (Boşluk)")

    def plaka_oku(self):
        if not self.b_oku.isEnabled():
            return
        self.tarama = TaramaIsi(self.okuyucu, self.son_kare.copy())
        self.tarama.bitti.connect(self._tarama_bitti)
        self.tarama.hata.connect(self._tarama_hatasi)
        self.tarama.finished.connect(self._tarama_temizle)
        self._oku_butonu_guncelle()
        self.tarama.start()
        log.info("Kare analiz ediliyor…")

    def _tarama_temizle(self):
        self.tarama.deleteLater()
        self.tarama = None
        self._oku_butonu_guncelle()

    def _tarama_hatasi(self, mesaj: str):
        log.error("Okuma hatası: %s", mesaj)
        self.son_islem.uyari_goster("HATA", f"Okuma sırasında hata oluştu: {mesaj}", renk=R["kirmizi"])

    def _tarama_bitti(self, sonuc: OkumaSonucu | None):
        if sonuc is None:
            self.son_islem.uyari_goster(
                "OKUNAMADI", "Görüntüde geçerli bir Türk plakası okunamadı. "
                "Aracı kameraya daha net gösterip tekrar deneyin.", renk=R["turuncu"])
            return
        log.info("Okunan plaka: %s (güven %.2f)", sonuc.plaka, sonuc.guven)

        simdi = time.monotonic()
        onceki = self.son_okumalar.get(sonuc.plaka)
        if onceki and simdi - onceki < ayarlar.TEKRAR_OKUMA_SURESI:
            kalan = ayarlar.TEKRAR_OKUMA_SURESI - (simdi - onceki)
            log.warning("%s az önce işlendi, tekrar okuma yok sayıldı.", sonuc.plaka)
            self.cerceve = (sonuc.kutu, sonuc.plaka, (60, 165, 245), simdi + 2.5)
            self.son_islem.uyari_goster(
                "TEKRAR OKUMA", f"Bu plaka az önce işlendi. Yanlışlıkla çıkış yapılmaması için "
                f"{kalan:.0f} sn sonra tekrar deneyin.", sonuc.plaka, sonuc.kirpim, R["turuncu"])
            self._goruntuyu_ciz()
            return
        self.son_okumalar[sonuc.plaka] = simdi

        islem = self._isle(sonuc.plaka, sonuc.kirpim)
        if islem:
            metin = sonuc.plaka + (f" -> {islem.slot_etiketi}" if islem.tur == "giris" else
                                   "  CIKIS" if islem.tur == "cikis" else "  DOLU")
            renk = {"giris": (113, 191, 47), "cikis": (36, 165, 245)}.get(islem.tur, (80, 83, 239))
            self.cerceve = (sonuc.kutu, metin, renk, simdi + 3)
            self._goruntuyu_ciz()

    def _isle(self, plaka: str, kirpim=None) -> IslemSonucu | None:
        try:
            sonuc = self.db.arac_isle(plaka)
        except Exception as e:  # noqa: BLE001
            log.error("Veritabanı hatası: %s", e)
            QMessageBox.critical(self, "Veritabanı hatası", str(e))
            return None
        self.son_islem.islem_goster(sonuc, kirpim)
        self.verileri_yenile()
        return sonuc

    def _manuel_isle(self):
        ham = self.manuel.text()
        plaka = plakayi_normalize_et(ham)
        if not plaka:
            QMessageBox.warning(self, "Geçersiz plaka",
                                f"“{ham}” geçerli bir Türk plakası değil.\nÖrnek: 34 ABC 123, 06 A 1234")
            return
        self.manuel.clear()
        self._isle(plaka)

    def _manuel_cikis(self, plaka: str):
        cevap = QMessageBox.question(
            self, "Çıkış onayı", f"{plaka_formatla(plaka)} plakalı araç için çıkış yapılsın mı?")
        if cevap != QMessageBox.StandardButton.Yes:
            return
        try:
            sonuc = self.db.cikis_yap(plaka)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Veritabanı hatası", str(e))
            return
        self.son_islem.islem_goster(sonuc)
        self.verileri_yenile()

    # ── Arama ───────────────────────────────────────────────────────
    def _arama_degisti(self, metin: str):
        self.harita.ara(temizle(metin))

    def _arama_onayla(self):
        sorgu = temizle(self.arama.text())
        if not sorgu:
            return
        self.sekmeler.setCurrentWidget(self.harita)
        eslesen = self.harita.ara(sorgu)
        if not eslesen:
            self.statusBar().showMessage(f"“{sorgu}” otoparkta bulunamadı.", 5000)
            log.info("Sorgu: %s otoparkta bulunamadı.", sorgu)
        else:
            for kart in eslesen:
                kat, et = self.db.plaka_konumu(kart.plaka)
                log.info("Sorgu: %s → %s (Kat %s)", kart.plaka, et, kat)
            ozet = ", ".join(f"{plaka_formatla(k.plaka)}" for k in eslesen[:3])
            self.statusBar().showMessage(f"{len(eslesen)} araç bulundu: {ozet}", 6000)

    def _odak_birak(self):
        if self.arama.hasFocus() and self.arama.text():
            self.arama.clear()
        self.setFocus()

    # ── Kayıt tablosu işlemleri ─────────────────────────────────────
    def _tablo_menu(self, konum):
        satir = self.tablo.rowAt(konum.y())
        if satir < 0:
            return
        kayit_id = self.tablo.item(satir, 0).data(Qt.ItemDataRole.UserRole)
        plaka = self.tablo.item(satir, 1).text()
        menu = QMenu(self)
        sil = menu.addAction(f"#{kayit_id} kaydını sil")
        if menu.exec(self.tablo.viewport().mapToGlobal(konum)) is sil:
            cevap = QMessageBox.question(
                self, "Kaydı sil", f"#{kayit_id} ({plaka}) kaydı kalıcı olarak silinsin mi?\n"
                "Araç içerideyse park ettiği slot da boşaltılır.")
            if cevap == QMessageBox.StandardButton.Yes:
                self.db.kayit_sil(kayit_id)
                log.info("#%s kaydı silindi.", kayit_id)
                self.verileri_yenile()

    def _csv_aktar(self):
        yol, _ = QFileDialog.getSaveFileName(
            self, "Kayıtları dışa aktar",
            str(ayarlar.PROJE_KLASORU / f"otopark_kayitlari_{datetime.now():%Y%m%d_%H%M}.csv"),
            "CSV (*.csv)")
        if not yol:
            return
        durum = self.durum_filtre.currentText()
        satirlar = self.db.kayitlar(temizle(self.kayit_arama.text()),
                                    None if durum == "Tüm kayıtlar" else durum, limit=-1)
        # utf-8-sig + ';' → Türkçe Excel'de doğrudan doğru açılır
        with open(yol, "w", newline="", encoding="utf-8-sig") as f:
            yazici = csv.writer(f, delimiter=";")
            yazici.writerow(["ID", "Plaka", "Slot", "Giriş", "Çıkış", "Ücret (₺)", "Durum"])
            for r in satirlar:
                yazici.writerow([r["id"], r["plaka"], r["slot_etiketi"] or "", r["giris_zamani"] or "",
                                 r["cikis_zamani"] or "", f"{r['ucret'] or 0:.2f}".replace(".", ","),
                                 r["durum"]])
        log.info("%d kayıt dışa aktarıldı: %s", len(satirlar), yol)
        self.statusBar().showMessage(f"{len(satirlar)} kayıt dışa aktarıldı.", 5000)

    # ── Diğer ───────────────────────────────────────────────────────
    def _saat_guncelle(self):
        self.saat.setText(datetime.now().strftime("%d.%m.%Y   %H:%M:%S"))
        if self.cerceve and not self.sabit_goruntu and time.monotonic() > self.cerceve[3]:
            self.cerceve = None

    def _gunluk_ekle(self, mesaj: str, seviye: int):
        renk = R["kirmizi"] if seviye >= logging.ERROR else R["turuncu"] if seviye >= logging.WARNING else R["yazi"]
        guvenli = mesaj.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.gunluk.appendHtml(f'<span style="color:{renk}">{guvenli}</span>')

    def closeEvent(self, olay):
        self.kamerayi_durdur()
        for is_ in (self.tarama, self.model_isi):
            if is_ is not None and is_.isRunning():
                is_.wait(3000)
        self.db.kapat()
        super().closeEvent(olay)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Akıllı Otopark")
    app.setStyle("Fusion")
    app.setStyleSheet(STIL)

    kopru = GunlukKoprusu()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(message)s", datefmt="%H:%M:%S")
    logging.getLogger().addHandler(GunlukIsleyici(kopru))

    try:
        db = Veritabani()
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(None, "Veritabanı açılamadı", f"{ayarlar.DB_YOLU}\n\n{e}")
        return 1

    pencere = AnaPencere(db, kopru)
    pencere.show()
    log.info("Uygulama başlatıldı. Veritabanı: %s", db.yol)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
