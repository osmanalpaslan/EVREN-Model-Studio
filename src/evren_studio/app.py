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


MUTEX_NAME = "EVREN.Studio"          # kurulum sihirbazı (Inno Setup AppMutex) çalışan uygulamayı bununla tanır
_mutex = None


def _hold_mutex() -> None:
    global _mutex
    if sys.platform != "win32":
        return
    try:
        import ctypes

        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    except (AttributeError, OSError):
        pass


def smoke_report(window) -> list[str]:
    """Paketli uygulamanın açılış denetimi (`--duman-testi <dosya>`; tools/paketle.py kullanır)."""
    from pathlib import Path

    from . import __version__
    from .agent import mcp, runner

    lines = [f"surum={__version__}", f"frozen={bool(getattr(sys, 'frozen', False))}",
             f"pencere={window.isVisible()}"]
    for name, p in (("wmcp_baslatici", mcp.WINDOWS_LAUNCHER),
                    ("blender_donustur", Path(runner.__file__).with_name("blender_donustur.py"))):
        lines.append(f"{name}={'var' if Path(p).is_file() else 'YOK'}")
    try:
        lines.append(f"python={mcp._base_python()}")
    except mcp.McpError:
        lines.append("python=YOK")
    from .agent import diagnostics

    lines.append(f"ruff={'var' if diagnostics.ruff_bin() else 'YOK'}")   # hata bekçisi (Madde 20 A2)
    try:                                    # bozuk JSON onarımı (agent/jsonfix.py) pakete girdi mi
        import json_repair  # noqa: F401

        lines.append("json_repair=var")
    except ImportError:
        lines.append("json_repair=YOK")
    try:                                    # anahtar Credential Manager'da: paketlenince arka uç kaybolabilir
        import keyring

        lines.append(f"keyring={type(keyring.get_keyring()).__name__}")
    except Exception as exc:                # noqa: BLE001 — rapor, uygulama değil
        lines.append(f"keyring=HATA {type(exc).__name__}")
    try:                                    # SSL sertifika paketi (certifi) pakette mi: anahtarsız istek 401 döner
        import httpx

        from .config import DEFAULT_BASE_URL

        r = httpx.get(f"{DEFAULT_BASE_URL.rstrip('/')}/models", timeout=15)
        lines.append(f"tls=tamam {r.status_code}")
    except Exception as exc:                # noqa: BLE001
        lines.append(f"tls=HATA {type(exc).__name__}")
    return lines


def main() -> int:
    if "--anahtarlari-sil" in sys.argv:
        # Kaldırıcı "kişisel verileri de sil" denince çağırır (installer/evren_studio.iss); pencere açılmaz
        from .secrets import delete_all_api_keys

        delete_all_api_keys()
        return 0
    from PySide6.QtWidgets import QApplication

    _install_excepthook()
    _hold_mutex()
    if getattr(sys, "frozen", False):
        # Kurulum sihirbazı Python/Git/Node'u yeni kurduysa uygulama eski PATH ile açılır (sihirbazın ortamı)
        from .agent.environment import refresh_path

        refresh_path()
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
    if "--duman-testi" in sys.argv:
        i = sys.argv.index("--duman-testi")
        out = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""

        def finish() -> None:
            text = "\n".join(smoke_report(window)) + "\nTAMAM\n"
            if out:
                from pathlib import Path

                Path(out).write_text(text, encoding="utf-8")
            app.quit()

        QTimer.singleShot(4000, window, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
