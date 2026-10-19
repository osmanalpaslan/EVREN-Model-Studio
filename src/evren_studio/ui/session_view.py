"""Oturum görünümü: başlık çubuğu, karşılama ekranı, akış ve yazma kutusu.

Ajan arka plan iş parçacığında çalışır; `AgentBridge` olayları Qt
sinyalleriyle ana iş parçacığına taşır. Onay isteyen her işlem ilgili araç
kartının içinde onay kutusu olarak gösterilir.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import time

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..agent import environment, prompts, scope
from ..agent.compaction import MAX_AUTO_RESUMES, CompactPolicy, needs_compaction, summarize
from ..agent.permissions import MODES, SessionPermissions, normalize_mode
from ..agent.runner import (
    AgentEvents,
    AgentRunner,
    ApprovalRequest,
    ToolCall,
    ToolResult,
    estimate_tokens,
    to_api_messages,
)
from ..agent import router
from ..agent.tools import FileChange, ToolBox, ToolError, Workspace
from ..api.client import CancelToken
from ..api.providers import PROVIDERS, estimate_cost, price_hint
from ..budget import current_state
from ..api.errors import ApiError, ErrorKind
from . import brand, icons, theme
from .attachments import Attachment, attachment_from_path, clipboard_image_attachment
from .composer import MODE_COMMANDS, SLASH_COMMANDS, Composer
from .usage_popup import UsageSnapshot
from .transcript import (
    COLUMN_WIDTH,
    AssistantMessageWidget,
    ActionCard,
    ErrorCard,
    InstallCard,
    NoteWidget,
    ToolCallWidget,
    Transcript,
    UserMessageWidget,
    faint_label,
    format_duration,
    icon_button,
    model_display,
)
from .workers import Task

HISTORY_WINDOW = 40          # uzun oturumda ilk çizilen son mesaj sayısı
ATTACH_OPEN = "<ekli_dosyalar>"
ATTACH_CLOSE = "</ekli_dosyalar>"
MENTION_RE = re.compile(r"(?<!\S)@([^\s]+)")
MAX_ATTACH_BYTES = 100 * 1024


def file_block(att: Attachment, ws: str | None) -> tuple[str, str]:
    """Ek dosyanın modele gidecek bloğu: (başlık etiketi, blok). Görseller hariç."""
    p = Path(att.path)
    label = att.name
    if ws:
        try:
            label = p.resolve().relative_to(Path(ws).resolve()).as_posix()
        except (ValueError, OSError):
            pass
    reason = ""
    content = ""
    try:
        size = p.stat().st_size
        if size > MAX_ATTACH_BYTES:
            reason = f"{size // 1024} KB, sınır {MAX_ATTACH_BYTES // 1024} KB"
        else:
            raw = p.read_bytes()
            if b"\x00" in raw[:8192]:
                reason = "ikili dosya (metin değil)"
            else:
                try:
                    content = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    content = raw.decode("cp1254", errors="replace")
    except OSError as exc:
        reason = f"okunamadı ({type(exc).__name__})"
    if reason:
        return label, f"### {label}\n(İçerik eklenmedi: {reason}. Dosya yolu: {p})"
    return label, f"### {label}\n```{p.suffix.lstrip('.')}\n{content}\n```"


def append_blocks(content: str, blocks: list[str]) -> str:
    if not blocks:
        return content
    if ATTACH_CLOSE in content:
        return content.replace(ATTACH_CLOSE, "\n\n".join(blocks) + "\n" + ATTACH_CLOSE, 1)
    return (content + "\n\n" if content else "") + ATTACH_OPEN + "\n" + "\n\n".join(blocks) + "\n" + ATTACH_CLOSE


def split_attachments(content: str) -> tuple[str, list[str]]:
    """Kayıtlı kullanıcı mesajından görünen metni ve ekli dosya adlarını ayırır."""
    if ATTACH_OPEN not in content:
        return content, []
    text, _, rest = content.partition("\n\n" + ATTACH_OPEN)
    names = re.findall(r"^### (.+)$", rest, re.M)
    return text, names


class AgentBridge(QObject, AgentEvents):
    """AgentEvents → Qt sinyalleri (iş parçacığından ana iş parçacığına)."""

    sig_text = Signal(str)
    sig_reasoning = Signal(str)
    sig_step = Signal(int)
    sig_message = Signal(object)
    sig_tool_started = Signal(object, str)
    sig_tool_output = Signal(object, str)
    sig_tool_finished = Signal(object, object)
    sig_approval = Signal(object)
    sig_todos = Signal(object)
    sig_file = Signal(object, object)
    sig_protocol = Signal(str, str)
    sig_status = Signal(str)

    def __init__(self):
        QObject.__init__(self)

    def text_delta(self, text: str) -> None: self.sig_text.emit(text)
    def reasoning_delta(self, text: str) -> None: self.sig_reasoning.emit(text)
    def step_started(self, step: int) -> None: self.sig_step.emit(step)
    def message_saved(self, message: dict) -> None: self.sig_message.emit(message)
    def tool_started(self, call: ToolCall, title: str) -> None: self.sig_tool_started.emit(call, title)
    def tool_output(self, call: ToolCall, chunk: str) -> None: self.sig_tool_output.emit(call, chunk)
    def tool_finished(self, call: ToolCall, result: ToolResult) -> None: self.sig_tool_finished.emit(call, result)
    def approval_needed(self, request: ApprovalRequest) -> None: self.sig_approval.emit(request)
    def todos_changed(self, todos: list) -> None: self.sig_todos.emit(todos)
    def file_changed(self, change_id, change: FileChange) -> None: self.sig_file.emit(change_id, change)
    def protocol_changed(self, protocol: str, reason: str) -> None: self.sig_protocol.emit(protocol, reason)
    def status(self, text: str) -> None: self.sig_status.emit(text)


# ---- karşılama ekranı ------------------------------------------------------------


class WelcomeView(QWidget):
    suggestion = Signal(str)
    workspace_changed = Signal(object)    # str | None
    open_settings = Signal()

    # (başlık, kısa açıklama, istem)
    AGENT_SUGGESTIONS = [
        ("Projeyi tanı", "Amacı, mimariyi ve önemli dosyaları özetler",
         "Bu projeyi incele; amacını, mimarisini ve önemli dosyalarını kısaca anlat."),
        ("Testleri çalıştır", "Testleri bulur, çalıştırır ve hataları açıklar",
         "Projenin testlerini bul ve çalıştır; başarısız olanların nedenini açıkla ve düzeltme öner."),
        ("Proje hafızası (/init)", "EVREN.md oluşturur; sonraki oturumlar projeyi hatırlar", "/init"),
        ("İyileştirme planı", "Plan modunda inceler, dosyalara dokunmaz",
         "/plan Kod tabanını incele ve öncelikli iyileştirmeler için adım adım bir plan hazırla."),
    ]
    CHAT_SUGGESTIONS = [
        ("Kavram açıkla", "Örnekli, sade bir anlatım",
         "Python'da async/await nasıl çalışır? Basit bir örnekle anlat."),
        ("Metin düzenle", "Daha akıcı ve resmi bir Türkçe",
         "Aşağıdaki metni daha akıcı ve resmi bir Türkçeyle yeniden yaz:\n\n"),
        ("Kod incele", "Hataları ve iyileştirmeleri bulur",
         "Şu kodu incele ve hataları açıkla:\n\n"),
        ("Yol haritası", "Adım adım uygulanabilir plan",
         "Küçük bir masaüstü uygulaması geliştirmek için adım adım bir yol haritası hazırla."),
    ]

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.workspace: str | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 12)
        outer.addStretch(2)
        col_host = QHBoxLayout()
        col_host.addStretch(1)
        col = QWidget()
        col.setMaximumWidth(COLUMN_WIDTH - 60)
        cl = QVBoxLayout(col)
        cl.setSpacing(14)
        self.logo = QLabel()
        self.refresh_logo()
        self.logo.setAlignment(Qt.AlignCenter)
        cl.addWidget(self.logo)
        title = QLabel("Bugün ne üzerinde çalışalım?")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        cl.addWidget(title)
        self.subtitle = QLabel("")
        self.subtitle.setProperty("role", "dim")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setWordWrap(True)
        cl.addWidget(self.subtitle)

        ws_row = QHBoxLayout()
        ws_row.addStretch(1)
        self.ws_btn = QToolButton()
        self.ws_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.ws_btn.setPopupMode(QToolButton.InstantPopup)
        self.ws_btn.setIconSize(QSize(16, 16))
        self.ws_btn.setCursor(Qt.PointingHandCursor)
        self.ws_menu = QMenu(self)
        self.ws_menu.aboutToShow.connect(self._fill_menu)
        self.ws_btn.setMenu(self.ws_menu)
        ws_row.addWidget(self.ws_btn)
        ws_row.addStretch(1)
        cl.addLayout(ws_row)

        self.key_card = QFrame()
        self.key_card.setObjectName("InfoCard")
        kl = QHBoxLayout(self.key_card)
        kl.setContentsMargins(14, 10, 10, 10)
        ki = QLabel()
        ki.setPixmap(icons.pixmap("alert", theme.current().warning, 16))
        kl.addWidget(ki)
        kt = QLabel("API anahtarı tanımlı değil. Başlamak için EVREN anahtarınızı girin; "
                    "anahtar Windows Credential Manager'da saklanır.")
        kt.setWordWrap(True)
        kl.addWidget(kt, 1)
        kb = QPushButton("Anahtar gir")
        kb.setProperty("variant", "primary")
        kb.clicked.connect(self.open_settings.emit)
        kl.addWidget(kb)
        cl.addWidget(self.key_card)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        cl.addLayout(self.grid)
        col_host.addWidget(col, 10)
        col_host.addStretch(1)
        outer.addLayout(col_host)
        outer.addStretch(3)
        self.set_workspace(ctx.settings.code_workdir if ctx.settings.code_workdir and Path(ctx.settings.code_workdir).is_dir() else None)

    def refresh_logo(self) -> None:
        self.logo.setPixmap(brand.pixmap(72))

    def refresh(self) -> None:
        self.key_card.setVisible(not self.ctx.has_api_key())

    def set_workspace(self, ws: str | None) -> None:
        self.workspace = ws
        if ws:
            self.ws_btn.setIcon(icons.icon("folder", theme.current().accent, 16))
            self.ws_btn.setText(f"  {Path(ws).name}   ▾")
            self.ws_btn.setToolTip(ws)
            self.subtitle.setText(
                "Kod ajanı bu klasörde dosya okuyabilir, düzenleyebilir ve onayınızla komut "
                "çalıştırabilir. Değişiklikleri sağ paneldeki “Değişiklikler” sekmesinden geri alabilirsiniz.")
        else:
            self.ws_btn.setIcon(icons.icon("message", size=16))
            self.ws_btn.setText("  Klasörsüz sohbet   ▾")
            self.ws_btn.setToolTip("Bir proje klasörü seçerek kod ajanını etkinleştirin")
            self.subtitle.setText("Genel sohbet: dosya erişimi yoktur. Kod üzerinde çalışmak için bir "
                                  "proje klasörü seçin.")
        self._fill_suggestions()
        self.refresh()

    def _fill_suggestions(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        items = self.AGENT_SUGGESTIONS if self.workspace else self.CHAT_SUGGESTIONS
        p = theme.current()
        for i, (head, desc, prompt) in enumerate(items):
            b = QPushButton()
            b.setObjectName("SuggestionCard")
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(68)
            bl = QVBoxLayout(b)
            bl.setContentsMargins(14, 10, 14, 10)
            bl.setSpacing(2)
            t = QLabel(head)
            t.setStyleSheet(f"font-weight: 600; color: {p.text};")
            d = QLabel(desc)
            d.setProperty("role", "dim")
            for lab in (t, d):
                lab.setAttribute(Qt.WA_TransparentForMouseEvents)
                bl.addWidget(lab)
            b.clicked.connect(lambda _=False, pr=prompt: self.suggestion.emit(pr))
            self.grid.addWidget(b, i // 2, i % 2)

    def _fill_menu(self) -> None:
        self.ws_menu.clear()
        recent = [p for p in self.ctx.settings.recent_workspaces if Path(p).is_dir()]
        if recent:
            sec = self.ws_menu.addAction("Son klasörler")
            sec.setEnabled(False)
            for p in recent[:8]:
                self.ws_menu.addAction(icons.icon("folder", size=15), f"{Path(p).name}   —   {p}",
                                       lambda pp=p: self._choose(pp))
            self.ws_menu.addSeparator()
        self.ws_menu.addAction(icons.icon("plus", size=15), "Klasör seç…", self._browse)
        self.ws_menu.addAction(icons.icon("message", size=15), "Klasörsüz sohbet", lambda: self._choose(None))

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Proje klasörü seç", self.workspace or str(Path.home()))
        if d:
            self._choose(str(Path(d)))

    def _choose(self, ws: str | None) -> None:
        if ws:
            self.ctx.settings.remember_workspace(ws)
            self.ctx.save_settings()
        self.set_workspace(ws)
        self.workspace_changed.emit(ws)


# ---- oturum görünümü ------------------------------------------------------------------


class SessionView(QWidget):
    sessions_changed = Signal()
    session_opened = Signal(object)        # int | None
    page_requested = Signal(str)
    toggle_sidebar = Signal()
    toggle_panel = Signal()
    notify = Signal(str, str)              # (başlık, metin) → ana pencere Windows bildirimi

    def __init__(self, ctx, panel, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.panel = panel
        self.session_id: int | None = None
        self.workspace: str | None = None
        self.mode = normalize_mode(ctx.settings.agent_mode)
        self.model = ctx.settings.default_model
        self.running = False
        self.cancel_token: CancelToken | None = None
        self.runner: AgentRunner | None = None
        self.bridge: AgentBridge | None = None
        self.current: AssistantMessageWidget | None = None
        self.tool_widgets: dict[str, ToolCallWidget] = {}
        self.perms: dict[int, SessionPermissions] = {}
        self.edit_from: int | None = None
        self._pending_approvals: list[ApprovalRequest] = []
        self._env_checked: set[tuple] = set()       # (oturum, klasör) başına bir ortam denetimi
        self._turn_id: int | None = None            # turu başlatan kullanıcı mesajı (değişiklik kaydı)
        self._plan_turn = False                     # "önce plan": bu tur salt okunur plan turu
        self._turn_hook = None                      # proje ajanı: tur bitince (outcome, exc) çağrılır
        from .project_ui import ProjectController

        self.project = ProjectController(self)
        self.project.notify.connect(self.notify.emit)
        self._skip_plan_once = False
        # Çalışma süresi / model göstergesi
        self.run_model = ""
        self._run_t0: float | None = None
        self._run_step = 0
        self._run_activity = ""
        self._run_timer = QTimer(self)
        self._run_timer.setInterval(500)
        self._run_timer.timeout.connect(self._tick_run)
        self._auto_resumes = 0          # bu kullanıcı mesajından beri otomatik devam sayısı
        self._budget_override = ""      # "YYYY-MM": kullanıcı bu ay bütçe aşımını onayladı
        self._budget_warned = ""        # "YYYY-MM": %80 uyarısı gösterildi

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_header())
        self.stack = QStackedWidget()
        self.welcome = WelcomeView(ctx)
        self.welcome.suggestion.connect(self._suggestion)
        self.welcome.workspace_changed.connect(self._welcome_ws)
        self.welcome.open_settings.connect(lambda: self.page_requested.emit("settings"))
        self.transcript = Transcript()
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.transcript)
        lay.addWidget(self.stack, 1)

        host = QHBoxLayout()
        host.setContentsMargins(24, 6, 24, 12)
        host.addStretch(1)
        self.composer = Composer()
        self.composer.setMaximumWidth(COLUMN_WIDTH)
        self.composer.submitted.connect(lambda t: self.send(t, self.composer.attachments.take()))
        self.composer.files_added.connect(self.add_files)
        self.composer.image_added.connect(self.add_image)
        self.composer.usage_btn.refresh_requested.connect(self.refresh_usage)
        self.composer.usage_btn.details_requested.connect(lambda: self.page_requested.emit("usage"))
        self._quota = None
        self._quota_error = ""
        self._quota_time = None
        self._usage_busy = False
        self._usage_timer = QTimer(self)
        self._usage_timer.setInterval(5 * 60 * 1000)
        self._usage_timer.timeout.connect(self.refresh_usage)
        self.composer.stop_requested.connect(self.stop)
        self.composer.mode_changed.connect(self.set_mode)
        self.composer.model_changed.connect(self.set_model)
        self.composer.attach_requested.connect(self.attach_files)
        self.composer.edit.send_with_enter = ctx.settings.send_with_enter
        host.addWidget(self.composer, 100)
        host.addStretch(1)
        lay.addLayout(host)

        self.panel.files.attach_requested.connect(lambda rel: self.composer.edit.insert_at_cursor(f"@{rel} "))
        self.panel.changes.changed.connect(lambda: None)
        self.refresh_models()
        self.new_session()

    # ---- başlık çubuğu ----

    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("HeaderBar")
        bar.setFixedHeight(48)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 0, 10, 0)
        h.setSpacing(6)
        self.sidebar_btn = icon_button("panel-left", "Kenar çubuğunu göster (Ctrl+B)", 17)
        self.sidebar_btn.clicked.connect(self.toggle_sidebar.emit)
        self.sidebar_btn.setVisible(False)
        h.addWidget(self.sidebar_btn)
        self.title_btn = QToolButton()
        self.title_btn.setProperty("variant", "chip")
        self.title_btn.setStyleSheet("font-weight: 600;")
        self.title_btn.setToolTip("Yeniden adlandırmak için tıklayın")
        self.title_btn.clicked.connect(self.rename)
        h.addWidget(self.title_btn)
        self.ws_chip = QToolButton()
        self.ws_chip.setProperty("variant", "chip")
        self.ws_chip.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.ws_chip.setIconSize(QSize(15, 15))
        self.ws_chip.clicked.connect(self._open_ws)
        h.addWidget(self.ws_chip)
        self.branch_chip = QToolButton()
        self.branch_chip.setProperty("variant", "chip")
        self.branch_chip.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.branch_chip.setIcon(icons.icon("branch", size=15))
        self.branch_chip.setIconSize(QSize(15, 15))
        self.branch_chip.setToolTip("Git dalı")
        h.addWidget(self.branch_chip)
        h.addStretch(1)
        self.more_btn = icon_button("more", "Oturum işlemleri", 17)
        self.more_btn.setPopupMode(QToolButton.InstantPopup)
        m = QMenu(self)
        m.addAction(icons.icon("map", size=15), "EVREN.md proje hafızası oluştur (/init)", lambda: self.send("/init"))
        m.addAction(icons.icon("refresh", size=15), "Konuşmayı özetle (/ozet)", lambda: self.send("/ozet"))
        m.addAction(icons.icon("download", size=15), "Markdown olarak dışa aktar", self.export)
        m.addSeparator()
        m.addAction(icons.icon("trash", theme.current().danger, 15), "Oturumu sil", self.delete_current)
        self.more_btn.setMenu(m)
        h.addWidget(self.more_btn)
        self.panel_btn = icon_button("panel-right", "Sağ paneli aç/kapat (Ctrl+J)", 17)
        self.panel_btn.clicked.connect(self.toggle_panel.emit)
        h.addWidget(self.panel_btn)
        return bar

    def _update_header(self) -> None:
        title = "Yeni oturum"
        if self.session_id:
            row = self.ctx.db.get_session(self.session_id)
            if row:
                title = row["title"]
        self.title_btn.setText(title[:60])
        ws = self.workspace if self.session_id else self.welcome.workspace
        if ws:
            self.ws_chip.setIcon(icons.icon("folder", size=15))
            self.ws_chip.setText(Path(ws).name)
            self.ws_chip.setToolTip(f"{ws}\nDosya Gezgini'nde açmak için tıklayın")
            self.ws_chip.setVisible(True)
            branch = Workspace(ws).git_branch() if Path(ws).is_dir() else None
            self.branch_chip.setText(branch or "")
            self.branch_chip.setVisible(bool(branch))
        else:
            self.ws_chip.setIcon(icons.icon("folder", theme.current().accent, 15))
            if self.session_id:
                self.ws_chip.setText("Proje klasörü bağla")
                self.ws_chip.setToolTip("Bu sohbete bir proje klasörü bağlayın: ajan dosyaları "
                                        "okuyup düzenleyebilir ve komut çalıştırabilir.")
            else:
                self.ws_chip.setText("Sohbet")
                self.ws_chip.setToolTip("Klasörsüz sohbet — dosya erişimi yok. Klasör seçmek için "
                                        "karşılama ekranındaki düğmeyi kullanın.")
            self.ws_chip.setVisible(True)
            self.branch_chip.setVisible(False)
        self.more_btn.setEnabled(self.session_id is not None)

    def _open_ws(self) -> None:
        ws = self.workspace if self.session_id else self.welcome.workspace
        if self.session_id and not self.workspace:
            self.attach_workspace()
            return
        if ws and os.name == "nt":
            subprocess.Popen(["explorer", ws])

    def attach_workspace(self, folder: str | None = None) -> bool:
        """Klasörsüz bir oturuma sonradan proje klasörü bağlar."""
        if self.running:
            QMessageBox.information(self, "Ajan çalışıyor", "Önce çalışan işlemi durdurun (Esc).")
            return False
        if not self.session_id or self.workspace:
            return False
        if folder is None:
            folder = QFileDialog.getExistingDirectory(self, "Bu oturuma proje klasörü bağla",
                                                      self.ctx.settings.code_workdir or str(Path.home()))
            if not folder:
                return False
        try:
            Workspace(folder)
        except ToolError as exc:
            QMessageBox.warning(self, "Klasör kullanılamıyor", str(exc))
            return False
        folder = str(Path(folder))
        self.ctx.db.update_session(self.session_id, workspace=folder)
        self.ctx.settings.remember_workspace(folder)
        self.ctx.save_settings()
        self.workspace = folder
        self.composer.set_agentic(True)
        self.composer.set_mode(self.mode)
        self.panel.set_session(self.session_id, folder, self.ctx.db.get_session_todos(self.session_id))
        self._update_header()
        self.sessions_changed.emit()
        self._note(f"Bu oturum artık “{Path(folder).name}” klasörüne bağlı. Ajan dosyaları "
                   f"okuyabilir; düzenleme ve komutlar {MODES[self.mode]} moduna göre sorulur.", "folder")
        self._env_check(folder)
        return True

    def set_sidebar_hidden(self, hidden: bool) -> None:
        self.sidebar_btn.setVisible(hidden)

    # ---- modeller ----

    def refresh_models(self) -> None:
        items = []
        # auto (önerilen varsayılan) EVREN grubunun en üstünde
        models = sorted(self.ctx.chat_models(),
                        key=lambda m: (m.provider != "evren", m.id != router.AKILLI_ID, m.id != "auto"))
        for m in models:
            desc = []
            if m.supports_tools:
                desc.append("araç")
            if m.supports_vision:
                desc.append("görsel")
            if m.context_length:
                desc.append(f"{m.context_length // 1000}k")
            if m.id == router.AKILLI_ID:
                desc = ["uygulama seçer · işe göre motor, görev ortasında değişmez, görünür"]
            elif m.id == "auto":
                desc = ["EVREN sunucusu seçer · her istekte değişebilir"]
            if m.provider != "evren":
                desc = [d for d in desc if d != "araç"] + [price_hint(m.id)]
            enabled = m.provider == "evren" or self.ctx.has_provider_key(m.provider)
            items.append((m.id, " · ".join(d for d in desc if d), m.supports_tools, m.provider, enabled))
        if not items:
            items = [(self.model, "", True, "evren", True)]
        ids = [i[0] for i in items]
        if self.model not in ids and ids:
            self.model = self.ctx.settings.default_model if self.ctx.settings.default_model in ids else ids[0]
        self.composer.set_models(items, self.model)
        self._update_context()

    # ---- oturum yönetimi ----

    def new_session(self) -> None:
        if self.running:
            QMessageBox.information(self, "Ajan çalışıyor", "Önce çalışan işlemi durdurun (Esc).")
            return
        self.session_id = None
        self.workspace = None
        self.edit_from = None
        self.mode = normalize_mode(self.ctx.settings.agent_mode)
        self.model = self.ctx.settings.default_model
        self.refresh_models()
        self.composer.set_mode(self.mode)
        self.transcript.clear()
        self.tool_widgets.clear()
        self.welcome.refresh()
        self.stack.setCurrentWidget(self.welcome)
        self.composer.set_agentic(self.welcome.workspace is not None)
        self.panel.set_session(None, self.welcome.workspace, [])
        self._update_header()
        self._update_context()
        self.session_opened.emit(None)
        self.composer.focus()

    def open_session(self, session_id: int) -> None:
        if self.running and session_id != self.session_id:
            QMessageBox.information(self, "Ajan çalışıyor",
                                    "Başka oturuma geçmeden önce çalışan işlemi durdurun (Esc).")
            self.session_opened.emit(self.session_id)
            return
        row = self.ctx.db.get_session(session_id)
        if not row:
            return
        self.session_id = session_id
        self.workspace = row["workspace"]
        self.mode = normalize_mode(row["mode"])
        self.model = row["model"]
        self.edit_from = None
        self.refresh_models()
        self.composer.set_model(self.model)
        self.composer.set_mode(self.mode)
        self.composer.set_agentic(self.workspace is not None)
        self.stack.setCurrentWidget(self.transcript)
        self.render_history(self.ctx.db.get_session_messages(session_id))
        self.panel.set_session(session_id, self.workspace, self.ctx.db.get_session_todos(session_id))
        self._update_header()
        self._update_context()
        self.session_opened.emit(session_id)
        run = self.ctx.db.latest_project_run(session_id)
        if run is not None and run["status"] in ("calisiyor", "duraklatildi") and not self.project.active:
            if run["status"] == "calisiyor":         # uygulama proje sürerken kapanmış
                from ..agent.project import ProjectState

                st = ProjectState.from_json(run["state_json"])
                st.status, st.pause_reason = "duraklatildi", "uygulama kapandı"
                for t in st.tasks:
                    if t.status == "calisiyor":
                        t.status = "bekliyor"
                self.ctx.db.update_project_run(run["id"], st.status, st.to_json())
            self.transcript.add(NoteWidget("Bu oturumda yarım kalan bir proje var. Kaldığı yerden sürdürmek "
                                           "için /proje-devam yazın.", "refresh"))
        if self.workspace and not Path(self.workspace).is_dir():
            self.transcript.add(NoteWidget(f"Proje klasörü bulunamadı: {self.workspace}", "alert"))
        elif self.workspace:
            self._env_check(self.workspace)

    def render_history(self, messages: list[dict], show_all: bool = False) -> None:
        """Oturum geçmişini çizer.

        PERFORMANS (2026-10-17): 200 mesajlık oturum açılışı ~30 sn sürüyordu. Artık
        çizim sırasında ekran güncellemesi askıya alınır ve uzun oturumlarda yalnız son
        HISTORY_WINDOW mesaj (bir kullanıcı mesajı sınırından) çizilir; üstte "Önceki
        mesajları göster" düğmesi tümünü açar. Modele giden geçmiş DEĞİŞMEZ.
        """
        self.transcript.setUpdatesEnabled(False)
        try:
            self._render_history(messages, show_all)
        finally:
            self.transcript.setUpdatesEnabled(True)

    def _render_history(self, messages: list[dict], show_all: bool) -> None:
        self.transcript.clear()
        self.tool_widgets.clear()
        hidden = 0
        if not show_all and len(messages) > HISTORY_WINDOW:
            start = len(messages) - HISTORY_WINDOW
            # Araç çağrısı ile sonucu ayrılmasın: bir kullanıcı mesajından başla
            while start > 0 and messages[start]["role"] not in ("user", "summary"):
                start -= 1
            hidden = start
            messages = messages[start:]
        if hidden:
            self.transcript.add(self._older_button(hidden))
        agentic = self.workspace is not None
        last_assistant: AssistantMessageWidget | None = None
        turn = {"total": 0.0, "steps": 0}

        def close_turn() -> None:
            # Çok adımlı turlarda son yanıtın altına tur toplamını yaz
            if last_assistant is not None and turn["steps"] > 1 and turn["total"] > 0:
                base = last_assistant.footer.text()
                last_assistant.set_footer(
                    f"{base}  ·  tur toplamı {format_duration(turn['total'])}, {turn['steps']} adım")
            turn["total"], turn["steps"] = 0.0, 0

        for m in messages:
            role = m["role"]
            if role == "user" and (m.get("meta") or {}).get("auto_continue"):
                self.transcript.add(NoteWidget("Bağlam özetlendi; ajan kaldığı yerden otomatik devam etti.",
                                               "refresh"))
                continue
            if role == "user":
                close_turn()
                text, attached = split_attachments(m["content"] or "")
                meta = m.get("meta") or {}
                if meta.get("display"):                 # proje ajanı: uzun istem yerine kısa başlık
                    text, attached = meta["display"], []
                atts = [Attachment.from_meta(d) for d in meta.get("attachments") or []]
                labels = set(meta.get("file_labels") or [])
                attached = [n for n in attached if n not in labels]
                w = UserMessageWidget(text + (("\n📎 " + ", ".join(attached)) if attached else ""), m["id"],
                                      attachments=atts)
                w.text = text
                w.edit_requested.connect(self.edit_message)
                self.transcript.add(w)
                last_assistant = None
            elif role == "assistant":
                meta = m.get("meta") or {}
                shown = model_display(m.get("model"), meta.get("routed_model"), meta.get("requested_model"))
                w = AssistantMessageWidget(shown, agentic)
                w.finalize(m["content"] or "", m.get("reasoning") if self.ctx.settings.show_reasoning else None,
                           meta.get("finish_reason"), shown, meta.get("duration_s"))
                if meta.get("duration_s") is not None:
                    turn["total"] += float(meta["duration_s"])
                turn["steps"] += 1
                for c in m.get("tool_calls") or []:
                    tw = w.add_tool(c["id"], c["name"], _parse_args(c.get("arguments")))
                    self.tool_widgets[c["id"]] = tw
                if not w.has_visible_content():
                    w.status.setText("(boş yanıt)")
                    w.status.setVisible(True)
                self.transcript.add(w)
                last_assistant = w
            elif role == "tool":
                meta = m.get("meta") or {}
                tw = self.tool_widgets.get(m.get("tool_call_id") or "")
                if tw is not None:
                    tw.set_result(not meta.get("error"), meta.get("summary") or "",
                                  {**meta, "error_text": m["content"] if meta.get("error") else None})
                else:
                    self.transcript.add(NoteWidget(m["content"][:300], "alert"))
            elif role == "summary":
                meta = m.get("meta") or {}
                w = AssistantMessageWidget("otomatik özet" if meta.get("auto") else "özet", False)
                head = "**Otomatik konuşma özeti**" if meta.get("auto") else "**Konuşma özeti**"
                why = f" ({meta['reason']})" if meta.get("reason") else ""
                w.finalize(f"{head}{why} — bu noktadan önceki mesajlar modele bu özet olarak "
                           "gönderilir; ekranda ve kayıtta durmaya devam eder.\n\n" + (m["content"] or ""),
                           duration=meta.get("duration_s"), model=m.get("model"))
                self.transcript.add(w)
        close_turn()
        self.current = None
        self.transcript.scroll_to_bottom()

    def _older_button(self, count: int) -> QWidget:
        host = QWidget()
        h = QHBoxLayout(host)
        h.setContentsMargins(0, 0, 0, 0)
        b = QPushButton(f"Önceki {count} mesajı göster")
        b.setProperty("variant", "ghost")
        b.setIcon(icons.icon("chevron-down", size=14))
        b.clicked.connect(self._show_full_history)
        h.addStretch(1)
        h.addWidget(b)
        h.addStretch(1)
        return host

    def _show_full_history(self) -> None:
        if not self.session_id:
            return
        self.render_history(self.ctx.db.get_session_messages(self.session_id), show_all=True)
        self.transcript._stick = False
        QTimer.singleShot(0, self, lambda: self.transcript.verticalScrollBar().setValue(0))

    def _ensure_session(self, first_text: str) -> int:
        if self.session_id is not None:
            return self.session_id
        ws = self.welcome.workspace
        title = first_text.strip().splitlines()[0][:60] if first_text.strip() else "Yeni oturum"
        sid = self.ctx.db.create_session(self.model, ws, self.mode, title=title,
                                         provider=self.ctx.provider_of(self.model))
        self.session_id = sid
        self.workspace = ws
        self.stack.setCurrentWidget(self.transcript)
        self.panel.set_session(sid, ws, [])
        self._update_header()
        self.sessions_changed.emit()
        self.session_opened.emit(sid)
        if ws:
            self._env_check(ws)
        return sid

    def rename(self) -> None:
        if not self.session_id:
            return
        row = self.ctx.db.get_session(self.session_id)
        title, ok = QInputDialog.getText(self, "Oturumu adlandır", "Yeni ad:", text=row["title"])
        if ok and title.strip():
            self.ctx.db.update_session(self.session_id, title=title.strip())
            self._update_header()
            self.sessions_changed.emit()

    def export(self, session_id: int | None = None) -> None:
        sid = session_id or self.session_id
        if not sid:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Oturumu dışa aktar", f"evren-oturum-{sid}.md",
                                              "Markdown (*.md)")
        if path:
            Path(path).write_text(self.ctx.db.export_session_markdown(sid), encoding="utf-8")

    def delete_current(self) -> None:
        if self.session_id:
            self.delete_session(self.session_id)

    def delete_session(self, sid: int) -> None:
        if self.running and sid == self.session_id:
            QMessageBox.information(self, "Ajan çalışıyor", "Önce çalışan işlemi durdurun.")
            return
        if QMessageBox.question(
            self, "Oturumu sil",
            "Bu oturum ve tüm mesajları silinecek. Proje dosyalarınız etkilenmez. Devam edilsin mi?",
        ) != QMessageBox.Yes:
            return
        self.ctx.db.delete_session(sid)
        self.perms.pop(sid, None)
        if sid == self.session_id:
            self.new_session()
        self.sessions_changed.emit()

    def _welcome_ws(self, ws: str | None) -> None:
        self.composer.set_agentic(ws is not None)
        self.panel.set_session(None, ws, [])
        self._update_header()

    def _suggestion(self, prompt: str) -> None:
        if prompt.startswith("/plan "):
            self.set_mode("plan")
            self.composer.set_mode("plan")
            prompt = prompt[len("/plan "):]
        if prompt == "/init":
            self.send(prompt)
            return
        # Öneriyi gönderilmeden önce düzenlenebilsin diye yazma kutusuna koy
        self.composer.set_text(prompt)

    # ---- mod / model ----

    def set_mode(self, mode: str) -> None:
        mode = normalize_mode(mode)
        changed = mode != self.mode
        self.mode = mode
        if changed and mode == "auto" and self.session_id:
            self._note("Otomatik mod: hiçbir işlem için onay istenmez — tüm dosya düzenlemeleri, "
                       "komutlar ve dosya okumaları onaysız çalışır. Durdurmak için Esc veya "
                       "Durdur düğmesini kullanın.", "spark")
        if self.runner is not None:
            self.runner.mode = mode       # sonraki araç kararından itibaren geçerli
        if self.session_id:
            self.ctx.db.update_session(self.session_id, mode=mode)
        self._remember(agent_mode=mode)

    def _remember(self, **values) -> None:
        """Kullanıcının son seçimi (motor / onay modu) yeni oturumlarda da gelir;
        kullanıcı yeniden değiştirene kadar korunur (kullanıcı kararı, 2026-10-16)."""
        s = self.ctx.settings
        changed = {k: v for k, v in values.items() if getattr(s, k) != v}
        if changed:
            for k, v in changed.items():
                setattr(s, k, v)
            self.ctx.save_settings()

    def set_model(self, model: str) -> None:
        provider = self.ctx.provider_of(model)
        if provider != "evren" and not self.ctx.has_provider_key(provider):
            name = PROVIDERS[provider].name
            self.composer.set_model(self.model)          # seçimi geri al
            if QMessageBox.question(
                self, f"{name} anahtarı gerekli",
                f"{model} bir {name} modelidir ve ücretlidir. Kullanmak için {name} API "
                "anahtarınızı Ayarlar > Sağlayıcılar bölümüne girin. Ayarlar açılsın mı?",
            ) == QMessageBox.Yes:
                self.page_requested.emit("settings")
            return
        self.model = model
        if self.session_id:
            self.ctx.db.update_session(self.session_id, model=model, provider=provider)
        self._remember(default_model=model)
        self._update_context()
        self.update_usage_view()

    # ---- ücretli sağlayıcı bütçesi ----

    @staticmethod
    def _month() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _budget_state(self):
        s = self.ctx.settings
        return current_state(self.ctx.db, s.monthly_budget_usd, s.budget_enforce)

    def _budget_blocks(self, provider: str) -> bool:
        if provider == "evren" or self._budget_override == self._month():
            return False
        return self._budget_state().exceeded

    def _ask_budget(self) -> bool:
        st = self._budget_state()
        ok = QMessageBox.question(
            self, "Aylık bütçe doldu",
            f"Ücretli sağlayıcılar için aylık bütçeye ulaşıldı ({st.text()}). Bu tahmindir; "
            "gerçek harcama için sağlayıcı panelinize bakın.\n\nBu ay bu sınırı aşarak devam "
            "edilsin mi? (Bütçeyi Ayarlar > Sağlayıcılar'dan değiştirebilirsiniz.)",
        ) == QMessageBox.Yes
        if ok:
            self._budget_override = self._month()
        return ok

    def _record_cost(self, model: str, usage: dict | None) -> None:
        provider = self.ctx.provider_of(model)
        if provider == "evren" or not usage:
            return
        cost = estimate_cost(model, usage)
        self.ctx.db.add_usage_cost(provider, model, usage, cost, self.session_id)
        st = self._budget_state()
        if st.warn and self._budget_warned != self._month():
            self._budget_warned = self._month()
            self._note(f"Ücretli kullanım bütçesinin %{int(st.ratio * 100)}'i kullanıldı ({st.text()}). "
                       "Tahminidir; bütçe Ayarlar > Sağlayıcılar'dan değiştirilebilir.", "gauge")

    def _policy(self) -> CompactPolicy:
        s = self.ctx.settings
        return CompactPolicy(enabled=s.auto_compact, percent=s.auto_compact_percent,
                             max_tokens=s.auto_compact_max_tokens)

    def _summary_model(self) -> str:
        """Özet modeli: ayar (varsayılan hızlı model) yoksa/kullanılamıyorsa oturumun modeli."""
        wanted = (self.ctx.settings.auto_compact_model or "").strip()
        if not wanted:
            return self._concrete_model("sohbet")
        ids = [m.id for m in self.ctx.chat_models()]
        return wanted if (not ids or wanted in ids) else self._concrete_model("sohbet")

    def _concrete_model(self, role: str = "sohbet") -> str:
        """Oturum modeli EVREN Akıllı ise o rol için seçilen gerçek model; değilse kendisi."""
        if not router.is_akilli(self.model):
            return self.model
        return self._route(role=role).model

    def _route(self, history: list | None = None, role: str | None = None) -> "router.Route":
        avail = {m.id for m in self.ctx.evren_chat_models()}
        health = {}
        try:
            health = {r["model"]: dict(r) for r in self.ctx.db.all_model_health()}
        except Exception:
            pass
        if role:
            return router.choose(role, available=avail or None, health=health, reason="yardımcı iş")
        history = history or []
        last_user = next((m for m in reversed(history) if m.get("role") == "user"), None)
        has_images = bool(((last_user or {}).get("meta") or {}).get("images"))
        est = estimate_tokens(to_api_messages("", history, "native")) if history else 0
        context_of = {m.id: m.context_length or 0 for m in self.ctx.evren_chat_models()}
        return router.route(agentic=self.workspace is not None,
                            mode=("plan" if self._plan_turn else self.mode), has_images=has_images,
                            est_tokens=est, context_of=context_of, available=avail or None, health=health)

    def _context_tokens(self) -> int | None:
        info = self.ctx.model_info(self.model)
        return info.context_length if info else None

    def _update_context(self) -> None:
        if not self.session_id:
            self.composer.set_context(0, None)
            return
        msgs = self.ctx.db.get_session_messages(self.session_id)
        info = self.ctx.model_info(self.model)
        ctx_tokens = info.context_length if info else None
        policy = self._policy()
        self.composer.set_context(estimate_tokens(to_api_messages("", msgs, "native")), ctx_tokens,
                                  policy.soft_limit(ctx_tokens) if policy.enabled else None)

    # ---- dosya ekleme ----

    def attach_files(self) -> None:
        ws = self.workspace if self.session_id else self.welcome.workspace
        files, _ = QFileDialog.getOpenFileNames(self, "Mesaja dosya veya görsel ekle", ws or str(Path.home()))
        self.add_files(files)

    def _data_dir(self) -> Path:
        return self.ctx.settings.resolved_data_dir()

    def add_files(self, paths: list) -> None:
        """Sürüklenen / yapıştırılan / seçilen dosyalar → ek kartı (yol metne yazılmaz)."""
        skipped = []
        for f in paths:
            att = attachment_from_path(str(f), self._data_dir())
            if att is None or not self.composer.attachments.add(att):
                skipped.append(Path(str(f)).name)
        if skipped:
            self.composer.set_run_status(None)
            QMessageBox.information(self, "Bazı dosyalar eklenmedi",
                                    "Eklenemedi (zaten ekli, okunamıyor veya en fazla "
                                    f"{10} ek sınırı): " + ", ".join(skipped))
        self.composer.edit.setFocus()

    def add_image(self, img) -> None:
        att = clipboard_image_attachment(img, self._data_dir())
        if att is None or not self.composer.attachments.add(att):
            QMessageBox.information(self, "Görsel eklenemedi", "Panodaki görsel kaydedilemedi.")
        self.composer.edit.setFocus()

    def _restore_attachments(self, atts: list) -> None:
        for a in atts:
            if Path(a.path).exists():
                self.composer.attachments.add(a)

    def _sees_images(self, model: str) -> bool:
        if router.is_akilli(model):
            return True                         # görselli turda görsel modele yönlendirir
        info = self.ctx.model_info(model)
        return bool(info and info.supports_vision)

    def _expand_mentions(self, text: str, ws: str | None) -> str:
        if not ws:
            return text
        try:
            workspace = Workspace(ws)
        except ToolError:
            return text
        tb = ToolBox(workspace)
        blocks = []
        seen = set()
        for m in MENTION_RE.finditer(text):
            rel = m.group(1).rstrip(".,;:)")
            if rel in seen:
                continue
            seen.add(rel)
            try:
                p = workspace.resolve(rel)
                if not p.is_file() or p.stat().st_size > MAX_ATTACH_BYTES:
                    continue
                content = tb.load_text(p).text
            except (ToolError, OSError):
                continue
            lang = p.suffix.lstrip(".")
            blocks.append(f"### {workspace.rel(p)}\n```{lang}\n{content}\n```")
        if not blocks:
            return text
        return text + "\n\n" + ATTACH_OPEN + "\n" + "\n\n".join(blocks) + "\n" + ATTACH_CLOSE

    # ---- gönderme ----

    def send(self, text: str, attachments: list | None = None) -> None:
        text = text.strip()
        atts = list(attachments or [])
        if not text and not atts:
            return

        def back() -> None:
            self.composer.set_text(text)
            self._restore_attachments(atts)

        if text.startswith("/") and not atts:
            if self._command(text):
                return
        if self.project.active or self.project.planning:
            self._note("Proje ajanı çalışıyor; şu an ayrı mesaj gönderilemez. Durdurmak için "
                       "/proje-durdur yazın.", "alert")
            back()
            return
        if self.running:
            back()
            return
        images = [a for a in atts if a.kind == "image"]
        if images and not self._sees_images(self.model):
            if QMessageBox.question(
                self, "Bu motor görsel okuyamaz",
                f"{self.model} görsel kabul etmiyor. Görsel okuyabilen “auto” motoruna geçip "
                "gönderilsin mi? (auto görseli uygun modele yönlendirir.)",
            ) != QMessageBox.Yes:
                back()
                return
            self.composer.set_model("auto", emit=True)
        provider = self.ctx.provider_of(self.model)
        if not self.ctx.has_provider_key(provider):
            self.stack.setCurrentWidget(self.transcript if self.session_id else self.welcome)
            self.welcome.refresh()
            name = PROVIDERS.get(provider).name if provider in PROVIDERS else provider
            QMessageBox.warning(self, "API anahtarı yok",
                                f"Önce Ayarlar sayfasından {name} API anahtarınızı girin.")
            back()
            return
        if self._budget_blocks(provider) and not self._ask_budget():
            back()
            return
        if not self.model:
            QMessageBox.warning(self, "Model seçilmedi", "Lütfen bir model seçin.")
            return
        visible, _att = split_attachments(text)
        sid = self._ensure_session(visible or (atts[0].name if atts else "Ek"))
        if self.edit_from is not None:
            self.ctx.db.delete_session_messages_from(sid, self.edit_from)
            self.edit_from = None
            self.render_history(self.ctx.db.get_session_messages(sid))
        content = self._expand_mentions(text, self.workspace)
        meta = None
        if atts:
            labels, blocks = [], []
            for a in atts:
                if a.kind != "image":
                    label, block = file_block(a, self.workspace)
                    labels.append(label)
                    blocks.append(block)
            content = append_blocks(content, blocks)
            meta = {"attachments": [a.to_meta() for a in atts], "file_labels": labels,
                    "images": [a.path for a in images]}
        self._auto_resumes = 0
        need, tokens, limit = needs_compaction(self.ctx.db.get_session_messages(sid), self._policy(),
                                               self._context_tokens(), content)
        if need:
            pct = int(tokens * 100 / limit) if limit else 0
            self.compact(auto=True, reason=f"bağlam ~{tokens // 1000}k token, otomatik özet eşiği "
                                           f"{limit // 1000}k ({pct}%)",
                         then=lambda: self._send_now(sid, content, text, meta),
                         on_cancel=back)
            return
        self._send_now(sid, content, text, meta)

    def _send_now(self, sid: int, content: str, text: str, meta: dict | None = None) -> None:
        msg_id = self.ctx.db.add_session_message(sid, "user", content, meta=meta)
        self._turn_id = msg_id
        # "Önce plan" (Ayarlar, varsayılan kapalı): dosyaya dokunmadan önce plan turu
        self._plan_turn = bool(self.ctx.settings.plan_first and self.workspace and self.mode != "plan"
                               and not self._skip_plan_once)
        self._skip_plan_once = False
        _, attached = split_attachments(content)
        labels = set((meta or {}).get("file_labels") or [])
        attached = [n for n in attached if n not in labels]
        atts = [Attachment.from_meta(d) for d in (meta or {}).get("attachments") or []]
        w = UserMessageWidget(text + (("\n📎 " + ", ".join(attached)) if attached else ""), msg_id,
                              attachments=atts)
        w.text = text
        w.edit_requested.connect(self.edit_message)
        self.transcript.add(w)
        self.transcript.scroll_to_bottom()
        self.sessions_changed.emit()
        self.start_run()

    def edit_message(self, message_id: int, text: str) -> None:
        if self.running or not message_id:
            return
        self.edit_from = message_id
        self.composer.set_text(text)
        for m in self.ctx.db.get_session_messages(self.session_id) if self.session_id else []:
            if m["id"] == message_id:
                self._restore_attachments([Attachment.from_meta(d)
                                           for d in (m.get("meta") or {}).get("attachments") or []])
                break
        self.transcript.add(NoteWidget(
            "Mesajı düzenliyorsunuz: gönderdiğinizde bu mesaj ve sonrası yeniden oluşturulur "
            "(dosya değişiklikleri otomatik geri alınmaz).", "pencil"))

    def _command(self, text: str) -> bool:
        cmd, _, arg = text.partition(" ")
        cmd = cmd.lower()
        if cmd not in SLASH_COMMANDS and cmd not in MODE_COMMANDS:
            return False
        if cmd.startswith("/proje"):
            self.project.command(cmd, arg)
            return True
        if cmd == "/yeni":
            self.new_session()
        elif cmd in MODE_COMMANDS:
            mode = MODE_COMMANDS[cmd]
            self.set_mode(mode)
            self.composer.set_mode(mode)
            self._note(f"Mod: {MODES[mode]}")
            if arg.strip():
                self.send(arg)
        elif cmd == "/model":
            ids = [m.id for m in self.ctx.chat_models()]
            if not arg.strip():
                self.composer.set_text("/model ")     # tıklanabilir model listesini aç
            elif arg.strip() in ids or (not ids and arg.strip()):
                self.set_model(arg.strip())
                self.composer.set_model(arg.strip())
                self._note(f"Model: {arg.strip()}")
            else:
                self._note("Kullanım: /model <ad>. Mevcut: " + ", ".join(ids or ["(liste yüklenmedi)"]))
        elif cmd == "/init":
            ws = self.workspace if self.session_id else self.welcome.workspace
            if not ws:
                self._note("/init için bir proje klasörü seçin.")
            else:
                self.send(prompts.INIT_PROMPT)
        elif cmd in ("/ozet", "/compact"):
            self.compact(focus=arg.strip() or None)
        elif cmd == "/disa-aktar":
            self.export()
        elif cmd == "/yardim":
            self._show_help()
        return True

    def _note(self, text: str, icon_name: str = "dot") -> None:
        if self.stack.currentWidget() is not self.transcript:
            if not self.session_id:
                QMessageBox.information(self, "EVREN Studio", text)
                return
            self.stack.setCurrentWidget(self.transcript)
        self.transcript.add(NoteWidget(text, icon_name))

    def _show_help(self) -> None:
        lines = ["**Komutlar**", ""]
        lines += [f"- `{c}` — {d}" for c, d in SLASH_COMMANDS.items()]
        lines += ["", "**Kısayollar**", "",
                  "- `Enter` gönder, `Shift+Enter` yeni satır, `Esc` durdur",
                  "- `Ctrl+N` yeni oturum, `Ctrl+B` kenar çubuğu, `Ctrl+J` sağ panel, `Ctrl+K` oturum ara",
                  "- Mesajda `@yol/dosya.py` yazarak dosya içeriğini ekleyin",
                  "", "**Modlar**", "",
                  "- **Plan**: yalnızca okur, plan çıkarır",
                  "- **Onaylı**: her değişiklik ve komut için onay ister",
                  "- **Otomatik düzenleme**: dosyaları onaysız düzenler, komutlar için onay ister"]
        if self.stack.currentWidget() is not self.transcript:
            self.stack.setCurrentWidget(self.transcript)
        w = AssistantMessageWidget("yardım")
        w.finalize("\n".join(lines))
        self.transcript.add(w)

    # ---- ajan çalıştırma ----

    def start_run(self, history_from: int | None = None, mode_override: str | None = None,
                  model_override: tuple[str, list[str], str] | None = None) -> None:
        """history_from: yalnız bu mesajdan itibaren geçmiş (proje görevi: temiz bağlam).
        mode_override / model_override: proje ajanının plan (salt okunur) ve görev (Otomatik) turları."""
        sid = self.session_id
        if sid is None:
            return
        history = self.ctx.db.get_session_messages(sid)
        if history_from is not None:
            history = [m for m in history if m["id"] >= history_from]
        ws = None
        if self.workspace:
            try:
                ws = Workspace(self.workspace)
            except ToolError as exc:
                self.transcript.add(ErrorCard("Proje klasörüne erişilemiyor", [str(exc)]))
                return
        # EVREN Akıllı: bu tur için rol + gerçek model + yedekler (tur boyunca sabit)
        self._run_route = None
        api_model, fallbacks = self.model, []
        if model_override is not None:
            api_model, fallbacks = model_override[0], list(model_override[1])
            if router.is_akilli(self.model):
                self._run_route = router.Route(api_model, model_override[2], "proje ajanı", fallbacks)
        elif router.is_akilli(self.model):
            self._run_route = self._route(history)
            api_model, fallbacks = self._run_route.model, list(self._run_route.fallbacks)
        row = self.ctx.db.get_session(sid)
        protocol = row["protocol"] if row and row["protocol"] else self.ctx.resolve_protocol(api_model)
        if self.ctx.settings.tool_protocol != "otomatik":
            protocol = self.ctx.resolve_protocol(api_model)
        info = self.ctx.model_info(api_model)
        self.cancel_token = CancelToken()
        self.bridge = AgentBridge()
        b = self.bridge
        b.sig_step.connect(self._on_step)
        b.sig_text.connect(self._on_text)
        b.sig_reasoning.connect(self._on_reasoning)
        b.sig_message.connect(self._on_message)
        b.sig_tool_started.connect(self._on_tool_started)
        b.sig_tool_output.connect(self._on_tool_output)
        b.sig_tool_finished.connect(self._on_tool_finished)
        b.sig_approval.connect(self._on_approval)
        b.sig_todos.connect(self._on_todos)
        b.sig_file.connect(lambda _id, _c: self.panel.changes.refresh())
        b.sig_protocol.connect(self._on_protocol)
        b.sig_status.connect(lambda t: self._note(t, "alert"))
        s = self.ctx.settings
        perms = self.perms.setdefault(sid, SessionPermissions())
        provider = self.ctx.provider_of(api_model)
        try:
            client = self.ctx.make_client_for(provider, log_sink=lambda m: None)
        except RuntimeError as exc:
            self.transcript.add(ErrorCard("İstemci oluşturulamadı", [str(exc)],
                                          [("Ayarlar", lambda: self.page_requested.emit("settings"))]))
            return

        def before_call(_step: int):
            return "budget" if self._budget_blocks(provider) else None
        self.runner = AgentRunner(
            client, api_model, session_id=sid, store=self.ctx.db, events=b,
            workspace=ws, mode=(mode_override or ("plan" if self._plan_turn else self.mode)), protocol=protocol,
            turn_id=self._turn_id,
            allow_protocol_fallback=(s.tool_protocol == "otomatik"),
            permissions=perms, cancel=self.cancel_token, stream=s.stream_responses,
            max_steps=s.agent_max_steps, command_timeout=s.command_timeout_seconds,
            output_limit=s.tool_output_limit,
            context_tokens=info.context_length if info else None,
            hard_context_limit=(self._policy().hard_limit(info.context_length if info else None)
                                if s.auto_compact else None),
            before_model_call=before_call if provider != "evren" else None,
            # Boş yanıt (düşünme bütçesi tükendi) sonrası tek yeniden denemede düşünmeyi kapat;
            # yalnız EVREN kaydı reasoning_effort desteği bildiren modellerde.
            stall_retry_body=({"reasoning_effort": "none"}
                              if provider == "evren" and info and (info.capabilities or {}).get("reasoning_effort")
                              else None),
            install_mode=s.install_mode,
            fallback_models=fallbacks,
        )
        runner = self.runner
        self.running = True
        self.composer.set_running(True)
        self._pending_approvals.clear()
        self.run_model = api_model
        self._run_t0 = time.monotonic()
        self._run_step = 0
        self._run_activity = "başlatılıyor"
        self._run_timer.start()
        self._tick_run()

        def job():
            try:
                return runner.run(history)
            finally:
                client.close()

        Task(job, on_done=self._on_done, on_error=self._on_fail).start()

    def stop(self) -> None:
        if not self.running or self.cancel_token is None:
            return
        self.cancel_token.cancel()
        for req in self._pending_approvals:
            req.resolve(ApprovalRequest.DENY)
        if self.current is not None:
            self.current.start_waiting("Durduruluyor")

    # -- olaylar --

    def _on_step(self, step: int) -> None:
        if self.current is not None and not self.current.has_visible_content():
            self.current.setVisible(False)
        self._run_step = step
        self._run_activity = "yanıt üretiyor"
        self.current = AssistantMessageWidget(self.model, self.workspace is not None)
        self.current.start_waiting("Düşünüyor" if step == 1 else "Devam ediyor")
        self.current.start_clock(self.run_model or self.model)
        self.transcript.add(self.current)
        self._tick_run()

    # -- çalışma durum çubuğu: hangi LLM, ne kadar süredir --

    def _tick_run(self) -> None:
        if not self.running or self._run_t0 is None:
            return
        elapsed = time.monotonic() - self._run_t0
        model = self.runner.model if self.runner is not None else self.run_model   # yedeğe geçişte güncel
        prov = self.ctx.provider_of(model)
        name = f"{PROVIDERS[prov].name} · {model}" if prov != "evren" else model
        route = getattr(self, "_run_route", None)
        if route is not None:
            name = f"{router.AKILLI_LABEL} → {model} ({router.ROLE_LABELS.get(route.role, route.role)})"
        parts = [f"{name}  {self._run_activity}", format_duration(elapsed)]
        if self.project.label:
            parts.insert(0, self.project.label)
        if self._run_step > 1:
            parts.append(f"adım {self._run_step}")
        self.composer.set_run_status("  ·  ".join(parts))

    def _on_text(self, delta: str) -> None:
        if self.current is not None:
            self.current.append_text(delta)

    def _on_reasoning(self, delta: str) -> None:
        if self.current is not None and self.ctx.settings.show_reasoning:
            self.current.append_reasoning(delta)

    def _on_message(self, msg: dict) -> None:
        role = msg.get("role")
        if role == "assistant" and self.current is not None:
            meta = msg.get("meta") or {}
            shown = model_display(msg.get("model"), meta.get("routed_model"), meta.get("requested_model"))
            self.current.finalize(msg.get("content") or "", msg.get("reasoning") if self.ctx.settings.show_reasoning else None,
                                  meta.get("finish_reason"), shown, meta.get("duration_s"))
            self._run_activity = "araç çalıştırıyor" if msg.get("tool_calls") else "yanıt üretiyor"
            self._record_cost(meta.get("requested_model") or self.model, meta.get("usage"))
            for c in msg.get("tool_calls") or []:
                tw = self.current.add_tool(c["id"], c["name"], _parse_args(c.get("arguments")))
                self.tool_widgets[c["id"]] = tw
            if not self.current.has_visible_content():
                self.current.status.setText("(boş yanıt — model içerik üretmedi)")
                self.current.status.setVisible(True)
        elif role == "tool" and msg.get("name") == "arac_cagrisi":
            self.transcript.add(NoteWidget(msg.get("content", "")[:300], "alert"))
        elif role == "tool":
            tw = self.tool_widgets.get(msg.get("tool_call_id") or "")
            meta = msg.get("meta") or {}
            if tw is not None and not tw.finished:
                # yürütülmeden sonuçlanan (iptal, bilinmeyen araç vb.)
                tw.set_result(not meta.get("error"), meta.get("summary") or "",
                              {**meta, "error_text": msg.get("content") if meta.get("error") else None})
        self._update_context()

    def _on_tool_started(self, call: ToolCall, title: str) -> None:
        tw = self.tool_widgets.get(call.id)
        if tw is not None:
            tw.set_running(title)
        self._run_activity = title[:60]
        self._tick_run()
        if call.name == "run_command":
            self.panel.terminal.log_command(call.arguments.get("command", ""))

    def _on_tool_output(self, call: ToolCall, chunk: str) -> None:
        tw = self.tool_widgets.get(call.id)
        if tw is not None:
            tw.append_output(chunk)
        self.panel.terminal.log_output(chunk)

    def _on_tool_finished(self, call: ToolCall, result: ToolResult) -> None:
        tw = self.tool_widgets.get(call.id)
        if tw is not None:
            tw.set_result(result.ok, result.summary,
                          {**result.extra, "error_text": None if result.ok else result.content})

    def _on_approval(self, req: ApprovalRequest) -> None:
        tw = self.tool_widgets.get(req.call.id)
        if tw is None and self.current is not None:
            tw = self.current.add_tool(req.call.id, req.call.name, req.call.arguments)
            self.tool_widgets[req.call.id] = tw
        self._pending_approvals.append(req)
        self._run_activity = "onayınızı bekliyor"
        self._tick_run()
        if tw is not None:
            def decided(_d: str, r=req) -> None:
                if r in self._pending_approvals:
                    self._pending_approvals.remove(r)
                self._run_activity = "çalışıyor"
                self._tick_run()

            tw.show_approval(req, decided)
        self.transcript.scroll_to_bottom()
        QApplication.alert(self.window(), 0)

    def _on_todos(self, todos: list) -> None:
        self.panel.todos.set_todos(todos)

    def _on_protocol(self, protocol: str, reason: str) -> None:
        if self.session_id:
            self.ctx.db.update_session(self.session_id, protocol=protocol)
        self._note(reason, "refresh")

    # ---- kullanım (kota) ----

    def _usage_snapshot(self) -> UsageSnapshot:
        s = UsageSnapshot(quota=self._quota, error=self._quota_error, updated=self._quota_time)
        if self.session_id:
            for m in self.ctx.db.get_session_messages(self.session_id):
                u = (m.get("meta") or {}).get("usage") or {}
                s.session_in += int(u.get("input_tokens") or 0)
                s.session_out += int(u.get("output_tokens") or 0)
        prov = self.ctx.provider_of(self.model) if self.model else "evren"
        if prov in PROVIDERS and PROVIDERS[prov].paid:
            st = self._budget_state()
            s.paid_name, s.paid_spent, s.paid_limit = PROVIDERS[prov].name, st.spent, st.limit
        return s

    def update_usage_view(self) -> None:
        self.composer.usage_btn.set_snapshot(self._usage_snapshot())

    def refresh_usage(self) -> None:
        """EVREN kotasını arka planda ister (R-04); sonuç düğmeye ve panele yazılır."""
        if self._usage_busy:
            return
        if not self.ctx.has_api_key():
            self._quota, self._quota_error = None, "EVREN API anahtarı yok"
            self.update_usage_view()
            return
        self._usage_busy = True

        def job():
            client = self.ctx.make_client()
            try:
                return client.get_quota()
            finally:
                close = getattr(client, "close", None)
                if close:
                    close()

        def done(q):
            from datetime import datetime

            self._usage_busy = False
            self._quota, self._quota_error, self._quota_time = q, "", datetime.now()
            if not self._usage_timer.isActive():
                self._usage_timer.start()
            self.update_usage_view()

        def fail(exc):
            from datetime import datetime

            self._usage_busy = False
            self._quota_error, self._quota_time = str(exc)[:160], datetime.now()
            self.update_usage_view()

        Task(job, on_done=done, on_error=fail).start()

    def _finish(self) -> None:
        self.running = False
        self._run_timer.stop()
        total = time.monotonic() - self._run_t0 if self._run_t0 is not None else None
        self._run_t0 = None
        self.composer.set_running(False)
        self.runner = None
        if self.ctx.provider_of(self.model) == "evren":
            QTimer.singleShot(400, self, self.refresh_usage)   # yanıt bitti: EVREN kotası değişti
        if self.current is not None:
            self.current.stop_waiting()
            self.current.stop_clock()
            if not self.current.has_visible_content():
                self.current.setVisible(False)
        # Turun özeti son görünür yanıtın altına: "glm-5.3 · 8,4 sn · tur toplamı 31 sn, 3 adım"
        last = self._last_visible_assistant()
        if last is not None and total is not None and self._run_step > 1:
            base = last.footer.text() or self.run_model
            last.set_footer(f"{base}  ·  tur toplamı {format_duration(total)}, {self._run_step} adım")
        self.current = None
        self._pending_approvals.clear()
        self.panel.changes.refresh()
        self.sessions_changed.emit()
        self._update_header()
        self._update_context()

    def _last_visible_assistant(self) -> AssistantMessageWidget | None:
        lay = self.transcript.lay
        for i in range(lay.count() - 1, -1, -1):
            w = lay.itemAt(i).widget()
            if isinstance(w, UserMessageWidget):
                return None
            if isinstance(w, AssistantMessageWidget) and w.isVisibleTo(self.transcript):
                return w
        return None

    def _on_done(self, outcome) -> None:
        hook, self._turn_hook = self._turn_hook, None
        if hook is not None:                    # proje ajanı turu: sonrası denetleyicide
            self._finish()
            if getattr(outcome, "test_edits", None):
                self._note("Dikkat: bu görevde var olan test dosyaları değiştirildi: "
                           + ", ".join(outcome.test_edits), "alert")
            hook(outcome, None)
            return
        self._finish()
        if getattr(outcome, "test_edits", None):
            self._note("Dikkat: bu turda var olan test dosyaları değiştirildi ve öyle kaldı: "
                       + ", ".join(outcome.test_edits) + ". Testleri değiştirmek istemediyseniz sağ "
                       "paneldeki Değişiklikler sekmesinden geri alın; testlerin geçmesi bu durumda "
                       "kodun doğru olduğunu göstermez.", "alert")
        if outcome.stopped == "cancelled":
            self._note("Durduruldu. Devam etmek için yeni bir mesaj gönderin.", "stop")
        elif outcome.stopped == "max_steps":
            pass  # durum notu runner tarafından gönderildi
        elif outcome.stopped == "budget":
            if self._ask_budget():
                self.start_run()          # geçmiş araç sonuçlarıyla biter; kaldığı yerden sürer
            else:
                self._note("Aylık bütçe nedeniyle durduruldu. Bütçeyi Ayarlar > Sağlayıcılar'dan "
                           "artırabilir veya ücretsiz bir EVREN modeline geçebilirsiniz.", "stop")
        elif outcome.stopped == "context_limit":
            if self._auto_resumes < MAX_AUTO_RESUMES:
                self._auto_resumes += 1
                self.compact(auto=True, reason="uzun görev bağlam sınırına yaklaştı (güvenli noktada durdu)",
                             then=self._auto_continue)
            else:
                self._note(f"Bağlam sınırı: bu mesaj için {MAX_AUTO_RESUMES} kez otomatik özetlenip "
                           "devam edildi. Devam etmek için yeni bir mesaj gönderin.", "alert")
        if self.session_id:
            self.panel.todos.set_todos(self.ctx.db.get_session_todos(self.session_id))
        if outcome.stopped in ("done", "loop", "max_steps", "cancelled"):
            if self._plan_turn:
                self._plan_turn = False
                if outcome.stopped == "done":
                    self._offer_plan()
            else:
                self._turn_review(self._turn_id)

    def _on_fail(self, exc: Exception) -> None:
        hook, self._turn_hook = self._turn_hook, None
        if hook is not None:                    # proje ajanı: hata yönetimi (bekle/yedek/duraklat) orada
            self._finish()
            self._note(f"Görev turu hata ile bitti: {exc}", "alert")
            hook(None, exc)
            return
        self._finish()
        if isinstance(exc, ApiError):
            open_mon = self.ctx.db.get_open_monitor_session()
            monitor_state = f"izleme #{open_mon['id']} çalışıyor" if open_mon else "izleme kapalı"
            error_id = self.ctx.recovery.record_error(
                exc, monitor_state=monitor_state, context=f"session_id={self.session_id}")
            advice = self.ctx.recovery.advise(exc)
            lines = [str(exc), "", f"Olası kaynak: {advice.source_guess}"]
            lines += [f"{i}. {s}" for i, s in enumerate(advice.recommended_steps, 1)]
            actions = [("Hata Merkezi", lambda: self.page_requested.emit("errors"))]
            prov = self.ctx.provider_of(exc.model or self.model)
            if prov in PROVIDERS and PROVIDERS[prov].paid:
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices

                billing = PROVIDERS[prov].billing_url
                actions.append((f"{PROVIDERS[prov].name} paneli",
                                lambda u=billing: QDesktopServices.openUrl(QUrl(u))))
            if exc.kind == ErrorKind.AUTH:
                actions.insert(0, ("Anahtarı güncelle", lambda: self.page_requested.emit("settings")))
            elif exc.kind == ErrorKind.UNKNOWN_RESULT:
                actions.insert(0, ("Kontrollü yeniden dene", self._retry_confirm))
            elif exc.kind != ErrorKind.QUOTA_EXHAUSTED:   # kredi bitince tekrar işe yaramaz
                actions.insert(0, ("Yeniden dene", self.start_run))
            if exc.kind in (ErrorKind.SERVER_UNAVAILABLE, ErrorKind.SERVER_ERROR) and prov == "evren":
                actions.append(("Durum İzleme", lambda: self.page_requested.emit("monitor")))
            card = ErrorCard(f"İstek başarısız (kayıt #{error_id}) — {exc.kind.value}", lines, actions)
            self.transcript.add(card)
            if exc.kind == ErrorKind.UNKNOWN_RESULT:
                self._query_unknown(exc, card)
        else:
            self.transcript.add(ErrorCard("Beklenmeyen yerel hata", [f"{type(exc).__name__}: {exc}"],
                                          [("Yeniden dene", self.start_run)]))
        self.transcript.scroll_to_bottom()

    def _retry_confirm(self) -> None:
        if QMessageBox.question(
            self, "Belirsiz sonuç",
            "Önceki isteğin sunucuda tamamlanıp tamamlanmadığı bilinmiyor. Yeniden göndermek "
            "aynı işi iki kez yaptırabilir. Yine de yeniden denensin mi?",
        ) == QMessageBox.Yes:
            self.start_run()

    def _query_unknown(self, exc: ApiError, card: ErrorCard) -> None:
        provider = self.ctx.provider_of(exc.model or self.model)

        def job():
            client = self.ctx.make_client_for(provider)
            try:
                return client.resolve_unknown_request(exc.request_id)
            finally:
                client.close()

        def done(status):
            terminal = status.get("execution_terminal", "unknown")
            note = status.get("note", "")
            card.append_line(f"\nİstek durumu: {terminal}" + (f" — {note}" if note else ""))

        Task(job, on_done=done, on_error=lambda e: card.append_line(
            "\nİstek durumu sorgulanamadı; sonuç belirsiz kaldı.")).start()

    # ---- özetleme ----

    def compact(self, focus: str | None = None, auto: bool = False, reason: str = "",
                then=None, on_cancel=None) -> None:
        """Konuşmayı özetler. auto=True: otomatik (eşik); then: özet sonrası devam."""
        if not self.session_id or (self.running and not auto):
            self._note("Özetlenecek bir oturum yok veya ajan çalışıyor.")
            return
        msgs = self.ctx.db.get_session_messages(self.session_id)
        # Otomatik özette tek bir dev araç çıktısı bile bağlamı doldurabilir: 2 mesaj yeter
        if len(msgs) < (2 if auto else 4):
            if then:
                then()
            else:
                self._note("Konuşma henüz özetlenecek kadar uzun değil.")
            return
        model = self._summary_model()
        sid = self.session_id
        info = self.ctx.model_info(model)
        ctx_tokens = info.context_length if info else self._context_tokens()
        self.running = True
        self.composer.set_running(True)
        self.cancel_token = CancelToken()
        token = self.cancel_token
        label = "Bağlam otomatik özetleniyor" if auto else "Konuşma özetleniyor"
        self.composer.set_run_status(f"{model}  {label.lower()}" + (f"  ·  {reason}" if reason else ""))
        waiting = AssistantMessageWidget("otomatik özet" if auto else "özet")
        waiting.start_waiting(label)
        waiting.start_clock(model)
        self.transcript.add(waiting)
        t0 = time.monotonic()

        def finish_ui():
            waiting.deleteLater()
            self.running = False
            self.composer.set_running(False)

        def job():
            client = self.ctx.make_client_for(self.ctx.provider_of(model))
            try:
                return summarize(client, model, msgs, focus=focus, context_tokens=ctx_tokens, cancel=token)
            finally:
                client.close()

        def done(result):
            finish_ui()
            if token.cancelled:
                # Kullanıcı Esc'ye bastı: özet kaydedilse de bekleyen iş başlatılmaz
                if (result.content or "").strip() and result.finish_reason != "cancelled_by_user":
                    self.ctx.db.add_session_message(sid, "summary", result.content.strip(),
                                                    model=result.routed_model or model,
                                                    meta={"auto": auto, "reason": reason} if reason else {"auto": auto})
                    self.render_history(self.ctx.db.get_session_messages(sid))
                self._note("Durduruldu. Mesajınız gönderilmedi.", "stop")
                if on_cancel:
                    on_cancel()
                return
            if result.finish_reason == "cancelled_by_user" or not (result.content or "").strip():
                self._note("Özet oluşturulamadı" + ("; özetsiz devam ediliyor (eski araç çıktıları "
                                                    "kısaltılarak gönderilir)." if then else "."), "alert")
                if then and result.finish_reason != "cancelled_by_user":
                    then()
                return
            self._record_cost(model, result.token_usage())
            meta = {"auto": auto, "duration_s": round(time.monotonic() - t0, 1)}
            if reason:
                meta["reason"] = reason
            if focus:
                meta["focus"] = focus
            self.ctx.db.add_session_message(sid, "summary", result.content.strip(),
                                            model=result.routed_model or model, meta=meta)
            self.render_history(self.ctx.db.get_session_messages(sid))
            self._update_context()
            if then:
                then()

        def fail(exc):
            finish_ui()
            if then:
                self._note(f"Otomatik özet başarısız ({exc}); özetsiz devam ediliyor.", "alert")
                then()
            else:
                self.transcript.add(ErrorCard("Özetleme başarısız", [str(exc)]))

        Task(job, on_done=done, on_error=fail).start()

    # ---- kapsam koruması (2026-10-17) ----

    def _offer_plan(self) -> None:
        """"Önce plan" turunun sonunda: Uygula / Vazgeç."""
        def apply() -> None:
            self._skip_plan_once = True
            self.send("Plan onaylandı. Yalnız plandaki değişiklikleri uygula.")

        card = ActionCard("Plan hazır — uygulansın mı?",
                          ["Ajan henüz hiçbir dosyayı değiştirmedi. Planı değiştirmek isterseniz "
                           "Vazgeç'e basıp ne istediğinizi yazın."],
                          [("Uygula", apply, "primary"),
                           ("Vazgeç", lambda: self._note("Plan uygulanmadı.", "stop"), "ghost")],
                          icon_name="map")
        self.transcript.add(card)
        self.transcript.scroll_to_bottom()

    def _turn_rows(self, turn_id: int | None) -> list:
        if not self.session_id or turn_id is None:
            return []
        return [r for r in self.ctx.db.list_file_changes(self.session_id)
                if r["turn_id"] == turn_id and not r["reverted"]]

    def _turn_review(self, turn_id: int | None) -> None:
        """Tur sonu: değişen dosyalar + "Turu geri al"; ayar açıksa kapsam denetimi."""
        rows = self._turn_rows(turn_id)
        if not rows:
            return
        paths = list(dict.fromkeys(r["path"] for r in rows))
        sid = self.session_id

        def revert(selected: list[str] | None = None, label: str = "Tur") -> None:
            todo = [r for r in self._turn_rows(turn_id) if selected is None or r["path"] in selected]
            errors = self.panel.changes.revert_rows(todo)
            self._update_context()
            if errors:
                self.transcript.add(ErrorCard("Bazı değişiklikler geri alınamadı", errors))
            else:
                self._note(f"{label} geri alındı: {len(todo)} değişiklik "
                           f"({', '.join(dict.fromkeys(r['path'] for r in todo))}).", "undo")

        card = ActionCard(f"Bu tur {len(paths)} dosyayı değiştirdi",
                          [f"• {p}" for p in paths],
                          [("Turu geri al", lambda: revert(None, "Tur"), "ghost")],
                          icon_name="file")
        self.transcript.add(card)
        self.transcript.scroll_to_bottom()
        if not self.ctx.settings.scope_check:
            return
        card.append_line("Kapsam denetleniyor…")
        msgs = self.ctx.db.get_session_messages(sid)
        requests = [split_attachments(m["content"] or "")[0] for m in msgs
                    if m["role"] == "user" and not (m.get("meta") or {}).get("auto_continue")]
        changes = [{"path": r["path"], "before_text": r["before_text"], "after_text": r["after_text"]}
                   for r in rows]
        wanted = (self.ctx.settings.scope_check_model or "").strip()
        ids = [m.id for m in self.ctx.chat_models()]
        model = wanted if wanted and (not ids or wanted in ids) else self._concrete_model("inceleme")
        info = self.ctx.model_info(model)
        provider = self.ctx.provider_of(model)
        extra = ({"reasoning_effort": "none"} if provider == "evren" and info
                 and (info.capabilities or {}).get("reasoning_effort") else None)

        def job():
            client = self.ctx.make_client_for(provider, log_sink=lambda m: None)
            try:
                return scope.check(client, model, requests, changes, extra)
            finally:
                client.close()

        def done(found) -> None:
            if sid != self.session_id:
                return
            card.set_lines([f"• {p}" for p in paths])
            if not found:
                card.append_line("✓ Kapsam denetimi: istenmemiş değişiklik görülmedi.")
                return
            out_paths = [o.path for o in found]
            warn = ActionCard(
                f"İstenmemiş olabilecek değişiklik: {len(found)} dosya",
                [f"• {o.path} — {o.reason or 'isteğinizle ilgisi görülmedi'}" for o in found]
                + ["Bunları siz istemediyseniz geri alabilirsiniz (denetim bir modele dayanır, yanılabilir)."],
                [("Kapsam dışını geri al", lambda: revert(out_paths, "Kapsam dışı değişiklikler"), "danger"),
                 ("Sorun yok", lambda: None, "ghost")],
                icon_name="alert", warn=True)
            self.transcript.add(warn)
            self.transcript.scroll_to_bottom()

        def fail(exc) -> None:
            if sid == self.session_id:
                card.set_lines([f"• {p}" for p in paths] + [f"Kapsam denetimi yapılamadı: {exc}"])

        Task(job, on_done=done, on_error=fail).start()

    # ---- ortam denetimi (eksik program) ----

    def _warn_self_source(self, ws: str) -> None:
        """Proje klasörü EVREN Studio'nun KENDİ kaynak kodu ise bir kez uyar (oturum başına).

        2026-10-19: uygulamanın ajanı kendi kaynağına hatalı bir değişiklik yaptı
        (main_window'da Windows'ta çöken `time.strftime('%f')`); uygulama açılmaz oldu ve
        sorun uygulamayla düzeltilemedi."""
        import evren_studio

        app_root = Path(evren_studio.__file__).resolve().parents[2]
        try:
            same = Path(ws).resolve() == app_root
        except OSError:
            same = False
        key = ("self", self.session_id)
        if not same or key in getattr(self, "_self_warned", set()):
            return
        self._self_warned = getattr(self, "_self_warned", set()) | {key}
        self.transcript.add(NoteWidget(
            "Dikkat: bu klasör EVREN Studio'nun kendi kaynak kodu. Ajanın yapacağı hatalı bir değişiklik "
            "uygulamayı açılmaz hâle getirebilir ve o zaman sorunu uygulamayla düzeltemezsiniz. Önce bir "
            "git dalı açın (git checkout -b deneme); uygulama açılmazsa değişiklikleri `git stash` ile "
            "kenara alıp yeniden açın.", "alert"))

    def _env_check(self, ws: str | None) -> None:
        """Proje klasörünün gerektirdiği programları arka planda denetler (R-04).

        Eksik varsa: Ayarlar > Eksik program kurulumu "otomatik" → hemen kurulur,
        "manuel" → Kur / Şimdi değil kartı (kullanıcı kararı 2026-10-17).
        """
        if not ws or not Path(ws).is_dir():
            return
        self._warn_self_source(ws)
        key = (self.session_id, str(Path(ws)).lower())
        if key in self._env_checked:
            return
        self._env_checked.add(key)
        sid = self.session_id

        def done(statuses) -> None:
            if sid != self.session_id or not statuses:
                return
            missing = [st for st in statuses if not st.installed]
            if not missing:
                self._note("Ortam denetimi: " + environment.status_line(statuses), "check")
                return
            auto = self.ctx.settings.install_mode == "otomatik"
            lines = [f"• {st.title} — gerekli ({st.reason}); kurulum: {environment.short_plan(st.key)}"
                     for st in missing]
            present = [st for st in statuses if st.installed]
            if present:
                lines.append("Kurulu olanlar: " + environment.status_line(present))
            n = len(missing)
            title = (f"Eksik program{'lar' if n > 1 else ''} otomatik kuruluyor (Ayarlar: Otomatik)" if auto
                     else f"Bu proje için {n} program gerekli ve bilgisayarda kurulu değil. Kurulsun mu?")
            card = InstallCard(title, lines, ask=not auto)
            self.transcript.add(card)
            keys = [st.key for st in missing]
            if auto:
                self._env_install(card, keys)
            else:
                card.install_requested.connect(lambda: self._env_install(card, keys))

        Task(lambda: environment.check(Path(ws)), on_done=done, on_error=lambda _e: None).start()

    def _env_install(self, card: InstallCard, keys: list[str]) -> None:
        card.set_title("Programlar kuruluyor… (birkaç dakika sürebilir)")

        def done(results) -> None:
            for r in results:
                title = environment.KNOWN_TOOLS[r.key].title if r.key in environment.KNOWN_TOOLS else r.key
                if r.ok:
                    text = f"✓ {title} kuruldu" + (f" ({r.version})" if r.version else "")
                    if r.needs_restart:
                        text += " — bulunamazsa EVREN Studio'yu yeniden başlatın"
                else:
                    last = (r.output or "").strip().splitlines()
                    text = f"✗ {title} kurulamadı — {last[-1][:160] if last else r.command}"
                card.append_line(text)
            ok = all(r.ok for r in results)
            card.set_title("Kurulum tamamlandı" if ok else "Kurulumda sorun çıktı")
            if self.runner is not None:
                self.runner._env_section = None

        def fail(exc) -> None:
            card.set_title("Kurulum başarısız")
            card.append_line(str(exc))

        Task(lambda: [environment.install(k) for k in keys], on_done=done, on_error=fail).start()

    def _auto_continue(self) -> None:
        """Güvenli noktada duran turu özetten sonra otomatik sürdürür."""
        if not self.session_id:
            return
        self.ctx.db.add_session_message(self.session_id, "user", prompts.AUTO_CONTINUE_PROMPT,
                                        meta={"auto_continue": True})
        self.transcript.add(NoteWidget("Bağlam özetlendi; ajan kaldığı yerden otomatik devam ediyor.",
                                       "refresh"))
        self.start_run()

    def shutdown(self) -> None:
        if self.running and self.cancel_token is not None:
            self.cancel_token.cancel()
            for req in self._pending_approvals:
                req.resolve(ApprovalRequest.DENY)


def _parse_args(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw) if raw else {}
        return v if isinstance(v, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
