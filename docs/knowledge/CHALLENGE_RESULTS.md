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
