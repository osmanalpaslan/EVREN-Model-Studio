---
id: 2026-10-19-auto-pro-yedek-listesi-farkli-saglayicinin-modelini-ayni-ist
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [auto-pro, failover, saglayici]
kurallar: []
---

# Auto Pro yedek listesi farklı sağlayıcının modelini aynı istemciyle deniyordu

## Belirti
Kod incelemesinde (MCP'yi ücretli sağlayıcıdan uzak tutma işi sırasında) fark edildi: dengeli
politikada `router.chain_for` EVREN ve ücretli modelleri tek zincirde birleştiriyor; AgentRunner
yedeğe geçerken (`_switch_model`) YALNIZ model adını değiştiriyor, istemci (EVREN/OpenAI/Anthropic)
tur boyunca aynı kalıyor. EVREN turu bir hata sonrası `claude-sonnet-5-5`'e geçse istek EVREN
istemcisine gider (NOT_FOUND → bir sonraki yedek). Gerçek kullanıcıda gözlenmedi (ücretli anahtar yok).

## Kök neden
Doğrulandı (kod okuması): yedek listesi sağlayıcıya göre süzülmüyordu.

## Çözüm
`router.same_provider(fallbacks, api_model, provider_of)`; session_view.start_run yedekleri turun
sağlayıcısıyla sınırlar. Bu, MCP araçlarının ücretli modele hiç ulaşmamasını da garanti eder.

## Kanıt
tests/test_mcp_akilli.py `test_yedekler_ayni_saglayiciyla_sinirli`.

## Önleme
Yedek/geçiş mantığını değiştirirken istemcinin kimin olduğunu da düşün.

## İlgili dosyalar
src/evren_studio/agent/router.py, src/evren_studio/ui/session_view.py
