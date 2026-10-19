---
id: 2026-10-19-serena-c-dil-sunucusu-windows-260-karakter-yol-sinirina-taki
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
etiketler: [serena, csharp, max-path, windows]
kurallar: []
---

# Serena C# dil sunucusu Windows 260 karakter yol sınırına takıldı

## Belirti
Serena C# projesinde başlamadı: "[WinError 3] Sistem belirtilen yolu bulamıyor" (Roslyn
paketini kopyalarken), düzeltme denemesinden sonra "Error extracting archive" (temp_downloads).
Ayrıca her proje kendi ev klasöründe dil sunucularını yeniden indiriyordu (Java ilk açılış 88 sn).

## Kök neden
Doğrulandı: dil sunucusu klasörü SERENA_HOME altında; proje başına ev klasörü
(`…\mcp\serena\home\<ad>-<özet>\language_servers\static\CSharpLanguageServer\roslyn-…\BuildHost-netcore\…runtimeconfig.json`)
260 karakteri aştı. İkinci denemede `…\mcp\serena\ls\…\temp_downloads\…` yolu 261 karakterdi.

## Çözüm
Serena venv'ine `sitecustomize.py` yaması: `EVREN_SERENA_LS_DIR` verilirse
`SolidLSPSettings.ls_resources_dir` o klasör olur. Klasör: `<veri>\mcp\ls`, Windows 8.3 kısa yol
biçiminde (GetShortPathNameW). Tüm projeler paylaşır.

## Kanıt
build/probe_serena_diller.py: C# başvuru 49,7 sn + teşhis "CS0103" (Türkçe ileti); TypeScript
11 sn → paylaşımlı klasörle 4,7 sn.

## Önleme
Windows'ta indirilen araçları sığ ve kısa yollu klasöre koy; derin proje başına klasör kullanma.

## İlgili dosyalar
src/evren_studio/agent/mcp.py (serena_ls_dir, ensure_serena_patch, SERENA_ENV)
