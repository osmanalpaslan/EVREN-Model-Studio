---
id: 2026-11-14-duman-testi-yolu-qtimer-ice-aktarmasi-silinince-cokuyordu
tarih: 2026-11-14
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: paket
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [paket, duman-testi, acilis]
kurallar: []
---

# Duman testi yolu QTimer içe aktarması silinince çöküyordu

## Belirti
0.5.1 paketlemesinde (`tools/paketle.py`, 2026-11-14 00:57) duman testi: `evren_studio\app.py`, satır 310, `main` →
`NameError: name 'QTimer' is not defined`. Paket yapımı durdu (çıkış 1). Tam takım (1454) geçmişti.

## Kök neden
Doğrulandı. c824b26 (Madde 21 e, açılış 2 kat hızlı) `app.main` içindeki `from PySide6.QtCore import QTimer` satırını,
taşıdığı iki gecikmeli çağrıyla birlikte kaldırdı; aynı fonksiyondaki `--duman-testi` dalı QTimer'ı kullanmaya devam
etti. Bu dal yalnız paketli exe'nin duman testinde çalışır; test takımında kaynaktan çalıştıran test yoktu. Kendi
hatam (aynı motor, önceki oturum).

## Çözüm
`--duman-testi` dalına yerel içe aktarma. Yeni `tests/test_duman_kaynak.py`: `python -m evren_studio --duman-testi`
ayrı süreçte, ekransız; çıkış 0 + rapor "TAMAM" ile bitmeli (~6 sn).

## Kanıt
Düzeltmeyle 1 geçti (6 sn); düzeltme geri alınınca düştü (mutasyon). Paket yeniden yapıldı (aşağıda oturum günlüğü).

## Önleme
Test. Ders: yalnız paketlemede çalışan kod yolu da kaynaktan test edilir; içe aktarma kaldıran düzenlemede aynı
fonksiyondaki tüm kullanımlar aranır (ruff F821 bunu yakalardı — app.py ruff denetiminde değil).

## İlgili dosyalar
- src/evren_studio/app.py
- tests/test_duman_kaynak.py
- tools/paketle.py
