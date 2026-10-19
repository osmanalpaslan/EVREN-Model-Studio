---
id: 2026-10-19-model-kisaltilmis-dosya-ciktisindan-kesin-sayi-uydurdu
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [uydurma, sayim, kisaltma, zorluk-paketi]
kurallar: [R-21]
---

# Model kısaltılmış dosya çıktısından kesin sayı uydurdu

## Belirti
Zorluk paketi `buyuk_dosya` (3000 satırlık log, 22 ERROR satırı, sonuncusu
#2999): auto "2 satır, son #1918" dedi. Düzeltmeden sonraki bir denemede kalan
satırları okudu ama 3000 satırı gözle sayıp "6 satır ... doğrulanmıştır" dedi.

## Kök neden
Doğrulandı (oturum kayıtları): `read_file` en fazla 2000 satır döndürür; sonuna
yalnızca "… (dosya 3000 satır; 1-2000 gösterildi)" yazıyordu, model bunu
görmezden geldi. İkinci neden: dil modelleri uzun metinde güvenilir sayamaz;
`search_files` toplam sayı vermiyordu, model sayıyı kendisi çıkarıyordu.

## Çözüm
- `read_file`: kısaltmada "⚠ KISALTILDI … 2001-3000 GÖRÜLMEDİ … kalanı oku
  (start_line=…) veya sayım için search_files kullan" uyarısı.
- `search_files`: ilk satırda "Toplam N eşleşen satır (K dosyada)"; 100 sonuç
  sınırının ötesi de sayılır.
- Ajan kuralları: kısaltılmış çıktıdan kesin bilgi verme; sayım/istatistik
  sorularında gözle sayma, search_files veya komut kullan. read_file açıklaması:
  "SAYMAK için kullanma".

## Kanıt
- Önce: auto 0/1 (ilk tur), 0/1 (yalnız uyarıyla, tam paket turu).
- Sayım kuralından sonra: auto 3/3, deepseek-v4-flash 2/2 (2 adım, search_files).
- `tests/test_zorluk_duzeltmeleri.py` (uyarı ve sayım biçimi).

## Önleme
R-21: ajan davranışını değiştirince `tests/e2e_zorluk_real_api.py` çalıştır.

## İlgili dosyalar
- src/evren_studio/agent/tools.py
- src/evren_studio/agent/prompts.py
- tests/e2e_zorluk_real_api.py
