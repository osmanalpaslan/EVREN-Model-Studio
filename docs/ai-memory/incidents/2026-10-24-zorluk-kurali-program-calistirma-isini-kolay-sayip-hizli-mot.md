---
id: 2026-10-24-zorluk-kurali-program-calistirma-isini-kolay-sayip-hizli-mot
tarih: 2026-10-24
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, gerçek EVREN API
etiketler: [autopro, A6, zorluk, R-22]
kurallar: [R-21, R-22]
---

# Zorluk kuralı program çalıştırma işini kolay sayıp hızlı motora gönderdi

## Belirti
F2 sonrası zorluk paketi auto-pro 10/12: `girdi` görevi ("oyun.py'yi çalıştır ve çıktısını bana söyle") A6 kuralıyla
"kolay" sayıldı, `kod_kolay` → gemma-4-31b'ye gitti; gemma programın girdi beklediğini söylemek yerine girdiyi
kendisi ("Kullanıcı") verip çıktıyı raporladı. Birim testim bu cümleyi bilerek "kolay" örneği olarak yazmıştı.

## Kök neden
Doğrulandı: kolay kuralı yalnız uzunluk, dosya sayısı ve test/çok dosya sözcüklerine bakıyordu; program
çalıştırmanın yargı gerektirdiğini (girdi bekleyen komut, yan etki) hesaba katmadım. gemma'nın "testi kandırma"
eğilimi MODEL_CAPABILITIES.md'de zaten yazılıydı.

## Çözüm
`modelstats._NOT_EASY_RE`'ye "çalıştır|başlat|komut" eklendi; birim testte cümle "kolay değil" listesine taşındı.
Aynı ölçümde kaçan iki ifade de eklendi: web için "javascript", metin için "yazım ve noktalama".

## Kanıt
build/zorluk/auto-pro/rapor.json (ilk koşu), `tests/test_autopro_akilli.py::test_cok_dosyali_test_veya_uzun_is_kolay_degil`,
ikinci tam zorluk koşusu: CHALLENGE_RESULTS.md "Rol paketleri ve Auto Pro akıllı seçim F2".

## Önleme
R-21/R-22: yeni otomatik yönlendirme kuralını hedef görevlerle değil zorluk paketinin TAMAMIYLA ölç; birim testteki
"tetiklenmeli" örnekleri modelin zayıf olduğu bilinen davranışlara karşı gözden geçir.

## İlgili dosyalar
- src/evren_studio/agent/modelstats.py
- tests/test_autopro_akilli.py
