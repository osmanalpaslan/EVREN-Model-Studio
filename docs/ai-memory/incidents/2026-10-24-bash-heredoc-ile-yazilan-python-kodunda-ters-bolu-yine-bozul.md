---
id: 2026-10-24-bash-heredoc-ile-yazilan-python-kodunda-ters-bolu-yine-bozul
tarih: 2026-10-24
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: araclar
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [heredoc, bash, regex]
kurallar: [R-29]
---

# Bash heredoc ile yazılan Python kodunda ters bölü yine bozuldu (regex karakter sınıfı)

## Belirti
F2 sırasında `agent/modelstats.py`'ye `cat >> … <<'EOF'` ile eklenen kodda `r"[\w\-./\\]+"` dosyaya
`r"[\w\-./\]+"` olarak yazıldı; modül içe aktarılırken `re.error: unterminated character set` verdi. Aynı
oturumda iki Python yaması da heredoc'ta tırnak/ters bölü yüzünden çalışmadı (`unexpected EOF`).

## Kök neden
Doğrulandı (dosyadaki fark): Bash aracı üzerinden giden heredoc gövdesinde çift ters bölü teke indi. 2026-10-21
kaydındaki `\b` sorununun aynı sınıfı; o kayıttan sonra yalnız "dikkat et" notu kalmıştı, kural yoktu.

## Çözüm
Bozulan iki satır düzenleyici aracıyla (Edit) düzeltildi; sonraki tüm yamalar Write aracıyla geçici klasörde
`.py` dosyasına yazılıp çalıştırıldı. İçe aktarma denetimi ve pytest hatayı hemen yakaladı.

## Kanıt
`python -c "import evren_studio.ui.session_view"` → re.error; düzeltmeden sonra içe aktarma ve
`tests/test_autopro_akilli.py` geçti.

## Önleme
R-29: ters bölü, regex veya iç içe tırnak içeren Python kodunu/yamasını bash heredoc ile yazma.

## İlgili dosyalar
- src/evren_studio/agent/modelstats.py
- docs/ai-memory/incidents/2026-10-21-bash-heredoc-icindeki-python-yamasi-regex-teki-b-yi-geri-sil.md
