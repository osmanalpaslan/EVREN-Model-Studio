---
id: 2026-10-21-proje-ajani-bozuk-dogrulama-komutu-yuzunden-gorevi-dusurup-8
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
etiketler: [proje-ajani, dogrulama, zincir, soru]
kurallar: [R-28]
---

# Proje ajanı bozuk doğrulama komutu yüzünden görevi düşürüp 8 görevi atladı

## Belirti
12 görevlik planda görev 3 (açık+kapalı işleri birleştir) 3 kez denendi (17 dk) ve "takıldı" sayıldı; ona zincirle
bağlı 8 görev atlandı; proje "Proje tamamlandı: bitti 3, takıldı 1, atlandı 8" diye BİTTİ işaretlendi. Ajanın kendi
özeti (deneme 2): "Doğrulama komutundaki `$t` işaretini dış kabuk … değiştiriyordu … Dosya ile ilgili bir sorun
değildi." Görev 2'de ise plan "onay metnini kullanıcıya sun" diyordu; gözetimsiz ajan onayı kendisi yazdı
(out/kararlar.md'de 26 "ONAY"). Kanıt kaynağı: kullanıcının EVREN Studio oturumu #16 (2026-10-21 13:50-15:40, Derin Mod, hesap kapama raporu; veritabanı kopyası ve klasördeki EVREN_DERIN.md / EVREN_RAPOR.md / EVREN_PLAN.md incelendi).

## Kök neden
Doğrulandı. (1) `ProjectRunner._verify` doğrulama komutunun çıkış kodu ≠ 0 ise görevi başarısız sayıyordu; komutun
KENDİSİNİN bozuk olduğunu (komut satırında sözdizimi/bağlama hatası) ayırmıyordu. (2) Takılan görev varken proje
"bitti" sayılıyordu. (3) Gözetimsiz görevin kullanıcıya soru sorma yolu yoktu; planlama istemi "kullanıcıya sun"
türü görevi engellemiyordu. (Proje ajanının tasarımı 2026-10-19, Claude Code.)

## Çözüm
- `check_command_broken`: hata `At line:N char:M` (komut satırı) VE kabuk/sözdizimi sınıfındaysa görev düşmez;
  karar notla incelemeye bırakılır. Betik dosyası içindeki hata (`At C:\…\x.ps1:15`) gerçek başarısızlıktır.
- Takılan görev varsa proje `duraklatildi` ("Proje kısmen bitti (n/m) …"); `/proje-devam` takılan görevi sıfır
  denemeyle, önceki nedenle yeniden dener; ona bağlı atlananlar beklemeye döner.
- `SORU: …` satırıyla biten görev projeyi duraklatır (deneme sayılmaz); `/proje-devam <yanıt>` yanıtı
  `answers`'a ekler, sonraki tüm görev istemlerine "Kullanıcının kararları" olarak girer.
- Görev istemine proje bilgi notu (`context`, Derin Anla özeti) eklenir; planlama kuralları: kullanıcı onayı
  isteyen görev yazma, doğrulamayı sarmalama, kelime saymak doğrulama değildir.

## Kanıt
`tests/test_derin_duzeltmeler.py`: bozuk komut → inceleme kararı (1 deneme); betik içi hata → takıldı;
kısmi proje duraklar ve sürdürmede 4/4 biter; SORU duraklatır, yanıt sonraki isteme girer; eski kayıt okunur.

## Önleme
R-28; ayrıca gözetimsiz akışta "kullanıcıya sor" adımı ya ÖNCEDEN sorulmalı ya da SORU ile duraklatmalı.

## İlgili dosyalar
- src/evren_studio/agent/project.py
- src/evren_studio/ui/project_ui.py
