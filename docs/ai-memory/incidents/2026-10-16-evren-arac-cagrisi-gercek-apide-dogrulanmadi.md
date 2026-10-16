---
id: 2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi
tarih: 2026-10-16
tur: risk
onem: yuksek
durum: acik
alan: api/kod-ajani
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor:
cozen_model:
ortam: Windows 11, Python 3.12 (API anahtarı yok)
etiketler: [tools, function-calling, evren-api, dogrulanmadi]
kurallar: [R-07]
---

# EVREN API'de araç çağrısı (tools) gerçek istekle doğrulanmadı

## Belirti
Kod ajanı (0.2.0) OpenAI uyumlu `tools` / `tool_calls` kullanıyor. Tüm
testler sahte model istemcisiyle yapıldı; bu bilgisayarda API anahtarı
olmadığı için EVREN'e gerçek araç isteği gönderilmedi.

## Kök neden
Doğrulanmamış varsayım: EVREN OpenAPI şemasında `tools` alanı var ve
`/v1/models` kayıtlarında bazı modeller `capabilities.tools: true` diyor;
ancak gerçek bir function-calling turu (`tool_calls` dönmesi, `role: tool`
mesajının kabul edilmesi, akışta `delta.tool_calls` biçimi) hiç gözlenmedi.

## Çözüm
Henüz yok. Hafifletme: istek 400/422 ile reddedilirse uygulama otomatik
olarak metin protokolüne (`<arac_cagrisi>` blokları) geçiyor; Ayarlar'dan
protokol elle seçilebiliyor. Bu geri dönüş de gerçek modelle denenmedi.

## Kanıt
`tests/test_agent_runner.py::test_yerel_arac_reddedilirse_metne_gecer`
(sahte), `tests/test_client_tools_sessions.py` (sahte SSE).

## Önleme
R-07. Kapatmak için: anahtarı olan bir makinede glm-5.3 ve
deepseek-v4.1-flash ile küçük bir projede "app.py'yi oku ve özetle" görevi
ver; sonucu (yerel araç mı, metin protokolü mü, hata mı) bu kayda, 
`docs/knowledge/MODEL_CAPABILITIES.md` ve `API_COMPATIBILITY.md`'ye yaz;
mümkünse `tests/e2e_real_api.py`'ye araç senaryosu ekle.

## İlgili dosyalar
src/evren_studio/api/client.py, src/evren_studio/agent/runner.py, docs/knowledge/MODEL_CAPABILITIES.md
