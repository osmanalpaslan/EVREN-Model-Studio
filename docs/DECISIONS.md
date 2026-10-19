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

## Değerlendirilip reddedilenler

- **PyInstaller paketleme (şimdi)**: Aşama 4'e bırakıldı; önce çalışan temel.
- **asyncio/qasync**: iki olay döngüsü karmaşıklığı; kazanım yok.
- **requests**: SSE akışı ve MockTransport'ta httpx daha iyi.
- **Düz metin anahtar dosyası**: güvenlik gereği reddedildi (kural).
- **Windows Görev Zamanlayıcı ile izleme**: MVP'de gereksiz sistem servisi;
  kullanıcı başlatmalı uygulama içi zamanlayıcı yeterli.
