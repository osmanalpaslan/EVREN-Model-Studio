---
id: 2026-10-16-claude-code-masaustu-varsayilan-motor-auto-son-secim-hatirlan
tarih: 2026-10-16
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/varsayilan-auto
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Varsayılan motor auto; son seçilen motor ve mod hatırlanır

## Görev
Kullanıcı: "Chat ekranında varsayılan olarak auto seçili gelsin; isteyen motoru
değiştirebilsin." Ara soru: yalnızca LLM (motor) mu? → Evet; onay modu
varsayılanı Manuel kaldı. "Her ayar ve değişiklik ben değiştirene kadar
korunsun." Kullanıcı kararları (AskUserQuestion): son seçilen motor + onay
modu yeni oturumlarda hatırlansın; mevcut kurulumlardaki eski varsayılan
glm-5.3 bir kez auto'ya çevrilsin.

## Yapılanlar
- config.py: `default_model="auto"`, `settings_version=2`, `migrate_raw()`
  (yalnızca sürüm<2 VE değer eski varsayılan glm-5.3 ise; bir kez).
  Liste/bozuk JSON güvenli.
- ui/app_context.py: `MEASURED_OVERRIDES` (auto 262k + yerel araç; kayıt
  32768/tools:false yanlış, kayda bakın).
- ui/session_view.py: `_remember()` — model seçici, /model, mod seçici ve mod
  komutları ayarlara yazar; anahtarsız ücretli model reddedilince yazılmaz.
  auto listenin en üstünde, açıklaması "önerilen · görevine göre modeli seçer".
- ui/settings_page.py: auto yedek listede ilk; hatırlama açıklaması.
- tests/test_default_auto.py (11 test). MODEL_CAPABILITIES, CHANGELOG,
  DECISIONS #37–38, PROJECT_STATE.

## Test sonuçları
- `pytest -q`: 223/223.
- Gerçek API (R-13): `e2e_agent_real_api.py auto` 2/2; `e2e_ui_real_api.py auto`
  15/15; `e2e_real_api.py` E2E_OK.
- Ekran (R-05, koyu): yeni oturum auto seçili, seçicide auto en üstte "önerilen".
- Gerçek ayar dosyasının testlerden etkilenmediği doğrulandı (değişiklik zamanı).

## Sorunlar ve kayıtlar
- 2026-10-16-auto-kaydi-32768-baglam-ve-tools-false-diyor-olcum-celisiyor (çözüldü)
- Kendi test hatalarım: `SessionView.set_model` doğrudan çağrısı seçiciyi
  güncellemiyor (sinyal işleyicisi) → testte `composer.set_model(..., emit=True)`;
  oturumsuz `/model` notu QMessageBox açıp testi askıda bıraktı → testte taklit.

## Sonraki motor için notlar
- Hatırlama kasıtlı: seçici/komut değişikliği `settings.default_model` ve
  `agent_mode`'u kalıcı yazar. Ayarlar sayfası açılınca güncel değeri yükler.
- Otomatik mod seçilirse yeni oturumlar da Otomatik açılır (kullanıcı kararı).
- auto'nun 108k istekte boş yanıtı doğrulanmadı; büyük bağlamda sorun görülürse
  `MEASURED_OVERRIDES` bağlamını düşür.
- Dal: `feat/varsayilan-auto` (birleştirilmedi).
