---
id: 2026-10-15-gitignore-secrets-kalibi-kaynak-modulu-disladi
tarih: 2026-10-15
tur: hata
onem: kritik
durum: cozuldu
alan: git/depo
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Git 2.55
etiketler: [gitignore, temiz-klon, guvenlik]
kurallar: [R-02]
---

# .gitignore `secrets*` kalıbı kaynak modülü depodan dışladı

## Belirti
İkinci bilgisayarda temiz klondan sonra `pytest` toplama aşamasında
`ImportError: cannot import name 'secrets' from 'evren_studio'` verdi;
uygulama açılmadı (`ModuleNotFoundError: evren_studio.secrets`).

## Kök neden
Doğrulandı: `.gitignore`'daki `secrets*` kalıbı (API anahtarı içerebilecek
dosyalar için eklenmişti) `src/evren_studio/secrets.py` kaynak modülünü de
eşledi. Dosya ilk bilgisayarda vardı ama hiç commit edilmedi; ilk
bilgisayardaki testler bu yüzden geçiyordu. `git check-ignore -v` sonucu:
`.gitignore:28:secrets*  src/evren_studio/secrets.py`.

## Çözüm
Modül kullanım yerleri ve testlerden yeniden yazıldı; `.gitignore`'a
`!src/evren_studio/secrets.py` istisnası eklendi. PR #1 (`25f582c`,
birleştirme `59a19e6`). Not: ilk bilgisayardaki özgün dosya biraz farklı
olabilir; o makinede pull öncesi karşılaştırılmalı.

## Kanıt
PR #1 sonrası temiz durumda `pytest`: 53/53, `SMOKE_OK`.

## Önleme
R-02. `tests/test_source_hygiene.py` git'in yok saydığı `.py` kaynak dosyası
olmadığını denetler.

## İlgili dosyalar
.gitignore, src/evren_studio/secrets.py
