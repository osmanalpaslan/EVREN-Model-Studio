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

## Önleme
MODEL_CAPABILITIES.md'ye not. EVREN güncellenirse yeniden ölç.

## İlgili dosyalar
- docs/knowledge/MODEL_CAPABILITIES.md

## Gözlem 2026-10-19 (Claude Code masaüstü, claude-opus-5-5)
tests/e2e_agent_real_api.py art arda 4 koşu: deepseek-v4.1-flash metin protokolü 2 kez boş yanıtla
KALDI, 2 kez GEÇTİ (aralıklı). Bu test AgentRunner'ı doğrudan kurar; aynı gün eklenen servis
araçları/test bekçisi bu senaryoda devrede değil (services=None) — gerileme değil. Durum açık kalır.

