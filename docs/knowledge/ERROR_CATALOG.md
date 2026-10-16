# Hata Kataloğu

> Her hata SQLite `error_records` tablosuna imzayla kaydedilir
> (imza: `işlem:hata_türü:HTTP:model`). Bu belge insan tarafından okunabilir
> özet ve ilk başvuru kaynağıdır. API anahtarı ve mesaj içerikleri asla
> kaydedilmez.

## Hata sınıfları ve Türkçe açıklamaları

| Tür | HTTP | Otomatik tekrar | Türkçe açıklama (özet) |
|---|---|---|---|
| kimlik_doğrulama | 401, 403 | HAYIR | Anahtar reddedildi; Ayarlar'dan yeniden girin |
| bulunamadı | 404 | HAYIR | Model/uc yok; listeyi yenileyin |
| kota_sınırı | 429 | Retry-After'a uy | Kullanım sınırı; kota sayfasına bakın |
| sunucu_kullanılamıyor | 503 | Retry-After/artan bekleme (≤3) | Sağlayıcı kaynaklı: 'sağlıklı endpoint yok' — yerel sorun DEĞİL |
| sunucu_hatası | 500, 502, 504 | Artan bekleme (≤3) | Geçici sunucu hatası |
| zaman_aşımı | 408 / istemci | HAYIR (sonuç belirsiz) | İstek sunucuda çalışmış olabilir; tekrar gönderilmez |
| istek_çok_büyük | 413 | HAYIR | Mesajı/dosyayı küçültün |
| geçersiz_istek | 400, 422 | HAYIR | Desteklenmeyen parametre; model yeteneklerine bakın |
| ağ_hatası | bağlantı kurulamadı | ≤3 | Bağlantı yok; yerel çalışma sürer |
| belirsiz_sonuç | akış kopması, okuma zaman aşımı | HAYIR | Durum sorgusu yapılır (`/v1/requests/{id}`), kullanıcı kararı beklenir |

## Bilinen hata örnekleri (gerçek gözlem)

### 1) `'glm-5.3' için sağlıklı endpoint yok` — HTTP 503

- **Sınıf**: sunucu_kullanılamıyor → sağlayıcı kaynaklı.
- **YANLIŞ yorumlar**: API anahtarı hatası, yerel bilgisayar arızası.
- **Davranış**: Retry-After varsa uyunur (≤300 sn); yoksa 5/10/20 sn artan
  beklemeyle en fazla 3 otomatik tekrar. Sonra model geçici olarak
  kullanılamıyor işaretlenir (model_health). Otomatik model değiştirme
  VARSAYILAN OLARAK KAPALIDIR.
- **Kod durumu**: 2026-10-15'e kadar gerçek 503 gözlemlenmedi; davranış birim
  testlerle doğrulandı (test_503_retry_after_ile_yeniden_dener,
  test_503_tekrar_limiti_asilinca_hata_verir).

### 2) Akış kopması / okuma zaman aşımı — belirsiz sonuç

- **Davranış**: aynı uzun istek otomatik TEKRAR GÖNDERİLMEZ. İstek kimliği
  varsa `GET /v1/requests/{id}` sorgulanır; `execution_terminal` değeri
  kullanıcıya gösterilir. Sonuç yine belirsizse kontrollü tekrar KULLANICI
  kararıyla yapılır.
- **Test kanıtı**: test_zaman_asimi_belirsiz_sonuç_tekrarsız,
  test_akis_kopmasi_belirsiz_sonuç.

### 3) Muhakeme modelinde boş içerik — HTTP 200 ama `content: null`

- glm-5.3 düşük `max_tokens` ile: `finish_reason: "length"`,
  `reasoning_budget_exhausted: true`. Bu bir API hatası DEĞİLDİR.
- **Çözüm**: `max_tokens`'ı artırın (örn. ≥800). Uygulama sohbette makul
  varsayılan kullanır; muhakeme metni ayrı kaydedilir.

### 4) Duyuru sayfası 401

- `api.ssyz.org.tr/api/v1/announcements/active` platform girişi ister.
- **Davranış**: izleme ajanı sayfayı değil, kullanıcının seçtiği genel URL'i
  izler; erişilemezse kayda 'başarısız' düşer, aşma girişimi YAPILMAZ.

## Kayıt şeması

Her hata kaydında: tarih/saat, uygulama sürümü, işlem, model, API yolu,
HTTP durumu, hata kodu, maskelenmiş mesaj, istek kimliği, Retry-After,
izleme durumu, bağlam, denenen çözüm, çözüm sonucu, sonraki adımlar, imza.
