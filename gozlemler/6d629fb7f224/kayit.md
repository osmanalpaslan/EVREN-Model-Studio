---
id: 6d629fb7f224
baslik: Ajan uçtan uca senaryosu düştü: glm-5.3 text
tur: e2e_basarisiz
onem: orta
alan: test
durum: acik                # acik | cozuldu | kabul-edildi
kaynak: e2e
ilk_gorulme: 2026-11-03T21:44:33+00:00
cozuldu_tarih:
cozum_kaydi:
---

# Ajan uçtan uca senaryosu düştü: glm-5.3 text

## Belirti (otomatik)
e2e_basarisiz: read_file=False doğru_değer=False

## Konum (otomatik)
- (yığın izi yok)

## Ayrıntı (otomatik)
- model: glm-5.3
- protokol: text
- durma: done
- adim: 1
- kaynak_betik: e2e_agent_real_api

## Ne yapılmalı
Geliştirici motoru: kullanıcıya bildir; onaylarsa `python tools/ai_memory.py gozlem kayda-donustur 6d629fb7f224` ile docs/ai-memory/incidents altına kayıt aç, kök nedeni bul ve düzelt, sonra `python tools/ai_memory.py gozlem kapat 6d629fb7f224 --kayit <kayit-id>`.
