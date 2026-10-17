---
id: 2026-10-17-model-ayni-cumleleri-tekrar-tekrar-yazip-aracsiz-bitiriyordu
tarih: 2026-10-17
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [dongu, metin-tekrari, auto]
kurallar: [R-19]
---

# Model aynı cümleleri tekrar tekrar yazıp araçsız bitiriyordu

## Belirti
Proje maratonu (tests/e2e_marathon_real_api.py, A projesi, auto): son mesajda
model araç çağırmadan "harcama.py dosyasını okuyayım. Testleri çalıştıracağım.
Testlerin çalışması için … doğrulayayım." cümlelerini onlarca kez yazdı (iki
yanıtta 48 bin karakter). Koşucu bunu normal yanıt sayıp turu `done` bitirdi;
projenin kendi 2 testi kırık kaldı. Kullanıcının "LLM döngüye giriyor"
şikâyetinin görünür biçimi.

## Kök neden
Model davranışı (dejenere tekrar). Uygulamada metin içi tekrar denetimi yoktu;
"söz verip durma" denetimi yalnız ≤300 karakterlik yanıtlara bakıyordu.

## Çözüm
`collapse_repetition()`: 12+ harfli cümleler en az 3 kez ve parçaların %30'u
tekrar ediyorsa metin kısaltılır ("[Tekrar eden metin kısaltıldı.]") ve araçsız
yanıtta bir kez `NUDGE_REPEAT` ile dürtülür. Akışta 8 tekrar görülünce istek
`_StepCancel` ile erken kesilir (finish_reason="repetition", kullanıcı iptali
sayılmaz) — zaman ve kota korunur.

## Kanıt
- Maratondaki 170 gerçek asistan mesajında: 2 doğru yakalama (auto'nun 48k
  karakterlik iki yanıtı → 254/348 karakter), 0 yanlış alarm.
- tests/test_loop_guard.py: metin tekrarı, normal özet, akışta kesme testleri.
- 2. turda (yeni kodla) auto A projesi 10/10; tekrar o koşuda oluşmadı (rastgele).

## Önleme
R-19 kapsamı; dedektörün eşikleri değişirse gerçek mesajlarla yanlış alarm ölç.

## İlgili dosyalar
- src/evren_studio/agent/runner.py
- tests/test_loop_guard.py
- docs/knowledge/LOOP_ANALYSIS.md
