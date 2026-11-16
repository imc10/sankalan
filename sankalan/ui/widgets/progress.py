"""ProgressPanel (UI-5): a running Job's stage, bar, rows done of total, elapsed time and Cancel.

It talks only to the Job interface (``progress()``, ``cancel()``), polling every ``POLL_INTERVAL_MS``. When the
fraction isn't known the bar runs as a busy indicator. Cancel is hidden for a Job that can't be cancelled (the
commit, RUN-5).
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from sankalan import formats
from sankalan.jobs import POLL_INTERVAL_MS, Job, JobState
from sankalan.ui import theme

BAR_STEPS = 1000


def rows_text(done: int | None, total: int | None, unit: str = "rows") -> str:
    if done is None:
        return ""
    if total:
        return f"{formats.number(done)} of {formats.number(total)} {unit}"
    return f"{formats.number(done)} {unit}"


class ProgressPanel(QWidget):
    finished = Signal(object)       # the Job, once it has ended (done, failed or cancelled)

    def __init__(self, parent=None, *, cancel_text: str = "Cancel", unit: str = "rows", note: str | None = None):
        super().__init__(parent)
        self.unit = unit
        self.job: Job | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.stage = QLabel(self)
        self.stage.setProperty("kind", "body")
        lay.addWidget(self.stage)
        self.bar = QProgressBar(self)
        self.bar.setRange(0, BAR_STEPS)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)
        line = QHBoxLayout()
        line.setSpacing(theme.CONTROL_GAP)
        self.rows = QLabel(self)
        self.elapsed = QLabel(self)
        for lab in (self.rows, self.elapsed):
            lab.setStyleSheet(f"color: {theme.MUTED_2}; font-size: {theme.GRID_TEXT_PX}px;")
        line.addWidget(self.rows, 1)
        line.addWidget(self.elapsed)
        lay.addLayout(line)
        self.note = QLabel(note or "", self)
        self.note.setProperty("kind", "body")
        self.note.setWordWrap(True)
        self.note.setVisible(bool(note))
        lay.addWidget(self.note)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_button = QPushButton(cancel_text, self)
        self.cancel_button.clicked.connect(self.cancel)
        buttons.addWidget(self.cancel_button)
        lay.addLayout(buttons)
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)

    def bind(self, job: Job) -> None:
        self.job = job
        self.cancel_button.setEnabled(True)
        self.refresh()
        self._timer.start()

    def cancel(self) -> None:
        if self.job is not None and self.job.cancel():
            self.cancel_button.setEnabled(False)
            self.refresh()

    def refresh(self) -> None:
        job = self.job
        if job is None:
            return
        p = job.progress()
        if p.state is JobState.CANCELLING:
            self.stage.setText("Cancelling…")
        else:
            self.stage.setText(p.stage or job.operation)
        if p.fraction is None:
            self.bar.setRange(0, 0)                     # busy indicator
        else:
            self.bar.setRange(0, BAR_STEPS)
            self.bar.setValue(round(p.fraction * BAR_STEPS))
        self.rows.setText(rows_text(p.rows_done, p.rows_total, self.unit))
        self.elapsed.setText(f"{formats.elapsed(p.elapsed)} elapsed")
        self.cancel_button.setVisible(p.cancellable or p.state is JobState.CANCELLING)
        if job.wait(0):
            self._timer.stop()
            if p.state is JobState.DONE:
                self.bar.setRange(0, BAR_STEPS)
                self.bar.setValue(BAR_STEPS)
            self.cancel_button.hide()
            self.finished.emit(job)
