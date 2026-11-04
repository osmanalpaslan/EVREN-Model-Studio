---
id: 2026-11-04-zorluk-paketi-gorevi-dustu-mini-proje
tarih: 2026-11-04
tur: risk            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: test
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gozlem]
kurallar: []
---

# Zorluk paketi görevi düştü: mini_proje

## Belirti
Gözlem ajanından (uygulama çalışırken, otomatik ve temizlenmiş):
e2e_basarisiz: kalan kontroller: kendi testleri geçiyor
Konum:
- (yığın izi yok)
Ayrıntı:
- gorev: mini_proje
- model: auto-pro
- sonuc: 4/5
- kaynak_betik: zorluk
- durma: cancelled

## Kök neden
Doğrulandı (model_calls + oturum kaydı): Madde 7 ölçümünün ÖNCE (b0998db) ve SONRA-1 (7a51eaf) koşuları. ÖNCE: qwen o saatte ~33 token/sn (normalinin üçte biri) üretti, 6 dk düzenek sınırında kesildi. SONRA-1: deepseek-v4.1-flash'ın tek çağrısı 304 sn boyunca yalnız ~2.100 karakter düşünme damlattı, yanıtsız kesildi.

## Çözüm
256967a: çağrı içi damla akış kuralı (DECISIONS #121) — ≥120 sn, <15 karakter/sn ve <10 akış satırı/sn → kes, yedek aynı adımı yapar. Son kodla tam paket 12/12, mini_proje 5/5 (PR #41).

## Kanıt
Gözlem `c9b5c1591110` (dal gozlem-kayitlari): 1 kez, 1 makine, ilk 2026-11-04T17:49:39+00:00, son 2026-11-04T17:49:39+00:00,
sürümler 0.2.0+b0998db.

## Önleme
tests/test_hiz_adim.py damla akış testleri (tetiklenen/tetiklenmeyen), mutasyon 7/7. Aynı imzalı gözlem cbf0ba444efe de bu kayda bağlandı.

## İlgili dosyalar
