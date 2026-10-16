---
id: 2026-10-16-offscreen-ekran-goruntulerinde-yazilar-kutucuk
tarih: 2026-10-16
tur: ortam
onem: dusuk
durum: kabul-edildi
alan: test/gorsel
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PySide6 6.12, QT_QPA_PLATFORM=offscreen
etiketler: [qt, offscreen, font, ekran-goruntusu]
kurallar: [R-05]
---

# Offscreen ekran görüntülerinde yazılar kutucuk görünüyor

## Belirti
`QT_QPA_PLATFORM=offscreen` ile alınan ekran görüntülerinde tüm metinler
kutucuk (tofu) olarak çıktı; yerleşim doğru.

## Kök neden
Doğrulandı: Windows'ta offscreen platform eklentisi sistem yazı tiplerini
yüklemiyor. Davranış testlerini etkilemez, yalnızca görsel kontrolü bozar.

## Çözüm
Görsel kontrol için `QT_QPA_PLATFORM=windows` ile çalıştır (pencere birkaç
saniye görünür). Davranış testleri offscreen'de kalır.

## Kanıt
Aynı `tests/e2e_ui_real_api.py` çalıştırması: offscreen → kutucuk, windows →
okunur metin (build/shots/real_*.png).

## Önleme
R-05'e not: görsel QA ekran görüntüleri `windows` platformuyla alınır.

## İlgili dosyalar
tools/ui_screenshots.py, tests/e2e_ui_real_api.py
