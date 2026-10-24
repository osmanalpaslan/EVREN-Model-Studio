---
id: 2026-10-24-evren-seed-ve-temperature-0-yalniz-gemma-4-31b-de-yaniti-sab
tarih: 2026-10-24
tur: yanlis-iddia            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: api
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, gerçek EVREN API
etiketler: [seed, tutarlilik, A10]
kurallar: [R-07]
---

# EVREN seed ve temperature=0 yalnız gemma-4-31b'de yanıtı sabitliyor

## Belirti
A10 önerisi (RAKIP_VE_AUTOPRO_ANALIZI.md) "rapor işlerinde düşük temperature + sabit seed tutarlılık sağlar"
varsayımına dayanıyordu. Gerçek ölçümde (`tests/e2e_tutarlilik_real_api.py`, aynı istem 3 kez, 2026-10-24):
deepseek-v4.1-flash ve qwen3.8-flash-next `temperature=0, seed=42` ile de 3/3 FARKLI metin yazdı; yalnız
gemma-4-31b 3 yanıtta aynı metni verdi. Sayısal JSON kısmı her modelde 18/18 aynıydı (fark yorum cümlesinde).

## Kök neden
Tahmin: deepseek/qwen arka ucunda seed desteklenmiyor veya toplu çıkarım deterministik değil. Doğrulanan yalnız
davranış; neden doğrulanmadı.

## Çözüm
Seed yalnız onu dinleyen modele ve yalnız veri rolünde gönderilir (`router.SEED_HONORED`, `consistent_body`).
Veri işinde tutarlılığı asıl sağlayan yol, modelin hesabı betikle yapması: `router.ROLE_HINTS["veri"]` (hesap
kapama ölçümünde sabit betik iki koşuda aynı raporu vermişti).

## Kanıt
`tests/e2e_tutarlilik_real_api.py` ÖZET: deepseek-v4.1-flash {varsayılan 3, seed+t0 3}, qwen3.8-flash-next
{3, 3}, gemma-4-31b {3, 1} farklı yanıt. Birim: `tests/test_autopro_akilli.py::test_tutarlilik_*`.

## Önleme
R-07 (gerçek istekle doğrulanmamış yeteneği sunma). Model listesi değişince ölçüm yeniden çalıştırılmalı;
sonuç docs/knowledge/MODEL_CAPABILITIES.md "Tutarlılık (seed)" bölümünde.

## İlgili dosyalar
- src/evren_studio/agent/router.py
- tests/e2e_tutarlilik_real_api.py
- docs/knowledge/MODEL_CAPABILITIES.md
