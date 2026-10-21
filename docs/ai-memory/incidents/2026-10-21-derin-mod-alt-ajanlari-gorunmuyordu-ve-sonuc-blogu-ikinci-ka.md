---
id: 2026-10-21-derin-mod-alt-ajanlari-gorunmuyordu-ve-sonuc-blogu-ikinci-ka
tarih: 2026-10-21
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PowerShell 5.1, Python 3.12.10
etiketler: [derin-mod, gorunurluk, r-26]
kurallar: [R-26]
---

# Derin Mod alt ajanları görünmüyordu ve sonuç bloğu ikinci katmanı yoktu

## Belirti
Anla+Planla (~7 dk) ve Doğrula (13 dk) süresince oturumda hiçbir mesaj yoktu (alt ajanlar bellek içi kayıtla
çalışıyor); kullanıcı işin sürüp sürmediğini göremedi. İkinci planlayıcı geçerli plan vermedi ("tek geçerli plan"),
nedeni görülemedi çünkü döküm kaydedilmiyordu. Belgede "yoksa bir kez daha istenir (R-26)" yazıyordu ama yalnız
aynı tur içi dürtme vardı. Kanıt kaynağı: kullanıcının EVREN Studio oturumu #16 (2026-10-21 13:50-15:40, Derin Mod, hesap kapama raporu; veritabanı kopyası ve klasördeki EVREN_DERIN.md / EVREN_RAPOR.md / EVREN_PLAN.md incelendi).

## Kök neden
Doğrulandı (kendi tasarım eksiğim). Alt ajan sonuçları yalnız son metin olarak dönüyordu; ilerleme/döküm yoktu;
R-26'nın ikinci katmanı ("yalnız sonucu ver" turu) uygulanmamıştı.

## Çözüm
- Her alt ajan bitince not: etiket, araç sayısı, süre, model, durma nedeni, blok yoksa "sonuç bloğu YOK";
  çalışma çubuğunda "Derin · <faz> (n alt ajan bitti)".
- Döküm `<veri>/deep/<zaman>/<etiket>.md`; rapor klasörü gösterir.
- `run_subagent`: blok yine yoksa araçsız 2 adımlık "yalnız bloğu yaz" turu. Plan vermeyen model günlüğe yazılır.

## Kanıt
`test_alt_ajan_blok_vermezse_yalniz_sonuc_turu_acilir`; arayüz testinde döküm dosyaları ve "anla-kod bitti" notu.

## Önleme
R-26 (üç katman) yeni gözetimsiz alt ajanlarda da uygulanmalı; gözetimsiz iş ekranda iz bırakmalı.

## İlgili dosyalar
- src/evren_studio/agent/deep.py
- src/evren_studio/ui/deep_ui.py
