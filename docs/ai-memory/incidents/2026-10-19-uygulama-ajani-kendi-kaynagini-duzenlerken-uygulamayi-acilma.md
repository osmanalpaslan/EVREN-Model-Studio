---
id: 2026-10-19-uygulama-ajani-kendi-kaynagini-duzenlerken-uygulamayi-acilma
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: kritik          # kritik | yuksek | orta | dusuk
durum: cozuldu
alan: ui
kaynak_motor: EVREN Studio
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [kendi-kaynak, cokme, kenar-cubugu, windows]
kurallar: [R-23]
---

# Uygulama ajanı kendi kaynağını düzenlerken uygulamayı açılmaz yaptı

## Belirti
Kullanıcı: "EVREN uygulamasının kendi içinden bir hata bulup düzeltmeye çalıştım ama
şu an uygulama açılmıyor." crash.log (13:52): `MainWindow.__init__` →
`_debug_log` → `time.strftime('%H:%M:%S.%f')` → `ValueError: Invalid format string`.

## Kök neden
Doğrulandı. EVREN Studio'nun kendi ajanı (model bilinmiyor; oturum kaydı Comodo
kapsamasında kaldığı için bulunamadı) bu deponun çalışma ağacında iki dosya değiştirdi:
1. `ui/sidebar.py` (13:18): "Developed by Osman Alpaslan" yazısını ad ile gizleme
   düğmesi arasına koydu; 220 px kenar çubuğunda yazı "…Osman Alp" diye kesildi
   (içerik en az 250 px istiyordu — gerçek pencerede ölçüldü).
2. `ui/main_window.py` (13:51): sorunu splitter'da sanıp görünürlük/genişlik mantığını
   yeniden yazdı ve "geçici" hata ayıklama günlüğü ekledi; `time.strftime`'ın `%f`'i
   Windows'ta desteklememesi uygulamayı açılışta çökertti. Ajanı çalıştıran uygulama
   bozulunca sorun uygulamayla düzeltilemedi.
Splitter'da hata YOK: 4 ayar × 17 adımlık gerçek pencere senaryosunda (büyüt/küçült,
Ctrl+B/J, sayfa geçişi, simge durumu) genişlik hiç 0'a düşmedi. Ayrı gerçek hata:
Ctrl+K kenar çubuğunu `setVisible(True)` ile açıyor, ayarı ve başlıktaki "göster"
düğmesini güncellemiyordu (yeniden açılışta çubuk kapanıyordu).

## Çözüm
- Ajanın değişiklikleri `build/evren_ajan_degisiklikleri/` altına yedeklendi; iki dosya
  geliştiricinin son sağlam hâline döndürüldü (uygulama yeniden açılıyor).
- Kullanıcının isteği korunarak: geliştirici satırı adın ALTINA, kendi satırına
  (ad hizasında, 8.5 pt); `top.setSpacing(8)` (iç düzen aralığı devralınıyordu),
  satır dikeyde sabit (boş alanı doldurup 149 px'e uzuyordu).
- Ctrl+K → `focus_session_search`: kapalıysa `toggle_sidebar` ile açar.
- Uygulamanın kendi kaynak klasörü proje olarak seçilince oturum başına bir uyarı notu.
- `tests/test_sidebar_fixes.py`: geliştirici satırı yerleşimi, Ctrl+K ayar senkronu,
  kaynakta `time.strftime('%f')` yasağı (ast ile; ajanın satırını yakaladığı doğrulandı),
  kendi kaynak uyarısı.

## Kanıt
- Gerçek pencere ekran görüntüleri: build/shots/sidebar_ajan.png (kesik) →
  sidebar_duzeltilmis.png (tam); en küçük genişlik 199 ≤ 220.
- Gerçek giriş noktası (`app.main`, kullanıcının gerçek config+db KOPYASIYLA):
  pencere açıldı, eski şema v1 → v3 taşındı, çökme günlüğü yok.
- `pytest -q` tam paket geçti (sayı oturum günlüğünde).

## Önleme
R-23: EVREN Studio'nun kendi kaynağı üzerinde EVREN ajanıyla çalışırken ayrı git dalı
kullan; hata ayıklama kodunu commit'leme; `time.strftime` ile `%f` kullanma
(`datetime.now().strftime` kullan).

## İlgili dosyalar
- src/evren_studio/ui/sidebar.py
- src/evren_studio/ui/main_window.py
- src/evren_studio/ui/session_view.py
- tests/test_sidebar_fixes.py
