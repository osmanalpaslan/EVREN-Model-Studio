---
id: 2026-10-21-kota-kapisi-bekleme-dongusu-kayan-noktada-sonsuz-donebilirdi
tarih: 2026-10-21
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [kota, quota-gate, kayan-nokta, sonsuz-dongu]
kurallar: []
---

# Kota kapısı bekleme döngüsü kayan noktada sonsuz dönebilirdi

## Belirti
`agent/quota.py` ilk yazımında `QuotaGate.before_call` pencere doluyken `while self.clock() < end:
self.sleep(min(2.0, end - self.clock()))` ile bekliyordu. Sahte saatli testte kalan süre ~1e-15'e
inince adım sıfıra yaklaştı ve döngü bitmedi (test takıldı).

## Kök neden
Doğrulandı. Kayan nokta toplamında `t + (end - t)` tam `end`'e eşit olmayabilir; her adım kalanın
tamamı kadar uyuduğundan kalan sıfıra hiç ulaşmaz.

## Çözüm
Döngü koşulu `while end - self.clock() > 0.05:` (50 ms eşiği). Bekleme en çok ~6 dk ile sınırlı ve
iptal edilebilir.

## Kanıt
`tests/test_kota_kapisi.py::test_pencere_doluysa_kodla_bekler_gunluk_azsa_duraklat` ve
`test_bekleme_iptal_edilebilir_ve_ust_sinirli` (sahte saat) geçiyor.

## Önleme
Süre bekleme döngülerinde kalan süreyi eşikle karşılaştır; sahte saatli birim testi yaz.

## İlgili dosyalar
- src/evren_studio/agent/quota.py
- tests/test_kota_kapisi.py
