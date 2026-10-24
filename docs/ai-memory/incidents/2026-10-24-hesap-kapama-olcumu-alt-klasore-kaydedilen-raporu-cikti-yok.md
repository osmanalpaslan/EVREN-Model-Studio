---
id: 2026-10-24-hesap-kapama-olcumu-alt-klasore-kaydedilen-raporu-cikti-yok
tarih: 2026-10-24
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: test
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, gerçek EVREN API
etiketler: [olcum-duzenegi, hesap-kapama, R-25]
kurallar: [R-25]
---

# Hesap kapama ölçümü alt klasöre kaydedilen raporu çıktı yok sandı

## Belirti
F3 açık koşusunda ölçüm "çıktı Excel dosyası yok, puan 0" yazdı; oysa ajan raporu 10 dakika içinde üretip
`hesap-kapama-raporu/Hesap Kapama Raporu.xlsx` (skill alt klasörü) olarak kaydetmişti. Elle denetim: 20/28.

## Kök neden
Doğrulandı: `tests/e2e_hesap_kapama_real_api.py` raporu yalnız kök klasörde arıyordu. Ajanın yanlış yere
kaydetmesi ayrı bir kusur (istem "bu klasöre" diyordu; betiği alt klasörde çalıştırıp göreli yol kullandı).

## Çözüm
Düzenek alt klasörlerdeki raporu da bulur, denetler ve ölçüme `yanlis_yer` olarak yazar (puandan ayrı, görünür).

## Kanıt
build/hk/kosu-deepseek-v4.1-flash-20261024-131222 (elle denetim 20/28); düzeltilmiş düzenek kodu.

## Önleme
R-25: kabul denetimini "yanlış yere ama doğru üretilmiş" çıktıyla da sına; "çıktı yok" sonucunu dökümle doğrula.

## İlgili dosyalar
- tests/e2e_hesap_kapama_real_api.py
