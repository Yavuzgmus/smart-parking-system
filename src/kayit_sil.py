"""
Araç kayıtlarını silme aracı.

    python src/kayit_sil.py --id 7      → tek bir kaydı siler
    python src/kayit_sil.py --hepsi     → tüm kayıtları siler, ID sayacını sıfırlar, slotları boşaltır
    (-y eklenirse onay sorulmaz)
"""
import argparse

from veritabani import Veritabani


def onayla(soru: str, evet: bool) -> bool:
    return evet or input(f"{soru} [e/H]: ").strip().lower() in ("e", "evet", "y", "yes")


def main():
    p = argparse.ArgumentParser(description="Otopark kayıtlarını sil")
    grup = p.add_mutually_exclusive_group(required=True)
    grup.add_argument("--id", type=int, help="silinecek kaydın ID'si")
    grup.add_argument("--hepsi", action="store_true", help="tüm kayıtları sil")
    p.add_argument("-y", "--evet", action="store_true", help="onay sorma")
    args = p.parse_args()

    db = Veritabani()
    try:
        if args.hepsi:
            if onayla(f"{db.yol} içindeki TÜM kayıtlar silinsin mi?", args.evet):
                db.tumunu_temizle()
                print("Veritabanı temizlendi, ID sayacı sıfırlandı ve slotlar boşaltıldı.")
        elif onayla(f"#{args.id} numaralı kayıt silinsin mi?", args.evet):
            print("Kayıt silindi." if db.kayit_sil(args.id) else f"#{args.id} numaralı kayıt bulunamadı.")
    finally:
        db.kapat()


if __name__ == "__main__":
    main()
