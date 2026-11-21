"""The app's look (UI-1, UI-3, UX §2): colours, sizes, bundled fonts, the "सं" monogram and the style sheet.

Light only: the Qt colour scheme is forced to Light so neither the widgets nor the native title bar follow Windows
dark mode (GEN-02). Text uses IBM Plex Sans bundled in ``ui/fonts`` with tabular figures switched on, so digits line
up in number columns (GEN-03). Sizes are in device-independent pixels; Qt scales them for 125% and 150% (NF-4).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPainter, QPalette, QPixmap)

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
FONT_FILES = ("IBMPlexSans-Regular.ttf", "IBMPlexSans-Medium.ttf", "IBMPlexSansDevanagari-Medium.ttf")
FAMILY = "IBM Plex Sans"
DEVANAGARI_FAMILY = "IBM Plex Sans Devanagari"
FALLBACK_FAMILY = "Segoe UI"
MONOGRAM = "सं"

# ---------------------------------------------------------------------------------------------- colours (canvas)
TEAL = "#0E6B6B"            # accent, primary buttons
TEAL_HOVER = "#0B5A5A"
TEAL_DARK = "#0A4F4F"       # text on tint, secondary button text
TINT = "#E3F1F0"            # selected rail item, tinted areas
TINT_BORDER = "#9CC7C4"     # secondary button outline
TEXT = "#1C2128"
MUTED = "#5B636E"
MUTED_2 = "#444B55"
SUBTLE = "#6B737D"
BORDER = "#E6E8EB"
INPUT_BORDER = "#D9DCE1"
DIVIDER = "#EEF0F2"
HEADER_BG = "#F8F9FA"
RAIL_BG = "#F6F7F8"
WHITE = "#FFFFFF"
ERROR = "#B42318"
ERROR_HOVER = "#912018"
ERROR_TINT = "#FDF1F0"
ERROR_TEXT = "#7A1A12"
WARNING = "#B54708"
WARNING_TINT = "#FEF6EC"
WARNING_BORDER = "#F7D9B5"
WARNING_TEXT = "#6A2C08"
SUCCESS = "#067647"
SUCCESS_TINT = "#ECF6F1"
SUCCESS_TEXT = "#05603A"
OVERRIDE_BG = "#FEF0E1"
OVERRIDE_TEXT = "#93370D"
DISABLED_BG = "#E6E8EB"
DISABLED_TEXT = "#9AA1AA"

# ---------------------------------------------------------------------------------------------- sizes (UX §2)
ROW_HEIGHT = 40             # grid rows and grid header rows (GEN-05)
GRID_TEXT_PX = 13
GRID_HEADER_PX = 12
BODY_PX = 14
SMALL_PX = 12
H1_PX = 22
H2_PX = 18                  # dialog titles
RAIL_WIDTH = 64
RAIL_ITEM = 52
BUTTON_HEIGHT = 36
SECTION_GAP = 24            # between sections
PANEL_PADDING = 16
CONTROL_GAP = 8             # 8-12 px between controls
PAGE_MARGINS = (32, 20, 32, 20)   # left, top, right, bottom
DIALOG_WIDTH = 500
DIALOG_PADDING = 24

# The design size (ENV-4). The window's minimum is this, capped to the screen's work area (FIT-04, decided
# 17-11-2026), so 1920x1080 at 150% (1280x720 logical) still fits. Layouts must fit down to MIN_LAYOUT.
DESIGN_SIZE = QSize(1366, 768)
MIN_LAYOUT = QSize(1280, 640)


_fonts_loaded: bool | None = None


def load_fonts() -> bool:
    """Register the bundled fonts with Qt (once). False if any file is missing or unreadable."""
    global _fonts_loaded
    if _fonts_loaded is None:
        ok = True
        for name in FONT_FILES:
            if QFontDatabase.addApplicationFont(str(FONTS_DIR / name)) < 0:
                ok = False
        _fonts_loaded = ok
    return _fonts_loaded


def font(px: int = BODY_PX, *, medium: bool = False, family: str = FAMILY) -> QFont:
    """A Plex font at ``px`` pixels with tabular figures (GEN-03)."""
    f = QFont(family)
    f.setFamilies([family, FALLBACK_FAMILY])
    f.setPixelSize(px)
    f.setWeight(QFont.Weight.Medium if medium else QFont.Weight.Normal)
    f.setFeature(QFont.Tag("tnum"), 1)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


def monogram_pixmap(size: int, device_ratio: float = 1.0) -> QPixmap:
    """The app mark: "सं" in white on a teal rounded square (UI-1)."""
    px = QPixmap(round(size * device_ratio), round(size * device_ratio))
    px.setDevicePixelRatio(device_ratio)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(TEAL))
    r = QRectF(0, 0, size, size)
    p.drawRoundedRect(r, size * 0.22, size * 0.22)
    f = font(max(6, round(size * 0.6)), medium=True, family=DEVANAGARI_FAMILY)
    p.setFont(f)
    p.setPen(QColor(WHITE))
    p.drawText(r.adjusted(0, -size * 0.04, 0, 0), Qt.AlignmentFlag.AlignCenter, MONOGRAM)
    p.end()
    return px


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(monogram_pixmap(s))
    return icon


def palette() -> QPalette:
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: WHITE, QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: WHITE, QPalette.ColorRole.AlternateBase: HEADER_BG,
        QPalette.ColorRole.Text: TEXT, QPalette.ColorRole.PlaceholderText: SUBTLE,
        QPalette.ColorRole.Button: WHITE, QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: TINT, QPalette.ColorRole.HighlightedText: TEAL_DARK,
        QPalette.ColorRole.ToolTipBase: TEXT, QPalette.ColorRole.ToolTipText: WHITE,
        QPalette.ColorRole.Link: TEAL, QPalette.ColorRole.LinkVisited: TEAL,
        QPalette.ColorRole.Light: WHITE, QPalette.ColorRole.Midlight: BORDER, QPalette.ColorRole.Mid: INPUT_BORDER,
        QPalette.ColorRole.Dark: MUTED, QPalette.ColorRole.Shadow: TEXT, QPalette.ColorRole.Accent: TEAL,
    }
    for role, colour in roles.items():
        pal.setColor(QPalette.ColorGroup.All, role, QColor(colour))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(DISABLED_TEXT))
    return pal


def style_sheet() -> str:
    """Widget looks by object name or the ``kind`` property: buttons (primary, secondary, plain, destructive,
    link), page headings, grids, banners, dialogs."""
    return f"""
QWidget {{ color: {TEXT}; }}
QMainWindow, QDialog, #Page {{ background: {WHITE}; }}
QToolTip {{ background: {TEXT}; color: {WHITE}; border: 0; padding: 4px 8px; font-size: {SMALL_PX}px; }}

QLabel[kind="h1"] {{ font-size: {H1_PX}px; font-weight: 500; }}
QLabel[kind="h2"] {{ font-size: {H2_PX}px; font-weight: 500; }}
QLabel[kind="subtitle"] {{ font-size: {GRID_TEXT_PX}px; color: {MUTED}; }}
QLabel[kind="body"] {{ font-size: {BODY_PX}px; color: {MUTED_2}; }}
QLabel[kind="small"] {{ font-size: {SMALL_PX}px; color: {MUTED}; }}
QLabel[kind="error"] {{ font-size: {GRID_TEXT_PX}px; color: {ERROR}; }}
QLabel[kind="warning"] {{ font-size: {GRID_TEXT_PX}px; color: {WARNING}; }}

QPushButton {{ min-height: {BUTTON_HEIGHT}px; max-height: {BUTTON_HEIGHT}px; padding: 0 16px; border-radius: 6px;
    font-size: {BODY_PX}px; border: 1px solid {INPUT_BORDER}; background: {WHITE}; color: {TEXT}; }}
QPushButton:hover {{ background: {HEADER_BG}; }}
QPushButton:focus {{ outline: none; border: 1px solid {TEAL}; }}
QPushButton:disabled {{ color: {DISABLED_TEXT}; background: {WHITE}; border-color: {BORDER}; }}
QPushButton[kind="primary"] {{ background: {TEAL}; color: {WHITE}; border: 0; font-weight: 500; }}
QPushButton[kind="primary"]:hover {{ background: {TEAL_HOVER}; }}
QPushButton[kind="primary"]:focus {{ border: 2px solid {TEAL_DARK}; }}
QPushButton[kind="primary"]:disabled {{ background: {DISABLED_BG}; color: {DISABLED_TEXT}; }}
QPushButton[kind="secondary"] {{ border: 1px solid {TINT_BORDER}; color: {TEAL_DARK}; font-weight: 500; }}
QPushButton[kind="secondary"]:hover {{ background: {TINT}; }}
QPushButton[kind="destructive"] {{ background: {ERROR}; color: {WHITE}; border: 0; font-weight: 500; }}
QPushButton[kind="destructive"]:hover {{ background: {ERROR_HOVER}; }}
QPushButton[kind="destructive"]:disabled {{ background: {DISABLED_BG}; color: {DISABLED_TEXT}; }}
QPushButton[kind="plain"] {{ border: 0; background: transparent; color: {TEAL_DARK}; font-weight: 500; }}
QPushButton[kind="plain"]:hover {{ background: {TINT}; }}
QPushButton[kind="plain"]:disabled {{ color: {DISABLED_TEXT}; }}
QPushButton[kind="op"] {{ min-height: 24px; max-height: 24px; padding: 0 12px; border-radius: 13px;
    font-size: {GRID_TEXT_PX}px; border: 1px solid {INPUT_BORDER}; background: {WHITE}; color: {MUTED_2}; }}
QPushButton[kind="op"]:hover {{ background: {HEADER_BG}; }}
QPushButton[kind="op"]:checked {{ border: 1px solid {TEAL}; background: {TINT}; color: {TEAL}; font-weight: 500; }}
#MeasureCard {{ border: 1px solid {BORDER}; border-radius: 6px; background: {WHITE}; }}
#MeasureCard[error="true"] {{ border: 1px solid {ERROR}; }}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{ min-height: 34px; border: 1px solid {INPUT_BORDER};
    border-radius: 6px; padding: 0 10px; background: {WHITE}; font-size: {BODY_PX}px;
    selection-background-color: {TINT}; selection-color: {TEAL_DARK}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {TEAL}; }}
QLineEdit[readOnly="true"] {{ background: {HEADER_BG}; color: {MUTED_2}; }}
QCheckBox {{ font-size: {BODY_PX}px; spacing: 10px; }}

#Rail {{ background: {RAIL_BG}; border-right: 1px solid {BORDER}; }}
#Rail QToolButton {{ border: 0; border-radius: 8px; background: transparent; color: {MUTED}; font-size: 11px;
    padding-top: 6px; }}
#Rail QToolButton:hover {{ background: {BORDER}; }}
#Rail QToolButton:checked {{ background: {TINT}; color: {TEAL_DARK}; font-weight: 500; }}
#Rail QToolButton:disabled {{ color: {DISABLED_TEXT}; }}

QTableView {{ border: 1px solid {BORDER}; border-radius: 8px; gridline-color: {DIVIDER}; background: {WHITE};
    font-size: {GRID_TEXT_PX}px; selection-background-color: {TINT}; selection-color: {TEXT}; outline: 0; }}
QTableView::item {{ border-bottom: 1px solid {DIVIDER}; padding: 0 8px; }}
QTableView::item:selected {{ background: {TINT}; color: {TEXT}; }}
QHeaderView {{ background: {HEADER_BG}; border: 0; }}
QHeaderView::section {{ background: {HEADER_BG}; color: {MUTED}; font-size: {GRID_HEADER_PX}px; font-weight: 500;
    border: 0; border-bottom: 1px solid {BORDER}; padding: 0 8px; height: {ROW_HEIGHT}px; }}
QTableCornerButton::section {{ background: {HEADER_BG}; border: 0; }}

QProgressBar {{ border: 0; border-radius: 4px; background: {BORDER}; max-height: 8px; min-height: 8px;
    text-align: center; color: transparent; }}
QProgressBar::chunk {{ border-radius: 4px; background: {TEAL}; }}

QScrollBar:vertical {{ width: 10px; background: transparent; margin: 2px; }}
QScrollBar:horizontal {{ height: 10px; background: transparent; margin: 2px; }}
QScrollBar::handle {{ background: {INPUT_BORDER}; border-radius: 3px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: #B9C0C7; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QMenu {{ background: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; font-size: {BODY_PX}px; }}
QMenu::item {{ padding: 8px 16px; border-radius: 6px; }}
QMenu::item:selected {{ background: {TINT}; color: {TEAL_DARK}; }}

QTabBar::tab {{ height: 38px; padding: 0; margin-right: 28px; border: 0; border-bottom: 2px solid transparent;
    background: transparent; color: {MUTED}; font-size: {BODY_PX}px; }}
QTabBar::tab:selected {{ color: {TEXT}; font-weight: 500; border-bottom: 2px solid {TEAL}; }}
"""


def apply(app: QGuiApplication) -> None:
    """Fonts, Fusion style, light palette, style sheet and window icon for the whole app."""
    load_fonts()
    hints = app.styleHints()
    try:
        hints.setColorScheme(Qt.ColorScheme.Light)     # light even when Windows is dark (GEN-02), title bar too
    except AttributeError:                              # pragma: no cover - Qt older than 6.8
        pass
    if hasattr(app, "setStyle"):
        app.setStyle("Fusion")
    app.setPalette(palette())
    app.setFont(font(BODY_PX))
    if hasattr(app, "setStyleSheet"):
        app.setStyleSheet(style_sheet())
    app.setWindowIcon(app_icon())


def polish(widget, **props) -> None:
    """Set dynamic properties (e.g. ``kind="primary"``) and re-apply the style sheet."""
    for k, v in props.items():
        widget.setProperty(k, v)
    st = widget.style()
    st.unpolish(widget)
    st.polish(widget)
