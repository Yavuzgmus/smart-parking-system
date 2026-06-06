# import sqlite3

# # Veritabanına bağlan
# baglanti = sqlite3.connect('otopark.db')
# imlec = baglanti.cursor()

# # id değeri 1 olan o ilk hatalı kaydı silme sorgusu
# imlec.execute("DELETE FROM arac_kayitlari WHERE id = 7")

# # Değişiklikleri kaydet ve bağlantıyı kapat
# baglanti.commit()
# baglanti.close()

# print("Seçili id numaralı yanlış kayıt silindi")




import sqlite3

# DB bağlantısı
baglanti = sqlite3.connect('otopark.db')
imlec = baglanti.cursor()

# 1. Tablodaki TÜM test kayıtlarını siler
imlec.execute("DELETE FROM arac_kayitlari")

# tamamen idleri sıfırlama 
imlec.execute("DELETE FROM sqlite_sequence WHERE name='arac_kayitlari'")

baglanti.commit()
baglanti.close()

print("Veritabanı tertemiz edildi ve ID sayacı sıfırlandı!")