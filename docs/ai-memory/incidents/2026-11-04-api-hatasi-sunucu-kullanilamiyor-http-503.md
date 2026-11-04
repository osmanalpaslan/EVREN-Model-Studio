---
id: 2026-11-04-api-hatasi-sunucu-kullanilamiyor-http-503
tarih: 2026-11-04
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: kabul-edildi                # acik | izleniyor | cozuldu | kabul-edildi
alan: ortam
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gozlem]
kurallar: []
---

# API hatası: sunucu_kullanılamıyor (HTTP 503)

## Belirti
Gözlem ajanından (uygulama çalışırken, otomatik ve temizlenmiş):
api_hatasi: {'message': 'Model şu anda dolu, lütfen kısa bir süre sonra tekrar deneyin.', 'type': 'api_error', 'param': None, 'code': 'model_capacity_exhausted', 'evren': {'resets_at': '2026-11-04T16:51:57.731531…
Konum:
- (yığın izi yok)
Ayrıntı:
- model: glm-5.3
- http: 503
- hata_turu: sunucu_kullanılamıyor
- islem: e2e_agent native

## Kök neden
Doğrulandı: EVREN sunucusu 2026-11-04 akşamı glm-5.3 için `model_capacity_exhausted` (503) ve `auto` yönlendirmesi glm'e düşünce 503 verdi; uygulama kodu değil (bu dalda `api/` değişmedi).

## Çözüm
Uygulama tarafında yapılacak yok: Auto Pro 503'te yedek modele geçiyor (gözlem 3235ecf4074b 'yedek modele geçti' bu beklenen tepkidir). Kabul edildi.

## Kanıt
Gözlem `70f7a9347342` (dal gozlem-kayitlari): 5 kez, 1 makine, ilk 2026-11-04T16:51:42+00:00, son 2026-11-04T19:09:06+00:00,
sürümler 0.2.0+256967a, 0.2.0+b0998db, 0.2.0+e86225a.

## Önleme
Sürerse `tests/e2e_real_api.py` `auto` adımını belirli bir modelle de dene. Gözlem 3235ecf4074b bu kayda bağlandı.

## İlgili dosyalar
