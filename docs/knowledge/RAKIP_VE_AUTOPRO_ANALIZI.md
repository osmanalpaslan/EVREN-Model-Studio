# Rakip uygulamalar ve Auto Pro analizi (2026-10-23)

> Amaç: EVREN Studio'nun benzerlerine göre eksiklerini ve Auto Pro'nun "doğru, hızlı, kendini düzelten"
> bir yönlendiriciye dönüşmesi için gerekenleri çıkarmak. Kullanıcı neredeyse her işini Auto Pro ile yapıyor.
> Yöntem: web araştırması (kaynaklar sonda; çoğu ikincil kaynak, "doğrulanmadı" diye işaretli olanlar var) +
> bu deponun kodu + iki günlük gerçek ölçümler (CHALLENGE_RESULTS.md). Onaylanan maddeler
> `docs/ILERIDE_YAPILACAKLAR.md` madde 7'ye taşınır. **Bu belge yapım kararı değildir.**

## 1. Benzer uygulamalar — öne çıkan yetenekler

| Uygulama | Tür | Öne çıkan (araştırma + genel bilgi) |
|---|---|---|
| Claude Code | CLI/masaüstü ajan | Kontrol noktası + geri sarma (kod ve konuşma, Esc Esc / `/rewind`), hook'lar (araçtan önce/sonra kullanıcı betiği), alt ajanlar, plan modu, skill'ler, proje hafızası (CLAUDE.md), arka plan işleri |
| Cline | VS Code eklentisi | Plan/Act, MCP pazaryeri, tarayıcı otomasyonu, ayrıntılı otomatik onay, CLI |
| Kilo Code | VS Code/JetBrains/CLI | Orchestrator modu (işi alt görevlere böler), Memory Bank (proje hafızası), özel modlar, çok sağlayıcı |
| Roo Code | VS Code | Özel modlar (Code/Architect/Ask/Debug/Orchestrator); 15 Mayıs 2026'da arşivlendi (Kilo'ya göre) |
| Aider | Terminal | Depo haritası (tree-sitter ile sembol özeti), "architect" (güçlü model planlar, hızlı model yazar), git'e otomatik commit, lint/test döngüsü, ses girişi — repo haritası ve architect modu bu aramada doğrulanmadı, genel bilgi |
| OpenHands | Ajan platformu | ~76 bin yıldız, MIT; yalıtılmış (sandbox) çalışma, tarayıcı, gözetimsiz PR açma; küçük modellerle zorlandığı belirtiliyor |
| OpenCode | Terminal | MCP, çoklu ajan, sandbox/izinler, hook/eklenti, web araması, yerel modeller, otomatik özet |
| Cursor (genel bilgi) | IDE | Kod tabanı anlamsal indeksleme, arka plan ajanları |
| LiteLLM / OpenRouter | Model yönlendirici | Yedekleme, bekleme (cooldown), zaman aşımı, yeniden deneme; LiteLLM'de "en düşük gecikme" stratejisi; OpenRouter 5xx/zaman aşımında sıradakine geçer |

## 2. EVREN Studio'da olanlar

Kapsam koruması + tur geri alma, değişiklik paneli, Plan/Onaylı/Otomatik modlar, Auto Pro, Proje ajanı (görev
başına commit), Derin Mod (alt ajanlar, çekişmeli doğrulama, soru kartı), QA ajanı (web), MCP (Serena, Playwright;
gerektiğinde açılır), test ve hata bekçisi, plan bekçisi, uzun işler, kota kapısı, otomatik özet, görsel girdi,
ücretli sağlayıcı (doğrulanmadı), Türkçe arayüz, ortak hafıza (`docs/ai-memory`).

## 3. Eksikler (rakiplerle karşılaştırma)

| No | Eksik | Rakipte | EVREN'de durum | Not |
|---|---|---|---|---|
| E1 | Konuşmayı da geri saran kontrol noktası | Claude Code | Dosya değişiklikleri ve tur geri alınıyor; konuşma "bu noktadan devam" yok | Mesaj düzenle-yeniden gönder kısmen karşılıyor |
| E2 | Otomatik depo haritası | Aider, Cursor | Serena gerektiğinde; isteme hazır harita girmiyor | Zayıf modelde keşif adımlarını azaltır |
| E3 | Planlayan + yazan iki model ("architect") | Aider | Yok (Derin'de plan ayrı model, uygulama tek model) | Auto Pro'ya rol olarak eklenebilir |
| E4 | Kullanıcı hook'ları | Claude Code, OpenCode | Yerleşik bekçiler var; kullanıcı tanımlı yok | Ör. "her düzenlemeden sonra şu betiği çalıştır" |
| E5 | Özel modlar / ajan profilleri | Roo, Kilo | Yok | Skill menüsüyle (7.2) birleşebilir |
| E6 | Kendini güncelleyen proje hafızası | Kilo Memory Bank, CLAUDE.md | `/init` ile EVREN.md bir kez; otomatik güncellenmiyor | Uzun projelerde bağlam kaybını azaltır |
| E7 | Yalıtılmış çalışma (sandbox) | OpenHands, OpenCode | Yok; Otomatik mod komutları gerçek sistemde çalıştırır | İnternetten gelen modlar için önemli (7.3 #15) |
| E8 | Web araması aracı | OpenCode, Cline | Yok | EVREN'in `evren_tools` uzantısı var (API_COMPATIBILITY) — ne sunduğu DOĞRULANMADI |
| E9 | MCP pazaryeri/listesi | Cline | Elle seçilmiş birkaç sunucu | Güvenlik için seçilmiş liste daha doğru; "önerilenler" listesi yeter |
| E10 | Komut paleti (tüm eylemler) | IDE'ler | Ctrl+K yalnız oturum arama | Küçük iş |
| E11 | IDE (VS Code) eklentisi | Hepsi | Yok — ayrı masaüstü uygulaması | Büyük iş; şimdilik önerilmez |
| E12 | Orchestrator (işi alt görevlere bölüp alt ajanlara dağıtma) | Kilo, Roo | Proje ajanı + Derin Mod karşılıyor | Eksik değil; Derin daha kapsamlı |

## 4. Auto Pro — bugünkü işleyiş (koddan)

- **Seçim** (`agent/router.py`): rol sınıflandırması çok kaba — görsel varsa `gorsel`, bağlam büyükse
  `buyuk_baglam`, Plan modunda `plan`, proje klasörü varsa HER iş `kod`, yoksa `sohbet`. İşin zorluğu/türü
  (Excel raporu, oyun, küçük düzeltme, büyük proje) ayırt edilmez.
- **Sıra**: 12 kısa görevlik ölçüme dayalı SABİT tablo (`EVREN_ROUTES`, son ölçüm 2026-10-21).
- **Sağlık**: `choose` son 30 dk'da "sağlıksız" işaretli modeli sona alır; ama bu kayıt YALNIZ "EVREN Durum
  İzleme" ekranından (`monitor.py`) yazılıyor. Gerçek kullanımda hata veren model kaydedilmiyor — kullanıcının
  gerçek veritabanında `model_health` tablosu BOŞTU (2026-10-21). Yani sağlık kuralı pratikte hiç çalışmıyor.
- **Değiştirme** (`runner._switch_model`): yalnız sunucu hatası (5xx, zaman aşımı, ağ, 404, görsel reddi) ve
  döngüde (tur başına bir kez). **Yavaşlık, boş/yarım yanıt, araç hatası çokluğu, test bozma** motor
  değiştirmez. Görev ortasında başka nedenle değiştirmeme 2026-10-19 kullanıcı kararıydı (DECISIONS).
- **Yanıt vermeme**: istemci zaman aşımı 120 sn ve yeniden denemeler; donmuş bir model yedeğe geçmeden önce
  dakikalar harcatabilir. İlk-token süresi ve akış sessizliği ayrıca izlenmiyor.
- **Turlar arası hafıza yok**: bir turda hata verip yedeğe geçilen model, sonraki turda yine birincil seçilir.
- **Kalite ölçümü yok**: araç hata oranı, test bekçisi uyarıları, plan bekçisi dürtmeleri, döngüler motor
  seçimine geri beslenmiyor.
- **Tutarlılık**: aynı veriden iki koşu farklı Yönetim Özeti üretti (hesap kapama). EVREN modelleri `seed`
  parametresini destekliyor (`/v1/models` capabilities) ama kullanılmıyor.
- **Görünürlük**: çalışma çubuğunda "Auto Pro → model (rol)" ve değişim notu var; neden seçildiği, o günkü hızı ve
  geçmiş başarı görünmüyor.
- Güçlü yan: kota/hız sınırında model değiştirmiyor (doğru: kota hesap başına), yedekler aynı sağlayıcıda kalıyor,
  ücretli sağlayıcıya sızma yok.

## 5. Auto Pro için öneriler

| No | Öneri | Neyi çözer | Not / risk |
|---|---|---|---|
| A1 | **Gerçek kullanım kaydı**: her model çağrısının süresi, ilk-token süresi, token/sn, hata türü, boş yanıt, döngü, araç hatası → model başına kayan istatistik (son ~2 saat / son 30 çağrı) | Sağlık kuralı gerçek veriyle çalışır; "o günkü" hız bilinir | Altyapı; diğer maddelerin temeli |
| A2 | **Yanıt vermeme algılama**: ilk token ~45 sn'de gelmezse veya akış ~30 sn susarsa isteği kes, yedeğe geç | Kilo Code'da gördüğümüz "sunucu hatasında takılma"; 120 sn × deneme kaybı | Eşikler ölçülerek ayarlanmalı (deepseek düşünürken uzun susabilir) |
| A3 | **Yavaşlama kuralı (kullanıcının %50 kuralı) — ONAYLANDI 2026-10-23, DECISIONS #88**: (1) yalnız güvenli noktada (iki adım arası, yarım düzenleme yokken; konuşma aynen aktarılır); (2) o günkü gerçek ölçümle (A1) hesaplanan normal hızın yarısının altında art arda 2 adım; (3) görev başına yavaşlıktan en çok 1 değişim; (4) her değişim gerekçesiyle bildirilir; (5) Proje/Derin'de önce görev aralarında, görev içinde yalnız ~3 kat yavaşlıkta | Günden güne değişen performans | A1'e bağlı (normal hız ölçümü olmadan çalışmaz) |
| A4 | **Bekleme süresi (cooldown)**: hata veren/yavaşlayan model 15–30 dk sıranın sonuna iner (turlar arası) | Aynı bozuk modele her turda geri dönme | LiteLLM'deki cooldown deseni |
| A5 | **Kalite puanı**: araç hata oranı, test bozma, plan bekçisi dürtmesi, döngü, kullanıcının "kötü yanıt" işareti → model puanı; düşen model öne alınmaz | "Hızlı ama özensiz" motoru ayıklar | Puan yalnız sıralamayı etkiler, modeli tamamen kapatmaz |
| A6 | **Zorluğa göre seçim**: kısa soru/küçük düzenleme → hızlı model (gemma, 3 dk/12 görev); çok dosyalı/uzun/Proje görevi → güvenilir model (deepseek-v4.1); 2 başarısız denemede güçlüye yüksel | Basit işte bekleme, zor işte özensizlik | gemma uzun işte döngüye girdi → yalnız kısa işler; maraton ölçümü gerekli |
| A7 | **İş türü rolleri**: veri/Excel raporu, oyun/3D, web/QA, Türkçe metin için ayrı rol + her biri için küçük ölçüm paketi (hesap kapama testi hazır) | "Kod" rolü her şeyi kapsıyor | Ölçüm kota harcar; paket başına ~10 dk |
| A8 | **Hafif yoklama**: uygulama açılınca ve Derin/Proje başlamadan önce her adaya birkaç yüz tokenlık istek (sağlık + gecikme) | Gün başında bozuk/yavaş modeli işe başlamadan elemek | Az token; plan onayı beklenirken arka planda |
| A9 | **Model listesi değişim uyarısı**: listeden kalkan/eklenen model (deepseek-v4-flash olayı) → not + "yeniden ölç" önerisi | Sessizce yedeğe düşme | Küçük iş |
| A10 | **Tutarlılık modu**: rapor/veri işlerinde `temperature` düşük + sabit `seed` | Aynı veriden farklı rapor | EVREN'de gerçek istekle denenmeli (R-07) |
| A11 | **Kota farkındalığı normal turlarda da**: pencere doluyken uzun işi hafif modele/kısa yanıtlara yönelt; günlük azken uyar | Kota kapısı şu an yalnız Derin'de | |
| A12 | **Şeffaflık**: çalışma çubuğunda "neden bu motor" (ör. "deepseek-v4.1 · son 2 saatte en hızlı ve hatasız"); Modeller sayfasında son 24 saat hız/başarı tablosu | Kullanıcı Auto Pro'ya neden güveneceğini görür | 7.3 #7–8 ile birleşir |
| A13 | **Architect rolü (E3)**: zor işte plan için güçlü/yavaş, yazım için hızlı model | Hız + kalite | Derin'de kısmen var; normal turda yeni |
| A14 | **İki modele aynı anda sorma (hedge)**: yalnız kısa iç işlerde (başlık, commit mesajı) ilk gelen yanıtı al | Gecikme | Token iki katı; ÖNERMİYORUM, yalnız seçenek olarak |

## 6. Önerilen sıra

1. A1 (kayıt) → A4 (cooldown) → A2 (yanıt vermeme) → A3 (yavaşlama; onaya bağlı) — Auto Pro'nun "kendini düzelten"
   çekirdeği.
2. A12 + A9 (görünürlük ve uyarı).
3. A6 + A7 (zorluk ve iş türüne göre seçim; ölçüm paketleriyle).
4. A10, A11, A5, A8, A13 (ince ayar). A14 isteğe bağlı.
Rakip eksiklerinden önce E2, E6, E8, E7 (zayıf EVREN modellerine en çok yardım edenler), sonra E1, E4, E5, E10.

## 7. Kullanıcı onayı (2026-10-23)

A1–A13 ve E1–E10 onaylandı; A14 ve E11 kapsam dışı; E3 = A13. Uygulama planı ve sıra:
`docs/ILERIDE_YAPILACAKLAR.md` madde 7.4. Kullanıcı "toplu yap" diyene kadar uygulanmaz.

## Kaynaklar

- Kilo/Cline/Roo karşılaştırması: https://kilo.ai/compare/roo-vs-cline-vs-kilo ·
  https://www.morphllm.com/comparisons/kilo-code-vs-cline · https://www.morphllm.com/comparisons/roo-code-vs-cline ·
  https://fast.io/resources/kilo-code-vs-cline/
- Aider / OpenHands / OpenCode: https://terminaltrove.com/compare/ai-coding-agents/opencode-vs-openhands-cli/ ·
  https://terminaltrove.com/compare/ai-coding-agents/aider-vs-openhands-cli/ ·
  https://dev.to/jovan_chan_9500711396d4e6/openhands-review-2026-the-76k-star-coding-agent-5pa
- Claude Code: https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously ·
  https://timewell.jp/en/columns/claude-code-complete-guide
- Yönlendiriciler: https://docs.litellm.ai/docs/routing · https://apitracker.io/llm-routers
