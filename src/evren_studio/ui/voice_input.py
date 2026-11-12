"""Yazı kutusundaki mikrofon düğmesi (Madde 20 C3): kaydet → yazıya çevir → kutuya ekle.

Akış: düğmeye basınca kaydedici AYRI süreçte başlar (agent/voice.Recording; uygulama QtMultimedia taşımaz), "HAZIR"
gelince düğme "dinliyor" olur; yeniden basınca kayıt durur, ses yine ayrı süreçte yazıya çevrilir (arka plan iş
parçacığı, R-04), metin kutudaki yazının sonuna EKLENİR — gönderilmez, kullanıcı düzeltip kendisi gönderir. İlk
kullanımda kurulum için onay sorulur (~600 MB indirme). Ses bilgisayardan çıkmaz; geçici kayıt iş bitince silinir.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QMessageBox

from ..agent import voice
from .workers import Task

MIN_SECONDS = 0.6


class VoiceInput(QObject):
    note = Signal(str, str)            # (metin, simge) → oturum notu

    def __init__(self, composer, data_dir: Path, parent=None):
        super().__init__(parent)
        self.composer = composer
        self.data_dir = Path(data_dir)
        self.rec: voice.Recording | None = None
        self.busy = False
        self._limit = QTimer(self)
        self._limit.setSingleShot(True)
        self._limit.timeout.connect(self.stop)
        composer.mic_btn.clicked.connect(self.toggle)
        from PySide6.QtCore import QCoreApplication

        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    @property
    def recording(self) -> bool:
        return self.rec is not None

    def toggle(self) -> None:
        if self.recording:
            self.stop()
        elif not self.busy:
            self.start()
        self._sync()

    def _sync(self) -> None:
        from . import icons, theme

        b = self.composer.mic_btn
        rec = self.recording
        b.setChecked(rec)
        # Görünür durum: çip düğmelerinin seçili hâli için genel stil yok → dinlerken yazı + kırmızı çerçeve (Derin gibi)
        b.setText("Dinliyor" if rec else ("…" if self.busy else ""))
        b.setIcon(icons.icon("mic", color="danger" if rec else None, size=15))
        theme.style(b, (lambda pal: f"QToolButton {{ border: 1px solid {pal.danger}; color: {pal.danger}; }}")
                    if rec else (lambda _pal: ""))
        b.setToolTip("Dinliyor — durdurmak için tıklayın" if self.recording else
                     ("Hazırlanıyor…" if self.busy else "Sesle yaz (konuşun; metin kutuya eklenir)"))
        b.setEnabled(not self.busy or self.recording)

    # -- kurulum --
    def _ensure_installed(self) -> bool:
        if voice.installed(self.data_dir):
            return True
        ans = QMessageBox.question(
            self.composer, "Sesle yazma",
            "Sesle yazma için konuşma tanıma bileşeni bir kez indirilecek (~600 MB: faster-whisper + Türkçe destekli "
            "model). Ses bilgisayarınızda yazıya çevrilir, hiçbir yere gönderilmez. Kurulsun mu?")
        if ans != QMessageBox.Yes:
            return False
        self.busy = True
        self._sync()
        self.note.emit("Sesle yazma kuruluyor (birkaç dakika sürebilir; bu sırada çalışmaya devam edebilirsiniz)…",
                       "download")

        def job():
            voice.install(self.data_dir, voice.base_python())

        def done(_r=None):
            self.busy = False
            self._sync()
            self.note.emit("Sesle yazma kuruldu. Mikrofon düğmesine basıp konuşun.", "check")

        def failed(exc):
            self.busy = False
            self._sync()
            self.note.emit(f"Sesle yazma kurulamadı: {exc}", "alert")

        Task(job, on_done=done, on_error=failed).start()
        return False

    # -- kayıt --
    def start(self) -> None:
        if not self._ensure_installed():
            return
        self.busy = True
        self._sync()
        rec = voice.Recording(self.data_dir)

        def done(r: voice.Recording):
            self.busy = False
            self.rec = r
            self._limit.start(int(voice.MAX_SECONDS * 1000))
            self._sync()

        def failed(exc):
            self.busy = False
            rec.cleanup()
            self._sync()
            self.note.emit(f"Mikrofon açılamadı: {exc} (Windows Ayarlar > Gizlilik > Mikrofon izni açık mı?)", "alert")

        Task(rec.start, on_done=done, on_error=failed).start()

    def stop(self) -> None:
        rec, self.rec = self.rec, None
        if rec is None:
            return
        self._limit.stop()
        self.busy = True
        self._sync()

        def done(wav: Path):
            if voice.duration(wav) < MIN_SECONDS:
                self.busy = False
                rec.cleanup()
                self._sync()
                self.note.emit("Kayıt çok kısa; düğmeye basıp konuşun, bitince yeniden basın.", "alert")
                return
            self.transcribe(wav, rec)

        def failed(exc):
            self.busy = False
            rec.cleanup()
            self._sync()
            self.note.emit(f"Kayıt alınamadı: {exc}", "alert")

        Task(rec.stop, on_done=done, on_error=failed).start()

    def transcribe(self, wav: Path, rec: voice.Recording | None = None) -> None:
        self.busy = True
        self._sync()

        def finish():
            self.busy = False
            if rec is not None:
                rec.cleanup()
            else:
                _cleanup(wav)
            self._sync()

        def done(res: voice.Transcript):
            finish()
            if not res.text:
                self.note.emit("Konuşma anlaşılamadı; biraz daha yüksek sesle yeniden deneyin.", "alert")
                return
            cur = self.composer.edit.toPlainText()
            self.composer.set_text((cur.rstrip() + " " if cur.strip() else "") + res.text)

        def failed(exc):
            finish()
            self.note.emit(f"Ses yazıya çevrilemedi: {exc}", "alert")

        Task(lambda: voice.transcribe(self.data_dir, wav), on_done=done, on_error=failed).start()

    def shutdown(self) -> None:
        """Uygulama kapanırken açık kayıt süreci kalmasın."""
        rec, self.rec = self.rec, None
        if rec is not None:
            rec.cleanup()


def _cleanup(wav: Path) -> None:
    import shutil

    shutil.rmtree(wav.parent, ignore_errors=True)
