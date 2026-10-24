"""Ayarlar > Oyun araçları: Godot + şablonlar ve Blender durumu; onaylı, sağlama toplamı doğrulamalı kurulum."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ..agent import gameinstall, gametools
from .workers import Task


def _mb(n: int) -> str:
    return f"{n / 1_000_000:,.0f} MB".replace(",", ".")


class GameToolsCard(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._busy = False
        self._task: Task | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        info = QLabel("Ajanın Godot ile Windows EXE ve tarayıcıda çalışan PWA üretmesi, modelleri Blender ile "
                      "dönüştürmesi için. Resmî sitelerden indirilir; her dosyanın sağlama toplamı doğrulanır "
                      "(uyuşmazsa silinir). Kurulumsuz: yönetici izni gerekmez.")
        info.setWordWrap(True)
        info.setProperty("role", "dim")
        lay.addWidget(info)
        self.state = QLabel()
        self.state.setWordWrap(True)
        lay.addWidget(self.state)
        row = QHBoxLayout()
        self.godot_btn = QPushButton()
        self.godot_btn.clicked.connect(lambda _=None: self.install("godot"))
        self.blender_btn = QPushButton()
        self.blender_btn.clicked.connect(lambda _=None: self.install("blender"))
        row.addWidget(self.godot_btn)
        row.addWidget(self.blender_btn)
        row.addStretch(1)
        lay.addLayout(row)
        self.log = QLabel("")
        self.log.setWordWrap(True)
        self.log.setProperty("role", "dim")
        lay.addWidget(self.log)
        self.refresh()

    def refresh(self) -> None:
        st = gameinstall.status()
        g, b = gametools.find_godot(), gametools.find_blender()
        lines = [f"Godot 4.7.2: {'kurulu — ' + g if st['godot'] else 'kurulu değil'}",
                 f"Dışa aktarma şablonları: {'kurulu' if st['sablonlar'] else 'kurulu değil'}",
                 f"Blender 5.2.3: {'kurulu — ' + b if st['blender'] else 'kurulu değil'}"]
        self.state.setText("\n".join(lines))
        need_g = [k for k in gameinstall.GROUPS["godot"] if not st[k]]
        self.godot_btn.setText(f"Godot + şablonları kur (~{_mb(gameinstall.total_size(need_g))})" if need_g
                               else "Godot kurulu")
        self.godot_btn.setEnabled(bool(need_g) and not self._busy)
        self.blender_btn.setText(f"Blender'ı kur (~{_mb(gameinstall.ITEMS['blender'].size)})" if not st["blender"]
                                 else "Blender kurulu")
        self.blender_btn.setEnabled(not st["blender"] and not self._busy)

    def install(self, group: str) -> None:
        if self._busy:
            return
        st = gameinstall.status()
        keys = [k for k in gameinstall.GROUPS[group] if not st[k]]
        if not keys:
            return
        dest = gameinstall.default_dir()
        items = "\n".join(f"• {gameinstall.ITEMS[k].title}: {_mb(gameinstall.ITEMS[k].size)}" for k in keys)
        if QMessageBox.question(self, "Oyun araçları indirilsin mi?",
                                f"Resmî sitelerden indirilecek (toplam ~{_mb(gameinstall.total_size(keys))}):\n{items}\n\n"
                                f"Kurulum yeri: {dest}\nSağlama toplamı doğrulanır; yönetici izni gerekmez. "
                                "Devam edilsin mi?") != QMessageBox.Yes:
            return
        self._busy = True
        self.refresh()
        task: Task

        def run():
            return gameinstall.install(keys, dest, log=task.log)

        def done(_res):
            self._busy = False
            self.refresh()
            self.log.setText("Kurulum tamamlandı ve doğrulandı. Ajan oyun işlerinde bu araçları kullanır.")

        def fail(exc):
            self._busy = False
            self.refresh()
            self.log.setText(f"Kurulamadı: {exc}")

        task = Task(run, on_done=done, on_error=fail, on_log=self.log.setText)
        self._task = task
        task.start()
