"""The window's side of the Job interface (T6, UI-5, SH-02).

``JobBridge`` starts Jobs on the app's ``JobRunner`` and polls them every ``POLL_INTERVAL_MS`` on the UI thread, so
screens get their results as callbacks on the UI thread and never block on a Job.

Two kinds of Job:
* **long Jobs** (load, validate, outputs, query, export, delete, move): one at a time. While one runs, every
  control registered with ``guard()`` is disabled with the tooltip "Another operation is running" (SH-02,
  confirmed 17-11-2026) and the rail shows its progress.
* **quiet Jobs** (a page of grid rows, a count): short reads. They don't disable anything; a long Job that wants to
  start cancels a running quiet Job first, and the quiet Job's owner asks again later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QWidget

from sankalan.jobs import POLL_INTERVAL_MS, Job, JobBusy, JobContext, JobRunner, JobState

BUSY_TOOLTIP = "Another operation is running"
QUIET_CANCEL_WAIT_S = 2.0


@dataclass
class _Tracked:
    job: Job
    quiet: bool
    on_done: Callable[[Any], None] | None = None
    on_failed: Callable[[BaseException | None], None] | None = None
    on_cancelled: Callable[[], None] | None = None
    on_finished: Callable[[Job], None] | None = None
    origin: Callable[[], None] | None = None        # opens the screen that started the Job (rail indicator)
    extra: dict = field(default_factory=dict)


class JobBridge(QObject):
    busyChanged = Signal(bool)          # a long Job started (True) or ended (False)
    progressed = Signal(object)         # the running long Job, every poll
    jobFinished = Signal(object)        # any tracked Job, once it has finished

    def __init__(self, runner: JobRunner | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._runner = runner
        self._tracked: list[_Tracked] = []
        self._guarded: dict[int, tuple[QWidget, bool, str]] = {}   # id → (widget, allowed, own tooltip)
        self._busy = False
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self.poll)

    # ------------------------------------------------------------------------------------------ runner
    @property
    def runner(self) -> JobRunner | None:
        return self._runner

    def set_runner(self, runner: JobRunner | None) -> None:
        self._runner = runner

    @property
    def busy(self) -> bool:
        """A long Job is running."""
        return self._busy

    @property
    def current(self) -> Job | None:
        """The running long Job, if any."""
        for t in self._tracked:
            if not t.quiet:
                return t.job
        return None

    def current_origin(self) -> Callable[[], None] | None:
        for t in self._tracked:
            if not t.quiet:
                return t.origin
        return None

    # ------------------------------------------------------------------------------------------ start
    def start(self, operation: str, work: Callable[[JobContext], Any], *, cancellable: bool = True,
              on_done=None, on_failed=None, on_cancelled=None, on_finished=None,
              origin: Callable[[], None] | None = None) -> Job:
        """Start a long Job. Raises ``JobBusy`` if another long Job is running (guarded controls make that rare).
        A running quiet Job is cancelled first."""
        if self._runner is None:
            raise JobBusy("starting")
        if self._busy:
            raise JobBusy(self.current.operation if self.current else "")
        self._stop_quiet()
        job = self._runner.start(operation, work, cancellable=cancellable)
        self._track(_Tracked(job, False, on_done, on_failed, on_cancelled, on_finished, origin))
        return job

    def track(self, job: Job, *, on_done=None, on_failed=None, on_cancelled=None, on_finished=None,
              origin=None) -> Job:
        """Follow a long Job that was started on the runner directly."""
        self._track(_Tracked(job, False, on_done, on_failed, on_cancelled, on_finished, origin))
        return job

    def try_quiet(self, operation: str, work: Callable[[JobContext], Any], *, on_done=None, on_failed=None,
                  on_cancelled=None) -> Job | None:
        """Start a quiet Job if the runner is free; None if it isn't (ask again after ``jobFinished``)."""
        if self._runner is None or self._runner.busy:
            return None
        try:
            job = self._runner.start(operation, work, cancellable=True)
        except JobBusy:
            return None
        self._track(_Tracked(job, True, on_done, on_failed, on_cancelled))
        return job

    def _stop_quiet(self) -> None:
        for t in list(self._tracked):
            if t.quiet:
                t.job.cancel()
                t.job.wait(QUIET_CANCEL_WAIT_S)
        self.poll()

    def _track(self, t: _Tracked) -> None:
        self._tracked.append(t)
        if not t.quiet:
            self._set_busy(True)
        if not self._timer.isActive():
            self._timer.start()

    # ------------------------------------------------------------------------------------------ polling
    def poll(self) -> None:
        for t in list(self._tracked):
            if t.job.wait(0):
                self._tracked.remove(t)
                if not any(not x.quiet for x in self._tracked):
                    self._set_busy(False)       # callbacks may start the next Job (the run wizard chains them)
                self._finish(t)
            elif not t.quiet:
                self.progressed.emit(t.job)
        if not any(not t.quiet for t in self._tracked):
            self._set_busy(False)
        if not self._tracked:
            self._timer.stop()

    def _finish(self, t: _Tracked) -> None:
        job = t.job
        try:
            if job.state is JobState.DONE and t.on_done:
                t.on_done(job.result)
            elif job.state is JobState.FAILED and t.on_failed:
                t.on_failed(job.error)
            elif job.state is JobState.CANCELLED and t.on_cancelled:
                t.on_cancelled()
            if t.on_finished:
                t.on_finished(job)
        finally:
            self.jobFinished.emit(job)

    def wait_all(self, timeout: float | None = None) -> None:
        """Wait for every tracked Job and deliver its callbacks (tests and shutdown)."""
        for t in list(self._tracked):
            t.job.wait(timeout)
        self.poll()

    # ------------------------------------------------------------------------------------------ SH-02 guard
    def guard(self, widget: QWidget, allowed: bool = True) -> QWidget:
        """Register a control that starts a long Job: it is disabled, with the tooltip "Another operation is
        running", while one runs. ``allowed`` is the screen's own condition (use ``set_allowed`` to change it)."""
        self._guarded[id(widget)] = (widget, allowed, widget.toolTip())
        widget.destroyed.connect(lambda *_a, k=id(widget): self._guarded.pop(k, None))
        self._apply(widget)
        return widget

    def set_allowed(self, widget: QWidget, allowed: bool, tooltip: str | None = None) -> None:
        w, _old, own = self._guarded.get(id(widget), (widget, True, widget.toolTip()))
        self._guarded[id(widget)] = (w, allowed, own if tooltip is None else tooltip)
        self._apply(widget)

    def _apply(self, widget: QWidget) -> None:
        w, allowed, own = self._guarded[id(widget)]
        w.setEnabled(allowed and not self._busy)
        w.setToolTip(BUSY_TOOLTIP if self._busy else own)

    def _set_busy(self, busy: bool) -> None:
        if busy == self._busy:
            return
        self._busy = busy
        for k in list(self._guarded):
            try:
                self._apply(self._guarded[k][0])
            except RuntimeError:            # the C++ widget is already gone
                self._guarded.pop(k, None)
        self.busyChanged.emit(busy)
