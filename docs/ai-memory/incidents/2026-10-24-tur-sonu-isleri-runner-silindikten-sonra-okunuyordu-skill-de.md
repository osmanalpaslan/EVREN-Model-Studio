---
id: 2026-10-24-tur-sonu-isleri-runner-silindikten-sonra-okunuyordu-skill-de
tarih: 2026-10-24
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [F3, F4, skill-denetcisi, E6, birim-testi-boslugu]
kurallar: [R-31]
---

# Tur sonu işleri runner silindikten sonra okunuyordu, skill denetçisi hiç çalışmıyordu

## Belirti
F5'te zaman özeti eklerken görüldü: `SessionView._on_done` önce `_finish()` çağırıyor, o da `self.runner = None`
yapıyor; F3/F4'te eklediğim `getattr(self.runner, "quality_events")` ve `getattr(self.runner, "used_skills")`
bundan SONRA okunuyordu → her zaman boş liste. Sonuç: gerçek kullanımda F4 skill denetçisi (#13) tur sonunda HİÇ
çalışmıyordu; E6 ders önerisi test-düşmesi sinyalini hiç görmüyordu. F4 PR'ı (#25) bu hatayla birleşti.

## Kök neden
Doğrulandı. Birim testleri `_skill_check([...])` ve `_suggest_learnings(..., [...])`'i DOĞRUDAN çağırdı; gerçek
tur akışından (send → koşucu → _on_done) geçen bir test yoktu. Gerçek API skill ölçümü (R-25) yalnız read_skill'i
ve sonucu denetledi, denetçi kartını değil.

## Çözüm
`_on_done` runner'ı ve başlangıç saatini `_finish()`'ten ÖNCE yerel değişkene alır (`done_runner`, `turn_total`).
Uçtan uca test: sahte istemciyle gerçek tur (`read_skill` çağrısı) → denetçi kartı çıkmalı
(tests/test_f5_arayuz.py::test_kosucu_arac_suresini_kaydeder_ve_tur_sonu_islerini_runner_silinmeden_yapar).

## Kanıt
Yeni test önce düzeltmesiz kodda kart çıkmayacağını gösterir (kod incelemesiyle doğrulandı); düzeltmeyle geçti.

## Önleme
Tur sonuna bağlanan her özellik için en az bir testi gerçek tur akışından (send) geçir; yalnız yardımcı fonksiyonu
doğrudan çağıran test, bağlantı hatasını yakalamaz.

## İlgili dosyalar
- src/evren_studio/ui/session_view.py
- tests/test_f5_arayuz.py
