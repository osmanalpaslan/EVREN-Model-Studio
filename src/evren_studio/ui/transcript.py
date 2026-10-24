"""Oturum akışı bileşenleri: mesajlar, düşünce bloğu, araç kartları, onaylar."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..agent import textproto
from . import brand, icons, theme
from .markdown_view import MarkdownView

COLUMN_WIDTH = 860

TOOL_ICONS = {
    "list_files": "folder", "read_file": "file", "search_files": "search",
    "find_files": "search", "write_file": "pencil", "edit_file": "pencil",
    "run_command": "terminal", "update_todos": "list", "arac_cagrisi": "alert",
    "read_table": "list", "web_fetch": "external", "read_skill": "bulb", "convert_model": "refresh",
    "polyhaven_search": "search", "polyhaven_download": "download", "godot_export": "download",
}


def icon_button(name: str, tip: str, size: int = 16, checkable: bool = False) -> QToolButton:
    b = QToolButton()
    b.setProperty("variant", "icon")
    b.setIcon(icons.icon(name, size=size))
    b.setIconSize(QSize(size, size))
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setCheckable(checkable)
    return b


def _retain(w: QWidget) -> QWidget:
    sp = w.sizePolicy()
    sp.setRetainSizeWhenHidden(True)
    w.setSizePolicy(sp)
    return w


def faint_label(text: str = "", role: str = "faint") -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", role)
    return lab


def format_duration(seconds: float | None) -> str:
    """8.4 → '8,4 sn', 72 → '1 dk 12 sn' (Türkçe ondalık virgül)."""
    if seconds is None:
        return ""
    if seconds < 60:
        return f"{seconds:.1f} sn".replace(".", ",")
    m, s = divmod(int(round(seconds)), 60)
    return f"{m} dk {s:02d} sn"


def model_display(model: str | None, routed: str | None = None, requested: str | None = None) -> str:
    """'auto → qwen3.8-flash-next' gibi yönlendirmeyi de gösteren model adı."""
    shown = model or requested or ""
    if routed and requested and routed != requested:
        return f"{requested} → {routed}"
    return shown


# ---- kod / diff görünümleri ---------------------------------------------------


class CodeView(QPlainTextEdit):
    def __init__(self, text: str = "", max_lines: int = 18, parent=None, auto_height: bool = True):
        super().__init__(parent)
        self.setObjectName("CodeView")
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setFont(theme.code_font(9))
        self.max_lines = max_lines
        self.auto_height = auto_height
        self.setPlainText(text)
        self._fit()

    def setPlainText(self, text: str) -> None:  # noqa: N802 (Qt adı)
        super().setPlainText(text)
        self._fit()

    def append_raw(self, text: str) -> None:
        cur = self.textCursor()
        cur.movePosition(QTextCursor.End)
        cur.insertText(text)
        self._fit()
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _fit(self) -> None:
        if not self.auto_height:
            return
        overflow = self.blockCount() > self.max_lines
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if overflow else Qt.ScrollBarAlwaysOff)
        lines = max(1, min(self.blockCount(), self.max_lines))
        lh = self.fontMetrics().lineSpacing()
        self.setFixedHeight(int(lines * lh + 24 + (14 if overflow else 0)))


class DiffView(CodeView):
    def __init__(self, diff: str, max_lines: int = 22, parent=None, auto_height: bool = True):
        super().__init__("", max_lines, parent, auto_height)
        self.setObjectName("DiffView")
        self.set_diff(diff)

    def set_diff(self, diff: str) -> None:
        lines = [ln for ln in diff.splitlines() if not ln.startswith(("--- ", "+++ "))]
        self.setPlainText("\n".join(lines) or "(fark yok)")
        p = theme.current()
        block = self.document().firstBlock()
        while block.isValid():
            t = block.text()
            fmt = QTextBlockFormat()
            if t.startswith("+"):
                fmt.setBackground(QColor(p.add_bg))
            elif t.startswith("-"):
                fmt.setBackground(QColor(p.del_bg))
            elif t.startswith("@@"):
                fmt.setForeground(QColor(p.hunk))
            else:
                block = block.next()
                continue
            cur = QTextCursor(block)
            cur.setBlockFormat(fmt)
            block = block.next()


# ---- akış kabı -------------------------------------------------------------------------


# F5 #11 sade görünüm: biten (başarılı) araç kartları ve düşünme blokları gizlenir; çalışan, onay bekleyen ve
# hatalı kartlar her zaman görünür. Uygulama genelinde tek bayrak (ayar `simple_view`).
VIEW = {"simple": False}


def set_simple_view(on: bool, root: QWidget | None = None) -> None:
    VIEW["simple"] = bool(on)
    if root is not None:
        for w in root.findChildren(AssistantMessageWidget):
            w.apply_view()


class Transcript(QScrollArea):
    """Ortalanmış, en fazla COLUMN_WIDTH genişliğinde mesaj sütunu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("TranscriptHost")
        hl = QHBoxLayout(host)
        hl.setContentsMargins(24, 20, 24, 28)
        self.col = QWidget()
        self.col.setMaximumWidth(COLUMN_WIDTH)
        self.lay = QVBoxLayout(self.col)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(18)
        self.lay.addStretch(1)
        self._host_lay = hl
        hl.addStretch(1)
        hl.addWidget(self.col, 100)
        hl.addStretch(1)
        self.setWidget(host)
        self._stick = True
        sb = self.verticalScrollBar()
        sb.rangeChanged.connect(self._on_range)
        sb.valueChanged.connect(self._on_value)

    def set_compact(self, on: bool) -> None:
        """F5 #12 sıkışık görünüm: mesajlar arası boşluk ve kenar payı azalır."""
        self.lay.setSpacing(10 if on else 18)
        self._host_lay.setContentsMargins(*((16, 10, 16, 14) if on else (24, 20, 24, 28)))

    def _on_range(self, _min: int, maximum: int) -> None:
        if self._stick:
            self.verticalScrollBar().setValue(maximum)

    def _on_value(self, value: int) -> None:
        self._stick = value >= self.verticalScrollBar().maximum() - 48

    def add(self, w: QWidget) -> QWidget:
        self.lay.insertWidget(self.lay.count() - 1, w)
        return w

    def clear(self) -> None:
        while self.lay.count() > 1:
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().hide()          # silinmeyi beklerken ekranda kalmasın
                item.widget().deleteLater()
        self._stick = True

    def scroll_to_bottom(self) -> None:
        self._stick = True
        QTimer.singleShot(0, self, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()))


# ---- mesajlar ---------------------------------------------------------------------------


class UserMessageWidget(QWidget):
    edit_requested = Signal(int, str)
    rewind_requested = Signal(int, str)          # F6/E1: bu mesajdan öncesine geri sar

    def __init__(self, text: str, message_id: int | None = None, parent=None, attachments=None):
        super().__init__(parent)
        self.message_id = message_id
        self.text = text
        self.attachments = list(attachments or [])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        row = QHBoxLayout()
        row.addStretch(1)
        bubble = QFrame()
        bubble.setObjectName("UserBubble")
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(14, 10, 14, 10)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setTextFormat(Qt.PlainText)
        body.setMaximumWidth(int(COLUMN_WIDTH * 0.82))
        bl.addWidget(body)
        row.addWidget(bubble)
        bubble.setVisible(bool(text.strip()))       # yalnız ek gönderildiyse balon gizli
        lay.addLayout(row)
        if self.attachments:
            from .attachments import AttachmentStrip

            lay.addWidget(AttachmentStrip(self.attachments))
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.copy_btn = _retain(icon_button("copy", "Kopyala", 14))
        self.copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.text))
        self.edit_btn = _retain(icon_button("pencil", "Düzenle ve yeniden gönder", 14))
        self.edit_btn.clicked.connect(
            lambda: self.edit_requested.emit(self.message_id or 0, self.text))
        self.rewind_btn = _retain(icon_button("undo", "Buraya geri sar: bu mesaj ve sonrası silinir, o turlardaki "
                                                      "dosya değişiklikleri geri alınır (önce onay sorulur)", 14))
        self.rewind_btn.clicked.connect(lambda: self.rewind_requested.emit(self.message_id or 0, self.text))
        for b in (self.rewind_btn, self.edit_btn, self.copy_btn):
            b.setVisible(False)
            actions.addWidget(b)
        lay.addLayout(actions)

    def enterEvent(self, e) -> None:
        self.copy_btn.setVisible(True)
        self.edit_btn.setVisible(self.message_id is not None)
        self.rewind_btn.setVisible(self.message_id is not None)
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self.copy_btn.setVisible(False)
        self.edit_btn.setVisible(False)
        self.rewind_btn.setVisible(False)
        super().leaveEvent(e)


class ThinkingBlock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.toggle = QToolButton()
        self.toggle.setProperty("variant", "chip")
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setIcon(icons.icon("bulb", size=14))
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.clicked.connect(self._flip)
        lay.addWidget(self.toggle, 0, Qt.AlignLeft)
        self.box = QFrame()
        self.box.setObjectName("ThinkingBox")
        bl = QVBoxLayout(self.box)
        bl.setContentsMargins(12, 2, 4, 2)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setProperty("role", "dim")
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text.setTextFormat(Qt.PlainText)
        bl.addWidget(self.text)
        self.box.setVisible(False)
        lay.addWidget(self.box)
        self._raw = ""
        self._live = True
        self._update_title()

    def _flip(self) -> None:
        self.box.setVisible(not self.box.isVisible())
        self._update_title()

    def _update_title(self) -> None:
        arrow = "▾" if self.box.isVisible() else "▸"
        label = "Düşünüyor…" if self._live else "Düşünce süreci"
        self.toggle.setText(f"{label}  {arrow}")

    def append(self, text: str) -> None:
        self._raw += text
        self.text.setText(self._raw[-6000:])

    def set_text(self, text: str) -> None:
        self._raw = text
        self.text.setText(text[-20000:])

    def finish(self) -> None:
        self._live = False
        self._update_title()


class AssistantMessageWidget(QWidget):
    # A5: kullanıcı yanıtı kötü işaretledi → (gerçek model). Auto Pro kalite puanına işlenir.
    feedback_bad = Signal(str, int)

    def __init__(self, model: str = "", agentic: bool = False, parent=None):
        super().__init__(parent)
        self.agentic = agentic
        self._raw = ""
        self.api_model = ""             # yanıtı yazan gerçek model (yoksa 👎 gösterilmez)
        self.msg_id = 0
        self._marked_bad = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(6)
        logo = QLabel()
        logo.setPixmap(brand.pixmap(16))
        head.addWidget(logo)
        name = QLabel("EVREN")
        name.setStyleSheet("font-weight: 600;")
        head.addWidget(name)
        self.model_label = faint_label(model)
        head.addWidget(self.model_label)
        head.addStretch(1)
        self.copy_btn = _retain(icon_button("copy", "Yanıtı kopyala", 14))
        self.copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self._raw))
        self.copy_btn.setVisible(False)
        head.addWidget(self.copy_btn)
        self.bad_btn = _retain(icon_button("thumbs-down", "Kötü yanıt: bu motor Auto Pro sıralamasında geri "
                                           "düşebilir (yalnız sıralamayı etkiler)", 14))
        self.bad_btn.clicked.connect(self._mark_bad)
        self.bad_btn.setVisible(False)
        head.addWidget(self.bad_btn)
        lay.addLayout(head)

        self.thinking = ThinkingBlock()
        self.thinking.setVisible(False)
        lay.addWidget(self.thinking)
        self.body = MarkdownView()
        self.body.setVisible(False)
        lay.addWidget(self.body)
        # Bekleme satırı: canlı yıldız (model çalışırken döner) + durum metni
        self.status_row = QWidget()
        sr = QHBoxLayout(self.status_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(8)
        self.busy = brand.BusyStar(14)
        self.busy.setVisible(False)
        sr.addWidget(self.busy)
        self.status = faint_label("")
        sr.addWidget(self.status, 1)
        lay.addWidget(self.status_row)
        self.tools = QVBoxLayout()
        self.tools.setSpacing(6)
        lay.addLayout(self.tools)
        self._has_thinking = False
        self.tool_summary = faint_label("")          # sade görünümde gizlenen adım sayısı
        self.tool_summary.setVisible(False)
        lay.addWidget(self.tool_summary)
        # Kalıcı alt bilgi: "glm-5.3 · 8,4 sn"
        self.footer = faint_label("")
        self.footer.setVisible(False)
        lay.addWidget(self.footer)

        self._model = model
        self._t0: float | None = None
        self._clock = QTimer(self)
        self._clock.setInterval(500)
        self._clock.timeout.connect(self._tick_clock)

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(70)
        self._render_timer.timeout.connect(self._render)
        self._dots = 0
        self._wait_timer = QTimer(self)
        self._wait_timer.setInterval(400)
        self._wait_timer.timeout.connect(self._tick)

    def enterEvent(self, e) -> None:
        self.copy_btn.setVisible(bool(self._raw))
        self.bad_btn.setVisible(bool(self._raw and self.api_model) or self._marked_bad)
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self.copy_btn.setVisible(False)
        self.bad_btn.setVisible(self._marked_bad)
        super().leaveEvent(e)

    def set_marked_bad(self) -> None:
        """Kayıtlı işareti geri yükler (oturum yeniden açılınca aynı yanıt ikinci kez işaretlenmesin)."""
        self._marked_bad = True
        self.bad_btn.setEnabled(False)
        self.bad_btn.setToolTip("Kötü yanıt olarak işaretlendi.")
        self.bad_btn.setVisible(True)

    def _mark_bad(self, _=None) -> None:
        """Bir kez işaretlenir (geri alınamaz; tekrar tıklamak puanı ikinci kez düşürmez)."""
        if self._marked_bad or not self.api_model:
            return
        self._marked_bad = True
        self.bad_btn.setEnabled(False)
        self.bad_btn.setToolTip(f"Kötü yanıt olarak işaretlendi ({self.api_model}). Auto Pro bu motoru "
                                "bugün sıralamada geri alabilir.")
        self.bad_btn.setVisible(True)
        self.feedback_bad.emit(self.api_model, int(self.msg_id or 0))

    # -- canlı süre --

    def start_clock(self, model: str) -> None:
        import time

        self._model = model
        self._t0 = time.monotonic()
        self._tick_clock()
        self._clock.start()

    def _tick_clock(self) -> None:
        import time

        if self._t0 is None:
            return
        elapsed = time.monotonic() - self._t0
        self.model_label.setText(f"{self._model}  ·  {format_duration(elapsed)}")

    def stop_clock(self) -> float | None:
        import time

        self._clock.stop()
        if self._t0 is None:
            return None
        elapsed = time.monotonic() - self._t0
        self._t0 = None
        return elapsed

    def set_footer(self, text: str) -> None:
        self.footer.setText(text)
        self.footer.setVisible(bool(text))

    # -- canlı akış --

    def start_waiting(self, text: str = "Yanıt bekleniyor") -> None:
        self._wait_text = text
        self._dots = 0
        self._tick()
        self.busy.setVisible(True)
        self._wait_timer.start()

    def _tick(self) -> None:
        self._dots = (self._dots + 1) % 4
        self.status.setText(getattr(self, "_wait_text", "") + "." * self._dots)
        self.status.setVisible(True)

    def stop_waiting(self) -> None:
        self._wait_timer.stop()
        self.busy.setVisible(False)
        self.status.setVisible(False)

    def append_text(self, delta: str) -> None:
        self._raw += delta
        if not self._render_timer.isActive():
            self._render_timer.start()

    def append_reasoning(self, delta: str) -> None:
        self._has_thinking = True
        self.thinking.setVisible(not VIEW["simple"])
        self.thinking.append(delta)

    def _render(self) -> None:
        shown = textproto.display_text(self._raw) if self.agentic else self._raw
        if shown.strip():
            self.stop_waiting()
            self.body.setVisible(True)
            self.body.set_markdown(shown)

    # -- tamamlanmış --

    def finalize(self, content: str, reasoning: str | None = None,
                 finish_reason: str | None = None, model: str | None = None,
                 duration: float | None = None) -> None:
        self._render_timer.stop()
        self.stop_waiting()
        live = self.stop_clock()
        if duration is None:
            duration = live
        self._raw = content or ""
        if model:
            self._model = model
            self.model_label.setText(model)
        if duration is not None and (model or self._model):
            self.set_footer(f"{model or self._model}  ·  {format_duration(duration)}")
        if reasoning:
            self._has_thinking = True
            self.thinking.setVisible(not VIEW["simple"])
            self.thinking.set_text(reasoning)
        self.thinking.finish()
        if self._raw.strip():
            self.body.setVisible(True)
            self.body.set_markdown(self._raw)
        else:
            self.body.setVisible(False)
        note = ""
        if finish_reason == "length":
            note = "Yanıt uzunluk sınırında kesildi (finish_reason: length)."
        elif finish_reason == "cancelled_by_user":
            note = "Yanıt durduruldu."
        if note:
            self.status.setText(note)
            self.status.setVisible(True)

    def has_visible_content(self) -> bool:
        return bool(self._raw.strip()) or self._has_thinking or self.tools.count() > 0

    def add_tool(self, call_id: str, name: str, args: dict[str, Any]) -> "ToolCallWidget":
        w = ToolCallWidget(call_id, name, args)
        w._owner = self
        self.tools.addWidget(w)
        return w

    def apply_view(self) -> None:
        """Sade görünüm bayrağını uygular (araç kartı bitince ve bayrak değişince çağrılır)."""
        simple = VIEW["simple"]
        hidden = 0
        for i in range(self.tools.count()):
            w = self.tools.itemAt(i).widget()
            if isinstance(w, ToolCallWidget):
                hide = simple and w.finished and w.property("state") == "ok"
                w.setVisible(not hide)
                hidden += hide
        self.tool_summary.setText(f"{hidden} araç adımı gizli (sade görünüm — Ctrl+Shift+H ile ayrıntı)")
        self.tool_summary.setVisible(hidden > 0)
        self.thinking.setVisible(not simple and getattr(self, "_has_thinking", False))


# ---- araç kartı ve onay ----------------------------------------------------------------------


class ApprovalWidget(QFrame):
    decided = Signal(str)

    def __init__(self, request: Any, parent=None):
        super().__init__(parent)
        self.setObjectName("ApprovalBox")
        self.request = request
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        title = QLabel(request.title)
        title.setStyleSheet("font-weight: 600;")
        title.setWordWrap(True)
        lay.addWidget(title)
        reason = getattr(request, "reason", "")
        if reason:
            why = QLabel(f"Neden soruluyor: {reason}")
            why.setWordWrap(True)
            why.setStyleSheet(f"color: {theme.current().warning};")
            lay.addWidget(why)
        if request.kind == "write" and request.change is not None:
            lay.addWidget(DiffView(request.detail, max_lines=24))
        elif request.kind == "read":
            lay.addWidget(faint_label(f"Dosya: {request.detail} — içeriği EVREN API'sine gönderilecek.", "dim"))
        elif request.kind == "install":
            lay.addWidget(CodeView(f"PS> {request.detail}", max_lines=4))
            lay.addWidget(faint_label("Program bilgisayara kurulur (winget/npm, yalnız bilinen listeden). "
                                      "Ayarlar > Eksik program kurulumu: Otomatik yapılırsa sorulmaz."))
        else:
            lay.addWidget(CodeView(f"PS> {request.detail}", max_lines=6))
            lay.addWidget(faint_label("Komut proje klasöründe çalışır. Çıktısı modele gönderilir."))
        self.feedback = QLineEdit()
        self.feedback.setPlaceholderText("İsteğe bağlı not: reddediyorsanız neyi farklı yapmalı?")
        lay.addWidget(self.feedback)
        row = QHBoxLayout()
        row.setSpacing(8)
        allow = QPushButton("Kur" if request.kind == "install" else "Onayla")
        allow.setProperty("variant", "primary")
        allow.setIcon(icons.icon("check", theme.current().on_accent, 16))
        allow.clicked.connect(lambda: self._decide("allow"))
        if request.kind == "write":
            session_text = "Bu oturumda tüm düzenlemelere izin ver"
        elif request.kind == "read":
            session_text = "Bu oturumda gizli dosya okumalarına izin ver"
        elif request.kind == "install":
            session_text = "Bu oturumda program kurulumlarına izin ver"
        else:
            session_text = f"“{request.prefix}” komutlarına bu oturumda izin ver"
        always = QPushButton(session_text)
        always.setProperty("variant", "ghost")
        always.clicked.connect(lambda: self._decide("allow_session"))
        deny = QPushButton("Reddet")
        deny.setProperty("variant", "danger")
        deny.clicked.connect(lambda: self._decide("deny"))
        row.addWidget(allow)
        row.addWidget(always)
        row.addStretch(1)
        row.addWidget(deny)
        lay.addLayout(row)
        allow.setFocus()

    def _decide(self, decision: str) -> None:
        self.request.resolve(decision, self.feedback.text())
        self.decided.emit(decision)


class ToolCallWidget(QFrame):
    _owner = None

    def _notify_owner(self) -> None:
        if self._owner is not None:
            self._owner.apply_view()

    def __init__(self, call_id: str, name: str, args: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setObjectName("ToolCard")
        self.call_id = call_id
        self.name = name
        self.args = args
        self.finished = False
        self._output_view: CodeView | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.icon = QLabel()
        self.icon.setPixmap(icons.pixmap(TOOL_ICONS.get(name, "dot"), None, 15))
        head.addWidget(self.icon)
        self.title = QLabel(self._initial_title())
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.title.setMinimumWidth(100)
        self.title.setWordWrap(False)
        head.addWidget(self.title, 1)
        self.state = faint_label("")
        head.addWidget(self.state)
        self.expand = icon_button("chevron-right", "Ayrıntılar", 14)
        self.expand.clicked.connect(self.toggle_details)
        self.expand.setVisible(False)
        head.addWidget(self.expand)
        lay.addLayout(head)
        self.details = QWidget()
        self.details_lay = QVBoxLayout(self.details)
        self.details_lay.setContentsMargins(0, 0, 0, 2)
        self.details_lay.setSpacing(6)
        self.details.setVisible(False)
        lay.addWidget(self.details)
        self.approval_host = QVBoxLayout()
        lay.addLayout(self.approval_host)
        self.set_state("queued")

    def _initial_title(self) -> str:
        a = self.args
        return {
            "list_files": f"Klasör: {a.get('path') or '.'}",
            "read_file": f"Oku: {a.get('path', '')}",
            "read_table": f"Tablo: {a.get('path', '')}" + (f" · {a['sheet']}" if a.get("sheet") else ""),
            "web_fetch": f"Web: {a.get('url', '')}",
            "read_skill": f"Skill: {a.get('name', '')}" + (f" · {a['path']}" if a.get("path") else ""),
            "convert_model": f"Model dönüştür: {a.get('path', '')}",
            "godot_export": f"Godot dışa aktar: {a.get('target') or 'EXE + PWA'}",
            "polyhaven_search": f"Poly Haven: \"{a.get('query', '')}\" ara",
            "polyhaven_download": f"Poly Haven: {a.get('asset_id', '')} indir",
            "search_files": f"Ara: “{a.get('pattern', '')}”",
            "find_files": f"Bul: {a.get('pattern', '')}",
            "write_file": f"Yaz: {a.get('path', '')}",
            "edit_file": f"Düzenle: {a.get('path', '')}",
            "run_command": f"Komut: {a.get('command', '')}",
            "update_todos": "Görev listesi",
        }.get(self.name, self.name)

    def set_state(self, state: str, text: str = "") -> None:
        p = theme.current()
        self.setProperty("state", "pending" if state == "approval" else state)
        self.style().unpolish(self)
        self.style().polish(self)
        labels = {"queued": "sırada", "running": "çalışıyor…", "approval": "onay bekliyor",
                  "ok": "", "error": "hata", "denied": "reddedildi"}
        self.state.setText(text or labels.get(state, ""))
        color = {"ok": p.success, "error": p.danger, "denied": p.warning}.get(state)
        if color:
            self.state.setStyleSheet(f"color: {color};")
            mark = {"ok": "check", "error": "x", "denied": "x"}[state]
            self.icon.setPixmap(icons.pixmap(mark, color, 15))
        else:
            self.state.setStyleSheet("")

    def toggle_details(self, force: bool | None = None) -> None:
        show = (not self.details.isVisible()) if force is None else force
        self.details.setVisible(show)
        self.expand.setIcon(icons.icon("chevron-down" if show else "chevron-right", size=14))

    def set_running(self, title: str | None = None) -> None:
        if title:
            self.title.setText(title)
        self.set_state("running")
        if self.name == "run_command":
            self._ensure_output()
            self.toggle_details(True)

    def _ensure_output(self) -> CodeView:
        if self._output_view is None:
            self._output_view = CodeView("", max_lines=14)
            self.details_lay.addWidget(self._output_view)
            self.expand.setVisible(True)
        return self._output_view

    def append_output(self, chunk: str) -> None:
        self._ensure_output().append_raw(chunk)

    def show_approval(self, request: Any, on_decided: Callable[[str], None] | None = None) -> None:
        self.set_state("approval")
        box = ApprovalWidget(request)

        def done(decision: str) -> None:
            box.setVisible(False)
            box.deleteLater()
            if decision == "deny":
                self.set_state("denied")
            else:
                self.set_state("running", "onaylandı")
            if on_decided:
                on_decided(decision)

        box.decided.connect(done)
        self.approval_host.addWidget(box)

    def set_result(self, ok: bool, summary: str, meta: dict[str, Any]) -> None:
        self.finished = True
        QTimer.singleShot(0, self, self._notify_owner)       # durum özelliği aşağıda ayarlandıktan sonra
        if summary:
            self.title.setText(summary)
            self.title.setToolTip(summary)
        if meta.get("denied"):
            self.set_state("denied")
        else:
            self.set_state("ok" if ok else "error")
        # Ayrıntılar: diff, komut çıktısı, okuma çıktısı veya hata
        for i in reversed(range(self.details_lay.count())):
            w = self.details_lay.itemAt(i).widget()
            if w is not None and w is not self._output_view:
                w.deleteLater()
        if meta.get("diff"):
            self.details_lay.addWidget(DiffView(meta["diff"]))
            self.expand.setVisible(True)
        elif self.name == "run_command":
            out = meta.get("output")
            view = self._ensure_output()
            if out is not None and not view.toPlainText().strip():
                view.setPlainText(out.strip() or "(çıktı yok)")
            code = meta.get("exit_code")
            if code is not None:
                self.state.setText(f"çıkış {code}" + (f" · {meta.get('duration')} sn" if meta.get("duration") else ""))
        if meta.get("auto_approved") and not meta.get("denied"):
            # Otomatik / düzenlemeleri kabul modunda onaysız çalıştı
            self.state.setText(("otomatik · " + self.state.text()).rstrip(" ·"))
            if meta.get("auto_reason"):
                self.state.setToolTip(meta["auto_reason"])
        elif meta.get("todos"):
            lines = []
            for t in meta["todos"]:
                mark = {"completed": "✓", "in_progress": "◐"}.get(t["status"], "○")
                lines.append(f"{mark} {t['content']}")
            self.details_lay.addWidget(CodeView("\n".join(lines), max_lines=12))
            self.expand.setVisible(True)
        elif meta.get("output"):
            self.details_lay.addWidget(CodeView(meta["output"], max_lines=14))
            self.expand.setVisible(True)
        if not ok and meta.get("error_text"):
            lab = faint_label(meta["error_text"], "dim")
            lab.setWordWrap(True)
            self.details_lay.addWidget(lab)
            self.expand.setVisible(True)


# ---- bilgi ve hata kartları ---------------------------------------------------------------------


class NoteWidget(QWidget):
    def __init__(self, text: str, icon_name: str = "dot", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, theme.current().text_faint, 14))
        lay.addWidget(ic)
        lab = faint_label(text)
        lab.setWordWrap(True)
        lay.addWidget(lab)
        lay.addStretch(1)


class InstallCard(QFrame):
    """Ortam denetimi kartı: eksik programlar. Manuel modda Kur / Şimdi değil düğmeleri.

    Kullanıcı kararı (2026-10-17): Ayarlar > "Eksik program kurulumu" Manuel ise
    kurulum bu kartla onaylanır; Otomatik ise kart yalnız ilerlemeyi gösterir.
    """

    install_requested = Signal()
    dismissed = Signal()

    def __init__(self, title: str, lines: list[str], ask: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("ApprovalBox")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(6)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("spark", theme.current().accent, 16))
        head.addWidget(ic)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: 600;")
        self.title.setWordWrap(True)
        head.addWidget(self.title, 1)
        lay.addLayout(head)
        self.body = QLabel("\n".join(lines))
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.body)
        self.buttons: list[QPushButton] = []
        if ask:
            row = QHBoxLayout()
            row.setSpacing(8)
            self.install_btn = QPushButton("Kur")
            self.install_btn.setProperty("variant", "primary")
            self.install_btn.setIcon(icons.icon("check", theme.current().on_accent, 16))
            self.install_btn.clicked.connect(self._install)
            later = QPushButton("Şimdi değil")
            later.setProperty("variant", "ghost")
            later.clicked.connect(self._dismiss)
            row.addWidget(self.install_btn)
            row.addWidget(later)
            row.addStretch(1)
            lay.addLayout(row)
            self.buttons = [self.install_btn, later]

    def _lock(self) -> None:
        for b in self.buttons:
            b.setEnabled(False)

    def _install(self) -> None:
        self._lock()
        self.install_requested.emit()

    def _dismiss(self) -> None:
        self._lock()
        self.append_line("Kurulum ertelendi. Ajan gerekirse yine sorar; Ayarlar'dan Otomatik yapılabilir.")
        self.dismissed.emit()

    def set_title(self, text: str) -> None:
        self.title.setText(text)

    def append_line(self, text: str) -> None:
        self.body.setText(self.body.text() + "\n" + text)


class ActionCard(QFrame):
    """Başlık + satırlar + eylem düğmeleri olan bilgi kartı (tur özeti, kapsam, plan).

    actions: [(etiket, geri çağrı, "primary"|"ghost"|"danger"|"")]. Bir düğmeye
    basılınca `disable_on_click` ise tüm düğmeler kilitlenir (çift tıklama olmasın).
    """

    def __init__(self, title: str, lines: list[str], actions=None, icon_name: str = "spark",
                 warn: bool = False, disable_on_click: bool = True, parent=None):
        super().__init__(parent)
        self.setObjectName("ApprovalBox" if warn else "ToolCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(6)
        head = QHBoxLayout()
        ic = QLabel()
        p = theme.current()
        ic.setPixmap(icons.pixmap(icon_name, p.warning if warn else p.accent, 16))
        head.addWidget(ic)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: 600;")
        self.title.setWordWrap(True)
        head.addWidget(self.title, 1)
        lay.addLayout(head)
        self.body = QLabel("\n".join(lines))
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body.setVisible(bool(lines))
        lay.addWidget(self.body)
        self.buttons: dict[str, QPushButton] = {}
        if actions:
            row = QHBoxLayout()
            row.setSpacing(8)
            for label, cb, variant in actions:
                b = QPushButton(label)
                if variant:
                    b.setProperty("variant", variant)
                b.clicked.connect(lambda _=False, f=cb: self._clicked(f, disable_on_click))
                row.addWidget(b)
                self.buttons[label] = b
            row.addStretch(1)
            lay.addLayout(row)

    def _clicked(self, cb, lock: bool) -> None:
        if lock:
            self.lock()
        cb()

    def lock(self) -> None:
        for b in self.buttons.values():
            b.setEnabled(False)

    def set_title(self, text: str) -> None:
        self.title.setText(text)

    def set_lines(self, lines: list[str]) -> None:
        self.body.setText("\n".join(lines))
        self.body.setVisible(bool(lines))

    def append_line(self, text: str) -> None:
        self.body.setVisible(True)
        self.body.setText((self.body.text() + "\n" if self.body.text() else "") + text)


class ChoiceCard(QFrame):
    """Öneri/seçim kartı (vurgu çerçeveli): başlık, açıklama ve düğmeler. Bir düğmeye basılınca
    düğmeler kilitlenir ve seçilen yazılır (çift tıklama olmaz)."""

    def __init__(self, title: str, text: str, actions: list[tuple[str, Callable[[], None]]],
                 icon_name: str = "list", parent=None):
        super().__init__(parent)
        self.setObjectName("PlanCard")
        p = theme.current()
        self.setStyleSheet(f"QFrame#PlanCard {{ background: {p.surface}; border: 1px solid {p.accent};"
                           f" border-radius: 12px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, p.accent, 18))
        head.addWidget(ic)
        t = QLabel(f"<b>{title}</b>")
        t.setWordWrap(True)
        head.addWidget(t, 1)
        lay.addLayout(head)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setProperty("role", "dim")
        lay.addWidget(body)
        row = QHBoxLayout()
        row.addStretch(1)
        self.buttons: list[QPushButton] = []
        for i, (label, cb) in enumerate(actions):
            b = QPushButton(label)
            if i == 0:
                b.setProperty("variant", "primary")
            b.clicked.connect(lambda _=None, c=cb, lb=label: self._choose(lb, c))
            row.addWidget(b)
            self.buttons.append(b)
        lay.addLayout(row)
        self.result = QLabel("")
        self.result.setProperty("role", "dim")
        self.result.setVisible(False)
        lay.addWidget(self.result)

    def _choose(self, label: str, cb: Callable[[], None]) -> None:
        for b in self.buttons:
            b.setEnabled(False)
            b.setVisible(False)
        self.result.setText("✓ " + label)
        self.result.setVisible(True)
        cb()


class ErrorCard(QFrame):
    def __init__(self, title: str, lines: list[str],
                 actions: list[tuple[str, Callable[[], None]]] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("ErrorCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("alert", theme.current().danger, 16))
        head.addWidget(ic)
        t = QLabel(title)
        t.setStyleSheet("font-weight: 600;")
        t.setWordWrap(True)
        head.addWidget(t, 1)
        lay.addLayout(head)
        self.body = QLabel("\n".join(lines))
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.body)
        if actions:
            row = QHBoxLayout()
            for label, cb in actions:
                b = QPushButton(label)
                b.clicked.connect(cb)
                row.addWidget(b)
            row.addStretch(1)
            lay.addLayout(row)

    def append_line(self, text: str) -> None:
        self.body.setText(self.body.text() + "\n" + text)
