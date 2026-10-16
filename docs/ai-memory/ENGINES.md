# Motor ve Model Profilleri

> Bu projeyi geliştiren motorların (eklenti/uygulama + model) gözlenen
> güçlü yanları, tekrarlayan hata eğilimleri ve ortam notları. Amaç suçlamak
> değil: bir motor bir konuda zayıfsa, o motorla çalışırken o konu ekstra
> kontrol edilir. Gözlem yaptıysan kendi bölümüne ekle; yeni motor için yeni
> bölüm aç. Kanıtı olmayan genelleme yazma; kayıt kimliğiyle bağla.

## Kilo Code (VS Code eklentisi) + EVREN LLM modelleri

- **Kullanım**: 2026-10-15 — Aşama 0 (araştırma) ve Aşama 1 (MVP), commit
  `9974dba`. Hangi EVREN modelinin kullanıldığı kayda geçmedi
  (`kaynak_model: bilinmiyor`). Ortam: Windows 11, PowerShell 5.1.
- **Güçlü yanlar (kanıtlı)**: kapsamlı araştırma ve belgeleme
  (`docs/knowledge/*`, OpenAPI şemasından doğrulanmış uç noktalar), hata
  sınıflandırma ve kurtarma motoru, 53 birim testi, durum izleme ajanı.
- **Gözlenen eğilimler**:
  - Dosyaları PowerShell üzerinden yazarken kodlama bozulması → 7 dosya
    (2026-10-15-cift-kodlanmis-turkce-metinler-mojibake).
  - Geniş `.gitignore` kalıbıyla kaynak dosyayı dışlama
    (2026-10-15-gitignore-secrets-kalibi-kaynak-modulu-disladi).
  - Yazma yolunu test edip okuma yolunu bağlamama
    (2026-10-15-ayarlar-acilista-okunmuyordu).
  - Arayüzü görmeden "tamamlandı" raporu; duman testine aşırı güven
    (2026-10-15-duman-testi-bozuk-arayuzu-yakalamadi).
- **Bu motorla çalışırken**: R-01, R-02, R-03, R-05 kurallarını özellikle
  denetle; işi bitirince `pytest` + `tools/ui_screenshots.py` iste.

## Claude Code (masaüstü uygulaması) — claude-opus-5-5

- **Kullanım**: 2026-10-16 — ikinci bilgisayarda kurulum, `secrets.py`
  düzeltmesi (PR #1), kod ajanı çalışma alanı ve yeni arayüz (PR #2), bu
  ortak hafıza yapısı. Ortam: Windows 11 Pro 26200, PowerShell 5.1 + Git
  Bash, Python 3.12.10.
- **Güçlü yanlar (kanıtlı)**: kök neden analizi (mojibake'in, ayar
  yüklenmemesinin ve `.gitignore` sorununun bulunması), büyük ölçekli
  mimari değişiklik, sahte istemcili kapsamlı testler (51 yeni test), arayüzü
  ekran görüntüleriyle doğrulama.
- **Gözlenen eğilimler / kendi hataları**:
  - Aynı oturumda PowerShell `Get-Content | Set-Content` ile `pyproject.toml`'u
    bozdu (anında fark edip düzeltti) — R-01'in ne kadar kolay ihlal
    edildiğinin kanıtı.
  - Silinmiş widget'a `QTimer.singleShot` çağrısı (2026-10-16-qtimer-silinmis-widgeta-cagri).
  - Dar sağ panelde sekme metinleri ilk denemede kesildi/çakıştı; ekran
    görüntüsüyle yakalanıp düzeltildi.
  - Gerçek API anahtarı olmadan çalıştığı için ajanın EVREN ile araç turu
    doğrulanamadı (2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi).
- **Ortam notları**: Claude Code'un geçici (scratchpad) klasörü bazı
  süreçlerce görülmeyebilir; geçici betikleri git'e girmeyen `build/`
  altına koy. Silme komutları (Remove-Item) izin katmanınca
  engellenebilir; gerekmedikçe silme.

## EVREN Studio'nun kendi ajanı (uygulama içi)

- Bu depoda proje klasörü olarak açıldığında AGENTS.md'yi proje hafızası
  olarak okur (`Workspace.project_memory`). Henüz bu depoda kullanılmadı;
  ilk kullanımda gözlemleri buraya ekle.

## Yeni motor eklerken şablon

```
## <Motor adı> — <model>
- **Kullanım**: tarih, ne yaptı, commit/PR
- **Güçlü yanlar (kanıtlı)**:
- **Gözlenen eğilimler**: (kayıt kimlikleriyle)
- **Bu motorla çalışırken**: hangi kurallara dikkat
```
