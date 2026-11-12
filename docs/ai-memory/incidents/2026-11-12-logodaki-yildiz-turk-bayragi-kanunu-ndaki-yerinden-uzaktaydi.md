---
id: 2026-11-12-logodaki-yildiz-turk-bayragi-kanunu-ndaki-yerinden-uzaktaydi
tarih: 2026-11-12
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, PySide6
etiketler: [marka, bayrak, logo, geometri, R-25]
kurallar: [R-25]
---

# Logodaki yıldız Türk Bayrağı Kanunu'ndaki yerinden uzaktaydı

## Belirti
Kullanıcı "animasyonları Türk bayrağı simgelerine sadık kalarak revize et" isteyince geometri yeniden ölçüldü:
32 px'ten büyük çizimlerde (karşılama logosu 72 px, .ico'nun 48–256 px boyutları, kurulum sihirbazı) yıldız
hilalden belirgin uzaktaydı; ≤32 px'te ise ayrı bir "sıkı" sabitle yakın çiziliyordu (iki boyutta iki farklı logo).

## Kök neden
Doğrulandı. Türk Bayrağı Tüzüğü: "E: Yıldız dairesinin ay iç dairesinden uzaklığı 1/3 G". Resmî çizimde E, iç ay
dairesinin SOL kenarından yıldız dairesinin SOL kenarına ölçülür. 2026-10-17 kodu (5328ecb, Claude Code) E'yi
DIŞ ay merkezinden ölçmüştü: yıldız merkezi dış ay merkezinden 0,4583 G uzaktaydı, doğrusu 0,3208 G (fark 0,1375 G).
Wikimedia "Flag of Turkey" SVG'si (G = 60000) ile doğrulandı: dış ay merkezi 30000, iç ay merkezi 33750, yıldızın
aya bakan ucu 41750 → yıldız merkezi uçkurluktan 0,8208 G. Eski testin kendisi de yanlış yorumu doğruluyordu
(`(_STAR_CX - _R_STAR) / G == 1/3`). Küçük boyutların "sıkı" sabiti (15,5 / 48 = 0,3229 G) rastlantıyla doğruya
yakındı. Yan bulgu: yol "winding" doldurma kuralıyla çiziliyordu; animasyonda iç ay dış ayın içindeyken halkanın
içi de doluyordu (eski sabit çizimde görünmüyordu).

## Çözüm
`ui/brand.py`: `_E = G/3`, `_STAR_CX = C − D/2 + E + F/2` (her boyutta aynı, "sıkı" sabit kaldırıldı); çift-tek
doldurma kuralı. Yeni cam karo simge, karşılama animasyonu (halka → hilal, yıldız 72° dönüşle yerine oturur) ve
72° adımlı çalışma yıldızı bu geometriyle çizilir; `assets/evren.ico` ve kurulum sihirbazı resimleri her
paketlemede koddan üretilir (`tools/paketle.py update_icon`).

## Kanıt
tests/test_brand.py: `test_bayrak_oranlari` (E iç ay dairesinden), `test_yildiz_wikimedia_resmi_cizimiyle_ayni_yerde`
(33750 / 41750 / 0,8208 G), `test_animasyon_basinda_halka_sonunda_yasal_hilal` (halkanın ortası boş), simge piksel
denetimi; mutasyon 13/13 (eski `_STAR_CX = G/3 + F/2` geri konunca iki test düşer).

## Önleme
Ölçü kuralı olan çizimlerde (bayrak, logo, standart) testi BAĞIMSIZ bir referans çizimle (resmî/kamuya açık SVG'nin
sayılarıyla) yaz; kodun kendi yorumunu doğrulayan test hatayı yakalamaz (R-25'teki "bilinen doğru" ilkesinin
geometri karşılığı).

## İlgili dosyalar
- src/evren_studio/ui/brand.py
- tests/test_brand.py
- tools/paketle.py (update_icon, wizard_images)
- assets/evren.ico
