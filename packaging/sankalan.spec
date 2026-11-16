# PyInstaller spec for Sankalan (one-folder, windowed). V2: fully reworked in Phase 11. Build: pyinstaller packaging/sankalan.spec
# Works on Windows (Sankalan.exe) and, for testing, on Linux.
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON = ROOT / "packaging" / "sankalan.ico"

# Qt modules the app never uses: keep the bundle small and offline (no network modules).
EXCLUDES = [
    "PySide6.QtNetwork", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D",
    "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtBluetooth", "PySide6.QtPositioning",
    "PySide6.QtNfc", "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtPdf", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtRemoteObjects", "PySide6.QtHttpServer",
    "pandas", "numpy", "matplotlib", "tkinter", "pytest", "IPython",
    "lxml", "openpyxl", "pyarrow", "xlrd", "xlwt", "xlsxwriter", "msoffcrypto", "cryptography",
    "legacy",                                     # V1 reference code, never shipped
]

a = Analysis(
    [str(ROOT / "sankalan" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "sankalan" / "ui" / "fonts"), "sankalan/ui/fonts")],   # IBM Plex (OFL); icon in Phase 11
    hiddenimports=[],
    excludes=EXCLUDES,
    noarchive=False,
)
# Drop Qt libraries/plugins that pull in Qt networking, QML or a VNC server: the app needs none of them.
DROP = ("qt6network", "qt6qml", "qt6quick", "qt6virtualkeyboard", "qt6pdf", "qpdf", "qtvirtualkeyboard",
        "qtuiotouch", "qvnc", "qt6websockets", "qt6webengine")
def _keep(entry):
    return not any(d in entry[0].lower() for d in DROP)


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]          # PyInstaller also lists library symlinks here

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Sankalan",
    console=False,                    # windowed app
    icon=str(ICON) if ICON.exists() else None,
    version=str(ROOT / "packaging" / "version_info.txt") if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Sankalan")
