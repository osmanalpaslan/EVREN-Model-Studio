# Mimari ve Teknoloji Kararları

| # | Karar | Gerekçe | Tarih |
|---|---|---|---|
| 1 | Python 3.12 (winget, kullanıcı kapsamı) | Desteklenen kararlı sürüm; PySide6/httpx/keyring uyumu; yönetici yetkisi gerektirmez | 2026-10-15 |
| 2 | PySide6 (Qt6) | Resmî Qt for Python; yerel Windows masaüstü görünümü; LGPL | 2026-10-15 |
| 3 | httpx (sync) | HTTP/1.1 + SSE akışı + MockTransport ile test edilebilirlik; requests akışta daha az esnek | 2026-10-15 |
| 4 | SQLite (stdlib sqlite3) | Yerel tek dosya; sohbet/hata/izleme için yeterli; sunucu gerektirmez | 2026-10-15 |
| 5 | keyring → Windows Credential Manager | OS kasası; anahtar kaynak koda/düz dosyaya yazılmaz; sessiz düz metin geçişi YOK | 2026-10-15 |
| 6 | src düzeni + pyproject.toml + pip install -e | Test/uygulama içe aktarımları temiz; `python -m evren_studio` çalışır | 2026-10-15 |
| 7 | Senkron istemci + QThread/sinyal | asyncio+qasync ek karmaşıklık getirirdi; MVP için sade ve yeterli | 2026-10-15 |
| 8 | Tek httpx.Client ömrü (istek başına değil) | Akış yanıtları istemci kapatılınca kopar (LESSONS_LEARNED #4 benzeri tuzak) | 2026-10-15 |
| 9 | İstemcide URL normalizasyonu (`/v1` soyma) | Resmî OpenAPI yollarıyla çakışmayı önler (ders #1) | 2026-10-15 |
| 10 | Retry-After üst sınırı 300 sn | Daha uzun bekleme kullanıcıyı bloklar; kararı kullanıcıya bırakma | 2026-10-15 |
| 11 | Belirsiz sonuçta otomatik tekrar YOK | İstek sunucuda çalışmış olabilir; `/v1/requests/{id}` doğrulandı | 2026-10-15 |
| 12 | Otomatik model değiştirme varsayılan KAPALI | Kullanıcı güveni + yanlış modele geçiş riski | 2026-10-15 |
| 13 | İzleme ajanı kullanıcı başlatmalı | Sonsuz arka plan izleme izinsiz kurulmaz; 30 dk/5 dk planı | 2026-10-15 |
| 14 | Duyuru izleme hedefi = genel ana sayfa | Duyuru API'si 401/giriş gerektiriyor; URL kullanıcı tarafından değiştirilebilir | 2026-10-15 |
| 15 | Mesajlar QPlainTextEdit (Markdown yok) — **#25 ile değişti** | MVP sadeliği; hata yüzeyini küçültür; Aşama 2'de zenginleştirildi | 2026-10-15 |
| 16 | Komut çalıştırma MVP'de YOK — **#23 ile değişti** | Güvenlik: onaylı ve sınırlı tasarım Aşama 2'de eklendi | 2026-10-15 |
| 17 | SQLite check_same_thread=False + RLock | İzleme ajanı ayrı iş parçacığında (ders #5) | 2026-10-15 |
| 18 | Ücretsiz/yerel araçlar dışında sağlayıcı YOK | Kullanım güvenliği; tüm istekler yalnız EVREN'e | 2026-10-15 |
| 19 | Arayüz oturum tabanlı (Claude Code benzeri): sol menü + akış + sağ panel | Kullanıcı isteği; sohbet ve kod çalışması tek yerde; 11 ayrı sayfa yerine tek çalışma alanı | 2026-10-16 |
| 20 | Ajan çekirdeği Qt'den bağımsız paket (`agent/`) | Arayüzsüz test edilebilir; döngü, araçlar, izinler ayrı modüller | 2026-10-16 |
| 21 | Yerel function calling + metin protokolü geri dönüşü | EVREN şemasında `tools` var ama gerçek tur doğrulanmadı; reddedilirse (400/422) `<arac_cagrisi>` bloklarıyla devam | 2026-10-16 |
| 22 | Yazma araçları "hazırla → onay → uygula" | Diff onaydan önce gösterilir; onay beklerken değişen dosyanın üzerine yazılmaz | 2026-10-16 |
| 23 | Komutlar hiçbir modda onaysız çalışmaz — **#28 ile değişti: Otomatik modda yalnız güvenli listedekiler onaysız** | Güvenlik; yalnızca kullanıcının izin verdiği öneklere ve zincirsiz komutlara oturum izni | 2026-10-16 |
| 24 | Dosya değişiklikleri DB'de önce/sonra içerikle saklanır | Git'ten bağımsız geri alma; git deposu olmayan projelerde de çalışır | 2026-10-16 |
| 25 | Markdown (python-markdown) + Pygments, QTextBrowser | Saf Python, küçük, BSD lisanslı; Qt zengin metniyle uyumlu satır içi stiller | 2026-10-16 |
| 26 | Şema v2: eski `chats/messages` silinmez, oturumlara kopyalanır | Geri dönüşü olmayan veri kaybını önler | 2026-10-16 |
| 27 | run.bat `pythonw` + crash.log | Konsol penceresi açılmaz; hatalar kaybolmaz | 2026-10-16 |
| 28 | Otomatik mod yalnız kural tabanlı | Kullanıcı kararı: hızlı, ücretsiz, deterministik; yapay zekâ denetçisi yok; tanınmayan komut sorulur | 2026-10-16 |
| 29 | Yeni mod anahtarları (manuel/kabul/plan/auto), eskiler güvenli eşdeğere | Eski `otomatik` = düzenlemeleri kabul et; yeni Otomatik'e çevrilseydi oturumlar sessizce yetki kazanırdı | 2026-10-16 |
| 30 | Korumalı dosyalar her modda sorulur; gizli dosya okuma da sorulur | Claude Code'daki korumalı yollar; .env içeriği EVREN'e gitmesin | 2026-10-16 |
| 31 | Otomatik özet: mesajdan önce + tur içinde yalnız güvenli noktada; eşik min(%75, 100k), sert min(%90, ×1,5) | İş yarıda kesilmez; özet isteği sığar; büyük bağlamda yavaşlık ve günlük kota korunur | 2026-10-16 |
| 32 | Özet modeli varsayılan deepseek-v4-flash, akışlı istek | Gerçek ölçüm: aynı özet glm-5.3 153 sn / deepseek-v4-flash 41 sn, kalite eşdeğer; akışsız istek glm-5.3'te koptu | 2026-10-16 |
| 33 | OpenAI için Responses API, Anthropic için yerel Messages API | Chat Completions yeni GPT'lerde reasoning + araç birlikte çalışmıyor; Anthropic uyumluluk katmanı "üretim için değil", thinking yok | 2026-10-16 |
| 34 | Sağlayıcı durumu (`_provider_state`) mesaj meta'sında saklanıp aynen geri gönderilir | Şifreli reasoning / imzalı thinking blokları araç turlarında zorunlu; EVREN'e gitmeden silinir | 2026-10-16 |
| 35 | Ücretli sağlayıcılarda aylık bütçe: %80 uyarı, sınırda her istekten önce onay (varsayılan $5) | Kullanıcı kararı; kalan kredi API'den okunamadığı için yerel tahmin; ücretli hizmet onay kuralı | 2026-10-16 |
| 36 | Ücretli model kataloğu statik ve tarihli (`PRICES_AS_OF`) | `/v1/models` fiyat/yetenek vermiyor; doğrulanmamış = `verified=False` (R-17) | 2026-10-16 |
| 37 | Varsayılan motor `auto`; eski varsayılan glm-5.3 bir kez taşınır | Kullanıcı kararı; eski sürüm varsayılanı dosyaya yazdığı için bilinçli seçimden ayırt edilemedi, kullanıcı taşımayı onayladı | 2026-10-16 |
| 38 | Sohbette seçilen motor ve onay modu kalıcı varsayılan olur | Kullanıcı kararı: "her değişiklik ben değiştirene kadar korunsun"; Otomatik mod da hatırlanır | 2026-10-16 |
| 39 | Ekler kart olarak; yol metne yazılmaz, mesaj meta'sında tutulur | Kullanıcı isteği (Claude Code gibi); geçmiş yeniden çizilebilir, düzenlemede geri gelir | 2026-10-19 |
| 40 | Görseller küçültülmüş kopyayla veri klasöründe saklanır, `_images` ile istemciye taşınır | Asıl dosya silinse de geçmiş bozulmaz; çekirdek Qt'siz kalır, sağlayıcı biçimi istemcide | 2026-10-19 |
| 41 | Görsel okuyamayan motorda gönderimden önce auto önerilir | Ölçüm: glm-5.3 ve deepseek-v4-flash 400 veriyor; auto görseli uygun modele yönlendiriyor | 2026-10-19 |
| 42 | Kullanım düğmesi: günlük kalan %; panel /v1/quota + oturum + ücretli bütçe | Kullanıcı isteği; ağ isteği arka planda, açılışta yalnız app.py'den (testler ağ yapmaz) | 2026-10-19 |
| 43 | Sürekli arka plan kendi kendini test etme yerine elle/CI çalıştırılan kısa zorluk paketi | Kota harcamaz, kullanıcı dosyalarına dokunmaz; her kullanıcı kendi anahtarıyla çalıştırır | 2026-10-19 |
| 44 | Model davranış hatalarında önce araç çıktısı/kod denetimi, sonra istem | Ölçüm: istem kuralı tek başına auto'da 2/3; kod denetimi 3/3 | 2026-10-19 |
| 45 | Kurulum: kurulum.bat (venv + kısayol), EXE sonraya | Hemen herkes kurabilsin; PyInstaller paketleme (Aşama 4) ayrı iş | 2026-10-19 |
| 46 | Uygulama içi yönlendirici (EVREN Akıllı, 51'de Auto Pro oldu); sunucu auto listede kalır | Kullanıcı kararı; auto öngörülemez/görünmez; rol tablosu 8 motor ölçümünden | 2026-10-19 |
| 47 | Tur ortasında model değişmez; yalnız sunucu hatası/döngü/görsel reddinde yedeğe (2026-10-23: #88 ile güncellendi — aşırı yavaşlık da neden) | Tutarlılık; kota/hız sınırı hesap başına olduğu için o hatalarda geçilmez | 2026-10-19 |
| 48 | Proje ajanı: plan onayı zorunlu, görev başına temiz bağlam, doğrulama + ikinci model incelemesi, ayrı git dalı | Kullanıcı kararları; uzun tek tur kalitesi düşüyordu; her adım geri alınabilir | 2026-10-19 |
| 49 | Takılan görev silinmez: git stash; bağımlıları atlanır, bağımsızlarla devam | Gözetimsiz çalışmada sonsuz deneme/veri kaybı olmasın | 2026-10-19 |
| 50 | Bildirim: Windows sistem tepsisi bildirimi + rapor dosyası (telefon yok) | Kullanıcı kararı; ek hizmet gerektirmez | 2026-10-19 |
| 51 | "EVREN Akıllı" → "Auto Pro"; yalnız anahtarı girilmiş sağlayıcıların modelleri listelenir ve yönlendirilir; yalnız ücretli anahtarda da Auto Pro var | Kullanıcı kararı: EVREN motorları EVREN anahtarı yokken çıkmamalı | 2026-10-19 |
| 52 | Çok sağlayıcıda "dengeli" politika: plan/inceleme/görsel önce ücretli, diğer roller önce EVREN | Kullanıcı kararı; çok token harcayan işler ücretsiz EVREN'de, az token yüksek değerli işler güçlü modelde | 2026-10-19 |
| 53 | Uygulamanın kendi yapay zekâ işleri tek yoldan: `AppContext.ai_chat(rol)` (Auto Pro zinciri, bütçe, maliyet, yedek) | Kullanıcı isteği: hangi API bağlıysa onu kullansın; yeni özellikler: başlık, hata açıklaması, commit mesajı | 2026-10-19 |
| 54 | Kısa iç yapay zekâ isteklerinde EVREN düşünmesi kapalı (`reasoning_effort: none`), boş yanıt = yedeğe geç | Gerçek API: düşünen modeller küçük `max_tokens`'ta boş içerik döndü | 2026-10-19 |
| 55 | Bağlam göstergesi yüzdesi özet eşiğine göre; Auto Pro penceresi seçilecek modelin (ve yedeklerin) en küçüğü; 100k üst sınır korunur | Kullanıcı "%10'da özetleniyor" dedi; ölçüm: 5 dk'da 2,5M, günde 15M token, ajan her adımda geçmişi yeniden gönderir | 2026-10-19 |
| 56 | Koyu temada tüm yazı/simge tek parlaklık (#e8e9ec); yalnız yer tutucu ve devre dışı `muted`; vurgu (düğme, onay kutusu, seçili sekme, bağlantı) mavi değil beyaz | Kullanıcı kararı: "Görevler" kadar parlak olsun, düğmeler mavi olmasın; devre dışı öğe etkin sanılmasın | 2026-10-19 |
| 57 | MCP istemcisi kendi küçük stdio JSON-RPC uygulamamız (yalnız initialize/tools), resmî `mcp` SDK değil | Ajan çekirdeği eşzamanlı; SDK asyncio ve 1.x→2.x API değişti; sahte sunucuyla tam test edilebilir | 2026-10-19 |
| 58 | İlk MCP sunucusu Serena 1.7.0 (MIT) sabit; 2.0.0 GPL-3.0 ve 6 günlük olduğu için alınmadı | Kullanıcı onayı (öneri); lisans ve tedarik zinciri temkini | 2026-10-19 |
| 59 | Serena veri klasöründe ayrı venv'e (uv + pyright dahil) kurulur; sisteme program kurulmaz | Kullanıcıda uv yoktu; uvx'in %APPDATA%\uv kurulumu ilk denemede hata verdi; tek yerde, kaldırması kolay | 2026-10-19 |
| 60 | MCP'de yalnız listelenen okuma araçları sormadan; Serena'da yalnız 3 okuma aracı açık | MCP değişiklikleri fark kartı/geri alma/kapsam denetimine girmez (R-20); sunucunun readOnlyHint'ine güvenilmez | 2026-10-19 |
| 61 | Sistem istemi sembol işlerinde search_files'tan önce Serena'yı önerir | Ölçüm: yönlendirme olmadan model Serena'yı hiç çağırmadı (MCP 0/4); yönlendirmeyle çağırdı, doğruluk aynı, büyük projede araç çıktısı yarıya indi | 2026-10-19 |
| 62 | MCP yalnız gerektiğinde: araçlar önbellekten, süreç ilk çağrıda, boşta kapanır; sunucu başına `when` (kod/web) | Kullanıcı kararı; zayıf model az araçla daha iyi seçer; küçük projede Serena yalnız süre ekledi (ölçüm) | 2026-10-19 |
| 63 | Ücretli sağlayıcıda MCP KESİNLİKLE yok; yedek modeller turun sağlayıcısıyla sınırlı | Kullanıcı kararı: uygulamanın amacı ücretsiz hizmet | 2026-10-19 |
| 64 | Hata bekçisi: düzenleme sonrası yerleşik denetim + Serena teşhisi, yalnız kesin hatalar | EVREN motorları kontrol etmeden "bitti" diyebiliyor; import/tip çıkarım uyarıları yanlış alarm (ölçüm) | 2026-10-19 |
| 65 | Playwright: kurulu Edge, `--isolated --headless --image-responses omit`, dosyalar 127.0.0.1 sunucusundan (gizliler hariç) | `file:` engelli; tüm diske izin veren seçenek fazla geniş; görüntü kotayı yer | 2026-10-19 |
| 66 | Node.js winget ile sistem geneline | Kullanıcı tercihi (taşınabilir Node yerine) | 2026-10-19 |
| 67 | Serena dil sunucuları ortak, kısa (8.3) klasörde; venv'e sitecustomize yaması | C# yolu 260 karakteri aşıyordu, her proje yeniden indiriyordu; Serena 1.7.0 sabit, yama yalnız env varsa etkin | 2026-10-19 |
| 68 | QA ajanı yalnız web (masaüstü otomasyonu yok) ve yalnız EVREN | Kullanıcı kararı; EVREN görsel modelleri koordinatla tıklamada güvenilir değil (analiz) | 2026-10-19 |
| 69 | QA senaryoları dosyaya YAZMADAN (no_writes) koşulur; düzeltme Proje ajanına ayrı onayla | Test eden ile düzelten ayrı: bulgu yanlış alarmsa kod bozulmaz | 2026-10-19 |
| 70 | Arka plan servisleri tur sonunda kapanır (QA hariç) | Kullanıcının bilgisayarında unutulmuş sunucu/port kalmasın | 2026-10-19 |
| 71 | Test bekçisi yalnız tur başında geçen testler bozulunca uyarır | Önceden bozuk ilgisiz testler modeli kapsam dışına sürüklemesin (R-20) | 2026-10-19 |
| 72 | QA kota bekçisi yok | Kullanıcı kararı (gerek görmedi) | 2026-10-19 |
| 73 | Faz unutma için plan bekçisi + Proje ajanı ÖNERİSİ (sessiz yönlendirme yok) | Kullanıcı kararı; Proje ajanı Otomatik mod, ayrı dal ve commit demek — kullanıcı seçmeli | 2026-10-21 |
| 74 | Plan bekçisi yalnız BU turda yazılan/düzenlenen plan dosyasını veya bu turun görev listesini sayar; ilerleme = gerçek iş (dosya yazma/komut), işaret değiştirmek değil | Eski TODO dosyaları yanlış tetiklemesin (R-22); model yalnız kutucuk işaretleyerek bekçiyi susturamasın | 2026-10-21 |
| 75 | Derin Mod düğmeyle açılır; açıkken HER iş anla→planla→uygula→doğrula→düzelt | Kullanıcı kararı | 2026-10-21 |
| 76 | Derin Mod çalışma modlarına (MODES) eklenmedi; ayrı düğme + `/derin` | R-14: izin modu adları yetki taşır; Derin bir akıştır, izin değil | 2026-10-21 |
| 77 | Derin Mod'da yazan TEK: Proje ajanı (onaylı plan); alt ajanlar salt okunur ve onay isteği anında reddedilir | Paralel yazıcılar dosya çakışması yaratır; arayüzsüz ajan onay beklerken sonsuza dek takılır | 2026-10-21 |
| 78 | Derin Mod yalnız EVREN; paralellik varsayılan 2, en çok 3; pencere ≥ %60 → 1 | Uygulamanın amacı ücretsiz hizmet; 5 dk penceresi 2,5M token | 2026-10-21 |
| 79 | Ek EVREN API anahtarı / anahtar döndürme YOK | EVREN Kullanım Şartları v1 §2: kota/hız sınırını atlatma, anahtar paylaşımı ve otomatik hesap oluşturma yasak (2026-10-21'de `/v1/terms/text` okundu) | 2026-10-21 |
| 80 | Uzun işler için ayrı araçlar (start_job/wait_job); bekleme KODLA | 5 dk pencere hız sınırıdır, süre sınırı değil: model çağrılmadan beklemek token harcamaz; run_command 30 dk'da keser | 2026-10-21 |
| 81 | Kota sonrası otomatik sürdürme, açılıp kapatılabilir (varsayılan açık) | Kullanıcı kararı (önerilen plan onaylandı) | 2026-10-21 |
| 82 | Tek `powershell … -Command "…"` sarmalaması açılır; -File/-EncodedCommand/belirsiz birleşik komutlar olduğu gibi | Dış kabuk `$`'ı yutuyordu; belirsiz durumda komutu değiştirmek yanlış komut çalıştırma riski taşır | 2026-10-21 |
| 83 | Doğrulama komutu komut SATIRINDA sözdizimi/bağlama hatası verirse görev düşmez, karar incelemeye | Komut planlayıcının hatası, görevin değil; betik içi hata gerçek başarısızlık | 2026-10-21 |
| 84 | Takılan görev varsa proje "bitti" değil "duraklatıldı"; sürdürme takılanı sıfır denemeyle yeniden dener | 3/12 ile "tamamlandı" yanıltıcıydı; Derin Mod bu duruma güvenip doğrulamaya geçiyordu | 2026-10-21 |
| 85 | Kullanıcı kararı gerektiren konular Derin'de planlamadan önce sorulur; görevde `SORU:` ile duraklatılır; yanıtsız sürdürme = açıkça yazılan varsayım | Gözetimsiz ajan onayı kendisi yazdı (R-28) | 2026-10-21 |
| 86 | ASCII dışı içerikli .ps1/.psm1/.psd1 UTF-8 BOM ile yazılır | PowerShell 5.1 BOM'suz betiği ANSI okur (ölçüm: 19 → 24 karakter) | 2026-10-21 |
| 87 | Auto Pro kod rolü: deepseek-v4.1-flash → qwen3.8-flash-next → gemma-4-31b | Yeniden ölçüm: üçü 12/12; v4.1 7,0 dk ve en az adım, qwen 8,9 dk en çok adım; gemma 3,1 dk ama uzun işte döngü geçmişi (kullanıcı kararı) | 2026-10-21 |
| 88 | (#47'yi günceller; F1'de UYGULANDI 2026-10-24) Aşırı yavaşlık da yedeğe geçme nedenidir: (1) yalnız güvenli noktada — iki adım arası, yarım düzenleme yokken, konuşma aynen aktarılır; (2) motorun o günkü gerçek ölçümle hesaplanan normal hızının yarısının altında art arda 2 adım; (3) görev başına yavaşlıktan en çok 1 değişim; (4) her değişim gerekçesiyle bildirilir; (5) Proje/Derin'de önce görev aralarında değişir, görev içinde yalnız ~3 kat yavaşlıkta | Kullanıcı: motor ortalama hızının %50'sinin altına düşerse değişsin; #47'nin amacı (tutarlılık + görünürlük) korunur (kullanıcı onayı, öneri A3) | 2026-10-23 |
| 89 | Auto Pro F1 parametreleri: yanıt vermeme 60 sn (ayar); normal hız = son 6 sa (yetmezse 24 sa) en az 6 başarılı çağrının ortancası; hız yalnız ≥150 token'lı yanıtta, ilk yanıt eşiği normalin 2 katı ve en az +10 sn; yedeğe geçen model 30 dk sona (model_health); akış kopması (UNKNOWN_RESULT) yedeğe geçirir | Ölçüm: sağlıklı motorda ilk parça ≤ 2,7 sn (küçük istek), zorluk paketinde ≤ 10,1 sn (büyük bağlam); az örnekle karar vermek yanlış geçiş üretir (R-22) | 2026-10-24 |
| 90 | Auto Pro zorluk (A6) ve iş türü (A7) kuralları model çağrısı yapmadan, açıklanabilir metin kurallarıyla; şüphede "normal". Kolay iş (kısa, tek dosya, test/çok dosya yok) → `kod_kolay` (gemma önde); kolay turu başarısızsa veya kullanıcı "olmadı" derse sonraki tur güçlü zincire yükselir. İş türü: veri/oyun/web mesajdan (dosya adı iş türü sayılmaz), proje dosyalarından yalnız tek tür varsa; kod projesindeki .csv veri yapmaz. Metin rolü yalnız klasörsüz sohbette | Yanlış "kolay" en pahalı hata (hızlı model uzun işte döngüye girer); sınıflama için ek model çağrısı hem gecikme hem kota; yanlış tetiklenme R-22 | 2026-10-24 |
| 91 | Rol zincirleri (rol paketi ölçümü 2026-10-24, paket başına 2 görev × 1 koşu): veri qwen → gemma → deepseek-v4.1; web ve oyun qwen → deepseek-v4.1 → gemma; metin qwen → gemma → deepseek-v4.1; kod_kolay gemma → deepseek-v4.1 → qwen. Kod rolü #87 olarak kalır | qwen 8/8 ve her pakette en hızlı; gemma 7/8, deepseek-v4.1 7/8 ve ~4 kat yavaş. Örnek küçük: model listesi değişince paket yeniden koşulur | 2026-10-24 |
| 92 | A10: `temperature=0 + seed` yalnız seed'i dinlediği ölçülen modele (gemma-4-31b) ve yalnız veri rolünde; veri tutarlılığı asıl "hesabı betikle yap" talimatıyla | Ölçüm: deepseek-v4.1 ve qwen seed'le de 3/3 farklı metin; temperature=0 ajan işinde tekrar döngüsü riskini artırabilir | 2026-10-24 |
| 93 | A5 kalite puanı: döngü (2), istenmeden kalan test değişikliği (2), testi bozma (1), plan bekçisinde ilerlemesizlik (1), kullanıcının 👎 işareti (3) — son 24 saat; en az 6 çağrıda puan < 0,6 veya 2 👎 → model zincirde sağlamların ARKASINA alınır, çıkarılmaz; aynı yanıt iki kez sayılmaz | Az örnekle cezalandırma yanlış sıralama üretir; kullanıcı işareti açık bir sinyal | 2026-10-24 |
| 94 | A8 yoklama: canlı model listesi ilk gelince ve Derin/Proje başlarken, en çok 30 dk'da bir (veritabanından bakılır), rol zincirlerindeki modellere ≤ 32 tokenlık istek; yalnız altyapı hatası (sunucu, zaman aşımı, ağ, bulunamadı) modeli 30 dk sona alır; başarılı yoklama yalnız önceki YOKLAMA hatasını siler; yoklama normal hız hesabına girmez | Kota/hız sınırı hesap başınadır; yavaşlık/döngü beklemesini kısa bir "tamam" yanıtı geçersiz kılmamalı; kısa istek ilk parça süresini olduğundan iyi gösterir | 2026-10-24 |
| 95 | A11: normal EVREN turunda kota kapısı (ayar, varsayılan açık): 5 dk pencere ≥ %85 → yenilenene kadar kodla bekle; günlük kota azken DURDURMA, bir kez uyar. Model değiştirilmez | Tüm EVREN modelleri aynı kotayı paylaşır; token çoğunu bağlam harcar, hafif modele geçmek kotayı çözmez | 2026-10-24 |
| 96 | A13 planlayan + yazan: zor işte (Auto Pro, proje klasörü, Plan modu değil, ayar açık) planlayıcı "plan" zincirinden salt okunur alt ajan olarak plan yazar, yazan "kod_kolay" zincirinden; aynı motorsa çalışmaz; plan alınamazsa iş plansız sürer. Varsayılan: ölçüme göre (CHALLENGE_RESULTS "A13") | Aider "architect" düzeni; kazanç gösterilmeden açık bırakılmaz (R-25) | 2026-10-24 |
| 97 | Test politikası: gerçek API testleri (R-13, zorluk paketi) faz sonunda, birleştirmeden önce bir kez; çok motorlu ölçüm yalnız motor sırası değişirken (R-30) | Faz başına 1,5–2 saat test; birleştirme öncesi tam kontrol kaldığı için bozuk kod master'a girmez (kullanıcı onayı) | 2026-10-24 |
| 98 | Özet/kapsam modeli varsayılanı "auto-pro" (rolün sağlıklı motoru); eski varsayılan deepseek-v4-flash ayar sürümü 4'te taşınır, bilerek seçilen korunur | v4-flash listeden kalktı; ayar ekranda kalkmış motoru gösteriyordu | 2026-10-24 |
| 99 | `read_table` yalnız standart kütüphaneyle (zipfile + XML akışı); hesap için değil yapı için | Uygulama ortamında openpyxl yok; büyük dosyada bellek şişmesin; sayılar betikle hesaplanır (ROLE_HINTS) | 2026-10-24 |
| 100 | Proje haritası sistem isteminde (~3 bin token, 3 dosyadan azsa yok, büyük projede klasör özeti); Proje görevine önceki görevlerde okunan dosyaların GÜNCEL içeriği (≤16 bin karakter, gizli dosya yok) | Keşif ve yeniden okuma adımları her biri tüm bağlamla model çağrısı; güncel içerik eski özetin yanıltmasını önler | 2026-10-24 |
| 101 | E6 ders önerisi: yalnız sinyal (başarısız→başarılı komut, kurulum, test düşmesi) varsa model çağrısı; EVREN.md'ye yalnız kullanıcı onayıyla, bölüm 30 madde | Sıradaki turda gereksiz çağrı/yazma olmasın (R-22); EVREN.md her turda isteme girer | 2026-10-24 |
| 102 | E8: `evren_tools` kullanılmaz (ölçümde canlı veri yok); kendi `web_fetch`: yalnız verilen http(s) adresi, arama yok, JavaScript yok, komut gibi onay (alan adı başına oturum izni), sonucun başında güvenilmez içerik uyarısı | Ücretli arama API'si yok (kullanıcı kararı); adres sorgusuyla veri dışarı gidebilir; sayfadaki talimat enjeksiyonu | 2026-10-24 |
| 103 | Skill'ler uygulama veri klasörüne KOPYALANIR; kaldırma yalnız kopyayı siler, kaynak klasöre dokunmaz; "kaynaktan yenile" ile güncellenir | Kaynak taşınsa/silinse de çalışsın; kullanıcının dosyasını uygulama asla silmesin | 2026-10-24 |
| 104 | İsteme skill'in yalnız adı + ≤300 karakter açıklaması girer; içerik `read_skill` ile, yalnız etkin skill varken ve yalnız o projenin skill'leri | 7.2 kararı; token tasarrufu; R-25 ölçümü modelin gerçekten açtığını gösterdi (2 çağrı, kurallar uygulandı) | 2026-10-24 |
| 105 | Profil = motor + mod + skill seçimi (boş = projedeki tümü) + ek talimat; oturuma bağlanır (sessions.profile) | E5; profil silinince oturumlar profilsiz sürer | 2026-10-24 |
| 106 | Skill denetçisi (SKILL.md `denetci:` veya denetle.py/check.py) yalnız o turda okunan skill için; Otomatik modda sormadan, diğer modlarda onay kartıyla; çıkış 0 = geçti | Skill kullanıcı tarafından eklendi ama betik çalıştırmak izin moduna uymalı | 2026-10-24 |
| 107 | Şablon mesaj kutusunu DOLDURUR, göndermez | Köşeli parantezli yerler kullanıcının işine göre düzenlenmeli | 2026-10-24 |
| 108 | Uzun oturum: tam sanallaştırma YOK; "önceki mesajlar" her tıklamada 60 mesaj daha | Ölçüm: açılış zaten ≤ 0,6 sn (son 40 mesaj); donma yalnız "tümünü göster"de (4000 mesaj 67 sn). Sanallaştırma karmaşık ve riskli, sayfalama sorunu çözüyor | 2026-10-24 |
| 109 | Sade görünüm yalnız BAŞARILI ve BİTMİŞ araç kartlarını gizler; çalışan, onay bekleyen ve hatalı kartlar her zaman görünür | Onay kaçırılmasın, hata görünsün | 2026-10-24 |
| 110 | Zaman özeti kartı yalnız ≥ 60 sn ve ≥ 3 adımlı turda; Proje/Derin tahmini "kaba tahmin" diye etiketlenir | Kısa turda gürültü (R-22); tahmin veriyle iyileşir ama kesin değildir (R-07) | 2026-10-24 |
| 111 | Oturum yedeği: sqlite backup API ile tutarlı kopya + config.json + skill'ler → kullanıcının seçtiği .zip; API anahtarları girmez | Açık veritabanını dosya kopyalamak bozuk yedek üretebilir; anahtarlar Credential Manager'da kalır | 2026-10-24 |

## Değerlendirilip reddedilenler

- **PyInstaller paketleme (şimdi)**: Aşama 4'e bırakıldı; önce çalışan temel.
- **asyncio/qasync**: iki olay döngüsü karmaşıklığı; kazanım yok.
- **requests**: SSE akışı ve MockTransport'ta httpx daha iyi.
- **Düz metin anahtar dosyası**: güvenlik gereği reddedildi (kural).
- **Windows Görev Zamanlayıcı ile izleme**: MVP'de gereksiz sistem servisi;
  kullanıcı başlatmalı uygulama içi zamanlayıcı yeterli.
