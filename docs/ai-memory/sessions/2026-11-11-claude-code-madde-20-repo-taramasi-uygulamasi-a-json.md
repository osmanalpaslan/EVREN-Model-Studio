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

## Test sonuçları
- A1: test_json_onarim 9, ilgili paket (qa, derin, scope, project, bozuk_json, kurulum) 112 geçti; mutasyon 7/7 (ilk turda 2
  kaçtı → iki test eklendi). Bulgu: json_repair TEK BAŞINA daha iyi değil — 2026-10-19 gerçek QA çıktısında (`'""'`)
  metni kesip alanı boş bıraktı; bizim okuyucu doğru okudu → ikisi yarışıyor.

## Sorunlar ve kayıtlar
- Yok (henüz).

## Sonraki motor için notlar
- Gerçek API (e2e_derin, zorluk, R-13) A aşaması sonunda toplu.
