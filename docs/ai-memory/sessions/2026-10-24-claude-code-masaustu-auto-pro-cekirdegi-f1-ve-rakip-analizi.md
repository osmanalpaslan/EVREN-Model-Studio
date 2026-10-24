---
id: 2026-10-24-claude-code-masaustu-auto-pro-cekirdegi-f1-ve-rakip-analizi
tarih: 2026-10-24
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/autopro-cekirdek
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Auto Pro çekirdeği F1 ve rakip analizi

## Görev
2026-10-23: kullanıcının iki isteği (oyun MCP'leri, skill menüsü) ve 16 uygulama fikri kaydedildi; benzer
uygulamalar ve açık kaynak repolarla eksik analizi + Auto Pro analizi yapıldı. Kullanıcı A1–A13 ve E1–E10'u onayladı
(A14, E11 hariç; sonra E7 iptal), A3 için karar #47'yi #88 ile güncelledi, "çalışmaya başlayabiliriz" dedi;
"hazırlık, planlama, yapım ve test kusursuz olsun". Bu oturum F1'i (Auto Pro çekirdeği) yaptı.

## Yapılanlar
- Belgeler: `docs/ILERIDE_YAPILACAKLAR.md` madde 7 (7.1–7.5: istekler, 16 fikir, onaylı A/E maddeleri ve
  planları, faz planı F1–F7), `docs/knowledge/RAKIP_VE_AUTOPRO_ANALIZI.md`, DECISIONS #88–#89.
- A1: `model_calls` tablosu, `agent/modelstats.py`, `AppContext.record_model_call/model_baselines`,
  koşucuda `stats_sink` (her çağrı + yedeğe geçiş).
- A2: `EvrenClient(stream_idle_timeout)`, `ChatResult.first_chunk_s`, ayar `stream_idle_timeout_seconds` (60,
  Ayarlar sayfasında); akış kopması (UNKNOWN_RESULT) artık yedeğe geçirir.
- A3: `SlowDetector` (art arda 2 yavaş adım, görev başına 1 değişim, güvenli nokta = döngü başı, Proje/Derin
  görevinde 1/3 eşik). A4: yedeğe geçişte `model_health` sağlıksız → 30 dk sona.
- A9: `known_model_ids` + `on_model_list_change` → not. A12: çalışma çubuğu ipucu + Modeller sayfası tablosu.
- Değişim notu "EVREN Akıllı" yerine "Auto Pro" diyor.

## Test sonuçları
- `tests/test_autopro_cekirdek.py` 10 test (tetiklenen/tetiklenmeyen: normal hız, ölçüm yok, görev içi eşik,
  kota hatası); tam pytest 517.
- Gerçek API: akış gecikmesi (ilk parça ≤ 2,7 sn, sessizlik ≤ 0,7 sn); zorluk paketi 12/12, 477 sn, yavaşlık
  geçişi 0, 57 çağrı kaydı, en uzun ilk parça 10,1 sn; R-13: E2E_OK, ajan 6/6, arayüz 15/15.
- Ekran görüntüsü (koyu + açık): Modeller "son 24 saat" tablosu, Ayarlar "Yanıt vermeme süresi" — bakıldı.

## Sorunlar ve kayıtlar
- 2026-10-24-akis-koptugunda-veya-model-sustugunda-yedege-gecilmiyor-tur
- 2026-10-24-auto-pro-saglik-kurali-gercek-kullanimda-hic-beslenmiyordu
- 2026-10-24-sqlite-datetime-ile-iso-zaman-damgasi-metin-olarak-karsilast

## Sonraki motor için notlar
- Sıradaki: F2 (A6 zorluk, A7 iş türü rolleri + ölçüm paketleri, A10 seed, A11 kota, A5 kalite puanı, A8 yoklama,
  A13/E3). `model_calls` artık veri topluyor; A5/A6 bu tabloyu kullanmalı.
- Yavaşlık kuralının GERÇEK tetiklenmesi henüz gözlenmedi (yalnız birim testte); motor gerçekten yavaşladığı bir
  günde notları kontrol et.
- Zorluk paketi bugün 477 sn: hata değil, EVREN o gün yavaş (deepseek ~51 token/sn).
