---
id: 2026-10-21-claude-masaustu-surecleri-appdata-local-i-sanal-goruyor-gerc
tarih: 2026-10-21
tur: ortam            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: kabul-edildi                # acik | izleniyor | cozuldu | kabul-edildi
alan: surec
kaynak_motor: bilinmiyor
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PowerShell 5.1, Python 3.12.10
etiketler: [msix, sanallastirma, appdata, claude-masaustu]
kurallar: []
---

# Claude masaüstü süreçleri AppData Local'i sanal görüyor; gerçek EVREN verisi UNC yolundan okunur

## Belirti
Kullanıcının çalışan EVREN Studio oturumunu incelerken `%LOCALAPPDATA%\EVREN-Model-Studio\evren.db` 19 Ekim tarihli
görünüyordu; bugün 13:46'dan beri çalışan uygulamanın verisi yoktu. Aynı dosya
`AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\EVREN-Model-Studio` altında da vardı.

## Kök neden
Doğrulandı (davranış), mekanizma tahmini: Claude masaüstü uygulaması MSIX paketi; onun başlattığı süreçlerin
(Claude Code araçları, testler) AppData\Local yazmaları paket önbelleğine yönlendiriliyor ve okumalar o kopyayı
gösteriyor. Kullanıcının kendi başlattığı uygulama gerçek klasöre yazıyor. 2026-10-19 kaydındaki "oturum kaydı Comodo
kapsamasında kaldığı için bulunamadı" açıklaması da büyük olasılıkla BU durumdu (doğrulanmadı).

## Çözüm
Gerçek klasör `\\localhost\C$\Users\<kullanıcı>\AppData\Local\EVREN-Model-Studio` yolundan okunur; çalışan
uygulamanın veritabanı önce KOPYALANIR, kopya incelenir (canlı dosyaya yazılmaz).

## Kanıt
UNC listesi: evren.db 5 MB, 15:27; sanal görünüm: 80 KB, 19.10 19:37.

## Önleme
Kullanıcının EVREN verisini incelerken önce UNC yolunu dene; testlerin EVREN_STUDIO_DATA_DIR kullanması doğru.

## İlgili dosyalar
- (yok — ortam)
