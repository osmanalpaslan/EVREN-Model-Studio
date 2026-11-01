"""`web_search`: internette arama yapan araç (Qt'siz).

Neden: `web_fetch` yalnız verilen adresi okur; güncel sürüm, hata mesajı, belge gibi bilgileri bulmak için
arama gerekir. EVREN'in `evren_tools` uzantısı canlı veri getirmedi (webfetch.py başı). Kullanıcı 2026-11-01'de
ücretsiz Tavily anahtarı aldı (Researcher planı: ayda 1000 kredi; temel arama 1, gelişmiş arama 2 kredi).

Sağlayıcı zinciri (biri olmazsa sıradakine geçilir — kota bitince proje durmaz):
1. Tavily, kullanıcının anahtarıyla (Credential Manager: ``tavily_api_key``; anahtar dosyaya/loga yazılmaz)
2. Tavily anahtarsız erişim (``X-Tavily-Access-Mode: keyless``; hız sınırlı)
3. DuckDuckGo HTML (anahtarsız; özet kısa, cevap yok)
Hiçbiri olmazsa `SearchUnavailable` — koşucu ajana "eldeki bilgiyle devam et" der.

Güvenlik: sonuç dış içeriktir (UNTRUSTED_NOTE). Sorgu dış sunucuya gider; koşucu bunu komut gibi izinden geçirir.
"""
from __future__ import annotations

import html
import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlparse

from .webfetch import UNTRUSTED_NOTE

TAVILY_URL = "https://api.tavily.com/search"
TAVILY_USAGE_URL = "https://api.tavily.com/usage"
DDG_URL = "https://html.duckduckgo.com/html/"
TIMEOUT_S = 25.0
MAX_RESULTS = 8
SNIPPET_CHARS = 600
# Kota/anahtar hatası alınan anahtar bu süre denenmez (her aramada boşa istek gitmesin)
KEY_COOLDOWN_S = 3600
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/130.0 Safari/537.36")
# Tavily: 401 geçersiz anahtar, 432 plan kotası doldu, 433 kullandıkça öde sınırı (belge: docs.tavily.com)
_KEY_DEAD = {401, 403, 432, 433}

_key_blocked_until = 0.0

# Tur başı hatırlatma: model aracı kendiliğinden seçmeyebilir (R-25) — istek dış/güncel bilgi isterse söylenir.
# Kelimeler bilerek dar: "kur" (kurulum), "son" (sonuç) gibi genel kelimeler yok; gereksiz tetiklenme testli (R-22).
_WEB_WORDS = re.compile(
    r"internette|internetten|\bweb'?de\b|\bweb'?den\b|google'?la|araştırması|\bgüncel\b|güncel bilgi|"
    r"en son sürüm|son sürümü|son sürüme|en yeni sürüm|hangi sürüm|latest version|haberler|haberleri|son dakika|"
    r"döviz|fiyatı|fiyatları|belgelerine bak|dokümantasyonuna bak|resmi belge|kaynak göster|kaynakla",
    re.IGNORECASE)
HINT = ("# Web araması (bu tur)\n"
        "Bu istek güncel ya da dış bilgi gerektiriyor olabilir. Bilgin eski olabilecekse tahmin etme: `web_search` "
        "ile ara, gerekirse sonuçtaki adresi `web_fetch` ile oku ve kullandığın kaynağın adresini belirt. Arama "
        "yapılamazsa tekrar deneme; eldeki bilgiyle devam et ve bunu söyle.")


def needs_web(text: str) -> bool:
    """Kullanıcı isteği internet araştırması gerektiriyor mu (kelime tabanlı, Türkçe büyük/küçük harf duyarsız)."""
    t = (text or "").replace("İ", "i").replace("I", "ı").lower()
    return bool(_WEB_WORDS.search(t))


class SearchUnavailable(Exception):
    """Hiçbir arama sağlayıcısı sonuç veremedi."""


@dataclass
class SearchResult:
    provider: str
    answer: str = ""
    results: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)   # yedeğe geçiş nedenleri (kullanıcıya/ajana bilgi)


def load_key() -> str | None:
    """Tavily anahtarı: önce kasa (Credential Manager), yoksa TAVILY_API_KEY ortam değişkeni (testler)."""
    try:
        from .. import secrets

        key = secrets.load_api_key("tavily")
    except Exception:      # kasa yok/bozuk → anahtarsız zincire düş; hata aramayı durdurmaz
        key = None
    return key or os.environ.get("TAVILY_API_KEY") or None


def _tavily(c, query: str, *, key: str | None, guncel: bool, haber: bool, max_results: int) -> SearchResult:
    body: dict = {"query": query[:400], "max_results": max_results, "include_answer": True,
                  "search_depth": "advanced" if guncel else "basic"}
    if haber:
        body.update(topic="news", time_range="week")
    elif guncel:
        body["time_range"] = "year"
    headers = {"Authorization": f"Bearer {key}"} if key else {"X-Tavily-Access-Mode": "keyless"}
    r = c.post(TAVILY_URL, json=body, headers=headers)
    if r.status_code != 200:
        raise _HttpFail(r.status_code)
    data = r.json()
    results = [{"title": x.get("title") or "", "url": x.get("url") or "",
                "date": x.get("published_date") or "", "snippet": x.get("content") or ""}
               for x in data.get("results") or [] if x.get("url")]
    return SearchResult("tavily" if key else "tavily-anahtarsız", (data.get("answer") or "").strip(), results)


class _HttpFail(Exception):
    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.status = status


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _ddg_url(href: str) -> str:
    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    p = urlparse(href)
    if p.netloc.endswith("duckduckgo.com") and p.path.startswith("/l/"):
        return unquote(parse_qs(p.query).get("uddg", [""])[0])
    return href


_DDG_BLOCK = re.compile(r'<div class="result results_links[^"]*"(.*?)(?=<div class="result results_links|\Z)', re.S)


def _ddg(c, query: str, *, max_results: int) -> SearchResult:
    r = c.post(DDG_URL, data={"q": query[:400]}, headers={"User-Agent": _BROWSER_UA})
    if r.status_code != 200:
        raise _HttpFail(r.status_code)
    results = []
    for block in _DDG_BLOCK.findall(r.text):
        a = re.search(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        url = _ddg_url(a.group(1))
        if not url.startswith("http") or "duckduckgo.com/y.js" in url:     # reklam
            continue
        sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, re.S)
        results.append({"title": _strip(a.group(2)), "url": url, "date": "",
                        "snippet": _strip(sn.group(1)) if sn else ""})
        if len(results) >= max_results:
            break
    if not results:
        raise _HttpFail(0)      # boş sayfa ya da robot doğrulaması
    return SearchResult("duckduckgo", "", results)


def search(query: str, *, guncel: bool = False, haber: bool = False, max_results: int = 5,
           client=None, key: str | None = "auto") -> SearchResult:
    """Zinciri sırayla dener. `key="auto"` → load_key(); None → anahtarlı adım atlanır."""
    global _key_blocked_until
    import httpx

    query = (query or "").strip()
    if not query:
        raise ValueError("Arama sorgusu boş.")
    max_results = max(1, min(int(max_results or 5), MAX_RESULTS))
    if key == "auto":
        key = load_key()
    own = client is None
    c = client or httpx.Client(timeout=TIMEOUT_S, follow_redirects=True)
    notes: list[str] = []
    try:
        steps = []
        if key and time.monotonic() >= _key_blocked_until:
            steps.append(("Tavily", lambda: _tavily(c, query, key=key, guncel=guncel, haber=haber,
                                                    max_results=max_results)))
        elif key:
            notes.append("Tavily anahtarının kotası/izni bu oturumda bitmiş görünüyor; anahtarsız aramaya geçildi.")
        steps.append(("Tavily (anahtarsız)", lambda: _tavily(c, query, key=None, guncel=guncel, haber=haber,
                                                             max_results=max_results)))
        steps.append(("DuckDuckGo", lambda: _ddg(c, query, max_results=max_results)))
        for i, (name, run) in enumerate(steps):
            try:
                res = run()
            except _HttpFail as exc:
                if i == 0 and key and name == "Tavily" and exc.status in _KEY_DEAD:
                    _key_blocked_until = time.monotonic() + KEY_COOLDOWN_S
                    why = "kota doldu" if exc.status in (432, 433) else "anahtar reddedildi"
                    notes.append(f"Tavily: {why} (HTTP {exc.status}); yedek aramaya geçildi.")
                else:
                    notes.append(f"{name}: {'sonuç yok' if exc.status == 0 else exc}")
                continue
            except (httpx.HTTPError, ValueError) as exc:
                notes.append(f"{name}: {type(exc).__name__}")
                continue
            res.notes = notes
            return res
    finally:
        if own:
            c.close()
    raise SearchUnavailable("; ".join(notes) or "arama sağlayıcısı yok")


def format_result(query: str, res: SearchResult, snippet_chars: int = SNIPPET_CHARS) -> str:
    lines = [UNTRUSTED_NOTE, f"Arama: {query}  (kaynak: {res.provider})"]
    lines += [f"Not: {n}" for n in res.notes]
    if res.answer:
        lines += ["", "Kısa cevap (arama servisinin özeti; kaynaklarla doğrula):", res.answer]
    lines.append("")
    for i, r in enumerate(res.results, 1):
        date = f" · {r['date'][:16]}" if r.get("date") else ""
        snippet = re.sub(r"\s+", " ", r.get("snippet") or "").strip()
        if len(snippet) > snippet_chars:
            snippet = snippet[:snippet_chars].rstrip() + "…"
        lines += [f"{i}. {r.get('title') or '(başlıksız)'}{date}", f"   {r['url']}", f"   {snippet}"]
    if not res.results:
        lines.append("(sonuç yok)")
    lines += ["", "Ayrıntı gerekirse ilgili adresi web_fetch ile oku. Cevapta kullandığın kaynağın adresini belirt."]
    return "\n".join(lines)


def usage(key: str | None = "auto", client=None) -> dict | None:
    """Tavily kota durumu: {"plan", "used", "limit"} ya da None (anahtar yok / okunamadı)."""
    import httpx

    if key == "auto":
        key = load_key()
    if not key:
        return None
    own = client is None
    c = client or httpx.Client(timeout=15.0)
    try:
        r = c.get(TAVILY_USAGE_URL, headers={"Authorization": f"Bearer {key}"})
        if r.status_code != 200:
            return None
        acc = (r.json() or {}).get("account") or {}
        return {"plan": acc.get("current_plan") or "", "used": int(acc.get("plan_usage") or 0),
                "limit": int(acc.get("plan_limit") or 0)}
    except (httpx.HTTPError, ValueError, TypeError):
        return None
    finally:
        if own:
            c.close()
