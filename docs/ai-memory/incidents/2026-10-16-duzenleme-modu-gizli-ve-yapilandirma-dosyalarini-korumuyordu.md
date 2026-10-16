---
id: 2026-10-16-duzenleme-modu-gizli-ve-yapilandirma-dosyalarini-korumuyordu
tarih: 2026-10-16
tur: eksik
onem: yuksek
durum: cozuldu
alan: guvenlik/kod-ajani
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12
etiketler: [izinler, env, korumali-yol, gizlilik]
kurallar: [R-14]
---

# Düzenleme modu gizli ve yapılandırma dosyalarını korumuyordu

## Belirti
Claude Code'un izin modlarıyla karşılaştırırken bulundu: 0.2.0'daki
"Otomatik düzenleme" modunda ajan `.env`, `.vscode/`, `.github/workflows/`
gibi dosyalara onaysız yazabiliyordu; yalnızca `.git/` engelliydi. Ayrıca
her modda `.env` içeriği okunup EVREN'e gönderilebiliyor ve `search_files`
sonuçlarında gizli değerler görünebiliyordu.

## Kök neden
Doğrulandı (kod incelemesi): izin politikası yalnızca araç türüne (okuma/
yazma/komut) bakıyordu; hedef yola bakmıyordu.

## Çözüm
`permissions.py`: `PROTECTED_WRITE` (yazma her modda sorulur) ve
`SENSITIVE_READ` (okuma her modda sorulur; `.env.example` gibi örnekler hariç).
`ToolBox.search_files` gizli dosyaları atlar ve kaç dosya atlandığını söyler.
Onay kutusu "Neden soruluyor" gerekçesini gösterir.

## Kanıt
`tests/test_auto_mode.py::test_korumali_dosyalar_ve_gizli_okumalar`,
`test_aramada_gizli_dosya_atlanir`, `test_gizli_dosya_okumasi_sorulur_reddedilirse_okunmaz`.

## Önleme
R-14 (mod anahtarları) ile birlikte: yeni araç eklerken yol tabanlı korumayı uygula.

## İlgili dosyalar
src/evren_studio/agent/permissions.py, src/evren_studio/agent/tools.py, src/evren_studio/agent/runner.py
