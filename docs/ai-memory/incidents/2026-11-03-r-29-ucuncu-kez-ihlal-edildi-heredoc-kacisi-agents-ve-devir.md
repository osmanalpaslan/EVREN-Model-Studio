---
id: 2026-11-03-r-29-ucuncu-kez-ihlal-edildi-heredoc-kacisi-agents-ve-devir
tarih: 2026-11-03
tur: surec            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: surec
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, Git Bash
etiketler: [heredoc, kacis, R-29]
kurallar: [R-29, R-10]
---

# R-29 üçüncü kez ihlal edildi: heredoc kaçışı AGENTS ve DEVIR notuna kontrol karakteri yazdı

## Belirti
Bash heredoc içinde çalıştırılan Python ile Markdown yamaladım (kendi hatam). (1) AGENTS.md gözlem adımında
`tools\ai_memory.py` → `tools<BEL>i_memory.py` (2 satır) oldu ve PR #33 ile master'a birleşti — tüm motorların
okuduğu talimat dosyası. (2) DEVIR_NOTU'nda `build\faz\acik` → `build<FF>az<BEL>cik`. Python bir kez
`SyntaxWarning: invalid escape sequence` verdi; mevcut testler (mojibake, BOM) kontrol karakterini görmüyordu.

## Kök neden
Doğrulandı: Python dizgesindeki `\a`, `\f` kaçışları gerçek kontrol karakterine dönüştü; R-29 yalnız `.py`
dosyası yazmayı anıyordu, ben Markdown yamaladığım için kuralı "kapsam dışı" saydım. Önceki iki ihlal:
2026-10-21-bash-heredoc-…, 2026-10-24-r-29-yine-ihlal-edildi-….

## Çözüm
- İki dosya Write aracıyla yazılan küçük betiklerle düzeltildi (AGENTS 2 yer, DEVIR 1 yer).
- Kalıcı önlem: tests/test_source_hygiene.py `test_metin_dosyalarinda_kontrol_karakteri_yok` — src/tests/tools/
  docs ve kök talimat dosyalarında sekme/satır sonu dışındaki C0 karakteri pytest'i düşürür. Eklenir eklenmez
  master'daki AGENTS.md bozulmasını yakaladı.

## Kanıt
`git show master:AGENTS.md | grep -c $'\a'` → 2 (düzeltmeden önce); yeni test bozuk sürümde düştü, düzeltince
5/5 geçti.

## Önleme
R-29 kapsamı: ters bölü içeren HER metin (Markdown dahil) heredoc'lu Python'la yazılmaz; Edit/Write aracı veya
Write ile yazılmış betik kullanılır. Hijyen testi artık bunu yakalar.

## İlgili dosyalar
- tests/test_source_hygiene.py
- AGENTS.md
- docs/DEVIR_NOTU.md
