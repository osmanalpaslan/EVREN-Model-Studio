"""Ana pencere: sol menü | oturum çalışma alanı (veya araç sayfası) | sağ panel."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QWidget,
)

from .. import __version__
from . import icons, theme
from .app_context import AppContext
from .connection_page import ConnectionPage
from .errors_page import ErrorsPage
from .help_page import HelpPage
from .home_page import HomePage
from .models_page import ModelsPage
from .monitor_page import MonitorPage
from .session_view import SessionView
from .settings_page import SettingsPage
from .side_panel import SidePanel
from .sidebar import Sidebar
from .usage_page import UsagePage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ctx = AppContext()
        s = self.ctx.settings
        app = QApplication.instance()
        if app is not None:
            theme.apply_theme(app, s.theme, s.font_size)
        self.setWindowTitle("EVREN Studio")
        self.setWindowIcon(icons.icon("spark", theme.current().accent, 32))
        self.resize(1440, 900)
        self.setMinimumSize(900, 600)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("Root")
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)

        self.sidebar = Sidebar(self.ctx)
        self.panel = SidePanel(self.ctx)
        self.center = QStackedWidget()
        self.center.setObjectName("CenterStack")
        self.session = SessionView(self.ctx, self.panel)
        self.center.addWidget(self.session)

        self.pages: dict[str, QWidget] = {}
        self._build_pages()

        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.center)
        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.setCentralWidget(self.splitter)
        self._sizes_applied = False

        # bağlantılar
        self.sidebar.new_session.connect(self.new_session)
        self.sidebar.session_selected.connect(self.open_session)
        self.sidebar.session_action.connect(self._session_action)
        self.sidebar.page_requested.connect(self.show_page)
        self.sidebar.collapse_requested.connect(self.toggle_sidebar)
        self.session.sessions_changed.connect(self.sidebar.refresh)
        self.session.session_opened.connect(self.sidebar.set_current)
        self.session.page_requested.connect(self.show_page)
        self.session.toggle_sidebar.connect(self.toggle_sidebar)
        self.session.toggle_panel.connect(self.toggle_panel)
        self.ctx.on_models_changed(self.session.refresh_models)

        self._shortcuts()
        self.sidebar.setVisible(s.sidebar_visible)
        self.session.set_sidebar_hidden(not s.sidebar_visible)
        self.panel.setVisible(s.panel_visible)
        self.show_sessions()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._sizes_applied:
            self._sizes_applied = True
            total = max(self.width(), 900)
            side, panel = 264, 360
            self.splitter.setSizes([side, max(total - side - panel, 420), panel])

    # ---- sayfalar ----

    def _build_pages(self) -> None:
        def add(key: str, page: QWidget) -> None:
            self.pages[key] = page
            self.center.addWidget(page)

        add("home", HomePage(self.ctx))
        add("models", ModelsPage(self.ctx))
        add("connection", ConnectionPage(self.ctx))
        add("usage", UsagePage(self.ctx))
        add("errors", ErrorsPage(self.ctx))
        add("monitor", MonitorPage(self.ctx))
        settings = SettingsPage(self.ctx)
        settings.settings_saved.connect(self._settings_saved)
        add("settings", settings)
        add("help", HelpPage(self.ctx))

    def show_page(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except TypeError:
                pass
        self.center.setCurrentWidget(page)
        self.sidebar.set_page(key)
        self.panel.setVisible(False)

    def show_sessions(self) -> None:
        self.center.setCurrentWidget(self.session)
        self.sidebar.set_page(None)
        self.sidebar.set_current(self.session.session_id)
        self.panel.setVisible(self.ctx.settings.panel_visible)
        self.session.welcome.refresh()

    def new_session(self) -> None:
        self.show_sessions()
        self.session.new_session()

    def open_session(self, sid: int) -> None:
        self.show_sessions()
        self.session.open_session(sid)

    def _session_action(self, action: str, sid: int) -> None:
        db = self.ctx.db
        if action == "rename":
            row = db.get_session(sid)
            title, ok = QInputDialog.getText(self, "Oturumu adlandır", "Yeni ad:", text=row["title"])
            if ok and title.strip():
                db.update_session(sid, title=title.strip())
                if sid == self.session.session_id:
                    self.session._update_header()
        elif action == "pin":
            row = db.get_session(sid)
            db.update_session(sid, pinned=0 if row["pinned"] else 1)
        elif action == "export":
            self.session.export(sid)
        elif action == "delete":
            self.session.delete_session(sid)
        self.sidebar.refresh()

    # ---- görünüm ----

    def toggle_sidebar(self) -> None:
        vis = not self.sidebar.isVisible()
        self.sidebar.setVisible(vis)
        self.session.set_sidebar_hidden(not vis)
        self.ctx.settings.sidebar_visible = vis

    def toggle_panel(self) -> None:
        if self.center.currentWidget() is not self.session:
            self.show_sessions()
            return
        vis = not self.panel.isVisible()
        self.panel.setVisible(vis)
        self.ctx.settings.panel_visible = vis

    def _shortcuts(self) -> None:
        def sc(seq: str, fn) -> None:
            s = QShortcut(QKeySequence(seq), self)
            s.setContext(Qt.WindowShortcut)
            s.activated.connect(fn)

        sc("Ctrl+N", self.new_session)
        sc("Ctrl+B", self.toggle_sidebar)
        sc("Ctrl+J", self.toggle_panel)
        sc("Ctrl+K", lambda: (self.sidebar.setVisible(True), self.sidebar.search.setFocus()))
        sc("Ctrl+L", lambda: (self.show_sessions(), self.session.composer.focus()))
        sc("Ctrl+,", lambda: self.show_page("settings"))
        sc("Esc", self.session.stop)

    def _settings_saved(self) -> None:
        s = self.ctx.settings
        app = QApplication.instance()
        if app is not None:
            icons.clear_cache()
            theme.apply_theme(app, s.theme, s.font_size)
        self.session.composer.edit.send_with_enter = s.send_with_enter

    def closeEvent(self, event) -> None:
        self.session.shutdown()
        monitor = self.pages.get("monitor")
        if monitor and getattr(monitor, "agent", None) and monitor.agent.is_running():
            monitor.agent.stop(status="app_closed")
        self.ctx.save_settings()
        self.ctx.close()
        super().closeEvent(event)
