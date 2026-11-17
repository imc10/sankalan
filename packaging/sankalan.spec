# PyInstaller spec for Sankalan: a folder build (not one exe), windowed (T3, Packaging).
#   python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\sankalan.spec
# Reader workers are this same Sankalan.exe started again in worker mode (multiprocessing spawn +
# freeze_support), so no second program is built and every worker runs the same signed exe (T5).
# Compiled packages shipped besides Python: PySide6-Essentials/shiboken6, duckdb, python-calamine (T2).
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "packaging"))
import version as app_version  # noqa: E402  packaging/version.py: the version from sankalan/__init__.py

ICON = ROOT / "packaging" / "sankalan.ico"
VERSION = app_version.version()

# Qt modules the app never uses: keep the bundle small and offline (no network modules, SEC-1).
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
    datas=[(str(ROOT / "sankalan" / "ui" / "fonts"), "sankalan/ui/fonts")],   # IBM Plex + OFL licence (GEN-03)
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


def _version_file():
    """version_info.txt with this build's version filled in, written next to the build's other work files."""
    if sys.platform != "win32":
        return None
    text = (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
    text = text.replace("{numbers}", repr(app_version.numeric(VERSION))).replace("{version}", VERSION)
    out = Path(workpath) / "version_info.generated.txt"  # noqa: F821  workpath is set by PyInstaller
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return str(out)


pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Sankalan",
    console=False,                    # windowed app
    upx=False,                        # compressed binaries trip antivirus and must not change after signing
    icon=str(ICON),
    version=_version_file(),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Sankalan", upx=False)
