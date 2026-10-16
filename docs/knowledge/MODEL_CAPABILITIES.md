# Model Yetenekleri Kaydı

> Kaynak: `GET /v1/models` canlı yanıtı — 2026-10-15 20:35 UTC.
> Yetenekler sağlayıcı kayıt defterinden gelir. Bir modelin listede olması
> o anda sağlıklı olduğu anlamına gelmez.

## Doğrulanmış canlı liste (16 model)

| Model | Görev | Bağlam | Araç çağrısı | Görsel | Notlar |
|---|---|---|---|---|---|
| glm-5.3 | chat | 524288 | ✓ | ✗ | Muhakeme modeli; `reasoning` alanı; düşük max_tokens'ta içerik boş kalır |
| auto | chat | 32768 | ✗ | ✗ | YÖNLENDİRİCİ — gerçek istekte qwen3.8-flash-next'e gitti; ayrı uzman model DEĞİL |
| deepseek-v4-flash | chat | 1048576 | ✓ | ✗ | |
| deepseek-v4.1-flash | chat | 1048576 | ✓ | ✓ | |
| mimo-v2.6-pro | chat | 1048576 | ✓ | ✓ | |
| qwen3.8-flash-next | chat | 262144 | ✓ | ✓ | auto'nun yönlendirdiği model |
| gemma-4-31b | chat | 262144 | ✓ | ✓ | |
| qwen3-vl-30b | vision_chat | 262144 | ✓ | ✓ | default_max_output_tokens=16384 |
| dots-ocr | ocr | 131072 | ✗ | ✗* | *görsel GİRDİ alır (modalities) ama capabilities.vision=false — OCR ucuyla kullanılır |
| deepseek-ocr-2 | ocr | 8192 | ✗ | ✗* | |
| qwen3-embedding-8b | embedding | 40960 | ✗ | ✗ | `/v1/embeddings` |
| qwen3-reranker-8b | rerank | 4096 | ✗ | ✗ | `/v1/rerank` |
| qwen3-asr-1.7b | audio_transcription | 32768 | ✗ | ✗ | `/v1/audio/transcriptions` |
| qwen3-guard-4b | guard | 32768 | ✗ | ✗ | default_max_output_tokens=256 |
| clef | decision | 16384 | ✗ | ✓ | `/v1/systemone`; görsel kabul eder |
| laya | decision | 8192 | ✗ | ✗ | `/v1/systemone` |

## Gerçek istekle doğrulananlar

- **glm-5.3**: sohbet ✅, akış ✅ (delta.reasoning + delta.content),
  muhakeme davranışı ✅, `/v1/requests/{id}` ✅.
- **auto**: sohbet ✅ — qwen/qwen3.8-flash-next'e yönlendirdi (usage.evren.
  routed_model).
- **Model listesi/kota/şart durumu**: 16 model, kota seviyesi ok, şartlar
  kabul edilmiş (2026-10-15).

## Doğrulanmamışlar (⬜ — canlı istekle test edilmedi)

- Görsel girdi (qwen3-vl-30b, gemma-4-31b, ...): yetenek bayrağı kayıt
  defterinden; gerçek görsel gönderilerek test EDİLMEDİ.
- Araç çağrısı (tools=true modeller): şemada `tools` geçiyor; gerçek
  function-calling turu test EDİLMEDİ.
- OCR, ASR, embedding, rerank, guard, systemone: uç noktalar şemada var;
  gerçek istekle test EDİLMEDİ.
- `response_format` (yapılandırılmış çıktı): bayraklar kayıtta var; test
  EDİLMEDİ.

## Fiyat (2026-10-15 snapshot)

Tüm modeller: girdi 0.0 CR/token, çıktı 0.0 CR/token,
`free_until: 2026-11-01`. Değişiklikler Model sayfasından canlı izlenir;
kota sayfası `remaining_cr` gösterir.

## Sağlık geçmişi

`SQLite model_health` tablosu: model başına son test zamanı, HTTP kodu,
hata özeti, gecikme. Ayrıca bkz. `EVREN_STATUS_HISTORY.md`.
