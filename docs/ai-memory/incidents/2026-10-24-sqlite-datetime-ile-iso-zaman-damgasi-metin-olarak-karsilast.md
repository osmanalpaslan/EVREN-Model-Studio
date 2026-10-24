---
id: 2026-10-24-sqlite-datetime-ile-iso-zaman-damgasi-metin-olarak-karsilast
tarih: 2026-10-24
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: veri
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [sqlite, zaman-damgasi, karsilastirma]
kurallar: []
---

# SQLite datetime ile ISO zaman damgası metin olarak karşılaştırılınca aynı gün hep "yeni" sayılır

## Belirti
`recent_model_calls` ilk yazımında `at >= datetime('now', '-6 hours')` kullanıldı. `at` uygulamada
`2026-10-24T07:41:16+00:00` biçiminde yazılıyor; SQLite `datetime()` `2026-10-24 01:41:16` döndürür. Metin
karşılaştırmasında `T` (0x54) boşluktan (0x20) büyük olduğu için aynı günün tüm kayıtları pencerede sayılırdı.
Commit'ten önce elle denemede fark edildi (7 saat önceki kayıt 6 saatlik pencerede çıkmadı mı diye bakıldı).

## Kök neden
Doğrulandı. İki farklı zaman biçimi metin olarak karşılaştırıldı.

## Çözüm
`strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)` ile aynı biçimde karşılaştırma (sorgu ve budama).

## Kanıt
Elle deneme: 7 saat önceki kayıt 6 saatlik pencerede yok, 8 saatlikte var.

## Önleme
`utcnow_iso()` ile yazılan sütunu SQLite zaman işleviyle karşılaştırırken `strftime` ile aynı biçimi üret.

## İlgili dosyalar
- src/evren_studio/db.py
