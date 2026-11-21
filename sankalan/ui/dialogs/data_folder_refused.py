"""Start-up on a data folder made by a test build (Tech spec A2 T40, 12.2; decision D77).

The catalogue of a version-1 data folder is refused before anything in the folder is touched (no backup, no
change). The user is told so and picks what to open instead:

- **Choose folder…**: an empty folder, or another Sankalan data folder (one that holds ``catalogue.duckdb``);
- **Create new folder…**: a new folder ``Sankalan Data`` inside the folder picked;
- **Close**: the app closes and nothing changes.

The checks are those of Change… in App settings (network folders refused, the refused folder or one inside or
around it refused, OneDrive warned, T25); in addition Choose folder… accepts an existing data folder. Choosing
writes ``settings.json``; the app then opens the folder on the background thread as at every start (a folder
refused again comes back here). No DuckDB on the UI thread: the version of a chosen data folder is read when it
opens.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QFileDialog

from sankalan import APP_NAME
from sankalan import paths as app_paths
from sankalan.db import datafolder
from sankalan.ui.dialogs.base import ask

MESSAGE = ("This data folder was made by a test build of Sankalan and can't be opened by this version. Choose "
           "another folder, or create a new one.")
SAME_REFUSAL = "Choose a folder other than the one that can't be opened."
NEW_FOLDER_NAME = "Sankalan Data"
CHOOSE, CREATE, CLOSE = "choose", "create", "close"


def choose_folder(parent, start: str, title: str) -> str | None:
    path = QFileDialog.getExistingDirectory(parent, title, start)
    return path or None


CHOOSER: Callable[[object, str, str], str | None] = choose_folder        # tests replace it


def is_data_folder(path: Path) -> bool:
    return (Path(path) / datafolder.CATALOGUE).is_file()


def new_folder_in(parent: Path) -> Path:
    """``<parent>\\Sankalan Data``, or ``Sankalan Data 2``, … when that one exists and isn't empty."""
    n = 1
    while True:
        dest = Path(parent) / (NEW_FOLDER_NAME if n == 1 else f"{NEW_FOLDER_NAME} {n}")
        if not dest.exists() or (dest.is_dir() and not any(dest.iterdir())):
            return dest
        n += 1


def check(refused: Path, dest: Path) -> datafolder.DestinationCheck:
    """Change…'s checks (T25), except that an existing data folder is accepted (it opens as it is)."""
    if app_paths.is_network_path(dest):
        return datafolder.DestinationCheck(datafolder.NETWORK_REFUSAL)
    dest = Path(os.path.abspath(dest))
    if app_paths.is_inside(dest, refused) or app_paths.is_inside(refused, dest):
        return datafolder.DestinationCheck(SAME_REFUSAL)
    if dest.exists() and not is_data_folder(dest) and (not dest.is_dir() or any(dest.iterdir())):
        return datafolder.DestinationCheck(datafolder.NOT_EMPTY_REFUSAL)
    warnings = [datafolder.ONEDRIVE_WARNING] if app_paths.is_onedrive_path(dest) else []
    return datafolder.DestinationCheck(None, warnings)


def ask_for_folder(parent, paths: app_paths.AppPaths, refused: Path) -> Path | None:
    """Show the message until the user picks a folder that passes the checks (saved to ``settings.json``), or
    closes (None; nothing changed)."""
    text = MESSAGE
    while True:
        key = ask(parent, APP_NAME, text, [(CLOSE, "Close", None), (CREATE, "Create new folder…", None),
                                          (CHOOSE, "Choose folder…", "primary")], width=520)
        if key not in (CHOOSE, CREATE):
            return None
        start = str(Path(refused).parent)
        if key == CHOOSE:
            picked = CHOOSER(parent, start, "Choose an empty folder, or another Sankalan data folder")
            dest = Path(picked) if picked else None
        else:
            picked = CHOOSER(parent, start, "Choose where to create the new data folder")
            dest = new_folder_in(Path(picked)) if picked else None
        if dest is None:
            text = MESSAGE
            continue
        result = check(refused, dest)
        if not result.ok:
            text = f"{result.refusal}\n\n{MESSAGE}"
            continue
        if result.warnings:
            answer = ask(parent, "Use a synced folder?", "\n\n".join(result.warnings),
                         [("cancel", "Cancel", None), ("use", "Use anyway", "primary")])
            if answer != "use":
                text = MESSAGE
                continue
        dest.mkdir(parents=True, exist_ok=True)
        settings = app_paths.load_settings(paths)
        settings["data_folder"] = str(Path(os.path.abspath(dest)))
        app_paths.save_settings(paths, settings)
        return dest
