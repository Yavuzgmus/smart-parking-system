import cv2
import easyocr
import sqlite3
import re
import time
import os
import numpy as np
from datetime import datetime
from inference import get_model

# ==============================================================
#  1. PLAKA DOĞRULAMA VE OCR YARDIMCILARI
# ==============================================================

PLAKA_HARFLERI = "ABCDEFGHIJKLMNOPRSTUVYZ"

PLATE_PATTERNS = [
    re.compile(rf'^(0[1-9]|[1-7]\d|8[01])[{PLAKA_HARFLERI}]{{1}}\d{{4,5}}$'),
    re.compile(rf'^(0[1-9]|[1-7]\d|8[01])[{PLAKA_HARFLERI}]{{2}}\d{{3,4}}$'),
    re.compile(rf'^(0[1-9]|[1-7]\d|8[01])[{PLAKA_HARFLERI}]{{3}}\d{{2,3}}$'),
]

# DÜZELTME 1: DIGIT_CORRECTIONS'da L->4 yanlıştı.
# Rakam bölümünde küçük-L (OCR'nin l yazması) ve büyük-I -> 1 olmalı.
# L->4 kaldırıldı; I->1 zaten vardı.
DIGIT_CORRECTIONS = {
    'O': '0', 'Q': '0', 'I': '1', 'Z': '2',
    'S': '5', 'G': '6', 'T': '7', 'B': '8'
}

# DÜZELTME 2: LETTER_CORRECTIONS'da D->0 yanlıştı (D geçerli harf).
# Harf bölümünde rakamları harfe çevir.
LETTER_CORRECTIONS = {
    '0': 'O', '1': 'I', '2': 'Z', '3': 'B',
    '4': 'A', '5': 'S', '6': 'G', '8': 'B'
}


def plaka_gecerli_mi(metin: str) -> bool:
    return any(p.fullmatch(metin) for p in PLATE_PATTERNS)


def segment_duzelt(segment: str, mapping: dict) -> str:
    return "".join(mapping.get(ch, ch) for ch in segment)


# DÜZELTME 3: Substring tarama eklendi.
# OCR bazen "TR06DGE17" veya "GÜRKAN ARTUN 06 DGE 17" gibi gürültülü metin
# döndürür. Eski kod bunu tamamen reddediyordu.
# Yeni yaklaşım: temizlenmiş metinden 6-8 karakterlik tüm alt dizileri dene.
def plakayi_substring_tara(metin: str):
    for uzunluk in [8, 7, 6]:
        for baslangic in range(len(metin) - uzunluk + 1):
            alt = metin[baslangic:baslangic + uzunluk]
            if plaka_gecerli_mi(alt):
                return alt
    return None


def plakayi_normalize_et(ham_metin: str):
    metin = re.sub(r'[^A-Z0-9]', '', ham_metin.upper())

    # 1) Doğrudan geçerliyse döndür
    if plaka_gecerli_mi(metin):
        return metin

    # 2) Substring tarama — gürültülü OCR için (TR prefix, plaka altı yazısı vb.)
    substring_sonuc = plakayi_substring_tara(metin)
    if substring_sonuc:
        return substring_sonuc

    # 3) Harf/rakam karışıklığı düzeltmesi
    adaylar = []
    for harf_sayisi, min_r, max_r in [(1, 4, 5), (2, 3, 4), (3, 2, 3)]:
        suffix_len = len(metin) - 2 - harf_sayisi
        if not (min_r <= suffix_len <= max_r):
            continue
        il_kodu  = segment_duzelt(metin[:2],                  DIGIT_CORRECTIONS)
        harfler  = segment_duzelt(metin[2:2 + harf_sayisi],   LETTER_CORRECTIONS)
        rakamlar = segment_duzelt(metin[2 + harf_sayisi:],    DIGIT_CORRECTIONS)
        aday = il_kodu + harfler + rakamlar
        if plaka_gecerli_mi(aday):
            degisim = sum(a != b for a, b in zip(metin, aday))
            adaylar.append((aday, degisim))

    # 4) Substring + düzeltme kombinasyonu
    if not adaylar:
        for uzunluk in [8, 7, 6]:
            for baslangic in range(len(metin) - uzunluk + 1):
                alt = metin[baslangic:baslangic + uzunluk]
                for harf_sayisi, min_r, max_r in [(1, 4, 5), (2, 3, 4), (3, 2, 3)]:
                    suffix_len = len(alt) - 2 - harf_sayisi
                    if not (min_r <= suffix_len <= max_r):
                        continue
                    il_kodu  = segment_duzelt(alt[:2],                  DIGIT_CORRECTIONS)
                    harfler  = segment_duzelt(alt[2:2 + harf_sayisi],   LETTER_CORRECTIONS)
                    rakamlar = segment_duzelt(alt[2 + harf_sayisi:],    DIGIT_CORRECTIONS)
                    aday = il_kodu + harfler + rakamlar
                    if plaka_gecerli_mi(aday):
                        degisim = sum(a != b for a, b in zip(alt, aday))
                        adaylar.append((aday, degisim))

    if not adaylar:
        return None
    adaylar.sort(key=lambda x: x[1])
    return adaylar[0][0]


def goruntu_varyasyonlari_uret(crop):
    gray  = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray  = cv2.bilateralFilter(gray, 7, 75, 75)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    blur  = cv2.medianBlur(clahe, 3)

    otsu  = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    adapt = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, 31, 11)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharp  = cv2.filter2D(clahe, -1, kernel)

    cikti = []
    for img in [gray, clahe, otsu, adapt, sharp]:
        buyuk = cv2.resize(img, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        padli = cv2.copyMakeBorder(buyuk, 12, 12, 12, 12,
                                   cv2.BORDER_CONSTANT, value=255)
        cikti.append(padli)
    return cikti


def en_iyi_plakayi_oku(crop, reader):
    adaylar = []
    for img in goruntu_varyasyonlari_uret(crop):
        ocr_result = reader.readtext(
            img,
            allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',
            decoder='beamsearch', beamWidth=10, detail=1
        )
        if not ocr_result:
            continue
        ocr_result = sorted(ocr_result, key=lambda x: min(pt[0] for pt in x[0]))
        # DÜZELTME 4: Tüm satırları birleştirmeden önce ve sonra dene
        tum_metin = "".join(r[1] for r in ocr_result)
        ham = re.sub(r'[^A-Z0-9]', '', tum_metin.upper())
        if not ham:
            continue
        print(f"    OCR ham: '{tum_metin}' -> temiz: '{ham}'")
        temiz = plakayi_normalize_et(ham)
        # Ayrıca her satırı ayrı ayrı dene (çok satırlı OCR için)
        if not temiz:
            for r in ocr_result:
                tek = re.sub(r'[^A-Z0-9]', '', r[1].upper())
                temiz = plakayi_normalize_et(tek)
                if temiz:
                    break
        if temiz:
            conf = sum(r[2] for r in ocr_result) / len(ocr_result)
            print(f"    ✅ Normalize: '{temiz}' (güven: {conf:.2f})")
            adaylar.append((temiz, conf))
        else:
            print(f"    ❌ Normalize başarısız: '{ham}'")

    if not adaylar:
        return None
    adaylar.sort(key=lambda x: x[1], reverse=True)
    return adaylar[0][0]


# ==============================================================
#  2. VERİTABANI İŞLEMLERİ
# ==============================================================

DB_YOLU = r"C:\Users\Yavuz Gümüş\OneDrive\Masaüstü\Otopark\otopark.db"

# WAL modu: Python yazarken Java okuyabilir, kilit çakışması olmaz
conn   = sqlite3.connect(DB_YOLU, check_same_thread=False, timeout=10)
cursor = conn.cursor()


def veritabani_hazirla():
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS arac_kayitlari (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            plaka         TEXT,
            giris_zamani  TEXT,
            cikis_zamani  TEXT,
            durum         TEXT,
            ucret         REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS otopark_slotlari (
            slot_id         INTEGER PRIMARY KEY,
            kat             INTEGER NOT NULL,
            kat_slot_no     INTEGER NOT NULL,
            slot_etiketi    TEXT NOT NULL,
            durum           TEXT DEFAULT 'Boş',
            park_eden_plaka TEXT
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM otopark_slotlari")
    if cursor.fetchone()[0] == 0:
        slot_id = 1
        for kat in range(1, 4):
            for s in range(1, 11):
                etiket = f"K{kat}-S{s}"
                cursor.execute(
                    "INSERT INTO otopark_slotlari (slot_id, kat, kat_slot_no, slot_etiketi, durum) VALUES (?, ?, ?, ?, 'Boş')",
                    (slot_id, kat, s, etiket)
                )
                slot_id += 1
    conn.commit()
    print("✅ Veritabanı hazır (3 kat, 30 slot).")


def guvenli_execute(query, params=(), retry=5):
    for i in range(retry):
        try:
            cursor.execute(query, params)
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                print("⏳ Veritabanı kilitli, tekrar deneniyor...")
                time.sleep(0.5)
            else:
                raise
    print("❌ Veritabanı kilidi açılamadı!")
    return False


# ---------------------------------------------------------------
#  DÜZELTME 1: sinyal_yaz() — Java paneline "yenile" sinyali gönderir
# ---------------------------------------------------------------
SINYAL_DOSYASI = r"C:\Users\Yavuz Gümüş\OneDrive\Masaüstü\Otopark\panel_yenile.signal"

def sinyal_yaz():
    """
    Boş bir dosya oluşturur. Java paneli bu dosyayı her 2 saniyede
    kontrol eder; bulunca verileriGetir() çalıştırır ve dosyayı siler.
    """
    try:
        with open(SINYAL_DOSYASI, "w") as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        print(f"⚠️  Sinyal yazılamadı: {e}")


# ---------------------------------------------------------------
#  DÜZELTME 2: araci_sisteme_kaydet() artık slot atamasını da yapıyor
# ---------------------------------------------------------------
def araci_sisteme_kaydet(plaka: str):
    """
    Giriş: arac_kayitlari'na ekle + rastgele boş slot ata
    Çıkış: kaydı güncelle + slotu boşalt
    Her iki durumda da Java paneline sinyal yazar.
    """
    try:
        cursor.execute(
            "SELECT id, giris_zamani FROM arac_kayitlari WHERE plaka=? AND durum='İçeride'",
            (plaka,)
        )
        mevcut    = cursor.fetchone()
        su_an     = datetime.now()
        zaman_str = su_an.strftime('%Y-%m-%d %H:%M:%S')

        if mevcut is None:
            # ── GİRİŞ ──────────────────────────────────────────────
            guvenli_execute(
                "INSERT INTO arac_kayitlari (plaka, giris_zamani, durum, ucret) VALUES (?, ?, 'İçeride', 0)",
                (plaka, zaman_str)
            )
            print(f"✅ GİRİŞ  : {plaka} | {zaman_str}")

            # Slot ataması (artık burada, ayrı çağrıya gerek yok)
            cursor.execute(
                "SELECT slot_id, kat, slot_etiketi FROM otopark_slotlari WHERE durum='Boş' ORDER BY RANDOM() LIMIT 1"
            )
            slot = cursor.fetchone()
            if slot:
                slot_id, kat, etiket = slot
                guvenli_execute(
                    "UPDATE otopark_slotlari SET durum='Dolu', park_eden_plaka=? WHERE slot_id=?",
                    (plaka, slot_id)
                )
                print(f"📍 ATANDI : {plaka} → {etiket}  (Kat {kat})")
                sinyal_yaz()          # ← Java panelini uyar
                return slot_id, kat, etiket
            else:
                print("⚠️  OTOPARK DOLU! Boş slot yok.")
                sinyal_yaz()
                return None, None, None

        else:
            # ── ÇIKIŞ ──────────────────────────────────────────────
            kayit_id     = mevcut[0]
            giris_zamani = datetime.strptime(mevcut[1], '%Y-%m-%d %H:%M:%S')
            sure_saniye  = int((su_an - giris_zamani).total_seconds())
            toplam_ucret = round(20.0 + sure_saniye * 0.10, 2)

            guvenli_execute(
                "UPDATE arac_kayitlari SET cikis_zamani=?, ucret=?, durum='Çıkış Yaptı' WHERE id=?",
                (zaman_str, toplam_ucret, kayit_id)
            )
            guvenli_execute(
                "UPDATE otopark_slotlari SET durum='Boş', park_eden_plaka=NULL WHERE park_eden_plaka=?",
                (plaka,)
            )
            print(f"🛑 ÇIKIŞ : {plaka} | Süre: {sure_saniye}s | Ücret: {toplam_ucret} ₺")
            sinyal_yaz()              # ← Java panelini uyar
            return None, None, None

    except Exception as e:
        print(f"⚠️  Veritabanı hatası: {e}")
        return None, None, None


def plaka_konumunu_bul(plaka: str):
    try:
        cursor.execute(
            "SELECT kat, slot_etiketi FROM otopark_slotlari WHERE park_eden_plaka=? AND durum='Dolu'",
            (plaka,)
        )
        row = cursor.fetchone()
        if row:
            return row[0], row[1]
        return None, None
    except Exception as e:
        print(f"⚠️  Konum sorgu hatası: {e}")
        return None, None


# ==============================================================
#  3. ANA DÖNGÜ
# ==============================================================

veritabani_hazirla()

print("🚀 Modeller yükleniyor...")
model  = get_model(model_id="turkish-license-plate/8", api_key="RHUbVoOM9FVbXnTopWZ6")
reader = easyocr.Reader(['tr', 'en'], gpu=False)
print("✅ Modeller hazır.")

cap = cv2.VideoCapture(0)

print("\n[SPACE] → Kameradaki plakayı oku    [S] → Plaka sorgula    [Q] → Çıkış\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    cv2.putText(frame,
                "OTOPARK | [SPACE]: Oku  [S]: Sorgula  [Q]: Cikis",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
    cv2.imshow("Akilli Otopark - 3 Kat", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break

    if key == ord('s'):
        sorgu = input("🔎 Sorgulanacak plaka: ").strip().upper()
        kat, etiket = plaka_konumunu_bul(sorgu)
        if kat:
            print(f"📌 {sorgu} → {etiket}  (Kat {kat})")
        else:
            print(f"❌ {sorgu} otopark içinde bulunamadı.")

    if key == 32:
        print("\n🔍 Kare analiz ediliyor...")
        results     = model.infer(frame)
        predictions = results[0].predictions if isinstance(results, list) else results.predictions
        predictions = sorted(predictions, key=lambda p: p.confidence, reverse=True)
        plaka_bulundu = False

        for pred in predictions:
            if pred.confidence < 0.4:
                continue

            x1 = int(pred.x - pred.width  / 2)
            y1 = int(pred.y - pred.height / 2)
            x2 = int(pred.x + pred.width  / 2)
            y2 = int(pred.y + pred.height / 2)

            mx = int((x2 - x1) * 0.08)
            my = int((y2 - y1) * 0.20)
            x1 = max(0, x1 - mx);  y1 = max(0, y1 - my)
            x2 = min(frame.shape[1], x2 + mx)
            y2 = min(frame.shape[0], y2 + my)

            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            temiz_plaka = en_iyi_plakayi_oku(crop, reader)

            if temiz_plaka:
                print(f"✅ Okunan plaka: {temiz_plaka}")

                # DÜZELTME: rastgele_slot_ata() ayrıca çağrılmıyor,
                # araci_sisteme_kaydet() hem kaydı hem slotu hallediyor
                slot_id, kat, etiket = araci_sisteme_kaydet(temiz_plaka)

                bilgi = temiz_plaka
                if etiket:
                    bilgi += f"  ->  {etiket} (Kat {kat})"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                cv2.putText(frame, bilgi, (x1, y1 - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 0), 2)
                cv2.imshow("Akilli Otopark - 3 Kat", frame)
                print("⌛ 2 saniye bekleniyor...")
                cv2.waitKey(2000)
                plaka_bulundu = True
                break

        if not plaka_bulundu:
            print("❌ Geçerli bir plaka formatı okunamadı.")

cap.release()
cv2.destroyAllWindows()
conn.close()