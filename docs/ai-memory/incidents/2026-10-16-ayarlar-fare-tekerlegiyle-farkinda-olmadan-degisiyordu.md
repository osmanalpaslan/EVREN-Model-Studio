---
id: 2026-10-16-ayarlar-fare-tekerlegiyle-farkinda-olmadan-degisiyordu
tarih: 2026-10-16
tur: hata
onem: orta
durum: cozuldu
alan: ui/ayarlar
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PySide6 6.12
etiketler: [qt, wheel, spinbox, combobox, kullanilabilirlik]
kurallar: [R-12]
---

# Ayarlar fare tekerleğiyle farkında olmadan değişiyordu

## Belirti
Kullanıcı bildirdi: Ayarlar sayfasında aşağı kaydırırken, fare yalnızca
bir alanın üzerinden geçince değer değişiyordu; bazı ayarlar farkında
olmadan değişti ve doğru değerlerin ne olduğu bilinmiyordu.

## Kök neden
Doğrulandı: Qt'de `QSpinBox`, `QDoubleSpinBox`, `QComboBox` varsayılan olarak
odak olmadan da tekerlek olayını işler (`Qt.WheelFocus`). Uzun kaydırılan
sayfada bu çok kolay tetiklenir. Ayrıca varsayılana dönme yolu ve
varsayılan değer bilgisi yoktu.

## Çözüm
- `ui/wheel_guard.py`: uygulama geneli olay filtresi; odakta olmayan
  sayı/liste alanına gelen tekerlek olayı kaydırma alanına iletilir; odak
  politikası StrongFocus yapılır.
- Ayarlar: "Varsayılanlara döndür" düğmesi (API anahtarı, veri klasörü,
  son projeler korunur; değişen alanları listeleyip onay ister), her alanın
  yanında "varsayılan: …" bilgisi, sayfa açılınca değerlerin yeniden
  yüklenmesi, üstte "Kaydet".

## Kanıt
`tests/test_ui_pages.py::test_tekerlek_odaksiz_alani_degistirmez` ve
`test_tum_ekranlar_ve_eylemleri` (kaydet → değişen alanlar → varsayılana
döndür → form yenilendi); `tests/e2e_ui_real_api.py` "varsayılanlara döndür".

## Önleme
R-12.

## İlgili dosyalar
src/evren_studio/ui/wheel_guard.py, src/evren_studio/ui/settings_page.py
