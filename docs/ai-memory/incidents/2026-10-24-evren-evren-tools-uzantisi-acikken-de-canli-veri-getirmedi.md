---
id: 2026-10-24-evren-evren-tools-uzantisi-acikken-de-canli-veri-getirmedi
tarih: 2026-10-24
tur: yanlis-iddia            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: api
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, gerçek EVREN API
etiketler: [evren_tools, E8, web]
kurallar: [R-07]
---

# EVREN evren_tools uzantısı açıkken de canlı veri getirmedi

## Belirti
API_COMPATIBILITY.md `evren_tools` uzantısını listeliyordu; rakip analizinde E8 (web araması) için "EVREN'in kendi aracı
olabilir" diye not düşülmüştü. Gerçek ölçüm (`tests/e2e_evren_tools_real_api.py`, 2026-10-24; qwen3.8-flash-next ve
deepseek-v4.1-flash; saat/tarih, USD/TRY kuru, python.org başlığı): `evren_tools: true` ile de modeller "canlı
veriye erişimim yok" dedi; yanıtta araç izi yok. qwen kapalıyken bile metin olarak `get_datetime` çağrısı yazdı
(sunucu araçlarının adı modele tanıdık, ama çalıştırılmadı).

## Kök neden
Doğrulanmadı. OpenAPI şeması (GET /openapi.json): "opt-in to server-executed live-data tools when `tools` is not
supplied" — kendi `tools` listemizle birlikte kullanılamaz; tek başına da bugün etkisiz.

## Çözüm
E8 ücretsiz yolla yapıldı: kendi `web_fetch` aracımız (verilen adresi okur, arama yapmaz; agent/webfetch.py).
`evren_tools` kullanılmıyor; ölçüm betiği EVREN uzantıyı etkinleştirirse yeniden denemek için kaldı.

## Kanıt
tests/e2e_evren_tools_real_api.py çıktısı (12 istek, 2026-10-24) — oturum günlüğünde özet.

## Önleme
R-07. API_COMPATIBILITY.md satırı güncellendi.

## İlgili dosyalar
- docs/knowledge/API_COMPATIBILITY.md
- src/evren_studio/agent/webfetch.py
