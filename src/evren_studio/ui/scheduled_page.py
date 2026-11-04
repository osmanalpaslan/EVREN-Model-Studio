"""Zamanlanmış görevler sayfası (Madde 12c, 2026-11-05) — Claude Code masaüstündeki "Scheduled" sayfası gibi:
liste → görev ayrıntısı (Şimdi çalıştır, Etkin/Duraklatıldı, Düzenle, Sil, Geçmiş) → oluşturma/düzenleme penceresi.
Çalıştırma motoru: ui/schedule_host.py · zaman hesabı: agent/schedule.py.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Qt, QTime, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ..agent import router
from ..agent import schedule as sched
from . import icons, theme
from .base_page import BasePage, card
from .schedule_host import STATUS_LABELS

MODES = (("auto", "Otomatik — hiçbir işlem için onay istemez (önerilir)"),
         ("plan", "Plan — yalnız okur ve rapor yazar, dosyaya dokunmaz"))
MODE_SHORT = {"auto": "Otomatik", "plan": "Plan (salt okuma)"}
EXAMPLES = ("Her sabah testleri çalıştır, kırmızı test varsa nedenini özetle.",
            "Hafta içi her gün bağımlılıkların güncel sürümlerini denetle ve rapor yaz.",
            "Her cuma bu haftaki git değişikliklerinin özetini CHANGELOG taslağına yaz.")


def when_text(dt: datetime | None, now: datetime | None = None) -> str:
    """Yerel zaman → "Bugün 09:00" / "Yarın 09:00" / "Cuma 09:00" / "12.11 09:00"."""
    if dt is None:
        return "—"
    now = now or datetime.now()
    hm = dt.strftime("%H:%M")
    days = (dt.date() - now.date()).days
    if days == 0:
        return f"Bugün {hm}"
    if days == 1:
        return f"Yarın {hm}"
    if days == -1:
        return f"Dün {hm}"
    if 1 < days < 7:
        return f"{sched.WEEKDAYS_TR[dt.weekday()]} {hm}"
    return dt.strftime("%d.%m.%Y %H:%M")


def _hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", "dim")
    lab.setWordWrap(True)
    return lab


class TaskDialog(QDialog):
    """Yeni görev / düzenleme. Eksik veya geçersiz alanda "Kaydet" kapalı kalır, nedeni altta yazar."""

    def __init__(self, ctx, row=None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.row = row
        self.setWindowTitle("Görevi düzenle" if row else "Yeni zamanlanmış görev")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        self.name = QLineEdit()
        self.name.setPlaceholderText("ör. Sabah test denetimi")
        form.addRow("Ad:", self.name)
        self.description = QLineEdit()
        self.description.setPlaceholderText("Listede görünen kısa açıklama (isteğe bağlı)")
        form.addRow("Açıklama:", self.description)
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Görev çalışınca ajanın ne yapacağını yazın.\nÖrn.: " + EXAMPLES[0])
        self.prompt.setMinimumHeight(110)
        form.addRow("Talimat:", self.prompt)
        ws_row = QHBoxLayout()
        self.workspace = QLineEdit()
        self.workspace.setPlaceholderText("Görevin çalışacağı proje klasörü")
        pick = QPushButton("Seç…")
        pick.setIcon(icons.icon("folder", size=15))
        pick.setMinimumWidth(100)                    # "Seç…" kesiliyordu (2026-11-05 ekran görüntüsü)
        pick.clicked.connect(self._pick)
        ws_row.addWidget(self.workspace, 1)
        ws_row.addWidget(pick)
        form.addRow("Klasör:", ws_row)
        self.model = QComboBox()
        ids = [router.AUTO_PRO_ID] + [m.id for m in ctx.chat_models() if m.id != router.AUTO_PRO_ID]
        self.model.addItems(ids)
        form.addRow("Model:", self.model)
        self.mode = QComboBox()
        for key, label in MODES:
            self.mode.addItem(label, key)
        form.addRow("Çalışma modu:", self.mode)
        self.kind = QComboBox()
        for k in sched.KINDS:
            self.kind.addItem(sched.KIND_LABELS[k], k)
        form.addRow("Sıklık:", self.kind)
        self.time = QTimeEdit()
        self.time.setDisplayFormat("HH:mm")
        self.time_label = QLabel("Saat:")
        form.addRow(self.time_label, self.time)
        self.weekday = QComboBox()
        self.weekday.addItems(list(sched.WEEKDAYS_TR))
        self.weekday_label = QLabel("Gün:")
        form.addRow(self.weekday_label, self.weekday)
        self.cron = QLineEdit()
        self.cron.setPlaceholderText("dakika saat gün ay haftanın-günü — ör. 0 9 * * 1-5")
        self.cron_label = QLabel("Cron:")
        form.addRow(self.cron_label, self.cron)
        lay.addLayout(form)
        lay.addWidget(_hint("Görev yalnız uygulama açıkken ve bilgisayar uyanıkken çalışır. Kaçırılan zamanlar için "
                            "uygulama açılınca son 7 gün içindeki en yenisi bir kez telafi edilir. Başında kimse "
                            "olmadığından yalnız onay istemeyen modlar seçilebilir."))
        self.error = QLabel("")
        self.error.setProperty("role", "warning")
        self.error.setWordWrap(True)
        lay.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Save).setText("Kaydet" if row else "Oluştur")
        self.buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        self.buttons.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self._fill(row)
        for sig in (self.name.textChanged, self.prompt.textChanged, self.workspace.textChanged,
                    self.cron.textChanged, self.time.timeChanged):
            sig.connect(self._validate)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self._kind_changed()

    def _fill(self, row) -> None:
        if row is None:
            self.time.setTime(QTime(9, 0))
            last = (self.ctx.settings.recent_workspaces or [""])[0]
            self.workspace.setText(last)
            self.kind.setCurrentIndex(sched.KINDS.index("daily"))
            return
        self.name.setText(row["name"])
        self.description.setText(row["description"] or "")
        self.prompt.setPlainText(row["prompt"])
        self.workspace.setText(row["workspace"] or "")
        if self.model.findText(row["model"]) < 0:
            self.model.addItem(row["model"])
        self.model.setCurrentText(row["model"])
        self.mode.setCurrentIndex(max(0, self.mode.findData(row["mode"])))
        self.kind.setCurrentIndex(max(0, self.kind.findData(row["kind"])))
        h, m = sched.Spec.from_row(row).hm()
        self.time.setTime(QTime(h, m))
        self.weekday.setCurrentIndex(int(row["weekday"] or 0))
        self.cron.setText(row["cron"] or "")

    def _pick(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Görevin klasörü", self.workspace.text())
        if d:
            self.workspace.setText(d)

    def _kind_changed(self, *_a) -> None:
        k = self.kind.currentData()
        show_time = k in ("daily", "weekdays", "weekly", "hourly")
        self.time_label.setText("Dakika:" if k == "hourly" else "Saat:")
        self.time.setDisplayFormat("mm" if k == "hourly" else "HH:mm")
        for w in (self.time_label, self.time):
            w.setVisible(show_time)
        for w in (self.weekday_label, self.weekday):
            w.setVisible(k == "weekly")
        for w in (self.cron_label, self.cron):
            w.setVisible(k == "custom")
        self._validate()

    def values(self) -> dict:
        t = self.time.time()
        return {
            "name": self.name.text().strip(),
            "description": self.description.text().strip(),
            "prompt": self.prompt.toPlainText().strip(),
            "workspace": self.workspace.text().strip(),
            "model": self.model.currentText().strip() or router.AUTO_PRO_ID,
            "mode": self.mode.currentData() or "auto",
            "kind": self.kind.currentData(),
            "time_hm": f"{t.hour():02d}:{t.minute():02d}",
            "weekday": self.weekday.currentIndex(),
            "cron": self.cron.text().strip(),
        }

    def problem(self) -> str:
        from pathlib import Path

        v = self.values()
        if not v["name"]:
            return "Ad gerekli."
        clash = self.ctx.db._exec("SELECT id FROM scheduled_tasks WHERE name=? COLLATE NOCASE",
                                  (v["name"],)).fetchone()
        if clash and (self.row is None or clash["id"] != self.row["id"]):
            return "Bu adla bir görev zaten var; ad benzersiz olmalı."
        if not v["prompt"]:
            return "Talimat gerekli."
        if not v["workspace"]:
            return "Görevin çalışacağı klasörü seçin."
        if not Path(v["workspace"]).is_dir():
            return "Seçilen klasör bulunamadı."
        return sched.Spec(v["kind"], v["time_hm"], v["weekday"], v["cron"]).validate()

    def _validate(self, *_a) -> None:
        p = self.problem()
        self.error.setText(p)
        self.buttons.button(QDialogButtonBox.Save).setEnabled(not p)

    def _accept(self) -> None:
        if not self.problem():
            self.accept()


class ScheduledPage(BasePage):
    title = "Zamanlanmış görevler"
    open_session = Signal(int)

    def __init__(self, ctx, host, parent=None):
        super().__init__(ctx, parent)
        self.host = host
        self.current_id: int | None = None
        self._runs_shown = 20
        self.new_btn = QPushButton("  Yeni görev")
        self.new_btn.setProperty("variant", "primary")
        self.new_btn.setIcon(icons.icon("plus", theme.current().on_accent, 15))   # ana düğme zemininde okunur
        self.new_btn.clicked.connect(self.new_task)
        self.header_extra.addWidget(self.new_btn)
        self.stack = QStackedWidget()
        self.root.addWidget(self.stack, 1)

        # ---- liste ----
        lst = QWidget()
        ll = QVBoxLayout(lst)
        ll.setContentsMargins(0, 0, 0, 0)
        self.state_note = _hint("")
        ll.addWidget(self.state_note)
        self.list = QListWidget()
        self.list.setObjectName("ScheduledList")
        self.list.setSpacing(4)
        self.list.itemClicked.connect(lambda it: self.show_task(it.data(Qt.UserRole)))
        ll.addWidget(self.list, 1)
        self.empty = QWidget()
        el = QVBoxLayout(self.empty)
        el.addStretch(1)
        ic = QLabel()
        ic.setPixmap(icons.icon("clock", size=40).pixmap(40, 40))
        ic.setAlignment(Qt.AlignCenter)
        el.addWidget(ic)
        t = QLabel("Henüz zamanlanmış görev yok")
        t.setProperty("role", "h2")
        t.setAlignment(Qt.AlignCenter)
        el.addWidget(t)
        ex = _hint("Tekrarlayan işleri ajana bırakın; zamanı gelince yeni bir oturumda kendiliğinden çalışır.\n"
                   + "\n".join("• " + e for e in EXAMPLES))
        ex.setAlignment(Qt.AlignCenter)
        el.addWidget(ex)
        b = QPushButton("  İlk görevi oluştur")
        b.setIcon(icons.icon("plus", size=15))
        b.clicked.connect(self.new_task)
        el.addWidget(b, 0, Qt.AlignCenter)
        el.addStretch(2)
        ll.addWidget(self.empty, 1)
        self.stack.addWidget(lst)

        # ---- ayrıntı ----
        det = QScrollArea()
        det.setWidgetResizable(True)
        det.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        dl = QVBoxLayout(inner)
        dl.setContentsMargins(0, 0, 8, 0)
        back = QPushButton("←  Zamanlanmış görevler")
        back.setProperty("variant", "ghost")
        back.clicked.connect(self.show_list)
        dl.addWidget(back, 0, Qt.AlignLeft)
        head = QHBoxLayout()
        self.d_title = QLabel()
        self.d_title.setProperty("role", "h1")
        self.d_title.setWordWrap(True)
        head.addWidget(self.d_title, 1)
        self.enabled = QCheckBox("Etkin")
        self.enabled.setToolTip("Kapalıyken görev zamanında çalışmaz (Duraklatıldı); silinmez")
        self.enabled.toggled.connect(self._toggle_enabled)
        head.addWidget(self.enabled)
        self.run_btn = QPushButton("  Şimdi çalıştır")
        self.run_btn.setProperty("variant", "primary")
        self.run_btn.setIcon(icons.icon("send", theme.current().on_accent, 14))
        self.run_btn.clicked.connect(self._run_or_stop)
        head.addWidget(self.run_btn)
        edit = QPushButton("  Düzenle")
        edit.setIcon(icons.icon("pencil", size=14))
        edit.clicked.connect(self.edit_task)
        head.addWidget(edit)
        delete = QPushButton("Sil")
        delete.setProperty("variant", "danger")
        delete.clicked.connect(self.delete_task)
        head.addWidget(delete)
        dl.addLayout(head)
        self.d_desc = _hint("")
        dl.addWidget(self.d_desc)
        c, l = card()
        self.d_info = QLabel()
        self.d_info.setWordWrap(True)
        self.d_info.setTextFormat(Qt.RichText)
        l.addWidget(self.d_info)
        dl.addWidget(c)
        c, l = card()
        h = QLabel("Talimat")
        h.setProperty("role", "h2")
        l.addWidget(h)
        self.d_prompt = QLabel()
        self.d_prompt.setWordWrap(True)
        self.d_prompt.setTextInteractionFlags(Qt.TextSelectableByMouse)
        l.addWidget(self.d_prompt)
        dl.addWidget(c)
        c, l = card()
        h = QLabel("Geçmiş")
        h.setProperty("role", "h2")
        l.addWidget(h)
        l.addWidget(_hint("Bir satıra tıklayınca o çalıştırmanın oturumu açılır. Atlanan çalıştırmaların nedeni "
                          "satırda yazar."))
        self.history = QListWidget()
        self.history.setObjectName("ScheduledHistory")
        self.history.setMinimumHeight(220)
        self.history.itemClicked.connect(self._open_run)
        l.addWidget(self.history)
        self.more_btn = QPushButton("Daha fazla göster")
        self.more_btn.clicked.connect(self._more)
        l.addWidget(self.more_btn, 0, Qt.AlignLeft)
        dl.addWidget(c)
        dl.addStretch(1)
        det.setWidget(inner)
        self.stack.addWidget(det)
        host.changed.connect(self.refresh)
        self.refresh()

    # ---- liste ----

    def refresh(self) -> None:
        rows = self.ctx.db.list_scheduled_tasks()
        s = self.ctx.settings
        note = "Görevler yalnız EVREN Studio açıkken ve bilgisayar uyanıkken çalışır."
        if not s.schedule_enabled:
            note = "Zamanlayıcı Ayarlar > Zamanlanmış görevler'den KAPATILMIŞ: görevler kendiliğinden çalışmaz."
        elif s.schedule_keep_awake:
            note += " Bilgisayarı uyanık tutma açık."
        self.state_note.setText(note)
        self.list.clear()
        for r in rows:
            it = QListWidgetItem()
            it.setData(Qt.UserRole, r["id"])
            w = self._row_widget(r)
            it.setSizeHint(QSize(0, w.sizeHint().height() + 6))
            self.list.addItem(it)
            self.list.setItemWidget(it, w)
        self.list.setVisible(bool(rows))
        self.empty.setVisible(not rows)
        if self.current_id is not None:
            if self.ctx.db.get_scheduled_task(self.current_id) is None:
                self.show_list()
            elif self.stack.currentIndex() == 1:
                self._fill_detail()

    def _row_widget(self, r) -> QWidget:
        w = QFrame()
        w.setObjectName("card")
        h = QHBoxLayout(w)
        h.setContentsMargins(14, 10, 14, 10)
        col = QVBoxLayout()
        name = QLabel(r["name"])
        name.setStyleSheet("font-weight: 600;")
        col.addWidget(name)
        spec = sched.Spec.from_row(r)
        sub = spec.describe()
        if r["description"]:
            sub = f"{r['description']}  ·  {sub}"
        s = QLabel(sub)
        s.setProperty("role", "dim")
        col.addWidget(s)
        h.addLayout(col, 1)
        h.addWidget(self._status_label(r))
        return w

    def _status_label(self, r) -> QLabel:
        if self.host.running_task() == r["id"]:
            text = "Çalışıyor"
        elif self.host.is_busy(r["id"]):
            text = "Sırada"
        elif not r["enabled"]:
            text = "Duraklatıldı"
        elif r["kind"] == "manual":
            text = "Elle"
        else:
            text = "Sonraki: " + when_text(self.host.next_run(r))
        lab = QLabel(text)
        lab.setProperty("role", "dim")
        return lab

    def show_list(self) -> None:
        self.current_id = None
        self.stack.setCurrentIndex(0)
        self.refresh()

    # ---- ayrıntı ----

    def show_task(self, task_id: int) -> None:
        self.current_id = int(task_id)
        self._runs_shown = 20
        self.stack.setCurrentIndex(1)
        self._fill_detail()

    def _fill_detail(self) -> None:
        r = self.ctx.db.get_scheduled_task(self.current_id)
        if r is None:
            return
        self.d_title.setText(r["name"])
        self.d_desc.setText(r["description"] or "")
        self.d_desc.setVisible(bool(r["description"]))
        self.enabled.blockSignals(True)
        self.enabled.setChecked(bool(r["enabled"]))
        self.enabled.setText("Etkin" if r["enabled"] else "Duraklatıldı")
        self.enabled.blockSignals(False)
        busy = self.host.is_busy(r["id"])
        self.run_btn.setText("  Durdur" if busy else "  Şimdi çalıştır")
        self.run_btn.setIcon(icons.icon("stop" if busy else "send", theme.current().on_accent, 14))
        spec = sched.Spec.from_row(r)
        nxt = self.host.next_run(r)
        rows = [
            ("Durum", "Etkin" if r["enabled"] else "Duraklatıldı"),
            ("Zamanlama", spec.describe()),
            ("Sonraki çalışma", when_text(nxt) if nxt else ("—" if r["kind"] == "manual" else "duraklatıldı")),
            ("Klasör", r["workspace"] or "—"),
            ("Model", r["model"]),
            ("Mod", MODE_SHORT.get(r["mode"], r["mode"])),
        ]
        self.d_info.setText("<table cellspacing='4'>" + "".join(
            f"<tr><td style='padding-right:18px'><b>{k}</b></td><td>{_esc(v)}</td></tr>" for k, v in rows)
            + "</table>")
        self.d_prompt.setText(r["prompt"])
        self.history.clear()
        runs = self.ctx.db.list_scheduled_runs(r["id"], limit=self._runs_shown)
        for run in runs:
            when = sched.to_local(run["started_at"] or run["scheduled_for"] or run["created_at"])
            label = STATUS_LABELS.get(run["status"], run["status"])
            extra = []
            if run["manual"]:
                extra.append("elle")
            if run["catch_up"]:
                extra.append("telafi")
            text = f"{when_text(when)}  ·  {label}" + (f" ({', '.join(extra)})" if extra else "")
            if run["reason"]:
                text += f"  —  {run['reason']}"
            it = QListWidgetItem(icons.icon(_status_icon(run["status"]), size=15), text)
            it.setData(Qt.UserRole, run["session_id"])
            it.setToolTip(run["reason"] or label)
            self.history.addItem(it)
        if not runs:
            self.history.addItem(QListWidgetItem("Henüz çalışmadı. “Şimdi çalıştır” ile deneyebilirsiniz."))
        self.more_btn.setVisible(self.ctx.db.count_scheduled_runs(r["id"]) > self._runs_shown)

    def _more(self) -> None:
        self._runs_shown += 20
        self._fill_detail()

    def _open_run(self, item: QListWidgetItem) -> None:
        sid = item.data(Qt.UserRole)
        if sid:
            self.open_session.emit(int(sid))

    def _toggle_enabled(self, on: bool) -> None:
        if self.current_id is None:
            return
        fields = {"enabled": int(on)}
        if on:
            # Yeniden etkinleştirilen görev duraklatılmışken geçen zamanları "kaçırılmış" saymasın
            fields["last_handled_at"] = sched.to_utc_iso(datetime.now())
        self.ctx.db.update_scheduled_task(self.current_id, **fields)
        self.host.apply_keep_awake()
        self.refresh()

    def _run_or_stop(self) -> None:
        if self.current_id is None:
            return
        if self.host.is_busy(self.current_id):
            self.host.stop_task(self.current_id)
        else:
            self.host.run_now(self.current_id)
        self.refresh()

    # ---- oluştur / düzenle / sil ----

    def new_task(self) -> None:
        dlg = TaskDialog(self.ctx, None, self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        tid = self.ctx.db.create_scheduled_task(**v, last_handled_at=sched.to_utc_iso(datetime.now()))
        self.host.apply_keep_awake()
        self.show_task(tid)

    def edit_task(self) -> None:
        r = self.ctx.db.get_scheduled_task(self.current_id) if self.current_id else None
        if r is None:
            return
        dlg = TaskDialog(self.ctx, r, self)
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        changed_schedule = any(str(v[k]) != str(r[k]) for k in ("kind", "time_hm", "weekday", "cron"))
        if changed_schedule:   # yeni zamanlama geçmişe dönük "kaçırılan" üretmesin
            v["last_handled_at"] = sched.to_utc_iso(datetime.now())
        self.ctx.db.update_scheduled_task(r["id"], **v)
        self.host.apply_keep_awake()
        self.refresh()

    def delete_task(self) -> None:
        r = self.ctx.db.get_scheduled_task(self.current_id) if self.current_id else None
        if r is None:
            return
        if QMessageBox.question(self, "Görevi sil",
                                f"“{r['name']}” silinsin mi?\n\nGörevin başlattığı oturumlar silinmez; kenar "
                                "çubuğunda kalır.") != QMessageBox.Yes:
            return
        self.host.stop_task(r["id"])
        self.ctx.db.delete_scheduled_task(r["id"])
        self.host.apply_keep_awake()
        self.show_list()


def _status_icon(status: str) -> str:
    return {"tamamlandi": "circle-check", "hata": "alert", "yarim": "circle-half", "atlandi": "circle",
            "durduruldu": "stop", "calisiyor": "refresh", "sirada": "clock", "kota_bekliyor": "clock"}.get(status, "dot")


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
