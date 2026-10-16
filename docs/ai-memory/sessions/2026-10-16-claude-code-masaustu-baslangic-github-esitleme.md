---
id: 2026-10-16-claude-code-masaustu-baslangic-github-esitleme
tarih: 2026-10-16
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/uzak-depo-esitleme
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# baslangic: GitHub ile otomatik eşitleme

## Görev
Kullanıcı: "Diğer bilgisayarda güncelledim desem fark edip devam edemez mi?" →
"Hemen ekle çünkü ben yapamayabilirim." Motor, başka bilgisayarda yapılıp
GitHub'a gönderilen işi kullanıcı söylemese de fark etmeli.

## Yapılanlar
- tools/ai_memory.py: `sync_with_remote()` + `_git_run()`; `baslangic` önce
  eşitler, sonra hafızayı okur; `--esitleme-yok` bayrağı. Yalnız güvenli işlem
  (ileri sarma, birleşmiş daldan master'a geçiş); veri kaybettiren komut yok.
- AGENTS.md §1: eşitleme çıktısını okuma ve "!" satırlarında kullanıcıya sorma adımı.
- RULES.md: R-18. CHANGELOG, PROJECT_STATE.

## Test sonuçları
- `tests/test_ai_memory_sync.py` 10/10; tam paket `pytest -q` 212/212; `denetle` DENETİM_TAMAM.
- İlk denemede bir test Windows'ta salt okunur git nesnelerini silemediği için
  düştü (PermissionError); uzak adres var olmayan yola çevrilerek düzeltildi.

## Sorunlar ve kayıtlar
- 2026-10-16-motor-baska-bilgisayarda-yapilan-isleri-fark-etmiyordu (çözüldü)

## Sonraki motor için notlar
- `baslangic` ağa çıkar (git fetch). Ağ yoksa uyarı verip devam eder.
- "!" ile başlayan eşitleme satırı varsa kullanıcıya sormadan reset/stash/
  checkout -- gibi geri dönüşsüz komut çalıştırma (R-18).
- Değişiklik `feat/uzak-depo-esitleme` dalında.
