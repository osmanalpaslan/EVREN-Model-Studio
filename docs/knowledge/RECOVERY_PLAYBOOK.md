# Kurtarma Rehberi (Recovery Playbook)

> Bu rehber, `src/evren_studio/recovery.py` içindeki RecoveryEngine ile
> birlikte çalışır. Kod, bu belgedeki kuralların yürütülmesidir.

## Her hatada uygulanacak süreç (12 adım)

1. **Koru**: mevcut sohbet, dosya ve görev durumunu bozma. Sohbetler her
   mesajda SQLite'a yazılır; API hatası veri KAYBETTİRMEZ.
2. **Sınıflandır**: hatayı `ApiError.kind` ile türle (bkz. ERROR_CATALOG).
3. **Oku**: aynı imzalı geçmiş kayıtları `find_similar_errors` ile bul.
4. **Doğrula**: geçmişte başarılı çözüm, bugünkü koşullarda hâlâ geçerli mi?
5. **Tekrarlama**: başarısız çözümü yeni bilgi olmadan YENİDEN DENEME.
6. **Ayır**: sorun istemci/ağ/kimlik/kota/model/yerel hangi kaynaktan?
7. **Uygula**: güvenli ve sınırlı tek adım at.
8. **Test et**: sonucu doğrula.
9. **Kaydet**: çözümü ve kanıtını `update_error_fix` ile yaz.
10. **Başarısızsa**: nedeni, bulguları ve sonraki adımı kaydet.
11. **Güncelle**: docs/PROJECT_STATE.md ve docs/TASK_CHECKLIST.md.
12. **İnsan kararı**: yalnızca gerekliyse kısa onay iste.

## 503 / sağlıklı endpoint yok — özel kurallar

- Bu hata otomatik olarak anahtar veya yerel bilgisayar hatası SAYILMAZ.
- `Retry-After` varsa uyunun (≤300 sn; üstü kullanıcıya bırakılır).
- Yoksa 5 → 10 → 20 sn artan bekleme, en fazla 3 otomatik tekrar.
- Model geçici olarak kullanılamıyor işaretlenir (`model_health`).
- Otomatik model değiştirme VARSAYILAN KAPALI; alternatif yalnız aynı görev
  için DOĞRULANMIŞSA ve kullanıcı İZİN VERDİYSE önerilir.
- API'yi sürekli sorgulamak YASAK; kapasite sorununu ağırlaştırır.
- Hata dönemi duyuru geçmişiyle ilişkilendirilir (izleme durumu kayda girer).
- Sağlayıcı sorunu sürerken yerel kodu GELİŞİGÜZEL DEĞİŞTİRME.

## Belirsiz sonuç (execution_unknown)

1. Aynı uzun isteği hemen tekrar gönderme.
2. İstek kimliği varsa `GET /v1/requests/{id}` sorgula
   (`execution_terminal`, `charge_terminal`).
3. Kimlik yoksa veya kayıt bulunamazsa: sonuç belirsiz olarak kaydedilir.
4. Kullanıcıya kontrollü tekrar seçeneği sunulur (Chat sayfası mesaj
   gövdesinde açıklanır).
5. Sunucunun desteklemediği idempotency/durum ucu VARSAYILMAZ; yalnız
   `/v1/requests/{id}` kullanılır (doğrulanmış).

## Duyuru + API değerlendirmesi (Durum İzleme Ajanı)

- Bakım duyurusu VARSA → `muhtemel sağlayıcı kaynaklı sorun` sınıfı.
- Yalnızca duyuruya dayanarak API'nin kesin bozuk olduğu İLAN EDİLMEZ.
- Gerçek testlerle karşılaştırılır: healthz/readyz + model listesi (token
  harcamaz) + kullanıcı seçtiyse gerçek model testi (token harcar).
- Bakım sürüyorsa: bekleme + sonraki kontrol önerilir; kod değişikliği ve
  sürekli API çağrısı YASAK.

## Daha önce başarısız olmuş çözümler (güncel liste)

| İmza | Denenen | Sonuç | Neden tekrar denenmez |
|---|---|---|---|
| (henüz kayıt yok) | — | — | İlk gerçek hatada doldurulur |

> Bu tablo, recovery sisteminin DB'de bulduğu 'başarısız' kayıtlarla birlikte
> okunur. DB kayıtları birincildir; bu tablo özet niteliğindedir.

## Başarılı çözümler

| İmza | Çözüm | Kanıt | Geçerlilik koşulu |
|---|---|---|---|
| (henüz kayıt yok) | — | — | — |
