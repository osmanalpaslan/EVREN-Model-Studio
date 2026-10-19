---
id: 2026-10-19-dugme-lambdasi-clicked-in-checked-degeriyle-varsayilan-argum
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [qt, lambda, clicked]
kurallar: [R-24]
---

# Düğme lambdası clicked'in checked değeriyle varsayılan argümanı kaybetti

## Belirti
Hata kartındaki "Yapay zekâ ile açıkla" düğmesi ve ücretli sağlayıcı panelini
açan düğme tıklanınca yanlış argümanla çalıştı / hiçbir şey yapmadı.

## Kök neden
Doğrulandı: `QPushButton.clicked` sinyali `checked` (False) değerini geçirir;
`lambda e=exc: ...` biçimindeki lambda'da bu değer ilk varsayılan argümanın
yerine geçti (e=False). `QMenu.addAction(metin, fn)` bu değeri geçirmediği için
aynı kalıp menülerde çalışıyordu, bu da hatayı gizledi.

## Çözüm
Lambda'lar `lambda _=None, e=exc: ...` biçimine çevrildi.

## Kanıt
tests/test_sidebar_fixes.py içindeki AST bekçisi: `clicked.connect`'e verilen,
varsayılan argümanlı lambda'nın ilk parametresi `_` olmalı. test_auto_pro.py
hata açıklama düğmesi testi.

## Önleme
R-24 ve AST bekçi testi.

## İlgili dosyalar
src/evren_studio/ui/session_view.py, tests/test_sidebar_fixes.py
