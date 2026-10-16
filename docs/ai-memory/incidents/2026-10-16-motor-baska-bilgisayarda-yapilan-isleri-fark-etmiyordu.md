---
id: 2026-10-16-motor-baska-bilgisayarda-yapilan-isleri-fark-etmiyordu
tarih: 2026-10-16
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu
alan: surec
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [git, cok-bilgisayar, esitleme]
kurallar: [R-18]
---

# Motor başka bilgisayarda yapılan işleri fark etmiyordu

## Belirti
Kullanıcı birden fazla bilgisayarda geliştiriyor. Bir bilgisayarda yapılıp
GitHub'a gönderilen iş, diğer bilgisayarda açılan motor oturumunda görünmüyordu.
`baslangic` yerel (eski) hafızayı okuyordu; kullanıcı "git pull" yapmayı
unutursa motor eski koda göre çalışıp işi tekrarlayabilir veya çakışma
üretebilirdi. Kullanıcı bunu kendisinin yapamayabileceğini söyledi.

## Kök neden
Doğrulandı: protokolde (AGENTS.md §1) ve `tools/ai_memory.py baslangic`
komutunda uzak depo kontrolü yoktu. Ortak hafıza git ile taşındığı için ancak
çekildiğinde güncel olur.

## Çözüm
`baslangic` artık hafızayı okumadan ÖNCE `sync_with_remote()` çalıştırır:
- `git fetch --prune origin` (45 sn zaman aşımı; ağ yoksa açık uyarı).
- Geride + temiz + gönderilmemiş commit yok → `merge --ff-only` ile otomatik alır.
- Bulunulan dal master'a tamamen birleştirilmiş ve ağaç temizse master'a geçer.
- Yerel değişiklik veya ayrışmış dal varsa DOKUNMAZ, nedenini ve komutu yazar.
- Gönderilmemiş commit, GitHub'da silinmiş dal, master'da yeni iş için uyarır.
- `--esitleme-yok` bayrağı veya `EVREN_AI_MEMORY_NO_SYNC` ile kapatılır.

## Kanıt
`tests/test_ai_memory_sync.py` (10 test, geçici çıplak depo + iki klon):
eşit, otomatik ileri sarma, yerel değişiklik korunur, ayrışmış dal korunur,
gönderilmemiş commit, birleşmiş daldan master'a geçiş, otomatik kapalı,
uzak depoya erişilemedi, origin yok, git deposu değil. Bu depoda elle
çalıştırıldı: gönderilmemiş dal ve commit'lenmemiş değişiklik doğru raporlandı.

## Önleme
Kural R-18. AGENTS.md §1 adım 1 güncellendi.

## İlgili dosyalar
- tools/ai_memory.py
- tests/test_ai_memory_sync.py
- AGENTS.md
