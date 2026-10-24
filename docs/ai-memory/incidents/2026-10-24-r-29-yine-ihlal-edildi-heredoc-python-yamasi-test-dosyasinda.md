---
id: 2026-10-24-r-29-yine-ihlal-edildi-heredoc-python-yamasi-test-dosyasinda
tarih: 2026-10-24
tur: surec            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: surec
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Git Bash, Python 3.12.10
etiketler: [heredoc, R-29]
kurallar: [R-29]
---

# R-29 yine ihlal edildi: heredoc Python yamasi test dosyasinda ters boluleri bozdu

## Belirti
tests/test_her_yere_birak.py'yi bash heredoc içindeki Python `str.replace` betiğiyle değiştirirken yeni metindeki
`"\\n"` kaçışları Python dizesinde gerçek satır sonuna dönüştü → "unterminated string literal" toplama hatası.

## Kök neden
Doğrulandı: R-29'un yasakladığı yöntem (heredoc ile Python yaması) kullanıldı; yamanın yeni metni normal (raw
olmayan) Python dizesiydi. Bu oturumda birkaç küçük yama daha heredoc ile yapıldı (ters bölüsüz oldukları için
bozulmadı, ama yine kurala aykırıydı).

## Çözüm
Bozulan iki satır Edit aracıyla düzeltildi; testler geçti. Sonraki değişiklikler Write/Edit ile yapıldı.

## Kanıt
pytest tests/test_her_yere_birak.py → 4 passed (düzeltmeden sonra).

## Önleme
R-29 geçerli; kaynak/test dosyasını yalnız Write/Edit ile değiştir — "küçük yama" istisnası yok.

## İlgili dosyalar
tests/test_her_yere_birak.py
