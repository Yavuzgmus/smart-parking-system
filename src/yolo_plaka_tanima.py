"""
Bir fotoğraftaki plakayı okur ve (isteğe bağlı) giriş/çıkış olarak kaydeder.

    python src/yolo_plaka_tanima.py test_photos/test_arac2.jpg
    python src/yolo_plaka_tanima.py foto.jpg --kaydetme     → sadece okur, veritabanına yazmaz
"""
import argparse
import logging

import cv2
import numpy as np

from plaka_okuma import PlakaOkuyucu, kutu_ciz
from veritabani import Veritabani

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")


def main():
    p = argparse.ArgumentParser(description="Fotoğraftan plaka okuma")
    p.add_argument("foto", nargs="?", default="test_photos/test_arac2.jpg")
    p.add_argument("--kaydetme", action="store_true", help="veritabanına yazma")
    args = p.parse_args()

    # cv2.imread Türkçe karakterli yolları okuyamaz; imdecode ile okuyoruz
    img = cv2.imdecode(np.fromfile(args.foto, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"Fotoğraf okunamadı: {args.foto}")

    okuyucu = PlakaOkuyucu()
    okuyucu.yukle()
    sonuc = okuyucu.oku(img)
    if sonuc is None:
        print("Görüntüde net bir plaka okunamadı.")
        return

    print(f"Okunan plaka: {sonuc.plaka}  (güven {sonuc.guven:.2f})")
    if not args.kaydetme:
        db = Veritabani()
        islem = db.arac_isle(sonuc.plaka)
        db.kapat()
        if islem.tur == "giris":
            print(f"🟢 GİRİŞ  → {islem.slot_etiketi} (Kat {islem.kat})")
        elif islem.tur == "cikis":
            print(f"🔴 ÇIKIŞ  → süre {islem.sure_saniye} sn, ücret {islem.ucret:.2f} ₺")
        else:
            print("⚠️  Otopark dolu, araç alınmadı.")

    kutu_ciz(img, sonuc.kutu, sonuc.plaka)
    cv2.imshow("Plaka", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
