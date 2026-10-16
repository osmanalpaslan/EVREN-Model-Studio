# Ortak Hafıza İndeksi

> Bu dosya `tools/ai_memory.py indeks` ile üretilir; elle düzenleme.

Kayıt: 9 · Açık/izlenen: 2 · Oturum: 4 · Kural: 10

## Açık ve izlenen kayıtlar

| Önem | Kayıt | Tür | Alan | Başlık |
|---|---|---|---|---|
| yuksek | [2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi](incidents/2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi.md) | risk | api/kod-ajani | EVREN API'de araç çağrısı (tools) gerçek istekle doğrulanmadı |
| dusuk | [2026-10-16-izleme-dongusu-testi-zamanlamaya-bagli-kararsiz](incidents/2026-10-16-izleme-dongusu-testi-zamanlamaya-bagli-kararsiz.md) | hata | test/izleme | İzleme döngüsü testi zamanlamaya bağlı ve kararsız |

## Tüm kayıtlar (yeniden eskiye)

| Tarih | Kayıt | Tür | Önem | Durum | Kaynak motor | Başlık |
|---|---|---|---|---|---|---|
| 2026-10-16 | [2026-10-16-qtimer-silinmis-widgeta-cagri](incidents/2026-10-16-qtimer-silinmis-widgeta-cagri.md) | hata | orta | cozuldu | Claude Code (masaüstü) | QTimer.singleShot silinmiş widget'ı çağırdı |
| 2026-10-16 | [2026-10-16-izleme-dongusu-testi-zamanlamaya-bagli-kararsiz](incidents/2026-10-16-izleme-dongusu-testi-zamanlamaya-bagli-kararsiz.md) | hata | dusuk | izleniyor | Kilo Code (VS Code eklentisi) | İzleme döngüsü testi zamanlamaya bağlı ve kararsız |
| 2026-10-16 | [2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi](incidents/2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi.md) | risk | yuksek | acik | Claude Code (masaüstü) | EVREN API'de araç çağrısı (tools) gerçek istekle doğrulanmadı |
| 2026-10-15 | [2026-10-15-gitignore-secrets-kalibi-kaynak-modulu-disladi](incidents/2026-10-15-gitignore-secrets-kalibi-kaynak-modulu-disladi.md) | hata | kritik | cozuldu | Kilo Code (VS Code eklentisi) | .gitignore `secrets*` kalıbı kaynak modülü depodan dışladı |
| 2026-10-15 | [2026-10-15-duman-testi-bozuk-arayuzu-yakalamadi](incidents/2026-10-15-duman-testi-bozuk-arayuzu-yakalamadi.md) | yanlis-iddia | yuksek | cozuldu | Kilo Code (VS Code eklentisi) | Duman testi bozuk arayüzü yakalamadı; belgeler "tamamlandı" diyordu |
| 2026-10-15 | [2026-10-15-code-studio-ajan-ozellikleri-eksikti](incidents/2026-10-15-code-studio-ajan-ozellikleri-eksikti.md) | eksik | yuksek | cozuldu | Kilo Code (VS Code eklentisi) | Code Studio'da kod ajanı özellikleri yoktu |
| 2026-10-15 | [2026-10-15-cift-kodlanmis-turkce-metinler-mojibake](incidents/2026-10-15-cift-kodlanmis-turkce-metinler-mojibake.md) | hata | yuksek | cozuldu | Kilo Code (VS Code eklentisi) | Çift kodlanmış Türkçe metinler (mojibake) depoya girdi |
| 2026-10-15 | [2026-10-15-ayarlar-acilista-okunmuyordu](incidents/2026-10-15-ayarlar-acilista-okunmuyordu.md) | hata | yuksek | cozuldu | Kilo Code (VS Code eklentisi) | Kaydedilen ayarlar açılışta hiç okunmuyordu |
| 2026-10-15 | [2026-10-15-acilista-senkron-model-yukleme-arayuzu-donduruyordu](incidents/2026-10-15-acilista-senkron-model-yukleme-arayuzu-donduruyordu.md) | hata | orta | cozuldu | Kilo Code (VS Code eklentisi) | Açılışta senkron model yükleme arayüzü donduruyordu |

## Oturum günlükleri (yeniden eskiye)

| Tarih | Oturum | Motor / model | Sonuç | Başlık |
|---|---|---|---|---|
| 2026-10-16 | [2026-10-16-claude-code-masaustu-ortak-gelistirici-hafizasi-yapisi](sessions/2026-10-16-claude-code-masaustu-ortak-gelistirici-hafizasi-yapisi.md) | Claude Code (masaüstü) / claude-opus-5-5 | tamamlandi | Ortak geliştirici hafızası yapısı |
| 2026-10-16 | [2026-10-16-claude-code-kod-ajani-calisma-alani-ve-yeni-arayuz](sessions/2026-10-16-claude-code-kod-ajani-calisma-alani-ve-yeni-arayuz.md) | Claude Code (masaüstü) / claude-opus-5-5 | kismi | Kod ajanı çalışma alanı ve yeni arayüz (0.2.0, PR #2) |
| 2026-10-16 | [2026-10-16-claude-code-ikinci-bilgisayar-kurulumu-ve-secrets-duzeltmesi](sessions/2026-10-16-claude-code-ikinci-bilgisayar-kurulumu-ve-secrets-duzeltmesi.md) | Claude Code (masaüstü) / claude-opus-5-5 | tamamlandi | İkinci bilgisayarda kurulum ve secrets.py düzeltmesi |
| 2026-10-15 | [2026-10-15-kilo-code-asama-0-1-arastirma-ve-mvp](sessions/2026-10-15-kilo-code-asama-0-1-arastirma-ve-mvp.md) | Kilo Code (VS Code eklentisi) / bilinmiyor (EVREN LLM) | kismi | Aşama 0 + 1: araştırma, MVP, testler ve bilgi tabanı (geriye dönük kayıt) |

## Kurallar

- **R-01** · Türkçe içerikli dosyayı PowerShell 5.1 ile yazma
- **R-02** · .gitignore kalıbını kaynak dosyalara karşı doğrula
- **R-03** · "Kaydediliyor" yetmez, okuma yolunu da test et
- **R-04** · Arayüz iş parçacığında ağ isteği yapma
- **R-05** · Arayüz işini görmeden "tamamlandı" deme
- **R-06** · Gecikmeli Qt çağrısına bağlam nesnesi ver
- **R-07** · Gerçek API ile doğrulanmamış yeteneği doğrulanmış gibi sunma
- **R-08** · Kararsız testte rastgele kod değiştirme
- **R-09** · Hafızayı oku, sonra besle
- **R-10** · Kodlamayı test ile koru
