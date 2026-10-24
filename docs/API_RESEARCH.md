# EVREN API Araştırma Günlüğü

> Araştırma tarihi: 2026-10-15 (UTC). Yöntem: resmî kaynak öncelikli,
> her iddia gerçek istekle doğrulandıysa "✅ doğrulandı", yalnızca
> okunduysa "⬜ şema/incelendi" olarak işaretlenir.

## Kaynaklar

| Kaynak | Tür | Bağlantı |
|---|---|---|
| EVREN LLM API OpenAPI 3.1 şeması | BİRİNCİL, resmî | https://evren-llmapi.ssyz.org.tr/openapi.json |
| EVREN LLM API Swagger UI | BİRİNCİL, resmî | https://evren-llmapi.ssyz.org.tr/docs |
| EVREN platform ana sayfası | BİRİNCİL | https://evren.ssyz.org.tr/ |
| Site CSP + JS paketi (API rotaları) | BİRİNCİL (istemci kodu) | /assets/index-CQe6Xsvs.js |
| robots.txt / sitemap.xml | BİRİNCİL | https://evren.ssyz.org.tr/robots.txt |
| Platform duyuru API'si | BİRİNCİL | https://api.ssyz.org.tr/api/v1/announcements/active |
| Gerçek API yanıt örnekleri | DOĞRULAMA | bu belge + EVREN_STATUS_HISTORY.md |

Topluluk/GitHub örnekleri KULLANILMADI; resmî belgeler yeterliydi.

## Doğrulanmış bulgular

1. ✅ API kimlik doğrulama: `Authorization: Bearer <anahtar>`; hatalı
   anahtar → 401.
2. ✅ `GET /healthz` ve `GET /readyz` kimlik gerektirmez; maliyetsiz
   sağlık kontrolü olarak izleme ajanında kullanılır.
3. ✅ `GET /v1/models`: 16 model; görev (task), modalite, bağlam uzunluğu,
   yetenek bayrakları (tools/vision/response_format/...), fiyat ve
   `free_until` içerir.
4. ✅ `POST /v1/chat/completions`: OpenAI sözleşmesi + `stream` SSE akışı
   (`delta.reasoning` + `delta.content`, `data: [DONE]`); ekstra
   parametreler geçer (şema notu); `usage.evren` uzantısı (routed_model,
   kredi bilgileri).
5. ✅ `GET /v1/quota`: 5 dk kayan pencere + günlük + CR kredi; `level`
   ok/warn/critical.
6. ✅ `GET /v1/requests/{uuid}`: execution_terminal/charge_terminal —
   belirsiz sonuç kurtarma ucudur.
7. ✅ `GET /v1/terms/status`: sürüm 1, kabul edilmiş.
8. ✅ Geçersiz model → 404; boş hata gövdesi olabilir.
9. ✅ `auto` bir yönlendiricidir (gerçek istekte qwen3.8-flash-next'e
   gitti); ayrı uzman model değildir.
10. ✅ glm-5.3 muhakeme modeli: düşük max_tokens'ta `content: null` +
    `finish_reason: length` (hata değil, davranış).

## Bilinmeyen / doğrulanmayan

- ⬜ Görsel, OCR, ASR, embedding, rerank, guard, systemone uçlarının
  gerçek davranışları (şema okundu, istek gönderilmedi).
- ⬜ Araç çağrısı (tools) gerçek tur davranışı.
- ⬜ `Retry-After` başlığının gerçek 429/503 yanıtlarında döndüğüne dair
  gözlem (503 henüz yaşanmadı; mantık testlerle doğrulandı).
- ⬜ 2027-01-01 sonrası fiyatlandırma (ücretsizlik 2026-10-24'te 2026-11-01'den uzatıldı).
- ⬜ `/v1/responses` ve `/v1/messages` (Anthropic) akış protokolleri.
- ⬜ Platform duyurularının API dışı genel erişimli bir yansıması var mı
  (sitemap'e göre YOK).

## Duyuru sayfası kararı

`announcements/active` ucu 401 (platform girişi; kimlik sağlayıcı
kimlik.ssb.gov.tr) → masaüstü uygulaması okuyamaz. SPA gövdesi sunucuda
render edilmez. Karar: varsayılan izlenen sayfa `https://evren.ssyz.org.tr/`
(genel ana sayfa: başlık/meta/görünür metin izlenir), kullanıcı Ayarlar'dan
değiştirebilir; hiçbir URL UYDURULMADI.

## Model listesi (canlı, 2026-10-15)

Ayrıntılar: docs/knowledge/MODEL_CAPABILITIES.md (16 model, tüm görev
türleri, yetenek matrisi).
