---
id: 2026-10-15-kilo-code-asama-0-1-arastirma-ve-mvp
tarih: 2026-10-15
motor: Kilo Code (VS Code eklentisi)
model: bilinmiyor (EVREN LLM)
ortam: Windows 11 (26200), PowerShell 5.1, Python 3.12.10
dal: master
sonuc: kismi
---

# Aşama 0 + 1: araştırma, MVP, testler ve bilgi tabanı (geriye dönük kayıt)

> Bu günlük 2026-10-16'da Claude Code tarafından git geçmişi (`9974dba` …
> `4ce1d38`) ve `docs/` içeriğinden yeniden oluşturuldu. O oturumda ortak
> hafıza yoktu; ayrıntılar eksik olabilir.

## Görev
Kullanıcının GPT yardımıyla hazırladığı ana proje istemiyle: EVREN API
araştırması, Windows masaüstü MVP (sohbet, Code Studio temeli, modeller,
kota, hata merkezi, durum izleme ajanı), kalıcı hata kurtarma belgeleri.

## Yapılanlar
- EVREN OpenAPI şeması incelendi; healthz/readyz/models/chat/quota/
  requests/terms uçları gerçek istekle doğrulandı (`docs/knowledge/`).
- PySide6 arayüzü (11 sayfa), httpx istemcisi, SQLite, keyring, izleme ajanı,
  kurtarma motoru; 53 birim testi, duman testi, uçtan uca gerçek API testi.
- Depo GitHub'da açık kaynak (MIT) yapıldı.

## Test sonuçları
Raporlanan: 53/53 birim testi, SMOKE_OK, E2E_OK (gerçek API, glm-5.3 + auto).
Sonradan bulunan: duman testi bozuk metinleri yakalamıyordu.

## Sorunlar ve kayıtlar
- 2026-10-15-cift-kodlanmis-turkce-metinler-mojibake
- 2026-10-15-gitignore-secrets-kalibi-kaynak-modulu-disladi
- 2026-10-15-ayarlar-acilista-okunmuyordu
- 2026-10-15-acilista-senkron-model-yukleme-arayuzu-donduruyordu
- 2026-10-15-duman-testi-bozuk-arayuzu-yakalamadi
- 2026-10-15-code-studio-ajan-ozellikleri-eksikti

## Sonraki motor için notlar
- API araştırması ve `docs/knowledge/` güvenilir ve gerçek isteklerle
  doğrulanmış; yeniden araştırma gerekmez.
- Arayüz ve Code Studio 2026-10-16'da Claude Code tarafından yeniden yazıldı.
