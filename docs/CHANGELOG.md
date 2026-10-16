# Değişiklik Günlüğü

## 0.2.0 — 2026-10-16 (Aşama 2: Kod ajanı çalışma alanı)

### Eklendi

- Kod ajanı (`src/evren_studio/agent/`): proje klasörüyle sınırlı 8 araç
  (list_files, read_file, search_files, find_files, write_file, edit_file,
  run_command, update_todos), izin politikası (Plan / Onaylı / Otomatik
  düzenleme), ajan döngüsü (adım sınırı, iptal, bağlam kısaltma).
- API istemcisinde araç çağrısı: `tools` gönderimi, akışlı/akışsız
  `tool_calls` birleştirme; yerel araç reddedilirse metin protokolüne
  (`<arac_cagrisi>`) otomatik geçiş.
- Yeni arayüz: oturum listeli sol menü, karşılama ekranı, Markdown +
  sözdizimi renklendirmeli akış, düşünce bloğu, araç kartları, diff'li onay
  kutuları, sağ panel (Görevler, Değişiklikler + geri alma, Dosyalar,
  Terminal), mod/model seçicili yazma kutusu, koyu/açık tema, simgeler.
- Eğik çizgi komutları (/init, /ozet, /plan, /onayli, /otomatik, /model,
  /yeni, /disa-aktar, /yardim) ve `@dosya` ekleme; mesajı düzenleyip
  yeniden gönderme.
- Veritabanı şema v2: `sessions`, `session_messages`, `file_changes`;
  v1 sohbetleri otomatik olarak klasörsüz oturumlara kopyalanır (eski
  tablolar silinmez).
- Komutlar projedeki `.venv`'i otomatik kullanır (PATH başına eklenir).
- Yakalanmamış hatalar `%LOCALAPPDATA%\EVREN-Model-Studio\logs\crash.log`
  dosyasına yazılır ve Türkçe uyarı gösterilir.
- 51 yeni test (araçlar, izinler, metin protokolü, ajan döngüsü, istemci
  araç çağrısı, oturum veritabanı, arayüz uçtan uca onay akışı).

- Ortak geliştirici hafızası: `AGENTS.md` protokolü, motor giriş dosyaları
  (CLAUDE.md, GEMINI.md, Copilot, Cursor, Kilo, Roo, Cline, Windsurf),
  `docs/ai-memory/` (kurallar, kayıtlar, oturum günlükleri, motor profilleri),
  `tools/ai_memory.py`, git ön-commit kancası, `test_ai_memory.py` ve
  `test_source_hygiene.py`. Uygulama ajanı EVREN.md + AGENTS.md'yi birlikte okur.

- Sohbet ekranında çalışan model ve süre: yazma kutusunun üstünde canlı
  durum çubuğu (model · etkinlik · süre · adım), yanıt başlığında canlı sayaç,
  her yanıtın altında kalıcı "model · süre" ve çok adımlı turlarda tur
  toplamı; `auto` için yönlendirilen model (`auto → …`).
- `/` ile açılan tıklanabilir komut listesi (fare, ↑↓, Enter, Esc);
  `/model` seçilince tıklanabilir model listesi.
- Ayarlar: "Varsayılanlara döndür", her alanın yanında varsayılan değer,
  üstte Kaydet; sayfa açılınca değerler yeniden yüklenir.
- Uygulama geneli fare tekerleği koruması (odaksız alan değişmez).
- Gerçek API uçtan uca testleri: `tests/e2e_agent_real_api.py` (8 model,
  2 protokol), `tests/e2e_ui_real_api.py` (gerçek arayüz, 14 kontrol);
  arayüz QA paketi `tests/test_ui_pages.py` (tüm ekranlar, iş parçacığı
  uyarısı denetimi).

### Düzeltildi

- Durum İzleme sayfası arayüzü arka plan iş parçacığından güncelliyordu
  (çökme/donma riski); durdurma arayüzü 10 sn'ye kadar donduruyordu.
- Arka plan görevlerinin sonucu, görev nesnesi çöpe giderse kaybolabiliyordu.
- Ayarlar fare tekerleğiyle farkında olmadan değişiyordu.
- Esc, açık komut listesini kapatmıyordu; LLM'lerin boş satırsız yazdığı
  Markdown listeleri paragraf görünüyordu.
- 7 kaynak dosyada çift kodlanmış (mojibake) Türkçe metinler: arayüzde
  "YanÄ±t bekleniyorâ€¦" gibi görünüyordu (kodlama-ornegi).
- Ayarlar açılışta hiç okunmuyordu (`ConfigStore.load()` çağrılmıyordu).
- `secrets.py` `.gitignore` nedeniyle depoya hiç girmemişti (0.1.x düzeltmesi).
- Açılışta model listesi ana iş parçacığında çekilip arayüzü donduruyordu.

### Kaldırıldı

- Eski Chat, Code Studio ve Sohbetler sayfaları (yerini oturum çalışma
  alanı aldı).

## 0.1.0 — 2026-10-15 (Aşama 1 MVP)

### Eklendi

- EVREN LLM API istemcisi: healthz/readyz (kimliksiz), models, chat
  (akışlı/akışsız), quota, istek durumu sorgusu, şart durumu.
- Hata sınıflandırma ve kurtarma motoru: 10 hata sınıfı, Türkçe
  açıklamalar, Retry-After/artan bekleme (≤3 tekrar), belirsiz sonuçta
  durum sorgusu, imza tabanlı geçmiş çözüm araması.
- Kalıcı bilgi sistemi: ERROR_CATALOG, RECOVERY_PLAYBOOK,
  MODEL_CAPABILITIES, API_COMPATIBILITY, KNOWN_LIMITATIONS, LESSONS_LEARNED,
  EVREN_STATUS_HISTORY + PROJECT_STATE, TASK_CHECKLIST, DECISIONS.
- Windows Credential Manager ile API anahtarı yönetimi (maskeleme dahil).
- Türkçe PySide6 arayüzü: ana sayfa, chat (akış + iptal + geçmiş),
  code studio temeli (dosya ağacı/düzenleyici/kaydet), modeller,
  bağlantı testi, kota, sohbet geçmişi, hata merkezi, durum izleme,
  ayarlar, yardım/tanılama.
- EVREN Durum İzleme Ajanı: 30 dk toplam / 5 dk aralıklı kontrol,
  duyuru sayfası değişiklik tespiti, healthz/readyz/models kontrollerı,
  isteğe bağlı gerçek model testi, Türkçe rapor (kesin/tahmini ayrı),
  yarım kalan izlemeye devam.
- SQLite: sohbetler, mesajlar, hata kayıtları, izleme oturumları/kontrollerı,
  model sağlığı. İş parçacığı güvenli (RLock).
- 53 birim testi + UI duman testi + uçtan uca gerçek API testi (E2E_OK).
- run.bat başlatıcı; pyproject.toml ile kurulabilir paket.

### Doğrulanan gerçek dünya sonuçları (2026-10-15)

- 16 canlı model; glm-5.3 sohbet+akış 200 OK; auto → qwen3.8-flash-next;
  kota ok; istek durumu sorgusu success; 404/401 hata davranışları.
