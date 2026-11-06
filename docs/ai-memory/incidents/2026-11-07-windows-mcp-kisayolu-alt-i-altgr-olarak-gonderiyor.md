---
id: 2026-11-07-windows-mcp-kisayolu-alt-i-altgr-olarak-gonderiyor
tarih: 2026-11-07
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, Windows-MCP 0.8.8 (Python 3.14 venv), Türkçe klavye
etiketler: [masaustu, windows-mcp, klavye]
kurallar: []
---

# Windows-MCP kisayolu Alt'i AltGr olarak gonderiyor

## Belirti
Gerçek masaüstü ajan denemesi (`tests/e2e_masaustu_real_api.py ajan`, 2026-11-07 01:45) 4/5: "pencere kapandı"
KALDI. Ajan `Shortcut alt+f4` çağırdı, araç "Pressed alt+f4." dedi, pencere açık kaldı. Ajan kapanmayı
`Snapshot use_ui_tree=false` ile "doğruladı" ve kullanıcıya "pencere kapatıldı" dedi (yanlış iddia).

## Kök neden
Doğrulandı (elle üretildi): 0.8.8 `Desktop.shortcut` "alt+f4" → `uia.SendKeys("{Alt}{F4}")`; uia her tuşu
`KeyboardEventFlag.ExtendedKey` ile basar → genişletilmiş VK_MENU = sağ Alt = Türkçe klavyede AltGr (Ctrl+Alt) →
Alt+F4 olmuyor. Pencere öndeyken aynı çağrı (ve "{Alt}({F4})") kapatmadı; bayraksız `keybd_event` Alt↓ F4↓ F4↑ Alt↑
kapattı. İkinci sorun: `use_ui_tree=false` hızlı yolu pencere listesini hiç okumaz (service.py "Fast path"), hep
"No windows found" döner.

## Çözüm
`wmcp_baslatici.patch_shortcut`: çok tuşlu kısayolda tuşlar VK'ye çevrilir (SpecialKeyNames + VkKeyScanW),
yalnız gerçekten genişletilmiş tuşlar (oklar, gezinme, Win) bayraklı; değiştiriciler basılı tutulur, bırakma
`finally` içinde ters sırayla. Tek tuş ve çözülemeyen tuş özgün yola gider; kullanıcı denetimi
(checkpoint/record_step) korunur. DESKTOP_PROMPT: kapanmayı WindowText ile doğrula, `use_ui_tree=false` ile değil.

## Kanıt
tests/test_wmcp_baslatici.py (+4 test), mutasyon 5/5; gerçek ajan yeniden 5/5, 75 sn (Shortcut alt+F4 → WindowText
"not found").

## Önleme
Testler: değiştiriciler bayraksız, hata olsa da bırakma, tek tuş özgün yol, istemde doğrulama yolu.

## İlgili dosyalar
src/evren_studio/agent/wmcp_baslatici.py, src/evren_studio/agent/mcp.py, tests/test_wmcp_baslatici.py
