---
id: 2026-10-16-arka-plan-gorevine-referans-tutulmuyordu
tarih: 2026-10-16
tur: risk
onem: orta
durum: cozuldu
alan: ui/is-parcacigi
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PySide6 6.12
etiketler: [qt, gc, task, sinyal]
kurallar: [R-11]
---

# Arka plan görevine (Task) referans tutulmuyordu

## Belirti
Tüm sayfalar `Task(job, on_done=..., on_error=...).start()` biçimini
kullanıyordu; Task nesnesine kimse referans tutmuyordu. Gözlenen bir hata
yok; kod incelemesinde risk olarak bulundu.

## Kök neden
Tahmin (yeniden üretilmedi): iş parçacığı bitince Task ve içindeki
`TaskSignals` QObject'i, kuyruklu sonuç sinyali ana iş parçacığına
ulaşmadan çöpe gidebilir; bu durumda geri çağrı hiç çalışmaz ve düğme
"hiçbir şey yapmıyor" gibi görünür.

## Çözüm
`workers.py`: çalışan görevler modül düzeyinde `_ACTIVE` kümesinde tutulur;
sonuç/hata ana iş parçacığında teslim edildikten sonra bırakılır.
`active_task_count()` eklendi.

## Kanıt
`tests/test_ui_pages.py::test_arka_plan_gorevi_sonucu_teslim_eder`:
referanssız 20 görev + `gc.collect()` → 20 sonucun hepsi teslim edildi,
etkin görev sayısı 0'a döndü.

## Önleme
R-11.

## İlgili dosyalar
src/evren_studio/ui/workers.py
