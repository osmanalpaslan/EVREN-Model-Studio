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
from .runner import estimate_tokens, history_after_summary, to_api_messages, trim_for_context

DEFAULT_PERCENT = 75
DEFAULT_MAX_TOKENS = 100_000
HARD_PERCENT = 90
HARD_FACTOR = 1.5
MAX_AUTO_RESUMES = 3
MIN_MESSAGES = 4
SYSTEM_OVERHEAD_TOKENS = 2_500     # sistem istemi + araç tanımları (tahmini)


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
    return estimate_tokens(msgs) + estimate_tokens([{"content": extra_text}]) + SYSTEM_OVERHEAD_TOKENS


def needs_compaction(history: list[dict], policy: CompactPolicy, context_tokens: int | None,
                     extra_text: str = "") -> tuple[bool, int, int]:
    """(özetlenmeli mi, tahmini token, yumuşak eşik)."""
    tokens = history_tokens(history, extra_text)
    limit = policy.soft_limit(context_tokens)
    since = history_after_summary(history)
    enough = sum(1 for m in since if m.get("role") in ("user", "assistant", "tool")) >= MIN_MESSAGES
    return (policy.enabled and enough and tokens >= limit), tokens, limit


def build_summary_request(history: list[dict], focus: str | None = None,
                          context_tokens: int | None = None) -> list[dict]:
    """Özet isteği: eski araç çıktıları gerekiyorsa kısaltılır ki istek sığsın."""
    visible = trim_for_context(history, context_tokens)
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
