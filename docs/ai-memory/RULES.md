# Kurallar

> Her kural bir veya daha fazla kayda dayanır. Yeni kural eklerken bir
> sonraki numarayı kullan ve aşağıdaki biçimi bozma (araç bu biçimi okur):
>
> ```
> ### R-NN · Kısa başlık
> - **Kural:** Tek cümle, emir kipinde, uygulanabilir.
> - **Neden:** Kısa gerekçe.
> - **Kaynak:** kayit-kimligi-1, kayit-kimligi-2   (veya AGENTS.md)
> ```
>
> Kural eskidiyse silme; başlığa "(KALDIRILDI: neden)" ekle ve Kural
> satırını "Uygulanmaz." yap.

### R-01 · Türkçe içerikli dosyayı PowerShell 5.1 ile yazma
- **Kural:** Dosyaları Python, düzenleyici aracı veya [IO.File]::WriteAllText(..., UTF8Encoding($false)) ile BOM'suz UTF-8 yaz; Get-Content | Set-Content zinciri kullanma.
- **Neden:** PowerShell 5.1 varsayılan olarak ANSI okur/yazar; Türkçe karakterler kalıcı olarak bozulur.
- **Kaynak:** 2026-10-15-cift-kodlanmis-turkce-metinler-mojibake

### R-02 · .gitignore kalıbını kaynak dosyalara karşı doğrula
- **Kural:** Yeni ignore kalıbından sonra `git check-ignore -v` ve `git ls-files -o -i --exclude-standard src` ile kaynak kodun dışlanmadığını kontrol et; mümkünse temiz klonda test et.
- **Neden:** Geniş kalıplar (`secrets*`) kaynak modülü sessizce depodan dışarıda bırakır.
- **Kaynak:** 2026-10-15-gitignore-secrets-kalibi-kaynak-modulu-disladi

### R-03 · "Kaydediliyor" yetmez, okuma yolunu da test et
- **Kural:** Bir ayar/veri kaydediliyorsa uygulamanın açılışta onu gerçekten okuduğunu uçtan uca test et.
- **Neden:** Kaydetme testi geçerken ayarlar hiç yüklenmiyordu.
- **Kaynak:** 2026-10-15-ayarlar-acilista-okunmuyordu

### R-04 · Arayüz iş parçacığında ağ isteği yapma
- **Kural:** Ağ/disk ağırlıklı işleri Task (arka plan iş parçacığı) ile çalıştır; Qt sinyalleriyle sonuç döndür.
- **Neden:** Açılışta senkron model listesi isteği pencereyi donduruyordu.
- **Kaynak:** 2026-10-15-acilista-senkron-model-yukleme-arayuzu-donduruyordu

### R-05 · Arayüz işini görmeden "tamamlandı" deme
- **Kural:** Arayüz değişikliğinden sonra tools/ui_screenshots.py ile (QT_QPA_PLATFORM=windows; offscreen'de yazılar kutucuk çıkar) ekran görüntüsü alıp bak; duman testi yalnızca açıldığını kanıtlar. Doğrulanmayanı açıkça yaz.
- **Neden:** Duman testi SMOKE_OK verirken arayüzde bozuk metinler ve eksik Code Studio vardı; belgeler "tamamlandı" diyordu.
- **Kaynak:** 2026-10-15-duman-testi-bozuk-arayuzu-yakalamadi, 2026-10-15-code-studio-ajan-ozellikleri-eksikti, 2026-10-16-offscreen-ekran-goruntulerinde-yazilar-kutucuk

### R-06 · Gecikmeli Qt çağrısına bağlam nesnesi ver
- **Kural:** QTimer.singleShot(ms, self, fn) biçimini kullan; widget silinince çağrı iptal olur.
- **Neden:** Silinmiş widget'a gecikmeli çağrı "Internal C++ object already deleted" hatası verdi.
- **Kaynak:** 2026-10-16-qtimer-silinmis-widgeta-cagri

### R-07 · Gerçek API ile doğrulanmamış yeteneği doğrulanmış gibi sunma
- **Kural:** tools, görsel, OCR vb. yetenekleri gerçek istekle test etmeden "çalışıyor" yazma; sonucu docs/knowledge/MODEL_CAPABILITIES.md'ye işle.
- **Neden:** Kod ajanı yalnızca sahte model istemcisiyle test edildi; EVREN'in tools desteği bilinmiyor.
- **Kaynak:** 2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi

### R-08 · Kararsız testte rastgele kod değiştirme
- **Kural:** Zamanlamaya bağlı bir test yük altında düşerse önce tek başına tekrar çalıştır; kararsızlığı kayda bağla, ilgisiz kodu değiştirme.
- **Neden:** İzleme döngüsü testi tam paket yükünde bir kez düştü, tek başına sürekli geçiyor.
- **Kaynak:** 2026-10-16-izleme-dongusu-testi-zamanlamaya-bagli-kararsiz

### R-09 · Hafızayı oku, sonra besle
- **Kural:** Her oturuma `tools/ai_memory.py baslangic` ile başla; kod değiştirdiysen oturum günlüğü yaz, `indeks` ve `denetle` çalıştır.
- **Neden:** Farklı motorlar aynı hataları tekrarlamasın; bilgi sohbet geçmişinde kaybolmasın.
- **Kaynak:** AGENTS.md

### R-10 · Kodlamayı test ile koru
- **Kural:** Kaynak/doküman dosyalarında bozuk Türkçe (mojibake) ve .py dosyalarında BOM olmamalı; tests/test_source_hygiene.py bunu denetler, kapatma.
- **Neden:** Bozulma gözden kaçtı ve depoya girdi; otomatik denetim olmadan tekrar eder.
- **Kaynak:** 2026-10-15-cift-kodlanmis-turkce-metinler-mojibake, 2026-10-15-duman-testi-bozuk-arayuzu-yakalamadi

### R-11 · Qt bileşenini yalnızca ana iş parçacığından güncelle
- **Kural:** Arka plan iş parçacığından gelen her geri çağrıyı QObject sinyaliyle ana iş parçacığına taşı; Task kullanırken workers.py'deki referans tutma düzenini bozma.
- **Neden:** İzleme sayfası arayüzü iş parçacığından güncelliyordu (Qt uyarısı, rastgele çökme riski); referanssız görevlerin sonucu kaybolabiliyordu.
- **Kaynak:** 2026-10-16-izleme-sayfasi-arayuzu-arka-plan-is-parcacigindan-guncelliyordu, 2026-10-16-arka-plan-gorevine-referans-tutulmuyordu

### R-12 · Fare tekerleği korumasını kaldırma
- **Kural:** Yeni sayı/liste alanları wheel_guard.protect() ile korunur (pencere kurulunca ve her ekran açılışında otomatik); korumayı kapatma, alan başına tekerlek davranışı ekleme ve UYGULAMA GENELİ Python olay filtresi kurma.
- **Neden:** Kullanıcı ayarları kaydırırken farkında olmadan değiştiriyordu; uygulama geneli filtre ise her olayı Python'dan geçirip oturum açılışını ve ekran geçişlerini yavaşlatıyordu.
- **Kaynak:** 2026-10-16-ayarlar-fare-tekerlegiyle-farkinda-olmadan-degisiyordu, 2026-10-17-gecmis-oturum-acma-ve-ekran-gecisleri-yavasti

### R-13 · API/ajan değişikliğinden sonra gerçek uçtan uca testleri çalıştır
- **Kural:** api/ veya agent/ ya da oturum arayüzüne dokunduysan ve API anahtarı varsa tests/e2e_real_api.py, tests/e2e_agent_real_api.py ve tests/e2e_ui_real_api.py çalıştır; sonucu oturum günlüğüne yaz.
- **Neden:** Sahte istemcili testler gerçek sağlayıcı davranışını kanıtlamaz; araç çağrısı ancak gerçek testle doğrulandı.
- **Kaynak:** 2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi

### R-14 · Eski izin anahtarını asla daha yetkili moda çevirme
- **Kural:** Mod/izin adlarını değiştirirken yeni anahtar kullan; eski değerleri normalize_mode ile eşdeğer veya daha kısıtlı moda eşle ve bunu test et.
- **Neden:** 0.2.0'daki "otomatik" (=düzenlemeleri kabul et) yeni Otomatik moda eşlenseydi eski oturumlar onaysız komut çalıştırırdı.
- **Kaynak:** 2026-10-16-duzenleme-modu-gizli-ve-yapilandirma-dosyalarini-korumuyordu

### R-15 · Özelliğin hangi dalda olduğunu kullanıcıya söyle
- **Kural:** Kullanıcıya bir özelliği "hazır" diye anlatırken birleştirilmemiş bir dalda/PR'da olup olmadığını ve diğer bilgisayarlarda nasıl güncelleneceğini belirt.
- **Neden:** Kullanıcı diğer bilgisayarda master'daki eski sürümü çalıştırıp kod ajanı yok sandı.
- **Kaynak:** 2026-10-16-kullanici-dosya-erisimi-yok-yaniti-aldi

### R-16 · Uzun sürebilecek model çağrısını akışlı yap
- **Kural:** Özet gibi uzun sürebilecek model çağrılarını stream=True ile yap; akışsız çağrıyı yalnız kısa, deterministik işler için kullan.
- **Neden:** glm-5.3 uzun düşünürken akışsız istekte bağlantı koptu ("sonuç belirsiz").
- **Kaynak:** 2026-10-16-glm-5-3-akissiz-ozet-isteginde-baglanti-koptu

### R-17 · Ücretli sağlayıcı fiyatını ve doğrulama durumunu tarihli tut
- **Kural:** api/providers.py'deki fiyatları değiştirirken PRICES_AS_OF'u güncelle, kaynağı yaz; gerçek istekle denenmemiş sağlayıcıyı verified=False bırak ve arayüzde "doğrulanmadı" ile "tahmini" ifadelerini kaldırma.
- **Neden:** OpenAI/Anthropic entegrasyonu anahtarsız, belgelerden yazıldı; fiyatlar değişir ve bütçe yalnızca tahmindir.
- **Kaynak:** 2026-10-16-openai-ve-anthropic-entegrasyonu-gercek-anahtarla-dogrulanma

### R-18 · Başlamadan önce GitHub ile eşitle, eşitleme uyarısını yok sayma
- **Kural:** `baslangic` çıktısındaki "GitHub eşitleme" bölümünü oku; "!" satırı varsa (geride, ayrışmış, commit'lenmemiş değişiklik) işe başlamadan kullanıcıya söyle ve veri kaybettiren git komutunu (reset, checkout --, stash drop, push --force) onaysız çalıştırma.
- **Neden:** Kullanıcı birden çok bilgisayarda çalışıyor ve git pull yapmayı unutabiliyor; eski kopyada çalışan motor işi tekrarlar veya çakışma üretir.
- **Kaynak:** 2026-10-16-motor-baska-bilgisayarda-yapilan-isleri-fark-etmiyordu

### R-19 · Ajan turunu araçsız yanıt geldi diye bitmiş sayma; döngü bekçisini koru
- **Kural:** agent/runner.py'de boş veya "yapacağım" türü araçsız yanıtı dürtmeden `done` sayma, tekrar/ileri-geri düzenleme bekçisini (`_guard`, tests/test_loop_guard.py) kaldırma; ajan davranışını değiştirince tests/e2e_agent_real_api.py ile birlikte çok adımlı (çelişkili görev) gerçek API ölçümü yap.
- **Neden:** EVREN modelleri düşünme bütçesini tüketip boş dönüyor, söz verip duruyor, takılınca aynı işi tekrarlıyor veya test dosyasını değiştirip yalan rapor veriyor; tek adımlı e2e testi bunları yakalamıyor.
- **Kaynak:** 2026-10-17-ajan-tekrar-ve-ileri-geri-duzenlemede-durmuyordu, 2026-10-17-bos-yanit-ve-soz-verip-durma-sessizce-bitti-sayiliyordu, 2026-10-17-zayif-modeller-takilinca-test-dosyasini-degistirip-yalan-rap
