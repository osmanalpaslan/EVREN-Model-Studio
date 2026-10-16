---
id: 2026-10-16-claude-code-masaustu-otomatik-mod-korumali-dosyalar-klasor-ba
tarih: 2026-10-16
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11 Pro 26200, Python 3.12.10, gerçek EVREN API
dal: feat/auto-mod
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Otomatik mod, korumalı dosyalar, klasör bağlama

## Görev
Kullanıcı: "Otomatik düzenleme" ne işe yarıyor; Claude Code'daki Auto ve
Manuel modlarını ekleyelim (mevcut modlar kalsın). Kararlar (kullanıcı):
denetim YALNIZ KURALLARLA, adlar Claude Code gibi, önce Auto mod (OpenAI/
Anthropic planından önce). Ayrıca "dosya erişimi yok" sorunu incelendi.

## Yapılanlar
- Claude Code izin modları resmî belgeden doğrulandı (claude-code-guide).
- `agent/commands.py`: kural tabanlı sınıflandırıcı (riskli kalıplar, proje
  dışı yollar, yönlendirme/ikame, güvenli liste; alt komut bazında).
- `agent/permissions.py`: yeni anahtarlar manuel/kabul/plan/auto,
  `normalize_mode` (onayli→manuel, otomatik→kabul), korumalı yazma ve gizli
  okuma listeleri, gerekçeli kararlar.
- `runner.py`: gizli dosya okuma onayı, yol tabanlı yazma kararı, komut
  kararında proje kökü, onay gerekçesi, `auto_approved` işareti; aramada
  gizli dosyalar atlanır.
- Arayüz: 4 mod (Claude Code adları), `/manuel /kabul /plan /otomatik`,
  Otomatik moda geçişte açıklama notu, onay kutusunda "Neden soruluyor",
  araç kartında "otomatik" etiketi, klasörsüz oturuma "Proje klasörü bağla".
- Klasörsüz sohbet istemi: model dosya istenirse bağlama düğmesini önerir.
- "Dosya erişimi yok" teşhisi: yeni sürüm bu makinede hiç çalışmamıştı; PR #2
  birleştirilmemişti (kullanıcı onayıyla birleştirildi, `c3a17b1`).

## Test sonuçları
- `pytest -q`: 165/165 (49 yeni: `tests/test_auto_mode.py`).
- Gerçek API: `e2e_ui_real_api.py` 15/15 (Otomatik mod adımı: Get-ChildItem
  onaysız çalıştı, 0 onay); `e2e_agent_real_api.py deepseek-v4-flash glm-5.3` 4/4.
- Ekran görüntüsü (windows platformu) incelendi: build/shots/real_otomatik_mod.png.

## Sorunlar ve kayıtlar
- 2026-10-16-duzenleme-modu-gizli-ve-yapilandirma-dosyalarini-korumuyordu (çözüldü)
- 2026-10-16-kullanici-dosya-erisimi-yok-yaniti-aldi (çözüldü)
- Yeni kurallar: R-14, R-15.

## Sonraki motor için notlar
- OpenAI/Anthropic entegrasyon planı kullanıcı onayını bekliyor; araştırma:
  docs/knowledge/PROVIDERS_RESEARCH.md (kararlar: tam entegrasyon, gruplu
  model seçici, aylık bütçe sınırında durdurma, sahte testler).
- Otomatik mod kural tabanlı; güvenli listeyi genişletirken RISKY kalıpları
  önce kontrol edildiğini unutma ve `tests/test_auto_mode.py`'ye örnek ekle.
- Güvenli listedeki test/derleme komutları projenin kodunu çalıştırır (SECURITY.md).
