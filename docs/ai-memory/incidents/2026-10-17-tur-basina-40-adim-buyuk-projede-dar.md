---
id: 2026-10-17-tur-basina-40-adim-buyuk-projede-dar
tarih: 2026-10-17
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [adim-siniri, ayarlar]
kurallar: [R-14]
---

# Tur başına 40 adım büyük projede dar

## Belirti
Maraton C projesi (Node + TS + pnpm kurulumu) ilk mesajı qwen3.8-flash-next ile
tam 40 adımda bitti; deepseek 39, auto 30–33 adım kullandı.

## Kök neden
Varsayılan `agent_max_steps = 40`; döngü bekçisi gelmeden önce tek koruma buydu.

## Çözüm
Varsayılan 80 (runner ve config). Ayar sürümü 3: kayıtlı değer eski varsayılan
(40) ise 80'e taşınır; kullanıcının seçtiği başka değer korunur.

## Kanıt
tests/test_default_auto.py::test_adim_siniri_tasima (4 durum), test_ui_pages.

## Önleme
Kontrolden çıkan turu döngü bekçisi durdurur (R-19); adım sınırı yalnız son
güvenlik ağıdır.

## İlgili dosyalar
- src/evren_studio/config.py
- src/evren_studio/agent/runner.py
