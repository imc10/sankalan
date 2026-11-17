r"""``Sankalan.exe --remove-data``: run by the uninstaller when the user answers Yes to deleting the data (T26,
DEP-12; decision confirmed 17-11-2026).

Deletes the data folder that settings.json names (wherever it was moved to), then %LOCALAPPDATA%\Sankalan
(settings.json, logs, the default Data folder) and %TEMP%\Sankalan. The uninstaller only calls this after checking
Sankalan isn't running.

A data folder is deleted only when it holds ``catalogue.duckdb`` and is not a drive root, so a damaged or edited
settings.json can never make the uninstaller delete some other folder. Exit codes: 0 everything gone, 1 something
could not be deleted (a file held open), 2 the data folder was left because it didn't look like Sankalan's.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from sankalan import paths as app_paths
from sankalan.db.datafolder import CATALOGUE

DONE, PARTLY, NOT_OURS = 0, 1, 2


def is_data_folder(folder: Path) -> bool:
    folder = Path(folder)
    if not folder.is_dir() or folder.resolve().parent == folder.resolve():      # a drive root
        return False
    return (folder / CATALOGUE).is_file()


def _rmtree(folder: Path) -> bool:
    """Delete ``folder``; True when it no longer exists. Read-only files are made writable first."""
    if not folder.exists():
        return True

    def retry(func, path, _exc):
        try:
            os.chmod(path, 0o666)
            func(path)
        except OSError:
            pass
    shutil.rmtree(folder, onexc=retry)
    return not folder.exists()


def remove_data(paths: app_paths.AppPaths | None = None) -> int:
    paths = paths or app_paths.AppPaths.from_environment()
    data = Path(app_paths.load_settings(paths)["data_folder"])
    code = DONE
    if not app_paths.is_inside(data, paths.root):
        if is_data_folder(data):
            if not _rmtree(data):
                code = PARTLY
        elif data.exists():
            code = NOT_OURS
    for folder in (paths.root, paths.temp):
        if not _rmtree(folder) and code == DONE:
            code = PARTLY
    return code
