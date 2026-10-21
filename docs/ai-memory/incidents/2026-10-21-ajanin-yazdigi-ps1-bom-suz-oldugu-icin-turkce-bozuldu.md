---
id: 2026-10-21-ajanin-yazdigi-ps1-bom-suz-oldugu-icin-turkce-bozuldu
tarih: 2026-10-21
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: bilinmiyor
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PowerShell 5.1, Python 3.12.10
etiketler: [powershell, bom, kodlama, turkce]
kurallar: [R-01]
---

# Ajanın yazdığı .ps1 BOM'suz olduğu için Türkçe bozuldu

## Belirti
Ajan betikleri "BOM tuzağına düşmemek için" yalnız ASCII yazdı, Türkçe metni ayrı dosyalara taşıdı
(`out/eslesme_metin.txt`), `_kaynak_pua2.ps1` gibi yardımcıları 5 kez düzenledi; yine de "Oluşturma Tarihi" sütun adı bozuk kodlanmış karakterlerle okunduğu için anahtarlarla "Index operation failed" aldı. Kanıt kaynağı: kullanıcının EVREN Studio oturumu #16 (2026-10-21 13:50-15:40, Derin Mod, hesap kapama raporu; veritabanı kopyası ve klasördeki EVREN_DERIN.md / EVREN_RAPOR.md / EVREN_PLAN.md incelendi).

## Kök neden
Doğrulandı. Windows PowerShell 5.1 BOM'suz .ps1'i ANSI (cp1254) okur; `write_file` yeni dosyayı BOM'suz UTF-8
yazıyordu. Ölçüm: aynı betik BOM'suz 24, BOM'lu 19 karakter uzunluk basıyor ("Açık işler Sözleşme" = 19).

## Çözüm
`tools.needs_ps_bom`: ASCII dışı karakter içeren .ps1/.psm1/.psd1 UTF-8 BOM ile yazılır (düzenlemede de BOM'a
geçer); okurken BOM gizlenir. İstem: ".ps1 otomatik BOM'lu; Türkçe karakter kullanabilirsin".

## Kanıt
`test_turkce_ps1_bom_ile_yazilir_digerleri_bomsuz`, `test_bomlu_ps1_turkceyi_bozmadan_calisir` (bilinen kötü: 24).

## Önleme
R-01'in ajan tarafı: PowerShell 5.1'e verilen Türkçe betik BOM'lu olmalı.

## İlgili dosyalar
- src/evren_studio/agent/tools.py
