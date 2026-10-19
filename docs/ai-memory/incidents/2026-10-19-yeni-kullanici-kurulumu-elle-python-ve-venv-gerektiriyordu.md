---
id: 2026-10-19-yeni-kullanici-kurulumu-elle-python-ve-venv-gerektiriyordu
tarih: 2026-10-19
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu
alan: kurulum
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [kurulum, yeni-kullanici, windows]
kurallar: []
---

# Yeni kullanıcı kurulumu elle Python ve venv gerektiriyordu

## Belirti
Kullanıcı: "bütün kullanıcılar uygulamayı artık kullanabilsin." Kurulum
belgesi PowerShell'de Python yolu, `venv` ve `pip` komutları istiyordu; yollar
geliştiricinin bilgisayarına göre yazılmıştı. `run.bat` sanal ortam yoksa
yalnızca komutları yazıp duruyordu. Teknik olmayan kullanıcı başlatamazdı.

## Kök neden
Doğrulandı: tek tık kurulum betiği yoktu. Ek tuzaklar (bu bilgisayarda ölçüldü):
`py` başlatıcısı yok; PATH'teki `python` Microsoft Store'un sahte kısayolu
(çalışmaz, Store açar). Ayrıca LF satır sonlu .bat dosyalarında cmd `goto` /
`call :etiket` atlamalarını kaçırabilir.

## Çözüm
- `kurulum.bat` (ASCII, CRLF): Python 3.12+ arar (venv, kullanıcı/program
  klasörleri, py/python/python3 — sürüm denetimiyle Store kısayolu elenir);
  yoksa izin isteyip `winget install Python.Python.3.12 --scope user`; `.venv`,
  `pip install -r requirements.txt` ve `-e .`; içe aktarma denetimi;
  `tools/kurulum_kisayol.py` ile masaüstü + Başlat menüsü kısayolu (pythonw,
  assets/evren.ico; OneDrive masaüstü desteklenir). `EVREN_KURULUM_EVET=1`,
  `EVREN_KURULUM_KISAYOL=0`, `EVREN_KISAYOL_KLASORU` test için.
- `run.bat`: kurulum yoksa `kurulum.bat`'ı çağırır.
- `.gitattributes`: `*.bat text eol=crlf`.
- README ve INSTALLATION: "ZIP indir → kurulum.bat'a çift tıkla" bölümü.

## Kanıt
`build/kurulum_test` (depodaki dosyaların temiz kopyası, .venv yok):
`kurulum.bat` → Python bulundu, sanal ortam + paketler kuruldu, kısayol
oluştu, çıkış 0. Kısayol hedefi `.venv\Scripts\pythonw.exe -m evren_studio`,
simge evren.ico; uygulama yeni ortamdan açıldı. winget ile Python KURMA yolu
denenmedi (bu bilgisayarda Python vardı) — doğrulanmadı.

## Önleme
Kurulumu etkileyen değişiklikte temiz kopyada `kurulum.bat` dene. Not: Claude
Code oturumunda `NoDefaultCurrentDirectoryInExePath` tanımlı olduğundan .bat'ı
tam yolla çağır (aksi hâlde "tanınmıyor" hatası; kullanıcıda olmaz).

## İlgili dosyalar
- kurulum.bat
- run.bat
- tools/kurulum_kisayol.py
- .gitattributes
- docs/INSTALLATION.md
- README.md
