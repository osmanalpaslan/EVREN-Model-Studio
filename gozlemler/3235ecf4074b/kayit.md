---
id: 3235ecf4074b
baslik: Auto Pro yedek modele geçti
tur: ajan_anomali
onem: dusuk
alan: ortam
durum: kabul-edildi                # acik | cozuldu | kabul-edildi
kaynak: e2e
ilk_gorulme: 2026-11-04T16:40:53+00:00
cozuldu_tarih: 2026-11-04T19:54:21+00:00
cozum_kaydi: 2026-11-04-api-hatasi-sunucu-kullanilamiyor-http-503
---

# Auto Pro yedek modele geçti

## Belirti (otomatik)
ajan_anomali

## Konum (otomatik)
- (yığın izi yok)

## Ayrıntı (otomatik)
- model: deepseek-v4.1-flash
- rol: plan
- olay: switch

## Ne yapılmalı
Geliştirici motoru: kullanıcıya bildir; onaylarsa `python tools/ai_memory.py gozlem kayda-donustur 3235ecf4074b` ile docs/ai-memory/incidents altına kayıt aç, kök nedeni bul ve düzelt, sonra `python tools/ai_memory.py gozlem kapat 3235ecf4074b --kayit <kayit-id>`.
