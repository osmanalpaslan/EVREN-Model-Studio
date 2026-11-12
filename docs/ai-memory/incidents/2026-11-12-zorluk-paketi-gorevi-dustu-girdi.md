---
id: 2026-11-12-zorluk-paketi-gorevi-dustu-girdi
tarih: 2026-11-12
tur: yanlis-iddia            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: test
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: gemma-4-31b
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gozlem, zorluk, R-25, R-22]
kurallar: [R-25]
---

# Zorluk paketi görevi düştü: girdi

## Belirti
Gözlem `2983bc967976`: e2e_basarisiz — kalan kontroller: "girdi beklediğini açıkladı"; görev girdi, model gemma-4-31b,
sonuç 0/1, durma done (2026-11-06, sürüm 0.2.0+dbacba9).

## Kök neden
Doğrulandı — denetleyicinin YANLIŞ ALARMI. Gemma'nın gerçek cevabı (build/motor_karnesi/gemma-4-31b/rapor.json):
"`oyun.py` dosyası kullanıcıdan isim girişi beklediği için doğrudan çalıştırdığımda hata verdi. Ancak örnek bir giriş
("Kullanıcı") sağlayarak çalıştırdığımda çıktı şu şekilde oldu: Merhaba Kullanıcı". Açıklama doğru; ama
`kontrol_girdi` yalnız input/girdi/eof/klavye/ad gir/adınız arıyordu — "giriş", "isim", "kullanıcıdan" yoktu. Ayrıca
Türkçe büyük harf ("GİRİŞ".lower() → birleşik noktalı i) eşleşmeyi bozardı.

## Çözüm
1. tests/e2e_zorluk_real_api.py `kontrol_girdi`: GIRDI_ANAHTAR'a giriş/isim/stdin/adını/kullanıcıdan; Türkçe küçük harf
   normalleştirmesi (İ→i, I→ı) + düz lower() birlikte. Denetleyici bilinen DOĞRU (gerçek gemma cevabı dahil) ve bilinen
   YANLIŞ (açıklamasız "Çıktı: Merhaba Ali") cevaplarla sınanır (R-25).
2. Uygulama: `tools.stdin_hint` — program klavyeden girdi bekleyip girdisiz çalıştırılınca (Python EOFError, PowerShell
   Read-Host NonInteractive) komut sonucuna ipucu: kullanıcıya açıkla, girdiyi komutla verirsen belirt, uydurma girdinin
   çıktısını gerçekmiş gibi sunma. Çıkış koduna BAKILMAZ: Read-Host girdisiz hata yazar ama betik 0 ile biter (ölçüldü).
3. Analiz sırasında bulunan ayrı hata: borulanan metne BOM ekleniyordu → kayıt
   2026-11-12-ajan-komutlarinda-pipe-edilen-metnin-basina-bom-ekleniyordu.

## Kanıt
Gözlem `2983bc967976` (dal gozlem-kayitlari): 1 kez, 1 makine, ilk 2026-11-06T19:36:54+00:00, son 2026-11-06T19:36:54+00:00,
sürümler 0.2.0+dbacba9. tests/test_zorluk_denetleyici.py 15 (denetleyici doğru 4 / yanlış 3; ipucu tetiklenen 2 /
tetiklenmeyen 3 — "unexpected EOF while parsing" tetiklemez; gerçek PowerShell'de python EOFError, Read-Host çıkış 0,
girdi verilince ipucu yok); mutasyon 7/8 (kaçan: PowerShell mesajındaki iki imza ifadesi her zaman birlikte geçiyor —
bilinçli yedeklik).

## Önleme
R-25 zaten "kabul denetimini bilinen doğru ve yanlış cevapla sına" diyor; girdi denetleyicisi artık birim testiyle
korunuyor. Yeni bir zorluk görevi denetleyicisi eklenince aynı düzen (gerçek model cevabıyla sınama) uygulanır.

## İlgili dosyalar
- tests/e2e_zorluk_real_api.py (kontrol_girdi, GIRDI_ANAHTAR)
- src/evren_studio/agent/tools.py (stdin_hint, STDIN_HINT), src/evren_studio/agent/runner.py (_run_exec)
- tests/test_zorluk_denetleyici.py
