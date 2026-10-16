---
id: 2026-10-15-code-studio-ajan-ozellikleri-eksikti
tarih: 2026-10-15
tur: eksik
onem: yuksek
durum: cozuldu
alan: ozellik/kod-ajani
kaynak_motor: Kilo Code (VS Code eklentisi)
kaynak_model: bilinmiyor (EVREN LLM)
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, PySide6 6.12
etiketler: [code-studio, ajan, kapsam]
kurallar: [R-05]
---

# Code Studio'da kod ajanı özellikleri yoktu

## Belirti
Kullanıcı "Claude Code masaüstü gibi bir proje geliştirme alanı" istemişti.
Code Studio yalnızca klasör açma, dosya ağacı, düz metin düzenleyici ve
kaydetme sunuyordu: AI ile kod üretme, diff, onaylı uygulama, komut
çalıştırma, görev listesi, geri alma yoktu.

## Kök neden
Doğrulandı: özellikler bilinçli olarak "Aşama 2"ye bırakılmıştı ve bu
`KNOWN_LIMITATIONS.md`'de yazıyordu; ancak kullanıcıya verilen rapor ve
arayüzdeki "Code Studio" adı beklentiyi karşılamıyordu. Ayrıca EVREN'in
araç çağrısı doğrulanmadığı için ajan tasarımı ertelenmişti.

## Çözüm
0.2.0'da `src/evren_studio/agent/` ile kod ajanı eklendi: 8 araç, izin
modları, diff'li onay, geri alma, görev listesi, metin protokolü geri
dönüşü; oturum tabanlı yeni arayüz. PR #2.

## Kanıt
`tests/test_agent_*.py`, `tests/test_ui_agent_flow.py` (104/104 geçti).
Gerçek EVREN ile araç turu ayrıca açık kayıtta izleniyor:
2026-10-16-evren-arac-cagrisi-gercek-apide-dogrulanmadi.

## Önleme
R-05: kullanıcıya rapor verirken neyin gerçekten çalıştığını ve neyin
eksik olduğunu aynı ayrıntıda söyle.

## İlgili dosyalar
src/evren_studio/agent/, src/evren_studio/ui/session_view.py
