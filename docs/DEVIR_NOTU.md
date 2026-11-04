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

- **Güncelleme:** 2026-11-04 akşam · Claude Code (claude-opus-5-5) · masaüstü bilgisayar. Eşitlendi (39 commit);
  bu bilgisayarda tam takım 777/778 — kırılan gözlem testi ortam farkıydı (depo ev klasörü altında) → düzeltildi
  (`fix/gozlem-ev-alti-yol`, PR #37 — birleştirme bu bilgisayarda Claude Code sınıflandırıcısınca engellendi,
  KULLANICI birleştirecek). Madde 6 SÜRÜYOR: kod + birim testleri commit'li (`feat/sohbette-web-arama`, #37'nin
  üstünde) — ÖLÇÜMLER TAMAM: sohbet açık/kapalı 2/2·2/2 (CHALLENGE_RESULTS), zorluk 12/12, R-13 E2E_OK · ui 15/15 ·
  ajan 5/6 (bilinen deepseek kaydı). PR #38 açıldı; #37'den sonra kullanıcı birleştirecek.
  Madde 9 KOD+TEST TAMAM (`feat/saglayici-ekle`, #38 üstünde; PR açıldı): ağ geçitleri (OpenRouter/Kilo/OpenAI
  uyumlu), "Sağlayıcı ekle" penceresi, sade Ayarlar. Gerçek anahtarla DOĞRULANMADI (ücretli; R-17). Tam takım
  792/794 — kırılan 2 test tek başına geçti (kararsız, aşağıda Madde 6 listesi). Sıradaki: Madde 7 (hız).
- **Aktif dal zinciri:** `fix/gozlem-ev-alti-yol` (#37) → `feat/sohbette-web-arama` (#38) → `feat/saglayici-ekle`.
  KULLANICI sırayla birleştirir (Claude Code bu bilgisayarda birleştiremiyor). Yeni iş bu zincirin ucundan sürer.
- **Çalışan uzun test:** yok. Önceki son durum: pytest 778/778 · zorluk auto-pro 12/12 (719 sn) · R-13 E2E_OK, ajan 5/6
  (deepseek metin protokolü — açık kayıt 2026-10-17-deepseek-…), arayüz 15/15 · e2e_derin GEÇTİ.
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
| 6 | Testlerde bulunan hata/eksikler | SIRADA | — | aşağıdaki liste |
| 7 | Proje bitirme hızı (tutarlılığı bozmadan) | SÜRÜYOR | (bu commit) | KARAR (kullanıcı 2026-11-01): UYARLANABİLİR sıra — kullanıcının sırası varsayılan; öndeki model son 3 saatte yedeğinden 2 kattan fazla yavaşsa o gün yedek öne alınır (YAPILDI: router.choose speeds, modelstats.effective_speeds, test_uyarlanabilir_sira 8, mutasyon). Zorluk paketi (21:20, EVREN yoğun) 8/12: celiski'de yavaşlık geçişi gemma'ya düştü → gemma hile yazdı (DÜZELTİLDİ: SLOW_SWITCH_EXCLUDE), kapsam/mini_proje düzenek hatasıyla iptal (DÜZELTİLDİ), planlama EVREN yavaşlığıyla zaman aşımı. 2026-11-03 tekrar (1117fae): düşen 4 görev 4/4, tam paket 12/12 · 1595 sn (YAPILDI). Kalan: adım sayısı azaltma / hız. Döküm YAPILDI (2026-11-01, maraton A-D + proje ajanı DB'leri): sürenin ~%97'si MODEL BEKLEMESİ; araç/komut toplam 0,3-1,4 dk. deepseek-v4.1-flash çağrı başına ort. 30-85 sn (en uzun 274), qwen3.8-flash-next 15-40 sn. Kaldıraçlar: kod rolünde model sırası (ölçümle), düşünme süresi (reasoning_effort/çıktı uzunluğu), adım sayısı (paralel araç çağrısı, gereksiz okuma), yavaş model erken geçişi (`_slow`). Tutarlılık zorluk + maraton kabulüyle korunur |
| 8 | Derin Mod yeniden ele alınacak | YAPILDI | `feat/derin-mod-v2` | Denetçi 10 yapılandırma / yargıç 11 yapılandırma ölçüldü (CHALLENGE_RESULTS); ikinci denetçi glm-5.3+high, yargıç değişmedi (hepsi 8/8), `high` qwen/deepseek'te kazanç yok; durum çubuğu arka plan fazında görünür (önceden hiç görünmüyordu); Plan modunda ilk yanıt araçsız inceleme niyetiyse dürtülür. Planlayıcı kalitesi ve Anla modeli ÖLÇÜLMEDİ (değişmedi). Eski not: | aşamaya göre en doğru/güçlü EVREN modelleri (ölçümle); çalışırken kısa canlı durum cümleleri; mevcut özellikleri önce kodda doğrula; `e2e_derin_real_api` önce/sonra |
| 10 | Doğruluk turu (kullanıcı 2026-11-03: "doğruluk ve sağlam iş bir tık daha önemli"; sıra: dalı kapat → doğruluk → güvenli hız) | SÜRÜYOR | `feat/dogruluk-turu` | 10a YAPILDI: test dosyası koruması komutla değiştirme/silmeyi de yakalar (kayıt 2026-11-03-test-dosyasi-korumasi-…). 10b YAPILDI (`feat/faz-unutma-olcumu`): faz unutma maraton F'de 4 koşuda üretilemedi, gözleme `devam_zorunlu` eklendi. Sonra: Madde 8 (Derin Mod, aşama başına en güçlü model, `"high"` effort ölçümü); en son Madde 7 hız (önce EVREN yükünü ayır, yalnız doğruluğa dokunmayan kaldıraçlar, kod/plan rolünde effort DÜŞÜRÜLMEZ) |
| 11 | Gözlem ajanı (kullanıcı 2026-11-03): uygulama/geliştirme sırasındaki hata ve anormallikleri temizleyip depoya gönder; geliştirme motoru görüp kullanıcıya bildirsin | YAPILDI | `feat/gozlem-ajani` (98c6cf2 +) | `src/evren_studio/gozlem.py`, `gozlem-kayitlari` dalı, `ai_memory.py gozlem …`, baslangic bildirimi, R-36. Ayrıntı: CHANGELOG "Gözlem ajanı" |
| 9 | Sade sağlayıcı/API anahtarı ekranı | YAPILDI (birleşme bekliyor) | `feat/saglayici-ekle` | OpenRouter/Kilo/OpenAI uyumlu ağ geçitleri tek anahtarla; Sağlayıcı ekle penceresi + Modelleri getir; modeller seçicide, Auto Pro'ya GİRMEZ; gerçek anahtarla doğrulanmadı (R-17); test_saglayici_ekle 7, mutasyon 2, ui_denetim HATA 0 |

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
- [~] Model zaman zaman İngilizce ara cümle yazıyor (ölçüm: 96 metinli yanıtın 3'ü, hepsi deepseek-v4.1-flash, tur başında). Dil kuralı ara cümleleri kapsayacak şekilde netleştirildi (734fd4c). A/B gerçek ölçüm (deepseek-v4.1-flash, 5'er, reasoning none): eski 0/4, yeni 0/4 İngilizce — sorun bu ölçümde tekrarlanmadı, etkisi DOĞRULANAMADI; dal sonu zorluk paketinde yanıtlar yine sayılacak.
- [x] Plan modunda `web_search`/`web_fetch` açıldı (dosyaya dokunmaz; sorulmadan çalışır, Manuel'de sorulur).
- [ ] Klasörsüz sohbet oturumlarında hiç araç yok (web araması da yok) — ayrı özellik: sohbette yalnız web_search/web_fetch sunmak (runner `agentic` değilken araç protokolü + `_execute` toolbox koruması gevşetilmeli). BEKLİYOR.
- [ ] deepseek-v4.1-flash bazı adımlarda 30-130 sn bekletiyor (Madde 7 ile birlikte).

- [x] R-05/AGENTS eski `ui_screenshots.py`'yi gösteriyordu → `ui_denetim.py`.

- [x] `test_db_recovery_monitor::test_icerik_degisikligi_tespit_edilir` kararsızlığı: kök neden testte — `start()` ilk kontrolü arka planda yapıyor, test beklemeden sayfayı değiştiriyordu; ilk kayıt beklenir (doğrulama aynı).
- [ ] `test_qa_araclari::test_bekci_bozulan_testi_bir_kez_bildirir` tam koşuda 1 kez düştü (2/3 çağrı; bekçi "düştü" görmedi, 1,7 sn — zaman aşımı değil). Tek başına ve önündeki 12 dosyayla 177/177 geçti; yeniden üretilemedi. Tekrar düşerse sıra bağımlılığı (PATH/ortam değişkeni sızıntısı) ve `testcheck.detect_command` seçimine bak.

## Birleştirmeden önce (zorunlu)
- Tam takım (`pytest -q`, ~4 dk) · R-13 gerçek e2e üçlüsü · R-21 zorluk paketi `auto-pro` (CHALLENGE_RESULTS
  ile karşılaştır) · arayüz değiştiyse `ui_denetim.py ikisi --goruntu`.
- Birleştirmeyi kullanıcı yapar (Claude Code'da "Merge Without Review" engelli): önce PR #30, sonra bu dal.

## Geçmiş
- 2026-11-01: devir düzeni kuruldu (bu dosya, `baslangic` gösterimi, ön-commit kancası, R-35).
