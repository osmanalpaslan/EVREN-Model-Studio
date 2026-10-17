---
id: 2026-10-17-claude-code-masaustu-claude-code-masaustu-ortam-denetimi-ve-p
tarih: 2026-10-17
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/ortam-denetimi
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Claude Code masaüstü: ortam denetimi ve program kurulumu

## Görev
Kullanıcı: proje için gereken programlar eksikse uygulama tespit edip kursun;
kullanıcı Ayarlar'dan "Otomatik" (sormadan kur) veya "Manuel" (kurulum bildirimi,
onayla kur) seçebilsin. Bu seçim ajanın çalışma modundan bağımsız.

## Yapılanlar
- `agent/environment.py` (Qt'siz): proje dosyalarından gereksinim tespiti
  (package.json+pnpm/yarn, pyproject/*.py, uv.lock, go.mod, Cargo.toml,
  .csproj/.sln, pom.xml/gradle, .git), PATH denetimi + sürüm, kurulum planı
  (bilinen liste: git, python, uv, node, pnpm, yarn, go, rust, dotnet, java;
  winget, pnpm/yarn için önce npm -g), gereksinim zinciri (pnpm → node), kurulum
  kilidi (aynı anda tek kurulum), kurulum sonrası PATH yenileme (kayıt defteri).
- Ajan aracı `install_program` (EXEC türü → Plan modunda engelli): Otomatik →
  sormadan; Manuel → "X kurulsun mu?" onayı (Kur / bu oturumda izin / Reddet).
  Sistem istemine "# Ortam denetimi" bölümü (durum + kurallar + `.cmd` kuralı).
- Arayüz: klasör bağlanınca / oturum açılınca arka planda denetim (R-04);
  eksik varsa `InstallCard` (Manuel: Kur / Şimdi değil; Otomatik: ilerleme).
  Ayarlar > Kod Ajanı > "Eksik program kurulumu" (varsayılan Otomatik).
- Ayarlar açıklaması düzeltildi ("Komutlar hiçbir modda onaysız çalışmaz" artık yanlıştı).
- conftest: testler ASLA gerçek kurulum yapmaz (otomatik kilit).

## Test sonuçları
- pytest tam paket geçti (yeni tests/test_environment.py: 19 test).
- Gerçek kurulum: `npm install -g yarn` 14 sn, hemen bulundu (PATH yenileme);
  9 winget kimliği `winget show` ile doğrulandı (kurmadan).
- Gerçek API ajan testi (yarn eksik, `yarn --version` → SURUM.txt):
  Manuel+Reddet: 1 kez soruldu, kurulmadı, model dolanmaya çalışmadı ·
  Manuel+Onay: kuruldu, dosya doğru · Otomatik (qwen, deepseek): sorulmadan
  kuruldu, dosya doğru. `.cmd` kuralından sonra hatalı deneme yok.
- Ekran görüntüleri (QT_QPA_PLATFORM=windows) incelendi: Ayarlar satırı, Manuel
  kart, kurulum sonrası kart, "Go kurulsun mu?" onay kutusu düzgün.

## Sorunlar ve kayıtlar
- 2026-10-17-npm-ile-kurulan-araclarin-ps1-kabugu-powershell-betik-politi (çözüldü;
  `-ExecutionPolicy Bypass` güvenlik nedeniyle UYGULANMADI, `.cmd` kuralı)

## Sonraki motor için notlar
- winget makine kapsamlı kurulumlar (Node, Go, Git, .NET, Java) Windows yönetici
  onayı (UAC) penceresi açabilir; bu uygulamanın dışında, engellenemez. Kullanıcı
  orada "Evet" demezse kurulum başarısız döner ve kartta görünür.
- Gerçek winget kurulumu (makine kapsamlı) bu oturumda denenmedi; yalnız npm yolu
  gerçek kuruldu, winget kimlikleri doğrulandı.
- Bilinen listeye program eklerken `winget show --id <ID> -e` ile doğrula ve
  test_environment.py'ye ekle.
