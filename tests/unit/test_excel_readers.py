"""The .xls and .xlsb readers' building blocks (D38): the compound-file reader, the BIFF8 scan and the .xlsb record
scan and peek, on hand-built files covering what Excel's own fixtures (F22-F27) don't: version 4 containers,
streams inside embedded objects, damaged chains, and the short cell records newer Excel versions write."""
import io
import struct
import zipfile

import pytest

from sankalan.ingest import cfb, source
from sankalan.ingest.excel import ExcelError, open_book
from sankalan.ingest.source import FileProblem
from sankalan.ingest.xlsb import XlsbBook

FREESECT, ENDOFCHAIN, FATSECT, NOSTREAM = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFF


# ---------------------------------------------------------------------------------------------- a tiny CFB writer
def _entry(name: str, typ: int, left=NOSTREAM, right=NOSTREAM, child=NOSTREAM, start=ENDOFCHAIN, size=0) -> bytes:
    enc = name.encode("utf-16-le") + b"\0\0" if name else b""
    return (enc.ljust(64, b"\0") + struct.pack("<HBB", len(enc), typ, 1) + struct.pack("<III", left, right, child)
            + b"\0" * 16 + b"\0" * 4 + b"\0" * 16 + struct.pack("<IQ", start, size))


def make_cfb(streams: dict[str, bytes], shift: int = 9, nested: dict[str, bytes] | None = None,
             fat_loop: bool = False) -> bytes:
    """A compound file with regular (>= 4096-byte) streams at the top level, and optionally a storage holding
    ``nested`` streams. Sector 0 is the FAT, sector 1 the directory."""
    ss = 1 << shift
    items = list(streams.items()) + list((nested or {}).items())
    fat = [FATSECT, ENDOFCHAIN]
    data = b""
    starts = []
    for _name, body in items:
        assert len(body) >= 4096
        n = -(-len(body) // ss)
        first = len(fat)
        starts.append(first)
        fat.extend(range(first + 1, first + n))
        fat.append(ENDOFCHAIN)
        data += body.ljust(n * ss, b"\0")
    if fat_loop:
        fat[starts[0]] = starts[0]
    fat.extend([FREESECT] * (ss // 4 - len(fat)))
    assert len(fat) == ss // 4
    top = list(streams)
    entries = [None] * (1 + len(items) + (1 if nested else 0))
    # root -> first top-level item; siblings chained to the right; the storage (last) holds the nested streams
    top_ids = list(range(1, 1 + len(top))) + ([len(entries) - 1] if nested else [])
    nested_ids = list(range(1 + len(top), 1 + len(items)))
    entries[0] = _entry("Root Entry", 5, child=top_ids[0])
    for k, i in enumerate(top_ids):
        right = top_ids[k + 1] if k + 1 < len(top_ids) else NOSTREAM
        if nested and i == len(entries) - 1:
            entries[i] = _entry("MBD0001", 1, right=right, child=nested_ids[0])
        else:
            name, body = items[i - 1]
            entries[i] = _entry(name, 2, right=right, start=starts[i - 1], size=len(body))
    for k, i in enumerate(nested_ids):
        right = nested_ids[k + 1] if k + 1 < len(nested_ids) else NOSTREAM
        name, body = items[i - 1]
        entries[i] = _entry(name, 2, right=right, start=starts[i - 1], size=len(body))
    directory = b"".join(entries).ljust(ss, b"\0")
    assert len(directory) == ss
    difat = [0] + [FREESECT] * 108
    header = (cfb.MAGIC + b"\0" * 16 + struct.pack("<HHHHH", 0x3E, 3 if shift == 9 else 4, 0xFFFE, shift, 6)
              + b"\0" * 6 + struct.pack("<IIIIIIIII", 0 if shift == 9 else 1, 1, 1, 0, 4096, ENDOFCHAIN, 0,
                                        ENDOFCHAIN, 0)
              + struct.pack("<109I", *difat))
    assert len(header) == 512
    return header.ljust(ss, b"\0") + struct.pack(f"<{ss // 4}I", *fat) + directory + data


def _body(n: int, seed: int) -> bytes:
    return bytes((i * seed + 7) % 251 for i in range(n))


@pytest.mark.parametrize("shift", [9, 12])
def test_cfb_reads_regular_streams_in_v3_and_v4(shift):
    a, b = _body(5000, 3), _body(9000, 5)
    cf = cfb.CompoundFile(io.BytesIO(make_cfb({"Workbook": a, "Other": b}, shift)))
    assert cf.has_stream("workbook") and cf.has_stream("Other")
    assert cf.read("Workbook") == a and cf.read("Other") == b


def test_cfb_mini_stream(fixtures_dir):
    """Excel writes the summary-information streams (well under 4,096 bytes) into the mini stream."""
    with open(fixtures_dir / "Sales_Nov.xls", "rb") as fh:            # F22, saved by Excel
        cf = cfb.CompoundFile(fh)
        summary = cf.read("\x05SummaryInformation")
        assert len(summary) < cf.mini_cutoff and summary[:2] == b"\xfe\xff"
        assert len(cf.read("Workbook")) >= 4096


def test_cfb_top_level_only():
    """A Workbook stream inside an embedded object's storage isn't the file's own workbook."""
    raw = make_cfb({"WordDocument": _body(4096, 3)}, nested={"Workbook": _body(4096, 5)})
    cf = cfb.CompoundFile(io.BytesIO(raw))
    assert not cf.has_stream("Workbook") and cf.has_stream("WordDocument") and cf.has_entry("MBD0001")
    with pytest.raises(FileProblem) as e:
        source.file_kind(io.BytesIO(raw), "Letter.xls")
    assert e.value.kind == "not_excel"


def test_cfb_damaged():
    raw = make_cfb({"Workbook": _body(5000, 3)})
    with pytest.raises(cfb.CfbError):
        cfb.CompoundFile(io.BytesIO(raw[:300]))
    with pytest.raises(cfb.CfbError):
        cfb.CompoundFile(io.BytesIO(make_cfb({"Workbook": _body(5000, 3)}, fat_loop=True))).read("Workbook")
    with pytest.raises(FileProblem) as e:
        source.file_kind(io.BytesIO(raw[:300]), "Broken.xls")
    assert e.value.kind == "damaged"
    with pytest.raises(ExcelError):            # an OLE file whose Workbook stream isn't BIFF8
        open_book(io.BytesIO(raw), "xls")


# ---------------------------------------------------------------------------------------------- .xlsb records
def _rec(typ: int, body: bytes = b"") -> bytes:
    out = bytearray()
    out.append((typ & 0x7F) | (0x80 if typ >= 0x80 else 0))
    if typ >= 0x80:
        out.append(typ >> 7)
    n = len(body)
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            break
    return bytes(out) + body


def _ws(s: str) -> bytes:
    return struct.pack("<I", len(s)) + s.encode("utf-16-le")


def _row(r: int, hidden=False) -> bytes:
    body = bytearray(struct.pack("<IIH", r, 0, 300)) + b"\0\0" + b"\0" * 5
    if hidden:
        body[11] |= 0x10
    return _rec(0, bytes(body))


def _cell(typ: int, col: int, value: bytes) -> bytes:
    return _rec(typ, struct.pack("<I", col) + b"\0\0\0\0" + value)


def _short(typ: int, value: bytes) -> bytes:
    return _rec(typ, b"\0\0\0\0" + value)


def make_xlsb() -> bytes:
    """Sheet Data: header row 2 (row 1 empty), RK and short records, a hidden row, error cells of both kinds."""
    wb = _rec(131) + _rec(156, struct.pack("<II", 0, 1) + _ws("rId1") + _ws("Data")) \
        + _rec(156, struct.pack("<II", 2, 2) + _ws("rId2") + _ws("Gone")) + _rec(132)
    sheet = (_rec(129) + _rec(148, struct.pack("<IIII", 1, 5, 0, 2)) + _rec(145)
             + _row(1) + _cell(7, 0, struct.pack("<I", 0)) + _short(17, _ws("Amount"))
             + _short(18, struct.pack("<I", 1))
             + _row(2) + _cell(2, 0, struct.pack("<I", (12345 << 2) | 0x03))
             + _short(13, struct.pack("<I", (7 << 2) | 2)) + _short(15, b"\x01")
             + _row(3, hidden=True) + _cell(5, 0, struct.pack("<d", 99999.99))
             + _row(4) + _cell(3, 0, b"\x2a") + _short(14, b"\x07") + _cell(11, 2, b"\x17\0\0")
             + _row(5) + _cell(6, 1, _ws("  kept  "))
             + _rec(146) + _rec(130))
    sst = _rec(159) + _rec(19, b"\0" + _ws("Code")) + _rec(19, b"\0" + _ws("Flag")) + _rec(160)
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="x/worksheet" Target="worksheets/sheet1.bin"/>'
            '<Relationship Id="rId2" Type="x/worksheet" Target="worksheets/sheet2.bin"/>'
            '<Relationship Id="rId3" Type="x/sharedStrings" Target="sharedStrings.bin"/></Relationships>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("xl/workbook.bin", wb)
        z.writestr("xl/_rels/workbook.bin.rels", rels)
        z.writestr("xl/worksheets/sheet1.bin", sheet)
        z.writestr("xl/worksheets/sheet2.bin", _rec(129) + _rec(145) + _rec(146) + _rec(130))
        z.writestr("xl/sharedStrings.bin", sst)
    return out.getvalue()


def test_xlsb_kind_sheets_scan_and_peek():
    raw = make_xlsb()
    assert source.file_kind(io.BytesIO(raw), "Data.xlsx") == "xlsb"         # content decides
    book = XlsbBook(io.BytesIO(raw))
    assert [(s.name, s.visible) for s in book.sheets] == [("Data", True), ("Gone", False)]
    scan = book.scan("Data")
    assert scan.hidden_rows == {4} and scan.last_row == 6
    assert scan.error_cells == {5: {0: "#N/A", 1: "#DIV/0!", 2: "#REF!"}}
    assert book.scan("Data", errors=False).error_cells == {}
    peek = book.peek("Data")
    assert peek.last_row == 6
    assert peek.rows == [(2, ["Code", "Amount", "Flag"]), (3, [123.45, 7.0, True]),
                         (5, ["#N/A", "#DIV/0!", "#REF!"]), (6, [None, "  kept  "])]
    assert [r for r, _ in book.peek("Data", 2).rows] == [2, 3]


def test_xlsb_truncated_part():
    raw = make_xlsb()
    src = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for n in src.namelist():
            body = src.read(n)
            z.writestr(n, body[:40] if n.endswith("sheet1.bin") else body)
    with pytest.raises(ExcelError):
        XlsbBook(io.BytesIO(out.getvalue())).scan("Data")
