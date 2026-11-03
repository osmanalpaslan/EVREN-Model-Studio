---
id: 2026-11-03-test-dosyasi-korumasi-komutla-yapilan-degisikligi-gormuyordu
tarih: 2026-11-03
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [test-hilesi, durustluk, kapsam]
kurallar: [R-20, R-22]
---

# Test dosyasi korumasi komutla yapilan degisikligi gormuyordu

## Belirti
Kod incelemesinde bulundu (gerçek oturumda gözlenmedi). "Zayıf modeller test dosyasını değiştirip yalan
rapor veriyor" kaydının koruması (scope.TEST_EDIT_WARNING, outcome.test_edits) yalnız `edit_file`/
`write_file` yolundaydı. Model test dosyasını `run_command` ile (Set-Content, `python -c`, Remove-Item …)
değiştirir veya silerse modele uyarı gitmiyor, tur sonu "test dosyaları değiştirildi" notu çıkmıyor,
Değişiklikler sekmesinde de görünmediği için geri alınamıyordu.

## Kök neden
Doğrulandı (kod): `_test_orig` yalnız düzenleme aracının `_apply_write` yolunda dolduruluyordu; `_run_exec`
dosya sistemi değişikliğine hiç bakmıyordu.

## Çözüm
- scope.py: `snapshot_tests` (var olan test dosyaları, en çok 400 dosya / dosya başı 1 MB / toplam 16 MB) ve
  `changed_tests` (değişen veya silinen; yeni test dosyası sayılmaz).
- runner.py `_run_exec`: kullanıcı testleri değiştirmeyi istemediyse komuttan önce anlık görüntü, sonra
  karşılaştırma → komut çıktısına TEST_EDIT_WARNING ("…, komutla" / "…, komutla silindi"), değişiklik
  file_changes'e yazılır (Değişiklikler sekmesinden geri alınabilir), `_remaining_test_edits` komutla
  değişenleri de sayar (model geri yüklerse not çıkmaz).
- Kapsam dışı (bilerek): `start_job` ile arka planda çalışan uzun işler denetlenmez.

## Kanıt
- tests/test_zorluk_duzeltmeleri.py: komutla değişen (uyarı + tur notu + geri alma), komutla silinen,
  komutla geri yüklenen (not yok), dokunmayan/yeni test dosyası/kodu düzelten komut (uyarı yok, R-22),
  kullanıcı testi isterse (uyarı yok). 19/19.
- Mutasyon: `_test_cmd_check` kapatılınca tetiklenmesi gereken 3 test düştü, tetiklenmemesi gereken 2 geçti.
- Tam pytest 738/738. Zorluk paketi: CHALLENGE_RESULTS "Doğruluk turu" bölümü.

## Önleme
Yeni bir dosya koruması eklerken yalnız düzenleme aracını değil `run_command` yolunu da test et.

## İlgili dosyalar
- src/evren_studio/agent/scope.py
- src/evren_studio/agent/runner.py
- tests/test_zorluk_duzeltmeleri.py
