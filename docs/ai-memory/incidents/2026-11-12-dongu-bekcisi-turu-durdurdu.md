---
id: 2026-11-12-dongu-bekcisi-turu-durdurdu
tarih: 2026-11-12
tur: risk            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: bilinmiyor
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gozlem, dongu-bekcisi, mcp, R-22]
kurallar: [R-19, R-22, R-36]
---

# Döngü bekçisi turu durdurdu

## Belirti
Gözlem ajanından (uygulama çalışırken, otomatik ve temizlenmiş):
ajan_anomali
Konum:
- (yığın izi yok)
Ayrıntı:
- model: deepseek-v4.1-flash
- rol: kod
- olay: loop

## Kök neden
Doğrulandı (iki katman):
1. 13 durdurmanın kaynağı masaüstü QA'sı (2026-11-05/06): "sonucu oku → Topla'ya tıkla → yeniden oku" döngü
   SAYILIYORDU — araya giren tıklama sayaçları sıfırlamıyordu. Aynı gün yalnız `mcp__masaustu__` için düzeltildi
   (runner yorumu "gözlem cf3c8b0737b8"); o tarihten beri tekrarlamadı.
2. Ama kural tek araç ailesine özeldi: kullanıcının GERÇEK veritabanında (2026-11-12 analiz) web QA oturumlarında
   Playwright `browser_navigate` / `browser_console_messages` tekrarları "arada dosya değişmedi; sonuç aynı olacak" diye
   YANLIŞ uyarı aldı (3 uyarı) — dış aracın sonucu dosyaya değil sayfanın durumuna bağlı. Ayrıca gözlem kaydı döngünün
   TÜRÜNÜ ve aracı hiç taşımıyordu (yalnız model/rol/olay) → 13 kaydın kaynağı geriye dönük ancak kod yorumundan
   bulunabildi; model değişip tur sürdüğünde de başlık "turu durdurdu" diyordu.

## Çözüm
`agent/runner.py` `_guard`: masaüstü kuralı TÜM dış araçlara (`mcp__*`) genellendi — (1) aynı sunucudaki başarılı
EYLEM o sunucunun diğer sayaçlarını sıfırlar, eylem eşiği 4/6; (2) başarılı YEREL komut (sunucuyu yeniden başlatma,
derleme) tüm dış sayaçları sıfırlar; (3) arada eylem yokken aynı dış okuma yine 3. kezde döngü (masaüstü ölçümü korunur);
dış araç uyarısı doğru gerekçeyle (EXTERNAL_REPEAT_NOTE). Gözlem: `dongu_turu` (ayni_cagri / dis_arac_tekrar /
basarisiz_duzenleme / ileri_geri) + `arac` (yalnız ad; yol/argüman değil, bilinmeyen tür/ad yazılmaz); model değişip tur
sürdüyse "Döngü bekçisi: model değiştirildi, tur sürdü" (düşük önem); kayıt döngüye giren modelin adına. Ek: proje görevi
turunda yürütücünün `EVREN_PLAN.md` / `EVREN_RAPOR.md`'si yazılmaz (PROTECTED_NOTE) — 2026-11-11 e2e'de ajan planı
"tamam" işaretleyip doğrulama komutunu orada düzeltmeye çalışmıştı (emek bir sonraki kayıtta siliniyordu).
İşe yaramayan ilk deneme: dış OKUMA eşiğini 3/5'e çıkarmak → masaüstü R-22 testleri (arada eylem yokken 3 okuma = döngü)
düştü; ölçülmüş kural bozulmasın diye geri alındı, yerine sıfırlama kuralları eklendi.

## Kanıt
Gözlem `cf3c8b0737b8` (dal gozlem-kayitlari): 13 kez, 1 makine, ilk 2026-11-05T19:07:47+00:00, son 2026-11-06T21:00:34+00:00,
sürümler 0.2.0+2a798a3, 0.2.0+69344d1, 0.2.0+b940200, 0.2.0+d1fd6c6, 0.2.0+ecd9cbc.
tests/test_dongu_dis_araclar.py 12 (tetiklenen + tetiklenmeyen: sayfayı yeniden açmak, yerel komut sonrası okuma,
eylemsiz 3 okuma, sonsuz tıklama, başarısız eylem, yerel kural değişmedi, model değişimi kaydı, gözlem gizliliği, korumalı
dosya / normal turda serbest) + test_masaustu_otomatik + test_loop_guard değişmeden geçti; mutasyon 15/15. Gerçek API
ölçümü (zorluk + web QA) 0.5.1 toplu testlerinde.

## Önleme
Yeni bir dış araç ailesi eklendiğinde ayrıca kural yazmaya gerek yok (`mcp__` öneki genel); gözlemde döngünün türü ve aracı
artık var — tekrar ederse kaynağı doğrudan görülür.

## İlgili dosyalar
- src/evren_studio/agent/runner.py (_guard, EXTERNAL_*, PROTECTED_NOTE, protected_files)
- src/evren_studio/gozlem.py (ajan_olayi, _AYRINTI_IZINLI)
- src/evren_studio/ui/project_ui.py, src/evren_studio/ui/session_view.py (protected_files bağlantısı)
- tests/test_dongu_dis_araclar.py, tests/test_project_ui.py
