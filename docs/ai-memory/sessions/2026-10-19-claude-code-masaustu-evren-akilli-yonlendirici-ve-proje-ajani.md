---
id: 2026-10-19-claude-code-masaustu-evren-akilli-yonlendirici-ve-proje-ajani
tarih: 2026-10-19
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/akilli-yonlendirme
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# EVREN Akıllı yönlendirici ve Proje ajanı

## Görev
Kullanıcı: ana odak EVREN; auto yönlendirmesi pek iyi değil; büyük projede birden
çok motor gerekebilir, kullanıcı her an başında değil. Önce plan, sonra uygulama.
Kararlar (AskUserQuestion): EVREN Akıllı ekle; Proje ajanı; plan onayı zorunlu;
Windows bildirimi + rapor. Çalışma sırasında kullanıcı EVREN uygulamasının kendi
ajanıyla bu depoda bir hata düzeltmeye çalışmış ve uygulama açılmaz olmuş
("mevcut geliştirmeyi tamamladıktan sonra hataları bul ve düzelt").

## Yapılanlar
- Ölçüm: zorluk paketine planlama + mini_proje; 8 EVREN motoru × 12 görev;
  EVREN Akıllı 12/12; proje ajanı gerçek API e2e kabul 5/5.
- `agent/router.py` (rol tablosu, sağlık, yedek), `agent/runner.py`
  (fallback_models, `_switch_model`; görsel reddi protokol değişiminden önce).
- `agent/project.py` (plan biçimi/ayrıştırma, görev istemi, inceleme, Git, ProjectRunner,
  rapor, uyku engelleme), `ui/project_ui.py` (komutlar, PlanCard, yürütme köprüsü,
  kota kararı), `db.py` (project_runs), `ui/session_view.py` (start_run
  history_from/mode/model, tur kancası, proje sürerken mesaj engeli, yarım proje notu),
  `ui/main_window.py` (sistem tepsisi bildirimi), `ui/app_context.py` (AKILLI_INFO),
  `ui/composer.py` (komutlar, "EVREN Akıllı" etiketi).
- `scope.wants_creation`: oluşturma isteğinde "dosya yok" uyarısı verilmez (gerileme).
- `Git.dirty` ajanın kendi plan/rapor dosyalarını saymaz (yanlış uyarı).
- Kullanıcının uygulama ajanı değişiklikleri (sidebar.py, main_window.py) ayrıldı
  ve `build/evren_ajan_degisiklikleri/` altına yedeklendi; bu dala girmedi (ayrı iş).
- Belgeler: CHALLENGE_RESULTS, ILERIDE_YAPILACAKLAR #3, CHANGELOG, README, DECISIONS
  #46–50, KNOWN_LIMITATIONS, PROJECT_STATE, AGENTS.md test satırı, R-22.

## Test sonuçları
- `pytest -q`: aşağıdaki son tam çalıştırma (commit öncesi) — sonuç commit mesajında.
- Yeni testler: test_router (10), test_project_agent (10), test_project_ui (3),
  test_zorluk_duzeltmeleri (+1).
- Gerçek API: 8 motor ölçümü; EVREN Akıllı 12/12; e2e_proje kabul 5/5; R-13 betikleri
  sonucu commit mesajında.
- Ekran (R-05, windows modu, sahte model): plan kartı, çalışma çubuğu, bitiş.

## Sorunlar ve kayıtlar
- 2026-10-19-olmayan-dosya-uyarisi-olusturma-isteklerinde-yanlis-alarm-ve (kendi gerilemem)
- 2026-10-19-sunucu-tarafi-auto-yonlendirmesi-ongorulemez-gorunmez
- Kendi hatalarım (testler yakaladı): diff için `git add -N` stash'i bozdu;
  bekleme döngüsü gerçek saate bağlıydı (test 180 sn); f-string'e kaçış hatasıyla
  satır sonu girdi; regex'e `\b` yerine geri silme karakteri yazıldı (yamaları
  bash heredoc'ta Python dizesi içinde yazmak kaçışları bozuyor → küçük düzeltmeleri
  Edit aracıyla yap); ölçüm betiğinde göreli yol ve cp1254 çıktı.
- Ortam: arka planda 4+ Qt süreci varken git alt süreçleri "Permission denied /
  cannot spawn sh.exe" verdi; ölçüm bitince aynı testler geçti (R-08).

## Sonraki motor için notlar
- Kullanıcının EVREN uygulamasıyla yaptığı değişiklik: `build/evren_ajan_degisiklikleri/`.
  main_window'daki `_debug_log` `time.strftime('%f')` Windows'ta ValueError →
  uygulama açılmıyordu. Ajan kenar çubuğu/panel görünürlük (splitter) sorununu
  çözmeye çalışıyordu; sidebar'a "Developed by Osman Alpaslan" eklemişti. Bu dalda
  YOK; ayrı işte ele alınır.
- Varsayılan motor hâlâ auto (kullanıcı ayarı glm-5.3); EVREN Akıllı'yı varsayılan
  yapmak kullanıcı onayı ister.
- Dal: `feat/akilli-yonlendirme` (birleştirilmedi).
