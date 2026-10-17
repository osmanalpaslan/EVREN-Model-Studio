---
id: 2026-10-17-claude-code-masaustu-claude-code-masaustu-dongu-analizi-ve-do
tarih: 2026-10-17
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/dongu-onleme
sonuc: kismi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Claude Code masaüstü: döngü analizi ve döngü bekçisi

## Görev
Kullanıcı: "LLM bazı süreçlerde tekrara düşüyor, aynı işlemleri yapıp duruyor;
test et, nedenini bul, çözüm önerelim." Ardından önerilen tüm düzeltmeler onaylandı.
Ayrıca: "Otomatik modda hiçbir şey için onay istemesin" (kesin karar) ve
"API anahtarım GitHub'da olmamalı".

## Yapılanlar
- Gerçek API döngü ölçümü: 8 model × 4 görev, 55 koşu + DepoWise oturumunun
  gerçek kullanım bulgusu → docs/knowledge/LOOP_ANALYSIS.md.
- `agent/runner.py`: döngü bekçisi (tekrar / ileri-geri düzenleme → uyarı, sonra
  `loop` ile durma), boş yanıt ve "söz verip durma" için tek seferlik geçici
  hatırlatma, boş yanıtta destekleyen modelde `reasoning_effort: "none"`.
- Ek: glm-5.3'ün tek yanıtta 39 (uydurma) çağrısı üzerine, döngü algılanınca kalan
  çağrılar atlanır ve tek yanıtta en fazla 12 çağrı çalışır.
- `api/client.py`: `chat(extra_body=...)`; OpenAI/Anthropic istemcileri yok sayar.
- `ui/session_view.py`: `stall_retry_body` model yeteneğine göre verilir.
- `agent/prompts.py`: tekrar etmeme, 2 başarısızlıktan sonra yol değiştirme,
  test dosyasını değiştirmeme/kandırmama, yapmadığını yaptım dememe kuralları;
  özet sonrası "yeniden oku" yönlendirmesi daraltıldı.
- `agent/tools.py`: EVREN.md varsa proje hafızası yalnız EVREN.md; depoya kısa
  EVREN.md eklendi.
- API anahtarı: depoda ve tüm git geçmişinde gerçek anahtar ARANDI, BULUNMADI
  (uygulama anahtarı Credential Manager'dan okur). Koruma: tools/secret_scan.py
  + ön-commit kancası + tests/test_source_hygiene.py::test_depoda_api_anahtari_yok.
- R-19 eklendi; MODEL_CAPABILITIES.md'ye düşünme ayarı ve model davranışı notları.

## Test sonuçları
- `pytest -q`: 236 geçti (yeni test_loop_guard.py dahil); hijyen testleri 4/4.
- `tests/e2e_real_api.py`: E2E_OK. `tests/e2e_agent_real_api.py auto deepseek-v4-flash
  qwen3.8-flash-next glm-5.3`: 8/8.
- Düzeltme sonrası `takil` (çelişkili test) gerçek ölçüm, 4 model × 3 koşu: hiçbir
  koşuda test dosyası değişmiş kalmadı (öncesi 3 koşu), hile kodu yok; auto'nun
  ileri-geri test düzenlemesi `loop` ile durduruldu.
- `tests/e2e_ui_real_api.py deepseek-v4-flash`: 14/15. KALAN: "Otomatik mod: güvenli
  komut onaysız çalıştı" — model zincirli komut seçti (`Get-ChildItem -Name; "Toplam…"`),
  güvenli listede olmadığı için onay istendi. Bu dalın değişikliğiyle ilgisiz (model
  komut seçimi değişken); kullanıcının "Otomatik modda hiç onay yok" kararı
  uygulanınca bu kontrol de geçer. Arayüz değişmediği için ekran görüntüsü
  incelemesi (R-05) gerekmedi; ui/session_view.py'de yalnız runner parametresi eklendi.

## Sorunlar ve kayıtlar
- 2026-10-17-ajan-tekrar-ve-ileri-geri-duzenlemede-durmuyordu (çözüldü)
- 2026-10-17-bos-yanit-ve-soz-verip-durma-sessizce-bitti-sayiliyordu (çözüldü)
- 2026-10-17-agir-agents-md-evren-ajanini-asil-isten-uzaklastiriyordu (çözüldü)
- 2026-10-17-deepseek-v4-1-flash-metin-protokolunde-akista-arac-cagrisi-k (izleniyor, sunucu)
- 2026-10-17-zayif-modeller-takilinca-test-dosyasini-degistirip-yalan-rap (izleniyor)

## Sonraki motor için notlar
- **Otomatik modda hiç onay istememe** (kullanıcının kesin kararı) bu oturumda
  UYGULANAMADI: Claude Code'un kendi güvenlik sınıflandırıcısı permissions.py
  değişikliğini engelledi; kullanıcıya bildirildi. Karar kullanıcıda; uygulanırsa
  `decide()` içinde mode=="auto" için READ/WRITE/EXEC → ALLOW, MODE_HINTS,
  prompts.py'deki Otomatik mod satırı, session_view.py:702 notu, README/SECURITY
  ve test_auto_mode.py beklentileri birlikte güncellenmeli (R-14'e dikkat).
- Sıradaki iş (kullanıcı onaylı): "proje maratonu" — arayüzle uzun gerçek
  projeler (A: Python CLI+SQLite, B: küçük web, C: kurulu olmayan araç) ve
  "ortam denetimi" (eksik programı winget + bilinen listeyle ONAYSIZ kurma).
- Uzun oturumda (özet + kısaltma) döngü henüz ölçülmedi.
