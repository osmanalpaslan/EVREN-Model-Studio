---
id: 2983bc967976
baslik: Zorluk paketi görevi düştü: girdi
tur: e2e_basarisiz
onem: orta
alan: test
durum: acik                # acik | cozuldu | kabul-edildi
kaynak: e2e
ilk_gorulme: 2026-11-06T19:36:54+00:00
cozuldu_tarih:
cozum_kaydi:
---

# Zorluk paketi görevi düştü: girdi

## Belirti (otomatik)
e2e_basarisiz: kalan kontroller: girdi beklediğini açıkladı

## Konum (otomatik)
- (yığın izi yok)

## Ayrıntı (otomatik)
- gorev: girdi
- model: gemma-4-31b
- sonuc: 0/1
- kaynak_betik: zorluk
- durma: done

## Ne yapılmalı
Geliştirici motoru: kullanıcıya bildir; onaylarsa `python tools/ai_memory.py gozlem kayda-donustur 2983bc967976` ile docs/ai-memory/incidents altına kayıt aç, kök nedeni bul ve düzelt, sonra `python tools/ai_memory.py gozlem kapat 2983bc967976 --kayit <kayit-id>`.
