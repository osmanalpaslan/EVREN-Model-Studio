---
id: 2026-11-13-qt-warning-qfontdatabase-cannot-find-font-directory-venv-lib
tarih: 2026-11-13
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: bilinmiyor
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gozlem]
kurallar: []
---

# Qt warning: qfontdatabase: cannot find font directory .venv/lib/site-packages/pyside#/lib/fo…

## Belirti
Gözlem ajanından (uygulama çalışırken, otomatik ve temizlenmiş):
qt_uyari: QFontDatabase: Cannot find font directory .venv/Lib/site-packages/PySide6/lib/fonts. Note that Qt no longer ships fonts. Deploy some (from https://dejavu-fonts.github.io/ for example) or switch to fon…
Konum:
- (yığın izi yok)
Ayrıntı:
- —

## Kök neden
Doğrulandı: uyarıyı yalnız Qt'nin ekransız (offscreen) platformu üretir — bu platform yazı tiplerini PySide6'nın kendi
`lib/fonts` klasöründe arar (Qt artık yazı tipi dağıtmıyor). Gerçek pencere (windows platformu) sistem yazı tiplerini
kullanır. Gözlem, ekransız kipte çalışan bir test/ölçüm sırasında (gözlem ajanı açıkken) kaydedildi; kullanıcı
uygulamasında görünmez. Kullanıcıya etkisi yok (dev-only gürültü).

## Çözüm
`gozlem._QT_ZARARSIZ` listesine "Cannot find font directory" eklendi (zararsız Qt uyarıları gibi kaydedilmez).
Düşünülüp UYGULANMAYAN: ekransız kipte `QT_QPA_FONTDIR`'i Windows yazı tiplerine yöneltmek — uyarıyı da kaldırırdı ama
ekransız kipte ölçü alan yüzlerce arayüz testinin yazı ölçülerini değiştirir (risk, kazanç yok).

## Kanıt
Gözlem `60677e5d4254` (dal gozlem-kayitlari): 1 kez, 1 makine, ilk 2026-11-12T16:19:14+00:00, son 2026-11-12T16:19:14+00:00,
sürümler 0.5.0+c1b467a. Ölçüm 2026-11-13 (QLabel gösteren küçük betik): offscreen → 1 uyarı (yazı tipi klasörü),
windows → 0 uyarı. tests/test_gozlem.py (kaydedilmez + gerçek uyarı yine kaydedilir) geçti; mutasyon 1/1.

## Önleme
tests/test_gozlem.py: yazı tipi uyarısının kaydedilmediği satır. Yeni bir Qt uyarısını zararsız listesine eklemeden önce
hangi platformda çıktığını iki platformda çalıştırarak doğrula.

## İlgili dosyalar
- src/evren_studio/gozlem.py (_QT_ZARARSIZ)
- tests/test_gozlem.py
