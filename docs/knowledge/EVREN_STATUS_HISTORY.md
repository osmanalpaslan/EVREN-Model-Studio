# EVREN Durum Geçmişi

> İzleme ajanı ve elle yapılan kontrollerin kaydı. Her giriş: zaman,
> gözlem, kaynak. Sağlayıcı kaynaklı olaylar burada izlenir.

## 2026-10-16 (bakım sonrası kontrol — gerçek testler)

| Saat (UTC) | Gözlem | Kaynak |
|---|---|---|
| 06:36 | `/healthz` → `ok`, `/readyz` → `ready` — servis ayakta | doğrudan HTTP |
| 06:36 | Ana sayfa erişilebilir; başlık/meta DEĞİŞMEDİ; JS paketi değişmiş (`index-CQe6Xsvs.js` → `index-6xb-jL0t.js`) → bakım sonrası yeni dağıtım yapılmış | sitemap + HTML |
| 06:36 | Sitemap lastmod değerleri hâlâ 2026-10-15 | sitemap.xml |
| 06:37 | 16 model listelendi (dünkü listeyle aynı); kota `ok`, kalan 1020 CR | gerçek anahtarla |
| 06:37 | Duyuru API'si hâlâ 401 (giriş gerekiyor; değişiklik yok) | doğrudan HTTP |
| 06:38 | **glm-5.3 sohbet: 200 OK, 3,4 sn, finish=stop, içerik döndü, istek durumu `success`** — "sağlıklı endpoint yok" sorunu YOK | uygulama istemcisiyle |
| 06:38 | glm-5.3 akış: 8 parça SSE, 3,7 sn, finish=stop — akış da sağlıklı | uygulama istemcisiyle |

**Sonuç (2026-10-16): Bakım bitmiş görünüyor.** API hazır, model listesi ve
kota normal, glm-5.3 hem akışsız hem akışlı isteklere başarılı yanıt veriyor.
Uygulama `model_health` tablosu güncellendi (glm-5.3 sağlıklı, ~3,7 sn).

> Not: Duyuru metnine platform girişi gerektiğinden doğrudan erişilemedi;
> "bakım bitti" yargısı API'nin KANITLANMIŞ sağlıklı durumuna dayanır
> (duyuru okuma tahmini değildir, test sonucudur).

## 2026-10-15 (Aşama 0 araştırması — gerçek testler)

| Saat (UTC) | Gözlem | Kaynak |
|---|---|---|
| 20:12 | `/healthz` → `ok`, `/readyz` → `ready` | doğrudan HTTP |
| 20:13 | `/v1/models` 401 (anahtar gerekiyor — uç nokta ayakta) | doğrudan HTTP |
| 20:30 | 16 model listelendi; tümü `free_until: 2026-11-01` | gerçek anahtarla |
| 20:31 | kota: `level=ok`, kalan 1010 CR, günlük 327k/15M | GET /v1/quota |
| 20:36 | glm-5.3 sohbet 200 OK (muhakeme modeli davranışı doğrulandı) | gerçek istek |
| 20:38 | glm-5.3 akış 200 OK, 194 SSE satırı, [DONE] | gerçek istek |
| 20:39 | geçersiz model → 404 | gerçek istek |
| 20:39 | `/v1/requests/{id}` → `execution_terminal: success` | gerçek istek |
| 20:40 | auto → qwen/qwen3.8-flash-next yönlendirmesi | gerçek istek |
| 20:41 | hatalı anahtar → 401 | gerçek istek |
| 20:57 | duyuru API'si `/api/v1/announcements/active` → 401 (giriş gerekli) | doğrudan HTTP |
| 21:50 | e2e: 16 model, kota ok/1020 CR, sohbet+akış başarılı, istek durumu success | uygulama koduyla |

**Sağlayıcı olayı (503/bakım) gözlemlenmedi** — 2026-10-15'e kadar.
Kullanıcının bildirdiği `'glm-5.3' için sağlıklı endpoint yok` örneği
için kurtarma kuralları kurumsallaştırıldı (ERROR_CATALOG.md #1).

> Bu dosya, izleme ajanı raporları SQLite'ta saklandığından yalnızca önemli
> dönüm noktalarıyla güncellenir. Ajanın tüm kontrol kayıtları
> `monitor_checks` tablosundadır.
