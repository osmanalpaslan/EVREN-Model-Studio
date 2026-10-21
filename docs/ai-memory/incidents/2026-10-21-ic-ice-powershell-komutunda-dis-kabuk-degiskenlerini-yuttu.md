---
id: 2026-10-21-ic-ice-powershell-komutunda-dis-kabuk-degiskenlerini-yuttu
tarih: 2026-10-21
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: bilinmiyor
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PowerShell 5.1, Python 3.12.10
etiketler: [powershell, kabuk, kacis, run-command]
kurallar: [R-28]
---

# İç içe PowerShell komutunda dış kabuk $ değişkenlerini yuttu

## Belirti
Hesap kapama oturumunda 23 araç hatasının 7'si aynı biçimdeydi: model `powershell -NoProfile -Command "$t=(Get-Content
out\isler.tsv).Count; Write-Output $t"` yazdı; çıktı `= : The term '=' is not recognized`, `ParameterBindingException`,
`foreach( in )` gibi. Model kendisi de fark etti ("Kabuk `$` değişkenlerini yutuyor; betikleri dosya olarak yazıp
-File ile çalıştıracağım") ama planın DOĞRULAMA komutları da bu biçimdeydi. Kanıt kaynağı: kullanıcının EVREN Studio oturumu #16 (2026-10-21 13:50-15:40, Derin Mod, hesap kapama raporu; veritabanı kopyası ve klasördeki EVREN_DERIN.md / EVREN_RAPOR.md / EVREN_PLAN.md incelendi).

## Kök neden
Doğrulandı. `tools.shell_argv` komutu zaten `powershell.exe -Command <komut>` ile çalıştırıyor. Komut bir PowerShell
daha sarınca, DIŞ kabuk çift tırnaklı dizgedeki `$t`'yi kendi (boş) değişkeniyle değiştirip iç kabuğa
`=(Get-Content …).Count; Write-Output` gönderiyor.

## Çözüm
`tools.unwrap_powershell`: TÜM komut tek bir `powershell|pwsh … -Command "…"` çağrısıysa iç betik doğrudan
çalıştırılır (`\"` → `"`). `-File`, `-EncodedCommand`, tek tırnak ve birden çok komut içeren belirsiz durumlara
dokunulmaz. İstemler: "zaten PowerShell içindesin, sarmalama; uzun iş için -File" (ajan kuralları ve planlama).

## Kanıt
`tests/test_derin_duzeltmeler.py`: 4 açılan + 6 dokunulmayan biçim; oturumdaki doğrulama komutu gerçek PowerShell'de
artık `3` döndürüyor (`test_ic_ice_komut_gercekte_calisir`).

## Önleme
R-28.

## İlgili dosyalar
- src/evren_studio/agent/tools.py
- src/evren_studio/agent/prompts.py
- src/evren_studio/agent/project.py
