---
id: 2026-10-21-ajan-cok-fazli-iste-faz-bitince-sonrakine-gecmeyi-unutuyor
tarih: 2026-10-21
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: izleniyor                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: EVREN Studio
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, gerçek EVREN API
etiketler: [faz, plan-bekcisi, compaction, derin-mod, proje-ajani]
kurallar: [R-19, R-22]
---

# Ajan çok fazlı işte faz bitince sonrakine geçmeyi unutuyor

## Belirti
Kullanıcı (2026-10-21): çok uzun istemlerde ajandan süreci bir dosyaya yazıp fazlara bölmesini istiyor;
ajan bir fazı bitirince sonrakine geçmeyi unutuyor, "devam" deyince "haklısın" deyip sürdürüyor.

## Kök neden
Kod incelemesiyle doğrulandı (gerçek API'de kısa denemelerde YENİDEN ÜRETİLEMEDİ, aşağıya bkz.):
1. Koşucu araçsız yanıtı plan/görev listesine bakmadan "done" sayıyordu (runner.py ~732-766).
2. `looks_like_unfinished_intent` yalnız ≤300 karakterlik "…geçiyorum" türü sonları yakalıyor; "Faz 1
   tamamlandı, devam edeyim mi?" (soru işaretli) yakalanmıyor; dürtme tur başına bir kez.
3. Uzun oturumda özet (compaction) özgün istemi ve planı düşürebiliyor; max_steps 80'de otomatik devam yok.

## Çözüm
- **Plan bekçisi** (`agent/planguard.py`, runner): bu turda yazılan plan dosyasında veya görev listesinde
  açık madde varken tur bitmez; en çok 8 dürtme, gerçek iş ilerlemezse 2 denemede durur; `ENGEL:` ile
  durulabilir; adım sınırında en çok 2 otomatik devam. "Yalnız plan yaz" isteğinde çalışmaz (bkz.
  2026-10-21-plan-bekcisi-yalniz-plan-yaz-kod-yazma-isteginde-ajani-plani).
- **Proje ajanı önerisi**: çok aşamalı uzun istemde kart (fazları kod sürer, unutma olmaz).
- **Derin Mod**: fazları kod sürer (anla→planla→uygula→doğrula→düzelt).

## Kanıt
- Birim: `tests/test_plan_bekcisi.py` (eski davranışın durduğu "Faz 1 tamamlandı" ve "geçeyim mi?"
  yanıtlarında sürdürür; eski TODO ve yalnız-plan isteğinde tetiklenmez).
- Gerçek API (`tests/e2e_plan_bekcisi_real_api.py`, deepseek-v4-flash ve qwen3.8-flash-next):
  A (5 faz) ve C (kullanıcının PLAN.md'si, 6 büyük faz) senaryolarında bekçi AÇIK ve KAPALI iki model de
  tüm fazları bitirdi, testler geçti, dürtme 0; B (eski TODO + soru) yanlış tetiklenme 0. Yani bekçinin
  YARARI gerçek API'de henüz gösterilemedi; zararı yok (zorluk paketi sonrası sonuç CHALLENGE_RESULTS.md).

## Önleme
Durum "izleniyor": kullanıcının gerçek uzun oturumlarında (özet sonrası) tekrar ederse, oturum kaydından
özet anını ve bekçi notlarını ("Plan bekçisi: ...") incele. Ölçüm betiği: tests/e2e_plan_bekcisi_real_api.py.

## İlgili dosyalar
- src/evren_studio/agent/planguard.py
- src/evren_studio/agent/runner.py
- src/evren_studio/ui/session_view.py
- tests/test_plan_bekcisi.py
- tests/e2e_plan_bekcisi_real_api.py
