---
id: 2026-10-21-deepseek-v4-flash-evren-model-listesinden-kalkti
tarih: 2026-10-21
tur: risk            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: api
kaynak_motor: bilinmiyor
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PowerShell 5.1, Python 3.12.10
etiketler: [evren, model-listesi, auto-pro, router]
kurallar: [R-07]
---

# deepseek-v4-flash EVREN model listesinden kalktı

## Belirti
Hesap kapama oturumunda Proje görevleri qwen3.8-flash-next ve gemma-4-31b ile koştu; Auto Pro'nun ölçülmüş en iyi kod
modeli deepseek-v4-flash hiç kullanılmadı. `/v1/models` (2026-10-21, gerçek istek): gemma-4-31b, qwen3-vl-30b, auto,
mimo-v2.6-pro, qwen3.8-flash-next, deepseek-v4.1-flash, glm-5.3 (+ OCR/embedding/ses) — deepseek-v4-flash YOK.

## Kök neden
EVREN tarafında değişiklik (neden belgelenmemiş). Rota tablosu 2026-10-19 ölçümüne dayanıyordu; listede olmayan
model atlanınca kod zinciri qwen → gemma'ya kalıyordu. Derin denetçilerinin ikisi de aynı modele düşüyordu.

## Çözüm
`router.EVREN_ROUTES` sohbet/kod: deepseek-v4.1-flash (12/12 ölçülmüş) ikinci yedek olarak eklendi; v4-flash geri
gelirse yine birincil. Derin denetçileri farklı model seçer (`_verifier_models`).

## Kanıt
Gerçek `/v1/models` çıktısı (oturum günlüğü); `tests/test_router.py`, `tests/test_auto_pro.py` geçiyor.

## Önleme
Rota tablosu değişince zorluk paketiyle yeniden ölç (R-21); model listesi değişimi Modeller sayfasında izlenmeli.

## İlgili dosyalar
- src/evren_studio/agent/router.py
