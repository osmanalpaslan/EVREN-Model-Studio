---
id: 2026-10-17-gecmis-oturum-acma-ve-ekran-gecisleri-yavasti
tarih: 2026-10-17
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [performans, wheel-guard, render-history]
kurallar: [R-12]
---

# Geçmiş oturum açma ve ekran geçişleri yavaştı

## Belirti
Kullanıcı: "geçmiş sohbetlere erişim ve diğer ekranlara geçiş yavaş." Ölçüm
(makine başka testlerle yüklüyken, offscreen): 200 mesajlık oturum açılışı
21,6 sn; 24 ekran geçişi 3,3 sn; tam test paketi 70 sn → 330 sn'ye çıkmıştı.

## Kök neden
Doğrulandı (cProfile):
1. `wheel_guard` UYGULAMA GENELİ Python olay filtresiydi: her Qt olayı Python'a
   gidip geliyordu — tek oturum açılışında 69 bin çağrı (~10 sn profil altında).
2. `render_history` 200 mesajın tamamını, her eklemede düzen yeniden hesaplanarak
   çiziyordu.
Pencere başına artan süre (6→13→25 sn) yalnız testlerde: kapatılan pencereler
bellekte kalıyor; uygulamada tek pencere var.

## Çözüm
- wheel_guard: filtre yalnız korunan alanlara takılır (`protect(kök)`: pencere
  kurulunca + her `show_page`'de); tekerlek koruması aynen sürüyor.
- render_history: çizim sırasında `setUpdatesEnabled(False)`; uzun oturumda yalnız
  son 40 mesaj (kullanıcı mesajı sınırından), üstte "Önceki N mesajı göster".
  Modele giden geçmiş değişmez. `Transcript.clear` eski parçaları hemen gizler.

## Kanıt
Aynı yük altında önce/sonra: 200 mesajlık oturum 21,6 → 3,9 sn; kısa oturuma
dönüş 0,58 → 0,15 sn; 24 ekran geçişi 3,3 → 2,55 sn; tam paket 330 → 208 sn.
Testler: test_uzun_oturum_son_mesajlarla_acilir_ve_tumu_gosterilir,
test_tekerlek_korumasi_sonradan_eklenen_alani_kapsar, test_tekerlek_odaksiz_alani_degistirmez.

## Önleme
R-12 güncellendi (uygulama geneli Python olay filtresi kurma).

## İlgili dosyalar
- src/evren_studio/ui/wheel_guard.py
- src/evren_studio/ui/session_view.py
- src/evren_studio/ui/main_window.py
- src/evren_studio/ui/transcript.py
