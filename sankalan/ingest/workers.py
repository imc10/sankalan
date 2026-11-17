"""Reader workers: separate processes started with spawn (T5).

As many workers as the smaller of task count and CPU cores − 1 run at once. Each task is one call of a module-level
function ``fn(*args, report=, stop=)`` in a worker; ``report(n)`` sends rows-read progress back and ``stop()`` says
whether to stop. Workers never open the database.

Cancel (Tech spec, Architecture → Cancel): the workers are signalled to stop, then killed after 2 seconds. The
caller deletes their partial files.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import queue
import time
from dataclasses import dataclass
from typing import Any, Callable

from sankalan.jobs import Cancelled

KILL_AFTER_S = 2.0
POLL_S = 0.05
DEAD_GRACE_S = 1.0


@dataclass
class TaskFailed:
    """A task that raised. ``kind`` is the error class or a FileProblem code; ``message`` is plain text for the
    file list when there is one (never a cell value, SEC-5)."""
    kind: str
    message: str = ""


def worker_count(tasks: int) -> int:
    return max(1, min(tasks, (os.cpu_count() or 2) - 1))


def _failure(e: BaseException) -> TaskFailed:
    from sankalan.ingest.source import FileProblem, is_sharing_violation, locked_message
    if isinstance(e, FileProblem):
        return TaskFailed(e.kind, e.message)
    if is_sharing_violation(e):
        name = os.path.basename(getattr(e, "filename", "") or "")
        return TaskFailed("locked", locked_message(name) if name else "")
    return TaskFailed(type(e).__name__)


def _child(fn, idx: int, args: tuple, q, stop_ev) -> None:
    def report(n: int) -> None:
        q.put(("rows", idx, n))
    try:
        res = fn(*args, report=report, stop=stop_ev.is_set)
        q.put(("done", idx, res))
    except BaseException as e:      # noqa: BLE001 - every failure goes back to the Job
        q.put(("failed", idx, _failure(e)))


def run_tasks(fn: Callable, tasks: list[tuple], *, workers: int | None = None,
              on_rows: Callable[[int], None] | None = None, should_stop: Callable[[], bool] | None = None,
              kill_after: float = KILL_AFTER_S) -> list[Any]:
    """Run ``fn(*task)`` for every task; results in task order (a ``TaskFailed`` for a task that raised).
    ``workers=0`` runs the tasks one by one in this process (small jobs and tests). Raises ``Cancelled`` when
    ``should_stop()`` turns true; by then every worker has stopped or been killed."""
    stop = should_stop or (lambda: False)
    if workers == 0:
        return _run_inline(fn, tasks, on_rows, stop)
    n_workers = worker_count(len(tasks)) if workers is None else max(1, min(workers, len(tasks)))
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    stop_ev = ctx.Event()
    results: list[Any] = [None] * len(tasks)
    finished: set[int] = set()
    pending = list(range(len(tasks)))
    running: dict[int, Any] = {}
    dead_since: dict[int, float] = {}
    try:
        while pending or running:
            if stop():
                raise Cancelled()
            while pending and len(running) < n_workers:
                idx = pending.pop(0)
                p = ctx.Process(target=_child, args=(fn, idx, tasks[idx], q, stop_ev), daemon=True,
                                name=f"sankalan-reader-{idx}")
                p.start()
                running[idx] = p
            try:
                msg = q.get(timeout=POLL_S)
            except queue.Empty:
                now = time.monotonic()
                for idx, p in list(running.items()):
                    if p.exitcode is not None and idx not in finished:
                        since = dead_since.setdefault(idx, now)
                        if now - since > DEAD_GRACE_S:      # exited without a result: crashed or killed
                            results[idx] = TaskFailed("WorkerDied")
                            finished.add(idx)
                            running.pop(idx).join(0)
                continue
            kind, idx = msg[0], msg[1]
            if kind == "rows":
                if on_rows is not None:
                    on_rows(msg[2])
                continue
            results[idx] = msg[2]
            finished.add(idx)
            p = running.pop(idx, None)
            if p is not None:
                p.join(kill_after)
                if p.is_alive():
                    p.kill()
                    p.join()
        return results
    finally:
        if running:
            stop_ev.set()
            deadline = time.monotonic() + kill_after
            for p in running.values():
                p.join(max(0.0, deadline - time.monotonic()))
            for p in running.values():
                if p.is_alive():
                    p.kill()
                    p.join()
        q.close()
        q.cancel_join_thread()


def _run_inline(fn, tasks, on_rows, stop) -> list[Any]:
    out = []
    for t in tasks:
        if stop():
            raise Cancelled()
        try:
            out.append(fn(*t, report=on_rows or (lambda n: None), stop=stop))
        except Cancelled:
            raise
        except Exception as e:      # noqa: BLE001
            out.append(_failure(e))
    if stop():
        raise Cancelled()
    return out
