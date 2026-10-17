---
id: 2026-10-17-evren-model-json-400-hatasi-kalici-metin-protokolune-geciriy
tarih: 2026-10-17
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [evren-sunucu, 400, arac-cagrisi, auto]
kurallar: [R-07]
---

# EVREN model JSON 400 hatası kalıcı metin protokolüne geçiriyordu

## Belirti
Maratonda auto ile iki koşuda "Model yerel araç çağrısını reddetti (400); metin
protokolüne geçildi." notu; oturumun kalanı daha zayıf metin protokolüyle sürdü.

## Kök neden
Doğrulandı: aynı geçmiş auto'ya 3 kez gönderildi → 2×200, 1×400
`{"message": "Expecting ',' delimiter: line 1 column 2371", "code": "bad_request"}`.
Sunucu, MODELİN ürettiği araç JSON'unu ayrıştıramayınca isteğe 400 dönüyor
(tek seferlik). Koşucu her VALIDATION hatasını "yerel araç desteklenmiyor"
sayıyordu. Ayrıca bu geri dönüş hata kaydına yazılmıyor (yalnız not).

## Çözüm
`looks_like_model_json_error()` mesajı tanırsa aynı adım tur başına en fazla
2 kez yeniden denenir (`MAX_JSON_400_RETRIES`); metin protokolüne yalnız gerçek
red durumunda geçilir.

## Kanıt
tests/test_loop_guard.py::test_sunucu_model_json_400_ayni_adimi_yeniden_dener,
test_gercek_400_metin_protokolune_gecer; doğrudan istek ölçümü (yukarıda).

## Önleme
EVREN sunucu davranışı değişirse mesaj kalıplarını güncelle.

## İlgili dosyalar
- src/evren_studio/agent/runner.py
