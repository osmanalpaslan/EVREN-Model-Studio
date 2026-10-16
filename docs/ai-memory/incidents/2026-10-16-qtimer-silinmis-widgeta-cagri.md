---
id: 2026-10-16-qtimer-silinmis-widgeta-cagri
tarih: 2026-10-16
tur: hata
onem: orta
durum: cozuldu
alan: ui/qt
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PySide6 6.12, offscreen
etiketler: [qt, qtimer, deleteLater]
kurallar: [R-06]
---

# QTimer.singleShot silinmiş widget'ı çağırdı

## Belirti
Ekran görüntüsü betiği çalışırken: `RuntimeError: libshiboken: Internal
C++ object (MarkdownView) already deleted.` (`markdown_view.py`, `_fit`).

## Kök neden
Doğrulandı: `MarkdownView.showEvent` içinde `QTimer.singleShot(0, self._fit)`
kullanıldı. Akış temizlenirken widget `deleteLater` ile silindi; zamanlayıcı
bağlam nesnesiz olduğu için iptal edilmedi ve silinmiş nesneyi çağırdı.

## Çözüm
`QTimer.singleShot(0, self, self._fit)` biçimine geçildi (aynısı
`Transcript.scroll_to_bottom` için). Bağlam nesnesi silinince Qt çağrıyı
iptal eder.

## Kanıt
Düzeltmeden sonra `tools/ui_screenshots.py` hatasız `SHOTS_OK`; 104/104 test.

## Önleme
R-06.

## İlgili dosyalar
src/evren_studio/ui/markdown_view.py, src/evren_studio/ui/transcript.py
