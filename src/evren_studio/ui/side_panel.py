"""Sağ panel: Görevler, Değişiklikler (geri alma), Dosyalar, Terminal, Çalışma, Git."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QDir, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileSystemModel,
    QFrame,
    QStackedWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,

    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..agent.tools import ToolBox, ToolError, Workspace, decode_bytes, diff_stats, make_diff, revert_file
from . import icons, theme
from .transcript import CodeView, DiffView, faint_label, icon_button
from .workers import Task


def _empty(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", "faint")
    lab.setAlignment(Qt.AlignCenter)
    lab.setWordWrap(True)
    lab.setContentsMargins(16, 30, 16, 30)
    return lab


class TodosTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        self.progress = faint_label("")
        lay.addWidget(self.progress)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setSpacing(2)
        lay.addWidget(self.list, 1)
        self.empty = _empty("Ajan çok adımlı bir iş planladığında görev listesi burada görünür.")
        lay.addWidget(self.empty)
        self.set_todos([])

    def set_todos(self, todos: list[dict]) -> None:
        p = theme.current()
        self.list.clear()
        for t in todos:
            status = t.get("status")
            name, color = {
                "completed": ("circle-check", "success"),
                "in_progress": ("circle-half", "accent"),
            }.get(status, ("circle", "text_faint"))
            it = QListWidgetItem(icons.icon(name, color, 16), t.get("content", ""))
            if status == "completed":
                f = it.font()
                f.setStrikeOut(True)
                it.setFont(f)
                it.setForeground(Qt.gray)
            self.list.addItem(it)
        done = sum(1 for t in todos if t.get("status") == "completed")
        self.progress.setText(f"{done}/{len(todos)} tamamlandı" if todos else "")
        self.empty.setVisible(not todos)
        self.list.setVisible(bool(todos))


class ChangesTab(QWidget):
    changed = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.session_id: int | None = None
        self.workspace: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)
        head = QHBoxLayout()
        self.summary = faint_label("")
        head.addWidget(self.summary, 1)
        self.revert_all_btn = QPushButton("Tümünü geri al")
        self.revert_all_btn.setIcon(icons.icon("undo", size=15))
        self.revert_all_btn.clicked.connect(self.revert_all)
        head.addWidget(self.revert_all_btn)
        lay.addLayout(head)
        split = QSplitter(Qt.Vertical)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show)
        split.addWidget(self.list)
        prev = QWidget()
        pl = QVBoxLayout(prev)
        pl.setContentsMargins(0, 6, 0, 0)
        self.diff = DiffView("", auto_height=False)
        self.diff.setMinimumHeight(120)
        pl.addWidget(self.diff, 1)
        row = QHBoxLayout()
        self.revert_btn = QPushButton("Bu değişikliği geri al")
        self.revert_btn.setIcon(icons.icon("undo", size=15))
        self.revert_btn.clicked.connect(self.revert_selected)
        row.addWidget(self.revert_btn)
        row.addStretch(1)
        pl.addLayout(row)
        split.addWidget(prev)
        split.setSizes([160, 300])
        lay.addWidget(split, 1)
        self.split = split
        self.empty = _empty("Ajanın bu oturumda yaptığı dosya değişiklikleri burada listelenir; "
                            "her birini tek tıkla geri alabilirsiniz.")
        lay.addWidget(self.empty)
        self.rows: list = []
        self._stats: dict[int, tuple[int, int]] = {}     # değişiklik kimliği → (+, −)
        self._dirty = False
        self.refresh()

    def set_session(self, session_id: int | None, workspace: str | None) -> None:
        self.session_id = session_id
        self.workspace = workspace
        self.refresh()

    def refresh(self) -> None:
        """PERFORMANS (2026-11-12): liste, sekme GÖRÜNÜRKEN doldurulur ve her değişikliğin +/− sayısı kimliğine göre
        önbellekte tutulur (kayıt değişmez; yalnız "geri alındı" bayrağı değişir). Eskiden her oturum açılışında ve
        ajanın HER dosya değişikliğinde oturumdaki tüm farklar baştan hesaplanıyordu (146 değişiklikte ~0,25 sn,
        uzun işte karesel büyüme)."""
        self.rows = list(self.ctx.db.list_file_change_meta(self.session_id)) if self.session_id else []
        files = {r["path"] for r in self.rows}
        active = [r for r in self.rows if not r["reverted"]]
        self.summary.setText(f"{len(files)} dosya, {len(self.rows)} değişiklik" if self.rows else "")
        self.revert_all_btn.setEnabled(bool(active))
        self.empty.setVisible(not self.rows)
        self.split.setVisible(bool(self.rows))
        self._dirty = True
        if self.isVisible():
            self._fill()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        if getattr(self, "_dirty", False):
            self._fill()

    def _full(self, r):
        """İçerikli satır: panelin hafif satırı (içeriksiz) ise veritabanından okunur; dışarıdan tam satır da gelebilir."""
        if "before_text" in r.keys():
            return r
        return self.ctx.db.get_file_change(r["id"]) or r

    @staticmethod
    def _is_new(r) -> bool:
        return bool(r["is_new"]) if "is_new" in r.keys() else r["before_text"] is None

    def _stat(self, r) -> tuple[int, int]:
        key = r["id"]
        if key not in self._stats:
            f = self._full(r)
            self._stats[key] = diff_stats(make_diff(f["before_text"], f["after_text"], f["path"]))
        return self._stats[key]

    def _fill(self) -> None:
        self._dirty = False
        self.list.clear()
        for r in self.rows:
            add, rem = self._stat(r)
            label = f"{r['path']}   +{add} −{rem}"
            if r["reverted"]:
                label += "   (geri alındı)"
            elif self._is_new(r):
                label += "   (yeni)"
            it = QListWidgetItem(icons.icon("file", "muted" if r["reverted"] else "text_dim", 15), label)
            self.list.addItem(it)
        if self.rows:
            self.list.setCurrentRow(len(self.rows) - 1)

    def _show(self, row: int) -> None:
        if 0 <= row < len(self.rows):
            r = self.rows[row]
            f = self._full(r)
            self.diff.set_diff(make_diff(f["before_text"], f["after_text"], f["path"]))
            self.revert_btn.setEnabled(not r["reverted"])
        else:
            self.diff.set_diff("")
            self.revert_btn.setEnabled(False)

    def _revert(self, r, ask_force: bool = True) -> bool:
        if not self.workspace:
            return False
        r = self._full(r)
        try:
            msg = revert_file(Path(self.workspace), r["path"], r["before_text"], r["after_text"])
        except ToolError as exc:
            if not ask_force:
                raise
            if QMessageBox.question(
                self, "Dosya sonradan değişmiş",
                f"{exc}\n\nYine de değişiklik öncesi hale döndürülsün mü?",
            ) != QMessageBox.Yes:
                return False
            msg = revert_file(Path(self.workspace), r["path"], r["before_text"], r["after_text"], force=True)
        self.ctx.db.mark_change_reverted(r["id"])
        self.summary.setText(msg)
        return True

    def revert_selected(self) -> None:
        row = self.list.currentRow()
        if not (0 <= row < len(self.rows)):
            return
        r = self.rows[row]
        if self._is_new(r):
            q = f"{r['path']} ajan tarafından oluşturulmuştu. Geri almak dosyayı SİLER. Devam edilsin mi?"
        else:
            q = f"{r['path']} bu değişiklikten önceki haline döndürülsün mü?"
        if QMessageBox.question(self, "Değişikliği geri al", q) != QMessageBox.Yes:
            return
        try:
            if self._revert(r):
                self.refresh()
                self.changed.emit()
        except (ToolError, OSError) as exc:
            QMessageBox.warning(self, "Geri alınamadı", str(exc))

    def revert_all(self) -> None:
        active = [r for r in self.rows if not r["reverted"]]
        if not active:
            return
        if QMessageBox.question(
            self, "Tüm değişiklikleri geri al",
            f"Bu oturumdaki {len(active)} değişiklik sondan başa doğru geri alınacak. "
            "Ajanın oluşturduğu dosyalar silinecek. Devam edilsin mi?",
        ) != QMessageBox.Yes:
            return
        errors = self.revert_rows(active)
        if errors:
            QMessageBox.warning(self, "Bazı değişiklikler geri alınamadı", "\n\n".join(errors))

    def revert_rows(self, rows) -> list[str]:
        """Verilen değişiklikleri sondan başa geri alır (soru sormaz). Dönüş: hata satırları."""
        errors = []
        for r in sorted((r for r in rows if not r["reverted"]), key=lambda r: r["id"], reverse=True):
            try:
                self._revert(r, ask_force=False)
            except (ToolError, OSError) as exc:
                errors.append(f"{r['path']}: {exc}")
        self.refresh()
        self.changed.emit()
        return errors


class _YolEtiketi(QLabel):
    """Uzun klasör yolunu ORTADAN kısaltan etiket (C:\\Users\\…\\proje); tamamı ipucunda.

    2026-11-01 arayüz denetimi: yol etiketi panele sığmayıp yarıda kesiliyordu.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("role", "faint")
        self._tam = ""
        self.setMinimumWidth(40)

    def set_full(self, text: str) -> None:
        self._tam = text or ""
        self.setToolTip(self._tam)
        self._kisalt()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._kisalt()

    def _kisalt(self) -> None:
        fm, w = self.fontMetrics(), max(20, self.contentsRect().width())
        satirlar = self._tam.splitlines()
        out = [fm.elidedText(s, Qt.ElideMiddle if i == 0 else Qt.ElideRight, w) for i, s in enumerate(satirlar)]
        super().setText("\n".join(out))


class FilesTab(QWidget):
    attach_requested = Signal(str)

    def __init__(self, parent=None, ctx=None):
        super().__init__(parent)
        self.ctx = ctx                                   # F6 #15 güvenilmeyen klasör işareti için (ayar)
        self.root: Path | None = None
        self.current: Path | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 8, 6, 8)
        lay.setSpacing(6)
        head = QHBoxLayout()
        self.root_label = _YolEtiketi()
        head.addWidget(self.root_label, 1)
        open_btn = icon_button("external", "Klasörü Dosya Gezgini'nde aç", 15)
        open_btn.clicked.connect(self._open_explorer)
        head.addWidget(open_btn)
        lay.addLayout(head)
        self.split = QSplitter(Qt.Vertical)
        self.model = QFileSystemModel(self)
        self.model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot | QDir.Hidden)
        self.model.setNameFilterDisables(False)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        for c in (1, 2, 3):
            self.tree.hideColumn(c)
        self.tree.setAnimated(True)
        self.tree.setIndentation(14)
        self.tree.clicked.connect(self._open)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.split.addWidget(self.tree)
        prev = QWidget()
        pl = QVBoxLayout(prev)
        pl.setContentsMargins(0, 4, 0, 0)
        pl.setSpacing(6)
        row = QHBoxLayout()
        self.file_label = faint_label("Bir dosya seçin")
        row.addWidget(self.file_label, 1)
        self.attach_btn = icon_button("paperclip", "Sohbete ekle (@)", 15)
        self.attach_btn.clicked.connect(self._attach)
        row.addWidget(self.attach_btn)
        self.edit_btn = icon_button("pencil", "Düzenle", 15, checkable=True)
        self.edit_btn.toggled.connect(self._toggle_edit)
        row.addWidget(self.edit_btn)
        self.save_btn = QPushButton("Kaydet")
        self.save_btn.setVisible(False)
        self.save_btn.clicked.connect(self._save)
        row.addWidget(self.save_btn)
        pl.addLayout(row)
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("CodeView")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setFont(theme.code_font(9))
        # F5 #9 çıktı önizleme: Excel/CSV tablo (sayfa seçimli), resim; diğerleri metin
        from PySide6.QtWidgets import QComboBox, QLabel, QScrollArea, QStackedWidget, QTableWidget

        self.sheet_combo = QComboBox()
        self.sheet_combo.setVisible(False)
        self.sheet_combo.activated.connect(lambda _i: self._show_table(self.current, self.sheet_combo.currentText()))
        pl.addWidget(self.sheet_combo)
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        img_scroll = QScrollArea()
        img_scroll.setWidgetResizable(True)
        img_scroll.setWidget(self.image)
        self.view_stack = QStackedWidget()
        for w in (self.preview, self.table, img_scroll):
            self.view_stack.addWidget(w)
        pl.addWidget(self.view_stack, 1)
        self.split.addWidget(prev)
        self.split.setSizes([260, 260])
        lay.addWidget(self.split, 1)
        self.empty = _empty("Bu oturum bir proje klasörüne bağlı değil.")
        lay.addWidget(self.empty)
        self._meta = None
        self.set_root(None)

    def set_root(self, root: str | None) -> None:
        self.root = Path(root) if root else None
        has = self.root is not None and self.root.is_dir()
        self.split.setVisible(has)
        self.empty.setVisible(not has)
        if has:
            idx = self.model.setRootPath(str(self.root))
            self.tree.setRootIndex(idx)
            self.root_label.set_full(str(self.root))
            self._update_root_label()
        else:
            self.root_label.set_full("")
        self.current = None
        self.preview.clear()
        self.file_label.setText("Bir dosya seçin")

    TABLE_SUFFIXES = {".xlsx", ".xlsm", ".csv", ".tsv"}
    IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

    def _show_table(self, p: Path | None, sheet: str | None = None) -> bool:
        from PySide6.QtWidgets import QTableWidgetItem

        from ..agent import tables

        if p is None:
            return False
        try:
            data = tables.preview(p, sheet or None)
        except (tables.TableError, OSError) as exc:
            self.file_label.setText(f"{p.name}: {exc}")
            return False
        rows, cols = data["rows"], min(data["cols"], 60)
        self.table.clear()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(cols)
        for r, row in enumerate(rows):
            for c in range(min(cols, len(row))):
                self.table.setItem(r, c, QTableWidgetItem(str(row[c])))
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.addItems(data["sheets"])
        self.sheet_combo.setCurrentText(data["sheet"])
        self.sheet_combo.blockSignals(False)
        self.sheet_combo.setVisible(len(data["sheets"]) > 1)
        more = f" · ilk {len(rows)} / {data['total']} satır" if data["total"] > len(rows) else f" · {data['total']} satır"
        self.file_label.setText(f"{self.root and p.relative_to(self.root.resolve()).as_posix() or p.name}{more}")
        self.view_stack.setCurrentIndex(1)
        return True

    def _show_image(self, p: Path) -> bool:
        from PySide6.QtGui import QPixmap

        pm = QPixmap(str(p))
        if pm.isNull():
            return False
        w = max(200, self.view_stack.width() - 20)
        self.image.setPixmap(pm if pm.width() <= w else pm.scaledToWidth(w, Qt.SmoothTransformation))
        self.file_label.setText(f"{p.name} · {pm.width()}×{pm.height()}")
        self.view_stack.setCurrentIndex(2)
        return True

    def _open(self, index) -> None:
        path = Path(self.model.filePath(index))
        if not path.is_file() or self.root is None:
            return
        self.edit_btn.setChecked(False)
        self.sheet_combo.setVisible(False)
        suffix = path.suffix.lower()
        if suffix in self.TABLE_SUFFIXES or suffix in self.IMAGE_SUFFIXES:
            self.current = path.resolve()
            self.edit_btn.setEnabled(False)          # tablo/resim önizlemesi düzenlenmez
            self._meta = None
            ok = self._show_table(self.current) if suffix in self.TABLE_SUFFIXES else self._show_image(self.current)
            if ok:
                return
        self.edit_btn.setEnabled(True)
        self.view_stack.setCurrentIndex(0)
        try:
            ws = Workspace(self.root)
            p = ws.resolve(str(path))
            tb = ToolBox(ws)
            self._meta = tb.load_text(p)
        except (ToolError, OSError) as exc:
            self.file_label.setText(f"{path.name}: {exc}")
            self.preview.clear()
            self.current = None
            return
        self.current = p
        self.file_label.setText(ws.rel(p))
        self.preview.setPlainText(self._meta.text)

    def untrusted(self) -> list[str]:
        return list(self.ctx.settings.untrusted_dirs or []) if self.ctx is not None else []

    def set_untrusted(self, folder: str, on: bool) -> None:
        """F6 #15: klasörü güvenilmeyen olarak işaretle/kaldır (kalıcı ayar)."""
        if self.ctx is None:
            return
        from ..agent import untrusted as untr

        dirs = self.untrusted()
        if on and not untr.inside(Path(folder), dirs):
            dirs.append(str(Path(folder).resolve()))
            untr.ensure_gdignore([folder])
        elif not on:
            dirs = [d for d in dirs if Path(d).resolve() != Path(folder).resolve()]
        self.ctx.settings.untrusted_dirs = dirs
        self.ctx.save_settings()
        self._update_root_label()

    def _update_root_label(self) -> None:
        if self.root is None:
            return
        from ..agent import untrusted as untr

        here = [d for d in self.untrusted() if untr.inside(Path(d), [str(self.root)])]
        text = str(self.root)
        if here:
            text += "\n⚠ Güvenilmeyen: " + ", ".join(Path(d).name for d in here)
        self.root_label.set_full(text)

    def _context_menu(self, pos) -> None:
        from PySide6.QtWidgets import QMenu

        from ..agent import untrusted as untr

        idx = self.tree.indexAt(pos)
        if not idx.isValid() or self.ctx is None:
            return
        path = Path(self.model.filePath(idx))
        folder = path if path.is_dir() else path.parent
        menu = QMenu(self)
        marked = untr.inside(folder, self.untrusted())
        if marked:
            menu.addAction(f"Güvenilmeyen işaretini kaldır ({Path(marked).name})",
                           lambda: self.set_untrusted(marked, False))
        else:
            menu.addAction(f"\"{folder.name}\" klasörünü güvenilmeyen olarak işaretle",
                           lambda: self.set_untrusted(str(folder), True))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _attach(self) -> None:
        if self.current and self.root:
            self.attach_requested.emit(self.current.resolve().relative_to(self.root.resolve()).as_posix())

    def _toggle_edit(self, on: bool) -> None:
        if self.current is None:
            self.edit_btn.setChecked(False)
            return
        self.preview.setReadOnly(not on)
        self.save_btn.setVisible(on)

    def _save(self) -> None:
        if self.current is None or self._meta is None:
            return
        if QMessageBox.question(self, "Dosyayı kaydet",
                                f"{self.current.name} dosyasının üzerine yazılsın mı?") != QMessageBox.Yes:
            return
        try:
            self.current.write_bytes(self._meta.to_disk(self.preview.toPlainText()))
            self._meta = decode_bytes(self.current.read_bytes())
            self.file_label.setText(f"Kaydedildi: {self.current.name}")
            self.edit_btn.setChecked(False)
        except OSError as exc:
            QMessageBox.critical(self, "Kaydedilemedi", str(exc))

    def _open_explorer(self) -> None:
        if self.root and os.name == "nt":
            subprocess.Popen(["explorer", str(self.root)])


class TerminalTab(QWidget):
    """İki görünüm: "Günlük" — ajanın çalıştırdığı komutlar + kullanıcının tek seferlik komutları; "Kabuk" — proje
    klasöründe SÜREKLİ, etkileşimli PowerShell (Madde 20 C4: cd/değişken kalır, soru soran komutlara yanıt verilir)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from .shell_view import ShellView

        self.root: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        seg = QHBoxLayout()
        seg.setSpacing(4)
        self.mode_group = QButtonGroup(self)
        self.log_btn = QPushButton("Günlük")
        self.shell_btn = QPushButton("Kabuk")
        self.log_btn.setToolTip("Ajanın çalıştırdığı komutlar ve çıktıları")
        self.shell_btn.setToolTip("Etkileşimli PowerShell: komutlar arası cd ve değişkenler kalır; soru soran "
                                  "komutlara yanıt verebilirsiniz (Ctrl+C: kes, Ctrl+V: yapıştır)")
        for i, b in enumerate((self.log_btn, self.shell_btn)):
            b.setCheckable(True)
            b.setProperty("variant", "chip")
            b.setCursor(Qt.PointingHandCursor)
            self.mode_group.addButton(b, i)
            seg.addWidget(b)
        seg.addStretch(1)
        self.restart_btn = icon_button("refresh", "Kabuğu yeniden başlat", 15)
        self.restart_btn.clicked.connect(lambda _=None: self.shell.restart())
        seg.addWidget(self.restart_btn)
        lay.addLayout(seg)
        self.stack = QStackedWidget()
        self.view = QPlainTextEdit()
        self.view.setObjectName("TerminalView")
        self.view.setReadOnly(True)
        self.view.setFont(theme.code_font(9))
        self.view.setPlaceholderText("Ajanın ve sizin çalıştırdığınız komutlar ve çıktıları burada görünür.")
        self.stack.addWidget(self.view)
        self.shell = ShellView()
        self.stack.addWidget(self.shell)
        lay.addWidget(self.stack, 1)
        self.log_btn.setChecked(True)
        self.mode_group.idClicked.connect(self.set_mode)
        self.input_row = QWidget()
        row = QHBoxLayout(self.input_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.input = QLineEdit()
        self.input.setFont(theme.code_font(9))
        self.input.setPlaceholderText("PS>  proje klasöründe komut çalıştır (Enter)")
        self.input.returnPressed.connect(self._run_user)
        row.addWidget(self.input, 1)
        clear = icon_button("trash", "Temizle", 15)
        clear.clicked.connect(self.view.clear)
        row.addWidget(clear)
        lay.addWidget(self.input_row)
        self._busy = False
        self.set_mode(0)

    def set_mode(self, index: int) -> None:
        """0 = Günlük, 1 = Kabuk. Kabuk ilk kez açılınca başlar (görünür olunca)."""
        self.stack.setCurrentIndex(index)
        (self.log_btn if index == 0 else self.shell_btn).setChecked(True)
        self.input_row.setVisible(index == 0)
        self.restart_btn.setVisible(index == 1)
        if index == 1:
            self.shell.setFocus()

    def set_root(self, root: str | None) -> None:
        self.root = root
        self.input.setEnabled(bool(root))
        self.shell.set_root(root)
        self.shell_btn.setEnabled(bool(root))
        if not root and self.stack.currentIndex() == 1:
            self.set_mode(0)

    def log_command(self, command: str, source: str = "ajan") -> None:
        self.view.appendPlainText(f"\n[{source}] PS> {command}")

    def log_output(self, text: str) -> None:
        self.view.moveCursor(self.view.textCursor().MoveOperation.End)
        self.view.insertPlainText(text)
        self.view.ensureCursorVisible()

    def _run_user(self) -> None:
        cmd = self.input.text().strip()
        if not cmd or not self.root or self._busy:
            return
        self.input.clear()
        self._busy = True
        self.log_command(cmd, "siz")
        task_ref: dict = {}

        def job():
            tb = ToolBox(Workspace(self.root))
            return tb.run_command(cmd, on_output=lambda s: task_ref["t"].log(s))

        def done(res):
            self._busy = False
            self.view.appendPlainText(f"[çıkış {res.exit_code} · {res.duration:.1f} sn]")

        def fail(exc):
            self._busy = False
            self.view.appendPlainText(f"[hata] {exc}")

        task = Task(job, on_done=done, on_error=fail, on_log=self.log_output)
        task_ref["t"] = task
        task.start()


class WorkTab(QWidget):
    """F5 #7 canlı iş paneli: çalışan turun/akışın durumu (session_view her saniye `update_state` çağırır)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        self.head = QLabel("")
        self.head.setProperty("role", "h2")
        self.head.setWordWrap(True)
        lay.addWidget(self.head)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.RichText)
        lay.addWidget(self.info)
        self.steps_title = faint_label("Son adımlar")
        lay.addWidget(self.steps_title)
        self.steps = QLabel("")
        self.steps.setWordWrap(True)
        self.steps.setTextFormat(Qt.RichText)
        lay.addWidget(self.steps)
        lay.addStretch(1)
        self.empty = _empty("Ajan çalışırken motor, süre, aşama ve son adımlar burada canlı görünür.")
        lay.addWidget(self.empty)
        self.update_state(None)

    def update_state(self, st: dict | None) -> None:
        on = bool(st)
        for w in (self.head, self.info, self.steps_title, self.steps):
            w.setVisible(on)
        self.empty.setVisible(not on)
        if not st:
            return
        self.head.setText(st.get("title") or "Çalışıyor")
        rows = [f"<b>Motor:</b> {st.get('model', '-')}" + (f" ({st['role']})" if st.get("role") else ""),
                f"<b>Süre:</b> {st.get('elapsed', '-')} · <b>adım</b> {st.get('step', 0)}",
                f"<b>Etkinlik:</b> {st.get('activity', '')}"]
        if st.get("flow"):
            rows.append(f"<b>Akış:</b> {st['flow']}")
        if st.get("progress"):
            rows.append(f"<b>İlerleme:</b> {st['progress']}")
        if st.get("tokens"):
            rows.append(f"<b>Bu turda çıktı:</b> ~{st['tokens']:,} token".replace(",", "."))
        self.info.setText("<br>".join(rows))
        steps = st.get("steps") or []
        self.steps.setText("<br>".join(steps[-8:]) or "—")


class GitTab(QWidget):
    """Madde 1: proje klasörünün git durumu, dosya farkı, yapay zekâ commit mesajı önerisi, onaylı commit.
    Madde 12d (2026-11-05): GitHub — onaylı Gönder (push, zorlamasız), Al (pull, yalnız ileri sarma), uzak depo yoksa
    "GitHub'da depo oluştur" (gizli). reset/zorla gönderme yok. Git işleri arka plan iş parçacığında (R-04)."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.root: str | None = None
        self.entries: list = []
        self._tasks: set = set()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)
        head = QHBoxLayout()
        self.branch = faint_label("")
        self.branch.setWordWrap(True)
        head.addWidget(self.branch, 1)
        self.refresh_btn = icon_button("refresh", "Yenile", 15)
        self.refresh_btn.clicked.connect(lambda _=None: self.refresh())
        head.addWidget(self.refresh_btn)
        lay.addLayout(head)
        # GitHub satırı (Madde 12d): uzak depo + Gönder / Al / Depo oluştur
        gh_row = QHBoxLayout()
        self.remote_label = faint_label("")
        self.remote_label.setWordWrap(True)
        gh_row.addWidget(self.remote_label, 1)
        self.pull_btn = QPushButton("Al")
        self.pull_btn.setToolTip("GitHub'daki yeni commit'leri al (git pull --ff-only; yerel değişiklik ezilmez)")
        self.pull_btn.clicked.connect(lambda _=None: self.pull())
        self.push_btn = QPushButton("Gönder")
        self.push_btn.setToolTip("Commit'lenmiş değişiklikleri GitHub'a gönder (git push; zorlama yok)")
        self.push_btn.clicked.connect(lambda _=None: self.push())
        self.create_btn = QPushButton("GitHub'da depo oluştur")
        self.create_btn.setToolTip("Bu proje için GitHub'da gizli bir depo oluşturur ve commit'leri gönderir")
        self.create_btn.clicked.connect(lambda _=None: self.create_remote())
        for b in (self.pull_btn, self.push_btn, self.create_btn):
            gh_row.addWidget(b)
        lay.addLayout(gh_row)
        self._remote = ""
        self.body = QSplitter(Qt.Vertical)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show)
        self.body.addWidget(self.list)
        self.diff = DiffView("", auto_height=False)
        self.diff.setMinimumHeight(100)
        self.body.addWidget(self.diff)
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 6, 0, 0)
        bl.setSpacing(6)
        self.message = QPlainTextEdit()
        self.message.setPlaceholderText("Commit mesajı (Türkçe, tek satır özet)…")
        self.message.setMaximumHeight(90)
        bl.addWidget(self.message)
        row = QHBoxLayout()
        self.suggest_btn = QPushButton("Mesaj öner")
        self.suggest_btn.setToolTip("Yapay zekâ, farka bakarak commit mesajı önerir (ücretsiz EVREN/Auto Pro)")
        self.suggest_btn.clicked.connect(lambda _=None: self.suggest())
        self.commit_btn = QPushButton("Commit'le")
        self.commit_btn.setProperty("variant", "primary")
        self.commit_btn.clicked.connect(lambda _=None: self.commit())
        row.addWidget(self.suggest_btn)
        row.addStretch(1)
        row.addWidget(self.commit_btn)
        bl.addLayout(row)
        self.body.addWidget(box)
        self.body.setSizes([150, 260, 130])
        lay.addWidget(self.body, 1)
        self.note = faint_label("")
        self.note.setWordWrap(True)
        lay.addWidget(self.note)
        self.empty = _empty("Proje klasörü git deposu olduğunda değişen dosyalar, farkları ve commit burada görünür.")
        lay.addWidget(self.empty)
        self.init_btn = QPushButton("Bu klasörde git deposu başlat")
        self.init_btn.clicked.connect(lambda _=None: self.init_repo())
        lay.addWidget(self.init_btn, 0, Qt.AlignHCenter)
        self._apply(None)

    def _bg(self, fn, done, fail=None) -> None:
        t = Task(fn, on_done=lambda r: (self._tasks.discard(t), done(r)),
                 on_error=lambda e: (self._tasks.discard(t), (fail or self._fail)(e)))
        self._tasks.add(t)
        t.start()

    def _fail(self, exc) -> None:
        self.note.setText(f"Git hatası: {exc}")
        self._busy(False)

    def _busy(self, on: bool) -> None:
        for b in (self.suggest_btn, self.commit_btn, self.refresh_btn, self.pull_btn, self.push_btn, self.create_btn):
            b.setEnabled(not on)

    def set_root(self, root: str | None) -> None:
        if root != self.root:
            self.root = root
            self.message.clear()
            self.note.clear()
        self.refresh()

    def refresh(self) -> None:
        if not self.root:
            self._apply(None)
            return
        from ..agent import github, gitview

        root = self.root

        def job():
            st = gitview.status(root)
            return st, (github.remote_url(root) if st.repo else "")

        def done(res):
            if root == self.root:
                self._remote = res[1]
                self._apply(res[0])
        self._bg(job, done)

    def _apply(self, st) -> None:
        repo = bool(st and st.repo)
        self.body.setVisible(repo)
        self.empty.setVisible(not repo)
        self.init_btn.setVisible(bool(self.root) and st is not None and not st.repo and not st.error)
        self.refresh_btn.setVisible(bool(self.root))
        if st is not None and st.error:
            self.empty.setText(f"Git kullanılamıyor: {st.error}")
        self._apply_remote(st if repo else None)
        if not repo:
            self.branch.setText("")
            self.entries = []
            return
        sync = (f" · {st.ahead} gönderilmemiş commit" if st.ahead else "") + \
               (f" · {st.behind} commit geride" if st.behind else "")
        self.branch.setText(f"Dal: {st.branch or '?'} · {len(st.entries)} değişen dosya{sync}")
        cur = self.entries[self.list.currentRow()].path if 0 <= self.list.currentRow() < len(self.entries) else ""
        self.entries = st.entries
        self.list.clear()
        p = theme.current()
        for e in st.entries:
            self.list.addItem(QListWidgetItem(icons.icon("file", "text_dim", 15), f"{e.path}   ({e.label})"))
        self.commit_btn.setEnabled(bool(st.entries))
        self.suggest_btn.setEnabled(bool(st.entries))
        if not st.entries:
            self.diff.set_diff("")
            self.diff.setPlainText("Değişiklik yok — çalışma ağacı temiz.")
            return
        idx = next((i for i, e in enumerate(st.entries) if e.path == cur), 0)
        self.list.setCurrentRow(idx)

    def _show(self, row: int) -> None:
        if not (0 <= row < len(self.entries)) or not self.root:
            return
        from ..agent import gitview

        root, e = self.root, self.entries[row]
        self._bg(lambda: gitview.file_diff(root, e), lambda d: self.diff.set_diff(d) if root == self.root else None)

    def suggest(self) -> None:
        if not self.root or not self.entries:
            return
        from ..agent import gitview
        from .project_ui import COMMIT_SYSTEM, clean_commit_message

        root = self.root
        self._busy(True)
        self.note.setText("Commit mesajı hazırlanıyor…")

        def job():
            diff = gitview.summary_diff(root)
            text, model = self.ctx.ai_chat("commit", [{"role": "system", "content": COMMIT_SYSTEM},
                                                      {"role": "user", "content": f"Değişiklikler:\n{diff}"}],
                                           max_tokens=160)
            return clean_commit_message(text), model

        def done(res):
            msg, model = res
            self._busy(False)
            if msg:
                self.message.setPlainText(msg)
                self.note.setText(f"Öneri: {model}. Düzenleyebilirsiniz.")
            else:
                self.note.setText("Model boş yanıt verdi; mesajı elle yazın.")

        self._bg(job, done)

    def commit(self) -> None:
        if not self.root or not self.entries:
            return
        msg = self.message.toPlainText().strip()
        if not msg:
            self.note.setText("Önce commit mesajı yazın veya \"Mesaj öner\"e basın.")
            return
        files = "\n".join(f"• {e.path} ({e.label})" for e in self.entries[:12])
        more = f"\n… ve {len(self.entries) - 12} dosya daha" if len(self.entries) > 12 else ""
        if QMessageBox.question(self, "Commit'lensin mi?",
                                f"{len(self.entries)} dosya commit'lenecek:\n{files}{more}\n\nMesaj: {msg.splitlines()[0]}"
                                "\n\nGönderme (push) yapılmaz.") != QMessageBox.Yes:
            return
        from ..agent import gitview

        root = self.root
        self._busy(True)

        def done(res):
            ok, info = res
            self._busy(False)
            if ok:
                self.message.clear()
                self.note.setText(f"Commit'lendi: {info}")
            else:
                self.note.setText(f"Commit'lenemedi: {info}")
            self.refresh()

        self._bg(lambda: gitview.commit(root, msg), done)

    def _apply_remote(self, st) -> None:
        """GitHub satırı: uzak depo yoksa "depo oluştur", varsa Gönder/Al (gönderilecek/alınacak sayısıyla)."""
        from ..agent import github

        if st is None:
            self.remote_label.setText("")
            for b in (self.pull_btn, self.push_btn, self.create_btn):
                b.setVisible(False)
            return
        name = github.github_name(self._remote)
        has = bool(self._remote)
        self.remote_label.setText(f"GitHub: {name}" if name else (f"Uzak depo: {self._remote}" if has
                                                                     else "Uzak depo yok (GitHub'a bağlı değil)"))
        self.push_btn.setVisible(has)
        self.pull_btn.setVisible(has)
        self.create_btn.setVisible(not has)
        self.push_btn.setText(f"Gönder ({st.ahead})" if st.ahead else "Gönder")
        self.pull_btn.setText(f"Al ({st.behind})" if st.behind else "Al")

    def push(self) -> None:
        if not self.root or not self._remote:
            return
        from ..agent import github

        if QMessageBox.question(self, "GitHub'a gönderilsin mi?",
                                f"Commit'lenmiş değişiklikler {github.github_name(self._remote) or self._remote} "
                                "deposuna gönderilecek (git push). Commit'lenmemiş dosyalar gönderilmez; zorla "
                                "gönderme yapılmaz.") != QMessageBox.Yes:
            return
        self._remote_job(lambda root: github.push(root), "Gönderildi", "Gönderilemedi")

    def pull(self) -> None:
        if not self.root or not self._remote:
            return
        from ..agent import github

        self._remote_job(lambda root: github.pull(root), "Güncellendi", "Alınamadı")

    def create_remote(self) -> None:
        if not self.root:
            return
        from PySide6.QtWidgets import QInputDialog

        from ..agent import github

        name, ok = QInputDialog.getText(self, "GitHub'da depo oluştur",
                                        "Depo adı (gizli depo olarak oluşturulur, commit'ler gönderilir):",
                                        text=github.suggest_repo_name(self.root))
        if not ok or not name.strip():
            return
        self._remote_job(lambda root: github.create_repo(root, name.strip(), private=True),
                         "Depo oluşturuldu", "Depo oluşturulamadı",
                         hint="GitHub hesabını Ayarlar > GitHub'dan bağlayın; depoda en az bir commit olmalı.")

    def _remote_job(self, fn, ok_text: str, fail_text: str, hint: str = "") -> None:
        root = self.root
        self._busy(True)
        self.note.setText("GitHub ile iletişim kuruluyor…")

        def done(res):
            ok, out = res
            self._busy(False)
            last = (out or "").strip().splitlines()[-1:] or [""]
            self.note.setText(f"{ok_text}." if ok else f"{fail_text}: {last[0][:200]}" + (f" {hint}" if hint else ""))
            self.refresh()
        self._bg(lambda: fn(root), done)

    def init_repo(self) -> None:
        if not self.root:
            return
        if QMessageBox.question(self, "Git deposu başlatılsın mı?",
                                f"{self.root} klasöründe boş bir git deposu oluşturulur (git init). "
                                "Dosyalarınız değişmez.") != QMessageBox.Yes:
            return
        from ..agent import gitview

        root = self.root
        self._bg(lambda: gitview.init(root), lambda _r: self.refresh())


class SidePanel(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(300)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        # Başlık satırı: etkin bölümün adı + bölüm düğmeleri (dar panelde metin kesilmez)
        head = QFrame()
        head.setObjectName("HeaderBar")
        head.setFixedHeight(48)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(14, 0, 8, 0)
        hl.setSpacing(2)
        self.tab_title = QLabel()
        self.tab_title.setProperty("role", "h2")
        hl.addWidget(self.tab_title, 1)
        self.stack = QStackedWidget()
        self.todos = TodosTab()
        self.changes = ChangesTab(ctx)
        self.files = FilesTab(ctx=ctx)
        self.terminal = TerminalTab()
        self.work = WorkTab()
        self.git = GitTab(ctx)
        self._titles: list[str] = []
        self._buttons: list = []
        # iOS bölümlü denetim (2026-11-12): bölüm düğmeleri tek bir iz içinde, seçili parça yükseltilmiş
        self.segments = QFrame()
        self.segments.setObjectName("Segmented")
        seg_lay = QHBoxLayout(self.segments)
        seg_lay.setContentsMargins(2, 2, 2, 2)
        seg_lay.setSpacing(1)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for i, (widget, icon_name, label) in enumerate((
            (self.todos, "list", "Görevler"),
            (self.changes, "undo", "Değişiklikler"),
            (self.files, "folder", "Dosyalar"),
            (self.terminal, "terminal", "Terminal"),
            (self.work, "activity", "Çalışma"),
            (self.git, "git", "Git"),
        )):
            self.stack.addWidget(widget)
            b = icon_button(icon_name, label, 17, checkable=True)
            b.clicked.connect(lambda _=False, idx=i: self.set_index(idx))
            group.addButton(b)
            seg_lay.addWidget(b)
            self._titles.append(label)
            self._buttons.append(b)
        hl.addWidget(self.segments)
        lay.addWidget(head)
        lay.addWidget(self.stack, 1)
        self.set_index(0)

    def set_index(self, index: int) -> None:
        if 0 <= index < len(self._titles):
            self.stack.setCurrentIndex(index)
            self.tab_title.setText(self._titles[index])
            self._buttons[index].setChecked(True)
            if self.stack.widget(index) is self.git:
                self.git.refresh()

    def set_session(self, session_id: int | None, workspace: str | None, todos: list[dict]) -> None:
        self.todos.set_todos(todos)
        self.changes.set_session(session_id, workspace)
        if self.files.root is None or str(self.files.root) != (workspace or ""):
            self.files.set_root(workspace)
        self.terminal.set_root(workspace)
        self.git.set_root(workspace)

    def show_tab(self, name: str) -> None:
        self.set_index({"todos": 0, "changes": 1, "files": 2, "terminal": 3, "work": 4, "git": 5}.get(name, 0))
