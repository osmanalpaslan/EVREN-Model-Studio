"""Yazı kutusundaki mikrofon düğmesi (Madde 20 C3): kaydet → yazıya çevir → kutuya ekle.

Akış: düğmeye basınca kayıt başlar (düğme kırmızı "dinliyor"), yeniden basınca durur; ses 16 kHz tek kanal WAV olarak
geçici dosyaya yazılır, agent/voice.transcribe AYRI süreçte çevirir (arka plan iş parçacığı, R-04), metin kutudaki
yazının sonuna eklenir — gönderilmez, kullanıcı düzeltip kendisi gönderir. İlk kullanımda kurulum için onay sorulur
(~600 MB indirme). Mikrofon yoksa / izin verilmediyse anlaşılır not.
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QMessageBox

from ..agent import voice
from .workers import Task


class VoiceInput(QObject):
    note = Signal(str, str)            # (metin, simge) → oturum notu

    def __init__(self, composer, data_dir: Path, parent=None):
        super().__init__(parent)
        self.composer = composer
        self.data_dir = Path(data_dir)
        self.source = None
        self.io = None
        self.buf = bytearray()
        self.busy = False
        self._t0 = 0.0
        self._limit = QTimer(self)
        self._limit.setSingleShot(True)
        self._limit.timeout.connect(self.stop)
        composer.mic_btn.clicked.connect(self.toggle)

    @property
    def recording(self) -> bool:
        return self.source is not None

    def toggle(self) -> None:
        if self.recording:
            self.stop()
        elif not self.busy:
            self.start()
        self._sync()

    def _sync(self) -> None:
        b = self.composer.mic_btn
        b.setChecked(self.recording)
        b.setToolTip("Dinliyor — durdurmak için tıklayın" if self.recording else
                     ("Yazıya çevriliyor…" if self.busy else "Sesle yaz (konuşun; metin kutuya eklenir)"))
        b.setEnabled(not self.busy)

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
        from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices

        dev = QMediaDevices.defaultAudioInput()
        if dev.isNull():
            self.note.emit("Mikrofon bulunamadı (Windows Ayarlar > Gizlilik > Mikrofon izni açık mı?).", "alert")
            return
        fmt = QAudioFormat()
        fmt.setSampleRate(voice.SAMPLE_RATE)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.Int16)
        if not dev.isFormatSupported(fmt):
            fmt = dev.preferredFormat()
        self.fmt = fmt
        self.buf = bytearray()
        self.source = QAudioSource(dev, fmt, self)
        self.io = self.source.start()
        if self.io is None:
            self.source = None
            self.note.emit("Mikrofon açılamadı.", "alert")
            return
        self.io.readyRead.connect(self._read)
        self._t0 = time.monotonic()
        self._limit.start(voice.MAX_SECONDS * 1000)

    def _read(self) -> None:
        if self.io is not None:
            self.buf += bytes(self.io.readAll())

    def stop(self) -> None:
        if self.source is None:
            return
        self._read()
        self._limit.stop()
        self.source.stop()
        self.source.deleteLater()
        self.source, self.io = None, None
        pcm = bytes(self.buf)
        self.buf = bytearray()
        if time.monotonic() - self._t0 < 0.6 or len(pcm) < voice.SAMPLE_RATE // 2:
            self.note.emit("Kayıt çok kısa; düğmeye basıp konuşun, bitince yeniden basın.", "alert")
            self._sync()
            return
        pcm = to_mono16k(pcm, self.fmt)
        wav = Path(tempfile.mkdtemp(prefix="evren-ses-")) / "kayit.wav"
        voice.write_wav(wav, pcm)
        self.transcribe(wav)

    def transcribe(self, wav: Path) -> None:
        self.busy = True
        self._sync()

        def done(res: voice.Transcript):
            self.busy = False
            self._sync()
            _cleanup(wav)
            if not res.text:
                self.note.emit("Konuşma anlaşılamadı; biraz daha yüksek sesle yeniden deneyin.", "alert")
                return
            cur = self.composer.edit.toPlainText()
            self.composer.set_text((cur.rstrip() + " " if cur.strip() else "") + res.text)

        def failed(exc):
            self.busy = False
            self._sync()
            _cleanup(wav)
            self.note.emit(f"Ses yazıya çevrilemedi: {exc}", "alert")

        Task(lambda: voice.transcribe(self.data_dir, wav), on_done=done, on_error=failed).start()


def _cleanup(wav: Path) -> None:
    import shutil

    shutil.rmtree(wav.parent, ignore_errors=True)


def to_mono16k(pcm: bytes, fmt) -> bytes:
    """Mikrofonun desteklediği biçim 16 kHz tek kanal 16 bit değilse dönüştürür (basit ortalama + doğrusal örnekleme)."""
    import array

    from PySide6.QtMultimedia import QAudioFormat

    rate, ch, sf = fmt.sampleRate(), fmt.channelCount(), fmt.sampleFormat()
    if rate == voice.SAMPLE_RATE and ch == 1 and sf == QAudioFormat.Int16:
        return pcm
    if sf == QAudioFormat.Float:
        a = array.array("f")
        a.frombytes(pcm[: len(pcm) - len(pcm) % 4])
        vals = [max(-1.0, min(1.0, x)) * 32767 for x in a]
    elif sf == QAudioFormat.Int32:
        a = array.array("i")
        a.frombytes(pcm[: len(pcm) - len(pcm) % 4])
        vals = [x / 65536 for x in a]
    elif sf == QAudioFormat.UInt8:
        vals = [(b - 128) * 256 for b in pcm]
    else:
        a = array.array("h")
        a.frombytes(pcm[: len(pcm) - len(pcm) % 2])
        vals = list(a)
    if ch > 1:
        vals = [sum(vals[i:i + ch]) / ch for i in range(0, len(vals) - ch + 1, ch)]
    if rate != voice.SAMPLE_RATE and vals:
        n = int(len(vals) * voice.SAMPLE_RATE / rate)
        step = rate / voice.SAMPLE_RATE
        vals = [vals[min(int(i * step), len(vals) - 1)] for i in range(n)]
    out = array.array("h", (int(max(-32768, min(32767, v))) for v in vals))
    return out.tobytes()
