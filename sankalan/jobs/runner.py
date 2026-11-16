"""JobRunner: one long Job at a time, app-wide (T6)."""
from __future__ import annotations

import threading
from typing import Any, Callable

from sankalan import log
from sankalan.jobs.job import Job, JobBusy, JobContext, JobState


class JobRunner:
    """Starts Jobs on a background thread, refusing a second while one runs.

    ``connection`` is the app-wide DuckDB connection (Jobs get cursors from it). ``on_job_end`` runs after every
    Job, whatever its outcome; the storage layer uses it to empty %TEMP%\\Sankalan (SEC-4)."""

    def __init__(self, connection=None, on_job_end: Callable[[Job], None] | None = None):
        self.connection = connection
        self.on_job_end = on_job_end
        self._lock = threading.Lock()
        self._current: Job | None = None
        self._thread: threading.Thread | None = None

    @property
    def current(self) -> Job | None:
        return self._current

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._current is not None and not self._current._finished.is_set()

    def start(self, operation: str, work: Callable[[JobContext], Any], *, cancellable: bool = True) -> Job:
        with self._lock:
            if self._current is not None and not self._current._finished.is_set():
                raise JobBusy(self._current.operation)
            job = Job(operation, work, cancellable=cancellable)
            self._current = job
            t = threading.Thread(target=self._run, args=(job,), name=f"job-{operation}", daemon=True)
            self._thread = t
        log.info(f"{operation} started")
        t.start()
        return job

    def run(self, operation: str, work: Callable[[JobContext], Any], *, cancellable: bool = True) -> Job:
        """Start a Job and wait for it (headless use and tests)."""
        job = self.start(operation, work, cancellable=cancellable)
        job.wait()
        return job

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for the current Job, e.g. when closing during a commit."""
        job = self._current
        return True if job is None else job.wait(timeout)

    def _run(self, job: Job) -> None:
        try:
            job._run(JobContext(job, self.connection))
        finally:
            try:
                if self.on_job_end is not None:
                    self.on_job_end(job)
            except Exception as e:      # noqa: BLE001
                log.failed(f"{job.operation} clean-up", e)
            if job.state is JobState.FAILED:
                log.failed(job.operation, job.error)
            else:
                log.info(f"{job.operation} {job.state.value}")
            job._finished.set()
