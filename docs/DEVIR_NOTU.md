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

- **Güncelleme:** 2026-11-01 19:42 · Claude Code (claude-opus-5-5) · masaüstü bilgisayar
- **Aktif dal:** `feat/profesyonel-kalite` (GitHub'da var; PR #30 `feat/clear-ve-buyuk-ozet` üzerine kurulu —
  ikisi de master'a BİRLEŞTİRİLMEDİ). Başka bilgisayarda: `git fetch && git switch feat/profesyonel-kalite`.
- **Kaldığı yer:** Madde 4 ve 5'in kodu commit'lendi (b099b7a, 7314251, 5e70bf1, c1ec1c9); iki gerçek ölçüm sürüyor
  (aşağıda). Sonuçlar işlenince Madde 4 ve 5 YAPILDI olur. Ölçümler sürerken Madde 6'ya (bulunan hatalar) geçildi.
- **Çalışan uzun testler (yalnız bu bilgisayarda; başka yerde devam edilirse tekrarla):**
  - özetli maraton A — 19:18, worktree `C:\Users\Osman Alpaslan\evm_wt`; günlük `...\evm_t3\maraton_A_ozet.log`;
    tekrar: `set MARATON_OZET_ESIK=20000` ve `tests\e2e_marathon_real_api.py A auto-pro <klasör>`
  - kotalı maraton A — 19:40, worktree `...\evm_wt2`; günlük `...\evm_t4\maraton_A_kota.log`;
    tekrar: `set MARATON_KOTA_TESTI=2:3` ve aynı komut. Beklenen: KOTA TESTİ durdu=1 kart=1 plan=1, devam turu=1,
    kabul 10/10.
  - İşi biten worktree'ler silinir: `git worktree remove <klasör>`.

## Geliştirme sırası (kullanıcı onaylı, 2026-11-01)

Kullanıcı neredeyse yalnız **Auto Pro** kullanıyor; hedef "tam profesyonel uygulama". Her madde: hedefli test +
kritikse mutasyon + paket; R-13/R-21 gerçek ölçümler dal sonunda.

| # | Madde | Durum | Dal / commit | Not / kalan |
|---|---|---|---|---|
| 0 | Taban ölçüm (auto-pro) | YAPILDI | — | zorluk 12/12, proje 5/5, maraton A 10/10 (26 dk), B 13/13 (19 dk), C 10/10 (28 dk; 1. mesaj 21 dk/33 adım) |
| 1 | Açık tema okunurluğu, görünmeyen düğmeler, Ayarlar'daki sabit renkler | YAPILDI | e940402, 5225fc1, 316d69d, 2050af9 | `tools/ui_denetim.py` + `tests/test_okunurluk.py` (R-33); açık/koyu HATA 0 |
| 2 | Ücretsiz web araması (Tavily) + Auto Pro'ya dahil | YAPILDI | 2050af9 | Tavily → anahtarsız Tavily → DuckDuckGo → "eldeki bilgiyle devam"; Ayarlar > Web Araması; R-25 ölçümü CHALLENGE_RESULTS.md |
| 3 | Uzun proje maratonları D (7 mesaj) ve E (PWA) | YAPILDI | 0ced757 | kabul denetimleri bilinen doğru/yanlışla sınandı |
| 4 | Auto Pro bağlam şişmesi (/compact olmuyor, otomatik özet yok) | SÜRÜYOR | b099b7a | token tahmini 3,5 → gerçek kullanımla kalibre (R-34). Maraton D 25/25 (52 dk, 7 mesaj; gerçek bağlam ~40k → özet gerekmedi; eski hesap %13 eksik, yeni varsayılan %24 fazla, kalibrasyonla gerçeğe iner). Kalan: özetli maraton A sonucu; Proje/Derin akışında özet tetiklenmesi |
| 5 | Kota bitince otomatik devam paneli | SÜRÜYOR | (bu commit) | Normal oturum YAPILDI: kota kapısı güvenli noktada durur, 429'da da kart; sohbette kart (yenilenme saati, geri sayım, ☑ otomatik devam = Ayarlar `auto_resume`, Şimdi dene/Vazgeç); saatinde kota yoklanır; plan DB `meta.pending_resume` (açılışta geri gelir); elle mesaj iptal eder. `tests/test_kota_devam.py` 8, mutasyon 2. (a) YAPILDI: Proje/QA/Derin aynı kart + kalıcı plan (`flow`); Derin Mod uygulama kapanınca fazdan sürdürülemez (not verilir). Kalan: (b) gerçek ölçüm: `DAILY_MIN_TOKENS` yapay yükseltilip maraton A ortasında dur → devam → kabul 10/10 |
| 6 | Testlerde bulunan hata/eksikler | SIRADA | — | aşağıdaki liste |
| 7 | Proje bitirme hızı (tutarlılığı bozmadan) | SIRADA | — | Döküm YAPILDI (2026-11-01, maraton A-D + proje ajanı DB'leri): sürenin ~%97'si MODEL BEKLEMESİ; araç/komut toplam 0,3-1,4 dk. deepseek-v4.1-flash çağrı başına ort. 30-85 sn (en uzun 274), qwen3.8-flash-next 15-40 sn. Kaldıraçlar: kod rolünde model sırası (ölçümle), düşünme süresi (reasoning_effort/çıktı uzunluğu), adım sayısı (paralel araç çağrısı, gereksiz okuma), yavaş model erken geçişi (`_slow`). Tutarlılık zorluk + maraton kabulüyle korunur |
| 8 | Derin Mod yeniden ele alınacak | SIRADA | — | aşamaya göre en doğru/güçlü EVREN modelleri (ölçümle); çalışırken kısa canlı durum cümleleri; mevcut özellikleri önce kodda doğrula; `e2e_derin_real_api` önce/sonra |
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
- [~] Model zaman zaman İngilizce ara cümle yazıyor (ölçüm: 96 metinli yanıtın 3'ü, hepsi deepseek-v4.1-flash, tur başında). Dil kuralı ara cümleleri kapsayacak şekilde netleştirildi; A/B ölçümü sürüyor.
- [ ] Plan modunda `web_search` kapalı (EXEC); araştırma için açılması değerlendirilecek.
- [ ] Klasörsüz sohbet oturumlarında hiç araç yok (web araması da yok).
- [ ] deepseek-v4.1-flash bazı adımlarda 30-130 sn bekletiyor (Madde 7 ile birlikte).

- [x] R-05/AGENTS eski `ui_screenshots.py`'yi gösteriyordu → `ui_denetim.py`.

## Birleştirmeden önce (zorunlu)
- Tam takım (`pytest -q`, ~4 dk) · R-13 gerçek e2e üçlüsü · R-21 zorluk paketi `auto-pro` (CHALLENGE_RESULTS
  ile karşılaştır) · arayüz değiştiyse `ui_denetim.py ikisi --goruntu`.
- Birleştirmeyi kullanıcı yapar (Claude Code'da "Merge Without Review" engelli): önce PR #30, sonra bu dal.

## Geçmiş
- 2026-11-01: devir düzeni kuruldu (bu dosya, `baslangic` gösterimi, ön-commit kancası, R-35).
