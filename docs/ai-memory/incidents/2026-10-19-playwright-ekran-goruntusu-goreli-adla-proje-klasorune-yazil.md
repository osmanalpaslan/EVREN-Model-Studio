---
id: 2026-10-19-playwright-ekran-goruntusu-goreli-adla-proje-klasorune-yazil
tarih: 2026-10-19
tur: risk            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: mcp
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [playwright, qa, dosya]
kurallar: []
---

# Playwright ekran görüntüsü göreli adla proje klasörüne yazılıyordu

## Belirti
Görsel göz denemesinde `browser_take_screenshot {"filename": "goz-test.png"}` görüntüyü KULLANICININ
proje klasörüne yazdı (build/pw_proje/goz-test.png). Yayına çıkmadan, deneme sırasında fark edildi.

## Kök neden
Doğrulandı: Playwright MCP göreli dosya adlarını "workspace root"a (sunucunun çalışma klasörü =
proje) göre çözer.

## Çözüm
QaTools her zaman MUTLAK yol verir: `<veri>/mcp/playwright/cikti/goz-<saat>-<n>.png` (çıktı klasörü
Playwright'a izinli). Bu araç modele sunulan araç listesinde yok; yalnız visual_check kullanır.
Test dosyası silindi.

## Kanıt
Mutlak yolla görüntü çıktı klasöründe oluştu, proje klasöründe yalnız index.html kaldı;
e2e_qa_real_api "proje dosyalarına dokunulmadı" denetimi geçti.

## Önleme
Dış araca dosya yolu verirken mutlak yol ver ve proje klasörünü yan etki için denetle.

## İlgili dosyalar
src/evren_studio/agent/qa.py (QaTools.run)
