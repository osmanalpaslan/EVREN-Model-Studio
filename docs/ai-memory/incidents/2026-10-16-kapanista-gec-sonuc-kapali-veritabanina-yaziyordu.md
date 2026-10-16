---
id: 2026-10-16-kapanista-gec-sonuc-kapali-veritabanina-yaziyordu
tarih: 2026-10-16
tur: hata
onem: dusuk
durum: cozuldu
alan: ui/is-parcacigi
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PySide6 6.12
etiketler: [kapanis, task, sqlite]
kurallar: [R-11]
---

# Kapanışta geç gelen arka plan sonucu kapalı veritabanına yazıyordu

## Belirti
Pencere açılış profillemesinde: `sqlite3.ProgrammingError: Cannot operate on a
closed database` (`models_page.set_models` → `db.get_model_health`).

## Kök neden
Doğrulandı: Modeller sayfası açılışta model listesini arka planda ister.
Kullanıcı pencereyi bu sırada kapatırsa `AppContext.close()` veritabanını
kapatır; sonuç sonra gelip veritabanını okumaya çalışır. Konsolsuz
çalıştırmada (pythonw) bu, yakalanmamış hata penceresi açabilirdi.

## Çözüm
`workers.set_accepting(False)` kapanışta çağrılır; `Task` geç gelen sonuç ve
hata geri çağrılarını işlemez. Yeni pencere açılırken tekrar `True` olur.

## Kanıt
`tests/test_auto_compact.py::test_kapanista_gec_gelen_sonuc_islenmez`:
düzeltmesiz BAŞARISIZ (ProgrammingError), düzeltmeyle geçti.

## Önleme
R-11 kapsamında: arka plan geri çağrıları uygulama yaşam döngüsünü denetlemeli.

## İlgili dosyalar
src/evren_studio/ui/workers.py, src/evren_studio/ui/main_window.py
