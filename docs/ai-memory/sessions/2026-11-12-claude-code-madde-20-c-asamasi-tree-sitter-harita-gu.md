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

## Sorunlar ve kayıtlar
- R-29 tuzağı bu oturumda iki kez daha: bash heredoc içindeki Python'da `\\n` → gerçek satır sonu oldu (test dosyası
  bozuldu, Edit aracıyla düzeltildi). Kural zaten var; uygulama disiplini: test dosyası yamalarını Edit ile yap.

## Sonraki motor için notlar
- C2-C4 aynı çalışma kopyasında sürüyor; B3/B4 ölçüm sonuçları ana klasördeki 2026-11-11 oturum günlüğünde.
