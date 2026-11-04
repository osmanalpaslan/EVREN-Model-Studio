"""Ayarlar > GitHub (Madde 12d, 2026-11-05): tarayıcıyla bağlanma, bağlantıyı kesme, depodan proje açma (klon).

Giriş akışı (ücretsiz, gh CLI): "GitHub hesabını bağla" → gh tek kullanımlık kod üretir → pencere kodu gösterir, panoya
kopyalar ve tarayıcıda github.com/login/device'ı açar → kullanıcı kodu girip onaylar → gh biter → `gh auth setup-git`
(git push/pull parolasız) → durum "Bağlı: kullanıcı". gh kurulu değilse "GitHub CLI'yi kur" (winget, ücretsiz).
"""
from __future__ import annotations

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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

from ..agent import github as gh
from .workers import Task


def _hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", "dim")
    lab.setWordWrap(True)
    return lab


class LoginDialog(QDialog):
    """gh auth login --web'i pencere içinden yürütür: kodu gösterir, tarayıcıyı açar, sonucu bekler."""
    done = Signal(bool, str)

    def __init__(self, parent=None, open_browser=True):
        super().__init__(parent)
        self.setWindowTitle("GitHub hesabını bağla")
        self.setMinimumWidth(460)
        self.open_browser = open_browser
        self.code = ""
        self.url = ""
        self.ok = False
        self._buf = ""
        lay = QVBoxLayout(self)
        self.info = _hint("GitHub'dan tek kullanımlık bir kod isteniyor…")
        lay.addWidget(self.info)
        self.code_label = QLabel("")
        self.code_label.setAlignment(Qt.AlignCenter)
        self.code_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.code_label.setStyleSheet("font-size: 22pt; font-weight: 700; letter-spacing: 3px; padding: 8px;")
        lay.addWidget(self.code_label)
        row = QHBoxLayout()
        self.copy_btn = QPushButton("Kodu kopyala")
        self.copy_btn.clicked.connect(self._copy)
        self.browser_btn = QPushButton("Tarayıcıda aç")
        self.browser_btn.setProperty("variant", "primary")
        self.browser_btn.clicked.connect(self._browser)
        for b in (self.copy_btn, self.browser_btn):
            b.setEnabled(False)
            row.addWidget(b)
        lay.addLayout(row)
        self.state = _hint("")
        lay.addWidget(self.state)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("GH_PROMPT_DISABLED", "1")
        env.insert("NO_COLOR", "1")
        self.proc.setProcessEnvironment(env)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(self._finished)
        self.proc.errorOccurred.connect(lambda _e: self._fail("gh başlatılamadı"))

    def start(self) -> bool:
        cmd = gh.gh_command()
        if cmd is None:
            self._fail("GitHub CLI (gh) kurulu değil")
            return False
        self.proc.start(cmd[0], cmd[1:] + gh.login_args())
        self.proc.closeWriteChannel()             # etkileşimsiz: gh kodu yazar ve onayı bekler
        return True

    def _read(self) -> None:
        self._buf += bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        if self.code:
            return
        code, url = gh.parse_device_code(self._buf)
        if code:
            self.code, self.url = code, url
            self.code_label.setText(code)
            self.info.setText("1) Kodu kopyalayın (otomatik kopyalandı)  2) Açılan GitHub sayfasına yapıştırın  "
                              "3) “Authorize” ile onaylayın. Pencere kendiliğinden kapanır.")
            self.state.setText("Tarayıcıda onay bekleniyor…")
            for b in (self.copy_btn, self.browser_btn):
                b.setEnabled(True)
            self._copy()
            if self.open_browser:
                self._browser()

    def _copy(self) -> None:
        if self.code:
            QGuiApplication.clipboard().setText(self.code)

    def _browser(self) -> None:
        QDesktopServices.openUrl(QUrl(self.url or gh.DEVICE_URL))

    def _finished(self, code: int, _status) -> None:
        if code == 0:
            self.ok = True
            self.state.setText("Onaylandı; git ayarlanıyor…")
            self.done.emit(True, "")
            self.accept()
        else:
            tail = self._buf.strip().splitlines()[-1:] or [""]
            self._fail(tail[0][:200] or f"gh çıkış kodu {code}")

    def _fail(self, text: str) -> None:
        self.state.setText(f"Bağlanamadı: {text}")
        self.state.setProperty("role", "warning")
        self.state.style().unpolish(self.state)
        self.state.style().polish(self.state)
        self.done.emit(False, text)

    def reject(self) -> None:
        if self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(2000)
        super().reject()


class RepoPicker(QDialog):
    """GitHub depolarından birini seçme (arama kutulu)."""

    def __init__(self, repos: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GitHub'dan proje aç")
        self.setMinimumSize(520, 460)
        self.repos = repos
        lay = QVBoxLayout(self)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Depo ara…")
        self.filter.textChanged.connect(self._fill)
        lay.addWidget(self.filter)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        lay.addWidget(self.list, 1)
        lay.addWidget(_hint("Seçtiğiniz depo bilgisayarınızda bir klasöre indirilir (klonlanır) ve proje olarak "
                            "açılabilir."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Klasör seç ve indir")
        bb.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._fill()

    def _fill(self, *_a) -> None:
        q = self.filter.text().strip().lower()
        self.list.clear()
        for r in self.repos:
            if q and q not in r.full_name.lower() and q not in r.description.lower():
                continue
            text = r.full_name + ("  ·  gizli" if r.private else "") + (f"\n{r.description}" if r.description else "")
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, r.full_name)
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)

    def selected(self) -> str:
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else ""


class GitHubCard(QWidget):
    """Ayarlar > GitHub kartı. `open_workspace(str)`: klonlanan klasörü yeni oturumda aç."""
    open_workspace = Signal(str)
    changed = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.account = gh.Account(False)
        self._tasks: set = set()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(_hint("GitHub hesabınızı tarayıcıdan onaylayarak ücretsiz bağlayın. Bağlantıdan sonra Git "
                            "panelinden değişiklikleri GitHub'a gönderebilir (push), güncellemeleri alabilir (pull), "
                            "projeniz için GitHub'da depo oluşturabilir veya depolarınızdan birini açabilirsiniz. "
                            "Giriş bilgisi GitHub'ın resmî aracı (gh) tarafından Windows Credential Manager'da "
                            "saklanır; EVREN Studio parolanızı veya belirtecinizi görmez."))
        self.status = QLabel("Denetleniyor…")
        self.status.setStyleSheet("font-weight: 600;")
        lay.addWidget(self.status)
        row = QHBoxLayout()
        self.connect_btn = QPushButton("GitHub hesabını bağla")
        self.connect_btn.setProperty("variant", "primary")
        self.connect_btn.clicked.connect(lambda _=None: self.connect_account())
        self.install_btn = QPushButton("GitHub CLI'yi kur (ücretsiz)")
        self.install_btn.clicked.connect(lambda _=None: self.install_gh())
        self.clone_btn = QPushButton("Depolarımdan aç…")
        self.clone_btn.clicked.connect(lambda _=None: self.clone_repo())
        self.logout_btn = QPushButton("Bağlantıyı kes")
        self.logout_btn.setProperty("variant", "danger")
        self.logout_btn.clicked.connect(lambda _=None: self.disconnect_account())
        for b in (self.connect_btn, self.install_btn, self.clone_btn, self.logout_btn):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.note = _hint("")
        lay.addWidget(self.note)
        # Durum (gh auth status, ağ) yalnız menü açılınca denetlenir: açılışta ve testlerde ağa çıkmasın
        self.status.setText("GitHub bağlantısı denetleniyor…")
        for b in (self.connect_btn, self.install_btn, self.clone_btn, self.logout_btn):
            b.setVisible(False)

    # ---- durum ----

    def _bg(self, fn, done, fail=None) -> None:
        t = Task(fn, on_done=lambda r: (self._tasks.discard(t), done(r)),
                 on_error=lambda e: (self._tasks.discard(t), (fail or self._fail)(e)))
        self._tasks.add(t)
        t.start()

    def _fail(self, exc) -> None:
        self.note.setText(f"Hata: {exc}")
        self._busy(False)

    def _busy(self, on: bool) -> None:
        for b in (self.connect_btn, self.install_btn, self.clone_btn, self.logout_btn):
            b.setEnabled(not on)

    def refresh(self) -> None:
        # Denetim sürerken yanıltıcı düğme gösterme (hesap bağlıyken "bağla" görünüyordu, 2026-11-05 ekran)
        self.status.setText("GitHub bağlantısı denetleniyor…")
        for b in (self.connect_btn, self.install_btn, self.clone_btn, self.logout_btn):
            b.setVisible(False)
        self._bg(gh.account, self._apply)

    def _apply(self, acc) -> None:
        self.account = acc
        self.status.setText(acc.text())
        self.install_btn.setVisible(not acc.installed)
        self.connect_btn.setVisible(acc.installed and not acc.connected)
        self.clone_btn.setVisible(acc.connected)
        self.logout_btn.setVisible(acc.connected)
        self._busy(False)
        self.changed.emit()

    # ---- eylemler ----

    def connect_account(self, open_browser: bool = True) -> LoginDialog | None:
        dlg = LoginDialog(self, open_browser=open_browser)
        result = {}
        dlg.done.connect(lambda ok, msg: result.update(ok=ok, msg=msg))
        if not dlg.start():
            self.note.setText("GitHub CLI (gh) kurulu değil; önce “GitHub CLI'yi kur”a basın.")
            return None
        self._login_dialog = dlg
        dlg.finished.connect(lambda _r: self._after_login(result))
        dlg.open()
        return dlg

    def _after_login(self, result: dict) -> None:
        if not result.get("ok"):
            if result.get("msg"):
                self.note.setText(f"Bağlanamadı: {result['msg']}")
            return
        self.note.setText("Bağlandı. Git ayarlanıyor (gh auth setup-git)…")

        def job():
            ok, out = gh.setup_git()
            return ok, out, gh.account()

        def done(res):
            ok, out, acc = res
            self._apply(acc)
            self.note.setText("Bağlantı tamam; git GitHub girişini kullanıyor." if ok
                              else f"Bağlandı ama git ayarlanamadı: {out[:160]}")
        self._bg(job, done)

    def disconnect_account(self) -> None:
        login = self.account.login
        if QMessageBox.question(self, "GitHub bağlantısını kes",
                                f"{login or 'GitHub'} hesabının bu bilgisayardaki girişi silinsin mi?\n\n"
                                "GitHub'daki depolarınız etkilenmez; yeniden bağlanabilirsiniz.") != QMessageBox.Yes:
            return
        self._busy(True)

        def job():
            ok, out = gh.logout(login)
            return ok, out, gh.account()

        def done(res):
            ok, out, acc = res
            self._apply(acc)
            self.note.setText("Bağlantı kesildi." if ok else f"Kesilemedi: {out[:160]}")
        self._bg(job, done)

    def install_gh(self) -> None:
        if QMessageBox.question(self, "GitHub CLI kurulsun mu?",
                                "GitHub'ın resmî ücretsiz komut satırı aracı (gh) Windows Paket Yöneticisi (winget) "
                                "ile kurulacak. Devam edilsin mi?") != QMessageBox.Yes:
            return
        self._busy(True)
        self.note.setText("GitHub CLI kuruluyor (1-2 dk)…")

        def job():
            import subprocess

            r = subprocess.run(gh.install_command(), capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return r.returncode, (r.stdout or "")[-300:] + (r.stderr or "")[-300:], gh.account()

        def done(res):
            code, out, acc = res
            self._apply(acc)
            self.note.setText("GitHub CLI kuruldu. Şimdi hesabınızı bağlayabilirsiniz." if acc.installed
                              else f"Kurulamadı (çıkış {code}): {out.strip()[-200:]}")
        self._bg(job, done)

    def clone_repo(self) -> None:
        self._busy(True)
        self.note.setText("Depolarınız alınıyor…")

        def done(repos):
            self._busy(False)
            self.note.setText("")
            if not repos:
                self.note.setText("Bu hesapta depo bulunamadı.")
                return
            pick = RepoPicker(repos, self)
            if pick.exec() != QDialog.Accepted or not pick.selected():
                return
            parent = QFileDialog.getExistingDirectory(self, "Deponun indirileceği üst klasör",
                                                      (self.ctx.settings.recent_workspaces or [""])[0])
            if parent:
                self._clone(pick.selected(), parent)
        self._bg(lambda: gh.list_repos(), done)

    def _clone(self, full_name: str, parent: str) -> None:
        self._busy(True)
        self.note.setText(f"{full_name} indiriliyor…")

        def done(res):
            ok, info = res
            self._busy(False)
            if not ok:
                self.note.setText(f"İndirilemedi: {info[:200]}")
                return
            self.note.setText(f"İndirildi: {info}")
            if QMessageBox.question(self, "Proje indirildi",
                                    f"{full_name} → {info}\n\nBu klasör yeni oturumda proje olarak açılsın mı?") \
                    == QMessageBox.Yes:
                self.open_workspace.emit(info)
        self._bg(lambda: gh.clone(full_name, parent), done)
