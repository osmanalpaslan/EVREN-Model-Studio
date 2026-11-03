---
id: 2026-11-04-derin-mod-arka-plan-fazlarinda-durum-cubugu-hic-gorunmuyordu
tarih: 2026-11-04
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10, QT_QPA_PLATFORM=windows
etiketler: [derin-mod, durum-cubugu, R-05]
kurallar: [R-05, R-31]
---

# Derin Mod arka plan fazlarında durum çubuğu hiç görünmüyordu

## Belirti
Madde 8'de alt ajan canlı durum cümlesi eklenince ekran görüntüsü alındı (R-05): anla/planla/doğrula
fazlarında yazma kutusunun üstündeki çalışma çubuğu YOK — ne yeni cümle ne de eski "N alt ajan bitti"
etiketi. Birim testleri `deep.label` değerinin değiştiğini doğruladığı için geçiyordu.

## Kök neden
Doğrulandı: `SessionView._tick_run` çubuğu yalnız `self.running` (oturumda ajan turu) iken çizer. Derin'in
arka plan fazları Task iş parçacığında koşar, oturumda tur yoktur → `deep.label` hiç ekrana çıkmadı. Etiket
yalnız uygula/düzelt turlarında görünüyordu. (2026-10-21'de "alt ajanlar ekranda iz bırakmadan 15-20 dk
çalışıyordu" şikâyetine not akışı eklenmiş, çubuk sorunu fark edilmemişti.)

## Çözüm
`DeepController._render_bar`: oturumda tur yokken ve Derin arka plan fazındayken çubuğu kendisi gösterir
(etiket + geçen süre, 1 sn'lik QTimer), faz bitince yalnız KENDİ gösterdiği çubuğu kapatır. Alt ajan her
araç başlatışında `progress` → `sig_label` (Qt sinyali, R-11) → "Derin · anla · anla-kod: Okunuyor: app.py".

## Kanıt
- tests/test_derin_v2.py `test_arka_plan_fazinda_calisma_cubugu_gorunur`; `_render_bar` boşaltılınca düştü (mutasyon).
- Ekran görüntüsü (koyu + açık): build/derin/derin_durum_*.png, çubuk görünür.

## Önleme
Durum/etiket değişikliğinde yalnız değişkeni değil bileşenin GÖRÜNÜR olduğunu test et (`isVisible()`),
ve R-05 ekran görüntüsünü atlama.

## İlgili dosyalar
- src/evren_studio/ui/deep_ui.py
- src/evren_studio/ui/session_view.py
- tests/test_derin_v2.py
