---
id: 2026-11-05-claude-code-masaustu-madde-13-masaustu-kontrolu-windows-mcp-v
tarih: 2026-11-05
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/masaustu-kontrol
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 13 masaüstü kontrolü (Windows-MCP) ve masaüstü QA

## Görev
Kullanıcı (2026-11-05): "Uygulamaya imleçle masaüstü kullanımı ve QA uygulama testi gibi görsel davranışlar
ekleyebilir miyiz? Benzer ücretsiz repolardan destek al; en iyisini, en başarılısını seç."

## Yapılanlar
- Araştırma: Windows-MCP (CursorTouch, MIT, ~11,1 bin yıldız, PyPI windows-mcp 0.8.8 2026-10-10, Python ≥3.14) seçildi:
  UI Automation ağacını metin olarak verir (görsel model şart değil → EVREN metin modelleri de kullanabilir), kendi
  güvenliği var (kontrol ışığı "AI", fareyi oynatınca / Ctrl+Alt+Shift+Backspace ile kullanıcıya dönüş). Elenenler:
  Microsoft UFO (ayrı ajan çatısı), Agent-S (güçlü görsel/konumlandırma modeli ister), pywinauto-mcp / windows-gui-mcp
  (küçük kitle).
- `agent/mcp.py`: hazır ayar "masaustu" (`windows_config`, `install_windows_mcp`: boot venv → uv 0.12.20 → uv ile
  Python 3.14 venv → windows-mcp==0.8.8; veri klasöründe), `when="masaustu"` (yalnız `DESKTOP_WORDS`), tam yetkili
  araçlar (PowerShell, FileSystem, Registry, Process, Clipboard, Scrape, Notification) DIŞARIDA, telemetri kapalı,
  `--control-policy balanced`, okuma araçları dışındakiler izin sisteminde "komut"; kullanıcıya `DESKTOP_NOTE`, modele
  `DESKTOP_PROMPT`.
- `agent/qa.py`: `QaState.target` (web | masaustu), masaüstü plan/senaryo istemleri, `DesktopQaTools.visual_check`
  (Windows-MCP Screenshot → görsel model), `save_mcp_image`. `ui/qa_ui.py`: `/qa-masaustu`, hedefe göre ön koşul ve araç.
- Ayarlar > Bağlayıcılar'da "Masaüstü kontrolünü kur / etkin / Dene" satırı.
- `tests/e2e_masaustu_real_api.py` (ajan: Tk hesap uygulamasında 2+3; QA: hatalı/doğru sürüm) — HENÜZ ÇALIŞTIRILMADI.

## Test sonuçları
- tests/test_masaustu.py 25 (tetiklenen/tetiklenmeyen, güvenlik yapılandırması, kurulum sırası, not/istem, görsel göz,
  QA istemleri, ön koşul, Ayarlar satırı); mutasyon 13/13 (ilk koşuda 1 kaçtı → test güçlendirildi).
- Tam takım 895/895 (6 dk 0 sn).
- Gerçek kurulum: windows-mcp 0.8.8 yalıtılmış deneme veri klasörüne 40 sn'de kuruldu (build/masaustu_deneme).
- DOĞRULANMADI: sunucunun gerçekten başlatılması ve masaüstünde çalışması. Claude Code otomatik denetimi, fare/klavyeyi
  yönetebilen sunucuyu başlatan yoklamayı (yalnız okuyan araçlar dahil) engelledi; atlatılmadı. Kullanıcı izniyle
  `tests/e2e_masaustu_real_api.py hepsi` koşulmalı.

## Gerçek masaüstü denemeleri (kullanıcı izniyle, 2026-11-05 akşam)
1. 19:07 — masaüstü araçları HİÇ sunulmadı: README'deki `--control-policy` 0.8.8'de yok, sunucu "No such option" ile
   kapanıyordu; ajan araçsız kendi PowerShell UIA betiklerini yazdı. Düzeltme: seçenek kaldırıldı + kurulumda
   `check_windows_flags` (kullanılan her seçenek kurulu sürümün `serve --help`'inde olmalı).
2. 19:21 — araçlar sunuldu (14), ajan 4/5: "Sonuç: 5" dedi ama uygulama HİÇ hesaplamadı (sonuc.txt yok). Kök neden:
   (a) Tk penceresi iç öğeleri UIA'ya bildirmiyor (yalnız başlık çubuğu) → ajan koordinatı koddan TAHMİN etti;
   (b) göremediği ekran görüntüsünden sonuç UYDURDU. Düzeltme: Screenshot ajana sunulmaz (QA visual_check görsel modele
   sorar), görsel yer tutucusu "GÖREMEZSİN" der, DESKTOP_PROMPT koordinat tahmini ve doğrulanmamış sonucu yasaklar,
   test uygulaması Qt'ye geçti (öğeler adlarıyla UIA'da). Ayrıca Type `caret_position:"end"` iki kez End bastı.
3. 19:31 — Snapshot `use_vision:true` ile sunucu 90 sn'de yanıt vermedi (3 kez); durduruldu. Kullanıcı: "End tuşu
   ekran yakalamayı açıyor, test yarıda kalır" → End basımı ekran yakalamayı açmış olabilir. Düzeltme: `desktop_guard`
   (Snapshot'ta görsel hep kapalı; engelli tuşlar — varsayılan End, Ayarlar > Bu bilgisayar — Type caret ve Shortcut'ta
   uygulanır), `desktop_blocked_keys` ayarı.
- Birim testinde takılma: Ayarlar'ı kaydeden test "Kaydedildi" kutusunu kapatmadığı için görünmez pencerede bekledi
  (20 dk); düzenek düzeltildi, 87/87. Mutasyon toplam 22/22.

## Sorunlar ve kayıtlar
- Engel (kayıt gerektirmez): motorun ortamında masaüstü kontrol sunucusunu başlatmak kullanıcı izni ister.

## Sonraki motor için notlar
- Birleştirmeden ÖNCE gerçek deneme (R-07/R-25): `.\.venv\Scripts\python.exe -u tests\e2e_masaustu_real_api.py hepsi`
  (çalışırken bilgisayara dokunulmamalı). Snapshot çıktısının biçimi (öğe kimliği/koordinat) README'de yazmıyor; gerçek
  çıktıya göre DESKTOP_PROMPT gerekirse ayarlanır. Araç adları (Snapshot, Click…) 0.8.8 README'sinden; gerçek listeyle
  karşılaştır (eksik araç `notes`'ta "bulunamayan araçlar" diye görünür).
