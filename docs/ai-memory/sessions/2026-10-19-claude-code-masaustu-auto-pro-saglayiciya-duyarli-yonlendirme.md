---
id: 2026-10-19-claude-code-masaustu-auto-pro-saglayiciya-duyarli-yonlendirme
tarih: 2026-10-19
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/akilli-yonlendirme
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Auto Pro: sağlayıcıya duyarlı yönlendirme ve iç yapay zekâ işleri

## Görev
Kullanıcı: "EVREN Akıllı"nın adını **Auto Pro** yap. EVREN motorları yalnız EVREN
anahtarı girildiyse görünsün; yalnız OpenAI/Anthropic anahtarında EVREN motorları
ve `auto` çıkmasın; birden fazla anahtarda iş uygun motora gitsin. Uygulamadaki
her yapay zekâ destekli iş bağlı API üzerinden çalışsın; önerilen alanları
bağla. Sonunda gönder ve birleştir. Kararlar (AskUserQuestion): maliyet politikası
**Dengeli**; yalnız ücretli anahtarda da Auto Pro **var**; yeni iç işler: oturum
başlığı, Hata Merkezi açıklaması, commit mesajı önerisi.

## Yapılanlar
- agent/router.py: `AUTO_PRO_ID="auto-pro"`, eski "akilli" → taşınır
  (`normalize_model_id`, config.migrate_raw). EVREN_ROUTES (ölçülmüş) + PAID_ROUTES
  (doğrulanmadı); `chain_for(rol, available)` dengeli birleştirme
  (`PAID_FIRST_ROLES = plan, inceleme, gorsel`). Yeni roller: baslik, commit, hata.
- ui/app_context.py: `available_providers()`, `chat_models()` (anahtara göre),
  `available_model_ids()`, `ai_route(rol)`, `ai_chat(rol, mesajlar)` (zincir,
  bütçe atlama, maliyet kaydı, `reasoning_effort: none`, boş yanıtta yedek),
  `REASONING_EFFORT_MODELS`, auto-pro için model_info/provider_of.
- ui/session_view.py: model listesi/anahtar kartı sağlayıcıya göre; özet ve
  kapsam denetimi `ai_route`; otomatik oturum başlığı (`_maybe_auto_title`,
  ayar `ai_session_titles`, test ortamında `EVREN_STUDIO_NO_AI_TITLE`); hata
  kartında "Yapay zekâ ile açıkla"; `load_live_models()`.
- ui/project_ui.py + agent/project.py: inceleme ve commit mesajı `ai_chat` ile;
  `ProjectHooks.commit_message`; EVREN anahtarı yoksa kota beklemesi yok.
- ui/sidebar.py + main_window.py: EVREN anahtarı yoksa Modeller, Kullanım ve Kota,
  Durum İzleme, Bağlantı Testi gizlenir.
- ui/usage_popup.py: EVREN kotası yoksa çip ücretli harcamayı ($) gösterir.
- ui/composer.py: "Otomatik yönlendirme" grubu, görünen ad "Auto Pro"
  (`DISPLAY_NAMES`), alt bilgi "Auto Pro'nun seçtiği sağlayıcıya".
- ui/settings_page.py: "Oturum başlığını yapay zekâ üretsin" kutusu.
- app.py: açılışta canlı model listesi arka planda.
- Dokümanlar: CHANGELOG, README, DECISIONS 51–54, KNOWN_LIMITATIONS,
  ILERIDE_YAPILACAKLAR madde 3, PROJECT_STATE, CHALLENGE_RESULTS, AGENTS.md test satırı.

## Test sonuçları
- Birim: tests/test_auto_pro.py (yeni), test_router, test_default_auto,
  test_project_ui, test_ui_pages, test_providers, test_sidebar_fixes güncellendi.
  Tam pytest: **348 passed** (commit öncesi).
- Gerçek EVREN API (R-13, R-21), Auto Pro ile:
  zorluk paketi **12/12** (301 sn, yakalanmamış hata 0);
  Proje ajanı uçtan uca durum=bitti, 6 commit, kabul **5/5** (331 sn);
  e2e_agent 2/2 · e2e_ui 15/15 · e2e_real_api E2E_OK.
  `reasoning_effort` düzeltmesinden sonra başlık/hata/commit iç işleri doğrudan
  denendi: hepsi dolu yanıt. Proje testi düzeltmeden sonra yeniden çalıştırıldı
  (commit mesajları yapay zekâdan: 6/6 dolu). İlk sayımda kabul 4/5 çıktı; neden
  tests/e2e_proje_real_api.py'nin `PYTHONIOENCODING`'i alt sürece sızdırmasıydı
  (üretilen proje normal ortamda 12/12 test geçiyor). Betik düzeltildi (temiz ortam,
  commit sayacı tam mesajı okur) → aynı projede kabul 5/5.
- Ekran görüntüsü (R-05, QT_QPA_PLATFORM=windows): yalnız EVREN → listede Auto Pro +
  EVREN modelleri; yalnız Anthropic (sahte anahtar) → EVREN sayfaları gizli,
  Auto Pro (Anthropic) + Claude modelleri, kullanım çipi "$0,37". İlk çekimde
  listede "auto-pro" kimliği ve taşan alt bilgi görüldü, düzeltildi.
- **Doğrulanmadı:** OpenAI/Anthropic ile gerçek yönlendirme (anahtar yok; R-07, R-17).

## Sorunlar ve kayıtlar
- 2026-10-19-evren-dusunen-modelleri-kisa-ic-yapay-zeka-isteklerinde-bos (çözüldü)
- 2026-10-19-dugme-lambdasi-clicked-in-checked-degeriyle-varsayilan-argum (çözüldü)
- 2026-10-19-canli-model-listesi-yalniz-modeller-sayfasi-acilinca-yukleni (çözüldü)
- Yeni kural: R-24.
- Otomatik başlık, sahte istemcili 4 testte senaryo sırasını kaydırdı → conftest'te
  `EVREN_STUDIO_NO_AI_TITLE=1` (testler kendi başlık testinde açar).

## Sonraki motor için notlar
- Uygulamanın kendi yapay zekâ işi eklenecekse `AppContext.ai_chat(rol)` kullan,
  rolü router.EVREN_ROUTES ve PAID_ROUTES'a ekle (R-24).
- PAID_ROUTES gerçek anahtarla ölçülmeli; ölçünce `PAID_ROUTES_VERIFIED` ve
  MODEL_CAPABILITIES.md güncellenmeli.
- Varsayılan motor hâlâ `auto` (EVREN anahtarı varken); yalnız ücretli anahtarda
  seçili model kendiliğinden Auto Pro'ya düşer.
