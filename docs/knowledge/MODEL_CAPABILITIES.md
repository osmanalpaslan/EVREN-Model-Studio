# Model Yetenekleri Kaydı

> Kaynak: `GET /v1/models` canlı yanıtı — 2026-10-15 20:35 UTC.
> Yetenekler sağlayıcı kayıt defterinden gelir. Bir modelin listede olması
> o anda sağlıklı olduğu anlamına gelmez.

## Doğrulanmış canlı liste (16 model)

| Model | Görev | Bağlam | Araç çağrısı | Görsel | Notlar |
|---|---|---|---|---|---|
| glm-5.3 | chat | 524288 | ✓ | ✗ | Muhakeme modeli; `reasoning` alanı; düşük max_tokens'ta içerik boş kalır |
| auto | chat | 32768* | ✗* | ✗ | YÖNLENDİRİCİ; *kayıt yanlış: ölçümde 108k token kabul etti, yerel araç çalışıyor → uygulama 262144 + araç kullanır (aşağıya bakın). **Uygulamanın varsayılan modeli** |
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

## auto bağlam ölçümü (2026-10-16, `build/probe_auto_ctx.py`)

| Girdi | Yönlendirilen | Sonuç |
|---|---|---|
| ~21,8k token | google/gemma-4-31b | doğru yanıt, 8,0 sn |
| ~54k token | qwen/qwen3.8-flash-next | doğru yanıt, 3,3 sn |
| ~108k token | qwen/qwen3.8-flash-next | kabul edildi; max_tokens=200 ile içerik boş (neden doğrulanmadı) |

Sonuç: kayıttaki 32768 sınırı uygulanmıyor; yönlendirilen modeller 262k.
Uygulama auto için 262144 bağlam + yerel araç kullanır
(`ui/app_context.py::MEASURED_OVERRIDES`). Aynı gün `e2e_agent_real_api.py auto`
2/2, `e2e_ui_real_api.py auto` 15/15.

## Araç çağrısı gerçek testi (2026-10-16, `tests/e2e_agent_real_api.py`)

Görev: geçici projede PLAN modunda "app.py'yi read_file ile oku, GIZLI_SAYI
değerini yaz". Her model iki protokolle: yerel (`tools` / akışta
`delta.tool_calls`) ve metin (`<arac_cagrisi>` blokları). Süreler tek
denemedir, ağ ve yüke göre değişir.

| Model | Yerel tools | Süre | Metin protokolü | Süre | Not |
|---|---|---|---|---|---|
| glm-5.3 | ✅ | 3,7 sn | ✅ | 7,3 sn | yönlendirme: zai/glm-5.3-fp8 |
| deepseek-v4.1-flash | ✅ | 18,8 sn | ✅ | 34,1 sn | en yavaş |
| deepseek-v4-flash | ✅ | 1,6 sn | ✅ | 4,4 sn | arayüz e2e'de Onaylı düzenleme ✅ |
| qwen3.8-flash-next | ✅ | 4,2 sn | ✅ | 2,3 sn | önce list_files çağırdı |
| mimo-v2.6-pro | ✅ | 5,0 sn | ✅ | 30,4 sn | |
| gemma-4-31b | ✅ | 9,2 sn | ✅ | 9,8 sn | |
| qwen3-vl-30b | ✅ | 0,6 sn | ✅ | 0,7 sn | |
| auto | ✅ | 2,1 sn | ✅ | 0,6 sn | kayıtta `tools: false` olmasına rağmen yerel çalıştı |

Sonuç: 16/16 senaryo geçti. `role: tool` mesajları kabul ediliyor; çok
araçlı yanıtlar (list_files + read_file) doğru işleniyor. Dosya yazma
(edit_file) gerçek arayüzde deepseek-v4-flash ile doğrulandı
(`tests/e2e_ui_real_api.py`, 14/14).

## Özet (compact) gerçek testi (2026-10-16, `tests/e2e_compact_real_api.py`)

Aynı ajan geçmişi (~8 mesaj, ~7k karakter) akışlı istekle özetlendi; özette
dosya yolu, karar, hata ve açık iş korunmalı.

| Model | Süre | Sonuç |
|---|---|---|
| deepseek-v4-flash | 40,7 sn | ✅ |
| qwen3.8-flash-next | 35,6 sn | ✅ |
| glm-5.3 | 153,2 sn | ✅ (akışsız istekte bağlantı koptu) |

## Doğrulanmamışlar (⬜ — canlı istekle test edilmedi)

- Görsel girdi (qwen3-vl-30b, gemma-4-31b, ...): yetenek bayrağı kayıt
  defterinden; gerçek görsel gönderilerek test EDİLMEDİ.
- Araç çağrısıyla komut çalıştırma (run_command) ve çok adımlı uzun görevler
  gerçek modellerle ayrıca denenmedi (okuma ve düzenleme denendi).
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

## Düşünme ayarı, ajan davranışı ve döngü (2026-10-17, ayrıntı: LOOP_ANALYSIS.md)

- `reasoning_effort: "none"` düşünmeyi kapatır (deepseek-v4-flash, qwen3.8-flash-next
  gerçek istekle); destekleyenler kayıtta `capabilities.reasoning_effort=true`:
  deepseek-v4-flash, deepseek-v4.1-flash, qwen3.8-flash-next, glm-5.3, mimo-v2.6-pro.
  Düşünmesiz yanıt kalitesi düşebilir (qwen yanlış yanıt verdi); uygulama yalnız
  boş yanıt kurtarmasında kullanır. `"low"` deepseek'te daha FAZLA düşündü.
- `default_max_output_tokens` çoğunda 16384 (deepseek-v4.1-flash 65536); muhakeme
  bu payı tüketirse içerik boş döner (`usage.evren.reasoning_budget_exhausted`).
- **deepseek-v4.1-flash + metin protokolü + akış:** 5 denemenin 3'ünde araç bloğu
  kayboldu, 2'sinde DSML artığı → bu modeli metin protokolüyle kullanma (yerel 5/5).
- Çelişkili görevde dürüst durup bildirenler: deepseek-v4-flash, deepseek-v4.1-flash,
  qwen3.8-flash-next, mimo-v2.6-pro. Test dosyasını değiştiren / testi kandıran:
  auto, qwen3-vl-30b, gemma-4-31b (kural eklendikten sonra azaldı, sıfırlanmadı).
