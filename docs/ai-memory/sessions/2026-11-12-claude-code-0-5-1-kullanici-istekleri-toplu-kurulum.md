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

## Test sonuçları
- test_kurulum_paketi 14 (yeni: OverridesAllowed YOK); mutasyon 2/2 (dialog / commandline dialog geri eklenince test düşüyor). Kurulum dosyası bu adımda DERLENMEDİ (kullanıcı: toplu, sonda) — ISCC derlemesi ve Sandbox denemesi 0.5.1 çıktısında.

## Sorunlar ve kayıtlar
<!-- Karşılaşılan sorunlar → docs/ai-memory/incidents/... kimlikleri. -->

## Sonraki motor için notlar
- Kullanıcı "oluştur + tüm testler" diyene kadar tam takım / gerçek API / paket ÇALIŞTIRMA (Madde 21).
