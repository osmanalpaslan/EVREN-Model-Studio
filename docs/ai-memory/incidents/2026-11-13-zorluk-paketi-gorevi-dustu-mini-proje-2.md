---
id: 2026-11-13-zorluk-paketi-gorevi-dustu-mini-proje-2
tarih: 2026-11-13
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: test
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: bilinmiyor
cozen_motor: Claude Code
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [gozlem, zorluk, kodlama]
kurallar: [R-21, R-25]
---

# Zorluk paketi görevi düştü: mini_proje (ikinci kök neden: kontrolün yarım UTF-8 ortamı)

## Belirti
Gözlem ajanından: "kalan kontroller: kendi testleri geçiyor" (mini_proje 4/5). 2026-11-13 21:10 tam paket ve tek başına
tekrarında (325 sn, süre İÇİNDE bitti) ajanın kendi `python -m unittest discover -s tests -v` koşusu çıkış 0, kontrol
betiğinde "FAILED (failures=2)": 'ıstanbul' beklenirken çift kodlanmış metin.
(İlk kök neden — 6 dk sınırı / uzun kod — ayrı kayıtta: 2026-11-13-zorluk-paketi-gorevi-dustu-mini-proje, izleniyor.)

## Kök neden
Doğrulandı. Modelin testi programı alt süreçte `text=True` ile çalıştırıp çıktıyı yerel kodlamayla okuyor. Üç ortam:
- ajanın ortamı (`agent/tools.project_env`: PYTHONUTF8=1 + PYTHONIOENCODING=utf-8): ikisi de UTF-8 → GEÇER;
- düz Windows (değişken yok): ikisi de cp1254 → GEÇER;
- kontrol betiğinin eski ortamı (yalnız PYTHONIOENCODING=utf-8): çocuk UTF-8 yazar, test cp1254 okur → DÜŞER.
Yani model kodu ve testi gerçek kullanım ortamlarında doğru; düşüş ölçüm ortamının yarım ayarından.

## Çözüm
`tests/e2e_zorluk_real_api.py::unittest_ok`: modelin kendi testleri İKİ ortamda koşar — uygulamanın ajana verdiği ortam
(project_env) ve hiçbir kodlama değişkeni eklenmemiş düz ortam; ikisinde de geçmeli. Denetim gevşetilmedi: yalnız UTF-8
kipinde geçen (ortama bağımlı) bir test artık "düz ortamda" diye düşer (eskiden yakalanmıyordu).

## Kanıt
R-25 bilinen doğru/yanlış sınaması (scratch kontrol_bilinen.py): doğru proje (True, OK) · yanlış (False, FAILED) ·
yalnız UTF-8 kipinde geçen (False, "düz ortamda: FAILED"). 2026-11-13 tekrar koşusunun çıktı klasörü yeni kontrolle
(True, OK). Gözlem c9b5c1591110: 7 kez, son 2026-11-13T18:43:53+00:00.

## Önleme
Kontrol artık ajanın gerçek ortamını kullanır (kopya ortam değil). Ders (dersler.md §12): "geçti" kanıtı en az bir temiz
ortamda alınır; yarım ayarlı ölçüm ortamı yanlış alarm üretir.

## İlgili dosyalar
- tests/e2e_zorluk_real_api.py (unittest_ok)
- src/evren_studio/agent/tools.py (project_env)
