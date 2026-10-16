---
id: 2026-10-16-dosya-yazimindan-hemen-sonra-gecici-errno-22-kilidi
tarih: 2026-10-16
tur: ortam            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: kabul-edildi
alan: ortam
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor:
cozen_model:
ortam: Windows 11 + Comodo, Python 3.12.10
etiketler: [comodo, dosya-kilidi]
kurallar: []
---

# Dosya yazımından hemen sonra geçici Errno 22 kilidi

## Belirti
`session_view.py` yazıldıktan hemen sonra okuma/yazma denemesi iki kez
`OSError: [Errno 22] Invalid argument` verdi. Birkaç saniye sonra aynı işlem
sorunsuz çalıştı.

## Kök neden
Tahmin: bu bilgisayardaki Comodo (gerçek zamanlı tarama / HIPS) yeni yazılan
.py dosyasını kısa süre kilitliyor. Diğer geliştirme bilgisayarlarında Comodo
yok; orada gözlenmedi. Doğrulanmadı.

## Çözüm
`sleep 3` sonra yeniden denemek yetti. Kod değişikliği gerekmedi.

## Kanıt
2026-10-16 sağlayıcı oturumunda iki kez gözlendi; tekrar denemede geçti.

## Önleme
Bu hatayı görürsen kodu değiştirme; birkaç saniye bekleyip tekrar dene. Sürekli
oluyorsa proje klasörünü Comodo istisnalarına eklemeyi kullanıcıya öner
(yönetici yetkisi gerektirebilir: önce onay al).

## İlgili dosyalar
- src/evren_studio/ui/session_view.py
