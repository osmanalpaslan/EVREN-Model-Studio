# DEVİR NOTU — işin şu anki yeri (tüm motorlar ve bilgisayarlar için tek kaynak)

> Kullanıcı farklı bilgisayar ve oturumlardan çalışır; proje hiç askıda kalmamalı.
> **Başlarken:** `tools/ai_memory.py baslangic` bu dosyayı (ve GitHub'daki daha yeni bir çalışma dalı
> varsa onunkini) en üstte gösterir. "Şu an" bölümündeki dala geç, "Kaldığı yer"den devam et.
> **Çalışırken:** her madde/alt adım bitince durumunu burada güncelle (YAPILDI + commit), commit'le ve
> **push et** — yarım iş de `wip:` commit'iyle gönderilir, yalnız bu bilgisayarda iş bırakılmaz (R-35).
> **Bitirirken / ayrılırken:** "Şu an" bölümünü doldur: dal, son commit, yarım kalan tam olarak ne,
> sıradaki adım, çalışan/yarıda kalan uzun test. `src/` değişen commit bu dosyayı da içermek zorunda
> (ön-commit kancası).
> Durumlar: YAPILDI · SÜRÜYOR · SIRADA · BEKLİYOR (kullanıcı kararı/ödeme gerekir).

## Şu an

- **Güncelleme:** 2026-11-03 akşam · Claude Code (claude-opus-5-5) · dizüstü bilgisayar
- **Aktif dal:** `master` (PR #30, #31, #32 ve gözlem ajanı PR'ı birleştirildi). Yeni iş için master'dan dal aç.
- **Kaldığı yer:** Madde 11 (gözlem ajanı) YAPILDI ve birleştirildi; Madde 10a YAPILDI. Sıradaki (kullanıcı
  2026-11-03: "doğruluk bir tık daha önemli", sırayı motor belirler):
  1. **10b** faz unutma kaydını (2026-10-21) uzun gerçek oturumla ölç (özet sonrası, `e2e_plan_bekcisi_real_api`
     + maraton D); yeniden üretilirse düzelt.
  2. **Madde 8** Derin Mod: aşama başına en doğru EVREN modeli (ölçümle), plan/doğrulama aşamasında `"high"`
     effort ölçümü, kısa canlı durum cümleleri; `e2e_derin_real_api` önce/sonra.
  3. **Madde 6** klasörsüz sohbette yalnız web_search/web_fetch.
  4. **Madde 9** sade sağlayıcı ekranı.
  5. **Madde 7** hız (en son): önce EVREN yükünü ayır; yalnız doğruluğa dokunmayan kaldıraçlar; kod/plan rolünde
     effort düşürülmez.
- **Gözlem ajanı notu:** her oturum başında `baslangic` "Uygulamadan gelen gözlemler" bölümünü gösterir; `!
  KULLANICIYA BİLDİR` varsa kullanıcıya söyle (R-36). Deneme gözlemi b12eb83f411c kabul-edildi olarak kapalı.
- **Çalışan uzun test:** yok.

## Geliştirme sırası (kullanıcı onaylı, 2026-11-01)

Kullanıcı neredeyse yalnız **Auto Pro** kullanıyor; hedef "tam profesyonel uygulama". Her madde: hedefli test +
kritikse mutasyon + paket; R-13/R-21 gerçek ölçümler dal sonunda.

| # | Madde | Durum | Dal / commit | Not / kalan |
|---|---|---|---|---|
| 0 | Taban ölçüm (auto-pro) | YAPILDI | — | zorluk 12/12, proje 5/5, maraton A 10/10 (26 dk), B 13/13 (19 dk), C 10/10 (28 dk; 1. mesaj 21 dk/33 adım) |
| 1 | Açık tema okunurluğu, görünmeyen düğmeler, Ayarlar'daki sabit renkler | YAPILDI | e940402, 5225fc1, 316d69d, 2050af9 | `tools/ui_denetim.py` + `tests/test_okunurluk.py` (R-33); açık/koyu HATA 0 |
| 2 | Ücretsiz web araması (Tavily) + Auto Pro'ya dahil | YAPILDI | 2050af9 | Tavily → anahtarsız Tavily → DuckDuckGo → "eldeki bilgiyle devam"; Ayarlar > Web Araması; R-25 ölçümü CHALLENGE_RESULTS.md |
| 3 | Uzun proje maratonları D (7 mesaj) ve E (PWA) | YAPILDI | 0ced757 | kabul denetimleri bilinen doğru/yanlışla sınandı |
| 4 | Auto Pro bağlam şişmesi (/compact olmuyor, otomatik özet yok) | YAPILDI | b099b7a (+PR #30 /clear, büyük özet) | token tahmini 3,5 → gerçek kullanımla kalibre (R-34). Gerçek: maraton D 25/25 (bağlam ~40k, özet gerekmedi); özetli maraton A (`MARATON_OZET_ESIK=20000`) 10/10, otomatik özet 1 kez tetiklendi ve iş bozulmadan sürdü. Proje görevlerinde sınır aşılırsa görev denetlenir, gerekirse temiz bağlamla yeniden denenir (tasarım gereği) |
| 5 | Kota bitince otomatik devam paneli | YAPILDI | 7314251, 5e70bf1, c1ec1c9 | Normal oturum + Proje/QA/Derin: güvenli noktada dur (kota kapısı / 429), sohbette kart (yenilenme saati, geri sayım, ☑ otomatik devam = Ayarlar `auto_resume`, Şimdi dene/Vazgeç), saatinde kota yoklanır, plan DB'de (açılışta geri gelir), elle mesaj iptal eder; Derin Mod uygulama kapanınca fazdan sürdürülemez (not verilir). Testler: test_kota_devam 8 + test_kota_kapisi, mutasyon. GERÇEK: kotalı maraton A (`MARATON_KOTA_TESTI=2:3`) — 4 araç adımından sonra durdu, kart+plan, gerçek yoklamayla devam, kabul 10/10 (EVREN yavaştı: 77 dk) |
| 6 | Testlerde bulunan hata/eksikler | SIRADA | — | aşağıdaki liste |
| 7 | Proje bitirme hızı (tutarlılığı bozmadan) | SÜRÜYOR | (bu commit) | KARAR (kullanıcı 2026-11-01): UYARLANABİLİR sıra — kullanıcının sırası varsayılan; öndeki model son 3 saatte yedeğinden 2 kattan fazla yavaşsa o gün yedek öne alınır (YAPILDI: router.choose speeds, modelstats.effective_speeds, test_uyarlanabilir_sira 8, mutasyon). Zorluk paketi (21:20, EVREN yoğun) 8/12: celiski'de yavaşlık geçişi gemma'ya düştü → gemma hile yazdı (DÜZELTİLDİ: SLOW_SWITCH_EXCLUDE), kapsam/mini_proje düzenek hatasıyla iptal (DÜZELTİLDİ), planlama EVREN yavaşlığıyla zaman aşımı. 2026-11-03 tekrar (1117fae): düşen 4 görev 4/4, tam paket 12/12 · 1595 sn (YAPILDI). Kalan: adım sayısı azaltma / hız. Döküm YAPILDI (2026-11-01, maraton A-D + proje ajanı DB'leri): sürenin ~%97'si MODEL BEKLEMESİ; araç/komut toplam 0,3-1,4 dk. deepseek-v4.1-flash çağrı başına ort. 30-85 sn (en uzun 274), qwen3.8-flash-next 15-40 sn. Kaldıraçlar: kod rolünde model sırası (ölçümle), düşünme süresi (reasoning_effort/çıktı uzunluğu), adım sayısı (paralel araç çağrısı, gereksiz okuma), yavaş model erken geçişi (`_slow`). Tutarlılık zorluk + maraton kabulüyle korunur |
| 8 | Derin Mod yeniden ele alınacak | SIRADA | — | aşamaya göre en doğru/güçlü EVREN modelleri (ölçümle); çalışırken kısa canlı durum cümleleri; mevcut özellikleri önce kodda doğrula; `e2e_derin_real_api` önce/sonra |
| 10 | Doğruluk turu (kullanıcı 2026-11-03: "doğruluk ve sağlam iş bir tık daha önemli"; sıra: dalı kapat → doğruluk → güvenli hız) | SÜRÜYOR | `feat/dogruluk-turu` | 10a YAPILDI: test dosyası koruması komutla değiştirme/silmeyi de yakalar (kayıt 2026-11-03-test-dosyasi-korumasi-…). Sonra: faz unutma kaydını uzun gerçek oturumla ölç; Madde 8 (Derin Mod, aşama başına en güçlü model, `"high"` effort ölçümü); en son Madde 7 hız (önce EVREN yükünü ayır, yalnız doğruluğa dokunmayan kaldıraçlar, kod/plan rolünde effort DÜŞÜRÜLMEZ) |
| 11 | Gözlem ajanı (kullanıcı 2026-11-03): uygulama/geliştirme sırasındaki hata ve anormallikleri temizleyip depoya gönder; geliştirme motoru görüp kullanıcıya bildirsin | YAPILDI | `feat/gozlem-ajani` (98c6cf2 +) | `src/evren_studio/gozlem.py`, `gozlem-kayitlari` dalı, `ai_memory.py gozlem …`, baslangic bildirimi, R-36. Ayrıntı: CHANGELOG "Gözlem ajanı" |
| 9 | Sade sağlayıcı/API anahtarı ekranı | SIRADA | — | tek "Sağlayıcı ekle": EVREN, OpenAI, Anthropic, Kilo, OpenRouter, OpenAI-uyumlu; çok modelli ağ geçitleri tek anahtarla |

### Madde 5 planı — kota bitince otomatik devam
Bugün: yalnız Proje/QA/Derin akışında (`project_ui.schedule_auto_resume`, Ayarlar'daki gizli `auto_resume`),
uygulama açıkken QTimer. Normal ajan turunda günlük kota azsa yalnız uyarı → 429 → iş yarıda kalır.
1. Otomatik devam açıksa normal turda kota kapısı güvenli noktada durdurur (`quota_daily`).
2. 429 tükenince (`_on_fail` RATE_LIMIT) de aynı yol.
3. Sohbette kart: "EVREN kotası doldu · yenilenme HH:MM (N dk)" + ☑ "Kota yenilenince otomatik devam et"
   (ayara bağlı, kalıcı) + Şimdi dene / Vazgeç; geri sayım.
4. Saatinde önce `/v1/quota` yoklanır (token harcamaz); yeterliyse oturuma dönüp `_auto_continue`; değilse
   yeniden kurulur; saat bilinmiyorsa 10 dk'da bir.
5. Kalıcı kayıt (DB `pending_resume`): uygulama kapanıp açılınca kart + zamanlayıcı geri gelir.
6. Proje/QA/Derin aynı kartı/kaydı kullanır.
7. Testler: tetiklenen/tetiklenmeyen (kutu kapalı), yoklama yetersiz, yeniden açılış; gerçek: eşik yapay
   yükseltilip maraton A ortasında dur → devam → kabul 10/10.

### Madde 6 — bulunan hata/eksik listesi (yeni buldukça ekle)
- [~] Model zaman zaman İngilizce ara cümle yazıyor (ölçüm: 96 metinli yanıtın 3'ü, hepsi deepseek-v4.1-flash, tur başında). Dil kuralı ara cümleleri kapsayacak şekilde netleştirildi (734fd4c). A/B gerçek ölçüm (deepseek-v4.1-flash, 5'er, reasoning none): eski 0/4, yeni 0/4 İngilizce — sorun bu ölçümde tekrarlanmadı, etkisi DOĞRULANAMADI; dal sonu zorluk paketinde yanıtlar yine sayılacak.
- [x] Plan modunda `web_search`/`web_fetch` açıldı (dosyaya dokunmaz; sorulmadan çalışır, Manuel'de sorulur).
- [ ] Klasörsüz sohbet oturumlarında hiç araç yok (web araması da yok) — ayrı özellik: sohbette yalnız web_search/web_fetch sunmak (runner `agentic` değilken araç protokolü + `_execute` toolbox koruması gevşetilmeli). BEKLİYOR.
- [ ] deepseek-v4.1-flash bazı adımlarda 30-130 sn bekletiyor (Madde 7 ile birlikte).

- [x] R-05/AGENTS eski `ui_screenshots.py`'yi gösteriyordu → `ui_denetim.py`.

## Birleştirmeden önce (zorunlu)
- Tam takım (`pytest -q`, ~4 dk) · R-13 gerçek e2e üçlüsü · R-21 zorluk paketi `auto-pro` (CHALLENGE_RESULTS
  ile karşılaştır) · arayüz değiştiyse `ui_denetim.py ikisi --goruntu`.
- Birleştirmeyi kullanıcı yapar (Claude Code'da "Merge Without Review" engelli): önce PR #30, sonra bu dal.

## Geçmiş
- 2026-11-01: devir düzeni kuruldu (bu dosya, `baslangic` gösterimi, ön-commit kancası, R-35).
