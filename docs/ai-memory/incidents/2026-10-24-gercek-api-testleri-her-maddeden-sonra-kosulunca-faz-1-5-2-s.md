---
id: 2026-10-24-gercek-api-testleri-her-maddeden-sonra-kosulunca-faz-1-5-2-s
tarih: 2026-10-24
tur: surec            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: test
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, gerçek EVREN API
etiketler: [test-suresi, R-13, R-21]
kurallar: [R-13, R-21, R-30]
---

# Gerçek API testleri her maddeden sonra koşulunca faz 1,5-2 saat test bekliyordu

## Belirti
F2'de test süresi: pytest ~2 dk, ama gerçek API ölçümleri (3 motorlu rol paketleri ~40 dk, ikinci dizi ~60 dk,
zorluk tekrarı ~10 dk) faz başına 1,5–2 saat sürdü. Kullanıcı projenin daha hızlı ilerlemesini istedi.

## Kök neden
R-13 ve R-21 "dokunduysan çalıştır" diyordu; her madde için tekrarlanınca aynı uçtan uca testler birkaç kez koşuldu.
Çok motorlu ölçümler yalnız motor sırası değişirken gerekli.

## Çözüm
Kullanıcı onayı (2026-10-24): test değişiklik türüne göre seçilir; gerçek API testleri (R-13, zorluk paketi R-21)
faz sonunda, birleştirmeden ÖNCE bir kez; çok motorlu ölçüm yalnız motor sırası değişirken veya model listesi
değişince. R-13, R-21 güncellendi; R-30 eklendi.

## Kanıt
Kullanıcı mesajı "onaylıyorum başla" (önerilen tablo üzerine).

## Önleme
R-30.

## İlgili dosyalar
- docs/ai-memory/RULES.md
