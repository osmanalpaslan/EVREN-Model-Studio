---
id: 2026-10-16-e2e-real-api-60-sn-zaman-asimi-glm-5-3-icin-dar
tarih: 2026-10-16
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu
alan: test
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [glm-5.3, zaman-asimi, e2e]
kurallar: [R-08]
---

# e2e_real_api 60 sn zaman aşımı glm-5.3 için dar

## Belirti
`tests/e2e_real_api.py`, glm-5.3 akışsız sohbet adımında iki kez üst üste
`httpx.ReadTimeout` → `ApiError(UNKNOWN_RESULT)` ile düştü. Ajan (6/6) ve
arayüz (15/15) gerçek testleri aynı anda geçti.

## Kök neden
Doğrulandı: sunucu tarafı gecikme. Aynı istek ayrı bir denemede akışsız
23,8 sn, akışlı 55,8 sn sürdü. Betik zaman aşımı 60 sn idi; istek gövdesi
master ile aynı (`strip_internal` düz mesajları değiştirmez). Uygulama kodu
kaynaklı değil.

## Çözüm
Betiğin zaman aşımı 180 sn yapıldı (uygulamanın sağlayıcı istemcileriyle
uyumlu). Yeniden çalıştırma: `E2E_OK`.

## Kanıt
`tests/e2e_real_api.py` → healthz ok, 16 model, kota ok, sohbet `Günaydın`,
35 parça akış, istek durumu success, `E2E_OK`.

## Önleme
R-08'e uygun davranıldı: önce tek başına tekrar çalıştırıldı, gecikme ölçüldü,
sonra yalnızca test betiği değiştirildi.

## İlgili dosyalar
- tests/e2e_real_api.py
