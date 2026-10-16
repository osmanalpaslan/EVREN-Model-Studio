# Bilinen Sınırlamalar

> Tamamlanmamış/doğrulanmamış özellikler DÜRÜSTÇE listelenir. "Aşama 2/3/4"
> etiketi planlanan çalışmayı gösterir; şimdi çalışmadığı anlamına gelir.

## Doğrulanmamış API yetenekleri

- Görsel girdi, OCR, ASR, embedding, rerank, guard, systemone uçları gerçek
  istekle test EDİLMEDİ (şema incelemesi yapıldı) → uygulama arayüzünde
  yokturlar; Aşama 3.
- Araç çağrısı: 2026-10-16'da 8 sohbet modelinde okuma turuyla DOĞRULANDI
  (MODEL_CAPABILITIES.md). Komut çalıştırma ve uzun çok adımlı görevler gerçek
  modellerle ayrıca denenmedi.
- `response_format` (yapılandırılmış çıktı): test EDİLMEDİ.
- Akış yanıtındaki `chatcmpl-...` kimliğinin `/v1/requests/{id}` ile
  eşleşmesi garanti DEĞİL; belirsizlik durumunda akışsız istek kimlikleri
  tercih edilir.

## Uygulama sınırları (Aşama 2)

- **Kod ajanı gerçek EVREN ile kısmen doğrulandı** (2026-10-16): okuma
  araçları 8 modelde, onaylı dosya düzenleme + geri alma deepseek-v4-flash
  ile gerçek arayüzde. Komut çalıştırma ve uzun görevler gerçek modelle
  denenmedi.
- **Otomatik mod yalnız kurallarla karar verir**: Claude Code'daki gibi bir
  yapay zekâ denetçisi yoktur; "kullanıcının isteğini aşan" eylemi ayırt
  edemez. Güvenli listedeki test/derleme komutları projenin kodunu çalıştırır.
  Tanınmayan her komut sorulur (Otomatik mod bu yüzden Claude Code'dan sık sorar).
- **Süre göstergesi**: her model çağrısının süresi kaydedilir; "tur toplamı"
  yalnızca kayıtlı adım sürelerinin toplamıdır (araç ve onay bekleme süresi
  canlı sayaçta görünür, kalıcı toplamda yoktur).
- **Bağlam yönetimi**: token sayımı tahminidir (≈3,5 karakter/token).
  Otomatik özet: yeni mesajdan önce, bağlam min(%75, 100k token) eşiğini
  aşınca; uzun görevde yalnız güvenli noktada (araç sonuçlarından sonra)
  min(%90, eşik×1,5) aşılınca özetleyip otomatik devam (mesaj başına en
  fazla 3 kez). Özet bir modeldir: ayrıntılar kaybolabilir; ajan dosyayı
  gerekirse yeniden okur. Bağlamın %70'i aşılınca eski araç çıktıları
  ayrıca kısaltılarak gönderilir. Elle: `/compact [odak]`.
- **Komutlar**: etkileşimli (girdi bekleyen) komutlar desteklenmez
  (stdin kapalı); uzun süren sunucular zaman aşımında sonlandırılır.
- **Geri alma**: yalnızca ajanın araçlarla yaptığı değişiklikler kaydedilir;
  ajanın çalıştırdığı komutların (örn. `git checkout`, formatlayıcı)
  dosyalarda yaptığı değişiklikler geri alınamaz.
- **Git**: yalnızca dal adı gösterilir; durum/diff/commit arayüzü yok.
- **Tema değişikliği**: bazı bileşenler renklerini oluşturulurken alır;
  tema değişikliği tam olarak uygulamanın yeniden başlatılmasıyla uygulanır.
- **Görsel ekleme**: yazma kutusundan görsel/ekran görüntüsü gönderme yok
  (Aşama 3).
- **Sohbet başlığı**: ilk mesajdan otomatik türetilir; sonradan
  değiştirilebilir.
- **Duyurular**: platform duyuru API'si giriş gerektirir → izlenen sayfa
  genel ana sayfadır; SPA olduğundan içerik değişikliği sınırlı algılanır
  (başlık/meta/gövde metni + sayfa erişilebilirliği izlenir). Ayarlardan
  farklı URL seçilebilir.
- **Paketleme**: EXE kurulumu yok (Aşama 4); `run.bat` ile kaynak koddan
  çalışır.
- **Yerel ay yedekleme**: yok; veriler `%LOCALAPPDATA%` altındadır,
  Ayarlar'dan JSON dışa aktarılabilir.

## Ücretli sağlayıcılar (OpenAI, Anthropic)

- Gerçek anahtarla **doğrulanmadı**; yalnızca belgelere göre yazıldı ve sahte
  HTTP testleriyle sınandı.
- Harcama **tahminidir**: uzun bağlam fiyat kademeleri (OpenAI >272K, bazı
  Claude modelleri) ve önbelleğe yazma ücreti hesaba katılmaz; fiyatlar
  2026-10-16 tarihlidir.
- Kalan kredi API'den okunamaz; Kullanım/Kota ve EVREN Durum İzleme
  ekranları yalnız EVREN içindir.
- "Sonuç belirsiz" durumunda istek durumu sorgulanamaz (EVREN'e özgü uç).
- OpenAI'de reasoning özeti yalnız model gönderirse görünür; Anthropic
  "extended thinking" ayrıca açılmaz (modelin varsayılanı).

## Sağlayıcıya bağlı sınırlar

- `free_until: 2026-11-01` — sonrası için fiyatlandırma bilinmiyor.
- Kota: 5 dk pencere + günlük 15M token; `level` alanı canlı görünür.
- `auto` yönlendiricinin kural kümesi belgelenmemiş; davranış değişebilir.

## Ortam notları

- PowerShell 5.1 konsolunda Türkçe karakterler bozuk GÖRÜNEBİLİR; bu
  yalnızca konsol kod sayfası sorunudur, veri UTF-8'dir.
- keyring/Windows Credential Manager servisi kapalıysa anahtar kaydı
  AÇIKÇA başarısız olur; düz metne sessiz geçiş YAPILMAZ.
