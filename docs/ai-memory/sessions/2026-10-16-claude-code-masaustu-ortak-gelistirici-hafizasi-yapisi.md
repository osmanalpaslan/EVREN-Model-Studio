---
id: 2026-10-16-claude-code-masaustu-ortak-gelistirici-hafizasi-yapisi
tarih: 2026-10-16
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11 Pro 26200, PowerShell 5.1 + Git Bash, Python 3.12.10
dal: feat/ajan-calisma-alani
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Ortak geliştirici hafızası yapısı

## Görev
Kullanıcı; farklı ortam ve motorların (Kilo Code, Claude Code, diğerleri)
birbirinin hatalarından öğrenmesi için eksikleri, sorunları, nedenlerini,
çözümlerini ve yapılanları kaydeden bir dosya yapısı istedi. Her motor
geliştirmeden önce bu verileri okuyup buna göre davranmalı ve sonrasında
beslemeli.

## Yapılanlar
- `AGENTS.md` (kök): tüm motorlar için tek doğruluk kaynağı protokolü
  (başlarken oku → çalışırken kaydet → bitirirken besle), proje özeti ve
  RULES.md'den otomatik üretilen kural özeti.
- Motor giriş dosyaları (hepsi AGENTS.md'ye yönlendirir): `CLAUDE.md`,
  `GEMINI.md`, `.github/copilot-instructions.md`, `.cursor/rules/ai-memory.mdc`,
  `.kilocode/rules/ai-memory.md`, `.roo/rules/ai-memory.md`,
  `.clinerules/ai-memory.md`, `.windsurf/rules/ai-memory.md`.
- `docs/ai-memory/`: README, RULES (R-01…R-10), ENGINES (motor profilleri),
  `incidents/` (9 kayıt: 2026-10-15/16 boyunca bulunan gerçek sorunlar),
  `sessions/` (4 günlük; Kilo Code oturumu git geçmişinden geriye dönük),
  INDEX (üretilen).
- `tools/ai_memory.py` (yalnız stdlib): baslangic, ara, kayit, oturum,
  indeks, denetle, kanca-kur, kanca.
- `tools/hooks/pre-commit`: src/ veya tests/ değişen commit'te
  docs/ai-memory değişikliği yoksa veya denetim başarısızsa commit'i durdurur.
  Bu makinede `kanca-kur` ile etkinleştirildi.
- `tests/test_ai_memory.py` (denetim pytest içinde), `tests/test_source_hygiene.py`
  (mojibake, BOM, git'in dışladığı kaynak dosya).
- Uygulamanın kendi ajanı: `Workspace.project_memory` artık EVREN.md +
  AGENTS.md'yi birlikte okuyor; bu depoda çalışan EVREN Studio ajanı da
  protokolü sistem isteminde görüyor.
- Bilerek örnek gösteren eski bozuk metin satırları `kodlama-ornegi`
  işaretiyle muaf tutuldu (LESSONS_LEARNED, CHANGELOG).

## Test sonuçları
- Yeni testler ilk çalıştırmada iki gerçek sorunu yakaladı: doldurulmamış
  oturum şablonu (bu dosya) ve işaretsiz bir örnek satır — ikisi de giderildi.
- Son durum: `pytest -q` ve `tools/ai_memory.py denetle` sonuçları commit
  öncesi çalıştırıldı (commit mesajında ve PR #2 açıklamasında).

## Sorunlar ve kayıtlar
- Yeni kayıt gerekmedi. Mevcut 9 kayıt bu oturumda oluşturuldu
  (bkz. INDEX.md).

## Sonraki motor için notlar
- Her oturum başında: `.\.venv\Scripts\python.exe tools\ai_memory.py baslangic`.
- Yeni bilgisayarda bir kez: `tools\ai_memory.py kanca-kur` (core.hooksPath).
- Kancayı `--no-verify` ile atlama; protokolü uygula.
- Kilo Code kullanırken `.kilocode/rules/ai-memory.md` otomatik yüklenir;
  modelin kayıt/oturum dosyası yazdığını kontrol et.
- En öncelikli açık kayıt: 2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi.
