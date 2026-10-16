# Kurulum ve Kullanım

## Gereksinimler

- Windows 10/11 (64 bit)
- Python 3.12 (kullanıcı kapsamında kurulu: `%LOCALAPPDATA%\Programs\Python\Python312`)
- İnternet bağlantısı (yalnızca EVREN API'sine erişim için)

## Kurulum (bir kez)

```powershell
cd C:\Projects\AI-Atolye\EVREN-Model-Studio
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

## Çalıştırma

En kolay yol:

```
C:\Projects\AI-Atolye\EVREN-Model-Studio\run.bat
```

veya PowerShell'den:

```powershell
cd C:\Projects\AI-Atolye\EVREN-Model-Studio
.\.venv\Scripts\python.exe -m evren_studio
```

## İlk kullanım

1. Karşılama ekranındaki **Anahtar gir** düğmesine (veya sol alttaki
   **Ayarlar**'a) tıklayın; EVREN anahtarınızı yapıştırıp **Kaydet**e
   basın. Anahtar Windows Credential Manager'da saklanır; ekranda asla
   tam görünmez. Her bilgisayarda bir kez girilir.
2. Sol menüden **Bağlantı Testi** ile bağlantıyı doğrulayın.
3. **Yeni oturum** → karşılama ekranında **proje klasörünü** seçin (kod
   ajanı) veya **Klasörsüz sohbet** ile genel sohbet edin.
4. Yazma kutusunun altından çalışma modunu (Plan / Onaylı / Otomatik
   düzenleme) ve modeli seçin; görevi yazıp Enter'a basın.
5. Ajanın önerdiği değişiklikleri onay kutusundan inceleyin; sağ paneldeki
   **Değişiklikler** sekmesinden istediğiniz an geri alın.
6. İlk kez çalıştığınız projede `/init` yazarak EVREN.md proje hafızasını
   oluşturun.
7. Sağlayıcı sorunu şüphesinde **EVREN Durum İzleme** sayfasından 30
   dakikalık izlemeyi başlatın.

## Yeni bir bilgisayarda geliştirmeye devam etme

```powershell
cd C:\Projects\AI-Atolye
gh repo clone osmanalpaslan/EVREN-Model-Studio
cd EVREN-Model-Studio
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
```

API anahtarı ve yerel veriler (oturumlar, hata kayıtları) bilgisayarlar
arasında taşınmaz; anahtarı yeni bilgisayarda yeniden girin.

## Testleri çalıştırma

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # birim testleri (ağ gerekmez)
.\.venv\Scripts\python.exe tests\smoke_ui.py     # arayüz duman testi
.\.venv\Scripts\python.exe -u tests\e2e_real_api.py  # gerçek API (anahtar gerekir)
```

## Verileriniz

- Ayarlar: `%LOCALAPPDATA%\EVREN-Model-Studio\config.json`
- Veritabanı: `%LOCALAPPDATA%\EVREN-Model-Studio\evren.db`
- API anahtarı: Windows Credential Manager ("EVREN-Model-Studio" kaydı)
- Ayarlar sayfasından JSON dışa aktarma ve tam silme yapılabilir.

## Sorun giderme

- **"Python bulunamadı"**: run.bat venv'i doğrudan kullanır; Python
  PATH'te olmak zorunda değildir.
- **Anahtar kaydedilemedi**: Windows "Credential Manager" hizmeti
  çalışıyor olmalı. Yardım > Tanılama'yı çalıştırın.
- **503 sağlıklı endpoint yok**: sağlayıcı kaynaklıdır; bekleyin veya
  başka doğrulanmış model seçin. Hata Merkezi'nde Türkçe öneriyi okuyun.
