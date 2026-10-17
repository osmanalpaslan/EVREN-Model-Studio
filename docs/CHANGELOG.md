# Değişiklik Günlüğü

## Yayınlanmamış — Döngü önleme (ajan tekrara düşmesin)

### Eklendi

- **Ay-yıldız simgesi**: Türk bayrağı oranlarıyla, arka plansız; koyu temada
  beyaz, açık temada bayrak kırmızısı. Masaüstü/görev çubuğu için `assets/evren.ico`.
- **Canlı çalışma göstergesi**: model çalışırken dönen yıldız (mesajda ve durum çubuğunda).
- **Hız**: uzun geçmiş oturumlar ~5 kat hızlı açılır (son 40 mesaj, "Önceki
  mesajları göster"); ekran geçişleri hızlandı (tekerlek koruması alan başına).
- **Ortam denetimi ve program kurulumu**: klasör bağlanınca gereken programlar
  denetlenir; eksikler Ayarlar > "Eksik program kurulumu" seçimine göre Otomatik
  (sormadan) veya Manuel ("Kurulsun mu?" bildirimi) kurulur. Ajan `install_program`
  aracıyla da isteyebilir. Kurulum winget/npm ile, yalnız bilinen listeden.
- **Döngü bekçisi**: ajan aynı aracı aynı parametrelerle (arada dosya değişmeden)
  ikinci kez çağırırsa modele uyarı gider, üçüncüde tur durur ve size bildirilir.
  Bir dosya bu tur içinde eski bir hâline geri dönerse (ileri-geri düzenleme)
  aynı şekilde uyarı, tekrarında durma.
- **Boş yanıt / "inceleyeyim" deyip durma**: model bir kez otomatik hatırlatılır;
  boş yanıtta (düşünme bütçesi tükenmesi) destekleyen EVREN modelinde o deneme
  düşünmesiz yapılır. Yine boşsa ekranda not çıkar.
- **Metin tekrarı denetimi**: model araç çağırmadan aynı cümleleri tekrar tekrar
  yazarsa metin kısaltılır, model bir kez yönlendirilir; akışta istek erken kesilir.
- **Sunucu 400 (bozuk araç JSON'u)**: aynı adım yeniden denenir, yerel araç
  çağrısı bırakılmaz.
- **Proje maratonu** (tests/e2e_marathon_real_api.py): gerçek arayüzle 3 proje
  baştan sona; kabul testleri dışarıdan.
- **API anahtarı koruması**: commit'e anahtar giremez (tools/secret_scan.py,
  ön-commit kancası ve test). Depoda/geçmişte anahtar olmadığı doğrulandı.

### Değişti

- **Otomatik mod hiçbir işlem için onay istemez** (kullanıcı kararı): riskli
  komutlar, korumalı dosyalar ve gizli dosya okuma dahil. Durdurmak için Esc.
- Tur başına adım sınırı varsayılanı 40 → 80 (eski varsayılan kendiliğinden taşınır).
- Proje hafızası: kökte EVREN.md varsa ajana yalnız o verilir (uzun AGENTS.md
  ajanı asıl işten uzaklaştırıyordu). Bu depoya kısa EVREN.md eklendi.
- Ajan kuralları: tekrar etmeme, iki başarısızlıktan sonra yol değiştirme veya
  durma, test dosyalarını değiştirmeme/kandırmama, yapmadığını yaptım dememe.
- Ayrıntı ve ölçümler: docs/knowledge/LOOP_ANALYSIS.md.

## Yayınlanmamış — Varsayılan motor auto, seçimler hatırlanır

### Değişti

- **Varsayılan motor `auto`** (EVREN yönlendiricisi): yeni oturumlar auto ile
  açılır; model seçicide EVREN grubunun en üstünde "önerilen". Mevcut
  kurulumlarda eski varsayılan glm-5.3 bir kez auto'ya çevrilir (ayar sürümü 2);
  başka bir model seçilmişse dokunulmaz. Onay modu varsayılanı değişmedi (Manuel).
- **Son seçim hatırlanır**: sohbet ekranında seçilen motor ve onay modu (seçici
  veya /model, /plan, /otomatik … komutları) kaydedilir; siz yeniden
  değiştirene kadar yeni oturumlar onunla açılır, uygulama güncellemeleri bunu değiştirmez.
- auto için ölçülen değerler: 262k bağlam + yerel araç çağrısı (kayıttaki
  32768 / tools:false yanlış çıktı). Otomatik özet artık auto'da erken çalışmaz.

## Yayınlanmamış — Ortak hafıza: GitHub eşitleme

### Eklendi

- `tools/ai_memory.py baslangic` önce GitHub'la eşitler: başka bilgisayarda
  gönderilmiş yeni commit'leri güvenliyse kendiliğinden alır (yalnız ileri
  sarma), master'a birleştirilmiş daldaysa master'a geçer; yerel değişiklik,
  ayrışmış dal, gönderilmemiş commit ve ağ hatasında dokunmadan uyarır.
  `--esitleme-yok` ile kapatılır. Kural R-18, `tests/test_ai_memory_sync.py`.

## Yayınlanmamış — OpenAI ve Anthropic sağlayıcıları (doğrulanmadı)

### Eklendi

- **Ücretli sağlayıcılar (isteğe bağlı)**: OpenAI (Responses API) ve Anthropic
  (Messages API) istemcileri; sohbet ve kod ajanı (yerel araç çağrısı) ikisinde
  de çalışır. OpenAI şifreli reasoning öğeleri ve Anthropic thinking blokları
  araç turlarında aynen geri gönderilir. **Gerçek anahtarla doğrulanmadı.**
- **Gruplu model seçici**: "EVREN · ücretsiz", "OpenAI · ücretli · doğrulanmadı",
  "Anthropic · ücretli · doğrulanmadı" başlıkları; fiyat ipucu; anahtarı
  olmayan sağlayıcının modelleri "(anahtar gerekli)" — seçilirse Ayarlar'a yönlendirir.
- **Ayarlar > Ücretli Sağlayıcılar**: anahtar kaydet/sil/doğrula (Credential
  Manager), adım adım anahtar alma rehberi, panel bağlantıları (anahtarlar,
  kredi, kullanım, belgeler), veri/kredi notları.
- **Aylık bütçe (varsayılan $5, tüm ücretli sağlayıcılar toplamı)**: harcama
  token sayıları ve tarihli fiyatlarla tahmin edilir; %80'de bir kez uyarı,
  sınırda her yeni istekten (ajan adımı dahil) önce onay. Ayarlar'da "bu ayki
  tahmini harcama".
- Hata türü "Kredi bitti" (402, 429 insufficient_quota, enforced_spend_limit):
  tekrar denenmez, hata kartında sağlayıcı paneli düğmesi. 529 = geçici aşırı yük.
- Şema v3: `usage_costs` tablosu, `sessions.provider`.
- `tests/test_providers.py` (28 sahte test), `tests/e2e_providers_real_api.py`
  (ücretli, `--evet` bayrağıyla).

### Değişti

- Yazma kutusunun altındaki not, verinin gönderildiği sağlayıcıyı gösterir.
- `tests/e2e_real_api.py` zaman aşımı 60 → 180 sn (glm-5.3 bugün 24–56 sn).

## Yayınlanmamış — Otomatik özet (auto-compact)

### Eklendi

- **Otomatik özet**: yeni mesaj gönderilmeden önce bağlam min(modelin %75'i,
  100.000 token) eşiğini aşarsa önce özetlenir, sonra mesaj gönderilir. Uzun
  bir ajan görevi sırasında yalnızca güvenli noktada (araç sonuçları
  kaydedildikten sonra, yeni model çağrısından önce) sert eşik aşılırsa
  özetlenip ajan otomatik devam eder (en fazla 3 kez). Akış, araç veya onay
  sırasında asla özetlenmez. Esc ile iptal: mesaj gönderilmez, kutuya geri konur.
- `/compact [odak]` (`/ozet` ile aynı), özet kartında neden/süre; bağlam
  göstergesinde eşik ve "özet yakında" uyarısı.
- Ayarlar: otomatik özet aç/kapa, eşik yüzdesi, üst sınır, özeti üreten model
  (varsayılan deepseek-v4-flash — ölçümde glm-5.3'ten ~4 kat hızlı).
- `tests/test_auto_compact.py` (9 test), `tests/e2e_compact_real_api.py` (gerçek API özet kalitesi).

### Düzeltildi

- Özet isteği akışsızdı; glm-5.3 uzun düşünürken bağlantı kopuyordu → akışlı.
- Pencere kapandıktan sonra gelen arka plan sonucu kapalı veritabanına yazıp hata veriyordu.
- Test paketinde silinmeyen pencereler birikip süreyi 166 sn'ye çıkarıyordu → 30 sn.

## Yayınlanmamış — Otomatik mod

### Eklendi

- **Otomatik mod** (Claude Code'daki Auto'ya denk, kural tabanlı): düzenlemeler ve
  güvenli listedeki komutlar onaysız; riskli/tanınmayan komutlar gerekçesiyle sorulur.
  Onaysız çalışan araç kartlarında "otomatik" etiketi.
- Modlar Claude Code adlarıyla: Manuel · Düzenlemeleri kabul et · Plan · Otomatik;
  `/manuel`, `/kabul`, `/plan`, `/otomatik` komutları (`/onayli` takma ad).
- Korumalı dosyalar (her modda sorulur) ve gizli dosya okuma onayı; gizli dosyalar
  aramaya dahil edilmez.
- Klasörsüz oturuma "Proje klasörü bağla"; klasörsüz sohbette model bu düğmeyi önerir.
- 49 yeni test (`tests/test_auto_mode.py`); gerçek arayüz e2e'ye Otomatik mod adımı (15/15).

### Değişti

- `/otomatik` artık tam Otomatik modu açar (0.2.0'da "Otomatik düzenleme" idi;
  o mod şimdi "Düzenlemeleri kabul et" / `/kabul`). Kayıtlı eski oturumlar
  güvenli eşdeğerine çevrilir.

## 0.2.0 — 2026-10-16 (Aşama 2: Kod ajanı çalışma alanı)

### Eklendi

- Kod ajanı (`src/evren_studio/agent/`): proje klasörüyle sınırlı 8 araç
  (list_files, read_file, search_files, find_files, write_file, edit_file,
  run_command, update_todos), izin politikası (Plan / Onaylı / Otomatik
  düzenleme), ajan döngüsü (adım sınırı, iptal, bağlam kısaltma).
- API istemcisinde araç çağrısı: `tools` gönderimi, akışlı/akışsız
  `tool_calls` birleştirme; yerel araç reddedilirse metin protokolüne
  (`<arac_cagrisi>`) otomatik geçiş.
- Yeni arayüz: oturum listeli sol menü, karşılama ekranı, Markdown +
  sözdizimi renklendirmeli akış, düşünce bloğu, araç kartları, diff'li onay
  kutuları, sağ panel (Görevler, Değişiklikler + geri alma, Dosyalar,
  Terminal), mod/model seçicili yazma kutusu, koyu/açık tema, simgeler.
- Eğik çizgi komutları (/init, /ozet, /plan, /onayli, /otomatik, /model,
  /yeni, /disa-aktar, /yardim) ve `@dosya` ekleme; mesajı düzenleyip
  yeniden gönderme.
- Veritabanı şema v2: `sessions`, `session_messages`, `file_changes`;
  v1 sohbetleri otomatik olarak klasörsüz oturumlara kopyalanır (eski
  tablolar silinmez).
- Komutlar projedeki `.venv`'i otomatik kullanır (PATH başına eklenir).
- Yakalanmamış hatalar `%LOCALAPPDATA%\EVREN-Model-Studio\logs\crash.log`
  dosyasına yazılır ve Türkçe uyarı gösterilir.
- 51 yeni test (araçlar, izinler, metin protokolü, ajan döngüsü, istemci
  araç çağrısı, oturum veritabanı, arayüz uçtan uca onay akışı).

- Ortak geliştirici hafızası: `AGENTS.md` protokolü, motor giriş dosyaları
  (CLAUDE.md, GEMINI.md, Copilot, Cursor, Kilo, Roo, Cline, Windsurf),
  `docs/ai-memory/` (kurallar, kayıtlar, oturum günlükleri, motor profilleri),
  `tools/ai_memory.py`, git ön-commit kancası, `test_ai_memory.py` ve
  `test_source_hygiene.py`. Uygulama ajanı EVREN.md + AGENTS.md'yi birlikte okur.

- Sohbet ekranında çalışan model ve süre: yazma kutusunun üstünde canlı
  durum çubuğu (model · etkinlik · süre · adım), yanıt başlığında canlı sayaç,
  her yanıtın altında kalıcı "model · süre" ve çok adımlı turlarda tur
  toplamı; `auto` için yönlendirilen model (`auto → …`).
- `/` ile açılan tıklanabilir komut listesi (fare, ↑↓, Enter, Esc);
  `/model` seçilince tıklanabilir model listesi.
- Ayarlar: "Varsayılanlara döndür", her alanın yanında varsayılan değer,
  üstte Kaydet; sayfa açılınca değerler yeniden yüklenir.
- Uygulama geneli fare tekerleği koruması (odaksız alan değişmez).
- Gerçek API uçtan uca testleri: `tests/e2e_agent_real_api.py` (8 model,
  2 protokol), `tests/e2e_ui_real_api.py` (gerçek arayüz, 14 kontrol);
  arayüz QA paketi `tests/test_ui_pages.py` (tüm ekranlar, iş parçacığı
  uyarısı denetimi).

### Düzeltildi

- Durum İzleme sayfası arayüzü arka plan iş parçacığından güncelliyordu
  (çökme/donma riski); durdurma arayüzü 10 sn'ye kadar donduruyordu.
- Arka plan görevlerinin sonucu, görev nesnesi çöpe giderse kaybolabiliyordu.
- Ayarlar fare tekerleğiyle farkında olmadan değişiyordu.
- Esc, açık komut listesini kapatmıyordu; LLM'lerin boş satırsız yazdığı
  Markdown listeleri paragraf görünüyordu.
- 7 kaynak dosyada çift kodlanmış (mojibake) Türkçe metinler: arayüzde
  "YanÄ±t bekleniyorâ€¦" gibi görünüyordu (kodlama-ornegi).
- Ayarlar açılışta hiç okunmuyordu (`ConfigStore.load()` çağrılmıyordu).
- `secrets.py` `.gitignore` nedeniyle depoya hiç girmemişti (0.1.x düzeltmesi).
- Açılışta model listesi ana iş parçacığında çekilip arayüzü donduruyordu.

### Kaldırıldı

- Eski Chat, Code Studio ve Sohbetler sayfaları (yerini oturum çalışma
  alanı aldı).

## 0.1.0 — 2026-10-15 (Aşama 1 MVP)

### Eklendi

- EVREN LLM API istemcisi: healthz/readyz (kimliksiz), models, chat
  (akışlı/akışsız), quota, istek durumu sorgusu, şart durumu.
- Hata sınıflandırma ve kurtarma motoru: 10 hata sınıfı, Türkçe
  açıklamalar, Retry-After/artan bekleme (≤3 tekrar), belirsiz sonuçta
  durum sorgusu, imza tabanlı geçmiş çözüm araması.
- Kalıcı bilgi sistemi: ERROR_CATALOG, RECOVERY_PLAYBOOK,
  MODEL_CAPABILITIES, API_COMPATIBILITY, KNOWN_LIMITATIONS, LESSONS_LEARNED,
  EVREN_STATUS_HISTORY + PROJECT_STATE, TASK_CHECKLIST, DECISIONS.
- Windows Credential Manager ile API anahtarı yönetimi (maskeleme dahil).
- Türkçe PySide6 arayüzü: ana sayfa, chat (akış + iptal + geçmiş),
  code studio temeli (dosya ağacı/düzenleyici/kaydet), modeller,
  bağlantı testi, kota, sohbet geçmişi, hata merkezi, durum izleme,
  ayarlar, yardım/tanılama.
- EVREN Durum İzleme Ajanı: 30 dk toplam / 5 dk aralıklı kontrol,
  duyuru sayfası değişiklik tespiti, healthz/readyz/models kontrollerı,
  isteğe bağlı gerçek model testi, Türkçe rapor (kesin/tahmini ayrı),
  yarım kalan izlemeye devam.
- SQLite: sohbetler, mesajlar, hata kayıtları, izleme oturumları/kontrollerı,
  model sağlığı. İş parçacığı güvenli (RLock).
- 53 birim testi + UI duman testi + uçtan uca gerçek API testi (E2E_OK).
- run.bat başlatıcı; pyproject.toml ile kurulabilir paket.

### Doğrulanan gerçek dünya sonuçları (2026-10-15)

- 16 canlı model; glm-5.3 sohbet+akış 200 OK; auto → qwen3.8-flash-next;
  kota ok; istek durumu sorgusu success; 404/401 hata davranışları.
