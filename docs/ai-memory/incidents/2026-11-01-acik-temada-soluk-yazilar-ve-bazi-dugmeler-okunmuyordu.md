---
id: 2026-11-01-acik-temada-soluk-yazilar-ve-bazi-dugmeler-okunmuyordu
tarih: 2026-11-01
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [tema, kontrast, okunurluk, acik-tema, qa]
kurallar: [R-33]
---

# Açık temada soluk yazılar ve bazı düğmeler okunmuyordu

## Belirti
Kullanıcı (2026-11-01): açık modda bazı düğmeler neredeyse görünmüyor; Ayarlar'da listelenen
bazı sabit yazılar koyu/açık mod yüzünden okunmuyor.

## Kök neden
Doğrulandı (tools/ui_denetim.py, pencere görüntüsünden WCAG kontrastı, her ekran × iki tema):
1. LIGHT `text_faint` #9095a0 açık zeminlerde 2,35–3,0 (metin alt sınırı 4,5): ipuçları,
   "varsayılan: …", boş liste yazıları, alt bilgi, "Developed by", "Esc ile durdur" vb. — 109 HATA.
2. Yer tutucu yazılar: palette PlaceholderText verilse de stil sayfası (QSS) olan alanlarda Qt kendi
   soluk varsayılanını kullanıyordu (ölçülen en koyu piksel 3,16; ayarlanan renk 3,85 vermeliydi).
3. Ayarlar'daki "…" (veri klasörü seç) düğmesi: üç küçük nokta, 1,87.
4. Liste yenilemede (Skill'ler, karşılama önerileri) eski bileşen silinmeyi beklerken görünür
   kalıp yenisinin üstüne biniyordu ("Henüz profil yok." 1,24).
5. LIGHT success/danger/warning açık zeminlerde 2,7–3,5.
Koyu tema zaten 2026-10-19 kararıyla düzeltilmişti (yalnız ortak hatalar).

## Çözüm
- theme LIGHT: text_faint #646974, muted #6f747e, success #13773d, danger #b93030, warning #8f5b0a
  (her biri tüm açık zeminlerde hesaplandı).
- QSS: `placeholder-text-color: {p.muted}` (QLineEdit/QTextEdit/QSpinBox/QComboBox).
- "…" → "Seç…" + klasör simgesi + ipucu.
- skills_page._clear ve öneri ızgarası: `hide()` sonra `deleteLater()`.
- tools/ui_denetim.py: kalıcı denetim aracı (ClearType'a dayanıklı "en az N pikselin ulaştığı
  kontrast" ölçümü; kaydırmalı sayfalar, panel sekmeleri, örnek kartlar).

## Kanıt
- Denetim: açık 109 HATA → 0, koyu 92 (ilk ölçüm, araç düzeltilmeden) / 1 → 0 (offscreen, iki tema).
- tests/test_okunurluk.py (3): iki tema her ekran HATA=0. Mutasyon: text_faint eski değere
  döndürülünce açık tema testi KALDI, koyu geçti.

## Önleme
R-33.

## İlgili dosyalar
- src/evren_studio/ui/theme.py
- src/evren_studio/ui/settings_page.py
- src/evren_studio/ui/skills_page.py
- src/evren_studio/ui/session_view.py
- tools/ui_denetim.py
- tests/test_okunurluk.py
