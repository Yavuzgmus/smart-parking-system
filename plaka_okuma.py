"""
Plaka tespiti (Roboflow modeli) + OCR (EasyOCR) + Türk plakası doğrulama.

Ağır kütüphaneler (inference, easyocr) yalnızca PlakaOkuyucu.yukle()
çağrıldığında içe aktarılır; böylece arayüz anında açılır.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass

import cv2
import numpy as np

import ayarlar

log = logging.getLogger("otopark.plaka")

# ==============================================================
#  1. PLAKA DOĞRULAMA
# ==============================================================

# Türk plakalarında Q, W, X harfleri kullanılmaz.
PLAKA_HARFLERI = "ABCDEFGHIJKLMNOPRSTUVYZ"
_IL = r"(0[1-9]|[1-7]\d|8[01])"

PLAKA_DESENLERI = [
    re.compile(rf"^{_IL}[{PLAKA_HARFLERI}]{{1}}\d{{4,5}}$"),
    re.compile(rf"^{_IL}[{PLAKA_HARFLERI}]{{2}}\d{{3,4}}$"),
    re.compile(rf"^{_IL}[{PLAKA_HARFLERI}]{{3}}\d{{2,3}}$"),
]

# (harf sayısı, en az rakam, en çok rakam)
PLAKA_YAPILARI = [(1, 4, 5), (2, 3, 4), (3, 2, 3)]

# Rakam olması gereken bölümde harfe benzeyen karakterler
RAKAM_DUZELTMELERI = {
    "O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2",
    "S": "5", "G": "6", "T": "7", "B": "8",
}

# Harf olması gereken bölümde rakama benzeyen karakterler
HARF_DUZELTMELERI = {
    "0": "O", "1": "I", "2": "Z", "3": "B", "4": "A",
    "5": "S", "6": "G", "8": "B", "Q": "O", "W": "V", "X": "K",
}


def temizle(metin: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", metin.upper())


def plaka_gecerli_mi(metin: str) -> bool:
    return any(d.fullmatch(metin) for d in PLAKA_DESENLERI)


def plaka_formatla(plaka: str) -> str:
    """'34ABC123' → '34 ABC 123'"""
    m = re.fullmatch(r"(\d{2})([A-Z]{1,3})(\d{2,5})", plaka or "")
    return " ".join(m.groups()) if m else (plaka or "")


def _segment_duzelt(segment: str, tablo: dict) -> str:
    return "".join(tablo.get(ch, ch) for ch in segment)


def _duzeltme_adaylari(metin: str):
    """Harf/rakam karışıklığını düzelterek geçerli plaka adayları üretir."""
    for harf_sayisi, en_az, en_cok in PLAKA_YAPILARI:
        rakam_sayisi = len(metin) - 2 - harf_sayisi
        if not (en_az <= rakam_sayisi <= en_cok):
            continue
        aday = (
            _segment_duzelt(metin[:2], RAKAM_DUZELTMELERI)
            + _segment_duzelt(metin[2:2 + harf_sayisi], HARF_DUZELTMELERI)
            + _segment_duzelt(metin[2 + harf_sayisi:], RAKAM_DUZELTMELERI)
        )
        if plaka_gecerli_mi(aday):
            degisim = sum(a != b for a, b in zip(metin, aday))
            yield aday, degisim


def _alt_diziler(metin: str):
    for uzunluk in (8, 7, 6):
        for i in range(len(metin) - uzunluk + 1):
            yield metin[i:i + uzunluk]


def plakayi_normalize_et(ham_metin: str) -> str | None:
    """
    OCR çıktısını geçerli bir Türk plakasına çevirir; çeviremezse None.
    Sıra: doğrudan eşleşme → alt dizi ("TR06DGE17" gibi gürültülü metin)
          → harf/rakam düzeltme → alt dizi + düzeltme.
    """
    metin = temizle(ham_metin)
    if not metin:
        return None
    if plaka_gecerli_mi(metin):
        return metin

    for alt in _alt_diziler(metin):
        if plaka_gecerli_mi(alt):
            return alt

    adaylar = list(_duzeltme_adaylari(metin))
    if not adaylar:
        for alt in _alt_diziler(metin):
            adaylar.extend(_duzeltme_adaylari(alt))

    if not adaylar:
        return None
    return min(adaylar, key=lambda x: x[1])[0]


# ==============================================================
#  2. GÖRÜNTÜ İŞLEME + OCR
# ==============================================================

def goruntu_varyasyonlari_uret(kirpim: np.ndarray) -> list[np.ndarray]:
    gri = cv2.cvtColor(kirpim, cv2.COLOR_BGR2GRAY)
    gri = cv2.bilateralFilter(gri, 7, 75, 75)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gri)
    bulanik = cv2.medianBlur(clahe, 3)

    otsu = cv2.threshold(bulanik, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    adaptif = cv2.adaptiveThreshold(bulanik, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 31, 11)
    keskin = cv2.filter2D(clahe, -1, np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]]))

    cikti = []
    # En çok işe yarayanlar önde: erken çıkışta daha az OCR çalışır.
    for img in (clahe, gri, otsu, keskin, adaptif):
        buyuk = cv2.resize(img, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        cikti.append(cv2.copyMakeBorder(buyuk, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255))
    return cikti


@dataclass
class OkumaSonucu:
    plaka: str
    guven: float                       # OCR güveni (0-1)
    kutu: tuple[int, int, int, int]    # x1, y1, x2, y2
    kirpim: np.ndarray


class PlakaOkuyucu:
    def __init__(self):
        self.model = None
        self.reader = None

    @property
    def hazir(self) -> bool:
        return self.model is not None and self.reader is not None

    def yukle(self):
        if not ayarlar.ROBOFLOW_API_KEY:
            raise RuntimeError("ROBOFLOW_API_KEY bulunamadı. .env.example dosyasını .env adıyla "
                               "kopyalayıp Roboflow API anahtarınızı yazın.")
        from inference import get_model
        import easyocr

        log.info("Plaka tespit modeli yükleniyor (%s)…", ayarlar.MODEL_ID)
        self.model = get_model(model_id=ayarlar.MODEL_ID, api_key=ayarlar.ROBOFLOW_API_KEY)
        log.info("OCR motoru yükleniyor…")
        self.reader = easyocr.Reader(["tr", "en"], gpu=ayarlar.OCR_GPU, verbose=False)
        log.info("Modeller hazır.")

    def tespit_et(self, kare: np.ndarray) -> list[tuple[tuple[int, int, int, int], float]]:
        """Karedeki plaka kutularını (biraz pay bırakarak) güvene göre sıralı döndürür."""
        sonuc = self.model.infer(kare)
        tahminler = sonuc[0].predictions if isinstance(sonuc, list) else sonuc.predictions
        h, w = kare.shape[:2]
        kutular = []
        for t in sorted(tahminler, key=lambda p: p.confidence, reverse=True):
            if t.confidence < ayarlar.TESPIT_GUVEN_ESIGI:
                continue
            x1, x2 = t.x - t.width / 2, t.x + t.width / 2
            y1, y2 = t.y - t.height / 2, t.y + t.height / 2
            mx, my = t.width * 0.08, t.height * 0.20
            kutu = (max(0, int(x1 - mx)), max(0, int(y1 - my)),
                    min(w, int(x2 + mx)), min(h, int(y2 + my)))
            kutular.append((kutu, float(t.confidence)))
        return kutular

    def kirpimi_oku(self, kirpim: np.ndarray) -> tuple[str, float] | None:
        """
        Kırpılmış plaka görüntüsünü farklı ön işlemelerle okur ve oylama yapar.
        Aynı plaka iki varyasyonda okunursa erken çıkar.
        """
        oylar: dict[str, list[float]] = defaultdict(list)
        for img in goruntu_varyasyonlari_uret(kirpim):
            sonuc = self.reader.readtext(
                img, allowlist="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                decoder="beamsearch", beamWidth=10, detail=1,
            )
            if not sonuc:
                continue
            sonuc = sorted(sonuc, key=lambda r: min(pt[0] for pt in r[0]))
            birlesik = "".join(r[1] for r in sonuc)
            plaka = plakayi_normalize_et(birlesik)
            if not plaka:  # çok satırlı okumalarda satırları tek tek dene
                plaka = next(filter(None, (plakayi_normalize_et(r[1]) for r in sonuc)), None)
            log.debug("OCR ham: %r → %s", birlesik, plaka or "geçersiz")
            if not plaka:
                continue
            oylar[plaka].append(sum(r[2] for r in sonuc) / len(sonuc))
            if len(oylar[plaka]) >= 2:
                break

        if not oylar:
            return None
        # Önce oy sayısı, sonra ortalama güven
        plaka, guvenler = max(oylar.items(), key=lambda kv: (len(kv[1]), sum(kv[1]) / len(kv[1])))
        return plaka, float(sum(guvenler) / len(guvenler))

    def oku(self, kare: np.ndarray) -> OkumaSonucu | None:
        if not self.hazir:
            raise RuntimeError("Modeller henüz yüklenmedi.")
        kutular = self.tespit_et(kare)
        if not kutular:
            log.info("Karede plaka tespit edilemedi.")
            return None
        for (x1, y1, x2, y2), _ in kutular:
            kirpim = kare[y1:y2, x1:x2]
            if kirpim.size == 0:
                continue
            okuma = self.kirpimi_oku(kirpim)
            if okuma:
                return OkumaSonucu(okuma[0], okuma[1], (x1, y1, x2, y2), kirpim.copy())
        log.info("Plaka bulundu ancak geçerli bir plaka metni okunamadı.")
        return None


def kutu_ciz(kare: np.ndarray, kutu, metin: str, renk=(80, 200, 120)) -> None:
    x1, y1, x2, y2 = kutu
    cv2.rectangle(kare, (x1, y1), (x2, y2), renk, 3)
    (tw, th), _ = cv2.getTextSize(metin, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    ty = max(th + 10, y1 - 8)
    cv2.rectangle(kare, (x1, ty - th - 8), (x1 + tw + 12, ty + 6), renk, -1)
    cv2.putText(kare, metin, (x1 + 6, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
