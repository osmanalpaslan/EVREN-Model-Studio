---
id: 2026-10-17-bos-yanit-ve-soz-verip-durma-sessizce-bitti-sayiliyordu
tarih: 2026-10-17
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [dongu, bos-yanit, reasoning]
kurallar: [R-19]
---

# Boş yanıt ve "söz verip durma" sessizce bitti sayılıyordu

## Belirti
- DepoWise oturumu (gerçek kullanım): deepseek-v4-flash 5 KB'lık kod
  incelemesinde 16384 çıktı token'ının tamamını muhakemeye harcadı, içerik boş;
  yanıtta `usage.evren.reasoning_budget_exhausted=true`.
- deepseek-v4.1-flash "Önce projeyi inceleyeyim." deyip araç çağırmadan bitirdi.
Her iki durumda koşucu turu `done` saydı; kullanıcıya uyarı yoktu.

## Kök neden
Doğrulandı: `run()` araçsız her yanıtı tur sonu kabul ediyordu. EVREN'e
düşünme ayarı gönderilmiyordu (`reasoning_effort` yoktu).

## Çözüm
Araçsız yanıt boşsa veya kısa bir niyet cümlesiyse (`looks_like_unfinished_intent`)
bir kez geçici hatırlatma (kayda yazılmaz) ile yeniden istenir. Boş yanıtta,
EVREN kaydı `capabilities.reasoning_effort` bildiren modellerde o tek deneme
`reasoning_effort: "none"` ile yapılır (`stall_retry_body`, session_view).
Yine boşsa kullanıcıya not düşülür. `EvrenClient.chat(extra_body=...)` eklendi;
OpenAI/Anthropic istemcileri parametreyi yok sayar.

Ölçüm (gerçek istek): `"none"` düşünmeyi 0'a indirir (deepseek 5,9→1,2 sn) ama
qwen'de yanıt yanlış çıktı → yalnız boş yanıt kurtarmada kullanılır, varsayılan
değil. `"low"` deepseek'te DAHA FAZLA düşündü — kullanılmaz.

## Kanıt
`tests/test_loop_guard.py::test_bos_yanit_bir_kez_durtulur_ve_dusunme_kapatilir`,
`test_soz_verip_durma_durtulur`, `test_niyet_algilama`; LOOP_ANALYSIS.md tablosu.

## Önleme
R-19.

## İlgili dosyalar
- src/evren_studio/agent/runner.py
- src/evren_studio/api/client.py
- src/evren_studio/ui/session_view.py
