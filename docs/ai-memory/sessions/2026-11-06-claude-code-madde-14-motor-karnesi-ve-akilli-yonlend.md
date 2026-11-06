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
