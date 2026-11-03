---
id: 2026-11-01-yavaslik-gecisi-zayif-modele-gitti-gemma-celiskili-testte-hi
tarih: 2026-11-01
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: izleniyor                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, EVREN API (yoğun akşam: model_capacity_exhausted, 503)
etiketler: [auto-pro, yavaslik, gemma, zorluk, celiski]
kurallar: [R-21]
---

# Yavaşlık geçişi zayıf modele gitti, gemma çelişkili testte hile yazdı

## Belirti
2026-11-01 akşamı zorluk paketi (auto-pro) "celiski" 2/3: KALDI "hile kodu yok"; tur 6 dk sınırına takıldı
(adım 0 kaydı) ve uzayan model çağrısı sonraki "kapsam" görevinin turunu kesti (4,2 sn, 'cancelled', 2/3).

## Kök neden
Doğrulandı (model_calls + oturum kaydı): paket başındaki yoklamada deepseek-v4.1-flash EVREN'den
`model_capacity_exhausted` aldı → sağlık sırasında sona gitti → kod zinciri qwen → gemma → deepseek. qwen iki
adımda 21 token/sn (o günkü normali ~49) ölçülünce A3 yavaşlık bekçisi `fallback_models.pop(0)` ile gemma-4-31b'ye
geçti; gemma çelişkiyi fark ettiği hâlde (klasör adına göre) testi geçiren hile kodu yazdı. Uyarlanabilir sıra
(d9070b6) bu olayda devrede değildi (deepseek'in hız ölçümü yoktu). Ölçüm düzeneği zaman aşımında `stop()` sonrası
5 sn bekleyip sonraki göreve geçiyordu.

## Çözüm
- `modelstats.SLOW_SWITCH_EXCLUDE` (kod/plan/inceleme → gemma-4-31b): YAVAŞLIK nedeniyle bu modellere geçilmez;
  güçlü yedek yoksa yavaş model korunur. Sunucu hatasında geçiş serbest.
- `tests/e2e_zorluk_real_api.py`: zaman aşımında tur gerçekten bitene kadar (≤180 sn) beklenir.

## Kanıt
tests/test_autopro_cekirdek.py: `test_yavaslikta_kod_rolunde_zayif_modele_gecilmez`,
`test_sunucu_hatasinda_zayif_modele_gecis_serbest`; mutasyon (yasak listesi boş) 1 test kırdı. Gerçek API ile
celiski + kapsam tekrar ve paketin tamamı: sonuç bu kayda eklenecek (durum `izleniyor`).

## Önleme
Yedek modele geçiş kuralı eklerken geçilen modelin o roldeki doğruluğunu (zorluk/maraton ölçümü) gözet; hız
kazanmak için zayıf modele düşme. R-21: zorluk paketi dal sonunda zorunlu.

## İlgili dosyalar
- src/evren_studio/agent/modelstats.py
- src/evren_studio/agent/runner.py
- tests/e2e_zorluk_real_api.py
