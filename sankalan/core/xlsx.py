"""A small, fast .xlsx/.xlsm reader built only on the Python standard library.

Why: Windows Smart App Control blocks unsigned compiled add-ons (it blocked python-calamine's .pyd).
The standard library's XML parser ships inside the signed Python runtime, so this reader always loads.

Reads cell values (shared strings, inline strings, numbers, booleans, dates by number format),
sheet visibility and hidden rows. Formulas are read as their last calculated values.
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_STRICT_REL_NS = "http://purl.oclc.org/ooxml/officeDocument/relationships"
# built-in number formats that are dates/times
_DATE_IDS = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59)) | set(range(71, 82))
_EPOCH_1900 = datetime(1899, 12, 30)
_EPOCH_1904 = datetime(1904, 1, 1)
_COL_RE = re.compile(r"([A-Z]+)(\d+)")


class XlsxError(Exception):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ns(tag: str) -> str:
    return tag[: tag.index("}") + 1] if tag.startswith("{") else ""


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def is_date_format(code: str) -> bool:
    if not code or code.lower() == "general":
        return False
    code = re.sub(r'\[[^\]]*\]|"[^"]*"|\\.|_.|\*.', "", code)   # colours, conditions, literals, padding
    code = code.split(";")[0]
    return bool(re.search(r"[dmyhs]", code, re.I))


class XlsxBook:
    def __init__(self, data: bytes):
        try:
            self.zip = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise XlsxError("not a valid Excel file") from exc
        names = set(self.zip.namelist())
        if "xl/workbook.xml" not in names:
            raise XlsxError("not a valid Excel file")
        wb = ET.fromstring(self.zip.read("xl/workbook.xml"))
        ns = _ns(wb.tag)
        pr = wb.find(f"{ns}workbookPr")
        self.date1904 = pr is not None and pr.get("date1904") in ("1", "true")
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for r in ET.fromstring(self.zip.read("xl/_rels/workbook.xml.rels")):
                rels[r.get("Id")] = r.get("Target", "")
        self._sheets = []          # (name, visible)
        self._paths = {}
        sheets_el = wb.find(f"{ns}sheets")
        for s in (sheets_el if sheets_el is not None else []):
            rid = s.get(f"{{{_REL_NS}}}id") or s.get(f"{{{_STRICT_REL_NS}}}id")
            target = rels.get(rid, "")
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            name = s.get("name")
            self._paths[name] = target
            self._sheets.append((name, s.get("state", "visible") == "visible"))
        self._strings = self._read_shared_strings(names)
        self._date_styles = self._read_date_styles(names)

    # ------------------------------------------------------------------ workbook parts
    def _read_shared_strings(self, names):
        if "xl/sharedStrings.xml" not in names:
            return []
        out = []
        with self.zip.open("xl/sharedStrings.xml") as fh:
            for _, el in ET.iterparse(fh, events=("end",)):
                if _local(el.tag) == "si":
                    out.append(self._text_of(el))
                    el.clear()
        return out

    @staticmethod
    def _text_of(el):
        """Text of a string item: plain <t>, or the runs <r><t> (phonetic <rPh> ignored)."""
        parts = []
        for child in el:
            name = _local(child.tag)
            if name == "t":
                parts.append(child.text or "")
            elif name == "r":
                for t in child:
                    if _local(t.tag) == "t":
                        parts.append(t.text or "")
        return "".join(parts)

    def _read_date_styles(self, names):
        if "xl/styles.xml" not in names:
            return set()
        st = ET.fromstring(self.zip.read("xl/styles.xml"))
        ns = _ns(st.tag)
        custom = {}
        nf = st.find(f"{ns}numFmts")
        if nf is not None:
            for f in nf:
                custom[int(f.get("numFmtId"))] = f.get("formatCode", "")
        dates = set()
        xfs = st.find(f"{ns}cellXfs")
        for i, xf in enumerate(xfs if xfs is not None else []):
            fid = int(xf.get("numFmtId", "0"))
            if fid in _DATE_IDS or (fid in custom and is_date_format(custom[fid])):
                dates.add(i)
        return dates

    def sheets(self):
        return list(self._sheets)

    # ------------------------------------------------------------------ cells
    def _to_date(self, v: float):
        base = _EPOCH_1904 if self.date1904 else _EPOCH_1900
        try:
            return base + timedelta(days=v)
        except (OverflowError, ValueError):
            return v

    def read(self, name: str):
        """Return (rows, hidden_rows): rows[i] holds the values of sheet row i+1 (empty rows kept,
        so list positions are the original row numbers); hidden_rows is a set of 1-based row numbers."""
        path = self._paths.get(name)
        if not path:
            raise XlsxError(f'no sheet named "{name}"')
        strings, date_styles = self._strings, self._date_styles
        rows: dict = {}
        hidden = set()
        row_tag = c_tag = None
        next_row = 1
        with self.zip.open(path) as fh:
            for _, el in ET.iterparse(fh, events=("end",)):
                tag = el.tag
                if row_tag is None:
                    lname = _local(tag)
                    if lname in ("c", "row"):
                        ns = _ns(tag)
                        row_tag, c_tag = ns + "row", ns + "c"
                        v_tag, is_tag = ns + "v", ns + "is"
                if tag != row_tag:
                    continue
                r = el.get("r")
                rnum = int(r) if r else next_row
                next_row = rnum + 1
                if el.get("hidden") in ("1", "true"):
                    hidden.add(rnum)
                vals = []
                pos = 0
                for c in el:
                    if c.tag != c_tag:
                        continue
                    ref = c.get("r")
                    if ref:
                        m = _COL_RE.match(ref)
                        pos = _col_index(m.group(1)) if m else pos
                    t = c.get("t")
                    v_el = c.find(v_tag)
                    text = v_el.text if v_el is not None else None
                    if t == "s":
                        val = strings[int(text)] if text is not None else None
                    elif t == "inlineStr":
                        is_el = c.find(is_tag)
                        val = self._text_of(is_el) if is_el is not None else None
                    elif t in ("str",):
                        val = text
                    elif t == "b":
                        val = (text == "1") if text is not None else None
                    elif t == "e":
                        val = None
                    elif t == "d":
                        try:
                            val = datetime.fromisoformat(text) if text else None
                        except ValueError:
                            val = text
                    else:
                        if text is None or text == "":
                            val = None
                        else:
                            try:
                                val = float(text)
                            except ValueError:
                                val = text
                            else:
                                s = c.get("s")
                                if s is not None and int(s) in date_styles:
                                    val = self._to_date(val)
                    if val == "":
                        val = None
                    if val is not None:
                        if pos >= len(vals):
                            vals.extend([None] * (pos - len(vals) + 1))
                        vals[pos] = val
                    pos += 1
                rows[rnum] = vals
                el.clear()
        last = max(rows) if rows else 0
        width = max((len(v) for v in rows.values()), default=0)
        out = []
        for i in range(1, last + 1):
            v = rows.get(i, [])
            out.append(v + [None] * (width - len(v)))
        return out, hidden

    def sum_columns(self, name: str, headers: list):
        """Fast path for the totals check: sum the numeric cells of the named header columns
        (header = row 1), without building the other cells."""
        path = self._paths.get(name)
        if not path:
            raise XlsxError(f'no sheet named "{name}"')
        first = self.read_header(name)
        want = {}
        for h in headers:
            if h in first:
                i = first.index(h)
                letters = ""
                n = i + 1
                while n:
                    n, rem = divmod(n - 1, 26)
                    letters = chr(65 + rem) + letters
                want[letters] = h
        sums = {h: 0.0 for h in headers}
        with self.zip.open(path) as fh:
            row_tag = None
            for _, el in ET.iterparse(fh, events=("end",)):
                tag = el.tag
                if row_tag is None:
                    if _local(tag) in ("c", "row"):
                        ns = _ns(tag)
                        row_tag, c_tag, v_tag = ns + "row", ns + "c", ns + "v"
                if tag != row_tag:
                    continue
                if el.get("r") != "1":
                    for c in el:
                        ref = c.get("r") or ""
                        letters = ref.rstrip("0123456789")
                        h = want.get(letters)
                        if h and c.get("t") in (None, "n"):
                            v = c.find(v_tag)
                            if v is not None and v.text:
                                sums[h] += float(v.text)
                el.clear()
        return sums

    def read_header(self, name: str):
        path = self._paths[name]
        strings = self._strings
        with self.zip.open(path) as fh:
            for _, el in ET.iterparse(fh, events=("end",)):
                if _local(el.tag) == "row":
                    vals = []
                    for c in el:
                        if _local(c.tag) != "c":
                            continue
                        m = _COL_RE.match(c.get("r") or "")
                        pos = _col_index(m.group(1)) if m else len(vals)
                        t = c.get("t")
                        txt = None
                        for ch in c:
                            if _local(ch.tag) == "v":
                                txt = ch.text
                            elif _local(ch.tag) == "is":
                                txt = self._text_of(ch)
                        if t == "s" and txt is not None:
                            txt = strings[int(txt)]
                        if pos >= len(vals):
                            vals.extend([None] * (pos - len(vals) + 1))
                        vals[pos] = txt
                    return vals
        return []
