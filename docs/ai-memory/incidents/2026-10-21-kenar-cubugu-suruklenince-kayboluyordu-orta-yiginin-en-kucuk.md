---
id: 2026-10-21-kenar-cubugu-suruklenince-kayboluyordu-orta-yiginin-en-kucuk
tarih: 2026-10-21
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: bilinmiyor
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, PySide6
etiketler: [kenar-cubugu, splitter, qstackedwidget, surukleme]
kurallar: [R-27]
---

# Kenar çubuğu sürüklenince kayboluyordu: orta yığının en küçük genişliği

## Belirti
Kullanıcı (2026-10-21): soldaki oturumlar çubuğunu genişletmek için kenarını sürükleyince çubuk
kayboluyor. "Geçmişte de düzelmemişti, sadece tekrar iletmemiştim." 2026-10-19 kaydı
"splitter'da hata yok" demişti (bkz. 2026-10-21-kenar-cubugu-icin-splitter-da-hata-yok-iddiasi-surukleme-den).

## Kök neden
Doğrulandı. Orta alan bir `QStackedWidget`; en küçük genişliği (minimumSizeHint) EN BÜYÜK sayfasınınkine
eşit. Ayarlar/Yardım gibi sayfalarda kaydırmasız uzun etiketler Windows'ta bunu 1728 px'e çıkarıyordu.
QSplitter sığdıramayınca kenar çubuğunu ekranın soluna itiyordu (ölçüm: sidebar x = -810, görünür
bölge boş). Hata yalnız ÇOK ADIMLI fare sürüklemesinde çıkıyordu; tek `moveSplitter`/`setSizes`
çağrısıyla veya pencereyi büyütüp küçültmekle görünmüyordu (eski kaydın denemesi bu yüzden kaçırdı).

## Çözüm
- `main_window.py`: `CENTER_MIN = 400` ile `self.center.setMinimumWidth(...)` (sabit en küçük genişlik;
  yığın en büyük sayfaya göre büyümez); 90 karakterden uzun kaydırmasız etiketlere `setWordWrap(True)`;
  pencerenin en küçük boyutu üç sütunu sığdıracak kadar (`SIDEBAR_MIN + CENTER_MIN + PANEL_MIN + 10`).
- `composer.py`: alt bilgi etiketi kaydırmalı.
- Kenar çubuğu ve sağ panel genişliği hatırlanır (`sidebar_width`, `panel_width`; açılışta sınırlanarak
  uygulanır — R-03).

## Kanıt
`tests/test_kenar_cubugu_surukleme.py` (9 test): QTest ile mutlak koordinatlı, 10 adımlı gerçek fare
sürüklemesi; 1440x900 ve 1000x700 pencerede dx 60/180/500, ayarlar sayfasında, sağ panel tutamacı,
yeni pencerede hatırlanan genişlik, en küçük pencere. Değişmezler: `sum(sizes) <= splitter.width()`,
`sidebar.x() >= 0`, görünür bölge boş değil, panel pencere içinde. Testlerin TAMAMI eski kodda düştü,
yeni kodda geçti.

## Önleme
R-27: Splitter/düzen değişikliğini çok adımlı gerçek sürükleme testiyle doğrula; yığın (QStackedWidget)
orta alana sabit en küçük genişlik ver, uzun etiketleri kaydır.

## İlgili dosyalar
- src/evren_studio/ui/main_window.py
- src/evren_studio/ui/composer.py
- src/evren_studio/config.py
- tests/test_kenar_cubugu_surukleme.py
