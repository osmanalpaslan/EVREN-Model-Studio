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
| 15 | Mesajlar QPlainTextEdit (Markdown yok) | MVP sadeliği; hata yüzeyini küçültür; Aşama 2'de zenginleştirilir | 2026-10-15 |
| 16 | Komut çalıştırma MVP'de YOK | Güvenlik: onaylı ve sınırlı tasarım Aşama 2'de | 2026-10-15 |
| 17 | SQLite check_same_thread=False + RLock | İzleme ajanı ayrı iş parçacığında (ders #5) | 2026-10-15 |
| 18 | Ücretsiz/yerel araçlar dışında sağlayıcı YOK | Kullanım güvenliği; tüm istekler yalnız EVREN'e | 2026-10-15 |

## Değerlendirilip reddedilenler

- **PyInstaller paketleme (şimdi)**: Aşama 4'e bırakıldı; önce çalışan temel.
- **asyncio/qasync**: iki olay döngüsü karmaşıklığı; kazanım yok.
- **requests**: SSE akışı ve MockTransport'ta httpx daha iyi.
- **Düz metin anahtar dosyası**: güvenlik gereği reddedildi (kural).
- **Windows Görev Zamanlayıcı ile izleme**: MVP'de gereksiz sistem servisi;
  kullanıcı başlatmalı uygulama içi zamanlayıcı yeterli.
