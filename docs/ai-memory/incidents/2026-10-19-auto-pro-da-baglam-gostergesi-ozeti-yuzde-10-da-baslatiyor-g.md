---
id: 2026-10-19-auto-pro-da-baglam-gostergesi-ozeti-yuzde-10-da-baslatiyor-g
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [baglam, compaction, auto-pro]
kurallar: []
---

# Auto Pro'da bağlam göstergesi özeti yüzde 10'da başlatıyor gibi görünüyordu

## Belirti
Kullanıcı: "bağlam %10'da özetleniyor, bu çok düşük." Gösterge "bağlam ~100k / 1048k (10%)"
iken otomatik özet devreye giriyordu.

## Kök neden
Doğrulandı: (1) Auto Pro bir model değil ama AUTO_PRO_INFO'ya sabit 1.048.576 pencere
yazılmıştı; (2) özet eşiği bilinçli olarak min(pencerenin %75'i, 100k) — ajan her adımda tüm
geçmişi yeniden gönderdiği için (gerçek kota 2026-10-19: 5 dk'da 2,5M, günde 15M token;
100k bağlamla ~150 adım/gün, 200k ile ~75); (3) gösterge yüzdeyi tam pencereye göre
hesaplıyordu. Eşik doğruydu, gösterge ve Auto Pro penceresi yanıltıcıydı.

## Çözüm
`SessionView._window()`: Auto Pro'da pencere = sıradaki tur için seçilecek model ve
yedeklerinin en küçüğü (yedeğe geçilse de sığsın); somut modelde kendi değeri. Gösterge
yüzdesi özet eşiğine göre ("bağlam ~42k / 100k (42%)"), ipucu model penceresini ve eşiğin
nedenini yazar; özet kapalıysa pencereye göre. 100k üst sınırı korundu (Ayarlar'dan değişir).

## Kanıt
tests/test_klavye_baglam_tema.py: `test_auto_pro_penceresi_secilecek_modelden_gelir_1m_degil`,
`test_somut_modelde_pencere_kendi_degeri`, `test_gosterge_yuzdesi_ozet_esigine_gore`.
Ekran görüntüsü build/shots/tema_2_yazma.png.

## Önleme
Sanal/yönlendirici model kimliklerine (auto-pro) sabit yetenek değeri yazma; seçilecek
gerçek modelden türet.

## İlgili dosyalar
src/evren_studio/ui/session_view.py, src/evren_studio/ui/composer.py,
src/evren_studio/agent/compaction.py
