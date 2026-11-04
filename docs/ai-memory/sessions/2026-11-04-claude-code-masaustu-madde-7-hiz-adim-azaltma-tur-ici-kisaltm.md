---
id: 2026-11-04-claude-code-masaustu-madde-7-hiz-adim-azaltma-tur-ici-kisaltm
tarih: 2026-11-04
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/hiz-adim-azaltma
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 7 hız: adım azaltma, tur içi kısaltma, boş yanıt ve damla akışta yedek

## Görev
Kullanıcı: "sıradaki maddeden devam et; hız maddesinde önceliğim ajanların tutarlı ve doğru çalışması (kaliteli iş),
aynı zamanda çalışma hızı da artsın; analizi kapsamlı yap". Sonra: "onay istemeden önerilerinle devam et, bilgisayar
başında olmayacağım; sıradaki maddelere de aynı şekilde devam edebilirsin".

## Yapılanlar
- Analiz (gerçek DB'ler: kullanıcının `evren.db` + zorluk/maraton DB'leri): süre ≈ model beklemesi; adımların %82'si tek
  araç çağrılı; değişmemiş dosyayı tekrar okuma ~0 (o kaldıraç boş); kod rolünde deepseek-v4.1-flash ort. 89 sn/çağrı,
  qwen 15 sn. Gerçek akış ölçümü: deepseek araçla dosya yazarken 182/396 sn akışta neredeyse veri yok.
- `prompts.AGENT_RULES`: bağımsız okuma/inceleme tek yanıtta birden çok araçla; bağımlı iş ayrı yanıtta.
- `runner.trim_for_context(budget=)` + `_trim_budget`/`_visible`/`TRIM_OF_HARD=0.7`: tur içi kısaltma sert sınırın
  %70'inde; sert sınır kısaltılmış geçmişe bakar; kısaltmadan sonra döngü bekçisinin tekrar sayacı sıfır.
- `_switch_model(empty_reason=)`: dürtmeden sonra da boş yanıt → yedek (tur başına bir kez, SLOW_SWITCH_EXCLUDE).
- Damla akış: `_StepCancel` her akış satırında görünür karakter + satır hızını ölçer; ≥120 sn ve <15 kar/sn ve <10
  satır/sn → çağrı kesilir (`finish_reason="slow_drip"`), yarım yanıt kaydedilmez, yedek aynı adımı yapar
  (`_slow_switch_possible`: görev başına bir kez, zayıf modele değil, yalnız akışlı). DECISIONS #121/#122.
- Kayıtlar: gözlem a0d2b1645e16 → `2026-11-04-tur-baglam-sinirinda-durdu` (çözüldü); gözlem 3854d7522898 /
  6d629fb7f224 → mevcut `2026-10-17-deepseek-v4-1-flash-metin-...` kaydına not (sunucu/model; açık kalır).
- ENGINES.md (deepseek akış davranışı), CHALLENGE_RESULTS.md, CHANGELOG.md, DEVIR_NOTU.md.

## Test sonuçları
- `tests/test_hiz_adim.py` 21 test (tetiklenen/tetiklenmeyen her davranış); mutasyon 6/6 (kısaltma, boş yanıt) +
  7/7 (damla akış). Risk paketi (17 dosya) 204/204.
- Gerçek: `e2e_agent_real_api.py deepseek-v4.1-flash glm-5.3` ×3 (tekrar üretim; düşüşler EVREN/metin protokolü).
- Zorluk auto-pro: ÖNCE 11/12 · 851 sn · 49 çağrı; SONRA-1 11/12 · 1300 sn · 42 çağrı; SON 12/12 · 1027 sn · 61 çağrı,
  damla kuralı 1 kez (celiski, deepseek → qwen, 3/3). Ayrıntı CHALLENGE_RESULTS "Madde 7 hız".
- Maraton F (`MARATON_OZET_ESIK=8000`): 17/17 · 1051 sn · özet 1 (dün aynı ayarla 3, 1228 sn) · tur 26 adım kesintisiz.
- R-13: arayüz 15/15 · ajan 4/6 (glm 503 kapasite + bilinen deepseek metin boş yanıtı) · e2e_real_api `auto` akışında
  503 (sunucu; `api/` değişmedi). İngilizce ara cümle: 3 zorluk koşusunun 77 yanıtında 0.

## Sorunlar ve kayıtlar
- 2026-11-04-tur-baglam-sinirinda-durdu (çözüldü).
- 2026-10-17-deepseek-v4-1-flash-metin-protokolunde-akista-arac-cagrisi-k (not eklendi, açık).
- Ağ: bir kez `Could not resolve host: github.com` (anlık; tekrar denemede gönderildi).

## Sonraki motor için notlar
- Damla akış eşikleri (`DRIP_*`) tek akşamın ölçümüne dayanır; EVREN akış biçimi değişirse (ör. deepseek düşünmeyi
  akıtmaya başlarsa) `akis_olcum` benzeri ölçümü tekrarla. Kural deepseek'in 2 dk'yı aşan her çağrısında tetiklenir
  (görev başına bir kez) — bu bilinçli: kullanıcının yavaşlık kuralının (#88) çağrı içi hâli.
- İstemin adım azaltma etkisi kısa görevlerde küçük ölçüldü; uzun maratonda ayrıca bakılmalı.
- Süre karşılaştırmaları tek koşu ve EVREN yükü saatten saate değişiyor; ölçüt adım/çağrı + kabul.
