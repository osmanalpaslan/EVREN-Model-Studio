---
id: 2026-10-15-ayarlar-acilista-okunmuyordu
tarih: 2026-10-15
tur: hata
onem: yuksek
durum: cozuldu
alan: ayarlar
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12
etiketler: [config, uctan-uca-test]
kurallar: [R-03]
---

# Kaydedilen ayarlar açılışta hiç okunmuyordu

## Belirti
Ayarlar sayfasında kaydedilen değerler (varsayılan model, zaman aşımı,
tema…) uygulama yeniden açıldığında varsayılana dönüyordu.

## Kök neden
Doğrulandı: `AppContext.__init__` `settings or Settings()` kullanıyordu;
`ConfigStore.load()` kodun hiçbir yerinde çağrılmıyordu
(`grep store.load` → 0 sonuç). Ayrıca config dosyası kullanıcı veri klasörü
değiştirirse yeni klasöre yazılıyor, sonra bulunamıyordu. `test_config.py`
yalnızca `ConfigStore` kaydet/oku çiftini test ettiği için hata görünmedi.

## Çözüm
`AppContext` artık `ConfigStore(default_data_dir()).load()` ile başlıyor;
config.json her zaman varsayılan veri klasöründe tutuluyor. Commit `c8e17d2`.

## Kanıt
`tests/test_ui_agent_flow.py` geçici veri klasörüyle `MainWindow` açıyor;
`tools/ui_screenshots.py` config.json'daki temayı (açık/koyu) gerçekten uyguluyor.

## Önleme
R-03: kaydetme özelliği okuma yoluyla birlikte uçtan uca test edilmeli.

## İlgili dosyalar
src/evren_studio/ui/app_context.py, src/evren_studio/config.py
