"""
Veritabanını oluşturur / eski şemayı günceller.
Uygulama açılırken bu işlem zaten otomatik yapılır; bu betik elle kurulum içindir.
"""
import logging

from veritabani import Veritabani

logging.basicConfig(level=logging.INFO, format="%(message)s")

if __name__ == "__main__":
    db = Veritabani()
    ist = db.istatistikler()
    print(f"✅ Veritabanı hazır: {db.yol}")
    print(f"   {ist['toplam_slot']} slot ({ist['dolu_slot']} dolu), {ist['iceride']} araç içeride.")
    db.kapat()
