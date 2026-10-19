---
id: 2026-10-19-koyu-temada-isaretli-onay-kutusu-tiksiz-beyaz-kare-gorunuyor
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [tema, onay-kutusu]
kurallar: []
---

# Koyu temada işaretli onay kutusu tiksiz beyaz kare görünüyordu

## Belirti
Koyu temada vurgu rengi beyaza çevrilince işaretli onay kutusu tiksiz dolu beyaz kare göründü
(MCP kartı ekran görüntüsünde fark edildi).

## Kök neden
Doğrulandı: QCheckBox::indicator:checked yalnız arka planı vurgu rengine boyuyordu; mavi iken
fark ediliyordu. Önceki değişikliğimin (mavi kaldırma) yan etkisi.

## Çözüm
theme._check_icon: on_accent renginde tik SVG'si geçici klasöre yazılır, QSS `image: url(...)`.

## Kanıt
build/shots/mcp_tik_crop.png (QT_QPA_PLATFORM=windows): işaretli kutularda koyu tik.

## Önleme
Renk belirteci değiştirince onay kutusu/seçili satır gibi DURUM gösteren öğelere ekran görüntüsünde bak.

## İlgili dosyalar
src/evren_studio/ui/theme.py
