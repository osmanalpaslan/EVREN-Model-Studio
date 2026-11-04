---
id: 2026-11-05-claude-code-masaustu-madde-12-claude-code-tarzi-arayuz-zamanl
tarih: 2026-11-05
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/claude-tarzi-arayuz
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 12 Claude Code tarzı arayüz, zamanlayıcı, GitHub

## Görev
Kullanıcı (2026-11-04 gece): Claude Code masaüstündeki görev zamanlayıcıyı (görülebilen, yönetilebilen) bu uygulamaya
getir; Ayarlar'ı Claude Code gibi menülere böl, yeni ayarlar da ilgili menüye; tüm tasarım Claude Code gibi; GitHub'a
tarayıcı yönlendirmesiyle ücretsiz bağlanma ve entegrasyon. Onay istemeden ilerle.

## Yapılanlar
- 12a Ayarlar: sol menü + arama, 14 kategori (`SettingsPage.CATEGORIES`, `_add`, `open_category`, `_fold`).
- 12b Kenar çubuğu: `PRIMARY_PAGES` (Zamanlanmış, Skill) üstte; altta Ayarlar + "Diğer" ⋯ menüsü (`MORE_PAGES`);
  `set_available_pages`, `page_visible`.
- 12c Zamanlayıcı: `agent/schedule.py` (Saatlik/Günlük/Hafta içi/Haftalık/Elle/Özel cron ≥1 sa; son 7 günde tek telafi),
  `ui/schedule_host.py` (dakikada bir; tek seferde tek çalıştırma + kuyruk; sürerken gelen zaman "atlandı";
  görünmez `SessionView.unattended` oturum: önce plan / proje önerisi / bütçe sorusu / anahtar uyarısı kapalı, seçimler
  varsayılana yazılmaz; kota beklerken bitmiş sayılmaz; süre sınırı; telafi + bitiş bildirimi; bilgisayarı uyanık tut),
  `ui/scheduled_page.py`, DB tabloları (yalnız ekleme), kenar çubuğunda "Zamanlanmış ·" alt yazısı, çalışan görev
  oturumunu açarken "Durdur ve aç" koruması. Modlar yalnız Otomatik / Plan (başında kimse yok).
- 12d GitHub: sürüyor.

## Test sonuçları
- tests/test_ayarlar_menu.py 16, mutasyon 6/6; ui_denetim iki tema HATA 0.
- tests/test_zamanlayici.py 23; mutasyon zaman 6/6, motor 10/10, gözetimsiz kip 3/3 (ilk koşuda 3 mutant kaçtı → testler güçlendirildi).
- Ekran: zamanlanmış liste/ayrıntı/oluşturma penceresi iki tema; düzeltilen: ana düğme simgesi görünmüyordu, saat kutusu temasızdı, geri oku ters.
- Kenar çubuğu: test_auto_pro (sayfa görünürlüğü yeni API'ye uyarlandı), test_kenar_cubugu_surukleme, test_f5_arayuz geçti.

## Sorunlar ve kayıtlar
- Tasarım tuzağı (önlendi): `SessionView.set_model/set_mode` seçimi kullanıcının VARSAYILAN ayarı olarak kaydediyor;
  zamanlanmış görevin görünmez oturumu bunu çağırırsa kullanıcının ayarı değişirdi → görünmez oturumda `_remember` kapalı.

## Sonraki motor için notlar
- Zamanlayıcı yalnız uygulama açıkken çalışır (Claude Code yerel görevleri gibi); kaçırılanlardan son 7 günde tek telafi.
