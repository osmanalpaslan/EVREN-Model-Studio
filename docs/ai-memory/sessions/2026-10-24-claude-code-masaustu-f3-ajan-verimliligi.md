---
id: 2026-10-24-claude-code-masaustu-f3-ajan-verimliligi
tarih: 2026-10-24
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/f3-ajan-verimliligi
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# F3 ajan verimliliği

## Görev
Kullanıcı: faz dışında bulunan hataları unutma, uygun sıraya alıp düzelt; F3'e başla. Ayrıca test süresini
kısaltma önerisini onayladı ("onaylıyorum başla").

## Yapılanlar
- Test politikası: R-13 ve R-21 "faz sonunda, birleştirmeden önce bir kez"; yeni R-30 (testi değişikliğin türüne göre
  seç). Kayıt: 2026-10-24-gercek-api-testleri-her-maddeden-sonra-kosulunca-faz-1-5-2-s.
- Faz dışı hata: "Özeti üreten model" ve kapsam denetimi modeli listeden kalkmış deepseek-v4-flash'ı gösteriyordu →
  varsayılan "auto-pro", ayar sürümü 4 ile eski varsayılan taşınır (bilerek seçilen korunur).
- #1 `read_table` (agent/tables.py, yalnız standart kütüphane: xlsx sayfa/başlık/tarih, csv ayırıcı/kodlama).
- #2 kurulu Python paketleri ortam bölümünde (proje venv'i varsa onunki; 10 dk önbellek).
- #3 Proje ajanı: önceki görevlerde read_file ile okunan dosyaların GÜNCEL içeriği sonraki göreve (≤16 bin karakter,
  gizli dosya yok).
- E2 proje haritası (agent/projectmap.py, ~3 bin token, ayar `project_map`).
- E6 ders önerisi (agent/learnings.py): yalnız sinyal varsa model çağrısı; onay kartıyla EVREN.md "Öğrenilenler".
- E8: `evren_tools` gerçek istekle denendi — canlı veri yok; kendi `web_fetch` (agent/webfetch.py; komut gibi onay,
  güvenilmez içerik uyarısı, yalnız http/https).
- Arayüz: Ayarlar'da 2 yeni kutu; araç kartlarında "Tablo: …", "Web: …".

## Test sonuçları
- pytest 587/587 (F3: tests/test_f3_verimlilik.py 16; ayar taşıma testi).
- Ekran görüntüleri (koyu + açık): Ayarlar F3 kutuları, ders kartı ve araç kartları — bakıldı.
- Gerçek API: evren_tools 12 istek (etkisiz). Hesap kapama deepseek-v4.1-flash 10 dk: F3 açık → rapor üretildi
  (18 adım, read_table 6 çağrı; ama skill alt klasörüne kaydedildi; elle denetim 20/28), F3 kapalı → 10 dk'da rapor
  yok (10 adım). Tek örnek; deepseek o gün yavaştı (F2'de 10 token/sn ölçülmüştü). Zorluk auto-pro 12/12 · 671 sn.
  R-13: E2E_OK · arayüz 15/15 · ajan 5/6 sonra 4/6 → A/B (F3 açık/kapalı, 3'er tekrar): deepseek metin protokolü
  2/3 ve 2/3, qwen 3/3 ve 3/3 — bilinen kararsızlık, F3 gerilemesi değil.

## Sorunlar ve kayıtlar
- 2026-10-24-evren-evren-tools-uzantisi-acikken-de-canli-veri-getirmedi
- 2026-10-24-hesap-kapama-olcumu-alt-klasore-kaydedilen-raporu-cikti-yok (benim ölçüm düzeneği hatam)
- 2026-10-24-gercek-api-testleri-her-maddeden-sonra-kosulunca-faz-1-5-2-s
- E6'da aynı çağrıdaki yinelenen ders iki kez ekleniyordu — birim testi yakaladı, düzeltildi.

## Sonraki motor için notlar
- Hesap kapama F3 açık/kapalı karşılaştırması tek koşu: güçlü kanıt değil; EVREN hızlı bir günde iki koşu daha
  yapılırsa CHALLENGE_RESULTS'a ekle.
- Ajan raporu skill alt klasörüne kaydetti (betiği orada çalıştırıp göreli yol kullandı): tekrar ederse istemde
  "çıktıyı proje KÖKÜNE kaydet" vurgusu düşünülebilir.
- deepseek-v4.1-flash + metin protokolü kararsız (MODEL_CAPABILITIES); e2e_agent'ta tek KALDI bunu gösterir.
- Sıradaki: F4 (skill menüsü ve profiller).
