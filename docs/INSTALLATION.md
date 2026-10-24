# Kurulum ve Kullanım

## En kolay yol (geliştirici olmayanlar için)

1. https://github.com/osmanalpaslan/EVREN-Model-Studio sayfasında
   **Code → Download ZIP** ile indirin ve bir klasöre çıkarın
   (ör. `Belgeler\EVREN-Studio`).
2. Klasördeki **`kurulum.bat`** dosyasına çift tıklayın. Betik:
   - Python 3.12 veya üstünü bulur; yoksa “kurulsun mu?” diye sorar ve
     `winget` ile yalnız sizin kullanıcı hesabınıza kurar (yönetici gerekmez),
   - `.venv` sanal ortamını oluşturup gerekli paketleri kurar (birkaç dakika),
   - masaüstüne ve Başlat menüsüne **EVREN Studio** kısayolu ekler.
3. Kısayolla açın; ilk açılışta EVREN API anahtarınızı girin.

Windows SmartScreen “tanınmayan uygulama” uyarısı verirse **Ek bilgi → Yine de
çalıştır** deyin (betik açık metindir, içeriğini Not Defteri ile görebilirsiniz).
`run.bat` de kurulum yapılmamışsa kurulumu kendiliğinden başlatır.

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
.\.venv\Scripts\python.exe tools\ai_memory.py kanca-kur   # ortak hafıza git kancası
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools\ai_memory.py baslangic   # önceki motorların notları
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

## Oyun araçları (isteğe bağlı, F7)

Godot ile EXE/PWA ve model dönüştürme için kurulumsuz programlar uygulama klasörünün YANINDAKİ `EVREN-Araclar`
klasöründe aranır (veya kullanıcı klasöründe `EVREN-Araclar`):

- `godot\Godot_v4.7.2-stable_win64(_console).exe` + boş `._sc_` dosyası; dışa aktarma şablonları
  `godot\editor_data\export_templates\4.7.2.stable\` altında (resmî `.tpz` içindeki `templates/`).
- `blender\blender-5.2.3-windows-x64\blender.exe`
- `godot-mcp\build\index.js` (isteğe bağlı; Ayarlar > MCP'den de kurulabilir).

Hepsi resmî sitelerden indirilir; sağlama toplamları (Godot SHA512-SUMS.txt, Blender .sha256) doğrulanmalıdır.
Programlar yoksa ajan "kurulu değil" der ve kendisi indirmeye çalışmaz.

**Kolay yol (başka bilgisayar):** Ayarlar > **Oyun araçları** kartında "Godot + şablonları kur (~1.367 MB)" ve
"Blender'ı kur (~406 MB)" düğmeleri. Onay penceresi dosyaları, boyutları ve kurulum yerini gösterir; her dosyanın
sağlama toplamı uygulamaya gömülü resmî değerle karşılaştırılır (uyuşmazsa dosya silinir, kurulum durur). Yönetici
izni gerekmez, AppData'ya yazılmaz. Yarıda kalırsa düğmeye yeniden basın: doğrulanmış indirmeler yeniden kullanılır.

