"""Uygulama giriş noktası."""
from __future__ import annotations

import sys
import traceback
from datetime import datetime


def _install_excepthook() -> None:
    """Yakalanmamış hataları günlüğe yazar ve kullanıcıya Türkçe bildirir.

    run.bat konsolsuz (pythonw) başlattığı için hatalar aksi halde kaybolur.
    Günlükte API anahtarı bulunmaz: mesaj mask_secret'tan geçer.
    """
    from .config import default_data_dir
    from .secrets import mask_secret

    def hook(exc_type, exc, tb) -> None:
        text = mask_secret("".join(traceback.format_exception(exc_type, exc, tb)))
        try:
            log_dir = default_data_dir() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "crash.log", "a", encoding="utf-8") as f:
                f.write(f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\n{text}")
        except OSError:
            pass
        sys.__stderr__ and sys.__stderr__.write(text)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None, "Beklenmeyen hata",
                    f"{exc_type.__name__}: {exc}\n\nUygulama çalışmaya devam ediyor. Ayrıntılar: "
                    f"{default_data_dir() / 'logs' / 'crash.log'}",
                )
        except Exception:
            pass

    sys.excepthook = hook


def main() -> int:
    from PySide6.QtWidgets import QApplication

    _install_excepthook()
    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("EVREN Studio")
    app.setOrganizationName("EVREN Studio")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
