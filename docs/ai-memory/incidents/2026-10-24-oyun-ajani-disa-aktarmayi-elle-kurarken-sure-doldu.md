---
id: 2026-10-24-oyun-ajani-disa-aktarmayi-elle-kurarken-sure-doldu
tarih: 2026-10-24
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, gerçek EVREN API (deepseek-v4.1-flash)
etiketler: [F7, godot, R-25, verimlilik]
kurallar: [R-25]
---

# Oyun ajanı dışa aktarmayı elle kurarken süre doldu

## Belirti
Gerçek ajan görevi (güvenilmeyen mod → Godot → EXE + PWA): model dönüştürüldü, sahne kuruldu, ama 18 adım / 15 dk
sonunda EXE ve PWA yoktu (3/5). Ajan export_presets.cfg'yi, içe aktarmayı ve doğrulama betiklerini elle kurmaya
çalışıyordu (deepseek ~50 sn/adım).

## Kök neden
Doğrulandı (döküm): en hataya açık kısım (ön ayar dosyası, içe aktarma, iki dışa aktarma, hata ayıklama) çok adım
gerektiriyordu; istem yalnız komutları tarif ediyordu.

## Çözüm
`godot_export` aracı: export_presets.cfg yoksa hazır ön ayar (EXE + PWA, gl_compatibility), içe aktarma, dışa
aktarma ve hata satırları tek adımda. Sonuç: aynı görev 7/7 · 297 sn · 13 adım. godot-mcp açıkken de 7/7 ama model
MCP araçlarını hiç çağırmadı ve 36 adım / 474 sn sürdü → godot-mcp varsayılan kapalı (R-25).

## Kanıt
build/oyun_ajan/auto-pro/rapor.json (oyun_mod 7/7, oyun_mod_mcp 7/7, mcp__godot çağrısı 0).

## Önleme
Ajanın tekrar tekrar elle kurduğu çok adımlı işi tek araca indir; aracın modelce gerçekten seçildiğini ölç (R-25).

## İlgili dosyalar
- src/evren_studio/agent/runner.py (_run_godot_export), src/evren_studio/agent/godot_sablon.py
