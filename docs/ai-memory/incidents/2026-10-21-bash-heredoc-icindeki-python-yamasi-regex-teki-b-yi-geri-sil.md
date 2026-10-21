---
id: 2026-10-21-bash-heredoc-icindeki-python-yamasi-regex-teki-b-yi-geri-sil
tarih: 2026-10-21
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: surec
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Git Bash, Python 3.12.10
etiketler: [heredoc, kacis, regex, yama]
kurallar: [R-01]
---

# Bash heredoc içindeki Python yaması regex'teki \b'yi geri silme karakterine çevirdi

## Belirti
`agent/deep.py`'deki soru sözcüğü düzenli ifadesini bash heredoc'una gömülü Python ile değiştirirken
kaynağa `\b` yerine görünmez bir geri silme karakteri (0x08) yazıldı; düzenli ifade eşleşmedi ve
`test_is_soru_ayrimi` düştü. Aynı oturumda tırnaklı başka bir heredoc da "unexpected EOF" verdi.

## Kök neden
Doğrulandı. Heredoc → Python dize sabiti → yazılan dosya zincirinde kaçışlar iki kez yorumlandı:
`'\\b'` Python'da `\b` dizesi olmadı, `"\b"` (0x08) oldu.

## Çözüm
Yama betikleri Write aracıyla dosyaya yazılıp çalıştırıldı; bozuk karakter Python ile düzeltildi
(`0x08` sayımı 1 → 0).

## Kanıt
`tests/test_derin_mod.py` 11/11 geçti; `tests/test_source_hygiene.py` geçiyor.

## Önleme
Kaçış/tırnak içeren yamaları heredoc'a gömme; Write/Edit aracıyla yaz (R-01 ile aynı ruh). Daha önce
bir heredoc yamasında `\n` da bozulmuştu.

## İlgili dosyalar
- src/evren_studio/agent/deep.py
