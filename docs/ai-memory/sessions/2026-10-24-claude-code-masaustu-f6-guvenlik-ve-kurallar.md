---
id: 2026-10-24-claude-code-masaustu-f6-guvenlik-ve-kurallar
tarih: 2026-10-24
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/f6-guvenlik-kurallar
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# F6 güvenlik ve kurallar

## Görev
Kullanıcı: "F6'ya başla." Kapsam: #15 güvenilmeyen klasör, E4 kullanıcı kuralları, E1 geri sarma. Kabul: güvenilmeyen
klasörde çalıştırma engellenir; geri sarma dosya + konuşmayı doğru döndürür.

## Yapılanlar
- #15 agent/untrusted.py: komutta güvenilmeyen klasördeki çalıştırılabilir dosya (veya aç/çalıştır fiili) → engel
  (izin modundan bağımsız; run_command, start_job, start_service); okunan içerik "DIŞ İÇERİK" uyarısıyla; isteme
  klasör listesi. Arayüz: Dosyalar'da sağ tık işaret, Ayarlar listesi (sıfırlamada korunur).
- E4 agent/userrules.py: `.evren/kurallar.json` — duzenleme_sonrasi (not), komut_oncesi (engelleyebilir), tur_sonu
  (dosya yazan turda bir kez; başarısızsa dürt). Onay: ilk kullanımda ve içerik her değişince kart (özet ayarda).
- E1: kullanıcı mesajında "Buraya geri sar" → kart (silinecek mesaj, geri alınacak dosyalar, elle değişmiş dosyalar,
  GERİ ALINAMAYACAK komut/kurulum/web etkileri, Proje commit'leri) → dosyalar sondan başa geri, konuşma kesilir,
  metin kutuya; geri alma hatasında konuşma SİLİNMEZ.

## Test sonuçları
- pytest 637/637 (F6: tests/test_f6_guvenlik.py 25).
- Ekran görüntüleri (koyu + açık): kural onay kartı, geri sarma kartı, Dosyalar'da güvenilmeyen işareti, Ayarlar
  listesi — bakıldı.
- Gerçek API (tests/e2e_guvenlik_real_api.py, Auto Pro): güvenilmeyen açık 3/3 (düzeltilmiş kontrol; model
  enjeksiyonu alıntılayıp uyardı, kur.bat çalışmadı), işaretsiz karşılaştırma: model yine çalıştırmadı, kullanıcı
  açıkça "çalıştır" dediğinde de çalıştırmadı ve nedenini söyledi (2/2) → koşucudaki zorunlu engel gerçek modelle
  TETİKLENMEDİ, yalnız birim testinde doğrulandı. Kural tur sonu 2/2 — gemma docstring'i kendiliğinden yazdı, kural
  ilk seferde geçti (dürtme gerçek modelde sınanmadı; birim testinde sınandı).
  Zorluk auto-pro 12/12 · 457 sn. R-13: E2E_OK · arayüz 15/15 · ajan 5/6 (deepseek metin protokolü, bilinen
  kararsızlık — F3 A/B).

## Sorunlar ve kayıtlar
- 2026-10-24-guvenlik-olcumu-enjeksiyonu-alintilayip-uyaran-yaniti-uydu-s (ölçüm düzeneği; R-29'u çiğnedim)
- Testte `reset_defaults` modal kutu açıp asıldı → test korunan ayar listesini doğrudan denetliyor.

## Sonraki motor için notlar
- Güvenilmeyen klasör denetimi komut satırı düzeyindedir (işletim sistemi yalıtımı değil; E7 iptal). `Get-FileHash
  mods\\x.exe` gibi zararsız komutlar da .exe adı geçtiği için ihtiyatla engellenir (bilerek).
- MCP araçları güvenilmeyen klasör denetiminden geçmez (Playwright/Serena kendi süreçleri).
- Sıradaki: F7 (oyun: Godot + MCP, Blender ekransız, E9 MCP kataloğu).
