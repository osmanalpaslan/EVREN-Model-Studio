# DEVİR NOTU — işin şu anki yeri (tüm motorlar ve bilgisayarlar için tek kaynak)

> Kullanıcı farklı bilgisayar ve oturumlardan çalışır; proje hiç askıda kalmamalı.
> **Başlarken:** `tools/ai_memory.py baslangic` bu dosyayı (ve GitHub'daki daha yeni bir çalışma dalı
> varsa onunkini) en üstte gösterir. "Şu an" bölümündeki dala geç, "Kaldığı yer"den devam et.
> **Çalışırken:** her madde/alt adım bitince durumunu burada güncelle (YAPILDI + commit), commit'le ve
> **push et** — yarım iş de `wip:` commit'iyle gönderilir, yalnız bu bilgisayarda iş bırakılmaz (R-35).
> **Bitirirken / ayrılırken:** "Şu an" bölümünü doldur: dal, son commit, yarım kalan tam olarak ne,
> sıradaki adım, çalışan/yarıda kalan uzun test. `src/` değişen commit bu dosyayı da içermek zorunda
> (ön-commit kancası).
> Durumlar: YAPILDI · SÜRÜYOR · SIRADA · BEKLİYOR (kullanıcı kararı/ödeme gerekir).

## Şu an

- **Güncelleme:** 2026-11-13 22:35 · Claude Code (claude-opus-5-5) · masaüstü bilgisayar. 0.5.0 yayında. Dal `surum/0.5.1-istekler`. Madde 22 (hız + doğruluk altyapısı) YAPILDI: A-F + gerçek masaüstü 5/5 (714 → 91 sn) + tam takım 1419 geçti + R-13 (API OK, arayüz 15/15, ajan 6/6 tekrarla; glm geçici) + zorluk 11/12 (mini_proje: modelin ortama bağlı testi, gerileme değil). Tam takımda bulunan gerçek hata (bayat .pyc ile test bekçisi eski kodu koşturuyordu) düzeltildi. Yarım iş YOK. Sırada: kullanıcının yeni isteği; paket/yayın İSTENMEDİ. Koşucu değişti → madde sonunda zorluk paketi TAMAMI (R-21) + R-13. Madde 21 (k)-(r) YAPILDI; masaüstü QA kullanıcı başındayken yeniden koşulacak. Paket/yayın İSTENMEDİ.
- **Aktif dal:** `surum/0.5.1-istekler` (master 9ba3543 üstünde; 0.5.1 istekleri burada birikir).
- **PR birleştirme:** masaüstünde `.claude/settings.local.json` allow `Bash(gh pr merge *)`, `Bash(gh pr edit *)` var →
  motor birleştirebilir. Başka bilgisayarda bu kural yoksa Claude Code engeller: kullanıcıya aynı dosyaya bu iki kuralı
  eklemesini anlat ya da PR'ları GitHub'dan ters sırayla (en üstteki önce) 'Merge pull request' ile birleştirt.
- **Çalışan uzun test:** yok.
- **Kullanıcının çalışma ilkesi (2026-11-03):** "Amacım sağlam, doğru iş ve olabildiği kadar hızlı; doğruluk bir
  tık daha önemli. Sırayı sen belirle." → Her maddede: hedefli test + tetiklenen/tetiklenmeyen (R-22) + kritikse
  mutasyon; ajan/arayüz değiştiyse dal sonunda R-13 üçlüsü + zorluk paketi; her şey geçerse PR'ı motor açar ve
  birleştirir (kullanıcı izni 2026-11-03). Effort: kod/plan rolünde DÜŞÜRÜLMEZ.

### Yeni bilgisayarda başlarken (sırayla)
1. `git pull` (ya da ilk kez: `git clone https://github.com/osmanalpaslan/EVREN-Model-Studio.git`); `kurulum.bat`
   veya INSTALLATION.md ile `.venv`; `.\.venv\Scripts\python.exe tools\ai_memory.py kanca-kur`.
2. `.\.venv\Scripts\python.exe tools\ai_memory.py baslangic` — "Uygulamadan gelen gözlemler" bölümünde
   `! KULLANICIYA BİLDİR` varsa İŞE BAŞLAMADAN kullanıcıya söyle (R-36).
3. EVREN anahtarı o bilgisayarın Credential Manager'ında yoksa gerçek API testleri koşmaz: kullanıcıdan Ayarlar'a
   girmesini iste (anahtarı asla dosyaya yazma).
4. `.\.venv\Scripts\python.exe -m pytest -q` (≈6 dk) geçmeli; sonra aşağıdaki sıradaki maddeye başla.

### Sıradaki maddeler ve planı (motorun belirlediği sıra)
**1) Madde 6 — klasörsüz sohbette yalnız web_search / web_fetch** (tahmin 1,5–3 saat). Bugün klasörsüz oturumda
hiç araç yok: `AgentRunner.agentic` = `workspace is not None`; `_specs()` agentic değilse `[]`; `_execute`
`toolbox is None` ise "proje klasörü yok" döner; `_system()` agentic değilse `build_chat_system()`.
- Plan: runner'a `chat_tools` (yalnız WEB_TOOLS: web_search, web_fetch) ekle; klasörsüz oturumda `_specs()` yalnız
  bunları versin, `_execute` toolbox'suz da WEB_TOOLS'u çalıştırsın (webfetch/websearch dosya sistemine dokunmaz);
  sohbet sistem istemine kısa araç notu; `websearch.needs_web` ipucu sohbet turunda da. Manuel modda sorma ve
  izin düzeni aynı kalsın. session_view'da klasörsüz turda bu aracı aç (ayar: mevcut web araması ayarı).
- Test: klasörsüz turda araç sunuluyor/çalışıyor; dosya araçları SUNULMUYOR; gereksiz tetiklenme yok (R-22);
  R-31 gerçek tur akışı. Gerçek: `tests/e2e_websearch_real_api.py`'ye klasörsüz senaryo (açık/kapalı, R-25) +
  zorluk paketi + R-13.
**2) Madde 9 — sade "Sağlayıcı ekle" ekranı** (tahmin 3–5 saat). Tek liste: EVREN, OpenAI, Anthropic, OpenRouter,
Kilo, OpenAI-uyumlu (taban URL + anahtar). Çok modelli ağ geçitleri tek anahtarla. Mevcut: `api/providers.py`,
`api/openai_client.py` (Responses), `api/anthropic_client.py`, Ayarlar > Ücretli Sağlayıcılar. OpenRouter/Kilo/
OpenAI-uyumlu için Chat Completions istemcisi gerekebilir (EvrenClient zaten OpenAI-uyumlu — genelleştirmeyi
değerlendir). Gerçek anahtar yoksa `verified=False` ve arayüzde "doğrulanmadı" (R-17); ücretli istek YAPMA.
Arayüz değişince `tools/ui_denetim.py <klasör> ikisi --goruntu` (R-05/R-33) ve görüntülere BAK.
**3) Madde 7 — hız (en son)** (tahmin 3–6 saat). Aynı zorluk paketi 2026-11-03/04'te 502–1595 sn arasında oynadı;
kod aynıyken. Önce farklı saatlerde 3 koşu ile EVREN yükünü ayır (adım başına model süresi: model_calls tablosu).
Yalnız doğruluğa dokunmayan kaldıraçlar: gereksiz yeniden okumayı azaltma, salt okunur araçları paralel çağırma,
yanıt vermeyen modelden erken yedeğe geçiş. Her değişiklik zorluk 12/12 + maraton kabulünü korumalı; korumazsa geri al.
**Plan dışı, kullanıcı kararı bekleyen:** Setup.exe paketleme (ILERIDE madde 1; kullanıcı "şimdi değil" demişti);
OpenAI/Anthropic gerçek anahtar doğrulaması (ücretli — yapılmaz).

- **Gözlem ajanı notu:** uygulama kaynaktan çalışırken gözlemleri `gozlem-kayitlari` dalına gönderir; deneme gözlemi
  b12eb83f411c kapalı (kabul-edildi). Bu bilgisayarın yerel kuyruğunda yalnız eşik altı 2 düşük önemli kayıt var
  (503 kapasite, yedeğe geçiş) — gönderilmez, normal.

## Geliştirme sırası (kullanıcı onaylı, 2026-11-01)

Kullanıcı neredeyse yalnız **Auto Pro** kullanıyor; hedef "tam profesyonel uygulama". Her madde: hedefli test +
kritikse mutasyon + paket; R-13/R-21 gerçek ölçümler dal sonunda.

| # | Madde | Durum | Dal / commit | Not / kalan |
|---|---|---|---|---|
| 0 | Taban ölçüm (auto-pro) | YAPILDI | — | zorluk 12/12, proje 5/5, maraton A 10/10 (26 dk), B 13/13 (19 dk), C 10/10 (28 dk; 1. mesaj 21 dk/33 adım) |
| 1 | Açık tema okunurluğu, görünmeyen düğmeler, Ayarlar'daki sabit renkler | YAPILDI | e940402, 5225fc1, 316d69d, 2050af9 | `tools/ui_denetim.py` + `tests/test_okunurluk.py` (R-33); açık/koyu HATA 0 |
| 2 | Ücretsiz web araması (Tavily) + Auto Pro'ya dahil | YAPILDI | 2050af9 | Tavily → anahtarsız Tavily → DuckDuckGo → "eldeki bilgiyle devam"; Ayarlar > Web Araması; R-25 ölçümü CHALLENGE_RESULTS.md |
| 3 | Uzun proje maratonları D (7 mesaj) ve E (PWA) | YAPILDI | 0ced757 | kabul denetimleri bilinen doğru/yanlışla sınandı |
| 4 | Auto Pro bağlam şişmesi (/compact olmuyor, otomatik özet yok) | YAPILDI | b099b7a (+PR #30 /clear, büyük özet) | token tahmini 3,5 → gerçek kullanımla kalibre (R-34). Gerçek: maraton D 25/25 (bağlam ~40k, özet gerekmedi); özetli maraton A (`MARATON_OZET_ESIK=20000`) 10/10, otomatik özet 1 kez tetiklendi ve iş bozulmadan sürdü. Proje görevlerinde sınır aşılırsa görev denetlenir, gerekirse temiz bağlamla yeniden denenir (tasarım gereği) |
| 5 | Kota bitince otomatik devam paneli | YAPILDI | 7314251, 5e70bf1, c1ec1c9 | Normal oturum + Proje/QA/Derin: güvenli noktada dur (kota kapısı / 429), sohbette kart (yenilenme saati, geri sayım, ☑ otomatik devam = Ayarlar `auto_resume`, Şimdi dene/Vazgeç), saatinde kota yoklanır, plan DB'de (açılışta geri gelir), elle mesaj iptal eder; Derin Mod uygulama kapanınca fazdan sürdürülemez (not verilir). Testler: test_kota_devam 8 + test_kota_kapisi, mutasyon. GERÇEK: kotalı maraton A (`MARATON_KOTA_TESTI=2:3`) — 4 araç adımından sonra durdu, kart+plan, gerçek yoklamayla devam, kabul 10/10 (EVREN yavaştı: 77 dk) |
| 6 | Testlerde bulunan hata/eksikler | SÜRÜYOR (1 kalem izleniyor: test_qa_araclari bekçi testi bir kez düştü; 2026-11-12'deki 3 tam koşuda (1114, 1171, 1188) geçti) | — | aşağıdaki liste |
| 7 | Proje bitirme hızı (tutarlılığı bozmadan) | YAPILDI | `feat/hiz-adim-azaltma` (2026-11-04: adım azaltma istemi, tur içi kısaltma, boş yanıtta yedek, çağrı içi damla akış → yedek; zorluk 12/12, maraton F 17/17 özet 3→1; CHALLENGE_RESULTS "Madde 7 hız") — önceki: | KARAR (kullanıcı 2026-11-01): UYARLANABİLİR sıra — kullanıcının sırası varsayılan; öndeki model son 3 saatte yedeğinden 2 kattan fazla yavaşsa o gün yedek öne alınır (YAPILDI: router.choose speeds, modelstats.effective_speeds, test_uyarlanabilir_sira 8, mutasyon). Zorluk paketi (21:20, EVREN yoğun) 8/12: celiski'de yavaşlık geçişi gemma'ya düştü → gemma hile yazdı (DÜZELTİLDİ: SLOW_SWITCH_EXCLUDE), kapsam/mini_proje düzenek hatasıyla iptal (DÜZELTİLDİ), planlama EVREN yavaşlığıyla zaman aşımı. 2026-11-03 tekrar (1117fae): düşen 4 görev 4/4, tam paket 12/12 · 1595 sn (YAPILDI). Kalan: adım sayısı azaltma / hız. Döküm YAPILDI (2026-11-01, maraton A-D + proje ajanı DB'leri): sürenin ~%97'si MODEL BEKLEMESİ; araç/komut toplam 0,3-1,4 dk. deepseek-v4.1-flash çağrı başına ort. 30-85 sn (en uzun 274), qwen3.8-flash-next 15-40 sn. Kaldıraçlar: kod rolünde model sırası (ölçümle), düşünme süresi (reasoning_effort/çıktı uzunluğu), adım sayısı (paralel araç çağrısı, gereksiz okuma), yavaş model erken geçişi (`_slow`). Tutarlılık zorluk + maraton kabulüyle korunur |
| 8 | Derin Mod yeniden ele alınacak | YAPILDI | `feat/derin-mod-v2` | Denetçi 10 yapılandırma / yargıç 11 yapılandırma ölçüldü (CHALLENGE_RESULTS); ikinci denetçi glm-5.3+high, yargıç değişmedi (hepsi 8/8), `high` qwen/deepseek'te kazanç yok; durum çubuğu arka plan fazında görünür (önceden hiç görünmüyordu); Plan modunda ilk yanıt araçsız inceleme niyetiyse dürtülür. Planlayıcı kalitesi ve Anla modeli ÖLÇÜLMEDİ (değişmedi). Eski not: | aşamaya göre en doğru/güçlü EVREN modelleri (ölçümle); çalışırken kısa canlı durum cümleleri; mevcut özellikleri önce kodda doğrula; `e2e_derin_real_api` önce/sonra |
| 10 | Doğruluk turu (kullanıcı 2026-11-03: "doğruluk ve sağlam iş bir tık daha önemli"; sıra: dalı kapat → doğruluk → güvenli hız) | YAPILDI | `feat/dogruluk-turu` | 10a YAPILDI: test dosyası koruması komutla değiştirme/silmeyi de yakalar (kayıt 2026-11-03-test-dosyasi-korumasi-…). 10b YAPILDI (`feat/faz-unutma-olcumu`): faz unutma maraton F'de 4 koşuda üretilemedi, gözleme `devam_zorunlu` eklendi. Sonra: Madde 8 (Derin Mod, aşama başına en güçlü model, `"high"` effort ölçümü); en son Madde 7 hız (önce EVREN yükünü ayır, yalnız doğruluğa dokunmayan kaldıraçlar, kod/plan rolünde effort DÜŞÜRÜLMEZ) |
| 11 | Gözlem ajanı (kullanıcı 2026-11-03): uygulama/geliştirme sırasındaki hata ve anormallikleri temizleyip depoya gönder; geliştirme motoru görüp kullanıcıya bildirsin | YAPILDI | `feat/gozlem-ajani` (98c6cf2 +) | `src/evren_studio/gozlem.py`, `gozlem-kayitlari` dalı, `ai_memory.py gozlem …`, baslangic bildirimi, R-36. Ayrıntı: CHANGELOG "Gözlem ajanı" |
| 9 | Sade sağlayıcı/API anahtarı ekranı | YAPILDI (birleşti: `feat/saglayici-ekle` master'da, 2026-11-12 denetimi) | `feat/saglayici-ekle` | OpenRouter/Kilo/OpenAI uyumlu ağ geçitleri tek anahtarla; Sağlayıcı ekle penceresi + Modelleri getir; modeller seçicide, Auto Pro'ya GİRMEZ; gerçek anahtarla doğrulanmadı (R-17); test_saglayici_ekle 7, mutasyon 2, ui_denetim HATA 0 |
| 12 | Claude Code tarzı arayüz (kullanıcı 2026-11-04 gece): (a) Ayarlar menülere bölünsün (sol menü, ilgili ayar ilgili menüde, yeni ayarlar da oraya) · (b) tasarımın tamamı Claude Code masaüstü gibi (kenar çubuğu düzeni) · (c) GÖREV ZAMANLAYICI: Claude Code masaüstündeki "Scheduled tasks" gibi görülebilen/yönetilebilen yapı · (d) GitHub bağlantısı tarayıcıyla (ücretsiz), entegrasyon | YAPILDI | `feat/claude-tarzi-arayuz` (016185c, 8820a32, 86b098e, ad92072) | Sıra: A Ayarlar → B kenar çubuğu → C zamanlayıcı → D GitHub. Zamanlayıcı başvurusu: code.claude.com/docs/en/desktop-scheduled-tasks (Hourly/Daily/Weekdays/Weekly/Manual/Custom cron ≥1 sa; dakikada bir denetim; uygulama açıkken; kaçırılanlardan son 7 günde TEK telafi; Run now / Active-Paused / Edit / History (atlananlar nedenle) / Delete → oturumlar silinmez). GitHub: `gh auth login --web` (cihaz kodu, tarayıcı) + `gh auth setup-git` |
| 13 | Masaüstü kontrolü (imleçle) ve masaüstü QA (kullanıcı 2026-11-05: "benzer ücretsiz repolardan en iyisini seç") | YAPILDI | PR #43 (birleşti 2026-11-06) | Ajan gerçek 5/5; masaüstü QA geçti (hatalı: hata bulundu, doğru 4/4); VS Code donması (bizim ekran okumamız) düzeltildi; Snapshot 15 → 0,5 sn; masaüstü kontrolü varsayılan kapalı. Zorluk 12/12, tam takım 983/983 |
| 14 | Motor karnesi ve akıllı yönlendirme (kullanıcı 2026-11-06 gece): (a) açılışta hafif yoklama; (b) gerçek kalite birkaç belirlenmiş günde, motorun EN İYİ gününde ölçülsün → her motora gerçek puan; (c) günlük yoklamada zayıf motor → daha güçlü yedeğe geçilsin, Auto Pro sırasını ajan yönetsin; (d) QA olabildiğince hızlı: basit iş dakikalarca sürmesin, motor kötüyse "şu an QA için uygun değil" de ya da en hızlı+doğru motora devret | YAPILDI | PR #43 + #44 (birleşti 2026-11-06) | İlk gerçek karne: qwen 95,5 · deepseek 91,7 · gemma 84,3 (puanlı rollerde sıra qwen → deepseek → gemma). Sonraki ölçüm günlerini kullanıcı belirler (`tools\motor_karnesi.py olc …`). Öneri (kullanıcı kararı): QA'da senaryo başına ~30 model çağrısı → adımları birleştirerek azaltma |
| 15 | QA'yı daha da hızlandır (kullanıcı 2026-11-06: "önerdiğin şekilde yap"): senaryo başına ~30 model çağrısını adımları birleştirerek azalt | YAPILDI (2026-11-07; 69344d1, baf9986, 2c1569a + kısayol düzeltmesi) | `perf/qa-adim-birlestir` | Sonuç: doğru sürüm 14,5 dk 4/4, hatalı 12,5 dk (hata bulundu), ajan 5/5 75 sn; Alt+F4 (AltGr) düzeltmesi wmcp_baslatici. Önceki gerçek QA: senaryo başına 16-21 adım (dosyaları yeniden okuma, her yazmadan sonra Snapshot, yazıyı görsel modele sorma). İstem: tek yanıtta Type+Type+Click+WindowText; ölçüm: e2e_masaustu qa + ajan, önce/sonra |
| 16 | Kurulumlu exe: MIT lisans + ücretsiz imza (kullanıcı 2026-11-07); uygulamanın çalışması için gereken programların kurulumları pakete eklensin | YAPILDI (temiz bilgisayar denemesi GEÇTİ 2026-11-07, 0.4.2) | `feat/kurulum-paketi` | tools/paketle.py + installer/ (PyInstaller onedir, Inno Setup 6, gömülü Python 3.12 / Git / Node LTS / gh, yalnız eksikler kurulur); kendi sertifikayla imza (PFX yedeği Drive EVREN_Anahtarlar). Bu bilgisayarda: sessiz kurulum, yükseltme, kaldırma (veri korunur), duman testi geçti. Kalan: Windows Sandbox'ta (Python/Git/Node YOK) gömülü programların gerçek kurulumu (Git /CURRENTUSER, MSI yönetici izni), GitHub Releases yayını (kullanıcı onayı) |
| 17 | Hız ve performans (kullanıcı 2026-11-07: "hız konusunda takıntılarım var; uygulama hiç hızlı değil") | YAPILDI (2026-11-07): 17A kısa ve öz (PR #49), 17C Derin paralellik 3 + 17E açılış (`perf/acilis-ve-paralel`); 17B gerekçeyle atlandı (adım sayısı zaten 3-6) | — | Analiz CHALLENGE_RESULTS "auto ↔ Auto Pro": asıl yavaşlık EVREN yazma hızı (qwen ~15 token/sn) × cevap uzunluğu; kısa ve öz talimatı token'ı ~yarıya indiriyor; ajan adım sayısı; eşzamanlı istek beklemiyor (paralel iş mümkün) |
| 18 | Açık mod tamamen güncellensin (kullanıcı 2026-11-07: sağ üst düğmeler açık modda neredeyse görünmez, başka ekranlarda da) | YAPILDI (2026-11-07) | `fix/acik-mod` | Kök neden YENİDEN ÜRETİLDİ: uygulama açıkken koyu→açık geçişte simgeler (33 setIcon) ve satır içi renkler (30 setStyleSheet) eski temada kalıyor (icons.clear_cache yetmiyor); ui_denetim her temayı sıfırdan açtığı ve yalnız yazıyı ölçtüğü için kaçırıyordu. Ayrıca açık temada ikincil yazı rengi 4,0-4,4 (115 uyarı) |
| 19 | Auto Pro kalsın mı? (kullanıcı 2026-11-07: "auto'dan daha iyi iş yapamayacaksak silelim") | YAPILDI (2026-11-07; gerçek ölçüm CHALLENGE_RESULTS) | `feat/auto-guvenlik-agi` | Kullanıcı onayı 2026-11-07: seçilebilir motor olarak kaldır, auto + güvenlik ağı. Aynı gün zorluk: auto 12/12 1319 sn, Auto Pro 11/12 1182 sn (berabere); sohbette aynı motor |
| 20 | Derin Modu geliştir/hızlandır + uygulamaya yarayacak açık kaynak depolar (kullanıcı 2026-11-11: "amacına tamamen uygun tam bir uygulama") | YAPILDI (2026-11-12) — A1-A3, B1 (PR #56), B3, B4 (PR #57), C1-C4 + uygulama analizi düzeltmeleri (PR #58), sürüm 0.5.0; B2 gerekçeyle yapılmadı | `feat/a1-json-onarim` … `feat/b3-paralel-gorev` | docs/knowledge/REPO_TARAMASI_2026-11.md: A1 json_repair, A2 ruff, A3 PDF/Word/PowerPoint, B1 yeniden üretme testi, B2 bulgular dosyaya, B3 worktree'de paralel uygulama (CAID), B4 eleştirmen erken durdurma, C1 tree-sitter harita, C2 güncelleme, C3 ses, C4 gerçek terminal |
| 21 | 0.5.1 kullanıcı istekleri — TOPLU (kullanıcı 2026-11-12: "kafamdaki planların tümünü tamamlayınca yeni çıktıyı oluştur ve gereken tüm testleri tamamla" diyene kadar uçtan uca/gerçek API testi, tam takım ve paket YOK; her istek ayrı commit + hedefli test/mutasyon) | SÜRÜYOR — (a) kurulum yalnız bu kullanıcı için, "kimin için" penceresi ve "tüm kullanıcılar" seçeneği kaldırıldı: YAPILDI; (b) döngü bekçisi kalıcı çözüm YAPILDI; (c) girdi düşüşü giderildi + borulanan metne BOM ekleyen hata düzeltildi; (d) uzun oturum açılışı 3 kat hızlı (1,01→0,34 sn; +80→+35 MB; 2265→418 bileşen) YAPILDI; (e) açılış 2 kat hızlı (MainWindow 1,10→0,19 sn) YAPILDI; (f) yeni logo + Türk bayrağına sadık animasyonlar + yıldız geometrisi düzeltmesi YAPILDI; (g) iOS 27 Liquid Glass tasarım dili + komut listesi taşması düzeltmesi YAPILDI; (h) analiz belgesi + öneriler (karar kullanıcıda) YAPILDI; (i) dosya geçmişi sıkıştırma (12,7→6,8 MB) YAPILDI; (j) ekran geçişlerinde yumuşak animasyon YAPILDI; (k) tek 'Sağlayıcılar ve anahtarlar' ekranı (Kilo Code gibi) + anahtarsız yerel sunucu düzeltmesi YAPILDI; (l) Derin Mod: doğrulamadan önce testler gerçekten çalışır (düşen test = onaylı yüksek sorun), alt ajanlara proje haritası, tekrar eden soruların ayıklanması (3 gerçek koşuyla ölçülü); kısa kod istem kuralı; edit_file en yakın bölüm ipucu YAPILDI; (m) SQLite WAL (yazma 3,42 → 0,96 ms; synchronous FULL; ağ sürücüsünde eski kip; VACUUM sonrası checkpoint; yedek notunda geri yükleme sırası) YAPILDI; (n) gözlem 60677e5d4254 (ekransız kipin yazı tipi uyarısı) kapatıldı + Mica değerlendirildi, şimdilik uygulanmadı (DECISIONS) YAPILDI; tam takım + kapsam 2026-11-13 01:29: 1326 testten 1325 geçti, düşen test_gecici_klasor (e2e_saglayici_ekrani geçici klasörü silmiyordu) düzeltildi; testcheck testleri (kapsam %72 → sınanan yollar) YAPILDI; (o) Derin Mod başlangıç ölçümü: testler işten önce de düşüyorsa otomatik sorun/düzeltme turu yok (R-20) YAPILDI; (p) gözlem b8efe202e31e (kapanmış pencerenin gecikmeli yedeği) + start_background_loads (e2e açılışı = uygulama) YAPILDI; gerçek API: zorluk 12/12 520 sn, R-13 E2E_OK + ajan 5/6 + arayüz 15/15, proje 8/8, derin GEÇTİ, sağlayıcı 14/14, web QA 9/9; (q) tekrar eden sorular model gruplamasıyla birleşir (gerçek: 5 → 3) YAPILDI; (r) gece kod incelemesi: klasör bağı koparsa doğrulama çökmez YAPILDI | `surum/0.5.1-istekler` | Kullanıcı "oluştur + tüm testler" deyince: sürüm 0.5.1 → tam takım → zorluk + R-13 (+ değişen alanın e2e'si) → paket + duman → Sandbox → PR → GitHub yayını (onaylı) → kalan madde denetimi |
| 22 | Hız + doğruluk altyapısı (kullanıcı onayı 2026-11-13: "önerdiğin gibi yap, bütün yetki sende, fazlar arası onay isteme"; 0.5.1 TOPLU dalında) — A ölçüm (önbellek isabeti, ilk yanıt, adım, düzenleme hatası, kotaya etki); B önbellek dostu istek düzeni (ölçüm: EVREN önek önbelleği 4-7 kat); C bekçiler (bozma koruması + tanımsız ad, iddia bekçisi, hata düzeltmede önce test); D masaüstü hız (tek pencere okuma, toplu UIA eylemi, otomatik okuma, kilit denetimi); E arka plan (yapılandırılmış çıktı, yedek istek, Derin aday yama); F talimatlar (kişisel kurallar, /hafiza-olustur) | YAPILDI (2026-11-13 22:35) — gerçek masaüstü 5/5 714 → 91 sn (PencereOgeleri + UIEylem seçildi); tam takım 1419; R-13 tamam; bayat .pyc hatası düzeltildi (kayıt 2026-11-13-test-bekcisi-bayat-pyc...). Ayrıntı: analiz + ölçüm YAPILDI; F YAPILDI (kişisel kurallar + /hafiza-olustur kısa doğrulanmış EVREN.md); E YAPILDI (yedek istek; yapılandırılmış çıktı ölçüldü/varsayılan değil; Derin aday yama gerekçeyle yapılmadı); D kod YAPILDI (PencereOgeleri + UIEylem + kilit denetimi; gerçek masaüstü ölçümü sırada); C YAPILDI (bozma koruması, iddia bekçisi, hata düzeltmede önce test ipucu; mutasyon 15/16 + 1 eşdeğer); B YAPILDI (dondurulmuş sabit istem + kuyruk notu; gerçek: tur başı önbellek %45 → %96, 3 tur 155/65 → 72/45 sn); A YAPILDI (önbellek göstergesi + tools/onbellek_raporu.py; ölçüm: EVREN önek önbelleği 4-7 kat, önbellek kotadan düşmüyor) | `surum/0.5.1-istekler` | Sırayla A→F; her faz ayrı commit + test + mutasyon + gerçek API önce/sonra; fayda yoksa geri al |
| 23 | Son 0.5.1 istekleri + ÇIKTI (kullanıcı 2026-11-13 gece: "en uygun haline getir, artık çıktıyı oluşturup dalları birleştirelim, testlerin eksiksiz olduğunu doğrula") — (a) iş sürerken yeni mesaj: kuyruk + çalışan işe iletme (Claude Code gibi) + işlenmemiş mesajı GERİ ÇEKME; (b) auto dışındaki işlerde (iç işler, Derin/Proje/QA rolleri) performansı düşen motordan yedeğe geçiş (gerçek kullanım hata oranı; iç işlerin çağrıları da kayda); (c) EVREN dışındaki API'de tüm otomatik işleyiş (bekçiler, Derin, QA, paralel proje, MCP, iç işler) o API'nin modelleriyle; (d) gözlem c9b5c1591110: ajan komutları UTF-8 ortamıyla (modelin ortama bağlı testi) | SÜRÜYOR — (a) YAPILDI (kuyruk + ara mesaj + geri çekme; 15 test, mutasyon 18/18) | `surum/0.5.1-istekler` | Sıra a → b → c → d; sonra sürüm 0.5.1 → tam takım → zorluk + R-13 + değişen alan e2e → paket + duman → PR + birleştirme → GitHub yayını (kullanıcı onayıyla) |

### Madde 5 planı — kota bitince otomatik devam
Bugün: yalnız Proje/QA/Derin akışında (`project_ui.schedule_auto_resume`, Ayarlar'daki gizli `auto_resume`),
uygulama açıkken QTimer. Normal ajan turunda günlük kota azsa yalnız uyarı → 429 → iş yarıda kalır.
1. Otomatik devam açıksa normal turda kota kapısı güvenli noktada durdurur (`quota_daily`).
2. 429 tükenince (`_on_fail` RATE_LIMIT) de aynı yol.
3. Sohbette kart: "EVREN kotası doldu · yenilenme HH:MM (N dk)" + ☑ "Kota yenilenince otomatik devam et"
   (ayara bağlı, kalıcı) + Şimdi dene / Vazgeç; geri sayım.
4. Saatinde önce `/v1/quota` yoklanır (token harcamaz); yeterliyse oturuma dönüp `_auto_continue`; değilse
   yeniden kurulur; saat bilinmiyorsa 10 dk'da bir.
5. Kalıcı kayıt (DB `pending_resume`): uygulama kapanıp açılınca kart + zamanlayıcı geri gelir.
6. Proje/QA/Derin aynı kartı/kaydı kullanır.
7. Testler: tetiklenen/tetiklenmeyen (kutu kapalı), yoklama yetersiz, yeniden açılış; gerçek: eşik yapay
   yükseltilip maraton A ortasında dur → devam → kabul 10/10.

### Madde 6 — bulunan hata/eksik listesi (yeni buldukça ekle)
- [x] Model zaman zaman İngilizce ara cümle yazıyor (ölçüm: 96 metinli yanıtın 3'ü, hepsi deepseek-v4.1-flash, tur başında). Dil kuralı ara cümleleri kapsayacak şekilde netleştirildi (734fd4c). A/B gerçek ölçüm (deepseek-v4.1-flash, 5'er, reasoning none): eski 0/4, yeni 0/4 İngilizce — sorun bu ölçümde tekrarlanmadı, etkisi DOĞRULANAMADI; dal sonu zorluk paketinde yanıtlar yine sayılacak. 2026-11-04 Madde 7 dalında 3 zorluk koşusunun 77 metinli yanıtında İngilizce cümle 0 (kod dışı metinde ≥2 İngilizce işaret sözcüğü, Türkçe işaret yok) → kapatıldı; yeniden görülürse açılır.
- [x] Plan modunda `web_search`/`web_fetch` açıldı (dosyaya dokunmaz; sorulmadan çalışır, Manuel'de sorulur).
- [x] Klasörsüz sohbet oturumlarında hiç araç yok (web araması da yok) — ayrı özellik: sohbette yalnız web_search/web_fetch sunmak (runner `agentic` değilken araç protokolü + `_execute` toolbox koruması gevşetilmeli). YAPILDI: PR #38 (Madde 6, 2026-11-04).
- [x] deepseek-v4.1-flash bazı adımlarda 30-130 sn bekletiyor (Madde 7 ile birlikte). Kök neden ölçüldü: düşünmeyi akışta göstermiyor (182/396 sn, ~0,5 satır/sn); 2 dk'yı aşan yanıtsız çağrı artık kesilip yedekle sürüyor (DECISIONS #121, `feat/hiz-adim-azaltma`).

- [x] R-05/AGENTS eski `ui_screenshots.py`'yi gösteriyordu → `ui_denetim.py`.

- [x] `test_db_recovery_monitor::test_icerik_degisikligi_tespit_edilir` kararsızlığı: kök neden testte — `start()` ilk kontrolü arka planda yapıyor, test beklemeden sayfayı değiştiriyordu; ilk kayıt beklenir (doğrulama aynı).
- [ ] `test_qa_araclari::test_bekci_bozulan_testi_bir_kez_bildirir` tam koşuda 1 kez düştü (2/3 çağrı; bekçi "düştü" görmedi, 1,7 sn — zaman aşımı değil). Tek başına ve önündeki 12 dosyayla 177/177 geçti; yeniden üretilemedi. Tekrar düşerse sıra bağımlılığı (PATH/ortam değişkeni sızıntısı) ve `testcheck.detect_command` seçimine bak.

## Birleştirmeden önce (zorunlu)
- Tam takım (`pytest -q`, ~4 dk) · R-13 gerçek e2e üçlüsü · R-21 zorluk paketi `auto-pro` (CHALLENGE_RESULTS
  ile karşılaştır) · arayüz değiştiyse `ui_denetim.py ikisi --goruntu`.
- Birleştirmeyi kullanıcı yapar (Claude Code'da "Merge Without Review" engelli): önce PR #30, sonra bu dal.

## Geçmiş
- 2026-11-01: devir düzeni kuruldu (bu dosya, `baslangic` gösterimi, ön-commit kancası, R-35).
