# Değişiklik Günlüğü

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
