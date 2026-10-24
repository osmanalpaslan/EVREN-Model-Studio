---
id: 2026-10-24-claude-code-masaustu-f4-skill-menusu-ve-profiller
tarih: 2026-10-24
motor: Claude Code (masaüstü)
model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
dal: feat/f4-skill-profiller
sonuc: tamamlandi        # tamamlandi | kismi | basarisiz | devam-ediyor
---

# F4 skill menüsü ve profiller

## Görev
Kullanıcı: "F4'e başla." Kapsam (ILERIDE 7.5): 7.2 skill menüsü + read_skill, E5 profiller, #10 şablonlar,
#13 skill denetçisi, #14 betikleştir. Kabul: proje bazlı aç/kapa kalıcı; model skill'i gerçekten okuyor (R-25).

## Yapılanlar
- agent/skills.py: SKILL.md ön bilgi (name, description, denetci/checker), kopyalayarak ekleme, kaynaktan yenileme,
  kapsam (tüm / seçili projeler / hiçbiri), istem bölümü (yalnız ad + ≤300 karakter açıklama), güvenli okuma.
- read_skill aracı (salt okunur; yalnız etkin skill varken sunulur; başka projenin skill'i okunamaz).
- DB: skills, profiles, templates tabloları; sessions.profile sütunu.
- ui/skills_page.py "Skill'ler ve Profiller": skill listesi (aç/kapa, kapsam, projeler, yenile, kaldır — kaynak
  klasöre dokunmaz), profil penceresi (motor, mod, skill seçimi, ek talimat), şablonlar (5 yerleşik + kullanıcı).
- Oturum: başlıkta profil çipi + /profil; profil talimatı ve skill'ler tura; tur sonu skill denetçisi (Otomatik
  modda sormadan, diğerlerinde kart; geçti → Betikleştir, kaldı → Ajana düzelttir); /betiklestir.
- Faz dışı: MCP sunucu penceresindeki İngilizce Ok/Cancel düğmeleri Türkçeleştirildi.

## Test sonuçları
- pytest 600/600 (F4: tests/test_f4_skill_profil.py 13).
- Ekran görüntüleri (koyu + açık): Skill'ler sayfası, profil penceresi (düğmeler önce İngilizceydi → düzeltildi),
  profil çipi + denetçi kartları — bakıldı.
- Gerçek API (R-25, tests/e2e_skill_real_api.py, Auto Pro): skill açık 4/4, read_skill 2 (SKILL.md + references);
  skill kapalı: model kuralı uydurmadı, kullanıcıya sordu (fatura.py yazılmadı — beklenen); konu dışı iş: read_skill 0.
  Zorluk 12/12 · 518 sn. R-13: E2E_OK · ajan 6/6 · arayüz 15/15.

## Sorunlar ve kayıtlar
- 2026-10-24-karsilama-ekraninda-profil-uygulamak-modal-bilgi-kutusu-aciy

## Sonraki motor için notlar
- Derin Mod alt ajanları (deep.run_subagent) skill almıyor; gerekirse ileride eklenmeli (Proje ajanı görevleri alıyor).
- Kullanıcının gerçek hesap kapama skill'i bu düzende henüz denenmedi (ölçüm sahte "fatura-kurallari" skill'iyle).
- Godot şablonu F7'de eklenecek. Sıradaki: F5 (arayüz).
