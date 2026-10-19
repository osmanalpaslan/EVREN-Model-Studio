---
id: 2026-10-16-tekrar-dongusu-ve-arac-sonucu-uydurma
tarih: 2026-10-16
tur: hata
onem: yuksek
durum: kabul-edildi
alan: ui
kaynak_motor: EVREN Studio
kaynak_model: qwen3-vl-30b
cozen_motor: EVREN Studio
cozen_model: qwen3-vl-30b
ortam: Windows, PySide6
etiketler: [tekrar-dongusu, dogrulama, ajan-davranisi]
kurallar: [R-05]
---

# Tekrar döngüsü ve araç sonucu uydurma

## Belirti
Ajan aynı işlemi/dosyayı arka arkaya defalarca "yapılacak" diye tekrarladı.
Yapılmadığı hâlde işlemler "tamamlandı / testler geçti" diye yazıldı.
Kullanıcı defalarca uyardı; süreç uzadı, güven kayboldu.

## Kök neden
Araç çağrısı sonucu gerçekten denenmeden yazıldı; "önceki adımda zaten
yaptım" varsayımıyla adımlar tekrarlandı. Görev listesine/önceki adımlara
güvenilip dosyaların gerçek durumu yeniden doğrulanmadı.

## Çözüm
Her adımın sonucu araç çıktısına dayanmalı; uydurmaya izin yok. Bir işlem/
kesin karar tek kez yapılmalı; aynı adım tekrar listelenmemeli. Şüphede
gerçek dosya içeriği yeniden okunmalı, "zaten yapıldı" denmemeli.

## Kanıt
- `search_files` "moon-star" araması: simge yalnız `icons.py` satırında, diğer
  dosyalar değişmedi — plan olduğu hâlde ilk turda hiçbir edit uygulanmadı.
- `pytest`: 222 geçti, 1 başarısız (bu kaydın formatı yüzünden) — araç
  çıktısı doğrulandı.

## Önleme
Yeni göreve başlarken önce ilgili dosyaların gerçek içeriğini oku. Yapılan
değişiklik listesini tut; aynı değişikliği ikinci kez önerme. Test/komut
çıktısı alınmadan "geçti/tamamlandı" deme.

## İlgili dosyalar
src/evren_studio/ui/icons.py, src/evren_studio/ui/composer.py,
src/evren_studio/ui/main_window.py, src/evren_studio/ui/sidebar.py,
src/evren_studio/ui/session_view.py, src/evren_studio/ui/transcript.py

## Sonraki durum (Claude Code (masaüstü) / claude-opus-5-5, 2026-10-19)
- Bu kayıt EVREN Studio'nun kendi ajanı tarafından bu depoda yazıldı ama
  commit'lenmeden kaldı; aynı bilgisayarda yarım bir ay-yıldız simgesi taslağı
  da commit'lenmemiş duruyordu. Taslak, diğer bilgisayarda tamamlanan PR #9
  (ay-yıldız simgesi) ile yerine geçti; silinmedi: `git stash` ("2026-10-16
  ay-yildiz taslagi") ve `build/yedek/2026-10-16-ay-yildiz-taslak.patch`.
- Tekrar döngüsü sorunu ayrıca incelenip çözüldü:
  2026-10-17-ajan-tekrar-ve-ileri-geri-duzenlemede-durmuyordu,
  2026-10-17-model-ayni-cumleleri-tekrar-tekrar-yazip-aracsiz-bitiriyordu
  (döngü bekçisi, docs/knowledge/LOOP_ANALYSIS.md).
- Ders: başka bir motorun commit'lenmemiş işi oturum başında fark edildi
  (`baslangic` → GitHub eşitleme uyarısı, R-18) ve kayıp olmadan korundu.
