"""Streaming .xlsx writer for the consolidated file, standard library only.

Writes exactly what Sankalan needs (OUT-6/7/8): bold shaded header, frozen first row, filter,
column widths, DD-MM-YYYY dates, Indian or standard number formats, an optional Issues sheet.
About 4x faster than a general-purpose writer because each row is built as one XML string.
"""
from __future__ import annotations

import math
import re
import zipfile
from datetime import date, datetime

_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_EPOCH = datetime(1899, 12, 30)
_EPOCH_DATE = date(1899, 12, 30)
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

S_DEFAULT, S_HEADER, S_DATE, S_INDIAN, S_PLAIN = 0, 1, 2, 3, 4


def col_letters(i: int) -> str:
    s, n = "", i + 1
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def _esc(s: str) -> str:
    if _ILLEGAL.search(s):
        s = _ILLEGAL.sub("", s)
    if len(s) > 32767:
        s = s[:32767]
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(ref: str, s: str, style: int = 0) -> str:
    sa = f' s="{style}"' if style else ""
    if s[:1].isspace() or s[-1:].isspace():
        return f'<c r="{ref}"{sa} t="inlineStr"><is><t xml:space="preserve">{_esc(s)}</t></is></c>'
    return f'<c r="{ref}"{sa} t="inlineStr"><is><t>{_esc(s)}</t></is></c>'


def _styles(indian_fmt: str, plain_fmt: str, date_fmt: str) -> str:
    def attr(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return (XML_DECL + f'<styleSheet xmlns="{MAIN}">'
            f'<numFmts count="3"><numFmt numFmtId="164" formatCode="{attr(date_fmt)}"/>'
            f'<numFmt numFmtId="165" formatCode="{attr(indian_fmt)}"/>'
            f'<numFmt numFmtId="166" formatCode="{attr(plain_fmt)}"/></numFmts>'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/><family val="2"/></font>'
            '<font><b/><sz val="11"/><name val="Calibri"/><family val="2"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor rgb="FFF2F2F2"/><bgColor indexed="64"/></patternFill></fill>'
            '</fills>'
            '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
            '<border><left/><right/><top/><bottom style="thin"><color auto="1"/></bottom><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="5">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>'
            '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
            '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
            '<xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
            '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            '</styleSheet>')


class _Sheet:
    def __init__(self, name, headers, rows, kinds, widths):
        self.name, self.headers, self.rows, self.kinds, self.widths = name, headers, rows, kinds, widths


def write_xlsx(path, sheets, *, indian=True, indian_fmt="", plain_fmt="#,##0.00", date_fmt="dd-mm-yyyy",
               progress=None, cancel=None):
    """sheets: list of (name, headers, rows, kinds) where kinds[c] is 'number' for amount columns.
    The first sheet gets the progress/cancel callbacks."""
    from .readers import Cancelled
    letters = [col_letters(i) for i in range(max(len(s[1]) for s in sheets) + 1)]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        n = len(sheets)
        ct = "".join(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" '
                     f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                     for i in range(n))
        z.writestr("[Content_Types].xml", XML_DECL +
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   + ct +
                   '<Override PartName="/xl/styles.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   '<Override PartName="/docProps/app.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels", XML_DECL +
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/>'
                   f'<Relationship Id="rId2" Type="{REL}/extended-properties" Target="docProps/app.xml"/>'
                   '</Relationships>')
        z.writestr("docProps/app.xml", XML_DECL +
                   '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
                   '<Application>Sankalan</Application></Properties>')
        defined = []
        sheet_xml = []
        for i, (name, headers, rows, kinds) in enumerate(sheets):
            last = f"{letters[max(len(headers) - 1, 0)]}{len(rows) + 1}"
            qname = "'" + name.replace("'", "''") + "'"
            defined.append(f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
                           f'{_esc(qname)}!$A$1:${letters[max(len(headers) - 1, 0)]}${len(rows) + 1}</definedName>')
            sheet_xml.append(f'<sheet name="{_esc(name)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>')
        z.writestr("xl/workbook.xml", XML_DECL +
                   f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><bookViews><workbookView/></bookViews>'
                   f'<sheets>{"".join(sheet_xml)}</sheets><definedNames>{"".join(defined)}</definedNames></workbook>')
        rels = "".join(f'<Relationship Id="rId{i + 1}" Type="{REL}/worksheet" Target="worksheets/sheet{i + 1}.xml"/>'
                       for i in range(n))
        z.writestr("xl/_rels/workbook.xml.rels", XML_DECL +
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + rels +
                   f'<Relationship Id="rId{n + 1}" Type="{REL}/styles" Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml", _styles(indian_fmt, plain_fmt, date_fmt))
        for si, (name, headers, rows, kinds) in enumerate(sheets):
            _write_sheet(z, si, headers, rows, kinds, letters, indian,
                         progress if si == 0 else None, cancel if si == 0 else None, Cancelled)


def _widths(headers, rows, kinds):
    widths = [min(max(len(str(h)), 8) + 2, 60) for h in headers]
    for r in rows[:500]:
        for c, v in enumerate(r):
            if v is None or c >= len(widths):
                continue
            if isinstance(v, (datetime, date)):
                n = 10
            elif kinds[c] == "number" and isinstance(v, (int, float)) and not isinstance(v, bool):
                n = len(f"{v:,.2f}") if math.isfinite(v) else 3
            else:
                n = len(str(v))
            if n + 2 > widths[c]:
                widths[c] = min(n + 2, 60)
    return widths


def _write_sheet(z, index, headers, rows, kinds, letters, indian, progress, cancel, Cancelled):
    ncols = len(headers)
    last_col = letters[max(ncols - 1, 0)]
    widths = _widths(headers, rows, kinds)
    number_cols = [k == "number" for k in kinds]
    with z.open(f"xl/worksheets/sheet{index + 1}.xml", "w", force_zip64=True) as fh:
        head = (XML_DECL + f'<worksheet xmlns="{MAIN}" xmlns:r="{REL}">'
                f'<dimension ref="A1:{last_col}{len(rows) + 1}"/>'
                f'<sheetViews><sheetView workbookViewId="0"{" tabSelected=\"1\"" if index == 0 else ""}>'
                '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
                '<selection pane="bottomLeft" activeCell="A2" sqref="A2"/></sheetView></sheetViews>'
                '<sheetFormatPr defaultRowHeight="15"/><cols>'
                + "".join(f'<col min="{c + 1}" max="{c + 1}" width="{w}" customWidth="1"/>'
                          for c, w in enumerate(widths)) + '</cols><sheetData>')
        hdr = '<row r="1">' + "".join(_inline(f"{letters[c]}1", str(h), S_HEADER) for c, h in enumerate(headers)) + "</row>"
        fh.write((head + hdr).encode("utf-8"))
        buf = []
        total = len(rows)
        for i, r in enumerate(rows, start=2):
            if cancel and i % 20000 == 2 and cancel():
                raise Cancelled()
            cells = []
            ap = cells.append
            for c, v in enumerate(r):
                if v is None:
                    continue
                cls = v.__class__
                ref = letters[c] + str(i)
                if cls is str:
                    if v:
                        ap(_inline(ref, v))
                elif cls is float or cls is int:
                    if cls is float and not math.isfinite(v):
                        ap(_inline(ref, str(v)))
                    elif number_cols[c]:
                        ap(f'<c r="{ref}" s="{S_INDIAN if (indian and v >= 0) else S_PLAIN}"><v>{v!r}</v></c>')
                    else:
                        ap(f'<c r="{ref}"><v>{v!r}</v></c>')
                elif cls is datetime:
                    serial = (v - _EPOCH).total_seconds() / 86400.0
                    ap(f'<c r="{ref}" s="{S_DATE}"><v>{serial!r}</v></c>')
                elif cls is date:
                    ap(f'<c r="{ref}" s="{S_DATE}"><v>{(v - _EPOCH_DATE).days}</v></c>')
                elif cls is bool:
                    ap(f'<c r="{ref}" t="b"><v>{1 if v else 0}</v></c>')
                else:
                    ap(_inline(ref, str(v)))
            buf.append(f'<row r="{i}">{"".join(cells)}</row>')
            if len(buf) >= 2000:
                fh.write("".join(buf).encode("utf-8"))
                buf.clear()
                if progress:
                    progress(i - 1, total)
        if buf:
            fh.write("".join(buf).encode("utf-8"))
        fh.write(f'</sheetData><autoFilter ref="A1:{last_col}{len(rows) + 1}"/></worksheet>'.encode("utf-8"))
