---
id: 2026-10-19-alt-enter-yeni-satir-yerine-mesaji-gonderiyordu
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
etiketler: [klavye, composer]
kurallar: []
---

# Alt+Enter yeni satır yerine mesajı gönderiyordu

## Belirti
Kullanıcı bildirdi: sohbet kutusunda Alt+Enter alt satıra geçmesi gerekirken mesajı gönderiyordu.

## Kök neden
Doğrulandı: composer.ComposerEdit.keyPressEvent yalnız Shift'i yeni satır sayıyordu;
"Enter ile gönder" açıkken Shift dışındaki her değiştirici (Alt, Ctrl) gönderime düşüyordu.

## Çözüm
Shift/Alt/Ctrl+Enter yeni satır ekler (`insertText("\n")`), düz Enter gönderir. Ayar
kapalıyken Ctrl+Enter gönderir, diğerleri yeni satır. Komut listesi açıkken Alt+Enter
öğe seçmez. Yardım ve ipucu metinleri güncellendi.

## Kanıt
tests/test_klavye_baglam_tema.py: `test_alt_shift_ctrl_enter_yeni_satir_enter_gonderir`,
`test_enter_ile_gonderme_kapaliyken_ctrl_enter_gonderir` (gerçek QTest tuş olayları).

## Önleme
Tuş davranışını her değiştirici için testte sına.

## İlgili dosyalar
src/evren_studio/ui/composer.py, src/evren_studio/ui/help_page.py
