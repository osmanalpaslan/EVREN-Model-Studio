---
id: 2026-11-13-arka-plan-gorevi-hata-verdi-operationalerror
tarih: 2026-11-13
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: genel
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: bilinmiyor
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gozlem, yedek, veritabani, kapanis]
kurallar: [R-06]
---

# Arka plan görevi hata verdi: OperationalError

## Belirti
Gözlem ajanından (uygulama çalışırken, otomatik ve temizlenmiş):
gorev_hatasi · OperationalError: unable to open database file
Konum:
- `src/evren_studio/ui/workers.py:70 _run`
- `src/evren_studio/ui/main_window.py:146 <lambda>`
- `src/evren_studio/backup.py:71 auto_backup`
- `src/evren_studio/backup.py:24 backup`
Ayrıntı:
- gorev: MainWindow._auto_backup.<locals>.<lambda>

## Kök neden
Doğrulandı (kod yolu + hata iletisi yeniden üretildi): aynı süreçte birden çok ana pencere kuran araçta (tools/ui_denetim
`ikisi` = iki tema; sürümler 06eff5c/4465847/b90873e/e68d71f = 2026-11-12 akşamki görsel denetim koşuları) ilk pencere
`close()` ile kapatılıp veri klasörü silindikten sonra pencere NESNESİ yaşamaya devam ediyordu; açılıştan 60 sn sonraya
kurulmuş `QTimer.singleShot(60 s, self, self._auto_backup)` ikinci tema ölçülürken çalıştı. `ctx.data_dir()` ortam
değişkenini her çağrıda yeniden okuduğu için (config.default_data_dir) yedek klasörü ikinci pencerenin klasörüydü, ama
`ctx.db.path` silinmiş ilk klasördeydi → `sqlite3.connect` "unable to open database file" (silinmiş klasördeki
veritabanına bağlanma denemesiyle birebir aynı ileti üretildi). R-06 bağlam nesnesi pencere SİLİNMEDİĞİ için çağrıyı
iptal etmedi. Ek kusur: `sqlite3.connect` eksik dosyayı sessizce BOŞ veritabanı olarak oluşturur → klasör varsa yedek
işlevi yanlış yerde başıboş evren.db bırakabilirdi. Kullanıcı etkisi: gerçek uygulamada pencere kapanınca süreç de
kapandığı için neredeyse yok; ama gözlem kanalını "yüksek" gürültüyle dolduruyordu.

## Çözüm
- `MainWindow._closed` (closeEvent başında): gecikmeli yedek, dosya geçmişi bakımı, güncelleme denetimi ve gözlem
  gönderimi kapanmış pencerede başlamaz; 30 dakikalık gözlem zamanlayıcısı durdurulur.
- `backup.backup`: veritabanı dosyası yoksa yeni dosya oluşturmadan `FileNotFoundError`.
- Ayrıca (aynı incelemede): açılış yükü `MainWindow.start_background_loads()` tek yöntemde; app.py ve pencereyi doğrudan
  kuran 10 gerçek API testi aynı yolu çağırır (e2e_ui "canlı model listesi" kontrolü bu yüzden düşmüştü).

## Kanıt
Gözlem `b8efe202e31e` (dal gozlem-kayitlari): 7 kez, 1 makine, ilk 2026-11-12T18:27:29+00:00, son 2026-11-12T20:36:54+00:00,
sürümler 0.5.0+06eff5c, 0.5.0+4465847, 0.5.0+b90873e, 0.5.0+e68d71f.
Testler: tests/test_otomatik_yedek.py `test_kapanan_pencerenin_gecikmeli_isleri_calismaz` (kapandıktan sonra 4 işin hiçbiri
başlamaz, gözlem açık olsa bile; zamanlayıcı durur) + `test_eksik_veritabaninin_yedegi_bos_dosya_olusturmaz` (klasör yok /
klasör var dosya yok); tetiklenen durum (açık pencerede yedek alınır) mevcut testte. Mutasyon 7/7.

## Önleme
Gecikmeli (QTimer.singleShot) iş kuran her pencere, kapanış bayrağını denetlemeli; bağlam nesnesi yalnız SİLİNEN nesnede
çağrıyı iptal eder (R-06), kapatılmış ama yaşayan pencerede etmez. Yerel dosya açan işlev eksik dosyayı yaratan bir
kütüphane çağrısından önce varlığı denetlemeli.

## İlgili dosyalar
- src/evren_studio/ui/main_window.py (closeEvent, _closed, start_background_loads)
- src/evren_studio/backup.py
- src/evren_studio/app.py
- tests/test_otomatik_yedek.py, tests/test_acilis_hizi.py
- tests/e2e_*_real_api.py (10 betik: start_background_loads)
