"""Windows 11 look (NF-9), matching the UI screens."""

ACCENT = "#005FB8"
ACCENT_DARK = "#003E92"
INK = "#1B1B1B"
QUIET = "#5C5C5C"
ERROR = "#A4262C"
ERROR_BG = "#FDE7E9"
WARN = "#7A4A00"
WARN_BG = "#FFF4CE"
OK = "#0F5B0F"
OK_BG = "#DFF6DD"

QSS = f"""
QWidget {{ font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", sans-serif; font-size: 10pt; color: {INK}; }}
QMainWindow, #page {{ background: #F3F3F3; }}
#sidebar {{ background: #F9F9F9; border-right: 1px solid #E5E5E5; }}
#h1 {{ font-size: 20pt; font-weight: 600; }}
#h2 {{ font-size: 11pt; font-weight: 600; }}
#sub, #quiet {{ color: {QUIET}; }}
#small {{ color: {QUIET}; font-size: 9pt; }}
#card {{ background: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 8px; }}
#drop {{ background: #FFFFFF; border: 2px dashed #8A8A8A; border-radius: 8px; }}
#tile {{ background: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 8px; }}
#tileValue {{ font-size: 20pt; font-weight: 600; }}
QPushButton {{ min-height: 34px; padding: 0 14px; border-radius: 4px; border: 1px solid #C8C8C8; background: #FFFFFF; }}
QPushButton:hover {{ background: #F5F5F5; }}
QPushButton:disabled {{ color: #9E9E9E; background: #F3F3F3; }}
QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: #FFFFFF; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_DARK}; }}
QPushButton#primary:disabled {{ background: #9DBAD8; border-color: #9DBAD8; }}
QPushButton#danger {{ border: none; background: transparent; color: {ERROR}; text-decoration: underline; }}
QPushButton#nav {{ text-align: left; border: none; background: transparent; padding: 8px 10px; }}
QPushButton#nav[current="true"] {{ background: #DCE8F5; color: {ACCENT_DARK}; font-weight: 600; }}
QPushButton#tab[selected="true"] {{ background: #F3F3F3; font-weight: 600; }}
QLineEdit, QComboBox, QSpinBox {{ min-height: 30px; padding: 0 8px; border: 1px solid #C8C8C8; border-bottom: 2px solid #8A8A8A; border-radius: 4px; background: #FFFFFF; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-bottom: 2px solid {ACCENT}; }}
QTableWidget {{ background: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 8px; gridline-color: #EDEDED; selection-background-color: #E5EEF8; selection-color: {INK}; }}
QHeaderView::section {{ background: #FFFFFF; color: {QUIET}; font-size: 9pt; font-weight: 600; border: none; border-bottom: 1px solid #E0E0E0; padding: 8px; }}
#banner[kind="error"] {{ background: {ERROR_BG}; border: 1px solid #F1B5B9; border-radius: 6px; }}
#banner[kind="warning"] {{ background: {WARN_BG}; border: 1px solid #F0D58C; border-radius: 6px; }}
#banner[kind="ok"] {{ background: {OK_BG}; border: 1px solid #A8D8A4; border-radius: 6px; }}
#banner[kind="info"] {{ background: #E5EEF8; border: 1px solid #B9D0EA; border-radius: 6px; }}
QProgressBar {{ border: 1px solid #C8C8C8; border-radius: 4px; background: #FFFFFF; text-align: center; height: 18px; }}
QProgressBar::chunk {{ background: {ACCENT}; }}
"""
