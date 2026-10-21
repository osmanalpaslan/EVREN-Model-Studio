---
id: 2026-10-21-kenar-cubugu-icin-splitter-da-hata-yok-iddiasi-surukleme-den
tarih: 2026-10-21
tur: yanlis-iddia            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [kenar-cubugu, yanlis-iddia, dogrulama]
kurallar: [R-05, R-27]
---

# Kenar çubuğu için "splitter'da hata yok" iddiası sürükleme denenmeden yazıldı

## Belirti
2026-10-19 kaydı (2026-10-19-uygulama-ajani-kendi-kaynagini-duzenlerken-uygulamayi-acilma) "Splitter'da
hata YOK: 4 ayar × 17 adımlık gerçek pencere senaryosunda ... genişlik hiç 0'a düşmedi" diyordu.
Kullanıcı 2026-10-21'de çubuğun sürüklemede kaybolmaya devam ettiğini ve hiç düzelmediğini bildirdi.

## Kök neden
Doğrulandı. O senaryo pencereyi büyütme/küçültme, Ctrl+B/J, sayfa geçişi ve simge durumunu denedi;
kullanıcının yaptığı şeyi — kenar tutamacını FAREYLE SÜRÜKLEMEYİ — denemedi. Ayrıca ölçülen değer
("genişlik 0'a düşmedi") yanlış değişmezdi: çubuk 0 genişliğe değil, negatif x konumuna itiliyordu.
Belirtiyi yeniden üretmeden "hata yok" yazıldı (aynı motor, Claude Code / claude-opus-5-5).

## Çözüm
Eski kayda düzeltme notu eklendi (silinmedi). Gerçek kök neden ve düzeltme:
2026-10-21-kenar-cubugu-suruklenince-kayboluyordu-orta-yiginin-en-kucuk.

## Kanıt
Yeni sürükleme testleri eski kodda düşüyor (tests/test_kenar_cubugu_surukleme.py).

## Önleme
R-05'in ruhu: kullanıcının bildirdiği eylemi aynen yeniden üretmeden "hata yok" deme. R-27: splitter
için çok adımlı sürükleme testi ve "görünür bölge + x >= 0" değişmezi.

## İlgili dosyalar
- docs/ai-memory/incidents/2026-10-19-uygulama-ajani-kendi-kaynagini-duzenlerken-uygulamayi-acilma.md
