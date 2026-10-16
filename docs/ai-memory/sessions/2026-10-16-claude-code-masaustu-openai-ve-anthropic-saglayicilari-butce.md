---
id: 2026-10-16-claude-code-masaustu-openai-ve-anthropic-saglayicilari-butce
tarih: 2026-10-16
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/saglayicilar
sonuc: kismi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# OpenAI ve Anthropic sağlayıcıları, aylık bütçe

## Görev
Kullanıcı: "OpenAI/Anthropic entegrasyon planına başla. Bütçe varsayılanı toplam
$5/ay olsun." Önceki kararlar: tam entegrasyon (OpenAI Responses, Anthropic
Messages; sohbet + ajan), yalnız gruplu model seçicide yardım (anahtar rehberi
Ayarlar'da), aylık sınırda dur (%80 uyarı, sınırda onay), anahtar yok → sahte
testler, kullanıcı sonra doğrular. (Oturum bir kez bağlam özetiyle devam etti.)

## Yapılanlar
- api/errors.py, recovery.py: `QUOTA_EXHAUSTED` ("kredi bitti"), 402 ve 529 eşlemesi.
- secrets.py: sağlayıcı başına anahtar (`evren/openai/anthropic`), `sk-…`/`sk-ant-…`
  ve `x-api-key` maskeleme.
- api/providers.py (yeni): sağlayıcı kaydı (adımlar, bağlantılar, notlar,
  `verified=False`), tarihli model/fiyat kataloğu, `estimate_cost`, `price_hint`.
- api/openai_client.py, api/anthropic_client.py (yeni): `EvrenClient` alt
  sınıfları; mesaj/araç dönüşümü, akış ayrıştırma, hata eşleme, model listesi.
- api/client.py: `ChatResult.provider_state`, `token_usage()`, `normalize_usage`,
  `strip_internal` (EVREN'e `_` alanları gitmez), `ModelInfo.provider`.
- agent/runner.py: `_provider_state` taşıma, meta'da usage/provider_state,
  `before_model_call` (bütçe durdurması "budget").
- db.py: şema v3 (`usage_costs`, `sessions.provider`), `add_usage_cost`, `month_spend`.
- budget.py (yeni), config.py (`monthly_budget_usd=5.0`, `budget_enforce=True`).
- ui/app_context.py: ücretli modeller, `provider_of`, `provider_key`, `make_client_for`.
- ui/session_view.py: anahtar kapısı, bütçe onayı (gönderim + ajan adımı),
  maliyet kaydı ve %80 uyarısı, sağlayıcı adı çalışma çubuğunda, kredi bitti
  kartında panel düğmesi, özet/sorgu doğru sağlayıcıyla.
- ui/composer.py: gruplu seçici (başlıklar seçilemez, ok tuşları başlıkları
  atlar, "(anahtar gerekli)"), alt notta verinin gittiği sağlayıcı.
- ui/settings_page.py: "Ücretli Sağlayıcılar" kartı (rehber, bağlantılar,
  kaydet/sil/doğrula, bütçe, bu ayki tahmini harcama).
- Belgeler: CHANGELOG, PROJECT_STATE, DECISIONS #33–36, SECURITY,
  KNOWN_LIMITATIONS, PROVIDERS_RESEARCH §5, README. Kural R-17.

## Test sonuçları
- `pytest -q`: 202/202 geçti (yeni `tests/test_providers.py` 28 test).
- R-13 gerçek EVREN: `e2e_real_api.py` E2E_OK (zaman aşımı 180 sn'ye
  çıkarıldıktan sonra; bkz. kayıt), `e2e_agent_real_api.py` 6/6,
  `e2e_ui_real_api.py` 15/15.
- `e2e_providers_real_api.py`: anahtar yok → iki sağlayıcı da ATLANDI.
  OpenAI/Anthropic gerçek istekle DOĞRULANMADI.
- Ekran görüntüsü (R-05, QT_QPA_PLATFORM=windows, koyu tema): Ayarlar
  sağlayıcı kartı, bütçe bölümü, gruplu model seçici incelendi. Açık tema
  görüntüsü alınmadı.

## Sorunlar ve kayıtlar
- 2026-10-16-openai-ve-anthropic-entegrasyonu-gercek-anahtarla-dogrulanma (risk, izleniyor)
- 2026-10-16-dosya-yazimindan-hemen-sonra-gecici-errno-22-kilidi (ortam, Comodo)
- 2026-10-16-e2e-real-api-60-sn-zaman-asimi-glm-5-3-icin-dar (çözüldü)
- Kendi hatam: ekran görüntüsü betiğinde `comp.popup.PositionAtTop` PySide6'da
  yoktu, zamanlayıcı içindeki istisna betiği askıda bıraktı →
  `QAbstractItemView.ScrollHint.PositionAtTop` + güvenlik `app.quit` zamanlayıcısı.

## Sonraki motor için notlar
- Değişiklikler `feat/saglayicilar` dalında; push/PR kullanıcı onayı bekliyor (R-15).
- Anahtarı olan biri `tests/e2e_providers_real_api.py --evet` çalıştırmalı;
  geçerse `verified=True` ve MODEL_CAPABILITIES.md'ye işle (R-07, R-17).
- Model kimlikleri ve fiyatlar 2026-10-16 araştırmasından; kullanmadan önce
  kaynak sayfadan doğrula.
- Bütçe onayı `_budget_override` ile oturum görünümü başına, UTC ayı için tutulur.
- Model listesi ve Ayarlar'daki varsayılan model listesi ücretli modelleri de
  içerir; anahtarsız ücretli model varsayılan seçilirse gönderimde anahtar uyarısı çıkar.
