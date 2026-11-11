---
id: 2026-11-11-proje-python-c-dogrulamasinin-kendi-yazim-hatasi-gorevi-taki
tarih: 2026-11-11
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [proje, dogrulama, R-28]
kurallar: [R-28]
---

# Proje: python -c dogrulamasinin kendi yazim hatasi gorevi takiltiyordu

## Belirti
B3 ölçümünde (`tests\e2e_proje_real_api.py auto --hedef paralel --paralel 1`) görev 3 (`sayi.py`) üç denemede de
"doğrulama komutu başarısız (çıkış 1)" ile TAKILDI, ona bağlı 3 görev atlandı, proje duraklatıldı (kabul 7/8). İş
aslında doğruydu (kabul denetiminde asal_mi/faktoriyel geçti). Çıktı:
`File "<string>", line 1 … SyntaxError: unexpected character after line continuation character`.

## Kök neden
Doğrulandı: planlayıcı (deepseek-v4.1-flash) doğrulamayı `python -c "import sayi; assert …; \nimport traceback;\ntry: …"`
biçiminde yazdı; `\n` gerçek satır sonu değil düz metin → Python komutun KENDİSİNİ okuyamadı. `check_command_broken`
yalnız PowerShell'in komut satırı hatalarını (At line:N + ParserError…) tanıyordu; R-28'deki "doğrulama komutunun
kendi sözdizimi hatası görev başarısızlığı değildir" kuralı `python -c` için uygulanmıyordu.

## Çözüm
`project._python_inline_broken`: hata satırından (SyntaxError/IndentationError/TabError) önceki SON `File "…"`
"<string>" ise satır içi kod bozuk → karar incelemeye bırakılır (mevcut R-28 yolu). İçe aktarılan modülün kendi yazım
hatası (`File "…\sayi.py"`) ve assert başarısızlığı gerçek başarısızlık kalır. PLAN_FORMAT'a kural: doğrulama tek
satır; `python -c` yalnız tek satırlık ifade, çok satırlı denetim test dosyasına.

## Kanıt
tests/test_derin_duzeltmeler.py: tetiklenen 4 (gerçek çıktı dahil) + tetiklenmeyen 4 + gerçek yürütücü akışı
(bozuk python -c doğrulaması → görev 1 denemede bitti) + plan biçimi; mutasyon 4/4.

## Önleme
R-28 kapsamı genişledi (yeni kural gerekmedi). Bundan sonra yeni bir doğrulama dili/çalıştırıcısı görülürse
check_command_broken'a aynı "komutun kendisi mi, işin mi" ayrımıyla eklenir.

## İlgili dosyalar
- src/evren_studio/agent/project.py (check_command_broken, _python_inline_broken, PLAN_FORMAT)
- tests/test_derin_duzeltmeler.py
