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
- **Kural:** Arayüz değişikliğinden sonra tools/ui_screenshots.py ile ekran görüntüsü alıp bak; duman testi yalnızca açıldığını kanıtlar. Doğrulanmayanı açıkça yaz.
- **Neden:** Duman testi SMOKE_OK verirken arayüzde bozuk metinler ve eksik Code Studio vardı; belgeler "tamamlandı" diyordu.
- **Kaynak:** 2026-10-15-duman-testi-bozuk-arayuzu-yakalamadi, 2026-10-15-code-studio-ajan-ozellikleri-eksikti

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
