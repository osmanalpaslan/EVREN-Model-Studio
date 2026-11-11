# PyInstaller ayarı — klasörlü (onedir), konsolsuz. Çalıştırma: tools\paketle.py (elle: pyinstaller installer\evren_studio.spec)
# Karar: docs/ILERIDE_YAPILACAKLAR.md §1.1 (onefile İSTENMİYOR: hızlı açılış, daha az antivirüs yanlış alarmı).
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent                      # depo kökü
AGENT = ROOT / "src" / "evren_studio" / "agent"

# Uygulamanın kendi içinde değil, AYRI bir Python ortamında çalışan betikler: içe aktarılmazlar, dosya olarak lazım
# (mcp.WINDOWS_LAUNCHER, runner'ın Blender betiği). Paketlenmezse masaüstü kontrolü / Blender dönüştürme çalışmaz.
datas = [
    (str(AGENT / "wmcp_baslatici.py"), "evren_studio/agent"),
    (str(AGENT / "blender_donustur.py"), "evren_studio/agent"),
    (str(ROOT / "assets" / "evren.ico"), "assets"),
    (str(ROOT / "LICENSE"), "."),
]
# ruff (Madde 20 A2): hata bekçisi Python dosyasında tanımsız ad / yapı hatası arar. pip paketinin ikili dosyası
# Scripts/ altına kurulur (paket klasörüne değil) → PyInstaller kendiliğinden almaz; elle `tools/` altına konur.
RUFF = Path(sys.executable).with_name("ruff.exe")
if RUFF.is_file():
    datas.append((str(RUFF), "tools"))

# Kullanılmayan Qt modülleri ve ayrı ortamda çalışan betiklerin bağımlılıkları (mcp SDK, windows_mcp, Serena, Blender)
excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.Qt3DExtras", "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets", "PySide6.QtQml", "PySide6.QtQuickControls2",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSerialBus", "PySide6.QtTextToSpeech", "PySide6.QtSpatialAudio",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtUiTools", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtWebSockets",
    "PySide6.QtHttpServer", "PySide6.QtNetworkAuth", "PySide6.QtVirtualKeyboard",
    "tkinter", "unittest", "pytest", "mcp", "windows_mcp", "solidlsp", "serena", "bpy",
]

a = Analysis(
    [str(Path(SPECPATH) / "evren_giris.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    # Ad ile (dize) yüklenenler — PyInstaller göremez: keyring arka ucu giriş noktasıyla, markdown eklentileri
    # markdown_view.py'de "fenced_code" vb. adla
    hiddenimports=["keyring.backends.Windows", "markdown.extensions.fenced_code", "markdown.extensions.tables",
                   "markdown.extensions.sane_lists", "markdown.extensions.codehilite"],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EVREN Studio",
    icon=str(ROOT / "assets" / "evren.ico"),
    version=str(ROOT / "build" / "surum_bilgisi.txt"),   # tools/paketle.py üretir (sürüm tek kaynaktan)
    console=False,
    upx=False,                                           # UPX antivirüs yanlış alarmını artırır
)
coll = COLLECT(exe, a.binaries, a.datas, name="EVREN Studio", upx=False)
