"""Sol menü: yeni oturum, arama, tarihe göre gruplanmış oturum listesi, araç sayfaları."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QModelIndex, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from . import brand, icons, theme
from .transcript import icon_button

ROLE_KIND = Qt.UserRole + 1      # "header" | "session"
ROLE_ID = Qt.UserRole + 2
ROLE_SUB = Qt.UserRole + 3
ROLE_PINNED = Qt.UserRole + 4

# Yalnız EVREN anahtarı varken anlamlı sayfalar (EVREN kotası, sağlık izleme, EVREN modelleri)
EVREN_ONLY_PAGES = {"models", "usage", "monitor", "connection"}
TOOL_PAGES = [
    ("models", "Modeller", "cpu"),
    ("usage", "Kullanım ve Kota", "gauge"),
    ("monitor", "EVREN Durum İzleme", "activity"),
    ("errors", "Hata Merkezi", "alert"),
    ("connection", "Bağlantı Testi", "plug"),
    ("home", "Sistem Durumu", "server"),
    ("help", "Yardım ve Tanılama", "help"),
    ("settings", "Ayarlar", "settings"),
]


def _group_for(iso: str, pinned: bool) -> str:
    if pinned:
        return "Sabitlenenler"
    try:
        ts = datetime.fromisoformat(iso)
    except ValueError:
        return "Daha eski"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    local = ts.astimezone()
    today = datetime.now().astimezone().date()
    d = local.date()
    if d == today:
        return "Bugün"
    if d == today - timedelta(days=1):
        return "Dün"
    if d > today - timedelta(days=7):
        return "Son 7 gün"
    if d > today - timedelta(days=30):
        return "Son 30 gün"
    return "Daha eski"


class SessionDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index: QModelIndex) -> QSize:
        if index.data(ROLE_KIND) == "header":
            return QSize(option.rect.width(), 30)
        return QSize(option.rect.width(), 46)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        p = theme.current()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        r: QRect = option.rect
        if index.data(ROLE_KIND) == "header":
            f = QFont(option.font)
            f.setPointSizeF(max(f.pointSizeF() - 1.5, 7.5))
            f.setWeight(QFont.DemiBold)
            painter.setFont(f)
            painter.setPen(QColor(p.text_faint))
            painter.drawText(r.adjusted(10, 8, -6, 0), Qt.AlignLeft | Qt.AlignVCenter,
                             index.data(Qt.DisplayRole))
            painter.restore()
            return
        if option.state & QStyle.State_Selected:
            painter.setBrush(QColor(p.selected))
        elif option.state & QStyle.State_MouseOver:
            painter.setBrush(QColor(p.hover))
        else:
            painter.setBrush(Qt.NoBrush)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(r.adjusted(2, 1, -2, -1), 8, 8)
        title = index.data(Qt.DisplayRole) or ""
        sub = index.data(ROLE_SUB) or ""
        f = QFont(option.font)
        painter.setFont(f)
        painter.setPen(QColor(p.text))
        fm = painter.fontMetrics()
        title_rect = r.adjusted(12, 6, -10, -r.height() // 2)
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         fm.elidedText(title, Qt.ElideRight, title_rect.width()))
        f2 = QFont(option.font)
        f2.setPointSizeF(max(f2.pointSizeF() - 1.5, 7.5))
        painter.setFont(f2)
        painter.setPen(QColor(p.text_faint))
        sub_rect = r.adjusted(12, r.height() // 2, -10, -5)
        painter.drawText(sub_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(sub, Qt.ElideRight, sub_rect.width()))
        painter.restore()


class Sidebar(QWidget):
    new_session = Signal()
    session_selected = Signal(int)
    session_action = Signal(str, int)      # rename | pin | export | delete
    page_requested = Signal(str)
    collapse_requested = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(220)
        self.setMaximumWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 12, 10, 10)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.logo = QLabel()
        self.refresh_logo()
        top.addWidget(self.logo)
        name = QLabel("EVREN Studio")
        name.setStyleSheet("font-weight: 700; font-size: 11.5pt;")
        top.addWidget(name)
        top.addStretch(1)
        collapse = icon_button("panel-left", "Kenar çubuğunu gizle (Ctrl+B)", 17)
        collapse.clicked.connect(self.collapse_requested.emit)
        top.addWidget(collapse)
        top.setSpacing(8)                  # iç düzen üst düzenin aralığını devralmasın
        header = QVBoxLayout()
        header.setSpacing(0)
        header.addLayout(top)
        # Geliştirici satırı ad satırının ALTINDA, tam genişlikte: ad ile gizleme düğmesi
        # arasına sıkıştırılınca 220 px'lik çubukta kesiliyordu ("…Osman Alp", 2026-10-19).
        credit = QLabel("Developed by Osman Alpaslan")
        credit.setObjectName("SidebarCredit")
        credit.setProperty("role", "faint")
        credit.setStyleSheet("font-size: 8.5pt;")
        credit.setContentsMargins(self.logo.sizeHint().width() + top.spacing(), 0, 0, 0)
        credit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)   # boş alanı o doldurmasın
        header.addWidget(credit)
        self.credit = credit
        lay.addLayout(header)

        self.new_btn = QPushButton("  Yeni oturum")
        self.new_btn.setObjectName("NewSession")
        self.new_btn.setIcon(icons.icon("plus", theme.current().text, 16))
        self.new_btn.setToolTip("Yeni oturum (Ctrl+N)")
        self.new_btn.setCursor(Qt.PointingHandCursor)
        self.new_btn.clicked.connect(self.new_session.emit)
        lay.addWidget(self.new_btn)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Oturumlarda ara…")
        self.search.addAction(icons.icon("search", size=15), QLineEdit.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.refresh())
        lay.addWidget(self.search)

        self.list = QListWidget()
        self.list.setObjectName("SessionList")
        self.list.setItemDelegate(SessionDelegate(self.list))
        self.list.setMouseTracking(True)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.itemClicked.connect(self._clicked)
        lay.addWidget(self.list, 1)

        self.empty = QLabel("Henüz oturum yok.\n“Yeni oturum” ile başlayın.")
        self.empty.setProperty("role", "faint")
        self.empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.empty)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {theme.current().border};")
        lay.addWidget(sep)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label, icon_name in TOOL_PAGES:
            b = QPushButton("  " + label)
            b.setProperty("nav", True)
            b.setCheckable(True)
            b.setIcon(icons.icon(icon_name, size=16))
            b.setIconSize(QSize(16, 16))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.page_requested.emit(k))
            lay.addWidget(b)
            self.nav_buttons[key] = b
        self._current_id: int | None = None
        self.refresh()

    # -- liste --

    def refresh_logo(self) -> None:
        self.logo.setPixmap(brand.pixmap(22))

    def refresh(self) -> None:
        rows = self.ctx.db.list_sessions(self.search.text().strip())
        self.list.clear()
        last_group = None
        for r in rows:
            group = _group_for(r["updated_at"], bool(r["pinned"]))
            if group != last_group:
                h = QListWidgetItem(group)
                h.setData(ROLE_KIND, "header")
                h.setFlags(Qt.NoItemFlags)
                self.list.addItem(h)
                last_group = group
            ws = r["workspace"]
            sub = Path(ws).name if ws else "Sohbet"
            it = QListWidgetItem(r["title"])
            it.setData(ROLE_KIND, "session")
            it.setData(ROLE_ID, r["id"])
            it.setData(ROLE_SUB, sub + ("" if not ws else f"  ·  {r['model']}"))
            it.setData(ROLE_PINNED, bool(r["pinned"]))
            it.setToolTip(f"{r['title']}\n{ws or 'Klasörsüz sohbet'}")
            self.list.addItem(it)
            if r["id"] == self._current_id:
                it.setSelected(True)
                self.list.setCurrentItem(it)
        self.empty.setVisible(not rows)
        self.list.setVisible(bool(rows))

    def set_current(self, session_id: int | None) -> None:
        self._current_id = session_id
        self.list.clearSelection()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(ROLE_ID) == session_id and session_id is not None:
                it.setSelected(True)
                self.list.setCurrentItem(it)

    def apply_providers(self, providers: set[str]) -> None:
        """EVREN anahtarı yoksa (yalnız OpenAI/Anthropic) EVREN'e özel sayfaları gizler.
        Hiç anahtar yoksa gösterilir (kullanıcı EVREN'i keşfetsin)."""
        show = "evren" in providers or not providers
        for key in EVREN_ONLY_PAGES:
            if key in self.nav_buttons:
                self.nav_buttons[key].setVisible(show)

    def set_page(self, key: str | None) -> None:
        for k, b in self.nav_buttons.items():
            b.setChecked(k == key)
        if key:
            self.list.clearSelection()

    def _clicked(self, item: QListWidgetItem) -> None:
        sid = item.data(ROLE_ID)
        if sid is not None:
            self.session_selected.emit(int(sid))

    def _menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None or item.data(ROLE_ID) is None:
            return
        sid = int(item.data(ROLE_ID))
        m = QMenu(self)
        m.addAction(icons.icon("pencil", size=15), "Yeniden adlandır",
                    lambda: self.session_action.emit("rename", sid))
        pinned = bool(item.data(ROLE_PINNED))
        m.addAction(icons.icon("pin", size=15), "Sabitlemeyi kaldır" if pinned else "Sabitle",
                    lambda: self.session_action.emit("pin", sid))
        m.addAction(icons.icon("download", size=15), "Markdown olarak dışa aktar",
                    lambda: self.session_action.emit("export", sid))
        m.addSeparator()
        m.addAction(icons.icon("trash", theme.current().danger, 15), "Sil",
                    lambda: self.session_action.emit("delete", sid))
        m.exec(self.list.mapToGlobal(pos))
