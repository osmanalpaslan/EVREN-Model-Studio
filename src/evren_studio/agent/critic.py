"""Gidiş eleştirmeni (Madde 20 B4, 2026-11-11; OpenHands "verification stack" fikri): gözetimsiz görevde ajan raydan
çıkıyor mu, ayrı ve HIZLI bir modelle ara ara puanlar.

Neden: Proje/Derin görevinde ajan yanlış yola girdiğinde (ilgisiz dosyaları kurcalama, aynı hatayı farklı biçimde
tekrarlama, görevin dışına taşma) bunu ancak tur bitince inceleme görüyor — o zamana kadar dakikalar ve onlarca adım
gidiyor. Döngü bekçisi yalnız BİREBİR tekrarı yakalar.

Nasıl (temkinli; yanlış alarm işi bozar, R-22):
- Her `every` adımda bir (ilk kontrol `every`. adımda) son mesajların kısa dökümü + görev metni hızlı modele gider;
  model JSON döndürür: {"puan": 0-10, "neden": "...", "oneri": "..."}.
- puan ≤ `low` → İLK seferde ajana yalnız NOT düşülür (eleştirmenin önerisi; iş sürer). Bir sonraki kontrol de düşükse
  tur "critic" ile durur; Proje yürütücüsü bunu başarısız deneme sayar ve eleştirmenin gerekçesiyle TEMİZ bağlamda
  yeniden dener. Arada iyi puan gelirse sayaç sıfırlanır.
- Eleştirmen çağrısı hata verir / yanıt okunamazsa: hiçbir şey yapılmaz (iş asla eleştirmen yüzünden durmaz).
- Görevin son kısmı (ör. testler geçiyor, özet yazılıyor) erken bitişe yakın: `min_steps` altındaki turda kontrol yok.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from . import jsonfix

CRITIC_SYSTEM = (
    "Bir kod ajanının çalışmasını izleyen eleştirmensin. Sana görev ve ajanın son adımları verilecek. Ajanın görevi "
    "bitirmeye doğru İLERLEYİP İLERLEMEDİĞİNİ puanla. Yalnız JSON yaz: {\"puan\": 0-10, \"neden\": \"kısa\", "
    "\"oneri\": \"ajanın şimdi yapması gereken tek somut şey\"}.\n"
    "Puan rehberi: 8-10 görevle ilgili dosyalarda ilerliyor (okuma, düzenleme, test çalıştırma, hatayı düzeltme normaldir); "
    "5-7 yavaş ama yolunda; 0-3 YALNIZ açık raydan çıkma: görevle ilgisiz işler, aynı başarısız yaklaşımı farklı biçimde "
    "tekrarlama, görevi bırakıp başka şey yapma, testleri silme/zayıflatma. Emin değilsen 6 ver. Hata alıp düzeltmeye "
    "çalışmak raydan çıkmak DEĞİLDİR.")

TOOL_ARG_CHARS = 200
TOOL_OUT_CHARS = 400
TEXT_CHARS = 500
TAIL = 16


def digest(history: list[dict], tail: int = TAIL) -> tuple[str, str]:
    """(görev metni, son adımların kısa dökümü). Görev = ilk kullanıcı mesajı."""
    task = next((str(m.get("content") or "") for m in history if m.get("role") == "user"), "")
    lines = []
    for m in history[-tail:]:
        role = m.get("role")
        if role == "assistant":
            text = str(m.get("content") or "").strip()
            if text:
                lines.append(f"[ajan] {text[:TEXT_CHARS]}")
            for c in m.get("tool_calls") or []:
                fn = c.get("function") or c
                args = str(fn.get("arguments") or "")
                lines.append(f"[araç] {fn.get('name')}({args[:TOOL_ARG_CHARS]})")
        elif role == "tool":
            meta = m.get("meta") or {}
            mark = "HATA " if meta.get("error") else ""
            lines.append(f"[sonuç {m.get('name') or ''}] {mark}{str(m.get('content') or '')[:TOOL_OUT_CHARS]}")
        elif role == "user" and m is not history[0]:
            lines.append(f"[kullanıcı/not] {str(m.get('content') or '')[:TEXT_CHARS]}")
    return task[:6000], "\n".join(lines)


def critic_messages(history: list[dict], step: int) -> list[dict]:
    task, steps = digest(history)
    return [{"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": f"GÖREV:\n{task}\n\nAJANIN SON ADIMLARI (toplam {step} adım):\n{steps}"}]


def parse(text: str) -> tuple[int | None, str, str]:
    data = jsonfix.obj(text or "")
    if not isinstance(data, dict):
        return None, "", ""
    try:
        score = int(round(float(data.get("puan"))))
    except (TypeError, ValueError):
        return None, "", ""
    return max(0, min(10, score)), str(data.get("neden") or "")[:300], str(data.get("oneri") or "")[:300]


@dataclass
class Critic:
    """AgentRunner'a verilir: `check(step, history)` → None (devam) | ("not", metin) | ("dur", gerekçe)."""
    chat: Callable[[list[dict]], str]           # mesajlar → model yanıtı (hızlı, ayrı model; ai_chat("elestirmen"))
    every: int = 8
    low: int = 3
    min_steps: int = 8
    strikes: int = 0
    log: list[dict] = field(default_factory=list)   # ölçüm: her kontrolün puanı (R-22 yanlış alarm oranı)

    def due(self, step: int) -> bool:
        return step >= self.min_steps and step % self.every == 0

    def check(self, step: int, history: list[dict]):
        if not self.due(step):
            return None
        try:
            score, why, tip = parse(self.chat(critic_messages(history, step)))
        except Exception:                       # eleştirmen asla işi düşürmez
            return None
        self.log.append({"adim": step, "puan": score, "neden": why})
        if score is None:
            return None
        if score > self.low:
            self.strikes = 0
            return None
        self.strikes += 1
        if self.strikes == 1:
            return ("not", "Gözetmen notu (ayrı model, adım " + str(step) + "): çalışma görevden uzaklaşıyor olabilir — "
                    + (why or "ilerleme görünmüyor") + (". Öneri: " + tip if tip else "")
                    + ". Görev ölçütüne dön; gerekmeyen işi bırak.")
        return ("dur", why or "ajan iki kontrol üst üste görevden uzaklaştı")


def to_json(log: list[dict]) -> str:
    return json.dumps(log, ensure_ascii=False)
