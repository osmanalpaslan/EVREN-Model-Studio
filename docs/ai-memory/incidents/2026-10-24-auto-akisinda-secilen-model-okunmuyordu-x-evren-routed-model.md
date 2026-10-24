---
id: 2026-10-24-auto-akisinda-secilen-model-okunmuyordu-x-evren-routed-model
tarih: 2026-10-24
tur: yanlis-iddia            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: api
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [evren, auto, akis, routed_model]
kurallar: []
---

# Auto akisinda secilen model okunmuyordu (X-Evren-Routed-Model basligi)

## Belirti
`auto` ile akışlı (stream) sohbet/ajan yanıtlarında hangi modelin çalıştığı kaydedilmiyor, yanıt başlığında
yalnız "auto" görünüyordu. Belgelerde ve kullanıcıya "EVREN bu bilgiyi akışta vermiyor, sınırlı" denmişti
(ILERIDE_YAPILACAKLAR, F7 kapanış mesajı) — bu iddia gerçek istekle denenmeden yapılmıştı.

## Kök neden
Doğrulandı: `api/client.py::_consume_stream` seçilen modeli yalnız `usage.evren.routed_model`'dan okuyordu; bu
alan yalnız AKIŞSIZ yanıtta gelir. Akışta EVREN seçilen modeli `X-Evren-Routed-Model` yanıt başlığında
(nedeni `X-Evren-Routing-Reason`, ör. `workload:balanced|picked:qwen3.8-flash-next`) ve her parçanın `model`
alanında veriyor (2026-10-24 gerçek istekle ölçüldü; `stream_options.include_usage` fark etmiyor).

## Çözüm
`_consume_stream` başlığı okur; başlık yoksa parçadaki `model` istenen modelden farklıysa onu kullanır.
`ChatResult.routing_reason` eklendi; ajan mesaj meta'sına `routing_reason` yazılır. Arayüz zaten
`meta.routed_model`'ı "auto → model" diye gösteriyordu.

## Kanıt
tests/test_api_client.py (3 yeni test: başlık, parça yedeği, doğrudan modelde yazılmaz). Gerçek istek:
"AKIŞ auto → routed: qwen/qwen3-vl-30b-a3b | neden: workload:balanced|picked:qwen3-vl-30b".

## Önleme
"API bunu vermiyor" demeden önce yanıt başlıklarını ve tüm parça alanlarını gerçek istekle dök (R-07).

## İlgili dosyalar
src/evren_studio/api/client.py, src/evren_studio/agent/runner.py, docs/knowledge/
