"""A13 / E3: planlayan + yazan iki motor (Aider "architect" düzeni; Qt'siz).

Zor işte (modelstats.difficulty → "zor") önce PLANLAYICI motor projeyi salt okunur inceleyip kısa bir uygulama
planı yazar; sonra YAZAN motor bu planla işi yapar. Planlayıcı Auto Pro'nun "plan" rolünden, yazan "kod" rolünden
seçilir. Planlayıcı Derin Mod'un salt okunur alt ajanıdır (deep.run_subagent): oturum geçmişini kirletmez,
onay gerektiren hiçbir şey yapamaz, sonuç bloğu yoksa R-26 gereği bir kez dürtülür ve kısa bir son tur açılır.

Ayar (`autopro_architect`) varsayılan KAPALI: gerçek API'de açık/kapalı ölçümü kazanç gösterirse açılır
(docs/knowledge/CHALLENGE_RESULTS.md "A13"). Plan alınamazsa iş planSIZ sürer — planlayıcı hatası turu bozmaz.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MARKER = "<uygulama_plani>"
PLAN_MAX_STEPS = 8
PLAN_MAX_CHARS = 4000

PROMPT = """Sen bir PLANLAYICISIN. Aşağıdaki isteği başka bir motor uygulayacak; sen yalnız planı yazacaksın.
Projeyi okuma araçlarıyla KISACA incele (en çok birkaç dosya), sonra yalnız şu bloğu yaz:

<uygulama_plani>
Amaç: (tek cümle)
Dosyalar: (değişecek / oluşturulacak dosyalar, her biri için bir satır ne yapılacağı)
Adımlar:
1. ...
Doğrulama: (işin bittiğini gösterecek komut veya kontrol)
Tuzaklar: (varsa: kodlama/BOM, mevcut testler, kapsam dışı dosyalar)
</uygulama_plani>

Kod yazma, dosya değiştirme. Kullanıcının istemediği işi plana ekleme. Belirsiz bir karar varsa planı
uydurmadan "Soru:" satırıyla belirt.

İSTEK:
{request}"""

HINT = """# Planlayıcının planı (Auto Pro: planlayan + yazan)
Bu işi önce {planner} motoru inceleyip planladı. Planı izle, ama dosyaların gerçek içeriğini kendin oku; plan
yanlış veya eksikse gerçeğe göre düzelt ve bunu yanıtında kısaca söyle. Planda "Soru:" varsa ve cevabı
projeden çıkmıyorsa kullanıcıya sor.

{plan}"""


def extract(text: str) -> str:
    """Yanıttan plan bloğu (yoksa ""). Kapanış etiketi unutulmuşsa sona kadar alınır."""
    m = re.search(r"<uygulama_plani>(.*?)(?:</uygulama_plani>|\Z)", text or "", re.S)
    plan = (m.group(1) if m else "").strip()
    return plan[:PLAN_MAX_CHARS]


def make_plan(*, client: Any, model: str, fallbacks: list[str], root: Path, request: str,
              cancel: Any = None, gate: Any = None, context_tokens: int | None = None) -> tuple[str, Any]:
    """(plan metni | "", deep.SubResult). Hata/iptal → ("", sonuç)."""
    from .deep import run_subagent

    res = run_subagent(client=client, model=model, fallbacks=list(fallbacks), root=Path(root),
                       prompt=PROMPT.format(request=request.strip()[:6000]), marker=MARKER, gate=gate,
                       cancel=cancel, max_steps=PLAN_MAX_STEPS, context_tokens=context_tokens)
    return (extract(res.text) if res.stopped != "error" else ""), res


def hint(plan: str, planner: str) -> str:
    return HINT.format(planner=planner, plan=plan) if plan else ""


def wanted(*, enabled: bool, auto_pro: bool, agentic: bool, mode: str, level: str, planner: str,
           writer: str) -> bool:
    """Planlayıcı çalıştırılsın mı? Yalnız Auto Pro + proje klasörü + Otomatik/Onaylı mod + zor iş ve
    planlayıcı ile yazan FARKLI motorsa (aynı motor kendi planını yazınca yalnız zaman harcanır)."""
    return bool(enabled and auto_pro and agentic and mode not in ("plan",) and level == "zor"
                and planner and writer and planner != writer)
