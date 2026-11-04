---
id: 2026-10-17-deepseek-v4-1-flash-metin-protokolunde-akista-arac-cagrisi-k
tarih: 2026-10-17
tur: risk            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: izleniyor                # acik | izleniyor | cozuldu | kabul-edildi
alan: api
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor:
cozen_model:
ortam: Windows 11, Python 3.12.10
etiketler: [deepseek-v4.1-flash, metin-protokolu, akis, evren-sunucu]
kurallar: [R-07]
---

# deepseek-v4.1-flash metin protokolünde akışta araç çağrısı kayboluyor

## Belirti
Metin protokolünde (`<arac_cagrisi>`) deepseek-v4.1-flash akışlı yanıtta 5
denemenin 3'ünde araç bloğunu hiç döndürmedi (yalnız "Önce projeyi
tanıyayım."), 2'sinde içeriğe `</｜DSML｜ calls>` artığı karıştı. Akışsız
yanıtta blok + DSML artığı görüldü.

## Kök neden
Tahmin (sunucu tarafı): model zaman zaman kendi yerel araç biçimine (DSML)
kayıyor; `tools` verilmediğinde EVREN'in akış ayrıştırıcısı bu kısmı yutuyor.
Uygulama kodu değil.

## Çözüm
Henüz yok (sunucu). Yerel protokol (varsayılan) aynı modelde 5/5 sorunsuz;
deepseek-v4-flash iki protokolde 5/5. Boş yanıt dürtmesi bu durumu kısmen
kurtarır. Bu modeli metin protokolüyle kullanma.

## Kanıt
2026-10-17 doğrudan istekler (stream=True, 5'er deneme), LOOP_ANALYSIS.md.
2026-11-03/04: `tests/e2e_agent_real_api.py` metin protokolünde deepseek-v4.1-flash 4 koşunun 3'ünde düştü
("Önce … app.py dosyasına bakıyorum." deyip araçsız durdu). Plan modu istisnası bu ilk araçsız inceleme
niyetini dürtmüyordu → düzeltildi (`looks_like_investigation_intent`); düzeltmeden sonra model dürtüldü
(3 adım) ama araç bloğu yine gelmedi → sorun hâlâ sunucu/model tarafında, durum "acik" kalır. Yerel protokol
aynı koşularda geçti.

## Önleme
MODEL_CAPABILITIES.md'ye not. EVREN güncellenirse yeniden ölç.

## İlgili dosyalar
- docs/knowledge/MODEL_CAPABILITIES.md

## Gözlem 2026-10-19 (Claude Code masaüstü, claude-opus-5-5)
tests/e2e_agent_real_api.py art arda 4 koşu: deepseek-v4.1-flash metin protokolü 2 kez boş yanıtla
KALDI, 2 kez GEÇTİ (aralıklı). Bu test AgentRunner'ı doğrudan kurar; aynı gün eklenen servis
araçları/test bekçisi bu senaryoda devrede değil (services=None) — gerileme değil. Durum açık kalır.

## Gözlem 2026-11-04 (Claude Code masaüstü, claude-opus-5-5) — gözlemler 3854d7522898, 6d629fb7f224
Gözlem ajanı aynı e2e senaryosunun düştüğünü bildirdi (deepseek-v4.1-flash metin 4 kez / 2 makine; glm-5.3 metin
1 kez). Bugün `e2e_agent_real_api.py deepseek-v4.1-flash glm-5.3` 3 tur: deepseek metin 2/3 geçti (düşen turda
dürtmeden sonra da BOŞ yanıt → tur boş "done" bitti); glm-5.3 yerel ve metin protokolünde birer kez EVREN hatası
(adım 0, `durum=hata`). Aynı çağrı bir turda 4,6 sn, diğerinde 71 sn sürdü (EVREN yükü). Sonuç: sorun sunucu/model
tarafında, açık kalır. Uygulama tarafı iyileştirme (dal `feat/hiz-adim-azaltma`): dürtmeden sonra da boş yanıt
gelirse yedek model varsa (Auto Pro) ona geçilir, tur boş bitmez (`tests/test_hiz_adim.py`). Metin protokolü Auto
Pro'da yalnız model yerel araç çağrısını reddederse devreye girer.
