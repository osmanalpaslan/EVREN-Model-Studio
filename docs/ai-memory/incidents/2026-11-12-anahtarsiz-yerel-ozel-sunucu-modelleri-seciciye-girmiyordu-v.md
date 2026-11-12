---
id: 2026-11-12-anahtarsiz-yerel-ozel-sunucu-modelleri-seciciye-girmiyordu-v
tarih: 2026-11-12
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: api
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, httpx
etiketler: [saglayici, ag-gecidi, yerel-sunucu, R-17, R-25]
kurallar: [R-17, R-25]
---

# Anahtarsız yerel/özel sunucu modelleri seçiciye girmiyordu ve "Bearer yok" başlığı gidiyordu

## Belirti
Tek "Sağlayıcılar ve anahtarlar" ekranının GERÇEK sunucu denemesinde (tests/e2e_saglayici_ekrani_real_api.py) Vercel
AI Gateway'in herkese açık model listesi "Anahtar reddedildi" ile düştü (13/14); aynı adres anahtarsız/başlıksız
yoklamada 200 dönmüştü. İnceleme ikinci bir kusur gösterdi: anahtar istemeyen bir sunucu (Madde 9'daki "OpenAI uyumlu
sunucu", yeni Ollama / LM Studio şablonları) anahtarsız kaydedilince modelleri model seçicide HİÇ görünmüyordu.

## Kök neden
Doğrulandı. (1) Anahtar boşken `CompatClient`'a yer tutucu "yok" veriliyordu; `EvrenClient._headers` her istekte
`Authorization: Bearer yok` gönderiyordu (OpenRouter/Kilo/Hugging Face yok sayıyor, Vercel reddediyor).
(2) `AppContext.available_providers` yalnız ANAHTARI olan sağlayıcıları sayıyordu (2026-10-19, 8338a91); ağ geçitleri
(2026-11-04, a3fa6a4) bu kuralı devraldı → anahtarsız kayıt "kullanılamaz"; `make_client_for` anahtarsız istemci
kurmayı reddediyordu; model seçimi/gönderim/zamanlanmış görev `has_provider_key` ile "anahtar gerekli" diyordu.

## Çözüm
`CompatClient._headers`: anahtar boşsa kimlik başlığı gönderilmez. `providers.KEYLESS_KINDS` (openai_uyumlu, ollama,
lmstudio): `available_providers` bu türdeki kayıtları sayar, `make_client_for` boş anahtarla istemci kurar, yeni
`AppContext.provider_ready` (anahtarı var YA DA anahtarsız tür) model seçimi, gönderim ve zamanlanmış görevde kullanılır;
`register_gateway` bu türleri ücretsiz sayar; seçicide "yerel · ücretsiz" yazar. Auto Pro sırasına yine girmez.

## Kanıt
tests/test_tek_saglayici_ekrani.py: `test_anahtarsiz_istekte_kimlik_basligi_gonderilmez` (başlık yok / anahtar varken
Bearer), `test_anahtarsiz_yerel_sunucu_modelleri_secicide_ve_kullanilir`, tetiklenmeyen
`test_anahtar_isteyen_ag_gecidi_anahtarsizken_hazir_degil`; mutasyon 6/6. Gerçek deneme 14/14 (Vercel 508 model).

## Önleme
R-25'in gereği: yeni bir sağlayıcı/ağ geçidi yolu eklenince GERÇEK sunucuya karşı ücretsiz uçla (model listesi, sahte
anahtar reddi, kapalı yerel sunucu) uçtan uca dene; "anahtarsız" durumunu da ayrıca sına.

## İlgili dosyalar
- src/evren_studio/api/compat_client.py, src/evren_studio/api/providers.py
- src/evren_studio/ui/app_context.py (available_providers, make_client_for, provider_ready)
- src/evren_studio/ui/session_view.py, src/evren_studio/ui/connections.py
- tests/test_tek_saglayici_ekrani.py, tests/e2e_saglayici_ekrani_real_api.py
