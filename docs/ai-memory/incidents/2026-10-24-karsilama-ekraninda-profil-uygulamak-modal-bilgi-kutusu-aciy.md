---
id: 2026-10-24-karsilama-ekraninda-profil-uygulamak-modal-bilgi-kutusu-aciy
tarih: 2026-10-24
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [F4, profil, modal, test-asilmasi]
kurallar: []
---

# Karşılama ekranında profil uygulamak modal bilgi kutusu açıyordu

## Belirti
F4 birim testi sessizce asıldı (pytest çıktısı yok, zaman aşımı). `SessionView.apply_profile` oturum açılmadan
(karşılama ekranı, ör. şablondan profil) çağrılınca `_note` → `QMessageBox.information` modal kutu açıyordu; testte
kapatan olmadığı için bekledi. Gerçek kullanımda şablon her kullanıldığında gereksiz bir kutu çıkacaktı.

## Kök neden
Doğrulandı: `_note` oturum yokken ve transcript görünmüyorken bilgi kutusu gösterir (bilinçli davranış; komutlar
için). Yeni çağrı yolu bunu hesaba katmadı.

## Çözüm
`apply_profile` karşılama ekranında not yazmaz; profil başlıktaki çipte görünür. `/betiklestir` gibi kullanıcı
komutlarında kutu kalır (testte kutu yakalanarak sınandı).

## Kanıt
tests/test_f4_skill_profil.py::test_profil_filtresi_uygulama_ve_oturumda_kalicilik, test_betiklestir_ve_sablon.

## Önleme
Yeni bir yoldan `_note` çağırırken karşılama ekranı durumunu düşün; asılan Qt testini önce tek tek, zaman aşımıyla
çalıştırıp hangi testin beklediğini bul.

## İlgili dosyalar
- src/evren_studio/ui/session_view.py
