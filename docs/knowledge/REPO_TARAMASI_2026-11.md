# Açık kaynak depo taraması — Derin Mod ve uygulamanın tamamı (2026-11-11)

> Kullanıcı isteği: "Derin modu daha çok geliştirmek ve hızlandırmak için güvenilir, kaliteli repolar var mı, detaylı tarama
> yap; uygulamaya farklı konularda işimize yarayacak her repoya bakabilirsin; amacına tamamen uygun tam bir uygulama."
> Yöntem: GitHub API (yıldız, lisans, son güncelleme, arşiv — 2026-11-11 anlık) + web araması + bu deponun kodu.
> **Bu belge yapım kararı değildir**; onaylanan maddeler `docs/DEVIR_NOTU.md` geliştirme sırasına taşınır.
> "Doğrulanmadı" = ikincil kaynak / kendi ölçümümüz yok.

## 0. Seçim ölçütleri

- Lisans: MIT / Apache-2.0 / BSD (uygulama MIT; GPL/AGPL bağımlılık dağıtımı bağlar → **alınmaz**).
- Bakım: son 3 ayda güncelleme, arşivlenmemiş.
- Yaklaşım: büyük çerçeveyi (LangGraph, CrewAI, AutoGen…) bağımlılık olarak ALMAYIZ — Qt'siz kendi çekirdeğimiz var,
  çerçeve = yeniden yazım + ağır bağımlılık. **Fikir alırız**, küçük ve tek işlevli kütüphaneyi doğrudan kullanırız.
- EVREN kısıtı: ücretsiz motorlar, 5 dk kota penceresi; aynı anahtarla 3 eşzamanlı istek beklemiyor (ölçüm 2026-11-07).

## 1. Derin Mod — bugün

anla (3 salt okunur alt ajan, paralel 3) → planla (iki motor + yargıç) → uygula (Proje ajanı: görevler SIRAYLA, görev
başına commit) → doğrula (2 bakış açısı, paralel) → düzelt. Ölçüm: CHALLENGE_RESULTS "Madde 17A + 19 sonrası".

## 2. Derin Mod için bulunanlar

| Kaynak | Ne | Lisans · ★ · son | Bize ne kazandırır |
|---|---|---|---|
| **CAID** (CMU, OpenHands üzerinde; OpenHands blog "Asynchronous SWE agents") | Yönetici ajan işi bağımlılık grafiğine böler; her "mühendis" ajan KENDİ git worktree'sinde uygular/test eder/commit'ler; dallar sırayla birleştirilir, çakışmayı yönetici çözer; iletişim yalnız yapılandırılmış JSON + commit | (yöntem; OpenHands MIT · 93k · 2026-11) | Bildirilen: tek ajana göre **+%14 (Commit0), +%27 (PaperBench)**; ortak klasörde çalışan ajanlarda belirgin düşüş; ajan sayısı paralel alt görev sayısını geçince kazanç yok. Bizim Proje ajanını paralelleştirmeme nedenimiz (aynı dosyalar) worktree ile çözülüyor. Görevlerimizde `depends` alanı ZATEN var. (Doğrulanmadı: kendi ölçümümüz yok) |
| **OpenHands doğrulama katmanı** (blog 2026-05-06) | Küçük hızlı "eleştirmen" model ajan çalışırken başarı olasılığını puanlar; düşükse erken durdur / yeniden dene. PR'da ayrı inceleme ajanı + değişikliği çalıştıran QA ajanı | OpenHands MIT; eleştirmen modelinin lisansı belirtilmemiş | Döngüye giren/raydan çıkan alt görevi dakikalar harcamadan keser. Bizde döngü bekçisi var (kural tabanlı); anlamsal "gidiş kötü" kararı yok. Uyarı: aynı modelin kendini denetlemesi zayıf (VerifiAgent makalesi) — eleştirmen ayrı motor olmalı |
| **Agentless** (OpenAutoCoder) | Ajansız hat: yerelleştir → birkaç aday onarım → **yeniden üretme testi** + regresyon testleriyle doğrula → en iyiyi seç | MIT · 2.1k · 2024-12 (bakımsız) | Fikir: hata düzeltme işinde ÖNCE hatayı yeniden üreten test yaz, sonra düzelt, o testle doğrula. Kod almayız (bakımsız) |
| **mini-swe-agent** (SWE-agent ekibi) | ~100 satırlık, yalnız bash kullanan ajan; standart iskeleyle açık modellerle SWE-bench Verified ~%80 bildiriliyor | MIT · 9.5k · 2026-11 | Ölçüm iskelesi: Derin Mod'u bağımsız bir görev setiyle (SWE-bench'in küçük alt kümesi) karşılaştırmak için. Fikir: az ve sade araç = daha az kafa karışıklığı |
| **SWE-agent / SWE-ReX** | Ajan + kum havuzunda (sandbox) paralel çalıştırma | MIT · 20.8k / 643 · 2026-11 | Paralel denemelerin yalıtımı için örnek; Windows'ta bizim için worktree yeterli |
| **deepagents** (LangChain) | "Pil dahil ajan donanımı": yapılacaklar listesi aracı, alt ajanlar (bağlam karantinası), büyük bulguları DOSYAYA yazıp bağlamdan çıkarma | MIT · 31k · 2026-11 | Fikir: alt ajan bulgularını dosyaya yaz, ana bağlama yalnız özet + yol → uzun Derin işlerde bağlam şişmesi ve token azalır. Bağımlılık olarak alınmaz (LangChain) |
| **OpenCodeReview** (Alibaba, makale 2608.09290) | İnceleme ajanının "yansıtıcı"sı yalnız farkı (diff) görür, keşif geçmişini görmez → uydurma yorum azalır | depo bulunamadı (doğrulanmadı) | Bizim doğrula aşaması zaten diff + istek görüyor; ilke doğrulandı, ek iş yok |
| **json_repair** | Modelden gelen bozuk JSON'u onarır | MIT · 5.1k · 2026-11 · **bağımlılıksız** | 2026-11-07'de qwen'in bozuk `<bulgu>`'su anla aşamasını 0/3 yapmıştı; kendi `loose_object`'imiz bunu çözdü. json_repair çok daha fazla bozukluk türünü kapsar (plan, QA sonucu, denetim, karne blokları) — küçük, güvenli iyileştirme |
| **Aider repo haritası** / **py-tree-sitter** + **tree-sitter-language-pack** | tree-sitter ile her dilde sembol çıkarma; Aider ayrıca PageRank ile en çok başvurulan sembolleri seçer | Aider Apache-2.0 · 50k · **2026-05 (yavaşladı)**; py-tree-sitter MIT · 1.5k · 2026-11; language-pack MIT · 485 · 2026-11 | Bizim haritamız Python'da `ast`, JS/TS'de basit tarayıcı; Go/Rust/C#/Java/PHP'de sembol yok → bu dillerde ajan keşif adımı harcıyor. Tree-sitter ile tüm dillerde sembol + "en çok kullanılan" sıralaması |
| **ruff** / **ty** (Astral) | Çok hızlı Python denetçisi / tür denetçisi (Rust) | MIT · 51k / 20k · 2026-11 | Hata bekçisi şu an yerleşik basit denetim + (varsa) Serena. ruff saniyenin altında gerçek hataları (tanımsız ad, kullanılmayan içe aktarma) bulur → Derin "doğrula" ve her düzenleme sonrası hızlı, güvenilir sinyal |

**Değerlendirilip alınmayanlar (Derin):** LangGraph (MIT, 44.8k), CrewAI (MIT, 60.8k), Microsoft Agent Framework (MIT,
14.6k), AutoGen (bakım kipinde; Agent Framework'e devredildi), smolagents (Apache, 30k), DSPy (MIT, 39k) — hepsi çerçeve;
yeniden yazım gerektirir, fikirleri yukarıda alındı. open_deep_research **arşivlendi**. coder/xum **AGPL** (alınmaz).
Plandex (MIT) 2025-10'dan beri güncellenmiyor.

## 3. Uygulamanın geri kalanı için bulunanlar

| Konu | Kaynak | Lisans · ★ · son | Durum bizde | Kazanç |
|---|---|---|---|---|
| **Belge okuma** (PDF, Word, PowerPoint) | MarkItDown (Microsoft) yaklaşımı; doğrudan kütüphaneler: **pdfminer.six**, **mammoth**, **python-pptx** | MarkItDown MIT · 195k; kütüphaneler MIT/BSD | **YOK** — yalnız görsel ve Excel (kendi `tables.py`) | Kullanıcı sohbete/ajana PDF, Word, sunum verebilir; ajan okuyup özetler, rapor çıkarır. MarkItDown'ın çekirdeği ağır `magika` (ML) getirir → doğrudan küçük kütüphaneler |
| **Gerçek terminal** | **pywinpty** | MIT · 164 · 2026-10 | Terminal paneli düz metin kutusu (etkileşimli program çalışmaz) | Renkli çıktı, etkileşimli komutlar. Bir terminal emülatörü de gerekir (pyte LGPL — dikkat) → büyük iş, düşük öncelik |
| **Güncelleme denetimi** | Kendi küçük denetimimiz (GitHub Releases API); tufup (MIT, 149★, 2025-10) | — | Yok (ILERIDE §1.4) | "Yeni sürüm var" bildirimi + kurulum dosyasını indirip açma. Önkoşul: GitHub Releases'a yayın (kullanıcı onayı) |
| **Sesle yazma** | **faster-whisper** / **whisper.cpp** | MIT · 26.7k / 55k · 2026-11 | Yok | Türkçe konuşmayı yazıya çevirme, internetsiz. Model indirme 75 MB–1.5 GB → isteğe bağlı kurulum |
| **Oturumlarda anlamsal arama** | **sqlite-vec** + **fastembed** | Apache · 8.3k / 3.3k | Ctrl+K metin araması var | "Geçen hafta Excel raporunu nasıl yapmıştık" türü arama. Orta öncelik |
| **Ajan hafızası** | mem0 (Apache, 69k), Letta (Apache, 25k) | — | EVREN.md + "Öğrenilenler" (E6) var | Ek kazanç belirsiz; şimdilik gerekmez |
| **Gözlemlenebilirlik** | Langfuse, Phoenix | lisans karışık | Kendi model_calls kaydımız + zaman özeti var | Gerekmez |
| **Çok sağlayıcı ağ geçidi** | LiteLLM | lisans karışık (çekirdek MIT + kurumsal) | Kendi ağ geçidi desteğimiz var (Madde 9) | Gerekmez |
| **Tarayıcı / masaüstü ajanı** | browser-use (MIT, 121k), Microsoft UFO (MIT, 10k) | — | Playwright MCP + Windows-MCP var (ölçüldü) | Değiştirmeye gerek yok |
| **Arayüz bileşenleri** | QtAwesome (MIT); PyQt-Fluent-Widgets **GPL-3 → alınmaz** | — | Kendi SVG simgelerimiz + tema sistemi | Gerekmez |
| **Mutasyon / özellik testi** | mutmut (BSD, 1.5k), Hypothesis (MPL-2.0, 9.2k) | — | Mutasyonu elle betikle yapıyoruz | İleride Derin "doğrula"da: ajanın yazdığı testler gerçekten yakalıyor mu? Ağır; sonra |

## 4. Önerilen sıra (her madde: hedefli test + mutasyon + gerçek API önce/sonra ölçümü)

| Aşama | Madde | Tahmini iş | Beklenen etki | Ölçüm |
|---|---|---|---|---|
| A1 | json_repair ile tüm yapılandırılmış blokların okunması (kendi okuyucu yedek kalır) | küçük | Derin/QA/Proje'de "blok okunamadı" sıfıra yakın | e2e_derin, e2e_qa, birim (gerçek bozuk çıktılar) |
| A2 | ruff ile hızlı hata denetimi (hata bekçisi + Derin doğrula; ilk kullanımda kurulur, Serena gibi) | küçük-orta | Python projelerinde hatalar düzenlemeden hemen sonra yakalanır | zorluk paketi (hata_ayikla vb.) önce/sonra |
| A3 | PDF / Word / PowerPoint okuma (sohbet eki + ajanın `read_file`'ı) | orta | Kullanıcı belgeleriyle çalışma (rapor, özet, karşılaştırma) | birim + gerçek API (örnek belgeler) |
| B1 | Derin: hata düzeltme işinde önce yeniden üretme testi (Agentless/SWE-agent) | orta (istem + doğrula) | Düzeltmenin gerçekten hatayı giderdiği kanıtlanır | e2e_derin + yeni "hata düzelt" senaryosu |
| B2 | Derin: alt ajan bulguları dosyaya, bağlama özet (deepagents) | küçük-orta | Uzun Derin işlerinde token ve süre azalır | e2e_derin süre/token |
| B3 | **Derin: bağımsız görevler ayrı git worktree'lerinde PARALEL uygulama + sıralı birleştirme (CAID)** | büyük | Çok görevli işlerde hız (görev sayısına göre) + bildirilen kalite artışı | e2e_proje / e2e_derin çok görevli senaryo, önce/sonra |
| B4 | Derin: ayrı hızlı motorla "gidiş" puanı, düşükse erken durdur/yeniden dene (OpenHands eleştirmeni) | orta | Raydan çıkan alt görevde dakika kaybı azalır | yanlış alarm oranı (R-22) + süre |
| C1 | Proje haritası tree-sitter ile tüm dillerde (+ en çok başvurulan semboller) | orta | Python dışı projelerde keşif adımı azalır | zorluk + Go/C# küçük proje |
| C2 | Güncelleme denetimi (GitHub Releases) | küçük-orta | Kullanıcı yeni sürümden haberdar olur | birim; önkoşul: yayın onayı |
| C3 | Sesle yazma (faster-whisper, isteğe bağlı kurulum) | orta | Konuşarak görev verme | gerçek Türkçe ses örneği |
| C4 | Gerçek terminal (pywinpty) | büyük | Etkileşimli komutlar | arayüz testi |

### Uygulama durumu (2026-11-11)

- A1, A2, A3, B1: YAPILDI (PR #56). Ölçümler oturum günlüğünde (`docs/ai-memory/sessions/2026-11-11-…`).
- B2: YAPILMADI (gerekçe): Derin'in bağlam notu ≤3500 karakter; alt ajan istemi bunun 5-10 katı. Bulguyu dosyaya
  taşımak her alt ajana bir okuma adımı (~10 sn) ekler; token kazancı küçük → net olumsuz.
- B3: YAPILDI (dal `feat/b3-paralel-gorev`): Proje ajanı (ve Derin'in uygulama aşaması) bağımsız görevleri ayrı git
  çalışma kopyalarında aynı anda yapar, sırayla birleştirir; çakışan/doğrulanamayan sırayla yeniden yapılır. Gerçek:
  3 bağımsız görev 80 sn (tek tek ~209 sn), kabul 8/8. Toplam süreyi sıralı kalan görevler (toparlama, README) belirler.
- B4: YAPILDI (dal `feat/b4-gozetmen`): gözetimsiz görevde ayrı hızlı model 8 adımda bir puan; tek düşük → not,
  iki üst üste düşük → erken durdur + gerekçeyle yeniden dene. Yanlış alarm ölçümü: oturum günlüğü.

## 5. Kaynaklar

- GitHub API, 2026-11-11 (her satırdaki yıldız/lisans/tarih).
- OpenHands — The Verification Stack: https://www.openhands.dev/blog/20260506-the-verification-stack
- OpenHands — Effective Strategies for Asynchronous Software Engineering Agents (CAID): https://www.openhands.dev/blog/asynchronous-software-engineering-agents
- SWE-bench Verified (Epoch AI): https://epoch.ai/benchmarks/swe-bench-verified · SWE-Bench Pro tartışması: https://www.morphllm.com/swe-bench-pro
- Paralel alt ajanlı araçlar karşılaştırması: https://www.morphllm.com/parallel-coding-agents
- tree-sitter depo haritası örnekleri: https://dev.to/oper18/giving-coding-agents-a-map-symbol-level-rag-with-tree-sitter-qdrant-and-sqlite-3ae5 · https://arxiv.org/html/2603.27277
- VerifiAgent (kendi kendini denetlemenin sınırları): https://arxiv.org/pdf/2504.00406 · OpenCodeReview: https://huggingface.co/papers/2608.09290.md
