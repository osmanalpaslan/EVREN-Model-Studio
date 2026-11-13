---
id: 2026-11-13-zorluk-paketi-gorevi-dustu-mini-proje
tarih: 2026-11-13
tur: risk            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: izleniyor                # acik | izleniyor | cozuldu | kabul-edildi
alan: test
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: bilinmiyor
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gozlem, zorluk, hiz]
kurallar: [R-21]
---

# Zorluk paketi görevi düştü: mini_proje

## Belirti
Gözlem ajanından (uygulama çalışırken, otomatik ve temizlenmiş):
e2e_basarisiz: kalan kontroller: kendi testleri geçiyor
Konum:
- (yığın izi yok)
Ayrıntı:
- gorev: mini_proje
- model: auto-pro
- sonuc: 4/5
- kaynak_betik: zorluk
- durma: cancelled

Aynı kök nedenli gözlemler: c9b5c1591110 (5 kez), cbf0ba444efe (2 kez), c416c64da149 (1 kez).

## Kök neden
Doğrulandı (2026-11-12 adım dökümü + 2026-11-13 karşılaştırma): görev 6 dk sınırına (TURN_TIMEOUT) dayanıyordu çünkü model
kodu ve testleri TEK yanıtta uzun yazıyor, EVREN o saatlerde yavaş akıyordu. Ölçülen: 2026-11-11 22:03 9315 karakter
(test dosyası 171 satır) 323 sn · 2026-11-12 00:40 6862 kar (117 satır) 289 sn · 2026-11-12 19:49 9831 kar (172 satır)
255 sn; yazma hızı 24–39 karakter/sn. Testler aynı kalıbı tekrar eden onlarca vakaydı. Kod hatası değil; süre = çıktı
uzunluğu × EVREN hızı. Düşüşler "cancelled" (sınırda kesildi) olarak kaydedildi.

## Çözüm
İstem kuralı (prompts.AGENT_RULES, bc60103): "Yazdığın her satır da bekleme demektir … Kodu ve testleri işi doğru yapacak
kadar KISA yaz: istenen her davranış ve kenar durum için bir test; aynı kalıbı tekrarlayan onlarca test yazma." Kenar
durum testi korunur (doğruluk). Görev sınırı GEVŞETİLMEDİ.

## Kanıt
Gözlem `c9b5c1591110` (dal gozlem-kayitlari): 5 kez, 1 makine, ilk 2026-11-04T17:49:39+00:00, son 2026-11-12T16:40:05+00:00,
sürümler 0.2.0+b0998db, 0.2.0+dbacba9, 0.3.0+2a978bc, 0.3.0+b0d543f, 0.5.0+c1b467a.
2026-11-13 01:40 zorluk paketi (auto, dal surum/0.5.1-istekler): **12/12, 520 sn**; mini_proje **5/5, 163 sn**, 8 adım.
Model bu kez 6034 karakter yazdı (test dosyası 102 satır) → önceki üç koşunun ortalamasına göre ~%30 az. Yazma hızı
58 kar/sn (EVREN bu gece ~2 kat hızlı) → süre kazancının bir kısmı dış etken. Aynı gece değişmeyen "planlama" görevi de
235 → 131 sn hızlandı (kontrol).

## Önleme
tests/test_hiz_adim.py::test_istem_kisa_kod_ister_ama_kenar_durum_testini_birakmaz (kural sistem istemine girer, kenar durum
testi korunur; mutasyon 2/2). İzleniyor: EVREN çok yavaşsa (≤ 20 kar/sn) 6034 karakter yine ~300 sn sürer; mini_proje
sınırı aşarsa önce adım dökümüne bak (scratch mini_adimlar betiği düzeni), sınırı gevşetme.

## İlgili dosyalar
- src/evren_studio/agent/prompts.py (AGENT_RULES)
- tests/test_hiz_adim.py
- tests/e2e_zorluk_real_api.py (TURN_TIMEOUT)
- docs/knowledge/CHALLENGE_RESULTS.md
