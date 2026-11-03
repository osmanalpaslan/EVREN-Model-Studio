---
id: 2026-11-01-token-tahmini-baglami-yuzde-40-60-kucuk-gosteriyordu-otomati
tarih: 2026-11-01
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, EVREN API
etiketler: [baglam, ozet, token, auto-pro]
kurallar: [R-32, R-34]
---

# Token tahmini bağlamı yüzde 40-60 küçük gösteriyordu, otomatik özet geç tetikleniyordu

## Belirti
Kullanıcı: "auto pro motorunda bağlam uzayan projelerde şişiyor; /compact yapamıyorum veya otomatik yapılmıyor."
Taban ölçümünde (maraton A/B/C, auto-pro) hiç otomatik özet olmadı (özet=0); 1M token'lık oturumda özet
isteği sığmadı (2026-10-29 kaydı).

## Kök neden
Doğrulandı (gerçek `usage.prompt_tokens` ölçümü, 2026-11-01): `runner.CHARS_PER_TOKEN = 3.5` varsayıyordu;
EVREN Türkçe metni 2,55, kodu 3,1-3,5, araç çıktısını 2,2, sistem istemi + araç tanımlarını 2,16 karakter/token
sayıyor. Ayrıca sistem istemi + araç tanımları (ilk istek 5.620 token) sabit 2.500 token sayılıyordu. Sonuç:
bağlam göstergesi, özet eşiği, kırpma bütçesi ve tur içi sert sınır gerçek boyutun ~%60-70'ini görüyordu.

## Çözüm
- Varsayılan oran 2,6; sistem+araç ek yükü 6.000 token (ölçüm 5.620).
- Her model yanıtındaki gerçek girdi token'ıyla model başına oran ve ek yük öğrenilir (`runner.calibrate`,
  yumuşatılmış ortalama, 1,8-4,5 sınırı); `estimate_tokens`, `trim_for_context`, `_history_tokens` ve
  `compaction.history_tokens` bunu kullanır. Model bilinmiyorsa ölçülmüşlerin en temkinlisi.
- Çok parçalı (görsel) içerikte yalnız metin sayılır (base64 sayılmaz).
- /clear önerisindeki ×1,35 telafi çarpanı kaldırıldı (artık çift sayardı).

## Kanıt
tests/test_token_kalibrasyonu.py (6 test; eski hesap 250k karakterlik Türkçe geçmişte eşiği aşmıyordu, yeni
hesap aşıyor; küçük geçmişte tetiklenmiyor; gerçek tur akışında sahte usage'tan 2,2 öğreniliyor). Mutasyon:
kalibrasyon kapatılınca 4, eski 3,5 oranında 2 test kırıldı. Gerçek: maraton D 25/25 (bağlam ~40k; eski hesap %13 eksik, yeni varsayılan %24 fazla, kalibrasyonla
gerçeğe iner); özetli maraton A (`MARATON_OZET_ESIK=20000`) 10/10, otomatik özet 1 kez tetiklendi (2026-11-01).

## Önleme
R-34: token/bağlam hesabını gerçek `usage` ile kalibre et; sabit oran/ek yük varsayma.

## İlgili dosyalar
- src/evren_studio/agent/runner.py
- src/evren_studio/agent/compaction.py
- src/evren_studio/ui/session_view.py
