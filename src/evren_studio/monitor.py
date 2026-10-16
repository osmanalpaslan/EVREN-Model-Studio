"""EVREN Durum İzleme Ajanı.

Kullanıcı 'İzlemeyi Başlat' dediğinde:
- Başlangıç zamanı kaydedilir; duyuru sayfası ilk kez alınır.
- Sayfa her 5 dakikada bir yeniden kontrol edilir (varsayılan; ayarlanabilir).
- Toplam 30 dakika sürer → normal koşullarda 7 kontrol (0,5,10,15,20,25,30).
- Her kontrol zaman damgasıyla ayrı olay olarak kaydedilir.
- İçerik değişirse eski/yeni fark kaydedilir; aynı duyuru tekrar yazılmaz.
- Uygulama kapanırsa kalan süre kaydedilir; yeniden açılışta devam seçeneği.

Sağlık testi katmanları:
1. /healthz + /readyz (kimlik doğrulamasız, maliyetsiz) — her tur.
2. GET /v1/models (anahtar gerekli, token tüketmez) — her tur.
3. Gerçek model testi (token harcar) — YALNIZCA kullanıcı seçtiyse.

Duyuru API'si (api.ssyz.org.tr/api/v1/announcements/active) platform girişi
istediğinden izlenen sayfa varsayılan olarak herkese açık
https://evren.ssyz.org.tr/ ana sayfasıdır; kullanıcı ayarlardan değiştirebilir.
"""
from __future__ import annotations

import difflib
import hashlib
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import httpx

from .api.client import EvrenClient
from .db import Database

CHECK_KINDS = ("announcement", "healthz", "readyz", "models", "model_test")


@dataclass
class CheckResult:
    kind: str
    ok: bool
    detail: str
    content_hash: str | None = None
    change_detected: bool = False
    change_summary: str | None = None
    checked_at: str = ""


@dataclass
class MonitorReport:
    started_at: str
    ended_at: str
    target_url: str
    total_checks: int
    successful_checks: int
    failed_checks: int
    changes: list[str] = field(default_factory=list)
    api_results: list[str] = field(default_factory=list)
    model_errors: list[str] = field(default_factory=list)
    provider_issue_guess: str = "belirlenemedi"
    certain_findings: list[str] = field(default_factory=list)
    uncertain_findings: list[str] = field(default_factory=list)
    recommendation: str = "-"


def _visible_text(html: str) -> str:
    """HTML'den betik/stil temizlenmiş görünür metin + başlık çıkarır."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # SPA'da gövde çoğu zaman boştur; başlık ve meta açıklaması anlamlı sinyal.
    title = re.search(r"(?is)<title>(.*?)</title>", html)
    desc = re.search(
        r'(?is)<meta\s+name="description"\s+content="([^"]*)"', html
    )
    parts = []
    if title:
        parts.append("TITLE: " + title.group(1).strip())
    if desc:
        parts.append("DESC: " + desc.group(1).strip())
    parts.append("BODY: " + text[:2000])
    return "\n".join(parts)


def _hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _meaningful_diff(old: str, new: str) -> str | None:
    """Eski/yeni içerik arasındaki anlamlı farkı özetler."""
    old_lines = [l for l in old.splitlines() if l.strip()]
    new_lines = [l for l in new.splitlines() if l.strip()]
    diff = [
        l for l in difflib.unified_diff(old_lines, new_lines, lineterm="")
        if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))
    ]
    if not diff:
        return None
    added = [l[1:].strip() for l in diff if l.startswith("+")]
    removed = [l[1:].strip() for l in diff if l.startswith("-")]
    parts = []
    if added:
        parts.append("EKLENEN: " + " | ".join(added[:5]))
    if removed:
        parts.append("ÇIKARILAN: " + " | ".join(removed[:5]))
    summary = " ~ ".join(parts)
    return summary[:800] or None


class MonitorAgent:
    """Kullanıcı başlatmalı 30 dakikalık izleme döngüsü."""

    def __init__(self, db: Database, target_url: str, interval_minutes: int = 5,
                 duration_minutes: int = 30, client: EvrenClient | None = None,
                 real_model_test: bool = False, test_model: str = "glm-5.3",
                 on_check: Callable[[CheckResult], None] | None = None,
                 on_finished: Callable[[MonitorReport], None] | None = None,
                 on_state_change: Callable[[str], None] | None = None):
        self.db = db
        self.target_url = target_url
        self.interval_minutes = max(1, interval_minutes)
        self.duration_minutes = max(1, duration_minutes)
        # Döngü saniye tabanlı çalışır; birim testler bunları küçültür.
        self.interval_seconds = self.interval_minutes * 60
        self.duration_seconds = self.duration_minutes * 60
        self.client = client
        self.real_model_test = real_model_test
        self.test_model = test_model
        self._on_check = on_check or (lambda c: None)
        self._on_finished = on_finished or (lambda r: None)
        self._on_state = on_state_change or (lambda s: None)

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.session_id: int | None = None
        self.last_text: str | None = None
        self.last_hash: str | None = None
        self.results: list[CheckResult] = []

    # ---- yaşam döngüsü -------------------------------------------------

    def start(self) -> int:
        """İzlemeyi başlatır; oturum kimliğini döndürür."""
        self.session_id = self.db.start_monitor_session(
            self.target_url, self.interval_minutes, self.duration_minutes
        )
        self._stop.clear()
        self.results = []
        self._on_state("running")
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="evren-monitor")
        self._thread.start()
        return self.session_id

    def stop(self, status: str = "stopped_by_user") -> None:
        self._stop.set()
        # İzleme iş parçacığının çıkmasını bekle (kayıt yazımları yarıda
        # kalmasın); yalnızca kendi içinden çağrılmıyorsa.
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=10)
        if self.session_id is not None:
            self.db.finish_monitor_session(self.session_id, status)
        self._on_state(status)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def remaining_minutes(self, started_at: str) -> float:
        try:
            start = datetime.fromisoformat(started_at)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() / 60.0
            return max(0.0, self.duration_minutes - elapsed)
        except ValueError:
            return 0.0

    # ---- döngü ------------------------------------------------------------

    def _run(self) -> None:
        deadline = time.monotonic() + self.duration_seconds
        while not self._stop.is_set():
            self._single_round()
            if time.monotonic() >= deadline:
                break
            # Beklemeyi küçük parçalara böl: durdurma anında tepki verir.
            wait_end = min(time.monotonic() + self.interval_seconds, deadline)
            while time.monotonic() < wait_end and not self._stop.is_set():
                time.sleep(min(1.0, max(0.01, self.interval_seconds / 60)))
        if not self._stop.is_set():
            if self.session_id is not None:
                self.db.finish_monitor_session(self.session_id, "completed")
            self._on_state("completed")
        self._on_finished(self.build_report())

    def _single_round(self) -> None:
        """Bir tur: duyuru sayfası + sağlık uçları (+ isteğe bağlı model testi)."""
        # 1) Duyuru sayfası
        try:
            with httpx.Client(timeout=30.0, verify=True,
                              follow_redirects=True) as http:
                resp = http.get(self.target_url)
            ok = 200 <= resp.status_code < 300
            text = _visible_text(resp.text) if ok else ""
            h = _hash_content(text) if ok else None
            change = False
            summary = None
            if ok and self.last_text is not None and h != self.last_hash:
                summary = _meaningful_diff(self.last_text, text)
                if summary:
                    change = True
            if ok:
                self.last_text, self.last_hash = text, h
            result = CheckResult(
                kind="announcement", ok=ok,
                detail=f"HTTP {resp.status_code}, {len(resp.content)} bayt",
                content_hash=h, change_detected=change,
                change_summary=summary,
            )
        except httpx.HTTPError as exc:
            result = CheckResult(
                kind="announcement", ok=False,
                detail=f"Sayfa alınamadı: {type(exc).__name__}",
            )
        self._record(result)

        # 2) /healthz
        self._safe_api_check("healthz", lambda: self.client.healthz())

        # 3) /readyz
        self._safe_api_check("readyz", lambda: self.client.readyz())

        # 4) Model listesi (token harcamaz)
        if self.client is not None:
            self._safe_api_check("models", lambda: self.client.list_models())

        # 5) Gerçek model testi — yalnızca kullanıcı seçtiyse
        if self.client is not None and self.real_model_test:
            try:
                t0 = time.monotonic()
                res = self.client.chat(
                    self.test_model,
                    [{"role": "user", "content": "Ping: yanıt olarak sadece 'ok' yaz."}],
                    max_tokens=2000,
                )
                latency = int((time.monotonic() - t0) * 1000)
                ok = bool(res.content) or bool(res.reasoning)
                self.db.upsert_model_health(
                    self.test_model, ok, 200, None, latency
                )
                self._record(CheckResult(
                    kind="model_test", ok=ok,
                    detail=f"{self.test_model}: {latency} ms, "
                           f"finish={res.finish_reason}",
                ))
            except Exception as exc:  # ApiError dahil
                self.db.upsert_model_health(
                    self.test_model, False,
                    getattr(exc, "status", None), str(exc)[:200], None
                )
                self._record(CheckResult(
                    kind="model_test", ok=False,
                    detail=f"{self.test_model}: {exc}",
                ))

    def _safe_api_check(self, kind: str, fn: Callable[[], object]) -> None:
        if self.client is None:
            return
        try:
            t0 = time.monotonic()
            data = fn()
            latency = int((time.monotonic() - t0) * 1000)
            if isinstance(data, list):
                detail = f"{len(data)} model listelendi, {latency} ms"
            else:
                detail = f"{data} ({latency} ms)"
            self._record(CheckResult(kind=kind, ok=True, detail=detail))
        except Exception as exc:
            self._record(CheckResult(
                kind=kind, ok=False,
                detail=f"{type(exc).__name__}: {str(exc)[:200]}",
            ))

    def _record(self, result: CheckResult) -> None:
        self.results.append(result)
        if self.session_id is not None:
            self.db.add_monitor_check(
                self.session_id, result.kind, result.ok, result.detail,
                result.content_hash, result.change_detected,
                result.change_summary, result.checked_at,
            )
        self._on_check(result)

    # ---- rapor ----------------------------------------------------------

    def build_report(self) -> MonitorReport:
        total = len(self.results)
        ok_count = sum(1 for r in self.results if r.ok)
        changes = [
            f"İçerik değişikliği tespit edildi: {r.change_summary}"
            for r in self.results if r.change_detected and r.change_summary
        ]
        api_results = [
            f"{r.kind}: {'BAŞARILI' if r.ok else 'BAŞARISIZ'} — {r.detail}"
            for r in self.results if r.kind != "announcement"
        ]
        model_errors = [
            r.detail for r in self.results
            if r.kind == "model_test" and not r.ok
        ]

        ready_ok = any(r.kind == "readyz" and r.ok for r in self.results)
        models_ok = any(r.kind == "models" and r.ok for r in self.results)
        ann_ok = any(r.kind == "announcement" and r.ok for r in self.results)
        test_ok = any(r.kind == "model_test" and r.ok for r in self.results)

        certain: list[str] = []
        uncertain: list[str] = []
        if ready_ok:
            certain.append("API /readyz 'ready' döndü — servis trafiğe açık.")
        else:
            certain.append("API /readyz hazır değil veya erişilemedi.")
        if models_ok:
            certain.append("Model listesi alındı — kimlik doğrulama ve kayıt defteri çalışıyor.")
        if ann_ok:
            certain.append("İzlenen duyuru sayfası erişilebilir durumda.")
        else:
            certain.append("İzlenen duyuru sayfasına erişilemedi.")

        provider_guess = "belirlenemedi"
        if not ready_ok and not models_ok:
            provider_guess = (
                "muhtemel sağlayıcı kaynaklı sorun (API servisleri yanıt vermiyor)"
            )
            uncertain.append(
                "Duyuru sayfasında bakım bildirimi olup olmadığı sayfa "
                "erişilebilirliğine göre değerlendirilmelidir."
            )
        elif models_ok and self.real_model_test and not test_ok:
            provider_guess = (
                "model katmanı sorunu olabilir (liste çalışıyor, model testi "
                "başarısız) — sağlayıcı kaynaklı olması muhtemel"
            )
        elif models_ok:
            provider_guess = "sistem genelinde sağlıklı görünüyor"

        if changes:
            uncertain.append(
                "Duyuru/bakım bilgisi yalnızca izlenen sayfanın içeriğine "
                "dayanır; kesin API durumu ile karşılaştırılmalıdır."
            )

        if provider_guess.startswith("muhtemel"):
            recommendation = (
                "Bekleme önerilir: birkaç dakika sonra 'Yeniden Test Et' ile "
                "durumu kontrol edin. Kod değişikliği gerekmez; model geçici "
                "olarak kullanılamıyor işaretlidir."
            )
        elif model_errors:
            recommendation = (
                "Başka bir doğrulanmış sohbet modeli seçmeyi deneyebilir veya "
                "kısa süre sonra aynı modelle yeniden test edebilirsiniz."
            )
        else:
            recommendation = (
                "Sistem sağlıklı görünüyor; çalışmaya devam edebilirsiniz."
            )

        started = self.db._exec(
            "SELECT started_at FROM monitor_sessions WHERE id=?",
            (self.session_id,),
        ).fetchone() if self.session_id else None

        return MonitorReport(
            started_at=started["started_at"] if started else "",
            ended_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            target_url=self.target_url,
            total_checks=total,
            successful_checks=ok_count,
            failed_checks=total - ok_count,
            changes=changes,
            api_results=api_results,
            model_errors=model_errors,
            provider_issue_guess=provider_guess,
            certain_findings=certain,
            uncertain_findings=uncertain,
            recommendation=recommendation,
        )

    def report_markdown(self, report: MonitorReport) -> str:
        """Türkçe izleme raporu (Markdown)."""
        lines = [
            "# EVREN Durum İzleme Raporu",
            "",
            f"- Başlangıç: {report.started_at or '-'}",
            f"- Bitiş: {report.ended_at}",
            f"- İzlenen sayfa: {report.target_url}",
            f"- Toplam kontrol: {report.total_checks} "
            f"(başarılı: {report.successful_checks}, başarısız: {report.failed_checks})",
            "",
            "## Duyuru Değişiklikleri",
        ]
        lines += [f"- {c}" for c in report.changes] or ["- Değişiklik tespit edilmedi."]
        lines += ["", "## API Test Sonuçları"]
        lines += [f"- {a}" for a in report.api_results] or ["- Test yapılmadı."]
        lines += ["", "## Model Hataları"]
        lines += [f"- {m}" for m in report.model_errors] or ["- Model hatası yok."]
        lines += [
            "",
            "## Sorunun Muhtemel Kaynağı",
            f"{report.provider_issue_guess}",
            "",
            "## Kesin Bulgular",
        ]
        lines += [f"- {c}" for c in report.certain_findings]
        lines += ["", "Tahmine Dayalı Bulgular"]
        lines += [f"- {u}" for u in report.uncertain_findings] or ["- -"]
        lines += ["", "## Önerilen Sonraki Adım", report.recommendation]
        return "\n".join(lines)
