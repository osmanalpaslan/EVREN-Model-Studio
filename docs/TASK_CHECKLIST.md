# Görev Denetim Listesi

> Yalnızca GERÇEKTEN uygulanmış ve test edilmiş maddeler işaretlenir.

## Aşama 0 — Araştırma ✅

- [x] Windows/PowerShell/Python/Git ortam incelendi (PS 5.1, Win11 26200)
- [x] EVREN OpenAPI şeması birincil kaynak alındı
- [x] healthz/readyz/models/quota/terms/istek-durumu uçları gerçek istekle doğrulandı
- [x] Duyuru sayfası araştırıldı: API 401 gerektiriyor; genel sayfa izlenir
- [x] 16 model canlı listesi + yetenek kayıtları tutuldu
- [x] Riskler ve doğrulanmayanlar kaydedildi (KNOWN_LIMITATIONS)

## Aşama 1 — Çalışan MVP ✅

- [x] Türkçe masaüstü arayüzü (PySide6, 11 sayfa) — SMOKE_OK
- [x] Güvenli API anahtarı yönetimi (Credential Manager, maskeleme)
- [x] Anahtarın loglara/config'e yazılmadığı testlerle doğrulandı
- [x] Bağlantı testi sayfası (healthz+readyz+models+quota+terms)
- [x] Model listesi + yetenek tablosu
- [x] Doğrulanmış modellerle Chat (glm-5.3, auto e2e'de 200 OK)
- [x] Akışlı yanıt (SSE) — e2e'de 17 parça doğrulandı
- [x] Kullanıcı iptali (gönderim öncesi + akış sırasında) — testli
- [x] Sohbet geçmişi (SQLite), arama, adlandırma, dışa aktarma, silme
- [x] Hata merkezi + kalıcı hata kurtarma belgeleri
- [x] EVREN Durum İzleme Ajanı (30dk/5dk, 7 kontrol planı, rapor)
- [x] 503/429/Retry-After/belirsiz sonuç yönetimi — testli
- [x] Otomatik model geçişi varsayılan KAPALI — testli
- [x] Kota sayfası (yalnız API sağladığı için)
- [x] Birim testleri: 53/53 geçti; e2e gerçek test E2E_OK
- [x] Duyuru sayfası erişilemediğinde güvenli davranış — testli
- [x] İzleme kapanıp devam seçeneği — testli
- [x] Ağ kesintisi sonrası yeniden açılma (yerel veriler korunur) — testli

## Aşama 2 — Kod ajanı çalışma alanı 🟨

- [x] Oturum tabanlı yeni arayüz (sol menü, akış, yazma kutusu, sağ panel) — SMOKE_OK + ekran görüntüleri
- [x] Koyu/açık tema, simge seti, Markdown + sözdizimi renklendirme
- [x] Dosya ağacı + önizleme + elle düzenleme/kaydetme (Dosyalar sekmesi)
- [x] Ajan araçları (oku/ara/bul/yaz/düzenle/komut/görev) — testli
- [x] Diff gösterimi + onayla dosyaya uygula — testli (arayüz uçtan uca dahil)
- [x] Geri alma (tekil/toplu, çakışma kontrolü) — testli
- [x] Onaylı ve proje diziniyle sınırlı komut çalıştırma — testli
- [x] Onaysız komut çalıştırmanın engellenmesi — testli
- [x] Görev listesi + kaldığı yerden devam (oturumlar kalıcı) — testli
- [x] Plan / Onaylı / Otomatik düzenleme modları — testli
- [x] Mesajı düzenleyip yeniden gönderme, /komutlar, @dosya ekleme
- [x] Uzun konuşma özetleme (/ozet) ve bağlam kısaltma — kısaltma testli
- [ ] **Gerçek EVREN ile yerel araç çağrısı turu** (anahtar gerekir)
- [ ] Git durumu/diff görünümü ve commit önerisi
- [ ] Değişiklik gerekçesi: ajan istemiyle isteniyor; ayrı arayüz yok

## Aşama 3 — Özel görev modelleri ⬜

- [ ] Görsel anlama (qwen3-vl-30b gerçek testi)
- [ ] OCR (dots-ocr, deepseek-ocr-2 gerçek testi)
- [ ] ASR (qwen3-asr-1.7b gerçek testi)
- [ ] Embedding/rerank gerçek testleri
- [ ] Guard sınıflandırma gerçek testi
- [ ] Araç çağrısı (function calling) gerçek testi (kod ajanı hazır; bkz. Aşama 2)

## Aşama 4 — Paketleme ⬜

- [ ] Windows EXE (PyInstaller) ve kolay başlatma
- [ ] Kurulum rehberi ve yedekleme
- [ ] Güvenlik incelemesi (secret taraması)
- [ ] Son test raporu

## Sürekli

- [ ] İlk gerçek 503 gözlemi → ERROR_CATALOG kaydı
- [ ] free_until 2026-11-01 yaklaşınca fiyatlandırma kontrolü
