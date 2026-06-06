import cv2
import easyocr
from inference import get_model
import sqlite3
from datetime import datetime
import re

# --- YENİ: VERİTABANI İŞLEM FONKSİYONU ---
def araci_sisteme_kaydet(plaka_metni):
    try:
        baglanti = sqlite3.connect('otopark.db')
        imlec = baglanti.cursor()
        
        # 1. KONTROL: Bu araç şu an zaten otoparkın içinde mi?
        imlec.execute("SELECT id, giris_zamani FROM arac_kayitlari WHERE plaka=? AND durum='İçeride'", (plaka_metni,))
        icerideki_arac = imlec.fetchone()
        
        su_an = datetime.now()
        # Zamanı veritabanı için standart bir formata çeviriyoruz
        zaman_str = su_an.strftime('%Y-%m-%d %H:%M:%S')
        
        if icerideki_arac is None:
            # 2. GİRİŞ İŞLEMİ: Araç içeride değilse, yeni giriş kaydı aç
            imlec.execute("INSERT INTO arac_kayitlari (plaka, giris_zamani, durum) VALUES (?, ?, 'İçeride')", (plaka_metni, zaman_str))
            baglanti.commit()
            print(f"\n[{zaman_str}] 🟢 GİRİŞ ONAYLANDI: {plaka_metni}")
            print("Giriş bariyeri açılıyor...")
        else:
            # Araç içerideyse çıkış yap
            kayit_id = icerideki_arac[0]
            giris_zamani_str = icerideki_arac[1]
            
            # Real time giriş 
            giris_zamani = datetime.strptime(giris_zamani_str, '%Y-%m-%d %H:%M:%S')
            kalinan_sure = su_an - giris_zamani
            
            saniye_farki = kalinan_sure.total_seconds()
            dakika_farki = saniye_farki / 60
            
            # Ücretlendirme
            toplam_ucret = 20.0 + (saniye_farki * 0.50)
            
            # Veritabanını çıkış verileriyle güncelle
            imlec.execute("UPDATE arac_kayitlari SET cikis_zamani=?, ucret=?, durum='Çıkış Yaptı' WHERE id=?", (zaman_str, round(toplam_ucret, 2), kayit_id))
            baglanti.commit()
            
            print(f"\n[{zaman_str}] 🔴 ÇIKIŞ ONAYLANDI: {plaka_metni}")
            print(f"İçeride Kalınan Süre: {int(dakika_farki)} dakika, {int(saniye_farki % 60)} saniye")
            print(f"Toplam Ödenecek Tutar: {round(toplam_ucret, 2)} TL")
            print("Ödeme alındı, çıkış bariyeri açılıyor...")
            
        baglanti.close()
    except Exception as e:
        print(f"Veritabanı Hatası: {e}")

# 1. Eğitilmiş Modeli Çek
print("Model yükleniyor...")
model = get_model(model_id="turkish-license-plate/8", api_key="RHUbVoOM9FVbXnTopWZ6")

# 2. Görüntüyü Oku (Test edeceğin resmin adını buraya yaz)
img_path = 'test_photos/test_arac2.jpg' 
img = cv2.imread(img_path)

# 3. Model ile Plaka Tespiti Yap
print("Plaka aranıyor...")
results = model.infer(img)
predictions = results[0].predictions if isinstance(results, list) else results.predictions

# 4. OCR Okuyucuyu Başlat
reader = easyocr.Reader(['tr', 'en'])
plaka_bulundu = False

for pred in predictions:
    if pred.confidence < 0.5:
        continue

    x_center, y_center = pred.x, pred.y
    width, height = pred.width, pred.height

    x1 = max(0, int(x_center - (width / 2)))
    y1 = max(0, int(y_center - (height / 2)))
    x2 = int(x_center + (width / 2))
    y2 = int(y_center + (height / 2))

    cropped_plate = img[y1:y2, x1:x2]

    # Görüntü iyileştirme (Gri tonlama ve büyütme)
    gray_plate = cv2.cvtColor(cropped_plate, cv2.COLOR_BGR2GRAY)
    gray_plate = cv2.resize(gray_plate, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

  # --- RAPOR İÇİN GÖRSELLERİ EKRANA BASTIRMA EKLENTİSİ ---
    cv2.imshow("A - Orijinal Kirpilmis Plaka", cropped_plate)
    cv2.imshow("B - Gri ve Buyutulmus Plaka", gray_plate)
    # -------------------------------------------------------

    # OCR İşlemi
    # ... (x1, y1 hesaplamaları ve gray_plate işlemlerinden sonrası)
    
    ocr_result = reader.readtext(gray_plate, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    if ocr_result:
        plaka_bulundu = True
        ham_metin = ""
        toplam_guven = 0
        
        # 1. Okunan her şeyi yan yana birleştir
        for parca in ocr_result:
            ham_metin += parca[-2]
            toplam_guven += parca[-1]
            
        ortalama_guven = toplam_guven / len(ocr_result)
        ham_metin = ham_metin.replace(" ", "").upper()
        
        # 2. REGEX İLE PLAKA FORMATINI AYIKLAMA (Veri Temizliği)
        # Kural: 2 Rakam ile başla (\d{2}), 1 ila 3 harf devam et ([A-Z]{1,3}), 2 ila 4 rakamla bitir (\d{2,4})
        import re
        eslesme = re.search(r'\d{2}[A-Z]{1,3}\d{2,4}', ham_metin)
        
        if eslesme:
            temiz_plaka = eslesme.group() # Kurallara uyan tertemiz plaka
        else:
            temiz_plaka = ham_metin # Eğer kurala uyan bir şey bulamazsa ham haliyle bırak
        
        print(f"YOLO Tespiti: {temiz_plaka} (Ham Okuma: {ham_metin})")

        # --- YENİ: TEMİZLENMİŞ PLAKAYI VERİTABANINA GÖNDER ---
        araci_sisteme_kaydet(temiz_plaka)

        # Ekrana çizdirme işlemleri
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, temiz_plaka, (x1, max(20, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

if not plaka_bulundu:
    print("Sistem görüntüyü taradı ancak net bir plaka metni okunamadı.")

cv2.imshow("Akilli Otopark - YOLOv11 + OCR + DB", img)
cv2.waitKey(0)
cv2.destroyAllWindows()