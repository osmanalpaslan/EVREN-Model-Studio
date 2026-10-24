"""F4 "Skill'ler ve Profiller" sayfası: skill ekle/aç-kapa/proje kapsamı, ajan profilleri (E5), iş şablonları (#10)."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..agent import skills as sk
from ..agent import templates as tpl
from ..agent.permissions import MODES
from .base_page import BasePage, card
from .settings_page import hint, section


def _tr_buttons(bb: QDialogButtonBox) -> QDialogButtonBox:
    """Qt'nin standart düğmeleri İngilizce gelir; Türkçe arayüz."""
    for kind, text in ((QDialogButtonBox.Save, "Kaydet"), (QDialogButtonBox.Ok, "Tamam"),
                       (QDialogButtonBox.Cancel, "Vazgeç")):
        btn = bb.button(kind)
        if btn is not None:
            btn.setText(text)
    return bb


def _btn(text: str, slot, variant: str = "") -> QPushButton:
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    b.clicked.connect(lambda _=None: slot())
    return b


class ProjectsDialog(QDialog):
    """Skill'in çalışacağı proje klasörleri (bilinen klasörler + elle ekleme)."""

    def __init__(self, known: list[str], selected: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Skill hangi projelerde çalışsın?")
        self.resize(560, 420)
        lay = QVBoxLayout(self)
        lay.addWidget(hint("İşaretlediğiniz proje klasörlerinde skill ajana sunulur. Listede yoksa ekleyin."))
        self.list = QListWidget()
        for w in dict.fromkeys(list(known) + list(selected)):
            it = QListWidgetItem(w)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if w in selected else Qt.Unchecked)
            self.list.addItem(it)
        lay.addWidget(self.list, 1)
        lay.addWidget(_btn("Klasör ekle…", self._add))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(_tr_buttons(bb))

    def _add(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Proje klasörü seç")
        if d:
            it = QListWidgetItem(str(Path(d)))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            self.list.addItem(it)

    def selected(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.Checked]


class ProfileDialog(QDialog):
    """Profil: ad, tercih edilen motor, çalışma modu, skill seçimi, ek talimat."""

    def __init__(self, ctx, profile: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajan profili")
        self.resize(560, 560)
        p = profile or {}
        form = QFormLayout()
        self.name = QLineEdit(p.get("name") or "")
        self.name.setPlaceholderText("ör. Raporcu, Web testçisi")
        self.name.setReadOnly(bool(profile))
        form.addRow("Ad:", self.name)
        self.model = QComboBox()
        self.model.addItem("(değiştirme)", "")
        for m in ctx.chat_models():
            self.model.addItem(m.id, m.id)
        i = self.model.findData(p.get("model") or "")
        self.model.setCurrentIndex(max(0, i))
        form.addRow("Motor:", self.model)
        self.mode = QComboBox()
        self.mode.addItem("(değiştirme)", "")
        for k, v in MODES.items():
            self.mode.addItem(v, k)
        i = self.mode.findData(p.get("mode") or "")
        self.mode.setCurrentIndex(max(0, i))
        form.addRow("Çalışma modu:", self.mode)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("Skill'ler:"))
        self.all_skills = QCheckBox("Projede etkin olan tüm skill'ler (önerilir)")
        self.skill_list = QListWidget()
        chosen = p.get("skills")
        for s in ctx.skills():
            it = QListWidgetItem(f"{s.name}")
            it.setData(Qt.UserRole, s.slug)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if chosen and (s.slug in chosen or s.name in chosen) else Qt.Unchecked)
            self.skill_list.addItem(it)
        self.all_skills.toggled.connect(lambda on: self.skill_list.setEnabled(not on))
        self.all_skills.setChecked(chosen is None)
        self.skill_list.setEnabled(chosen is not None)
        lay.addWidget(self.all_skills)
        lay.addWidget(self.skill_list, 1)
        lay.addWidget(QLabel("Ek talimat (her turda ajana verilir):"))
        self.instr = QPlainTextEdit(p.get("instructions") or "")
        self.instr.setPlaceholderText("ör. Raporları her zaman Excel'e yaz; Türkçe sayı biçimi 1.234,50 kullan.")
        lay.addWidget(self.instr, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(_tr_buttons(bb))

    def _ok(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Ajan profili", "Profile bir ad verin.")
            return
        self.accept()

    def values(self) -> tuple[str, str | None, str | None, str | None, str]:
        skills = None if self.all_skills.isChecked() else json.dumps(
            [self.skill_list.item(i).data(Qt.UserRole) for i in range(self.skill_list.count())
             if self.skill_list.item(i).checkState() == Qt.Checked], ensure_ascii=False)
        return (self.name.text().strip(), self.model.currentData() or None, self.mode.currentData() or None,
                skills, self.instr.toPlainText().strip())


class TemplateDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni şablon")
        self.resize(560, 420)
        form = QFormLayout()
        self.name = QLineEdit()
        form.addRow("Ad:", self.name)
        self.profile = QComboBox()
        self.profile.addItem("(profil yok)", "")
        for p in ctx.db.list_profiles():
            self.profile.addItem(p["name"], p["name"])
        form.addRow("Profil:", self.profile)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("İstem (köşeli parantezli yerleri kullanırken doldurursunuz):"))
        self.prompt = QPlainTextEdit()
        lay.addWidget(self.prompt, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(lambda: self.accept() if self.name.text().strip() and self.prompt.toPlainText().strip()
                            else QMessageBox.warning(self, "Şablon", "Ad ve istem gerekli."))
        bb.rejected.connect(self.reject)
        lay.addWidget(_tr_buttons(bb))


class SkillsPage(BasePage):
    title = "Skill'ler ve Profiller"
    # (istem, profil) — ana pencere yeni oturum açar, profili uygular, mesaj kutusunu doldurur
    template_requested = Signal(str, str)

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self.header_extra.addWidget(_btn("Klasörden skill ekle…", self.add_skill, "primary"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        self.col = QVBoxLayout(inner)
        self.col.setSpacing(12)
        c, l = card()
        l.addWidget(section("Skill'ler"))
        l.addWidget(hint("Skill = SKILL.md'li bir iş talimatı klasörü (ör. hesap kapama kuralları). Ajan yalnız adını ve "
                         "kısa açıklamasını görür; iş konusuna girerse skill'i kendisi açıp okur. Eklenen skill "
                         "uygulamanın veri klasörüne kopyalanır; kaynağınız değişmez."))
        self.skills_box = QVBoxLayout()
        l.addLayout(self.skills_box)
        self.col.addWidget(c)
        c, l = card()
        h = QHBoxLayout()
        h.addWidget(section("Ajan profilleri"))
        h.addStretch(1)
        h.addWidget(_btn("Yeni profil…", lambda: self.edit_profile(None)))
        l.addLayout(h)
        l.addWidget(hint("Profil; motor, çalışma modu, hangi skill'lerin açık olacağı ve ek talimatı tek seferde seçer. "
                         "Oturumda başlıktaki \"Profil\" düğmesi veya /profil <ad> ile uygulanır."))
        self.profiles_box = QVBoxLayout()
        l.addLayout(self.profiles_box)
        self.col.addWidget(c)
        c, l = card()
        h = QHBoxLayout()
        h.addWidget(section("İş şablonları"))
        h.addStretch(1)
        h.addWidget(_btn("Yeni şablon…", self.add_template))
        l.addLayout(h)
        l.addWidget(hint("Şablon yeni bir oturum açar ve mesaj kutusunu doldurur; göndermeden önce köşeli parantezli "
                         "yerleri kendi işinize göre düzenleyin."))
        self.templates_box = QVBoxLayout()
        l.addLayout(self.templates_box)
        self.col.addWidget(c)
        self.col.addStretch(1)
        scroll.setWidget(inner)
        self.root.addWidget(scroll, 1)
        self.refresh()

    # ---- liste çizimi ----

    @staticmethod
    def _clear(box: QVBoxLayout) -> None:
        while box.count():
            it = box.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()

    def refresh(self) -> None:
        self._clear(self.skills_box)
        skills = self.ctx.skills()
        if not skills:
            self.skills_box.addWidget(hint("Henüz skill yok. \"Klasörden skill ekle…\" ile SKILL.md içeren bir "
                                           "klasör seçin."))
        for s in skills:
            self.skills_box.addWidget(self._skill_row(s))
        self._clear(self.profiles_box)
        profs = self.ctx.db.list_profiles()
        if not profs:
            self.profiles_box.addWidget(hint("Henüz profil yok."))
        for p in profs:
            self.profiles_box.addWidget(self._profile_row(p))
        self._clear(self.templates_box)
        items = list(tpl.BUILTIN) + [tpl.from_row(r) for r in self.ctx.db.list_templates()]
        for t in items:
            self.templates_box.addWidget(self._template_row(t))

    def _skill_row(self, s: sk.Skill) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 6, 0, 6)
        top = QHBoxLayout()
        on = QCheckBox(s.name)
        on.setChecked(s.enabled)
        on.setStyleSheet("font-weight: 600;")
        on.toggled.connect(lambda val, x=s: self._set(x, enabled=val))
        top.addWidget(on)
        top.addStretch(1)
        scope = QComboBox()
        for k, label in sk.SCOPES.items():
            scope.addItem(label, k)
        scope.setCurrentIndex(max(0, scope.findData(s.scope)))
        scope.currentIndexChanged.connect(lambda _i, x=s, c=scope: self._set(x, scope=c.currentData()))
        top.addWidget(scope)
        top.addWidget(_btn(f"Projeler ({len(s.projects)})…", lambda x=s: self.pick_projects(x)))
        top.addWidget(_btn("Kaynaktan yenile", lambda x=s: self.refresh_skill(x)))
        top.addWidget(_btn("Kaldır", lambda x=s: self.remove_skill(x), "ghost"))
        v.addLayout(top)
        desc = QLabel((s.description or "(açıklama yok)")[:400])
        desc.setWordWrap(True)
        desc.setProperty("role", "dim")
        v.addWidget(desc)
        extra = [f"Denetçi: {s.checker}" if s.checker else "Denetçi yok"]
        if s.scope == "secili":
            extra.append("Projeler: " + (", ".join(Path(p).name for p in s.projects) or "(seçilmedi — hiçbir yerde "
                                                                                          "çalışmaz)"))
        meta = QLabel(" · ".join(extra))
        meta.setProperty("role", "dim")
        meta.setWordWrap(True)
        v.addWidget(meta)
        return w

    def _profile_row(self, p: dict) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 4, 0, 4)
        try:
            sks = json.loads(p["skills"]) if p.get("skills") else None
        except ValueError:
            sks = None
        info = (f"<b>{p['name']}</b> — motor: {p.get('model') or '(değiştirmez)'} · mod: "
                f"{MODES.get(p.get('mode') or '', '(değiştirmez)')} · skill: "
                + ("tümü" if sks is None else (", ".join(sks) or "hiçbiri")))
        lab = QLabel(info)
        lab.setWordWrap(True)
        h.addWidget(lab, 1)
        h.addWidget(_btn("Düzenle", lambda x=p: self.edit_profile(x)))
        h.addWidget(_btn("Sil", lambda x=p: self.delete_profile(x), "ghost"))
        return w

    def _template_row(self, t: tpl.Template) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 4, 0, 4)
        lab = QLabel(f"<b>{t.name}</b> — {t.description}")
        lab.setWordWrap(True)
        lab.setToolTip(t.prompt)
        h.addWidget(lab, 1)
        h.addWidget(_btn("Kullan", lambda x=t: self.use_template(x), "primary"))
        if not t.builtin:
            h.addWidget(_btn("Sil", lambda x=t: (self.ctx.db.delete_template(x.id), self.refresh()), "ghost"))
        return w

    # ---- eylemler ----

    def _set(self, s: sk.Skill, **kw) -> None:
        for k, v in kw.items():
            setattr(s, k, v)
        self.ctx.save_skill(s)
        if "scope" in kw:
            self.refresh()

    def add_skill(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "SKILL.md içeren klasörü seç")
        if not d:
            return
        try:
            s = self.ctx.add_skill(Path(d))
        except (sk.SkillError, OSError) as exc:
            QMessageBox.warning(self, "Skill eklenemedi", str(exc))
            return
        QMessageBox.information(self, "Skill eklendi", f"{s.name} eklendi ve tüm projelerde açık. Kapsamı "
                                                        "\"Yalnız seçtiğim projeler\" yapabilirsiniz.")
        self.refresh()

    def pick_projects(self, s: sk.Skill) -> None:
        dlg = ProjectsDialog(self.ctx.known_workspaces(), s.projects, self)
        if dlg.exec():
            s.projects = dlg.selected()
            if s.projects and s.scope == "tum":
                s.scope = "secili"
            self.ctx.save_skill(s)
            self.refresh()

    def refresh_skill(self, s: sk.Skill) -> None:
        try:
            sk.refresh(s)
        except (sk.SkillError, OSError) as exc:
            QMessageBox.warning(self, "Yenilenemedi", str(exc))
            return
        self.ctx.save_skill(s)
        self.refresh()

    def remove_skill(self, s: sk.Skill) -> None:
        if QMessageBox.question(self, "Skill kaldırılsın mı?",
                                f"{s.name} uygulamadan kaldırılsın mı? Uygulamanın kopyası silinir; sizin kaynak "
                                f"klasörünüze ({s.source or '-'}) dokunulmaz.") != QMessageBox.Yes:
            return
        self.ctx.remove_skill(s.slug)
        self.refresh()

    def edit_profile(self, p: dict | None) -> None:
        prof = self.ctx.profile(p["name"]) if p else None
        dlg = ProfileDialog(self.ctx, prof, self)
        if dlg.exec():
            self.ctx.db.save_profile(*dlg.values())
            self.refresh()

    def delete_profile(self, p: dict) -> None:
        if QMessageBox.question(self, "Profil silinsin mi?", f"{p['name']} profili silinsin mi? Bu profili kullanan "
                                "oturumlar profilsiz devam eder.") == QMessageBox.Yes:
            self.ctx.db.delete_profile(p["name"])
            self.refresh()

    def add_template(self) -> None:
        dlg = TemplateDialog(self.ctx, self)
        if dlg.exec():
            self.ctx.db.add_template(dlg.name.text().strip(), dlg.prompt.toPlainText().strip(),
                                     dlg.profile.currentData() or None)
            self.refresh()

    def use_template(self, t: tpl.Template) -> None:
        if t.needs_skill and not any(t.needs_skill in s.slug for s in self.ctx.skills()):
            QMessageBox.information(self, t.name, "Bu şablon bir skill ile en iyi çalışır, ama ilgili skill ekli değil. "
                                                  "Yine de kullanabilirsiniz; önce \"Klasörden skill ekle…\" önerilir.")
        self.template_requested.emit(t.prompt, t.profile)
