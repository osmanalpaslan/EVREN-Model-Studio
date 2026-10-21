# Hesap kapama raporu — ölçüm araçları ve EVREN'in yazdığı rapor betiği

| Dosya | Ne |
|---|---|
| `hk_veri.py` | Gerçek dosyalarla aynı sütun yapısında SAHTE veri (1: 32 iş · 2: 96 iş, sütun/satır sırası karışık), kurallardan beklenen sonuç ve çıktı denetçisi. openpyxl gerekir. |
| `SKILL_DUZELTME_ONERILERI.md` | Skill'deki çelişki ve belirsizlikler için düzeltme önerileri (skill dosyası değiştirilmedi). |
| `rapor_uret.py` | EVREN'in (deepseek-v4.1-flash) yazdığı, her ay tekrar çalıştırılabilir rapor betiği. Skill + düzeltme önerilerini uygular. |
| `../e2e_hesap_kapama_real_api.py` | Gerçek API ölçümü: ajana raporu ürettirir (`--betik` ile betiği yazdırır) ve denetler. |

## Betiğin sınanması (2026-10-21)

Ajansız, denetçiyle: aynı veri 27/27 · aynı veri ikinci kez 27/27 ve çıktı hücre hücre aynı · 96 işlik karışık veri
27/27 · zorunlu sütun ("Hesap Uyum") eksik → çıkış kodu 2, dosya yazılmadı. Her çalıştırma ~0,5 sn.

## Gerçek veriyle kullanım (öneri)

1. Önce `SKILL_DUZELTME_ONERILERI.md`'deki önerileri onaylayın veya değiştirin; betik bu önerilere göre yazıldı
   (ör. Kapama Türü "Manuel", dağılımlar tüm kaynak işler üzerinden).
2. Betiği ve skill klasörünü gerçek dosyaların bulunduğu klasörün yanına kopyalayın; `kullanici_listesi.tsv`
   kaynak klasörde olmalı.
3. `python rapor_uret.py "<kaynak klasör>" "<çıktı.xlsx>"` — betik önce tanıdığı dosya ve sütunları yazar.
   İlk ay bu eşlemeyi kontrol edin. Gerçek başlıklar bozuksa (ör. `tcvknürün`) betik durursa EVREN'e
   "şu sütun eşlemesini ekle" deyip betiği güncelletin ve bu denetçiyle yeniden sınayın.
4. Gerçek 2.500 satırlık veriyle HENÜZ denenmedi; ilk gerçek çıktıyı eski raporla karşılaştırın.
