---
id: 2026-11-06-dongu-bekcisi-turu-durdurdu
tarih: 2026-11-06
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: bilinmiyor
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gozlem, masaustu, qa, dongu-bekcisi]
kurallar: [R-19, R-22]
---

# Döngü bekçisi turu durdurdu

## Belirti
Gözlem ajanından (uygulama çalışırken, otomatik ve temizlenmiş):
ajan_anomali
Konum:
- (yığın izi yok)
Ayrıntı:
- model: deepseek-v4.1-flash
- rol: kod
- olay: loop

Hepsi masaüstü QA gerçek denemelerinde (2026-11-05 akşam, 2026-11-06 19:32). 2026-11-06 koşusunun model kaydında:
`qwen3.8-flash-next qa loop: “MCP masaustu: WindowText — EVREN Hesap Deneme” 3 kez aynı sonuçla tekrarlandı` → `switch
qwen → deepseek-v4.1-flash` → deepseek ~19 dk, 21 çağrı × ~41 sn → damla kuralıyla qwen'e geri dönüş.

## Kök neden
Doğrulandı (kod + gerçek kayıt): `AgentRunner._guard` aynı araç+parametre tekrarını sayar ve sayacı yalnız başarılı
DOSYA YAZIMINDA sıfırlar. Masaüstü eylemleri (Click/Type/Shortcut — MCP EXEC) sayacı sıfırlamıyordu; QA'nın meşru
"sonucu oku → Topla'ya tıkla → yeniden oku" akışında ekran değiştiği hâlde aynı WindowText/Snapshot "döngü" sayıldı.
Bekçinin turu durdurması/yedeğe geçirmesi QA'yı en yavaş motora taşıdı (QA süresinin büyük kısmı).

## Çözüm
`runner._guard`: başarılı masaüstü EYLEMİ (`mcp__masaustu__*`, EXEC) masaüstü OKUMALARININ sayacını sıfırlar (dosya
yazımı gibi); başarısız eylem sıfırlamaz; eylemlerin kendi tekrarı sayılmaya devam eder (uyarı 4, durma 6 — "art arda
hızlı tıklama" senaryosu için okumadan biraz yüksek). Arada eylem yoksa aynı okuma yine 3. kezde durur.

## Kanıt
Gözlem `cf3c8b0737b8` (dal gozlem-kayitlari): 7 kez, 1 makine, ilk 2026-11-05T19:07:47+00:00, son 2026-11-06T16:32:41+00:00,
sürümler 0.2.0+2a798a3, 0.2.0+b940200, 0.2.0+d38e945, 0.2.0+ecd9cbc.
Testler (tests/test_masaustu_otomatik.py, gerçek tur akışı R-31): arada tıklama → döngü değil; arada eylem yok → döngü;
3 kasıtlı tıklama serbest, 6 tekrar yakalanır; başarısız tıklama sayacı sıfırlamaz. test_loop_guard değişmeden geçti.
Mutasyon 4/4 (+1 eşdeğer koşul kaldırıldı). Gerçek QA ile sonra ölçümü: bu kaydın ardından (CHALLENGE_RESULTS).

## Önleme
Döngü bekçisine yeni bir "durum değiştiren" araç türü eklendiğinde (dosya yazımı, masaüstü eylemi, tarayıcı eylemi)
okumaların sayacını sıfırlayıp sıfırlamadığını tur akışından test et (R-22: tetiklenen + tetiklenmeyen).

## İlgili dosyalar
- src/evren_studio/agent/runner.py (`_guard`, DESKTOP_PREFIX, DESKTOP_ACTION_WARN/STOP)
- tests/test_masaustu_otomatik.py
