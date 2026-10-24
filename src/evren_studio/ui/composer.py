"""Mesaj yazma kutusu: çok satırlı giriş, komut/model seçim listesi,
mod ve model seçici, kullanım düğmesi, ekler, çalışma durum çubuğu, gönder/durdur.

Sürükle-bırak ve yapıştır (Ctrl+V): yerel dosya → ek kartı (yol metne yazılmaz),
panodaki görsel (ekran görüntüsü) → küçük resimli ek; düz metin normal yapıştırılır.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, QSize, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QImage, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..agent.permissions import MODE_HINTS, MODES, normalize_mode
from . import brand, icons, theme
from .attachments import AttachmentBar
from .usage_popup import UsageChip


def local_files(md: QMimeData) -> list[str]:
    """Panodaki/sürüklenen verideki yerel dosya yolları (klasörler hariç)."""
    if not md.hasUrls():
        return []
    out = []
    for u in md.urls():
        if u.isLocalFile():
            path = u.toLocalFile()
            if Path(path).is_file():
                out.append(path)
    return out

SLASH_COMMANDS = {
    "/model": "Modeli değiştir — listeden seçin",
    "/manuel": "Manuel mod: her değişiklik ve komut için onay",
    "/kabul": "Düzenlemeleri kabul et: dosyalar onaysız, komutlar onaylı",
    "/plan": "Plan modu: salt okunur, plan çıkarır",
    "/otomatik": "Otomatik mod: hiçbir işlem için onay istenmez",
    "/init": "Projeyi inceleyip EVREN.md proje hafızası oluştur",
    "/compact": "Konuşmayı özetleyip bağlamı küçült — /compact <odak> ile odak verin",
    "/ozet": "Konuşmayı özetle (/compact ile aynı)",
    "/yeni": "Yeni oturum başlat",
    "/disa-aktar": "Oturumu Markdown olarak dışa aktar",
    "/yardim": "Komutları ve kısayolları göster",
    "/proje": "Proje ajanı: /proje <hedef> — plan çıkarır, onayınızla görev görev yürütür",
    "/proje-duzelt": "Proje planını değiştir: /proje-duzelt <geri bildirim>",
    "/proje-devam": "Duraklatılan projeyi sürdür — /proje-devam <yanıt> ile sorusunu yanıtlayın",
    "/proje-durdur": "Çalışan projeyi güvenli noktada durdur",
    "/qa": "QA ajanı: /qa <neyi test etsin> — web uygulamasını tarayıcıda test uzmanı gibi dener",
    "/qa-duzelt": "QA senaryolarını değiştir: /qa-duzelt <geri bildirim>",
    "/qa-devam": "Duraklatılan QA testini sürdür",
    "/qa-durdur": "Çalışan QA testini durdur",
    "/derin": "Derin Mod: /derin aç-kapat · /derin <istek> bu işi çok ajanlı anla→planla→uygula→doğrula ile yürüt",
    "/derin-durdur": "Çalışan Derin Mod akışını durdur",
    "/profil": "Ajan profili seç: /profil <ad> · /profil yok (kaldır) · /profil (liste)",
    "/betiklestir": "Bu oturumdaki işi tekrar çalıştırılabilir betiğe çevir: /betiklestir [dosya.py]",
}
COMMAND_ICONS = {
    "/model": "cpu", "/plan": "map", "/manuel": "shield", "/kabul": "pencil", "/otomatik": "spark",
    "/init": "spark", "/ozet": "refresh", "/compact": "refresh", "/yeni": "plus", "/disa-aktar": "download",
    "/yardim": "help", "/proje": "list", "/proje-duzelt": "pencil", "/proje-devam": "refresh",
    "/proje-durdur": "stop", "/qa": "check", "/qa-duzelt": "pencil", "/qa-devam": "refresh",
    "/qa-durdur": "stop", "/derin": "spark", "/derin-durdur": "stop",
}
FOOTER_SENT_TO = {"evren": "EVREN API'sine", "openai": "OpenAI'ye (ücretli)",
                  "anthropic": "Anthropic'e (ücretli)",
                  "otomatik": "Auto Pro'nun seçtiği sağlayıcıya"}
# Kimliği yerine görünen ad kullanılan modeller
DISPLAY_NAMES = {"auto-pro": "Auto Pro", "akilli": "Auto Pro"}

# Model seçicideki sağlayıcı başlıkları
GROUP_TITLES = {
    "otomatik": "Otomatik yönlendirme",
    "evren": "EVREN · ücretsiz",
    "openai": "OpenAI · ücretli · doğrulanmadı",
    "anthropic": "Anthropic · ücretli · doğrulanmadı",
}


def _norm_item(item: tuple) -> tuple:
    """(id, açıklama, araç[, sağlayıcı, etkin]) → 5'li demet (eski 3'lü biçim de kabul)."""
    mid, desc, tools = item[0], item[1], item[2]
    provider = item[3] if len(item) > 3 else "evren"
    enabled = item[4] if len(item) > 4 else True
    return mid, desc, tools, provider, enabled


MODE_ICONS = {"manuel": "shield", "kabul": "pencil", "plan": "map", "auto": "spark"}
# Eğik çizgi komutu → mod anahtarı (/onayli eski ad, gizli takma ad)
MODE_COMMANDS = {"/manuel": "manuel", "/onayli": "manuel", "/kabul": "kabul",
                 "/plan": "plan", "/otomatik": "auto"}
ROLE_VALUE = Qt.UserRole + 1
ROLE_KIND = Qt.UserRole + 2     # "command" | "model"


class ComposerEdit(QPlainTextEdit):
    submit = Signal()
    escape = Signal()
    files_dropped = Signal(list)        # yerel dosya yolları (sürükle-bırak / yapıştır)
    image_pasted = Signal(QImage)       # panodaki görsel (ekran görüntüsü vb.)

    def canInsertFromMimeData(self, source: QMimeData) -> bool:
        return bool(local_files(source)) or source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source: QMimeData) -> None:
        files = local_files(source)
        if files:
            self.files_dropped.emit(files)      # yol metne YAZILMAZ; ek kartı olur
            return
        if source.hasImage():
            img = source.imageData()
            if isinstance(img, QImage) and not img.isNull():
                self.image_pasted.emit(img)
                return
        if source.hasUrls() and not source.hasText():
            return                              # uzak adres / klasör: sessizce yok say
        super().insertFromMimeData(source)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ComposerEdit")
        self.send_with_enter = True
        self.popup_keys = None      # Composer: tuş → seçim listesi işledi mi?
        self.setTabChangesFocus(False)
        self.document().contentsChanged.connect(self._grow)
        self._grow()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if self.popup_keys is not None and self.popup_keys(e):
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            mods = e.modifiers()
            # Enter gönderir (ayar açıkken); Shift/Alt/Ctrl+Enter yeni satır. Ayar kapalıysa
            # Ctrl+Enter gönderir, diğerleri yeni satır. Alt+Enter önceden gönderiyordu (2026-10-19).
            newline_mods = Qt.ShiftModifier | Qt.AltModifier | Qt.ControlModifier
            if self.send_with_enter:
                send = not (mods & newline_mods)
            else:
                send = bool(mods & Qt.ControlModifier)
            if send:
                self.submit.emit()
            else:
                self.textCursor().insertText("\n")
                self.ensureCursorVisible()
            return
        if e.key() == Qt.Key_Escape:
            self.escape.emit()
            return
        if e.key() == Qt.Key_Tab:
            self.focusNextChild()
            return
        super().keyPressEvent(e)

    def _grow(self) -> None:
        total = self.document().size().height()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if total > 12 else Qt.ScrollBarAlwaysOff)
        lines = max(1, min(total, 12))
        lh = self.fontMetrics().lineSpacing()
        self.setFixedHeight(int(lines * lh + 16))

    def insert_at_cursor(self, text: str) -> None:
        cur = self.textCursor()
        cur.insertText(text)
        self.setTextCursor(cur)
        self.setFocus()


class Composer(QWidget):
    submitted = Signal(str)
    stop_requested = Signal()
    mode_changed = Signal(str)
    deep_toggled = Signal(bool)
    model_changed = Signal(str)
    attach_requested = Signal()
    files_added = Signal(list)          # ComposerEdit veya çerçeveye bırakılan dosyalar
    image_added = Signal(QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._model = ""
        self._mode = "manuel"
        self._agentic = True
        self._models: list[tuple[str, str, bool, str, bool]] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        # ---- komut / model seçim listesi (tıklanabilir) ----
        self.popup = QListWidget()
        self.popup.setObjectName("CommandPopup")
        self.popup.setVisible(False)
        self.popup.setMouseTracking(True)
        self.popup.setIconSize(QSize(16, 16))
        self.popup.setFocusPolicy(Qt.NoFocus)
        self.popup.itemClicked.connect(self._accept_item)
        outer.addWidget(self.popup)
        self.popup_title = QLabel()
        self.popup_title.setProperty("role", "faint")
        self.popup_title.setVisible(False)
        outer.insertWidget(0, self.popup_title)

        # ---- çalışma durum çubuğu: model + süre ----
        self.run_bar = QFrame()
        self.run_bar.setObjectName("RunBar")
        rl = QHBoxLayout(self.run_bar)
        rl.setContentsMargins(12, 5, 12, 5)
        rl.setSpacing(8)
        # Canlı gösterge: çubuk görünürken döner, gizlenince durur (işlemci harcamaz)
        self.run_dot = brand.BusyStar(14)
        rl.addWidget(self.run_dot)
        self.run_text = QLabel()
        rl.addWidget(self.run_text, 1)
        self.run_hint = QLabel("Esc ile durdur")
        self.run_hint.setProperty("role", "faint")
        rl.addWidget(self.run_hint)
        self.run_bar.setVisible(False)
        outer.addWidget(self.run_bar)

        self.frame = QFrame()
        self.frame.setObjectName("Composer")
        fl = QVBoxLayout(self.frame)
        fl.setContentsMargins(14, 10, 10, 8)
        fl.setSpacing(6)
        self.attachments = AttachmentBar()
        self.attachments.changed.connect(self._update_send)
        fl.addWidget(self.attachments)
        self.setAcceptDrops(True)
        self.edit = ComposerEdit()
        self.edit.files_dropped.connect(self.files_added.emit)
        self.edit.image_pasted.connect(self.image_added.emit)
        self.edit.setPlaceholderText("EVREN'e bir görev verin veya soru sorun…  (/ komutlar, @ dosya)")
        self.edit.submit.connect(self._submit)
        self.edit.escape.connect(self.stop_requested.emit)
        self.edit.textChanged.connect(self._on_text)
        self.edit.popup_keys = self._popup_key
        self.edit.installEventFilter(self)
        fl.addWidget(self.edit)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.attach_btn = self._chip("paperclip", "")
        self.attach_btn.setToolTip("Dosya veya görsel ekle — sürükleyip bırakabilir ya da "
                                   "Ctrl+V ile yapıştırabilirsiniz")
        self.attach_btn.clicked.connect(self.attach_requested.emit)
        row.addWidget(self.attach_btn)

        self.mode_btn = self._chip("shield", MODES["manuel"])
        self.mode_btn.setPopupMode(QToolButton.InstantPopup)
        self.mode_menu = QMenu(self)
        group = QActionGroup(self)
        self.mode_actions: dict[str, QAction] = {}
        for key, label in MODES.items():
            act = QAction(icons.icon(MODE_ICONS[key], size=16), f"{label} — {MODE_HINTS[key]}", self)
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, k=key: self.set_mode(k, emit=True))
            group.addAction(act)
            self.mode_menu.addAction(act)
            self.mode_actions[key] = act
        self.mode_btn.setMenu(self.mode_menu)
        row.addWidget(self.mode_btn)

        self.model_btn = self._chip("cpu", "model")
        self.model_btn.setToolTip("Modeli değiştir (veya /model yazın)")
        self.model_btn.setPopupMode(QToolButton.InstantPopup)
        self.model_menu = QMenu(self)
        self.model_btn.setMenu(self.model_menu)
        row.addWidget(self.model_btn)
        # Derin Mod: açıkken her iş birden çok EVREN ajanıyla anla→planla→uygula→doğrula→düzelt
        self.deep_btn = self._chip("spark", "Derin")
        self.deep_btn.setCheckable(True)
        self.deep_btn.toggled.connect(self._on_deep)
        row.addWidget(self.deep_btn)
        self.usage_btn = UsageChip()
        row.addWidget(self.usage_btn)

        row.addStretch(1)
        self.context_label = QLabel("")
        self.context_label.setProperty("role", "faint")
        row.addWidget(self.context_label)
        self.send_btn = QPushButton()
        self.send_btn.setObjectName("SendButton")
        self.send_btn.setFixedSize(30, 30)
        self.send_btn.setIconSize(QSize(18, 18))
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._on_send_clicked)
        row.addWidget(self.send_btn)
        fl.addLayout(row)
        outer.addWidget(self.frame)

        self.footer = QLabel("EVREN hata yapabilir; önemli değişiklikleri gözden geçirin. "
                             "Mesajlar ve dosya içerikleri EVREN API'sine gönderilir.")
        self.footer.setProperty("role", "faint")
        self.footer.setAlignment(Qt.AlignCenter)
        self.footer.setWordWrap(True)          # dar pencerede orta alanı genişletmesin
        outer.addWidget(self.footer)
        self.set_mode("manuel")
        self._update_send()

    def _chip(self, icon_name: str, text: str) -> QToolButton:
        b = QToolButton()
        b.setProperty("variant", "chip")
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setIcon(icons.icon(icon_name, size=15))
        b.setIconSize(QSize(15, 15))
        b.setText(text)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def eventFilter(self, obj, event) -> bool:
        if obj is self.edit and event.type() in (event.Type.FocusIn, event.Type.FocusOut):
            self.frame.setProperty("focus", event.type() == event.Type.FocusIn)
            self.frame.style().unpolish(self.frame)
            self.frame.style().polish(self.frame)
        return super().eventFilter(obj, event)

    # ---- durum ----------------------------------------------------------

    def set_agentic(self, agentic: bool) -> None:
        self._agentic = agentic
        self.mode_btn.setVisible(agentic)
        self.edit.setPlaceholderText(
            "EVREN'e bir görev verin veya soru sorun…  (/ komutlar, @ dosya)" if agentic
            else "Mesajınızı yazın…  (/ komutlar)")

    def set_mode(self, mode: str, emit: bool = False) -> None:
        mode = normalize_mode(mode)
        self._mode = mode
        self.mode_btn.setText(MODES[mode])
        self.mode_btn.setIcon(icons.icon(MODE_ICONS[mode], size=15))
        self.mode_btn.setToolTip(MODE_HINTS[mode])
        self.mode_actions[mode].setChecked(True)
        if emit:
            self.mode_changed.emit(mode)

    def mode(self) -> str:
        return self._mode

    def set_models(self, models: list, current: str) -> None:
        """models: [(id, açıklama, araç_destekli, sağlayıcı, etkin)] — sağlayıcıya göre gruplanır."""
        self._models = [_norm_item(m) for m in models]
        self.model_menu.clear()
        group = QActionGroup(self.model_menu)
        last_provider = None
        for mid, desc, tools, provider, enabled in self._models:
            if provider != last_provider:
                self.model_menu.addSection(GROUP_TITLES.get(provider, provider))
                last_provider = provider
            label = DISPLAY_NAMES.get(mid, mid) + (f"   ·  {desc}" if desc else "")
            if not enabled:
                label += "   (anahtar gerekli)"
            act = QAction(label, self.model_menu)
            act.setData(mid)
            act.setCheckable(True)
            act.setChecked(mid == current)
            if not enabled:
                act.setToolTip("Bu sağlayıcının API anahtarı yok — Ayarlar > Sağlayıcılar")
            elif provider != "evren":
                act.setToolTip("Ücretli model; harcama aylık bütçeye sayılır (tahmini)")
            else:
                act.setToolTip("Yerel araç çağrısı destekli" if tools else "Metin protokolü ile çalışır")
            act.triggered.connect(lambda _=False, m=mid: self.set_model(m, emit=True))
            group.addAction(act)
            self.model_menu.addAction(act)
        self.set_model(current)

    def set_model(self, model: str, emit: bool = False) -> None:
        self._model = model
        self.model_btn.setText(DISPLAY_NAMES.get(model, model) or "model seçin")
        provider = next((m[3] for m in self._models if m[0] == model), "evren")
        self.footer.setText("Yapay zekâ hata yapabilir; önemli değişiklikleri gözden geçirin. "
                            f"Mesajlar ve dosya içerikleri {FOOTER_SENT_TO.get(provider, provider)} gönderilir.")
        for act in self.model_menu.actions():
            act.setChecked(act.data() == model)
        if emit:
            self.model_changed.emit(model)

    def model(self) -> str:
        return self._model

    def model_ids(self) -> list[str]:
        return [m[0] for m in self._models]

    def set_deep(self, on: bool) -> None:
        self.deep_btn.blockSignals(True)
        self.deep_btn.setChecked(bool(on))
        self.deep_btn.blockSignals(False)
        self._style_deep(bool(on))

    def _on_deep(self, on: bool) -> None:
        self._style_deep(on)
        self.deep_toggled.emit(on)

    def _style_deep(self, on: bool) -> None:
        p = theme.current()
        self.deep_btn.setText("Derin · açık" if on else "Derin")
        self.deep_btn.setIcon(icons.icon("spark", color=p.accent if on else None, size=15))
        self.deep_btn.setStyleSheet(f"QToolButton {{ border: 1px solid {p.accent}; color: {p.text}; }}" if on else "")
        self.deep_btn.setToolTip(
            "Derin Mod AÇIK: her iş anla → planla (iki model + yargıç) → uygula (onaylı plan) → çekişmeli doğrula "
            "→ düzelt akışıyla birden çok EVREN ajanıyla yürür. Daha yavaş ve daha çok token harcar; yalnız ücretsiz "
            "EVREN. Kapatmak için tıklayın." if on else
            "Derin Mod: zor işler için Claude Code'daki ultracode benzeri çok ajanlı çalışma. Açmak için tıklayın "
            "(veya /derin <istek> ile tek bir işte kullanın).")

    def set_running(self, running: bool) -> None:
        self._running = running
        if not running:
            self.set_run_status(None)
        self._update_send()

    def set_run_status(self, text: str | None) -> None:
        """Yazma kutusunun üstündeki durum çubuğu: 'glm-5.3 çalışıyor · 0:12 · adım 2'."""
        self.run_bar.setVisible(bool(text))
        self.run_text.setText(text or "")

    def set_context(self, used_tokens: int, limit: int | None, compact_at: int | None = None,
                    model: str = "") -> None:
        """Bağlam göstergesi. Özet açıksa yüzde ÖZET EŞİĞİNE göredir (dolunca özetlenir);
        modelin tam penceresi ipucunda yazar. compact_at: otomatik özet eşiği (token)."""
        if not used_tokens:
            self.context_label.setText("")
            self.context_label.setToolTip("")
            return

        def k(n: int) -> str:
            if n >= 1_000_000:
                return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
            return f"{n / 1000:.1f}k" if n < 100_000 else f"{n // 1000}k"
        name = DISPLAY_NAMES.get(model, model)
        window = f"{name} penceresi {k(limit)}" if (limit and name) else (f"model penceresi {k(limit)}"
                                                                         if limit else "")
        tip = "Tahmini bağlam (≈3,5 karakter/token)."
        color = ""
        if compact_at:
            ratio = used_tokens / compact_at
            text = f"bağlam ~{k(used_tokens)} / {k(compact_at)} ({min(100, int(ratio * 100))}%)"
            tip += (f" Yüzde, otomatik özetin devreye gireceği ~{k(compact_at)} token'a göredir"
                    + (f" ({window})" if window else "") + ". Eşik bilinçli olarak pencereden küçüktür: "
                    "ajan her adımda tüm geçmişi yeniden gönderir; büyük bağlam yavaşlatır, EVREN "
                    "kotasını (5 dk ve günlük) veya ücretli bütçeyi hızla tüketir. "
                    "Ayarlar > Otomatik özet'ten değiştirilebilir. Elle: /compact")
            if ratio >= 0.85:
                color = theme.current().warning
                text += "  ·  özet yakında"
        else:
            if limit:
                text = f"bağlam ~{k(used_tokens)} / {k(limit)} ({min(100, int(used_tokens * 100 / limit))}%)"
            else:
                text = f"bağlam ~{k(used_tokens)}"
            tip += (f" {window[0].upper() + window[1:]}." if window else "") + \
                " Otomatik özet kapalı (Ayarlar). Elle: /compact"
        self.context_label.setText(text)
        self.context_label.setToolTip(tip)
        self.context_label.setStyleSheet(f"color: {color};" if color else "")

    def _update_send(self) -> None:
        p = theme.current()
        self.send_btn.setProperty("running", self._running)
        self.send_btn.style().unpolish(self.send_btn)
        self.send_btn.style().polish(self.send_btn)
        if self._running:
            self.send_btn.setIcon(icons.icon("stop", p.bg, 18))
            self.send_btn.setToolTip("Durdur (Esc)")
            self.send_btn.setEnabled(True)
        else:
            has_text = bool(self.edit.toPlainText().strip()) or bool(self.attachments.items())
            self.send_btn.setIcon(icons.icon("send", p.on_accent if has_text else p.muted, 18))
            self.send_btn.setToolTip("Gönder (Enter) — yeni satır: Shift+Enter veya Alt+Enter")
            self.send_btn.setEnabled(has_text)

    # ---- komut / model seçim listesi -------------------------------------

    def _on_text(self) -> None:
        self._update_send()
        self._refresh_popup()

    def _refresh_popup(self) -> None:
        text = self.edit.toPlainText()
        if not text.startswith("/") or "\n" in text:
            self.hide_popup()
            return
        low = text.lower()
        if low.startswith("/model ") or low == "/model ":
            self._show_models(low[len("/model "):].strip())
            return
        word = low.split(" ")[0]
        if " " in low:          # komut yazıldı, argüman giriliyor: listeyi kapat
            self.hide_popup()
            return
        self.popup.clear()
        for cmd, desc in SLASH_COMMANDS.items():
            if cmd.startswith(word):
                it = QListWidgetItem(icons.icon(COMMAND_ICONS.get(cmd, "dot"), size=16),
                                     f"{cmd}    {desc}")
                it.setData(ROLE_VALUE, cmd)
                it.setData(ROLE_KIND, "command")
                self.popup.addItem(it)
        if self.popup.count() == 0:
            it = QListWidgetItem("Eşleşen komut yok — /yardim yazın")
            it.setFlags(Qt.NoItemFlags)
            self.popup.addItem(it)
        self._open_popup("Komutlar  ·  tıklayın veya ↑↓ + Enter")

    def _show_models(self, filt: str = "") -> None:
        self.popup.clear()
        last_provider = None
        for mid, desc, tools, provider, enabled in self._models:
            if filt and filt not in mid.lower() and filt not in DISPLAY_NAMES.get(mid, "").lower():
                continue
            if provider != last_provider:
                head = QListWidgetItem(GROUP_TITLES.get(provider, provider))
                head.setFlags(Qt.NoItemFlags)       # başlık: seçilemez
                f = head.font()
                f.setBold(True)
                head.setFont(f)
                self.popup.addItem(head)
                last_provider = provider
            mark = "✓ " if mid == self._model else "    "
            text = f"{mark}{DISPLAY_NAMES.get(mid, mid)}" + (f"    {desc}" if desc else "") + ("" if enabled else "    (anahtar gerekli)")
            it = QListWidgetItem(icons.icon("cpu", size=16), text)
            it.setData(ROLE_VALUE, mid)
            it.setData(ROLE_KIND, "model")
            it.setToolTip("Bu sağlayıcının API anahtarı yok — Ayarlar > Sağlayıcılar" if not enabled
                          else ("Ücretli model" if provider != "evren"
                                else ("Yerel araç çağrısı destekli" if tools else "Metin protokolü ile çalışır")))
            self.popup.addItem(it)
        if not any(self.popup.item(i).data(ROLE_KIND) == "model" for i in range(self.popup.count())):
            self.popup.clear()
            it = QListWidgetItem("Eşleşen model yok")
            it.setFlags(Qt.NoItemFlags)
            self.popup.addItem(it)
        self._open_popup("Model seçin  ·  tıklayın veya ↑↓ + Enter")
        for i in range(self.popup.count()):
            if self.popup.item(i).data(ROLE_VALUE) == self._model:
                self.popup.setCurrentRow(i)
                break

    def _open_popup(self, title: str) -> None:
        self.popup_title.setText(title)
        self.popup_title.setVisible(True)
        rows = max(1, min(self.popup.count(), 9))
        row_h = max(self.popup.sizeHintForRow(0), 24) if self.popup.count() else 30
        self.popup.setFixedHeight(rows * (row_h + 2) + 14)
        self.popup.setVisible(True)
        if self.popup.currentRow() < 0:
            for i in range(self.popup.count()):
                if self.popup.item(i).flags() & Qt.ItemIsEnabled:
                    self.popup.setCurrentRow(i)
                    break

    def hide_popup(self) -> None:
        self.popup.setVisible(False)
        self.popup_title.setVisible(False)

    def popup_visible(self) -> bool:
        return self.popup.isVisible()

    def _popup_key(self, e: QKeyEvent) -> bool:
        if not self.popup.isVisible():
            return False
        key = e.key()
        if key in (Qt.Key_Down, Qt.Key_Up):
            n = self.popup.count()
            step = 1 if key == Qt.Key_Down else -1
            row = self.popup.currentRow()
            for _ in range(n):
                row = (row + step) % n
                if self.popup.item(row).flags() & Qt.ItemIsEnabled:
                    self.popup.setCurrentRow(row)
                    break
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab) and not (e.modifiers() & (Qt.ShiftModifier | Qt.AltModifier)):
            item = self.popup.currentItem()
            if item is not None and item.flags() & Qt.ItemIsEnabled:
                self._accept_item(item)
                return True
            return False
        if key == Qt.Key_Escape:
            self.hide_popup()
            return True
        return False

    def _accept_item(self, item: QListWidgetItem) -> None:
        kind = item.data(ROLE_KIND)
        value = item.data(ROLE_VALUE)
        if not kind:
            return
        if kind == "model":
            self.edit.clear()
            self.hide_popup()
            self.set_model(value, emit=True)
            self.edit.setFocus()
            return
        if value == "/model":
            self.set_text("/model ")      # model listesine geç
            return
        self.edit.clear()
        self.hide_popup()
        self.submitted.emit(value)

    # ---- gönderme -----------------------------------------------------------

    def _on_send_clicked(self) -> None:
        if self._running:
            self.stop_requested.emit()
        else:
            self._submit()

    def _submit(self) -> None:
        if self._running and not self.edit.toPlainText().strip().startswith("/"):
            return
        text = self.edit.toPlainText().strip()
        if not text and not self.attachments.items():
            return
        self.edit.clear()
        self.hide_popup()
        self.submitted.emit(text)

    # ---- sürükle-bırak (çerçevenin tamamı) ----

    def dragEnterEvent(self, e) -> None:
        md = e.mimeData()
        if local_files(md) or md.hasImage():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dropEvent(self, e) -> None:
        md = e.mimeData()
        files = local_files(md)
        if files:
            self.files_added.emit(files)
            e.acceptProposedAction()
        elif md.hasImage() and isinstance(md.imageData(), QImage):
            self.image_added.emit(md.imageData())
            e.acceptProposedAction()

    def set_text(self, text: str) -> None:
        self.edit.setPlainText(text)
        cur = self.edit.textCursor()
        cur.movePosition(QTextCursor.End)
        self.edit.setTextCursor(cur)
        self.edit.setFocus()

    def focus(self) -> None:
        self.edit.setFocus()
