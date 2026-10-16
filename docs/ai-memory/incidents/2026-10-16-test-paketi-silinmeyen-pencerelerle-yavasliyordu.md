---
id: 2026-10-16-test-paketi-silinmeyen-pencerelerle-yavasliyordu
tarih: 2026-10-16
tur: surec
onem: dusuk
durum: cozuldu
alan: test
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, pytest 9.1, PySide6 offscreen
etiketler: [pytest, qt, performans]
kurallar: []
---

# Test paketi silinmeyen pencerelerle yavaşlıyordu

## Belirti
Tam test paketi 35-48 sn'den 120-166 sn'ye çıktı; `--durations` her arayüz
testinin kurulumunun (pencere açılışı) 8-10 sn sürdüğünü gösterdi. Aynı
testler tek başına ~10 sn'de bitiyordu.

## Kök neden
Doğrulandı: testler pencereyi `close()` ile kapatıyor ama silmiyordu;
zamanlayıcılar, dosya sistemi izleyicileri ve bileşenler test boyunca birikti.

## Çözüm
`tests/conftest.py`: her testten sonra çalışan `_qt_pencere_temizligi`
(üst düzey pencereleri kapatır, `deleteLater` + `DeferredDelete` işler).

## Kanıt
Tam paket 173 test: 166 sn → 29,6 sn.

## Önleme
Yeni arayüz testlerinde pencereyi elle silmeye gerek yok; conftest temizliğini kaldırma.

## İlgili dosyalar
tests/conftest.py
