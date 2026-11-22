"""Where Sankalan keeps things (T25, SEC-4, UX-11, ENV-5).

    %LOCALAPPDATA%\\Sankalan\\settings.json     {"data_folder": "<path>"}
    %LOCALAPPDATA%\\Sankalan\\logs\\            rotated log (SEC-5)
    %LOCALAPPDATA%\\Sankalan\\Data\\            default data folder (T25)
    %TEMP%\\Sankalan\\                          DuckDB spill files; emptied at start-up and after every Job

Every path is read from the environment when an ``AppPaths`` is built, so tests point LOCALAPPDATA and TEMP at a
temporary folder.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sankalan import APP_NAME


@dataclass(frozen=True)
class AppPaths:
    root: Path              # %LOCALAPPDATA%\Sankalan
    temp: Path              # %TEMP%\Sankalan

    @classmethod
    def from_environment(cls) -> "AppPaths":
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        tmp = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
        return cls(Path(local) / APP_NAME, Path(tmp) / APP_NAME)

    @property
    def settings_file(self) -> Path:
        return self.root / "settings.json"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def default_data_folder(self) -> Path:
        return self.root / "Data"


# ---------------------------------------------------------------------------------------------- settings.json
def load_settings(paths: AppPaths) -> dict:
    """Settings as a dict; a missing or unreadable file gives the defaults."""
    try:
        data = json.loads(paths.settings_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data.setdefault("data_folder", str(paths.default_data_folder))
    return data


def save_settings(paths: AppPaths, settings: dict) -> None:
    """Write settings.json atomically (write a sibling file, then replace)."""
    paths.root.mkdir(parents=True, exist_ok=True)
    tmp = paths.settings_file.with_name("settings.json.new")
    tmp.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, paths.settings_file)


def data_folder(paths: AppPaths) -> Path:
    return Path(load_settings(paths)["data_folder"])


# ---------------------------------------------------------------------------------------------- temp folder
def empty_folder(folder: Path, keep: Callable[[str], bool] | None = None) -> None:
    """Delete everything inside ``folder`` (the folder itself stays), except entries whose name ``keep`` accepts.
    Files still held open are skipped; they go at the next clean-up."""
    if not folder.is_dir():
        return
    for child in folder.iterdir():
        if keep is not None and keep(child.name):
            continue
        try:
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------------------------- folder checks
DRIVE_REMOTE = 4


def _drive_type(drive: str) -> int:
    """GetDriveTypeW for a root such as 'Z:\\'. 0 (unknown) off Windows."""
    if sys.platform != "win32":
        return 0
    import ctypes
    return int(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(drive)))


def is_network_path(path) -> bool:
    """True for UNC paths (\\\\server\\share, \\\\?\\UNC\\…) and for drive letters mapped to a network share (ENV-5)."""
    s = str(path).replace("/", "\\")
    if s.upper().startswith("\\\\?\\UNC\\"):
        return True
    if s.startswith("\\\\?\\") or s.startswith("\\\\.\\"):
        s = s[4:]
    if s.startswith("\\\\"):
        return True
    if len(s) >= 2 and s[1] == ":":
        return _drive_type(s[0].upper() + ":\\") == DRIVE_REMOTE
    return False


def is_onedrive_path(path) -> bool:
    """True when the folder is inside a OneDrive-synced folder (R6): under one of the OneDrive environment folders,
    or with a path part named 'OneDrive' / 'OneDrive - <organisation>'."""
    p = os.path.normcase(os.path.abspath(str(path)))
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        root = os.environ.get(var)
        if root:
            r = os.path.normcase(os.path.abspath(root))
            if p == r or p.startswith(r.rstrip("\\/") + os.sep):
                return True
    return any(part == "onedrive" or part.startswith("onedrive - ") for part in Path(p).parts)


def is_inside(child, parent) -> bool:
    c = os.path.normcase(os.path.abspath(str(child)))
    p = os.path.normcase(os.path.abspath(str(parent))).rstrip("\\/")
    return c == p or c.startswith(p + os.sep)
