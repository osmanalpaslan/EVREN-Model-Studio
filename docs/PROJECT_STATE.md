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

- (2026-10-17) Proje maratonu YAPILDI (LOOP_ANALYSIS.md); sıradaki: "ortam denetimi" (eksik programı winget + bilinen
  listeyle onaysız kurma). Otomatik mod artık hiç onay istemiyor (uygulandı). Döngü analizi: docs/knowledge/LOOP_ANALYSIS.md.
0. OpenAI/Anthropic'i gerçek anahtarla doğrula; geçerse `api/providers.py`'de
   `verified=True` ve MODEL_CAPABILITIES.md güncelle.
1. ~~Uzun çok adımlı görev senaryosu~~ — YAPILDI (2026-10-17):
   `tests/e2e_marathon_real_api.py` (A/B/C projeleri, kabul testleri).
2. ~~`auto` için protokol seçimi~~ — ÇÖZÜLDÜ (2026-10-16): ölçülen değerler
   (262k + yerel araç) uygulanıyor; auto artık varsayılan motor.
3. Git entegrasyonu (durum/diff görünümü, ajan değişikliklerini commit'leme
   önerisi) — şu an yalnızca dal adı gösteriliyor.
4. Görsel girdi (Aşama 3): qwen3-vl-30b ile ekran görüntüsü ekleme.
5. Paketleme (Aşama 4): PyInstaller ile tek klasör EXE.

## Ortam notları

- Python: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` (PATH'te yok;
  run.bat venv'deki pythonw'u doğrudan kullanır).
- Test: `.\.venv\Scripts\python.exe -m pytest -q`
- Çalıştırma: `run.bat` veya `.\.venv\Scripts\python.exe -m evren_studio`
- PowerShell 5.1'de `Get-Content`/`Set-Content` varsayılan olarak ANSI
  kullanır: Türkçe içerikli dosyaları bu komutlarla YAZMAYIN (bkz.
  LESSONS_LEARNED #10).
