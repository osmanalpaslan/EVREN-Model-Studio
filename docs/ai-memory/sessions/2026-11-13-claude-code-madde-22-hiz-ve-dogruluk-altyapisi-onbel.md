---
id: 2026-11-13-claude-code-madde-22-hiz-ve-dogruluk-altyapisi-onbel
tarih: 2026-11-13
motor: Claude Code
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: surum/0.5.1-istekler
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 22 hiz ve dogruluk altyapisi (onbellek, bekciler, masaustu, arka plan, talimatlar)

## Görev
Kullanıcı (2026-11-13): "projelerin yapım hızını ve doğruluk oranını nasıl artırırız; API'leri doğru yönlendiren altyapı;
kurulumda token tasarruflu varsayılan .md mantıklı mı; hata bekçileri; masaüstü kontrolü aşırı yavaş; arka planda EVREN
motorlarıyla yönetim; hangi biçimde göndermek hız kazandırır — derin düşün, web + repo raporları araştır". Analiz sunuldu;
kullanıcı: "olması gereken her şeyi önerdiğin gibi yap, bütün yetki sende, fazlar arası onay isteme" + mesajlar KISA.
Plan: A ölçüm → B önbellek dostu istek → C bekçiler → D masaüstü hız → E arka plan → F talimatlar.

Araştırma kaynakları (özet): ETH "Evaluating AGENTS.md" (arXiv 2602.11988, ICLR 2026: uzun/LLM üretimi bağlam dosyası
başarıyı düşürür, maliyet +%20; kısa insan yazımı +%4; dizin özeti işe yaramaz) · Manus "Context Engineering" (önbellek
isabeti en önemli ölçü; sabit önek, yalnız ekleyerek büyüyen geçmiş, deterministik JSON) · SWE-agent (arXiv 2405.15793:
lint'li düzenleme çıkarılınca %18 → %10,3) · Agentless (arXiv 2407.01489: bul → düzelt → testle seç) · UFO2 (arXiv
2504.14603: tek çağrıda çoklu eylem + UIA ön koşul denetimi) · OSWorld-Human (arXiv 2506.16042: gecikmenin çoğu model
çağrısı; ajanlar 2,7-4,3 kat fazla adım) · Sierra hedged requests (P99 > %70 düşüş) · Aider edit formats (zayıf/açık
modelde tam dosya daha güvenilir) · vLLM APC + structured outputs.

## Yapılanlar
- A ölçüm (gerçek EVREN, scratch betikleri):
  - Önek önbelleği VAR ve usage.prompt_tokens_details.cached_tokens bildiriliyor. deepseek-v4.1-flash 17,6k istem:
    13,6 sn → tekrar 2-3 sn (17.536 önbellek); istemin BAŞINA saat eklenince 7,5 sn, önbellek 0. qwen3.8-flash-next
    12,1k: 15,7 → 0,8-11 sn (9.600 önbellek). qwen 1600 token'lık bloklarla, deepseek 64'lük bloklarla önbellekliyor.
  - Önbellekten okunan token GÜNLÜK KOTADAN DÜŞMÜYOR: 52.824 gönderildi, 35.072 önbellek, kotadan 18.806 düştü.
  - EVREN auto tur içinde model değiştirmiyor (zorluk 60 adım, 0 geçiş) → adımlar arası önbellek korunabilir.
  - Mevcut oran: zorluk %54 (2.+ adım %60), proje %68 (%72). Adım dökümü: kayıp qwen'in blok yapısından (her adım ~1
    blok); sahte istemciyle yakalanan ardışık isteklerde araç listesi ve önceki mesajların TAMAMI aynen korunuyor (tur
    arası dahil, harita değişmediğinde). Risk: proje haritası/hafıza/ortam sistem isteminde → değişince geçmişin
    önbelleği tümden gider (uzun oturumlarda tur başı).
  - Kalıcı: kullanım penceresinde "Bu oturum → Önbellekten: N (%X) — kotadan düşmez, yanıtı hızlandırır" (önbellek
    yoksa satır yok); tools/onbellek_raporu.py (tüm / 2.+ adım / TUR BAŞI oranı, kotadan düşmeyen token).

## Test sonuçları
- A: test_attachments_usage +1 (gerçek _usage_snapshot yolu + panel satırı, önbelleksiz satır yok), test_onbellek_raporu
  (oranlar + tur başı + komut satırı). Mutasyon 4/4.

## Sorunlar ve kayıtlar
- Kendi hatam (R-29, yine): DEVIR tablosuna madde 22 satırını eklerken Python'u bash heredoc ile çalıştırdım (içerik
  basit, sonuç doğru). Bundan sonra yalnız Write ile yazılmış .py betikleri.

## Sonraki motor için notlar
- Faz sırası A→F; her faz ayrı commit + test + mutasyon + gerçek API önce/sonra (tools/onbellek_raporu.py ile). Fayda
  göstermeyen değişiklik geri alınır.
