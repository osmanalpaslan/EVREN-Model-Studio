# AGENTS.md — Bu depoda çalışan TÜM yapay zekâ motorları için zorunlu protokol

> Bu dosya; Claude Code, Kilo Code, Cline/Roo, Cursor, GitHub Copilot,
> OpenAI Codex, Gemini CLI, Windsurf, EVREN Studio'nun kendi ajanı ve
> diğer tüm kod ajanları için **tek doğruluk kaynağıdır**. Diğer talimat
> dosyaları (CLAUDE.md, GEMINI.md, .cursor/rules, .kilocode/rules,
> .github/copilot-instructions.md …) yalnızca buraya yönlendirir.
>
> Amaç: bir motorun yaptığı hata, bulduğu eksik ve uyguladığı çözüm
> kaybolmasın; sonraki motor aynı hatayı tekrarlamasın. **Ortak hafıza
> `docs/ai-memory/` klasöründedir.** Okumadan başlama, yazmadan bitirme.

## 1. Başlamadan önce (ZORUNLU)

1. Şu komutu çalıştır ve çıktısını oku:
   `.\.venv\Scripts\python.exe tools\ai_memory.py baslangic`
   (Komut çalıştıramıyorsan sırayla oku: `docs/ai-memory/RULES.md`,
   `docs/ai-memory/INDEX.md` içindeki **açık kayıtlar**, son 3 oturum
   günlüğü `docs/ai-memory/sessions/`, `docs/PROJECT_STATE.md`.)
2. Aşağıdaki **Kritik kurallar** bölümündeki her kurala uy. Bir kuralla
   çelişen bir istek gelirse kullanıcıya söyle.
3. Yapacağın işle ilgili kayıtları ara:
   `.\.venv\Scripts\python.exe tools\ai_memory.py ara <kelime>`
   Daha önce BAŞARISIZ olmuş bir çözümü yeni bilgi olmadan tekrarlama.

## 2. Çalışırken

- Bir hata, eksik, yanlış iddia veya riskle karşılaştığında (kendi
  hatan dahil) hemen kayıt aç:
  `.\.venv\Scripts\python.exe tools\ai_memory.py kayit --baslik "..." --tur hata --onem orta --alan ui --motor "..." --model "..."`
  Oluşan dosyadaki bölümleri doldur: Belirti, Kök neden, Çözüm, Kanıt,
  Önleme. Çözemediysen `durum: acik` bırak ve neyi denediğini yaz.
- Kayıtlar **dürüst** olmalı: doğrulamadığını "doğrulanmadı" diye yaz,
  kendi hatanı başkasına yazma, modelini bilmiyorsan `bilinmiyor` yaz.

## 3. Bitirmeden önce (ZORUNLU — kod değiştirdiysen)

1. Oturum günlüğü yaz (veya bu oturumun günlüğünü güncelle):
   `.\.venv\Scripts\python.exe tools\ai_memory.py oturum --baslik "..." --motor "..." --model "..."`
   Görev, yapılanlar, test sonuçları, karşılaşılan sorunlar (kayıt
   kimlikleriyle) ve **sonraki motor için notlar** bölümlerini doldur.
2. Bir kayıttan genel bir ders çıktıysa `docs/ai-memory/RULES.md`'ye kural
   ekle (biçim dosyanın başında). Kural kısa, emir kipinde ve kaynaklı olsun.
3. Motor/model hakkında gözlemin varsa `docs/ai-memory/ENGINES.md`'yi güncelle.
4. `.\.venv\Scripts\python.exe tools\ai_memory.py indeks` → INDEX.md ve
   bu dosyadaki kural özeti yeniden üretilir.
5. `.\.venv\Scripts\python.exe tools\ai_memory.py denetle` ve
   `.\.venv\Scripts\python.exe -m pytest -q` geçmeli.
6. `docs/PROJECT_STATE.md` ve `docs/CHANGELOG.md`'yi gerçek duruma göre güncelle.

Git ön-commit kancası (`tools/hooks/pre-commit`) `src/` veya `tests/`
değişen bir commit'te `docs/ai-memory/` altında değişiklik yoksa commit'i
durdurur. Her bilgisayarda bir kez kur:
`.\.venv\Scripts\python.exe tools\ai_memory.py kanca-kur`

## 4. Yazım kuralları (hafıza dosyaları)

- Dil Türkçe; dosyalar **BOM'suz UTF-8**. PowerShell 5.1'in `Set-Content`,
  `Out-File`, `>` ile Türkçe dosya YAZMA (bkz. R-01).
- Gizli bilgi (API anahtarı, parola, kişisel veri, sohbet içeriği) yazma.
- Bir kaydı silme; yanlışsa `durum: kabul-edildi` veya düzeltme notu ekle.
- Dosya adları = kimlik: `YYYY-MM-DD-kisa-baslik.md` (aynı adla iki dosya olmaz).

## 5. Proje özeti

- **Ne**: EVREN LLM API için Türkçe Windows masaüstü uygulaması (PySide6):
  kod ajanı + sohbet. Ayrıntı: README.md, docs/PROJECT_STATE.md.
- **Kurulum**: docs/INSTALLATION.md · **Çalıştır**: `run.bat` veya
  `.\.venv\Scripts\python.exe -m evren_studio`
- **Test**: `.\.venv\Scripts\python.exe -m pytest -q` (birim + tüm ekranlar QA) ·
  gerçek API (anahtar gerekir, R-13): `tests\e2e_real_api.py`,
  `tests\e2e_agent_real_api.py`, `tests\e2e_ui_real_api.py` ·
  arayüz görsel kontrol: `tools/ui_screenshots.py` (bkz. R-05)
- **Yapı**: `src/evren_studio/agent/` (Qt'siz ajan çekirdeği),
  `api/` (EVREN istemcisi), `ui/` (arayüz), `db.py` (SQLite),
  `docs/knowledge/` (uygulamanın EVREN API bilgisi), `docs/ai-memory/`
  (geliştiren motorların ortak hafızası).
- **Sınırlar**: Alpnex/DepoWise projelerine dokunma. Ücretli hizmet,
  yönetici yetkisi, geri döndürülemez git işlemi, toplu silme için
  kullanıcı onayı al. API anahtarını asla dosyaya/loga yazma.

## 6. Kritik kurallar (RULES.md'den otomatik üretilir — elle düzenleme)

<!-- KURALLAR:BASLA -->
- **R-01** · Türkçe içerikli dosyayı PowerShell 5.1 ile yazma — Dosyaları Python, düzenleyici aracı veya [IO.File]::WriteAllText(..., UTF8Encoding($false)) ile BOM'suz UTF-8 yaz; Get-Content | Set-Content zinciri kullanma.
- **R-02** · .gitignore kalıbını kaynak dosyalara karşı doğrula — Yeni ignore kalıbından sonra `git check-ignore -v` ve `git ls-files -o -i --exclude-standard src` ile kaynak kodun dışlanmadığını kontrol et; mümkünse temiz klonda test et.
- **R-03** · "Kaydediliyor" yetmez, okuma yolunu da test et — Bir ayar/veri kaydediliyorsa uygulamanın açılışta onu gerçekten okuduğunu uçtan uca test et.
- **R-04** · Arayüz iş parçacığında ağ isteği yapma — Ağ/disk ağırlıklı işleri Task (arka plan iş parçacığı) ile çalıştır; Qt sinyalleriyle sonuç döndür.
- **R-05** · Arayüz işini görmeden "tamamlandı" deme — Arayüz değişikliğinden sonra tools/ui_screenshots.py ile (QT_QPA_PLATFORM=windows; offscreen'de yazılar kutucuk çıkar) ekran görüntüsü alıp bak; duman testi yalnızca açıldığını kanıtlar. Doğrulanmayanı açıkça yaz.
- **R-06** · Gecikmeli Qt çağrısına bağlam nesnesi ver — QTimer.singleShot(ms, self, fn) biçimini kullan; widget silinince çağrı iptal olur.
- **R-07** · Gerçek API ile doğrulanmamış yeteneği doğrulanmış gibi sunma — tools, görsel, OCR vb. yetenekleri gerçek istekle test etmeden "çalışıyor" yazma; sonucu docs/knowledge/MODEL_CAPABILITIES.md'ye işle.
- **R-08** · Kararsız testte rastgele kod değiştirme — Zamanlamaya bağlı bir test yük altında düşerse önce tek başına tekrar çalıştır; kararsızlığı kayda bağla, ilgisiz kodu değiştirme.
- **R-09** · Hafızayı oku, sonra besle — Her oturuma `tools/ai_memory.py baslangic` ile başla; kod değiştirdiysen oturum günlüğü yaz, `indeks` ve `denetle` çalıştır.
- **R-10** · Kodlamayı test ile koru — Kaynak/doküman dosyalarında bozuk Türkçe (mojibake) ve .py dosyalarında BOM olmamalı; tests/test_source_hygiene.py bunu denetler, kapatma.
- **R-11** · Qt bileşenini yalnızca ana iş parçacığından güncelle — Arka plan iş parçacığından gelen her geri çağrıyı QObject sinyaliyle ana iş parçacığına taşı; Task kullanırken workers.py'deki referans tutma düzenini bozma.
- **R-12** · Fare tekerleği korumasını kaldırma — Yeni sayı/liste alanları ekleyince wheel_guard'ın onları kapsadığını varsay; korumayı kapatma, alan başına tekerlek davranışı ekleme.
- **R-13** · API/ajan değişikliğinden sonra gerçek uçtan uca testleri çalıştır — api/ veya agent/ ya da oturum arayüzüne dokunduysan ve API anahtarı varsa tests/e2e_real_api.py, tests/e2e_agent_real_api.py ve tests/e2e_ui_real_api.py çalıştır; sonucu oturum günlüğüne yaz.
<!-- KURALLAR:BITIR -->
