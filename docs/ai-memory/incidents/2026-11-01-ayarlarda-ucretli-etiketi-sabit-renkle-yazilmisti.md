---
id: 2026-11-01-ayarlarda-ucretli-etiketi-sabit-renkle-yazilmisti
tarih: 2026-11-01
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [tema, okunurluk, ayarlar]
kurallar: [R-33]
---

# Ayarlarda ücretli etiketi sabit renkle yazılmıştı

## Belirti
Ayarlar > Ücretli Sağlayıcılar'da OpenAI/Anthropic başlığının yanındaki "ücretli · doğrulanmadı" yazısı
`<span style='color:#d9a441'>` ile sabit sarı renkteydi; açık zeminde (#ffffff/#f6f6f4) kontrast ~2,1 —
okunmuyordu. Kullanıcının "ayarlarda sabit tanımlar koyu/açık mod kaynaklı hataya düşüyor" bildiriminin
parçası. tools/ui_denetim.py bunu yakalamadı: zengin metin (HTML) içindeki kısa span etiketin tamamı gibi
ölçülmüyor (etiketin baskın rengi siyah başlık).

## Kök neden
Doğrulandı: renk temadan değil koda gömülü HTML'den geliyordu; tema değişince değişmiyordu. Arayüz kodunda
`color:#` araması bunun tek örnek olduğunu gösterdi (2026-11-01).

## Çözüm
Başlık iki etikete bölündü; "ücretli" etiketi `role="warning"` aldı ve rengi QSS'ten (`QLabel[role="warning"]`
→ `p.warning`; açıkta #8f5b0a, koyuda mevcut uyarı rengi) gelir.

## Kanıt
`QT_QPA_PLATFORM=windows tools/ui_denetim.py … ikisi --goruntu`: açık ve koyu HATA 0; açık tema Ayarlar
görüntüsünde "ücretli · doğrulanmadı" koyu kehribar ve okunur. tests/test_okunurluk.py geçti.

## Önleme
R-33 (renk/stil değişikliğinde denetim). Arayüz kodunda HTML içine sabit renk (`color:#…`) yazma; rol özelliği
+ QSS kullan. Denetim aracı zengin metindeki renkli parçaları ayrı ölçmüyor — bilinen sınır.

## İlgili dosyalar
- src/evren_studio/ui/settings_page.py
- src/evren_studio/ui/theme.py
