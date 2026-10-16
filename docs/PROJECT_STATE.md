# Proje Durumu

> Oturum kesilirse çalışmaya bu dosyadan devam edilir.
> Son güncelleme: 2026-10-16 (Aşama 2 — kod ajanı çalışma alanı)

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
| 2 — Kod ajanı çalışma alanı | 🟨 UYGULANDI, sahte modelle test edildi; gerçek EVREN ile araç turu DOĞRULANMADI |
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
- Testler: 104/104 geçti (53 eski + 51 yeni). SMOKE_OK.

## Sıradaki iş

1. **Gerçek EVREN ile araç turu testi** (anahtar gerekir): glm-5.3 ve
   deepseek-v4.1-flash ile `tools` gönderimi; yanıt `tool_calls` dönüyor mu,
   400/422 mi? Sonucu MODEL_CAPABILITIES.md ve API_COMPATIBILITY.md'ye yaz.
2. Gerçek kullanımda onay kutusu, uzun komut çıktısı ve bağlam göstergesini
   gözden geçir; gerekirse `tests/e2e_real_api.py`'ye araç senaryosu ekle.
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
