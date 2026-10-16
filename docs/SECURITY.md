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

## Kod ajanı güvenliği (Aşama 2)

- **Sınır**: tüm araçlar oturumun proje klasörüyle sınırlıdır. Yollar
  çözülür; `..` veya sembolik bağlantıyla kök dışına çıkan yollar reddedilir.
  `.git` klasörüne doğrudan yazılamaz. İkili ve 512 KB üstü dosyalar
  okunmaz; 2 MB üstü içerik yazılmaz.
- **Model çıktısı komut değildir**: yerel `tool_calls` veya metin
  protokolündeki bloklar ayrıştırılır, araç adı ve parametreleri
  doğrulanır, izin politikasından geçer. Bilinmeyen araçlar reddedilir.
- **Modlar (Claude Code'a denk):** Manuel (her düzenleme ve komut sorulur) ·
  Düzenlemeleri kabul et (proje içi düzenlemeler onaysız, komutlar sorulur) ·
  Plan (yalnız okuma) · Otomatik (düzenlemeler ve GÜVENLİ LİSTEDEKİ komutlar
  onaysız; riskli ve tanınmayan komutlar sorulur). Eski anahtarlar güvenli
  eşdeğerine çevrilir: `onayli`→Manuel, `otomatik`→Düzenlemeleri kabul et
  (asla Otomatik'e değil).
- **Otomatik modun komut kararı yalnızca kurallarla** verilir
  (`agent/commands.py`): salt okuma git komutları, test/derleme/lint,
  dosya görüntüleme güvenlidir; silme, git push/reset/clean, paket kurma,
  ağdan indirme, `iex`, süreç başlatma/sonlandırma, sistem ayarı, dosyaya
  yönlendirme, satır içi kod (`python -c`) ve proje dışı yollar sorulur.
  **Uyarı:** testler ve derleme projenin kendi kodunu çalıştırır; ajanın
  yazdığı kod Otomatik modda `pytest` ile onaysız çalışabilir.
- **Korumalı dosyalar (her modda sorulur):** `.env*`, `*.pem`, `*.key`, `id_rsa*`,
  `.npmrc`, `.pypirc`, `.vscode/`, `.idea/`, `.github/workflows/`, `.claude/`,
  `.cursor/`, `.kilocode/` yazmaları; `.env*`, anahtar ve kimlik dosyalarını
  OKUMAK da sorulur (içerik EVREN'e gider) ve bu dosyalar aramaya dahil edilmez.
- **Komutlar Manuel, Düzenlemeleri kabul et ve Plan modlarında onaysız çalışmaz.** Kullanıcı tek tek onaylar ya da
  "bu oturumda hep izin ver" ile belirli bir komut önekine (örn.
  `python -m pytest`) izin verir. `; && || | > < ` $(` içeren zincirli
  komutlar önek iznine rağmen HER ZAMAN sorulur. Oturum izinleri yalnızca
  bellekte tutulur; uygulama kapanınca silinir.
- **Dosya değişiklikleri**: Onaylı modda her değişiklik diff ile gösterilir.
  Otomatik düzenleme modu kullanıcı seçimidir. Onay beklerken dosya
  dışarıdan değişirse üzerine yazılmaz. Her değişikliğin önceki/sonraki
  içeriği yerel veritabanına kaydedilir ve geri alınabilir.
- **Komut ortamı**: proje kökünde, zaman aşımıyla (varsayılan 120 sn) ve
  `CREATE_NO_WINDOW` ile çalışır; zaman aşımında süreç ağacı sonlandırılır.
  Projede `.venv` varsa PATH başına eklenir. Çıktı kısaltılarak modele
  gönderilir — **komut çıktıları ve okunan dosyalar EVREN'e gönderilir**;
  gizli bilgi içeren dosyaları ajana okutmayın.
- **İstem kuralları**: ajan istemi gizli bilgi toplamayı/göndermeyi ve proje
  dışına çıkmayı yasaklar; bu kurallar teknik engellerin YERİNE değil
  ÜSTÜNE uygulanır.
- Dosyalar sekmesindeki elle kaydetme her zaman açık onay ister.

## Repo hijyeni

- `.gitignore`: `.venv`, `data/`, `*.db`, `logs/*.log`, `.env`, `secrets*`
  (istisna: `src/evren_studio/secrets.py` — anahtar içermeyen kasa erişim
  kodu; bu istisna olmadan dosya depoya girmiyordu).
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
