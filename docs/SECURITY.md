# Güvenlik Dokümanı

## API anahtarı yaşam döngüsü

- **Saklama**: yalnızca Windows Credential Manager (`keyring`).
  Kayıt adı: `EVREN-Model-Studio` / `evren_api_key`.
- **YASAK olanlar**: kaynak kodu, config.json, loglar, hata kayıtları,
  Git geçmişi, istemci hata gövdeleri, üçüncü taraf servisler.
- **Gösterim**: daima maskeli (`evren_ll...dGXQ` biçimi).
- **Silme**: Ayarlar > Anahtarı Sil (Credential Manager kaydı silinir).
- Credential Manager kullanılamazsa düz metne SESSİZCE GEÇİLMEZ; açık hata
  gösterilir.

## Gizlilik

- Her API isteği, mesaj içeriğinizi EVREN sunucularına gönderir (ana sayfada
  ve ilk kullanımda belirtilir).
- Sohbetler, hata kayıtları ve izleme verileri YALNIZCA yerel SQLite'ta
  tutulur; hiçbir telemetri/analitik YOKTUR.
- Tek dış ağ adresi: kullanıcının yapılandırdığı EVREN API'si + izlenen
  duyuru sayfası. Başka sağlayıcıya istek YAPILMAZ.
- Hata kayıtlarına anahtar/token/kişisel veri YAZILMAZ; mesaj bağlamı
  ilk 60 karakterle sınırlıdır; hata gövdeleri maskelemeye tabidir.

## Taşıma güvenliği

- HTTPS + sertifika doğrulama her zaman açık (`verify=True`).
- Sertifikayı devre dışı bırakan seçenek YOKTUR.

## Kod çalıştırma güvenliği (MVP)

- MVP'de komut çalıştırma ÖZELLİĞİ YOKTUR.
- Code Studio düzenlemeleri yalnızca kullanıcının açtığı proje klasörüyle
  sınırlıdır; 2 MB üstü ve ikili görünümlü dosyalar açılmaz; proje kökü
  dışına semolik bağlantıyla çıkış engellenir.
- Kaydetme her zaman açık kullanıcı onayı ister.

## Repo hijyeni

- `.gitignore`: `.venv`, `data/`, `*.db`, `logs/*.log`, `.env`, `secrets*`.
- Secret taraması: `git grep -IiE "(evren_ll|api[_-]?key|token)" -- src`
  boş dönmelidir; commit öncesi kontrol edilir.
- Veritabanı ve ayar dosyaları LOCALAPPDATA'da, depo DIŞINDADIR.

## Risk bildirimleri (kullanıcıya)

- Ücretsiz erişim `free_until: 2026-11-01` ile sınırlı görünüyor; kalıcı
  olduğu VARSAYILMAZ; Model sayfası canlı fiyat gösterir.
- Kota: 5 dk pencere + günlük 15M token; Kota sayfası görünür.
- Kullanıcı adına şart kabulü, ücretli hizmet veya abonelik BAŞLATILMAZ.

## Olay müdahalesi

1. Anahtar sızdığından şüphelenilirse: EVREN panelinden anahtarı iptal
   edin, uygulamada silin, yenisini girin.
2. `docs/SECURITY.md` ve CHANGELOG'a olay notu ekleyin.
