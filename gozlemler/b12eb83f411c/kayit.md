---
id: b12eb83f411c
baslik: Gözlem ajanı kurulum denemesi (gerçek gönderim testi)
tur: gelistirici
onem: dusuk
alan: test
durum: acik                # acik | cozuldu | kabul-edildi
kaynak: motor
ilk_gorulme: 2026-11-03T18:49:52+00:00
cozuldu_tarih:
cozum_kaydi:
---

# Gözlem ajanı kurulum denemesi (gerçek gönderim testi)

## Belirti (otomatik)
gelistirici

## Konum (otomatik)
- (yığın izi yok)

## Ayrıntı (otomatik)
- kaynak_betik: ai_memory gozlem ekle

## Ne yapılmalı
Geliştirici motoru: kullanıcıya bildir; onaylarsa `python tools/ai_memory.py gozlem kayda-donustur b12eb83f411c` ile docs/ai-memory/incidents altına kayıt aç, kök nedeni bul ve düzelt, sonra `python tools/ai_memory.py gozlem kapat b12eb83f411c --kayit <kayit-id>`.
