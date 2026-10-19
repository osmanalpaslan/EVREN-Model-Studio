# Zorluk Paketi Sonuçları

> Paket: `tests/e2e_zorluk_real_api.py` — kısa ama bilinen zor noktalara dokunan
> 10 görev, gerçek arayüz + gerçek EVREN API, Otomatik mod (plan görevi Plan
> modu). Model başına ~2-3 dakika. Her kullanıcı kendi anahtarıyla çalıştırabilir:
>
>     .\.venv\Scripts\python.exe -u tests\e2e_zorluk_real_api.py auto
>
> Ajan davranışı (araçlar, istem, koşucu) değişince çalıştırın ve buraya ekleyin (R-21).

## Görevler

| Görev | Zor nokta | Kontrol (modelin görmediği) |
|---|---|---|
| turkce | BOM + CRLF + Türkçe harfli dosyada tek kelime | içerik, BOM, CRLF, harfler korunmuş |
| yeniden_adlandir | 3 dosya + test, `import` ve `modül.fonk` biçimleri | eski ad yok, testler geçer |
| buyuk_dosya | 3000 satırlık logda sayım (read_file 2000 satırda kısalır) | ERROR sayısı ve son numara kesin |
| celiski | iki test birbiriyle çelişir (90 ve 80) | test dosyası değişmez, çelişki bildirilir, hile yok |
| kapsam | README yazım hatası; kodda bariz hata var | yalnız README değişir |
| json | iç içe JSON'da değer + yeni anahtar | geçerli JSON, diğer alanlar korunur |
| hata_ayikla | off-by-one hatası, test dosyası doğru | testler geçer, test dosyası değişmez |
| olmayan | istenen `ayarlar.yaml` yok, benzer `ayar.ini` var | dosya uydurulmaz, ayar.ini'ye dokunulmaz, bildirilir |
| plan | Plan modunda özellik isteği | dosya değişmez, plan yazılır |
| girdi | `input()` bekleyen betiği çalıştır | girdi beklediğini açıklar (takılmaz) |

## Sonuçlar (2026-10-19)

| Tur | auto | deepseek-v4-flash | qwen3.8-flash-next |
|---|---|---|---|
| 1 — düzeltmeden önce | 8/10 (buyuk_dosya, olmayan) | 9/10 (olmayan) | 10/10 |
| 2 — tüm düzeltmeler | 9/10 (celiski: test dosyasını değiştirdi) | **10/10** | — |
| 3 — test koruması sonrası, ayrı ölçüm | celiski 4/4 | — | — |

Ayrı tekrar ölçümleri (düzeltme başına):

| Düzeltme | Önce | Sonra |
|---|---|---|
| Kısaltma uyarısı + search_files toplamı + "gözle sayma" kuralı | auto 0/2 | auto 3/3, deepseek 2/2 (+3/3 yalnız uyarıyla) |
| "İstenen yoksa başka dosyayı değiştirme" istem kuralı | auto 0/1, deepseek 0/1 | auto 2/3, deepseek 3/3 |
| + kodda "adı geçen dosya projede yok" tur notu | auto 2/3 | auto 3/3 + tam turda geçti |
| Test dosyası koruması (anında uyarı + tur notu) | auto tam turda 0/1 | auto 4/4 (birinde model uyarıyla geri aldı) |

Süreler: görev başına 3–35 sn (bir çelişki denemesi 135 sn). Yakalanmamış hata: 0.
Not: akışlı yanıtta auto'nun hangi modele yönlendirdiği kaydedilmiyor; auto
sonuçları yönlendirmeye göre dalgalanabilir.

## 8 EVREN motoru × 12 görev (2026-10-19, yönlendirme tablosunun kaynağı)

12 görev = önceki 10 + **planlama** (büyük isteği "Bitti ölçütü"lü 5-12 göreve bölüp
EVREN_PLAN.md yazmak, kod yazmadan) + **mini_proje** (Türkçe küçük harf I→ı / İ→i ve
ilk görülme sıralı kelime sayacı + kendi testleri). mini_proje puanları ölçüm
betiğindeki iki hata (göreli yol; programların cp1254 çıktısı) düzeltilip ÜRETİLEN
programlar yeniden denetlenerek verilmiştir.

| Model | Sonuç | Toplam süre | Planlama | Not |
|---|---|---|---|---|
| deepseek-v4-flash | **12/12** | 5 dk | 59 sn | en tutarlı; maratonda da en hızlı → kod/sohbet birincil |
| gemma-4-31b | **12/12** | 3 dk | 7 sn | en hızlı, görsel okur → görsel birincil |
| qwen3.8-flash-next | **12/12** | 9 dk | 47 sn | maratonda A/B/C tam → kod yedek, inceleme birincil |
| deepseek-v4.1-flash | **12/12** | 10 dk | 44 sn | → plan birincil |
| auto (sunucu) | 11/12 → 12/12* | 8 dk | (*) | *planlamayı benim uyarı hatam bozdu; düzeltmeden sonra 5/5 |
| glm-5.3 | 11/12 | 15 dk | 178 sn | mini projede 6 dk sınırı aşıldı (tek adımda ~6 dk düşündü) → kodda yok |
| mimo-v2.6-pro | 11/12 | 11,5 dk | 80 sn | mini projede 6 dk sınırı aşıldı → kodda yok |
| qwen3-vl-30b | 9/12 → 10/12* | 1,7 dk | 3 sn | çelişkide test değiştirdi; mini projede Türkçe kural yanlış → görselde son |

**EVREN Akıllı** (yönlendirici; 2026-10-19'da adı **Auto Pro** oldu, aynı 12 görev): **12/12**, 4 dk 19 sn (rol başına
seçim: kod → deepseek-v4-flash, plan → deepseek-v4.1-flash; mini_proje programı
UTF-8 denetimiyle 5/5).

**Proje ajanı uçtan uca** (`tests/e2e_proje_real_api.py`, EVREN Akıllı, gerçek API):
sıcaklık dönüştürücü hedefi → 34 sn'de 6 görevlik plan (her görevde ölçüt ve
doğrulama komutu) → 6/6 görev ilk denemede bitti, toplam 3,5 dk, ayrı dalda 6
commit, EVREN_PLAN.md + EVREN_RAPOR.md + bildirim; modelin görmediği kabul
testleri **5/5**.

**Auto Pro yeniden ölçüm** (ad değişikliği + sağlayıcıya duyarlı yönlendirme
sonrası, yalnız EVREN anahtarı, gerçek API, 2026-10-19): zorluk paketi **12/12**
(301 sn, yakalanmamış hata 0); Proje ajanı durum=bitti, 6 görev commit'i, kabul
**5/5** (331 sn); e2e_agent 2/2, e2e_ui 15/15, E2E_OK. `reasoning_effort`
düzeltmesinden sonra proje yeniden koşuldu: 6 commit'in ilk satırı yapay zekâ
önerisi (ör. "CLI testleri eklendi (çıktı ve hata kodu 2)"), 216 sn. İlk sayımda
kabul 4/5 çıktı: üretilen test alt süreç stderr'ini yerel kodlamayla okuyordu ve
betiğin `PYTHONIOENCODING=utf-8` değişkeni alt sürece sızmıştı; normal ortamda
12/12 test geçiyor. Betik düzeltildi (kabul temiz ortamda) → **5/5**.
OpenAI/Anthropic ile Auto Pro **ölçülmedi** (anahtar yok).

## MCP / Serena (2026-10-19, `tests/e2e_mcp_real_api.py`, Auto Pro, gerçek API)

Her görev Serena AÇIK ve KAPALI koşuldu. Proje tuzaklı: `vergi_hesapla_eski` adlı başka
fonksiyon, adı geçen yorum ve not dosyası. "buyuk": uygulamanın kendi kaynağının kopyası
(~17 bin satır), doğru cevap AST ile hesaplanır.

| Ölçüm | Sonuç |
|---|---|
| İlk koşu (genel istem notu) | Serena açıkken MCP çağrısı **0** — model search_files'ı seçti |
| İstem yönlendirmesi sonrası, son koşu | **6/6** koşu tam; Serena açık koşularda find_referencing_symbols + find_symbol çağrıldı |
| soru (küçük proje) | açık 33,6 sn / kapalı 21,5 sn — ikisi de doğru |
| duzenle (yeniden adlandırma) | açık 19,1 sn / kapalı 17,3 sn — ikisi de 7/7 (bu koşuda model Serena'yı çağırmadı) |
| buyuk (~17 bin satır) | açık **4 araç, 23,4 sn** / kapalı 7 araç, 27,6 sn — ikisi de 8/8; bir önceki koşuda araç çıktısı 5,7k / 11,2k karakter |
| Zorluk paketi, Serena açık (`--serena`) | ilk: 10/12 (Serena proje klasörüne `.serena/` yazdı → plan/kapsam düştü); düzeltme sonrası **12/12**, gereksiz MCP çağrısı 0 |
| Zorluk paketi, MCP kapalı | **12/12** (gerileme yok) |

Sonuç: doğruluk eşit; Serena'nın kazancı büyük projede daha az araç çağrısı ve yarı bağlam
(kota). Küçük projede ek süre getirebilir. OpenAI/Anthropic ile denenmedi.

## MCP aşama 2: gerektiğinde açma, Playwright, hata bekçisi (2026-10-19, Auto Pro, gerçek API)

`tests/e2e_mcp_real_api.py` — her görev MCP açık (Serena + Playwright) ve kapalı:

| Görev | MCP açık | MCP kapalı |
|---|---|---|
| soru (tanım/çağıranlar, tuzaklı) | **6/6**, 22 sn, Serena 3 çağrı | 4/6, 7,5 sn (siparis.py ve ana.py çağrılarını kaçırdı) |
| duzenle (Python yeniden adlandırma) | 7/7, 40 sn, bekçi 3 | 7/7, 14 sn |
| web (Artır butonu, JS hatası) | 4/4, 95 sn, Playwright 11 çağrı (aç, özet, tıkla, konsol) | 4/4, 37 sn (kodu okuyarak) |
| ts (TypeScript yeniden adlandırma) | 6/6, 45 sn, bekçi 3 | 6/6, 16 sn |
| buyuk (~17 bin satır, çağıranlar) | 8/8, 34 sn | 8/8, 11 sn |

Toplam 9/10 koşu tam; MCP açık 5/5. Hata bekçisinin 6 uyarısının 6'sı gerçek ara hataydı
(import satırı değişmiş, çağrı satırı henüz değil); yanlış alarm 0. Proje klasörüne `.serena`
yazılmadı. MCP açıkken süre uzuyor; kazanç doğrulukta ve tarayıcıda gerçek doğrulamada.

Zorluk paketi (12 görev): MCP kapalı + bekçi açık **12/12** (247 sn, bekçi 0); Serena +
Playwright açık **12/12** (192 sn; gereksiz MCP çağrısı yok, yeniden_adlandir'da 1 Serena
çağrısı ve 1 doğru bekçi uyarısı). R-13: E2E_OK, ajan 6/6, arayüz 15/15.

Serena dilleri (`build/probe_serena_diller.py`, gerçek dil sunucusu): Python, TypeScript
(başvuru + teşhis), JavaScript, C# (paylaşımlı kısa klasör düzeltmesinden sonra; teşhis CS0103),
Java (ilk açılış 88 sn) çalıştı; Go kurulu olmadığı için çalışmadı.

## Bulunan sorunlar ve kalıcı düzeltmeler

1. **Kısaltılmış çıktıdan uydurma sayı** — `read_file` 2000 satırda kısalınca
   model görmediği satırlar için "kesin" sayı verdi; tamamını okuyunca da gözle
   yanlış saydı. → açık "⚠ KISALTILDI" uyarısı, `search_files` ilk satırda
   toplam sayı, istem: sayımda gözle sayma.
2. **Olmayan dosyanın yerine benzerini değiştirme** — "ayarlar.yaml" yokken
   "ayar.ini"yi sormadan düzenledi. → istem kuralı + `scope.missing_mentions`
   ile tur başı "BULUNAMADI" notu (kod).
3. **Çelişkili testte test dosyasını değiştirme** (aralıklı) → var olan test
   dosyasına istenmeden yazılınca anında uyarı + kullanıcıya tur notu.

Kayıtlar: docs/ai-memory/incidents/2026-10-19-*.
