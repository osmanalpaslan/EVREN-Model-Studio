# İleride Yapılacaklar

> Kararlaştırılmış ama henüz başlanmamış işler. Her madde, başlayan motorun
> kullanıcıya yeniden sormadan ilerleyebileceği kadar ayrıntılıdır. Bir işe
> başlarken maddeyi "Devam ediyor", bitince "Yapıldı (tarih, dal/PR)" diye
> güncelle; silme. Kararları değiştirmeden önce kullanıcıya sor.
>
> Oturum başında `tools/ai_memory.py baslangic` bu dosyayı PROJECT_STATE.md
> "Sıradaki iş" bölümü üzerinden gösterir.

---

## 1. Profesyonel Windows kurulum paketi (Setup.exe) — BEKLİYOR

**Kullanıcı kararı (2026-10-19):** "Uygulamayı yapacağım ama şimdi değil."
- Tek dosyalık (onefile) EXE **İSTENMİYOR**. Kurulumu olan, profesyonel bir
  uygulama olacak: kurulum sihirbazı, Başlat menüsü, kaldırıcı, güncelleme.
- Uygulamanın ihtiyaç duyduğu harici programlar varsa kurulum bunları da
  içerecek veya kuracak.
- Hedef kullanıcıların ve diğer geliştirme bilgisayarlarının çoğunda Comodo
  YOK; paket buna göre tasarlanır. Comodo'lu bilgisayar ayrıca ele alınır (1.9).
- "En uygun ve olması gereken neyse" motorun teknik kararına bırakıldı; aşağıdaki
  kararlar bu yetkiyle alındı. Ücretli adımlar (kod imzalama) için yine sorulur.

### 1.1 Mimari kararlar

| Konu | Karar | Neden |
|---|---|---|
| Paketleyici | **PyInstaller, klasörlü (onedir)**, pencereli (konsolsuz) | Olgun, ücretsiz, PySide6 desteği iyi. Onedir her açılışta geçici klasöre açılmaz: hızlı başlar, antivirüs yanlış alarmı daha az |
| Kurulum aracı | **Inno Setup 6** (ücretsiz, açık kaynak; `ISCC.exe`) | Türkçe arayüz hazır (`Turkish.isl`), kullanıcı veya tüm kullanıcılar kurulumu, kaldırıcı, yükseltme, imzalama desteği |
| Değerlendirilip ertelenen | MSIX (imza zorunlu, Store akışı), Nuitka (derleme uzun; antivirüs açısından daha iyi olabilir; sorun çıkarsa yeniden değerlendir), cx_Freeze, WiX/MSI (kurumsal dağıtım istenirse) | — |
| Kurulum kapsamı | Varsayılan **yalnız bu kullanıcı** (`PrivilegesRequired=lowest`, `PrivilegesRequiredOverridesAllowed=dialog`): yönetici izni gerekmez. İsteyen "tüm kullanıcılar" seçer (UAC ister) | Kurumsal bilgisayarlarda yönetici izni olmayan kullanıcılar da kurabilsin |
| Kurulum yeri | Kullanıcı: `%LOCALAPPDATA%\Programs\EVREN Studio` · Tüm kullanıcılar: `%ProgramFiles%\EVREN Studio` | Windows standardı |
| Kullanıcı verisi | Değişmez: `%LOCALAPPDATA%\EVREN-Model-Studio` (config.json, evren.db, attachments, logs), anahtar Credential Manager'da | Kaynak koddan kurulumla aynı yer: geçişte veri kaybolmaz |
| Mimari | Yalnız **Windows 10/11 x64** | PySide6 6.7+ gereksinimi |
| Sürüm | Tek kaynak: `evren_studio.__version__` → pyproject, EXE sürüm bilgisi ve Inno `AppVersion` buradan | Şu an sürüm `pyproject.toml` ve `__init__.py`'de iki kez yazılı (0.2.0) |
| Dağıtım | GitHub Releases: `EVREN-Studio-Setup-<sürüm>.exe` + SHA256 | Depo herkese açık; GitHub Actions Windows derleyicisi ücretsiz |

### 1.2 Harici programlar (kurulumun içine alınacaklar)

**Uygulamanın kendisi için zorunlu olanlar — pakete GÖMÜLÜ gelir, ayrı kurulum yok:**
- Python çalışma zamanı + PySide6 (QtCore, QtGui, QtWidgets, QtSvg) + httpx,
  keyring, markdown, pygments (PyInstaller toplar).
- MSVC çalışma zamanı DLL'leri (`vcruntime140*.dll`, `msvcp140*.dll`):
  PyInstaller/PySide6 ile gelir. **Doğrula**: temiz makinede eksikse kuruluma
  "Microsoft Visual C++ 2015-2022 Redistributable (x64)" eklenir ve kayıt
  defterinde yoksa sessiz kurulur (`/install /quiet /norestart`).
- Windows PowerShell 5.1 (ajan komutları) ve Credential Manager: Windows'ta yerleşik.

**Kod ajanının kullanıcı projelerinde çalıştırdığı araçlar — İSTEĞE BAĞLI kurulum sayfası:**

Gömülü Python yalnız uygulamanın içindir; ajanın kullanıcı projesinde `python`,
`git`, `npm` çalıştırabilmesi için bu programların sistemde kurulu olması gerekir.
Kurulum sihirbazında "Geliştirme araçları" sayfası (onay kutuları):

| Araç | Varsayılan | Kurulum yolu |
|---|---|---|
| Git for Windows | işaretli (kurulu değilse) | winget `Git.Git` → yoksa resmî yükleyiciyi indir (`/VERYSILENT /NORESTART`) |
| Python 3.12 | işaretli (kurulu değilse) | winget `Python.Python.3.12 --scope user` → yoksa python.org yükleyicisi (`/quiet InstallAllUsers=0 PrependPath=1`) |
| Node.js LTS | işaretsiz | winget `OpenJS.NodeJS.LTS` → yoksa resmî MSI (`/qn`) |

- Zaten kuruluysa satır "kurulu (sürüm)" diye gösterilir ve atlanır. Algılama
  `agent/environment.py`'deki bilinen araç listesiyle aynı olmalı (tek doğruluk kaynağı).
- İndirmeler Inno Setup 6.1+ `DownloadTemporaryFile` ile ve **SHA256
  doğrulamasıyla** yapılır; adres/özet listesi `installer/prereqs.json`'da tarihli tutulur.
- Varsayılan kurulum **çevrimiçi** (küçük boyut). İstenirse ileride "çevrimdışı
  tam kurulum" yapı seçeneği: yükleyiciler pakete gömülür (boyut büyür).
- Kurulum sonrası eksik kalan araçlar uygulamadaki ortam denetimiyle
  (`agent/environment.py`, Otomatik/Manuel kurulum) yine kurulabilir.

### 1.3 Kurulum sihirbazının özellikleri

- Türkçe arayüz (İngilizce seçeneği), lisans sayfası (MIT, `LICENSE`).
- Başlat menüsü kısayolu; masaüstü kısayolu (onay kutusu, varsayılan işaretli).
- "Kurulumdan sonra EVREN Studio'yu başlat" seçeneği.
- **Yükseltme**: sabit `AppId` (GUID, bir kez üretilip değiştirilmez); eski
  sürümün üzerine kurulur, veriye dokunmaz. Çalışan uygulama `AppMutex`
  ("EVREN.Studio") ile algılanır ve kapatılması istenir. Uygulamaya aynı adlı
  mutex eklenmeli.
- **Kaldırma**: Ayarlar > Uygulamalar'da görünür. Kaldırırken "Kişisel verileri
  de sil (oturumlar, ayarlar, ekler)" sorusu (varsayılan HAYIR); evet ise
  `%LOCALAPPDATA%\EVREN-Model-Studio` silinir ve Credential Manager'daki
  `EVREN-Model-Studio` kayıtları da (EVREN/OpenAI/Anthropic anahtarları)
  kaldırılır. Hayır ise anahtar ve veri kalır (yeniden kurulumda geri gelir).
- Görev çubuğu kimliği: `EVREN.Studio` (app.py'de zaten var), simge `assets/evren.ico`.
- EXE dosya bilgileri: ürün adı, sürüm, şirket/geliştirici adı, telif (PyInstaller `--version-file`).

### 1.4 Uygulama tarafında gereken değişiklikler

- [ ] Sürümü tek kaynağa indir (`__version__`; pyproject dinamik sürüm).
- [ ] Paketlenmiş çalışma (`sys.frozen`) için kaynak yolları: `assets/evren.ico`
      ve varsa diğer dosyalar `sys._MEIPASS`/uygulama klasöründen okunmalı
      (2026-10-19 itibarıyla kod dosya kaynağına bağımlı değil; simgeler kodla çiziliyor).
- [ ] `sys.executable` kullanımını tara: paketli uygulamada bu EXE'nin kendisidir;
      Python sanıp alt süreç başlatan kod OLMAMALI (2026-10-19 taramasında `src/`
      içinde yok; testler/araçlar etkilenmez).
- [ ] Tek örnek (single instance) + `AppMutex` adı.
- [ ] Geliştiriciye özel dosyalar pakete girmez: `tools/ai_memory.py`, `tests/`,
      `docs/ai-memory/`, motor talimat dosyaları.
- [ ] Hakkında/Ayarlar: sürüm ve "Güncellemeleri denetle" (GitHub Releases
      API'den son sürümü okuyup bildirir; otomatik indirip kurmaz — ilk aşamada).
- [ ] Çökme günlüğü yeri değişmez (`%LOCALAPPDATA%\EVREN-Model-Studio\logs`).

### 1.5 Yapım hattı (build)

- `tools/paketle.py`:
  1. Temiz sanal ortamda bağımlılıkları sabit sürümle kur (`requirements.lock`).
  2. PyInstaller spec (`installer/evren_studio.spec`): onedir, `--windowed`,
     simge, sürüm dosyası, kullanılmayan Qt modüllerini dışla (QtWebEngine,
     QtMultimedia, Qt3D, QtQuick/QML, QtPdf…), gereksiz Qt çevirileri dışla.
  3. Duman testi: paketli EXE'yi `--duman-testi` ile başlat, pencereyi açıp kapat.
  4. `ISCC installer/evren_studio.iss` → `dist/EVREN-Studio-Setup-<sürüm>.exe`.
  5. SHA256 üret.
- GitHub Actions (`.github/workflows/release.yml`): `v*` etiketiyle tetiklenir,
  `windows-latest`'te yukarıdakini yapar, Release'e ekler. Push ve etiket
  kullanıcı onayıyla atılır.
- Boyut hedefi: paketin kendisi birkaç yüz MB'ı geçmemeli; setup sıkıştırılmış
  hâlde yaklaşık 100 MB civarı beklenir (TAHMİN — ilk yapımda ölç ve buraya yaz).

### 1.6 İmzalama ve Windows uyarıları

- İmzasız setup'ta Windows SmartScreen "Windows bilgisayarınızı korudu" der
  (Ek bilgi → Yine de çalıştır). Defender yanlış alarm verebilir.
- Seçenekler (ÜCRETLİ — kullanıcı karar verir): kod imzalama sertifikası (OV/EV,
  yıllık ücret) veya Azure Trusted Signing (aylık ücret, kimlik doğrulama gerekir).
  İmzalama yapılırsa hem EXE'ler hem setup imzalanır (Inno `SignTool`).
- Karar verilene kadar: imzasız yayınla; README/INSTALLATION'da SmartScreen
  adımlarını ve SHA256 doğrulamasını anlat; yanlış alarm olursa Microsoft'a
  "false positive" bildirimi yap.

### 1.7 Doğrulama listesi (bitti saymak için)

Temiz bir Windows'ta (Python, Git, Node KURULU OLMAYAN) — en kolayı **Windows
Sandbox** (Windows 10/11 Pro'da yerleşik) veya sanal makine:
- [ ] Setup açılır, Türkçe, kullanıcı kapsamında yönetici istemeden kurar.
- [ ] Geliştirme araçları sayfası: işaretlenenler kurulur, kurulu olanlar atlanır.
- [ ] Başlat menüsü + masaüstü kısayolu, simge doğru; uygulama açılır.
- [ ] EVREN anahtarı kaydedilir/okunur (Credential Manager), gerçek istek çalışır.
- [ ] Görsel yapıştırma, kullanım düğmesi, ajan bir Python projesinde test çalıştırır.
- [ ] Kullanıcı adında boşluk ve Türkçe harf (ör. `C:\Users\Osman Alpaslan`).
- [ ] Eski sürümün üzerine yükseltme: veri ve anahtar korunur.
- [ ] Kaldırma: "verileri sil = hayır" veri kalır; "evet" veri + anahtarlar silinir.
- [ ] Tüm kullanıcılar kurulumu (UAC) da çalışır.
- [ ] Defender taraması temiz; SmartScreen davranışı belgelenir.
- [ ] Ekran görüntüleriyle kurulum adımları (R-05), sonuç bu dosyaya ve
      CHANGELOG'a yazılır; doğrulanmayan madde "doğrulanmadı" diye kalır.

### 1.8 Kaynaktan kurulum yolu kalır

`kurulum.bat` + `run.bat` (2026-10-19) geliştiriciler ve Python'lu kullanıcılar
için korunur; README'de "Kurulum dosyası (önerilen)" ve "Kaynaktan çalıştırma"
iki yol olarak anlatılır.

### 1.9 Comodo'lu bilgisayar (yalnız kullanıcının bir geliştirme bilgisayarı)

- İmzasız, tanınmayan EXE büyük olasılıkla Comodo'nun otomatik kapsamasına
  (sandbox) girer: anahtar Credential Manager'a yazılamayabilir, veriler sanal
  klasöre gidebilir. Bu bilgisayarda: kurulum klasörünü Comodo "Güvenilir
  dosyalar"a ekle, sonra 1.7 listesinin anahtar/veri maddelerini tekrar dene.
- Bu bilgisayarda şu an `python.exe` (imzalı) ile kaynaktan çalışmak sorunsuz.
- Dosya yazımından hemen sonra geçici kilit görülebilir (kayıt:
  2026-10-16-dosya-yazimindan-hemen-sonra-gecici-errno-22-kilidi).

### 1.10 Açık sorular (başlarken kullanıcıya sorulacak)

- Kod imzalama alınacak mı? (ücretli)
- Geliştirici/şirket adı EXE ve kurulumda ne yazsın?
- İngilizce arayüz seçeneği kurulumda olsun mu?
- Uygulama içi otomatik güncelleme (indirip kurma) istenir mi, yoksa yalnız bildirim mi?

---

## 3. Auto Pro (eski adı EVREN Akıllı) yönlendirici ve Proje ajanı — YAPILDI (2026-10-19, dal `feat/akilli-yonlendirme`)

**Ek karar (2026-10-19, aynı gün):** "EVREN Akıllı" adı **Auto Pro** oldu. Yalnız
anahtarı girilmiş sağlayıcıların modelleri listelenir ve yönlendirilir (yalnız
OpenAI/Anthropic anahtarında EVREN motorları ve `auto` görünmez); çok sağlayıcıda
"dengeli" politika; uygulamanın kendi yapay zekâ işleri (özet, inceleme, oturum
başlığı, hata açıklaması, commit mesajı) bağlı API üzerinden Auto Pro ile çalışır.
Ücretli tablo doğrulanmadı (anahtar yok).

**Kullanıcı kararları (2026-10-19):** Ana odak EVREN API ve motorları. Sunucu
tarafı `auto` öngörülemez (her istekte sunucu seçer, akışta hangi model olduğu
görünmez, uzun görevde adımlar farklı modellere gidebilir). Kararlar:
- **EVREN Akıllı** eklenecek: uygulama içi, ölçüme dayalı yönlendirici. İşe göre
  model seçer (görsel → görsel model, kod/araç → en tutarlı, plan/muhakeme →
  güçlü düşünen, çok büyük bağlam → 1M, özet → hızlı); görev ortasında modeli
  DEĞİŞTİRMEZ (yalnız hata/aşırı yük/döngüde yedeğe geçer ve söyler); hangi
  modelin çalıştığı her zaman görünür. `auto` listede kalır.
- **Proje ajanı** eklenecek: büyük istek → güçlü modelle plan (`EVREN_PLAN.md`,
  her görevin "bitti" ölçütü) → **kullanıcı planı onaylar** → her görev temiz
  bağlamla ayrı turda → test/kabul + ikinci model kontrolü → git dalında kontrol
  noktası commit'i → takılırsa N kez başka modelle dene, olmazsa işaretle ve
  bağımsız sonrakine geç → rapor.
- Gözetimsiz çalışma: engelleyici onay penceresi yok (önceden seçilen kurallar),
  5 dk kota penceresi/günlük kota yönetimi, EVREN kesintisinde bekle-dene, uyku
  engelleme, uygulama kapanırsa kaldığı yerden devam.
- Bildirim: **Windows bildirimi + rapor dosyası** (telefon bildirimi şimdilik yok).

**Aşamalar:** (1) tüm EVREN modellerini zorluk paketi + planlama görevleriyle
ölç → yetenek tablosu; (2) EVREN Akıllı; (3) Proje ajanı; (4) gözetimsiz çalışma;
her aşama sonunda zorluk paketiyle ölç (R-21).

**Durum (2026-10-19):** dört aşama uygulandı ve ölçüldü — sonuçlar
docs/knowledge/CHALLENGE_RESULTS.md ("8 EVREN motoru", "Proje ajanı uçtan uca").
Kalanlar / sonraki iyileştirmeler:
- Varsayılan motoru `auto` yerine Auto Pro yapmak kullanıcıya soruldu
  (ayarlar korunur; yalnız onayla değişir).
- Uygulama kapanırsa proje kendiliğinden yeniden başlamaz: açılışta "yarım kalan
  proje" notu çıkar, `/proje-devam` ile sürer (otomatik sürdürme isteğe bağlı eklenebilir).
- Günlük kota bitince proje duraklar; sıfırlanınca otomatik sürdürme yok (zamanlayıcı eklenebilir).
- Proje görevleri yalnız EVREN modelleriyle denendi; ücretli sağlayıcıda bütçe
  onayı penceresi gözetimsiz çalışmayı durdurabilir (ölçülmedi).

## 4. MCP (Model Context Protocol) entegrasyonu — İLK AŞAMA YAPILDI (2026-10-19, dal `feat/mcp`)

**Durum:** Kullanıcı önerilen yolu onayladı ("önerdiğin gibi işlemlere başla ve test et").
Genel MCP desteği (agent/mcp.py, kendi stdio istemcimiz) + Serena 1.7.0 tek tıkla kurulum
yapıldı ve gerçek API ile ölçüldü (CHALLENGE_RESULTS.md "MCP / Serena"). Sıradaki:
Playwright MCP (Node gerekir; isteğe bağlı), Serena'yı başka dillerde denemek, repo
tarafını (kod dahil etme) lisans/bakım açısından konuşmak. Not: Serena 2.0.0 GPL-3.0'a geçti.

**Sonraki aşama — kullanıcı kararları (2026-10-19) — YAPILDI (dal `feat/mcp-akilli`; ölçüm CHALLENGE_RESULTS.md "MCP aşama 2"). Kalan: Go/Rust için araç kurulumu önerisi, uzun süren geliştirme sunucularını (npm run dev) ajanın arka planda başlatabilmesi:**
- MCP yalnız gerektiğinde açılsın (ilk araç çağrısında başlat, boşta kapat; araçlar yalnız
  ilgili projede/görevde sunulsun), gerekmediğinde kapalı kalsın.
- Ücretli sağlayıcılarla MCP KESİNLİKLE çalışmayacak (uygulamanın amacı ücretsiz hizmet);
  MCP araçları yalnız EVREN modellerine, Auto Pro MCP işini EVREN'e yönlendirir.
- Serena Python dışındaki dillerde de çalışacak (gerçek küçük projelerle denenecek).
- Playwright MCP eklenecek (web projelerini tarayıcıda test).
- Node.js (Playwright ve TypeScript dil sunucusu için) **winget ile sistem geneline** kurulacak
  (kullanıcı tercihi; taşınabilir Node yerine).
- Önerilen ek: düzenlemeden sonra Serena hata denetimi (diagnostics) kendiliğinden çalışıp
  hataları modele geri versin ("hata bekçisi").


**Kullanıcı isteği:** Serena gibi kod, test ve görsel alanında güçlü MCP sunucularını
uygulamaya bağlamak; uygulamayı geliştirecek repolar varsa koda dahil etmek. Önce MCP
kapsamı araştırılıp bilgi verilecek, sonra repo tarafına bakılacak. Henüz kod yazılmadı.

**Bulgular (web araştırması, 2026-10-19; doğrulanmadı = denenmedi):**
- MCP, modele dış araç/kaynak bağlayan açık protokol. EVREN Studio bir **MCP istemcisi**
  olur: sunucuyu (çoğunlukla stdio ile alt süreç) başlatır, araç listesini alır, araçları
  modele function calling olarak sunar, çağrıyı sunucuya iletir. Resmî Python SDK `mcp`
  (MIT); 2.x kararlı hattı spesifikasyon 2026-07-28'i destekliyor (1.x ile API farkı var,
  sürüm sabitlenmeli).
- Aday sunucular: **Serena** (oraios/serena, MIT; dil sunucusu tabanlı sembol düzeyinde
  bul/başvuru/düzenle; uv ile kurulur, Python 3.11+); **Playwright MCP** (Microsoft;
  tarayıcı sürme, ekran görüntüsü, web testi; Node gerekir, `--isolated` önerilir);
  **Chrome DevTools MCP** (Google; konsol, ağ, performans hata ayıklama); **Context7**
  (güncel kütüphane belgeleri); **GitHub MCP** (resmî; PR/issue).
- Sınırlar: Qt masaüstü uygulamasını süren hazır bir MCP yok (bu oturumda da QTest +
  ekran görüntüsü aracı kullanılıyor); ekran görüntüsü yoğun sunucular bağlamı hızla
  doldurur (30 adımlık tarayıcı akışı ~20k token); her MCP aracı ajan izin sistemine
  (Onaylı/Otomatik) ve kapsam denetimine bağlanmalı; harici sunucu = harici kod
  (yalnız kullanıcının eklediği, sürümü sabit sunucular).

**Önerilen yol (karar kullanıcıda):** (1) agent/mcp_client.py (Qt'siz, `mcp` SDK, stdio),
Ayarlar'da sunucu listesi (`mcp_servers`), araçlar `mcp__sunucu__arac` adıyla,
varsayılan "sor"; (2) ilk sunucu Serena (Python, kod odaklı, EVREN'in kod ajanını
doğrudan güçlendirir); (3) Playwright MCP isteğe bağlı (Node); (4) her aşamada zorluk
paketi + gerçek API ölçümü (R-21). Repo tarafı (kod dahil etme) lisans ve bakım yükü
incelendikten sonra ayrı konuşulacak.

## 5. QA ajanı (web) — YAPILDI (2026-10-19, dal `feat/qa`)

Kullanıcı kararları: masaüstü uygulama testi yok, web kısmı gerçek QA gibi; yalnız EVREN; kota bekçisi yok.
Yapılanlar: arka plan servisleri, test bekçisi, `/qa` (plan → onay → gözetimsiz senaryolar → rapor →
"Hataları düzelt"), görsel göz, erişilebilirlik/performans/güvenlik denetimi. Ölçüm: CHALLENGE_RESULTS.md
"QA ajanı". Kalan fikirler: Playwright iz kaydı (trace) ile adımları izleme, API ucu testi için ayrı araç,
mobil görünüm (browser_resize) senaryoları.

## 6. Derin Mod, plan bekçisi, uzun işler, kota kapısı — YAPILDI (2026-10-21, dal `feat/derin-mod`)

Kullanıcı istekleri: faz bitince sonrakine geçmeyi unutma sorunu; Claude Code ultracode benzeri mod;
90 dakikayı aşan testler; kenar çubuğu. Yapılanlar CHANGELOG'da; ölçüm CHALLENGE_RESULTS.md.
Açık kalanlar / ileride:
- [ ] Derin Mod alt ajanlarına MCP (Serena) — eşzamanlı alt ajanlarda paylaşılan süreç güvenli mi ölçülmeli.
- [ ] Denetçi bulgularını anlamca birleştirme (şu an yalnız dosya + metin başı).
- [ ] Plan bekçisinin kullanıcı yazdığı ve ajanın hiç güncellemediği plan dosyasını görmesi (yanlış
      tetiklenme riskiyle birlikte ölçülmeli, R-22).
- [ ] Uygulama kapalıyken otomatik sürdürme (Windows Görev Zamanlayıcı) — gerekirse.
- EVREN'den sorulacak (şartlarda yok): eşzamanlı istek sınırı; kota anahtar mı hesap mı başına.

## 2. Diğer bekleyen işler (özet; ayrıntı PROJECT_STATE.md)

- OpenAI/Anthropic'i gerçek anahtarla doğrula (`tests/e2e_providers_real_api.py --evet`).
- Git entegrasyonu (durum/diff görünümü, commit önerisi).
- Sohbet alanının tamamına dosya bırakma (şu an yazma kutusu kabul ediyor).
- Akışlı yanıtta auto'nun yönlendirdiği modeli kaydetme (EVREN akışta vermiyor).
