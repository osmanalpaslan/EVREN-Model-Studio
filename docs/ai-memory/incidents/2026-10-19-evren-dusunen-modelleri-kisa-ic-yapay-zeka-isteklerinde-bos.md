---
id: 2026-10-19-evren-dusunen-modelleri-kisa-ic-yapay-zeka-isteklerinde-bos
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: api
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [auto-pro, reasoning, ai_chat]
kurallar: [R-24]
---

# EVREN düşünen modelleri kısa iç yapay zekâ isteklerinde boş yanıt verdi

## Belirti
Auto Pro'nun iç yapay zekâ işleri (oturum başlığı, hata açıklaması, commit
mesajı) gerçek EVREN API'de denendiğinde `ai_chat` boş metin döndürdü; başlık
üretilmedi, commit mesajı varsayılana düştü. Sahte istemcili birim testleri geçiyordu.

## Kök neden
Doğrulandı: deepseek-v4-flash, qwen3.8-flash-next gibi düşünen modeller küçük
`max_tokens` (60–400) ile çağrıldığında bütçeyi düşünmeye harcayıp `content`'i
boş döndürüyor. gemma-4-31b de kısa başlık isteğinde iki kez boş yanıt verdi.

## Çözüm
`AppContext.ai_chat`: `reasoning_effort` yeteneği olan EVREN modellerine
`extra_body={"reasoning_effort": "none"}` gönderilir; boş içerik "hata" sayılıp
zincirdeki sıradaki modele geçilir. Yedek model listesine (`REASONING_EFFORT_MODELS`)
yetenek bayrağı eklendi (canlı liste gelmeden de çalışsın). Başlık rotasında
gemma sona alındı.

## Kanıt
Gerçek API: başlık "Aylık Satış Grafiği Python" (deepseek-v4-flash), hata
açıklaması ve commit mesajı dolu döndü. Birim: tests/test_auto_pro.py
`test_ai_chat_dusunmeyi_kapatir_bos_yanitta_siradakine_gecer`,
`test_yedek_listede_dusunme_yetenegi_isaretli`.

## Önleme
R-24. Kısa iç yapay zekâ isteği eklerken gerçek API ile en az bir kez dene;
sahte istemci boş içerik senaryosunu yakalamaz.

## İlgili dosyalar
src/evren_studio/ui/app_context.py, src/evren_studio/agent/router.py,
tests/test_auto_pro.py
