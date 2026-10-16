---
id: 2026-10-16-llm-markdown-listeleri-paragraf-gorunuyordu
tarih: 2026-10-16
tur: hata
onem: dusuk
durum: cozuldu
alan: ui/markdown
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, python-markdown 3.11, gerçek EVREN yanıtı (deepseek-v4-flash)
etiketler: [markdown, llm-ciktisi]
kurallar: []
---

# LLM'lerin boş satırsız yazdığı listeler paragraf olarak görünüyordu

## Belirti
Gerçek API yanıtında "**Yapılan değişiklik:**" satırının hemen altındaki
"- …" maddeleri liste yerine tek paragrafa karışmış göründü.

## Kök neden
Doğrulandı: python-markdown, liste öğesinden önce boş satır ister. EVREN
modelleri (ve çoğu LLM) başlık/kalın satırın hemen altına boş satırsız liste
yazıyor.

## Çözüm
`markdown_view.normalize_llm_markdown`: kod blokları dışında, liste
öğesinden önce boş satır yoksa ekler.

## Kanıt
`tests/test_ui_pages.py::test_llm_markdown_listesi_bos_satirsiz_da_liste_olur`.

## Önleme
Model çıktısını gösteren yeni bir yüzey eklenirse aynı normalleştirmeyi kullan.

## İlgili dosyalar
src/evren_studio/ui/markdown_view.py
