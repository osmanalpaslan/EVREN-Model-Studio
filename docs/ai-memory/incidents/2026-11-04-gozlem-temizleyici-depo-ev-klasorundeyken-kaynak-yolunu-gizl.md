---
id: 2026-11-04-gozlem-temizleyici-depo-ev-klasorundeyken-kaynak-yolunu-gizl
tarih: 2026-11-04
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: gozlem
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10 (masaüstü; depo C:\Users\<ad soyad>\Projects altında)
etiketler: [gozlem, gizlilik, test, ortam-farki]
kurallar: [R-36]
---

# Gözlem temizleyici depo ev klasöründeyken kaynak yolunu gizliyordu

## Belirti
Başka bilgisayarda yazılıp geçen `tests/test_gozlem.py::test_temizleme_uygulamanin_kendi_kaynak_yolunu_goreli_tutar`
bu bilgisayarda her koşuda kırıldı (tam takım 777/778): beklenen `src/evren_studio/ui/session_view.py`, çıkan `<yol>`.

## Kök neden
Doğrulandı: `gozlem.temizle` önce ev klasörünü `~` yapıyor, sonra yolları `_rel_source` ile depo göreli yola
çeviriyordu. Depo ev klasörünün ALTINDAYSA kaynak yolu önce `~\Projects\...` olup "bilinmeyen yol" sayılıyor ve
`<yol>` yazılıyordu. Testin yazıldığı bilgisayarda depo ev klasörü dışında olmalı (doğrulanmadı) — ortam farkı.

## Çözüm
Ev klasörü silinmeden önce `SOURCE_ROOT` altındaki yollar (iki ayırıcıyla) depo göreli yazılır; `..` ile depo
dışına çıkan ve boşluktan sonraki metin bu kurala girmez (yine `<yol>`). Gizlilik değişmedi.

## Kanıt
test_gozlem 26/26; yeni `test_depo_ev_klasorunun_altindaysa_kaynak_yolu_yine_goreli` depoyu ev klasörü altında
taklit eder (her bilgisayarda aynı sonuç). Mutasyon (kural kapalı) 2 test kırdı.

## Önleme
Yol/ortama bağlı testte ortamı testin içinde kur (monkeypatch); "bu bilgisayarda geçiyor" yetmez.

## İlgili dosyalar
- src/evren_studio/gozlem.py
- tests/test_gozlem.py
