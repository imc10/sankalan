# Sankalan — Technical Spec (v1.0)

Nov 16, 2026 · @Chetan Mundhada

**A2 (Feature-Updates) folded in 22-11-2026; Technical Spec A2 (`docs/specs/technical-spec-a2.md`) holds the detail.** It adds decisions T32–T56 and T67 and changes the sections below, each marked **Changed** or **Added** 22-11-2026 (A2). Behaviour is in Feature Spec A2 (`docs/specs/feature-spec-a2.md`); where the two differ, Technical Spec A2 wins (its section 15.1).

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

**Added** 22-11-2026 (A2): T32–T56 and T67 come from Technical Spec A2 section 2 (21-11-2026; those marked Answered were settled with the user). Section references (§) in those rows point to Technical Spec A2. T28–T31 are not used here: Feature Spec A2 cites them from a newer live copy of this spec, and their A2 changes (text in Number and Date columns, Is not a date, "(Not a date)", Count distinct rules, the Load step) are carried by T23, T41, T42, T44 and T55. Technical Spec A1's T28–T44 are superseded. T57–T66 are left unused.

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
| T23 | Contains ignores case. Count counts non-blank values only. Sorting a result with subtotals sorts within each parent group. A removed column in a saved analysis keeps working, labelled "(removed)". **Changed** 22-11-2026 (A2): Count includes text kept in Number and Date cells (TXT-8); the Rows card counts every row (MEA-10); Count distinct isn't offered on Number columns and counts dates only on Date columns (D70) | ANA-4, ANA-6, ANA-7, ANA-1, MEA-5, MEA-10 |
| T24 | V3-1, V3-2 and V3-4 confirmed as designed under Query layer | V3, O11 |
| T25 | Default data folder `%LOCALAPPDATA%\Sankalan\Data`. Change… refuses network paths and warns for OneDrive folders | UX-11, ENV-5 |
| T26 | Uninstalling asks whether to delete the data folder | SEC-6 |
| T27 | This spec is kept as a live doc, with a copy in the Sankalan project | — |
| T32 | Stored order is made true at Convert: `data.parquet` is written `ORDER BY _src_file, _src_row`, and every stored-order read (Rows grid fetch; run data, left-out rows and Rows view exports) adds the same `ORDER BY` on one run's file at a time. Nothing relies on DuckDB's unstated row order (Technical Spec A2 §2, §5.2) | ROW-12 |
| T33 | DuckDB writes each export chunk, with no header, to `%TEMP%\Sankalan`; Python streams the chunks into the parts in the chosen folder, writing the BOM and header into each part. No rename shortcut (§8.2) | EXP-8 |
| T34 | The free-space check covers two drives: the temp drive needs the largest chunk plus a margin, the destination the whole export plus a margin; on one drive the needs add up (§8.4) | EXP-13 |
| T35 | Parts are written as `<final name>.partial`. Finish renames files being replaced to `.replaced`, renames the parts into place, then deletes the `.replaced` files; any failure renames them back. Finish can't be cancelled (§8.2) | EXP-14 |
| T36 | Before writing and again before finishing, every file to be replaced is opened for writing; if it is open elsewhere: "\<file> is open in another program. Close it, then export again." (§8.2) | EXP-10, EXP-14 |
| T37 | Part size is `PART_ROWS = 1_000_000` in `sankalan/exporting.py`; tests pass a smaller value, the app never changes it (§8.3) | EXP-9 |
| T38 | **Answered.** The grand total stays the last row of a result export; when split, the last row of the last part (§8.1) | EXP-12 |
| T39 | **Answered.** A result with group levels and no measures lists each group combination once, with no subtotal or grand total rows; Show subtotals is disabled (§9.4) | MEA-11 |
| T40 | **Answered (D77).** Catalogue schema version 2, created whole for a new data folder, with no upgrade code; a version-1 catalogue (test builds only) is refused at start-up (§12) | Storage |
| T41 | Text companions are written by Convert into `data.parquet` and carried into `left_out.parquet` by the split. `conversion_failures.parquet` is retired; Is a number and Is a date issues read the companions (§5.1) | TXT-1, TXT-13 |
| T42 | Result tables get a kind column `k1…kn` beside each group value `g1…gn` (0 value, 1 text, 2 blank); grouping is `ROLLUP((k1, g1), …)`; sorting orders by kind first (P8 confirmed) (§5.6) | TXT-10, TXT-11 |
| T43 | Check data before loading is held in the template's `settings` JSON (`"checks"`), not a new column; the run stores the value it used (`run.checks`) (§6.1) | NCK-1, NCK-12 |
| T44 | A run's third step is Validate or Load, chosen from `RunSession.checks` when the wizard starts; the step bar always has five steps. Load runs one Job: Read, Convert and the text-value summary, with no scan and no split (§6.4, §6.5) | NCK-6, NCK-7 |
| T45 | **Answered.** For a run without checks, Rows read includes blank rows; Rows left out is 0 ("None"); Load, Commit and the Run summary add "Blank rows skipped: N"; Rows loaded = Rows read − blank rows (§6.7) | NCK-4, NCK-8, NCK-9 |
| T46 | **Answered.** Choose sheets is offered on .xlsx, .xlsm, .xlsb and .xls files (§7.2) | SHT-2 |
| T47 | Probe returns every Excel file's sheet list (name, visible, approximate rows). A file whose sheets don't satisfy the rule or the choice is **one** error row (`problem = "sheet"`) naming its visible sheets (§7.1) | SHT-4, SHT-6 |
| T48 | A Rows view result is a temporary table `_rows_<uuid>` with a sequence column `_seq`, filled per run with one `ORDER BY _src_file, _src_row LIMIT <rows still needed>` and dropped like analysis results (§10.3) | ROW-3, ROW-11 |
| T49 | Measures are held as cards (a column and its ticked operations) in memory and in definition JSON version 2; the compiler works on the flattened list in MEA-6 order; only version 2 is read (§9.1) | MEA-1 to MEA-6 |
| T50 | Each committed run keeps its outputs' headers in `run_output.headers` (JSON list, group headers included); the Outputs tab and exports read them, and they never change after commit (§9.5) | MEA-9, DO-6 |
| T51 | One header widget, `RenamableHeader`, gives the ✎ rename to the analysis grid and both Default outputs previews (§9.7) | MEA-8 |
| T52 | `PagedGrid` gains an optional frozen first column; in the Rows view, header clicks do nothing and no sort arrow is drawn (§10.5) | ROW-11 |
| T53 | Job progress gains a detail line (`ctx.set_detail("part 2 of 3")`) shown under the stage (§8.5) | EXP-11 |
| T54 | **BUG-1.** After a Job, `%TEMP%\Sankalan` is emptied except files named `duckdb_temp_<this process's PID>_*`; closing the data folder and start-up still empty it completely (§11) | SEC-4 |
| T55 | Is not a number and Is not a date are offered wherever Blank is: Analysis, the Rows view and default outputs; stored as filter ops `not_number` and `not_date` (§5.8) | TXT-6, TXT-7 |
| T56 | `run.text_counts` holds, per Number and Date column, the count of text values in the run's loaded rows, computed in the commit Job for every run (§5.7, §12.1) | NCK-9 |
| T67 | **Answered.** The repository's D38 (.xls and .xlsb input) becomes D81 in Feature Spec v2.0 and `docs/PROGRESS.md` (§1) | IN-3 |

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

**Jobs.** Each Job has states running, cancelling, done and failed. It reports its stage, rows done of total, and time elapsed, and it has `cancel()`. Every progress panel and dialog (UI-5) talks only to this interface. **Changed** 22-11-2026 (A2): progress also carries an optional detail line (`ctx.set_detail(…)`, e.g. "part 2 of 3"), shown under the stage by the progress panel (T53, EXP-11).

**Cancel.**

- DuckDB work: `interrupt()` on the Job's own cursor.
- Reader workers: signalled to stop, then stopped after 2 seconds, and their partial files deleted.
- Progress: DuckDB's query progress, checked every 250 ms, or rows read reported by the workers.

**DuckDB settings.**

- `memory_limit` = 50% of RAM, `threads` = logical cores, `temp_directory` = `%TEMP%\Sankalan`. The temp folder is emptied at start-up and when each Job ends. **Changed** 22-11-2026 (A2, BUG-1): when a Job ends, the open connection's own spill files (`duckdb_temp_<this process's PID>_*`) are kept, because DuckDB may still use them in the next Job and deletes them itself; start-up and closing the data folder still empty the folder completely (T54).
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
      data.parquet                    rows to load, sorted by _src_file, _src_row (T32)
      left_out.parquet                rows left out on override, with reason (runs with checks only)
      issues.parquet                  full issue list (runs with checks only)
      outputs\<n>.parquet             default output results
  t\<template-id>\runs\<run-id>\      the same files after commit (raw\ removed)
```

**Changed** 22-11-2026 (A2): there is no `conversion_failures.parquet`; the text of cells that don't convert is kept in companion columns (T41). A run without checks writes no `issues.parquet` or `left_out.parquet` (T44).

**Stable column IDs.** Parquet columns are named by permanent IDs (`c001`, `c002`, …), never by display name.

- Renaming a column changes only the catalogue (MAP-8).
- A removed column stays in older files and is hidden.
- A new column reads as null in older runs, because files are read together by name (MAP-11).
- Types and decimal places never change after the first commit (MAP-12), so the files always match.

**Fixed columns in every data and left-out file.** `run_id`, `_src_file` (index into `run_file`), `_src_sheet`, `_src_row`. `left_out.parquet` also has `_reason` (the rule IDs that caused it).

**Text companions (Added 22-11-2026, A2; T41, TXT-1).** Every Number and Date column `cNNN` has a companion `cNNN_t VARCHAR` in every `data.parquet` and `left_out.parquet`. It holds the cell's text exactly as staged, only where the cell isn't blank and doesn't convert; on every other row it is null, so `cNNN` and `cNNN_t` are never both filled. A column with no source in a file (MAP-6) or added after an older run (MAP-11) is null in both. Text columns have no companion. Detail: Technical Spec A2 §5.1.

**Row order (Added 22-11-2026, A2; T32).** `data.parquet` is written sorted by `_src_file, _src_row`, which is the stored order the Rows view and run data exports read back.

**Catalogue tables.** Definitions are stored as JSON text and parsed in Python, so no DuckDB JSON extension is needed.

| Table | Holds |
| --- | --- |
| client | ID, name (unique) |
| template | ID, client, name, current version, created, modified; settings JSON, which holds `"checks"` (Check data before loading, A2: T43) |
| template\_version | Full snapshot of settings (`checks` included), columns, rules and default outputs at each save (TPL-7); rules are kept when checks is No |
| column | ID, template, name, type, decimal places, order, aliases, totals tick, removed flag |
| rule | Column, rule type, settings, severity |
| default\_output | Template, name, order, definition (version-2 measures, A2: T49) |
| run | Internal ID, Run ID (R-0001…), template, template version, loaded on, status, comment, rows read, loaded, left out (by reason), issue counts, run-only rule changes and aliases, totals; A2: `checks` (as used by the run, T43) and `text_counts` (JSON column ID → count of text values in the loaded rows, every run, T56) |
| run\_file | Run, file name, path, size, modified, sheet, SHA-256, header row, rows read, hidden rows and sheets skipped, duplicate decision (RUN-7); A2: `sheets_chosen` (true when the sheets were chosen by hand; never shown, SHT-10) |
| run\_issue\_count | Run, rule, file and sheet, errors, warnings (ISS-1) |
| run\_output | Run, output name, order, definition used (version 2), file; A2: `headers` (JSON list of the resolved headers at commit, T50) |
| run\_id\_counter | Template, last Run ID number issued (T22) |
| saved\_analysis | Template, name, definition (version-2 measures, T49) |
| schema\_version | Catalogue version for upgrades. **Changed** 22-11-2026 (A2): version 2, created whole for a new data folder with the A2 fields above; there is no upgrade code, and a version-1 catalogue (made only by test builds) is refused at start-up with "This data folder was made by a test build of Sankalan and can't be opened by this version. Choose another folder, or create a new one.", leaving the folder unchanged (T40, Technical Spec A2 §12) |

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

1. **Probe** (Files step, reader workers). Builds the file list, with each Excel file's sheet list.
2. **Decide** (Files and Mapping steps, window). Which sheets each file reads: the template's rule, or the user's choice for that file in this run (SHT, A2). For each file and sheet, maps source header to template column ID, or leave as null.
3. **Read** (Validate step, or Load for a template without checks, T44; reader workers in parallel). Writes one raw text file per file and sheet.
4. **Convert** (Validate or Load step, DuckDB). Writes the typed rows.

### 1. Probe (IN-1 to IN-15)

| Check | How |
| --- | --- |
| Lock files, the same file twice (IN-10) | Skipped by name and resolved path; listed as skipped |
| File type | Read from the content: ZIP with `xl/workbook.xml` → .xlsx or .xlsm, with `xl/workbook.bin` → .xlsb; Office container (OLE) with a `Workbook` stream → .xls; encrypted Office container (`EncryptionInfo` stream, or an .xls with a `FILEPASS` record) → password-protected, an error (IN-9); an Excel 5.0/95 workbook (`Book` stream only) → an error asking to save it as .xlsx; text named as a workbook and starting with `<` (a web page or XML saved with an Excel name) → an error asking to save it as .xlsx; other text → CSV |
| File can't be opened (IN-15) | A sharing violation becomes "…is open in another program. Close it, then Re-check" |
| Sheets to read (IN-5, IN-13) | Sheet list with visibility from calamine; hidden sheets listed as skipped. **Changed** 22-11-2026 (A2): for every .xlsx, .xlsm, .xlsb and .xls file that opens, Probe returns the full sheet list (name, visible, approximate rows from the sheet's dimension, no header scan; T47). The sheets read are the user's choice for that file when there is one (`RunSession.sheet_choice`, path → names), else the template's rule. A named or chosen sheet that is missing or hidden puts the file in Sheet not found as **one** error row (`problem = "sheet"`) naming the visible sheets; Re-check keeps the choice; removing or excluding the file drops it. Detail: Technical Spec A2 §7 |
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
- **Cancel.** As in Architecture; `_staging\<job-id>\` is deleted and the screen returns to Mapping (A2: from the Load step, to Files when Mapping was skipped, NCK-7).

### 4. Convert (MAP-9, MAP-10)

One `SELECT` per file and sheet lines its columns up by mapping onto column IDs (missing → null). They are joined with `UNION ALL`, converted, and written to `data.parquet`. **Changed** 22-11-2026 (A2): the write is `ORDER BY _src_file, _src_row` (T32), each conversion is computed once per cell, and Number and Date columns also write their text companion; no failures file is written (T41). Detail: Technical Spec A2 §5.2.

| Type | Rule |
| --- | --- |
| Text | Kept exactly as typed. Empty or only spaces → blank (T14) |
| Number | Remove `₹`, spaces and `,` grouping (Indian or international); `(1,234)` → −1234; convert to DECIMAL(38, d) with the column's decimal places, rounded half away from zero (T13). Not readable and not blank → null, and the original text goes to the companion `cNNN_t` (A2, T41); with checks, Is a number reports it from there |
| Date | ISO from Excel dates, or the template's format for text dates (DD-MM-YYYY or DD/MM/YYYY); any time of day is dropped. Not readable and not blank → null, and the original text goes to the companion `cNNN_t` (A2, T41); with checks, Is a date reports it from there |

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

**Text cells (Added 22-11-2026, A2; TXT-13).** For a Number or Date column `c` with companion `c_t` (Technical Spec A2 §5.4):

| Rule | SQL |
| --- | --- |
| Is a number, Is a date | Fails where `c_t IS NOT NULL`; the issue's value is `c_t`. The failures CTE is a `UNION ALL` over the typed columns reading `data.parquet` |
| Number range, Date range, Allowed values | Unchanged: they test `c`, and the `c IS NOT NULL AND (…)` wrapper skips text like a blank, so a text cell gives exactly one issue (from the type rule) |
| Not blank | Fails where `c IS NULL AND c_t IS NULL` |
| Unique within the run | Key part per typed column `coalesce(CAST(c AS VARCHAR), c_t)`, so two "NA" cells are equal; blank keys are skipped as in VAL-9 above |
| Text length, Character pattern | Unchanged (Text columns) |

A template without checks runs no validation scan and writes no issues (T44).

**Issues file.** One row per failure in `issues.parquet`: file, sheet, source row, column ID, rule ID, severity, and the value as typed. Counts per rule and per file and sheet go to `run_issue_count` at commit (ISS-1). **Changed** 22-11-2026 (A2): the original text of values that failed conversion is also kept in the companions of `data.parquet` and `left_out.parquet` (T41).

**Run-only rule changes (VR-5).** Editing rules for this run reruns only the validation scan. "Save to template" saves a new template version (TPL-7). The run records its template version plus run-only changes, which the run summary shows (RUN-12).

**Testing rules (VR-8).**

- New template wizard: the 100,000 sample rows go through the same reading and conversion code into a temporary in-memory database, so wizard counts behave exactly like a run. The first 20 failing rows are kept for Show.
- Test rules on latest run: runs the scan on the latest committed `data.parquet` and returns counts only. Values that failed conversion are stored blank, so they count as blank there. **Changed** 22-11-2026 (A2): they are now read from the companions, so type failures are found in committed data; the wizard's dry run reads them the same way. Not offered while the template's checks are off (NCK-13).

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
- **Changed** 22-11-2026 (A2): the split carries the text companions into `left_out.parquet` (T41). A run without checks has no split: its Load Job writes `data.parquet` only, and its totals check is Input = Loaded (T44, NCK-5).

**Default outputs (DO-1 to DO-8).**

| Item | Design |
| --- | --- |
| Definition | Stored as structured JSON and turned into SQL by the same compiler as Analysis |
| Input | This run's `data.parquet` only (DO-2); left-out rows are excluded |
| Relative dates (DO-3) | The calendar month, quarter or year containing the latest date in the chosen Date column. No dates in the column → an empty result with the note "No dates in this run" (T21) |
| Columns left as null (MAP-6) | Grouped under "(Null)" |
| Running (DO-4, DO-5) | One Job with a status per output. Cancel interrupts the running output; it and any not started show Retry. Next is enabled only when all are done |
| Stored (DO-6) | `outputs\<n>.parquet`, plus the definition used in `run_output`. **Changed** 22-11-2026 (A2): stored outputs include the kind columns `k1…kn` (T42), so committed runs show the same "(Not a number)" / "(Not a date)" labels |
| Subtotals (DO-7) | Calculated with every level (`ROLLUP`) and marked by level, so subtotals of Average and Count distinct are correct; Show subtotals only hides or shows those rows. A2: an output with no measures has no subtotal or grand total rows (T39) |
| Column names and headers | **Added** 22-11-2026 (A2). Result columns are named internally `g1…gn` (group levels) and `m1…mk` (measures, in MEA-6 order); `resolve_headers()` gives the header text. At the Outputs step each output's resolved headers are returned, and the commit transaction stores them in `run_output.headers`; the Outputs tab and exports read them from there, so later renames never change a committed run (T50, MEA-9; Technical Spec A2 §9.3, §9.5) |

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

1. The commit protocol under Storage: flush, rename, one catalogue transaction. (A2: the Job also computes `run.text_counts` from the run's `data.parquet`, T56.)
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
| `count_rows(spec, columns, runs)` | **Added** (A2). Rows view match count (ROW-10): one `GROUP BY run_id` scan with the filters, per-run counts; with no filters, rows loaded from the catalogue (no scan) |
| `fetch_rows(spec, columns, runs, counts, table)` | **Added** (A2). Fills the Rows view table with the first 100,000 matching rows in stored order (ROW-11, T48) |
| `rows_page(table, first, count)` | **Added** (A2). A page of the Rows view table by a `_seq` range (PERF-9) |
| `export_source(spec, columns, runs, counts)` | **Added** (A2). Rows view export: one chunk per run with matches (ROW-12) |
| `text_counts(data, columns)`, `text_values(data, column)` | **Added** (A2). Count of text values per Number and Date column (one scan of the companions), and one column's values as typed, most frequent first, up to 1,000, with first file, sheet and row (NCK-3, NCK-8, NCK-9, T56) |
| `resolve_headers(definition, columns)` | **Added** (A2). Header text of every result column: defaults "\<Column> · \<Operation>", custom names, " (2)" for clashes, " (removed)" (MEA-7 to MEA-9) |
| `estimate(sources, folder, options)` | **Added** (A2). Export size, parts, names and free space on both drives (EXP-13, T34) |

Entry points and SQL in full: Technical Spec A2 §5.6, §5.7, §8, §9.3, §10.2. All run inside Jobs.

**Definition to SQL.**

| Part | SQL |
| --- | --- |
| Date filters | Year, quarter or month is (calendar) → a date range; Between → `>=` and `<=`; Blank and Not blank → `IS NULL` and `IS NOT NULL` |
| Text filters | Is one of → `IN (…)`, exact; Contains → ignores case (T23); Blank and Not blank, where blank includes only-spaces values |
| Number filters | Equals and Between, at the column's decimal places |
| Group levels | In order; date grain → `date_trunc` to day, month, quarter or year; blank → "(Null)" |
| Measures | Sum, Count (non-blank values, T23), Count distinct, Average (shown and exported at the column's decimal places), Min, Max |
| Subtotals and grand total | `ROLLUP` over the group levels, marked by level; the grand total row is pinned |

**Changed** 22-11-2026 (A2): for a Number or Date column `c` with companion `c_t` (TXT, T41, T42, T55; Technical Spec A2 §5.6, Feature Spec A2 8.8):

| Part | SQL |
| --- | --- |
| Equals, Between, Year / Quarter / Month is, relative dates | On `c` only, so text never matches (TXT-5, TXT-7, TXT-12) |
| Is not a number, Is not a date | `c_t IS NOT NULL` (ops `not_number`, `not_date`) |
| Blank / Not blank | `c IS NULL AND c_t IS NULL` / its negation |
| Count | `count(c) + count(c_t)` (TXT-8); Text columns `count(c)`; the Rows card `count(*)` (MEA-10) |
| Count distinct | Date: `count(DISTINCT c)`, text not counted; Text: `count(DISTINCT c)`; refused on Number columns (D70) |
| Sum, Avg, Min, Max | On `c` only |
| Group levels | `g_i` = `c` (or `date_trunc`), `k_i` = 0 value, 1 text, 2 blank; `GROUP BY ROLLUP((k1, g1), …)`; labels "(Not a number)", "(Not a date)", "(Null)" (T42) |
| Sorting | By `k_i` first, then `g_i` in the chosen direction: values, then text, then "(Null)" (TXT-11, P8) |
| Measures | Taken from the cards in MEA-6 order (`flat_measures()`); result columns `g1…gn`, `m1…mk` (T49) |
| No measures | Plain `GROUP BY` of the group keys: no `ROLLUP`, so no subtotal or grand total rows (T39) |

**Results (ANA-7, ANA-8).**

- The full result goes into a temporary DuckDB table, which can spill to disk.
- The grid fetches pages as it scrolls and shows the first 100,000 rows, with a note when there are more.
- Sorting a header re-queries the table. With subtotals on, rows sort within each parent group (T23).
- Export copies from the table, so nothing is recalculated.
- Cancel calls `interrupt()`, and the previous result is greyed.

**Distinct values (ANA-4).** Top 1,000 values by count over the ticked runs, plus search across the whole column. Runs as a short Job inside the dropdown, with a spinner and Cancel.

**Saved analyses (ANA-1, V3-2).** Stored as JSON, for example `{template_id, filters:[{column_id, op, values}], groups:[{column_id, grain}], measures:[{column_id, fn, label}], subtotals}`. Runs are not stored (D33). Columns are referenced by ID, so renames are safe; a removed column keeps working, labelled "(removed)" (T23). **Changed** 22-11-2026 (A2): definitions are JSON version 2 (`"definition_version": 2`), with measures as cards, e.g. `measures:[{column_id: "_rows", ops:[{fn: "count", name: null}]}, {column_id: "c007", ops:[{fn: "sum", name: "Taxable value"}, {fn: "max", name: null}]}]`; `fn` is sum, count, count\_distinct, avg, min or max, stored in that order; `name: null` is the default name; filter ops add `not_number` and `not_date`. Only version 2 is read; saved analyses, default outputs, template-version snapshots and `run_output` all hold it (T49, Technical Spec A2 §9.1).

**Rows view (Added 22-11-2026, A2; ROW, T48).** The spec `{template_id, filters, columns, show_source}` is held in memory only (ROW-3). Run is one Job: `count_rows`, then `fetch_rows` into a temporary table `_rows_<uuid>` holding `_seq`, every non-removed column with its companion, `run_id`, `_src_file`, `_src_sheet` and `_src_row`. It is filled run by run in Run ID order, each with one `SELECT … FROM read_parquet('<run>\data.parquet') WHERE <filters> ORDER BY _src_file, _src_row LIMIT <rows still needed>`, and stops at 100,000 rows. The grid reads pages of 200 by `_seq`; column ticks and order re-read pages from the same table, with no query against the runs. The table is dropped like an analysis result. Left-out rows are in their own file, so they are never read (ROW-13). Detail: Technical Spec A2 §10.

**Exports (EXP-1 to EXP-7).** All use DuckDB `COPY … TO` with the chosen delimiter, `DATEFORMAT '%d-%m-%Y'`, numbers at the column's decimal places with no grouping, and display names as headers.

| Export | Columns |
| --- | --- |
| A run's data | Template columns + Source File, Source Sheet, Source Row, Run ID (EXP-6) |
| Left-out rows (T19) | The same + Reason |
| Issue list | File, Sheet, Row, Column, Value, Rule, Severity, Message |
| Default outputs and analysis results | The full stored or temporary result, subtotal rows included when shown |
| Rows view (A2, ROW-12) | The ticked columns in order + Source File, Source Sheet, Source Row, Run ID |

Number and Date columns export one value per cell: `coalesce(CAST(c AS VARCHAR), c_t)` and `coalesce(strftime(c, '%d-%m-%Y'), c_t)`, so text exports as typed (A2, TXT-4). Group columns export the kind labels "(Not a number)", "(Not a date)" and "(Null)" (T42).

- **UTF-8 with BOM (EXP-3).** DuckDB's COPY always writes UTF-8 without a BOM. The export writes `<name>.part`, then streams it into the final file after the 3 BOM bytes, and deletes the part file. Plain UTF-8 renames the part file instead. **Replaced** 22-11-2026 (A2) by the pipeline below.
- **Cancel (EXP-7).** Deletes the `.part` file. **Replaced** 22-11-2026 (A2): see the pipeline below.
- **File names.** Characters Windows doesn't allow in file names are replaced with `_`. Overwriting needs confirmation (EXP-4).

**Export pipeline (Added 22-11-2026, A2; EXP-8 to EXP-14, T33 to T37).** Every export is one or more sources, each a header list, a known row count N and one or more chunks: one per ticked run with matches for the Rows view, one for everything else. Run data, left-out rows and Rows view chunks are ordered `ORDER BY _src_file, _src_row` (T32); result exports put the grand total last (T38). `export()` runs in one Job:

1. **Check.** Free space again (T34); each file to be replaced opened for writing, to check it isn't open in another program (T36).
2. **Extract.** For each chunk, `COPY (<select>) TO '%TEMP%\Sankalan\<job>-<k>.csv'` with no header, the chosen delimiter and `DATEFORMAT '%d-%m-%Y'` (T33). Stage "Reading rows".
3. **Split.** Python streams the chunk into the parts, then deletes it before the next `COPY`, so working space never exceeds one chunk. Each part, `<final name>.partial` in the chosen folder, starts with the BOM (when chosen) and the header. The splitter counts CSV records, not lines (a `\n` outside quotes ends a record), in 8 MB blocks. Stage "Writing files", rows written of N, detail "part K of M" (T53).
4. **Verify.** Records per chunk equal its `COPY` count and the total equals N; otherwise "Export check failed: wrote X of N rows".
5. **Finish** (not cancellable, T35). Files being replaced → `.replaced`; parts renamed into place; `.replaced` deleted. Any failure restores the `.replaced` files and deletes the parts.

Cancel or failure deletes every chunk and `.partial` file and restores any `.replaced` file, so existing files are left as they were (EXP-14).

- **Parts and names (EXP-9, EXP-10).** N ≤ `PART_ROWS` (1,000,000, T37) gives one file with the dialog's name; otherwise ceil(N ÷ 1,000,000) parts `<stem>_partKKofMM.csv`, both numbers zero-padded to at least 2 digits. "All outputs" plans each output on its own. The overwrite confirmation lists every existing target; other files in the folder are never touched.
- **Estimate and free space (EXP-13, T34).** When the dialog opens, a short Job copies up to 10,000 sample rows to `%TEMP%\Sankalan` for bytes per row; estimate = bytes per row × N × 1.05. The temp drive needs the largest chunk's estimate + max(1 GB, 10%); the destination needs the estimate + max(1 GB, 10%); on one drive they add up. Free space is read again when the folder changes and at step 1. Each drive has its own message.

Detail, dialogs and banners: Technical Spec A2 §8.

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
- An update is a new installer run over the old one (SEC-6). At the first start after an update, the catalogue is backed up, then upgraded by `schema_version`. Parquet files are never rewritten. (A2: there is no upgrade to version 2; a version-1 catalogue, made only by test builds, is refused, T40.)
- Uninstall asks whether to delete the data folder (T26).

**Offline and data handling (SEC-1 to SEC-7).**

- No network code. DuckDB extensions are switched off and the configuration is locked (Architecture).
- Source files are opened read-only (SEC-2).
- Spill files live in `%TEMP%\Sankalan`; the run being staged lives in `_staging` (T9). Both are emptied when the operation ends and at start-up. **Changed** 22-11-2026 (A2, BUG-1): when a Job ends, the open connection's own spill files (`duckdb_temp_<this process's PID>_*`) are kept in `%TEMP%\Sankalan`; DuckDB deletes them itself. Closing the data folder and start-up empty it completely (T54, SEC-4). Export chunks also live there only while the export runs (T33).
- The log is in `%LOCALAPPDATA%\Sankalan\logs\`, rotated. It records the operation, the file name and the error class only. DuckDB error message text is never logged, because it can contain cell values (SEC-5).

## Tests and release acceptance

The automated suite runs on every build. The performance suite and a Smart App Control check run once before release, on a 16 GB, 4-core laptop (T4).

| Test | Checks | Source |
| --- | --- | --- |
| No network code | Static scan of imports; a full run with the network blocked (SEC-1, SEC-7) | V1 |
| Sources unchanged | File hashes before and after a run (SEC-2) | V1 |
| No leftovers | Temp and `_staging` empty after each Job and after a restart (SEC-4). **Changed** 22-11-2026 (A2): after a Job, temp may hold only the current process's `duckdb_temp_<pid>_*` spill files; after closing the data folder or a restart it is empty (AC-BUG-1b) | V1, extended |
| No cell values in the log | Marker values planted in test files are searched for in the log (SEC-5) | V1 |
| Allowed compiled packages | Only the packages in the dependency table load | V1, updated |
| Crash during commit | Process killed at each commit step; after a restart only committed runs exist and no extra folders remain | New |
| Conversion values | ₹, Indian grouping, brackets, rounding to each decimal setting, both date formats, Excel dates | New |
| Rule meanings | Every row of the rule table, including blanks and duplicate groups | New |
| Totals reconciliation | Input = Loaded + Left out across error, duplicate, hidden and blank cases | New |
| Columns across runs | Add, remove and rename across runs; null in older runs; "(removed)" in saved analyses | New |
| Export | BOM bytes, delimiters, DD-MM-YYYY dates, `.part` deleted on Cancel. **Changed** 22-11-2026 (A2): parts and `.partial` instead of `.part` (see Export in parts below) | New |
| Text companions (A2) | Convert keeps text exactly as typed (spaces, `#N/A`), never both filled, MAP-6 / MAP-11 nulls; one issue per text cell, Not blank passes, two "NA" duplicates; totals; filters, Count, Distinct, Min / Max, kinds and P8 sorting (AC-TXT-1 to AC-TXT-9) | New (A2) |
| Templates without checks (A2) | Model and Duplicate; wizard No / Yes keeps rules; Settings makes a new version; Load Job (no issues or left-out files, Cancel empties staging, Back target); text values list; Commit lines; run row fields; Runs list and Run detail (AC-NCK-1 to AC-NCK-10) | New (A2) |
| Choose sheets (A2) | Probe sheet lists for all four Excel kinds; one error row per file; resolution from choice and rule; dialog ticks; footer wording; `sheets_chosen` at commit (AC-SHT-1 to AC-SHT-9) | New (A2) |
| Export in parts (A2) | Splitter unit tests with quotes, doubled quotes, `\r`, `\n` and delimiters on part and block boundaries; part plan and names; every export kind split with a small part size; Cancel at each step leaves no chunk, `.partial` or `.replaced` file and replaced files keep their SHA-256; failure during finish restores them; a target held open; count mismatch; free-space refusal; grand total in the last part only (T38) | New (A2) |
| Stored order (A2, slow) | A multi-file load of ≥ 2M rows: `data.parquet` ascending in `_src_file, _src_row`; Rows export Run ID never goes back; two exports byte-identical (AC-ROW-12b) | New (A2) |
| Measures (A2) | Version-2 round trip; version 1 refused; the checks before Run, Save and Preview; `resolve_headers` defaults, clashes and removed columns; Rows card and no-measure results without totals (T39); headers kept after a rename (AC-MEA-1 to AC-MEA-11) | New (A2) |
| Rows view (A2) | Count vs an independent `count(*)`; fetch across runs fills to exactly 100,000 in stored order; paging by `_seq`; Cancel keeps the old table (AC-ROW-1 to AC-ROW-14) | New (A2) |
| BUG-1 and catalogue (A2) | A spilled temp table survives the next Job's clean-up (AC-BUG-1a); AC-BUG-1b; a full-size 3-run load commits (AC-BUG-1c, slow); a new folder at catalogue version 2; a version-1 catalogue refused with no change to the folder | New (A2) |
| Screen fit (UI-2) | Every screen at 1366×768 at 100%, and at 1920×1080 at 125% and 150%: the window never scrolls | New |
| Self-test after install | Small pipeline; DuckDB and calamine load; signatures checked with `Get-AuthenticodeSignature` | V1, extended |
| Performance suite (release only) | Generated data: PERF-1 (10M rows from CSV), PERF-2 (10M rows from 10 .xlsx), PERF-3 to PERF-6 over 12 runs and 120M rows. Misses are reported, not blocking. **Changed** 22-11-2026 (A2): adds PERF-7 to PERF-14 on TPL-R at full size, including a 120M-row Rows export; PERF-1 and PERF-2 now include the Convert sort and the companions | New |
| Smart App Control (release only) | The signed installer installs and runs on a laptop with Smart App Control on | New |

A2 fixtures (TPL-R, TPL-N and the sheet files, in full and small sizes), the A2 GUI tests and the existing tests A2 changes: Technical Spec A2 §14. Expected figures do not change.

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
