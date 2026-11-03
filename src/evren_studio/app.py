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
        from . import gozlem

        gozlem.kaydet("cokme", f"Yakalanmamış hata: {exc_type.__name__}", onem="yuksek", alan="ui",
                      exc=exc, tb=tb)
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

    import threading

    def thread_hook(args) -> None:
        # Arka plan iş parçacığında yakalanmamış hata (Task dışında açılan iş parçacıkları)
        from . import gozlem

        if args.exc_type is SystemExit:
            return
        gozlem.kaydet("cokme", f"İş parçacığında yakalanmamış hata: {args.exc_type.__name__}", onem="yuksek",
                      alan="genel", exc=args.exc_value, tb=args.exc_traceback)
        threading.__excepthook__(args)

    threading.excepthook = thread_hook


def _install_qt_message_handler() -> None:
    """Qt uyarılarını (ör. başka iş parçacığından arayüz güncelleme, R-11) gözlem ajanına iletir."""
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    from . import gozlem

    levels = {QtMsgType.QtWarningMsg: "warning", QtMsgType.QtCriticalMsg: "critical",
              QtMsgType.QtFatalMsg: "fatal"}

    def handler(mode, _ctx, message) -> None:
        level = levels.get(mode)
        if level:
            gozlem.qt_mesaji(level, message)
        if sys.__stderr__:
            try:
                sys.__stderr__.write(f"{message}\n")
            except (OSError, ValueError):
                pass

    qInstallMessageHandler(handler)


def main() -> int:
    from PySide6.QtWidgets import QApplication

    _install_excepthook()
    _install_qt_message_handler()
    from .ui.main_window import MainWindow

    if sys.platform == "win32":
        # Görev çubuğunda "Python" yerine uygulamanın kendi simgesi (ay-yıldız) görünsün
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EVREN.Studio")
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("EVREN Studio")
    app.setOrganizationName("EVREN Studio")
    window = MainWindow()
    window.show()
    # Kullanım düğmesi açılışta dolsun (testler MainWindow'u doğrudan kurar; ağ isteği yapmaz)
    from PySide6.QtCore import QTimer

    QTimer.singleShot(1500, window, window.session.refresh_usage)
    # Canlı EVREN model listesi (yetenek bayrakları, yeni modeller) açılışta arka planda yüklenir;
    # önceden yalnız Modeller sayfası açılınca yükleniyordu.
    QTimer.singleShot(1000, window, window.session.load_live_models)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
