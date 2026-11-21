r"""Exports as Job work: one chunked, splitting, verifiable engine (EXP-1 to EXP-14; Tech spec A2 8.2–8.5, T33–T38).

Every export is a list of ``ExportSource``s (``sankalan.query.export``), one file each, or parts of ``PART_ROWS``
records each when a source has more rows (EXP-8, EXP-9). ``export`` runs five steps:

1. **Check.** Free space on the destination and temp drives (``estimate``, ``space_problem``; EXP-13, T34), and every
   file to be replaced opened for writing, to catch one open in Excel (T36).
2. **Extract.** DuckDB writes each chunk to ``%TEMP%\Sankalan\<job>-<k>.csv`` with no header (T33, spike S2).
3. **Split.** ``exporting_split.Splitter`` streams the chunk into ``<final name>.partial`` parts (BOM and header in
   each), and the chunk file is deleted before the next COPY, so working space never exceeds one chunk.
4. **Verify.** Records counted in each chunk equal its COPY count and the total equals N, otherwise "Export check
   failed: wrote X of N rows".
5. **Finish** (T35), not cancellable: files being replaced are renamed ``.replaced``, the parts renamed into place,
   the ``.replaced`` files deleted. On any error the ``.replaced`` files are renamed back.

Cancel or a failure at any step deletes every chunk and ``.partial`` file and leaves the files that would have been
replaced as they were (EXP-14). A file name that exists and isn't in ``replace`` (the dialog's confirmed set,
EXP-10) refuses the export before anything is written. Test hooks are arguments (``part_rows``,
``missing_rows``) or module functions tests replace; the app never sets them.
"""
from __future__ import annotations

import csv
import io
import math
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from sankalan import formats
from sankalan.exporting_split import BLOCK, BOM, SplitError, Splitter
from sankalan.jobs import JobContext
from sankalan.model.export import ExportOptions
from sankalan.query.export import ExportSource, copy_csv, copy_sample

PART_ROWS = 1_000_000           # T37: tests pass a smaller value; the app never changes it
SAMPLE_ROWS = 10_000            # rows COPYed to estimate bytes per row (8.4)
ESTIMATE_FACTOR = 1.05
GB = 1024 ** 3
PROGRESS_EVERY_S = 0.25
SPLIT_BLOCK = BLOCK             # the splitter's read size (tests use a smaller one)

STAGE_CHECK = "Checking size"
STAGE_READ = "Reading rows"
STAGE_WRITE = "Writing files"
STAGE_FINISH = "Finishing"
PARTIAL, REPLACED = ".partial", ".replaced"

DEST_SHORT = ("Not enough free space on {drive}. This export needs about {need}, including working space; {free} is "
              "free. Free up space or choose a folder on another drive.")
TEMP_SHORT = ("Not enough free space on {drive} for working files. This export needs about {need} there; {free} is "
              "free. Free up space on {drive}.")
IN_USE = "{name} is open in another program. Close it, then export again."
CHECK_FAILED = "Export check failed: wrote {written} of {total} rows"


# ---------------------------------------------------------------------------------------------- errors
class ExportExists(Exception):
    """Files to be written exist and replacing them wasn't confirmed (EXP-4, EXP-10)."""

    def __init__(self, paths: list[Path]):
        self.paths = [Path(p) for p in paths]
        super().__init__(", ".join(p.name for p in self.paths))

    @property
    def path(self) -> Path:
        return self.paths[0]


class NotEnoughSpace(Exception):
    """EXP-13: the message names the drive and both sizes."""


class FileInUse(Exception):
    """T36: a file to be replaced is open in another program."""

    def __init__(self, path: Path):
        self.path = Path(path)
        super().__init__(IN_USE.format(name=self.path.name))


class ExportCheckFailed(Exception):
    """8.2 step 4: the records written don't match the rows expected."""

    def __init__(self, written: int, total: int):
        self.written, self.total = written, total
        super().__init__(CHECK_FAILED.format(written=formats.number(written), total=formats.number(total)))


@dataclass(frozen=True)
class ExportResult:
    """One source written: its files (one, or the parts in order) and its rows."""
    paths: list[Path]
    rows: int

    @property
    def path(self) -> Path:
        return self.paths[0]

    @property
    def split(self) -> bool:
        return len(self.paths) > 1


# ---------------------------------------------------------------------------------------------- names (8.3)
def header_line(headers: list[str], delimiter: str) -> bytes:
    """The header as DuckDB would quote it: a name with the delimiter, a quote or a line break is quoted."""
    buf = io.StringIO()
    csv.writer(buf, delimiter=delimiter, quotechar='"', lineterminator="\n",
               quoting=csv.QUOTE_MINIMAL).writerow(headers)
    return buf.getvalue().encode("utf-8")


def part_count(rows: int, part_rows: int = PART_ROWS) -> int:
    return max(1, math.ceil(rows / part_rows))


def stem(file_name: str) -> str:
    """The file name without a final ``.csv`` of any case."""
    return file_name[:-4] if file_name.lower().endswith(".csv") else file_name


def plan(rows: int, file_name: str, part_rows: int = PART_ROWS) -> list[str]:
    """The final names (EXP-10): one file with the dialog's name when ``rows`` ≤ ``part_rows``, else M parts
    ``<stem>_partKKofMM.csv``, both numbers zero-padded to ``max(2, len(str(M)))`` digits."""
    m = part_count(rows, part_rows)
    if m == 1:
        return [file_name]
    w = max(2, len(str(m)))
    base = stem(file_name)
    return [f"{base}_part{k:0{w}d}of{m:0{w}d}.csv" for k in range(1, m + 1)]


# ---------------------------------------------------------------------------------------------- estimate (8.4)
@dataclass(frozen=True)
class Estimate:
    rows: tuple[int, ...]           # N per source
    parts: tuple[int, ...]          # M per source
    labels: tuple[str, ...]         # output names (Export all outputs)
    bytes: int                      # the whole export, headers and BOMs included
    largest_chunk: int              # working space for the largest chunk (temp drive)
    part_rows: int = PART_ROWS

    @property
    def total_rows(self) -> int:
        return sum(self.rows)

    @property
    def files(self) -> int:
        return sum(self.parts)

    @property
    def split(self) -> bool:
        return any(m > 1 for m in self.parts)


def _remove(path: Path) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def estimate(ctx: JobContext, temp_dir: Path, sources: list[ExportSource], options: ExportOptions,
             part_rows: int = PART_ROWS) -> Estimate:
    """Bytes per row from a COPY of up to 10,000 rows per source (later chunks too when the first is short), × N ×
    1.05, plus the header and BOM once per part."""
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    total, largest = 0, 0
    sample = temp_dir / f"{ctx.job_id}-sample.csv"
    try:
        for s in sources:
            sampled = size = 0
            for chunk in s.chunks:
                if sampled >= SAMPLE_ROWS or not chunk.rows:
                    continue
                ctx.check_cancelled()
                sampled += copy_sample(ctx.cursor(), chunk, sample, options.delimiter, SAMPLE_ROWS - sampled)
                size += sample.stat().st_size
                _remove(sample)
            per_row = size / sampled if sampled else 0.0
            lead = len(header_line(s.headers, options.delimiter)) + (len(BOM) if options.bom else 0)
            total += math.ceil(per_row * s.rows * ESTIMATE_FACTOR) + lead * part_count(s.rows, part_rows)
            for chunk in s.chunks:
                largest = max(largest, math.ceil(per_row * chunk.rows * ESTIMATE_FACTOR))
    finally:
        _remove(sample)
    return Estimate(tuple(s.rows for s in sources), tuple(part_count(s.rows, part_rows) for s in sources),
                    tuple(s.label for s in sources), total, largest, part_rows)


def _drive(path: Path) -> str:
    """The drive a path is on ("C:"), or its UNC share."""
    d = os.path.splitdrive(str(Path(path).resolve()))[0]
    return d.upper() if len(d) == 2 else d


def margin(num_bytes: int) -> int:
    return max(GB, num_bytes // 10)


def space_problem(est: Estimate, folder: Path, temp_dir: Path) -> str | None:
    """EXP-13, T34: the message when a drive is short, else None. The destination needs the export plus a margin,
    the temp drive the largest chunk plus a margin; on one drive the two add up. Free space is read now
    (``shutil.disk_usage``, no DuckDB), so the dialog calls it on the UI thread when the folder changes."""
    dest_need = est.bytes + margin(est.bytes)
    temp_need = est.largest_chunk + margin(est.largest_chunk)
    fd, td = _drive(folder), _drive(temp_dir)
    free = shutil.disk_usage(folder).free
    if fd == td:
        need = dest_need + temp_need
        if free < need:
            return DEST_SHORT.format(drive=fd, need=formats.size(need), free=formats.size(free))
        return None
    if free < dest_need:
        return DEST_SHORT.format(drive=fd, need=formats.size(dest_need), free=formats.size(free))
    tfree = shutil.disk_usage(temp_dir).free
    if tfree < temp_need:
        return TEMP_SHORT.format(drive=td, need=formats.size(temp_need), free=formats.size(tfree))
    return None


# ---------------------------------------------------------------------------------------------- checks (T36)
def check_not_open(paths) -> None:
    """Open each existing file for append and close it again: a file Excel holds open refuses (T36)."""
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        try:
            with open(p, "ab"):
                pass
        except PermissionError:
            raise FileInUse(p) from None


# ---------------------------------------------------------------------------------------------- test hooks
def _after_block() -> None:
    """Called after each block is split (tests use it to cancel mid-stream)."""


def _before_finish() -> None:
    """Called just before the finish step (tests use it to cancel there)."""


def _open_write(path: Path):
    """Opens a part for writing (tests replace it to simulate a full disk)."""
    return open(path, "wb")


_rename = os.replace            # the finish step's renames (tests replace it to fail one)


# ---------------------------------------------------------------------------------------------- export (8.2)
@dataclass
class _Work:
    """Files the export has made, for clean-up on cancel or failure."""
    chunks: list[Path] = field(default_factory=list)
    partials: list[Path] = field(default_factory=list)
    splitter: Splitter | None = None

    def clean(self) -> None:
        if self.splitter is not None:
            try:
                self.splitter.abandon()
            except OSError:
                pass
            self.splitter = None
        for p in self.chunks + self.partials:
            try:
                _remove(p)
            except OSError:
                pass


def _finish(pairs: list[tuple[Path, Path]]) -> None:
    """T35: move existing targets aside, rename the parts into place, delete what was moved aside. On any error,
    put everything back as it was and delete the parts."""
    moved: list[Path] = []
    placed: list[Path] = []
    try:
        for _partial, target in pairs:
            if target.exists():
                _rename(target, target.with_name(target.name + REPLACED))
                moved.append(target)
        for partial, target in pairs:
            _rename(partial, target)
            placed.append(target)
    except BaseException:
        for target in placed:
            try:
                _remove(target)
            except OSError:
                pass
        for target in moved:
            try:
                os.replace(target.with_name(target.name + REPLACED), target)
            except OSError:
                pass
        for partial, _target in pairs:
            try:
                _remove(partial)
            except OSError:
                pass
        raise
    for target in moved:
        try:
            _remove(target.with_name(target.name + REPLACED))
        except OSError:
            pass


def export(ctx: JobContext, temp_dir: Path, sources: list[ExportSource], folder: Path, names: list[str],
           options: ExportOptions, *, replace=frozenset(), part_rows: int = PART_ROWS,
           estimate_: Estimate | None = None, missing_rows: int = 0) -> list[ExportResult]:
    """Write each source to ``folder`` under its name (split into parts when needed); one result per source.
    ``replace``: the existing files the user agreed to replace. ``missing_rows``: a test fault that makes the count
    check fail."""
    folder, temp_dir = Path(folder), Path(temp_dir)
    sources, names = list(sources), list(names)
    if len(sources) != len(names):
        raise ValueError("one name per source")
    if not folder.is_dir():
        raise FileNotFoundError(str(folder))
    targets = [[folder / n for n in plan(s.rows, name, part_rows)] for s, name in zip(sources, names)]
    flat = [t for ts in targets for t in ts]
    replace = {Path(p) for p in replace}
    existing = [t for t in flat if t.exists()]
    refused = [t for t in existing if t not in replace]
    if refused:
        raise ExportExists(refused)

    # 1. Check
    ctx.set_stage(STAGE_CHECK)
    temp_dir.mkdir(parents=True, exist_ok=True)
    est = estimate_ if estimate_ is not None else estimate(ctx, temp_dir, sources, options, part_rows)
    problem = space_problem(est, folder, temp_dir)
    if problem:
        raise NotEnoughSpace(problem)
    check_not_open(existing)

    work = _Work()
    ctx.on_abort(work.clean)
    total = sum(s.rows for s in sources)
    header_bom = options.bom
    many = len(sources) > 1
    files = len(flat)
    try:
        results: list[ExportResult] = []
        pairs: list[tuple[Path, Path]] = []
        done = 0                    # records written by earlier sources
        first_file = 0              # files written by earlier sources
        seq = 0
        for s, ts in zip(sources, targets):
            partials = [t.with_name(t.name + PARTIAL) for t in ts]
            m = len(ts)

            def detail(part: int, m=m, first_file=first_file) -> str | None:
                if many:
                    return f"file {first_file + part} of {files}"
                return f"part {part} of {m}" if m > 1 else None

            def open_part(k: int, partials=partials, s=s):
                if k >= len(partials):          # more records than planned
                    raise ExportCheckFailed(done + work.splitter.written, total)
                work.partials.append(partials[k])
                return _open_write(partials[k])

            last = [0.0]

            def tick(written: int, part: int, done=done, detail=detail, last=last) -> None:
                now = time.monotonic()
                if now - last[0] >= PROGRESS_EVERY_S:
                    last[0] = now
                    ctx.set_rows(done + written)
                    ctx.set_detail(detail(part))
                _after_block()
                ctx.check_cancelled()

            splitter = Splitter(open_part, header_line(s.headers, options.delimiter), header_bom, part_rows,
                                tick=tick, block=SPLIT_BLOCK)
            work.splitter = splitter
            for chunk in s.chunks:
                # 2. Extract
                ctx.set_stage(STAGE_READ)
                path = temp_dir / f"{ctx.job_id}-{seq}.csv"
                seq += 1
                work.chunks.append(path)
                copied = copy_csv(ctx.cursor(), chunk.sql, path, options.delimiter)
                ctx.check_cancelled()
                # 3. Split
                ctx.set_stage(STAGE_WRITE, total)
                ctx.set_rows(done + splitter.written)
                ctx.set_detail(detail(splitter.part))
                try:
                    actual = splitter.feed(path)
                except SplitError:
                    raise ExportCheckFailed(done + splitter.written, total) from None
                _remove(path)
                # 4. Verify, per chunk
                got, missing_rows = actual - missing_rows, 0
                if got != copied:
                    raise ExportCheckFailed(done + splitter.written - (actual - got), total)
            counts = splitter.close()
            work.splitter = None
            written = sum(counts)
            if written != s.rows or len(counts) != m:
                raise ExportCheckFailed(done + written, total)
            ctx.set_rows(done + written)
            done += written
            first_file += m
            pairs += list(zip(partials, ts))
            results.append(ExportResult(list(ts), written))
        if done != total:
            raise ExportCheckFailed(done, total)

        # 5. Finish
        _before_finish()
        ctx.check_cancelled()
        ctx.set_cancellable(False)
        ctx.set_stage(STAGE_FINISH)
        check_not_open(existing)
        _finish(pairs)
        work.partials.clear()
        return results
    except BaseException:
        work.clean()
        raise
