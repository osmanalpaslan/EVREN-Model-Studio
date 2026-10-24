---
id: 2026-10-24-claude-code-masaustu-auto-pro-akilli-secim-f2
tarih: 2026-10-24
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/autopro-akilli-secim
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Auto Pro akıllı seçim F2

## Görev
Kullanıcı: "F2'ye geç: A6 zorluk, A7 iş türü rolleri ve ölçüm paketleri, A10 tutarlılık, A11 kota, A5 kalite
puanı, A8 yoklama, A13 planlayan+yazan; aynı titizlikle test et, gönderip birleştir."

## Yapılanlar
- A6/A7: `modelstats.difficulty`, `is_complaint`, `task_kind`; yeni roller `kod_kolay`, `veri`, `oyun`, `web`,
  `metin` (router zincirleri + ücretli tablo); `SessionView._route` zorluk/tür/yükseltme; ayar `autopro_smart`.
- A5: koşucu kalite olayları (`loop`, `test_edit`, `test_break`, `plan_stall`), 👎 düğmesi (`feedback_bad`, mesaj
  kimliğiyle tekil), `modelstats.quality/penalized`, `router.choose(penalties)`, Modeller tablosunda "Kalite".
- A8: `AppContext.probe_models` (arka plan, 30 dk, altyapı hatası → sona; testlerde `EVREN_STUDIO_NO_PROBE`).
- A10: `router.consistent_body` (seed yalnız gemma + veri), `ROLE_HINTS["veri"]` (betikle hesapla);
  koşucuda `base_body`, `extra_hint`.
- A11: `QuotaGate.before_call(daily_blocks=False)` normal EVREN turunda; ayar `quota_guard_turns`.
- A13: `agent/architect.py` (Derin'in salt okunur alt ajanıyla plan), ayar `autopro_architect` (varsayılan kapalı).
- Ölçüm araçları: `tests/e2e_tutarlilik_real_api.py`, `tests/e2e_rol_paketi_real_api.py` (veri/web/oyun/metin/zor),
  zorluk sürücüsü paylaşımlı + `--mimar`; kontrol doğrulama testi `tests/test_rol_paketi_kontrolleri.py`.
- Ajan kuralı: çıktı dosyasını PowerShell yönlendirmesiyle yazma (BOM).
- Belgeler: DECISIONS #90–#96, MODEL_CAPABILITIES "Tutarlılık", CHALLENGE_RESULTS "Rol paketleri…F2",
  ILERIDE 7.5 F2 YAPILDI, CHANGELOG, PROJECT_STATE. Kural R-29.

## Test sonuçları
- pytest: 570/570 (F2 testleri `test_autopro_akilli.py` 43,
  `test_rol_paketi_kontrolleri.py` 10).
- Gerçek API: tutarlılık (seed yalnız gemma); rol paketleri 3 motor (qwen 8/8, gemma 7/8, deepseek 7/8); Auto Pro
  rol paketleri 8/8; A13 kapalı 2/2 · 271 sn, açık 1/2 · 307 sn → kapalı; zorluk auto-pro ilk koşu 10/12, düzeltme
  sonrası 12/12 · 473 sn; R-13 E2E_OK · ajan 6/6 · arayüz 15/15.
- Ekran görüntüleri (koyu + açık, QT_QPA_PLATFORM=windows): Modeller Kalite sütunu, Ayarlar Auto Pro kutuları,
  yanıtta 👎 — bakıldı.

## Sorunlar ve kayıtlar
- 2026-10-24-zorluk-kurali-program-calistirma-isini-kolay-sayip-hizli-mot (benim hatam; düzeltildi)
- 2026-10-24-evren-seed-ve-temperature-0-yalniz-gemma-4-31b-de-yaniti-sab
- 2026-10-24-bash-heredoc-ile-yazilan-python-kodunda-ters-bolu-yine-bozul (→ R-29)
- Rol kontrolü ilk sürümde gemma'nın doğru çözümlerini (keyCode, `score`, "10.00'da") reddediyordu; kontrol
  düzeltildi ve doğrulama testine eklendi.

## Sonraki motor için notlar
- Rol paketleri tek koşu, paket başına 2 görev: küçük örnek. Model listesi değişince veya bir motor sürekli
  geride kalırsa paketleri yeniden koş.
- Yavaşlama kuralı (F1) bugün iki kez GERÇEKTEN tetiklendi (deepseek 10 token/sn; ilk yanıt 12 sn): doğru davrandı.
  İlk yanıt eşiği (normalin 2 katı ve en az +10 sn) sınırda çalışıyor; yanlış geçiş görülürse #89'u yeniden ölç.
- Özet modeli ayarı varsayılanı hâlâ listede olmayan deepseek-v4-flash (bu fazın dışında, zincir yedeğe düşüyor).
- Sıradaki: F3 (ILERIDE 7.5).
