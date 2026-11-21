"""The export splitter (Tech spec A2 8.5; AC-EXP-9a, AC-EXP-9b, R9): records with quotes, doubled quotes, \\r, \\n and
delimiters planted on and around part boundaries and block boundaries are never cut; every part parses as CSV with
the expected record count, starts with the BOM and header, and the parts' data rows joined are byte-identical to the
input."""
import csv
import io
import math
import random

import pytest

from conftest import spec
from sankalan.exporting import header_line
from sankalan.exporting_split import BOM, SplitError, Splitter

HEADER = header_line(["Invoice No", "Narration, notes", "Taxable Value"], ",")
NASTY = ['say "hi"', "a,b", "line1\r\nline2", "line1\nline2", '""', '"', ",", "\n", "\r\n", "x\r", "",
         'end with quote"', '"start quote', "plain", "₹ 12,000/-"]


def records(n: int, seed: int, nasty_at: set[int] = frozenset()) -> list[bytes]:
    """``n`` CSV records quoted as DuckDB quotes them; rows in ``nasty_at`` hold a value with line breaks and quotes."""
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        if i in nasty_at:
            row = [f"INV-{i}", 'He said "stop",\r\nthen\n"go"', "12,000/-"]
        else:
            row = [f"INV-{i}", rnd.choice(NASTY) if rnd.random() < 0.6 else "", f"{rnd.randint(0, 99999)}.{i % 100:02d}"]
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL).writerow(row)
        out.append(buf.getvalue().encode("utf-8"))
    return out


def write_chunks(tmp_path, recs: list[bytes], cuts: list[int]) -> list:
    paths, start = [], 0
    for k, end in enumerate(cuts + [len(recs)]):
        p = tmp_path / f"chunk-{k}.csv"
        p.write_bytes(b"".join(recs[start:end]))
        paths.append(p)
        start = end
    return paths


def split(tmp_path, recs, part_rows, *, bom=True, block=1 << 23, cuts=(), ticks=None):
    files = []

    def open_part(k):
        files.append(tmp_path / f"part-{k}.csv")
        return open(files[-1], "wb")
    sp = Splitter(open_part, HEADER, bom, part_rows, block=block,
                  tick=(lambda w, p: ticks.append((w, p))) if ticks is not None else None)
    got = [sp.feed(p) for p in write_chunks(tmp_path, recs, list(cuts))]
    return got, sp.close(), files


def check_parts(recs, part_rows, counts, files, bom=True):
    n = len(recs)
    m = max(1, math.ceil(n / part_rows))
    assert len(files) == m and len(counts) == m
    assert counts == [min(part_rows, n - k * part_rows) for k in range(m)] if n else counts == [0]
    lead = (BOM if bom else b"") + HEADER
    data = b""
    for path, c in zip(files, counts):
        raw = path.read_bytes()
        assert raw.startswith(lead)
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
        assert rows[0] == ["Invoice No", "Narration, notes", "Taxable Value"] and len(rows) == c + 1
        data += raw[len(lead):]
    assert data == b"".join(recs)


@spec("AC-EXP-9a", "AC-EXP-9b", "EXP-9", "R9")
@pytest.mark.parametrize("block", [1, 2, 3, 7, 64, 4096, 1 << 23])
def test_parts_parse_and_join_byte_identical(tmp_path, block):
    part_rows = 50
    nasty = {part_rows - 1, part_rows, part_rows + 1, 2 * part_rows - 1, 2 * part_rows}
    recs = records(173, seed=block, nasty_at=nasty)
    got, counts, files = split(tmp_path, recs, part_rows, block=block, cuts=[30, 50, 51, 120])
    assert sum(got) == 173 and got == [30, 20, 1, 69, 53]
    check_parts(recs, part_rows, counts, files)


@spec("AC-EXP-9a", "EXP-9")
@pytest.mark.parametrize("seed", range(6))
def test_random_records_part_sizes_and_plain_utf8(tmp_path, seed):
    rnd = random.Random(seed)
    n = rnd.randint(1, 400)
    part_rows = rnd.choice([1, 2, 7, 33, 100, 1000])
    recs = records(n, seed)
    cuts = sorted(rnd.sample(range(1, n), min(3, n - 1))) if n > 1 else []
    got, counts, files = split(tmp_path, recs, part_rows, bom=False, block=rnd.choice([1, 5, 97, 1 << 23]),
                               cuts=cuts)
    assert sum(got) == n
    check_parts(recs, part_rows, counts, files, bom=False)


@spec("EXP-9", "AC-EXP-8a")
def test_exact_multiple_gives_no_empty_part_and_no_rows_gives_header_only(tmp_path):
    recs = records(100, 1)
    _got, counts, files = split(tmp_path, recs, 50)
    assert counts == [50, 50] and len(files) == 2
    check_parts(recs, 50, counts, files)
    (tmp_path / "e").mkdir()
    _got, counts, files = split(tmp_path / "e", [], 50)
    assert counts == [0] and files[0].read_bytes() == BOM + HEADER


@spec("8.5", "AC-EXP-14b")
def test_unbalanced_quote_or_cut_record_at_chunk_end_fails(tmp_path):
    sp = Splitter(lambda k: open(tmp_path / f"p{k}.csv", "wb"), HEADER, True, 10)
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b'INV-1,"open quote\nstill inside,1.00\n')
    with pytest.raises(SplitError):
        sp.feed(bad)
    sp.abandon()
    sp = Splitter(lambda k: open(tmp_path / f"q{k}.csv", "wb"), HEADER, True, 10)
    cut = tmp_path / "cut.csv"
    cut.write_bytes(b"INV-1,a,1.00\nINV-2,b,2.0")
    with pytest.raises(SplitError):
        sp.feed(cut)
    sp.abandon()


@spec("8.5", "EXP-11")
def test_tick_after_every_block(tmp_path):
    ticks = []
    recs = records(40, 3)
    split(tmp_path, recs, 10, block=64, ticks=ticks)
    size = sum(len(r) for r in recs)
    assert len(ticks) == math.ceil(size / 64)
    assert ticks[-1] == (40, 4) and [w for w, _p in ticks] == sorted(w for w, _p in ticks)
