---
id: 2026-11-13-claude-code-madde-23-mesaj-kuyrugu-yedek-motor-sagla
tarih: 2026-11-13
motor: Claude Code
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: surum/0.5.1-istekler
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 23 mesaj kuyrugu yedek motor saglayicidan bagimsiz otomatik isler ve 0.5.1 cikti

## Görev
Kullanıcı 2026-11-13 gece: (a) bir istem işlenirken yeni istem yazılamıyor — Claude Code gibi ara mesajla iş sürsün,
işlenmemiş istem geri çekilebilsin; (b) auto dışındaki işlerde kullanılan motorlar bozulunca (bakım, düşük performans)
yedek motor(lar)a geçilsin; (c) EVREN API'si kullanılmadığında tüm otomatik işleyiş (ajanlar, bekçiler) mevcut API'nin
modelleriyle yürüsün; sonra "çıktıyı oluşturup dalları birleştirelim, testlerin eksiksiz olduğunu doğrula".
Ek (R-36): açık gözlem c9b5c1591110 (mini_proje: modelin ortama bağlı testi) → (d).

## Yapılanlar
### (a) Mesaj kuyruğu + çalışan işe iletme + geri çekme
- Yeni `agent/inbox.py` (Qt'siz, kilitli): `add`, `withdraw` (alınmışsa None), `take_steerable` (yalnız BAŞTAKİ ekli
  olmayan/komut olmayan mesajlar — sıra korunur), `take_batch` (komut tek başına, diğerleri birlikte), `merge`.
- `runner.py`: `steer_source` parametresi; döngü başında (araç sonuçları tamam) ve yanıt bitince `_take_steer` → mesaj
  kayda GERÇEK kullanıcı mesajı (meta steer, shown) olarak girer; o mesajın ardındaki çağrıda kuyruk notuna `STEER_NOTE`
  ("yarım adımı bitir, mesajı dikkate al, durdur diyorsa uy"). Yanıt bitmişken bekleyen mesaj varsa tur aynı bağlamla
  sürer. İptalde alınmaz. Kaynak hata verirse yok sayılır.
- `claims.current_turn`: ara mesaj iddia bekçisinin turunu bölmez (önceki test kanıtı geçerli kalır).
- `session_view.py`: `send` artık iş sürerken (ajan turu, özet, QA, Proje, Derin) REDDETMEZ → `_enqueue`. Ara mesaj
  yalnız normal kullanıcı turunda iletilir (`steer_ok`: model_override yok, tur kancası yok, gözetimsiz değil); görev
  turlarında sırada bekler. `_flush_inbox` (600 ms zamanlayıcı) hiçbir akış çalışmıyorken sıradakini yeni tur yapar.
  Esc/stop, `/...-durdur` komutları ve oturum değişimi sıradakileri yazma kutusuna döndürür (kendiliğinden gönderilmez,
  başka oturuma gitmez). İletilen ara mesaj konuşmada kullanıcı balonu olarak görünür.
- `composer.py`: iş sürerken Enter gönderir (düğme yine Durdur); yer tutucu ve ipucu metni; `QueueBar` (her satırda
  metin "…" ile kısalır, durum notu "çalışan işe iletilecek" / "iş bitince gönderilecek", "Geri çek" düğmesi);
  `theme.py` QueueBar stili (surface + rim).

### (b) Bozulan motordan yedeğe geçiş (auto dışındaki işler)
- `modelstats.failing`: son 2 saatte ≥3 başarısız (sunucu hatası, boş yanıt, damlayan akış) VE oran ≥ %50 → zayıf.
  `AppContext.model_weak` artık bunu HER ZAMAN içerir (motor karnesi rafta olsa da) → `ai_route` (iç işler, Derin/Proje/QA
  rolleri, auto güvenlik ağı) zayıfı sağlam yedeklerin arkasına alır; zincirden çıkarmaz; pencere geçince eski sıraya
  döner. Modeller sayfası gerekçeyi zaten gösteriyor.
- İç işlerin (`ai_chat`, paralel yedek dahil) her çağrısı `ic:<rol>` rolüyle kaydedilir (kota/anahtar hatası hariç).
  `ic:` kayıtları A5 kalite puanına ve A3 normal hızına GİRMEZ (kısa iç çağrılar ajan olaylarını sulandırmasın).
- `router.choose`: tabloda tek/hiç motor kalmadıysa (EVREN listeden kaldırdı, ağ geçidi) erişilebilir diğer motorlar en
  çok 3 yedek olur; `prefer` (kullanıcının seçtiği motor) önce. Tabloda ≥2 motor varsa davranış aynı.

### (c) Sağlayıcıdan bağımsız otomatik işleyiş
- Kural (`AppContext.auto_providers`): EVREN anahtarı varken otomatik işler yalnız EVREN (2026-10-19 kararı korunur:
  ücretli sağlayıcıya otomatik iş yok); EVREN yoksa kullanıcının seçili motorunun API'si (`current_model`,
  SessionView.model özelliği günceller); hiç anahtar yoksa EVREN varsayılır. `auto_ok`, `auto_label`.
- `available_model_ids`: EVREN yokken izinli ağ geçidi / yerel sunucu modelleri de (eskiden yalnız OpenRouter/Ollama
  kullanan kişide iç işler "API anahtarı yok"); EVREN varken ağ geçidi otomatik sıraya girmez (eski karar).
- `ai_route(prefer=seçili motor)`, `evren_only` = otomatik iş kuralı; `ai_chat`, `qa_readiness`, `test_tools`,
  `mcp_toolset`, Derin (`unavailable_reason`, `_evren_chain`, `_quota`, `_sub` istemcisi, 2. denetçi), Proje
  (`_model_for`, gözetmen, `_free_chain`, paralel görev istemcisi, `_fetch_quota`), QA (`precheck`) bu kurala geçti.
- Ücretli API'de arayüzsüz alt ajan (Derin alt ajanları, paralel görev) maliyet kaydı tutmuyordu → bütçe sınırını
  aşabilirdi. `deep.run_subagent(cost_sink, budget_stop)` + `AppContext.headless_billing`: her yanıtın kullanımı
  `usage_costs`'a yazılır, aylık bütçe dolunca sıradaki çağrı yapılmaz ("budget"). Ücretsizde (EVREN, yerel) kapalı.
- Bekçiler (test, iddia, bozma, döngü, plan) zaten koşucuda ve sağlayıcıdan bağımsız.

### (d) Gözlem c9b5c1591110 (mini_proje "kendi testleri")
- Kök neden ölçüm ortamı: zorluk kontrolü YARIM UTF-8 ortamında (yalnız PYTHONIOENCODING) koşuyordu; modelin testi
  ajanın ortamında da düz ortamda da geçiyor. `unittest_ok` artık ajanın gerçek ortamı (project_env) + düz ortamda koşar,
  ikisinde de geçmeli (yalnız UTF-8 kipinde geçen test artık yakalanır). R-25 bilinen doğru/yanlış/ortama bağlı: 3/3.
  Kayıt 2026-11-13-zorluk-paketi-gorevi-dustu-mini-proje-2, gözlem kapatıldı.

## Test sonuçları
- (a) tests/test_mesaj_kuyrugu.py 15 test (kuyruk sırası/geri çekme/parti; 60 turlu eşzamanlı alma-geri çekme yarışı
  switchinterval 1 µs; koşucu: adım arası, tur sonu, yok/hatalı kaynak, iptal; iddia turu; arayüz R-31: çalışırken
  iletme, geri çekme (kutudaki yazı korunur), akış sürerken bekleme + bitince yeni tur + yazılan yazıya dokunmama,
  durdurma komutu / yeni oturum / başka oturum, görev turuna iletilmeme, Esc). test_project_ui eski "engellenir" testi
  yeni davranışa çevrildi (görev turu bir adım daha atar ama mesajı almaz; /proje-durdur kutuya döndürür).
  Mutasyon: ilk koşu 12/18 → kaçanlar için test eklendi/düzeltildi (biri test hatası: `str(list)` satır sonunu kaçışlı
  yazdığı için olumsuz denetim hiç eşleşmiyordu) → 18/18 + akış bekçisi 1/1. Alan paketi 79 geçti.
  Görsel (R-05/R-33): sıra paneli iki temada (QT_QPA_PLATFORM=windows) bakıldı; ilk görüntüde uzun metin nota
  taşıyordu → `_ElidedLabel` ("…") ile düzeltildi.
- (b) tests/test_yedek_motor.py 12 test (tetiklenen + 3 tetiklenmeyen durum R-22; iç çağrı kalite puanını sulandırmaz;
  zayıf motor arkaya, çıkarılmaz; tek motorda yedek + seçilen önce; model_weak karne kapalıyken; iç işte başarı/hata/boş
  kaydı; kota hatası sayılmaz; paralel yolda kayıt; gerçek AppContext'te bozulan motor başka rolde de geri alınır).
  test_yedek_istek kaydı ayıracak biçimde uyarlandı. Mutasyon 14/14. Yönlendirme paketi 168 geçti.
- (c) tests/test_saglayicidan_bagimsiz.py 9 test (kural matrisi; EVREN yokken iç/otomatik iş kullanıcının API'si +
  maliyet; EVREN varken ücretliye gitmez + MCP/test aracı yok; Derin/QA/paralel EVREN yokken açık; yalnız yerel sunucu +
  seçilen önce + iki API'de seçili olan; EVREN varken ağ geçidi sıraya girmez; alt ajan maliyeti + bütçe durdurması;
  EVREN yokken kota sorgusu yok). Eski "yalnız EVREN" beklentili 4 test yeni karara çevrildi (biri gerçek ağa 401'lik
  istek atıyordu → sahte istemci). Mutasyon 18/18 (bir gereksiz koşul kaldırıldı). Geniş alan paketi 384 + sağlayıcı
  ekranı 30 geçti.

## Sorunlar ve kayıtlar
- Yeni testte oturumsuz `_note` modal QMessageBox açtı → test 10 dk asıldı (mutasyon koşucusu zaman aşımı); faulthandler
  ile bulundu, testte QMessageBox.information susturuldu.

## Sonraki motor için notlar
- (b), (c), (d) ve çıktı adımları DEVIR_NOTU madde 23'te.
