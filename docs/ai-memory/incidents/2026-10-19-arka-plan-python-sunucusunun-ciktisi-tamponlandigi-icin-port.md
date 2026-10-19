---
id: 2026-10-19-arka-plan-python-sunucusunun-ciktisi-tamponlandigi-icin-port
tarih: 2026-10-19
tur: hata            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: dusuk          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [services, python, buffering]
kurallar: []
---

# Arka plan Python sunucusunun çıktısı tamponlandığı için port algılanmadı

## Belirti
tests/test_qa_araclari.py `test_port_ciktidan_bulunur`: port verilmeden başlatılan `python -m http.server`
için port çıktıdan bulunamadı (None); 5 sn sonra "hazır" sayıldı.

## Kök neden
Doğrulandı: Python stdout boruya bağlıyken tamponlu yazar; "Serving HTTP on … port N" satırı geç geldi.

## Çözüm
Servis ortamına `PYTHONUNBUFFERED=1` (flask/django günlükleri de canlı okunur).

## Kanıt
Test geçti (12/12).

## Önleme
Alt süreç çıktısını canlı okuyacaksan tamponlamayı kapat.

## İlgili dosyalar
src/evren_studio/agent/services.py
