# Proje Durumu

> Oturum kesilirse çalışmaya bu dosyadan devam edilir.
> Son güncelleme: 2026-10-16 (OpenAI/Anthropic sağlayıcıları — `feat/saglayicilar` dalı)

## Konum ve sınırlar

- Proje: `C:\Projects\AI-Atolye\EVREN-Model-Studio`
- Uzak depo: https://github.com/osmanalpaslan/EVREN-Model-Studio (HERKESE
  AÇIK, MIT lisansı). Varsayılan dal `master`.
- Bağımsız Git deposu ✅, Python 3.12 venv (`.venv`) ✅
- Alpnex/DepoWise'a DOKUNULMADI. Tüm işlemler proje klasörü içinde.
- Veriler: `%LOCALAPPDATA%\EVREN-Model-Studio\` (config.json + evren.db +
  logs\crash.log). API anahtarı Windows Credential Manager'da
  (`EVREN-Model-Studio`).
- Geliştirme 2026-10-16'da ikinci bilgisayarda sürdürülüyor; `.venv` her
  makinede yeniden kurulur (INSTALLATION.md).

## Aşama durumu

| Aşama | Durum |
|---|---|
| 0 — Araştırma | ✅ TAMAMLANDI |
| 1 — Çalışan MVP | ✅ TAMAMLANDI |
| 2 — Kod ajanı çalışma alanı | ✅ UYGULANDI; gerçek EVREN ile araç turu 8 modelde doğrulandı (2026-10-16) |
| 3 — Özel görev modelleri | ⬜ BAŞLAMADI |
| 4 — Paketleme | ⬜ BAŞLAMADI |

## Aşama 2'de çalışan ve test edilenler (sahte model istemcisiyle)

- Oturum tabanlı arayüz: sol menü (arama, tarih grupları, sabitleme, sağ tık
  menüsü), karşılama ekranı, ortalanmış akış, yazma kutusu, sağ panel.
- Ajan araçları ve proje sınırı (kök dışı / .git yazma engeli), CRLF/BOM
  korunması, onay sırasında dışarıdan değişen dosyanın üzerine yazılmaması.
- İzin modları; komutların hiçbir modda onaysız çalışmaması; oturum izinleri;
  zincirli komutlarda önek izninin geçersiz olması.
- Ajan döngüsü: yerel araç çağrısı, metin protokolü, 400/422'de metne geçiş,
  adım sınırı, onay beklerken iptal, bilinmeyen araç/bozuk JSON.
- Dosya değişikliği kaydı + geri alma (tekil, toplu, çakışmada onaylı zorlama).
- Arayüz uçtan uca: mesaj → araç kartı → onay kutusu → dosya değişir →
  Değişiklikler paneli → oturum yeniden açılınca aynı çizim → geri alma.
- Testler: 116/116 geçti (tüm ekranlar için arayüz QA paketi dahil). SMOKE_OK.
- Gerçek API: `tests/e2e_real_api.py` E2E_OK; `tests/e2e_agent_real_api.py`
  16/16 (8 model × 2 protokol); `tests/e2e_ui_real_api.py` 14/14.
- Sohbet ekranında canlı model + süre, tıklanabilir `/` komut ve `/model`
  listesi, Ayarlar'da varsayılana döndürme ve tekerlek koruması.

## Ücretli sağlayıcılar (dal: `feat/saglayicilar`, birleştirilmedi)

- OpenAI (Responses) ve Anthropic (Messages) istemcileri, gruplu model seçici,
  Ayarlar > Ücretli Sağlayıcılar, aylık bütçe ($5 varsayılan, tahmini).
- Durum: **sahte testlerle** doğrulandı (`tests/test_providers.py`, 28 test);
  gerçek anahtarla DOĞRULANMADI (kayıt: 2026-10-16-openai-ve-anthropic-entegrasyonu-gercek-anahtarla-dogrulanma).
- Doğrulamak için: anahtarı Ayarlar'a girip
  `.\.venv\Scripts\python.exe tests\e2e_providers_real_api.py --evet`.
- Tüm test paketi: 202/202. EVREN gerçek testleri (R-13): E2E_OK, ajan 6/6, arayüz 15/15.

## Ortak geliştirici hafızası

Her motor oturuma `.\.venv\Scripts\python.exe tools\ai_memory.py baslangic`
ile başlar (komut önce GitHub'la eşitler; başka bilgisayardaki işler böylece
görünür), bitirirken `docs/ai-memory/` altına oturum günlüğü ve gerekirse
kayıt/kural yazar (protokol: AGENTS.md). Açık kayıtlar: docs/ai-memory/INDEX.md.

## Sıradaki iş

  - (2026-10-24) F4 skill'ler ve profiller (dal `feat/f4-skill-profiller`): Skill'ler ve Profiller sayfası,
    read_skill, proje bazlı kapsam, profiller (/profil), şablonlar, skill denetçisi, /betiklestir. R-25 ölçümü: skill
    açık 4/4, konu dışında açılmadı. Sıradaki faz F5.

  - (2026-10-24) F3 ajan verimliliği (dal `feat/f3-ajan-verimliligi`): read_table, Python paket bilgisi, proje
    haritası, Proje görevleri arası okuma paylaşımı, EVREN.md ders önerisi, web_fetch (evren_tools etkisiz çıktı);
    özet/kapsam modeli varsayılanı auto-pro; test politikası R-30. Sıradaki faz F4.

  - (2026-10-24) Auto Pro akıllı seçim F2 (dal `feat/autopro-akilli-secim`): zorluk (A6) ve iş türü (A7)
    rolleri + rol ölçüm paketleri, kalite puanı ve 👎 (A5), yoklama (A8), normal turda kota kapısı (A11), seed
    yalnız gemma + veri rolünde (A10), planlayan + yazan (A13, ölçümde kazanç yok → ayar kapalı). Sıradaki faz F3.

  - (2026-10-24) Auto Pro çekirdeği F1 (dal `feat/autopro-cekirdek`): gerçek kullanım kaydı, yavaşlama kuralı
    (#88), bekleme süresi, yanıt vermeme süresi, akış kopmasında yedeğe geçiş, model listesi uyarısı, son 24 saat
    tablosu. Sıradaki faz F2 (ILERIDE_YAPILACAKLAR 7.5).

  - (2026-10-21) Auto Pro kod sırası yeniden ölçümle değişti (dal `feat/kod-motor-sirasi`):
    deepseek-v4.1-flash → qwen3.8-flash-next → gemma-4-31b. Ölçüm: CHALLENGE_RESULTS.md "Kod motoru sırası".

  - (2026-10-21) Derin/Proje düzeltmeleri (dal `feat/derin-duzeltmeler`): kullanıcının gerçek hesap kapama
    oturumundaki 10 kusur giderildi (iç içe PowerShell, bozuk doğrulama komutu, kısmi projede "bitti", soru kartı ve
    `SORU:` duraklaması, görev bağlamı, görünürlük/dökümler, .ps1 BOM, deepseek-v4-flash'ın listeden kalkması).
    Ayrıntı: CHANGELOG, incidents 2026-10-21-*.

  - (2026-10-21) Derin Mod (dal `feat/derin-mod`): composer "Derin" düğmesi / `/derin`; anla → planla
    (iki model + yargıç) → onaylı Proje uygulaması → çekişmeli doğrulama → düzeltme. Plan bekçisi ve Proje
    ajanı önerisi (faz unutma), uzun işler (`start_job`/`wait_job`), kota kapısı ve kota sonrası otomatik
    sürdürme, kenar çubuğu sürükleme düzeltmesi (gerçek kök neden). EVREN şartları okundu: ek anahtarla
    kota genişletme yasak. Ölçüm: CHALLENGE_RESULTS.md "Derin Mod ve plan bekçisi".

  - (2026-10-19) QA ajanı (dal `feat/qa`): `/qa` web uygulamasını tarayıcıda test uzmanı gibi dener;
    arka plan servisleri, test bekçisi, görsel göz, ek denetimler. Gerçek koşu: bilinen hata 3/3 (3 koşu).

  - (2026-10-19) MCP aşama 2 (dal `feat/mcp-akilli`): MCP gerektiğinde açılır/boşta kapanır,
    ücretli sağlayıcıda yok, hata bekçisi, Playwright MCP 0.0.83 (Edge), Serena çok dilli
    (Python/TS/JS/C#/Java). Node.js 24 winget ile kuruldu. Ölçüm: CHALLENGE_RESULTS.md.

  - (2026-10-19) MCP desteği + Serena 1.7.0 tek tıkla kurulum (dal `feat/mcp`, `feat/klavye-baglam-tema`
    üstünde): ajan MCP araçlarını izin sistemiyle kullanır; gerçek API ölçümü CHALLENGE_RESULTS.md.

  - (2026-10-19) Alt+Enter yeni satır; bağlam göstergesi özet eşiğine göre (Auto Pro
    penceresi seçilecek modelden); koyu tema tek parlaklık (dal `feat/klavye-baglam-tema`).
    MCP araştırması: docs/ILERIDE_YAPILACAKLAR.md madde 4 (kod yok, karar bekliyor).

  - (2026-10-19) Auto Pro (eski adı EVREN Akıllı) + Proje ajanı uygulandı (dal
    `feat/akilli-yonlendirme`): 8 motor ölçümü, Auto Pro 12/12, proje ajanı gerçek
    API'de kabul 5/5. Auto Pro yalnız anahtarı girilmiş sağlayıcıları kullanır;
    uygulamanın kendi yapay zekâ işleri `AppContext.ai_chat` üzerinden (başlık,
    hata açıklaması, commit mesajı, özet, inceleme). Ücretli yönlendirme doğrulanmadı.
    Ayrıntı: CHALLENGE_RESULTS.md, ILERIDE_YAPILACAKLAR.md madde 3.

  - **Kararlaştırılmış ileri işler: docs/ILERIDE_YAPILACAKLAR.md** — ilk madde
    profesyonel Windows kurulum paketi (PyInstaller onedir + Inno Setup, isteğe
    bağlı Git/Python/Node kurulumu); kullanıcı "şimdi değil" dedi (2026-10-19).

  - (2026-10-19) Zorluk paketi eklendi (`tests/e2e_zorluk_real_api.py`, sonuçlar
    CHALLENGE_RESULTS.md: deepseek-v4-flash 10/10, auto 9/10 → düzeltmelerle
    tek tek geçiyor); tek tıkla kurulum `kurulum.bat` (temiz kopyada doğrulandı;
    winget ile Python kurma yolu denenmedi). Paketleme planı: docs/ILERIDE_YAPILACAKLAR.md
    madde 1.

- (2026-10-17) Proje maratonu YAPILDI (LOOP_ANALYSIS.md); "ortam denetimi" de YAPILDI (Otomatik/Manuel kurulum seçeneği). Otomatik mod artık hiç onay istemiyor (uygulandı). Döngü analizi: docs/knowledge/LOOP_ANALYSIS.md.
0. OpenAI/Anthropic'i gerçek anahtarla doğrula; geçerse `api/providers.py`'de
   `verified=True` ve MODEL_CAPABILITIES.md güncelle.
1. ~~Uzun çok adımlı görev senaryosu~~ — YAPILDI (2026-10-17):
   `tests/e2e_marathon_real_api.py` (A/B/C projeleri, kabul testleri).
2. ~~`auto` için protokol seçimi~~ — ÇÖZÜLDÜ (2026-10-16): ölçülen değerler
   (262k + yerel araç) uygulanıyor; auto artık varsayılan motor.
3. Git entegrasyonu (durum/diff görünümü, ajan değişikliklerini commit'leme
   önerisi) — şu an yalnızca dal adı gösteriliyor.
4. ~~Görsel girdi~~ — YAPILDI (2026-10-19): yapıştır/sürükle-bırak ekleri,
   görsel okuyan modeller ölçüldü; kullanım düğmesi eklendi.
5. Paketleme (Aşama 4): PyInstaller ile tek klasör EXE.

## Ortam notları

- Python: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` (PATH'te yok;
  run.bat venv'deki pythonw'u doğrudan kullanır).
- Test: `.\.venv\Scripts\python.exe -m pytest -q`
- Çalıştırma: `run.bat` veya `.\.venv\Scripts\python.exe -m evren_studio`
- PowerShell 5.1'de `Get-Content`/`Set-Content` varsayılan olarak ANSI
  kullanır: Türkçe içerikli dosyaları bu komutlarla YAZMAYIN (bkz.
  LESSONS_LEARNED #10).
