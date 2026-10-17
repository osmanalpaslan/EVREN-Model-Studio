---
id: 2026-10-17-ajan-istenmeyen-tasarim-degisikligi-yapiyordu-kapsam-tasmasi
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
etiketler: [kapsam, tasma, tasarim, model-davranisi]
kurallar: [R-20]
---

# Ajan istenmeyen tasarım değişikliği yapıyordu (kapsam taşması)

## Belirti
Kullanıcı (2026-10-17): simge isteğini EVREN ajanına verdi; ajan belirtilmediği
hâlde arayüz tasarımını değiştirip simgeleri başka alanlara da ekledi; kullanıcı
geliştirmeyi elle geri aldı. (Oturum kaydı kullanıcı tarafından silindi.)

## Kök neden
Model davranışı + uygulamada kapsam koruması yoktu: sistem isteminde "yalnız
isteneni yap" kuralı yoktu, tur sonunda değişikliklerin istekle uyumu
denetlenmiyordu, değişiklikler tura bağlı kaydedilmediği için (turn_id hep NULL)
"turu geri al" yapılamıyordu.

## Çözüm
1. prompts.AGENT_RULES başına "Kapsam (EN ÖNEMLİ KURAL)": yalnız isteneni yap,
   ek iyileştirmeyi uygulama → "Öneriler", belirsizse önce sor.
2. agent/scope.py: tur bitince istek + farklar hızlı modele (deepseek-v4-flash,
   düşünmesiz) verilir; kapsam dışı dosyalar uyarı kartında, "Kapsam dışını geri al".
   Onay istemez. Ayarlar: kapsam denetimi (varsayılan açık).
3. Değişiklikler tura bağlı (turn_id = turu başlatan kullanıcı mesajı); tur
   sonu kartı "Bu tur N dosyayı değiştirdi" + "Turu geri al".
4. Ayarlar: "Önce plan" (varsayılan kapalı): tur salt okunur plan turu olarak
   başlar, "Uygula" ile seçili modda uygulanır. Plan modunda niyet cümlesi dürtülmez.

## Kanıt
Kullanıcının GERÇEK isteği, EVREN Studio deposunun simge öncesi kopyası (ab179ed),
Otomatik mod, gerçek API:

| Model | Kural | Değişen dosya | Kapsam dışı (inceleme) | Denetim işaretledi |
|---|---|---|---|---|
| auto | eski | 8 | theme.py'den `scrollbar` alanı silindi (çökme hatası; kapsam değil doğruluk) | — |
| auto | yeni | 6 | — | — |
| gemma-4-31b | eski | 5 | composer.py: mod/komut simgeleri ay-yıldıza çevrildi | ✓ composer.py |
| gemma-4-31b | yeni | 2 | genel `spark` simgesi değişti (başka düğmeleri de etkiler) | ✓ icons.py (+ transcript.py, kısmen yanlış) |
| qwen3.8-flash-next | eski | 8 | araç kartlarına istenmeyen dönen gösterge (spin.py) | ✓ spin.py, transcript.py |
| qwen3.8-flash-next | yeni | 1 | — (40 adımda bitmedi) | — |
| deepseek-v4-flash | eski | 2 | tools/_flag_probe.py (geçici deneme dosyası) | ✓ |
| deepseek-v4-flash | yeni | 5 | — (40 adımda bitmedi) | — |

Yeni kuralla değişen dosya sayısı düştü (auto 8→6, gemma 5→2, qwen 8→1);
eski kuralda görülen 3 kapsam taşmasının 3'ünü denetim işaretledi. Bilinen kapsam
dışı değişiklik içeren yapay örnekte denetim 3/3 doğru (theme.py + settings_page.py,
istenen dosyalara dokunmadı). Sınır: denetim "istenmemiş" değişikliği bulur,
"hatalı" kodu değil (auto'nun scrollbar silmesi) — onu testler bulur.
Birim/arayüz: tests/test_scope.py (7), pytest tam paket geçti.

## Önleme
R-20. Büyük/yoruma açık işlerde "Önce plan" ayarı; kod işlerinde deepseek-v4-flash.

## İlgili dosyalar
- src/evren_studio/agent/prompts.py
- src/evren_studio/agent/scope.py
- src/evren_studio/ui/session_view.py
- src/evren_studio/ui/side_panel.py
- src/evren_studio/ui/transcript.py
