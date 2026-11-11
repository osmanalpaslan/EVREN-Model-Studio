---
id: 2026-11-12-claude-code-madde-20-c-asamasi-tree-sitter-harita-gu
tarih: 2026-11-12
motor: Claude Code
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/c1-harita
sonuc: devam-ediyor        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Madde 20 C asamasi: tree-sitter harita, guncelleme, ses, terminal

## Görev
Madde 20'nin C aşaması (kullanıcı 2026-11-11: sırayla, onaysız; 2026-11-12 00:05: "bütün işlemleri ve testleri
tamamla, raporla; ardından uygulamayı detaylı analiz et, hata/eksikleri bul ve düzelt; en son bilgisayarı kapat;
hiçbir işlem için onay isteme"). C1 tree-sitter proje haritası, C2 güncelleme denetimi, C3 sesle yazma, C4 gerçek
terminal. B3/B4 gerçek API ölçümleri ana klasörde koşarken C maddeleri ayrı git çalışma kopyasında (`../EVREN-C`)
geliştirildi (koşu modülleri sonradan yükler; ana klasörde kaynak değişmemeli).

## Yapılanlar
- C1 (dal feat/c1-harita): agent/tsmap.py — dil başına küçük ÇEVRİMDIŞI tree-sitter paketleri (Go, Rust, Java, C#,
  JS, TS/TSX, PHP, C, C++, Ruby, Kotlin; hepsi MIT, toplam ~2 MB). `tree-sitter-language-pack` SEÇİLMEDİ: yeni
  sürümleri çözümleyiciyi ilk kullanımda internetten indiriyor (paket 2,2 MB) → çevrimdışı kurulumda çalışmaz.
  Sınıf/yapı/arayüz/trait/impl/enum/modül/ad alanı + üyeleri, fonksiyonlar, JS/TS `const f = () =>`; `_` ile başlayan
  gizli adlar yok. Paket yoksa / dil nesnesi hata verirse (ABI) None → eski yöntem (düzenli ifade), harita bozulmaz.
  projectmap: semboller sığmayınca eskiden HEPSİ atılıyordu → artık BAŞKA dosyalardan en çok başvurulan dosyaların
  sembolleri önce (Aider PageRank'in sade hâli: tanımlanan ad başka dosyada geçiyorsa dosya puanı +1). Python `ast`
  ile kaldı. Paket: requirements/pyproject, spec hiddenimports (importlib ile adla yüklenir), duman `harita_dilleri=11`
  + check_smoke denetimi.

## Test sonuçları
- C1: test_proje_haritasi_diller 21 (11 dil örneği, Go/C#/Rust haritası, çözümleyici yok → eski yöntem, bozuk kaynak,
  uyumsuz paket, bütçe darken en çok başvurulan önce, kendi dosyasını saymama) + test_f3_verimlilik harita testleri
  değişmeden geçti; mutasyon 10/10 (ilk turda 3 kaçtı: sıralama testi alfabetik sıraya denk geliyordu, ABI hatası ve
  gizli üye sınanmıyordu → testler güçlendirildi). test_kurulum_paketi duman denetimi güncellendi.

## Sorunlar ve kayıtlar
- R-29 tuzağı bu oturumda iki kez daha: bash heredoc içindeki Python'da `\\n` → gerçek satır sonu oldu (test dosyası
  bozuldu, Edit aracıyla düzeltildi). Kural zaten var; uygulama disiplini: test dosyası yamalarını Edit ile yap.

## Sonraki motor için notlar
- C2-C4 aynı çalışma kopyasında sürüyor; B3/B4 ölçüm sonuçları ana klasördeki 2026-11-11 oturum günlüğünde.
