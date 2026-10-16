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

## Uygulama sınırları (MVP — Aşama 1)

- **Code Studio**: yalnızca proje açma + dosya ağacı + düzenleyici +
  kaydetme çalışır. Kod üretme, diff ile onaylı uygulama, test çalıştırma,
  görev listesi, geri alma AŞAMA 2.
- **Markdown render**: mesajlar düz metin (QPlainTextEdit) gösterilir;
  zengin Markdown/kod vurgulama Aşama 2'de.
- **Muhakeme akışı**: glm-5.3 `reasoning` içeriği akış sırasında
  GÖSTERİLMEZ (yalnızca kaydedilir) — arayüz kalabalığını önlemek için.
- **Sohbet başlığı**: ilk mesajdan otomatik türetilir.
- **Duyurular**: platform duyuru API'si giriş gerektirir → izlenen sayfa
  genel ana sayfadır; SPA olduğundan içerik değişikliği sınırlı algılanır
  (başlık/meta/gövde metni + sayfa erişilebilirliği izlenir). Ayarlardan
  farklı URL seçilebilir.
- **Paketleme**: EXE kurulumu yok (Aşama 4); `run.bat` ile kaynak koddan
  çalışır.
- **Onaylı komut çalıştırma**: MVP'de komut çalıştırma YOKTUR; bu bir
  güvenlik tercihidir. Aşama 2'de kullanıcı onaylı, proje diziniyle
  sınırlı tasarımla eklenecek.
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
