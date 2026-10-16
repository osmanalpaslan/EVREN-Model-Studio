"""Ana pencere: sol menü + sayfa yığını."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from .. import __version__
from .app_context import AppContext
from .chat_page import ChatPage
from .code_studio_page import CodeStudioPage
from .connection_page import ConnectionPage
from .errors_page import ErrorsPage
from .help_page import HelpPage
from .history_page import HistoryPage
from .home_page import HomePage
from .models_page import ModelsPage
from .monitor_page import MonitorPage
from .settings_page import SettingsPage
from .usage_page import UsagePage

NAV_ITEMS = [
    ("Ana Sayfa", "home"),
    ("Chat", "chat"),
    ("Code Studio", "code"),
    ("Modeller", "models"),
    ("API Bağlantı Testi", "connection"),
    ("Kullanım / Kota", "usage"),
    ("Sohbetler ve Projeler", "history"),
    ("Hata Merkezi", "errors"),
    ("EVREN Durum İzleme", "monitor"),
    ("Ayarlar", "settings"),
    ("Yardım ve Tanılama", "help"),
]

STYLE = """
QWidget { font-size: 10pt; }
#pageTitle { font-size: 15pt; font-weight: 600; }
#dim { color: #9aa4b2; }
QListWidget#nav {
    background: #141a26; color: #d7dde6; border: none;
    padding: 8px 4px; font-size: 10.5pt;
}
QListWidget#nav::item {
    padding: 10px 14px; border-radius: 8px; margin: 2px 6px;
}
QListWidget#nav::item:selected { background: #2a3f6f; color: #ffffff; }
QListWidget#nav::item:hover { background: #1d2739; }
QFrame#card {
    background: #1a2233; border-radius: 10px;
    border: 1px solid #263145;
}
QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #141a26; color: #e4e9f0; border: 1px solid #2c3a52;
    border-radius: 6px; padding: 4px;
}
QPlainTextEdit#msgBody { background: #10151f; color: #dbe4f0; }
QPushButton {
    background: #2a3f6f; color: #ffffff; border: none;
    border-radius: 6px; padding: 7px 14px;
}
QPushButton:hover { background: #35508c; }
QPushButton:disabled { background: #232c3d; color: #6b7686; }
QTableWidget {
    background: #141a26; color: #d7dde6; gridline-color: #263145;
    border: 1px solid #263145; border-radius: 6px;
}
QHeaderView::section {
    background: #1a2233; color: #9aa4b2; border: none; padding: 6px;
}
QProgressBar {
    background: #141a26; border: 1px solid #2c3a52; border-radius: 6px;
    text-align: center; color: #d7dde6;
}
QProgressBar::chunk { background: #2a3f6f; border-radius: 5px; }
QLabel { color: #d7dde6; }
QScrollArea { background: transparent; }
QSplitter::handle { background: #263145; }
QCheckBox { color: #d7dde6; }
QTreeView { background: #141a26; color: #d7dde6; border: 1px solid #263145; }
"""

DARK_BG = "#0d1119"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ctx = AppContext()
        self.setWindowTitle(f"EVREN Model Studio {__version__}")
        self.resize(1280, 820)

        central = QWidget()
        central.setObjectName("central")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sol menü
        nav_host = QWidget()
        nav_host.setObjectName("navHost")
        nav_lay = QHBoxLayout(nav_host)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(232)
        for label, _key in NAV_ITEMS:
            self.nav.addItem(QListWidgetItem(label))
        self.nav.setCurrentRow(0)
        nav_lay.addWidget(self.nav)
        layout.addWidget(nav_host)

        # Sayfa yığını
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.pages: dict[str, QWidget] = {}
        self._build_pages()
        self.nav.currentRowChanged.connect(self._switch)

        self.setCentralWidget(central)
        self.setStyleSheet(STYLE)
        self.setStyleSheet(
            self.styleSheet()
            + f" QWidget {{ background: {DARK_BG}; }}"
            + " QListWidget#nav, QTreeView::branch { background: #141a26; }"
        )

    def _build_pages(self) -> None:
        def add(key: str, page: QWidget) -> None:
            self.pages[key] = page
            self.stack.addWidget(page)

        add("home", HomePage(self.ctx))
        add("chat", ChatPage(self.ctx))
        add("code", CodeStudioPage(self.ctx))
        add("models", ModelsPage(self.ctx))
        add("connection", ConnectionPage(self.ctx))
        add("usage", UsagePage(self.ctx))
        add("history", HistoryPage(self.ctx, open_chat_callback=self._open_chat))
        add("errors", ErrorsPage(self.ctx))
        add("monitor", MonitorPage(self.ctx))
        add("settings", SettingsPage(self.ctx))
        add("help", HelpPage(self.ctx))

        # Chat sayfasına ilk model listesini yüklemeyi dene
        try:
            if self.ctx.has_api_key():
                client = self.ctx.make_client()
                try:
                    models = client.list_models()
                    self.pages["chat"].set_models(models)
                finally:
                    client.close()
        except Exception:
            pass  # anahtar yoksa/erişilemezse Model sayfasından yenilenebilir

    def _switch(self, row: int) -> None:
        key = NAV_ITEMS[row][1]
        page = self.pages[key]
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except TypeError:
                pass
        self.stack.setCurrentWidget(page)

    def _open_chat(self, chat_id: int) -> None:
        # Sohbetler sayfasından Chat sayfasına geç
        for i, (_label, key) in enumerate(NAV_ITEMS):
            if key == "chat":
                self.nav.setCurrentRow(i)
        self.pages["chat"].load_chat(chat_id)

    def closeEvent(self, event) -> None:
        # İzleme ajanı çalışıyorsa kalan süreyi kaydet (devam seçeneği için)
        monitor = self.pages.get("monitor")
        if monitor and monitor.agent and monitor.agent.is_running():
            monitor.agent.stop(status="app_closed")
        self.ctx.save_settings()
        self.ctx.close()
        super().closeEvent(event)
