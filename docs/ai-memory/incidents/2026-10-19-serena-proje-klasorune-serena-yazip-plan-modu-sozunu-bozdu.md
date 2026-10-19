---
id: 2026-10-19-serena-proje-klasorune-serena-yazip-plan-modu-sozunu-bozdu
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: yuksek          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: mcp
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [mcp, serena, plan-modu, R-22]
kurallar: [R-22]
---

# Serena proje klasörüne .serena yazıp Plan modu sözünü bozdu

## Belirti
Zorluk paketi Serena AÇIK (`--serena`): 10/12. `plan` ve `kapsam` görevlerinde "yeni dosya yok"
denetimi düştü — yeni dosya `.serena/`; model hiç MCP aracı çağırmamıştı (MCP 0). MCP kapalı
koşuda 12/12.

## Kök neden
Doğrulandı: Serena 1.7.0 açılışta proje klasöründe `.serena/` (project.yml, önbellek, .gitignore)
oluşturur; ayrıca `%USERPROFILE%\.serena`'ya günlük ve genel proje listesi yazar. Plan modunun
"dosyaya dokunmaz" sözü ve kapsam denetimi bozuldu. İlk çözümüm (.git/info/exclude) yalnız git
commit'ini gizliyordu, dosya yine oluşuyordu — yetersizdi.

## Çözüm
Serena sürecine proje başına `SERENA_HOME` (<veri>/mcp/serena/home/<ad>-<sha1>) verilir; ev
klasörüne `projects: []` + `project_serena_folder_location: <home>/proje/.serena` içeren
serena_config.yml önceden yazılır. Proje klasörüne ve kullanıcı ev klasörüne yazma kalmadı.
.git/info/exclude kodu kaldırıldı.

## Kanıt
Elle: build/mcp_proje2 üzerinde Serena çalıştı, klasörde yalnız ana.py ve hesap.py kaldı.
tests/test_mcp.py `test_serena_proje_basina_ayri_ev_klasoru_proje_klasorune_yazmaz`;
e2e_mcp_real_api.py her koşuda ".serena proje klasörüne yazılmadı" denetimi; zorluk paketi
Serena açık yeniden koşu (sonuç CHALLENGE_RESULTS.md).

## Önleme
R-22 bunu yakaladı: yeni dış bileşeni zorluk paketinin TAMAMIYLA açık/kapalı ölç.
Dış sunucunun dosya sistemi yan etkilerini (proje ve ev klasörü) ilk denemede listele.

## İlgili dosyalar
src/evren_studio/agent/mcp.py (serena_home, prepare_serena_home, SERENA_ENV)
