---
id: 2026-10-16-openai-ve-anthropic-entegrasyonu-gercek-anahtarla-dogrulanma
tarih: 2026-10-16
tur: risk            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: izleniyor
alan: api
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor:
cozen_model:
ortam: Windows 11, Python 3.12.10
etiketler: [openai, anthropic, dogrulanmadi]
kurallar: [R-07, R-17]
---

# OpenAI ve Anthropic entegrasyonu gerçek anahtarla doğrulanmadı

## Belirti
OpenAI (Responses API) ve Anthropic (Messages API) istemcileri, maliyet
tahmini ve bütçe koruması eklendi; ancak geliştirme sırasında iki sağlayıcının
da API anahtarı yoktu. Tüm davranış yalnızca sahte HTTP (httpx.MockTransport)
testleriyle sınandı.

## Kök neden
Doğrulandı: anahtar yok (kullanıcı kararı "Sahte testler, sonra doğrularsınız").
İstek/yanıt biçimleri resmî belgelerden (docs/knowledge/PROVIDERS_RESEARCH.md)
yazıldı. Belgeyle gerçek davranış arasındaki farklar (akış olay adları, hata
gövdeleri, model kimlikleri, fiyatlar) bilinmiyor.

## Çözüm
Henüz yok (izleniyor). Riskler arayüzde açıkça işaretlendi:
- `api/providers.py`: `verified=False`; model seçicide ve Ayarlar'da
  "doğrulanmadı" rozeti.
- Fiyatlar tarihli (`PRICES_AS_OF = 2026-10-16`); harcama "tahmini" diye
  gösteriliyor.
- Doğrulama betiği: `tests/e2e_providers_real_api.py --evet` (ücretli olduğu
  için bayraksız istek göndermez; en ucuz modeller: gpt-6-luna, claude-haiku-5-5).

## Kanıt
- `tests/test_providers.py`: 28 test (gövde/başlık, akış, araç döngüsü,
  thinking/encrypted reasoning geri gönderimi, hata eşleme, bütçe, arayüz).
- Gerçek istek: YAPILMADI.

## Önleme
Anahtarı olan ilk motor/kullanıcı `tests/e2e_providers_real_api.py --evet`
çalıştırmalı. Geçerse `verified=True` yapılmalı, sonuç
docs/knowledge/MODEL_CAPABILITIES.md ve bu kayda yazılmalı (R-07, R-17).

## İlgili dosyalar
- src/evren_studio/api/openai_client.py
- src/evren_studio/api/anthropic_client.py
- src/evren_studio/api/providers.py
- src/evren_studio/budget.py
- tests/test_providers.py
- tests/e2e_providers_real_api.py
