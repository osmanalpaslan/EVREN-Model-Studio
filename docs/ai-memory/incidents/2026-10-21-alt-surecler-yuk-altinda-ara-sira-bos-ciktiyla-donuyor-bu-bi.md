---
id: 2026-10-21-alt-surecler-yuk-altinda-ara-sira-bos-ciktiyla-donuyor-bu-bi
tarih: 2026-10-21
tur: ortam            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: izleniyor                # acik | izleniyor | cozuldu | kabul-edildi
alan: test
kaynak_motor: bilinmiyor
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Comodo güvenlik yazılımı, Python 3.12.10
etiketler: [kararsiz-test, alt-surec, comodo, ortam]
kurallar: [R-08]
---

# Alt süreçler yük altında ara sıra boş çıktıyla dönüyor (bu bilgisayar)

## Belirti
2026-10-21: `tests/test_uzun_isler.py` geliştirilirken alt süreçler (python -c, powershell) bir
dönemde 30 denemenin 17'sinde ÇIKIŞ 0 ve BOŞ çıktıyla döndü; daha sonra aynı komutlar 0/30.
Tam takımda `tests/test_mcp_ui.py::test_elle_sunucu_eklenir_oturum_araclari_gercek_surecten_gelir`
bir kez düştü (`'mcp__sahte__topla' in set()`: sahte MCP sunucu sürecinden araç listesi gelmedi);
tek başına çalıştırınca 7/7 geçti.

## Kök neden
Tahmin (doğrulanmadı): bilgisayardaki Comodo kapsama/davranış engelleyicisi yeni süreçleri ara sıra
sanal ortamda başlatıyor ya da çıktısını kesiyor. Kod kaynaklı olmadığı ölçüldü: doğrudan
`subprocess.run`, venv ve sistem Python'u, farklı env/cwd ile aynı belirti; kod değişmeden kendiliğinden
kayboldu.

## Çözüm
Kod değiştirilmedi (R-08). Testler çıkış kodunu "sıfır değil" diye denetler (PowerShell kendi çıkış
kodunu verir), tam eşitlik aramaz. Düşen test tek başına yeniden çalıştırılır.

## Kanıt
Oturum 2026-10-21 (Derin Mod/plan bekçisi): tam pytest 1 düşen (mcp_ui) → tek başına 7/7 geçti.

## Önleme
Bu bilgisayarda alt süreç testi düşerse önce tek başına yeniden çalıştır; tekrarlıyorsa Comodo
günlüğüne bak. İlgisiz kodu değiştirme (R-08).

## İlgili dosyalar
- tests/test_uzun_isler.py
- tests/test_mcp_ui.py
