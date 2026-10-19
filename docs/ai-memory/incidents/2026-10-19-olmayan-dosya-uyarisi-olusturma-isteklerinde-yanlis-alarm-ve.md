---
id: 2026-10-19-olmayan-dosya-uyarisi-olusturma-isteklerinde-yanlis-alarm-ve
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gerileme, kapsam, yanlis-alarm]
kurallar: [R-21, R-22]
---

# Olmayan dosya uyarısı oluşturma isteklerinde yanlış alarm verdi (kendi gerilemem)

## Belirti
8 motor ölçümünde (12 görev) qwen3-vl-30b ve auto, "EVREN_PLAN.md dosyasına ...
plan yaz" ve "kelime_say.py yaz" isteklerinde dosyayı yazmak yerine "dosya
bulunamadı, oluşturayım mı / README'yi mi kastettiniz?" diye sordu.

## Kök neden
Doğrulandı: aynı gün (2026-10-19) eklediğim `scope.missing_mentions` tur notu,
kullanıcının OLUŞTURMAK istediği dosyayı da "projede bulunamadı" diye
işaretliyordu. Notta "açıkça yeni dosya istenmiyorsa" istisnası vardı ama zayıf
modeller istisnayı uygulamadı. Uyarıyı yalnız tetiklenmesi gereken senaryoda
(olmayan) ölçmüştüm; gereksiz tetiklendiği senaryoyu ölçmemiştim.

## Çözüm
`scope.wants_creation`: dosya adının ~25 karakter öncesi / 70 karakter sonrasında
oluşturma fiili (yaz, oluştur, ekle, hazırla, kaydet, üret, yeni…) varsa o dosya
için uyarı verilmez. "…dosyasındaki/içindeki…/oku/düzelt" gibi mevcut dosyaya
atıflarda uyarı sürer.

## Kanıt
- Önce: qwen3-vl-30b planlama 0/1, mini_proje dosyayı hiç yazmadı; auto planlama 0/1.
- Sonra: qwen3-vl-30b planlama 5/5, olmayan 3/3; auto ve EVREN Akıllı sonuçları
  CHALLENGE_RESULTS.md "8 motor" bölümünde.
- `tests/test_zorluk_duzeltmeleri.py::test_olusturulacak_dosya_icin_uyari_yok`.

## Önleme
R-22: otomatik eklenen her uyarı/denetim için gereksiz tetiklenme senaryosunu da
test et ve tüm paketle ölç (yalnız hedef görevle değil).

## İlgili dosyalar
- src/evren_studio/agent/scope.py
- tests/test_zorluk_duzeltmeleri.py
