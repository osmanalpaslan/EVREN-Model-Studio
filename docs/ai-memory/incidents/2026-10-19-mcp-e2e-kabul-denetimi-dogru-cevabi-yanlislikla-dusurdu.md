---
id: 2026-10-19-mcp-e2e-kabul-denetimi-dogru-cevabi-yanlislikla-dusurdu
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: test
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [test, e2e, kabul]
kurallar: [R-25]
---

# MCP e2e kabul denetimi doğru cevabı yanlışlıkla düşürdü

## Belirti
e2e_mcp_real_api.py "soru" görevinde iki koşu 4/5 "KALDI" dedi; cevap okununca doğruydu
(vergi_hesapla_eski "sayılmaz" diye ayrılmıştı).

## Kök neden
Doğrulandı: denetim "eski" geçen HER satırda ayrım kelimesi arıyordu; tablo satırlarında kelime
başlıktaydı. Benim test hatam.

## Çözüm
Denetim, vergi_hesapla_eski geçişlerinin en az birinin ±300 karakter yakınında ayrım
("farklı/ayrı/değil/sayılma/hariç/benzer") arar; kayıtlı doğru cevap ve bilinen yanlış cümleyle sınandı.

## Kanıt
Kayıtlı cevaplar yeniden puanlandı: 4/4 doğru; yanlış örnek düşüyor.

## Önleme
R-25: kabul denetimini önce bilinen doğru ve yanlış cevapla sına.

## İlgili dosyalar
tests/e2e_mcp_real_api.py
