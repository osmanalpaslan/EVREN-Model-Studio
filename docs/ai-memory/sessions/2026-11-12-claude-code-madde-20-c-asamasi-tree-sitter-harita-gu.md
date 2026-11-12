---
id: 2026-11-12-claude-code-madde-20-c-asamasi-tree-sitter-harita-gu
tarih: 2026-11-12
motor: Claude Code
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/c1-harita
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 20 C asamasi: tree-sitter harita, guncelleme, ses, terminal

## Görev
Madde 20'nin C aşaması (kullanıcı 2026-11-11: sırayla, onaysız; 2026-11-12 00:05: "bütün işlemleri ve testleri
tamamla, raporla; ardından uygulamayı detaylı analiz et, hata/eksikleri bul ve düzelt; en son bilgisayarı kapat;
hiçbir işlem için onay isteme"). C1 tree-sitter proje haritası, C2 güncelleme denetimi, C3 sesle yazma, C4 gerçek
terminal. B3/B4 gerçek API ölçümleri ana klasörde koşarken C maddeleri ayrı git çalışma kopyasında (`../EVREN-C`)
geliştirildi (koşu modülleri sonradan yükler; ana klasörde kaynak değişmemeli).

## Yapılanlar
- C1 (dal feat/c1-harita): agent/tsmap.py — dil başına küçük ÇEVRİMDIŞI tree-sitter paketleri (Go, Rust, Java, C#,
  JS, TS/TSX, PHP, C, C++, Ruby, Kotlin; hepsi MIT, toplam ~2 MB). `tree-sitter-language-pack` SEÇİLMEDİ: yeni
  sürümleri çözümleyiciyi ilk kullanımda internetten indiriyor (paket 2,2 MB) → çevrimdışı kurulumda çalışmaz.
  Sınıf/yapı/arayüz/trait/impl/enum/modül/ad alanı + üyeleri, fonksiyonlar, JS/TS `const f = () =>`; `_` ile başlayan
  gizli adlar yok. Paket yoksa / dil nesnesi hata verirse (ABI) None → eski yöntem (düzenli ifade), harita bozulmaz.
  projectmap: semboller sığmayınca eskiden HEPSİ atılıyordu → artık BAŞKA dosyalardan en çok başvurulan dosyaların
  sembolleri önce (Aider PageRank'in sade hâli: tanımlanan ad başka dosyada geçiyorsa dosya puanı +1). Python `ast`
  ile kaldı. Paket: requirements/pyproject, spec hiddenimports (importlib ile adla yüklenir), duman `harita_dilleri=11`
  + check_smoke denetimi.
- C2 güncelleme denetimi: `evren_studio/updates.py` (Qt'siz) — GitHub Releases `releases/latest` (depo PUBLIC,
  kimliksiz), sürüm karşılaştırma, taslak/ön sürüm önerilmez, "bu sürümü atla", yalnız kendi deposunun sayfa/indirme
  adresi açılır (yanıt başka adres gösterirse sabit sayfa), günde en çok bir kez (saat geri alınırsa da denetler).
  MainWindow: açılıştan 20 sn sonra arka planda (R-04), yeni sürümde oturum ekranında kart (İndir / Sürüm notları /
  Bu sürümü atla) + Windows bildirimi; KENDİLİĞİNDEN İNDİRMEZ/KURMAZ. Ayarlar > Genel "Yeni sürüm çıkınca haber ver",
  Yardım > "Güncellemeleri denetle" (elle; günlük sınır yok). Testlerde otomatik denetim kapalı
  (EVREN_STUDIO_NO_UPDATE_CHECK, conftest — yoklama ile aynı düzen). Ayarlar > Ajan'a "Gözetmen" (B4) seçeneği de eklendi.
- C3 sesle yazma: agent/voice.py (Qt'siz) + ui/voice_input.py + yazı kutusunda mikrofon düğmesi. İlk tıklamada onay
  (~600 MB) → `<veri>/ses/venv` (sistem Python'u, _base_python) + `pip install faster-whisper==1.2.1` + "small" model
  (int8, CPU). Kayıt QAudioSource ile (16 kHz tek kanal; desteklenmezse cihazın biçimi alınıp dönüştürülür), en çok
  120 sn; çeviri AYRI süreçte (uygulama donmaz, bellek iade), metin kutuya EKLENİR (gönderilmez), geçici ses silinir.
  Ses bilgisayardan çıkmaz. GERÇEK KURULUMDA bulunan: faster-whisper 1.2.1 dosyayı PyAV ile çözerken PyAV 19'da
  kaldırılmış `metadata_errors` parametresini kullanıyor → çöküyordu; WAV artık numpy ile okunup modele DİZİ olarak
  veriliyor (PyAV sürümünden bağımsız). Bulunan arayüz kusuru: oturum yokken (karşılama ekranı) `_note` MODAL pencere
  açıyor → sesle yazma notları orada mikrofon baloncuğuna gidiyor (`_voice_note`); test bunu yakaladı (takılma).

- ARAYÜZ GÖRSEL DENETİM (R-05/R-33, QT_QPA_PLATFORM=windows, iki tema): ui_denetim HATA 0 / KESİK 0 (açıkta 1 eski
  UYARI: karşılama kenar çubuğu soluk yazı 4,39 < 4,5 — yeni değil, analiz aşamasında). Görüntülere bakınca 3 kusur
  bulundu ve düzeltildi: (1) çip düğmelerinin SEÇİLİ hâli için stil yoktu → Kabuk/Günlük seçimi görünmüyordu
  (QPushButton[variant=chip]:checked eklendi); (2) mikrofonun "dinliyor" hâli yalnız ipucundaydı → "Dinliyor" yazısı +
  kırmızı çerçeve (Derin düğmesinin düzeni); (3) güncelleme kartı oturum yokken (karşılama ekranı — açılışta genelde
  bu) GÖRÜNMÜYORDU → kenar çubuğunda her ekranda görünen "Yeni sürüm X — indir" düğmesi ("atla" gizler).

## Test sonuçları
- C1: test_proje_haritasi_diller 21 (11 dil örneği, Go/C#/Rust haritası, çözümleyici yok → eski yöntem, bozuk kaynak,
  uyumsuz paket, bütçe darken en çok başvurulan önce, kendi dosyasını saymama) + test_f3_verimlilik harita testleri
  değişmeden geçti; mutasyon 10/10 (ilk turda 3 kaçtı: sıralama testi alfabetik sıraya denk geliyordu, ABI hatası ve
  gizli üye sınanmıyordu → testler güçlendirildi). test_kurulum_paketi duman denetimi güncellendi.
- C2: test_guncelleme 19 (sürüm karşılaştırma 8, taslak/ön sürüm/aynı, atla, ağ hatası, yabancı adres, günlük sınır,
  arayüz kartı + atla + 24 sa + ayar kapalı, test ortamında otomatik kapalı, Yardım'dan elle) + test_ayarlar_menu;
  mutasyon 10/10. GERÇEK GitHub: depoda henüz yayın yok → 404 → "güncel" (0,7 sn, hata yok); gerçek yanıt
  ayrıştırması başka herkese açık depoyla (ruff 0.17.4) doğrulandı. 0.5.0 yayınlanınca uçtan uca tekrar denenecek.
- C3: test_sesle_yazma 12 (kurulu değil, yarım kurulum, kurulum sırası, ayrı süreç + bozuk çıktı, eski çevirici
  yenilenir, WAV, 48 kHz stereo float → 16 kHz tek kanal, onay hayır/evet, metin eklenir gönderilmez, boş/hata notu,
  çok kısa kayıt, karşılama ekranında modal yok); mutasyon 9/9. GERÇEK: temiz klasöre kurulum 139 sn, 752 MB;
  Windows "Tolga" Türkçe sesiyle üretilen 3 cümle: 4,3 / 5,3 / 5,8 sn (model yükleme dahil); doğruluk iyi, küçük
  hatalar ("KDV" → "kat mater vergisi", "şüpheli" → "Şükeli", "Projeklasöründeki") — metin gönderilmeden düzeltilebilir.
  Gerçek mikrofonla kayıt: aşağıdaki C3 DÜZELTME maddesinde (gerçek mikrofon, sessizlik).
- C4: test_gercek_terminal 6 (GERÇEK kabukla: cd + değişken + Read-Host yanıtı; ping + Ctrl+C keser ve sonraki komut
  çalışır, boyut değişir; çıkışta açık kabuk kapanır; tuş dizileri; arayüzde Kabuk sekmesine yazılan komut çalışır,
  proje kapanınca süreç biter; kütüphane yoksa anlaşılır not) + duman denetimi; mutasyon 9/9 (kaçan Ctrl eşlemesi:
  test Qt metnini dolu veriyordu → boş metinle güçlendirildi).
- C3 DÜZELTME (C4 paketlemesine bakarken bulundu): kurulum paketi (spec excludes) `PySide6.QtMultimedia`'yı DIŞARIDA
  bırakıyor → QAudioSource ile kayıt kurulu uygulamada ÇALIŞMAZDI (kaynaktan çalışınca görünmüyor). QtMultimedia'yı
  eklemek ~60 MB (FFmpeg). Bunun yerine KAYIT da ses ortamında ayrı süreçte: `sounddevice` (MIT) ile `kaydet.py`
  ("HAZIR" yazınca dinliyor; durdurma dosyası gelince WAV yazıp çıkar; üst sınır 120 sn). Kurulum takımı sürümü
  (`kuruldu.json` surum=2): eski kurulumda kaydedici yoksa yeniden kurulur (gerçek: 3,4 sn). Uygulama kapanınca açık
  kayıt süreci öldürülür. GERÇEK MİKROFON: kaydedici 0,78 sn'de hazır, 2,5 sn kayıt, sessizlik → boş metin (uydurma
  yok; arayüz "anlaşılamadı" der), geçici klasör silindi. test_sesle_yazma 15; mutasyon (yeni parçalar) 8/8.
- C4 gerçek terminal: agent/ptyshell.py (Qt'siz; pywinpty MIT + pyte LGPL-3.0 ekran öykünücüsü) + ui/shell_view.py;
  Terminal sekmesi iki görünüm: "Günlük" (eski: ajan komutları + tek seferlik komut) / "Kabuk" (proje klasöründe
  SÜREKLİ PowerShell; cd/değişken kalır, Read-Host gibi soru soran komutlara yanıt; Ctrl+C keser, seçim varken
  kopyalar; Ctrl+V yapıştırır; ok tuşları/Tab/Home/End). Projenin .venv'i PATH'te (ajanla aynı ortam). ÖLÇÜLDÜ:
  pywinpty'nin varsayılan ConPTY arka ucunda yazılan Ctrl+C uzun komutu (ping) KESMİYOR, sonraki komut kuyrukta
  kalıyor; WinPTY arka ucunda kesiyor → önce WinPTY, açılamazsa ConPTY. Kapanış: ShellView aboutToQuit + ptyshell
  atexit (açık kabuk süreci kalmaz); proje kapanınca kabuk kapanır. Paket: winpty-agent.exe/winpty.dll/conpty.dll/
  OpenConsole.exe spec datas (`winpty/`; PyInstaller kancası yok), duman `terminal=var` + check_smoke. Ajanın
  komutları bu kabukta ÇALIŞMAZ (ajan kendi yalıtılmış komutlarını kullanır).

- TAM TAKIM (C dalı + master birleşik, sürüm 0.5.0): 1171/1171, 8 dk 54 sn (2026-11-12 18:51-19:00). İlk deneme
  01:36'da başlatılmıştı: 1 dk sonra Windows Modern Bekleme'ye geçti, 06:59'da Windows Update yeniden başlattı
  (olay günlüğü Kernel-Power 506/507, User32 1074) → koşu ve oturum kapandı; kod sorunu değil. Artık uzun
  işlerden önce `~/.claude/skills/yeni-proje/uyanik_tut.ps1` (SetThreadExecutionState).

- UYGULAMA ANALİZİ (kullanıcı 2026-11-12: "uygulamayı detaylı analiz et, hata/eksikleri bul"). Kaynaklar: gerçek
  kullanım veritabanı (salt okunur, yalnız hata türleri/sayıları), statik tarama (ruff F/B/PLE), ekran görüntüleri,
  ILERIDE/INDEX açık maddeleri. Bulgu 1 — ajan PowerShell'de bash heredoc'u (`python - <<'PY'`) deniyordu (gerçek
  kullanımda araç hataları arasında): komut hiç çalışmaz, adım kaybı. Düzeltme: tools.heredoc_hint — işaret + SONRAKİ
  satırda tek başına bitiş kelimesi varsa çalıştırmadan ne yapılacağını söyleyen ToolError (bit kaydırma `x << y`
  etkilenmez). Tetiklenen 4 / tetiklenmeyen 6 (gerçek PowerShell'de çalıştırılarak).

- Bulgu 2 (HATA) — tek örnek koruması YOKTU: `EVREN.Studio` mutex'i yalnız kurulum sihirbazı içindi; uygulama ikinci
  kez açılınca ikinci pencere açılıyor, aynı veritabanı/ayarlar iki süreçte kullanılıyor, zamanlanmış görevler, otomatik
  devam ve gözlem gönderimi İKİ KEZ çalışabiliyordu. Düzeltme: app._hold_mutex() 'zaten açık mı' döndürür; ikinci açılış
  kullanıcıya özgü yerel sokete (QLocalServer, UserAccessOption) "goster" yazar ve 0 ile çıkar; ilk pencere küçültülmüşse
  açılıp öne gelir. Ulaşamazsa (ör. eski sürüm açık) eskisi gibi pencere açar. Duman testi `tek_ornek=var` (QtNetwork).
  Testler: mutex, sinyal yok, pencere öne gelir, GERÇEK iki süreç (`python -m evren_studio` ×2 → ikinci 0 ile çıkar, ilk
  açık kalır); mutasyon 3/4 + gereksiz satır sadeleştirildi.

- Bulgu 3 (EKSİK) — otomatik yedek YOKTU: tüm oturumlar tek veritabanında (kullanıcının gerçek verisi 12,7 MB, 716
  mesaj); yalnız elle .zip yedeği vardı. Düzeltme: backup.auto_backup — günde bir kez `<veri>/yedekler/otomatik-YYYYMMDD.zip`
  (sqlite backup API: açık bağlantıda tutarlı kopya; önce .yaziliyor.zip sonra yeniden adlandırma), en yeni 7 kalır,
  kullanıcının kendi dosyalarına dokunmaz, anahtarlar girmez; açılıştan 60 sn sonra arka planda; Ayarlar > Gizlilik
  "Her gün otomatik yedek al" (varsayılan açık); testlerde kapalı (EVREN_STUDIO_NO_AUTO_BACKUP). test_otomatik_yedek 3;
  mutasyon 4/4.

- Bulgu 4 — okunurluk: açık temada kenar çubuğundaki "Henüz oturum yok" yazısı 4,39 kontrast (ui_denetim UYARI) →
  "dim" rolü. Bulgu 5 — statik tarama (ruff F/B/PLE, 6 bulgu): GERÇEK ÇALIŞMA HATASI YOK; tip açıklamasında eksik içe
  aktarma (usage_page QWidget), C2'de iki kez içe aktarılan sürüm adı temizlendi. Bulgu 6 — belge: ILERIDE §1.4/§1.7
  kurulum listesi yapılmış maddeleri işaretsiz gösteriyordu → kanıtıyla işaretlendi; doğrulanmayan (tüm kullanıcılar
  kurulumu/UAC) DOĞRULANMADI olarak kaldı.
- DÜZELTİLMEYEN / KULLANICI KARARI GEREKTİREN analiz bulguları: (a) OpenAI/Anthropic sağlayıcıları gerçek ücretli
  anahtarla hiç doğrulanmadı (izleniyor kaydı; ücretli → onay); (b) model davranış riskleri (zayıf model test dosyasını
  değiştirme, çok fazlı işte faz unutma) izleniyor — bekçiler var; (c) testlerde PySide6 QDragEnterEvent eskimiş kurucu
  uyarısı (yalnız test kodu); (d) tüm kullanıcılar (UAC) kurulumu ve kaldırmada veri silme seçeneği gerçek ortamda
  denenmedi.

- Paket 0.5.0 (ilk derleme 19:18): 210 MB, imzalı; duman harita_dilleri=11, tek_ornek=var, terminal=var. Terminal
  denetimi yalnız dosya varlığına bakıyordu → duman testi artık paketli uygulamada kabuğu GERÇEKTEN açıp komut çalıştırır
  (`terminal=var WinPTY`); kaynaktan doğrulandı, paket yeniden derlendi.

## Sorunlar ve kayıtlar
- R-29 tuzağı bu oturumda iki kez daha: bash heredoc içindeki Python'da `\\n` → gerçek satır sonu oldu (test dosyası
  bozuldu, Edit aracıyla düzeltildi). Kural zaten var; uygulama disiplini: test dosyası yamalarını Edit ile yap.

## Sonraki motor için notlar
- C2-C4 aynı çalışma kopyasında sürüyor; B3/B4 ölçüm sonuçları ana klasördeki 2026-11-11 oturum günlüğünde.
