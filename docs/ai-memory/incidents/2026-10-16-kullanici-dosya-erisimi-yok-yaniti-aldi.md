---
id: 2026-10-16-kullanici-dosya-erisimi-yok-yaniti-aldi
tarih: 2026-10-16
tur: surec
onem: orta
durum: cozuldu
alan: kullanici-deneyimi/surum
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, iki bilgisayar
etiketler: [birlestirilmemis-pr, klasorsuz-oturum, ux]
kurallar: [R-15]
---

# Kullanıcı uygulamada "dosya düzenleme erişimim yok" yanıtı aldı

## Belirti
Kullanıcı: uygulamayı açtığında model dosya düzenleme erişimi olmadığını
söylüyor; Cursor ve VS Code'da aynı API ile düzenleme yapabiliyor.

## Kök neden
Doğrulandı (yerel veri incelemesi): bu bilgisayarda yeni sürüm hiç çalışmamıştı
(veritabanı şema v1, config eski biçim; Comodo sanal kutusunda da veri yok).
Yeni kod ajanı birleştirilmemiş PR #2'deydi; `master`'daki 0.1.0 düz sohbetti
ve araç vermiyordu. Ek olarak yeni sürümde de klasörsüz oturumda dosya aracı
yoktur ve sonradan klasör bağlanamıyordu; model bunu kullanıcıya açıklamıyordu.

## Çözüm
PR #2 kullanıcı onayıyla birleştirildi (`c3a17b1`). Klasörsüz oturuma
"Proje klasörü bağla" düğmesi eklendi; klasörsüz sohbet sistem istemi modele
dosya istenirse bu düğmeyi önermesini söylüyor.

## Kanıt
`tests/test_auto_mode.py::test_klasorsuz_oturuma_proje_klasoru_baglanir`.

## Önleme
R-15: kullanıcıya özellik anlatırken hangi dalda olduğunu ve birleştirme
gerekip gerekmediğini açıkça söyle.

## İlgili dosyalar
src/evren_studio/ui/session_view.py, src/evren_studio/agent/prompts.py
