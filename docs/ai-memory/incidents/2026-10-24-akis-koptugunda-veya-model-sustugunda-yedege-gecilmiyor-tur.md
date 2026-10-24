---
id: 2026-10-24-akis-koptugunda-veya-model-sustugunda-yedege-gecilmiyor-tur
tarih: 2026-10-24
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ajan
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [auto-pro, yedek-model, akis, zaman-asimi]
kurallar: []
---

# Akış koptuğunda veya model sustuğunda yedeğe geçilmiyor, tur hatayla bitiyordu

## Belirti
Auto Pro analizi (2026-10-23/24) sırasında kod incelemesiyle bulundu: akışlı yanıt koparsa veya model 120 sn
susarsa istemci `UNKNOWN_RESULT` yükseltiyor; `runner._switch_model`'in yedeğe geçme kümesi bu türü içermediği
için tur yedek denemeden "error" ile bitiyordu. Kullanıcı Kilo Code'da "sunucu hatası alınca başka motora
geçemedi" sorununu yaşamıştı; EVREN Studio'da da sessiz akış için aynı açık vardı.

## Kök neden
Doğrulandı (kod). `_consume_stream` her httpx hatasını UNKNOWN_RESULT yapıyor (doğru: sonuç belirsiz); ama sohbet
isteğinin yan etkisi olmadığı için yedeğe yeniden sormak güvenli — bu ayrım yapılmamıştı. Ayrıca "yanıt vermeme"
için ayrı bir eşik yoktu (yalnız genel 120 sn zaman aşımı).

## Çözüm
- `EvrenClient(stream_idle_timeout=…)`: akışta ilk parça gelmezse veya akış bu kadar susarsa `TIMEOUT`
  ("Model N sn boyunca yanıt vermedi"); ayar `stream_idle_timeout_seconds` (varsayılan 60, Ayarlar'da).
- `_switch_model` yedeğe geçme kümesine `UNKNOWN_RESULT` eklendi. Kota hatası hâlâ geçirmez.
- Eşik ölçümü: `tests/e2e_akis_gecikme_real_api.py` — sağlıklı motorlarda ilk parça ≤ 2,7 sn, en uzun sessizlik
  ≤ 0,7 sn (küçük istek). Büyük bağlamda değer bilinmiyor; A1 kaydı biriktirecek.

## Kanıt
`tests/test_autopro_cekirdek.py`: gerçek yerel HTTP sunucusu ilk parçadan sonra susunca TIMEOUT (0,5 sn eşik),
eşiksiz istemci bekliyor; UNKNOWN_RESULT'ta y yedeğine geçip tur "done"; kota hatasında geçiş yok.

## Önleme
Yeni bir hata türü eklerken "yedeğe geçilmeli mi" sorusunu `_switch_model` kümesiyle birlikte test et.

## İlgili dosyalar
- src/evren_studio/api/client.py
- src/evren_studio/agent/runner.py
- src/evren_studio/config.py
