# EVREN API Uyumluluk Kaydı

> Kaynak: `https://evren-llmapi.ssyz.org.tr/openapi.json` (resmî OpenAPI 3.1 şeması)
> Son doğrulama: 2026-10-15 — gerçek isteklerle test edildi.

## Doğrulanmış uç noktalar

| Uç nokta | Yöntem | Kimlik | Durum | Not |
|---|---|---|---|---|
| `/healthz` | GET | Gerekmez | ✅ Test edildi | `{"status":"ok"}` — liveness; maliyetsiz |
| `/readyz` | GET | Gerekmez | ✅ Test edildi | `{"status":"ready"}` — readiness |
| `/v1/models` | GET | Bearer | ✅ Test edildi | 16 model; yetenek/fiyat içerir |
| `/v1/chat/completions` | POST | Bearer | ✅ Test edildi | OpenAI uyumlu; `stream` SSE; `evren_tools` uzantısı; **`tools`/`tool_calls` 8 sohbet modelinde doğrulandı (2026-10-16, bkz. MODEL_CAPABILITIES)** |
| `/v1/quota` | GET | Bearer | ✅ Test edildi | 5 dk pencere + günlük + CR kredi |
| `/v1/requests/{id}` | GET | Bearer | ✅ Test edildi | `execution_terminal`, `charge_terminal` |
| `/v1/terms/status` | GET | Bearer | ✅ Test edildi | Sürüm 1, kabul edilmiş |
| `/v1/terms/text` | GET | Bearer | ⬜ Şema doğrulandı | Uygulamada kullanılmıyor (kabul zaten yapılmış) |
| `/v1/terms/accept` | POST | Bearer | ⬜ Şema doğrulandı | Kullanıcı adına asla otomatik çağrılmaz |
| `/v1/embeddings` | POST | Bearer | ⬜ Şema doğrulandı | qwen3-embedding-8b (yetenek kaydı) |
| `/v1/rerank` | POST | Bearer | ⬜ Şema doğrulandı | qwen3-reranker-8b (yetenek kaydı) |
| `/v1/ocr` | POST | Bearer | ⬜ Şema doğrulandı | dots-ocr, deepseek-ocr-2 |
| `/v1/audio/transcriptions` | POST | Bearer | ⬜ Şema doğrulandı | qwen3-asr-1.7b |
| `/v1/responses` | POST | Bearer | ⬜ Şema doğrulandı | Codex tarzı; akış protokolü farklı ([DONE] yok) |
| `/v1/messages` | POST | Bearer | ⬜ Şema doğrulandı | Anthropic uyumlu |
| `/v1/systemone` | POST | Bearer | ⬜ Şema doğrulandı | Karar modelleri (clef, laya) |
| `/v1/media*` | POST/GET | Bearer | ⬜ Şema doğrulandı | Medya yükleme akışı |

⬜ = yalnızca şema incelendi, gerçek istekle test EDİLMEDİ. Bu uçları
kullanmadan önce canlı test yapılmalıdır.

## Kimlik doğrulama

- `Authorization: Bearer <anahtar>` başlığı.
- Hatalı anahtar → `401` (gövde boş dönebilir).
- Şart kabulü: `/v1/terms/status` → `accepted: true` değilse sohbet çağrıları
  engellenebilir. Mevcut anahtar için kabul zaten yapılmış (2026-10-15).

## Yanıt biçimi ayrıntıları (gerçek testlerden)

- Sohbet yanıtı `usage.evren` uzantısı içerir: `routed_model`,
  `credits_held_cr`, `credits_remaining_cr`, `reasoning_budget_exhausted`.
- Muhakeme modelleri (glm-5.3): `message.reasoning` ayrı alandır; `content`
  yalnızca muhakeme bütçesi bittikten sonra dolar. Düşük `max_tokens` →
  `finish_reason: "length"` + boş içerik.
- Akış: `text/event-stream`; parçalar `delta.reasoning` ve `delta.content`;
  sonlandırma `data: [DONE]`.
- `auto` modeli yönlendiricidir: `qwen/qwen3.8-flash-next`'e yönlendirdiği
  gerçek istekte görüldü.
- Geçersiz model → `404`.
- İstek kimliği: akışsız yanıtta `id` alanı UUID'dir ve `/v1/requests/{id}`
  sorgusunda kullanılabilir; akıştaki `chatcmpl-...` kimliği bu sorgu için
  garanti DEĞİLDİR.

## Hata başlıkları

- `Retry-After`: 429/503 yanıtlarında saniye cinsinden (sayısal) beklenebilir.
  Uygulama ≤300 sn ise uyar, değilse kullanıcıya bırakır.
- Kota bilgisi `GET /v1/quota` üzerinden: `level` = ok/warn/critical,
  `remaining_cr`, `daily_*` alanları.

## Duyuru sayfası

- Platform duyuru API'si: `https://api.ssyz.org.tr/api/v1/announcements/active`
  — **401, platform girişi (kimlik.ssb.gov.tr) gerektirir** (2026-10-15
  doğrulandı). Masaüstü uygulaması bu uca erişemez.
- Genel erişilebilir sayfalar (sitemap): `/`, `/explore`, `/pricing`,
  `/llm-inference`, `/infrastructure` — SPA; sunucu tarafında duyuru metni
  render EDİLMEZ.
- Uygulamanın varsayılan izlenen sayfası: `https://evren.ssyz.org.tr/`
  (ana sayfa). Kullanıcı Ayarlar'dan farklı URL seçebilir.
- Web arayüzünün duyuruları 5 dakikada bir yenilediği JS paketinden
  doğrulandı (refetchInterval=5*6e4) — uygulamanın 5 dk kontrol aralığı
  bununla uyumludur.

## Ücretsizlik

- Tüm modellerin kayıt defterinde `free_until: 2026-11-01` ve fiyat 0.0 CR
  (2026-10-15 snapshot). Ücretsiz erişimin kalıcı olduğu VARSAYILMAZ;
  `free_until` ve fiyat alanları değişebilir, Model sayfası canlı gösterir.
