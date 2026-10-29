---
id: 2026-10-29-buyuk-oturumda-compact-calismiyor-mesajlar-baglam-asimiyla-r
tarih: 2026-10-29
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [compact, ozet, baglam, clear, proje-ajani]
kurallar: [R-32]
---

# Büyük oturumda /compact çalışmıyor, mesajlar bağlam aşımıyla reddediliyordu

## Belirti
Kullanıcı (2026-10-29): Derin Mod/Proje ajanıyla 12 görevlik oyun projesi (oturum 12,
1.357 mesaj) bitti; "oyunu hangi dosyaya exe olarak oluşturdun?" sorusu 4 kez cevapsız
kaldı. Hata kayıtları: EVREN 400 "İstem (1062522) + çıktı tavanı (65536) modelin bağlam
penceresini (1048576) aşıyor" (deepseek-v4.1-flash ×3, qwen3.8-flash-next ×1).
Kullanıcı /compact da yapamadı ("izin vermiyor"), /clear istedi.

## Kök neden
Doğrulandı:
1. Proje ajanı her görevi temiz bağlamla (`history_from`) çalıştırdığı için görevler
   sorunsuzdu ama oturum kaydı hiç özetlenmeden ~1M token'a büyüdü.
2. Normal mesajda gönderim öncesi otomatik özet tetiklendi; ancak özet isteği
   (`build_summary_request`) yalnız eski araç çıktılarını kısaltıyordu — araç
   parametrelerindeki dosya içerikleri ve 25k karakterlik görev mesajları duruyordu:
   uygulama tahmini 724k, EVREN sayımı >1M → özet modeli de reddetti.
3. Özet başarısız olunca kod "özetsiz devam" edip mesajı yine gönderdi → 400.
4. Uygulamanın token tahmini (3,5 karakter/token) Türkçe/kodda düşük: EVREN ~1,35 kat fazla saydı.

## Çözüm
- `agent/compaction.fit_for_summary`: özet isteği özet modelinin bağlamının en fazla
  yarısına (≤300k) KESİN sığdırılır — temkinli sayım (2,6 karakter/token), uzun araç
  çıktısı/parametresi (JSON geçerli kalır)/kullanıcı/asistan metni kısaltılır; yine
  büyükse ilk hedef mesajı korunarak en eski mesajlar çıkarılır ve not eklenir.
- `SessionView._after_failed_summary`: özet başarısız ve geçmiş modele sığmıyorsa
  mesaj GÖNDERİLMEZ, kutuya geri konur; kart: "Temiz sayfa aç (/clear)" / "Yeniden özetle".
- `/clear` (`/temizle`): aynı klasör, model, mod, profille temiz sayfa; eski oturum silinmez.

## Kanıt
- Kullanıcının gerçek oturumunun KOPYASI: özet isteği 724k → 299k (temkinli) token;
  gerçek API (deepseek-v4-flash) 174 sn'de özetledi, özet exe yolunu da içeriyordu.
- tests/test_clear_ve_buyuk_ozet.py (8): 3 bağlam boyutunda bütçeye sığma, hedef/son soru
  korunur, JSON geçerli, önceki özet korunur, /clear davranışı, send → başarısız özet →
  gönderilmez (R-31 tur yolu).

## Önleme
R-32.

## İlgili dosyalar
- src/evren_studio/agent/compaction.py
- src/evren_studio/ui/session_view.py
- src/evren_studio/ui/composer.py
- tests/test_clear_ve_buyuk_ozet.py
