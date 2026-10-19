---
id: 2026-10-19-qa-senaryosunda-model-sonuc-blogunu-yazmayi-unuttu
tarih: 2026-10-19
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [qa, istem, R-19]
kurallar: []
---

# QA senaryosunda model sonuç bloğunu yazmayı unuttu

## Belirti
İlk gerçek QA koşusunda (e2e_qa_real_api, 11 senaryo) bir senaryo "engellendi — sonuç <qa_sonuc>
bloğuyla bildirilmedi" oldu; model senaryoyu denemiş ama yapılandırılmış sonucu yazmamıştı.

## Kök neden
Doğrulandı: zayıf model uzun araç zincirinden sonra istenen son biçimi unuttu.

## Çözüm
AgentRunner `final_marker`: son yanıtta işaret yoksa BİR kez hatırlatır (yalnız QA turunda
"<qa_sonuc>"). Ayrıca senaryo istemine çalışan servisler yazılır (model 10 kez start_service denemişti).

## Kanıt
tests/test_qa_ajani.py `test_son_isaret_yoksa_bir_kez_hatirlatilir`, `test_servis_bilgisi_istemde`;
ikinci gerçek koşu: CHALLENGE_RESULTS.md "QA ajanı".

## Önleme
Yapılandırılmış son çıktı isteyen her gözetimsiz akışta eksikliği bir kez dürt.

## İlgili dosyalar
src/evren_studio/agent/runner.py, src/evren_studio/agent/qa.py, src/evren_studio/ui/qa_ui.py
