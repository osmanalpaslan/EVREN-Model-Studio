"""Code Studio — Aşama 2 temeli.

Şu an GERÇEKTEN çalışan kısımlar: proje klasörü açma, dosya ağacı,
metin düzenleyici, kaydetme. AI kod üretme/diff/onaylı uygulama akışı
aşama 2'de eklenecektir; eksik kısımlar aşağıda açıkça belirtilir.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QItemSelectionModel

SAFE_TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".c", ".h", ".cpp",
    ".hpp", ".cs", ".go", ".rs", ".java", ".sql", ".sh", ".ps1", ".bat",
    ".env", ".gitignore", "",
}
MAX_EDIT_SIZE = 2 * 1024 * 1024  # 2 MB üzeri dosyalar düzenlenmez


class CodeStudioPage(QWidget):
    title = "Code Studio"

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 20, 24, 20)
        self.root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Code Studio")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.root.addLayout(header)

        info = QLabel(
            "Aşama 2 temeli: proje klasörü açma, dosya ağacı ve düzenleyici "
            "çalışır durumdadır. Kod üretme, diff ile onaylı değişiklik "
            "uygulama, test çalıştırma ve görev listesi aşama 2'nin devamında "
            "eklenecektir. Düzenlemeler yalnızca açtığınız proje klasörü "
            "içindeki dosyalara kaydedilir."
        )
        info.setWordWrap(True)
        info.setObjectName("dim")
        self.root.addWidget(info)

        bar = QHBoxLayout()
        open_btn = QPushButton("Proje Klasörü Aç…")
        open_btn.clicked.connect(self.open_project)
        self.save_btn = QPushButton("Kaydet (Ctrl+S)")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_file)
        self.project_label = QLabel("Proje açılmadı.")
        bar.addWidget(open_btn)
        bar.addWidget(self.save_btn)
        bar.addStretch(1)
        bar.addWidget(self.project_label)
        self.root.addLayout(bar)

        splitter = QSplitter(Qt.Horizontal)
        self.tree = QTreeView()
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath("")
        self.tree.setModel(self.fs_model)
        self.tree.setSelectionMode(QTreeView.SingleSelection)
        self.tree.clicked.connect(self.open_selected)
        splitter.addWidget(self.tree)

        editor_host = QWidget()
        editor_lay = QVBoxLayout(editor_host)
        editor_lay.setContentsMargins(0, 0, 0, 0)
        self.file_label = QLabel("Dosya seçilmedi.")
        self.file_label.setObjectName("dim")
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Soldaki ağaçtan bir metin dosyası seçin…"
        )
        editor_lay.addWidget(self.file_label)
        editor_lay.addWidget(self.editor)
        splitter.addWidget(editor_host)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)
        self.root.addWidget(splitter, 1)

        self.current_file: Path | None = None

    def open_project(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Proje Klasörü Seç", str(Path.home())
        )
        if not d:
            return
        root = self.fs_model.setRootPath(d)
        self.tree.setRootIndex(root)
        self.project_label.setText(f"Proje: {d}")
        self.ctx.settings.code_workdir = d
        self.ctx.save_settings()

    def open_selected(self, index) -> None:
        path = Path(self.fs_model.filePath(index))
        if not path.is_file():
            return
        if path.suffix.lower() not in SAFE_TEXT_SUFFIXES:
            self.file_label.setText(
                f"{path.name}: bu dosya türü düzenleyicide açılmaz (güvenlik)"
            )
            self.editor.clear()
            self.current_file = None
            self.save_btn.setEnabled(False)
            return
        if path.stat().st_size > MAX_EDIT_SIZE:
            self.file_label.setText(f"{path.name}: dosya çok büyük (2 MB üzeri)")
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.file_label.setText(f"{path.name}: okunamadı ({exc})")
            return
        # Proje kökünün içinde mi? (sembolik bağlantı dışına çıkma engeli)
        root_dir = Path(self.fs_model.rootPath())
        if not path.resolve().is_relative_to(root_dir.resolve()):
            self.file_label.setText(
                f"{path.name}: proje klasörü dışındaki dosyalar açılmaz."
            )
            return
        self.current_file = path
        self.editor.setPlainText(text)
        self.file_label.setText(str(path))
        self.save_btn.setEnabled(True)

    def save_file(self) -> None:
        if not self.current_file:
            return
        confirm = QMessageBox.question(
            self, "Dosyayı Kaydet",
            f"{self.current_file.name} dosyasının üzerine yazılsın mı?\n"
            "Değişiklik geri alınamaz; gerekiyorsa önce Git ile yedekleyin."
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.current_file.write_text(
                self.editor.toPlainText(), encoding="utf-8"
            )
            self.file_label.setText(f"Kaydedildi: {self.current_file}")
        except OSError as exc:
            QMessageBox.critical(self, "Kaydedilemedi", str(exc))
