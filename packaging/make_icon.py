"""Write packaging/sankalan.ico and sankalan.png from the app's own mark (theme.monogram_pixmap: "सं" in white on
teal, UI-1), so Sankalan.exe, the installer and the shortcuts show the same icon as the window.

    set QT_QPA_PLATFORM=offscreen
    python packaging/make_icon.py

Development tool, run once when the mark changes; the outputs are committed. The .ico holds PNG images (Windows
Vista and later read them) at the sizes Explorer and the Start menu ask for.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def png_bytes(size: int) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from sankalan.ui import theme
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    theme.monogram_pixmap(size).save(buf, "PNG")
    buf.close()
    return bytes(data)


def ico(images: list[tuple[int, bytes]]) -> bytes:
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size            # 0 means 256 in an ICO directory entry
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    return head + entries + blobs


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from PySide6.QtGui import QGuiApplication
    from sankalan.ui import theme
    app = QGuiApplication.instance() or QGuiApplication([])
    theme.load_fonts()
    images = [(s, png_bytes(s)) for s in SIZES]
    (ROOT / "packaging" / "sankalan.ico").write_bytes(ico(images))
    (ROOT / "packaging" / "sankalan.png").write_bytes(images[-1][1])
    del app
    return 0


if __name__ == "__main__":
    sys.exit(main())
