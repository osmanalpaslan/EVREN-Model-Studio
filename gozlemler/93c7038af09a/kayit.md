---
id: 93c7038af09a
baslik: Model boş yanıt döndü
tur: ajan_anomali
onem: dusuk
alan: ortam
durum: acik                # acik | cozuldu | kabul-edildi
kaynak: uygulama
ilk_gorulme: 2026-11-07T16:28:42+00:00
cozuldu_tarih:
cozum_kaydi:
---

# Model boş yanıt döndü

## Belirti (otomatik)
ajan_anomali

## Konum (otomatik)
- (yığın izi yok)

## Ayrıntı (otomatik)
- model: auto
- rol: kod

## Ne yapılmalı
Geliştirici motoru: kullanıcıya bildir; onaylarsa `python tools/ai_memory.py gozlem kayda-donustur 93c7038af09a` ile docs/ai-memory/incidents altına kayıt aç, kök nedeni bul ve düzelt, sonra `python tools/ai_memory.py gozlem kapat 93c7038af09a --kayit <kayit-id>`.
