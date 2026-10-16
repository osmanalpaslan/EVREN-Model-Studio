---
id: 2026-10-16-esc-kisayolu-komut-listesini-kapatmiyordu
tarih: 2026-10-16
tur: hata
onem: dusuk
durum: cozuldu
alan: ui/klavye
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PySide6 6.12, offscreen
etiketler: [qt, qshortcut, klavye]
kurallar: []
---

# Esc kısayolu komut listesini kapatmıyordu

## Belirti
Yeni tıklanabilir komut listesi testi: `/` yazıp Esc'ye basınca liste açık kaldı.

## Kök neden
Doğrulandı: Ana penceredeki `QShortcut("Esc")` (ajanı durdur) tuşu yazma
kutusunun `keyPressEvent`'inden ÖNCE yakalıyor; kutudaki "Esc → listeyi
kapat" kodu hiç çalışmıyordu.

## Çözüm
`MainWindow._escape`: liste açıksa kapatır, değilse ajanı durdurur.

## Kanıt
`tests/test_ui_pages.py::test_komut_listesi_tiklanir_ve_model_secilir` geçti.

## Önleme
Pencere düzeyi kısayol eklerken aynı tuşu kullanan alt bileşenleri kontrol et.

## İlgili dosyalar
src/evren_studio/ui/main_window.py, src/evren_studio/ui/composer.py
