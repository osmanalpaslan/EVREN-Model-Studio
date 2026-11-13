---
id: 2026-11-13-test-bekcisi-bayat-pyc-ile-eski-kodu-kosturuyordu
tarih: 2026-11-13
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [test-bekcisi, pyc, kararsiz-test]
kurallar: [R-08]
---

# Test bekcisi bayat pyc ile eski kodu kosturuyordu

## Belirti
Tam takımda (2026-11-13 21:53) `tests/test_qa_araclari.py::test_bekci_bozulan_testi_bir_kez_bildirir` düştü
(`len(client.calls) == 3` yerine 2): test bekçisi, ajanın `a + b` → `a - b` düzenlemesinden sonra "testler geçti" dedi.
Tek başına koşunca geçiyordu (kararsız). Senaryo döngüde 8 kez koşturulunca 1'inde yakalandı.

## Kök neden
Doğrulandı. Tur başı taban test koşusu (`_test_baseline_once`) projenin `__pycache__/hesap.cpython-312.pyc`
dosyasını üretir. Python .pyc'yi kaynağın mtime'ı (saniye) + boyutuyla doğrular. Ajanın düzenlemesi aynı saniyede ve
aynı boyutta yazılınca .pyc geçerli sayıldı; tur sonu test koşusu ESKİ (sağlam) kodu çalıştırdı → bozuk değişiklik
"testler geçti" göründü. Gerçek kullanımda da olabilir (ajan hızlı, küçük düzeltmeler sık aynı boyutta).

## Çözüm
`agent/tools.py` → `drop_pycache(path)`: .py yazılınca/geri alınınca/silinince `__pycache__/<ad>.*.pyc` (tüm Python
sürümleri) silinir. Çağrıldığı yerler: `ToolBox.apply_change`, `revert_file`, yan paneldeki "Kaydet"
(`ui/side_panel.py`). `PYTHONDONTWRITEBYTECODE` yalnız yeni .pyc yazmayı keser, var olan bayat kopyayı okumayı
engellemez — bu yüzden seçilmedi.

## Kanıt
- `tests/test_bekciler_c.py::test_ayni_saniye_ayni_boyut_duzenleme_bayat_pyc_ile_eski_kodu_kosturmaz` (en kötü durum:
  `os.utime` ile mtime + boyut aynı) → düzeltmesiz yeni kod koşmuyor, düzeltmeyle koşuyor.
- Mutasyon 4/4 (çağrıyı kaldır, .py denetimini kaldır, glob kalıbını boz, test yardımcısını boz).
- Tam takım 22:09: 1419 geçti.

## Önleme
Test. R-08'e not: tek başına geçmesi kararsız testi temize çıkarmaz; senaryoyu döngüde koşturup ara durumu yazdır.

## İlgili dosyalar
- src/evren_studio/agent/tools.py
- src/evren_studio/ui/side_panel.py
- tests/test_bekciler_c.py
- tests/test_qa_araclari.py
