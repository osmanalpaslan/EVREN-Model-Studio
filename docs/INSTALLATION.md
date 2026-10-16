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

1. Uygulama açılınca **Ayarlar** sayfasına gidin.
2. **API Anahtarı** alanına EVREN anahtarınızı yapıştırıp **Kaydet**e
   basın. Anahtar Windows Credential Manager'da saklanır; ekranda asla
   tam görünmez.
3. **API Bağlantı Testi** sayfasından bağlantıyı doğrulayın.
4. **Chat** sayfasında model seçip sohbet edin. Yanıtlar akış halinde
   gelir, mesajlar bilgisayarınızda saklanır.
5. Sağlayıcı sorunu şüphesinde **EVREN Durum İzleme** sayfasından 30
   dakikalık izlemeyi başlatın.

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
