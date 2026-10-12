"""
Otopark sisteminin tüm ayarları tek yerde.

Ortam değişkenleriyle (environment variable) ya da proje klasöründeki .env
dosyasıyla değiştirilebilir (örnek için .env.example dosyasına bakın):
    OTOPARK_DB          → veritabanı dosyasının yolu
    OTOPARK_SINYAL      → Java paneline yenileme sinyali dosyası
    ROBOFLOW_API_KEY    → Roboflow plaka tespit modelinin API anahtarı
    OTOPARK_KAMERA      → kamera numarası (varsayılan 0)
"""
import os
from pathlib import Path

# Kodlar src/ içinde; .env ve otopark.db proje kök klasöründe durur.
PROJE_KLASORU = Path(__file__).resolve().parent.parent


def _env_dosyasini_yukle(yol: Path):
    """.env dosyasındaki ANAHTAR=deger satırlarını okur (gerçek ortam değişkenleri önceliklidir)."""
    if not yol.exists():
        return
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        anahtar, deger = satir.split("=", 1)
        os.environ.setdefault(anahtar.strip(), deger.strip().strip('"').strip("'"))


_env_dosyasini_yukle(PROJE_KLASORU / ".env")

# ── Veritabanı ───────────────────────────────────────────────────────
# Varsayılan: projenin yanındaki otopark.db. Java paneli farklı bir dosyaya
# bakıyorsa OTOPARK_DB ile aynı yolu gösterin.
DB_YOLU = Path(os.environ.get("OTOPARK_DB", PROJE_KLASORU / "otopark.db"))
SINYAL_DOSYASI = Path(os.environ.get("OTOPARK_SINYAL", DB_YOLU.with_name("panel_yenile.signal")))

# ── Otopark yapısı ───────────────────────────────────────────────────
KAT_SAYISI = 3
KAT_BASINA_SLOT = 10

# ── Ücretlendirme ────────────────────────────────────────────────────
BASLANGIC_UCRETI = 20.0   # ₺, giriş anında
SANIYE_UCRETI = 0.10      # ₺, kalınan her saniye için


def ucret_hesapla(sure_saniye: int) -> float:
    return round(BASLANGIC_UCRETI + max(0, sure_saniye) * SANIYE_UCRETI, 2)


# ── Plaka tanıma ─────────────────────────────────────────────────────
MODEL_ID = "turkish-license-plate/8"
# Gizli anahtar koda yazılmaz; .env dosyasından veya ortam değişkeninden okunur.
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "")
TESPIT_GUVEN_ESIGI = 0.40
OCR_GPU = False

# Aynı plaka bu süre (saniye) içinde tekrar okunursa yok sayılır.
# Böylece giriş yapan araç yanlışlıkla hemen "çıkış" yapmış sayılmaz.
TEKRAR_OKUMA_SURESI = 10

KAMERA_NO = int(os.environ.get("OTOPARK_KAMERA", "0"))
