---
id: 2026-10-19-claude-code-masaustu-mcp-gerektiginde-acma-playwright-hata-be
tarih: 2026-10-19
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, Node.js 24.20.0 (winget), .NET 10
dal: feat/mcp-akilli
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# MCP gerektiğinde açma, Playwright, hata bekçisi, çok dilli Serena

## Görev
Kullanıcı (MCP aşama 1'den sonra):
- Serena Python dışındaki dillerde de çalışmalı.
- Playwright gibi gerçek sunucular eklenmeli.
- Ücretli sağlayıcılarla MCP KESİNLİKLE olmamalı (uygulamanın amacı ücretsiz hizmet).
- MCP ihtiyaç duyulduğunda açılmalı, duyulmadığında kapanmalı.
- EVREN motorları yetenekli değil; amaç sorunsuz, doğru proje geliştirmek. Akla gelmeyenler de uygun şekilde dahil edilsin.

Kararlar: Node.js winget ile sistem geneline; testlerden kalan iki klasör silinsin (yapıldı); "başla".

## Yapılanlar
- **agent/mcp.py:**
  - McpServerConfig'e `when` (her_zaman/kod/web), `idle_seconds`, `diagnostics_tool` alanları; ProjectProfile/needed() ile kod ve web projesi algılama, sembol ve tarayıcı anahtar kelimeleri.
  - McpManager:
    - araç listesi önbelleği (`veri/mcp/cache`);
    - süreç ilk araç çağrısında açılır;
    - boşta kapatma (reap_idle; meşgulken kapatmaz);
    - süreç başlamadan önce `refresh_path`.
  - McpToolset: tembel çağrı, `diagnostics()`, `hints`.
  - Hazır ayarlar yeniden kurulur (configs_from_settings + PRESETS); eski Serena kaydı güncel tanımı alır.
  - Serena:
    - `when=kod`, teşhis aracı `get_diagnostics_for_file` (modele sunulmaz);
    - dil sunucuları ortak kısa (8.3) klasörde: `sitecustomize.py` yaması ve `EVREN_SERENA_LS_DIR`.
  - Playwright MCP 0.0.83:
    - npm ile veri klasörüne kurulur;
    - `--headless --isolated --browser msedge --image-responses omit`;
    - yalnız okuyan 4 araç sormadan çalışır;
    - proje dosyaları ProjectWebServer'dan (127.0.0.1) verilir; gizli dosyalar ve `.git` 403 döner, favicon 204.
- **agent/diagnostics.py (yeni):** hata bekçisi.
  - Yerleşik denetimler: py compile, JSON, TOML, `node --check`.
  - serena_problems: yalnız Error önemindeki kesin kodlar; import/eksik paket ve C# CS0246 gibi ortam kaynaklı hatalar atılır.
- **runner.py:** `edit_check` ayarı ve `_post_edit_check`; istem notu `hints` alır.
- **router.same_provider:** session_view yedek modelleri turun sağlayıcısıyla sınırlar. Bu, gizli bir hatayı da düzeltti (farklı sağlayıcının modeli aynı istemciyle deneniyordu).
- **app_context.mcp_toolset:** `provider != "evren"` ise None; mesaj ve durum geri çağrısı alır.
- **config:** `edit_diagnostics`. Ayarlar: "Hata bekçisi" kutusu.
- **mcp_settings:** hazır ayar satırları (Serena, Playwright) ve "Node.js'i kur (winget)" düğmesi.
- **Testler:**
  - test_mcp_akilli.py (22);
  - e2e_mcp_real_api.py'ye web ve ts görevleri, bekçi sayacı;
  - zorluk paketine bekçi sayacı; `--serena` artık Playwright'ı da açar.
- **Belgeler:** CHANGELOG, DECISIONS 62–67, SECURITY, KNOWN_LIMITATIONS, CHALLENGE_RESULTS, MODEL_CAPABILITIES, README, ILERIDE_YAPILACAKLAR, PROJECT_STATE.

## Test sonuçları
- Tam pytest: **403 passed** (indeks sonrası).
- e2e_mcp_real_api (Auto Pro):
  - 9/10 koşu tam; MCP açık 5/5.
  - soru görevinde MCP kapalı 4/6: iki çağrı kaçırıldı.
  - Bekçinin 6 uyarısının 6'sı gerçek ara hata.
- Zorluk paketi:
  - MCP kapalı + bekçi açık: 12/12.
  - Serena + Playwright açık: 12/12, gereksiz MCP çağrısı yok.
- R-13: E2E_OK · ajan 6/6 · arayüz 15/15.
- Serena dilleri (gerçek): Python, TS, JS, C# ve Java çalıştı; Go kurulu değil.
- Ekran görüntüsü (QT_QPA_PLATFORM=windows): build/shots/mcp_1_kurulu_degil.png ve mcp_2_kurulu_etkin.png (Serena ve Playwright satırları).
- **Doğrulanmadı:**
  - Ayarlar'daki "Node.js'i kur" ve "Playwright'ı kur" düğmelerinin gerçek tıklaması. Kurulum işlevleri betikle gerçek olarak çalıştırıldı; düğmeler birim testle sınandı.
  - Go/Rust.
  - Edge olmayan makinede Chromium indirme yolu.

## Sorunlar ve kayıtlar
- 2026-10-19-auto-pro-yedek-listesi-farkli-saglayicinin-modelini-ayni-ist (çözüldü)
- 2026-10-19-serena-c-dil-sunucusu-windows-260-karakter-yol-sinirina-taki (çözüldü)
- 2026-10-19-yerel-web-sunucusu-turkce-403-iletisinde-yanitsiz-kaldi (çözüldü)
- Playwright `file:` adreslerini engelliyor; tüm diske izin vermek yerine yerel sunucu yazıldı.
- Playwright'ın navigate yanıtı snapshot'ı dosya yolu olarak veriyor; istem notu "yolu okuma, browser_snapshot kullan" der.

## Sonraki motor için notlar
- Yeni MCP hazır ayarı: PRESETS'e ekle; `when` ve okuma listesini dar tut; ücretli sağlayıcı yasağı app_context.mcp_toolset'te.
- Serena sürümünü yükseltirken `sitecustomize` yaması (SolidLSPSettings.ls_resources_dir) yeniden denenmeli.
- Hata bekçisi kod listesini genişletirken yanlış alarm ölç (R-22): eksik paket uyarıları modeli import silmeye itebilir.
- Uzun süren geliştirme sunucusu (npm run dev) desteği yok: ileride arka plan süreç aracı düşünülebilir.
