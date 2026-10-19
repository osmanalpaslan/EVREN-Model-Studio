---
id: 2026-10-19-canli-model-listesi-yalniz-modeller-sayfasi-acilinca-yukleni
tarih: 2026-10-19
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [models, startup]
kurallar: []
---

# Canlı model listesi yalnız Modeller sayfası açılınca yükleniyordu

## Belirti
Canlı EVREN model listesi (yetenek bayrakları, yeni modeller) yalnız Modeller
sayfası açılınca yükleniyordu; açılışta yedek statik liste kullanıldığı için
`reasoning_effort` gibi bayraklar yoktu.

## Kök neden
Doğrulandı: yükleme yalnız models_page açılışına bağlıydı.

## Çözüm
`SessionView.load_live_models()` eklendi; app.py açılıştan 1 sn sonra arka planda
çağırır (testler MainWindow'u doğrudan kurduğu için ağ isteği yapmaz). Ayrıca
yedek listeye yetenek bayrağı eklendi.

## Kanıt
Uygulama açılışında model listesi canlı veriyle doldu (elle gözlendi);
tests/test_auto_pro.py `test_yedek_listede_dusunme_yetenegi_isaretli`.

## Önleme
Yeteneğe bağlı karar veren kod yedek listede de bayrağı bulmalı.

## İlgili dosyalar
src/evren_studio/app.py, src/evren_studio/ui/session_view.py,
src/evren_studio/ui/app_context.py
