---
id: 2026-10-16-izleme-sayfasi-arayuzu-arka-plan-is-parcacigindan-guncelliyordu
tarih: 2026-10-16
tur: hata
onem: yuksek
durum: cozuldu
alan: ui/is-parcacigi
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PySide6 6.12
etiketler: [qt, thread, monitor, cokme]
kurallar: [R-11]
---

# Durum İzleme sayfası arayüzü arka plan iş parçacığından güncelliyordu

## Belirti
Kullanıcı "bazı ekranlar çalışmıyor" dedi. Yeni QA testi
(`tests/test_ui_pages.py::test_tum_ekranlar_ve_eylemleri`) eski izleme
sayfasıyla çalıştırılınca Qt uyarısı verdi: "... current thread is
QThread(0x…)" — yani bileşenler ana iş parçacığı dışından değiştiriliyordu.
Bu Qt'de tanımsız davranıştır: rastgele çökme, donma veya güncellenmeyen ekran.

## Kök neden
Doğrulandı: `MonitorAgent` kendi `threading.Thread`'inde çalışır ve
`on_check`, `on_state_change`, `on_finished` geri çağrılarını doğrudan
çağırır. `MonitorPage` bu geri çağrılarda `QPlainTextEdit.appendPlainText`,
`QProgressBar.setValue`, `QLabel.setText` kullanıyordu. Ayrıca "Durdur"
düğmesi `agent.stop()` içindeki `join(timeout=10)` ile arayüzü 10 sn'ye kadar
dondurabiliyordu.

## Çözüm
`_MonitorBridge(QObject)` sinyalleri eklendi; ajan geri çağrıları
`signal.emit` olarak verildi, sinyaller ana iş parçacığında arayüzü
günceller. Durdurma ayrı iş parçacığında yapılıyor. Sayfa açılınca duyuru
adresi Ayarlar'dan yeniden okunuyor; hiç güncellenmeyen "Kalan süre: -"
etiketi kaldırıldı.

## Kanıt
Eski kodla test: Qt iş parçacığı uyarısı → başarısız. Yeni kodla:
`test_tum_ekranlar_ve_eylemleri` geçti; `tests/e2e_ui_real_api.py` gerçek
API ile "Qt iş parçacığı uyarısı yok" kontrolünü geçti.

## Önleme
R-11. `tests/test_ui_pages.py` her testte Qt iş parçacığı uyarılarını arar.

## İlgili dosyalar
src/evren_studio/ui/monitor_page.py, src/evren_studio/monitor.py
