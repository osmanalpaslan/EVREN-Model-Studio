---
id: 2026-11-07-claude-code-madde-16-kurulumlu-exe-mit-kendi-imza-go
tarih: 2026-11-07
motor: Claude Code
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/kurulum-paketi
sonuc: kismi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 16 kurulumlu exe (MIT, kendi imza, gomulu programlar)

## Görev
Kullanıcı (2026-11-07): uygulamayı MIT lisans ve imza ile kurulumlu exe'ye çevir; ücretsiz imza yolu seçildi.
"Başlamadan önce uygulamanın çalışmasına/işlem yapmasına engel olan, inmesi gereken programlar var mı? Varsa
kurulum paketine gerekli program setuplarını ekle."

## Yapılanlar
- Harici bağımlılık taraması (koddan): uygulama çekirdeği pakete gömülü (Python, PySide6, httpx, keyring…).
  Özellik başına gereken: Python 3.12 (ajanın Python projeleri, Serena/Windows-MCP kurulumu), Git, Node.js LTS
  (Playwright/web QA, npm, godot-mcp), GitHub CLI (GitHub menüsü). Dördü pakete GÖMÜLDÜ (çevrimdışı), yalnız eksik
  olan görev listesinde görünür (Inno `Check:`), seçilen kurulur.
- Paketli çalışmayı bozacak 2 sorun bulundu ve düzeltildi: (1) `mcp._base_python()` sys.executable kullanıyordu →
  paketli uygulamada bu uygulamanın exe'si; Serena/Windows-MCP `-m venv` çalışmazdı → frozen'da sistem Python'u
  (refresh_path + find_exe), yoksa Türkçe McpError; (2) `wmcp_baslatici.py` ve `blender_donustur.py` ayrı ortamda
  DOSYA olarak çalışır → spec `datas`.
- Ek düzeltmeler: `environment.find_exe` Microsoft Store'un sahte python.exe'sini (WindowsApps) kurulu saymaz (temiz
  Windows'ta hep PATH'te); paketli açılışta `refresh_path()` (sihirbazın eski PATH'i); AppMutex `EVREN.Studio`;
  `--duman-testi <dosya>` (pencere, betikler, sistem Python, keyring arka ucu, SSL); `--anahtarlari-sil`
  (CredEnumerate/CredDelete ile SERVICE_NAME içeren tüm kayıtlar; kaldırıcı "Evet" deyince).
- Sürüm tek kaynak `__version__` = 0.3.0 (pyproject dinamik).
- Yeni: `installer/evren_studio.spec` (onedir, konsolsuz, UPX yok, kullanılmayan Qt modülleri dışarıda, markdown
  eklentileri ve keyring arka ucu gizli içe aktarım), `installer/evren_studio.iss` (Türkçe+İngilizce, MIT lisans
  sayfası, yalnız bu kullanıcı varsayılan, sabit AppId, AppMutex, kaldırırken veri sorusu varsayılan Hayır),
  `installer/prereqs.json` (sürüm, adres, SHA256, beklenen yayıncı), `installer/imza.ps1` (Set-AuthenticodeSignature,
  SHA256, zaman damgası), `tools/paketle.py` (sertifika | onkosullar | tam yapım).
- İmza: kendinden imzalı kod imzalama sertifikası `CN=EVREN Studio - Osman Alpaslan` (5 yıl, CurrentUser\My).
  PFX + parola kullanıcının Drive'ına (`EVREN_Anahtarlar`) ve gizli yedek deposuna (~/.claude-yedek/anahtarlar).

## Test sonuçları
- Yeni tests/test_kurulum_paketi.py 15 test; ilgili paketler (environment, mcp, secrets, hygiene) 88 geçti;
  mutasyon 9/9 (Store süzgeci, frozen dalı, anahtar süzgeci, duman denetimleri, kaldırıcı varsayılan Hayır, sessiz
  kaldırmada silmeme, iss Store süzgeci, --anahtarlari-sil).
- Gerçek yapım: 184 MB kurulum, ~2 dk. Duman testi (yapımda ve KURULU uygulamada): frozen, pencere, betikler var,
  sistem Python bulundu, keyring=WinVaultKeyring, tls 401 (anahtarsız, bağlantı tamam).
- Bu bilgisayarda: sessiz kullanıcı kurulumu (yönetici izni yok), Başlat menüsü + masaüstü kısayolu, Uygulamalar
  kaydı (sürüm 0.3.0, yayıncı), aynı sürümün üzerine yükseltme, sessiz kaldırma (veri 8/8 dosya ve 2 anahtar kaldı).
- DOĞRULANMADI: gömülü programların gerçek kurulumu (bu bilgisayarda dördü de kurulu → görev listesi boş); Git
  `/CURRENTUSER` (yönetici izinsiz) desteği; Node/gh MSI'nın yönetici izni penceresi; etkileşimli kaldırmada "Evet"
  yolu (veri + anahtar silme; mantık birim testiyle); paketli uygulamada Serena/masaüstü kontrolü gerçek kurulumu;
  başka bilgisayarda SmartScreen davranışı.

## Sorunlar ve kayıtlar
- paketle.py: f-string olmayan parçada `}}` kaldı → sertifika bulunamadı (düzeltildi).
- ISCC `/S` imza aracı: yoldaki tırnak subprocess'te `\"` olunca ISCC "birden çok betik" dedi → Inno `$q`.
- CredEnumerateW süzgeci yalnız "önek*" kabul eder ("*ad*" boş döndü) → hepsini al, Python'da süz.
- cmdkey çıktısı "LegacyGeneric:target=" önekli → kaldırıcıda cmdkey yerine uygulamanın kendi silmesi.

- Kullanıcı (2026-11-07 13:30): "setupta logo yok; çift tıklayınca açılmıyor, uzantısı farklı". Neden: (1) sihirbazda
  Inno'nun varsayılan resmi vardı, hoş geldiniz sayfası kapalıydı; (2) masaüstüne kurulumun yanına
  `.exe.sha256` da kopyalanmıştı — adı neredeyse aynı, simgesiz, çift tıklayınca "nasıl açılsın" (kullanıcı onu
  açtı). Düzeltme: paketle.py logodan sihirbaz resimleri üretir (FLAG_RED; koyu temada brand_color beyaz;
  QT_QPA_PLATFORM=windows yoksa yazı kutucuk), DisableWelcomePage=no; masaüstüne yalnız .exe. Ekran görüntüsüyle
  doğrulandı. Ders: kullanıcıya verilen klasöre yalnız açacağı dosyayı koy.

- 2026-11-07 17:00-18:15 ANALİZ (kullanıcı: hız, açık mod, Auto Pro silinsin mi): ölçümler CHALLENGE_RESULTS
  "auto ↔ Auto Pro"; DEVIR maddeleri 17-19 (plan, kullanıcı onayı bekliyor). Yeni: tests/e2e_hiz_auto_karsilastirma_real_api.py,
  e2e_zorluk `--karne` (gerçek karneyi geçici veriye kopyalar). Açık mod kök nedeni yeniden üretildi (çalışırken tema
  geçişi), ekran görüntüleri build/acik_mod_denetim/.

- 2026-11-07 18:30-19:25 MADDE 18 AÇIK MOD (dal fix/acik-mod): kök neden — simge (65 kullanım) ve satır içi renkler
  bileşen oluşturulurken sabitleniyordu; koyu→açık geçişte görünmez (yeni `ui_denetim --gecis` eski kodda 200 HATA).
  Çözüm: icons._ThemedEngine (rol rengi her çizimde temadan; çağrılar '#hex' yerine rol adı), icons.set_pixmap,
  theme.watch/style/rich (sahip silinince düşer, anahtarla yerine geçer), MarkdownView/DiffView temada yeniden üretilir,
  bağlantılarda sabit renk yok + tema değişince bağlantılı etiketler yeniden dizilir; açık temada text_dim/text_faint/
  muted koyulaştı (uyarı 115 → 1). Testler: test_tema_gecisi 6, test_okunurluk 4 senaryo (gecis dahil), mutasyon 7/7,
  tam takım 1013/1013. Ekran görüntüleri iki temada bakıldı (R-05). Tuzak: mutasyon geri alındı ama aynı uzunluk + aynı
  saniye → bayat .pyc; tam koşu bozuk paletle koştu (3 kırmızı) → __pycache__ silinip yeniden (dersler.md).

- 2026-11-07 19:40 MADDE 17A KISA VE ÖZ CEVAP (dal perf/kisa-cevap): Settings.answer_style "kisa" (varsayılan) |
  "ayrintili" (Ayarlar > Genel > Sohbet yanıtları); prompts.STYLE_BRIEF/STYLE_DETAILED, build_chat_system(brief=),
  AgentRunner(brief_answers=) yalnız SOHBETTE (ajan istemi değişmez). test_kisa_cevap 7 (R-22, R-31, R-03), mutasyon 5/5.
  Mutasyon koşucusu artık PYTHONDONTWRITEBYTECODE + __pycache__ temizliğiyle (bayat .pyc tuzağı).

- 2026-11-07 20:05 MADDE 19 (dal feat/auto-guvenlik-agi): Auto Pro seçilebilir motor DEĞİL (chat_models'tan çıktı);
  eski "auto-pro"/"akilli" → "auto" (normalize_model_id, config v5 göçü, set_model, zamanlanmış görev). auto GÜVENLİK
  AĞI: kullanıcı auto seçtiyse ve başka yedek yoksa turun yedekleri = ai_route("kod", evren_only) (karneye göre);
  auto 503/zaman aşımı/boş/yavaş → runner._switch_model. İç işler (özet, inceleme, QA, Derin/Proje rolleri) ai_route ile
  sürer. Testler: test_router (güvenlik ağı R-31 + başka motor seçilince eklenmez R-22), test_auto_pro/default_auto/
  f4 güncellendi (eski karar testleri), mutasyon 6/6.

## Sonraki motor için notlar
- Temiz bilgisayar denemesi için Windows Sandbox (Windows 11 Pro'da var, KAPALI; açmak yönetici izni + yeniden
  başlatma ister — kullanıcı onayı). Sandbox'ta: kurulum → gerekli programlar sayfası 4 madde → kur → uygulama
  açılır, `python`/`git`/`node`/`gh` PATH'te. Git per-user başarısızsa: Git'i `/ALLUSERS` (UAC) ile kur ya da
  MinGit taşınabilir zip'e geç.
- Yayın: `dist\` depoya girmez. GitHub Releases + Actions henüz yok (kullanıcı onayı). 184 MB'ın ~145 MB'ı gömülü
  yükleyiciler.
- Sürüm değişince `__version__` (tek kaynak); gömülü program sürümü değişince prereqs.json + iss #define birlikte
  (test denetler).
