---
id: 2026-10-19-sohbete-dosya-ve-gorsel-yapistirilamiyordu-birakilan-dosya-y
tarih: 2026-10-19
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [ekler, gorsel, yapistir, surukle-birak]
kurallar: [R-05, R-07]
---

# Sohbete dosya ve görsel yapıştırılamıyordu; bırakılan dosya yol yazıyordu

## Belirti
Kullanıcı: "Chat ekranına kopyaladığım dosya veya görseli yapıştıramıyorum;
dosyaları sürüklediğimde adresleri yazıyor." Ataç düğmesi yalnız proje
klasöründeki dosyaları `@yol` metni olarak ekliyordu ve klasörsüz sohbette
gizliydi. Görsel girdi hiç yoktu ve EVREN'de gerçek istekle denenmemişti.

## Kök neden
Doğrulandı: `ComposerEdit` (QPlainTextEdit) varsayılan `insertFromMimeData`
kullanıyordu; dosya URL'leri düz metin (yol) olarak yazılıyor, panodaki görsel
yok sayılıyordu. Mesaj modeli yalnız metin içeriği taşıyordu.

## Çözüm
- `ui/attachments.py`: ek kartları (küçük resim / dosya kartı, ✕), görseller
  1568 px'e küçültülüp veri klasörü `attachments/` altına kopyalanır.
- `ComposerEdit.insertFromMimeData`: yerel dosya → ek, panodaki görsel → ek,
  metin → normal yapıştırma. Çerçeveye bırakma da desteklenir.
- Görseller kullanıcı mesajının `meta.images` alanında; `to_api_messages`
  `_images` iç alanıyla taşır (en yeni 6 görsel), istemci gönderirken çevirir
  (`api/images.py`: EVREN/OpenAI Chat image_url, OpenAI Responses input_image,
  Anthropic image/base64). Özet isteği görsel göndermez.
- Dosya ekleri metinse içeriği `<ekli_dosyalar>` bloğuna girer; ikili veya
  100 KB üstü dosyada yalnız ad + yol notu gider.
- Görsel okuyamayan motorda (glm-5.3, deepseek-v4-flash) gönderimden önce
  auto'ya geçmek sorulur; reddedilirse metin ve ekler geri konur.

## Kanıt
- Gerçek API (2026-10-19, `build/probe_vision.py`, "K7Q4" + kırmızı kare):
  qwen3-vl-30b, gemma-4-31b, qwen3.8-flash-next, deepseek-v4.1-flash ve auto
  doğru okudu; mimo-v2.6-pro rengi doğru söyledi (yazı testi ilk turdaki
  bozuk görselle yapıldı); glm-5.3 ve deepseek-v4-flash 400
  `feature_not_enabled` (yalnız metin).
- Gerçek uygulama (`build/shot_attach.py`): görsel + CSV sürükle-bırak yolu ile
  auto'ya gönderildi; yanıt kare rengini (mavi) ve CSV toplamını (215) doğru verdi.
- `tests/test_attachments_usage.py` (12 test).

## Önleme
Yapıştırma/bırakma davranışı test ile korunur (yol metne yazılmaz). Ekran
görüntüsü için test görseli ÇİZERKEN de QT_QPA_PLATFORM=windows kullan:
offscreen'de harfler kutucuk çizildi ve ilk görsel ölçümü yanılttı (R-05).

## İlgili dosyalar
- src/evren_studio/ui/attachments.py
- src/evren_studio/ui/composer.py
- src/evren_studio/ui/session_view.py
- src/evren_studio/api/images.py
- src/evren_studio/agent/runner.py
