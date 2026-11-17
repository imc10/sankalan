"""Analysis and default outputs as Job work (ANA-4, ANA-7, ANA-8, DO-4, DO-6, DO-8).

DuckDB is only used inside Jobs; the screens start these through the Job runner. Cancel interrupts the running
query (``ctx.cursor()`` is the connection the Job interrupts), and the screen keeps the previous result greyed.
"""
from __future__ import annotations

from pathlib import Path

from sankalan.jobs import JobContext
from sankalan.model.definition import Definition
from sankalan.model.template import Column
from sankalan.query import layer

STAGE_ANALYSIS = "Running analysis"
STAGE_VALUES = "Reading values"
STAGE_OUTPUT = "Generating output"


def run_analysis(ctx: JobContext, definition: Definition, columns: list[Column], sources: list[Path],
                 previous: layer.Result | None = None) -> layer.Result:
    """An analysis over the ticked runs (or a default output's preview on one run, DO-8). The previous result's
    temporary table is dropped only once the new one exists."""
    ctx.set_stage(STAGE_ANALYSIS)
    cur = ctx.cursor()
    res = layer.run_definition(cur, definition, columns, sources)
    if previous is not None:
        layer.drop(cur, previous)
    return res


def preview_output(ctx: JobContext, definition: Definition, columns: list[Column], data: Path,
                   previous: layer.Result | None = None) -> layer.Result:
    """A default output's preview: on the latest committed run, or the wizard's staged sample (DO-8)."""
    ctx.set_stage(STAGE_ANALYSIS)
    cur = ctx.cursor()
    res = layer.run_definition(cur, definition, columns, [data], output=True)
    if previous is not None:
        layer.drop(cur, previous)
    return res


def distinct_values(ctx: JobContext, column: Column, sources: list[Path], search: str | None = None):
    ctx.set_stage(STAGE_VALUES)
    return layer.distinct_values(ctx.cursor(), column, sources, search)


def write_outputs(ctx: JobContext, outputs: list[tuple[str, Definition]], columns: list[Column], data: Path,
                  folder: Path) -> list[layer.Result]:
    r"""Default outputs on a staged run's rows, stored as ``outputs\<n>.parquet`` (DO-4, DO-6). ``outputs``:
    (name, definition) in order; files are numbered from 1. Phase 5 adds the per-output status and Retry."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for n, (name, definition) in enumerate(outputs, 1):
        ctx.set_stage(f"{STAGE_OUTPUT}: {name}")
        out.append(layer.write_output(ctx.cursor(), definition, columns, data, folder / f"{n}.parquet"))
        ctx.check_cancelled()
    return out
