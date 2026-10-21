---
id: 2026-10-21-plan-bekcisi-yalniz-plan-yaz-kod-yazma-isteginde-ajani-plani
tarih: 2026-10-21
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, gerçek EVREN API (Auto Pro)
etiketler: [plan-bekcisi, yanlis-tetiklenme, kapsam, zorluk-paketi]
kurallar: [R-22, R-20]
---

# Plan bekçisi "yalnız plan yaz, kod yazma" isteğinde ajanı planı uygulamaya itti

## Belirti
Plan bekçisi eklendikten sonra zorluk paketi (auto-pro) 11/12: "planlama" görevi ("Henüz KOD YAZMA.
Sadece EVREN_PLAN.md dosyasına ... görev planı yaz") düştü — ajan cli.py, db.py, models.py … yazdı,
365 sn'de zaman sınırına takıldı ("KALDI: henüz kod yazılmadı").

## Kök neden
Doğrulandı. Ajan isteneni yaptı (EVREN_PLAN.md, `- [ ]` maddeleri); bekçi bu turda yazılan plan
dosyasındaki açık maddeleri "bitmemiş iş" saydı ve ajanı "sormadan sıradakine geç" diye dürttü. Yalnız plan
istenen turda açık maddeler İSTENEN SONUÇTUR. Birim testlerinde bu "tetiklenmemesi gereken" senaryo yoktu
(R-22'nin uyardığı durum); gerçek API ölçümünde (tests/e2e_plan_bekcisi_real_api.py) de yoktu — yalnız
zorluk paketinin TAMAMI yakaladı.

## Çözüm
`planguard.plan_only_request(history)`: son gerçek kullanıcı mesajında "kod yazma", "uygulamaya başlama",
"dosyalara dokunma", "sadece/yalnız … plan", "only/just … plan", "don't implement" varsa bekçi o turda
çalışmaz (`AgentRunner._plan_guard_active`). Proje ajanı önerisi kartı da bu istekte çıkmaz.

## Kanıt
- `tests/test_plan_bekcisi.py::test_yalniz_plan_istegi_algilama` (6 durum: 3 plan-only, 3 değil —
  "Kod yazmayı bilen biri gibi…" yanlış eşleşmez) ve
  `test_yalniz_plan_isteginde_plan_dosyasi_tetiklemez` (dürtme yok, 2 çağrıda biter).
- Zorluk paketi yeniden: sonucu oturum günlüğünde ve CHALLENGE_RESULTS.md'de.

## Önleme
R-22 zaten bunu söylüyordu; uygulanmadı. Otomatik dürtme ekleyen her değişiklikte "kullanıcı tam
olarak bu çıktıyı istiyor" senaryosunu (burada: yalnız plan) birim testine yaz, sonra paketin tamamını koş.

## İlgili dosyalar
- src/evren_studio/agent/planguard.py
- src/evren_studio/agent/runner.py
- src/evren_studio/ui/session_view.py
- tests/test_plan_bekcisi.py
