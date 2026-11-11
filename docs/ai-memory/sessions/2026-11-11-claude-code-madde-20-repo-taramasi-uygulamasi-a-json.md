---
id: 2026-11-11-claude-code-madde-20-repo-taramasi-uygulamasi-a-json
tarih: 2026-11-11
motor: Claude Code
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/a1-json-onarim
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 20 repo taraması uygulaması (A json_repair ruff belgeler, B Derin, C)

## Görev
Kullanıcı (2026-11-11): Derin Modu geliştirmek/hızlandırmak ve uygulamanın tamamı için güvenilir açık kaynak depoları tara
(rapor: docs/knowledge/REPO_TARAMASI_2026-11.md). Sonra: "sırasıyla başla, hiçbir maddeye geçerken onay isteme, yetki sende".
Sıra: A1 json_repair → A2 ruff → A3 PDF/Word/PowerPoint → B1 yeniden üretme testi → B2 bulgular dosyaya → B3 worktree'de
paralel uygulama → B4 eleştirmen → C1 tree-sitter harita → C2 güncelleme → C3 ses → C4 gerçek terminal.
Ayrıca kullanıcının sorusu: "auto kendi sırasını belirlemiyor mu, neden qwen sorusu?" → yanıtlandı (sıra yalnız güvenlik
ağı + iç işler); yetki verildiği için kod tablosunda qwen öne alınacak (ölçüm 2026-11-06).

## Yapılanlar
- A1 (dal feat/a1-json-onarim): `agent/jsonfix.py` — katı json.loads → json_repair (MIT, bağımlılıksız, 0.52) ile kendi
  anahtar-sınırı okuyucumuz (qa.loose_object) YARIŞIR, en çok bilgiyi kurtaran seçilir (`best`, `_score`). Bağlanan yerler:
  qa._json_block (QA planı/sonucu, Derin bulgu/denetim), project.parse_review (inceleme kararı), scope.parse_response
  (kapsam kararı — bozuk JSON önceden "ihlal yok" sayılıyordu!), deep.plan yargıcı (bozuk karar hep "A" sayılıyordu).
  Araç argümanları BİLEREK onarılmaz (yarım write_file sessizce eksik dosya yazardı) — test bunu kilitler.
  Duman testi `json_repair=var` (paketle.py denetler). requirements + pyproject.

- Kod rolü yedek sırası qwen → deepseek → gemma (kullanıcı "yetki sende"; karne ölçümü 2026-11-06). Yalnız auto güvenlik
  ağı + iç işler (Derin/Proje kod aşaması). 6 test eski sırayı adla yazmıştı → tablo-göreli yazıldı (first/second), anlamı
  korundu (ceza/bekleme/puan/zayıf gün mantığı).

- GEÇİCİ KLASÖR SIZINTISI (disk temizliği oturumundan istek, 2026-11-11): Temp'te 21 evren-masaustu-* (~8,5 GB; Windows-MCP
  venv + uv önbelleği) ve 154 evren-denetim-* birikmişti. tools/gecici.py (klasor() kaydeder, çıkışta atexit ile siler;
  kilitte kısa bekleyip yeniden dener; salt okunur dosya; `--sakla` / EVREN_GECICI_SAKLA=1). Uygulandı: e2e_masaustu,
  e2e_hiz, e2e_ui, e2e_zamanlayici; ui_denetim denetle() pencere kapanınca hemen siler. test_gecici_klasor 4 (bekçi: mkdtemp
  kullanıp silmeyen betik testi düşürür). Gerçek: ui_denetim çalıştırıldı, klasör sayısı değişmedi. Mevcut eski klasörler
  SİLİNMEDİ (toplu silme kullanıcı onayı ister; disk oturumu yürütüyor).

- A2 ruff (0.17.4, MIT): hata bekçisi Python'da sözdizimi temizken `ruff check --isolated --select E9,F63,F7,F82` (stdin;
  projenin ayarı karışmaz) → tanımsız ad / yapı hatası; Serena açıksa ikisi birleşir, aynı satır tekrarlanmaz
  (diagnostics.lint_problems + merge). Stil/kullanılmayan import bilerek yok. Paket: spec ruff.exe'yi `_internal/tools/`
  altına koyar (pip ikilisi Scripts'te → PyInstaller kendiliğinden almaz); duman `ruff=var`. test_ruff_bekci 6 +
  test_mcp_akilli güncellendi; mutasyon 5/6 → kaçan "yıldızlı import koruması" GEREKSİZDİ (ruff F405 verir) → kaldırıldı.

- A3 belgeler (dal feat/a3-belgeler): agent/documents.py — PDF (pdfminer.six, `--- Sayfa N ---`; taranmış PDF'te "metin
  yok" notu, uydurma yok), Word (python-docx; başlık/liste/tablo belge sırasıyla), PowerPoint (python-pptx; slayt, tablo,
  konuşmacı notu); hepsi MIT. read_file belgeyi metne çevirip okur (salt okunur); write_file .docx/.pptx/.pdf adına düz
  metin YAZMAZ (bozuk dosya) → betikle üretmeyi önerir; sohbet eki metne çevrilir (≤120 bin karakter). Gerçek Türkçe PDF
  (Windows çizimi, gömülü yazı tipi): ğ ş ı İ doğru. Testte PDF elle üretildi (offscreen'de Qt yazıyı yol olarak çiziyor →
  metin katmanı yok). Duman `belge=var` (şablon dosyaları dahil). test_belgeler 7; mutasyon 8/8.
- Tuzak tekrarı (R-29): heredoc içinde Python yaması ters bölü/
'yi bozdu (iki kez) → Write aracıyla dosya + birleştirme.

- A AŞAMASI KAPANIŞ (21:15-22:10): tam takım 1055/1055; zorluk auto 12/12 1410 sn (sunucu yavaş); R-13: E2E_OK · ajan 5/6
  (incelenecek) · arayüz 15/15; paket 0.4.2 yeniden: 207 MB, duman ruff/belge/json_repair var. e2e_belge (yeni, gerçek API):
  Word tablosu sohbet eki 98.500 doğru, ajan PDF'i read_file ile okudu 45.000 TL doğru. e2e_derin KALDI: PLANLA 0 geçerli
  plan (373 sn; aynı koşuda ilgisiz adımlar 270-310 sn → sunucu yükü şüphesi); hemen ardından plan-yalnız koşu 2 geçerli
  plan 141 sn → tekrar ölçülecek.
- B1 yeniden üretme testi (dal feat/b1-yeniden-uretme): project.is_bugfix + REPRO_RULE (planning_prompt; Proje + Derin) +
  deep.REPRO_VERIFY (doğrulama). GERÇEK önce/sonra (tests/e2e_yeniden_uretme_real_api.py, div sıfır hatası): ÖNCE iki
  planlayıcının 1. görevi doğrudan düzeltme (0/2) → SONRA ikisinde de "başarısız testi yaz, şu an kalıyor" (2/2), 93 sn.
  test_yeniden_uretme 13 (tetiklenen 6 + tetiklenmeyen 4…); mutasyon 4/4.
- B2 (alt ajan bulguları dosyaya) YAPILMADI, gerekçeli: Derin bağlam notu ≤3500 karakter, alt ajan istemi bunun 5-10
  katı; bulguyu dosyaya taşımak her alt ajana bir okuma adımı (~10 sn) ekler, kazanç yok → net olumsuz.
- B3 paralel görev (dal feat/b3-paralel-gorev, CAID): ProjectRunner bağımsız görevleri (bağımlılıkları bitmiş, hiç
  denenmemiş, son görev değil) `<veri>/worktrees/<dal>/gorev-N` git çalışma kopyalarında ThreadPoolExecutor ile aynı
  anda yapar (project_ui._run_task_in → deep.run_subagent mode="auto", test_check=True), kopyada doğrular + commit'ler,
  sonra SIRAYLA `merge --no-ff`; çakışma → `merge --abort` + görev seq_only ile sırayla, paralel denemenin dersi
  (PAR_NOTE) isteme geçer. Açılmaz: parallel ≤1, git yok, <3 görev, planda HİÇ bağımlılık yok (planlayıcı yazmamışsa
  "bağımsız" sanılan görev aslında sıralı olabilir), birincil kod modeli EVREN değil (arayüzsüz ajanın kullanımı
  maliyet/bütçe kaydına girmez). Kota kapısı (QuotaGate): pencere ≥%60 → sırayla; günlük kota / durdurma → deneme
  hakkı geri verilir. .venv/node_modules (yoksayılan) kopyaya dizin bağlantısı (junction) ile verilir; ÖLÇÜLDÜ:
  `git worktree remove --force` bağlantının hedefine girmiyor ama klasörü bağlantıyla bırakıyor → önce bağlantı
  kaldırılır, kalan artık Python 3.12 rmtree ile (bağlantı içine girmez) silinir. Eşitlik yaması: arayüzsüz ajana
  oturum ajanının ayarları (onaylı proje kuralları — onay ANA klasörün anahtarıyla, kopyada içerik aynıysa —, beceriler,
  güvenilmeyen klasörler, kurulum kipi, komut süre/çıktı sınırı, düzenleme denetimi, rol ipucu + profil, istatistik).
  test_paralel_gorev 14 + test_project_ui 3 yeni; mutasyon 29/30 (kaçan: çift katman korumanın ilk katmanı, bilinçli;
  ilk turda kaçan kurulum kipi / runner_kw iletimi → testler güçlendirildi). Riskli alan paketi 122 + güvenlik/döngü 54 geçti.
  GERÇEK (e2e_proje `--hedef paralel`, 3 bağımsız modül + tests + README, kabul denetimi önce doğru 8/8 / hatalı 7/8
  ile sınandı): `--paralel 3` → plan 5 görev (1-3 bağımsız), 1-3 AYNI ANDA 80 sn (tek tek 69+66+74 sn), toplam 725 sn,
  kabul 8/8. Sıralı tail (görev 4: 292 sn — ajanın `find /c "test_"` komutu tüm diski taradı, 120 sn zaman aşımı;
  görev 5: 220 sn) toplamı belirliyor. `find` sorunu ÖLÇÜM ORTAMI farkı: betik Git Bash'ten başlatıldı, PATH'te
  /usr/bin önde → Unix find; kullanıcı uygulamayı Başlat menüsünden açınca Windows find.exe (gerçekçi ölçüm PowerShell'den).
  `--paralel 1` (aynı hedef, planlayıcı bu kez 8 görev yazdı): yürütme 1490 sn, DURAKLATILDI, kabul 7/8 — görev 3 üç
  denemede takıldı: planlayıcının doğrulama komutu `python -c "…; 
import traceback;
try: …"` (düz metin `
`) →
  Python komutun KENDİSİNİ okuyamadı (SyntaxError, File "<string>"); check_command_broken yalnız PowerShell
  hatalarını tanıyordu → ayrı düzeltme (R-28). Karşılaştırma: paralel 630 sn / 8/8 · sıralı 1490 sn / 7/8 (plan
  şekli farklı; adil kıyas paralel bölümde: 3 görev 80 sn ↔ tek tek ~209 sn).

- Düzeltme (B3 ölçümünden): `python -c` satır içi kodun kendi yazım hatası artık bozuk doğrulama komutu sayılır
  (karar incelemeye; kayıt 2026-11-11-proje-python-c-…); PLAN_FORMAT: doğrulama tek satır. Testler 4+4+2, mutasyon 4/4.

## Test sonuçları
- A1: test_json_onarim 9, ilgili paket (qa, derin, scope, project, bozuk_json, kurulum) 112 geçti; mutasyon 7/7 (ilk turda 2
  kaçtı → iki test eklendi). Bulgu: json_repair TEK BAŞINA daha iyi değil — 2026-10-19 gerçek QA çıktısında (`'""'`)
  metni kesip alanı boş bıraktı; bizim okuyucu doğru okudu → ikisi yarışıyor.

## Sorunlar ve kayıtlar
- Yok (henüz).

## Sonraki motor için notlar
- Gerçek API (e2e_derin, zorluk, R-13) A aşaması sonunda toplu.
