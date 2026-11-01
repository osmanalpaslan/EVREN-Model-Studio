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
- **Kural:** api/ veya agent/ ya da oturum arayüzüne dokunduysan ve API anahtarı varsa tests/e2e_real_api.py, tests/e2e_agent_real_api.py ve tests/e2e_ui_real_api.py'yi faz/dal sonunda, birleştirmeden ÖNCE bir kez (son kodla) çalıştır; sonucu oturum günlüğüne yaz.
- **Neden:** Sahte istemcili testler gerçek sağlayıcı davranışını kanıtlamaz; araç çağrısı ancak gerçek testle doğrulandı.
- **Kaynak:** 2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi, 2026-10-24-gercek-api-testleri-her-maddeden-sonra-kosulunca-faz-1-5-2-s

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

### R-20 · Ajanın kapsam korumasını kaldırma; değişiklikleri tura bağla
- **Kural:** prompts.AGENT_RULES'taki "Kapsam" bölümünü kısaltma/kaldırma; AgentRunner'a her turda turn_id ver (değişiklikler tura bağlı kalsın); tur sonu kartını ve kapsam denetimini (agent/scope.py) kapatma, yalnız ayar kapatabilir.
- **Neden:** EVREN modelleri istenmeyen tasarım/arayüz değişikliği yapıyor; kural tek başına yetmiyor, denetim + tek tıkla geri alma gerekiyor.
- **Kaynak:** 2026-10-17-ajan-istenmeyen-tasarim-degisikligi-yapiyordu-kapsam-tasmasi

### R-21 · Ajan davranışını değiştirince zorluk paketiyle ölç
- **Kural:** agent/ (araçlar, istem, koşucu) değiştiyse ve anahtar varsa faz/dal sonunda, birleştirmeden önce `tests/e2e_zorluk_real_api.py auto-pro` paketinin TAMAMINI bir kez çalıştır; önceki sonuçla docs/knowledge/CHALLENGE_RESULTS.md'de karşılaştır, gerilemeyi düzeltmeden birleştirme. Düzeltmeden sonra önce yalnız düşen görevi, sonra birleştirmeden önce tam paketi tekrarla.
- **Neden:** Birim testleri model davranışını ölçmez; istem kuralı tek başına bazen yetmedi (olmayan dosya), araç çıktısı biçimi sonucu değiştirdi (sayım).
- **Kaynak:** 2026-10-19-model-kisaltilmis-dosya-ciktisindan-kesin-sayi-uydurdu, 2026-10-19-istenen-dosya-yokken-ajan-benzer-dosyayi-sormadan-degistirdi, 2026-10-24-gercek-api-testleri-her-maddeden-sonra-kosulunca-faz-1-5-2-s

### R-22 · Otomatik uyarı/denetimin gereksiz tetiklenmesini de test et
- **Kural:** Ajana otomatik eklenen her uyarı, not veya denetim için hem tetiklenmesi gereken hem de tetiklenmemesi gereken (ör. kullanıcı dosyayı oluşturmak istiyor) senaryoyu birim testiyle yaz ve zorluk paketinin TAMAMIYLA ölç; yalnız hedef görevle ölçme.
- **Neden:** "Adı geçen dosya yok" uyarısı olmayan dosya görevini düzeltti ama oluşturma isteklerinde zayıf modelleri soru sormaya itti (planlama 0/1).
- **Kaynak:** 2026-10-19-olmayan-dosya-uyarisi-olusturma-isteklerinde-yanlis-alarm-ve

### R-23 · Uygulamanın kendi kaynağını ajanla düzenlerken ayrı dalda çalış; `%f` ile time.strftime kullanma
- **Kural:** EVREN Studio'nun kaynağı üzerinde (EVREN uygulamasının kendi ajanı dahil) değişiklik yaparken önce ayrı git dalı aç, geçici hata ayıklama kodu bırakma; zaman damgasında `time.strftime(... %f ...)` değil `datetime.now().strftime` kullan. Bir motorun bitmemiş değişikliğini bulursan silme, yedekle ve ayrı ele al.
- **Neden:** Uygulama ajanının eklediği `time.strftime('%f')` Windows'ta açılışta ValueError verdi; ajanı çalıştıran uygulama bozulunca sorun uygulamayla düzeltilemedi.
- **Kaynak:** 2026-10-19-uygulama-ajani-kendi-kaynagini-duzenlerken-uygulamayi-acilma

### R-24 · Kısa iç yapay zekâ isteğini ai_chat'ten geçir ve gerçek API'de dene; düğme lambdasında `_=None`
- **Kural:** Uygulamanın kendi yapay zekâ işlerini (başlık, özet, inceleme, commit, hata açıklaması) doğrudan istemciyle değil `AppContext.ai_chat(rol)` ile yap (EVREN'de düşünmeyi kapatır, boş yanıtta yedeğe geçer, bütçe/maliyeti işler) ve en az bir kez gerçek API'de dene; `clicked.connect`'e varsayılan argümanlı lambda verirken ilk parametreyi `_=None` yap.
- **Neden:** Düşünen EVREN modelleri küçük max_tokens'ta boş içerik döndürdü, sahte istemcili testler bunu yakalamadı; `clicked` sinyalinin `checked` değeri lambda'nın ilk varsayılan argümanını ezdi.
- **Kaynak:** 2026-10-19-evren-dusunen-modelleri-kisa-ic-yapay-zeka-isteklerinde-bos, 2026-10-19-dugme-lambdasi-clicked-in-checked-degeriyle-varsayilan-argum

### R-25 · Yeni araç eklerken modelin onu gerçekten seçtiğini ve kabul denetimini ölç
- **Kural:** Ajana yeni araç (MCP dahil) eklediğinde gerçek API ile aracın açık/kapalı karşılaştırmasını yap ve çağrı sayısını kaydet (sunmak, kullanılması demek değildir); e2e kabul denetimini çalıştırmadan önce bilinen doğru ve bilinen yanlış bir cevapla sına.
- **Neden:** Serena araçları sunulduğu hâlde model istem yönlendirmesi olmadan hiç çağırmadı; ilk kabul denetimi doğru cevabı düşürdü.
- **Kaynak:** 2026-10-19-model-serena-araclarini-yonlendirme-olmadan-hic-kullanmadi, 2026-10-19-mcp-e2e-kabul-denetimi-dogru-cevabi-yanlislikla-dusurdu

### R-26 · Gözetimsiz akışta yapılandırılmış sonucu üç katmanla güvenceye al
- **Kural:** Modelden sonunda belirli bir blok/JSON (ör. `<qa_sonuc>`, `<plan>`) isteyen gözetimsiz akışta: (1) blok yoksa aynı turda bir kez dürt (`final_marker`), (2) tur yine bloksuz biterse aynı bağlamla kısa "yalnız sonucu ver" turu aç, (3) bozuk JSON'u (kaçışsız tırnak vb.) anahtar adlarından esnek oku; ayrıştırıcıyı gerçek model çıktısıyla test et.
- **Neden:** Gerçek QA koşularında EVREN modelleri sonucu ya hiç yazmadı, ya boş yanıtla bitirdi, ya da değer içinde kaçışsız çift tırnakla bozuk JSON verdi; senaryo yanlışlıkla "engellendi" sayıldı.
- **Kaynak:** 2026-10-19-qa-senaryosunda-model-sonuc-blogunu-yazmayi-unuttu


### R-27 · Splitter ve düzen değişikliğini gerçek sürüklemeyle doğrula
- **Kural:** Kenar çubuğu/panel/splitter'a dokunduğunda çok adımlı gerçek fare sürüklemesi testi yaz (`tests/test_kenar_cubugu_surukleme.py` düzeni) ve "görünür bölge boş değil, x >= 0, toplam genişlik <= splitter" değişmezlerini denetle; QStackedWidget orta alana sabit en küçük genişlik ver, uzun etiketleri kaydır.
- **Neden:** Kenar çubuğu yalnız sürüklemede ekran dışına itiliyordu; büyüt/küçült ve tek setSizes denemesi bunu göstermedi ve "hata yok" diye yanlış kayıt yazıldı.
- **Kaynak:** 2026-10-21-kenar-cubugu-suruklenince-kayboluyordu-orta-yiginin-en-kucuk, 2026-10-21-kenar-cubugu-icin-splitter-da-hata-yok-iddiasi-surukleme-den

### R-28 · Gözetimsiz akışta "bitti"yi istenen çıktıya bağla, kararı kullanıcıya sor
- **Kural:** Proje/Derin/QA gibi gözetimsiz akışlarda iş ancak istenen nihai çıktı doğrulanınca "bitti" sayılır; takılan veya atlanan görev varsa duraklat ve nedenini söyle; doğrulama komutunun kendi kabuk/sözdizimi hatasını görev başarısızlığı sayma; kullanıcının kararını gerektiren eksik veri veya seçimi varsayımla geçme (önceden sor ya da `SORU:` ile duraklat); ajan komutlarını ikinci bir `powershell -Command "…"` ile sarmalatma.
- **Neden:** Hesap kapama oturumunda Derin Mod 3/12 görevle "bitti, sorun yok" dedi; bozuk doğrulama komutu (`$` dış kabukta yutuldu) bir görevi düşürüp 8 görevi atlattı; Anla'nın bulduğu sorular hiç sorulmadı ve ajan onayı kendisi yazdı.
- **Kaynak:** 2026-10-21-derin-mod-kismi-projede-bitti-dedi-ve-kullaniciya-sorulari-s, 2026-10-21-proje-ajani-bozuk-dogrulama-komutu-yuzunden-gorevi-dusurup-8, 2026-10-21-ic-ice-powershell-komutunda-dis-kabuk-degiskenlerini-yuttu

### R-29 · Python kodunu bash heredoc ile yazma
- **Kural:** Ters bölü, regex veya iç içe tırnak içeren Python kodunu/yamasını bash heredoc ile dosyaya yazma; Write/Edit aracıyla `.py` dosyasına yaz, sonra çalıştır ve içe aktarma denetimi yap.
- **Neden:** Heredoc gövdesinde çift ters bölü teke indi, `\b` geri silme karakterine döndü; bozuk regex modülü içe aktarılamaz hâle getirdi (bu kuralın ilk yazımı da heredoc'ta bozuldu).
- **Kaynak:** 2026-10-21-bash-heredoc-icindeki-python-yamasi-regex-teki-b-yi-geri-sil, 2026-10-24-bash-heredoc-ile-yazilan-python-kodunda-ters-bolu-yine-bozul

### R-30 · Testi değişikliğin türüne göre seç; gerçek API ölçümünü faz sonunda topla
- **Kural:** Her değişiklikte pytest; arayüzde yalnız değişen ekranın iki temalı ekran görüntüsü; gerçek API (R-13, zorluk paketi R-21) faz sonunda bir kez; yeni araç/özellikte yalnız onun küçük açık/kapalı ölçümü (R-25); çok motorlu sıralama ölçümünü yalnız motor sırası değişirken veya EVREN model listesi değişince yap.
- **Neden:** Her maddeden sonra tekrarlanan uçtan uca testler faz başına 1,5–2 saat sürüyordu; birleştirme öncesi tam kontrol korunduğu için bozuk kod master'a girmez (kullanıcı onayı 2026-10-24).
- **Kaynak:** 2026-10-24-gercek-api-testleri-her-maddeden-sonra-kosulunca-faz-1-5-2-s

### R-31 · Tura bağlanan özelliği gerçek tur akışından da test et
- **Kural:** Tur başına veya sonuna bağlanan her özellik (denetçi, öneri kartı, özet, kayıt) için en az bir testi `send` → koşucu → `_on_done` yolundan sahte istemciyle geçir; yalnız yardımcı fonksiyonu doğrudan çağıran test yetmez.
- **Neden:** `_on_done` runner'ı `_finish()` ile sildikten sonra okuduğu için skill denetçisi gerçek kullanımda hiç çalışmadı; doğrudan çağıran birim testleri ve R-25 ölçümü bunu yakalamadı, hata bir PR ile birleşti.
- **Kaynak:** 2026-10-24-tur-sonu-isleri-runner-silindikten-sonra-okunuyordu-skill-de

### R-32 · Model isteğini bağlama KESİN sığdır; sığmayan geçmişi gönderme
- **Kural:** Özet veya iç yapay zekâ isteği oluştururken içeriği hedef modelin bağlamına temkinli sayımla (~2,6 karakter/token) sığdır (`compaction.fit_for_summary` düzeni); özet başarısız olunca geçmiş modele sığmıyorsa mesajı gönderme, kullanıcıya /clear öner; ölçülen süreye kurulum (istemci/SSL) maliyetini katma.
- **Neden:** 1M token'lık oturumda özet isteği de sığmadı, mesaj yine gönderildi, EVREN 4 kez reddetti; kullanıcı ne /compact ne cevap alabildi. Uygulamanın 3,5 karakter/token tahmini Türkçe/kodda ~1,35 kat düşük kalıyor.
- **Kaynak:** 2026-10-29-buyuk-oturumda-compact-calismiyor-mesajlar-baglam-asimiyla-r

### R-33 · Renk/stil değişikliğini okunurluk denetimiyle ölç
- **Kural:** theme.py renklerine, QSS'e veya yeni bileşen stiline dokunduğunda `tools/ui_denetim.py <klasör> ikisi --goruntu` (QT_QPA_PLATFORM=windows) çalıştır ve görüntülere bak; tests/test_okunurluk.py HATA=0 olmalı. Yeni renk seçerken tüm zeminlerde (bg, sidebar, panel, surface, surface2, hover, selected) WCAG oranını hesapla; liste yenilerken eski bileşeni `hide()` sonra `deleteLater()` et.
- **Neden:** Açık temada soluk yazılar 2,4–3,0 kontrasttaydı (109 bileşen), yer tutucu rengi QSS yüzünden uygulanmıyordu, yenilenen listelerde eski yazı yenisinin üstüne biniyordu; gözle kontrol bunları kaçırdı.
- **Kaynak:** 2026-11-01-acik-temada-soluk-yazilar-ve-bazi-dugmeler-okunmuyordu

### R-34 · Token/bağlam hesabını gerçek kullanımla kalibre et; sabit oran varsayma
- **Kural:** Bağlam göstergesi, özet eşiği, kırpma ve sert sınır `runner.estimate_tokens` / `calibration()` ile hesaplanır; yeni bir token hesabı yazma, sabit karakter/token oranı veya sabit sistem ek yükü ekleme. Modelden gelen `usage` girdi token'ı kalibrasyona akmalı (`runner.calibrate`); görselin base64'ünü sayma. Oranı değiştirince tests/test_token_kalibrasyonu.py'de hem tetiklenen hem tetiklenmeyen durumu sına.
- **Neden:** 3,5 karakter/token varsayımı EVREN'de bağlamı %40-60 küçük gösterdi (Türkçe 2,55, araç çıktısı 2,2, sistem+araç tanımları 2,16; ek yük 2.500 değil 5.620 token); otomatik özet uzun projelerde hiç tetiklenmedi.
- **Kaynak:** 2026-11-01-token-tahmini-baglami-yuzde-40-60-kucuk-gosteriyordu-otomati
