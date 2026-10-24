---
id: 2026-10-24-auto-pro-saglik-kurali-gercek-kullanimda-hic-beslenmiyordu
tarih: 2026-10-24
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [auto-pro, saglik, model-health, kayit]
kurallar: []
---

# Auto Pro sağlık kuralı gerçek kullanımda hiç beslenmiyordu

## Belirti
`router.choose` son 30 dk'da sağlıksız ölçülen modeli sona alıyor; ama `model_health` yalnız "EVREN Durum İzleme"
ekranından yazılıyordu. Kullanıcının gerçek veritabanında tablo BOŞTU (2026-10-21); bir turda hata verip yedeğe
geçilen model sonraki turda yine birincil seçiliyordu. Motor hızı da hiç ölçülmüyordu.

## Kök neden
Doğrulandı (kod + kullanıcı veritabanı kopyası). 2026-10-19 tasarımında sağlık kaynağı yalnız izleme ekranıydı.

## Çözüm
F1 (2026-10-24, dal `feat/autopro-cekirdek`):
- A1: `model_calls` tablosu + `agent/modelstats.py`; her çağrı (süre, ilk parça, çıktı token'ı, hata, boş yanıt)
  ve her yedeğe geçiş kaydedilir; 7 günden eski kayıt budanır.
- A4: yedeğe geçişte eski model `model_health`'e sağlıksız yazılır → 30 dk sıranın sonunda.
- A3 (DECISIONS #88): o günkü normal hız (son 6 sa, yetmezse 24 sa; en az 6 örnek) üzerinden yavaşlık kuralı.
- A9: model listesi değişince uyarı; A12: çalışma çubuğu ipucu + Modeller sayfasında "son 24 saat" tablosu.

## Kanıt
`tests/test_autopro_cekirdek.py` (10 test); tam pytest 517; gerçek API sonuçları oturum günlüğünde.

## Önleme
Yönlendirme kuralı eklerken kuralın VERİ KAYNAĞININ gerçek kullanımda dolduğunu uçtan uca doğrula (R-03 ruhu).

## İlgili dosyalar
- src/evren_studio/agent/modelstats.py
- src/evren_studio/db.py
- src/evren_studio/ui/app_context.py
- src/evren_studio/ui/session_view.py
- src/evren_studio/ui/models_page.py
