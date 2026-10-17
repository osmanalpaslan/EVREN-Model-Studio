---
id: 2026-10-17-ajan-tekrar-ve-ileri-geri-duzenlemede-durmuyordu
tarih: 2026-10-17
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [dongu, tekrar, ajan]
kurallar: [R-19]
---

# Ajan tekrar ve ileri-geri düzenlemede durmuyordu

## Belirti
Kullanıcı: "LLM bazı süreçlerde sürekli tekrara düşüyor, aynı işlemleri yapıp
duruyor." Gerçek API ölçümünde (docs/knowledge/LOOP_ANALYSIS.md) qwen3-vl-30b
çelişen testlerde KDV'yi 0,20→0,18→0,20 yaptı; auto test dosyalarını ileri-geri
değiştirdi. Koşucu yalnızca 40 adım sınırıyla duruyordu.

## Kök neden
Doğrulandı: `agent/runner.py` aynı araç+parametre tekrarını ve bir dosyanın
önceki hâline dönmesini izlemiyordu; modele de "bunu zaten yaptın" bilgisi
verilmiyordu. Kısaltılan çıktıdaki "gerekirse yeniden oku" ve özet sonrası
"emin değilsen yeniden oku" metinleri yeniden okumaya davet ediyordu.

## Çözüm
Döngü bekçisi (`AgentRunner._guard`): aynı imza (arada başarılı yazma yoksa)
2. kez → araç sonucuna "[Döngü uyarısı]", 3. kez → tur `loop` ile durur ve
kullanıcıya not; dosya önceki bir hâline dönerse uyarı, 2. kez → durur.
Başarılı yazma okuma/komut sayaçlarını sıfırlar (test → düzelt → test meşru).
TRIMMED_NOTE ve AUTO_CONTINUE_PROMPT yeniden okumaya davet etmeyecek biçimde
değişti; sistem istemine tekrar/yol değiştirme kuralları eklendi.

## Kanıt
- `tests/test_loop_guard.py` (12 test), tam paket 236+ geçti.
- Gerçek API, düzeltme sonrası `takil` görevi 12 koşu: auto koşusunda test
  dosyası ileri-geri düzenlemesi `loop` ile durduruldu; hiçbir koşuda test
  dosyası değişmiş kalmadı (öncesinde 3 koşuda değişmişti).

## Önleme
R-19. Ajan davranışı değişikliğinde `test_loop_guard.py` korunur.

## İlgili dosyalar
- src/evren_studio/agent/runner.py
- src/evren_studio/agent/prompts.py
- tests/test_loop_guard.py
- docs/knowledge/LOOP_ANALYSIS.md
