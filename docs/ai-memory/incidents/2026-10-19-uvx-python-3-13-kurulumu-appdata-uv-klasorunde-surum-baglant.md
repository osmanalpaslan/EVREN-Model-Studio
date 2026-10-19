---
id: 2026-10-19-uvx-python-3-13-kurulumu-appdata-uv-klasorunde-surum-baglant
tarih: 2026-10-19
tur: ortam            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: mcp
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [mcp, serena, uv, comodo]
kurallar: []
---

# uvx Python 3.13 kurulumu APPDATA uv klasöründe sürüm bağlantısı hatası verdi

## Belirti
Serena'nın Python dil sunucusu başlamadı: `uvx -p 3.13 --from pyright==1.1.403 pyright-langserver`
→ "Missing expected target directory for Python minor version link at
%APPDATA%\uv\python\cpython-3.13.15-windows-x86_64-none". Önce de "uvx bulunamadı" hatası (uv yok).

## Kök neden
Tahmin: ilk indirmede sürüm bağlantısı (junction) hedef klasörden önce denetlendi (yarış) veya
Comodo dosya sanallaştırması; sonra bakıldığında bağlantı ve hedef vardı. Doğrulanmadı.

## Çözüm
uv 0.12.20 Serena'nın venv'ine pip ile kurulur, yalnız Serena sürecinin PATH'ine eklenir;
UV_PYTHON_INSTALL_DIR ve UV_CACHE_DIR Serena klasörüne yönlendirilir; pyright kurulumda bir kez
önceden indirilir (hata kurulumda görünür, ilk ajan turu beklemez). Sonrasında hata görülmedi.
Not: ilk denemenin %APPDATA%\uv\python altında bıraktığı Python 3.13 kopyası silinmedi.

## Kanıt
install_serena 36 sn (pyright ısınması); ardından find_referencing_symbols 7,8 sn'de doğru sonuç.

## Önleme
Dış araç kurulumlarını uygulamanın veri klasöründe tut; kurulumda ısınma çalıştır.

## İlgili dosyalar
src/evren_studio/agent/mcp.py (install_serena, SERENA_ENV)
