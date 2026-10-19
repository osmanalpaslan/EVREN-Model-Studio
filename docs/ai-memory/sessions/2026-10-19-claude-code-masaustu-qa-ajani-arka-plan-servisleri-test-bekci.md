---
id: 2026-10-19-claude-code-masaustu-qa-ajani-arka-plan-servisleri-test-bekci
tarih: 2026-10-19
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, Node.js 24.20.0, Microsoft Edge
dal: feat/qa
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# QA ajanı, arka plan servisleri, test bekçisi, görsel göz

## Görev
Kullanıcı:
- Masaüstü testinden vazgeçti; web kısmı gerçek QA gibi test edilsin.
- Yapılacak sıra: (1) arka plan sunucu aracı, (2) test bekçisi, (3) QA ajanı ve rapor, (4) görsel göz, (5) ek denetimler.
- Kota bekçisi gerekmiyor. "Bugün başka geliştirme yok."
- Ajan bağlı API'yi kullanır; QA yalnız EVREN ile çalışır (MCP kararıyla aynı).

## Yapılanlar
- **agent/services.py (yeni):** ServiceManager ve start_service / service_logs / stop_service.
  - Port hazır olmasını bekler; port çıktıdan da bulunur.
  - PYTHONUNBUFFERED, en fazla 3 servis, süreç ağacıyla kapatma.
- **agent/testcheck.py (yeni):** test komutu algılama (pytest/unittest, npm test, dotnet test, go test).
  - Taban durum ilk yazmadan ÖNCE alınır.
  - Tur başında geçen testler bozulduysa tur sonunda bir kez dürter.
- **agent/qa.py (yeni):**
  - QaState/Scenario, planlama ve senaryo istemleri, `<qa_plan>` ve `<qa_sonuc>` ayrıştırma (bozuk JSON için esnek yedek), rapor, fix_goal.
  - QaTools:
    - visual_check: Playwright ekran görüntüsü mutlak yolla çıktı klasörüne kaydedilir, EVREN görsel modeline sorulur;
    - qa_audit: axe-core erişilebilirlik, performans, güvenlik taraması ve npm audit.
  - QaRunner:
    - kesintide bekler, kotada duraklar, iptalde duraklar;
    - sonuç bloğu yoksa aynı bağlamda "yalnız sonucu ver" turu açar;
    - çalışan servisler istemde gösterilir.
- **runner.py:**
  - Yeni parametreler: services, test_check, no_writes (QA: yazma araçları sunulmaz ve engellenir), extra_tools, final_marker (son işaret yoksa bir kez dürt).
  - _run_service, _test_gate, _test_baseline_once.
- **mcp.py:** axe-core 4.13.0 (Playwright kurulumunda) ve ensure_axe.
- **project.py:** Git.dirty, EVREN_QA_RAPORU.md dosyasını yok sayar.
- **ui/qa_ui.py (yeni):**
  - QaController: /qa, /qa-duzelt, /qa-devam, /qa-durdur.
  - Yalnız EVREN modelleri; Playwright ön koşulu.
  - QaPlanCard, QaDoneCard ("Hataları düzelt" → Proje ajanı).
  - Durum: veri/qa/oturum-N.json.
- **session_view:**
  - Servis yöneticisi proje başına; tur sonunda servisler kapanır, QA çalışırken açık kalır.
  - start_run'a yeni parametreler (no_writes, extra_tools, final_marker); QA mesaj engeli ve çalışma çubuğu etiketi.
- **app_context:** `ai_chat(evren_only=True)`.
- **config/settings:** `test_check` ayarı ve kutusu.
- **composer:** /qa komutları.
- **Testler:** test_qa_araclari.py (12), test_qa_ajani.py (14); gerçek API: tests/e2e_qa_real_api.py (yeni).
- **Belgeler:** CHANGELOG, DECISIONS 68–72, SECURITY, KNOWN_LIMITATIONS, README, CHALLENGE_RESULTS, ILERIDE_YAPILACAKLAR madde 5, PROJECT_STATE.

## Test sonuçları
- Tam pytest: **429 passed** (indeks sonrası).
- e2e_qa_real_api (gerçek EVREN + Edge), 3 koşu:
  - Bilinen hata her koşuda **3/3**, denetimler 9/9.
  - Proje dosyalarına dokunulmadı, servisler kapatıldı.
  - Süre 521 → 277 → 358 sn.
  - Model bilinmeyen gerçek bir eksik de buldu: geçersiz girişte hata mesajı yok.
- Zorluk paketi (servis araçları ve test bekçisi açık): **12/12**, bekçi yanlış uyarısı 0.
- R-13:
  - E2E_OK, arayüz 15/15.
  - e2e_agent 4/6 → 5/6 → 5/6 → 6/6. Düşen tek senaryo deepseek-v4.1-flash metin protokolü; bilinen açık kayıt (2026-10-17), aralıklı, gerileme değil (R-08).
- Görsel göz gerçek: gemma-4-31b sayfayı 1,2 sn'de doğru okudu. axe-core gerçek ihlalleri buldu.
- Ekran görüntüleri (QT_QPA_PLATFORM=windows): build/e2e_qa/qa_1_plan.png ve qa_2_sonuc.png.
- **Doğrulanmadı:**
  - "Hataları düzelt" düğmesinden sonra Proje ajanının düzeltmesi (düğme birim testli).
  - npm audit yolu (test projesinde package-lock yok).
  - Edge olmayan makine.

## Sorunlar ve kayıtlar
- 2026-10-19-playwright-ekran-goruntusu-goreli-adla-proje-klasorune-yazil (çözüldü)
- 2026-10-19-arka-plan-python-sunucusunun-ciktisi-tamponlandigi-icin-port (çözüldü)
- 2026-10-19-qa-senaryosunda-model-sonuc-blogunu-yazmayi-unuttu (çözüldü; üç katman: işaret dürtmesi, sonuç isteme turu, esnek JSON)
- 2026-10-17-deepseek-v4-1-flash-… (açık; bugünkü gözlem eklendi)
- Kendi test hatalarım:
  - PowerShell'de tırnaklı yol `&` ile çağrılmalı.
  - "diyorum" kelimesi niyet dürtmesini tetikledi.
  - Var olmayan klasörü rmtree.
  - `ErrorKind.QUOTA` yok (QUOTA_EXHAUSTED).
- Yeni kural: R-26.

## Sonraki motor için notlar
- QA turları `no_writes=True`. Düzeltme yalnız Proje ajanında; QA ile düzelten ayrı tutulmalı.
- Yapılandırılmış çıktı isteyen yeni gözetimsiz akışta R-26'yı uygula.
- Kullanıcı bugün başka geliştirme istemedi; sıradaki fikirler ILERIDE_YAPILACAKLAR madde 5'te.
