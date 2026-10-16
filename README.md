# EVREN Model Studio

EVREN LLM API'si için Türkçe Windows masaüstü uygulaması: sohbet, model
incelemesi, kota takibi, hata kurtarma merkezi ve 30 dakikalık durum izleme
ajanı.

## Hızlı başlangıç

1. `run.bat` dosyasını çalıştırın (kurulum için bkz. docs/INSTALLATION.md).
2. Ayarlar > API Anahtarı'na EVREN anahtarınızı girin (Windows Credential
   Manager'da güvenle saklanır, ekranda maskeli kalır).
3. API Bağlantı Testi ile doğrulayın, sonra Chat sayfasında sohbet edin.

## Özellikler (Aşama 1 MVP — hepsi test edildi)

- **Chat**: akışlı yanıtlar (SSE), iptal, model seçimi, yerel geçmiş,
  arama, dışa aktarma; glm-5.3 dahil doğrulanmış modeller.
- **Modeller**: canlı liste, görev türü, yetenek bayrakları, ücretsizlik
  bitişi, son test ve sağlık durumu.
- **Kota**: 5 dakikalık pencere + günlük kullanım + CR kredi.
- **Hata Merkezi**: her hata sınıflandırılır, imzayla saklanır, geçmiş
  çözümler aranır, Türkçe öneriler sunulur.
- **Durum İzleme Ajanı**: kullanıcı başlatmalı 30 dk izleme (5 dk
  aralıkla; başlangıç dahil 7 kontrol), duyuru sayfası değişiklik tespiti,
  maliyetsiz sağlık uçları, isteğe bağlı gerçek model testi, kesin/tahmin
  ayrımlı Türkçe rapor; yarım kalan izlemeye devam seçeneği.
- **Güvenlik**: anahtar yalnız Credential Manager'da; HTTPS zorunlu;
  telemetri yok; veriler `%LOCALAPPDATA%` altında.
- **Kurtarma kuralları**: 503 'sağlıklı endpoint yok' sağlayıcı kaynaklı
  sayılır (en fazla 3 otomatik tekrar, Retry-After'a uyum); belirsiz
  sonuçta otomatik tekrar YOK — `/v1/requests/{id}` sorgulanır.

## Belgeler

- Kurulum: docs/INSTALLATION.md
- Proje durumu: docs/PROJECT_STATE.md | Görev listesi: docs/TASK_CHECKLIST.md
- Kararlar: docs/DECISIONS.md | Değişiklikler: docs/CHANGELOG.md
- Bilgi tabanı: docs/knowledge/ (API uyumluluğu, model yetenekleri, hata
  kataloğu, kurtarma rehberi, sınırlamalar, dersler, durum geçmişi)
- Güvenlik: docs/SECURITY.md

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q              # 53 birim testi
.\.venv\Scripts\python.exe tests\smoke_ui.py         # arayüz dumanı
.\.venv\Scripts\python.exe -u tests\e2e_real_api.py  # gerçek API (anahtar gerekir)
```

## Durum

Aşama 1 (MVP) tamamlandı. Code Studio AI özellikleri Aşama 2'de; özel
görev modelleri (görsel/OCR/ASR/...) Aşama 3'te; Windows paketleme Aşama
4'te. Ayrıntılı ve dürüst durum: docs/TASK_CHECKLIST.md.

## Lisans

MIT — bkz. [LICENSE](LICENSE). Bağımlılıklar: PySide6 (LGPLv3), httpx
(BSD), keyring (MIT).

