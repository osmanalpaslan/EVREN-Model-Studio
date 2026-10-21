---
id: 2026-10-21-claude-code-masaustu-derin-mod-plan-bekcisi-uzun-isler-kota-k
tarih: 2026-10-21
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/derin-mod
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Derin Mod, plan bekçisi, uzun işler, kota kapısı ve kenar çubuğu

## Görev
Kullanıcı (2026-10-21): (1) çok uzun istemde ajan fazlara böldüğü işte bir fazı bitirince sonrakine
geçmeyi unutuyor — bunu otomatik çözen bir yapı; (2) Claude Code'daki ultracode benzeri ayrı bir mod;
(3) daha fazla EVREN API anahtarı gerekir mi (konuşuldu: hayır, şartlar yasaklıyor); (4) sol kenar çubuğu
genişletilince kayboluyor ("geçmişte de düzelmemişti"); (5) 90 dakikayı aşan testler için çözüm. Kararlar
(AskUserQuestion): bekçi + Proje önerisi; Derin Mod düğmeyle açılır, açıkken her iş; çubuk genişliği
hatırlansın, EVREN koşullarını oku, artık log dosyasını sil. Son onay: "bu planla (uzun iş aracı, kota
kapısı ve otomatik sürdürme dahil) toplu uygulamaya başla; bitince gönderip birleştir".

## Yapılanlar
- Kenar çubuğu: gerçek kök neden (orta QStackedWidget'ın en küçük genişliği) → `CENTER_MIN`, uzun etiket
  kaydırma, en küçük pencere, genişlikler hatırlanır (`main_window.py`, `composer.py`, `config.py`).
- Plan bekçisi (`agent/planguard.py`, `runner.py`, `prompts.py`), Proje ajanı önerisi kartı
  (`transcript.ChoiceCard`, `session_view._offer_project`), adım sınırında en çok 2 otomatik devam; "yalnız
  plan" isteğinde devre dışı (zorluk paketiyle bulunan yanlış tetiklenme).
- Uzun işler (`agent/jobs.py`, `tools.py` start_job/wait_job/job_status/stop_job, `runner._run_job`,
  `app_context.jobs`, oturumda bitiş notu + bildirim).
- Kota kapısı (`agent/quota.py`) ve kota sonrası otomatik sürdürme (`project_ui.schedule_auto_resume`,
  Proje/QA/Derin).
- Derin Mod: `agent/deep.py` (arayüzsüz salt okunur alt ajanlar — onay anında RET, paralel yürütücü,
  anla/planla/yargıç/doğrula/çekişmeli karar/rapor), `ui/deep_ui.py` (DeepController), composer "Derin"
  düğmesi, `/derin`, `/derin-durdur`, Esc; ProjectController'a `present_plan`, `finished_hooks`,
  `evren_only`.
- `services.py` okuyucu yarışı düzeltmesi; Ayarlar'da yatay taşma (açılır liste) düzeltmesi; Ayarlar
  onay kutuları (plan bekçisi, Proje önerisi, otomatik sürdürme).
- EVREN `/v1/terms/text` okundu → API_COMPATIBILITY.md; artık `evren_sidebar_debug.log` silindi (0 bayt, onaylı).
- Belgeler: CHANGELOG, DECISIONS #73-81, SECURITY, KNOWN_LIMITATIONS, README, ILERIDE (madde 6),
  PROJECT_STATE, CHALLENGE_RESULTS. Kural R-27.

## Test sonuçları
- Yeni birim testleri: kenar çubuğu sürükleme 9 (eski kodda hepsi düşer), plan bekçisi 15+7, uzun işler 5,
  kota kapısı 7, Derin Mod 11.
- Tam pytest: son koşu 483/483 geçti. Önceki koşularda `test_mcp_ui` bir kez düştü (tek başına 7/7,
  ortam kaydı) ve ai_memory testi bu günlük doldurulmadan düştü.
- R-13: e2e_real_api E2E_OK; e2e_agent 6/6; e2e_ui 15/15.
- Derin Mod gerçek API: GEÇTİ (anla 3/3, 2 plan + yargıç, bilinen yanlış/doğru değişiklik ayrımı doğru).
- Plan bekçisi gerçek API A/B/C: yanlış tetiklenme 0; kısa denemelerde unutma yeniden üretilemedi.
- Zorluk paketi auto-pro: 11/12 (planlama düştü → düzeltildi) → 11/12 (planlama 5/5; mini_proje zaman
  sınırı → tek başına 2/2 geçti). Serena açık koşu: 12/12 (535 sn).
- Ekran görüntüleri (QT_QPA_PLATFORM=windows, koyu + açık): Derin düğmesi, öneri kartı, Derin plan kartı,
  çalışma çubuğu etiketi, Ayarlar onay kutuları — bakıldı.

## Sorunlar ve kayıtlar
- 2026-10-21-kenar-cubugu-suruklenince-kayboluyordu-orta-yiginin-en-kucuk
- 2026-10-21-kenar-cubugu-icin-splitter-da-hata-yok-iddiasi-surukleme-den (eski kayda düzeltme notu)
- 2026-10-21-ajan-cok-fazli-iste-faz-bitince-sonrakine-gecmeyi-unutuyor (izleniyor)
- 2026-10-21-plan-bekcisi-yalniz-plan-yaz-kod-yazma-isteginde-ajani-plani
- 2026-10-21-alt-surecler-yuk-altinda-ara-sira-bos-ciktiyla-donuyor-bu-bi (ortam)
- 2026-10-21-kota-kapisi-bekleme-dongusu-kayan-noktada-sonsuz-donebilirdi
- 2026-10-21-ayarlar-sayfasi-uzun-acilir-liste-yuzunden-yatay-kayiyordu
- 2026-10-21-bash-heredoc-icindeki-python-yamasi-regex-teki-b-yi-geri-sil

## Sonraki motor için notlar
- Derin Mod'un tam arayüz akışı GERÇEK API'de uçtan uca koşulmadı (fazlar ayrı ayrı gerçek API'de, akışın
  tamamı sahte modelle). Kullanıcı ilk gerçek kullanımda raporu (`EVREN_DERIN.md`) paylaşırsa bak.
- Plan bekçisinin yararı gerçek API'de gösterilemedi (kısa görevlerde model unutmadı); unutma uzun
  oturum + özet sonrasında bildirildi. Tekrar bildirilirse oturum kaydında özet anına bak.
- Kullanıcının hazırladığı ama ajanın hiç güncellemediği plan dosyası bekçiye görünmez (bilerek).
- Ek EVREN anahtarı ÖNERME: şartlar §2 anahtar paylaşımını ve kota atlatmayı yasaklıyor.
- Bu bilgisayarda alt süreç testleri ara sıra boş çıktıyla düşebiliyor: önce tek başına yeniden çalıştır.
