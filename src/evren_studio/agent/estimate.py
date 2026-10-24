"""F5 #5 Derin/Proje öncesi süre ve token tahmini (Qt'siz). KABA tahmindir; arayüz bunu açıkça söyler.

Kaynaklar (varsa, öncelik sırasıyla):
- süre: geçmiş proje çalışmalarında BİTEN görevlerin süreleri (project_runs.state_json → task.seconds);
  yoksa son model çağrılarının ortanca süresi × görev başına çağrı (CALLS_PER_TASK); o da yoksa varsayılan aralık.
- token: son asistan mesajlarının (prompt + completion) ortancası × görev başına çağrı.
Görev başına çağrı sayısı zorluk paketi ölçümlerinden (görev başına ~3–8 adım) — 6 alındı.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass

CALLS_PER_TASK = 6
DEFAULT_TASK_S = (120.0, 300.0)       # veri yoksa görev başına 2–5 dk
DEFAULT_CALL_TOKENS = 15_000
MIN_HISTORY = 5


@dataclass
class Estimate:
    low_s: float
    high_s: float
    tokens: int
    basis: str

    def text(self, daily_remaining: float | None = None) -> str:
        lo, hi = max(1, round(self.low_s / 60)), max(1, round(self.high_s / 60))
        dur = f"~{lo} dk" if lo == hi else f"~{lo}–{hi} dk"
        tok = f"~{self.tokens / 1_000_000:.1f}M token" if self.tokens >= 1_000_000 else f"~{self.tokens // 1000}k token"
        quota = ""
        if daily_remaining:
            pct = 100 * self.tokens / max(daily_remaining, 1)
            quota = f" (bugün kalan kotanın ~%{pct:.0f}'i)" if pct < 1000 else " (bugün kalan kotayı AŞABİLİR)"
        return f"süre {dur}, {tok}{quota} — kaba tahmin; {self.basis}."


def task_seconds(state_jsons: list[str]) -> list[float]:
    out = []
    for js in state_jsons:
        try:
            d = json.loads(js or "{}")
        except ValueError:
            continue
        for t in d.get("tasks") or []:
            if t.get("status") == "bitti" and (t.get("seconds") or 0) > 5:
                out.append(float(t["seconds"]))
    return out


def call_tokens(metas: list[str | dict]) -> list[int]:
    out = []
    for m in metas:
        try:
            d = json.loads(m) if isinstance(m, str) else (m or {})
        except ValueError:
            continue
        u = d.get("usage") or {}
        n = int(u.get("prompt_tokens") or 0) + int(u.get("completion_tokens") or 0)
        if n > 0:
            out.append(n)
    return out


def estimate(n_tasks: int, task_s: list[float], call_s: list[float], tokens: list[int]) -> Estimate:
    n = max(1, int(n_tasks))
    per_call_tok = int(statistics.median(tokens)) if len(tokens) >= MIN_HISTORY else DEFAULT_CALL_TOKENS
    tok = n * CALLS_PER_TASK * per_call_tok
    if len(task_s) >= MIN_HISTORY:
        q = statistics.quantiles(task_s, n=4)
        return Estimate(n * q[1], n * q[2], tok, f"geçmiş {len(task_s)} görevin süresinden")
    if len(call_s) >= MIN_HISTORY:
        med = statistics.median(call_s)
        return Estimate(n * CALLS_PER_TASK * med, n * CALLS_PER_TASK * med * 1.8, tok,
                        f"son {len(call_s)} model çağrısının ortanca süresinden")
    return Estimate(n * DEFAULT_TASK_S[0], n * DEFAULT_TASK_S[1], tok, "henüz ölçüm yok, varsayılan aralık")
