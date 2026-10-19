"""Ayarlar > MCP sunucuları kartı (agent/mcp.py).

- Serena: tek tıkla kur (veri klasöründe ayrı Python ortamı; uv dahil, sisteme program
  kurulmaz), aç/kapa, dene. Yalnız okuma yapan sembol araçları açılır.
- Diğer sunucular: ad + komut + argümanlar + sormadan çalışabilecek (okuma) araçlar.
- "Dene": sunucuyu başlatır, araç listesini ve açılış süresini gösterir.
Kurulum ve deneme arka planda (Task) çalışır (R-04); sonuçlar ana iş parçacığına sinyalle döner.
"""
from __future__ import annotations

import shlex
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..agent import mcp
from .workers import Task


def _label(text: str, role: str = "dim") -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", role)
    lab.setWordWrap(True)
    return lab


class ServerDialog(QDialog):
    """Elle MCP sunucusu ekleme (stdio)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MCP sunucusu ekle")
        self.setMinimumWidth(560)
        form = QFormLayout(self)
        self.name = QLineEdit()
        self.name.setPlaceholderText("ör. playwright")
        self.command = QLineEdit()
        self.command.setPlaceholderText("ör. npx")
        self.args = QLineEdit()
        self.args.setPlaceholderText("ör. @playwright/mcp@0.0.40 --isolated   ({proje} = proje klasörü)")
        self.read_only = QLineEdit()
        self.read_only.setPlaceholderText("virgülle: browser_snapshot, browser_take_screenshot")
        form.addRow("Ad:", self.name)
        form.addRow("Komut:", self.command)
        form.addRow("Argümanlar:", self.args)
        form.addRow("Sormadan çalışacak (okuma) araçlar:", self.read_only)
        form.addRow(_label("Listede olmayan her araç, çalışma modunuza göre onay ister. Sunucu "
                           "bilgisayarınızda çalışan dış bir programdır: yalnız güvendiğiniz, "
                           "sürümü sabit sunucuları ekleyin.", "faint"))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def config(self) -> mcp.McpServerConfig | None:
        name, cmd = mcp.safe_name(self.name.text()), self.command.text().strip()
        if not name or not cmd:
            return None
        try:
            args = shlex.split(self.args.text(), posix=False)
        except ValueError:
            args = self.args.text().split()
        args = [a[1:-1] if len(a) >= 2 and a[0] == a[-1] == '"' else a for a in args]
        ro = [t.strip() for t in self.read_only.text().split(",") if t.strip()]
        return mcp.McpServerConfig(name=name, command=cmd, args=args, read_only_tools=ro)


class McpSettingsCard(QWidget):
    """Ayarlar sayfasına gömülen kart. load()/collect() SettingsPage tarafından çağrılır."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._servers: list[dict] = []
        self._busy = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(_label(
            "MCP (Model Context Protocol) sunucuları ajana ek araç verir. Yalnız proje klasörlü "
            "oturumlarda kullanılır; okuma dışındaki araçlar çalışma modunuza göre onay ister. "
            "MCP aracının yaptığı dosya değişiklikleri Değişiklikler paneline düşmez — bu yüzden "
            "Serena'da yalnız okuma araçları açıktır, düzenlemeyi ajanın kendi araçları yapar."))
        self.enabled = QCheckBox("MCP sunucularını ajanda kullan")
        lay.addWidget(self.enabled)

        # Serena
        lay.addWidget(_label(f"Serena {mcp.SERENA_VERSION} (oraios/serena, MIT) — kodu sembol düzeyinde "
                             "anlar: tanım, kullanıldığı yerler, dosya özeti. Python projelerinde denendi.",
                             "dim"))
        row = QHBoxLayout()
        self.serena_status = QLabel("")
        self.serena_install = QPushButton("Serena'yı kur")
        self.serena_install.clicked.connect(self.install_serena)
        self.serena_toggle = QCheckBox("Serena etkin")
        self.serena_toggle.toggled.connect(self._toggle_serena)
        self.serena_test = QPushButton("Dene")
        self.serena_test.clicked.connect(lambda _=None: self.test_server("serena"))
        row.addWidget(self.serena_status, 1)
        row.addWidget(self.serena_toggle)
        row.addWidget(self.serena_install)
        row.addWidget(self.serena_test)
        lay.addLayout(row)

        # diğer sunucular
        lay.addWidget(_label("Diğer sunucular", "dim"))
        self.list = QListWidget()
        self.list.setMaximumHeight(110)
        lay.addWidget(self.list)
        row2 = QHBoxLayout()
        add = QPushButton("Sunucu ekle…")
        add.clicked.connect(self.add_server)
        self.toggle_btn = QPushButton("Aç / kapat")
        self.toggle_btn.clicked.connect(self.toggle_selected)
        remove = QPushButton("Kaldır")
        remove.setProperty("variant", "danger")
        remove.clicked.connect(self.remove_selected)
        test = QPushButton("Dene")
        test.clicked.connect(self.test_selected)
        for b in (add, self.toggle_btn, remove, test):
            row2.addWidget(b)
        row2.addStretch(1)
        lay.addLayout(row2)
        self.log = _label("", "faint")
        lay.addWidget(self.log)

    # ---- ayarlarla eşitleme ----
    def load(self, s) -> None:
        self.enabled.setChecked(bool(s.mcp_enabled))
        self._servers = [dict(d) for d in (s.mcp_servers or []) if isinstance(d, dict)]
        self._refresh()

    def collect(self, s) -> None:
        s.mcp_enabled = self.enabled.isChecked()
        s.mcp_servers = [dict(d) for d in self._servers]

    def _find(self, name: str) -> dict | None:
        return next((d for d in self._servers if d.get("name") == name), None)

    def _refresh(self) -> None:
        data_dir = self.ctx.settings.resolved_data_dir()
        ready = mcp.serena_ready(data_dir)
        cfg = self._find("serena")
        if ready:
            self.serena_status.setText(f"Kurulu · {mcp.serena_dir(data_dir)}")
        else:
            self.serena_status.setText("Kurulu değil (~2 dk, ~150 MB indirilir; Python 3.13 ve pyright dahil)")
        self.serena_install.setVisible(not ready)
        self.serena_toggle.blockSignals(True)
        self.serena_toggle.setChecked(bool(cfg and cfg.get("enabled", True)))
        self.serena_toggle.setEnabled(ready)
        self.serena_toggle.blockSignals(False)
        self.serena_test.setEnabled(ready and not self._busy)
        self.serena_install.setEnabled(not self._busy)
        self.list.clear()
        for d in self._servers:
            if d.get("name") == "serena":
                continue
            state = "etkin" if d.get("enabled", True) else "kapalı"
            it = QListWidgetItem(f"{d['name']}  ·  {d.get('command', '')} {' '.join(d.get('args') or [])}  ·  {state}")
            it.setData(256, d["name"])
            self.list.addItem(it)

    def _toggle_serena(self, on: bool) -> None:
        cfg = self._find("serena")
        if on and cfg is None:
            self._servers.append(mcp.serena_config().to_dict())
        elif cfg is not None:
            cfg["enabled"] = on
        self._save()

    def _save(self) -> None:
        """MCP değişiklikleri hemen kalıcı olur (kurulum sonrası kaybolmasın; R-03)."""
        self.collect(self.ctx.settings)
        self.ctx.save_settings()
        self._refresh()

    # ---- eylemler ----
    def install_serena(self) -> None:
        if self._busy:
            return
        ok = QMessageBox.question(
            self, "Serena kurulsun mu?",
            f"Serena {mcp.SERENA_VERSION} ve uv, uygulamanın veri klasöründe ayrı bir Python ortamına "
            "kurulacak; Python dil sunucusu (pyright, Python 3.13 ile) de indirilecek. Yaklaşık "
            "2 dakika ve ~150 MB. Bilgisayara ayrıca program kurulmaz, yönetici izni gerekmez.\n\n"
            "Devam edilsin mi?")
        if ok != QMessageBox.Yes:
            return
        self._busy = True
        self._refresh()
        data_dir = self.ctx.settings.resolved_data_dir()
        task: Task

        def job():
            return mcp.install_serena(data_dir, log=task.log)

        def done(_exe):
            self._busy = False
            if self._find("serena") is None:
                self._servers.append(mcp.serena_config().to_dict())
            self.enabled.setChecked(True)
            self._save()
            self.log.setText("Serena kuruldu ve etkinleştirildi. Proje klasörlü bir oturumda ajan "
                             "sembol araçlarını kullanabilir.")

        def fail(exc):
            self._busy = False
            self._refresh()
            self.log.setText(f"Serena kurulamadı: {exc}")

        task = Task(job, on_done=done, on_error=fail, on_log=self.log.setText)
        task.start()

    def _project_root(self) -> Path | None:
        p = (self.ctx.settings.code_workdir or "").strip()
        return Path(p) if p and Path(p).is_dir() else None

    def test_server(self, name: str) -> None:
        d = self._find(name) or (mcp.serena_config().to_dict() if name == "serena" else None)
        if d is None or self._busy:
            return
        cfg = mcp.McpServerConfig.from_dict(d)
        root = self._project_root()
        self._busy = True
        self._refresh()
        self.log.setText(f"'{cfg.name}' başlatılıyor…" + (f" (proje: {root})" if root else " (proje klasörü yok)"))

        def job():
            return self.ctx.mcp.test(cfg, root)

        def done(res):
            tools, secs = res
            self._busy = False
            self._refresh()
            ro = set(cfg.read_only_tools)
            allowed = set(cfg.allowed_tools)
            shown = [t["name"] for t in tools if not allowed or t["name"] in allowed]
            marks = ", ".join(f"{n}{'' if n in ro else ' (onaylı)'}" for n in shown)
            self.log.setText(f"'{cfg.name}' çalışıyor · açılış {secs:.1f} sn · sunucuda {len(tools)} araç, "
                             f"ajana açık {len(shown)}: {marks}")

        def fail(exc):
            self._busy = False
            self._refresh()
            self.log.setText(f"'{cfg.name}' başlatılamadı: {exc}")

        Task(job, on_done=done, on_error=fail).start()

    def add_server(self) -> None:
        dlg = ServerDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        cfg = dlg.config()
        if cfg is None:
            QMessageBox.warning(self, "Eksik bilgi", "Ad ve komut gerekli.")
            return
        if self._find(cfg.name) is not None:
            QMessageBox.warning(self, "Aynı ad", f"'{cfg.name}' adlı sunucu zaten var.")
            return
        self._servers.append(cfg.to_dict())
        self._save()

    def _selected(self) -> str | None:
        it = self.list.currentItem()
        return it.data(256) if it is not None else None

    def toggle_selected(self) -> None:
        d = self._find(self._selected() or "")
        if d is not None:
            d["enabled"] = not d.get("enabled", True)
            self._save()

    def remove_selected(self) -> None:
        name = self._selected()
        if name and QMessageBox.question(self, "Kaldır", f"'{name}' sunucusu listeden kaldırılsın mı?") \
                == QMessageBox.Yes:
            self._servers = [d for d in self._servers if d.get("name") != name]
            self._save()

    def test_selected(self) -> None:
        name = self._selected()
        if name:
            self.test_server(name)
