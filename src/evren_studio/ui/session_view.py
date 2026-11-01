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

from ..agent import environment, modelstats, prompts, scope
from ..agent.compaction import MAX_AUTO_RESUMES, CompactPolicy, history_tokens, needs_compaction, summarize

PLAN_AUTO_CONTINUES = 2      # plan bekçisi: kullanıcı mesajı başına adım sınırı sonrası otomatik devam
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
from ..agent import architect, learnings, router, userrules
from ..agent import resume
from ..agent.quota import QuotaGate
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
    ChoiceCard,
    ErrorCard,
    InstallCard,
    NoteWidget,
    QuotaResumeCard,
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
# F5 #6 ölçümü (2026-10-24, gerçek pencere): açılış ≤ 0,6 sn (4000 mesaj), ama "önceki mesajlar" HEPSİNİ çizince
# 1600 mesaj 17 sn, 4000 mesaj 67 sn donuyordu → her tıklamada bu kadar daha (sayfa sayfa).
HISTORY_PAGE = 60
ATTACH_OPEN = "<ekli_dosyalar>"
ATTACH_CLOSE = "</ekli_dosyalar>"
MENTION_RE = re.compile(r"(?<!\S)@([^\s]+)")
MAX_ATTACH_BYTES = 100 * 1024


TITLE_SYSTEM = ("Bir sohbet oturumuna başlık veriyorsun. Yalnızca başlığı yaz: Türkçe, 3-6 kelime, "
                "tırnak, nokta, emoji veya açıklama yok.")
ERROR_SYSTEM = ("Bir masaüstü yapay zekâ uygulamasında kullanıcının aldığı API/ajan hatasını açıklıyorsun. "
                "Sade Türkçeyle, teknik olmayan birine: 1) ne olduğunu 1-2 cümleyle, 2) en olası nedeni, "
                "3) şimdi yapabileceği en fazla 3 adımı yaz. API anahtarı veya gizli bilgi isteme; uydurma "
                "bilgi verme, emin değilsen söyle. En fazla 8 satır.")


def clean_title(text: str) -> str:
    t = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    t = t.strip().strip('"').strip("'").strip("“”").rstrip(".").strip()
    if t.lower().startswith("başlık:"):
        t = t.split(":", 1)[1].strip()
    return t[:60]


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
        kt = QLabel("Henüz API anahtarı yok. Ücretsiz EVREN anahtarınızı (önerilir) veya OpenAI / "
                    "Anthropic anahtarınızı Ayarlar'dan girin; anahtarlar Windows Credential Manager'da saklanır.")
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
        self.key_card.setVisible(not self.ctx.available_providers())

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
                item.widget().hide()          # silinmeyi beklerken yeni kartların üstüne binmesin
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
        self._services: dict[str, object] = {}     # proje klasörü → ServiceManager (arka plan servisleri)
        self.keep_services = False                 # QA çalışması: senaryolar arası servisler açık kalır
        # Uzun iş bitince (sonucu model wait_job ile almadıysa) not + Windows bildirimi
        self._job_timer = QTimer(self)
        self._job_timer.setInterval(5000)
        self._job_timer.timeout.connect(self._check_jobs)
        self._job_timer.start()
        from .project_ui import ProjectController

        self.project = ProjectController(self)
        self.project.notify.connect(self.notify.emit)
        from .qa_ui import QaController

        self.qa = QaController(self)
        self.qa.notify.connect(self.notify.emit)
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
        self._plan_continues = 0        # plan bekçisi: adım sınırından sonra otomatik devam sayısı
        self._project_offered: set[int] = set()   # Proje ajanı önerisi gösterilen metinler (hash)
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
        # Madde 2: dosya/görsel sohbet alanının HER YERİNE bırakılabilir (yalnız yazma kutusu değil)
        self.setAcceptDrops(True)
        self._drop_hint = QLabel("Bırakın: dosyalar ek olarak eklenir", self)
        self._drop_hint.setObjectName("DropHint")
        self._drop_hint.setAlignment(Qt.AlignCenter)
        self._drop_hint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._drop_hint.hide()
        self.composer.usage_btn.refresh_requested.connect(self.refresh_usage)
        self.composer.usage_btn.details_requested.connect(lambda: self.page_requested.emit("usage"))
        self._quota = None
        self._resume_timer: QTimer | None = None      # kota sonrası otomatik devam (agent/resume.py)
        self._resume_card: QuotaResumeCard | None = None
        self._run_gate = None
        self.profile: str | None = None         # F4/E5: oturumun ajan profili (sessions.profile)
        self._rules_asked: set = set()          # E4: bu açılışta sorulan kural dosyaları (tekrar sorma)
        # A6: kolay işte (hızlı motor) tur başarısız olduysa veya kullanıcı "olmadı" derse güçlü motora yüksel
        self._kolay_fail = False
        self._last_route_role = ""
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
        from .deep_ui import DeepController

        self.deep = DeepController(self)
        self._pending_model_note = ""
        ctx.on_model_list_change(self._on_model_list_change)
        self.deep.notify.connect(self.notify.emit)
        self.composer.set_deep(ctx.settings.deep_mode)
        self.composer.deep_toggled.connect(self.deep.set_enabled)
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
        # F4/E5: ajan profili (model, mod, skill'ler, ek talimat) — tıklayınca seçim menüsü
        self.profile_chip = QToolButton()
        self.profile_chip.setProperty("variant", "chip")
        self.profile_chip.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.profile_chip.setIcon(icons.icon("bulb", size=15))
        self.profile_chip.setIconSize(QSize(15, 15))
        self.profile_chip.setPopupMode(QToolButton.InstantPopup)
        self.profile_menu = QMenu(self.profile_chip)
        self.profile_menu.aboutToShow.connect(self._fill_profile_menu)
        self.profile_chip.setMenu(self.profile_menu)
        h.addWidget(self.profile_chip)
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
        has_profiles = bool(self.profile) or bool(self.ctx.db.list_profiles())
        self.profile_chip.setText(f"Profil: {self.profile}" if self.profile else "Profil seç")
        self.profile_chip.setToolTip("Ajan profili: tercih edilen motor, çalışma modu, etkin skill'ler ve ek talimat. "
                                     "Skill'ler sayfasından düzenlenir.")
        self.profile_chip.setVisible(has_profiles)
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
                        key=lambda m: (m.id != router.AUTO_PRO_ID, m.provider != "evren", m.id != "auto"))
        for m in models:
            desc = []
            if m.supports_tools:
                desc.append("araç")
            if m.supports_vision:
                desc.append("görsel")
            if m.context_length:
                desc.append(f"{m.context_length // 1000}k")
            if m.id == router.AUTO_PRO_ID:
                provs = self.ctx.available_providers()
                scope = (" + ".join(sorted({"evren": "EVREN", "openai": "OpenAI", "anthropic": "Anthropic"}[p]
                                           for p in provs)) or "EVREN")
                desc = [f"önerilen · işe göre motor seçer ({scope})"]
            elif m.id == "auto":
                desc = ["EVREN sunucusu seçer · her istekte değişebilir"]
            if m.provider != "evren":
                desc = [d for d in desc if d != "araç"] + [price_hint(m.id)]
            group = "otomatik" if m.id == router.AUTO_PRO_ID else m.provider
            items.append((m.id, " · ".join(d for d in desc if d), m.supports_tools, group, True))
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
        self._kolay_fail, self._last_route_role = False, ""
        self.profile = None
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

    def clear_session(self) -> None:
        """/clear: aynı proje klasörü, model, mod ve profille temiz sayfa (Claude Code'daki gibi).

        Eski oturum SİLİNMEZ (kenar çubuğunda kalır); yeni oturum ilk mesajla oluşur ve
        modele eski geçmiş gitmez. Kullanıcı isteği 2026-10-29: 1M token'a ulaşan oturumda
        /compact da çalışmayınca çıkış yolu yoktu.
        """
        if self.running:
            QMessageBox.information(self, "Ajan çalışıyor", "Önce çalışan işlemi durdurun (Esc).")
            return
        if not self.session_id:                  # karşılama ekranında temizlenecek bir şey yok
            self.composer.focus()
            return
        ws = self.workspace if self.workspace and Path(self.workspace).is_dir() else None
        model, mode, profile = self.model, self.mode, self.profile
        old = self.ctx.db.get_session(self.session_id)
        old_title = (old["title"] if old else "") or "oturum"
        # Kullanıcı geri bildirimi 2026-10-29: önceki sürüm karşılama ekranına atıyordu. Artık yeni
        # oturum HEMEN oluşturulup açılır; kullanıcı aynı proje sohbet ekranında kalır.
        sid = self.ctx.db.create_session(model, ws, mode, title=f"{old_title[:50]} · temiz sayfa",
                                         provider=self.ctx.provider_of(model))
        self.open_session(sid)
        if profile and self.ctx.profile(profile) is not None:
            self.apply_profile(profile)          # önce profil; sonra o an kullanılan model/mod korunur
        self.set_model(model)
        self.composer.set_model(model)
        self.set_mode(mode)
        self.composer.set_mode(mode)
        self.sessions_changed.emit()
        self._note(f"Temiz sayfa: önceki sohbet (“{old_title[:60]}”) modele gönderilmez; kenar "
                   "çubuğunda duruyor. Aynı klasör, model ve modla devam ediyorsunuz.", "refresh")
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
        if session_id != self.session_id:
            self._kolay_fail, self._last_route_role = False, ""
        self.session_id = session_id
        self.workspace = row["workspace"]
        self.mode = normalize_mode(row["mode"])
        self.profile = row["profile"] if "profile" in row.keys() else None
        self.model = router.normalize_model_id(row["model"])
        if self.model != row["model"]:
            self.ctx.db.update_session(session_id, model=self.model)
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

    def render_history(self, messages: list[dict], show_all: bool = False, window: int | None = None) -> None:
        """Oturum geçmişini çizer.

        PERFORMANS (2026-10-17): 200 mesajlık oturum açılışı ~30 sn sürüyordu. Artık
        çizim sırasında ekran güncellemesi askıya alınır ve uzun oturumlarda yalnız son
        HISTORY_WINDOW mesaj (bir kullanıcı mesajı sınırından) çizilir; üstte "Önceki
        mesajları göster" düğmesi tümünü açar. Modele giden geçmiş DEĞİŞMEZ.
        """
        self._history_window = window or HISTORY_WINDOW
        self.transcript.setUpdatesEnabled(False)
        try:
            self._render_history(messages, show_all)
        finally:
            self.transcript.setUpdatesEnabled(True)

    def _render_history(self, messages: list[dict], show_all: bool) -> None:
        self.transcript.clear()
        self.tool_widgets.clear()
        hidden = 0
        win = getattr(self, "_history_window", HISTORY_WINDOW)
        if not show_all and len(messages) > win:
            start = len(messages) - win
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
        try:
            marked = self.ctx.db.marked_bad_messages()      # A5: işaretli yanıt yeniden işaretlenmesin
        except Exception:
            marked = set()

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
                w.rewind_requested.connect(self.rewind_to)
                self.transcript.add(w)
                last_assistant = None
            elif role == "assistant":
                meta = m.get("meta") or {}
                shown = model_display(m.get("model"), meta.get("routed_model"), meta.get("requested_model"))
                w = AssistantMessageWidget(shown, agentic)
                w.finalize(m["content"] or "", m.get("reasoning") if self.ctx.settings.show_reasoning else None,
                           meta.get("finish_reason"), shown, meta.get("duration_s"))
                self._bind_feedback(w, m, marked)
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
        b = QPushButton(f"Önceki mesajlardan {min(count, HISTORY_PAGE)} tane daha göster ({count} gizli)")
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
        self.render_history(self.ctx.db.get_session_messages(self.session_id),
                            window=getattr(self, "_history_window", HISTORY_WINDOW) + HISTORY_PAGE)
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
        if self.profile:
            self.ctx.db.update_session(sid, profile=self.profile)
        # İlk yanıttan sonra yapay zekâyla kısa başlık üretilecek (proje oturumları hariç)
        self._auto_title = None if title.startswith("Proje:") else (sid, title, first_text.strip()[:1500])
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
        avail = self.ctx.available_model_ids()
        if wanted and wanted in avail:
            return wanted
        if not wanted and not router.is_auto_pro(self.model):
            return self.model
        return self.ctx.ai_route("ozet").model or self.model

    def _concrete_model(self, role: str = "sohbet") -> str:
        """Oturum modeli EVREN Akıllı ise o rol için seçilen gerçek model; değilse kendisi."""
        if not router.is_akilli(self.model):
            return self.model
        return self._route(role=role).model

    def _route(self, history: list | None = None, role: str | None = None) -> "router.Route":
        avail = self.ctx.available_model_ids()
        health = {}
        try:
            health = {r["model"]: dict(r) for r in self.ctx.db.all_model_health()}
        except Exception:
            pass
        if role:
            return self.ctx.ai_route(role, reason="yardımcı iş")
        history = history or []
        last_user = next((m for m in reversed(history) if m.get("role") == "user"), None)
        has_images = bool(((last_user or {}).get("meta") or {}).get("images"))
        est = estimate_tokens(to_api_messages("", history, "native")) if history else 0
        context_of = {m.id: m.context_length or 0 for m in self.ctx.chat_models()}
        agentic = self.workspace is not None
        level = lreason = kind = kreason = ""
        if self.ctx.settings.autopro_smart:
            # "devam" gibi otomatik mesajlar işin kendisi değildir: son GERÇEK kullanıcı isteğine bakılır
            real = next((m for m in reversed(history) if m.get("role") == "user"
                         and not (m.get("meta") or {}).get("auto_continue")), None)
            text = (real or {}).get("content") or ""
            if agentic:
                level, lreason = modelstats.difficulty(text)
                if level == "kolay" and (self._kolay_fail or (self._last_route_role == "kod_kolay"
                                                               and modelstats.is_complaint(text))):
                    level, lreason = "normal", "kolay işte önceki deneme olmadı → güçlü motor"
            kind, kreason = modelstats.task_kind(text, agentic=agentic, files=self._ws_names())
        return router.route(agentic=agentic,
                            mode=("plan" if self._plan_turn else self.mode), has_images=has_images,
                            est_tokens=est, context_of=context_of, available=avail or None, health=health,
                            level=level, level_reason=lreason, kind=kind, kind_reason=kreason,
                            penalties=self.ctx.model_penalties())

    def _ws_names(self) -> list[str]:
        """İş türü (A7) için proje dosya adları: kök + bir alt düzey, en çok ~600 ad; 60 sn önbellek."""
        if not self.workspace:
            return []
        now = time.monotonic()
        c = getattr(self, "_ws_names_cache", None)
        if c and c[0] == self.workspace and now - c[1] < 60:
            return c[2]
        names: list[str] = []
        skip = {"node_modules", "venv", ".venv", "__pycache__", ".git", "build", "dist"}
        try:
            for e in Path(self.workspace).iterdir():
                names.append(e.name)
                if e.is_dir() and e.name not in skip and not e.name.startswith("."):
                    for i, x in enumerate(e.iterdir()):
                        if i >= 200:
                            break
                        names.append(x.name)
                if len(names) > 600:
                    break
        except OSError:
            pass
        self._ws_names_cache = (self.workspace, now, names)
        return names

    def _route_explain(self, model: str, fallbacks: list[str]) -> str:
        """A12: çalışma çubuğu ipucu — neden bu motor ve bugünkü ölçümü."""
        r = getattr(self, "_run_route", None)
        lines = []
        if r is not None:
            lines.append(f"Auto Pro seçimi: {model} — rol: {router.ROLE_LABELS.get(r.role, r.role)}"
                         + (f" ({r.reason})" if r.reason else ""))
        else:
            lines.append(f"Motor: {model}")
        try:
            st = modelstats.summary(self.ctx.db.recent_model_calls(modelstats.WINDOW_HOURS)).get(model)
        except Exception:
            st = None
        if st and st.get("calls"):
            lines.append(f"Son {modelstats.WINDOW_HOURS} saat: {st['calls']} çağrı, hata %{int(st['error_rate'] * 100)}"
                         + (f", ~{st['tps']} token/sn" if st.get("tps") else "")
                         + (f", ilk yanıt ~{st['first_chunk_s']} sn" if st.get("first_chunk_s") else ""))
        else:
            lines.append("Bugün için ölçüm yok (hız kuralı yeterli örnek birikince devreye girer).")
        if fallbacks:
            lines.append("Yedekler: " + " → ".join(fallbacks))
        return "\n".join(lines)

    def _window(self, msgs: list | None = None) -> tuple[int | None, str]:
        """(bağlam penceresi, model adı). Auto Pro bir model değildir, kendi penceresi yoktur:
        sıradaki tur için seçilecek modelin ve yedeklerinin EN KÜÇÜĞÜ alınır (yedeğe geçilse de
        bağlam sığsın). Önceden sabit 1M yazılıydı; 100k özet eşiği göstergede "%10" görünüyordu."""
        if router.is_auto_pro(self.model):
            if msgs is None:
                msgs = self.ctx.db.get_session_messages(self.session_id) if self.session_id else []
            r = self._route(msgs)
            sizes = [(i.context_length, m) for m in [r.model, *r.fallbacks]
                     if (i := self.ctx.model_info(m)) and i.context_length]
            if not sizes:
                return None, r.model
            return min(sizes)[0], r.model
        info = self.ctx.model_info(self.model)
        return (info.context_length if info else None), self.model

    @staticmethod
    def _last_user_text(history: list) -> str:
        last = next((m for m in reversed(history or []) if m.get("role") == "user"), None)
        return str((last or {}).get("content") or "")

    def _context_tokens(self) -> int | None:
        return self._window()[0]

    def _update_context(self) -> None:
        if not self.session_id:
            self.composer.set_context(0, None)
            return
        msgs = self.ctx.db.get_session_messages(self.session_id)
        ctx_tokens, model = self._window(msgs)
        policy = self._policy()
        self.composer.set_context(estimate_tokens(to_api_messages("", msgs, "native")), ctx_tokens,
                                  policy.soft_limit(ctx_tokens) if policy.enabled else None,
                                  model=model)

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

    # ---- sürükle-bırak (oturum alanının tamamı) ----

    def _drop_ok(self, md) -> bool:
        from .composer import local_files

        return bool(local_files(md)) or md.hasImage()

    def _show_drop_hint(self, on: bool) -> None:
        if on:
            p = theme.current()
            self._drop_hint.setStyleSheet(
                f"#DropHint {{ background: {p.bg}; color: {p.text}; border: 2px dashed {p.accent};"
                f" border-radius: 14px; font-size: 15px; }}")
            self._drop_hint.setGeometry(self.rect().adjusted(16, 16, -16, -16))
            self._drop_hint.raise_()
        self._drop_hint.setVisible(on)

    def dragEnterEvent(self, e) -> None:
        if self._drop_ok(e.mimeData()):
            e.acceptProposedAction()
            self._show_drop_hint(True)
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e) -> None:
        if self._drop_ok(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dragLeaveEvent(self, e) -> None:
        self._show_drop_hint(False)
        super().dragLeaveEvent(e)

    def dropEvent(self, e) -> None:
        from PySide6.QtGui import QImage

        from .composer import local_files

        self._show_drop_hint(False)
        md = e.mimeData()
        files = local_files(md)
        if files:
            e.acceptProposedAction()
            self.add_files(files)
        elif md.hasImage() and isinstance(md.imageData(), QImage):
            e.acceptProposedAction()
            self.add_image(md.imageData())
        else:
            super().dropEvent(e)

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
        pending = self._pending_plan()
        if pending is not None and pending.session_id == self.session_id:
            self.cancel_auto_resume()       # kullanıcı kendisi sürdürüyor: bekleyen otomatik devam iptal
        if self.qa.active or self.qa.planning:
            self._note("QA ajanı çalışıyor; şu an ayrı mesaj gönderilemez. Durdurmak için "
                       "/qa-durdur yazın (veya Esc).", "alert")
            back()
            return
        if self.project.active or self.project.planning:
            self._note("Proje ajanı çalışıyor; şu an ayrı mesaj gönderilemez. Durdurmak için "
                       "/proje-durdur yazın.", "alert")
            back()
            return
        if self.deep.awaiting_answers and not atts:
            self.composer.set_text("")
            self.deep.answer(text)                  # soru kartının yanıtı mesaj kutusundan da verilebilir
            return
        if self.deep.active:
            self._note("Derin Mod çalışıyor; şu an ayrı mesaj gönderilemez. Durdurmak için Esc veya "
                       "/derin-durdur.", "alert")
            back()
            return
        if self.running:
            back()
            return
        if self.deep_on and not atts and self.edit_from is None:
            reason = self.deep.unavailable_reason()
            if not reason:
                self.composer.set_text("")
                self.deep.start(text)
                return
            self._note(reason + " Bu mesaj normal ajan turuyla gönderildi.", "alert")
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
        self._plan_continues = 0
        if self._pending_model_note:
            self._note(self._pending_model_note, "alert")
            self._pending_model_note = ""
        if self._offer_project(text, atts, back):
            return
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
        w.rewind_requested.connect(self.rewind_to)
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

    # ---- F6 / E1: konuşmayı geri sarma ---------------------------------------------------------

    UNDOABLE_TOOLS = {"run_command", "start_job", "start_service", "install_program", "web_fetch", "web_search"}

    def rewind_plan(self, message_id: int) -> dict:
        """Geri sarmanın etkisi (onay kartı ve testler için): silinecek mesajlar, geri alınacak değişiklikler,
        sonradan elle değişmiş dosyalar, geri alınamayacak araç etkileri."""
        from ..agent.tools import decode_bytes

        sid = self.session_id
        msgs = [m for m in self.ctx.db.get_session_messages(sid) if m["id"] >= message_id]
        rows = [r for r in self.ctx.db.list_file_changes(sid)
                if r["turn_id"] is not None and r["turn_id"] >= message_id and not r["reverted"]]
        last: dict[str, object] = {}
        for r in rows:
            last[r["path"]] = r
        conflicts = []
        for path, r in last.items():
            p = Path(self.workspace or ".") / path
            try:
                now = decode_bytes(p.read_bytes()).text if p.exists() else None
            except OSError:
                now = None
            if now != r["after_text"]:
                conflicts.append(path)
        effects = []
        for m in msgs:
            for c in m.get("tool_calls") or []:
                name = c.get("name") or ""
                if name in self.UNDOABLE_TOOLS or name.startswith("mcp__"):
                    try:
                        args = json.loads(c.get("arguments") or "{}") or {}
                    except (ValueError, TypeError):
                        args = {}
                    effects.append(f"{name}: {str(args.get('command') or args.get('name') or args.get('url') or '')[:90]}")
        project = any((m.get("meta") or {}).get("project_task") for m in msgs)
        return {"messages": len(msgs), "rows": rows, "paths": list(last), "conflicts": conflicts,
                "effects": effects, "project": project}

    def rewind_to(self, message_id: int, text: str = "") -> None:
        """Onay kartı → dosya değişikliklerini sondan başa geri al, bu mesaj ve sonrasını sil, metni kutuya koy."""
        if self.running or not self.session_id or not message_id:
            if self.running:
                self._note("Ajan çalışırken geri sarılamaz; önce durdurun (Esc).", "alert")
            return
        plan = self.rewind_plan(message_id)
        lines = [f"• {plan['messages']} mesaj silinecek (bu mesaj ve sonrası); mesaj metni yazı kutusuna geri konur."]
        if plan["paths"]:
            lines.append(f"• {len(plan['rows'])} dosya değişikliği geri alınacak: " + ", ".join(plan["paths"][:8])
                         + (" …" if len(plan["paths"]) > 8 else ""))
        else:
            lines.append("• Geri alınacak dosya değişikliği yok.")
        if plan["conflicts"]:
            lines.append("⚠ Sonradan elle değişmiş dosyalar (o değişiklikler de kaybolur): " + ", ".join(plan["conflicts"]))
        if plan["effects"]:
            lines.append("⚠ GERİ ALINAMAYACAK etkiler (komut, kurulum, servis, web): " + "; ".join(plan["effects"][:6])
                         + (" …" if len(plan["effects"]) > 6 else ""))
        if plan["project"]:
            lines.append("⚠ Proje ajanının yaptığı git commit'leri geri alınmaz (git geçmişinde kalır).")

        def go() -> None:
            self._do_rewind(message_id, text, plan)
        card = ActionCard("Buraya geri sarılsın mı?", lines,
                          [("Geri sar", go, "danger"), ("Vazgeç", lambda: None, "ghost")], icon_name="undo",
                          warn=True)
        self.transcript.add(card)
        self.transcript.scroll_to_bottom()

    def _do_rewind(self, message_id: int, text: str, plan: dict) -> None:
        from ..agent.tools import ToolError, revert_file

        sid, ws = self.session_id, self.workspace
        if self.running or sid is None:
            return
        errors = []
        for r in sorted(plan["rows"], key=lambda r: r["id"], reverse=True):
            try:
                revert_file(Path(ws), r["path"], r["before_text"], r["after_text"], force=True)
                self.ctx.db.mark_change_reverted(r["id"])
            except (ToolError, OSError) as exc:
                errors.append(f"{r['path']}: {exc}")
        if errors:
            self.panel.changes.refresh()
            self.transcript.add(ErrorCard("Geri sarma yarım kaldı — konuşma silinmedi", errors
                                          + ["Geri alınabilenler alındı; kalanları Değişiklikler panelinden deneyin."]))
            return
        atts = []
        for m in self.ctx.db.get_session_messages(sid):
            if m["id"] == message_id:
                atts = [Attachment.from_meta(d) for d in (m.get("meta") or {}).get("attachments") or []]
                break
        self.ctx.db.delete_session_messages_from(sid, message_id)
        self.edit_from = None
        self.render_history(self.ctx.db.get_session_messages(sid))
        self.panel.changes.refresh()
        self.panel.set_session(sid, ws, self.ctx.db.get_session_todos(sid))
        self._update_context()
        self.composer.set_text(text)
        if atts:
            self._restore_attachments(atts)
        self._note(f"Geri sarıldı: {plan['messages']} mesaj silindi, {len(plan['rows'])} dosya değişikliği geri "
                   "alındı." + (" Komut etkileri geri alınmadı." if plan["effects"] else ""), "undo")

    def _command(self, text: str) -> bool:
        cmd, _, arg = text.partition(" ")
        cmd = cmd.lower()
        if cmd not in SLASH_COMMANDS and cmd not in MODE_COMMANDS:
            return False
        if cmd.startswith("/proje"):
            self.project.command(cmd, arg)
            return True
        if cmd.startswith("/qa"):
            self.qa.command(cmd, arg)
            return True
        if cmd == "/derin-durdur":
            if (self.deep.active or self.deep.waiting_project
                    or getattr(self.deep, "_resume_timer", None) is not None):
                self.deep.stop()
            else:
                self._note("Çalışan bir Derin Mod akışı yok.", "spark")
            return True
        if cmd == "/derin":
            self.deep.command(arg)
            return True
        if cmd == "/yeni":
            self.new_session()
        elif cmd in ("/clear", "/temizle"):
            self.clear_session()
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
        elif cmd == "/profil":
            name = arg.strip()
            names = [p["name"] for p in self.ctx.db.list_profiles()]
            if not name:
                self._note("Profiller: " + (", ".join(names) or "(henüz yok — Skill'ler sayfasından ekleyin)")
                           + (f". Bu oturumda: {self.profile}" if self.profile else ""), "bulb")
            elif name.lower() in ("yok", "kaldır", "kaldir"):
                self.apply_profile(None)
            else:
                self.apply_profile(name)
        elif cmd == "/betiklestir":
            self.scriptify(arg.strip())
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
                  "- `Enter` gönder, `Shift+Enter` veya `Alt+Enter` yeni satır, `Esc` durdur",
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
                  model_override: tuple[str, list[str], str] | None = None, no_writes: bool = False,
                  extra_tools=None, final_marker: str | None = None) -> None:
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
        # A13: zor işte planlayan + yazan (ayar açıksa; planlayıcı "plan", yazan "kod_kolay" zincirinden)
        planner = None
        r0 = self._run_route
        if (model_override is None and r0 is not None and r0.role == "kod"
                and self.ctx.settings.autopro_smart):
            p_route, w_route = self.ctx.ai_route("plan"), self.ctx.ai_route("kod_kolay")
            if architect.wanted(enabled=self.ctx.settings.autopro_architect, auto_pro=True, agentic=self.workspace is not None,
                                mode=(mode_override or ("plan" if self._plan_turn else self.mode)), level=r0.level,
                                planner=p_route.model, writer=w_route.model):
                planner = p_route
                self._run_route = router.Route(w_route.model, "kod", f"{r0.reason} · planlayan {p_route.model}, "
                                               f"yazan {w_route.model}", list(w_route.fallbacks), r0.level)
                api_model, fallbacks = w_route.model, list(w_route.fallbacks)
        run_role = (model_override[2] if model_override is not None
                    else (self._run_route.role if self._run_route is not None else ""))
        self.composer.run_text.setToolTip(self._route_explain(api_model, fallbacks))
        row = self.ctx.db.get_session(sid)
        protocol = row["protocol"] if row and row["protocol"] else self.ctx.resolve_protocol(api_model)
        if self.ctx.settings.tool_protocol != "otomatik":
            protocol = self.ctx.resolve_protocol(api_model)
        # Yedekler turun sağlayıcısıyla sınırlı: istemci tur boyunca aynıdır; EVREN turu ücretli
        # modele (veya tersi) geçemez — MCP'nin ücretli modele ulaşmaması da bununla garanti.
        fallbacks = router.same_provider(fallbacks, api_model, self.ctx.provider_of)
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

        # A11: normal EVREN turunda da kota kapısı — 5 dk pencere %85 doluysa yenilenmesini bekler (token
        # harcamaz); günlük kota azsa DURDURMAZ, bir kez uyarır. Derin/Proje kendi kapısını kullanır.
        gate = (QuotaGate(self._fetch_quota) if provider == "evren" and s.quota_guard_turns
                and model_override is None else None)
        self._run_gate = gate
        warned: list[bool] = []

        def before_call(_step: int):
            if provider != "evren":
                return "budget" if self._budget_blocks(provider) else None
            if gate is None:
                return None
            low, reset = gate.daily_low()
            if low and s.auto_resume:
                # Kota bitince otomatik devam: model çağrısından ÖNCE dur (araç sonuçları kayıtlı, yarım iş yok);
                # kart + zamanlayıcı _on_done → _quota_pause'ta kurulur.
                return "quota_daily"
            if low and not warned:
                warned.append(True)
                b.sig_status.emit("Günlük EVREN kotası azaldı" + (f" (yenilenme: {reset})" if reset else "")
                                  + ". Tur sürüyor; uzun işleri kota yenilenince başlatmanız önerilir.")
            return gate.before_call(cancel=self.cancel_token, status=b.sig_status.emit, daily_blocks=False)
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
            before_model_call=before_call if (provider != "evren" or gate is not None) else None,
            # Boş yanıt (düşünme bütçesi tükendi) sonrası tek yeniden denemede düşünmeyi kapat;
            # yalnız EVREN kaydı reasoning_effort desteği bildiren modellerde.
            stall_retry_body=({"reasoning_effort": "none"}
                              if provider == "evren" and info and (info.capabilities or {}).get("reasoning_effort")
                              else None),
            install_mode=s.install_mode,
            fallback_models=fallbacks,
            # MCP (Ayarlar > MCP Sunucuları): yalnız EVREN turunda ve gerektiğinde; yoksa None
            mcp=(self.ctx.mcp_toolset(ws.root, self._last_user_text(history), provider,
                                      status=b.sig_status.emit)
                 if ws is not None else None),
            edit_check=s.edit_diagnostics,
            services=self.service_manager(ws.root) if ws is not None else None,
            jobs=self.ctx.jobs if ws is not None else None,
            test_check=s.test_check and not no_writes,
            no_writes=no_writes,
            extra_tools=extra_tools,
            final_marker=final_marker,
            # Plan bekçisi yalnız normal turlarda (Proje/QA/Derin akışları fazları zaten kodla sürer)
            plan_guard=s.plan_guard and model_override is None and not no_writes,
            # Auto Pro çekirdeği (A1/A3/A4): gerçek kullanım kaydı, o günkü normal hız, yavaşlık kuralı.
            # Proje/Derin/QA görevinde görev içi eşik ~3 kat (görevler arası geçişi bekleme süresi yapar).
            stats_sink=self.ctx.record_model_call,
            baselines=self.ctx.model_baselines() if fallbacks else None,
            slow_factor=(modelstats.FACTOR_TASK if model_override is not None else modelstats.FACTOR_TURN),
            route_role=run_role,
            # A10: tutarlılık (yalnız seed'i dinleyen modelde) · A7: rol talimatı (ör. veri → betikle hesapla)
            base_body=router.consistent_body(run_role, api_model),
            extra_hint="\n\n".join(h for h in (router.ROLE_HINTS.get(run_role, ""), self._profile_hint()) if h),
            project_map=s.project_map,
            skills=self._run_skills(ws.root if ws is not None else None),
            untrusted=list(s.untrusted_dirs or []),
            user_rules=self._user_rules(ws.root) if ws is not None else None,
            game_tools=self._wants_game_tools(ws.root if ws is not None else None, run_role, history),
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

        cancel = self.cancel_token
        ws_root = ws.root if ws is not None else None

        def job():
            try:
                if planner is not None and ws_root is not None:
                    self._architect_plan(client, planner, ws_root, history, runner, cancel, b)
                return runner.run(history)
            finally:
                client.close()

        Task(job, on_done=self._on_done, on_error=self._on_fail).start()

    def _bind_feedback(self, w: AssistantMessageWidget, msg: dict, marked: set | None = None) -> None:
        """A5: 👎 düğmesi — yalnız gerçek modelin yazdığı, içerikli yanıtta."""
        model = msg.get("model") or ""
        if not model or router.is_auto_pro(model) or not (msg.get("content") or "").strip():
            return
        w.api_model = model
        w.msg_id = int(msg.get("id") or 0)
        if marked and w.msg_id in marked:
            w.set_marked_bad()
        w.feedback_bad.connect(self._on_feedback_bad)

    def _on_feedback_bad(self, model: str, msg_id: int) -> None:
        self.ctx.record_feedback_bad(model, msg_id)
        pen = self.ctx.model_penalties().get(model)
        self._note(f"Yanıt kötü olarak işaretlendi ({model})."
                   + (f" Auto Pro bu motoru bugün sıralamada geri alıyor: {pen}." if pen else
                      " Aynı motor 24 saatte bir kez daha işaretlenirse Auto Pro onu sıralamada geri alır."))

    # ---- F4: profil, skill denetçisi, betikleştir ----------------------------------------------

    def _fill_profile_menu(self) -> None:
        m = self.profile_menu
        m.clear()
        for p in self.ctx.db.list_profiles():
            a = m.addAction(p["name"], lambda n=p["name"]: self.apply_profile(n))
            a.setCheckable(True)
            a.setChecked(p["name"] == self.profile)
        m.addSeparator()
        m.addAction("Profil yok", lambda: self.apply_profile(None))
        m.addAction("Profilleri düzenle…", lambda: self.page_requested.emit("skills"))

    def apply_profile(self, name: str | None) -> None:
        """Profilin motorunu ve modunu uygular, oturuma bağlar; skill'ler ve talimat sonraki turlarda kullanılır."""
        if name is None:
            self.profile = None
            if self.session_id:
                self.ctx.db.update_session(self.session_id, profile=None)
            self._update_header()
            if self.session_id:                  # karşılama ekranında _note modal kutu açar; çip yeterli
                self._note("Profil kaldırıldı.", "bulb")
            return
        prof = self.ctx.profile(name)
        if prof is None:
            self._note(f"Böyle bir profil yok: {name}. /profil ile listeyi görün.", "alert")
            return
        if prof.get("model") and prof["model"] in [m.id for m in self.ctx.chat_models()]:
            self.set_model(prof["model"])
            self.composer.set_model(self.model)
        if prof.get("mode"):
            self.set_mode(prof["mode"])
            self.composer.set_mode(self.mode)
        self.profile = prof["name"]
        if self.session_id:
            self.ctx.db.update_session(self.session_id, profile=self.profile)
        self._update_header()
        sk = prof.get("skills")
        if not self.session_id:                  # karşılama ekranı (ör. şablon): başlıktaki çip gösterir
            return
        self._note(f"Profil: {self.profile} — motor {prof.get('model') or '(değişmedi)'}, mod "
                   f"{MODES.get(normalize_mode(prof.get('mode') or self.mode), self.mode)}"
                   + (f", skill'ler: {', '.join(sk) or 'hiçbiri'}" if sk is not None else ", skill'ler: projedeki tümü"),
                   "bulb")

    def _run_skills(self, ws_root) -> list:
        return self.ctx.skills_for(str(ws_root), self.profile) if ws_root is not None else []

    def _profile_hint(self) -> str:
        prof = self.ctx.profile(self.profile)
        if not prof or not (prof.get("instructions") or "").strip():
            return ""
        return f"# Profil talimatı ({prof['name']}; kullanıcı tanımladı)\n{prof['instructions'].strip()[:4000]}"

    def scriptify(self, name: str = "") -> None:
        """F4 #14: oturumdaki işi tekrar çalıştırılabilir betiğe çevirme turu."""
        if not self.session_id or not self.workspace:
            self._note("Betikleştirmek için proje klasörlü ve en az bir iş yapılmış oturum gerekir.", "alert")
            return
        path = name if name.endswith(".py") else f"scripts/{(name or 'is_betigi').strip().replace(' ', '_')}.py"
        used = [s for s in self._run_skills(self.workspace) if s.checker]
        checker = (f"\n- Skill denetçisi var ({used[0].name}: {used[0].checker}); betiğin çıktısını onunla da doğrula."
                   if used else "")
        self.send(prompts.BETIKLESTIR_PROMPT.format(path=path, checker=checker))

    def _skill_check(self, used: list[str]) -> None:
        """F4 #13: bu turda okunan skill'lerin denetçisi varsa çalıştır (Otomatik modda sormadan, diğerlerinde kartla)."""
        if not used or not self.workspace or not self.session_id:
            return
        ws = self.workspace
        checks = [s for s in self._run_skills(ws) if s.name in used and s.checker]
        for s in checks:
            if normalize_mode(self.mode) == "auto":
                self._run_checker(s, ws)
            else:
                card = ActionCard(f"Skill denetçisi çalıştırılsın mı? ({s.name})",
                                  [f"Skill kendi doğrulama betiğini taşıyor: {s.checker}. Proje klasöründe çalışır, "
                                   "sonucu burada gösterir."],
                                  [("Çalıştır", lambda sk=s: self._run_checker(sk, ws), "primary"),
                                   ("Geç", lambda: None, "ghost")], icon_name="shield")
                self.transcript.add(card)
                self.transcript.scroll_to_bottom()

    def _run_checker(self, skill, ws: str) -> None:
        import subprocess as sp

        from ..agent import environment
        from ..agent.tools import project_env

        script = Path(skill.folder) / skill.checker
        py = environment.find_exe(environment.KNOWN_TOOLS["python"]) or "python"
        self._note(f"Skill denetçisi çalışıyor: {skill.name} ({skill.checker})…", "shield")

        def job():
            try:
                r = sp.run([py, str(script), ws], cwd=ws, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300, env=project_env(Path(ws)),
                           creationflags=getattr(sp, "CREATE_NO_WINDOW", 0))
                return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
            except sp.TimeoutExpired:
                return -9, "zaman aşımı (5 dk)"

        def done(res):
            code, out = res
            tail = "\n".join(out.splitlines()[-12:])[-1500:] or "(çıktı yok)"
            if code == 0:
                card = ActionCard(f"Skill denetçisi geçti: {skill.name}", [tail],
                                  [("Betikleştir", lambda: self.scriptify(""), "ghost")], icon_name="check")
            else:
                msg = (f"{skill.name} skill denetçisi ({skill.checker}) şu sorunları buldu (çıkış {code}). "
                       f"Düzelt ve denetçiyi yeniden çalıştırıp geçtiğini göster:\n```\n{tail}\n```")
                card = ActionCard(f"Skill denetçisi sorun buldu: {skill.name} (çıkış {code})", [tail],
                                  [("Ajana düzelttir", lambda: self.send(msg), "primary"),
                                   ("Geç", lambda: None, "ghost")], icon_name="alert", warn=True)
            self.transcript.add(card)
            self.transcript.scroll_to_bottom()

        Task(job, on_done=done, on_error=lambda e: self.transcript.add(
            ErrorCard("Skill denetçisi çalışamadı", [str(e)]))).start()

    def _user_rules(self, root: Path):
        """E4: projenin kural dosyası onaylıysa UserRules, değilse None (+ bir kez onay kartı)."""
        try:
            rules, digest = userrules.load(root)
        except userrules.RulesError as exc:
            key = ("hata", str(root), str(exc))
            if key not in self._rules_asked:
                self._rules_asked.add(key)
                self.transcript.add(ErrorCard("Kullanıcı kuralları okunamadı", [str(exc)]))
            return None
        if not rules:
            return None
        key = str(Path(root).resolve()).lower()
        approved = self.ctx.settings.approved_rules or {}
        if approved.get(key) == digest:
            return userrules.UserRules(Path(root), rules)
        if (key, digest) in self._rules_asked:
            return None
        self._rules_asked.add((key, digest))

        def allow() -> None:
            self.ctx.settings.approved_rules = {**(self.ctx.settings.approved_rules or {}), key: digest}
            self.ctx.save_settings()
            self._note("Kullanıcı kuralları onaylandı; sonraki turdan itibaren çalışır. Dosya değişirse yeniden "
                       "sorulur.", "check")
        title = ("Kullanıcı kuralları DEĞİŞTİ — çalıştırılsın mı?" if key in approved
                 else "Bu projede kullanıcı kuralları var — çalıştırılsın mı?")
        card = ActionCard(title, [f"• {r.describe()}" for r in rules]
                          + [f"Kaynak: {userrules.RULES_FILE}. Komutlar proje klasöründe çalışır; onaylamazsanız bu "
                             "turlar kuralsız sürer."],
                          [("İzin ver", allow, "primary"), ("Hayır", lambda: None, "ghost")], icon_name="shield",
                          warn=True)
        self.transcript.add(card)
        return None

    GAME_WORDS = re.compile(r"(?<![\w.])(?:godot|blender|3b|3d|model(?:i|ini|ler)?|fbx|obj|gltf|glb|poly ?haven|"
                            r"mod(?:u|unu|lar|ları)?|oyun(?:u|a|da)?|sahne|sprite|doku|hdri)(?![\w.])", re.I)

    def _wants_game_tools(self, root, role: str, history: list) -> bool:
        """F7: oyun/3B araçları (convert_model, Poly Haven) + Godot/Blender bilgisi yalnız gerektiğinde (token)."""
        if root is None:
            return False
        if role == "oyun" or (Path(root) / "project.godot").is_file():
            return True
        real = next((m for m in reversed(history or []) if m.get("role") == "user"
                     and not (m.get("meta") or {}).get("auto_continue")), None)
        return bool(self.GAME_WORDS.search((real or {}).get("content") or ""))

    def _fetch_quota(self):
        """Kota kapısı (A11) için; koşucu iş parçacığında çağrılır (R-04)."""
        client = self.ctx.make_client()
        try:
            return client.get_quota()
        finally:
            client.close()

    def _architect_plan(self, client, planner, root, history, runner, cancel, b) -> None:
        """A13 — İŞ PARÇACIĞINDA: planlayıcı motor salt okunur planı yazar, yazan motorun tur ipucuna eklenir.
        Plan alınamazsa iş plansız sürer (planlayıcı hatası turu bozmaz)."""
        real = next((m for m in reversed(history) if m.get("role") == "user"
                     and not (m.get("meta") or {}).get("auto_continue")), None)
        request = (real or {}).get("content") or ""
        b.sig_status.emit(f"Auto Pro planlayan + yazan: {planner.model} işi inceleyip planlıyor; "
                          f"ardından {runner.model} yazacak.")
        t0 = time.monotonic()
        info = self.ctx.model_info(planner.model)
        try:
            plan, res = architect.make_plan(client=client, model=planner.model, fallbacks=planner.fallbacks,
                                            root=root, request=request, cancel=cancel,
                                            context_tokens=info.context_length if info else None)
        except Exception as exc:                       # planlayıcı hatası yazanı durdurmasın
            plan, res = "", None
            b.sig_status.emit(f"Planlayıcı çalışamadı ({type(exc).__name__}); iş plansız sürüyor.")
        if getattr(cancel, "cancelled", False):
            return
        took = time.monotonic() - t0
        self.ctx.record_model_call({"model": getattr(res, "model", "") or planner.model, "role": "plan",
                                    "ok": bool(plan), "duration_s": round(took, 1),
                                    "error_kind": None if plan else "plan_yok"})
        if plan:
            runner.extra_hint = "\n\n".join(h for h in (runner.extra_hint, architect.hint(plan, planner.model)) if h)
            short = plan if len(plan) <= 900 else plan[:900] + " …"
            b.sig_status.emit(f"Plan hazır ({took:.0f} sn, {planner.model}):\n{short}")
        elif res is not None:
            b.sig_status.emit(f"Planlayıcı plan bloğu vermedi ({took:.0f} sn); iş plansız sürüyor.")

    def stop(self) -> None:
        if self.deep.active or getattr(self.deep, "_resume_timer", None) is not None:
            self.deep.stop()
            if self.running and not self.project.active:
                self._stop_run()
            return
        self._stop_run()

    def _stop_run(self) -> None:
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

    def _work_state(self) -> dict | None:
        """F5 #7: canlı iş paneli için durum (çalışmıyorsa None)."""
        if not self.running or self._run_t0 is None:
            return None
        model = self.runner.model if self.runner is not None else self.run_model
        route = getattr(self, "_run_route", None)
        flow = self.project.label or self.deep.label or self.qa.label or ""
        progress = ""
        st = getattr(self.project, "state", None)
        if self.project.active and st is not None:
            done = sum(1 for t in st.tasks if t.status == "bitti")
            progress = f"{done}/{len(st.tasks)} görev bitti"
        steps, tokens = [], 0
        if self.session_id and self._turn_id is not None:
            for m in self.ctx.db.get_session_messages(self.session_id):
                if m["id"] < self._turn_id:
                    continue
                meta = m.get("meta") or {}
                if m["role"] == "tool":
                    mark = "✗" if meta.get("error") else "✓"
                    dur = meta.get("duration_s")
                    steps.append(f"{mark} {meta.get('summary') or m.get('name') or '?'}"
                                 + (f" · {format_duration(float(dur))}" if dur else ""))
                elif m["role"] == "assistant":
                    tokens += int(((meta.get("usage") or {}).get("completion_tokens")) or 0)
        return {"title": "Ajan çalışıyor", "model": model,
                "role": router.ROLE_LABELS.get(route.role, route.role) if route is not None else "",
                "elapsed": format_duration(time.monotonic() - self._run_t0), "step": self._run_step,
                "activity": self._run_activity, "flow": flow, "progress": progress, "steps": steps,
                "tokens": tokens}

    def _tick_run(self) -> None:
        if not self.running or self._run_t0 is None:
            self.panel.work.update_state(None)
            return
        now = time.monotonic()
        if (self.panel.isVisible() and self.panel.stack.currentWidget() is self.panel.work
                and now - getattr(self, "_work_at", 0.0) >= 2.0):   # yalnız görünürken, 2 sn'de bir (DB okur)
            self._work_at = now
            self.panel.work.update_state(self._work_state())
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
        elif self.deep.label:
            parts.insert(0, self.deep.label)
        elif self.qa.label:
            parts.insert(0, self.qa.label)
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
            self._bind_feedback(self.current, msg)
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
        if self._quota is not None:             # F5 #5 tahmin: günlük kalan kota (son okunan)
            self.ctx.last_daily_remaining = getattr(self._quota, "daily_remaining_tokens", None)
        if self.session_id:
            for m in self.ctx.db.get_session_messages(self.session_id):
                u = (m.get("meta") or {}).get("usage") or {}
                s.session_in += int(u.get("input_tokens") or 0)
                s.session_out += int(u.get("output_tokens") or 0)
        prov = self.ctx.provider_of(self.model) if self.model else "evren"
        provs = self.ctx.available_providers()
        paid_provs = [p for p in provs if p != "evren"]
        if (prov in PROVIDERS and PROVIDERS[prov].paid) or (paid_provs and "evren" not in provs):
            st = self._budget_state()
            names = [PROVIDERS[p].name for p in sorted(paid_provs)] or [PROVIDERS[prov].name]
            s.paid_name, s.paid_spent, s.paid_limit = " + ".join(names), st.spent, st.limit
        return s

    def update_usage_view(self) -> None:
        self.composer.usage_btn.set_snapshot(self._usage_snapshot())

    def refresh_usage(self) -> None:
        """EVREN kotasını arka planda ister (R-04); sonuç düğmeye ve panele yazılır."""
        if self._usage_busy:
            return
        if not self.ctx.has_api_key():
            # EVREN yok: kota yok; düğme ücretli sağlayıcıların aylık tahmini harcamasını gösterir
            self._quota, self._quota_error = None, ("" if self.ctx.available_providers() else "API anahtarı yok")
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

    def service_manager(self, root):
        """Projenin arka plan servis yöneticisi (start_service/service_logs/stop_service)."""
        from ..agent.services import ServiceManager

        key = str(root).lower()
        if key not in self._services:
            self._services[key] = ServiceManager(root)
        return self._services[key]

    def _check_jobs(self) -> None:
        jm = getattr(self.ctx, "_jobs", None)
        if jm is None:
            return
        for job in jm.finished_unnotified():
            text = f"Uzun iş bitti: {job.id} — {job.state()}, {job.elapsed() / 60:.1f} dk. Çıktı: {job.log_path}"
            self._note(text, "check" if job.exit_code == 0 else "alert")
            self.notify.emit("EVREN Studio — uzun iş bitti", text[:200])

    def stop_services(self, quiet: bool = False) -> list[str]:
        stopped: list[str] = []
        for sm in self._services.values():
            stopped += sm.stop_all()
        if stopped and not quiet:
            self._note("Arka plan servisleri kapatıldı: " + ", ".join(stopped), "stop")
        return stopped

    def _finish(self) -> None:
        self.running = False
        if not self.keep_services:
            self.stop_services()        # tur bitti: ajanın başlattığı sunucular açık kalmasın
        self._run_timer.stop()
        self.panel.work.update_state(None)
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
        # _finish runner'ı ve başlangıç saatini siler: tur sonu işleri (ders, denetçi, zaman özeti) için önce al.
        # 2026-10-24: önceden getattr(self.runner, ...) _finish'ten SONRA okunuyordu → denetçi hiç çalışmıyordu.
        done_runner = self.runner
        turn_total = time.monotonic() - self._run_t0 if self._run_t0 is not None else 0.0
        self._finish()
        role = self._run_route.role if getattr(self, "_run_route", None) is not None else ""
        if role == "kod_kolay":
            self._kolay_fail = outcome.stopped != "done" or bool(getattr(outcome, "model_switches", None))
        elif role:
            self._kolay_fail = False
        self._last_route_role = role
        if getattr(outcome, "test_edits", None):
            self._note("Dikkat: bu turda var olan test dosyaları değiştirildi ve öyle kaldı: "
                       + ", ".join(outcome.test_edits) + ". Testleri değiştirmek istemediyseniz sağ "
                       "paneldeki Değişiklikler sekmesinden geri alın; testlerin geçmesi bu durumda "
                       "kodun doğru olduğunu göstermez.", "alert")
        if outcome.stopped == "cancelled":
            self._note("Durduruldu. Devam etmek için yeni bir mesaj gönderin.", "stop")
        elif outcome.stopped == "max_steps":
            # Plan bekçisi: adım sınırı doldu ama planda açık madde var → sınırlı otomatik devam
            if getattr(outcome, "open_plan_items", None) and self._plan_continues < PLAN_AUTO_CONTINUES:
                self._plan_continues += 1
                self._auto_continue(note=f"Adım sınırı doldu; planda {len(outcome.open_plan_items)} açık madde "
                                         f"var, ajan otomatik devam ediyor ({self._plan_continues}/"
                                         f"{PLAN_AUTO_CONTINUES}).")
        elif outcome.stopped == "budget":
            if self._ask_budget():
                self.start_run()          # geçmiş araç sonuçlarıyla biter; kaldığı yerden sürer
            else:
                self._note("Aylık bütçe nedeniyle durduruldu. Bütçeyi Ayarlar > Sağlayıcılar'dan "
                           "artırabilir veya ücretsiz bir EVREN modeline geçebilirsiniz.", "stop")
        elif outcome.stopped == "quota_daily":
            self._quota_pause("gunluk", "günlük EVREN kotası azaldı")
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
                if outcome.stopped == "done":
                    self._suggest_learnings(self._turn_id, list(getattr(done_runner, "quality_events", []) or []))
                    self._skill_check(list(getattr(done_runner, "used_skills", []) or []))
                self._time_summary(self._turn_id, turn_total, len(getattr(outcome, "model_switches", None) or []))
        self._maybe_auto_title()

    def _on_fail(self, exc: Exception) -> None:
        hook, self._turn_hook = self._turn_hook, None
        if hook is not None:                    # proje ajanı: hata yönetimi (bekle/yedek/duraklat) orada
            self._finish()
            self._note(f"Görev turu hata ile bitti: {exc}", "alert")
            hook(None, exc)
            return
        self._finish()
        if (isinstance(exc, ApiError) and exc.kind == ErrorKind.RATE_LIMIT and self.session_id
                and self.ctx.provider_of(exc.model or self.model) == "evren"):
            # 429 tekrarları tükendi: hata kartı yerine kota kartı (iş kaldığı yerden sürdürülebilir)
            q = getattr(self._run_gate, "_q", None) or self._quota
            self._quota_pause(resume.kind_for(q) if q is not None else "pencere", f"EVREN kota sınırı (429): {exc}")
            return
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
                                lambda _=None, u=billing: QDesktopServices.openUrl(QUrl(u))))
            if exc.kind == ErrorKind.AUTH:
                actions.insert(0, ("Anahtarı güncelle", lambda: self.page_requested.emit("settings")))
            elif exc.kind == ErrorKind.UNKNOWN_RESULT:
                actions.insert(0, ("Kontrollü yeniden dene", self._retry_confirm))
            elif exc.kind != ErrorKind.QUOTA_EXHAUSTED:   # kredi bitince tekrar işe yaramaz
                actions.insert(0, ("Yeniden dene", self.start_run))
            if exc.kind in (ErrorKind.SERVER_UNAVAILABLE, ErrorKind.SERVER_ERROR) and prov == "evren":
                actions.append(("Durum İzleme", lambda: self.page_requested.emit("monitor")))
            holder: dict = {}
            # `_=None`: düğme tıklamasında Qt ilk argüman olarak `checked` (bool) geçirir
            actions.append(("Yapay zekâ ile açıkla",
                            lambda _=None, e=exc, a=advice: self._explain_error(e, a, holder)))
            card = ErrorCard(f"İstek başarısız (kayıt #{error_id}) — {exc.kind.value}", lines, actions)
            holder["card"] = card
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
                if then and result.finish_reason != "cancelled_by_user":
                    self._after_failed_summary("Özet oluşturulamadı (boş yanıt)", then, on_cancel)
                else:
                    self._note("Özet oluşturulamadı.", "alert")
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
                self._after_failed_summary(f"Otomatik özet başarısız ({exc})", then, on_cancel)
            else:
                self.transcript.add(ErrorCard(
                    "Özetleme başarısız", [str(exc), "", "Temiz bir sayfayla devam etmek için /clear yazın "
                                           "(eski sohbet silinmez)."],
                    [("Temiz sayfa aç (/clear)", self.clear_session)]))

        Task(job, on_done=done, on_error=fail).start()

    def _after_failed_summary(self, why: str, then, on_cancel) -> None:
        """Özet başarısız: geçmiş modele hâlâ sığıyorsa özetsiz devam et; sığmıyorsa GÖNDERME.

        2026-10-29: 1M token'lık oturumda özet başarısız olunca mesaj yine de gönderildi ve
        EVREN 4 kez "bağlam penceresini aşıyor" diye reddetti; kullanıcı cevap alamadı.
        """
        msgs = self.ctx.db.get_session_messages(self.session_id) if self.session_id else []
        ctx = self._context_tokens()
        # tahmin artık ölçülmüş/kalibre oranla yapılıyor (runner.calibration); eski ×1,35 telafisi gerekmez
        too_big = bool(ctx) and history_tokens(msgs) > ctx * 0.95
        if not too_big:
            self._note(f"{why}; özetsiz devam ediliyor (eski araç çıktıları kısaltılarak gönderilir).", "alert")
            then()
            return
        if on_cancel:
            on_cancel()                           # yazılan mesaj kutuya geri konur, kaybolmaz
        self.transcript.add(ActionCard(
            "Konuşma modelin sınırını aşıyor — mesaj gönderilmedi",
            [f"{why}.", f"Bu sohbet ~{history_tokens(msgs) // 1000}k token; seçili modelin sınırı "
             f"{ctx // 1000}k. Mesajınız kutuda duruyor.",
             "Temiz sayfa aynı klasör/model/modla yeni oturum açar; eski sohbet silinmez."],
            [("Temiz sayfa aç (/clear)", self.clear_session, "primary"),
             ("Yeniden özetlemeyi dene (/compact)", lambda: self.compact(), "ghost")],
            icon_name="alert", warn=True))
        self.transcript.scroll_to_bottom()

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
        model = (wanted if wanted and wanted in self.ctx.available_model_ids()
                 else (self.ctx.ai_route("inceleme").model or self._concrete_model("inceleme")))
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

    # ---- uygulamanın yapay zekâ destekli küçük işleri (bağlı API üzerinden, ctx.ai_chat) ----

    def load_live_models(self) -> None:
        """Canlı EVREN model listesini arka planda alır (R-04); başarısızsa yedek liste kalır."""
        if not self.ctx.has_api_key():
            return

        def job():
            client = self.ctx.make_client()
            try:
                return client.list_models()
            finally:
                client.close()

        Task(job, on_done=lambda models: self.ctx.set_models(models), on_error=lambda _e: None).start()

    def _time_summary(self, turn_id: int | None, total_s: float, switches: int) -> None:
        """F5 #8: uzun turda (≥ 60 sn, ≥ 3 adım) zaman dağılımı kartı; kısa turda hiçbir şey (R-22)."""
        from .timesummary import TimeSummaryCard, breakdown

        if not self.session_id or turn_id is None:
            return
        msgs = [m for m in self.ctx.db.get_session_messages(self.session_id) if m["id"] >= turn_id]
        data = breakdown(msgs, total_s, switches)
        if data is None:
            return
        self.transcript.add(TimeSummaryCard(data))
        self.transcript.scroll_to_bottom()

    def _suggest_learnings(self, turn_id: int | None, events: list[str]) -> None:
        """E6: ders sinyali varsa (learnings.signals) kısa model çağrısıyla en çok 3 ders → onay kartı. Sinyal
        yoksa model ÇAĞRILMAZ (R-22). Onaysız EVREN.md'ye yazılmaz."""
        if (not self.ctx.settings.learnings_suggest or not self.workspace or not self.session_id or turn_id is None
                or os.environ.get("EVREN_STUDIO_NO_LEARNINGS")):
            return
        msgs = [m for m in self.ctx.db.get_session_messages(self.session_id) if m["id"] >= turn_id]
        sig = learnings.signals(msgs, events)
        if not sig:
            return
        sid, root = self.session_id, Path(self.workspace)
        prompt = [{"role": "system", "content": learnings.SYSTEM},
                  {"role": "user", "content": "Ders sinyalleri: " + "; ".join(sig) + "\n\nAraç kaydı:\n"
                                              + learnings.transcript(msgs)}]

        def job():
            return self.ctx.ai_chat("ozet", prompt, max_tokens=400, session_id=sid)[0]

        def done(text):
            items = learnings.parse(text)
            if not items or sid != self.session_id:
                return

            def add():
                try:
                    p = learnings.append(root, items)
                    self._note(f"{p.name} \"Öğrenilenler\" bölümüne {len(items)} madde eklendi; sonraki turlarda "
                               "ajan bunu okur.", "check")
                except OSError as exc:
                    self.transcript.add(ErrorCard("EVREN.md yazılamadı", [str(exc)]))
            card = ActionCard("Bu turdan öğrenilenler — EVREN.md'ye eklensin mi?",
                              [f"• {i}" for i in items]
                              + ["Eklenirse sonraki turlarda ajan bunları okur (Ayarlar'dan kapatılabilir)."],
                              [("EVREN.md'ye ekle", add, "primary"), ("Geç", lambda: None, "ghost")],
                              icon_name="bulb")
            self.transcript.add(card)
            self.transcript.scroll_to_bottom()

        Task(job, on_done=done, on_error=lambda _e: None).start()

    def _maybe_auto_title(self) -> None:
        """Yeni oturumun ilk yanıtından sonra 3-6 kelimelik başlık (kullanıcı kararı 2026-10-19).
        Kullanıcı bu arada adı elle değiştirdiyse dokunulmaz. Hata → sessizce eski başlık kalır."""
        pending = getattr(self, "_auto_title", None)
        if not pending or pending[0] != self.session_id:
            return
        if not self.ctx.settings.ai_session_titles or os.environ.get("EVREN_STUDIO_NO_AI_TITLE"):
            self._auto_title = None        # kapalı (ayar) / testlerde ek model çağrısı yapılmaz
            return
        self._auto_title = None
        sid, old_title, first = pending
        msgs = self.ctx.db.get_session_messages(sid)
        answer = next((m["content"] for m in msgs if m["role"] == "assistant" and (m["content"] or "").strip()), "")
        prompt = [{"role": "system", "content": TITLE_SYSTEM},
                  {"role": "user", "content": f"Kullanıcının isteği:\n{first}\n\nYanıtın başı:\n{answer[:800]}"}]

        def job():
            return self.ctx.ai_chat("baslik", prompt, max_tokens=40, session_id=sid)[0]

        def done(text):
            title = clean_title(text)
            row = self.ctx.db.get_session(sid)
            if title and row and row["title"] == old_title:
                self.ctx.db.update_session(sid, title=title)
                self.sessions_changed.emit()
                if sid == self.session_id:
                    self._update_header()

        Task(job, on_done=done, on_error=lambda _e: None).start()

    def _explain_error(self, exc, advice, holder: dict) -> None:
        """Hata kartındaki "Yapay zekâ ile açıkla": hatayı sade Türkçeyle açıklar (yalnız istenince)."""
        card = holder.get("card")
        if card is None:
            return
        card.append_line("Açıklama hazırlanıyor…")
        body = (f"Hata türü: {exc.kind.value}\nHTTP: {exc.status or '-'}\nİşlem: {exc.operation or '-'}\n"
                f"Model: {exc.model or '-'}\nMesaj (maskeli): {str(exc.message)[:600]}\n"
                f"Uygulamanın önerileri: {'; '.join(advice.recommended_steps)[:600]}")
        prompt = [{"role": "system", "content": ERROR_SYSTEM}, {"role": "user", "content": body}]

        def job():
            return self.ctx.ai_chat("hata", prompt, max_tokens=500, session_id=self.session_id)

        def done(res):
            text, model = res
            card.append_line(f"Yapay zekâ açıklaması ({model}):\n{text.strip()}")

        Task(job, on_done=done, on_error=lambda e: card.append_line(f"Açıklama alınamadı: {e}")).start()

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

    # ---- kota bitince otomatik devam (agent/resume.py; kullanıcı isteği 2026-11-01) ----

    def _quota_pause(self, kind: str, reason: str) -> None:
        """Kota yüzünden güvenli noktada duran iş: devam planını KALICI yaz, kartı göster, açıksa zamanlayıcı kur."""
        if not self.session_id:
            return
        q = getattr(self._run_gate, "_q", None) or self._quota
        plan = resume.make_plan(self.session_id, kind, q, reason)
        self.ctx.db.set_meta(resume.META_KEY, plan.to_json())
        self._show_resume_card(plan)

    def _show_resume_card(self, plan) -> None:
        if self._resume_card is not None:
            self._resume_card.finish("Yerine yeni kota kartı açıldı.")
        title = ("Günlük EVREN kotası doldu — iş güvenli noktada durdu" if plan.kind == "gunluk"
                 else "EVREN kota sınırına ulaşıldı — iş güvenli noktada durdu")
        self._resume_card = QuotaResumeCard(
            title, lambda: resume.describe(self._pending_plan() or plan), bool(self.ctx.settings.auto_resume),
            self._set_auto_resume, lambda: self._resume_probe(manual=True), self.cancel_auto_resume)
        self.transcript.add(self._resume_card)
        self.transcript.scroll_to_bottom()
        self._schedule_resume(plan)

    def _pending_plan(self):
        return resume.ResumePlan.from_json(self.ctx.db.get_meta(resume.META_KEY))

    def _set_auto_resume(self, on: bool) -> None:
        self.ctx.settings.auto_resume = bool(on)
        self.ctx.save_settings()
        plan = self._pending_plan()
        if on and plan is not None:
            self._schedule_resume(plan)
        elif not on and self._resume_timer is not None:
            self._resume_timer.stop()
        if self._resume_card is not None:
            self._resume_card.refresh()

    def _schedule_resume(self, plan) -> None:
        if self._resume_timer is not None:
            self._resume_timer.stop()
        if not self.ctx.settings.auto_resume:
            return
        self._resume_timer = QTimer(self)
        self._resume_timer.setSingleShot(True)
        self._resume_timer.timeout.connect(self._resume_probe)
        self._resume_timer.start(int(max(1.0, plan.seconds_left()) * 1000))

    def _resume_probe(self, manual: bool = False) -> None:
        """Kotayı yokla (token harcamaz, R-04: arka planda); yeterliyse devam, değilse yeni saat kur."""
        if getattr(self, "_closed", False):
            return
        plan = self._pending_plan()
        if plan is None:
            return
        if self.running:
            self._schedule_resume(resume.after_probe(plan, None))
            return

        def done(q):
            self._quota = q
            if resume.quota_ok(q):
                self._resume_now(plan)
                return
            nxt = resume.after_probe(plan, q)
            self.ctx.db.set_meta(resume.META_KEY, nxt.to_json())
            if manual:
                self._note(f"Kota henüz yenilenmedi; yeni deneme: {resume.describe(nxt)}.", "alert")
            self._schedule_resume(nxt)
            if self._resume_card is not None:
                self._resume_card.refresh()

        def fail(exc):
            nxt = resume.after_probe(plan, None)
            self.ctx.db.set_meta(resume.META_KEY, nxt.to_json())
            if manual:
                self._note(f"Kota okunamadı ({exc}); yeni deneme: {resume.describe(nxt)}.", "alert")
            self._schedule_resume(nxt)

        Task(self._fetch_quota, on_done=done, on_error=fail).start()

    def _resume_now(self, plan) -> None:
        self.ctx.db.delete_meta(resume.META_KEY)
        if self._resume_timer is not None:
            self._resume_timer.stop()
        if self.session_id != plan.session_id:
            self.open_session(plan.session_id)      # bekleme sırasında başka oturuma geçilmişse işin oturumuna dön
        if self._resume_card is not None:
            self._resume_card.finish("Kota yenilendi; ajan kaldığı yerden devam etti.")
            self._resume_card = None
        self._auto_continue(note="Kota yenilendi; ajan kaldığı yerden otomatik devam ediyor.",
                            prompt=prompts.QUOTA_CONTINUE_PROMPT)

    def cancel_auto_resume(self) -> None:
        """Vazgeç ya da kullanıcı kendisi yeni mesaj yazdı: bekleyen devam silinir."""
        if self._resume_timer is not None:
            self._resume_timer.stop()
        if self.ctx.db.get_meta(resume.META_KEY) is not None:
            self.ctx.db.delete_meta(resume.META_KEY)
        if self._resume_card is not None:
            self._resume_card.finish("Otomatik devam iptal edildi. Sürdürmek için yeni bir mesaj yazın.")
            self._resume_card = None

    def restore_pending_resume(self) -> None:
        """Uygulama açılışı: önceki çalışmadan kalan devam planı varsa oturumu aç, kartı göster, zamanlayıcıyı kur."""
        if getattr(self, "_closed", False):
            return                              # pencere açılır açılmaz kapatıldı (veritabanı kapalı)
        plan = self._pending_plan()
        if plan is None:
            return
        if self.ctx.db.get_session(plan.session_id) is None:
            self.ctx.db.delete_meta(resume.META_KEY)      # oturum silinmiş
            return
        self.open_session(plan.session_id)
        self._show_resume_card(plan)

    def _auto_continue(self, note: str = "", prompt: str = "") -> None:
        """Güvenli noktada duran turu (özet, adım sınırı veya kota sonrası) otomatik sürdürür."""
        if not self.session_id:
            return
        self.ctx.db.add_session_message(self.session_id, "user", prompt or prompts.AUTO_CONTINUE_PROMPT,
                                        meta={"auto_continue": True})
        self.transcript.add(NoteWidget(note or "Bağlam özetlendi; ajan kaldığı yerden otomatik devam ediyor.",
                                       "refresh"))
        self.start_run()

    def _on_model_list_change(self, removed: list[str], added: list[str]) -> None:
        """A9: EVREN model listesi değişti → not (oturum yoksa ilk mesajda gösterilir)."""
        in_route = {m for chain in router.EVREN_ROUTES.values() for m in chain}
        parts = []
        if removed:
            parts.append("kalkan: " + ", ".join(m + (" (Auto Pro sırasındaydı)" if m in in_route else "")
                                                for m in removed))
        if added:
            parts.append("eklenen: " + ", ".join(added))
        text = ("EVREN model listesi değişti — " + "; ".join(parts) + ". Auto Pro kalkan modeli kendiliğinden "
                "atlar; yeni modeller ölçülmeden Auto Pro sırasına girmez (Modeller sayfası).")
        if self.session_id:
            self._note(text, "alert")
        else:
            self._pending_model_note = text

    @property
    def deep_on(self) -> bool:
        return bool(self.ctx.settings.deep_mode)

    def _offer_project(self, text: str, atts: list, back) -> bool:
        """Çok aşamalı uzun istemde Proje ajanını ÖNERİR (sessizce yönlendirmez: Otomatik mod,
        ayrı git dalı ve commit demektir). True → mesaj kartın kararına bırakıldı."""
        from ..agent.planguard import looks_multi_phase, plan_only_request

        s = self.ctx.settings
        key = hash(text)
        if (not s.suggest_project or not self.workspace or atts or key in self._project_offered
                or self.deep_on or not looks_multi_phase(text)
                or plan_only_request([{"role": "user", "content": text}])):
            return False
        self._project_offered.add(key)
        def choose(run) -> None:
            self.composer.set_text("")
            run()
        card = ChoiceCard(
            "Bu iş çok aşamalı görünüyor",
            "Proje ajanı işi plana böler, onayınızdan sonra her fazı/görevi ayrı turda, doğrulayarak ve "
            "unutmadan sırayla yürütür (ayrı git dalı, görev başına commit). Normal devam ederseniz plan "
            "bekçisi açık maddeler bitene kadar ajanı sürdürmeye çalışır.",
            [("Proje ajanıyla yürüt", lambda: choose(lambda: self.project.command("/proje", text))),
             ("Normal devam", lambda: choose(lambda: self.send(text)))])
        self.stack.setCurrentWidget(self.transcript if self.session_id else self.welcome)
        if not self.session_id:
            self._ensure_session(text[:60])
            self.stack.setCurrentWidget(self.transcript)
        self.transcript.add(card)
        self.transcript.scroll_to_bottom()
        back()
        return True

    def shutdown(self) -> None:
        self._closed = True
        if self._resume_timer is not None:
            self._resume_timer.stop()          # devam planı veritabanında kalır; sonraki açılışta yeniden kurulur
        self.stop_services(quiet=True)
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
