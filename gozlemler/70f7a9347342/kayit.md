---
id: 70f7a9347342
baslik: API hatası: sunucu_kullanılamıyor (HTTP 503)
tur: api_hatasi
onem: dusuk
alan: ortam
durum: kabul-edildi                # acik | cozuldu | kabul-edildi
kaynak: e2e
ilk_gorulme: 2026-11-04T16:51:42+00:00
cozuldu_tarih: 2026-11-04T19:54:16+00:00
cozum_kaydi: 2026-11-04-api-hatasi-sunucu-kullanilamiyor-http-503
---

# API hatası: sunucu_kullanılamıyor (HTTP 503)

## Belirti (otomatik)
api_hatasi: {'message': 'Model şu anda dolu, lütfen kısa bir süre sonra tekrar deneyin.', 'type': 'api_error', 'param': None, 'code': 'model_capacity_exhausted', 'evren': {'resets_at': '2026-11-04T16:51:57.731531…

## Konum (otomatik)
- (yığın izi yok)

## Ayrıntı (otomatik)
- model: glm-5.3
- http: 503
- hata_turu: sunucu_kullanılamıyor
- islem: e2e_agent native

## Ne yapılmalı
Geliştirici motoru: kullanıcıya bildir; onaylarsa `python tools/ai_memory.py gozlem kayda-donustur 70f7a9347342` ile docs/ai-memory/incidents altına kayıt aç, kök nedeni bul ve düzelt, sonra `python tools/ai_memory.py gozlem kapat 70f7a9347342 --kayit <kayit-id>`.
