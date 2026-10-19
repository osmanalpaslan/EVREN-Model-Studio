---
id: 2026-10-19-sunucu-tarafi-auto-yonlendirmesi-ongorulemez-gorunmez
tarih: 2026-10-19
tur: risk            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu
alan: api
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [auto, yonlendirme, evren-akilli]
kurallar: [R-21]
---

# Sunucu tarafı auto yönlendirmesi öngörülemez ve görünmez

## Belirti
Kullanıcı: "Auto yönlendirme motoru pek iyi değil; büyük projede birden fazla motor
gerekebilir." Ölçümler: zorluk paketinde auto 8/10 → 9/10 (deepseek-v4-flash 10/10);
maratonda en yavaşlardan, metin tekrarı ve bir kez metin protokolüne düşme.

## Kök neden
Doğrulandı (kısmen): auto her istekte modeli EVREN sunucusunda seçer; seçim kuralları
belgelenmemiş. Gözlenen yönlendirmeler orta seviye modellere (qwen3.8-flash-next,
gemma-4-31b, qwen3-vl-30b). Akışlı yanıtta `routed_model` gelmez: hangi modelin
çalıştığı görülemez. Uzun ajan görevinde adımlar farklı modellere gidebilir
(doğrulanamadı — akışta görünmüyor).

## Çözüm
Kullanıcı kararı: uygulama içi **EVREN Akıllı** (`agent/router.py`): işe göre rol
(sohbet/kod/plan/görsel/büyük bağlam/inceleme), ölçüme dayalı rol tablosu, tur
boyunca sabit model, yalnız sunucu hatası/döngü/görsel reddinde yedeğe geçiş
(AgentRunner.fallback_models), çalışma çubuğunda "EVREN Akıllı → model (rol)".
auto listede kalır.

## Kanıt
- 8 motor × 12 görev ölçümü ve EVREN Akıllı ölçümü: CHALLENGE_RESULTS.md.
- `tests/test_router.py` (rol, sağlık, yedeğe geçiş, arayüzde API'ye gerçek model gider).

## Önleme
Model listesi veya EVREN davranışı değişince rol tablosunu zorluk paketiyle yeniden
ölç (R-21); tablo tarihi `router.ROUTES_MEASURED`.

## İlgili dosyalar
- src/evren_studio/agent/router.py
- src/evren_studio/agent/runner.py
- src/evren_studio/ui/session_view.py
