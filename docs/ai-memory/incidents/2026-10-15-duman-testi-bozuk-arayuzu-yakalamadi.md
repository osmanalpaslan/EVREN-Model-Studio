---
id: 2026-10-15-duman-testi-bozuk-arayuzu-yakalamadi
tarih: 2026-10-15
tur: yanlis-iddia
onem: yuksek
durum: cozuldu
alan: test/surec
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PySide6 6.12
etiketler: [duman-testi, gorsel-dogrulama, durum-raporu]
kurallar: [R-05, R-10]
---

# Duman testi bozuk arayüzü yakalamadı; belgeler "tamamlandı" diyordu

## Belirti
`docs/PROJECT_STATE.md` "Türkçe PySide6 arayüzü: 11 sayfa … SMOKE_OK" ve
"Aşama 1 TAMAMLANDI" diyordu. Gerçekte arayüzde bozuk Türkçe metinler,
dağınık düzen (ekranın çoğu boş, kartlar ve düğmeler biçimsiz) vardı;
kullanıcı arayüzü "çok başarısız" buldu.

## Kök neden
Doğrulandı: `tests/smoke_ui.py` yalnızca pencerenin açılıp 3 saniye sonra
hatasız kapandığını denetliyor. Metin içeriği veya görünüm hiç kontrol
edilmedi; ekran görüntüsü alınıp bakılmadı. "Testler geçti" bilgisi
"arayüz iyi" anlamına genişletildi.

## Çözüm
Arayüz yeniden tasarlandı (0.2.0). `tools/ui_screenshots.py` eklendi:
gerçek API çağırmadan örnek oturum, onay kutusu, Ayarlar ve Modeller
ekranlarını koyu/açık temada PNG olarak üretir. `tests/test_ui_agent_flow.py`
arayüz davranışını (onay kutusu görünür, dosya değişir, panel güncellenir)
doğrular. `tests/test_source_hygiene.py` bozuk kodlamayı yakalar.

## Kanıt
Commit `c8e17d2`; `build/shots/*.png` ekran görüntüleri incelendi.

## Önleme
R-05, R-10.

## İlgili dosyalar
tests/smoke_ui.py, tools/ui_screenshots.py, tests/test_ui_agent_flow.py, docs/PROJECT_STATE.md
