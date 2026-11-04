---
id: 2026-11-05-claude-code-masaustu-madde-12-claude-code-tarzi-arayuz-zamanl
tarih: 2026-11-05
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/claude-tarzi-arayuz
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
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
- 12d GitHub: `agent/github.py` + `ui/github_card.py` + Git paneli (Gönder/Al/Depo oluştur). Ücretsiz: GitHub'ın
  resmî `gh` aracı (`auth login --web`); belirteç gh tarafından Credential Manager'da, uygulama görmez. gh yoksa winget
  ile kurulum düğmesi. Durum yalnız GitHub menüsü açılınca denetlenir (açılışta ağ yok).

## Test sonuçları
- tests/test_ayarlar_menu.py 16, mutasyon 6/6; ui_denetim iki tema HATA 0.
- tests/test_zamanlayici.py 23; mutasyon zaman 6/6, motor 10/10, gözetimsiz kip 3/3 (ilk koşuda 3 mutant kaçtı → testler güçlendirildi).
- tests/test_github.py 16 (sahte gh + yerel çıplak git deposu; ağ yok); mutasyon 11/11 (ilk koşuda 1 kaçtı).
- Ekran: zamanlanmış liste/ayrıntı/oluşturma penceresi iki tema; düzeltilen: ana düğme simgesi görünmüyordu, saat kutusu temasızdı, geri oku ters.
- Kenar çubuğu: test_auto_pro (sayfa görünürlüğü yeni API'ye uyarlandı), test_kenar_cubugu_surukleme, test_f5_arayuz geçti.

## Sorunlar ve kayıtlar
- Süreç hatası (kendi): 12c sonrası tam takım koşarken kaynak değiştirdim (GitHub kartı) → o koşu (854/854) geçersiz
  sayıldı; Faz D sonunda temiz tam koşu. Kural zaten vardı (tam koşuda yalnız belge işi).
- Mutasyon koşusunda depo adı denetimi kaldırılınca sahte gh repo kökünde `etc; rm -rf` klasörü açtı (silindi): test
  sonuca değil "gh hiç çağrılmadı mı"ya bakacak şekilde güçlendirildi. Denetimin değerini de gösterdi.
- Tasarım tuzağı (önlendi): `SessionView.set_model/set_mode` seçimi kullanıcının VARSAYILAN ayarı olarak kaydediyor;
  zamanlanmış görevin görünmez oturumu bunu çağırırsa kullanıcının ayarı değişirdi → görünmez oturumda `_remember` kapalı.

## Sonraki motor için notlar
- Zamanlayıcı yalnız uygulama açıkken çalışır (Claude Code yerel görevleri gibi); kaçırılanlardan son 7 günde tek telafi.
- Temiz tam koşu 1 (ad92072): 869/870 — test_github giriş reddi testinde JSONDecodeError: sahte gh çağrı günlüğüne
  yazarken test okudu (yarım satır, yük altında yarış). Tek başına 3/3 geçti. Düzeltme: yardımcı yalnız tamamlanmış
  satırları okur (doğrulama aynı). Tam koşu tekrarlandı.
- Temiz tam koşu 2 (3159bb0): 870/870 (6 dk 11 sn). R-13: E2E_OK · arayüz 15/15 · ajan 5/6 (glm 503). Gerçek
  zamanlanmış görev (tests/e2e_zamanlayici_real_api.py): 6/6, 37 sn. Zorluk paketi koşulmadı (ajan davranışı değişmedi).
- Doğrulanmadı: GitHub tarayıcı onayının tamamlanması, gerçek GitHub'da depo oluşturma/push (sahte gh + yerel git).
