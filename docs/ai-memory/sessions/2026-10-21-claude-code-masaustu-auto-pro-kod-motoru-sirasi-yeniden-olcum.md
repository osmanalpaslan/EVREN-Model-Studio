---
id: 2026-10-21-claude-code-masaustu-auto-pro-kod-motoru-sirasi-yeniden-olcum
tarih: 2026-10-21
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/kod-motor-sirasi
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# Auto Pro kod motoru sırası yeniden ölçüm

## Görev
Kullanıcı: "doğru motoru seçmediği için mi yavaştı?" → ölçüm istendi; sonuçlara göre "kod işi için motor
sırasını deepseek-v4.1-flash → qwen3.8-flash-next → gemma-4-31b olarak değiştir, ölçümü belgeye işle, test et,
gönderip birleştir".

## Yapılanlar
- Hesap kapama oturumunun zaman dökümü: 86 dk'nın 80'i model süresi, 6'sı komut; 247 model çağrısı. Yavaşlığın
  asıl nedeni boşa giden adımlar (önceki oturumda düzeltildi); motor (qwen) bir kısmını büyüttü.
- 3 motor tek tek zorluk paketiyle ölçüldü (sonuçlar CHALLENGE_RESULTS.md "Kod motoru sırası").
- `agent/router.py`: kod = deepseek-v4.1-flash → qwen3.8-flash-next → gemma-4-31b; ROUTES_MEASURED 2026-10-21.
- Testler yeni sıraya göre: test_auto_pro, test_router (bağlam haritasına v4.1), test_project_ui.
- Belgeler: CHANGELOG, DECISIONS #87, CHALLENGE_RESULTS, MODEL_CAPABILITIES notu, ILERIDE (hız takibi, gemma
  maratonu), PROJECT_STATE.

## Test sonuçları
- Ölçüm: gemma 12/12 185 sn · deepseek-v4.1-flash 12/12 420 sn · qwen 12/12 531 sn.
- Yeni sırayla Auto Pro zorluk paketi 12/12, 249 sn (aynı gün qwen birincilken 516 sn). e2e_ui 15/15.
- pytest tam takım: bitişte koşuldu (commit öncesi).

## Sorunlar ve kayıtlar
- Yeni kayıt yok; bağlam: 2026-10-21-deepseek-v4-flash-evren-model-listesinden-kalkti.

## Sonraki motor için notlar
- Motor hızı günden güne değişiyor (v4.1: 10 → 7 dk). Kalıcı çözüm ILERIDE_YAPILACAKLAR madde 6: gerçek
  kullanımdan hız takibi ve görev arası motor değişimi — henüz yapılmadı.
- gemma-4-31b kısa görevlerde açık ara hızlı ama maratonla ölçülmedi; öne almadan önce tests/e2e_marathon_real_api.py.
- deepseek-v4-flash listeye dönerse kod sırasına kendiliğinden girmez (kod zincirinden çıkarıldı); yeniden ölç.
