"""Arayüz yardımcıları: arka plan iş parçacıkları ve sinyaller."""
from __future__ import annotations

import threading
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

# Çalışan görevlere güçlü referans: iş parçacığı bittiğinde Task nesnesi
# sonuç sinyali ana iş parçacığına ulaşmadan çöpe giderse geri çağrı hiç
# çalışmaz (düğme "hiçbir şey yapmıyor" gibi görünür). Sonuç teslim
# edilince referans bırakılır.
_ACTIVE: set["Task"] = set()
# Uygulama kapanırken False yapılır: geç gelen sonuçlar (ör. kapanmış
# veritabanına yazacak model listesi) işlenmez.
_ACCEPTING = True


def set_accepting(value: bool) -> None:
    global _ACCEPTING
    _ACCEPTING = value


class TaskSignals(QObject):
    finished = Signal(object)
    failed = Signal(object)
    log = Signal(str)


class Task:
    """Bir işlevi arka plan iş parçacığında çalıştırır.

    Kullanım:
        task = Task(fn, on_done=..., on_error=...)
        task.start()
    Sinyaller Qt kuyruklu bağlantıyla ana iş parçacığına düşer.
    """

    def __init__(self, fn: Callable[..., Any], on_done: Callable[[Any], None],
                 on_error: Callable[[Exception], None] | None = None,
                 on_log: Callable[[str], None] | None = None,
                 args: tuple = ()):
        self.signals = TaskSignals()
        self._on_done = on_done
        self._on_error = on_error
        self.signals.finished.connect(self._deliver_done)
        self.signals.failed.connect(self._deliver_error)
        if on_log:
            self.signals.log.connect(on_log)
        self._fn = fn
        self._args = args
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _deliver_done(self, result: Any) -> None:
        try:
            if _ACCEPTING:
                self._on_done(result)
        finally:
            _ACTIVE.discard(self)

    def _deliver_error(self, exc: Exception) -> None:
        try:
            if self._on_error and _ACCEPTING:
                self._on_error(exc)
        finally:
            _ACTIVE.discard(self)

    def _run(self) -> None:
        try:
            result = self._fn(*self._args)
            self.signals.finished.emit(result)
        except Exception as exc:  # ApiError dahil tüm hatalar
            self.signals.failed.emit(exc)

    def start(self) -> None:
        _ACTIVE.add(self)
        self._thread.start()

    def log(self, msg: str) -> None:
        self.signals.log.emit(msg)


def active_task_count() -> int:
    return len(_ACTIVE)
