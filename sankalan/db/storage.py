"""Storage start-up and shutdown, and the data-folder move Job.

Start-up order (T7, T9, T10, SEC-4):
  settings.json → data folder created → %TEMP%\\Sankalan emptied → log → catalogue backed up (last 5 kept) →
  hardened connection opened → schema created or upgraded → recovery (staging emptied, orphan folders removed,
  missing runs marked damaged) → JobRunner ready.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from sankalan import log
from sankalan import paths as app_paths
from sankalan.db import catalogue, connection, datafolder
from sankalan.db.datafolder import DataFolder, DestinationCheck, RecoveryReport
from sankalan.jobs import Job, JobContext, JobRunner
from sankalan.query import catalogue as q


class MoveRefused(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class MoveFailed(Exception):
    """The copy could not be checked; the data folder is unchanged."""


class Storage:
    def __init__(self, paths: app_paths.AppPaths, *, memory_limit: str | None = None, threads: int | None = None):
        self.paths = paths
        self._memory_limit = memory_limit
        self._threads = threads
        self.folder: DataFolder | None = None
        self.con = None
        self.runner: JobRunner | None = None
        self.recovery: RecoveryReport | None = None

    # ------------------------------------------------------------------------------------------ open / close
    def open(self) -> RecoveryReport:
        settings = app_paths.load_settings(self.paths)
        if not self.paths.settings_file.exists():
            app_paths.save_settings(self.paths, settings)
        self.folder = DataFolder(Path(settings["data_folder"]))
        self.folder.ensure()
        self.paths.temp.mkdir(parents=True, exist_ok=True)
        app_paths.empty_folder(self.paths.temp)
        log.setup(self.paths.logs)
        log.info("start")
        catalogue.backup(self.folder.catalogue, self.folder.backups)
        self.con = self._connect(self.folder)
        catalogue.ensure_schema(self.con)
        self.recovery = datafolder.recover(self.con, self.folder)
        self.runner = JobRunner(self.con, on_job_end=self._job_end)
        return self.recovery

    def _connect(self, folder: DataFolder):
        return connection.open_connection(folder.catalogue, folder.path, self.paths.temp,
                                          memory_limit=self._memory_limit, threads=self._threads)

    def _job_end(self, _job: Job) -> None:
        app_paths.empty_folder(self.paths.temp)            # SEC-4: spill files gone after every Job

    def close(self) -> None:
        if self.runner is not None:
            self.runner.wait()
        if self.con is not None:
            self.con.close()
            self.con = None
        app_paths.empty_folder(self.paths.temp)

    # ------------------------------------------------------------------------------------------ move (UX-11)
    def check_move(self, dest: Path) -> DestinationCheck:
        """For the Change… dialog: a refusal message, or warnings (OneDrive) to confirm before ``move_to``."""
        return datafolder.check_destination(self.folder.path, Path(dest), needed_bytes=self.folder.size_bytes())

    def move_to(self, dest: Path) -> Job:
        """Start the move Job: copy everything, check it, switch settings.json, delete the old folder.
        Cancel works until the copy is checked; after that the move finishes."""
        return self.runner.start("Move data folder", self.move_work(dest))

    def move_work(self, dest: Path):
        """The move as Job work, for the window to start through its Job bridge."""
        dest = Path(os.path.abspath(dest))
        return lambda ctx: self._move(ctx, dest)

    def _move(self, ctx: JobContext, dest: Path) -> Path:
        old = self.folder
        check = datafolder.check_destination(old.path, dest, needed_bytes=old.size_bytes())
        if not check.ok:
            raise MoveRefused(check.refusal)
        created = not dest.exists()
        expected = q.counts(self.con)
        q.checkpoint(self.con)
        self.con.close()
        self.con = None
        new_con = None
        switched = False

        def undo():
            nonlocal new_con, switched
            if switched:
                return
            if new_con is not None:
                new_con.close()
                new_con = None
            if created:
                shutil.rmtree(dest, ignore_errors=True)
            else:
                app_paths.empty_folder(dest)
            if self.con is None:
                self.con = self._connect(old)
                self.runner.connection = self.con

        ctx.on_abort(undo)
        ctx.set_stage("Copying")
        files = datafolder.copy_tree(old.path, dest, on_bytes=lambda d, t: ctx.set_rows(d, t),
                                     check_cancelled=ctx.check_cancelled)
        ctx.set_stage("Checking")
        ctx.check_cancelled()
        new = DataFolder(dest)
        if not datafolder.verify_copy(old.path, dest, files):
            raise MoveFailed()
        new_con = self._connect(new)
        if q.counts(new_con) != expected:
            raise MoveFailed()
        ctx.check_cancelled()

        ctx.set_cancellable(False)
        ctx.set_stage("Switching")
        settings = app_paths.load_settings(self.paths)
        settings["data_folder"] = str(dest)
        app_paths.save_settings(self.paths, settings)
        self.folder, self.con, new_con = new, new_con, None
        switched = True
        self.runner.connection = self.con
        new.ensure()

        ctx.set_stage("Removing old folder")
        shutil.rmtree(old.path, ignore_errors=True)
        if old.path.exists():
            log.info("Move data folder: old folder not fully removed")
        return dest
