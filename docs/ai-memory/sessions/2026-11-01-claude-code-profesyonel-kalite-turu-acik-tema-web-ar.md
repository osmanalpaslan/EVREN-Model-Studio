---
id: 2026-11-01-claude-code-profesyonel-kalite-turu-acik-tema-web-ar
tarih: 2026-11-01
motor: Claude Code
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/profesyonel-kalite
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Profesyonel kalite turu: açık tema, web araması, maraton D/E

## Görev
Kullanıcı (yalnız Auto Pro kullanıyor): uygulamayı uzun projelerle kapsamlı test edip profesyonel hâle getir;
açık temada görünmeyen düğmeler ve Ayarlar'daki sabit renk hataları; QA. Ek maddeler (sırasıyla): bağlam
şişmesi, bulunan hatalar, proje bitirme hızı, Derin Mod, ücretsiz web araması (Tavily anahtarı verildi),
sade sağlayıcı ekranı, kota bitince otomatik devam paneli.

## Yapılanlar
- Açık tema okunurluğu (önceki commit'ler e940402, 5225fc1, 316d69d): palet, yer tutucu, ghost düğme çerçevesi,
  kesik yol etiketi; `tools/ui_denetim.py` + `tests/test_okunurluk.py` (R-33).
- Ayarlar'daki "ücretli" etiketi koda gömülü `#d9a441` idi → `role="warning"` + QSS; arayüz kodunda HTML'e sabit
  renk yazılmasını engelleyen test (`test_arayuz_kodunda_html_icine_sabit_renk_yok`).
- `web_search` aracı (`agent/websearch.py`): Tavily (Credential Manager `tavily_api_key`) → anahtarsız Tavily →
  DuckDuckGo HTML → yoksa "eldeki bilgiyle devam et". 401/403/432/433'te anahtar 1 saat denenmez. İzin: web_fetch
  gibi EXEC (Otomatik sormaz, Manuel sorar, Plan engeller). Tur başı hatırlatma `websearch.needs_web` (dar kelime
  listesi; "güncelle", "nedenini araştır" tetiklemez). Ayarlar > Web Araması kartı (kaydet/sil, kalan kota).
  `secrets` maskesine `tvly-` eklendi.
- Maraton D (Flask kütüphane, 7 mesaj — uzun oturum) ve E (PWA) `tests/e2e_marathon_real_api.py`'ye eklendi.
- `tests/e2e_websearch_real_api.py` (açık/kapalı ölçüm; kapalı koşu artık `<cikti>/kapali` altına yazar).

- Token tahmini kalibrasyonu (b099b7a, R-34): 3,5 → 2,6 + gerçek usage ile model başına oran/ek yük.
- Devir düzeni (R-35, kullanıcı isteği: farklı bilgisayar/oturumdan devam): `docs/DEVIR_NOTU.md` (şu an + geliştirme sırası + birleştirme öncesi); `baslangic` en üstte gösterir ve GitHub'da daha yeni çalışma dalı varsa uyarır (`active_work_branch`); `src/` değişen commit devir notu olmadan durur; `denetle` bölümleri denetler.

- Kota bitince otomatik devam (normal oturum): `agent/resume.py`, `QuotaResumeCard`, session_view `_quota_pause` /
  `_resume_probe` / `restore_pending_resume`, db `get/set/delete_meta`, `prompts.QUOTA_CONTINUE_PROMPT`. Testin
  yakaladığı hata: `set_meta` commit etmiyordu → yeniden açılışta plan kayboluyordu (düzeltildi). Kapanmış pencerenin
  gecikmeli çağrısı kapalı DB'ye erişiyordu (`_closed` koruması). `ui_denetim`: kaydırma kenarında yarısı görünen
  bileşen ölçülmez (yanlış HATA).

- Proje/QA/Derin kota duraklaması da ortak karta ve kalıcı plana taşındı (`ResumePlan.flow`, `project_ui.schedule_auto_resume` → `session_view._quota_pause`); `test_kota_kapisi` 3 testi yeni düzene uyarlandı (eski iç `_resume_timer` ayrıntısı yerine plan/zamanlayıcı/yoklama → devam); mutasyon 2 testi kırdı.

- Maraton betiğine `MARATON_KOTA_TESTI=<mesaj>:<adım>`: o mesajda <adım> araç sonucundan sonra günlük kota "bitmiş" gösterilir; güvenli durma + kart + plan ve gerçek yoklamayla devam ölçülür, kabul yine tam olmalı.

- Madde 6: dil kuralı ara cümleleri kapsıyor (ölçüm: 96 yanıtın 3'ü İngilizce, hepsi deepseek-v4.1-flash); R-05/AGENTS `ui_denetim.py`'ye yönlendi. Madde 7 dökümü: sürenin ~%97'si model beklemesi (DEVIR_NOTU).

- Plan modunda web_search/web_fetch açıldı (`tools.WEB_TOOLS`, READ_ONLY_SPECS); 2 eski test yeni karara uyarlandı, mutasyon 2 testi kırdı.

## Test sonuçları
- Hedefli: tests/test_websearch.py 23 geçti; mutasyon: `_KEY_DEAD` boşaltılınca kota testi, hatırlatma kapatılınca
  tetiklenme testi kırıldı (geri alındı).
- Paket: okunurluk, mcp_ui, f6, f3, source_hygiene, websearch → 98 geçti (72 sn).
- `ui_denetim.py ikisi --goruntu` (windows QPA): açık/koyu HATA 0, KESIK 0; açık UYARI 78 (önceden bilinen soluk
  küçük yazı ölçüm gürültüsü, 3,5–4,5 arası). Ayarlar görüntüleri bakıldı.
- Gerçek API taban ölçümü (auto-pro, değişiklikten önceki kod): zorluk 12/12, proje ajanı 5/5, maraton A 10/10
  (1544 sn), B 13/13 (1113 sn), C 10/10 (1676 sn; 1. mesaj 1284 sn/33 adım — hız maddesi). Hiçbirinde otomatik
  özet olmadı (özet=0).
- Web araması R-25: CHALLENGE_RESULTS.md "Web araması web_search açık/kapalı" — açık 3/3, kapalı 3/3; model
  adresini bilmediği soruda web_search'ü kendiliğinden seçti, gereksiz görevde çağırmadı.
- Tam takım 712/712 (kalibrasyon sonrası, 3 dk 57 sn). Devir: test_ai_memory_sync 13/13 ×6 (aynı saniye commit kararsızlığı bulunup düzeltildi), mutasyon 2 testi kırdı.
- R-13 e2e üçlüsü ve son kodla zorluk paketi bu dal birleşmeden önce koşulacak (henüz koşulmadı).

## Sorunlar ve kayıtlar
- 2026-11-01-acik-temada-soluk-yazilar-ve-bazi-dugmeler-okunmuyordu (çözüldü)
- 2026-11-01-ayarlarda-ucretli-etiketi-sabit-renkle-yazilmisti (çözüldü)
- Kendi hatam: regex/`\n` içeren yamayı bash heredoc ile yazdım, dosyaya gerçek satır sonu girdi (R-29 zaten
  yasaklıyor); Edit aracıyla düzeltildi.

## Sonraki motor için notlar
- Sıradaki: bağlam şişmesi — `runner.CHARS_PER_TOKEN=3.5` gerçekte 2,2–2,6 (Türkçe/araç çıktısı); öneri: API'nin
  `usage.prompt_tokens` değeriyle oturum içi oran kalibrasyonu; maraton D ile özet tetiklenmesini ölç.
- Kota bitince otomatik devam: bugün yalnız Proje/QA/Derin (`project_ui.schedule_auto_resume`, gizli
  `auto_resume`, uygulama açıkken QTimer). Normal ajan oturumu sürmüyor; kalıcı devam kaydı yok.
- Plan modunda web_search kapalı (EXEC); araştırma için açılması ayrıca düşünülebilir.
- Sohbet (klasörsüz) oturumlarında araç yok, dolayısıyla web_search de yok.
