---
id: 2026-11-05-claude-code-masaustu-madde-13-masaustu-kontrolu-windows-mcp-v
tarih: 2026-11-05
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/masaustu-kontrol
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 13 masaüstü kontrolü (Windows-MCP) ve masaüstü QA

## Görev
Kullanıcı (2026-11-05): "Uygulamaya imleçle masaüstü kullanımı ve QA uygulama testi gibi görsel davranışlar
ekleyebilir miyiz? Benzer ücretsiz repolardan destek al; en iyisini, en başarılısını seç."

## Yapılanlar
- Araştırma: Windows-MCP (CursorTouch, MIT, ~11,1 bin yıldız, PyPI windows-mcp 0.8.8 2026-10-10, Python ≥3.14) seçildi:
  UI Automation ağacını metin olarak verir (görsel model şart değil → EVREN metin modelleri de kullanabilir), kendi
  güvenliği var (kontrol ışığı "AI", fareyi oynatınca / Ctrl+Alt+Shift+Backspace ile kullanıcıya dönüş). Elenenler:
  Microsoft UFO (ayrı ajan çatısı), Agent-S (güçlü görsel/konumlandırma modeli ister), pywinauto-mcp / windows-gui-mcp
  (küçük kitle).
- `agent/mcp.py`: hazır ayar "masaustu" (`windows_config`, `install_windows_mcp`: boot venv → uv 0.12.20 → uv ile
  Python 3.14 venv → windows-mcp==0.8.8; veri klasöründe), `when="masaustu"` (yalnız `DESKTOP_WORDS`), tam yetkili
  araçlar (PowerShell, FileSystem, Registry, Process, Clipboard, Scrape, Notification) DIŞARIDA, telemetri kapalı,
  `--control-policy balanced`, okuma araçları dışındakiler izin sisteminde "komut"; kullanıcıya `DESKTOP_NOTE`, modele
  `DESKTOP_PROMPT`.
- `agent/qa.py`: `QaState.target` (web | masaustu), masaüstü plan/senaryo istemleri, `DesktopQaTools.visual_check`
  (Windows-MCP Screenshot → görsel model), `save_mcp_image`. `ui/qa_ui.py`: `/qa-masaustu`, hedefe göre ön koşul ve araç.
- Ayarlar > Bağlayıcılar'da "Masaüstü kontrolünü kur / etkin / Dene" satırı.
- `tests/e2e_masaustu_real_api.py` (ajan: Tk hesap uygulamasında 2+3; QA: hatalı/doğru sürüm) — HENÜZ ÇALIŞTIRILMADI.

## Test sonuçları
- tests/test_masaustu.py 25 (tetiklenen/tetiklenmeyen, güvenlik yapılandırması, kurulum sırası, not/istem, görsel göz,
  QA istemleri, ön koşul, Ayarlar satırı); mutasyon 13/13 (ilk koşuda 1 kaçtı → test güçlendirildi).
- Tam takım 895/895 (6 dk 0 sn).
- Gerçek kurulum: windows-mcp 0.8.8 yalıtılmış deneme veri klasörüne 40 sn'de kuruldu (build/masaustu_deneme).
- DOĞRULANMADI: sunucunun gerçekten başlatılması ve masaüstünde çalışması. Claude Code otomatik denetimi, fare/klavyeyi
  yönetebilen sunucuyu başlatan yoklamayı (yalnız okuyan araçlar dahil) engelledi; atlatılmadı. Kullanıcı izniyle
  `tests/e2e_masaustu_real_api.py hepsi` koşulmalı.

## Gerçek masaüstü denemeleri (kullanıcı izniyle, 2026-11-05 akşam)
1. 19:07 — masaüstü araçları HİÇ sunulmadı: README'deki `--control-policy` 0.8.8'de yok, sunucu "No such option" ile
   kapanıyordu; ajan araçsız kendi PowerShell UIA betiklerini yazdı. Düzeltme: seçenek kaldırıldı + kurulumda
   `check_windows_flags` (kullanılan her seçenek kurulu sürümün `serve --help`'inde olmalı).
2. 19:21 — araçlar sunuldu (14), ajan 4/5: "Sonuç: 5" dedi ama uygulama HİÇ hesaplamadı (sonuc.txt yok). Kök neden:
   (a) Tk penceresi iç öğeleri UIA'ya bildirmiyor (yalnız başlık çubuğu) → ajan koordinatı koddan TAHMİN etti;
   (b) göremediği ekran görüntüsünden sonuç UYDURDU. Düzeltme: Screenshot ajana sunulmaz (QA visual_check görsel modele
   sorar), görsel yer tutucusu "GÖREMEZSİN" der, DESKTOP_PROMPT koordinat tahmini ve doğrulanmamış sonucu yasaklar,
   test uygulaması Qt'ye geçti (öğeler adlarıyla UIA'da). Ayrıca Type `caret_position:"end"` iki kez End bastı.
3. 19:31 — Snapshot `use_vision:true` ile sunucu 90 sn'de yanıt vermedi (3 kez); durduruldu. Kullanıcı: "End tuşu
   ekran yakalamayı açıyor, test yarıda kalır" → End basımı ekran yakalamayı açmış olabilir. Düzeltme: `desktop_guard`
   (Snapshot'ta görsel hep kapalı; engelli tuşlar — varsayılan End, Ayarlar > Bu bilgisayar — Type caret ve Shortcut'ta
   uygulanır), `desktop_blocked_keys` ayarı.
- Birim testinde takılma: Ayarlar'ı kaydeden test "Kaydedildi" kutusunu kapatmadığı için görünmez pencerede bekledi
  (20 dk); düzenek düzeltildi, 87/87. Mutasyon toplam 22/22.

## Kullanıcı istekleri (2026-11-05 gece) ve 4. deneme
- "Kullanıcı test sırasında fareyi/klavyeyi yanlışlıkla kullanabilir; test durmamalı, kaldığı yerden sürmeli" → 0.8.8
  kodu okundu (tools/control_notifications.py, desktop/control.py): kontrol kullanıcıdayken çağrı hiçbir şey yapmadan
  USER_CONTROL/TAKEOVER_PENDING ile reddediliyor, son girdiden 10 sn sonra kontrol döner; yarıda kesilen CONTROL_PREEMPTED
  + executed_steps. `McpToolset._call_desktop`: bekle → aynı adımı tekrarla; yarıda kesilende ekranı yeniden okut; 5 dk →
  `user_paused` → koşucu `user_control` ile durur → "Devam et" kartı (DESKTOP_RESUME_PROMPT).
- "Ajan QA testlerini gerektiğinde kendi açabilmeli; kullanıcı kapatmışsa çalışmasın" → `test_araci_ac` aracı
  (runner.TEST_TOOL_SPEC, app_context.TestTools), `auto_test_tools` ayarı (varsayılan açık), /qa ve /qa-masaustu eksik aracı
  kendisi kurar. Kullanıcının Bağlayıcılar'da kapattığı araç (kayıtlı + enabled=false) açılmaz.
- 4. deneme (21:02): App ile açılan Qt uygulamasından sonra Snapshot/WaitFor 90 sn yanıtsız. Teşhis: ControlStatus ve
  DisplayInventory anında yanıt veriyor, takılan yalnız Snapshot; IsHungAppWindow → bu oturumun çalıştığı VS Code
  penceresi ASKIDA ("Yanıt Vermiyor"). 0.8.8 öğe ağacını tararken askıdaki pencerede sonsuza kadar bekliyor. Düzeltme:
  her masaüstü çağrısından önce askıdaki programlar `WINDOWS_MCP_EXCLUDE_PROCESSES`'e eklenip sunucu yenilenir; zaman
  aşımında bir kez yenileyip yeniden denenir (`hung_window_processes`, `McpManager.restart`). Testler gerçek masaüstüne
  bakmasın diye conftest taramayı kapatır.
- 5. deneme (21:20): ajan `test_araci_ac {"tur":"masaustu"}` ile aracı KENDİSİ açtı (doğrulandı), App ile Qt uygulamasını
  başlattı; Snapshot yine takıldı. Askıdaki iki pencere: Code.exe (atlanıyordu) ve "(Yanıt Vermiyor)" hayalet penceresi —
  sahibi korumalı `dwm.exe`; OpenProcess reddettiği için adı okunamadı, atlanmadı. Düzeltme: `_process_name` süreç
  açılamazsa adı Toolhelp32 süreç listesinden alır (`_name_from_snapshot`); test (System pid 4 açılamaz → "System"),
  mutasyon 4/4.
- 6. deneme (21:28, 2/5): dwm.exe de atlandığı hâlde Snapshot 2×90 sn yanıtsız. Kurulu 0.8.8 kaynağı okundu: atlama
  listesi yalnız öğe ağacı taramasında (`Tree.get_window_wise_nodes`) uygulanıyor; ondan ÖNCE `Desktop.get_windows`
  (her görünür pencerede ControlFromHandle/Name/GetPattern) ve `get_foreground_window` askıdaki pencereye UIA ile giriyor.
  Düzeltme: sunucu artık `venv\python.exe -P agent\wmcp_baslatici.py serve …` ile açılıyor; başlatıcı her taramada
  askıdaki (IsHungAppWindow) ve atlanan programların pencerelerini `get_controls_handles`'tan çıkarır, askıdaki ön
  pencerede `get_foreground_window` None döner; paket sürümü değişmez. İstemci tarafı ortam değişkeni + yeniden başlatma
  kaldırıldı (yalnız bilgi notu). Eski kayıt (`{windows_mcp}`) `legacy_commands` ile yeni tanıma taşınır. Gerçek ölçüm
  (aynı askıdaki VS Code + hayalet dururken, yalnız okuma): Snapshot 15,9 / 18,9 / 15,4 / 18,4 sn, dolu (pencereler +
  masaüstü öğeleri). Testler: test_wmcp_baslatici 8, mutasyon 7/7 + 7/7.

- 7. deneme (21:50, durduruldu): Snapshot artık takılmıyor (16 sn) ama ajanın açtığı test uygulamasının penceresi hiç
  oluşmadı: e2e betiğinin `QT_QPA_PLATFORM=offscreen` ayarı sunucuya ve açılan uygulamaya geçiyordu (test düzeneği
  hatası; 4./5. denemeleri de etkilemiş olabilir). Betik Qt kurulduktan sonra değişkeni ortamdan çıkarıyor.
- 8. deneme (22:00, 2/5, VS Code dondu): kullanıcı donma sırasında fareyi kullandı → ajan **~63 sn bekleyip sürdürdü**
  (devralma beklemesi gerçek masaüstünde doğrulandı). Ajan kutulara 2 ve 3 yazdı, Topla'ya bastı, uygulama **gerçekten 5
  hesapladı** (sonuc.txt). Kalan: 0.8.8 Snapshot masaüstü uygulamasında düz yazıyı (etiket) hiç vermiyor (yalnız
  tarayıcıda) → ajan sonucu doğrulayamadı (uydurmadı); 10 dk sınırı doldu. Düzeltme: başlatıcı salt-okunur `WindowText`
  aracını ekler (pencerenin düz yazıları + konumları); gerçek Qt penceresinde 6,5-8 sn, "Durum: hazır" okundu. Sınır:
  uygulama etikete erişilebilir ad verdiyse Windows yalnız adı bildirir (gerçek UIA incelemesi). e2e süresi 15 dk.

## Sorunlar ve kayıtlar
- Engel (kayıt gerektirmez): motorun ortamında masaüstü kontrol sunucusunu başlatmak kullanıcı izni ister.

## Sonraki motor için notlar
- Birleştirmeden ÖNCE gerçek deneme (R-07/R-25): `.\.venv\Scripts\python.exe -u tests\e2e_masaustu_real_api.py hepsi`
  (çalışırken bilgisayara dokunulmamalı). Snapshot çıktısının biçimi (öğe kimliği/koordinat) README'de yazmıyor; gerçek
  çıktıya göre DESKTOP_PROMPT gerekirse ayarlanır. Araç adları (Snapshot, Click…) 0.8.8 README'sinden; gerçek listeyle
  karşılaştır (eksik araç `notes`'ta "bulunamayan araçlar" diye görünür).
