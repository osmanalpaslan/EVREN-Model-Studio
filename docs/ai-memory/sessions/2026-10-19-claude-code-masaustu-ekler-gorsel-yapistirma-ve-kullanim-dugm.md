---
id: 2026-10-19-claude-code-masaustu-ekler-gorsel-yapistirma-ve-kullanim-dugm
tarih: 2026-10-19
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/ekler-ve-kullanim
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Ekler (görsel/dosya yapıştırma, sürükle-bırak) ve kullanım düğmesi

## Görev
Kullanıcı: (1) sohbete kopyalanan dosya/görsel yapıştırılabilsin; (2) sürüklenen
dosyalar adres yazmasın, Claude Code gibi görselleri/kartları görünsün, adres
arka planda tutulsun; (3) motor seçiminin yanında kalan kullanımı grafik ve
açıklamayla gösteren bir düğme.

## Yapılanlar
- Yeni: `ui/attachments.py`, `ui/usage_popup.py`, `api/images.py`.
- `ui/composer.py`: ek şeridi, yapıştır/bırak işleme, ataç her modda görünür,
  kullanım düğmesi (halka + kalan günlük %).
- `ui/session_view.py`: `add_files`, `add_image`, `send(text, attachments)`,
  görsel-motor denetimi, dosya blokları, ek meta'sı, geçmişte ek şeridi,
  düzenlemede ekleri geri getirme, `refresh_usage` (Task, R-04) — açılışta
  (app.py), her EVREN yanıtından sonra, panel açılınca ve 5 dk'da bir.
- `ui/transcript.py`: `UserMessageWidget(attachments=...)`, yalnız ek varsa balon gizli.
- `agent/runner.py`: `to_api_messages(..., images=True)`, `MAX_HISTORY_IMAGES=6`.
- `agent/compaction.py`: özet isteği `images=False`.
- İstemciler: EVREN `expand_chat_images`, OpenAI `responses_content`,
  Anthropic `anthropic_blocks`.
- `ui/app_context.py`: auto için ölçülen `vision: True` (yedek liste dahil).
- `ui/theme.py`: AttachmentChip / UsagePanel stilleri.

## Test sonuçları
- `pytest -q`: 296/296 (yeni `tests/test_attachments_usage.py` 12 test).
- Gerçek API görsel ölçümü ve gerçek uygulama uçtan uca: kayda bakın.
- R-13 gerçek testler: `e2e_agent_real_api.py auto deepseek-v4-flash` 4/4, `e2e_ui_real_api.py` 15/15, `e2e_real_api.py` E2E_OK.
- Ekran (R-05, koyu tema, QT_QPA_PLATFORM=windows): ek kartları, gönderilen
  mesajdaki ek şeridi, kullanım paneli. Açık tema görüntüsü ALINMADI.

## Sorunlar ve kayıtlar
- 2026-10-19-sohbete-dosya-ve-gorsel-yapistirilamiyordu-birakilan-dosya-y (çözüldü)
- Kendi hatalarım: ilk görsel ölçümünü offscreen'de çizilmiş görselle yaptım
  (harfler kutucuk → "yazı yok" sonuçları), windows modunda tekrarlandı;
  import yerleştirme betiği client.py'de satırı parantez içine koydu, test
  yakaladı; yedek model listesinde auto görsel bayrağı eksikti, test yakaladı.

## Sonraki motor için notlar
- Kullanım paneli ayrı açılır pencere: ekran görüntüsünde `w.grab()` yakalamaz,
  `usage_btn.panel.grab()` kullan.
- held_cr anlamı belgelerde yok; panel yalnız değeri gösterir.
- Bağlam göstergesi görsel token'larını saymaz (yaklaşık).
- Sohbet alanının tamamına (yazma kutusu dışına) bırakma desteklenmiyor;
  yazma kutusu ve çerçevesi kabul eder.
- OpenAI/Anthropic görsel biçimi belgelere göre; gerçek istekle doğrulanmadı.
- Dal: `feat/ekler-ve-kullanim` (birleştirilmedi).
