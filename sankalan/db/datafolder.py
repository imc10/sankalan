"""The data folder: layout, staging, commit and delete protocols, start-up recovery, and moving the folder
(T8, T9, T22, T25, RUN-5, RUN-9, SEC-4, UX-11, ENV-5).

    <data folder>\\
      catalogue.duckdb
      catalogue-backups\\           last 5 copies, taken at app start (T10)
      _staging\\<run-id>\\           the run in progress (raw\\, data.parquet, left_out.parquet, issues.parquet, outputs\\)
      t\\<template-id>\\runs\\<run-id>\\   the same files after commit, raw\\ removed

Folders are named by internal ID, so renaming a client or template never moves files. The staging folder's ID
becomes the run's internal ID, so the commit is a rename plus one catalogue transaction.

Staging lives for the whole new-run wizard: it is removed when the run is committed (renamed), discarded or left,
when the load Job is cancelled or fails, and at start-up (decision confirmed 16-11-2026).
"""
from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from sankalan import paths as app_paths
from sankalan.model.run import NewRun
from sankalan.query import catalogue as q

CATALOGUE = "catalogue.duckdb"
BACKUPS = "catalogue-backups"
STAGING = "_staging"
TEMPLATES = "t"
RAW = "raw"
REQUIRED_RUN_FILES = ("data.parquet",)


class DataFolder:
    def __init__(self, path: Path):
        self.path = Path(path)

    @property
    def catalogue(self) -> Path:
        return self.path / CATALOGUE

    @property
    def backups(self) -> Path:
        return self.path / BACKUPS

    @property
    def staging_root(self) -> Path:
        return self.path / STAGING

    @property
    def templates_root(self) -> Path:
        return self.path / TEMPLATES

    def template_dir(self, template_id: str) -> Path:
        return self.templates_root / template_id

    def run_dir(self, template_id: str, run_id: str) -> Path:
        return self.templates_root / template_id / "runs" / run_id

    def ensure(self) -> None:
        for p in (self.path, self.backups, self.staging_root, self.templates_root):
            p.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------------------------------ staging (T9)
    def new_staging(self) -> "Staging":
        sid = uuid.uuid4().hex
        st = Staging(sid, self.staging_root / sid)
        (st.path / RAW).mkdir(parents=True)
        return st

    def discard_staging(self, staging: "Staging") -> None:
        shutil.rmtree(staging.path, ignore_errors=True)

    def empty_staging(self) -> None:
        app_paths.empty_folder(self.staging_root)

    # ------------------------------------------------------------------------------------------ disk figures
    def size_bytes(self) -> int:
        total = 0
        for root, _dirs, files in os.walk(self.path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total

    def free_bytes(self) -> int:
        return shutil.disk_usage(self.path).free


@dataclass
class Staging:
    id: str             # becomes the run's internal ID on commit
    path: Path

    @property
    def raw(self) -> Path:
        return self.path / RAW


# ---------------------------------------------------------------------------------------------- commit (RUN-5, T8)
COMMIT_STEPS = ("flushed", "renamed", "recorded")


class CommitError(Exception):
    pass


def _fsync_tree(folder: Path) -> None:
    for root, _dirs, files in os.walk(folder):
        for name in files:
            with open(os.path.join(root, name), "rb+") as fh:
                os.fsync(fh.fileno())


def commit(con, folder: DataFolder, staging: Staging, run: NewRun,
           on_step: Callable[[str], None] | None = None,
           in_transaction: Callable[[object], None] | None = None) -> int:
    """Commit a staged run. Returns the Run ID number issued.

    1. Flush every staged file to disk and delete raw\\.
    2. Rename _staging\\<id>\\ to t\\<template-id>\\runs\\<id>\\ (all-or-nothing on one drive).
    3. One catalogue transaction: issue the Run ID and insert run, run_file, run_issue_count, run_output.
       This is the commit point.

    A crash before step 3 completes leaves no catalogue row, and start-up recovery removes the folder. If step 3
    fails without a crash, the folder is moved back to staging so the run can be committed again.
    ``on_step(name)`` is called after each step (progress; tests use it to crash at each point).
    ``in_transaction(con)`` runs inside the catalogue transaction before the run is inserted: the run pipeline saves
    aliases learned and columns added in the run there, so they commit together with the run (RUN-5)."""
    step = on_step or (lambda _name: None)
    for name in REQUIRED_RUN_FILES:
        if not (staging.path / name).is_file():
            raise CommitError(f"missing {name}")
    if staging.raw.exists():
        shutil.rmtree(staging.raw)
    _fsync_tree(staging.path)
    step("flushed")

    target = folder.run_dir(run.template_id, staging.id)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.rename(staging.path, target)
    step("renamed")

    try:
        with q.Transaction(con):
            if in_transaction is not None:
                in_transaction(con)
            number = q.insert_run(con, staging.id, run)
    except BaseException:
        try:
            os.rename(target, staging.path)
        except OSError:
            pass            # start-up recovery deletes the orphan folder
        raise
    step("recorded")
    return number


# ---------------------------------------------------------------------------------------------- delete (RUN-9, TPL-2, TPL-4)
def delete_run(con, folder: DataFolder, run_id: str) -> bool:
    """Catalogue records first (one transaction), then the folder. A folder that can't be deleted now is
    removed by start-up recovery. The Run ID is not freed (T22)."""
    with q.Transaction(con):
        template_id = q.delete_run_records(con, run_id)
    if template_id is None:
        return False
    shutil.rmtree(folder.run_dir(template_id, run_id), ignore_errors=True)
    return True


def delete_template(con, folder: DataFolder, template_id: str) -> None:
    with q.Transaction(con):
        q.delete_template_records(con, template_id)
    shutil.rmtree(folder.template_dir(template_id), ignore_errors=True)


def delete_client(con, folder: DataFolder, client_id: str) -> None:
    with q.Transaction(con):
        tids = q.delete_client_records(con, client_id)
    for tid in tids:
        shutil.rmtree(folder.template_dir(tid), ignore_errors=True)


# ---------------------------------------------------------------------------------------------- start-up recovery
@dataclass
class RecoveryReport:
    staging_removed: list[str] = field(default_factory=list)
    orphan_folders_removed: list[str] = field(default_factory=list)
    damaged: list[str] = field(default_factory=list)
    repaired: list[str] = field(default_factory=list)


def recover(con, folder: DataFolder) -> RecoveryReport:
    """Empty _staging; delete run and template folders with no catalogue record; mark catalogue runs whose folder
    is missing as damaged (and clear the mark when the folder is back)."""
    report = RecoveryReport()
    if folder.staging_root.is_dir():
        report.staging_removed = sorted(p.name for p in folder.staging_root.iterdir())
    folder.empty_staging()

    known = q.run_locations(con)
    known_runs = {(t, r) for t, r in known}
    known_templates = set(q.template_ids(con)) | {t for t, _ in known}
    if folder.templates_root.is_dir():
        for tdir in folder.templates_root.iterdir():
            if not tdir.is_dir():
                continue
            if tdir.name not in known_templates:
                shutil.rmtree(tdir, ignore_errors=True)
                report.orphan_folders_removed.append(f"{TEMPLATES}/{tdir.name}")
                continue
            runs = tdir / "runs"
            if runs.is_dir():
                for rdir in runs.iterdir():
                    if (tdir.name, rdir.name) not in known_runs:
                        shutil.rmtree(rdir, ignore_errors=True)
                        report.orphan_folders_removed.append(f"{TEMPLATES}/{tdir.name}/runs/{rdir.name}")

    damaged_now = {r.id for r in q.list_runs(con) if r.damaged}
    missing = [r for t, r in known if not folder.run_dir(t, r).is_dir()]
    back = [r for r in damaged_now if r not in set(missing)]
    if missing or back:
        with q.Transaction(con):
            q.set_damaged(con, missing, True)
            q.set_damaged(con, back, False)
    report.damaged = sorted(missing)
    report.repaired = sorted(back)
    return report


# ---------------------------------------------------------------------------------------------- moving (UX-11, T25)
NETWORK_REFUSAL = "Network folders can't be used for Sankalan data. Choose a folder on this laptop."
NOT_EMPTY_REFUSAL = "Choose an empty folder. This folder already contains files."
INSIDE_REFUSAL = "Choose a folder outside the current data folder."
SAME_REFUSAL = "This is already the data folder."
SPACE_REFUSAL = "There isn't enough free space on that drive to hold the data."
ONEDRIVE_WARNING = ("This folder is synced by OneDrive. Syncing can conflict with Sankalan's files and damage them. "
                    "Use a folder that isn't synced if you can.")


@dataclass
class DestinationCheck:
    refusal: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.refusal is None


def check_destination(current: Path, dest: Path, needed_bytes: int | None = None) -> DestinationCheck:
    """Refuse network paths (ENV-5), non-empty folders, the current folder or one inside it, and too little free
    space; warn for OneDrive (T25). ``dest`` itself is the new data folder."""
    if app_paths.is_network_path(dest):
        return DestinationCheck(NETWORK_REFUSAL)
    dest = Path(os.path.abspath(dest))
    if os.path.normcase(str(dest)) == os.path.normcase(os.path.abspath(current)):
        return DestinationCheck(SAME_REFUSAL)
    if app_paths.is_inside(dest, current) or app_paths.is_inside(current, dest):
        return DestinationCheck(INSIDE_REFUSAL)
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        return DestinationCheck(NOT_EMPTY_REFUSAL)
    if needed_bytes is not None:
        probe = dest
        while not probe.exists() and probe.parent != probe:
            probe = probe.parent
        try:
            if shutil.disk_usage(probe).free < needed_bytes:
                return DestinationCheck(SPACE_REFUSAL)
        except OSError:
            return DestinationCheck(NETWORK_REFUSAL if not probe.exists() else SPACE_REFUSAL)
    warnings = [ONEDRIVE_WARNING] if app_paths.is_onedrive_path(dest) else []
    return DestinationCheck(None, warnings)


def _files(root: Path) -> list[Path]:
    """Every file under root, relative, skipping _staging (it is empty between Jobs anyway)."""
    out = []
    for dirpath, dirs, files in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        if rel.parts[:1] == (STAGING,):
            dirs[:] = []
            continue
        out.extend(rel / f for f in files)
    return sorted(out)


def copy_tree(src: Path, dest: Path, on_bytes: Callable[[int, int], None] | None = None,
              check_cancelled: Callable[[], None] | None = None, chunk: int = 8 * 1024 * 1024) -> list[Path]:
    """Copy the data folder's files (not _staging) to dest, reporting bytes done of total. Returns the files."""
    files = _files(src)
    total = sum((src / f).stat().st_size for f in files)
    done = 0
    dest.mkdir(parents=True, exist_ok=True)
    (dest / STAGING).mkdir(exist_ok=True)
    for f in files:
        if check_cancelled:
            check_cancelled()
        target = dest / f
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(src / f, "rb") as fi, open(target, "wb") as fo:
            while True:
                if check_cancelled:
                    check_cancelled()
                buf = fi.read(chunk)
                if not buf:
                    break
                fo.write(buf)
                done += len(buf)
                if on_bytes:
                    on_bytes(done, total)
            fo.flush()
            os.fsync(fo.fileno())
        shutil.copystat(src / f, target)
    return files


def verify_copy(src: Path, dest: Path, files: list[Path]) -> bool:
    """Same file list and the same size for every file."""
    if _files(dest) != files:
        return False
    return all((src / f).stat().st_size == (dest / f).stat().st_size for f in files)
