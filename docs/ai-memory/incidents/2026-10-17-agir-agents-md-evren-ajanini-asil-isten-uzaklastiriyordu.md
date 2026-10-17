---
id: 2026-10-17-agir-agents-md-evren-ajanini-asil-isten-uzaklastiriyordu
tarih: 2026-10-17
tur: surec            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [proje-hafizasi, agents-md, evren-md]
kurallar: []
---

# Ağır AGENTS.md EVREN ajanını asıl işten uzaklaştırıyordu

## Belirti
Bu deponun kopyasında "new_call_id'ye tek satırlık docstring ekle" görevi
qwen3.8-flash-next ile 23 adım / 646 sn sürdü: asıl iş 1 adım, geri kalanı
AGENTS.md'nin "ZORUNLU" törenleri (baslangic, oturum günlüğü, indeks) ve
ortamdaki ilgisiz bir yol hatası için olay kaydı açma. Kullanıcıya "aynı
işleri yapıp duruyor" gibi görünür.

## Kök neden
Doğrulandı: `Workspace.project_memory()` EVREN.md ve AGENTS.md'yi birlikte her
adımda sistem istemine ekliyordu; bu depoda EVREN.md yoktu.

## Çözüm
EVREN.md varsa yalnız o verilir (yoksa AGENTS.md, o da yoksa CLAUDE.md). Bu
depoya kısa, EVREN ajanına özel EVREN.md eklendi. AGENTS.md diğer motorlar için
aynen duruyor.

## Kanıt
`tests/test_agent_tools.py::test_proje_hafizasi` güncellendi; LOOP_ANALYSIS.md.

## Önleme
EVREN.md'yi kısa tut (EVREN.md'nin kendi başındaki not).

## İlgili dosyalar
- src/evren_studio/agent/tools.py
- EVREN.md
