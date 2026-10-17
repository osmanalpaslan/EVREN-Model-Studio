---
id: 2026-10-17-claude-code-masaustu-claude-code-masaustu-kapsam-korumasi
tarih: 2026-10-17
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/kapsam-korumasi
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Claude Code masaüstü: kapsam koruması

## Görev
Kullanıcı: EVREN ajanı simge isteğinde belirtilmeyen tasarım değişiklikleri yaptı;
.md kuralı yeter mi, başka ne gerekir? Önce düşünme, sonra onayla dört katman:
kural, kapsam denetimi, turu geri al, "önce plan" (varsayılan kapalı).

## Yapılanlar
Ayrıntı: kayıt 2026-10-17-ajan-istenmeyen-tasarim-degisikligi-yapiyordu-kapsam-tasmasi.
- prompts.py kapsam kuralı; agent/scope.py; ActionCard; ChangesTab.revert_rows;
  session_view: turn_id, tur sonu kartı, kapsam denetimi (arka plan), plan akışı;
  config: scope_check (açık), scope_check_model, plan_first (kapalı); Ayarlar.
- runner: plan modunda "…yapacağım" ile biten yanıt dürtülmez (plan akışında
  bulunan hata: dürtme modeli plan modunda düzenlemeye itiyordu).

## Test sonuçları
- tests/test_scope.py (7) + test_loop_guard (plan modu) — tam paket geçti.
- Gerçek API: kullanıcının gerçek isteğiyle depo kopyasında 4 model × eski/yeni
  kural (tablo kayıtta); yapay örnekte denetim 3/3 doğru.

## Sorunlar ve kayıtlar
- 2026-10-17-ajan-istenmeyen-tasarim-degisikligi-yapiyordu-kapsam-tasmasi (çözüldü)

## Sonraki motor için notlar
- Kapsam denetimi bir modele dayanır; kısmen yanlış işaret görüldü (gemma yeni
  transcript.py). Bu yüzden yalnız uyarır, geri almayı kullanıcıya bırakır.
- Büyük tasarım işleri 40 adımda bitmeyebiliyor (deepseek, qwen); varsayılan 80.
