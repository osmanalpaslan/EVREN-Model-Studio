---
id: 2026-10-16-auto-kaydi-32768-baglam-ve-tools-false-diyor-olcum-celisiyor
tarih: 2026-10-16
tur: yanlis-iddia            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu
alan: api
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [auto, baglam, evren-kayit]
kurallar: [R-07]
---

# auto kaydı 32768 bağlam ve tools:false diyor; ölçüm çelişiyor

## Belirti
`GET /v1/models` kaydı `auto` için `context_length: 32768`,
`capabilities.tools: false` döndürüyor. Varsayılan model auto yapılırken bu
değerler kullanılsaydı ajan metin protokolüne düşer, otomatik özet ~24k
token'da (32768 × %75) sık sık çalışırdı.

## Kök neden
Doğrulandı (gerçek istek, 2026-10-16): kayıt yönlendiricinin kendi sınırını
değil sabit bir değeri gösteriyor. `build/probe_auto_ctx.py` ölçümü:
- ~21,8k token → gemma-4-31b'ye yönlendi, doğru yanıt (110).
- ~54k token → qwen3.8-flash-next, doğru yanıt (249).
- ~108k token → kabul edildi (qwen3.8-flash-next) ama max_tokens=200 ile
  içerik boş döndü (nedeni doğrulanmadı; muhtemelen yanıt bütçesi).
Yönlendirilen iki model de 262144 bağlamlı. Yerel araç çağrısı daha önce ve
bu oturumda iki protokolde de çalıştı.

## Çözüm
`ui/app_context.py`: `MEASURED_OVERRIDES` → auto için bağlam 262144 ve
tools:true (canlı liste ve yedek listeye uygulanır). Böylece auto yerel
protokolle çalışır; otomatik özet eşiği min(%75 × 262k, 100k) = 100k.

## Kanıt
- `tests/e2e_agent_real_api.py auto`: 2/2 (yerel ve metin protokolü).
- `tests/e2e_ui_real_api.py auto`: 15/15 (düzenleme, geri alma, Otomatik mod).
- `tests/test_default_auto.py::test_auto_olculen_degerler`.

## Önleme
Kayıt değerini ölçümle çelişen her model `MEASURED_OVERRIDES`'a kanıtla
eklenir; MODEL_CAPABILITIES.md'ye işlenir (R-07). EVREN yönlendirici
davranışını değiştirirse bu değer yeniden ölçülmeli.

## İlgili dosyalar
- src/evren_studio/ui/app_context.py
- docs/knowledge/MODEL_CAPABILITIES.md
