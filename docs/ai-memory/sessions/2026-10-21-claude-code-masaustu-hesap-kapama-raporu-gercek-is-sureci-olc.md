---
id: 2026-10-21-claude-code-masaustu-hesap-kapama-raporu-gercek-is-sureci-olc
tarih: 2026-10-21
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/hesap-kapama-olcum
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Hesap kapama raporu gerçek iş süreci ölçümü

## Görev
Kullanıcı: "en çok 10 dakika sürecek veri hazırlayıp EVREN'e hesap kapama raporunu ürettir, hataları tespit et;
EVREN'i iş süreçlerimde kullanmak istiyorum, ne kadar yetenekli görmeliyim?"

## Yapılanlar
- `tests/hesap_kapama/hk_veri.py`: kullanıcının dosyalarıyla aynı sütun yapısında SAHTE veri (32 iş, fırsat,
  sözleşme, CRS, sayaç tipleri, kullanıcı sözlüğü; her SKILL kuralı için tuzak), kurallardan beklenen sonuç
  (kahin), çıktı denetçisi ve denetçiyi sınamak için referans rapor (doğru/bozuk). openpyxl gerekir (sistem Python).
- `tests/e2e_hesap_kapama_real_api.py`: skill'i kopyalar, ajanı Otomatik modda 10 dk sınırla koşar, Excel
  süreçlerini izler (kullanıcının Excel'i öldürülmüş mü), denetler; çıktılar `build/hk/kosu-*`.
- İstemde: sütun onayı önceden verildi; `Stop-Process -Name EXCEL` yasaklandı (skill'in teknik_tuzaklar #9'u
  kullanıcının açık Excel'ini kaydetmeden kapatabilecek komut öneriyor).
- Sonuçlar CHALLENGE_RESULTS.md "Gerçek iş süreci: hesap kapama raporu".

## Test sonuçları
- Denetçi sınaması (R-25): referans doğru rapor 25/25; eski hatalı kural → açılış kaynağı hatası yakalandı.
- Koşu 1: 537 sn, 30 adım, 24/25 (tek ihlal: Yönetim Özeti "Notlar:" bloğu). Tüm hesaplamalar doğru.
- Koşu 2: 528 sn, 49 adım, döngü → qwen'e geçiş, 23/26; Yönetim Özeti dağılımları 30 iş üzerinden (skill 32
  istiyor) — denetçi bunu ölçmüyordu, elle bulundu; `_build.py` skill klasöründe kaldı.
- pytest: bitişte koşuldu (yalnız yeni test dosyaları; src değişmedi).

## Sorunlar ve kayıtlar
- Yeni kayıt açılmadı: ajan tarafı bulgular (koşular arası tutarsızlık, geçici betiğin kaynak klasöre yazılması)
  kullanıcıyla konuşulacak; skill çelişkileri kullanıcının dosyası (değiştirilmedi).

## Sonraki motor için notlar
- Denetçi Yönetim Özeti sayılarını ölçmüyor: eklenmeli (dağılım toplamı = kaynak iş sayısı).
- Skill çelişkileri: `Manuel / Kullanıcı` ↔ " / " yasağı; dağılım tabanı (kapsam dışı dahil mi) açık değil;
  açık işte Kapatan Kullanıcı ve sözlükte olmayan id biçimi tanımsız; "Soru 1–5" tanımsız; tarih biçimi yok.
- Test gerçek veriden kolay: 32 satır, temiz başlık, önceden onay. Gerçek 2.500 satırda ve bozuk başlıkta
  ölçülmedi; Derin Mod ile de koşulmadı.
- Öneri: aylık iş için ajana bir kez doğrulanmış, sabit bir betik (`rapor_uret.py`) yazdırıp her ay onu çalıştırmak
  (tekrarlanabilir, ~1 dk); denetçi testi her sürümde koşulmalı.
