"""One Job: state, progress and cancel (Tech spec, Architecture → Jobs)."""
from __future__ import annotations

import enum
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

POLL_INTERVAL_MS = 250
INTERRUPT_REPEAT_S = 0.05


class JobState(enum.Enum):
    RUNNING = "running"
    CANCELLING = "cancelling"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"     # final state after a cancel was honoured (the spec's four states plus this outcome)

    @property
    def finished(self) -> bool:
        return self in (JobState.DONE, JobState.FAILED, JobState.CANCELLED)


class Cancelled(Exception):
    """Raised inside a Job's work when cancel was requested."""


class JobBusy(Exception):
    """Another long Job is already running (T6)."""


@dataclass(frozen=True)
class Progress:
    state: JobState
    stage: str
    rows_done: int | None
    rows_total: int | None
    fraction: float | None      # 0..1 when known: from rows, else from DuckDB's query progress
    elapsed: float              # seconds
    cancellable: bool
    error_class: str | None


class JobContext:
    """Handed to the Job's work function."""

    def __init__(self, job: "Job", connection=None):
        self._job = job
        self._connection = connection
        self.job_id = job.id

    # progress
    def set_stage(self, stage: str, rows_total: int | None = None) -> None:
        with self._job._lock:
            self._job._stage = stage
            self._job._rows_done = 0 if rows_total is not None else None
            self._job._rows_total = rows_total

    def set_rows(self, done: int, total: int | None = None) -> None:
        with self._job._lock:
            self._job._rows_done = done
            if total is not None:
                self._job._rows_total = total

    def add_rows(self, n: int) -> None:
        with self._job._lock:
            self._job._rows_done = (self._job._rows_done or 0) + n

    # cancel
    @property
    def cancel_requested(self) -> bool:
        return self._job._cancel.is_set()

    def check_cancelled(self) -> None:
        if self._job._cancel.is_set():
            raise Cancelled()

    def on_cancel(self, callback: Callable[[], None]) -> None:
        """Run ``callback`` when cancel is requested (e.g. signal reader workers to stop). Runs at once if a cancel
        is already pending."""
        self._job._add_cancel_callback(callback)

    def on_abort(self, callback: Callable[[], None]) -> None:
        """Run ``callback`` if the Job fails or is cancelled (e.g. discard the staging it created)."""
        self._job._abort_callbacks.append(callback)

    def set_cancellable(self, cancellable: bool) -> None:
        """Switch cancel off for a step that must finish, such as the commit (RUN-5)."""
        with self._job._lock:
            self._job.cancellable = cancellable

    # DuckDB
    def cursor(self):
        """The app-wide DuckDB connection, which ``cancel()`` interrupts and whose query progress feeds
        ``Job.progress()``. Jobs use the connection itself, not ``connection.cursor()``: progress reporting is a
        per-connection setting that the locked configuration refuses on new cursors, and only one Job (and no
        other code) ever uses the connection at a time (T6)."""
        if self._connection is None:
            raise RuntimeError("this Job has no database connection")
        self._job._register_cursor(self._connection)
        return self._connection


class Job:
    def __init__(self, operation: str, work: Callable[[JobContext], Any], *, cancellable: bool = True):
        self.id = uuid.uuid4().hex
        self.operation = operation
        self.cancellable = cancellable
        self._work = work
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._finished = threading.Event()
        self._state = JobState.RUNNING
        self._stage = ""
        self._rows_done: int | None = None
        self._rows_total: int | None = None
        self._started = time.monotonic()
        self._ended: float | None = None
        self._cursors: list = []
        self._cancel_callbacks: list[Callable[[], None]] = []
        self._abort_callbacks: list[Callable[[], None]] = []
        self.result: Any = None
        self.error: BaseException | None = None

    # ---- the interface the window uses
    @property
    def state(self) -> JobState:
        return self._state

    def cancel(self) -> bool:
        """Ask the Job to stop. Returns False when the Job can't be cancelled now or has already finished."""
        with self._lock:
            if not self.cancellable or self._state.finished:
                return False
            if self._state is JobState.RUNNING:
                self._state = JobState.CANCELLING
            self._cancel.set()
            cursors = list(self._cursors)
            callbacks = list(self._cancel_callbacks)
        for cur in cursors:
            try:
                cur.interrupt()
            except Exception:
                pass
        # An interrupt only stops a query that is already running. Keep interrupting until the Job ends, so a
        # query started just after cancel() is stopped too.
        threading.Thread(target=self._keep_interrupting, name=f"cancel-{self.operation}", daemon=True).start()
        for cb in callbacks:
            try:
                cb()
            except Exception:
                pass
        return True

    def progress(self) -> Progress:
        with self._lock:
            done, total = self._rows_done, self._rows_total
            cursors = list(self._cursors)
            fraction = (done / total) if (done is not None and total) else None
        if fraction is None:
            for cur in cursors:
                try:
                    pct = cur.query_progress()
                except Exception:
                    continue
                if pct is not None and pct >= 0:
                    fraction = pct / 100.0
                    break
        end = self._ended if self._ended is not None else time.monotonic()
        return Progress(self._state, self._stage, done, total,
                        None if fraction is None else max(0.0, min(1.0, fraction)), end - self._started,
                        self.cancellable and not self._state.finished,
                        type(self.error).__name__ if self.error is not None else None)

    def wait(self, timeout: float | None = None) -> bool:
        return self._finished.wait(timeout)

    # ---- internals
    def _keep_interrupting(self) -> None:
        # Interrupt under the lock: the final state is set under the same lock and the runner starts no new Job
        # before that, so this never interrupts the next Job's query on the shared connection.
        while not self._finished.wait(INTERRUPT_REPEAT_S):
            with self._lock:
                if self._state.finished:
                    return
                for cur in self._cursors:
                    try:
                        cur.interrupt()
                    except Exception:
                        pass

    def _register_cursor(self, cur) -> None:
        with self._lock:
            if not any(c is cur for c in self._cursors):
                self._cursors.append(cur)
            cancelled = self._cancel.is_set()
        if cancelled:
            cur.interrupt()

    def _add_cancel_callback(self, cb) -> None:
        with self._lock:
            self._cancel_callbacks.append(cb)
            pending = self._cancel.is_set()
        if pending:
            cb()

    def _run(self, ctx: JobContext) -> None:
        try:
            self.result = self._work(ctx)
            final = JobState.DONE
        except BaseException as e:   # noqa: BLE001 - every failure ends the Job, never the app
            interrupted = self._cancel.is_set() and (isinstance(e, Cancelled) or _is_interrupt(e))
            final = JobState.CANCELLED if interrupted else JobState.FAILED
            if final is JobState.FAILED:
                self.error = e
            for cb in self._abort_callbacks:
                try:
                    cb()
                except Exception:
                    pass
        finally:
            with self._lock:
                self._cursors = []      # the shared connection stays open
        self._ended = time.monotonic()
        with self._lock:
            self._state = final


def _is_interrupt(e: BaseException) -> bool:
    try:
        import duckdb
    except ImportError:
        return False
    return isinstance(e, duckdb.InterruptException)
