---
id: 2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi
tarih: 2026-10-16
tur: risk
onem: yuksek
durum: cozuldu
alan: api/kod-ajani
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11 Pro 26200, Python 3.12.10, gerçek EVREN API (kullanıcı anahtarı)
etiketler: [tools, function-calling, evren-api, dogrulandi]
kurallar: [R-07]
---

# EVREN API'de araç çağrısı (tools) gerçek istekle doğrulanmadı

## Belirti
Kod ajanı (0.2.0) OpenAI uyumlu `tools` / `tool_calls` kullanıyor. İlk
yazıldığında tüm testler sahte model istemcisiyle yapılmıştı; o bilgisayarda
API anahtarı olmadığı için EVREN'e gerçek araç isteği gönderilmemişti.

## Kök neden
Doğrulanmamış varsayım: EVREN OpenAPI şemasında `tools` alanı var ve
`/v1/models` kayıtlarında bazı modeller `capabilities.tools: true` diyordu;
gerçek bir function-calling turu hiç gözlenmemişti.

## Çözüm
2026-10-16 13:30 civarı (yerel saat), kullanıcının anahtarıyla
`tests/e2e_agent_real_api.py` çalıştırıldı: geçici projede PLAN modunda
"app.py'yi read_file ile oku, GIZLI_SAYI değerini yaz" görevi, her model için
hem yerel (`native`) hem metin (`text`) protokolüyle.
Sonuç: **8 sohbet modelinin hepsi, her iki protokolde 16/16 GEÇTİ** —
yerel `tool_calls` akışta (`delta.tool_calls`) geldi, `role: tool` sonuçları
kabul edildi, doğru değer yanıtlandı. Ayrıntılı tablo:
`docs/knowledge/MODEL_CAPABILITIES.md` → "Araç çağrısı gerçek testi".
Ayrıca `tests/e2e_ui_real_api.py` gerçek arayüzde deepseek-v4-flash ile
Onaylı modda dosya düzenlemesini (onay kutusu → yazma → geri alma) 14/14
kontrolle doğruladı.

## Kanıt
- `tests/e2e_agent_real_api.py` çıktısı: "SONUÇ: 6/6" (glm-5.3,
  deepseek-v4.1-flash, qwen3.8-flash-next) ve "SONUÇ: 10/10" (mimo-v2.6-pro,
  gemma-4-31b, deepseek-v4-flash, qwen3-vl-30b, auto).
- `tests/e2e_ui_real_api.py`: "SONUÇ: 14/14 kontrol geçti".
- Not: `auto` modelinin kayıt defterinde `capabilities.tools: false`
  yazmasına rağmen yerel araç çağrısı çalıştı (istek yönlendirilen modele
  gidiyor). Uygulama `auto` için yine metin protokolünü seçiyor; ikisi de çalışır.

## Önleme
R-07 uygulandı. API veya ajan koduna dokunan motor, bitirmeden önce
`tests/e2e_agent_real_api.py` çalıştırmalı (anahtar varsa) — R-13.

## İlgili dosyalar
src/evren_studio/api/client.py, src/evren_studio/agent/runner.py,
tests/e2e_agent_real_api.py, tests/e2e_ui_real_api.py, docs/knowledge/MODEL_CAPABILITIES.md
