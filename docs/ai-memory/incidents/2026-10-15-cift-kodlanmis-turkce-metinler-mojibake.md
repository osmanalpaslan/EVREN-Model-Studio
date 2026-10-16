---
id: 2026-10-15-cift-kodlanmis-turkce-metinler-mojibake
tarih: 2026-10-15
tur: hata
onem: yuksek
durum: cozuldu
alan: kodlama/encoding
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PowerShell 5.1, Python 3.12
etiketler: [powershell, utf-8, bom, mojibake, arayuz]
kurallar: [R-01, R-10]
---

# Çift kodlanmış Türkçe metinler (mojibake) depoya girdi

## Belirti
Arayüzde Türkçe metinler bozuk görünüyordu. Örnekler (kodlama-ornegi): "GÃ¶nder", "Yeniden AdlandÄ±r", "MesajÄ±nÄ±zÄ± yazÄ±nâ€¦".
7 kaynak dosya etkilenmişti: `db.py`, `ui/chat_page.py`,
`ui/connection_page.py`, `ui/help_page.py`, `ui/models_page.py`,
`ui/monitor_page.py`, `ui/settings_page.py`. Dosyalar ayrıca UTF-8 BOM ile
başlıyordu (`ef bb bf`).

## Kök neden
Doğrulandı: UTF-8 dosyalar PowerShell 5.1'de varsayılan ANSI (cp1254/cp1252)
kodlamayla okunup tekrar UTF-8 (BOM'lu) yazılmış; her Türkçe karakter iki
karaktere dönüşmüş. Aynı tuzağa 2026-10-16'da Claude Code da düştü:
`(Get-Content pyproject.toml -Raw).Replace(...) | Set-Content` zinciri
`pyproject.toml` açıklamasını aynı biçimde bozdu (hemen düzeltildi).

## Çözüm
Her dosya için ters dönüşüm: metin cp1252 olarak (tanımsız baytlar latin-1
ile) kodlanıp UTF-8 olarak çözüldü, BOM kaldırıldı. Sonrasında bozulma
işaretleri taranıp sıfır bulundu. Eski Chat sayfası daha sonra tamamen
yeniden yazıldı.

## Kanıt
- Commit `c8e17d2` (dal `feat/ajan-calisma-alani`).
- Onarım öncesi/sonrası `pytest`: 53/53 geçti; ekran görüntüsünde metinler doğru.
- `tests/test_source_hygiene.py` artık bozulma işaretlerini ve BOM'u denetliyor.

## Önleme
R-01 (PowerShell 5.1 ile Türkçe dosya yazma), R-10 (hijyen testi).
`docs/knowledge/LESSONS_LEARNED.md` #10.

## İlgili dosyalar
src/evren_studio/db.py, src/evren_studio/ui/*.py, pyproject.toml
