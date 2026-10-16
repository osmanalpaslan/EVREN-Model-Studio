---
id: 2026-10-15-acilista-senkron-model-yukleme-arayuzu-donduruyordu
tarih: 2026-10-15
tur: hata
onem: orta
durum: cozuldu
alan: ui/is-parcacigi
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PySide6 6.12
etiketler: [qt, ag, donma]
kurallar: [R-04]
---

# Açılışta senkron model yükleme arayüzü donduruyordu

## Belirti
Anahtar tanımlıyken uygulama açılışında pencere, model listesi isteği
bitene (veya zaman aşımına düşene, varsayılan 120 sn) kadar yanıt vermiyordu.

## Kök neden
Doğrulandı (kod incelemesi): `MainWindow._build_pages` içinde
`client.list_models()` ana iş parçacığında çağrılıyordu. Ağ yavaşsa veya
EVREN erişilemezse arayüz kilitlenir. Gerçek ağ ile ölçüm yapılmadı.

## Çözüm
Senkron çağrı kaldırıldı; model listesi `ModelsPage.refresh_models` içinde
`Task` ile arka planda alınıyor ve `AppContext.set_models` dinleyicileriyle
oturum görünümüne iletiliyor. Liste gelene kadar belgelenmiş yedek model
listesi (`FALLBACK_MODELS`) kullanılıyor. Commit `c8e17d2`.

## Kanıt
Kod incelemesi; `SMOKE_OK`. Yavaş ağ koşulunda ölçüm yapılmadı.

## Önleme
R-04.

## İlgili dosyalar
src/evren_studio/ui/main_window.py, src/evren_studio/ui/app_context.py, src/evren_studio/ui/models_page.py
