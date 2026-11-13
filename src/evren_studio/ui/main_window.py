"""Ana pencere: sol menü | oturum çalışma alanı (veya araç sayfası) | sağ panel."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QLabel,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QWidget,
)

from .. import __version__
from . import brand, icons, theme, transcript, transitions, wheel_guard, workers
from .app_context import AppContext
from .connection_page import ConnectionPage
from .errors_page import ErrorsPage
from .help_page import HelpPage
from .home_page import HomePage
from .models_page import ModelsPage
from .monitor_page import MonitorPage
from .session_view import SessionView
from .settings_page import SettingsPage
from .skills_page import SkillsPage
from .side_panel import SidePanel
from .sidebar import Sidebar
from .usage_page import UsagePage

# Sütun sınırları (px). Orta alanın AÇIK alt sınırı kenar çubuğu kaybolma hatasını önler.
SIDEBAR_MIN, SIDEBAR_MAX = 220, 420
PANEL_MIN, PANEL_MAX = 300, 560
CENTER_MIN = 400


class _LazyPages(dict):
    """Sayfa sözlüğü: `pages[k]` sayfa yoksa kurar, pencereye ekler ve döndürür. `.get(k)`, `in`, `items()` yalnız
    KURULMUŞ sayfaları görür (kapanışta izleme ajanını durdurmak gibi işler kurulmamış sayfayı boşuna kurmasın).
    Tüm sayfa adları: `MainWindow.page_keys`."""

    def __init__(self, factories: dict, install) -> None:
        super().__init__()
        self._factories = factories
        self._install = install

    def __missing__(self, key: str):
        if key not in self._factories:
            raise KeyError(key)
        page = self._factories[key]()
        self[key] = page
        self._install(key, page)
        return page


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        workers.set_accepting(True)
        self.ctx = AppContext()
        s = self.ctx.settings
        app = QApplication.instance()
        if app is not None:
            theme.apply_theme(app, s.theme, s.font_size, s.compact_view)
            wheel_guard.install(app)
        self.setWindowTitle("EVREN Studio")
        self.setWindowIcon(brand.app_icon())       # ay-yıldız, temaya göre beyaz/kırmızı
        self.resize(1440, 900)
        # En küçük pencere = kenar çubuğu (220) + orta (CENTER_MIN) + sağ panel (300) + tutamaçlar
        self.setMinimumSize(SIDEBAR_MIN + CENTER_MIN + PANEL_MIN + 10, 600)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("Root")
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)

        self.sidebar = Sidebar(self.ctx)
        self.panel = SidePanel(self.ctx)
        self.center = QStackedWidget()
        self.center.setObjectName("CenterStack")
        # KENAR ÇUBUĞU KAYBOLMA HATASI (2026-10-21): QStackedWidget'ın en küçük boyut ipucu TÜM
        # sayfaların en büyüğü (kaydırmasız uzun açıklamalar yüzünden 1728 px > pencere). QSplitter
        # sürüklemede bunu orta alanın alt sınırı sayıp taşanı SOLDAN kesiyordu: çubuk x=-810'a
        # itiliyor, görünmez oluyordu; genişletmek hiç mümkün değildi. Açık alt sınır bunu keser.
        self.center.setMinimumWidth(CENTER_MIN)
        self.session = SessionView(self.ctx, self.panel)
        self.center.addWidget(self.session)

        # Zamanlanmış görevler (Madde 12c): motor sayfadan önce kurulur (sayfa onun sinyallerine bağlanır)
        from .schedule_host import ScheduleHost

        self.scheduler = ScheduleHost(self.ctx, self)
        self._build_pages()
        self.sidebar.set_available_pages(self.page_keys)

        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.center)
        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.setCentralWidget(self.splitter)
        self._sizes_applied = False
        self.splitter.splitterMoved.connect(self._remember_widths)

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
        self.session.notify.connect(self.show_notification)
        self.scheduler.notify.connect(self.show_notification)
        self.scheduler.sessions_changed.connect(self.sidebar.refresh)
        self._tray = None
        self.sidebar.apply_providers(self.ctx.available_providers())
        self.ctx.on_models_changed(self.session.refresh_models)

        self._shortcuts()
        self._apply_view()
        wheel_guard.protect(self)              # tüm sayı/liste alanları (bkz. wheel_guard)
        self.sidebar.setVisible(s.sidebar_visible)
        self.session.set_sidebar_hidden(not s.sidebar_visible)
        self.panel.setVisible(s.panel_visible)
        self.show_sessions()
        # Kota yüzünden duran iş varsa (önceki açılıştan) oturumunu aç ve otomatik devamı yeniden kur
        QTimer.singleShot(0, self, self.session.restore_pending_resume)
        self.scheduler.start()
        # Gözlem ajanı: kuyruktaki gözlemleri arka planda depoya gönder (açılıştan 2 dk sonra, sonra 30 dk'da bir)
        from .. import gozlem

        gozlem.AYAR_ACIK = bool(s.gozlem_enabled)
        self._gozlem_timer = QTimer(self)
        self._gozlem_timer.setInterval(30 * 60 * 1000)
        self._gozlem_timer.timeout.connect(self._send_gozlem)
        self._gozlem_timer.start()
        QTimer.singleShot(2 * 60 * 1000, self, self._send_gozlem)
        # C2: güncelleme denetimi açılıştan 20 sn sonra (açılışı yavaşlatmaz), günde en çok bir kez
        QTimer.singleShot(20 * 1000, self, self._auto_update_check)
        # Günlük otomatik yerel yedek (açılıştan 60 sn sonra, arka planda; açılışı yavaşlatmaz)
        QTimer.singleShot(60 * 1000, self, self._auto_backup)
        QTimer.singleShot(15 * 1000, self, self._maintain_history)

    update_info = None
    last_auto_backup = None
    last_history_maintenance = None
    # Pencere kapandı (closeEvent: bağlam ve veritabanı kapalı). Gecikmeli işler (yedek 60 sn, bakım 15 sn, güncelleme
    # 20 sn, gözlem gönderimi) bundan sonra çalışmaz — gözlem b8efe202e31e (2026-11-12, 7 kez): aynı süreçte ikinci
    # pencere açan araçta kapanmış pencerenin yedeği silinmiş klasördeki veritabanını açmaya çalışıyordu.
    _closed = False

    def start_background_loads(self) -> None:
        """Açılıştan sonra arka planda: canlı EVREN model listesi (1 sn; yetenek bayrakları, yeni modeller) ve kullanım
        düğmesi (1,5 sn). Pencere kurulumu ağ isteği YAPMAZ (açılış hızı, tests/test_acilis_hizi). Uygulama (app.py) ve
        pencereyi doğrudan kuran gerçek API testleri aynı yolu çağırır — 2026-11-13: e2e_ui_real_api canlı listeyi hiç
        yüklemiyordu ("canlı model listesi" kontrolü düştü; açılış hızlandırması Modeller sayfasındaki isteği kaldırınca)."""
        QTimer.singleShot(1500, self, self.session.refresh_usage)
        QTimer.singleShot(1000, self, self.session.load_live_models)

    def _maintain_history(self) -> None:
        """Ajanın dosya geçmişini arka planda bir kez sıkıştırır ve gerekiyorsa veritabanını küçültür (2026-11-12,
        kullanıcı onayı; bkz. db.maintain_file_history). Testte kapalı (EVREN_STUDIO_NO_DB_MAINT)."""
        import os

        from ..db import PACK_DONE_KEY

        if self._closed:
            return
        db = self.ctx.db
        if os.environ.get("EVREN_STUDIO_NO_DB_MAINT") or db.get_meta(PACK_DONE_KEY) == "1":
            return

        def done(info) -> None:
            self.last_history_maintenance = info

        workers.Task(db.maintain_file_history, on_done=done, on_error=lambda _e: None).start()

    def _auto_backup(self) -> None:
        import os

        from ..backup import auto_backup

        if self._closed or not self.ctx.settings.auto_backup or os.environ.get("EVREN_STUDIO_NO_AUTO_BACKUP"):
            return
        ctx = self.ctx

        def done(path) -> None:
            self.last_auto_backup = path

        workers.Task(lambda: auto_backup(ctx.db.path, ctx.data_dir(), ctx.store.path), on_done=done,
                     on_error=lambda _e: None).start()

    def _auto_update_check(self) -> None:
        import os

        if not self._closed and not os.environ.get("EVREN_STUDIO_NO_UPDATE_CHECK"):   # testler GitHub'a gitmesin
            self.check_updates()

    def check_updates(self, force: bool = False) -> None:
        from datetime import datetime, timezone

        from .. import updates

        s = self.ctx.settings
        if not s.update_check or (not force and not updates.due(s.update_last_check)):
            return
        skipped = s.update_skipped

        def done(info) -> None:
            s.update_last_check = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.ctx.save_settings()
            if info is not None:
                self._show_update(info)

        workers.Task(lambda: updates.check(__version__, skipped=skipped), on_done=done,
                     on_error=lambda _e: None).start()

    def _show_update(self, info) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from .transcript import ActionCard

        self.update_info = info

        def skip() -> None:
            self.ctx.settings.update_skipped = info.version
            self.ctx.save_settings()
            self.sidebar.update_btn.hide()

        lines = [f"Yüklü sürüm {__version__}; yeni sürüm {info.version}. Kurulum dosyası indirilir, çalıştırınca "
                 "eski sürümün üstüne kurulur (ayarlarınız ve oturumlarınız korunur)."]
        if info.notes:
            lines.append(info.notes.strip().splitlines()[0][:200])
        card = ActionCard(f"EVREN Studio {info.version} yayınlandı", lines,
                          [("İndir", lambda: QDesktopServices.openUrl(QUrl(info.asset_url or info.url)), "primary"),
                           ("Sürüm notları", lambda: QDesktopServices.openUrl(QUrl(info.url)), "ghost"),
                           ("Bu sürümü atla", skip, "ghost")], icon_name="download")
        self.session.transcript.add(card)
        # Kart yalnız oturum açıkken görünür; kenar çubuğundaki düğme her ekranda görünür
        btn = self.sidebar.update_btn
        btn.setText(f"Yeni sürüm {info.version} — indir")
        btn.setToolTip(f"Yüklü sürüm {__version__}. Tıklayınca kurulum dosyası tarayıcıda indirilir.")
        try:
            btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        btn.clicked.connect(lambda _=None: QDesktopServices.openUrl(QUrl(info.asset_url or info.url)))
        btn.show()
        self.show_notification("EVREN Studio — yeni sürüm", f"{info.version} yayınlandı. İndirmek için uygulamaya bakın.")

    def _send_gozlem(self) -> None:
        from .. import gozlem

        if self._closed:
            return
        gozlem.AYAR_ACIK = bool(self.ctx.settings.gozlem_enabled)
        if not gozlem.etkin() or self._gozlem_busy:
            return
        self._gozlem_busy = True

        def finished(_res=None):
            self._gozlem_busy = False

        workers.Task(gozlem.gonder, on_done=finished, on_error=finished).start()

    _gozlem_busy = False

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._sizes_applied:
            self._sizes_applied = True
            s = self.ctx.settings
            side = min(max(int(s.sidebar_width or 264), SIDEBAR_MIN), SIDEBAR_MAX)
            panel = min(max(int(s.panel_width or 360), PANEL_MIN), PANEL_MAX)
            total = max(self.splitter.width(), self.width())
            self.splitter.setSizes([side, max(total - side - panel, CENTER_MIN), panel])

    def _remember_widths(self, *_args) -> None:
        """Kullanıcı tutamacı sürükleyince genişlikler ayara yazılır (kapanışta kaydedilir)."""
        sizes = self.splitter.sizes()
        s = self.ctx.settings
        if self.sidebar.isVisible() and sizes[0] > 0:
            s.sidebar_width = min(max(sizes[0], SIDEBAR_MIN), SIDEBAR_MAX)
        if self.panel.isVisible() and sizes[2] > 0:
            s.panel_width = min(max(sizes[2], PANEL_MIN), PANEL_MAX)

    # ---- sayfalar ----

    def _build_pages(self) -> None:
        """AÇILIŞ HIZI (2026-11-12): sayfalar ilk açıldıklarında kurulur (`pages[k]` kurar; `.get(k)` kurmaz). Ölçüm:
        pencere kurulumunun yarıdan fazlası Qt'nin stil (QSS) uygulamasıydı; görünmeyen Ayarlar/Yardım/... sayfaları
        da açılışta kurulup stillendiriliyordu. Modeller sayfası kurulurken canlı model listesini çekiyordu — açılışta
        aynı listeyi zaten app.py (`session.load_live_models`) çekiyor: çift ağ isteği de kalktı. İzleme sayfası
        kendiliğinden başlamaz; kapanışta yalnız kurulmuşsa durdurulur (`pages.get`)."""
        from .scheduled_page import ScheduledPage

        def settings() -> QWidget:
            page = SettingsPage(self.ctx)
            page.settings_saved.connect(self._settings_saved)
            page.open_workspace.connect(self.open_workspace)
            return page

        def skills() -> QWidget:
            page = SkillsPage(self.ctx)
            page.template_requested.connect(self._use_template)
            return page

        def scheduled() -> QWidget:
            page = ScheduledPage(self.ctx, self.scheduler)
            page.open_session.connect(self.open_session)
            return page

        factories = {
            "home": lambda: HomePage(self.ctx),
            "models": lambda: ModelsPage(self.ctx),
            "connection": lambda: ConnectionPage(self.ctx),
            "usage": lambda: UsagePage(self.ctx),
            "errors": lambda: ErrorsPage(self.ctx),
            "monitor": lambda: MonitorPage(self.ctx),
            "settings": settings,
            "help": lambda: HelpPage(self.ctx),
            "skills": skills,
            "scheduled": scheduled,
        }
        self.page_keys: tuple[str, ...] = tuple(factories)
        self.pages = _LazyPages(factories, self._install_page)

    def _install_page(self, key: str, page: QWidget) -> None:
        self.center.addWidget(page)
        # Uzun açıklama yazıları kaydırılsın: kaydırmasız etiket sayfanın (dolayısıyla orta alanın)
        # en küçük genişliğini 1000+ px'e çıkarıyordu (kenar çubuğu kaybolma hatasının kaynağı).
        for lab in page.findChildren(QLabel):
            if not lab.wordWrap() and len(lab.text()) > 90:
                lab.setWordWrap(True)

    def show_page(self, key: str) -> None:
        # "settings:saglayicilar:evren" → Ayarlar, Sağlayıcılar menüsü, EVREN ekleme penceresi (2026-11-12)
        key, _, rest = key.partition(":")
        page = self.pages[key] if key in self.page_keys else None
        if page is None:
            return
        if rest and hasattr(page, "open_category"):
            cat, _, action = rest.partition(":")
            page.open_category(cat)
            if action and hasattr(page, "open_connection"):
                QTimer.singleShot(0, page, lambda a=action: page.open_connection(a))   # sayfa görünür olduktan sonra
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except TypeError:
                pass
        wheel_guard.protect(page)          # ekranda sonradan eklenen alanlar da korunsun
        transitions.switch(self.center, page)          # yumuşak geçiş (2026-11-12)
        self.sidebar.set_page(key)
        self.panel.setVisible(False)

    def _use_template(self, prompt: str, profile: str) -> None:
        """F4 #10: şablon → yeni oturum, profil, mesaj kutusu dolu (gönderilmez)."""
        self.show_sessions()
        self.session.new_session()
        if profile and self.ctx.profile(profile):
            self.session.apply_profile(profile)
        self.session.composer.set_text(prompt)
        self.session.composer.focus()

    def show_sessions(self) -> None:
        transitions.switch(self.center, self.session)
        self.sidebar.set_page(None)
        self.sidebar.set_current(self.session.session_id)
        self.panel.setVisible(self.ctx.settings.panel_visible)
        self.session.welcome.refresh()

    def new_session(self) -> None:
        self.show_sessions()
        self.session.new_session()

    def open_workspace(self, path: str) -> None:
        """GitHub'dan indirilen (veya başka yerden gelen) klasörü yeni oturumda proje olarak açar."""
        self.show_sessions()
        if self.session.running:
            return
        self.session.new_session()
        self.session.welcome._choose(path)

    def open_session(self, sid: int) -> None:
        a = self.scheduler.active
        if a is not None and a["sid"] == sid:
            # Aynı oturumu iki görünüm birden sürdürmesin: görev bitince açılır ya da durdurulup açılır
            from PySide6.QtWidgets import QMessageBox

            box = QMessageBox(QMessageBox.Information, "Zamanlanmış görev çalışıyor",
                              f"“{a['name']}” bu oturumda şu an arka planda çalışıyor. Bitince açabilirsiniz.",
                              parent=self)
            stop = box.addButton("Durdur ve aç", QMessageBox.DestructiveRole)
            box.addButton("Tamam", QMessageBox.AcceptRole)
            box.exec()
            if box.clickedButton() is not stop:
                self.sidebar.set_current(self.session.session_id)
                return
            self.scheduler.stop_task(a["task_id"])
            # durdurma kayıtları (iptal sonuçları) yazılsın, sonra güncel hâli aç
            QTimer.singleShot(1500, self, lambda: (self.show_sessions(), self.session.open_session(sid)))
            return
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

    def focus_session_search(self) -> None:
        """Ctrl+K: oturum araması. Kenar çubuğu kapalıysa normal yoldan açılır; doğrudan
        setVisible(True) ayarı ve başlıktaki "kenar çubuğunu göster" düğmesini güncel
        bırakmıyordu (yeniden açılışta çubuk kendiliğinden kapanıyordu)."""
        if not self.sidebar.isVisible():
            self.toggle_sidebar()
        self.sidebar.search.setFocus()

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
        sc("Ctrl+K", self.focus_session_search)
        sc("Ctrl+L", lambda: (self.show_sessions(), self.session.composer.focus()))
        sc("Ctrl+,", lambda: self.show_page("settings"))
        sc("Esc", self._escape)
        # F5 #12 canlı yazı boyutu · #11 sade görünüm
        sc("Ctrl+=", lambda: self.zoom(+1))
        sc("Ctrl++", lambda: self.zoom(+1))
        sc("Ctrl+-", lambda: self.zoom(-1))
        sc("Ctrl+0", lambda: self.zoom(0))
        sc("Ctrl+Shift+H", self.toggle_simple_view)
        sc("Ctrl+Shift+P", self.open_palette)

    def zoom(self, delta: int) -> None:
        """Yazı boyutu: +1/-1 pt (8-16), 0 → varsayılan 10. Kalıcı (ayar)."""
        s = self.ctx.settings
        size = 10 if delta == 0 else max(8, min(16, int(s.font_size) + delta))
        if size == s.font_size:
            return
        s.font_size = size
        self.ctx.save_settings()
        app = QApplication.instance()
        if app is not None:
            theme.apply_theme(app, s.theme, s.font_size, s.compact_view)

    # ---- E10 komut paleti ----

    def palette_actions(self) -> list:
        from ..agent import templates as tpl
        from .command_palette import Action
        from .composer import MODE_COMMANDS, SLASH_COMMANDS
        from .settings_page import backup_sessions, open_data_dir
        from .sidebar import TOOL_PAGES

        s = self.session
        acts = [Action("Yeni oturum", "Oturum", self.new_session, "yeni sohbet", "Ctrl+N"),
                Action("Sohbet ekranı", "Git", self.show_sessions, "oturum mesaj")]
        acts += [Action(title, "Git", lambda k=key: self.show_page(k), key) for key, title, _i in TOOL_PAGES]
        labels = {"/manuel": "Manuel mod", "/kabul": "Düzenlemeleri kabul et", "/plan": "Plan modu",
                  "/otomatik": "Otomatik mod"}
        acts += [Action(labels[c], "Mod", lambda c=c: (self.show_sessions(), s._command(c)), c)
                 for c in labels if c in MODE_COMMANDS]
        for cmd, desc in SLASH_COMMANDS.items():
            if cmd in MODE_COMMANDS:
                continue
            acts.append(Action(f"{cmd} — {desc[:70]}", "Komut",
                               lambda c=cmd: (self.show_sessions(), s.composer.set_text(c + " "), s.composer.focus()),
                               desc))
        st = self.ctx.settings
        acts += [
            Action(("Sade görünümü kapat" if st.simple_view else "Sade görünüm (araç adımlarını gizle)"), "Görünüm",
                   self.toggle_simple_view, "sade basit gizle", "Ctrl+Shift+H"),
            Action(("Sıkışık görünümü kapat" if st.compact_view else "Sıkışık görünüm"), "Görünüm",
                   self.toggle_compact_view, "sikisik yogun"),
            Action("Yazıyı büyüt", "Görünüm", lambda: self.zoom(+1), "font yazi boyutu", "Ctrl+="),
            Action("Yazıyı küçült", "Görünüm", lambda: self.zoom(-1), "font yazi boyutu", "Ctrl+-"),
            Action("Yazı boyutunu sıfırla", "Görünüm", lambda: self.zoom(0), "font yazi boyutu", "Ctrl+0"),
            Action("Kenar çubuğunu aç/kapat", "Görünüm", self.toggle_sidebar, "sidebar", "Ctrl+B"),
            Action("Sağ paneli aç/kapat", "Görünüm", self.toggle_panel, "panel", "Ctrl+J"),
            Action("Veri klasörünü aç", "Veri", lambda: open_data_dir(self, self.ctx), "dosya gezgini"),
            Action("Oturumları yedekle…", "Veri", lambda: backup_sessions(self, self.ctx), "yedek zip backup"),
        ]
        acts += [Action(f"Profil uygula: {p['name']}", "Profil",
                        lambda n=p["name"]: (self.show_sessions(), s.apply_profile(n)))
                 for p in self.ctx.db.list_profiles()]
        if s.profile:
            acts.append(Action("Profili kaldır", "Profil", lambda: s.apply_profile(None)))
        acts += [Action(f"Şablon: {t.name}", "Şablon", lambda t=t: self._use_template(t.prompt, t.profile),
                        t.description)
                 for t in list(tpl.BUILTIN) + [tpl.from_row(r) for r in self.ctx.db.list_templates()]]
        return acts

    def open_palette(self) -> None:
        from .command_palette import CommandPalette

        dlg = CommandPalette(self.palette_actions(), self)
        geo = self.geometry()
        dlg.move(geo.x() + (geo.width() - dlg.width()) // 2, geo.y() + 80)
        if dlg.exec() and dlg.chosen is not None:
            dlg.chosen.run()

    def toggle_compact_view(self) -> None:
        s = self.ctx.settings
        s.compact_view = not s.compact_view
        self.ctx.save_settings()
        app = QApplication.instance()
        if app is not None:
            theme.apply_theme(app, s.theme, s.font_size, s.compact_view)
        self._apply_view()

    def toggle_simple_view(self) -> None:
        s = self.ctx.settings
        s.simple_view = not s.simple_view
        self.ctx.save_settings()
        self._apply_view()

    def _apply_view(self) -> None:
        s = self.ctx.settings
        transcript.set_simple_view(s.simple_view, self.session)
        self.session.transcript.set_compact(s.compact_view)

    def _escape(self) -> None:
        """Esc: önce açık komut/model listesini kapatır, yoksa çalışan ajanı durdurur."""
        comp = self.session.composer
        if comp.popup_visible():
            comp.hide_popup()
        else:
            self.session.stop()

    def show_notification(self, title: str, text: str) -> None:
        """Windows bildirimi (proje ajanı bitti/duraklatıldı). Ek hizmet gerektirmez:
        sistem tepsisi simgesi üzerinden Windows bildirim merkezine düşer."""
        from PySide6.QtWidgets import QSystemTrayIcon

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if self._tray is None:
            self._tray = QSystemTrayIcon(self.windowIcon(), self)
            self._tray.setToolTip("EVREN Studio")
            self._tray.messageClicked.connect(lambda: (self.showNormal(), self.raise_(), self.activateWindow()))
        self._tray.show()
        self._tray.showMessage(title, text, QSystemTrayIcon.Information, 15000)

    def _apply_providers(self) -> None:
        """Anahtar eklenip silinince EVREN'e özel sayfalar ve model listesi güncellenir."""
        from .sidebar import EVREN_ONLY_PAGES

        provs = self.ctx.available_providers()
        self.sidebar.apply_providers(provs)
        cur = next((k for k, p in self.pages.items() if p is self.center.currentWidget()), None)
        if cur in EVREN_ONLY_PAGES and provs and "evren" not in provs:
            self.show_sessions()

    def _settings_saved(self) -> None:
        self._apply_providers()
        s = self.ctx.settings
        app = QApplication.instance()
        if app is not None:
            icons.clear_cache()
            theme.apply_theme(app, s.theme, s.font_size, s.compact_view)
            self.setWindowIcon(brand.app_icon())
            self.sidebar.refresh_logo()
            self.session.welcome.refresh_logo()
        self._apply_view()
        self.session.composer.edit.send_with_enter = s.send_with_enter
        self.sidebar.refresh()
        self.session.refresh_models()
        self.session.welcome.refresh()
        if self.session.session_id and not self.ctx.db.get_session(self.session.session_id):
            self.session.new_session()   # veriler silindiyse

    def closeEvent(self, event) -> None:
        self._closed = True            # gecikmeli yedek/bakım/güncelleme/gözlem işleri artık çalışmaz
        timer = getattr(self, "_gozlem_timer", None)
        if timer is not None:
            timer.stop()
        workers.set_accepting(False)   # kapanırken geç gelen sonuçlar işlenmesin
        self.session.shutdown()
        self.scheduler.shutdown()
        monitor = self.pages.get("monitor")
        if monitor and getattr(monitor, "agent", None) and monitor.agent.is_running():
            monitor.agent.stop(status="app_closed")
        self.ctx.save_settings()
        self.ctx.close()
        super().closeEvent(event)
