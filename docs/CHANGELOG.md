# Değişiklik Günlüğü

## Yayınlanmamış — Auto Pro akıllı seçim (F2)

### Eklendi
- **İşin zorluğuna göre motor:** Kısa, tek dosyalık işler (yazım düzeltme, tek değer değiştirme) hızlı motora
  gider; test, çok dosya, hata ayıklama veya program çalıştırma içeren işler güçlü motora. Hızlı motorla tur
  başarısız olursa ya da "olmadı" derseniz sonraki tur güçlü motorla yapılır.
- **İş türü rolleri:** veri/rapor (Excel, CSV), web, oyun ve Türkçe metin işleri için ayrı motor sırası; her biri
  gerçek ölçüm paketiyle belirlendi. Veri işlerinde model sayıları elle değil betikle hesaplamaya yönlendirilir.
- **Kötü yanıt düğmesi (👎):** Yanıtın üstünde; aynı motor 24 saatte iki kez işaretlenirse Auto Pro onu sıralamada
  geri alır. Döngü, testi bozma ve plan takılması da motorun kalite puanına işlenir (Modeller > son 24 saat
  tablosunda "Kalite" sütunu). Puan yalnız sıralamayı değiştirir, motoru kapatmaz.
- **Motor yoklaması:** Açılışta ve Derin/Proje başlarken motorlara birkaç tokenlık istek; bozuk motor işe
  başlamadan sona alınır (en çok 30 dakikada bir).
- **Normal turda kota koruması:** 5 dakikalık EVREN penceresi dolarken tur, pencere yenilenene kadar bekler (token
  harcamaz); günlük kota azalınca uyarır ama durdurmaz.
- **Planlayan + yazan (deneysel, varsayılan kapalı):** Zor işte önce bir motor planlar, başka bir motor yazar.
  Ölçümde kazanç göstermediği için kapalı; Ayarlar'dan açılabilir.
- Ayarlar'da dört yeni kutu (akıllı seçim, yoklama, planlayan + yazan, kota koruması).

### Düzeltildi
- Ajan çıktı dosyalarını (JSON/CSV) PowerShell yönlendirmesiyle BOM'lu yazabiliyordu; artık write_file veya
  Python kullanması söyleniyor.

## Yayınlanmamış — Auto Pro çekirdeği (F1)

### Eklendi
- **Gerçek kullanım kaydı:** Her model çağrısının süresi, ilk yanıt süresi, hızı ve hatası kaydedilir; motorun
  "o günkü normal hızı" buradan hesaplanır.
- **Yavaşlama kuralı (onaylı karar #88):** Motor bugünkü normal hızının yarısının altında art arda 2 adım kalırsa
  Auto Pro iki adım arasında yedek motora geçer; görev başına en çok bir kez ve gerekçesiyle bildirir.
  Proje/Derin görevlerinde görev içi eşik ~3 kat yavaşlık. Bugün için yeterli ölçüm yoksa kural devreye girmez.
- **Bekleme süresi:** Hata veren veya yavaşlayan motor 30 dakika sıranın sonuna alınır (eskiden bir sonraki
  turda yine ilk seçiliyordu).
- **Yanıt vermeme süresi (Ayarlar, varsayılan 60 sn):** Model bu sürede yanıt vermeye başlamazsa veya akış
  susarsa yedek motora geçilir.
- **Model listesi uyarısı:** EVREN'in model listesi değişince (ör. bir motor kalkınca) not düşülür.
- **Şeffaflık:** Çalışma çubuğunun ipucunda "neden bu motor" ve bugünkü ölçümü; Modeller sayfasında
  "Auto Pro — son 24 saat" tablosu (çağrı, hata, hız, ilk yanıt, yedeğe geçiş, bekleme durumu).

### Düzeltildi
- Akış koptuğunda veya model sustuğunda tur yedek motor denenmeden hatayla bitiyordu; artık yedeğe geçilir.

## Yayınlanmamış — Auto Pro kod motoru sırası

### Değişti

- **Auto Pro kod işinde artık önce deepseek-v4.1-flash'ı kullanır** (sonra qwen3.8-flash-next, sonra gemma-4-31b).
  Bugünkü ölçümde üç motor da 12 zor görevin hepsini geçti; deepseek-v4.1-flash qwen'den hızlı (7,0 dk / 8,9 dk)
  ve çok daha az adımla çalıştı. Proje ajanı görevleri ve Derin Mod düzeltme turları da bu sırayı kullanır.

## Yayınlanmamış — Derin Mod ve Proje ajanı düzeltmeleri (hesap kapama oturumundan)

Kullanıcının gerçek Derin Mod oturumu (hesap kapama raporu, 1 sa 50 dk) incelendi: Excel raporu oluşmadı,
12 görevden 3'ü bitti, ama akış "bitti, sorun yok" dedi. Düzeltmeler:

### Düzeltildi

- **İç içe PowerShell komutu**: ajanın `powershell -Command "…$t…"` biçimindeki komutlarında `$` değişkenleri dış
  kabukta yutuluyordu (araç hatalarının ~1/3'ü). Bu biçim artık tek PowerShell'de, sarmalanmadan çalışır.
- **Bozuk doğrulama komutu görevi düşürmez**: komutun kendisi yazım hatası verirse karar inceleme modeline kalır
  (eskiden iş doğru olduğu hâlde görev 3 kez denenip "takıldı" sayılıyordu).
- **Proje kısmen biterse "tamamlandı" denmez**: proje duraklar ("Proje kısmen bitti (3/12) …"); `/proje-devam`
  takılan görevi yeniden dener, ona bağlı atlanan görevler yeniden sıraya girer.
- **Derin Mod kısmi projede "bitti" demez**: proje tamamlanana kadar bekler; denetçiler önce istenen nihai çıktının
  (ör. Excel dosyası) gerçekten var olduğunu kontrol eder; iki denetçi farklı modeldir.
- **.ps1 dosyaları UTF-8 BOM ile yazılır**: Windows PowerShell 5.1 BOM'suz betikteki Türkçe harfleri bozuyordu.
- **Auto Pro**: `deepseek-v4-flash` EVREN model listesinden kalktı; kod/sohbet yedeğine `deepseek-v4.1-flash` eklendi.

### Eklendi

- **Derin Mod soru kartı**: inceleme, cevabı projede olmayan kararları (eksik veri dosyası, iki geçerli seçenek,
  çıktı adı) bulursa planlamadan ÖNCE size sorar. Yanıtı kartta veya mesaj kutusunda verirsiniz; "Sormadan devam"
  derseniz varsayımlar raporda yazılır. Yanıtlar plana ve her göreve iletilir.
- **Proje ajanı soru sorabilir**: görev, kararınız olmadan doğru yapılamıyorsa `SORU:` ile durur; proje duraklar,
  yanıtı `/proje-devam <yanıt>` ile verirsiniz.
- **Görev bağlamı**: Derin Mod'un inceleme notu ve yanıtlarınız her Proje görevine verilir (her görev aynı dosyaları
  baştan keşfetmez).
- **Görünürlük**: Derin Mod'un her alt ajanı bitince not düşer (araç sayısı, süre, model); dökümleri veri klasöründe
  `deep/<zaman>/` altına yazılır. Sonuç bloğu vermeyen alt ajana araçsız "yalnız sonucu yaz" turu açılır.

## Yayınlanmamış — Derin Mod, plan bekçisi, uzun işler, kota kapısı, kenar çubuğu

### Eklendi

- **Derin Mod** (composer'daki **Derin** düğmesi veya `/derin <istek>`; `/derin-durdur`): Claude Code'un
  ultracode moduna benzer çok ajanlı çalışma. Düğme açıkken her iş şu akışla yürür; fazları KOD sürer:
  1. **Anla**: 2-3 bağımsız, salt okunur alt ajan projeyi farklı açılardan inceler (yapı, ilgili kod,
     test yolu), aynı anda.
  2. **Planla**: iki farklı EVREN modeli bağımsız plan yazar; yargıç model birini seçer (kapsam dışı iş
     ekleyen planı eler).
  3. **Uygula**: seçilen plan onay kartıyla size sunulur; onaylarsanız Proje ajanı görev görev yürütür.
  4. **Çekişmeli doğrula**: iki bağımsız denetçi değişikliği isteğe karşı çürütmeye çalışır.
  5. **Düzelt**: onaylanan sorunlar düzeltilir (en çok 2 tur), sonra yeniden doğrulanır.
  Soru türü isteklerde yalnız Anla + yanıt yapılır, dosya değişmez. Rapor: `EVREN_DERIN.md`.
  Yalnız ücretsiz EVREN; daha yavaş ve daha çok token harcar.
- **Plan bekçisi**: ajan bir plan dosyası veya görev listesi tutarken açık madde varken turu bitirmez;
  "sıradakine geçeyim mi?" demeden devam etmesi için en çok 8 kez dürtülür, gerçek iş ilerlemiyorsa
  durur. Gerçek engelde ajan `ENGEL: <neden>` yazar. Adım sınırında açık madde kalırsa tur en çok 2 kez
  kendiliğinden sürer. Ayarlar'dan kapatılabilir.
- **Proje ajanı önerisi**: çok aşamalı uzun bir istem yazınca "Proje ajanıyla yürüt / Normal devam"
  kartı çıkar (sessizce yönlendirmez). Ayarlar'dan kapatılabilir.
- **Uzun işler** (`start_job`, `wait_job`, `job_status`, `stop_job`): 90 dakikalık test takımı gibi uzun
  komutlar arka planda çalışır, tur bitince kapanmaz. Ajan beklerken modele istek gitmez (token
  harcanmaz); iş bitince not ve Windows bildirimi gelir. Tam çıktı veri klasöründe günlük dosyasındadır.
- **Kota kapısı**: Derin Mod'un paralel alt ajanları EVREN'in 5 dakikalık hız penceresi dolarken tek tek
  çalışır, pencere çok doluysa yenilenmesini bekler (token harcamaz); günlük kota azalınca durur.
- **Kota sonrası otomatik sürdürme**: kota yüzünden duraklayan Proje/QA/Derin çalışması kota yenilenince
  kendiliğinden sürer (uygulama açık kalmalı; durdur komutuyla iptal). Ayarlar'dan kapatılabilir.
- Kenar çubuğu ve sağ panel genişliği hatırlanır.

### Düzeltildi

- **Sol kenar çubuğu sürüklenince kayboluyordu** (2026-10-19'da "düzeldi" denmişti, düzelmemişti):
  orta alanın en küçük genişliği en büyük sayfanın uzun etiketlerine göre 1700+ px'e çıkıyor, çubuk
  ekranın dışına itiliyordu. Gerçek fare sürüklemesiyle 9 test eklendi.
- Ayarlar sayfası dar pencerede yatay kayıyordu (uzun açılır liste).
- Arka plan servisi hemen kapanırsa son çıktı mesajdan eksik kalabiliyordu.

## Yayınlanmamış — QA ajanı, arka plan servisleri, test bekçisi

### Eklendi

- **QA ajanı** (`/qa <neyi test etsin>`, `/qa-duzelt`, `/qa-devam`, `/qa-durdur`): web uygulamasını
  gerçek bir test uzmanı gibi tarayıcıda dener.
  - Önce senaryo planı çıkarır (uç durumlar dahil: boş giriş, uzun metin, Türkçe karakter, art arda
    tıklama); planı siz onaylarsınız.
  - Her senaryoyu temiz bağlamla, gözetimsiz ve DOSYA DEĞİŞTİRMEDEN dener.
  - Sonuç: geçti / kaldı / engellendi, kanıtla birlikte. Rapor `EVREN_QA_RAPORU.md`'ye yazılır,
    bitince Windows bildirimi gelir.
  - "Hataları düzelt" düğmesi kalan hataları Proje ajanına verir.
  - Yalnız EVREN modelleriyle ve Playwright MCP ile çalışır.
- **Arka plan servisleri** (`start_service`, `service_logs`, `stop_service`): ajan `npm run dev`,
  `python server.py` gibi sürekli çalışan sunucuları başlatıp porta hazır olmasını bekler ve
  çıktısını okur. Normal tur bitince servisler kapanır; QA çalışmasında senaryolar arasında açık kalır.
- **Test bekçisi**: dosya değiştiren turun sonunda projenin kendi testleri çalışır (pytest/unittest,
  npm test, dotnet test, go test). Tur başında geçen testler bozulduysa model bir kez uyarılır;
  önceden düşen testler için uyarı verilmez. Ayarlar'dan kapatılabilir.
- **Görsel göz** (`visual_check`, QA turlarında): ekran görüntüsünü EVREN'in görsel modeline
  (gemma-4-31b) sorar; görüntü proje klasörüne değil uygulama klasörüne kaydedilir.
- **Ek denetimler** (`qa_audit`):
  - Erişilebilirlik: axe-core 4.13.0, açık sayfada.
  - Performans: yükleme süresi ve en büyük dosyalar.
  - Güvenlik: projede unutulmuş anahtar/parola taraması; `package-lock.json` varsa `npm audit`.

## Yayınlanmamış — MCP gerektiğinde, Playwright, hata bekçisi, çok dilli Serena

### Eklendi

- **MCP gerektiğinde açılır, gerekmediğinde kapalı kalır**: araç listesi önbellekten sunulur,
  sunucu ilk araç çağrısında başlar ve boşta kalınca kapanır (Serena 10 dk, Playwright 5 dk).
  Serena yalnız yeterince büyük kod projesinde (≥5 kod dosyası veya ≥800 satır) ya da sembol
  işinde (yeniden adlandır, nerede kullanılıyor…), Playwright yalnız tarayıcı/arayüz testi
  istendiğinde sunulur.
- **Ücretli sağlayıcıda MCP yok**: MCP araçları yalnız EVREN modellerine verilir.
- **Hata bekçisi**: ajan bir dosyayı düzenleyince kesin hatalar aynı turda modele bildirilir.
  Yerleşik denetimler: Python sözdizimi, JSON, TOML, Node varsa JavaScript. Serena açıksa dil
  sunucusu hataları da eklenir: tanımsız ad, eksik argüman. Eksik paket/import uyarıları yanlış
  alarm olabileceği için atılır. Ayarlar'dan kapatılabilir.
- **Playwright MCP 0.0.83** (Apache-2.0): ajan web sayfasını gerçek tarayıcıda (kurulu Microsoft
  Edge) açar, okur, tıklar, konsol hatalarını görür. Proje dosyaları yalnız bu bilgisayardan
  erişilebilen yerel bir adresten (127.0.0.1) verilir; `.env`, anahtar dosyaları ve `.git` verilmez.
  Adrese gitme, tıklama ve JavaScript çalıştırma çalışma moduna göre onay ister.
- **Serena çok dilli**: Python, TypeScript, JavaScript, C# ve Java gerçek dil sunucusuyla denendi.
  Dil sunucuları tüm projeler için tek ve kısa yollu bir klasörde tutulur.
- Ayarlar > MCP: Playwright satırı ve Node.js yoksa "Node.js'i kur (winget)" düğmesi.

### Düzeltildi

- Auto Pro yedek listesi farklı sağlayıcının modelini içerebiliyordu; tur boyunca istemci aynı
  kaldığı için istek yanlış sağlayıcıya gidiyordu. Yedekler artık turun sağlayıcısıyla sınırlı.
- Serena'nın C# dil sunucusu Windows'un 260 karakterlik yol sınırına takılıp başlamıyordu.

## Yayınlanmamış — MCP sunucuları ve Serena

### Eklendi

- **MCP desteği** (`agent/mcp.py`): EVREN Studio artık bir MCP istemcisi. Ayarlar >
  MCP Sunucuları'ndan eklenen stdio sunucularının araçları ajana `mcp__<sunucu>__<araç>`
  adıyla sunulur. Yalnız proje klasörlü oturumlarda; Plan modunda yalnız okuma araçları.
  Okuma listesinde olmayan araç çalışma moduna göre onay ister (sunucunun readOnlyHint
  iddiasına güvenilmez). Başlatılamayan sunucu turu düşürmez, not olarak bildirilir.
- **Serena 1.7.0** (MIT) tek tıkla kurulum: veri klasöründe ayrı Python ortamı, uv ve
  pyright (Python 3.13 ile) dahil, sisteme program kurulmaz (~2 dk). Yalnız okuma yapan
  3 sembol aracı açık: get_symbols_overview, find_symbol, find_referencing_symbols.
  Serena'nın verisi (önbellek, proje ayarı, günlük) proje başına uygulamanın veri klasöründe
  tutulur; proje klasörüne ve `%USERPROFILE%\.serena`'ya yazılmaz.
- Ayarlar'da "Dene": sunucuyu başlatır, açılış süresini ve ajana açık araçları gösterir.
- `tests/e2e_mcp_real_api.py` (Serena açık/kapalı karşılaştırması, gerçek API) ve
  zorluk paketine `--serena` seçeneği.

### Düzeltildi

- Koyu temada işaretli onay kutusu içi boş beyaz kare görünüyordu (vurgu beyaz olunca);
  artık koyu tik işareti var.

## Yayınlanmamış — Klavye, bağlam göstergesi, koyu tema

### Düzeltildi

- **Alt+Enter** artık yeni satır ekler (önceden mesajı gönderiyordu). Shift/Alt/Ctrl+Enter
  yeni satır, Enter gönderir; "Enter ile gönder" kapalıysa Ctrl+Enter gönderir.
- **Bağlam göstergesi**: Auto Pro'ya sabit 1M pencere yazılıydı; özet 100k'de başladığı
  için gösterge "%10"da özetliyor gibi görünüyordu. Auto Pro'nun penceresi artık sıradaki
  turda seçilecek model ve yedeklerinden gelir; yüzde, özetin devreye gireceği eşiğe göre
  gösterilir ("bağlam ~42k / 100k (42%)"); ipucu model penceresini ve eşiğin nedenini
  (EVREN kotası: 5 dk'da 2,5M, günde 15M token) açıklar. 100k üst sınır korundu.
- **Koyu tema okunurluğu**: tüm ikincil yazı, düğme ve simgeler "Görevler" başlığıyla aynı
  parlaklıkta (#e8e9ec). Yalnız yer tutucu ve devre dışı öğeler okunur ama daha soluk
  (#9ca1ab, ≥4,5:1). Koyu temada mavi vurgu kaldırıldı: birincil düğmeler (Kaydet, Gönder)
  beyaz zemin + koyu yazı, seçili satır nötr gri, bağlantılar beyaz ve altı çizili.

## Yayınlanmamış — Auto Pro yönlendirici ve Proje ajanı

### Eklendi

- **Auto Pro** (eski adı "EVREN Akıllı"; kayıtlı eski seçim kendiliğinden
  taşınır): yalnız **API anahtarı girilmiş** sağlayıcıların modellerini kullanır.
  Yalnız EVREN → ölçülmüş EVREN tablosu; yalnız OpenAI/Anthropic → onların
  tablosu (EVREN motorları ve `auto` listede görünmez); birden fazla → "dengeli":
  çok token harcayan işler (kod, sohbet, özet, başlık, commit, hata) önce ücretsiz
  EVREN'de, plan/inceleme/görsel önce güçlü ücretli modelde; aylık bütçe aşılınca
  ücretli model atlanır.
- Model listesi ve kenar çubuğu anahtara göre: anahtarı olmayan sağlayıcının
  modelleri listelenmez; EVREN anahtarı yoksa EVREN'e özgü sayfalar (Modeller,
  Kullanım ve Kota, Durum İzleme, Bağlantı Testi) gizlenir; kullanım düğmesi
  ücretli harcamayı ($) gösterir.
- Uygulamanın kendi yapay zekâ işleri bağlı API üzerinden Auto Pro ile çalışır
  (`AppContext.ai_chat`): bağlam özeti, proje incelemesi ve yeni olarak
  **oturum başlığı üretme** (ilk yanıttan sonra; Ayarlar'dan kapatılabilir),
  **hata kartında "Yapay zekâ ile açıkla"**, **proje ajanında commit mesajı
  önerisi**. Hata/boş yanıtta sıradaki modele geçer; ücretli maliyet bütçeye yazılır.
- Canlı EVREN model listesi (yetenek bayrakları) açılışta arka planda yüklenir.

- **Auto Pro** (model seçicide en üstte): uygulama içi, ölçüme dayalı
  yönlendirici. İşe göre motor seçer (sohbet / kod / plan / görsel / büyük bağlam
  / inceleme), görev ortasında motoru değiştirmez; yalnız EVREN hata verirse,
  model döngüye girerse veya görseli reddederse yedeğe geçer ve söyler. Çalışma
  çubuğunda "Auto Pro → model (rol)". Zorluk paketinde 12/12. auto listede kalır.
- **Proje ajanı**: `/proje <hedef>` → plan (EVREN_PLAN.md, her görevde bitti
  ölçütü/doğrulama) → **onay kartı** → görevler Otomatik modda, temiz bağlamla,
  gözetimsiz sırayla yürür; her görev doğrulama komutu + ikinci model incelemesiyle
  denetlenir; git deposunda ayrı dalda görev başına commit; takılan görev 3
  denemeden sonra stash'e alınıp atlanır (bağımlıları da); kota penceresi /
  EVREN kesintisinde bekler, günlük kota bitince duraklar; uyku engellenir;
  bitince Windows bildirimi + EVREN_RAPOR.md. `/proje-duzelt`, `/proje-devam`,
  `/proje-durdur`; Esc projeyi duraklatır; açılışta yarım kalan proje bildirilir.
- Zorluk paketine `planlama` ve `mini_proje` görevleri; `tests/e2e_proje_real_api.py`.

### Düzeltildi

- EVREN düşünen modelleri kısa yapay zekâ isteklerinde (başlık, commit, hata
  açıklaması) boş yanıt veriyordu (düşünme bütçeyi bitiriyordu): bu isteklerde
  `reasoning_effort: none` gönderilir, boş yanıtta yedeğe geçilir.
- Hata kartı ve ücretli sağlayıcı düğmeleri tıklanınca çalışmıyordu
  (`clicked` sinyalinin `checked` değeri lambda'nın varsayılan argümanını ezdi).
- Uygulama açılmıyordu: uygulamanın kendi ajanının main_window'a eklediği hata
  ayıklama günlüğü (`time.strftime('%f')`, Windows'ta geçersiz) kaldırıldı.
- "Developed by Osman Alpaslan" yazısı kenar çubuğunda kesiliyordu: adın altına,
  kendi satırına alındı.
- Ctrl+K kenar çubuğunu açarken ayarı güncellemiyordu (yeniden açılışta kapanıyordu).
- Proje klasörü olarak uygulamanın kendi kaynak kodu seçilince uyarı gösterilir.
- "Adı geçen dosya projede yok" uyarısı, dosyanın oluşturulması istendiğinde
  verilmiyor (zayıf modelleri soru sormaya itiyordu).
- Ölçüm betiği: mutlak yol ve UTF-8 çıktı (yanlış "başarısız" puanları).

## Yayınlanmamış — Zorluk paketi ve tek tıkla kurulum

### Eklendi

- **Tek tıkla kurulum**: `kurulum.bat` — Python 3.12+ bulur (yoksa sorup winget
  ile kullanıcı kapsamında kurar; Microsoft Store'un sahte `python` kısayolunu
  eler), sanal ortam ve paketleri kurar, masaüstü + Başlat menüsü kısayolu
  ekler. `run.bat` kurulum yoksa onu çağırır. README/INSTALLATION: "ZIP indir →
  kurulum.bat".
- **Zorluk paketi** `tests/e2e_zorluk_real_api.py`: 10 kısa zor görev (Türkçe/
  BOM/CRLF, yeniden adlandırma, büyük dosyada sayım, çelişkili test, kapsam,
  JSON, hata ayıklama, olmayan dosya, Plan modu, girdi bekleyen komut), gerçek
  API, otomatik puanlama. Sonuçlar: docs/knowledge/CHALLENGE_RESULTS.md.

### Düzeltildi (paketin bulduğu)

- Kısaltılmış dosya çıktısından uydurma sayı: açık "⚠ KISALTILDI" uyarısı;
  `search_files` ilk satırda toplam eşleşme sayısını verir; sayımda gözle sayma kuralı.
- İstenen dosya yokken benzer dosyanın sormadan değiştirilmesi: istem kuralı +
  tur başı "adı geçen dosya projede yok" denetimi.
- Çelişkili testte test dosyasının değiştirilmesi: istenmeden var olan test
  dosyası düzenlenince ajana anında uyarı, kullanıcıya tur sonu notu.
- `.bat` dosyaları CRLF'e sabitlendi (`.gitattributes`).

## Yayınlanmamış — Ekler ve kullanım düğmesi

### Eklendi

- **Dosya ve görsel ekleme (Claude Code gibi)**: yazma kutusuna sürükle-bırak,
  Ctrl+V ile yapıştırma (Gezgin'den kopyalanan dosya veya ekran görüntüsü) ve
  ataç düğmesi. Ekler kutunun üstünde küçük resim / dosya kartı olarak görünür,
  ✕ ile kaldırılır; dosya yolu metne yazılmaz, arka planda tutulur. Gönderilen
  mesajda da ek şeridi görünür; mesaj düzenlenince ekler geri gelir.
- **Görsel girdi**: görseller görsel okuyabilen modellere gönderilir (gerçek API
  ile doğrulandı). Görsel okuyamayan motorda (glm-5.3, deepseek-v4-flash)
  gönderimden önce auto'ya geçmek önerilir.
- **Dosya ekleri**: metin dosyalarının içeriği modele eklenir (100 KB'a kadar);
  ikili dosyalarda yalnız ad ve yol.
- **Kullanım düğmesi**: model seçicinin yanında günlük kotadan kalan yüzde;
  tıklayınca halka grafik (günlük kota), çubuk (5 dakikalık hız penceresi),
  kredi, bu oturumun token kullanımı ve ücretli sağlayıcıda aylık tahmini
  harcama — her birinin altında kısa açıklama.

## Yayınlanmamış — Döngü önleme (ajan tekrara düşmesin)

### Eklendi

- **Kapsam koruması**: ajan yalnız isteneni yapar (kural); tur sonunda "Bu tur N
  dosyayı değiştirdi" kartı ve **Turu geri al**; kapsam denetimi istenmemiş
  değişiklikleri işaretler ve **Kapsam dışını geri al** sunar (onay istemez);
  Ayarlar'da isteğe bağlı **Önce plan** (varsayılan kapalı).
- **Ay-yıldız simgesi**: Türk bayrağı oranlarıyla, arka plansız; koyu temada
  beyaz, açık temada bayrak kırmızısı. Masaüstü/görev çubuğu için `assets/evren.ico`.
- **Canlı çalışma göstergesi**: model çalışırken dönen yıldız (mesajda ve durum çubuğunda).
- **Hız**: uzun geçmiş oturumlar ~5 kat hızlı açılır (son 40 mesaj, "Önceki
  mesajları göster"); ekran geçişleri hızlandı (tekerlek koruması alan başına).
- **Ortam denetimi ve program kurulumu**: klasör bağlanınca gereken programlar
  denetlenir; eksikler Ayarlar > "Eksik program kurulumu" seçimine göre Otomatik
  (sormadan) veya Manuel ("Kurulsun mu?" bildirimi) kurulur. Ajan `install_program`
  aracıyla da isteyebilir. Kurulum winget/npm ile, yalnız bilinen listeden.
- **Döngü bekçisi**: ajan aynı aracı aynı parametrelerle (arada dosya değişmeden)
  ikinci kez çağırırsa modele uyarı gider, üçüncüde tur durur ve size bildirilir.
  Bir dosya bu tur içinde eski bir hâline geri dönerse (ileri-geri düzenleme)
  aynı şekilde uyarı, tekrarında durma.
- **Boş yanıt / "inceleyeyim" deyip durma**: model bir kez otomatik hatırlatılır;
  boş yanıtta (düşünme bütçesi tükenmesi) destekleyen EVREN modelinde o deneme
  düşünmesiz yapılır. Yine boşsa ekranda not çıkar.
- **Metin tekrarı denetimi**: model araç çağırmadan aynı cümleleri tekrar tekrar
  yazarsa metin kısaltılır, model bir kez yönlendirilir; akışta istek erken kesilir.
- **Sunucu 400 (bozuk araç JSON'u)**: aynı adım yeniden denenir, yerel araç
  çağrısı bırakılmaz.
- **Proje maratonu** (tests/e2e_marathon_real_api.py): gerçek arayüzle 3 proje
  baştan sona; kabul testleri dışarıdan.
- **API anahtarı koruması**: commit'e anahtar giremez (tools/secret_scan.py,
  ön-commit kancası ve test). Depoda/geçmişte anahtar olmadığı doğrulandı.

### Değişti

- **Otomatik mod hiçbir işlem için onay istemez** (kullanıcı kararı): riskli
  komutlar, korumalı dosyalar ve gizli dosya okuma dahil. Durdurmak için Esc.
- Tur başına adım sınırı varsayılanı 40 → 80 (eski varsayılan kendiliğinden taşınır).
- Proje hafızası: kökte EVREN.md varsa ajana yalnız o verilir (uzun AGENTS.md
  ajanı asıl işten uzaklaştırıyordu). Bu depoya kısa EVREN.md eklendi.
- Ajan kuralları: tekrar etmeme, iki başarısızlıktan sonra yol değiştirme veya
  durma, test dosyalarını değiştirmeme/kandırmama, yapmadığını yaptım dememe.
- Ayrıntı ve ölçümler: docs/knowledge/LOOP_ANALYSIS.md.

## Yayınlanmamış — Varsayılan motor auto, seçimler hatırlanır

### Değişti

- **Varsayılan motor `auto`** (EVREN yönlendiricisi): yeni oturumlar auto ile
  açılır; model seçicide EVREN grubunun en üstünde "önerilen". Mevcut
  kurulumlarda eski varsayılan glm-5.3 bir kez auto'ya çevrilir (ayar sürümü 2);
  başka bir model seçilmişse dokunulmaz. Onay modu varsayılanı değişmedi (Manuel).
- **Son seçim hatırlanır**: sohbet ekranında seçilen motor ve onay modu (seçici
  veya /model, /plan, /otomatik … komutları) kaydedilir; siz yeniden
  değiştirene kadar yeni oturumlar onunla açılır, uygulama güncellemeleri bunu değiştirmez.
- auto için ölçülen değerler: 262k bağlam + yerel araç çağrısı (kayıttaki
  32768 / tools:false yanlış çıktı). Otomatik özet artık auto'da erken çalışmaz.

## Yayınlanmamış — Ortak hafıza: GitHub eşitleme

### Eklendi

- `tools/ai_memory.py baslangic` önce GitHub'la eşitler: başka bilgisayarda
  gönderilmiş yeni commit'leri güvenliyse kendiliğinden alır (yalnız ileri
  sarma), master'a birleştirilmiş daldaysa master'a geçer; yerel değişiklik,
  ayrışmış dal, gönderilmemiş commit ve ağ hatasında dokunmadan uyarır.
  `--esitleme-yok` ile kapatılır. Kural R-18, `tests/test_ai_memory_sync.py`.

## Yayınlanmamış — OpenAI ve Anthropic sağlayıcıları (doğrulanmadı)

### Eklendi

- **Ücretli sağlayıcılar (isteğe bağlı)**: OpenAI (Responses API) ve Anthropic
  (Messages API) istemcileri; sohbet ve kod ajanı (yerel araç çağrısı) ikisinde
  de çalışır. OpenAI şifreli reasoning öğeleri ve Anthropic thinking blokları
  araç turlarında aynen geri gönderilir. **Gerçek anahtarla doğrulanmadı.**
- **Gruplu model seçici**: "EVREN · ücretsiz", "OpenAI · ücretli · doğrulanmadı",
  "Anthropic · ücretli · doğrulanmadı" başlıkları; fiyat ipucu; anahtarı
  olmayan sağlayıcının modelleri "(anahtar gerekli)" — seçilirse Ayarlar'a yönlendirir.
- **Ayarlar > Ücretli Sağlayıcılar**: anahtar kaydet/sil/doğrula (Credential
  Manager), adım adım anahtar alma rehberi, panel bağlantıları (anahtarlar,
  kredi, kullanım, belgeler), veri/kredi notları.
- **Aylık bütçe (varsayılan $5, tüm ücretli sağlayıcılar toplamı)**: harcama
  token sayıları ve tarihli fiyatlarla tahmin edilir; %80'de bir kez uyarı,
  sınırda her yeni istekten (ajan adımı dahil) önce onay. Ayarlar'da "bu ayki
  tahmini harcama".
- Hata türü "Kredi bitti" (402, 429 insufficient_quota, enforced_spend_limit):
  tekrar denenmez, hata kartında sağlayıcı paneli düğmesi. 529 = geçici aşırı yük.
- Şema v3: `usage_costs` tablosu, `sessions.provider`.
- `tests/test_providers.py` (28 sahte test), `tests/e2e_providers_real_api.py`
  (ücretli, `--evet` bayrağıyla).

### Değişti

- Yazma kutusunun altındaki not, verinin gönderildiği sağlayıcıyı gösterir.
- `tests/e2e_real_api.py` zaman aşımı 60 → 180 sn (glm-5.3 bugün 24–56 sn).

## Yayınlanmamış — Otomatik özet (auto-compact)

### Eklendi

- **Otomatik özet**: yeni mesaj gönderilmeden önce bağlam min(modelin %75'i,
  100.000 token) eşiğini aşarsa önce özetlenir, sonra mesaj gönderilir. Uzun
  bir ajan görevi sırasında yalnızca güvenli noktada (araç sonuçları
  kaydedildikten sonra, yeni model çağrısından önce) sert eşik aşılırsa
  özetlenip ajan otomatik devam eder (en fazla 3 kez). Akış, araç veya onay
  sırasında asla özetlenmez. Esc ile iptal: mesaj gönderilmez, kutuya geri konur.
- `/compact [odak]` (`/ozet` ile aynı), özet kartında neden/süre; bağlam
  göstergesinde eşik ve "özet yakında" uyarısı.
- Ayarlar: otomatik özet aç/kapa, eşik yüzdesi, üst sınır, özeti üreten model
  (varsayılan deepseek-v4-flash — ölçümde glm-5.3'ten ~4 kat hızlı).
- `tests/test_auto_compact.py` (9 test), `tests/e2e_compact_real_api.py` (gerçek API özet kalitesi).

### Düzeltildi

- Özet isteği akışsızdı; glm-5.3 uzun düşünürken bağlantı kopuyordu → akışlı.
- Pencere kapandıktan sonra gelen arka plan sonucu kapalı veritabanına yazıp hata veriyordu.
- Test paketinde silinmeyen pencereler birikip süreyi 166 sn'ye çıkarıyordu → 30 sn.

## Yayınlanmamış — Otomatik mod

### Eklendi

- **Otomatik mod** (Claude Code'daki Auto'ya denk, kural tabanlı): düzenlemeler ve
  güvenli listedeki komutlar onaysız; riskli/tanınmayan komutlar gerekçesiyle sorulur.
  Onaysız çalışan araç kartlarında "otomatik" etiketi.
- Modlar Claude Code adlarıyla: Manuel · Düzenlemeleri kabul et · Plan · Otomatik;
  `/manuel`, `/kabul`, `/plan`, `/otomatik` komutları (`/onayli` takma ad).
- Korumalı dosyalar (her modda sorulur) ve gizli dosya okuma onayı; gizli dosyalar
  aramaya dahil edilmez.
- Klasörsüz oturuma "Proje klasörü bağla"; klasörsüz sohbette model bu düğmeyi önerir.
- 49 yeni test (`tests/test_auto_mode.py`); gerçek arayüz e2e'ye Otomatik mod adımı (15/15).

### Değişti

- `/otomatik` artık tam Otomatik modu açar (0.2.0'da "Otomatik düzenleme" idi;
  o mod şimdi "Düzenlemeleri kabul et" / `/kabul`). Kayıtlı eski oturumlar
  güvenli eşdeğerine çevrilir.

## 0.2.0 — 2026-10-16 (Aşama 2: Kod ajanı çalışma alanı)

### Eklendi

- Kod ajanı (`src/evren_studio/agent/`): proje klasörüyle sınırlı 8 araç
  (list_files, read_file, search_files, find_files, write_file, edit_file,
  run_command, update_todos), izin politikası (Plan / Onaylı / Otomatik
  düzenleme), ajan döngüsü (adım sınırı, iptal, bağlam kısaltma).
- API istemcisinde araç çağrısı: `tools` gönderimi, akışlı/akışsız
  `tool_calls` birleştirme; yerel araç reddedilirse metin protokolüne
  (`<arac_cagrisi>`) otomatik geçiş.
- Yeni arayüz: oturum listeli sol menü, karşılama ekranı, Markdown +
  sözdizimi renklendirmeli akış, düşünce bloğu, araç kartları, diff'li onay
  kutuları, sağ panel (Görevler, Değişiklikler + geri alma, Dosyalar,
  Terminal), mod/model seçicili yazma kutusu, koyu/açık tema, simgeler.
- Eğik çizgi komutları (/init, /ozet, /plan, /onayli, /otomatik, /model,
  /yeni, /disa-aktar, /yardim) ve `@dosya` ekleme; mesajı düzenleyip
  yeniden gönderme.
- Veritabanı şema v2: `sessions`, `session_messages`, `file_changes`;
  v1 sohbetleri otomatik olarak klasörsüz oturumlara kopyalanır (eski
  tablolar silinmez).
- Komutlar projedeki `.venv`'i otomatik kullanır (PATH başına eklenir).
- Yakalanmamış hatalar `%LOCALAPPDATA%\EVREN-Model-Studio\logs\crash.log`
  dosyasına yazılır ve Türkçe uyarı gösterilir.
- 51 yeni test (araçlar, izinler, metin protokolü, ajan döngüsü, istemci
  araç çağrısı, oturum veritabanı, arayüz uçtan uca onay akışı).

- Ortak geliştirici hafızası: `AGENTS.md` protokolü, motor giriş dosyaları
  (CLAUDE.md, GEMINI.md, Copilot, Cursor, Kilo, Roo, Cline, Windsurf),
  `docs/ai-memory/` (kurallar, kayıtlar, oturum günlükleri, motor profilleri),
  `tools/ai_memory.py`, git ön-commit kancası, `test_ai_memory.py` ve
  `test_source_hygiene.py`. Uygulama ajanı EVREN.md + AGENTS.md'yi birlikte okur.

- Sohbet ekranında çalışan model ve süre: yazma kutusunun üstünde canlı
  durum çubuğu (model · etkinlik · süre · adım), yanıt başlığında canlı sayaç,
  her yanıtın altında kalıcı "model · süre" ve çok adımlı turlarda tur
  toplamı; `auto` için yönlendirilen model (`auto → …`).
- `/` ile açılan tıklanabilir komut listesi (fare, ↑↓, Enter, Esc);
  `/model` seçilince tıklanabilir model listesi.
- Ayarlar: "Varsayılanlara döndür", her alanın yanında varsayılan değer,
  üstte Kaydet; sayfa açılınca değerler yeniden yüklenir.
- Uygulama geneli fare tekerleği koruması (odaksız alan değişmez).
- Gerçek API uçtan uca testleri: `tests/e2e_agent_real_api.py` (8 model,
  2 protokol), `tests/e2e_ui_real_api.py` (gerçek arayüz, 14 kontrol);
  arayüz QA paketi `tests/test_ui_pages.py` (tüm ekranlar, iş parçacığı
  uyarısı denetimi).

### Düzeltildi

- Durum İzleme sayfası arayüzü arka plan iş parçacığından güncelliyordu
  (çökme/donma riski); durdurma arayüzü 10 sn'ye kadar donduruyordu.
- Arka plan görevlerinin sonucu, görev nesnesi çöpe giderse kaybolabiliyordu.
- Ayarlar fare tekerleğiyle farkında olmadan değişiyordu.
- Esc, açık komut listesini kapatmıyordu; LLM'lerin boş satırsız yazdığı
  Markdown listeleri paragraf görünüyordu.
- 7 kaynak dosyada çift kodlanmış (mojibake) Türkçe metinler: arayüzde
  "YanÄ±t bekleniyorâ€¦" gibi görünüyordu (kodlama-ornegi).
- Ayarlar açılışta hiç okunmuyordu (`ConfigStore.load()` çağrılmıyordu).
- `secrets.py` `.gitignore` nedeniyle depoya hiç girmemişti (0.1.x düzeltmesi).
- Açılışta model listesi ana iş parçacığında çekilip arayüzü donduruyordu.

### Kaldırıldı

- Eski Chat, Code Studio ve Sohbetler sayfaları (yerini oturum çalışma
  alanı aldı).

## 0.1.0 — 2026-10-15 (Aşama 1 MVP)

### Eklendi

- EVREN LLM API istemcisi: healthz/readyz (kimliksiz), models, chat
  (akışlı/akışsız), quota, istek durumu sorgusu, şart durumu.
- Hata sınıflandırma ve kurtarma motoru: 10 hata sınıfı, Türkçe
  açıklamalar, Retry-After/artan bekleme (≤3 tekrar), belirsiz sonuçta
  durum sorgusu, imza tabanlı geçmiş çözüm araması.
- Kalıcı bilgi sistemi: ERROR_CATALOG, RECOVERY_PLAYBOOK,
  MODEL_CAPABILITIES, API_COMPATIBILITY, KNOWN_LIMITATIONS, LESSONS_LEARNED,
  EVREN_STATUS_HISTORY + PROJECT_STATE, TASK_CHECKLIST, DECISIONS.
- Windows Credential Manager ile API anahtarı yönetimi (maskeleme dahil).
- Türkçe PySide6 arayüzü: ana sayfa, chat (akış + iptal + geçmiş),
  code studio temeli (dosya ağacı/düzenleyici/kaydet), modeller,
  bağlantı testi, kota, sohbet geçmişi, hata merkezi, durum izleme,
  ayarlar, yardım/tanılama.
- EVREN Durum İzleme Ajanı: 30 dk toplam / 5 dk aralıklı kontrol,
  duyuru sayfası değişiklik tespiti, healthz/readyz/models kontrollerı,
  isteğe bağlı gerçek model testi, Türkçe rapor (kesin/tahmini ayrı),
  yarım kalan izlemeye devam.
- SQLite: sohbetler, mesajlar, hata kayıtları, izleme oturumları/kontrollerı,
  model sağlığı. İş parçacığı güvenli (RLock).
- 53 birim testi + UI duman testi + uçtan uca gerçek API testi (E2E_OK).
- run.bat başlatıcı; pyproject.toml ile kurulabilir paket.

### Doğrulanan gerçek dünya sonuçları (2026-10-15)

- 16 canlı model; glm-5.3 sohbet+akış 200 OK; auto → qwen3.8-flash-next;
  kota ok; istek durumu sorgusu success; 404/401 hata davranışları.
