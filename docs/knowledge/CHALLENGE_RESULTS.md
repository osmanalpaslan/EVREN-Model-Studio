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
