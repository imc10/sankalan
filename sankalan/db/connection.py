"""The one app-wide DuckDB connection (T5, T7, SEC-1).

Settings: memory_limit = 50% of RAM, threads = logical cores, temp_directory = %TEMP%\\Sankalan. Extensions are
never installed or loaded, and the configuration is locked. Phase 0 spike S1 showed that a locked configuration
alone still lets DuckDB download an extension when explicitly told to, so external access is also switched off,
with only the data folder and the temp folder allowed (decision confirmed 16-11-2026). DuckDB can therefore read
and write files only inside those two folders; moving the data folder closes this connection and opens a new one.

This module is used only by db/ and by Jobs. Never on the UI thread.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb

MEMORY_SHARE = 0.5
SETTINGS_CHECKED = ("memory_limit", "threads", "temp_directory", "lock_configuration", "enable_external_access",
                    "autoinstall_known_extensions", "autoload_known_extensions", "allow_community_extensions",
                    "allow_unsigned_extensions")


def total_ram_bytes() -> int:
    if sys.platform == "win32":
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.ullTotalPhys)
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return 8 * 1024 ** 3


def memory_limit_text(ram_bytes: int | None = None) -> str:
    """50% of RAM, in whole MiB (T7). DuckDB reads 'MB' as 10^6 bytes, so MiB is used."""
    ram = total_ram_bytes() if ram_bytes is None else ram_bytes
    return f"{max(256, int(ram * MEMORY_SHARE) // (1024 * 1024))}MiB"


def _sql_path(p: Path) -> str:
    """A folder as DuckDB wants it in allowed_directories: forward slashes and a trailing slash."""
    return Path(os.path.abspath(p)).as_posix().rstrip("/") + "/"


def _quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def open_connection(catalogue: Path, data_folder: Path, temp_folder: Path, *,
                    memory_limit: str | None = None, threads: int | None = None) -> duckdb.DuckDBPyConnection:
    """Open the catalogue with the hardened, locked configuration. ``temp_folder`` is created if missing."""
    temp_folder.mkdir(parents=True, exist_ok=True)
    no_ext = temp_folder / "no-extensions"          # an empty folder: nothing cached can ever be loaded from it
    no_ext.mkdir(exist_ok=True)
    con = duckdb.connect(str(catalogue), config={
        "autoinstall_known_extensions": False,
        "autoload_known_extensions": False,
        "allow_community_extensions": False,
        "allow_unsigned_extensions": False,
        "extension_directory": str(no_ext),
        "custom_extension_repository": str(temp_folder / "no-repository"),   # local and missing
    })
    try:
        con.execute(f"SET memory_limit = {_quote(memory_limit or memory_limit_text())}")
        con.execute(f"SET threads = {int(threads or os.cpu_count() or 1)}")
        con.execute(f"SET temp_directory = {_quote(Path(os.path.abspath(temp_folder)).as_posix())}")
        con.execute("SET enable_progress_bar = true")          # query_progress() for the 250 ms progress poll
        con.execute("SET enable_progress_bar_print = false")
        con.execute("SET progress_bar_time = 0")                # progress from the start, not after 2 s
        allowed = ", ".join(_quote(_sql_path(p)) for p in (data_folder, temp_folder))
        con.execute(f"SET allowed_directories = [{allowed}]")
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")
    except BaseException:
        con.close()
        raise
    return con


def settings(con: duckdb.DuckDBPyConnection) -> dict:
    """The safety-relevant settings, for the self-test and tests."""
    names = ", ".join(_quote(n) for n in SETTINGS_CHECKED)
    return dict(con.execute(f"SELECT name, value FROM duckdb_settings() WHERE name IN ({names})").fetchall())
