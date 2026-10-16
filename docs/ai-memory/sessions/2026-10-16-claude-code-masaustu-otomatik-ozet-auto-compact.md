---
id: 2026-10-16-claude-code-masaustu-otomatik-ozet-auto-compact
tarih: 2026-10-16
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11 Pro 26200, Python 3.12.10, gerçek EVREN API
dal: feat/otomatik-ozet (feat/auto-mod üzerine; PR #3 birleşmeden önce)
sonuc: tamamlandi
---

# Otomatik özet (auto-compact)

## Görev
Kullanıcı: çalışma sekteye uğramasın diye otomatik /compact; ne zaman ve
yüzde kaç eşikte olacağına karar ver ve uygula.

## Yapılanlar
- Karar: özet yeni mesajdan ÖNCE; tur içinde yalnız güvenli noktada (araç
  sonuçları kaydedildikten sonra) ve sonra otomatik devam (≤3). Eşik
  min(bağlamın %75'i, 100k token); sert eşik min(%90, ×1,5).
- `agent/compaction.py` (politika, eşikler, özet isteği; eski araç çıktıları
  kısaltılarak sığdırılır), `runner.py` güvenli nokta denetimi
  (`hard_context_limit` → `context_limit`), `prompts.py` özet/devam istemleri.
- Arayüz: göndermeden önce özet, Esc iptalinde mesaj geri konur, otomatik devam
  notu, özet kartında neden/süre, bağlam göstergesinde eşik, `/compact [odak]`.
- Ayarlar: aç/kapa, yüzde, üst sınır, özet modeli (varsayılan deepseek-v4-flash).
- Kapanışta geç gelen sonuç düzeltmesi; test paketinde pencere temizliği.

## Test sonuçları
- `pytest -q`: 174/174 (9 yeni, `tests/test_auto_compact.py`), süre ~30 sn.
- `tests/e2e_compact_real_api.py`: 3/3 (deepseek-v4-flash 41 sn, qwen3.8 36 sn,
  glm-5.3 153 sn). İlk denemede glm-5.3 akışsız istekte koptu → akışlı yapıldı.
- Gerçek arayüzde otomatik özet tetiklenmesi uçtan uca DENENMEDİ (eşiğe ulaşmak
  için çok uzun gerçek konuşma gerekir); sahte istemcili arayüz testleri var.

## Sorunlar ve kayıtlar
- 2026-10-16-glm-5-3-akissiz-ozet-isteginde-baglanti-koptu
- 2026-10-16-kapanista-gec-sonuc-kapali-veritabanina-yaziyordu
- 2026-10-16-test-paketi-silinmeyen-pencerelerle-yavasliyordu
- Kendi testim yakaladı: tek büyük araç çıktısında mesaj sayısı az olduğu için
  özet atlanıyordu → otomatik özette alt sınır 2 mesaj.
- Yeni kural: R-16.

## Sonraki motor için notlar
- Bu dal feat/auto-mod üzerine kuruldu; PR #3 birleşince master'a PR açılmalı (R-15).
- Gerçek uzun bir oturumda otomatik özeti gözlemle; eşik değerlerini kullanıcı
  geri bildirimine göre ayarla (Ayarlar'dan değiştirilebilir).
