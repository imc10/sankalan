"""Opening source files: read-only (SEC-2), sharing violations, file type from content (IN-3, IN-9, IN-15).

Source files are only ever opened for reading. On Windows the probe opens each file with GENERIC_READ and a share
mode that refuses other writers: if another program (Excel, typically) has the file open for writing, that open
fails with a sharing violation, which becomes "<file> is open in another program. Close it, then Re-check"
(RUNF-06, decision confirmed 16-11-2026).
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

CHUNK = 1024 * 1024

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06")
ENCRYPTION_INFO = "EncryptionInfo".encode("utf-16-le")

KIND_EXCEL, KIND_CSV = "excel", "csv"

_SHARING_ERRORS = {32, 33}          # ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION


class FileProblem(Exception):
    """A file can't be read. ``message`` is the plain text for the file list (UI-6, IN-15); ``kind`` is a short code
    for tests and the log (never a cell value, SEC-5)."""

    def __init__(self, kind: str, message: str):
        super().__init__(kind)
        self.kind = kind
        self.message = message


def locked_message(name: str) -> str:
    return f"{name} is open in another program. Close it, then Re-check."


def is_sharing_violation(e: BaseException) -> bool:
    return isinstance(e, OSError) and getattr(e, "winerror", None) in _SHARING_ERRORS


def _open_deny_write(path: Path):
    """Windows: open for reading while refusing other writers, so a file another program is writing (or holding
    open for writing, as Excel does) fails with a sharing violation."""
    import ctypes
    import msvcrt
    from ctypes import wintypes

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID = wintypes.HANDLE(-1).value

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
    h = k32.CreateFileW(str(path), GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if h == INVALID or h is None:
        err = ctypes.get_last_error()
        raise OSError(None, ctypes.FormatError(err).strip(), str(path), err)
    fd = msvcrt.open_osfhandle(h, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    return os.fdopen(fd, "rb")


def open_source(path: Path):
    """Open a source file read-only (SEC-2), mapping failures to ``FileProblem``."""
    name = Path(path).name
    try:
        if sys.platform == "win32":
            return _open_deny_write(Path(path))
        return open(path, "rb")
    except FileNotFoundError:
        raise FileProblem("missing", f"{name} was not found. It may have been moved or deleted.") from None
    except OSError as e:
        if is_sharing_violation(e):
            raise FileProblem("locked", locked_message(name)) from None
        if getattr(e, "winerror", None) in (2, 3):
            raise FileProblem("missing", f"{name} was not found. It may have been moved or deleted.") from None
        raise FileProblem("unreadable", f"{name} can't be opened.") from None


def sniff(head: bytes) -> str:
    """'zip', 'ole' or 'text' from the first bytes."""
    if head.startswith(ZIP_MAGIC):
        return "zip"
    if head.startswith(OLE_MAGIC):
        return "ole"
    return "text"


def ole_is_encrypted(fh) -> bool:
    """An encrypted Office file is an OLE container holding an EncryptionInfo stream (IN-9)."""
    fh.seek(0)
    tail = b""
    while True:
        chunk = fh.read(CHUNK)
        if not chunk:
            return False
        if ENCRYPTION_INFO in tail + chunk:
            return True
        tail = chunk[-len(ENCRYPTION_INFO):]


def sha256_of(fh, extra=None) -> str:
    """SHA-256 of the whole file from the start (RUN-7). ``extra(chunk)`` sees every chunk too (CSV line count and
    UTF-8 check in the same pass)."""
    fh.seek(0)
    h = hashlib.sha256()
    while True:
        chunk = fh.read(CHUNK)
        if not chunk:
            break
        h.update(chunk)
        if extra is not None:
            extra(chunk)
    return h.hexdigest()
