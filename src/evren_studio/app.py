"""Uygulama giriş noktası."""
from __future__ import annotations

import os
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
ERROR_ALREADY_EXISTS = 183


def _hold_mutex() -> bool:
    """Mutex'i alır. Dönüş: başka bir EVREN Studio ZATEN açık mı (aynı kullanıcı oturumunda)."""
    global _mutex
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        # EVREN_STUDIO_INSTANCE: testler gerçek uygulamayla çakışmasın diye ayrı ad (kurulum sihirbazı sabit adı bilir)
        _mutex = k32.CreateMutexW(None, False, os.environ.get("EVREN_STUDIO_INSTANCE") or MUTEX_NAME)
        return k32.GetLastError() == ERROR_ALREADY_EXISTS
    except (AttributeError, OSError):
        return False


# Tek örnek (2026-11-12 analiz bulgusu): ikinci açılış eskiden İKİNCİ pencere açıyordu → aynı veritabanı ve ayarlar iki
# süreçte; zamanlanmış görevler, otomatik devam ve gözlem gönderimi İKİ KEZ çalışıyordu. Artık ikinci açılış çalışan
# pencereye "öne gel" der ve kapanır. Yerel soket adı kullanıcıya özgüdür (aynı bilgisayardaki başka hesap etkilenmez).
def instance_server_name() -> str:
    import getpass

    try:
        user = getpass.getuser()
    except Exception:                       # noqa: BLE001
        user = "kullanici"
    safe = "".join(ch if ch.isalnum() else "_" for ch in user)
    return f"{os.environ.get('EVREN_STUDIO_INSTANCE') or 'EVREN.Studio'}.{safe}"


def signal_existing(name: str | None = None, timeout_ms: int = 1500) -> bool:
    """Çalışan örneğe "göster" iletir. Ulaşılamazsa False (o zaman yeni pencere açılır — ör. eski sürüm açık)."""
    from PySide6.QtNetwork import QLocalSocket

    sock = QLocalSocket()
    sock.connectToServer(name or instance_server_name())
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write(b"goster\n")
    sock.waitForBytesWritten(timeout_ms)
    sock.disconnectFromServer()
    return True


def listen_for_instances(window, name: str | None = None):
    """İkinci açılışların "göster" isteğini dinler: pencere küçültülmüşse geri açılır ve öne gelir."""
    from PySide6.QtCore import Qt
    from PySide6.QtNetwork import QLocalServer

    name = name or instance_server_name()
    server = QLocalServer(window)
    server.setSocketOptions(QLocalServer.UserAccessOption)
    if not server.listen(name):
        QLocalServer.removeServer(name)               # önceki çökmeden kalan ad
        if not server.listen(name):
            return None

    def on_conn() -> None:
        sock = server.nextPendingConnection()
        if sock is None:
            return
        sock.readyRead.connect(sock.readAll)
        sock.disconnected.connect(sock.deleteLater)
        window.setWindowState((window.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        window.show()                                  # küçültme yukarıda kaldırıldı; gizliyse görünür olur
        window.raise_()
        window.activateWindow()
        window.instance_pings = getattr(window, "instance_pings", 0) + 1
    server.newConnection.connect(on_conn)
    window._instance_server = server
    return server


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
    try:                                    # belge okuma (Madde 20 A3): kütüphaneler + Word/PowerPoint şablon dosyaları
        import docx
        import pdfminer.high_level  # noqa: F401
        import pptx

        docx.Document()
        pptx.Presentation()
        lines.append("belge=var")
    except Exception as exc:                # noqa: BLE001
        lines.append(f"belge=HATA {type(exc).__name__}")
    try:                                    # bozuk JSON onarımı (agent/jsonfix.py) pakete girdi mi
        import json_repair  # noqa: F401

        lines.append("json_repair=var")
    except ImportError:
        lines.append("json_repair=YOK")
    try:                                    # proje haritası dil çözümleyicileri (agent/tsmap.py, Madde 20 C1)
        from .agent import tsmap

        lines.append(f"harita_dilleri={len(tsmap.available())}")
    except Exception as exc:                # noqa: BLE001
        lines.append(f"harita_dilleri=HATA {type(exc).__name__}")
    try:                                    # tek örnek (ikinci açılış çalışan pencereyi öne getirir) QtNetwork ister
        from PySide6.QtNetwork import QLocalServer, QLocalSocket  # noqa: F401

        lines.append("tek_ornek=var")
    except ImportError:
        lines.append("tek_ornek=YOK")
    try:                                    # etkileşimli terminal (agent/ptyshell.py, Madde 20 C4): kütüphane + yardımcı exe
        from pathlib import Path as _P

        import winpty

        from .agent import ptyshell

        agent_exe = _P(winpty.__file__).parent / "winpty-agent.exe"
        lines.append("terminal=" + ("var" if ptyshell.available() and agent_exe.is_file() else "EKSIK"))
    except Exception as exc:                # noqa: BLE001
        lines.append(f"terminal=HATA {type(exc).__name__}")
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
    already = _hold_mutex()
    smoke = "--duman-testi" in sys.argv or "--ikinci-ornek" in sys.argv
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
    if already and not smoke and signal_existing():
        return 0                                  # çalışan pencere öne geldi; ikinci pencere açılmaz
    window = MainWindow()
    window.show()
    if not smoke:
        listen_for_instances(window)
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
