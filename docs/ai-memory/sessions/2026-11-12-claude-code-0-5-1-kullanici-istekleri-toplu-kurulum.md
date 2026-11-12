---
id: 2026-11-12-claude-code-0-5-1-kullanici-istekleri-toplu-kurulum
tarih: 2026-11-12
motor: Claude Code
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: surum/0.5.1-istekler
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# 0.5.1 kullanici istekleri (toplu): kurulum yalniz kullanici

## Görev
Kullanıcı (2026-11-12 20:40): (1) kurulum "yalnız benim için" gibi kursun ama bu seçenek kurulumdan önce GÖRÜNMESİN, "tüm kullanıcılar" seçeneği olmasın; (2) uçtan uca testlere şimdi başlama — birden fazla isteği olacak; hepsini verip "yeni çıktıyı oluştur ve gereken tüm testleri tamamla" deyince sürüm + tüm testler yapılıp süreç bitirilecek; (3) bu işlemlerden sonra yapılacak madde kalmış mı kontrol et.

## Yapılanlar
- installer/evren_studio.iss: `PrivilegesRequiredOverridesAllowed=dialog` kaldırıldı → Inno Setup "Kimin için kurulsun?" penceresini göstermez, yalnız kullanıcı kipinde (PrivilegesRequired=lowest, `{autopf}` = %LOCALAPPDATA%\Programs) kurar; komut satırı /ALLUSERS da etkisiz. tools/kurulum_sandbox.py artık /CURRENTUSER vermiyor (gereksiz). ILERIDE §1.1/§1.7 ve CHANGELOG "Yayınlanmamış — 0.5.1".
- Çalışma düzeni: dal `surum/0.5.1-istekler` istekleri biriktirir; DEVIR Madde 21.
- Kullanıcı 2026-11-12 (en yüksek düşünme): mini_proje neden var (cevaplandı: paketteki tek uçtan uca "küçük
  proje" görevi; 6 dk sınırı EVREN yavaşken aşılıyor); döngü bekçisine KALICI çözüm; "girdi" düşüşünü analiz edip
  gider; ücretli sağlayıcılar ERTELENDİ (mali durum; sonra API anahtarı alınacak); tüm projeyi yeniden analiz edip
  performans, tasarım, kolay kullanım, eksik/hata ve akla gelmeyenleri iyileştir; en iyi referansı (repo/web/kendi)
  kullan; tasarımda GÜNCEL iOS dili (iOS 27 Liquid Glass); animasyon ve logolar Türk bayrağı simgelerine sadık, modern.
- Döngü bekçisi kalıcı çözüm (kayıt 2026-11-12-dongu-bekcisi-turu-durdurdu, gözlem cf3c8b0737b8 kapatıldı): masaüstü
  kuralı tüm dış araçlara genellendi; yerel komut dış sayaçları sıfırlar; doğru uyarı metni; gözlemde döngü türü + araç
  adı; model değişip tur sürdüyse "durdurdu" denmez; proje görevinde EVREN_PLAN.md / EVREN_RAPOR.md yazılmaz.
- "girdi" düşüşü (kayıt 2026-11-12-zorluk-paketi-gorevi-dustu-girdi, gözlem 2983bc967976 kapatıldı): kök neden
  DENETLEYİCİNİN yanlış alarmı — gemma doğru açıklamıştı ("isim girişi bekliyor"), liste "giriş/isim"i tanımıyordu.
  Denetleyici düzeltildi + bilinen doğru/yanlış cevaplarla birim testi (R-25). Uygulama: girdi bekleyen program
  girdisiz çalışınca ajana ipucu (tools.stdin_hint; Read-Host çıkış 0 olsa da).
- YENİ HATA (analizde bulundu, kayıt 2026-11-12-ajan-komutlarinda-pipe-edilen-metnin-basina-bom-ekleniyordu): ajan
  komutlarında borulanan metnin başına BOM ekleniyordu ($OutputEncoding BOM'lu UTF8) → BOM'suz UTF-8.

## Test sonuçları
- test_kurulum_paketi 14 (yeni: OverridesAllowed YOK); mutasyon 2/2 (dialog / commandline dialog geri eklenince test düşüyor). Kurulum dosyası bu adımda DERLENMEDİ (kullanıcı: toplu, sonda) — ISCC derlemesi ve Sandbox denemesi 0.5.1 çıktısında.
- Döngü bekçisi: test_dongu_dis_araclar 12 + test_loop_guard / test_masaustu / test_masaustu_otomatik / test_gozlem /
  test_project_ui / test_hiz_adim / test_agent_runner (174) geçti; mutasyon 15/15. İlk denemede dış OKUMA eşiğini 3/5
  yapmak masaüstü R-22 testlerini düşürdü → geri alındı (ölçülmüş kural korunur).
- Girdi + BOM: test_zorluk_denetleyici 15 (gerçek PowerShell dahil); komut/araç risk paketi 71 + 98 geçti; mutasyon
  7/8 + 2/2 (kaçan: PowerShell mesajının iki imzası her zaman birlikte — bilinçli yedeklik).

## Sorunlar ve kayıtlar
<!-- Karşılaşılan sorunlar → docs/ai-memory/incidents/... kimlikleri. -->

## Sonraki motor için notlar
- Kullanıcı "oluştur + tüm testler" diyene kadar tam takım / gerçek API / paket ÇALIŞTIRMA (Madde 21).
