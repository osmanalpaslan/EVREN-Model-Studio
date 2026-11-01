"""Otomatik ve elle konuşma özetleme (/compact, /ozet).

NE ZAMAN:
1. Yeni kullanıcı mesajı gönderilmeden ÖNCE: tahmini bağlam yumuşak eşiği
   aştıysa önce özetlenir, sonra mesaj gönderilir. İş yarıda kesilmez.
2. Uzun bir ajan turu içinde YALNIZCA GÜVENLİ NOKTADA: bir adımın araç
   sonuçları kaydedildikten sonra, yeni model çağrısından önce bağlam sert
   eşiği aştıysa tur durur ("context_limit"), arayüz özetler ve otomatik
   devam eder (tur başına en fazla MAX_AUTO_RESUMES kez).
   Akış, araç çalışması veya onay beklerken asla özetlenmez.

EŞİKLER (varsayılan):
- yumuşak = min(bağlamın %75'i, 100.000 token)
- sert    = min(bağlamın %90'ı, yumuşak × 1,5)
Gerekçe: özet isteğinin kendisi tüm konuşmayı göndermek zorunda (pay
kalmalı); EVREN modellerinin bağlamı çok büyük ama ajan her adımda geçmişi
yeniden gönderir — 100k üstü hem yavaşlatır hem günlük kotayı hızla bitirir.
Mevcut kısaltma (trim_for_context, bağlamın %70'i) özetten bağımsız çalışır.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .prompts import COMPACT_PROMPT, SUMMARY_SYSTEM
from .runner import calibration, estimate_tokens, history_after_summary, to_api_messages, trim_for_context

DEFAULT_PERCENT = 75
DEFAULT_MAX_TOKENS = 100_000
HARD_PERCENT = 90
HARD_FACTOR = 1.5
MAX_AUTO_RESUMES = 3
MIN_MESSAGES = 4


@dataclass
class CompactPolicy:
    enabled: bool = True
    percent: int = DEFAULT_PERCENT
    max_tokens: int = DEFAULT_MAX_TOKENS

    def soft_limit(self, context_tokens: int | None) -> int:
        limit = max(1000, int(self.max_tokens))
        if context_tokens:
            limit = min(limit, int(context_tokens * self.percent / 100))
        return limit

    def hard_limit(self, context_tokens: int | None) -> int:
        soft = self.soft_limit(context_tokens)
        hard = int(soft * HARD_FACTOR)
        if context_tokens:
            hard = min(hard, int(context_tokens * HARD_PERCENT / 100))
        return max(hard, soft)


def history_tokens(history: list[dict], extra_text: str = "") -> int:
    """Modele gidecek geçmişin (son özetten sonrası) tahmini token sayısı."""
    msgs = to_api_messages("", history, "native")
    # sistem istemi + araç tanımları: gerçek token sayısından kalibre edilmiş ek yük (runner.calibration)
    return estimate_tokens(msgs) + estimate_tokens([{"content": extra_text}]) + calibration()[1]


def needs_compaction(history: list[dict], policy: CompactPolicy, context_tokens: int | None,
                     extra_text: str = "") -> tuple[bool, int, int]:
    """(özetlenmeli mi, tahmini token, yumuşak eşik)."""
    tokens = history_tokens(history, extra_text)
    limit = policy.soft_limit(context_tokens)
    since = history_after_summary(history)
    enough = sum(1 for m in since if m.get("role") in ("user", "assistant", "tool")) >= MIN_MESSAGES
    return (policy.enabled and enough and tokens >= limit), tokens, limit


# Özet isteği bütçesi. 2026-10-29: 1.357 mesajlık oturumda özet isteği 724k token tahmin
# edildi, EVREN 1.06M saydı (Türkçe/kod metninde ~2,6 karakter/token) → model reddetti,
# /compact hiç çalışmadı, oturum kilitlendi. Bu yüzden temkinli sayım + kesin sığdırma.
SUMMARY_CHARS_PER_TOKEN = 2.6
SUMMARY_BUDGET_SHARE = 0.5            # özet modelinin bağlamının en fazla yarısı
SUMMARY_BUDGET_MAX = 300_000          # çok büyük bağlamda bile (hız + kalite)
SUMMARY_BUDGET_DEFAULT = 100_000      # bağlam bilinmiyorsa
_KEEP_RECENT = 6                      # son mesajlar daha az kısaltılır


def _cut(text: str, limit: int, head: int, tail: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:head]}\n…[{len(text) - head - tail} karakter özet için kısaltıldı]…\n{text[-tail:]}"


def _shrink_args(raw: str, limit: int = 300) -> str:
    """Araç çağrısı parametrelerindeki uzun metinleri (ör. write_file içeriği) kısaltır; JSON geçerli kalır."""
    import json

    try:
        args = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return _cut(str(raw or ""), limit, limit // 2, limit // 4)
    if not isinstance(args, dict):
        return raw
    out = {k: (_cut(v, limit, limit * 2 // 3, limit // 4) if isinstance(v, str) else v) for k, v in args.items()}
    return json.dumps(out, ensure_ascii=False)


def _conservative_tokens(msgs: list[dict]) -> int:
    return int(sum(len(m.get("content") or "") for m in msgs) / SUMMARY_CHARS_PER_TOKEN)


def summary_budget(context_tokens: int | None) -> int:
    if not context_tokens:
        return SUMMARY_BUDGET_DEFAULT
    return max(8_000, min(SUMMARY_BUDGET_MAX, int(context_tokens * SUMMARY_BUDGET_SHARE)))


def fit_for_summary(history: list[dict], context_tokens: int | None) -> list[dict]:
    """Özete gidecek geçmişi (son özetten sonrası) bütçeye KESİN sığdırır.

    1) uzun araç çıktısı, araç parametresi (dosya içeriği), kullanıcı ve asistan metni kısaltılır;
    2) hâlâ büyükse ilk kullanıcı mesajı (hedef) korunarak en eski mesajlar çıkarılır ve
       bunu belirten bir not eklenir. Kayıt DEĞİŞMEZ (kopya üzerinde çalışır).
    """
    budget = summary_budget(context_tokens)
    start = 0
    for i, m in enumerate(history):
        if m.get("role") == "summary":
            start = i
    head, part = list(history[:start]), [dict(m) for m in history[start:]]
    n = len(part)
    for i, m in enumerate(part):
        recent = i >= n - _KEEP_RECENT
        role, text = m.get("role"), m.get("content") or ""
        if role == "tool":
            m["content"] = _cut(text, 6000 if recent else 1200, 4000 if recent else 600, 1500 if recent else 300)
        elif role == "user":
            m["content"] = _cut(text, 4000, 3000, 800)
        elif role == "assistant":
            m["content"] = _cut(text, 8000 if recent else 4000, 5000 if recent else 2500, 1500)
            if m.get("tool_calls"):
                m["tool_calls"] = [dict(c, arguments=_shrink_args(c.get("arguments") or "")) for c in m["tool_calls"]]

    def size(items: list[dict]) -> int:
        return _conservative_tokens(to_api_messages("", head[-1:] + items if head else items, "text", images=False))

    if size(part) <= budget:
        return head + part
    keep_first = next((i for i, m in enumerate(part) if m.get("role") == "user"), None)
    first = [part[keep_first]] if keep_first is not None else []
    rest = part[keep_first + 1:] if keep_first is not None else part
    dropped = 0
    while rest and size(first + rest) > budget:
        cut_n = max(1, len(rest) // 20)       # büyük geçmişte hızlı ilerle
        rest = rest[cut_n:]
        dropped += cut_n
    note = {"role": "user", "content": f"[Not: bu konuşmanın {dropped} eski mesajı özet bütçesine sığmadığı "
                                       "için özete alınmadı; yalnız hedef mesaj ve son bölüm aşağıda.]"}
    return head + first + ([note] if dropped else []) + rest


def build_summary_request(history: list[dict], focus: str | None = None,
                          context_tokens: int | None = None) -> list[dict]:
    """Özet isteği: geçmiş özet modelinin bağlamına KESİN sığacak şekilde kısaltılır."""
    visible = fit_for_summary(trim_for_context(history, context_tokens), context_tokens)
    msgs = to_api_messages(SUMMARY_SYSTEM, visible, "text", images=False)
    prompt = COMPACT_PROMPT
    if focus:
        prompt += f"\n\nÖzellikle şuna odaklan: {focus.strip()}"
    msgs.append({"role": "user", "content": prompt})
    return msgs


def summarize(client: Any, model: str, history: list[dict], focus: str | None = None,
              context_tokens: int | None = None, cancel: Any = None):
    """Özet üretir (araçsız). ChatResult döndürür.

    AKIŞLI istenir: muhakeme modelleri (glm-5.3) uzun düşünürken akışsız
    istekte bağlantı sessiz kalıp kopabiliyor (2026-10-16 gerçek testte
    "sonuç belirsiz" hatası); akışta parçalar bağlantıyı canlı tutar ve iptal
    her parçada denetlenir.
    """
    return client.chat(model, build_summary_request(history, focus, context_tokens),
                       stream=True, cancel=cancel)
