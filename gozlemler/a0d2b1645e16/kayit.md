---
id: a0d2b1645e16
baslik: Tur bağlam sınırında durdu
tur: tur_sonu
onem: orta
alan: ajan
durum: acik                # acik | cozuldu | kabul-edildi
kaynak: e2e
ilk_gorulme: 2026-11-03T19:56:29+00:00
cozuldu_tarih:
cozum_kaydi:
---

# Tur bağlam sınırında durdu

## Belirti (otomatik)
tur_sonu

## Konum (otomatik)
- (yığın izi yok)

## Ayrıntı (otomatik)
- durma: context_limit
- model: deepseek-v4.1-flash
- rol: kod
- adim: 18
- mod: auto

## Ne yapılmalı
Geliştirici motoru: kullanıcıya bildir; onaylarsa `python tools/ai_memory.py gozlem kayda-donustur a0d2b1645e16` ile docs/ai-memory/incidents altına kayıt aç, kök nedeni bul ve düzelt, sonra `python tools/ai_memory.py gozlem kapat a0d2b1645e16 --kayit <kayit-id>`.
