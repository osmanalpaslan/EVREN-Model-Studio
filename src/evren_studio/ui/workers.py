"""Arayüz yardımcıları: arka plan iş parçacıkları ve sinyaller."""
from __future__ import annotations

import threading
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal


class TaskSignals(QObject):
    finished = Signal(object)
    failed = Signal(object)
    log = Signal(str)


class Task:
    """Bir işlevi arka plan iş parçacığında çalıştırır.

    Kullanım:
        task = Task(fn, on_done=..., on_error=...)
        task.start()
    Sinyaller Qt kuyruklı bağlantıyla ana iş parçacığına düşer.
    """

    def __init__(self, fn: Callable[..., Any], on_done: Callable[[Any], None],
                 on_error: Callable[[Exception], None] | None = None,
                 on_log: Callable[[str], None] | None = None,
                 args: tuple = ()):
        self.signals = TaskSignals()
        self.signals.finished.connect(on_done)
        if on_error:
            self.signals.failed.connect(on_error)
        if on_log:
            self.signals.log.connect(on_log)
        self._fn = fn
        self._args = args
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        try:
            result = self._fn(*self._args)
            self.signals.finished.emit(result)
        except Exception as exc:  # ApiError dahil tüm hatalar
            self.signals.failed.emit(exc)

    def start(self) -> None:
        self._thread.start()

    def log(self, msg: str) -> None:
        self.signals.log.emit(msg)
