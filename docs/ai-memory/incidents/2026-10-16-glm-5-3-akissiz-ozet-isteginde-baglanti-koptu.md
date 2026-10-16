---
id: 2026-10-16-glm-5-3-akissiz-ozet-isteginde-baglanti-koptu
tarih: 2026-10-16
tur: hata
onem: orta
durum: cozuldu
alan: api/ozet
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, gerçek EVREN API, glm-5.3
etiketler: [stream, reasoning, timeout, compact]
kurallar: [R-16]
---

# glm-5.3 akışsız özet isteğinde bağlantı koptu

## Belirti
`tests/e2e_compact_real_api.py` ilk çalıştırmada glm-5.3 için:
`ApiError: Sonuç belirsiz: yanıt gelirken bağlantı kesildi`. deepseek-v4-flash
aynı istekte başarılıydı.

## Kök neden
Tahmin (yüksek olasılık): özet `stream=False` ile isteniyordu. glm-5.3 muhakeme
modelidir ve uzun süre düşünür (akışlı istekte bile 153 sn sürdü); akışsız
istekte bu süre boyunca bağlantıdan veri geçmediği için ara katman/sunucu
bağlantıyı kapatıyor. Kesin zaman aşımı değeri doğrulanmadı.

## Çözüm
`compaction.summarize` akışlı (`stream=True`) istiyor; parçalar bağlantıyı canlı
tutuyor ve iptal her parçada denetleniyor. Ayrıca özet için hızlı bir model
ayarı eklendi (varsayılan deepseek-v4-flash: 41 sn, glm-5.3: 153 sn).

## Kanıt
Düzeltme sonrası `e2e_compact_real_api.py`: deepseek-v4-flash, glm-5.3,
qwen3.8-flash-next → 3/3 geçti.

## Önleme
R-16.

## İlgili dosyalar
src/evren_studio/agent/compaction.py, src/evren_studio/config.py
