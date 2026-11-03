# OpenAI ve Anthropic API Araştırması

> Tarih: 2026-10-16 · Yöntem: yalnızca resmî belgeler (aşağıdaki kaynaklar),
> iki bağımsız araştırma. **Hiçbiri gerçek istekle test EDİLMEDİ** (anahtar yok).
> Fiyatlar ve model adları hızla değişir; kullanmadan önce kaynak sayfadan
> yeniden doğrulayın. "doğrulanamadı" = belgede bulunamadı.

## 1. Özet karşılaştırma

| Konu | EVREN (bugün) | OpenAI | Anthropic (Claude) |
|---|---|---|---|
| Adres | evren-llmapi.ssyz.org.tr/v1 | `https://api.openai.com/v1` | `https://api.anthropic.com/v1` |
| Kimlik | `Authorization: Bearer` | `Authorization: Bearer` | `x-api-key` + `anthropic-version: 2023-06-01` (Bearer da kabul) |
| Sohbet ucu | `/v1/chat/completions` | `/v1/chat/completions` (destekleniyor) ve **`/v1/responses` (önerilen)** | **`/v1/messages`** (kendi biçimi) |
| Bugünkü istemciyle | ✅ | Sohbet ✅; ajan ⚠ (aşağıda) | Yalnızca uyumluluk katmanıyla, üretim için önerilmiyor |
| Araç çağrısı | OpenAI biçimi, 8 modelde doğrulandı | Yeni modellerde Chat Completions + reasoning ile **çalışmıyor**; Responses gerekli | `tool_use` / `tool_result` blokları |
| Model listesi yetenek veriyor mu | ✅ (görev, tools, context) | ❌ (yalnızca id) → statik tablo gerekir | ✅ (`max_input_tokens`, `capabilities`) |
| Kalan kredi uçtan okunur mu | ✅ `/v1/quota` | ❌ (yalnız Admin anahtarı; panelden) | ❌ (yalnız Admin API; panelden) |
| Ücret | Şu an ücretsiz (free_until 2027-01-01; 2026-10-24 canlı) | Ön ödemeli kredi | Ön ödemeli kredi |
| Türkiye | ✅ | ✅ desteklenen ülke | ✅ desteklenen bölge |

## 2. OpenAI

### Hesap ve anahtar
1. platform.openai.com'da hesap aç.
2. Anahtar oluştur: https://platform.openai.com/settings/organization/api-keys
3. Kredi yükle ("Add credits"); ilk ücretli kademe "Build" $5 alımla, $500/ay tavan.
- Anahtarlar proje bazlı; son kullanma ve rotasyon öneriliyor. Biçim `sk-...`
  (önek doğrulaması yapılmamalı).
- "Free" kademe var (izinli coğrafya şartı); kredi bitince 429
  `insufficient_quota` / `credit_balance_exhausted`.
- Asgari tutar ve kredi süresi yalnızca arama özetinden: **kısmen doğrulanamadı**.

### API seçimi — kritik
- "Chat Completions remains supported, Responses is recommended for all new projects."
- **GPT-5.4 ve sonrası: Chat Completions'ta `reasoning_effort` `none` dışındayken
  araç çağrısı yok.** gpt-6-astra ve gpt-6.1-sol Chat Completions'ta function
  calling'i hiç desteklemiyor; gpt-6-luna yalnız `reasoning_effort:none` ile.
  gpt-5.3-codex yalnız Responses.
- Sonuç: düz sohbet bugünkü kodla çalışır; **kod ajanı için Responses API
  istemcisi gerekir** (typed SSE: `response.output_text.delta`,
  `response.function_call_arguments.delta/.done`, `response.output_item.*`,
  `response.completed`, `error`; araç sonucu `function_call_output` + `call_id`;
  reasoning öğeleri geri gönderilmeli).

### Modeller (Standard, $/1M token: girdi / önbellekli girdi / çıktı)

| Rol | Model | Bağlam | Fiyat |
|---|---|---|---|
| Amiral gemisi | gpt-6-astra | 1,05M | 10 / 1,00 / 50 |
| Dengeli | gpt-6.1-sol | 1,05M | 2 / 0,10 / 10 |
| Hızlı / ucuz | gpt-6-luna | 1,05M | 0,10 / 0,01 / 0,50 |
| Diğer | gpt-5.6-terra | 1,05M | 2 / 0,20 / 12 |
| Kodlama | gpt-5.3-codex | 400K | 1,75 / 0,175 / 14 |

272K üzeri girdide fiyat artar; bölgesel uçlarda %10 ek ücret. Hepsi reasoning modeli.

### Parametreler, hatalar, limitler
- `max_tokens` eskidi → `max_completion_tokens`; `developer` rolü öneriliyor;
  kullanım için `stream_options.include_usage`; yeni hesaplarda Chat Completions
  varsayılan olarak saklanıyor (`store:false` ile kapatılır).
- Başlıklar: `x-request-id`, `x-ratelimit-*`, 429/503'te `Retry-After`.
- 401 anahtar, 403 ülke, 429 hız (`rate_limit_error`) veya **kota
  (`insufficient_quota` — tekrar denemek işe yaramaz)**, 503 `server_is_overloaded`.
- Kullanım/maliyet uçları Admin anahtarı ister; panel:
  https://platform.openai.com/settings/organization/usage ,
  https://platform.openai.com/settings/organization/limits
- Veri: API verisi opt-in olmadan eğitimde kullanılmaz; kötüye kullanım
  logları ≤30 gün; ZDR ön onayla.

## 3. Anthropic (Claude)

### Hesap ve anahtar
1. platform.claude.com'da hesap aç.
2. Settings > API keys > Create key (anahtar `sk-ant-` ile başlar, **bir kez** gösterilir).
3. Settings > Billing > Buy credits (USD, kart; kredi 1 yılda düşer; auto-reload var).
- Yeni kullanıcılara "small amount of free credits" (miktar doğrulanamadı).
- **Claude Pro/Max aboneliği API'yi karşılamaz; üçüncü taraf uygulamaların
  abonelik girişiyle istek göndermesine izin verilmez.** Uygulama yalnız
  kullanıcının Console API anahtarıyla çalışmalı. (Max/Team planlarına aylık
  API kredisi verilebiliyor; Console organizasyonu bağlanarak.)
- "Claude Code" bir üründür, API değildir.

### Messages API (kendi biçimi)
- `system` üst düzey alan; `max_tokens` her istekte gönderilmeli; içerik blokları.
- 4.7+ modellerde varsayılan dışı `temperature/top_p/top_k` → 400; 4.6+ modellerde
  son mesaj assistant (prefill) → 400.
- Akış: `message_start` → (`content_block_start` → `content_block_delta`… →
  `content_block_stop`)… → `message_delta` (stop_reason, kümülatif usage) →
  `message_stop`; arada `ping`, akış içinde `error` olayı gelebilir; bilinmeyen
  olaylar yok sayılmalı. Delta türleri: `text_delta`, `input_json_delta`
  (`partial_json` birleştirilip blok kapanınca parse), `thinking_delta`, `signature_delta`.
- Araçlar: `tools:[{name, description, input_schema}]`; yanıt `tool_use{id,name,input}`,
  `stop_reason:"tool_use"`; sonuçlar **tek user mesajında, en başta**
  `tool_result{tool_use_id, content, is_error?}`. Paralel çağrı varsayılan açık.
  Opus 5.5 / Sonnet 5.5 / Fable 5.1 `tool_choice` `any`/`tool` reddeder.
- Düşünme: 5.x'te `budget_tokens` kaldırıldı → `thinking:{type:"adaptive"}` +
  `output_config.effort`; varsayılan açık, metin `display:"summarized"` ile
  görünür; **araç turlarında thinking blokları değiştirilmeden geri gönderilmeli**.

### OpenAI uyumluluk katmanı
- `base_url https://api.anthropic.com/v1/` + Chat Completions: akış ve araçlar
  çalışıyor; thinking içeriği yok, önbellek yok, bazı alanlar yok sayılıyor.
- Belge: "not considered a long-term or production-ready solution" → yalnız deneme için.

### Modeller ($/1M token: girdi / çıktı / önbellek okuma)

| Model | Bağlam / maks. çıktı | Fiyat | Not |
|---|---|---|---|
| claude-fable-5-1 | 1M / 128K | 10 / 50 / 0,25 | en güçlü, yavaş |
| claude-opus-5-5 | 1M / 128K | 4 / 20 / 0,20 | belge: emin değilseniz başlayın; ajan kodlama |
| claude-sonnet-5-5 | 1M / 128K | 2 / 10 / 0,10 | hız-zekâ dengesi |
| claude-haiku-5-5 | 1M / 128K | 0,10 / 0,50 / 0,01 (≤100K) | en hızlı/ucuz |

Yeni tokenizer aynı metinde ~%30 daha fazla token üretir (maliyet tahmininde dikkate alınmalı).

### Hatalar, limitler, veri
- Gövde: `{"type":"error","error":{"type","message"},"request_id"}`; 401, 402
  `billing_error`, 403, 404, 413, 429 `rate_limit_error`, 500, 504, **529 `overloaded_error`**.
  Aylık tavan aşımında 429 + `enforced_spend_limit_reached` ve `retry-after`
  yok → tekrar denenmemeli.
- Başlıklar: `request-id`, `retry-after`, `anthropic-ratelimit-*`.
- Kullanım/maliyet yalnız Admin API (bireysel hesaplarda yok); panel:
  https://platform.claude.com/usage , https://platform.claude.com/cost ,
  https://platform.claude.com/settings/billing
- Veri: varsayılan 30 günde silinir; açık izin olmadan eğitimde kullanılmaz; ZDR satış ekibiyle.

## 4. Uygulama için çıkarımlar

1. Ajan çekirdeği sağlayıcıdan bağımsız (`client.chat(...)`) → her sağlayıcı
   için bu arayüzü uygulayan bir istemci yeterli.
2. OpenAI ajan için Responses istemcisi, Anthropic için Messages istemcisi
   gerekir; uyumluluk yolları yalnız sohbet/deneme için.
3. Ücretli sağlayıcılarda kalan kredi uçtan okunamaz → uygulama `usage`
   alanlarından **yerel maliyet tahmini** tutmalı ve panel bağlantıları vermeli.
4. Anahtar maskeleme `sk-…` / `sk-ant-…` biçimlerini de kapsamalı.
5. EVREN'e özel ekranlar (Kota, İzleme, istek durumu) diğer sağlayıcılarda gizlenmeli.
6. Fiyat/model tabloları statik ve tarihli tutulmalı; sonraki motorlar güncellemeli.

## 5. Uygulama notları (2026-10-16, `feat/saglayicilar`)

- İstemciler: `api/openai_client.py` (POST /v1/responses, `store:false`,
  `include:["reasoning.encrypted_content"]`), `api/anthropic_client.py`
  (POST /v1/messages, `x-api-key`, `anthropic-version: 2023-06-01`,
  `max_tokens` zorunlu, temperature gönderilmez).
- Ajan iç mesajları OpenAI Chat biçiminde kalır; dönüşüm istemcide yapılır.
  Sağlayıcıya özel ham çıktı `ChatResult.provider_state` → mesaj meta'sı →
  `_provider_state` ile bir sonraki istekte aynen geri gider.
- Hata eşleme: 402/billing_error, 429 insufficient_quota ve
  enforced_spend_limit_reached → `QUOTA_EXHAUSTED` (tekrar yok); 529 →
  geçici (tekrar edilebilir).
- Katalog ve fiyatlar: `api/providers.py` (`PRICES_AS_OF`, `verified=False`).
- Doğrulama betiği: `tests/e2e_providers_real_api.py --evet`.

## 6. Web araması sağlayıcıları (2026-11-01, `web_search`, gerçek istekle denendi)

| Sağlayıcı | Anahtar | Kota | Denenen | Not |
|---|---|---|---|---|
| Tavily `POST /search` | `Authorization: Bearer tvly-…` | Researcher (ücretsiz): ayda 1000 kredi; temel arama 1, `advanced` 2 kredi | 200, ~2,5 sn | `include_answer` kısa cevap verir; `time_range=year` + `search_depth=advanced` güncel sürüm sorusunda doğru sonuç getirdi; `topic=news` + `time_range=week` günün haberleri |
| Tavily anahtarsız | `X-Tavily-Access-Mode: keyless` başlığı | hız sınırlı (sayı belgelenmemiş) | 200 | yalnız search/extract |
| Tavily `GET /usage` | Bearer | — | 200 | `account.current_plan`, `plan_usage`, `plan_limit` (kredi harcamaz) |
| DuckDuckGo HTML `POST html.duckduckgo.com/html/` | yok | resmî değil (robot doğrulaması çıkabilir) | 200, ~1 sn, 10 sonuç | reklam satırı `y.js`; bazen adres `/l/?uddg=` ile sarılı |

Hata kodları (Tavily belgesi, denenmedi): 401 geçersiz anahtar, 429 hız sınırı, 432 plan kotası doldu,
433 kullandıkça öde sınırı. Uygulama 401/403/432/433'te anahtarı 1 saat denemez, anahtarsız Tavily'ye, sonra
DuckDuckGo'ya geçer; hiçbiri yoksa ajana "eldeki bilgiyle devam et" denir (agent/websearch.py).
Tavily `extract` dosya indirmez: sayfa metnini çıkarır.

## Kaynaklar

OpenAI: developers.openai.com/api/docs/{pricing, models, models/gpt-6-astra,
models/gpt-6.1-sol, models/gpt-6-luna, models/gpt-5.6-terra, models/gpt-5.3-codex,
guides/migrate-to-responses, guides/reasoning, guides/function-calling, guides/text,
guides/streaming-responses, guides/error-codes, guides/rate-limits,
supported-countries, quickstart, guides/production-best-practices,
guides/admin-apis, guides/your-data}; developers.openai.com/api/reference/{overview,
resources/chat/subresources/completions/streaming-events, resources/models/methods/list};
developers.openai.com/cookbook/examples/completions_usage_api;
help.openai.com/en/articles/8264644 (403, yalnız arama özeti).

Anthropic: platform.claude.com/docs/en/{api/overview, api/beta-headers,
get-api-key, api/supported-regions, build-with-claude/working-with-messages,
build-with-claude/streaming, agents-and-tools/tool-use/define-tools,
agents-and-tools/tool-use/handle-tool-calls, agents-and-tools/tool-use/parallel-tool-use,
cli-sdks-libraries/libraries/openai-sdk, api/models/list, models/overview,
about-claude/pricing, build-with-claude/thinking, api/errors, api/rate-limits,
manage-claude/usage-cost-api, manage-claude/api-and-data-retention,
about-claude/api-credits-for-subscribers}; support.claude.com/en/articles/{8977456,
8114531, 9876003}; privacy.claude.com/en/articles/7996866; code.claude.com/docs/en/legal-and-compliance.
