---
id: 2026-10-17-npm-ile-kurulan-araclarin-ps1-kabugu-powershell-betik-politi
tarih: 2026-10-17
tur: ortam            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [powershell, execution-policy, npm, ortam-denetimi]
kurallar: []
---

# npm ile kurulan araçların .ps1 kabuğu PowerShell betik politikasına takılıyor

## Belirti
Ortam denetimi gerçek testinde ajan yarn'ı `install_program` ile kurdu, ardından
`yarn --version` çıkış 1: "yarn.ps1 cannot be loaded because running scripts is
disabled on this system". Model `yarn.cmd` deneyerek kendisi aştı (fazladan adım).

## Kök neden
Doğrulandı: bu bilgisayarda `Get-ExecutionPolicy` = Restricted; npm global
araçlar için .ps1 + .cmd kabuk yazıyor, PowerShell .ps1'i seçiyor.

## Çözüm
Denenen ve UYGULANMAYAN: run_command'a `-ExecutionPolicy Bypass` eklemek —
Claude Code güvenlik denetimi "güvenliği zayıflatma" diye engelledi; doğru
karar (Windows korumasını atlatır). Uygulanan: sistem istemindeki ortam
bölümü ve npm kurulumu sonucu modele "`.cmd` uzantısıyla çağır (pnpm.cmd,
yarn.cmd)" der.

## Kanıt
Düzeltme sonrası gerçek API (deepseek-v4-flash, Otomatik kurulum): install_program
→ `yarn.cmd --version` doğrudan başarılı, hatalı deneme yok.

## Önleme
environment.prompt_section kuralı; test_environment.py istem testi.

## İlgili dosyalar
- src/evren_studio/agent/environment.py
- src/evren_studio/agent/runner.py
