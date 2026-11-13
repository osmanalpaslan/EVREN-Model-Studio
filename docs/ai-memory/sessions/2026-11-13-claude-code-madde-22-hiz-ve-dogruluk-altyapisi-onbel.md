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

- B önbellek dostu istek düzeni (runner): SABİT sistem istemi oturum başına dondurulur (`_FROZEN_SYSTEM`, anahtar
  (veritabanı, oturum), imza: kip, protokol, araç listesi, gün, EVREN/AGENTS/CLAUDE.md mtime+boyut, özet sonrası geçmiş
  başı, harita/skill/klasör/oyun/MCP ipuçları, kalıcı rol+profil talimatı); kurulum sonrası geçersizlenir. DEĞİŞEN notlar
  (tura özel ipucu: eksik dosya/web/model değişti, mimar planı → `turn_extra`, açık plan bölümü) sistem isteminden çıkıp
  son mesajın sonuna kuyruk notu (`append_tail`, kayda yazılmaz). Proje haritası artık oturum başında alınır (özetten
  sonra yenilenir) — eskiden her turda yeniden hesaplanıp değişince tüm geçmişin önbelleğini bozuyordu. A/B için
  EVREN_STUDIO_ONBELLEK_ESKI=1. Yeni gerçek API betiği tests/e2e_onbellek_real_api.py (3 tur; tur başı oranı).

- C bekçiler: C1 bozma koruması (tools.guard_breakage: önceden sağlam .py/.json/.toml'u bozan edit_file/write_file
  YAZILMAZ, hata + önerilen sonucun ilgili satırları döner; yeni dosya ve zaten bozuk dosya serbest). Tanımsız ad
  denetimi ruff ile ZATEN vardı (Madde 20 A2) — analizdeki öneri kodda doğrulandı, tekrar yazılmadı. C2 iddia bekçisi
  (agent/claims.py: "testler geçti" → son yazmadan sonra çıkış 0 test komutu ya da test bekçisi geçişi; "`x` oluşturuldu"
  → dosya var mı; olumsuz/soru/öneri cümleleri iddia değil; tur başına bir kez; kalite olayı unverified_claim ağırlık 1).
  C3 hata düzeltme isteğinde (project.is_bugfix) ve testli projede tur ipucu "önce kırmızı test, sonra düzelt, aynı test
  yeşil" (kuyrukta; plan kipinde/testsiz projede yok). C4 (modele göre düzenleme biçimi) YAPILMADI: düzenleme hatası
  %2,3 ve en yakın bölüm ipucu var; ölçülmüş ihtiyaç yok.

## Test sonuçları
- A: test_attachments_usage +1 (gerçek _usage_snapshot yolu + panel satırı, önbelleksiz satır yok), test_onbellek_raporu
  (oranlar + tur başı + komut satırı). Mutasyon 4/4.
- B: tests/test_onbellek_duzeni.py 6 (ardışık isteklerde önceki istek kuyruksuz olarak sonrakinin AYNEN başı — adım ve
  tur, dosya değişse ve ipucu gelip gitse bile; EVREN.md / kip / aynı araçlı kip değişince yenilenir; özetten sonra
  yenilenir, kurulumda geçersizlenir; eski düzen; kuyruk ekleme biçimleri) + güncellenen 3 test (plan, web, eksik dosya
  ipucu artık kuyrukta). Mutasyon 9/9 (ilk turda 2 kaçış → aynı araçlı kip + kalıcı talimat kuyrukta değil testleri).
  Risk paketi (ajan/derin/proje/plan/web/skill/MCP 20 dosya) 354 geçti. GERÇEK EVREN (deepseek-v4.1-flash, aynı saatte
  ikişer): ESKİ tur başı %45/%46, tüm %69/%65, süre 155/65 sn → YENİ tur başı %96/%96, tüm %87/%86, süre 72/45 sn;
  görev 4/4 GEÇTİ.
- C: tests/test_bekciler_c.py 21 (C1: bozan düzenleme yazılmaz + satır, zaten bozuk/adım adım düzeltme serbest, JSON
  üstüne bozuk yazma reddedilir, yeni dosya/metin serbest, akışta model düzeltir; C2: kanıtsız/önce/düşen test → dürt,
  kanıtlı/bekçi geçirdi → yok, 7 olumsuz/iddiasız cümle, dosya yok → dürt, akışta bir kez + tekrar iddiada döngü yok,
  gerçek pytest'le test bekçisi geçirince yok, plan kipinde yok; C3 tetiklenen + 3 tetiklenmeyen). Mutasyon 15/16 +
  1 eşdeğer (dosya türü süzgeci yalnız hız; alt denetim türü zaten seçiyor). Risk paketi 377 geçti.

## Sorunlar ve kayıtlar
- Kendi hatam (R-29, yine): DEVIR tablosuna madde 22 satırını eklerken Python'u bash heredoc ile çalıştırdım (içerik
  basit, sonuç doğru). Bundan sonra yalnız Write ile yazılmış .py betikleri.

## Sonraki motor için notlar
- Faz sırası A→F; her faz ayrı commit + test + mutasyon + gerçek API önce/sonra (tools/onbellek_raporu.py ile). Fayda
  göstermeyen değişiklik geri alınır.
