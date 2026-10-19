---
id: 2026-10-19-koyu-temada-ikincil-yazilar-ve-dugmeler-okunmuyordu
tarih: 2026-10-19
tur: eksik            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: ui
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [tema, kontrast]
kurallar: []
---

# Koyu temada ikincil yazılar ve düğmeler okunmuyordu

## Belirti
Kullanıcı: koyu modda bazı düğme ve yazılar aşırı sönük, yer yer okunmuyor; hepsi "Görevler"
başlığı kadar parlak olmalı.

## Kök neden
Doğrulandı: koyu palette text_dim #a2a6af ve text_faint #6d717a (zemin #16171b'de ~3,5:1);
simgeler varsayılan olarak text_dim, gezinme düğmeleri, sekmeler, ipuçları text_dim/faint.
QSS uygulanınca QLabel bağlantıları Qt'nin koyu mavisini alıyordu.

## Çözüm
Koyu temada text_dim = text_faint = text (#e8e9ec, "Görevler" ile aynı). Yalnız yer tutucu
yazı ve devre dışı öğeler için yeni `muted` belirteci (#9ca1ab, tüm koyu zeminlerde ≥4,5:1)
— etkin sanılmasınlar. Ayarlar bağlantıları vurgu rengiyle. Açık tema değişmedi.
Kullanıcı ek kararı: düğmeler mavi olmasın → koyu temada accent = #e8e9ec, accent_hover
#ffffff, accent_soft nötr #30343c, on_accent #16171b; bağlantılar altı çizili.

## Kanıt
tests/test_klavye_baglam_tema.py: `test_koyu_temada_tum_yazilar_gorevler_kadar_parlak`
(WCAG kontrast hesabı), `test_stil_yer_tutucu_ve_devre_disi_icin_muted_kullanir`;
ekran görüntüleri build/shots/tema_1_ana.png, tema_3_ayarlar.png (QT_QPA_PLATFORM=windows).

## Önleme
Yeni renk eklerken kontrast testine zemin ekle; bileşende sabit renk yazma.

## İlgili dosyalar
src/evren_studio/ui/theme.py, src/evren_studio/ui/composer.py,
src/evren_studio/ui/side_panel.py, src/evren_studio/ui/settings_page.py
