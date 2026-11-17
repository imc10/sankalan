"""The app log (SEC-5): operation, file name and error class only.

Never pass cell values, DuckDB error text or exception messages to this log. ``failed()`` takes the exception only
to record its class name.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

log = logging.getLogger("sankalan")
MAX_BYTES = 1_000_000
BACKUPS = 5


def setup(logs_folder: Path) -> None:
    """Send the log to <logs>\\sankalan.log, rotated at 1 MB, 5 old files kept. Safe to call more than once."""
    logs_folder.mkdir(parents=True, exist_ok=True)
    target = str(logs_folder / "sankalan.log")
    for h in list(log.handlers):
        if isinstance(h, RotatingFileHandler):
            if h.baseFilename == os.path.abspath(target):
                return
            log.removeHandler(h)
            h.close()
    h = RotatingFileHandler(target, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(h)
    log.setLevel(logging.INFO)
    log.propagate = False


def info(operation: str, file_name: str | None = None) -> None:
    log.info("%s%s", operation, f" [{file_name}]" if file_name else "")


def failed(operation: str, error: BaseException, file_name: str | None = None) -> None:
    """Record a failure by its error class only (SEC-5)."""
    log.error("%s failed: %s%s", operation, type(error).__name__, f" [{file_name}]" if file_name else "")


def close_handlers_under(folder: Path) -> None:
    """Close and remove log files inside ``folder`` (the self-test's temporary folder) so it can be deleted."""
    root = os.path.normcase(os.path.abspath(folder))
    for h in list(log.handlers):
        if isinstance(h, RotatingFileHandler) and os.path.normcase(h.baseFilename).startswith(root):
            log.removeHandler(h)
            h.close()
