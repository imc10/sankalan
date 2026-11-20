# Sankalan — Technical Spec (v1.0)

Nov 16, 2026 · @Chetan Mundhada

## Purpose and scope

Sankalan's final version is built as a PySide6 window over DuckDB 2.0 LTS. Each run is stored as Parquet files, Excel and CSV files are read in parallel worker processes, and the app ships as a signed per-user installer. Every decision here was agreed in the technical discussion on 16-11-2026.

| Source | What this spec takes from it |
| --- | --- |
| [Feature Spec v2.0](https://claude.ai/artifact/NGA281HjAfaYXVHNwNCqh8) | Features and IDs (ENV, UI, TPL, IN, MAP, RUN, DO, VAL, VR, ISS, ANA, EXP, SEC, NF, PERF, V3) |
| Sankalan\_UX\_Context.md and the [UI screens canvas](https://claude.ai/artifact/U522ApcDroz6pGW3VKMvaD) | Screens C1 to C6, A0, A1, and shared states |
| V1 code (Sankalan 1.0.0) | Modules copied over and the security tests (T1) |

Feature IDs in brackets point to Feature Spec v2.0. Changes this spec requires in that spec are listed under Feature spec changes. The next step is the implementation plan, which is handed to Claude Code to build.

## Decisions

27 technical decisions were settled on 16-11-2026. They close open items O9 (benchmark), O10 (distribution) and O11 (V3 proposals) of Feature Spec v2.0. O12 (customer accepts unencrypted local data) stays open.

| # | Decision | Spec items |
| --- | --- | --- |
| T1 | New codebase. Copied over from V1: header detection, CSV encoding and delimiter detection, mapping (normalisation and aliases), number and date reading rules, the hidden-row scan, packaging scripts and security tests. Dropped: the V1 pipeline, validation, writers and screens | NF-8 |
| T2 | DuckDB 2.0 LTS is the engine. An RSA OV code-signing certificate, in the legal name of Ollyver Analytics Pvt Ltd, signs every compiled file so that Smart App Control allows it | NF-7, NF-8 |
| T3 | Signed per-user installer (PyInstaller + NSIS), not running from source | NF-2, NF-7, O10 |
| T4 | No pre-build benchmark. A performance suite runs once on a 16 GB, 4-core laptop as a release acceptance test; any missed target is reported, not blocking | PERF, O9 |
| T5 | Process model C: the window and DuckDB in one process, Excel and CSV reading in worker processes | UI-5, NF-3 |
| T6 | One long Job at a time, app-wide | UI-5 |
| T7 | DuckDB memory capped at 50% of RAM; spill files in the user's temp folder | ENV-3 |
| T8 | Storage layout B: one folder of Parquet files per run plus a DuckDB catalogue; the commit is a folder rename plus one catalogue transaction | RUN-1, RUN-5, RUN-9 |
| T9 | The run being staged lives in the data folder's `_staging` area | SEC-4 (changed) |
| T10 | The catalogue is backed up at each app start; the last 5 copies are kept | New |
| T11 | Excel values read with python-calamine; hidden rows and error cells found by a separate scan of the sheet XML (.xlsx, .xlsm) or of the sheet's binary records (.xlsb, .xls; added 20-11-2026) | IN-3, IN-13 |
| T12 | CSV files are read by the worker processes; Windows-1252 is converted to UTF-8 in Python | IN-4 |
| T13 | Number columns are stored as DECIMAL(38, d), with d set per column (0 to 6, default 2) and fixed after the first committed run. Extra decimals are rounded silently, half away from zero | MAP-10, TPL-1 (changed) |
| T14 | A cell that is empty or only spaces counts as blank. All other spaces are kept as typed | MAP-9, VAL-1 |
| T15 | PERF-2 target: 10M rows from 10 or more .xlsx files in 5 minutes or less (provisional) | PERF-2 |
| T16 | Rule meanings as set out under Validation | VAL-1 to VAL-9 |
| T17 | Every row in a duplicate group is flagged | VAL-9 |
| T18 | Continue despite errors leaves out rows with Error-level issues. In a duplicate group, the first occurrence is kept and later ones are left out | RUN-4 (changed) |
| T19 | Left-out rows are stored with the run and can be exported | RUN-10, EXP-1 (changed) |
| T20 | The totals check is a reconciliation, Input = Loaded + Left out, all calculated in DuckDB | RUN-6 (changed) |
| T21 | A default output with a relative date filter, on a run with no dates in that column, gives an empty result with the note "No dates in this run" | DO-3, DO-5 |
| T22 | Run IDs count up per template and are never reused | RUN-2 |
| T23 | Contains ignores case. Count counts non-blank values only. Sorting a result with subtotals sorts within each parent group. A removed column in a saved analysis keeps working, labelled "(removed)" | ANA-4, ANA-6, ANA-7, ANA-1 |
| T24 | V3-1, V3-2 and V3-4 confirmed as designed under Query layer | V3, O11 |
| T25 | Default data folder `%LOCALAPPDATA%\Sankalan\Data`. Change… refuses network paths and warns for OneDrive folders | UX-11, ENV-5 |
| T26 | Uninstalling asks whether to delete the data folder | SEC-6 |
| T27 | This spec is kept as a live doc, with a copy in the Sankalan project | — |

## Architecture

One app process holds the window and the only DuckDB connection. Every long operation runs as a Job on a background thread, and file reading is handed to worker processes (T5, T6).

&#91;embedded content: process model C · one app process, reader workers, data folder\]

The window starts Jobs; a Job either queries DuckDB through the query layer or hands files to reader workers, whose staged text DuckDB then reads.

| Part | Runs in | Does | Never does |
| --- | --- | --- | --- |
| Window | Main thread | Draws screens and talks to Jobs through their progress and cancel interface | Touches DuckDB or input files |
| Job runner | Background thread, one Job at a time | Load, validate, outputs, commit, query, export, delete, moving the data folder | Run a second long Job |
| Query layer | Inside Jobs | All SQL, through one module (see Query layer) | — |
| DuckDB | App process | Catalogue, staging and run data | Open the data from another process |
| Reader workers | Separate processes started with spawn, as many as the smaller of file-and-sheet count and CPU cores − 1 | Probe and read one file and sheet each, write raw staged text | Open the database |

**Jobs.** Each Job has states running, cancelling, done and failed. It reports its stage, rows done of total, and time elapsed, and it has `cancel()`. Every progress panel and dialog (UI-5) talks only to this interface.

**Cancel.**

- DuckDB work: `interrupt()` on the Job's own cursor.
- Reader workers: signalled to stop, then stopped after 2 seconds, and their partial files deleted.
- Progress: DuckDB's query progress, checked every 250 ms, or rows read reported by the workers.

**DuckDB settings.**

- `memory_limit` = 50% of RAM, `threads` = logical cores, `temp_directory` = `%TEMP%\Sankalan`. The temp folder is emptied at start-up and when each Job ends.
- Extensions: none are loaded. Auto-install and auto-load are off, community extensions are disallowed, and the configuration is locked after start-up (SEC-1).

**One copy of the app.** Starting Sankalan again brings the open window to the front.

**Closing.**

- While a Job that can be cancelled is running: "Cancel \[operation\] and close?".
- During a commit: closing waits until the commit finishes.
- At start-up: leftover staging is deleted (see Storage).

## Storage

Each committed run is a folder of Parquet files, and a small DuckDB catalogue records which runs exist. The catalogue row is the commit point, so a half-written run is never visible (T8).

**Data folder.** The default is `%LOCALAPPDATA%\Sankalan\Data` (T25). Its location is stored in `%LOCALAPPDATA%\Sankalan\settings.json`. Folders are named by internal ID, so renaming a client or template never moves files.

```
<data folder>\
  catalogue.duckdb                    clients, templates, runs, saved analyses
  catalogue-backups\                  last 5 copies, taken at app start (T10)
  _staging\<job-id>\                  the run in progress, emptied at start-up (T9)
      raw\<file-sheet-id>.csv         raw text from the reader workers
      data.parquet                    rows to load
      left_out.parquet                rows left out on override, with reason
      issues.parquet                  full issue list
      outputs\<n>.parquet             default output results
  t\<template-id>\runs\<run-id>\      the same files after commit (raw\ removed)
```

**Stable column IDs.** Parquet columns are named by permanent IDs (`c001`, `c002`, …), never by display name.

- Renaming a column changes only the catalogue (MAP-8).
- A removed column stays in older files and is hidden.
- A new column reads as null in older runs, because files are read together by name (MAP-11).
- Types and decimal places never change after the first commit (MAP-12), so the files always match.

**Fixed columns in every data and left-out file.** `run_id`, `_src_file` (index into `run_file`), `_src_sheet`, `_src_row`. `left_out.parquet` also has `_reason` (the rule IDs that caused it).

**Catalogue tables.** Definitions are stored as JSON text and parsed in Python, so no DuckDB JSON extension is needed.

| Table | Holds |
| --- | --- |
| client | ID, name (unique) |
| template | ID, client, name, current version, created, modified |
| template\_version | Full snapshot of settings, columns, rules and default outputs at each save (TPL-7) |
| column | ID, template, name, type, decimal places, order, aliases, totals tick, removed flag |
| rule | Column, rule type, settings, severity |
| default\_output | Template, name, order, definition |
| run | Internal ID, Run ID (R-0001…), template, template version, loaded on, status, comment, rows read, loaded, left out (by reason), issue counts, run-only rule changes and aliases, totals |
| run\_file | Run, file name, path, size, modified, sheet, SHA-256, header row, rows read, hidden rows and sheets skipped, duplicate decision (RUN-7) |
| run\_issue\_count | Run, rule, file and sheet, errors, warnings (ISS-1) |
| run\_output | Run, output name, order, definition used, file |
| run\_id\_counter | Template, last Run ID number issued (T22) |
| saved\_analysis | Template, name, definition |
| schema\_version | Catalogue version for upgrades |

**Commit protocol (RUN-5).**

1. Flush every staged file to disk and delete `raw\`.
2. Rename `_staging\<job-id>\` to `t\<template-id>\runs\<run-id>\`. A rename on the same drive is all-or-nothing.
3. In one catalogue transaction, issue the Run ID and insert `run`, `run_file`, `run_issue_count` and `run_output`. This is the commit point.

**Delete protocol (RUN-9, TPL-4, TPL-2).** Remove the catalogue records in one transaction, then delete the folders.

**Start-up recovery.**

- Empty `_staging\`.
- Delete any run folder with no catalogue record.
- Mark any catalogue run whose folder is missing as damaged.

Queries only read runs listed in the catalogue.

**Figures on screen (UX-1, C4).** Rows stored is the sum of rows loaded in `run`. GB is the size of the data folder on disk. Free space is read from the drive.

**Changing the data folder (UX-11).** A Job copies everything, checks it, switches `settings.json`, then deletes the old folder. Network paths are refused (ENV-5), and folders inside OneDrive get a warning.

## Ingestion

Files go through four stages, from the Files step to typed rows in `_staging\<job-id>\data.parquet`. Re-check (VR-6) or a return to Mapping reruns stages 3 and 4.

1. **Probe** (Files step, reader workers). Builds the file list.
2. **Decide** (Mapping step, window). For each file and sheet, maps source header to template column ID, or leave as null.
3. **Read** (Validate step, reader workers in parallel). Writes one raw text file per file and sheet.
4. **Convert** (Validate step, DuckDB). Writes the typed rows.

### 1. Probe (IN-1 to IN-15)

| Check | How |
| --- | --- |
| Lock files, the same file twice (IN-10) | Skipped by name and resolved path; listed as skipped |
| File type | Read from the content: ZIP with `xl/workbook.xml` → .xlsx or .xlsm, with `xl/workbook.bin` → .xlsb; Office container (OLE) with a `Workbook` stream → .xls; encrypted Office container (`EncryptionInfo` stream, or an .xls with a `FILEPASS` record) → password-protected, an error (IN-9); an Excel 5.0/95 workbook (`Book` stream only) → an error asking to save it as .xlsx; text named as a workbook and starting with `<` (a web page or XML saved with an Excel name) → an error asking to save it as .xlsx; other text → CSV |
| File can't be opened (IN-15) | A sharing violation becomes "…is open in another program. Close it, then Re-check" |
| Sheets to read (IN-5, IN-13) | Sheet list with visibility from calamine; hidden sheets listed as skipped |
| Header row (IN-6) | V1 header detection on the first rows of each sheet |
| CSV encoding and delimiter (IN-4) | V1 detection on the first 64 KB; the template's setting overrides it |
| Row count (IN-11) | Excel: the sheet's dimension record. CSV: a fast line count. Approximate until stage 3, which gives the exact count |
| Duplicate contents (RUN-7) | SHA-256 of the file, compared with `run_file` |
| Header match (TPL-6) | All headers match → the Mapping step is skipped |

### 3. Read

- **Excel (T11).** python-calamine reads the values; formulas give their last calculated values, and error cells (`#N/A`, `#REF!`) are read as text. A separate scan collects hidden rows and error cells, which calamine doesn't report: for .xlsx/.xlsm the decompressed sheet XML (rows with `hidden="1"`), for .xlsb the sheet's records (`BrtRowHdr` hidden flag, `BrtCellError`/`BrtFmlaError`), for .xls the sheet's BIFF8 records in the `Workbook` stream (`ROW` hidden flag, `BOOLERR`, `FORMULA` with an error result). Hidden rows are dropped and counted (IN-13).
- **CSV (T12).** Read with Python's `csv` module. Windows-1252 is converted to UTF-8 with the standard library. A single large CSV is read on one core, because a CSV can't be split safely when values may contain line breaks.
- **Raw staging format.** UTF-8 CSV, one file per file and sheet, with `_src_row` first and every value as text in one standard form:
  - numbers: the shortest exact decimal, never in exponent form
  - Excel dates: `YYYY-MM-DD`
  - text: exactly as typed
- **Blank rows (IN-8).** Rows where every cell is blank are dropped and counted. Blank means empty or only spaces (T14).
- **Cancel.** As in Architecture; `_staging\<job-id>\` is deleted and the screen returns to Mapping.

### 4. Convert (MAP-9, MAP-10)

One `SELECT` per file and sheet lines its columns up by mapping onto column IDs (missing → null). They are joined with `UNION ALL`, converted, and written to `data.parquet`.

| Type | Rule |
| --- | --- |
| Text | Kept exactly as typed. Empty or only spaces → blank (T14) |
| Number | Remove `₹`, spaces and `,` grouping (Indian or international); `(1,234)` → −1234; convert to DECIMAL(38, d) with the column's decimal places, rounded half away from zero (T13). Not readable → null; the original text goes to the issue list |
| Date | ISO from Excel dates, or the template's format for text dates (DD-MM-YYYY or DD/MM/YYYY); any time of day is dropped. Not readable → null; the original text goes to the issue list |

The raw staged text stays until commit, because the input side of the totals check reads it (T20).

## Validation and issues

Every rule becomes a SQL condition, and one scan of `data.parquet` marks which rules each row fails. Unique within the run takes one extra grouping pass over its key columns.

**Rule meanings (T16).** Blank means empty or only spaces. "Skipped" means a blank cell can only fail Not blank.

| Rule | Allowed on | Passes when | Blank cells |
| --- | --- | --- | --- |
| VAL-1 Not blank | Any type | The cell is not blank | Fail |
| VAL-2 Is a number | Number (added automatically, VR-7) | The text converts to a number | Skipped |
| VAL-3 Number range | Number | min ≤ value ≤ max, both inclusive; "Not negative" = value ≥ 0; compared after rounding to the column's decimal places | Skipped |
| VAL-4 Is a date | Date (added automatically, VR-7) | The text converts to a date | Skipped |
| VAL-5 Date range | Date | from ≤ date ≤ to, both inclusive | Skipped |
| VAL-6 Allowed values | Text, Number | Text: equals a listed value ignoring case, spaces counting. Number: equal in value (18 = 18.00) | Skipped |
| VAL-7 Text length | Text | Character count of the value as typed, spaces included: exactly, at least or at most N | Skipped |
| VAL-8 Character pattern | Text | Same length as the pattern; `A` = letter A–Z of either case, `9` = digit, any other character matches exactly. Turned into a regular expression internally | Skipped |
| VAL-9 Unique within the run | Any types, 1 or more key columns | No other row in the run has the same key; every row in a duplicate group is flagged, and the message names the first occurrence (T17) | Rows with a blank key column are skipped |

**Issues file.** One row per failure in `issues.parquet`: file, sheet, source row, column ID, rule ID, severity, and the value as typed. For values that failed conversion, this is the only place the original text is kept. Counts per rule and per file and sheet go to `run_issue_count` at commit (ISS-1).

**Run-only rule changes (VR-5).** Editing rules for this run reruns only the validation scan. "Save to template" saves a new template version (TPL-7). The run records its template version plus run-only changes, which the run summary shows (RUN-12).

**Testing rules (VR-8).**

- New template wizard: the 100,000 sample rows go through the same reading and conversion code into a temporary in-memory database, so wizard counts behave exactly like a run. The first 20 failing rows are kept for Show.
- Test rules on latest run: runs the scan on the latest committed `data.parquet` and returns counts only. Values that failed conversion are stored blank, so they count as blank there.

**Issue grid (ISS-2).** Up to 10,000 issues per rule, ordered by file, sheet and row, fetched in pages as the grid scrolls. Filter and sort work within those rows.

**Issue export (ISS-3).** Columns: File, Sheet, Row, Column, Value, Rule, Severity, Message. Message uses the UI-6 wording, e.g. "Sales\_Oct.xlsx, Sales, row 214, Taxable Value: value is not a number".

## Outputs, totals check and commit

All slow work happens before the Commit button, where it can still be cancelled. The commit itself is a rename plus one catalogue transaction, about a second, and can't be cancelled (RUN-5).

**Leaving the Validate step.** On Next, or on Continue despite errors (RUN-4, T18), one cancellable Job splits the staged rows:

- `data.parquet` keeps the rows to load: every row except those with Error-level issues and the later rows of duplicate groups. In each duplicate group, the first occurrence in file, sheet and row order is kept.
- `left_out.parquet` gets the excluded rows, with `_reason`.
- Warning-level issues never leave a row out.
- When nothing is left out, no rewrite happens.
- The override dialog states the count, e.g. "1,204 rows with errors will be left out".

**Default outputs (DO-1 to DO-8).**

| Item | Design |
| --- | --- |
| Definition | Stored as structured JSON and turned into SQL by the same compiler as Analysis |
| Input | This run's `data.parquet` only (DO-2); left-out rows are excluded |
| Relative dates (DO-3) | The calendar month, quarter or year containing the latest date in the chosen Date column. No dates in the column → an empty result with the note "No dates in this run" (T21) |
| Columns left as null (MAP-6) | Grouped under "(Null)" |
| Running (DO-4, DO-5) | One Job with a status per output. Cancel interrupts the running output; it and any not started show Retry. Next is enabled only when all are done |
| Stored (DO-6) | `outputs\<n>.parquet`, plus the definition used in `run_output` |
| Subtotals (DO-7) | Calculated with every level (`ROLLUP`) and marked by level, so subtotals of Average and Count distinct are correct; Show subtotals only hides or shows those rows |

**Totals check (RUN-6, T20).** For each column ticked for the totals check, all three totals are calculated in DuckDB when the Commit step opens, and shown on the Commit screen.

| Total | From |
| --- | --- |
| Input | The raw staged text, converted with the column's rules and rounded per value to its decimal places; values that can't be read count as 0 |
| Loaded | `data.parquet`, read back from disk |
| Left out | `left_out.parquet` |

The check passes when Input = Loaded + Left out, exactly. Hidden rows are never read, so they appear in no total. A mismatch blocks the commit, with no override.

**Commit button enabled when:**

- the totals check passes
- every default output has finished
- the comment is filled in for an overridden run (RUN-13)
- there is enough free disk space

**Commit Job.**

1. The commit protocol under Storage: flush, rename, one catalogue transaction.
2. The Run ID is issued in that transaction: next number per template, never reused (T22).
3. The Run screen (C6) opens with a success banner.

## Query layer, analysis and export

Every read of data goes through one query module; screens never write SQL (V3-1). An analysis reads only the ticked runs: `read_parquet([data.parquet of each ticked run], union_by_name = true)`, which fills columns missing from older runs with null. Left-out rows are in their own file, so they are never part of an analysis.

| Entry point | Used by |
| --- | --- |
| `run_definition(spec, runs)` | Analysis (ANA), default outputs (DO), testing rules on the latest run |
| `distinct_values(column, runs, search)` | The "Is one of" picker (ANA-4) |
| `export(source, options)` | Every export (EXP) |
| `select_only(sql)` | Reserved for V3. Accepts exactly one statement that DuckDB's parser classifies as SELECT (V3-4) |

**Definition to SQL.**

| Part | SQL |
| --- | --- |
| Date filters | Year, quarter or month is (calendar) → a date range; Between → `>=` and `<=`; Blank and Not blank → `IS NULL` and `IS NOT NULL` |
| Text filters | Is one of → `IN (…)`, exact; Contains → ignores case (T23); Blank and Not blank, where blank includes only-spaces values |
| Number filters | Equals and Between, at the column's decimal places |
| Group levels | In order; date grain → `date_trunc` to day, month, quarter or year; blank → "(Null)" |
| Measures | Sum, Count (non-blank values, T23), Count distinct, Average (shown and exported at the column's decimal places), Min, Max |
| Subtotals and grand total | `ROLLUP` over the group levels, marked by level; the grand total row is pinned |

**Results (ANA-7, ANA-8).**

- The full result goes into a temporary DuckDB table, which can spill to disk.
- The grid fetches pages as it scrolls and shows the first 100,000 rows, with a note when there are more.
- Sorting a header re-queries the table. With subtotals on, rows sort within each parent group (T23).
- Export copies from the table, so nothing is recalculated.
- Cancel calls `interrupt()`, and the previous result is greyed.

**Distinct values (ANA-4).** Top 1,000 values by count over the ticked runs, plus search across the whole column. Runs as a short Job inside the dropdown, with a spinner and Cancel.

**Saved analyses (ANA-1, V3-2).** Stored as JSON, for example `{template_id, filters:[{column_id, op, values}], groups:[{column_id, grain}], measures:[{column_id, fn, label}], subtotals}`. Runs are not stored (D33). Columns are referenced by ID, so renames are safe; a removed column keeps working, labelled "(removed)" (T23).

**Exports (EXP-1 to EXP-7).** All use DuckDB `COPY … TO` with the chosen delimiter, `DATEFORMAT '%d-%m-%Y'`, numbers at the column's decimal places with no grouping, and display names as headers.

| Export | Columns |
| --- | --- |
| A run's data | Template columns + Source File, Source Sheet, Source Row, Run ID (EXP-6) |
| Left-out rows (T19) | The same + Reason |
| Issue list | File, Sheet, Row, Column, Value, Rule, Severity, Message |
| Default outputs and analysis results | The full stored or temporary result, subtotal rows included when shown |

- **UTF-8 with BOM (EXP-3).** DuckDB's COPY always writes UTF-8 without a BOM. The export writes `<name>.part`, then streams it into the final file after the 3 BOM bytes, and deletes the part file. Plain UTF-8 renames the part file instead.
- **Cancel (EXP-7).** Deletes the `.part` file.
- **File names.** Characters Windows doesn't allow in file names are replaced with `_`. Overwriting needs confirmation (EXP-4).

**V3 readiness (O11).** V3-1 is met by the query module and plain Parquet plus a DuckDB catalogue. V3-2 is met by definitions stored as JSON. V3-4 is met by `select_only`. Full hardening for an agent, such as blocking file-reading table functions, is left to V3.

## Packaging and security

Sankalan ships as a signed per-user installer with three compiled packages besides Python. Every compiled file in it is signed, so it runs on laptops with Smart App Control on (T2, T3).

**Runtime dependencies (pinned in `requirements-lock.txt`).**

| Package | Why | Signing |
| --- | --- | --- |
| Python 3.13 (bundled by PyInstaller) | Runtime | Already signed by its publisher |
| PySide6-Essentials, shiboken6 | Window toolkit | Already signed by its publisher; any unsigned file is signed by us |
| duckdb 2.0.x (LTS line) | Storage and queries | Signed by us |
| python-calamine | Excel reading | Signed by us |

Dropped from V1: XlsxWriter, xlrd, xlwt, msoffcrypto-tool, cryptography, olefile, cffi, pycparser. No pandas, numpy or pyarrow. Development only: pytest, pytest-qt, PyInstaller, and XlsxWriter for generating large test files.

**Build** (`packaging\build_windows.bat`, on the Windows PC with the certificate's USB token).

1. Run all tests.
2. PyInstaller build in a folder layout, not a single exe.
3. `sign_files.ps1` signs every unsigned `.exe`, `.dll` and `.pyd` with the RSA certificate. Smart App Control doesn't accept ECC signatures. Each signature is timestamped by the CA's timestamp server, so the build PC needs internet while signing. The app itself stays offline.
4. Self-test of the built app.
5. A per-user NSIS installer, also signed.

**Reader workers.** Reader workers are `Sankalan.exe` started again in worker mode (`multiprocessing.freeze_support()`). Because it's the same signed exe, Smart App Control allows them.

**Install, update, uninstall.**

- Install to `%LOCALAPPDATA%\Programs\Sankalan`, with no admin rights (NF-2).
- An update is a new installer run over the old one (SEC-6). At the first start after an update, the catalogue is backed up, then upgraded by `schema_version`. Parquet files are never rewritten.
- Uninstall asks whether to delete the data folder (T26).

**Offline and data handling (SEC-1 to SEC-7).**

- No network code. DuckDB extensions are switched off and the configuration is locked (Architecture).
- Source files are opened read-only (SEC-2).
- Spill files live in `%TEMP%\Sankalan`; the run being staged lives in `_staging` (T9). Both are emptied when the operation ends and at start-up.
- The log is in `%LOCALAPPDATA%\Sankalan\logs\`, rotated. It records the operation, the file name and the error class only. DuckDB error message text is never logged, because it can contain cell values (SEC-5).

## Tests and release acceptance

The automated suite runs on every build. The performance suite and a Smart App Control check run once before release, on a 16 GB, 4-core laptop (T4).

| Test | Checks | Source |
| --- | --- | --- |
| No network code | Static scan of imports; a full run with the network blocked (SEC-1, SEC-7) | V1 |
| Sources unchanged | File hashes before and after a run (SEC-2) | V1 |
| No leftovers | Temp and `_staging` empty after each Job and after a restart (SEC-4) | V1, extended |
| No cell values in the log | Marker values planted in test files are searched for in the log (SEC-5) | V1 |
| Allowed compiled packages | Only the packages in the dependency table load | V1, updated |
| Crash during commit | Process killed at each commit step; after a restart only committed runs exist and no extra folders remain | New |
| Conversion values | ₹, Indian grouping, brackets, rounding to each decimal setting, both date formats, Excel dates | New |
| Rule meanings | Every row of the rule table, including blanks and duplicate groups | New |
| Totals reconciliation | Input = Loaded + Left out across error, duplicate, hidden and blank cases | New |
| Columns across runs | Add, remove and rename across runs; null in older runs; "(removed)" in saved analyses | New |
| Export | BOM bytes, delimiters, DD-MM-YYYY dates, `.part` deleted on Cancel | New |
| Screen fit (UI-2) | Every screen at 1366×768 at 100%, and at 1920×1080 at 125% and 150%: the window never scrolls | New |
| Self-test after install | Small pipeline; DuckDB and calamine load; signatures checked with `Get-AuthenticodeSignature` | V1, extended |
| Performance suite (release only) | Generated data: PERF-1 (10M rows from CSV), PERF-2 (10M rows from 10 .xlsx), PERF-3 to PERF-6 over 12 runs and 120M rows. Misses are reported, not blocking | New |
| Smart App Control (release only) | The signed installer installs and runs on a laptop with Smart App Control on | New |

## Feature spec changes

Feature Spec v2.0 needs 21 updates to match this spec. Three of them change screens on the design canvas: 2.3, 3.3 and 4.5, plus a new menu item on 3.1 and 5.1.

| Feature item | Change | From |
| --- | --- | --- |
| TPL-1, MAP-10 | Number columns gain Decimal places (0 to 6, default 2); extra decimals are rounded half away from zero, silently | T13 |
| TPL-9, MAP-12 | Decimal places are fixed after the first committed run, like the type | T13 |
| Screens 2.3, 3.3 | A Decimals field on Number columns | T13 |
| MAP-9, VAL-1 | A cell that is empty or only spaces is blank; other spaces are kept as typed | T14 |
| IN-11 | Row counts on the Files step are approximate until Validate reads the file | Ingestion |
| RUN-4 | Continue despite errors leaves out rows with Error-level issues; in a duplicate group the first occurrence is kept. The override dialog states how many rows will be left out | T18 |
| RUN-6, screen 4.5 | Totals check: Input = Loaded + Left out per ticked column, all three shown on the Commit step | T20 |
| RUN-10, UX-9, screens 3.1 and 5.1 | New action: Export left-out rows | T19 |
| EXP-1 | Add left-out rows (columns + Reason) to what can be exported | T19 |
| RUN-12 | Rows left out broken down into blank rows, rows with errors, and later duplicates | T18 |
| RUN-2 | Run IDs count up per template and are never reused | T22 |
| DO-3 | No dates in the run → an empty result with "No dates in this run", not a failure | T21 |
| VAL-6, VAL-8, VAL-9 | Allowed values ignores case and also applies to Number columns; pattern `A` matches either case; Unique within the run skips rows with a blank key and flags every row in a group | T16, T17 |
| ANA-4, ANA-6, ANA-7, ANA-1 | Contains ignores case; Count counts non-blank values; sorting with subtotals stays within each parent group; a removed column in a saved analysis is labelled "(removed)" | T23 |
| TPL-5, UX-11 | Default data folder `%LOCALAPPDATA%\Sankalan\Data`; Change… refuses network paths and warns for OneDrive | T25 |
| SEC-4 | Spill files in the user's temp folder; the run being staged in the data folder's `_staging` area; both deleted when the operation ends and at start-up | T9 |
| SEC-6 | Uninstalling asks whether to delete the data folder | T26 |
| NF-7, O10 | Signed per-user installer; O10 closed | T2, T3 |
| NF-8, D18 | DuckDB 2.0 LTS confirmed; python-calamine for Excel | T2, T11 |
| PERF-2, NF-9, O9 | PERF-2 = 5 minutes or less (provisional); disk use per run measured by the performance suite; O9 closed by the release acceptance test | T4, T15 |
| V3-1, V3-2, V3-4, O11 | Confirmed; O11 closed | T24 |

The catalogue backups (T10) are a new behaviour with no screen.

## Risks and open items

The largest risk is the certificate: until it arrives, nothing can be tested on a laptop with Smart App Control on. Performance targets PERF-2 and PERF-5 are the least certain, because no benchmark was run.

| # | Risk or open item | Impact | Plan |
| --- | --- | --- | --- |
| R1 | Code-signing certificate not yet bought (RSA, OV, Ollyver Analytics Pvt Ltd) | Without it, DuckDB and calamine may be blocked on executives' laptops | Being arranged by Chetan. Development runs on a PC with Smart App Control off; release requires the Smart App Control test |
| R2 | PERF-2: Excel reading speed is unmeasured | 10M rows from .xlsx may take longer than 5 minutes | Measure in the first build; the target is provisional |
| R3 | PERF-5: about 1M groups across 120M rows with Count distinct and subtotals, under an 8 GB memory cap | Heavy spilling to disk; may miss 60 s | Release performance suite; it is reported, not blocking |
| R4 | One 10M-row CSV is read on a single core | Could approach the PERF-1 limit of 2 minutes | Measure in the first build |
| R5 | python-calamine reports no hidden rows | Hidden rows would be loaded by mistake | A separate XML or record scan (T11), covered by tests with hidden rows in .xlsx, .xlsb and .xls |
| R6 | Data folder inside a synced or network folder | Sync conflicts or damaged files | Default outside OneDrive; Change… refuses network paths and warns for OneDrive (T25) |
| O12 | The customer has not confirmed that client data may be kept on the laptop unencrypted (SEC-3) | Could require encryption, which is out of scope today | Open, carried over from Feature Spec v2.0 |
