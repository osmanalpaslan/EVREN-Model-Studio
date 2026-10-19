---
id: 2026-10-19-yerel-web-sunucusu-turkce-403-iletisinde-yanitsiz-kaldi
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: mcp
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [http, latin-1, playwright]
kurallar: []
---

# Yerel web sunucusu Türkçe 403 iletisinde yanıtsız kaldı

## Belirti
ProjectWebServer `.env` isteğinde 403 yerine 5 sn zaman aşımı (test_yerel_web_sunucusu_gizli_dosyalari_vermez).

## Kök neden
Doğrulandı: `send_error(403, "… tarayıcıya …")` — HTTP durum satırı Latin-1 kodlanır, "ı" hata
verdi; işleyici iş parçacığı çöktü, bağlantı yanıtsız açık kaldı.

## Çözüm
İleti ASCII ("Forbidden (EVREN Studio: gizli dosya verilmez)").

## Kanıt
Test 21/21 geçti; elle: .env/.git/config/%2Eenv → 403.

## Önleme
HTTP başlık/durum satırına Türkçe karakter yazma.

## İlgili dosyalar
src/evren_studio/agent/mcp.py (ProjectWebServer)
