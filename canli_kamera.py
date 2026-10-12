"""
Basit OpenCV penceresiyle canlı plaka okuma (konsol modu).
Tam özellikli arayüz için:  python otopark_arayuz.py

Tuşlar:  [SPACE] plakayı oku   [S] plaka sorgula   [Q] çıkış
"""
import logging
import time

import cv2

import ayarlar
from plaka_okuma import PlakaOkuyucu, kutu_ciz, plakayi_normalize_et
from veritabani import Veritabani

PENCERE = "Akilli Otopark"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("otopark")


def main():
    db = Veritabani()
    okuyucu = PlakaOkuyucu()
    okuyucu.yukle()

    cap = cv2.VideoCapture(ayarlar.KAMERA_NO)
    son_okumalar: dict[str, float] = {}
    print("\n[SPACE] → Plakayı oku    [S] → Plaka sorgula    [Q] → Çıkış\n")

    try:
        while True:
            ok, kare = cap.read()
            if not ok:
                log.error("Kameradan görüntü alınamadı.")
                break

            gosterim = kare.copy()
            cv2.putText(gosterim, "OTOPARK | [SPACE]: Oku  [S]: Sorgula  [Q]: Cikis",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
            cv2.imshow(PENCERE, gosterim)
            tus = cv2.waitKey(1) & 0xFF

            if tus == ord("q"):
                break

            if tus == ord("s"):
                plaka = plakayi_normalize_et(input("🔎 Sorgulanacak plaka: ")) or ""
                kat, etiket = db.plaka_konumu(plaka)
                print(f"📌 {plaka} → {etiket} (Kat {kat})" if kat else f"❌ {plaka} otoparkta bulunamadı.")

            if tus == 32:
                log.info("Kare analiz ediliyor…")
                sonuc = okuyucu.oku(kare)
                if sonuc is None:
                    log.info("Geçerli bir plaka okunamadı.")
                    continue

                simdi = time.monotonic()
                if simdi - son_okumalar.get(sonuc.plaka, -1e9) < ayarlar.TEKRAR_OKUMA_SURESI:
                    log.warning("%s az önce işlendi, yok sayıldı.", sonuc.plaka)
                    continue
                son_okumalar[sonuc.plaka] = simdi

                islem = db.arac_isle(sonuc.plaka)
                metin = sonuc.plaka
                if islem.tur == "giris":
                    metin += f" -> {islem.slot_etiketi} (Kat {islem.kat})"
                elif islem.tur == "cikis":
                    metin += f"  CIKIS  {islem.ucret:.2f} TL"
                else:
                    metin += "  OTOPARK DOLU"
                kutu_ciz(kare, sonuc.kutu, metin)
                cv2.imshow(PENCERE, kare)
                cv2.waitKey(2000)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        db.kapat()


if __name__ == "__main__":
    main()
