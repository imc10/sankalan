# Sankalan — Technical Spec A2: Feature-Updates

21-11-2026 · Chetan Mundhada · Builds on Technical Spec v1.0 (`docs/specs/technical-spec-v1.0.md`) · Replaces
Technical Spec A1 (`docs/specs/technical-spec-a1.md`)

## 1. Purpose and scope

This spec says how to build Feature Spec A2 (`docs/specs/feature-spec-a2.md`) in the existing V2 codebase. It
covers six features and one bug fix:

- A: Rows view (ROW-1 to ROW-14)
- B: Measures by column (MEA-1 to MEA-11)
- C: Export in parts (EXP-8 to EXP-14)
- D: Choose sheets for a file (SHT-1 to SHT-10)
- E: Number and Date columns keep text (TXT-1 to TXT-14)
- F: Template without checks (NCK-1 to NCK-14)
- BUG-1: temp clean-up deletes DuckDB's live spill files

It is the input for the A2 implementation plan.

It was written from a read of the current code (`Feature-Updates`, commit `674c678`), Technical Spec A1's spikes S7a
to S7i, and new spikes S8 run on the dev PC on 21-11-2026 (section 3). Where Feature Spec A2 can't be built as
written, or the code or spikes point to a better way, this spec says so; section 15 lists every such correction.
As with Technical Spec v1.0, **this spec wins where the two differ**.

| Source | What this spec takes from it |
| --- | --- |
| Feature Spec A2 (21-11-2026), copy in `docs/specs/feature-spec-a2.md` | Behaviour, IDs ROW, MEA, EXP-8 to EXP-14, SHT, TXT, NCK, BUG-1, PERF-7 to PERF-14, AC-*, D38 to D80, P8 |
| Technical Spec v1.0 | Architecture, Jobs, storage, ingestion, validation, query layer, export path, T1 to T27 |
| Technical Spec A1 | Export engine, splitter, measures model, header rename, Rows view engine; revised here for A2 |
| `docs/PROGRESS.md` decisions | Spikes S1/S2 (DuckDB writes only to the data folder and `%TEMP%\Sankalan`), staging, labels |
| Current code | Module layout, what exists and what changes (section 4) |

**Unchanged.**

- Offline (SEC-1); DuckDB configuration locked after start-up.
- One long Job at a time (T6); all SQL in `sankalan/query/` (schema DDL in `sankalan/db/`).
- CSV export only (EXP-2); UI rules UI-1 to UI-8.
- No new runtime packages and no new processes.

**Numbering.** Feature Spec A2 refers to Technical Spec v1.0 decisions T28 to T31 held in a newer copy than the
repository's, which stops at T27. To avoid a clash, this spec's decisions start at **T32**. Technical Spec A1's T28
to T44 are superseded: where one still holds, it is restated here under a new number. Feature Spec A2 reuses D38 to
D60 for Addendum A1. The repository's D38 (.xls and .xlsb input, 20-11-2026) therefore becomes **D81** (T67).

## 2. Decisions

The decisions marked **Answered** were settled with the user on 21-11-2026. The rest are technical and follow from
the code and the spikes.

| # | Decision | Items |
| --- | --- | --- |
| T32 | Stored order is made true at Convert: `data.parquet` is written with `ORDER BY _src_file, _src_row`. Every stored-order read (Rows grid fetch, run data, left-out rows and Rows view exports) also has `ORDER BY _src_file, _src_row`, on one run's file at a time. Nothing relies on DuckDB's unstated row order | 8.7, ROW-12, R7 |
| T33 | DuckDB writes each export chunk to `%TEMP%\Sankalan`, the only place outside the data folder it may write (spike S2). Chunk files have no header. Python streams the chunks into the parts in the chosen folder, writing the BOM and header into each part. There is no rename shortcut | EXP-8, 8.5 |
| T34 | The free-space check looks at two drives. The temp drive needs the largest chunk plus a margin; the destination drive needs the whole export plus a margin. When both are the same drive, the needs add up | EXP-13 |
| T35 | Parts are written as `<final name>.partial`. Finishing does three things: renames each file being replaced to `<name>.replaced`, renames the parts into place, then deletes the `.replaced` files. On any failure the `.replaced` files are renamed back. Finishing can't be cancelled and takes milliseconds | EXP-14, P5 |
| T36 | Before writing, and again before finishing, every file to be replaced is opened for writing, to check it isn't open in Excel. If it is: "\<file> is open in another program. Close it, then export again." | EXP-10, EXP-14 |
| T37 | The part size is `PART_ROWS = 1_000_000` in `sankalan/exporting.py`. Tests pass a smaller value as an argument; the app never changes it | EXP-9 |
| T38 | **Answered.** The grand total stays the last row of a result export, as on screen (pinned at the bottom) and as built today. When the export is split, it is the last row of the last part | EXP-12 |
| T39 | **Answered.** A Summary or default output with group levels and no measures lists each group combination once, with **no subtotal or grand total rows**. Show subtotals is disabled for it | MEA-11 |
| T40 | **Answered (D77).** The catalogue schema becomes version 2, created whole for a new data folder. There is no upgrade code. A version-1 catalogue (made by a test build) is refused at start-up with a message, and the user picks or creates another data folder | 8.4 |
| T41 | Text companions (Feature E) are written by Convert into `data.parquet` and carried into `left_out.parquet` by the split. `conversion_failures.parquet` is retired: Is a number and Is a date issues read the companions | TXT-1, TXT-13 |
| T42 | Result tables get a kind column `k1`…`kn` beside each group value `g1`…`gn` (0 = value, 1 = text, 2 = blank). Grouping is `ROLLUP((k1, g1), …, (kn, gn))`, which DuckDB 2.0 supports (S8g). Sorting orders by kind first (P8, **confirmed**) | TXT-10, TXT-11 |
| T43 | Check data before loading is held in the template's `settings` JSON (`"checks": true / false`), not in a new `template` column, so snapshots and Duplicate carry it with no new code path. The run row stores the value it used (`run.checks`) | NCK-1, NCK-12 |
| T44 | A run's third step is Validate or Load, chosen from `RunSession.checks` when the wizard starts. The step bar always has five steps. Load runs one Job: Read, Convert and the text-value summary. No scan and no split run | NCK-6, NCK-7 |
| T45 | **Answered.** For a run without checks, Rows read still includes blank rows (as RUNV-02). Rows left out is 0 and shows "None". Load, Commit and the Run summary add "Blank rows skipped: N", like hidden rows. Rows loaded = Rows read − blank rows | NCK-4, NCK-8, NCK-9 |
| T46 | **Answered.** Choose sheets is offered on .xlsx, .xlsm, .xlsb and .xls files; all four readers already list sheets with visibility | SHT-2 |
| T47 | Probe returns the full sheet list of an Excel file (name, visible, approximate rows). A file whose sheets don't satisfy the rule, or the user's choice, becomes **one** error row for the file (`problem = "sheet"`), not one row per missing sheet. Its message names the visible sheets | SHT-4, SHT-6 |
| T48 | A Rows view result is a temporary table `_rows_<uuid>` with a sequence column `_seq`, dropped through the window's existing `drop_results` / `pending_drops` path, like analysis results. It is filled per run with one `ORDER BY _src_file, _src_row LIMIT <rows still needed>` (S8c) | ROW-3, ROW-11 |
| T49 | Measures are held as cards (a column and its ticked operations) in memory and in JSON version 2. The compiler works on the flattened list in MEA-6 order. `Definition.from_dict` reads version 2 only | MEA-1 to MEA-6 |
| T50 | Each committed run keeps its outputs' headers in `run_output.headers` (a JSON list, group headers included). The Outputs tab and exports read them; they never change after commit (P4) | MEA-9, DO-6 |
| T51 | One header widget, `RenamableHeader`, gives the ✎ rename to the analysis grid (6.2) and to both Default outputs previews (3.2, 2.5) | MEA-8 |
| T52 | `PagedGrid` gains an optional frozen first column, using a second, overlaid table view (Qt's frozen-column pattern). In the Rows view, header clicks do nothing and no sort arrow is drawn | ROW-11, 2.2 |
| T53 | Job progress gains a detail line (`ctx.set_detail("part 2 of 3")`), shown under the stage by the progress panel | EXP-11 |
| T54 | **BUG-1.** After a Job, `%TEMP%\Sankalan` is emptied **except** files named `duckdb_temp_<this process's PID>_*` (spike S8h). Closing the data folder and start-up still empty it completely | BUG-1, SEC-4 |
| T55 | Is not a number and Is not a date are offered wherever Blank is offered: Analysis, the Rows view and default outputs. They are stored as filter ops `not_number` and `not_date` | TXT-6, TXT-7 |
| T56 | `run.text_counts` holds, per Number and Date column, the count of text values in the run's **loaded** rows (`data.parquet`). It is computed in the commit Job for every run | 8.4, NCK-9 |
| T67 | **Answered.** Decision renumbering: the repository's D38 (.xls and .xlsb input) becomes D81 in Feature Spec v2.0 and `docs/PROGRESS.md` | 1 |

T57 to T66 are left unused, so later additions can be inserted in order.

## 3. Findings from the code and the spikes

Spikes S8 ran with DuckDB 2.0.0 from the project's `.venv`, at 4 and 8 threads, on generated data. The main set was
10M rows written as 10 "files" of 1M rows by a `UNION ALL`, like Convert. It had 20 template columns (8 text, 4
DECIMAL(38,2), 2 dates, plus 2 companions), `_src_file`, `_src_sheet` and `_src_row`. That is 267 MB as Parquet and
1.2 GB as CSV. Times are from the dev PC, which is faster than the 16 GB, 4-core release laptop.

| # | Question | Result | Consequence |
| --- | --- | --- | --- |
| S8a | Does Convert's `UNION ALL`, written by `COPY … TO parquet` with `preserve_insertion_order` on (the default), keep load order? | **No.** The parts landed out of order in 3 places. This confirms A1's S7a | Feature Spec A2 8.7's design can't be relied on. T32 |
| S8b | Cost of sorting at Convert | 13.2 s to rewrite 10M rows sorted (8 threads) | Inside PERF-1. Measured against today's Convert in A2-0 |
| S8c | First 100,000 matching rows of one 10M-row run, all columns, into a temp table: one step `ORDER BY _src_file, _src_row LIMIT 100000` | 0.9 s (8 threads), 2.2 s (4 threads) | One step is enough for PERF-7; no join. T48 |
| S8d | The same in two steps (keys, then a bounded range) | 0.5 s / 1.3 s, identical rows | Faster, but more code for no PERF gain. Not used (D55) |
| S8e | Match count with 2 filters, 10M rows | 0.24 s | PERF-7/PERF-8 counts are cheap |
| S8f | Export of 10M rows to CSV with and without `ORDER BY _src_file, _src_row`, on a sorted file | 16.3 s vs 13.4 s (+22%); output byte-identical | Paid for certainty (T32) |
| S8g | `GROUP BY ROLLUP((k, g))` with composite levels | Works; `grouping(g)` marks rolled-up levels as today | T42 |
| S8h | Spill file names under `temp_directory` | `duckdb_temp_<pid>_<n>_owner` and `duckdb_temp_<pid>_<n>_storage_<size>-<k>.tmp` | T54 matches `duckdb_temp_<pid>_` |
| S8i | Page of 200 rows from a 100,000-row temp table by `OFFSET` | 0.18 s | Pages use a `_seq` range instead (PERF-9) |

A1's findings that still apply: S7h (DuckDB `COPY … CSV` quotes values containing `\r`, `\n`, `"` or the
delimiter, and doubles quotes, so the splitter's quote rule holds), S7i (match counts are cheap), S7b (sorting
narrow files is cheap).

Findings from the code:

- **Text cells today.** A Number or Date cell that doesn't convert is null in `data.parquet`. Its text is kept only
  in `conversion_failures.parquet` until commit, and then in `issues.parquet` (`query/convert.py`,
  `query/validate.py` `fl` CTE). A type rule set to Warning loads the row with a null. Excel error cells are already
  restored as text (`#N/A`) by the error-cell scan.
- **Test rules on latest run (VR-8)** finds no type failures today, because committed text is null
  (`validation/scan.py:9`). With companions it will find them. This is a side benefit, not a behaviour change
  anyone relies on.
- **Totals check.** Input is computed from the raw staged text, with `coalesce(number_sql(raw), 0)`; Loaded and Left
  out are `coalesce(sum(col), 0)`. Text already counts as 0 and null, so TXT-14 needs no code change, only tests.
- **Sheets.** `_probe_excel` (`ingest/probe.py:138`) matches named sheets case-insensitively against visible sheets.
  It gives one ERROR row per missing name, alongside READY rows for the sheets found. Only the hidden-sheet names
  survive Probe; the visible list is a local variable.
- **Blank rows** are dropped and counted in the reader workers (`excel.read_sheet`, `csvread`). They come back as
  `PartResult.blank_rows`.
- **Run steps.** The step indices are constants (`ui/screens/new_run.py:37`, `FILES … COMMIT = range(5)`) and
  `new_run_steps.py:380` hard-codes `OUTPUTS_STEP = 3`. Keeping five steps and swapping the third page (T44) keeps
  all of them.
- **`file_index`** is the position in `RunSession.readable_files`. It is assigned in three places that must agree
  (mapping, `LoadPart.from_probe`, commit). Choose sheets changes which rows exist, not how they are numbered.
- **Exports** already write the header in Python and stream DuckDB's headerless file from `%TEMP%\Sankalan`
  (`sankalan/exporting.py`). The result export puts the grand total last (`query/export.py`, `ORDER BY (_depth = 0)`).
- **Result tables** already use internal names `g1…gn` and `m1…mk` (`query/compiler.py`). `layer.open_output` builds a
  committed output's headers from today's names, so a column rename currently changes committed runs' headers.
  T50 stops that.
- **Definitions.** `definition.check()` refuses a definition without measures. `measure_label` gives "Sum of Taxable
  Value" and "Count of rows"; MEA-7 changes them.

## 4. Module map

New modules are marked **New**; everything else is a change to an existing module.

| Module | Change |
| --- | --- |
| `sankalan/db/catalogue.py` | `SCHEMA_VERSION = 2`; `_V2` is the whole schema (12.1); a version-1 catalogue raises `CatalogueFromTestBuild` |
| `sankalan/db/storage.py` | `_job_end` keeps `duckdb_temp_<pid>_*` (T54); start-up and close unchanged |
| `sankalan/paths.py` | `empty_folder(path, keep=None)` gains a name filter |
| `sankalan/model/template.py` | `Template.checks: bool = True`, in `settings_dict`, `copy`, `snapshot` (T43) |
| `sankalan/model/definition.py` | Version-2 measures (`Op`, `MeasureCard`, `ROWS`, `flat_measures`), filter ops `not_number`, `not_date`, new checks, default names, `NOT_NUMBER_LABEL`, `NOT_DATE_LABEL` |
| `sankalan/model/rowspec.py` **New** | `RowSpec` (10.1) |
| `sankalan/model/run.py` | `Run.checks`, `Run.text_counts`; `RunFile.sheets_chosen` |
| `sankalan/model/export.py` | `ExportRequest.kind` gains `rows`; `part_names()`; runs without checks offer no issue or left-out export |
| `sankalan/ingest/probe.py` | `SheetEntry` list on `FileSheet`; sheet resolution from a choice or the rule; one error row per file for sheet problems (T47) |
| `sankalan/ingest/stage.py` | `probe(..., choices)` passes each file's choice to the worker |
| `sankalan/query/convert.py` | Companion columns; `ORDER BY _src_file, _src_row` (T32); `write_failures`, `failure_counts`, `read_failures` removed |
| `sankalan/query/validate.py` | Type rules, Not blank and Unique read companions (5.4); the `fl` CTE reads `data.parquet` |
| `sankalan/query/split.py` | Keeps companions (selects `*`); rewrite keeps the sort |
| `sankalan/query/textvalues.py` **New** | `text_counts`, `text_values` (5.7) |
| `sankalan/query/compiler.py` | Companions in filters and Count; kind columns and composite ROLLUP; measures from `flat_measures()`; `_rows` → `count(*)`; no-measure results (T39) |
| `sankalan/query/layer.py` | `order_by` with kinds; `open_output` takes stored headers; `Result` headers from `resolve_headers` |
| `sankalan/query/headers.py` **New** | `resolve_headers(definition, columns)` (9.3) |
| `sankalan/query/rows.py` **New** | Rows view SQL: count, fetch, page, export chunks (10.2) |
| `sankalan/query/export.py` | `ExportSource` and `Chunk`; companion display expressions; run data and left-out rows ordered; Rows view chunks; kind labels in result exports |
| `sankalan/query/catalogue.py` | Reads and writes `run.checks`, `run.text_counts`, `run_file.sheets_chosen`, `run_output.headers`; template `checks` |
| `sankalan/exporting.py` | Rewritten around `estimate()` and `export()` with chunks, splitter and parts (section 8) |
| `sankalan/exporting_split.py` **New** | The record splitter (8.5): pure Python, no Qt, no DuckDB |
| `sankalan/jobs/job.py` | `set_detail()` and `Progress.detail` (T53) |
| `sankalan/formats.py` | `cell_text(col, value, text)` for one-column display (TXT-2) |
| `sankalan/run/pipeline.py` | `RunSession.checks`, `sheet_choice`, `load_unchecked()`; commit stores the new run fields and output headers |
| `sankalan/runs.py`, `manage.py` | Export items and Test rules respect `checks`; Settings save handles `checks` |
| `sankalan/newtemplate.py` | Type note with the text share (5.9); the sample's text counts for 2.4b; `build_template` saves `checks` |
| `sankalan/analysis.py`, `analyses.py` | Headers from `resolve_headers`; `write_outputs` returns headers for commit; describe lines in the new wording |
| `sankalan/rowsview.py` **New** | Rows view Job work: run, page and export source (no SQL) |
| `sankalan/ui/widgets/builder.py` | Measures section replaced by `MeasuresSection`; sections can be hidden (Rows mode); new filter ops with help text |
| `sankalan/ui/widgets/measures.py` **New** | `MeasuresSection`, `MeasureCardWidget`, `OpChip`, `AddColumnPopup` (9.6) |
| `sankalan/ui/widgets/header_rename.py` **New** | `RenamableHeader` (9.7) |
| `sankalan/ui/widgets/paged_grid.py` | Frozen first column; sorting can be switched off (T52) |
| `sankalan/ui/widgets/result_table.py` | Kind labels; stored headers |
| `sankalan/ui/widgets/progress.py` | Shows `Progress.detail` |
| `sankalan/ui/screens/analysis.py` | Summary \| Rows switch; hosts the Rows view; header rename on the result |
| `sankalan/ui/screens/rows_view.py` **New** | `ColumnsSection`, `RowsResult` panel and states (10.5) |
| `sankalan/ui/screens/new_template_rules.py` | Check data before loading bar; 2.4b panel (6.2) |
| `sankalan/ui/screens/template_settings.py` | Check data before loading (3.4) |
| `sankalan/ui/screens/template_columns.py` | Rules greyed and "Not in use" when checks is No; Test rules hidden (NCK-11, NCK-13) |
| `sankalan/ui/screens/template_outputs.py`, `new_template.py` | Previews use `RenamableHeader`; renames mark the tab changed |
| `sankalan/ui/screens/new_run.py` | Step 3 named Load or Validate; Choose sheets… action and banner; footer wording (SHT-6) |
| `sankalan/ui/screens/new_run_steps.py` | `LoadStep` (4.3b); Commit summary for runs without checks (4.5b) |
| `sankalan/ui/dialogs/choose_sheets.py` **New** | Choose sheets dialog (4.1c) |
| `sankalan/ui/screens/run.py`, `template.py` | "Not checked"; no Issues tab; no issue or left-out export for runs without checks |
| `sankalan/ui/dialogs/export_dialog.py` | Estimate on open, parts line, disk message, overwrite list, Export rows mode (7.9), new banners |

## 5. Feature E · Number and Date columns keep text

This feature comes first: the storage it adds is read by Features A, B, C and F.

### 5.1 Storage (T41)

- Every Number and Date column `cNNN` has a companion `cNNN_t VARCHAR` in every `data.parquet` and `left_out.parquet`.
- The companion holds the cell's text as staged (exactly as typed, spaces included, T14), only where the cell isn't
  blank and doesn't convert. On every other row it is null. `cNNN` and `cNNN_t` are never both filled.
- A column with no source in a file (MAP-6), or added after an older run (MAP-11), is null in both.
- Text columns have no companion.
- Helper: `convert.companion(col_id) -> f"{col_id}_t"`; `template.typed(columns)` returns the Number and Date
  columns.

### 5.2 Convert

`part_select` becomes two levels, so each conversion is computed once per cell:

```sql
SELECT run_id, _src_file, _src_sheet, _src_row,
       x_c007 AS c007,
       CASE WHEN x_c007 IS NULL AND NOT <blank(v3)> THEN v3 END AS c007_t,
       ...
FROM (SELECT '<run>' AS run_id, <file> AS _src_file, '<sheet>' AS _src_sheet, _src_row,
             v3, CAST(<number_sql(v3)> AS DECIMAL(38,2)) AS x_c007, ...
      FROM read_csv('<raw>\3.csv', ...))
```

- The conversion rules themselves are unchanged. A Date takes an Excel date (staged as ISO), or text in the
  template's date format, with any time of day dropped; anything else that isn't blank goes to the companion.
- `write_data` writes the `UNION ALL` of the parts with `ORDER BY _src_file, _src_row` (T32).
- `write_failures` is removed and no `conversion_failures.parquet` is written. `commit` no longer deletes it.
- `convert_values` (the test oracle helper) returns `(value, text)` pairs.
- The New template wizard's sample (`newtemplate.convert_sample`) uses the same `write_data`. Its previews, dry run
  and the 2.4b counts therefore see companions; `StagedSample.failures` is removed.

### 5.3 Display and export: one expression

| Type | On screen (Python, `formats.cell_text`) | In exports (SQL, `query/export._text`) |
| --- | --- | --- |
| Number | value with grouping at the column's decimals, else the text; right-aligned either way (TXT-3) | `coalesce(CAST(c AS VARCHAR), c_t)` |
| Date | DD-MM-YYYY, else the text; left-aligned either way | `coalesce(strftime(c, '%d-%m-%Y'), c_t)` |

The export expression replaces `_text` for run data, left-out rows and Rows view exports. CSV quoting of the text is
DuckDB's (S7h).

### 5.4 Validation (TXT-13)

Applies only to templates with checks.

| Rule | SQL for a Number or Date column `c` with companion `c_t` |
| --- | --- |
| Is a number, Is a date | Fails where `c_t IS NOT NULL`. The issue's value is `c_t`. The `fl` CTE becomes a `UNION ALL` over the typed columns of `SELECT _src_file, _src_sheet, _src_row, '<cid>' AS column_id, <cid>_t AS value FROM data WHERE <cid>_t IS NOT NULL` |
| Number range, Date range, Allowed values | Unchanged: they test `c`, and the existing `c IS NOT NULL AND (…)` wrapper skips text like a blank, so a text cell gives exactly one issue (from the type rule) |
| Not blank | Fails where `c IS NULL AND c_t IS NULL`. The `_bad` list (`fr`, `dd` CTEs) is no longer needed and is removed |
| Unique within the run | Key part per typed column: `coalesce(CAST(c AS VARCHAR), c_t)`, so two "NA" cells are equal. A row is skipped only when every key part is null, as today |
| Text length, Character pattern | Unchanged (Text columns) |

The new-template dry run (`newtemplate.dry_run`) and Test rules on latest run (`scan.test_rules_on_run`) read
companions the same way. For Test rules this means type failures are found in committed data (section 3).

### 5.5 Totals check (TXT-14)

No code change. Input already counts text as 0 (`coalesce(number_sql(raw), 0)`), and Loaded and Left out sum `c`, in
which text is null. Tests cover it (AC-TXT-8). Only Number columns ticked for the totals check are totalled.

### 5.6 Query layer

`compiler.column_expr(col, present)` returns the column, or a typed null when no run has it. A new
`companion_expr(col, present)` does the same for `c_t` (`CAST(NULL AS VARCHAR)` when absent). The compiler selects a
companion only when a filter, Count or group on that column needs it.

| Part | SQL |
| --- | --- |
| Equals, Between, Year / Quarter / Month is, relative dates | On `c` only, as today: text never matches (TXT-5, TXT-7, TXT-12) |
| Is not a number / Is not a date | `c_t IS NOT NULL` (ops `not_number`, `not_date`, T55) |
| Blank | Typed: `(c IS NULL AND c_t IS NULL)`. Text: as today |
| Not blank | `NOT (Blank)` |
| Count | Typed: `count(c) + count(c_t)` (TXT-8). Text: `count(c)` |
| Count distinct | Date: `count(DISTINCT c)`, text not counted (D70). Text: `count(DISTINCT c)`. Refused on Number (`definition.check`) |
| Sum, Avg, Min, Max | On `c` only. Avg is today's exact `average_sql` (T13) |
| Group key | `g_i` = `c` (or `date_trunc` for a grain), `k_i` = `CASE WHEN c IS NOT NULL THEN 0 WHEN c_t IS NOT NULL THEN 1 ELSE 2 END`. A Text group has `k_i` = 0 or 2. `GROUP BY ROLLUP((k1, g1), …)` (T42) |
| Relative date period (DO-3) | `max(c)`, ignoring text (TXT-12); a text row has null `c`, so it is outside every period |

`_depth` is computed from `grouping(g_i)` as today. On a rolled-up level, `k_i` and `g_i` are both null and `_depth`
tells them apart.

**Ordering (TXT-11, P8).** In `layer.order_by`, each `g{i} ASC NULLS LAST` becomes `k{i} ASC, g{i} <dir>`. A sort
on a group column flips only `g{i}`, so values come first in the chosen direction, then "(Not a number)" or "(Not a
date)", then "(Null)", in both directions. Measure sorts are unchanged, with group keys as tie-breakers.

**Labels.** Group cells show `d.NOT_NUMBER_LABEL = "(Not a number)"` or `d.NOT_DATE_LABEL = "(Not a date)"` for kind
1, and `"(Null)"` for kind 2, on screen (`result_table`, analysis grid) and in exports:
`CASE k_i WHEN 1 THEN '(Not a number)' WHEN 2 THEN '(Null)' ELSE <format(g_i)> END`.

**Stored outputs** (`outputs\<n>.parquet`) include the kind columns, so committed runs show the same labels.

### 5.7 Text values (`query/textvalues.py`)

| Function | SQL | Used by |
| --- | --- | --- |
| `text_counts(con, data, columns)` | `SELECT count(c007_t), count(c013_t), … FROM read_parquet(data)`; one scan, companions only | 2.4b (sample), 4.3b, 4.5b, `run.text_counts` (T56) |
| `text_values(con, data, column, limit=1000)` | `SELECT c_t, count(*) AS n, min((_src_file, _src_row)) AS first FROM read_parquet(data) WHERE c_t IS NOT NULL GROUP BY c_t ORDER BY n DESC, c_t LIMIT 1000`. The sheet of `first` is read with a second lookup on those ≤ 1,000 keys | NCK-8 values list |

File names for "where it first appears" come from the session's file list (`readable_files[file_index]`), mapped in
Python. Both functions run inside Jobs.

### 5.8 Filters UI (6.5, 6.6)

`FILTER_OPS[NUMBER]` gains `not_number` and `FILTER_OPS[DATE]` gains `not_date`. `OUTPUT_DATE_OPS` gains `not_date`
(T55). `FilterRow` shows each op's help text under the op picker:

- Is not a number: "Cells with text such as NA or Nil instead of a number"
- Is not a date: "Cells with text such as NA instead of a date"

Neither op takes a value. `analyses.describe` words them "Taxable Value is not a number".

### 5.9 Template wizard (6.2)

`newtemplate.detect` adds the text share to the note when a Number or Date column is detected with some values that
don't fit:

- "98% numbers · 2% aren't numbers and are kept as text"
- "97% dates · DD-MM-YYYY · 3% aren't dates and are kept as text"

The percentages use the existing `percent()`, which never rounds up to 100%. The note stays amber when not exact, as
today.

## 6. Feature F · Template without checks

### 6.1 Model and storage (T43)

- `Template.checks: bool = True`, written into `settings` JSON as `"checks"`, so it lands in every snapshot (TPL-7).
  `Template.copy()` carries it, so Duplicate copies it (NCK-1).
- `load_template` reads `settings.get("checks", True)`.
- Rules are kept in the `rule` table whatever the setting (NCK-11).
- `RunSession.checks` is taken from the template version the run starts with. A change to the template during the
  run has no effect on it.

### 6.2 New template wizard, step 4 Rules (2.4, 2.4b)

- A Yes / No bar at the top of `new_template_rules.py`, Yes selected, with "Applies to every run of this template.
  Can be changed later in Settings."
- **No** hides the rule editor and shows:
  - the explanation;
  - a table of the sample's text counts per Number and Date column ("Tax Amount · 38 of 100,000"), from
    `text_counts` on the converted sample, with columns that have none left out;
  - the footer "No rules will be set for this template".
- The rules entered so far stay in the step's memory and come back on Yes.
- `build_template` saves `checks`. With No it saves **no** rules, so a template created with No has only the automatic
  Is a number and Is a date rules once the setting is turned to Yes (NCK-11, VR-7). The wizard keeps 6 steps.

### 6.3 Template › Settings (3.4) and Columns & rules (3.3)

- **Settings.** Under Template name: Check data before loading, Yes / No, with "A change applies from the next run.
  Runs already loaded don't change." Saving goes through `manage.save_template` and makes a new version (TPL-7).
- **No → Yes.** Saving applies `with_type_rules`, so 3.3 shows the automatic rules at once.
- **Columns & rules with checks No.**
  - Each rule row is drawn greyed.
  - A banner above the rules reads "Not in use: this template loads without checks".
  - Add rule, edit and delete are disabled.
  - Test rules on latest run is hidden (NCK-13).
  - Column edits (names, types, decimals, totals tick) stay enabled.

### 6.4 Run steps (T44)

- `STEPS` stays five long. The third label is "Validate" or "Load" from `sess.checks`, as are the Next button labels
  ("Next: Load").
- Page index 2 holds `ValidateStep` or the new `LoadStep`, chosen when the wizard starts.
- When Mapping is skipped (TPL-6), Next on Files goes straight to Load.

### 6.5 Load Job (NCK-7)

`RunSession.load_unchecked(ctx) -> LoadSummary`, run by the "Load files" Job when the step is entered:

1. Create `_staging\<id>\`.
2. Stage 3 Read (workers write `raw\<i>.csv`), then stage 4 Convert into `data.parquet` with companions and the sort
   (T32). Progress shows the stage, files done of total, and rows read.
3. `text_counts` on the staged `data.parquet`.

No validation scan runs, and no `issues.parquet` or `left_out.parquet` is written. Cancel and Back both delete the
staging folder (as a cancelled Validate does today) and return to Mapping, or to Files when Mapping was skipped.

`LoadSummary` holds:

- files and sheets read;
- rows read (with blank rows, T45);
- blank rows;
- hidden rows;
- rows to load;
- text counts per column.

### 6.6 Load step result (4.3b)

- **Banner:** "3 files read · 3,126,480 rows to load".
- **Four stat cards:** Files and sheets read · Rows read · Rows to load · Values that aren't numbers or dates.
  "Blank rows skipped: N" and "Hidden rows skipped: N" appear as small lines under Rows read, when non-zero (T45).
- **Table:** each Number and Date column with text values, with its count.
- **Values list.** Selecting a column starts a short Job ("Read values") that calls `text_values` and lists up to 1,000
  values with count and where each first appears (file, sheet, row).
- **Re-check files** probes every file again:
  - A new file problem goes back to Files.
  - A new header goes back to Mapping.
  - Otherwise the Load Job runs again.
- **Next** goes to Outputs (default outputs run from `data.parquet`, as today).

### 6.7 Commit (4.5b, NCK-9, NCK-10)

The Commit step summary for a run without checks shows:

- "Data checks: Not checked · template setting"
- "Rows left out: None"
- "Blank rows skipped: N", when non-zero
- Per Number column with text: "Taxable Value: 3,412 values aren't numbers and are left out of sums"
- Per Date column with text: "Invoice Date: 120 values aren't dates and are left out of date filters and groups"
- Under the totals table: "Values that aren't numbers count as 0 on both sides"

The totals check runs Input = Loaded; a missing `left_out.parquet` counts as 0. The comment is optional. These
counts never block the commit.

The run row is written with:

- `checks = false`, `status = "committed"`
- `errors = 0`, `warnings = 0`
- `rows_left_out = 0`, `left_out_by_reason = {"blank": 0, "errors": 0, "duplicates": 0}`
- `rows_read` = rows with blank rows; `rows_loaded` = rows in `data.parquet`

The blank count is shown as `rows_read − rows_loaded` for these runs. No new column is needed.

### 6.8 Runs without checks elsewhere (NCK-12 to NCK-14)

| Place | Change |
| --- | --- |
| Runs list (3.1) | Issues column: "Not checked" |
| Run detail (5.1) | No Issues tab. Summary: "Data checks: Not checked" and the blank-rows line. Export issue list and Export left-out rows are hidden |
| `model/export`, `runs.export_items` | `issues` and `left_out` are refused for a run with `checks = false` (defence behind the UI) |
| Analysis, Rows view | Nothing differs: runs with and without checks are read the same way (NCK-14) |

## 7. Feature D · Choose sheets for a file

### 7.1 Probe (T47)

`FileSheet` gains `sheets: list[SheetEntry]`, with `SheetEntry(name, visible, rows_approx)`, for every Excel file
whose workbook could be opened. `rows_approx` is the sheet's dimension last row − 1, read with the existing dimension
logic of each reader (`xlsx`/`xlsm` sheet XML, `.xlsb` BrtWsDim, `.xls` DIMENSIONS), without a header scan. Hidden
sheets are listed with no count. CSV files and files that can't be opened have an empty list.

`probe_file(path, settings, known, chosen: list[str] | None = None)` resolves the sheets to read:

| Case | Sheets read | When it's an error |
| --- | --- | --- |
| `chosen` given | The chosen names, matched case-insensitively to visible sheets, in workbook order | Any chosen sheet missing or hidden (SHT-9) |
| Rule: by name | Each named sheet, matched as today | Any named sheet missing or hidden: the file is in Sheet not found even if some match (SHT-6) |
| Rule: first visible / all visible | As today | No visible sheet |

**Sheet not found** is one row for the file:

- `status = ERROR`, `problem = "sheet"`, `sheet = ""`
- message "Sheets found: Sales Nov, Returns Nov" (visible sheets, workbook order), or "\<file> has no visible sheet."
  when there are none
- the file's `sheets` list

No READY rows are produced for that file until it is resolved. Header detection then runs per sheet as today, and a
sheet with no header gives `problem = "header"` (SHT-8).

### 7.2 Session

- `RunSession.sheet_choice: dict[str, list[str]]` (path → chosen names, workbook order).
- `add_files` and `recheck_files` pass each path's choice to `stage.probe`.
- `remove_file` and Exclude delete the path's entry (SHT-9).
- `choose_sheets(path, names)` stores the choice and probes that one path again ("Check files" Job), swapping its rows
  in place as Re-check does.
- Like any change on Files, it drops the mapping and everything after (`_invalidate(FILES)`).

`can_choose_sheets(path)` is true when all of these hold (SHT-2):

- the file is an Excel kind (T46);
- its `sheets` list is non-empty and has at least one visible sheet;
- none of its rows has `problem` in `header`, `locked`, `password`, `damaged`, `missing`, `unreadable`.

### 7.3 Files step (4.1, 4.1a, 4.1b)

| Item | Build |
| --- | --- |
| Action column | "Choose sheets…" link on the file's first row, next to ✕, when `can_choose_sheets` |
| Sheet not found banner | Message from the row; actions Choose sheets… and Exclude file (no Re-check) |
| Footer | When every file in error has `problem = "sheet"`: "Choose sheets for N file(s), or exclude them, to continue" ("Choose sheets for 1 file, or exclude it, to continue"). Otherwise today's wording |
| Drop-zone hint | `sheets_text` adds "unless you choose others for a file": "reads sheets Sales and Sales Returns unless you choose others for a file" |
| No marker | Nothing shows that sheets were chosen (D66) |

### 7.4 Dialog (`ui/dialogs/choose_sheets.py`, 4.1c)

- **Built from the session's `FileSheet.sheets`.** No Job is needed to open it.
- **Title:** "Choose sheets for \<file name>", with the file size.
- **Sheet rows:** one checkbox row per sheet with "about 206,150 rows". A hidden sheet is disabled and reads "Hidden,
  skipped".
- **Note:** "The header row is found in each sheet. Headers that don't match the template's columns are handled in
  Mapping."
- **Total:** "2 sheets · about 412,300 rows".
- **Buttons:** Cancel and "Read N sheets" ("Read 1 sheet"), disabled when nothing is ticked.

Ticks when it opens (SHT-5):

1. If the path has a choice, the chosen sheets that are still visible.
2. Otherwise, the visible sheets the template's rule selects (by name: the named ones that exist; first: the first
   visible; all: every visible).

### 7.5 Commit and later steps

- `run_file.sheets_chosen` is true for each row of a path in `sheet_choice` (AC-SHT-8).
- Source Sheet holds the sheet's own name, as today.
- Mapping, the RUN-7 duplicate check, Validate and Load are unchanged: chosen sheets are ordinary file-and-sheet rows.

## 8. Feature C · Export in parts

### 8.1 Shape of an export

Every export becomes one or more `ExportSource`s, built inside the Job by `runs.export_items`, the analysis screen or
the Rows view:

```python
@dataclass(frozen=True)
class ExportSource:
    headers: list[str]          # display names, written by Python
    chunks: list[Chunk]         # extracted and split in order
    rows: int                   # N, known before writing

@dataclass(frozen=True)
class Chunk:
    select: str                 # SELECT of text values in export form, with its ORDER BY
    rows: int                   # this chunk's row count, for progress and the check
```

| Export | Chunks | Order | N from |
| --- | --- | --- | --- |
| A run's data | 1 | `ORDER BY _src_file, _src_row` | `count(*)` of `data.parquet` (Parquet metadata) |
| Left-out rows (with checks only) | 1 | `ORDER BY _src_file, _src_row` | `count(*)` of `left_out.parquet` |
| Issue list (with checks only; committed or Validate step) | 1 | File, row, rule (as today) | `count(*)` of `issues.parquet` |
| One default output | 1 | As stored, grand total last (T38) | rows of the stored output as exported |
| All outputs | 1 source per output, each split on its own | as above | as above |
| Analysis result | 1 | As on screen, grand total last | visible rows + grand total |
| Rows view | 1 per ticked run with matches, in Run ID order | `ORDER BY _src_file, _src_row` per run | the match count (ROW-10) |

### 8.2 Steps

`exporting.export(ctx, temp_dir, sources, folder, names, options, *, replace: set[Path], part_rows=PART_ROWS)`:

1. **Check** (EXP-13, T36). Recompute free space (8.4); fail with the dialog's message if short. Open each file in
   `replace` for append and close it again.
2. **Extract** chunk *k*: `COPY (<select>) TO '%TEMP%\Sankalan\<job>-<k>.csv' (FORMAT csv, HEADER false, DELIMITER …,
   QUOTE '"', DATEFORMAT '%d-%m-%Y')`. Stage "Reading rows", with the fraction from DuckDB's query progress.
3. **Split** chunk *k* into the current part (8.5), then delete the chunk file before the next `COPY` (P6). Working
   space never exceeds one chunk. Stage "Writing files", rows written of N, detail "part K of M".
4. **Verify.** Records counted in each chunk equal its `COPY` row count, and the total equals N. Otherwise fail with
   "Export check failed: wrote X of N rows". The log gets the error class only (SEC-5).
5. **Finish** (T35), with `ctx.set_cancellable(False)`: re-check T36, rename existing targets to `.replaced`, rename
   each `.partial` to its final name, delete the `.replaced` files. On any error, restore the `.replaced` files and
   delete the `.partial` files.

`ctx.on_abort` deletes every chunk, `.partial` and (after restoring) `.replaced` file (EXP-14). The temp folder is
also cleaned after every Job (T54). Start-up removes no files from user folders: a `.partial` left by a power cut
stays, with an honest name.

### 8.3 Plan and names (EXP-9, EXP-10)

`plan(rows, file_name, part_rows)` gives the final names:

- N ≤ `part_rows`: one file, with the dialog's name.
- Otherwise M = ceil(N / `part_rows`) parts named `<stem>_partKKofMM.csv`. `<stem>` is the file name without a final
  `.csv` (any case). Both numbers are zero-padded to `max(2, len(str(M)))` digits.
- Export all outputs: one plan per output, each named from the pattern as today.

The dialog shows the names and lists every existing one for the overwrite confirmation: up to 10, then "and 4 more".
It passes the confirmed set as `replace`. Other files in the folder are never touched.

### 8.4 Estimate and free space (EXP-13, T34)

`exporting.estimate(ctx, temp_dir, sources, folder, options)` runs as a short Job ("Checking size") when the dialog
opens. The dialog shows "Checking size…" and keeps Export disabled until it returns.

- **Bytes per row.** `COPY` the first chunk's select with `LIMIT 10000` and no `ORDER BY`, to a temp file; size ÷
  rows. If the first chunk has fewer than 10,000 rows, later chunks are sampled too, up to 10,000 in all. Header and
  BOM bytes are added once per part. Estimate = bytes per row × N × 1.05.
- **Needs.**
  - Temp drive: the largest chunk's estimate + max(1 GB, 10% of it).
  - Destination drive: the estimate + max(1 GB, 10% of the estimate).
  - When both are the same drive (by `os.path.splitdrive` of the resolved paths), the two needs add up.
- **Free.** `shutil.disk_usage` of the folder and of `%TEMP%\Sankalan`. It is read again on the UI thread (no Job)
  when the folder changes, and once more at step 1.
- **Messages.**
  - Destination short: Feature Spec A2's EXP-13 wording.
  - Temp drive short: "Not enough free space on C: for working files. This export needs about 2.6 GB there; 1.1 GB
    is free. Free up space on C:."

The estimate (N, M, names, bytes) also feeds the summary line ("3 CSV files · about 610 MB") and the parts line.

### 8.5 Splitter (`exporting_split.py`)

Chunk files hold only data records, so the splitter's only job is to count records and cut on record boundaries.

| Item | Design |
| --- | --- |
| Input | Chunk files in order, read in 8 MB binary blocks |
| Record end | `\n` outside quotes. Quote state flips on every `"`; a doubled quote inside a value flips twice (S7h) |
| Fast path | Outside quotes and `b'"' not in block`: `block.count(b"\n")`. If the part fills inside the block, `bytes.find` steps to the exact `\n` |
| Slow path | Walk the block by `bytes.find` of `"` and `\n`, counting `\n` only outside quotes |
| Quote state | Carried across blocks. It must be "outside" at the end of every chunk; otherwise the export fails as in 8.2 step 4 |
| New part | Close the part; open `<next>.partial`; write the BOM if chosen, then `header_line` (as today) |
| Progress | `ctx.set_rows(written, N)` and `ctx.set_detail(f"part {k} of {m}")` at most every 250 ms; `ctx.check_cancelled()` per block |
| Interface | `Splitter(open_part, header, bom, part_rows)`, `.feed(path)`, `.close() -> counts`. No Qt or DuckDB, so it is unit-tested alone |
| Thread | The Job's thread; file I/O and `bytes` methods release the GIL, so the window stays responsive (NF-3) |

### 8.6 Dialogs and banners

| Item | Change |
| --- | --- |
| 7.4 Export data, output, analysis | Estimate on open. Summary "N rows · CSV file", or "N rows · 3 CSV files · about X". Parts line under the file name (Feature Spec A2 4.3 wording). Disk message above the buttons |
| Overwrite confirmation | Lists every file that would be replaced (EXP-10), then sets `replace` |
| 7.5 Exporting | Stage, rows written of N, "part K of M" (T53), elapsed, Cancel |
| Success banner | One file: as today. Split: "Exported 2,341,118 rows to 3 files", with Open folder (EXP-14) |
| Cancel banner | "Export cancelled. No files were written; files that would have been replaced are unchanged." |
| Runs without checks | No Export issue list or Export left-out rows (NCK-12) |

## 9. Feature B · Measures by column

### 9.1 Model (T49)

```python
ROWS = "_rows"                                  # the Rows card (MEA-10)

@dataclass
class Op:
    fn: str                                     # sum | count | count_distinct | avg | min | max
    name: str | None = None                     # custom header; None = default (MEA-7)

@dataclass
class MeasureCard:
    column_id: str                              # a template column ID, or ROWS
    ops: list[Op]                               # stored in MEA-6 order on every save

Definition.measures: list[MeasureCard]

def flat_measures(defn) -> list[FlatMeasure]:   # (column_id or ROWS, fn, name): cards in order, ops in the
                                                # fixed order sum, count, count_distinct, avg, min, max
```

JSON is Feature Spec A2 8.8, with `"definition_version": 2`. `from_dict` reads version 2 only; any other version
raises `DefinitionError`. Saved analyses, default outputs, template-version snapshots and `run_output.definition`
all hold version 2. There is no upgrade (T40).

### 9.2 Checks (`definition.check`, Feature Spec A2 8.9)

The screens run these checks in this order before Run, Save and Preview. The first failure shows under its section,
and no Job starts:

1. No runs ticked: "Tick at least one run" (Analysis and Rows; screen check).
2. Rows view with no column ticked: "Tick at least one column" (screen check).
3. No measure card and no group level: "Add a group level or a measure" (MEA-11).
4. A card with no op: "Tick at least one operation for \<column>, or remove it" (MEA-4).
5. A default output with no name: as DO-1 today.

`definition.check` also refuses, as programming errors, these cases the UI can't produce:

- a column on two cards, or Rows twice;
- an op that doesn't fit the type: Number takes sum, count, avg, min, max (no count_distinct, D70); Date takes count,
  count_distinct, min, max; Text takes count, count_distinct; Rows takes count only;
- custom names that aren't 1–100 characters after trimming, or aren't unique ignoring case across every header of the
  result (MEA-8).

### 9.3 Headers (`query/headers.py`)

`resolve_headers(definition, columns) -> list[str]` returns the headers in result order (groups, then
`flat_measures()`):

- **Group:** the column name, plus " (removed)" when the column is removed (T23).
- **Measure, custom name:** the name.
- **Measure, default name:** "\<column name> · \<Sum | Count | Count distinct | Average | Min | Max>", or "Rows ·
  Count" for the Rows card; " (removed)" follows the column name when removed. A default follows later column renames
  (MEA-7).
- **Clashes (P3).** Group headers and custom names are placed first. Then each default, in order, gets " (2)", " (3)"
  … if its name is already taken, ignoring case. Two group levels on the same column (by Month and by Year) get the
  same treatment.

The hover text on a measure header is the default form "Invoice No · Count", whatever its name (MEA-8).

### 9.4 SQL (`query/compiler.py`)

- The compiler loops over `flat_measures()`: Rows → `count(*)`; the other ops as in 5.6.
- Subtotals use the composite `ROLLUP` (T42).

**No measures (T39):**

```sql
SELECT CAST(n AS INTEGER) AS _depth, k1, g1, …, kn, gn FROM (…) GROUP BY k1, g1, …, kn, gn
```

- There is no ROLLUP, so there are no subtotal or grand total rows.
- The screen disables Show subtotals and hides the pinned total row.
- `grand_total()` returns None, and the export has no "Grand total" row.

### 9.5 Names in saved analyses, default outputs and runs (T50)

| Where | Behaviour |
| --- | --- |
| Unsaved analysis (6.2) | A rename sets `Op.name` and redraws the header. It never marks the result stale and never re-runs. Unticking drops the op with its name; re-ticking adds `Op(fn, None)` (MEA-9) |
| Saved analysis (6.3) | No ✎. The locked summary reads "Invoice No: Count, shown as Invoices", or "Invoice No: Count" for a default name |
| Default outputs (3.2, 2.5) | A rename in the preview sets the name on that output's definition and marks the tab changed (Save / Discard / Stay) |
| Committed runs | At the Outputs step, `analysis.write_outputs` returns `resolve_headers()` per output with the template's columns at that moment. The commit transaction stores them in `run_output.headers`. `layer.open_output` takes the stored headers. Later renames never change them |

### 9.6 Measures section (`ui/widgets/measures.py`)

| Widget | Build |
| --- | --- |
| `MeasuresSection` | Heading "Measures" with "+ Add column" on the right; the cards; the note under them; the empty text (Feature Spec A2 3.2). Emits `changed` on add, remove, move and tick |
| `MeasureCardWidget` | Bordered frame, 6 px corners. Line 1: name (medium), type (grey), ↑ ↓ ✕ (`icon_button`). Line 2: chips. An error label under the card for MEA-4 |
| `OpChip` | Checkable `QPushButton`, 26 px, pill. Theme QSS for ticked (#0E6B6B on #E3F1F0) and unticked. Tooltip with the full name |
| `AddColumnPopup` | Popup frame: a search box when the template has more than 12 columns, then Rows and the unused columns, each with its type. Picking adds the card with nothing ticked (Rows: Count ticked) |

- `DefinitionBuilder` replaces its measure rows with `MeasuresSection`.
- It gains `set_sections(filters=…, groups=…, measures=…, subtotals=…)` for the Rows mode.
- `definition()` keeps each op's name from the previous definition while the same (column, fn) stays ticked.

### 9.7 Header rename (`ui/widgets/header_rename.py`)

`RenamableHeader(QHeaderView)`:

- `set_renamable(callback)` says which sections have ✎: the measure columns of an unsaved result or preview.
- It paints a ✎ in the right 20 px of those sections. A click on ✎ starts editing; a click elsewhere sorts, as before.
- **Editing.** A `QLineEdit` opens over the section, with the text selected.
  - Enter emits `rename_requested(section, text)`. The screen validates the name (9.2) and calls `finish()`, or
    `show_error("Another column is already called …")`, which keeps the box open with an error label below it.
  - Esc or focus loss cancels.
  - A blank name returns the header to its default.
- Tooltips per section come from a callback (the 9.3 hover text).

`RenamableHeader` is used by `PagedGrid` (6.2) and by the `QTableWidget` previews in `template_outputs.py` (3.2) and
`new_template.py` (2.5).

## 10. Feature A · Rows view

### 10.1 Spec

```python
@dataclass
class RowSpec:                     # in memory only, never stored (ROW-3)
    template_id: str
    filters: list[Filter]          # the builder's filters, compiled exactly as for Analysis
    columns: list[str]             # ticked column IDs, in order
    show_source: bool              # Show them on screen (ROW-8)
```

There is no sort (D71). The runs are passed as `RunRef(id, number, label, data_path, rows_loaded, file_names)`, in
Run ID order (`run_number`), read from the catalogue at Run. File names come from `run_file`.

### 10.2 Queries (`query/rows.py`)

| Entry point | SQL |
| --- | --- |
| `count_rows(con, spec, columns, runs) -> dict[run_id, int]` | `SELECT run_id, count(*) FROM read_parquet([…], union_by_name = true) WHERE <filters> GROUP BY run_id`. With no filters, `rows_loaded` from the catalogue (no scan). The match count is the sum. Rows searched (ROW-10) is always the sum of `rows_loaded` |
| `fetch_rows(con, spec, columns, runs, counts, table)` | Creates `table`, then fills it run by run (10.3) |
| `rows_page(con, table, first, count)` | `SELECT * FROM table WHERE _seq > first AND _seq <= first + count ORDER BY _seq` |
| `export_source(con, spec, columns, runs, counts)` | One chunk per run with matches (10.4) |

Filters compile through the compiler's shared `filter_sql` (with 5.6's companion rules). Left-out rows are in their
own file and are never read (ROW-13). Removed columns are never offered or selected.

### 10.3 Fetch (T48)

`CREATE TEMP TABLE _rows_<uuid>` with:

- `_seq BIGINT`;
- every non-removed template column, with its companion for Number and Date columns;
- `run_id`, `_src_file`, `_src_sheet`, `_src_row`.

Then, for each run in Run ID order with matches, while fewer than 100,000 rows are held:

```sql
INSERT INTO _rows_<uuid>
SELECT <held> + row_number() OVER (ORDER BY _src_file, _src_row) AS _seq, *
FROM (SELECT <each column or typed NULL>, <each companion or NULL>, run_id, _src_file, _src_sheet, _src_row
      FROM read_parquet('<run>\data.parquet') WHERE <filters>
      ORDER BY _src_file, _src_row LIMIT <100,000 − held>)
```

- The first run usually fills the table, so later runs are never read.
- One Job ("Rows view") runs the count, then the fetch, with stages "Counting rows" and "Fetching the first 100,000".
- Cancel interrupts DuckDB. `ctx.on_abort` drops the new table, and the previous table stays (2.4 Cancelled).
- When the Job finishes, the previous table goes to `window.drop_results`.

**Display values.** For the page's rows, Python maps:

- `run_id` → "R-0003";
- (`run_id`, `_src_file`) → file name;
- empty `_src_sheet` → blank;
- numbers, dates and companions via `formats.cell_text` (5.3).

Ticking, unticking or reordering columns, and Show them on screen, change only the grid's columns and re-read pages
from the same table (P1, PERF-10).

### 10.4 Export chunks (ROW-12)

For each ticked run with matches, in Run ID order, one chunk over that run's file alone:

```sql
SELECT <export text of each ticked column, in order (5.3)>,
       <file name CASE on _src_file>, nullif(_src_sheet, ''), _src_row, '<R-0003>'
FROM (SELECT <columns and companions or typed NULLs>, _src_file, _src_sheet, _src_row
      FROM read_parquet('<run>\data.parquet') WHERE <filters>)
ORDER BY _src_file, _src_row
```

- **Headers:** the ticked columns' names, then Source File, Source Sheet, Source Row, Run ID (ROW-8).
- **Row counts:** each chunk's count comes from `count_rows`, so the estimate needs no extra query.
- **Order:** the grid's 100,000 rows equal the export's first 100,000 data rows, in the same order (AC-ROW-11b).

### 10.5 UI

| Part | Build |
| --- | --- |
| Switch | "Summary \| Rows" beside the title in New analysis (6.2); hidden for a saved analysis (ROW-4) |
| Rows mode | The same `DefinitionBuilder` with groups, measures and subtotals hidden, so filters carry over and Summary's settings come back (ROW-2). Save is hidden; the header reads "Row views aren't saved". `leave_guard()` returns None (no prompt). `closing()` cancels a running Rows Job and drops the table |
| `ColumnsSection` | Every non-removed column with a tick and ↑ ↓; "N of M ticked"; the tick "Show them on screen". Emits `columns_changed` (no Run) |
| Settings changes | Client, template, runs or filters grey the result with "Settings changed: Run again" and disable Export rows (ROW-9). A template change drops the table |
| `RowsResult` header | "2,341,118 rows match · 3 runs · 7,499,937 rows searched · 0.9 s"; Export rows (.csv) |
| Grid | `PagedGrid` over `RowsSource` (a `PageSource` reading `rows_page` in pages of 200). Frozen first column (medium weight), 40 px rows, read-only. Widths from the column type, resizable, reset on leave. Sorting off: no arrows, and header clicks do nothing (T52) |
| Footer | N ≤ 100,000: "Showing all N rows". Otherwise: "Showing the first 100,000 of N rows, in the order they were loaded. Export gets all of them." |
| States | Feature Spec A2 2.4, using the existing empty, progress and error panels |
| Export rows (7.9) | The Export dialog with `ExportRequest(kind="rows")`: title "Export N rows"; summary line; a box with the filters in words (`analyses.describe`), the columns line and the row-order line; folder and encoding from the template's export defaults; file name `{Client}_{Template}_Rows_{DD-MM-YYYY}.csv`; estimate, parts line and disk message as 8.6 |

## 11. BUG-1 · Temp clean-up and DuckDB spill files (T54)

- `paths.empty_folder(path, keep: Callable[[str], bool] | None = None)` skips entries for which `keep(name)` is true.
- `Storage._job_end` calls it with `keep = lambda n: n.startswith(f"duckdb_temp_{os.getpid()}_")`. DuckDB frees
  those blocks itself and deletes the files when the connection closes (S8h).
- `Storage.open` (start-up) and `Storage.close` (closing the data folder, and before a data-folder move reopens the
  connection) empty the folder completely, as today.
- The SEC-4 "no leftovers" test allows only the current process's `duckdb_temp_<pid>_*` files after a Job, and
  nothing after close or restart (AC-BUG-1b).

## 12. Catalogue version 2 (T40)

### 12.1 Schema

`_V2` is `_V1` with these changes; `MIGRATIONS = {2: _V2}`. A new data folder is created straight at version 2.

| Table | Change |
| --- | --- |
| `template` | No new column. `settings` JSON gains `"checks"` (T43) |
| `template_version` | Snapshot includes `settings.checks`; rules kept when No |
| `run` | `checks BOOLEAN NOT NULL`; `text_counts VARCHAR NOT NULL` (JSON `{column_id: count}`, T56) |
| `run_file` | `sheets_chosen BOOLEAN NOT NULL` (never shown, SHT-10) |
| `run_output` | `headers VARCHAR NOT NULL` (JSON list of resolved headers at commit, T50) |
| `saved_analysis`, `default_output`, `run_output` | `definition` holds version-2 measures |

### 12.2 Old data folders

`ensure_schema` raises `CatalogueFromTestBuild` when it finds `schema_version` = 1. Start-up handles it like
`CatalogueTooNew`:

- no backup and no change to the folder;
- the message "This data folder was made by a test build of Sankalan and can't be opened by this version. Choose
  another folder, or create a new one.";
- the data-folder chooser.

The dev PC's existing folders are recreated by hand. No client data exists (D77).

## 13. Performance

Nothing in these features sorts all matching rows across runs. The Rows grid stops reading at 100,000 rows, every
export streams, and the per-run export sort costs about 22% (S8f). Expected times are scaled from the dev-PC
spikes. The release suite measures them on the 16 GB, 4-core laptop and reports misses without blocking (T4).

| ID | Target | Expected | Note |
| --- | --- | --- | --- |
| PERF-7 | ≤ 5 s | ~1.5–3 s: count 0.3 s + fetch 1–2.5 s (S8c, S8e) | 4-core laptop at the high end |
| PERF-8 | ≤ 30 s | ~4–6 s: count over 12 runs + usually one run's fetch | Fetch reads more runs only when the first has < 100,000 matches |
| PERF-9 | ≤ 100 ms | `_seq` range on a 100,000-row temp table | Not `OFFSET` (S8i) |
| PERF-10 | ≤ 200 ms | Pages re-read from the temp table only | |
| PERF-11 | ≤ 60 s | ~16 s extract + split at disk speed for ~2.4 GB | |
| PERF-12 | ≤ 12 min | 12 × (~16 s extract + ~2.4 GB split) | SSD-bound (R10) |
| PERF-13 | ≤ 2 s | 10,000-row sample `COPY` + metadata counts; the Rows view reuses its counts | |
| PERF-14 | ≤ 2 min | PERF-1's load + 13 s sort (S8b) + `text_counts` (one scan of the companions) | Measure in A2-0 against today's Convert |

Companions are read only by queries that need them, so PERF-3 to PERF-5 are unaffected. PERF-1 and PERF-2 now
include the Convert sort and the companions: they are measured again in A2-0 and A2-1.

## 14. Tests

### 14.1 Fixtures

`tests/fixtures/generate.py` gains:

| Set | Contents | Sizes |
| --- | --- | --- |
| TPL-R | Feature Spec A2 10.1 (20 columns; 3 runs; left-out rows; Place of Supply added in R-0002; null Invoice No in R-0003; text values in Taxable Value and Invoice Date; values with commas, quotes, line breaks) | Full (3 × 2,500,000 rows) for slow and performance tests; small (3 × 2,500 rows, same shape and ratios) for the normal suite with `part_rows = 1000` |
| TPL-N | TPL-R's columns, checks No; 2 CSV files; repeated rows; 6,802 / 120 text values | Full (2 × 500,000) slow; small (2 × 5,000, with the same text counts scaled) normal |
| Sheet files | `Sales_Nov-2026_Central.xlsx` (Sales Nov, Returns Nov, hidden Notes), `…_East.xlsx` (Sales), `…_West.xlsx` (Sales, Sales Returns, Cover with no header), plus .xlsb and .xls copies of Central made by `make_static_formats.ps1` | Small |

Acceptance figures that depend on full size (7,499,937 rows searched, 400,000 blank Invoice No, 6,802 text values)
are checked in the slow tests only. The small sets assert the same relations: counts equal independent queries.

### 14.2 Test areas

| Area | Tests |
| --- | --- |
| Companions (engine) | Convert: text kept exactly as typed (spaces, `#N/A`), never both filled, MAP-6 / MAP-11 nulls, sort order; validation TXT-13 (one issue per text cell, Not blank passes, two "NA" duplicates); totals TXT-14; filters, Count, Distinct, Min/Max, kinds, sorting P8 (AC-TXT-1 to AC-TXT-9) |
| Without checks | Model and Duplicate; wizard No / Yes keeps rules; Settings new version; Load Job (no issues or left-out files, cancel empties staging, Back target); text values list; Commit lines; run row fields; Runs list and Run detail (AC-NCK-1 to AC-NCK-10) |
| Choose sheets | Probe sheet lists for all four Excel kinds; one error row per file; resolution from choice and rule; dialog ticks (first time, later, after a sheet vanishes); `can_choose_sheets`; footer wording; `sheets_chosen` at commit (AC-SHT-1 to AC-SHT-9) |
| Splitter (unit) | Random CSV with quotes, doubled quotes, `\r`, `\n` and delimiters planted on and around part and block boundaries; records per part checked with Python's `csv`; parts joined without headers byte-identical to a one-file export; BOM and header on every part; an unbalanced quote at a chunk's end fails |
| Plan and names (unit) | 1,000,000 → one file; 1,000,001 → 2 parts; `_part01of03`; `_part001of120`; `.CSV` stem |
| Export engine | `part_rows = 1000` on small fixtures for every export kind in 8.1; cancel during extract, split and before finish (no chunk, `.partial` or `.replaced` left; replaced files keep their SHA-256); forced failure during finish restores originals; a target held open (T36); count mismatch via a test hook; free-space refusal via a patched `disk_usage`; grand total last part only (AC-EXP-12 as T38) |
| Stored order | A multi-file load large enough to run in parallel (≥ 2M rows, marked slow): `data.parquet` ascending in `_src_file, _src_row`; Rows export Run ID never goes back; two exports byte-identical (AC-ROW-12b) |
| Measures | Model round trip; `from_dict` refuses version 1; checks 9.2; `resolve_headers` defaults, clashes, removed columns; compiler with Rows and no-measure results (no totals, T39); AC-MEA-1 to AC-MEA-11 |
| Rows view engine | Count vs an independent `count(*)`; fetch across runs fills to exactly 100,000 in stored order; paging by `_seq`; cancel keeps the old table; AC-ROW-10 to AC-ROW-14 |
| BUG-1 | AC-BUG-1a (a spilled temp table survives the next Job's clean-up; fails on the old code); AC-BUG-1b; AC-BUG-1c (slow) |
| Catalogue | A new folder at version 2; a version-1 catalogue refused with no change to the folder |
| GUI | Switch; Columns section; grid redraw without a Job; no sort on header click; header rename (Enter, Esc, blank, clash); chips and Add column popup; filter help text; Choose sheets dialog; Load step; export dialog parts line and overwrite list; screen fit at 1366×768 |
| Release only | PERF-7 to PERF-14 on TPL-R at full size, and a 120M-row Rows export |

**Existing tests that change:**

- default measure headers ("Sum of Taxable Value" → "Taxable Value · Sum", "Count of rows" → "Rows · Count");
- every test that builds a version-1 definition;
- tests of `conversion_failures.parquet`;
- Sheet not found rows (one per file);
- the destination part name (`.part` → `.partial`) and the cancel banner;
- tests that expect a type-rule Warning row to load as null (it now loads with its text).

Expected figures do not change.

## 15. Changes to other docs

### 15.1 Feature Spec A2 (this spec wins)

| Item | Change | From |
| --- | --- | --- |
| 8.7 Stored order, R7 | Convert sorts; every stored-order read adds `ORDER BY _src_file, _src_row` per run. R7 retired (S8a showed `UNION ALL` order isn't kept) | T32 |
| 8.7 First 100,000 rows | One `ORDER BY … LIMIT` per run; table `_rows_<uuid>` with `_seq`, not `rows_view` | T48 |
| 8.1 | `fetch_rows(spec, runs, counts, table)`; `count_rows` returns per-run counts | 10.2 |
| 8.5 step 3, step 4 | Chunk files go to `%TEMP%\Sankalan`, not the chosen folder. They have no header. There is no rename shortcut for one plain UTF-8 file | T33 |
| 8.5 step 1, EXP-13 | Working space is needed on the temp drive, also for a single file. Added message for a short temp drive | T34 |
| 8.5 step 3 Source File | `CASE` on `_src_file` (today's helper) instead of a list literal | Code |
| 8.6 Header | Python writes the header into each part; chunks have none | T33 |
| EXP-12, AC-EXP-12 | Grand total is the last row of the last part, not the first row of part 1 | T38 |
| MEA-11, AC-MEA-11 | A result with no measures has no subtotal or grand total rows | T39 |
| 8.2, 8.3 | `conversion_failures.parquet` retired; companions carried into `left_out.parquet` | T41 |
| 8.4 `template.checks` | Held in `template.settings` JSON | T43 |
| 8.4 | Schema version 2; version-1 folders refused (no upgrade) | T40 |
| SHT-2, AC-SHT-1 | Choose sheets also on .xlsb and .xls | T46 |
| SHT-6 | Sheet not found is one error row per file | T47 |
| NCK-4, NCK-8, NCK-9, AC-NCK-2 | "Blank rows skipped: N"; Rows loaded = Rows read − blank rows | T45 |
| TXT-6, TXT-7 | Also offered in default outputs | T55 |
| 13.2 OA-5 | Closed: P8 confirmed | T42 |
| 11 Decisions | The repository's D38 (.xls / .xlsb) becomes D81 | T67 |

### 15.2 Feature Spec v2.0 and Technical Spec v1.0

Feature Spec A2 section 12 applies once development is done, with the corrections in 15.1. In addition, Technical
Spec v1.0 gains:

- T32 to T56 and T67;
- Storage → companions and catalogue version 2;
- Ingestion 1 → the sheet list and choice;
- Ingestion 4 → Convert sorts and writes companions, and no failures file;
- Validation → rule SQL for text cells;
- Architecture → Jobs → the progress detail line;
- SEC-4 → the spill-file exception.

`docs/PROGRESS.md` renames D38 to D81 (T67).

### 15.3 Test cases

- Add one case per Feature Spec A2 criterion (71) and per performance target (8), corrected for T38 (AC-EXP-12),
  T39 (AC-MEA-11), T45 (AC-NCK-2) and T46 (AC-SHT-1).
- Add cases for the temp-drive message (T34), the version-1 folder refusal (T40), and Choose sheets on .xlsb and .xls.
- Update existing cases whose expected headers use the old default names, and the Sheet not found cases.
- Keep `docs/specs/test-cases.md` and the live sheet in step.

### 15.4 Technical Spec A1, Feature Spec A1

Both are superseded by A2 and kept for history, each with a note at the top.

## 16. Suggested build order

Each phase ends with the full suite passing, as today. E and the stored-order change come first because the rest
reads their storage. C comes before A because A's export depends on it. B depends only on E.

| Phase | Scope | Depends on |
| --- | --- | --- |
| A2-0 | Fixtures (TPL-R and TPL-N in both sizes, sheet files); catalogue version 2 and the refusal; BUG-1; record PERF-1/PERF-2 baselines | — |
| A2-1 | Feature E engine and display: companions in Convert with the sort (T32); validation; query layer (filters, Count, kinds, P8); export text; `formats.cell_text`; filter ops and help text; wizard type note | A2-0 |
| A2-2 | Feature F: model and Settings; wizard step 4 and 2.4b; 3.3 greyed rules; Load step and Job; text values; Commit; Runs list and Run detail | A2-1 |
| A2-3 | Feature D: Probe sheet lists for all four kinds; one error row per file; session choice; dialog; banner and footer; `sheets_chosen` | A2-0 |
| A2-4 | Export engine: `ExportSource`, plan, estimate, splitter, finish and rollback, progress detail | A2-1 |
| A2-5 | Export dialogs: estimate, parts line, disk messages, overwrite list, banners | A2-4 |
| A2-6 | Measures v2 engine: model, checks, `resolve_headers`, compiler, no-measure results, `run_output.headers` | A2-1 |
| A2-7 | Measures UI: section, cards, chips, Add column popup, `RenamableHeader` on 6.2, 3.2, 2.5; 6.3 wording | A2-6 |
| A2-8 | Rows view engine: `RowSpec`, `query/rows.py`, `rowsview.py`, export chunks | A2-4 |
| A2-9 | Rows view UI: switch, Columns section, grid with frozen column and no sort, states, Export rows dialog | A2-5, A2-8 |
| A2-10 | Spec and test-sheet updates (section 15), slow tests at full size, performance suite additions | All |

A2-3 is independent of A2-1, A2-2 and A2-4 to A2-9, and can be built in parallel with them.

## 17. Risks and open items

No open items remain: OA-5 (P8) is confirmed.

| # | Risk | Impact | Plan |
| --- | --- | --- | --- |
| R8 | A Rows export needs one run's chunk (~2.4 GB) of working space on the temp drive, usually C:, even when exporting to another drive | Blocked exports on a full C: | T34 states it up front, with the drive named |
| R9 | Splitter mistakes near a part boundary | A record cut across parts | Unit tests with planted values; per-chunk count check (8.2 step 4) |
| R10 | PERF-12 depends on disk write speed (~29 GB for 120M rows) | Missed on slow disks | Measured and reported (T4) |
| R11 | A CSV whose text dates use another format than the template's now loads every date as text, instead of failing | Without checks, a whole Date column becomes text, with only a count to show it | Load and Commit counts (NCK-8, NCK-9) and the wizard's type note make it visible; with checks, Is a date reports every row |
| R12 | One dialog per file when a client renames sheets in all of a month's files | Many dialogs per run | Accepted (D65); the deferred run-level rule (Feature Spec A2 5.3) removes it later |
| R13 | The Convert sort (T32) adds ~13 s per 10M rows to every load | PERF-1/PERF-2 slower | Measured in A2-0 against today's baseline |
| R14 | Probe now reads every Excel sheet's dimension, not only the target sheets | Slightly slower Probe on workbooks with many large sheets | Dimension only, no header scan; measured on the sheet fixtures and the PERF-2 set |
| R15 | Old dev data folders can't be opened (T40) | Manual re-setup on the dev PC | By decision; the start-up message says what to do |
