"""The 64 px left rail (UX §3, GEN-01): Clients and Analysis at the top, the running Job and the gear at the bottom.

While a long Job runs, a "Working" item shows its progress; clicking it opens the screen that started the Job
(SH-02).
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QToolButton, QVBoxLayout

from sankalan import formats
from sankalan.ui import theme
from sankalan.ui.widgets import icons

AREAS = (("clients", "Clients"), ("analysis", "Analysis"))


class Rail(QFrame):
    areaClicked = Signal(str)
    settingsClicked = Signal()
    jobClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Rail")
        self.setFixedWidth(theme.RAIL_WIDTH)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 12, 6, 12)
        lay.setSpacing(4)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: dict[str, QToolButton] = {}
        for key, label in AREAS:
            b = QToolButton(self)
            b.setObjectName(f"rail-{key}")
            b.setText(label)
            b.setAccessibleName(label)
            b.setCheckable(True)
            b.setIcon(icons.icon(key, theme.MUTED, checked_colour=theme.TEAL))
            b.setIconSize(QSize(20, 20))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setFixedSize(theme.RAIL_ITEM, theme.RAIL_ITEM)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=key: self.areaClicked.emit(k))
            self._group.addButton(b)
            self.buttons[key] = b
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(1)

        self.job_button = QToolButton(self)
        self.job_button.setObjectName("rail-job")
        self.job_button.setText("Working")
        self.job_button.setIcon(icons.icon("working", theme.TEAL, stroke=2.0))
        self.job_button.setIconSize(QSize(18, 18))
        self.job_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.job_button.setFixedSize(theme.RAIL_ITEM, theme.RAIL_ITEM)
        self.job_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.job_button.clicked.connect(self.jobClicked)
        self.job_button.hide()
        lay.addWidget(self.job_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.settings_button = QToolButton(self)
        self.settings_button.setObjectName("rail-settings")
        self.settings_button.setAccessibleName("App settings")
        self.settings_button.setToolTip("App settings")
        self.settings_button.setIcon(icons.icon("settings", theme.MUTED))
        self.settings_button.setIconSize(QSize(20, 20))
        self.settings_button.setFixedSize(40, 40)
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.clicked.connect(self.settingsClicked)
        lay.addWidget(self.settings_button, 0, Qt.AlignmentFlag.AlignHCenter)

    def select(self, area: str | None) -> None:
        if area in self.buttons:
            self.buttons[area].setChecked(True)
        else:
            self._group.setExclusive(False)
            for b in self.buttons.values():
                b.setChecked(False)
            self._group.setExclusive(True)

    def selected(self) -> str | None:
        for k, b in self.buttons.items():
            if b.isChecked():
                return k
        return None

    def show_job(self, job) -> None:
        """Show (or update) the running Job's indicator; ``None`` hides it."""
        if job is None:
            self.job_button.hide()
            return
        p = job.progress()
        pct = "" if p.fraction is None else f"{round(p.fraction * 100)}%"
        self.job_button.setText(pct or "Working")
        stage = f" · {p.stage}" if p.stage else ""
        self.job_button.setToolTip(f"{job.operation}{stage} · {formats.elapsed(p.elapsed)} elapsed")
        self.job_button.setAccessibleName(f"{job.operation} running")
        self.job_button.show()
