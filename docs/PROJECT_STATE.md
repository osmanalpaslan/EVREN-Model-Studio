# Proje Durumu

> Oturum kesilirse çalışmaya bu dosyadan devam edilir.
> Son güncelleme: 2026-10-15 (Aşama 1 sonu)

## Konum ve sınırlar

- Proje: `C:\Projects\AI-Atolye\EVREN-Model-Studio`
- Uzak depo: https://github.com/osmanalpaslan/EVREN-Model-Studio (ÖZEL,
  `origin/master`; 2026-10-16'da oluşturuldu ve push edildi)
- Bağımsız Git deposu ✅, Python 3.12.10 venv (`.venv`) ✅
- Alpnex/DepoWise'a DOKUNULMADI. Tüm işlemler proje klasörü içinde.
- Veriler: `%LOCALAPPDATA%\EVREN-Model-Studio\` (config.json + evren.db).
  API anahtarı Windows Credential Manager'da (`EVREN-Model-Studio`).

## Aşama durumu

| Aşama | Durum |
|---|---|
| 0 — Araştırma | ✅ TAMAMLANDI (docs/knowledge/* ve docs/API_RESEARCH.md) |
| 1 — Çalışan MVP | ✅ TAMAMLANDI (aşağıdaki liste) |
| 2 — Code Studio (AI özellikleri) | ⬜ BAŞLAMADI — yalnızca temel dosya düzenleyici çalışır |
| 3 — Özel görev modelleri | ⬜ BAŞLAMADI |
| 4 — Paketleme | ⬜ BAŞLAMADI |

## Aşama 1'de GERÇEKTEN çalışan ve test edilenler

- Türkçe PySide6 arayüzü: 11 sayfa (ana sayfa, chat, code studio temeli,
  modeller, bağlantı testi, kota, sohbetler, hata merkezi, durum izleme,
  ayarlar, yardım). UI duman testi: SMOKE_OK.
- API anahtarı Windows Credential Manager'da; maskeli gösterim; silme.
- Model listesi (16 model), yetenek tablosu, kota görünümü, şart durumu.
- Chat: akışlı yanıt (SSE), iptal, model seçimi, yerel kayıt, dışa aktarma.
- Hata merkezi: sınıflandırma, kalıcı kayıt, imza ile geçmiş arama,
  Türkçe kurtarma önerileri.
- EVREN Durum İzleme Ajanı: kullanıcı başlatmalı 30 dk / 5 dk kontrol,
  içerik değişikliği tespiti, sağlık uçları, isteğe bağlı gerçek model
  testi, Türkçe rapor, yarım kalan izlemeye devam seçeneği.
- 503/429/belirsiz sonuç kurtarma kuralları kodda + testlerde.
- Birim testler: 53/53 GEÇTİ. Uçtan uca gerçek API testi: E2E_OK.

## Sıradaki iş (Aşama 2 başlangıcı)

1. Code Studio: AI kod üretimi için sohbet entegrasyonu (onay akışıyla).
2. Diff görünümü + onaylı dosya uygulama (QTextDocument diff veya difflib).
3. Görev listesi (SQLite tasks tablosu) + kaldığı yerden devam.
4. Komut çalıştırma: proje diziniyle sınırlı, açık kullanıcı onaylı.
5. Markdown/kod vurgulu mesaj gösterimi.
6. İlk gerçek 503 gözlemlendiğinde: ERROR_CATALOG.md #1 kaydını doldur.

## Ortam notları

- Python: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` (PATH'te yok;
  run.bat venv'i doğrudan kullanır).
- Test: `.\.venv\Scripts\python.exe -m pytest -q`
- Çalıştırma: `run.bat` veya `.\.venv\Scripts\python.exe -m evren_studio`
