---
id: 2026-10-21-ayarlar-sayfasi-uzun-acilir-liste-yuzunden-yatay-kayiyordu
tarih: 2026-10-21
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: bilinmiyor
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, PySide6
etiketler: [ayarlar, qcombobox, tasma, yatay-kaydirma]
kurallar: [R-05]
---

# Ayarlar sayfası uzun açılır liste yüzünden yatay kayıyordu

## Belirti
Yeni onay kutularının ekran görüntüsünde (R-05) Ayarlar sayfası 1280 px pencerede yatay kaydırma
çubuğu gösterdi; satırların sağı kesikti.

## Kök neden
Doğrulandı (ölçüm). "Kod Ajanı" kartındaki "Varsayılan çalışma modu" açılır listesi öğe metnini
("<mod> — <açıklama>") tam sığdıracak genişlik istiyordu: kart 1072 px, sayfa 1090 px, görünür alan 957 px.
Yeni eklenen onay kutuları değil (en genişi 556 px).

## Çözüm
`settings_page.py`: listeye `AdjustToMinimumContentsLengthWithIcon` ve `setMinimumContentsLength(24)`;
açılan listede tam metin görünmeye devam eder. Ölçüm sonrası sayfa 823 px ≤ 957 px.

## Kanıt
Açık temada yeniden alınan ayarlar ekran görüntüsünde yatay çubuk yok (oturum 2026-10-21).

## Önleme
Uzun metinli QComboBox'a en küçük içerik uzunluğu ver; arayüz değişikliğinde ekran görüntüsüne bak.

## İlgili dosyalar
- src/evren_studio/ui/settings_page.py
