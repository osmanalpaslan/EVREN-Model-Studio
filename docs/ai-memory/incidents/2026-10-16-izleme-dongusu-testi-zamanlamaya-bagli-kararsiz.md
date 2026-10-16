---
id: 2026-10-16-izleme-dongusu-testi-zamanlamaya-bagli-kararsiz
tarih: 2026-10-16
tur: hata
onem: dusuk
durum: izleniyor
alan: test/izleme
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor:
cozen_model:
ortam: Windows 11, Python 3.12, pytest 9.1
etiketler: [flaky, zamanlama, monitor]
kurallar: [R-08]
---

# İzleme döngüsü testi zamanlamaya bağlı ve kararsız

## Belirti
Tam test paketi çalışırken bir kez:
`test_dongu_30_dakika_planina_uyar — AssertionError: 30 dk / 5 dk planı
~7 kontrol üretmeli (başlangıç dahil); 3 oldu`. Tek başına 3 kez çalıştırıldı:
her seferinde geçti; değişiklikten önceki `db.py` ile de geçti.

## Kök neden
Tahmin: test 0,05 sn aralık / 0,3 sn süreyle gerçek uyku kullanıyor. Paket
yükü altında (aynı anda PowerShell alt süreçleri başlatan testler)
iş parçacığı zamanlaması kayıyor ve süre dolmadan daha az tur atılıyor.

## Çözüm
Henüz yok (kod değiştirilmedi, R-08). Olası çözüm: izleme ajanına
enjekte edilebilir saat/uyku işlevi ekleyip testte sanal zaman kullanmak
veya kontrol sayısı yerine planlanan zamanları doğrulamak.

## Kanıt
2026-10-16 Claude Code oturumu: tam paket 1 başarısız / 100 geçti, tekrar
koşularda 101-104/104 geçti.

## Önleme
R-08. Tekrar düşerse bu kayda tarih ve koşulu ekle.

## İlgili dosyalar
tests/test_db_recovery_monitor.py, src/evren_studio/monitor.py
