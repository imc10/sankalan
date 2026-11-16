"""Line icons from the design canvas, drawn from inline SVG in any colour."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS = {
    "clients": '<path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/><path d="M9 21v-6h6v6"/><path d="M9 10h.01M15 10h.01"/>',
    "analysis": '<path d="M4 20h16"/><path d="M7 16V10"/><path d="M12 16V5"/><path d="M17 16v-4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1'
                'a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8'
                '.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 '
                '0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1'
                '.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0'
                ' 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.5h.01"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "storage": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/>'
               '<path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "working": '<path d="M12 3a9 9 0 1 0 9 9"/>',
}


def svg(name: str, colour: str, stroke: float = 1.6) -> bytes:
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="{colour}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{_PATHS[name]}</svg>'
            ).encode("utf-8")


def pixmap(name: str, colour: str, size: int = 20, ratio: float = 2.0, stroke: float = 1.6) -> QPixmap:
    pm = QPixmap(round(size * ratio), round(size * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.GlobalColor.transparent)
    r = QSvgRenderer(QByteArray(svg(name, colour, stroke)))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r.render(p, QRectF(0, 0, size, size))
    p.end()
    return pm


def icon(name: str, colour: str, size: int = 20, *, checked_colour: str | None = None,
         disabled_colour: str | None = None, stroke: float = 1.6) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, colour, size, stroke=stroke), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(pixmap(name, checked_colour or colour, size, stroke=stroke), QIcon.Mode.Normal, QIcon.State.On)
    if disabled_colour:
        ic.addPixmap(pixmap(name, disabled_colour, size, stroke=stroke), QIcon.Mode.Disabled, QIcon.State.Off)
    return ic
