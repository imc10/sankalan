"""Jobs: every long operation runs as one Job on a background thread, one at a time app-wide (T5, T6, UI-5).

A Job reports its state, stage, rows done of total and elapsed time, and has ``cancel()``. Every progress panel and
dialog talks only to this interface: the window polls ``Job.progress()`` every ``POLL_INTERVAL_MS``.

The work itself is a function ``work(ctx: JobContext)``. It reports progress through ``ctx``, calls
``ctx.check_cancelled()`` between steps, and gets DuckDB cursors from ``ctx.cursor()`` so that ``cancel()`` can
interrupt them.
"""
from sankalan.jobs.job import (POLL_INTERVAL_MS, Cancelled, Job, JobBusy, JobContext, JobState, Progress)
from sankalan.jobs.runner import JobRunner

__all__ = ["POLL_INTERVAL_MS", "Cancelled", "Job", "JobBusy", "JobContext", "JobRunner", "JobState", "Progress"]
