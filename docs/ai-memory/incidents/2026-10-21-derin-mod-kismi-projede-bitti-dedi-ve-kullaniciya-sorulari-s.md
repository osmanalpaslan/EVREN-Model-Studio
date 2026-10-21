---
id: 2026-10-21-derin-mod-kismi-projede-bitti-dedi-ve-kullaniciya-sorulari-s
tarih: 2026-10-21
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PowerShell 5.1, Python 3.12.10
etiketler: [derin-mod, kabul, kullanici-sorusu]
kurallar: [R-28]
---

# Derin Mod kısmi projede bitti dedi ve kullanıcıya soruları sormadı

## Belirti
Derin Mod 1 sa 50 dk sonunda EVREN_DERIN.md'ye "Durum: bitti · Onaylanan sorun yok" yazdı; oysa istenen Excel
raporu hiç oluşmamıştı (3/12 görev). ANLA'nın 3 alt ajanı da tam doğru soruları bulmuştu (CRS verisi yok,
kullanici_listesi.tsv proje dışında, fırsat dosyası 28.09 tarihli mi, çıktı adı) ve "önce kullanıcıya sor" demişti;
bu sorular kullanıcıya hiç gösterilmedi. Kanıt kaynağı: kullanıcının EVREN Studio oturumu #16 (2026-10-21 13:50-15:40, Derin Mod, hesap kapama raporu; veritabanı kopyası ve klasördeki EVREN_DERIN.md / EVREN_RAPOR.md / EVREN_PLAN.md incelendi).

## Kök neden
Doğrulandı (kendi tasarım hatam, aynı gün yazdığım Derin Mod). (1) `_project_finished` Proje'nin `bitti` durumuna
güvendi; Proje kısmi işi de `bitti` sayıyordu. (2) Denetçiler yalnız diff'e bakıyordu; istenen nihai çıktının
varlığını sormuyordu. (3) Anla bulgularında "sorular" alanı ve akışta kullanıcıya sorma adımı yoktu.

## Çözüm
- Anla bloğuna `sorular`; birleştirilip (benzer olan bir kez, en çok 6) PLANLAMADAN ÖNCE soru kartıyla sorulur;
  yanıt kartta veya mesaj kutusunda; "Sormadan devam" → varsayımlar raporda. Yanıt plana ve görevlere iner.
- Proje kısmi/duraklatıldıysa Derin `bitti` demez: bekler (`waiting_project`), proje bitince doğrulama başlar;
  `/derin-durdur` beklemeyi bırakır.
- Denetçi istemi önce nihai çıktının varlığını doğrulatır ve proje görev durumlarını alır; iki denetçi farklı model.

## Kanıt
`tests/test_derin_duzeltmeler.py` arayüz testleri (soru kartı, mesajla yanıt, görev istemine iniş, kısmi projede
bekleme ve sürdürünce doğrulama). Gerçek API: tests/e2e_derin_real_api.py (sonuç CHALLENGE_RESULTS.md).

## Önleme
R-28: "bitti" yalnız kabul ölçütü (istenen çıktı) doğrulanınca; eksik veri/karar varsa sor.

## İlgili dosyalar
- src/evren_studio/agent/deep.py
- src/evren_studio/ui/deep_ui.py
- src/evren_studio/ui/session_view.py
