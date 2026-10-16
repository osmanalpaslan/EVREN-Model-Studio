# Ortak Geliştirici Hafızası (`docs/ai-memory/`)

Bu klasör, EVREN Studio'yu geliştiren **tüm yapay zekâ motorlarının ve
insanların** ortak hafızasıdır. Bir motorun yaptığı hata, bulduğu eksik,
bunların nedeni, çözümü ve o oturumda ne yapıldığı burada kalıcı olarak
tutulur. Sonraki motor (farklı bilgisayar, farklı eklenti, farklı model)
işe bunları okuyarak başlar ve aynı hatayı tekrarlamaz.

Protokolün kendisi kök dizindeki **AGENTS.md** dosyasındadır. Bu dosya
yalnızca yapıyı anlatır.

## Yapı

| Yol | İçerik | Kim yazar |
|---|---|---|
| `RULES.md` | Kayıtlardan damıtılmış kısa, emir kipinde kurallar (R-01…) | Bir kayıttan genel ders çıkaran motor |
| `incidents/YYYY-MM-DD-baslik.md` | Tek bir hata / eksik / risk / yanlış iddia kaydı: belirti, kök neden, çözüm, kanıt, önleme | Sorunu bulan veya çözen motor |
| `sessions/YYYY-MM-DD-motor-baslik.md` | Bir geliştirme oturumunun günlüğü: görev, yapılanlar, testler, sorunlar, sonraki motora notlar | Her oturumun sonunda o motor |
| `ENGINES.md` | Motor/model profilleri: güçlü yanlar, tekrarlayan hata eğilimleri, ortam notları | Gözlem yapan her motor |
| `INDEX.md` | Otomatik üretilen indeks (açık kayıtlar önce) | `tools/ai_memory.py indeks` |

Neden her kayıt ayrı dosya? Farklı motorlar aynı anda farklı dallarda
çalışabilir; tek dosyaya ekleme yapmak birleştirme çakışması üretir.
Dosya adı tarih + başlık olduğu için kimlik çakışmaz.

## Kayıt türleri

- `hata` — yanlış çalışan kod veya yapılandırma
- `eksik` — yapılması gerekip yapılmamış/iddia edilip olmayan özellik
- `risk` — henüz sorun çıkarmamış ama doğrulanmamış varsayım
- `yanlis-iddia` — belge veya raporda gerçeği yansıtmayan "tamamlandı/çalışıyor"
- `surec` — çalışma biçimi hatası (test etmeden bitirmek vb.)
- `ortam` — işletim sistemi, kabuk, araç kaynaklı tuzak

Önem: `kritik | yuksek | orta | dusuk` · Durum: `acik | izleniyor | cozuldu | kabul-edildi`

## Komutlar

```powershell
.\.venv\Scripts\python.exe tools\ai_memory.py baslangic          # başlarken oku
.\.venv\Scripts\python.exe tools\ai_memory.py ara powershell       # ilgili kayıtları bul
.\.venv\Scripts\python.exe tools\ai_memory.py kayit --baslik "..." --tur hata --onem orta --alan ui --motor "..." --model "..."
.\.venv\Scripts\python.exe tools\ai_memory.py oturum --baslik "..." --motor "..." --model "..." --sonuc tamamlandi
.\.venv\Scripts\python.exe tools\ai_memory.py indeks                # INDEX.md + AGENTS.md kural özeti
.\.venv\Scripts\python.exe tools\ai_memory.py denetle               # biçim ve güncellik denetimi
.\.venv\Scripts\python.exe tools\ai_memory.py kanca-kur             # her bilgisayarda bir kez
```

`tests/test_ai_memory.py` aynı denetimi pytest içinde çalıştırır; hafıza
bozuksa veya indeks güncel değilse test paketi başarısız olur.

## `docs/knowledge/` ile farkı

- `docs/knowledge/`: **uygulamanın** bildiği şeyler — EVREN API davranışı,
  model yetenekleri, çalışma zamanı hata kataloğu, kurtarma rehberi.
- `docs/ai-memory/`: **uygulamayı geliştirenlerin** öğrendikleri — geliştirme
  sırasında yapılan hatalar, eksikler, çalışma kuralları, motor profilleri.

`docs/knowledge/LESSONS_LEARNED.md` 2026-10-15/16 tarihli eski dersleri
içerir; yeni dersler artık `incidents/` + `RULES.md` olarak yazılır.
