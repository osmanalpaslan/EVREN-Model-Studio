"""UI duman testi: uygulamayı aç, 3 saniye sonra güvenli kapat."""
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from evren_studio.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    QTimer.singleShot(3000, app.quit)
    rc = app.exec()
    print("SMOKE_OK" if rc == 0 else f"SMOKE_FAIL_{rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
