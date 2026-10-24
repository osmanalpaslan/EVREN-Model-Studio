---
id: 2026-10-24-godot-guvenilmeyen-mod-klasorunu-ice-aktarinca-oyun-modelsiz
tarih: 2026-10-24
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Godot 4.7.2, Blender 5.2.3
etiketler: [F7, godot, guvenilmeyen-klasor, olcum-duzenegi]
kurallar: [R-25]
---

# Godot güvenilmeyen mod klasörünü içe aktarınca oyun modelsiz paketlendi

## Belirti
F7 hattında EXE ekransız çalışırken "Cannot get class ''" yazdı; PWA kontrolüm yine de GEÇTİ dedi. İnceleme: Godot
`--import` proje içindeki mods/ klasörünü de taradı, oradaki .blend için Blender yolu istedi ("Blender path is invalid")
ve tarama yarıda kaldı; assets/kilic.glb hiç içe aktarılmadı → oyun MODELSİZ paketlendi. PWA kontrolü yalnız "motor
başladı + tuval var" baktığı için bunu kaçırdı. Ayrıca gerçek ajan, güvenilmeyen klasöre .gdignore yazıp sonra sildi.

## Kök neden
Doğrulandı: Godot proje kökündeki her klasörü içe aktarır; güvenilmeyen klasör Godot için de dışlanmamıştı. Kabul
denetimi zayıftı (konsol hatası ve model yüklenmesi denetlenmiyordu).

## Çözüm
- Güvenilmeyen klasörlere otomatik boş `.gdignore` (işaretlenince, her ajan turunda, godot_export'tan önce):
  Godot o klasörü hiç işlemez — güvenlik kazancı da.
- Güvenilmeyen klasöre YAZMA da engellendi (okuma serbest).
- PWA kontrolü konsolda ERROR/"Failed loading" varsa KALIR; EXE kontrolü de ERROR satırına bakar. Görsel doğrulama:
  Playwright ekran görüntüsünde kılıç modeli görüldü.

## Kanıt
tests/e2e_oyun_real_api.py hat 9/9 (düzeltmeden önce 8/9 ve zayıf kontrol); tests/test_f7_oyun.py.

## Önleme
R-25: kabul denetimi "çalıştı" ile yetinmesin; asıl çıktının (model) yüklendiğini/ göründüğünü denetle.

## İlgili dosyalar
- src/evren_studio/agent/untrusted.py, src/evren_studio/agent/runner.py, tests/e2e_oyun_real_api.py
