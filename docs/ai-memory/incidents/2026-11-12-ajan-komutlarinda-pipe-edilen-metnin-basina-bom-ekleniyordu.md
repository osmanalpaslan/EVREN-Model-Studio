---
id: 2026-11-12-ajan-komutlarinda-pipe-edilen-metnin-basina-bom-ekleniyordu
tarih: 2026-11-12
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, Windows PowerShell 5.1
etiketler: [powershell, kodlama, bom, R-01]
kurallar: [R-01]
---

# Ajan komutlarında pipe edilen metnin başına BOM ekleniyordu

## Belirti
"girdi" düzeltmesinin gerçek komut testinde `'Ali' | python oyun.py` çıktısı "Merhaba Ali" değil
"Merhaba ﻿Ali" oldu: programa gelen metnin başında görünmez BOM (U+FEFF) vardı.

## Kök neden
Doğrulandı: `tools.shell_argv` her ajan komutunun başına `$OutputEncoding=[System.Text.Encoding]::UTF8` koyuyordu;
.NET'in hazır UTF8 nesnesi BOM'LU (önsözlü) kodlamadır → PowerShell bir yerel programa boruyla (pipe) metin
gönderirken başa BOM ekler. Etki: ajanın `Get-Content veri.csv | python isle.py`, `'girdi' | program`,
`... | node x.js` gibi tüm boru komutlarında ilk satır/alan sessizce bozuluyordu (ilk sütun adı, ilk sayı, ilk kelime
eşleşmiyor) — hata mesajı da vermeden.

## Çözüm
`[Console]::OutputEncoding` ve `$OutputEncoding` → `[System.Text.UTF8Encoding]::new($false)` (BOM'suz UTF-8;
PowerShell 5.1 destekler). Etkileşimli Kabuk (agent/ptyshell.py) kullanıcının kendi PowerShell ayarlarıyla çalışır;
bu ayar yalnız ajan komutları içindir.

## Kanıt
tests/test_zorluk_denetleyici.py::test_gercek_komut_girdi_verilince_ipucu_yok (gerçek PowerShell + python: "Merhaba Ali"
tam eşleşir); mutasyonda eski kodlama geri konunca test düşüyor. Komut/araç risk paketi (test_agent_tools,
test_client_tools_sessions, test_f6_guvenlik, test_uzun_isler, test_f3_verimlilik, test_auto_mode, test_agent_runner)
geçti.

## Önleme
R-01 (Türkçe dosyayı PowerShell 5.1 ile BOM'lu yazma) ile aynı kökten: PowerShell'de "UTF8" dendiğinde BOM'lu kodlama
gelir. Kural: PowerShell'e kodlama verirken her zaman `UTF8Encoding($false)`.

## İlgili dosyalar
- src/evren_studio/agent/tools.py (shell_argv)
- tests/test_zorluk_denetleyici.py
