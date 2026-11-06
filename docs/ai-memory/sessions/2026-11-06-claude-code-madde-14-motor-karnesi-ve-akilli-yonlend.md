---
id: 2026-11-06-claude-code-madde-14-motor-karnesi-ve-akilli-yonlend
tarih: 2026-11-06
motor: Claude Code
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/motor-karnesi
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 14 motor karnesi ve akilli yonlendirme

## Görev
Kullanıcı 2026-11-06 gece: motorlar sürekli eğitiliyor, günlük performans değişiyor. (a) Açılışta hafif yoklama;
(b) gerçek kalite birkaç belirlenmiş günde, motorun EN İYİ gününde ölçülsün → her motora gerçek puan; (c) günlük
yoklamada zayıfsa daha güçlü yedeğe geçilsin, Auto Pro motorlarını ajan yönetsin; (d) QA olabildiğince hızlı (basit iş
dakikalarca sürmesin; motor kötüyse "QA için uygun değil" de ya da en hızlı+doğru motora devret). Motorlar BAKIMDA:
gerçek API testi YOK, kullanıcı "başlat" diyene kadar; birlikte deneme 2026-11-06 19:00-20:00.

## Yapılanlar
- Kök neden bulgusu: `qa_ui._evren_model` `router.choose(role)`'u sağlık/hız/ceza bilgisi OLMADAN çağırıyordu → QA hep
  sabit tablonun ilk motorunu (deepseek-v4.1-flash) aldı; 2026-11-05 gerçek QA'da süre %84 model beklemesiydi.
- `agent/karne.py` (yeni): `day_state`/`weak_models` (son 2 saatteki yoklama: hata, normalinin 3 katı ve ≥8 sn, geçmiş
  yoksa >30 sn → zayıf), `score_report` (zorluk raporu → 0-100; doğruluk %80, hız %12, kararlılık %8),
  `best_scores` (iyi-gün ölçümlerinin en yükseği), `card`.
- `db.py`: `model_scores` tablosu (yalnız ekleme), `add_model_score`, `model_scores`.
- `router.py`: `choose(scores=, weak=)`; puan yalnız `SCORE_ROLES`'ta ve ≥2 aday puanlıysa (puansızın yeri sabit);
  zayıf → sağlamların arkasına, gerekçe notta; SLOW_SWITCH_EXCLUDE zayıflıkla öne geçmez; hız kuralı zayıfı öne almaz;
  yeni `qa` rolü (qwen3.8-flash-next → deepseek-v4.1-flash, gemma yok).
- `app_context.py`: `ai_route(evren_only=)`, `model_scores`, `model_weak`, `qa_readiness`; `session_view` rotası
  puan+zayıflık geçirir.
- `qa_ui.py`: QA motoru `ai_route("qa", evren_only=True)` (seçim gerekçesi notta); QA motorlarının hepsi zayıfsa
  uyarı, aynı komut 5 dk içinde yeniden → başlar.
- `qa.py`: `scenario_range` — kısa istek 2-4, orta 3-7, kapsamlı 6-12, "en fazla N senaryo" → N.
- `tools/motor_karnesi.py` (yeni): `goster`, `olc <model> [--zorla]` (önce yoklama; iyi gün değilse ERTELENİR),
  `iceri-al <rapor> <model>`.

## Test sonuçları
- test_motor_karnesi 25/25 (yoklama, puan, kalıcılık R-03, yönlendirme, senaryo sayısı, R-31 QA ekran akışı, araç).
- Mutasyon: karne 10/10, router 7/8 + 1 EŞDEĞER ("tek puanla da sıralar": tek elemanı sıralamak no-op), qa_ui 4/4.
- Risk paketi (router, auto_pro×3, qa×2, ayarlar, kaynak temizliği) 122/122. Tam takım **974/974, 6 dk 22 sn**.
- GERÇEK API: ÇALIŞTIRILMADI (kullanıcı: motorlar bakımda). Madde 13 QA e2e da durduruldu (27 dk'da 34 mesaj).

- 18:22 gerçek yoklama: qwen3.8-flash-next 1,1 sn · deepseek-v4.1-flash 13,2 sn (ilk parça 12,2) · gemma-4-31b ağ
  hatası → bugün zayıf. Veritabanında yoklama geçmişi yoktu → her motor "bilinmiyor" → karne ölçümü HİÇ yapılamazdı.
  Düzeltme: geçmişsiz ama sağlıklı ve ≤30 sn → "ilk" (ölçülür, sayılır; puan en iyi gün olduğu için güvenli). Mutasyon 1/1.
- 18:22-19:04 masaüstü QA e2e kullanıcı isteğiyle ZORLA durduruldu: "ekran kullanımı başladıktan birkaç dakika sonra VS
  Code yanıt vermiyor, tıklayınca kapanıyor". Windows olay kaydı (Application Hang 1002): 30 günde Code.exe 5 askı —
  11-05 19:50, 21:59, 23:50, 11-06 18:53, 19:03 — HEPSİ masaüstü testlerinde; öncesinde hiç yok. Mekanizma: Snapshot
  her taramada tüm pencerelere UIA ile giriyor; VS Code (Electron) erişilebilirlik ağacını (çok uzun Claude Code sohbeti)
  ana iş parçacığında kurup donuyor. DÜN "askıdaki VS Code Snapshot'ı kilitliyor" teşhisi SIRASI TERSTİ: Snapshot VS
  Code'u askıya alıyordu. (LL kancaları tüm girdiyi geciktirirdi; yalnız VS Code'un donması onunla açıklanmıyor.)
  Düzeltme: `desktop_skip_processes` (varsayılan Code.exe, Cursor.exe, Windsurf.exe; Ayarlar > Bu bilgisayar) →
  `WINDOWS_MCP_EXCLUDE_PROCESSES` → başlatıcı pencere listesi + ön plan + ağaçta hiç dokunmaz. Gerçek doğrulama: 6
  Snapshot (14-21 sn) boyunca VS Code'a 0,5 sn'de bir WM_NULL: en kötü tepki 0 ms, askı 0; çıktıda yalnız görev
  çubuğu düğmesi. Düzeltmesiz deneme BİLEREK yapılmadı (oturum VS Code içinde, kapanırdı). Test + mutasyon 2/2.

- 19:58-21:20 masaüstü QA gerçek denemesi (d1fd6c6): GEÇTİ — hatalı 3 kaldı (doğru teşhis), doğru 4/4 geçti. VS Code 2
  sa askı 0. Yeni yanlış alarm: "Click 6 kez" (farklı sayı yazıp Topla'ya basmak) → başarılı masaüstü eylemi DİĞER tüm
  masaüstü sayaçlarını sıfırlar; aynı eylemin değişikliksiz tekrarı yine yakalanır. Test + mutasyon 4/4.

- 21:40 Zorluk auto-pro (8ae59fe): **12/12 · 973 sn** (önceki 12/12 · 1027) · test_araci_ac 0/59 çağrı (R-22/R-25
  tetiklenmeme) · mini_proje 5/5 ama 6 dk sınırında "cancelled", bekçi 2. R-13: e2e_ui 15/15 · e2e_agent 4/6 (glm-5.3
  EVREN 503, deepseek+qwen 4/4) · e2e_real_api glm-5.3 503 (sunucu; önceki koşularla aynı).
- Kullanıcı: "QA çok uzun; hızlandırma yoksa masaüstünü varsayılan açık bırakmayalım". Ölçüm: Snapshot'ın paket içi
  taraması 0,48 sn, araç olarak 15 sn → fark sunucunun KENDİ AI ışığı katman pencerelerini aynı süreçten UIA ile
  okuması. Başlatıcı kendi pencerelerini atlıyor → gerçek sunucuda **Snapshot 15 sn → 0,5 sn**. QA'nın kalan süresi
  model beklemesi (~30 çağrı/senaryo). Karar: `auto_desktop_tool` varsayılan KAPALI (ajan masaüstünü kendiliğinden
  açmaz; /qa-masaustu ve Bağlayıcılar'da elle açma açık istek). Testler + mutasyon 3/3 + 1/1; ui_denetim HATA 0.

- 22:00-22:41 İLK GERÇEK KARNE ÖLÇÜMÜ (master 5329fcb sonrası, dal fix/karne-ilk-olcum): qwen 12/12 801 sn → 95,5 ·
  deepseek 12/12 1093 sn → 91,7 · gemma 10/12 450 sn → 84,3. Bulunan 3 hata düzeltildi: hız eşiği 60 → 20 sn (tavan
  etkisi), hız tam geçme oranıyla ölçeklenir (gemma deepseek'i geçiyordu), yoklama 400'de `reasoning_effort` olmadan
  yeniden dener (gemma haksız ertelendi). Puanlar aynı raporlardan yeniden hesaplandı (yalnız bu 3 kayıt). Testler +
  mutasyon 4/4. Sonuç: puanlı rollerde Auto Pro sırası qwen → deepseek → gemma.

- 22:58 Madde 15 (kullanıcı: QA'yı daha da hızlandır): bugünkü QA kaydı senaryo başına 16-21 adım — her senaryo
  dosyaları yeniden okuyor, her Type'tan sonra ayrı Snapshot, yazıyı visual_check'e soruyor. desktop_scenario_prompt +
  DESKTOP_PROMPT: tek yanıtta Type+Type+Click+WindowText, bir Snapshot, dosyaları yeniden okuma, visual_check yalnız
  görünüm. Sabitleyici test. Ölçüm: e2e_masaustu qa (önce: hatalı 40 dk'da 3 senaryo, doğru ~38 dk 4 senaryo).

- 23:00-00:00 Madde 15 ölçüm 1 (69344d1): GEÇTİ — hatalı 4/4 senaryo bitti (hata bulundu) 39,3 dk / 78 model çağrısı;
  doğru 4/4 geçti 33,6 dk / 75 çağrı. Önce: hatalı 40 dk'da 3 senaryo, doğru ~38 dk. Senaryo 1: 1,6 dk (önce ~10-15).
  Kalan: plan 3-4. senaryolara çok deneme sıkıştırdı (20 / 32 adım) ve denemeler arası Snapshot sürdü → ek: senaryo TEK
  konu, en fazla 4 deneme (MAX_TRIES); denemeler arası Snapshot yok. Ölçüm 2 sürüyor.

- 00:13-01:14 Madde 15 ölçüm 2 (baf9986): toplam 61 dk (ölçüm 1: 73 dk), 120 model çağrısı (ölçüm 1: 153). Hatalı
  sürüm 4/4 senaryo ~24 dk (ölçüm 1: 39,3), hata bulundu (3 kaldı). Doğru sürüm ~37 dk, 2/4 "kaldı" — İNCELENDİ, ikisi
  de deneme uygulamasının GERÇEK kusuru (QA kanıtıyla): 0.1+0.2 → "0.30000000000000004" ve 400 haneli sayıda
  yakalanmayan OverflowError (etiket eski kaldı, hata mesajı yok); ayrıca hata durumunda erişilebilir ad güncellenmiyordu
  (WindowText bayat). Düzeltme yalnız tests/e2e_masaustu_real_api.py deneme uygulamasında: Decimal ile kesin toplama,
  inf/nan reddi, 30 hane sınırı ("Hata: sayı çok büyük"), hata metni erişilebilir ada da yazılır; e2e'ye `qa-dogru` /
  `qa-hatali` kipleri (yarıyı yeniden koşmak için). Elle 19 uç değerle sınandı (hatalı sürüm hâlâ çıkarma yapar).
  Kabul ölçütü gevşetilmedi (doğru sürümde 0 kaldı).

- 01:20-01:47 Madde 15 ölçüm 3 (düzeltilmiş deneme uygulaması): doğru sürüm 4/4 geçti 871 sn (kurulum dahil, önce ~38
  dk); hatalı sürüm 747 sn, 3/4 kaldı (hata bulundu; önce 40 dk'da 3 senaryo). Masaüstü ajanı 4/5: "pencere kapandı"
  KALDI. Kök neden (elle üretildi): Windows-MCP 0.8.8 `Desktop.shortcut` → uia.SendKeys("{Alt}{F4}") her tuşu
  ExtendedKey ile basıyor → Alt = sağ Alt = Türkçe klavyede AltGr → pencere kapanmıyor; aynı tuşlar bayraksız
  keybd_event ile → kapandı. Ajan da kapanmayı `use_ui_tree=false` Snapshot ile "doğruladı" (bu kip pencere listesini
  hiç okumaz, hep "No windows found"). Düzeltme: wmcp_baslatici.patch_shortcut (değiştiriciler bayraksız basılı tutulur,
  bırakma finally'de; tek tuş/çözülemeyen tuş özgün yola), DESKTOP_PROMPT: kapanmayı WindowText ile doğrula. Testler +4,
  hedefli 97 geçti, mutasyon 5/5. Gerçek ajan yeniden: 5/5, 75 sn (önce 153 sn), Shortcut alt+F4 + WindowText doğrulama.

## Sorunlar ve kayıtlar
- Yama betiğinde bash heredoc + `\\b` → kontrol karakteri (R-29 yeniden). Write aracıyla düzeltildi; sonraki yamalar
  yalnız Edit/Write.

## Sonraki motor için notlar
- 2026-11-06 19:00-20:00 (kullanıcıyla): önce Madde 13 kalanları (feat/masaustu-kontrol: QA e2e, zorluk, R-13, PR),
  sonra Madde 14: `tools\motor_karnesi.py olc qwen3.8-flash-next deepseek-v4.1-flash gemma-4-31b` (motor başına
  ~10-15 dk, iyi gün değilse ertelenir), zorluk auto-pro + QA e2e ile önce/sonra ölç (R-21/R-22).
- Doğrulanmadı: yoklama eşikleri (3 kat, 8 sn, 30 sn) gerçek dağılımla ayarlanmadı; puan ağırlıkları gerçek
  raporla sınanmadı.
- 18:20 Modeller ekranına "Motor karnesi" kartı (gerçek puan, iyi gün/ölçüm, son ölçüm, bugünkü yoklama) ve "Sıra durumu"na "bugün zayıf" eklendi; test 1 (R-03 kayıt→ekran); ui_denetim iki tema HATA 0 (açık 116 UYARI, hepsi önceden var olan kenar çubuğu yazıları), görüntülere bakıldı.
