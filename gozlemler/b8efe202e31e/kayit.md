---
id: b8efe202e31e
baslik: Arka plan görevi hata verdi: OperationalError
tur: gorev_hatasi
onem: yuksek
alan: genel
durum: cozuldu                # acik | cozuldu | kabul-edildi
kaynak: uygulama
ilk_gorulme: 2026-11-12T18:27:29+00:00
cozuldu_tarih: 2026-11-12T23:02:25+00:00
cozum_kaydi: 2026-11-13-arka-plan-gorevi-hata-verdi-operationalerror
---

# Arka plan görevi hata verdi: OperationalError

## Belirti (otomatik)
gorev_hatasi · OperationalError: unable to open database file

## Konum (otomatik)
- `src/evren_studio/ui/workers.py:70 _run`
- `src/evren_studio/ui/main_window.py:146 <lambda>`
- `src/evren_studio/backup.py:71 auto_backup`
- `src/evren_studio/backup.py:24 backup`

## Ayrıntı (otomatik)
- gorev: MainWindow._auto_backup.<locals>.<lambda>

## Ne yapılmalı
Geliştirici motoru: kullanıcıya bildir; onaylarsa `python tools/ai_memory.py gozlem kayda-donustur b8efe202e31e` ile docs/ai-memory/incidents altına kayıt aç, kök nedeni bul ve düzelt, sonra `python tools/ai_memory.py gozlem kapat b8efe202e31e --kayit <kayit-id>`.
