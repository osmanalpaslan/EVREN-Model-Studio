# Bilinen Sınırlamalar

> Tamamlanmamış/doğrulanmamış özellikler DÜRÜSTÇE listelenir. "Aşama 2/3/4"
> etiketi planlanan çalışmayı gösterir; şimdi çalışmadığı anlamına gelir.

## Doğrulanmamış API yetenekleri

- Görsel girdi, OCR, ASR, embedding, rerank, guard, systemone uçları gerçek
  istekle test EDİLMEDİ (şema incelemesi yapıldı) → uygulama arayüzünde
  yokturlar; Aşama 3.
- Araç çağrısı (function calling): model kayıt defterinde bayrak var
  (glm-5.3, deepseek-*, mimo, qwen3.8, gemma, qwen3-vl) ama gerçek tur
  test EDİLMEDİ → Code Studio otonom ajanı bu nedenle Aşama 2'de.
- `response_format` (yapılandırılmış çıktı): test EDİLMEDİ.
- Akış yanıtındaki `chatcmpl-...` kimliğinin `/v1/requests/{id}` ile
  eşleşmesi garanti DEĞİL; belirsizlik durumunda akışsız istek kimlikleri
  tercih edilir.

## Uygulama sınırları (Aşama 2)

- **Kod ajanı gerçek EVREN ile DOĞRULANMADI**: ajan döngüsü, araçlar ve
  arayüz sahte model istemcisiyle test edildi. EVREN'in `tools` parametresini
  gerçekten kabul edip `tool_calls` döndürdüğü bilinmiyor. Reddederse
  (400/422) uygulama metin protokolüne geçer; model metin protokolüne
  uymazsa araçlar çalışmaz (yanıt düz metin kalır).
- **Bağlam yönetimi**: token sayımı tahminidir (≈3,5 karakter/token).
  Bağlamın %70'i aşılınca eski araç çıktıları modele kısaltılmış gönderilir;
  tam özet için `/ozet` elle çalıştırılır (otomatik özetleme yok).
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

## Sağlayıcıya bağlı sınırlar

- `free_until: 2026-11-01` — sonrası için fiyatlandırma bilinmiyor.
- Kota: 5 dk pencere + günlük 15M token; `level` alanı canlı görünür.
- `auto` yönlendiricinin kural kümesi belgelenmemiş; davranış değişebilir.

## Ortam notları

- PowerShell 5.1 konsolunda Türkçe karakterler bozuk GÖRÜNEBİLİR; bu
  yalnızca konsol kod sayfası sorunudur, veri UTF-8'dir.
- keyring/Windows Credential Manager servisi kapalıysa anahtar kaydı
  AÇIKÇA başarısız olur; düz metne sessiz geçiş YAPILMAZ.
