"""Export in parts at the real part size (``slow``; Feature Spec A2 AC-EXP-8a, EXP-9; Tech spec A2 T37).

1,000,000 rows are one file with no part suffix; 1,000,001 rows are two parts of 1,000,000 and 1. The rows come from
DuckDB's ``range`` with values that need quoting (the delimiter, quotes, a line break) on and around the cut. The
full-size TPL-R run export (3 parts) is in ``test_stored_order.py``, which already commits the full runs.

    pytest -m slow tests/engine/test_export_big.py
"""
import csv

import pytest

from conftest import open_storage, run_job, spec, temp_leftovers
from sankalan import exporting
from sankalan.model.export import ExportOptions
from sankalan.query.export import Chunk, ExportSource

pytestmark = pytest.mark.slow

HEADERS = ["Invoice No", "Narration", "Taxable Value"]


def source(n: int) -> ExportSource:
    """``n`` rows; every 1,000th narration holds a comma, quotes and a line break, and so do rows 999,999–1,000,001."""
    nasty = "'He said \"stop\", then' || chr(10) || 'go'"
    select = (f"SELECT 'INV-' || i, CASE WHEN i % 1000 = 0 OR i BETWEEN 999998 AND 1000001 THEN {nasty} "
              f"ELSE 'plain ' || i END, CAST(CAST(i AS DECIMAL(38,2)) / 100 AS VARCHAR) FROM range({n}) t(i)")
    return ExportSource(HEADERS, [Chunk(select, n, "ORDER BY i")], n)


@pytest.fixture(scope="module")
def storage(tmp_path_factory):
    s = open_storage(tmp_path_factory.mktemp("big"))
    yield s
    s.close()


def records(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        assert next(r) == HEADERS
        return [row[0] for row in r]


@spec("AC-EXP-8a", "EXP-8", "EXP-9", "T37")
def test_one_million_rows_one_file_and_one_more_two_parts(storage, tmp_path):
    s = storage
    assert exporting.PART_ROWS == 1_000_000
    out, = run_job(s.runner, lambda ctx: exporting.export(ctx, s.paths.temp, [source(1_000_000)], tmp_path,
                                                          ["Big.csv"], ExportOptions()))
    assert [p.name for p in out.paths] == ["Big.csv"] and out.rows == 1_000_000
    assert len(records(out.path)) == 1_000_000
    out, = run_job(s.runner, lambda ctx: exporting.export(ctx, s.paths.temp, [source(1_000_001)], tmp_path,
                                                          ["More.csv"], ExportOptions()))
    assert [p.name for p in out.paths] == ["More_part01of02.csv", "More_part02of02.csv"]
    first, second = records(out.paths[0]), records(out.paths[1])
    assert len(first) == 1_000_000 and second == ["INV-1000000"] and first[-1] == "INV-999999"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Big.csv", "More_part01of02.csv", "More_part02of02.csv"]
    assert temp_leftovers(s.paths.temp) == []
