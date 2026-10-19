---
id: 2026-10-19-claude-code-masaustu-mcp-destegi-ve-serena-entegrasyonu
tarih: 2026-10-19
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/mcp
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# MCP desteği ve Serena entegrasyonu

## Görev
Kullanıcı (önceki turdaki MCP araştırmasından sonra): "önerdiğin gibi işlemlere başla ve test et."
Öneri: genel MCP desteği (Ayarlar'da sunucu listesi, araçlar izin sistemine bağlı), ilk sunucu
Serena, Playwright isteğe bağlı sonraki adım; repo dahil etme ayrı konuşulacak.
Dal `feat/mcp`, `feat/klavye-baglam-tema` üstünde (o dal da henüz birleştirilmedi).

## Yapılanlar
- agent/mcp.py (yeni, Qt'siz): kendi stdio JSON-RPC MCP istemcimiz (initialize → initialized →
  tools/list sayfalı → tools/call; sunucunun ping/roots/list isteklerine yanıt; stderr kuyruğu;
  zaman aşımı; çöken sunucu). McpServerConfig (yer tutucular {proje} {veri} {serena}
  {serena_bin} {serena_dir} {serena_home} {PATH}), McpManager (sunucu × proje başına süreç,
  close_all), McpToolset / LazyToolset (ilk kullanımda arka planda başlatır), prompt_section.
- Serena 1.7.0 (MIT; 2.0.0 GPL-3.0 ve 6 günlük → alınmadı) + uv 0.12.20 veri klasöründe ayrı
  venv'e; pyright kurulumda ısıtılır; SERENA_HOME proje başına veri klasöründe → proje
  klasörüne ve ~/.serena'ya yazmaz. Yalnız 3 okuma aracı açık.
- runner.py: `mcp=` parametresi; _specs (Plan modunda yalnız okuma MCP araçları), _spec,
  _run_mcp (okuma listesi dışı → EXEC gibi izin, oturum izni `mcp:<araç>`), hata/başlatma
  notları events.status ile; describe_call MCP adı.
- tools.py: IGNORED_DIRS'e .serena. config.py: mcp_enabled, mcp_servers.
- ui/mcp_settings.py (yeni): Ayarlar kartı — Serena kur/etkin/dene, elle sunucu ekle/aç-kapa/
  kaldır/dene; değişiklik hemen kaydedilir. settings_page: kart + PRESERVED_ON_RESET'e mcp_servers.
- app_context: `mcp` yöneticisi, mcp_configs, mcp_toolset, close'ta close_all.
- session_view: AgentRunner'a `mcp=self.ctx.mcp_toolset(ws.root)`.
- theme.py: işaretli onay kutusuna tik (koyu tema vurgu beyaz olunca boş kare görünüyordu).
- Testler: tests/fake_mcp_server.py, test_mcp.py (21), test_mcp_ui.py (7); gerçek API:
  tests/e2e_mcp_real_api.py (yeni), e2e_zorluk_real_api.py `--serena`.
- Belgeler: SECURITY (MCP bölümü), DECISIONS 57–61, CHANGELOG, README, KNOWN_LIMITATIONS,
  MODEL_CAPABILITIES, CHALLENGE_RESULTS, ILERIDE_YAPILACAKLAR madde 4, PROJECT_STATE.

## Test sonuçları
- Tam pytest: **382 passed** (indeks sonrası).
- Gerçek API (R-13): E2E_OK · e2e_agent 6/6 · e2e_ui 15/15.
- Zorluk paketi (R-21): MCP kapalı 12/12 (503 sn); Serena açık ilk 10/12 (.serena yan etkisi),
  düzeltme sonrası 12/12, gereksiz MCP çağrısı 0 (R-22).
- e2e_mcp_real_api.py: ilk koşu MCP 0 (model Serena'yı seçmedi) → istem yönlendirmesi →
  son koşu 6/6 tam, ".serena proje klasörüne yazılmadı" denetimi dahil. Büyük projede Serena
  açık 4 araç / 23 sn, kapalı 7 araç / 28 sn; araç çıktısı ~yarı.
- Ekran görüntüleri (QT_QPA_PLATFORM=windows): build/shots/mcp_1_kurulu_degil.png,
  mcp_2_kurulu_etkin.png, mcp_tik_crop.png.
- Doğrulanmadı: Serena'nın Python dışı dilleri; Playwright vb. başka gerçek sunucu; ücretli
  sağlayıcılarla MCP; Ayarlar'daki "Serena'yı kur" düğmesinin GERÇEK kurulumu (kurulum işlevi
  betikle gerçek olarak denendi; düğme yalnız sahte kurulum durumu ve birim testle).

## Sorunlar ve kayıtlar
- 2026-10-19-model-serena-araclarini-yonlendirme-olmadan-hic-kullanmadi (çözüldü, R-25)
- 2026-10-19-uvx-python-3-13-kurulumu-appdata-uv-klasorunde-surum-baglant (çözüldü)
- 2026-10-19-mcp-e2e-kabul-denetimi-dogru-cevabi-yanlislikla-dusurdu (çözüldü, R-25)
- 2026-10-19-koyu-temada-isaretli-onay-kutusu-tiksiz-beyaz-kare-gorunuyor (çözüldü)
- 2026-10-19-serena-proje-klasorune-serena-yazip-plan-modu-sozunu-bozdu (çözüldü)
- Test sırasında kullanıcının bilgisayarında kalanlar (benim denemelerim): `%USERPROFILE%\.serena`
  (ilk denemelerin günlükleri/proje listesi) ve `%APPDATA%\uv\python\cpython-3.13.15…`.
  Silinmedi; kullanıcıya söylendi.
- Git nesneleri salt okunur olduğu için e2e betiği eski klasörü silemedi → `_force_remove`.

## Sonraki motor için notlar
- MCP aracı eklerken: okuma listesini dar tut; yazan araç fark kartına girmez (R-20).
- Serena sürümünü değiştirirken lisansa bak (2.x GPL-3.0) ve pyright ısınmasını yeniden dene.
- Yeni ajan aracı = açık/kapalı gerçek API ölçümü + zorluk paketi `--serena` (R-25, R-22).
- Kullanıcı Ayarlar'dan "Serena'yı kur"a basınca gerçek veri klasörüne ~150 MB iner.
