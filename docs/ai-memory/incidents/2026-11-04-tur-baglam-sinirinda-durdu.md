---
id: 2026-11-04-tur-baglam-sinirinda-durdu
tarih: 2026-11-04
tur: risk            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: bilinmiyor
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gozlem]
kurallar: []
---

# Tur bağlam sınırında durdu

## Belirti
Gözlem ajanından (uygulama çalışırken, otomatik ve temizlenmiş):
tur_sonu
Konum:
- (yığın izi yok)
Ayrıntı:
- durma: context_limit
- model: deepseek-v4.1-flash
- rol: kod
- adim: 18
- mod: auto

## Kök neden
1. **Yapısal (doğrulandı, kod okuma + birim testi):** tur içi kısaltma (`trim_for_context`) yalnız modelin bağlamının
   %70'inde başlıyordu; deepseek-v4.1-flash'ta (1M bağlam) bu ~700k token. Tur içi sert sınır ise
   `min(bağlam %90, yumuşak × 1,5)` = ~150k. Yani sert sınır hep önce geliyor, eski araç çıktıları HİÇ kısaltılmadan
   tur duruyor, özet (ayrı, yavaş model çağrısı) yapılıyor ve turun ayrıntısı özete sıkışıyordu. Araç çıktısı adım
   başına 20.000 karaktere kadar (Godot/3B gibi büyük çıktılı işte ~18 adımda dolar).
2. **Bu 6 kaydın zamanlaması (tahmin):** 2026-11-03 19:56–20:05 arası 9 dakikada 6 kez — aynı akşam maraton F
   bilerek çok düşük özet eşiğiyle (`MARATON_OZET_ESIK=8000`) koşuyordu (CHALLENGE_RESULTS "Faz unutma ölçümü").
   Kayıtların çoğu o deneyin yan ürünü olabilir; gerçek kullanımda sıklığı ölçülmedi.

## Çözüm
Dal `feat/hiz-adim-azaltma` (Madde 7): `AgentRunner` tur içinde eski araç çıktılarını sert sınırın %70'ine
(`TRIM_OF_HARD`) inene kadar kısaltır (son 8 mesaj korunur, kalıcı kayıt değişmez); sert sınır denetimi modele
gerçekten giden (kısaltılmış) geçmişe bakar → tur yalnız kısaltma yetmezse durur. Kısaltma olunca döngü bekçisinin
tekrar sayacı sıfırlanır (kısaltılan çıktıyı yeniden okumak meşru, "aynı sonuçla tekrar" değil).

## Kanıt
Gözlem `a0d2b1645e16` (dal gozlem-kayitlari): 6 kez, 1 makine, ilk 2026-11-03T19:56:29+00:00, son 2026-11-03T20:05:03+00:00,
sürümler 0.2.0+cc74648.

Birim: `tests/test_hiz_adim.py` (kısaltma tetiklenir/tetiklenmez, kısaltma yetmezse yine durur, kısaltılan çıktıyı
yeniden okumak döngü sayılmaz / kısaltma yokken sayılır); 6 mutasyonun 6'sı yakalandı.

## Önleme
`tests/test_hiz_adim.py`; mevcut `test_auto_compact::test_ajan_dongusu_guvenli_noktada_durur` (kısaltılamayan dev
çıktıda yine güvenli noktada durur) korunur.

## İlgili dosyalar
- src/evren_studio/agent/runner.py (`trim_for_context`, `_trim_budget`, `_visible`, `TRIM_OF_HARD`)
- tests/test_hiz_adim.py
