# Plan: accept .xls and .xlsb files

Status: **approved and implemented** (20-11-2026, decision D38). See the PROGRESS.md session log for what was
built and what differs from this plan.

## 1. Decision

| Format | Decision | Why |
| --- | --- | --- |
| .xlsx, .xlsm, .csv | Already supported | — |
| **.xls** (Excel 97-2003, BIFF8) | **Add** | Still common in accounting and ERP exports |
| **.xlsb** (Excel Binary) | **Add** | Used for large workbooks |
| Strict Open XML (.xlsx) | Already accepted; add a test | Same extension; calamine and `excel.Book` both read it (checked) |
| .xltx/.xltm/.xlt templates | Not now | Cheap, but data is rarely kept in templates |
| .ods | Not now | Rarely used; calamine reads `#N/A` as **0** (wrong number, no warning) |
| .txt (Tab-delimited, Unicode Text) | Not now (user decision) | Needs UTF-16 and tab defaults; plan separately |
| .xml 2003, .prn, .dif, .slk, .htm/.mht, .xlam/.xla, .pdf/.xps | No | Obsolete, or not a data format; calamine can't read them |

Excel-saved .xls and .xlsb files keep every rule V2 already applies: values from python-calamine, hidden rows and
sheets skipped and counted (IN-13), error cells read as their text (CONV-05), password-protected files are an error (IN-9),
and source files are opened read-only (SEC-2). There is **no new dependency**: only the standard library and
python-calamine 0.9.1, which we already ship.

## 2. What the spike found (Excel 16 saved one workbook in every format; scratch only)

The test workbook has a title row, a header on row 2, text `00123`, 2.345, a date-time, `=100*1.5`, `=NA()`, `=1/0`, two
hidden rows, a hidden sheet and a value with surrounding spaces.

| | .xls | .xlsb |
| --- | --- | --- |
| Values, formulas (last calculated value), dates, `00123`, spaces kept | ✔ | ✔ |
| Sheet list with hidden sheets (`sheets_metadata`) | ✔ | ✔ |
| Hidden rows | ✘ not reported (same as .xlsx, R5) | ✘ not reported |
| Error cells `#N/A`, `#DIV/0!` | ✘ read as `''` (same as .xlsx, S3) | ✘ read as `''` |
| Password-protected | `PasswordError`; the file has **no** `EncryptionInfo` stream (RC4 `FILEPASS` record), so today's `ole_is_encrypted` misses it | `PasswordError`; OLE container with `EncryptionInfo` (already detected) |
| Reads the whole sheet to give the first rows | Yes (at most 65,536 rows, acceptable) | Yes (**too slow** for the probe on a large file) |

Confirmed binary details: the .xlsb `BrtRowHdr` hidden flag is bit `0x10` of byte 11, and `BrtFmlaError` holds the error
code at offset 8 (`0x2A` = `#N/A`, `0x07` = `#DIV/0!`).

## 3. Design

### 3.1 File type from content (IN-3, technical spec "File type")

`source.sniff` keeps `zip` / `ole` / `text`, followed by a second look:

| Content | Kind | Outcome |
| --- | --- | --- |
| ZIP with `xl/workbook.xml` | `xlsx` / `xlsm` (by extension, as today) | Read |
| ZIP with `xl/workbook.bin` | `xlsb` | Read |
| ZIP, neither | — | "can't be read. It may be damaged, or not an Excel workbook." (unchanged) |
| OLE with `EncryptionInfo` stream | — | Password-protected error (unchanged; covers encrypted .xlsx/.xlsm/.xlsb) |
| OLE with `Workbook` stream, BIFF8, `FILEPASS` in globals | — | Password-protected error (**new**) |
| OLE with `Workbook` stream, BIFF8 | `xls` | Read |
| OLE with only a `Book` stream (Excel 5.0/95) | — | "{file} was saved in a format older than Excel 97. Open it in Excel and save it as .xlsx." |
| Other OLE (for example a renamed .doc) | — | "{file} isn't a valid Excel workbook." |
| Text named .xls/.xlsb/.xlsx/.xlsm, starts with `<` | — | "{file} is a web page or XML file with an Excel name. Open it in Excel and save it as .xlsx." (common for ERP 'Excel' exports) |
| Other text not named .csv | — | "{file} isn't a valid Excel workbook." (unchanged) |

As today, content decides: a real .xls named `.xlsx` is read as .xls.

### 3.2 One workbook interface, three readers

Today `excel.Book` (.xlsx/.xlsm) provides `sheets` (name, visible, part), `peek(name)` (first visible rows + dimension last
row), and `scan(name, errors=, stop=)` (hidden rows + error cells). The new readers give the same three things:

- **`ingest/cfb.py`** (new, ~150 lines): a minimal read-only Compound File reader: header, DIFAT/FAT, directory, regular
  and mini streams, 512- and 4096-byte sectors. It lists stream names and returns one stream's bytes. Damaged
  structure → `ExcelError`.
- **`ingest/xls.py`** (new): `XlsBook(fh)`.
  - Globals: `BOUNDSHEET8` (name, visibility, worksheet type only, stream offset), `FILEPASS` → password problem.
  - `scan`: walks the sheet's records: `ROW` grbit `0x0020` (hidden), `BOOLERR` with fError, and `FORMULA` with a
    cached error result → error-code text (`#NULL!`, `#DIV/0!`, `#VALUE!`, `#REF!`, `#NAME?`, `#NUM!`, `#N/A`);
    `DIMENSIONS` → last row.
  - `peek`: calamine's values for the sheet (at most 65,536 rows), with hidden rows (from the scan) left out, in the
    same `Peek` shape.
- **`ingest/xlsb.py`** (new): `XlsbBook(fh)`.
  - Sheets from `xl/workbook.bin` `BrtBundleSh` (state, rel id, name) + `workbook.bin.rels`.
  - Streams the sheet part record by record (7-bit variable type and size), never the whole sheet in memory.
  - `scan`: `BrtRowHdr` hidden bit, `BrtCellError` / `BrtFmlaError` → error text, `BrtWsDim` → last row.
  - `peek`: decodes cells of the first rows itself (RK, real, bool, inline string, shared-string index, formula
    string/number/bool) and reads `sharedStrings.bin` only up to the highest index needed (the same approach as the
    .xlsx peek), so probing a large .xlsb doesn't load the sheet.
- **`excel.open_book(fh, kind)`** chooses the reader. `excel.read_sheet` stays one function: calamine values, hidden
  rows dropped and counted, error cells patched in from the scan. This is already the .xlsx path, now with the
  reader chosen by kind.

`probe._probe_excel`, `sample._inspect_excel`, `stage.read_part` and `sample.read_part` call `open_book` instead of
`Book`. The `kind` value gains `xls` and `xlsb` (it isn't stored in the catalogue; only in memory).

### 3.3 Screens and messages (UI-6 plain text)

- File pickers (New run, New template): `Excel and CSV files (*.xlsx *.xlsm *.xlsb *.xls *.csv)`.
- "Accepts" notes: `.xlsx, .xlsm, .xlsb, .xls or .csv`.
- Refusal for other types: "{file}: only .xlsx, .xlsm, .xlsb, .xls and .csv files can be added."
- The `.xls`-specific refusal and the "may be an old .xls file renamed" messages are removed.

### 3.4 Unchanged on purpose

- CSV handling, templates, mapping, validation, staging, commit and analysis: the staged raw text is the same for every
  workbook format.
- `selftest.py` still checks .xlsx + CSV only (it builds its files with the standard library, which can't write
  .xls/.xlsb). It already confirms that calamine loads, which covers the new formats' reading library.

## 4. Spec and test-sheet changes (need your OK, CLAUDE.md: specs are only changed with approval)

| File | Change |
| --- | --- |
| `feature-spec-v2.0.md` | IN-3: ".xlsx, .xlsm, .xlsb, .xls, .csv. No .txt"; remove ".xls" from the out-of-scope line |
| `technical-spec-v1.0.md` | T11: also .xls and .xlsb, with hidden rows and error cells from our own record scan; "File type" row as in 3.1; R5 mitigation wording |
| `test-cases.md` | C3-04 and RUNF-03: .xls accepted, a `.txt` file refused instead; F11 outcome "Ready, 100 rows"; new fixtures F22–F27 and cases below |
| `PROGRESS.md` | Decision D-row "Accept .xls and .xlsb (20-11-2026)"; session log |

## 5. Fixtures

No package can write .xlsb, and nothing in requirements-dev writes .xls, so the new files are **checked-in binaries**,
like F11. They're built once by `tests/fixtures/make_static_formats.ps1` (development only; uses Excel through COM),
which opens the generated .xlsx fixtures and saves them with Excel:

| ID | File | Made from | Expected |
| --- | --- | --- | --- |
| F11 | Sales_Old.xls (existing) | — | Now **Ready**, 100 rows |
| F22 | Sales_Nov.xls | F03 | Same as F03: 4,000 rows loaded, 10 blank, 25 hidden + sheet Old; Taxable 6,029,500.00, Tax 765,378.00 |
| F23 | Sales_Nov.xlsb | F03 | Same as F22 |
| F24 | Conversion_Values.xls | F19 | CONV-05 values: 150.00; blank + warning "#N/A"; 05-11-2026; 00123 |
| F25 | Conversion_Values.xlsb | F19 | Same as F24 |
| F26 | Sales_Protected.xls | F06, password `Sankalan@123` | Password-protected error |
| F27 | Sales_Protected.xlsb | F06, password `Sankalan@123` | Password-protected error |
| F28 | Sales_Export.xls (generated) | HTML table text | Web page/XML error message |
| F29 | Sales_Notes.txt (generated) | Text | Refused: only .xlsx, .xlsm, .xlsb, .xls and .csv |

`generate.py` copies the binaries into the pack and checks them (magic bytes, calamine row counts), as it does for F11.

## 6. Tests (written first, from the figures above)

- **Unit:** `cfb` (regular vs mini stream, 4096-byte sectors, damaged header → `ExcelError`); xls `scan` / xlsb `scan`
  (hidden rows, error texts, last row); xlsb `peek` reads only the first rows (stops early) and resolves shared strings.
- **Engine probe:** F11/F22/F23 Ready with kind, header row 2, 25 hidden rows, hidden sheet Old listed, rows approx;
  F26/F27 password; F28 and an Excel 95 `Book` stream → their messages; .xls named `.xlsx` read as .xls; Strict .xlsx.
- **Engine load:** full runs on F22 and F23 reproduce RUNV-02 and RUNC-03 totals exactly; F24/F25 reproduce CONV-05.
- **Template sample:** F22/F23 inspect (sheets, header, preview) and `read_part`.
- **GUI:** pickers and refusal tests switch from F11 to F29; F11 accepted in New template and New run.
- Full suite passes; `test_only_allowed_compiled_addons_load` and the offline tests stay green (nothing new loads).

## 7. Order of work

1. Spec, test-sheet and PROGRESS updates (section 4).
2. Fixture script + binaries + `generate.py` checks (section 5).
3. Failing tests (section 6).
4. `cfb.py` → `xls.py` → `xlsb.py` → `open_book` + `read_sheet` dispatch.
5. File-type detection and messages in `source` / `probe` / `sample`; picker filters and notes.
6. Full suite, manual check in the app with the F22/F23 files, PROGRESS.md, commit on `v2`.

## 8. Risks

| Risk | Mitigation |
| --- | --- |
| Hand-written binary readers miss a variant (e.g. `CONTINUE` records, mini-stream workbooks, xlsb short cell records) | Readers only *read hidden rows, errors and first rows*; values still come from calamine. Unknown records are skipped by size. Fixtures come from real Excel saves |
| An .xls written by another tool (ERP) has no `ROW` records | No hidden rows are reported, which is correct: such writers can't hide rows |
| Very large .xlsb on the full read | Same calamine full-sheet path as .xlsx (PERF-2 note); only the probe is made streaming |
| `.xls` sheets limited to 65,536 rows | Nothing needed; the format can't hold more |
