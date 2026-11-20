# Sankalan — Technical Spec A1: Rows view, Measures by column, Export in parts

20-11-2026 · Chetan Mundhada · Builds on Technical Spec v1.0 (`docs/specs/technical-spec-v1.0.md`)

## 1. Purpose and scope

This spec says how to build Feature Spec A1 (`docs/specs/feature-spec-a1.md`) in the existing V2 codebase: a Rows
view in the analysis builder (ROW-1 to ROW-15), measures picked by column (MEA-1 to MEA-11), and exports split into
parts of up to 1,000,000 rows (EXP-8 to EXP-14). It is the input for the implementation plan.

It was written from a read of the current code (`v2`, commit `f80084f`) and four DuckDB 2.0.0 spikes run on the dev
PC on 20-11-2026 (section 3). Where Feature Spec A1 cannot be built as written, or the spikes found a better way,
this spec says so and lists the correction in section 14. As with Technical Spec v1.0, **this spec wins where the
two differ**.

| Source | What this spec takes from it |
| --- | --- |
| Feature Spec A1 (20-11-2026), copy in `docs/specs/feature-spec-a1.md` | Behaviour, IDs ROW, MEA, EXP-8 to EXP-14, PERF-7 to PERF-14, AC-*, D38 to D60, P1 to P7 |
| Technical Spec v1.0 | Architecture, Jobs, storage, query layer, export path, T1 to T27 |
| `docs/PROGRESS.md` decisions | Spike S1/S2 (DuckDB writes only to the data folder and `%TEMP%\Sankalan`), export path, labels |
| Current code | Module layout, what already exists and what changes (section 4) |

**Unchanged.** Offline (SEC-1), DuckDB configuration locked after start-up, one long Job at a time (T6), all SQL in
`sankalan/query/`, CSV only (EXP-2), UI rules UI-1 to UI-8, no new runtime packages, no new processes.

## 2. Decisions

T28 to T44 continue Technical Spec v1.0's numbering. The four answered on 20-11-2026 close Feature Spec A1's open
items OA-1, OA-3 and OA-4 and correct EXP-12. The others are technical and follow from the code and the spikes.

| # | Decision | Items |
| --- | --- | --- |
| T28 | DuckDB writes each export chunk to `%TEMP%\Sankalan` (it may write nowhere else, spike S2). Python streams the chunks into the parts in the chosen folder. Chunk files have no header; Python writes the header into each part | EXP-8, 5.4 |
| T29 | Stored order is made true at Convert: `data.parquet` is written with `ORDER BY _src_file, _src_row`. Every stored-order export also has `ORDER BY _src_file, _src_row` per run, so it never relies on DuckDB's unstated order | 5.3, ROW-12, R7 |
| T30 | The Rows view fetches its first 100,000 rows in two steps: a top-N on the sort key and row identity only, then the full rows for those 100,000 identities | ROW-11, ROW-13, PERF-7 to PERF-9 |
| T31 | **Answered (OA-3).** The grid's default order is stored order (Run ID, then file and sheet in load order, then Source Row), the same as the export. A header click sorts. Ties in a sort are broken by stored order | ROW-13, P2 |
| T32 | **Answered.** The grand total stays the last row of a result export, as built and as on screen (pinned at the bottom). When split, it is the last row of the last part | EXP-12 |
| T33 | **Answered (OA-1).** A catalogue upgrade (schema version 2) converts version-1 definitions to version 2 and fills `run_output.headers`. MEA-11 and Feature Spec A1 section 3.4 stay | MEA-11, 5.7 |
| T34 | **Answered (OA-4).** A Summary or default output may have group levels and no measures. It then shows one row per distinct group combination, with no subtotal or grand total rows. With no group levels, at least one measure is still needed | MEA, ANA-7, DO-1 |
| T35 | Each committed run keeps the headers of its outputs in `run_output.headers` (JSON list), group headers included. The Outputs tab and exports read them; they never change after commit (P4 confirmed) | MEA-9, DO-6 |
| T36 | Parts are written as `<final name>.partial`. Finishing renames each file being replaced to `<name>.replaced`, renames the parts into place, then deletes the `.replaced` files; any failure renames them back. Finishing can't be cancelled and takes milliseconds (P5 extended) | EXP-14 |
| T37 | Before writing and again before finishing, every file to be replaced is opened for writing to check it isn't open in Excel. If it is: "\<file> is open in another program. Close it, then export again." | EXP-10, EXP-14 |
| T38 | The part size is `PART_ROWS = 1_000_000` in `sankalan/exporting.py`. Tests pass a smaller value as an argument; the app never changes it | EXP-9 |
| T39 | The free-space check looks at two drives: the temp drive needs the largest chunk plus a margin, the destination drive needs the whole export plus a margin. When both are the same drive the needs add up | EXP-13 |
| T40 | A Rows view result is a temporary table named `_rows_<uuid>`, dropped through the window's existing `drop_results` / `pending_drops` path, like analysis results | ROW-3 |
| T41 | Measures are held as cards (column + ticked operations) in memory and in JSON version 2; the compiler works on the flattened list in MEA-6 order, so its SQL is unchanged | MEA-1 to MEA-6 |
| T42 | One header widget, `RenamableHeader`, gives the ✎ rename to the analysis grid (6.2) and both Default outputs previews (3.2, 2.5) | MEA-8 |
| T43 | `PagedGrid` gains an optional frozen first column (a second, overlaid table view, Qt's frozen-column pattern) and a hook that hands header clicks to the screen. Only the Rows view uses them | ROW-11, ROW-13, 2.2 |
| T44 | Job progress gains a detail line (`ctx.set_detail("part 2 of 3")`), shown under the stage by the progress panel | EXP-11 |

Feature Spec A1's proposed decisions: P1, P3, P4, P5, P6 and P7 are confirmed as written. P2 is confirmed with one
refinement (T31): ties are broken by stored order, where "file and sheet" means load order (`_src_file`, which
numbers each file-and-sheet in load order), not file name.

## 3. Findings from the code and the spikes

Spikes ran with DuckDB 2.0.0 from the project's `.venv`, 8 threads, on generated data: 10M rows per run, 22 columns
(8 text, 8 DECIMAL(38,2), 4 date, plus `_src_file` and `_src_row`), about 2.4 GB as CSV per run. Times are from the
dev PC, which is faster than the 16 GB, 4-core release laptop.

| # | Question | Result | Consequence |
| --- | --- | --- | --- |
| S7a | Does Convert's `UNION ALL` of file-and-sheet selects, written by `COPY … TO parquet`, keep load order? | **No.** With 10 parts of 1M rows the parts were interleaved through the whole file (part 0 spans rows 0 to 7.9M) | Today's run-data export, which has no `ORDER BY`, can write rows out of file and row order on a multi-file run. Fixed by T29 |
| S7b | Cost of sorting at Convert (`ORDER BY _src_file, _src_row`) | 13.2 s for 10M × 22 columns; 5.2 s for a narrow file (faster than unsorted, 9.8 s) | Acceptable inside PERF-1 (2 minutes); the plan measures it against today's Convert |
| S7c | Does a filtered `COPY` of a sorted file keep its order? | Yes, 3 of 3 runs | Order holds in practice, but T29 still adds `ORDER BY` |
| S7d | Cost of `ORDER BY _src_file, _src_row` at export | 10.8 s vs 9.0 s for 10M rows to CSV (+20%); output byte-identical | Paid for certainty; also exports runs committed before T29 correctly |
| S7e | Top-N with every column, 30M rows (3 runs), sort by a Date | 32.2 s in one step; **9.1 s** in two steps (keys 3.4 s, then join 5.7 s) | T30 |
| S7f | The same, sort by Text `COLLATE NOCASE DESC` | 53.0 s in one step; **19.1 s** in two steps | T30; PERF-9 is at risk (R11) |
| S7g | `COLLATE NOCASE` with extensions off and the configuration locked | Works; NULLs last in both directions | No extension needed |
| S7h | `COPY … CSV` quoting | Values with `\r`, `\n`, `"` or the delimiter are quoted, quotes doubled; spaces are not quoted | The splitter's quote rule (5.5) holds |
| S7i | Match count with 2 filters, 30M rows | 1.0 s | PERF-7 and PERF-8 counts are cheap |

Other findings from the code:

- Exports already write the header in Python and stream DuckDB's headerless `.csv.part` from `%TEMP%\Sankalan` to
  `<dest>.part` (`sankalan/exporting.py`). The splitter replaces that streaming loop; there is no rename shortcut
  for plain UTF-8, because the temp folder and the destination are different places.
- Result tables already use internal names `g1…gn`, `m1…mk` (`query/compiler.py`); headers are labels on
  `OutColumn`. `open_output` builds a committed output's headers from today's column names, so a column rename
  currently changes committed runs' headers. T35 stops that.
- `_src_file` is the `run_file.file_index`, one per file **and sheet**, numbered in load order.
- `data.parquet`'s `run_id` holds the internal run ID, not "R-0001". Run ID order needs the catalogue's
  `run_number`.
- The catalogue's `MIGRATIONS` are SQL lists only; T33 needs a Python step (section 11).
- `definition.check()` refuses a definition without measures ("Add at least one measure"); T34 relaxes it.

## 4. Module map

New modules are marked **New**; everything else is a change to an existing module.

| Module | Change |
| --- | --- |
| `sankalan/model/definition.py` | Version-2 measures: `Op`, `MeasureCard`, `ROWS = "_rows"`, `flat_measures()`, `to_dict`/`from_dict` v2, new checks, default names (6.1, 6.2) |
| `sankalan/model/upgrade.py` **New** | Version-1 → version-2 conversion of a definition, and of a template snapshot (section 11); pure Python |
| `sankalan/model/rowspec.py` **New** | `RowSpec` and sort keys (7.1) |
| `sankalan/model/export.py` | `ExportRequest.kind` gains `rows`; part file names (`part_names`) |
| `sankalan/query/compiler.py` | Measures from `flat_measures()`; `_rows` → `count(*)`; no-measure results (T34); shared `filtered_base()` used by the Rows view |
| `sankalan/query/headers.py` **New** | `resolve_headers(definition, columns)` (6.3) |
| `sankalan/query/rows.py` **New** | Rows view SQL: count, two-step fetch, page, re-sort, export chunks (7.2 to 7.5) |
| `sankalan/query/convert.py` | `write_data` adds `ORDER BY _src_file, _src_row` (T29) |
| `sankalan/query/export.py` | `ExportSource` (headers, chunk SQL, row count); run data and left-out rows add `ORDER BY`; Rows view chunks; result exports with T34 |
| `sankalan/query/layer.py` | `open_output` takes stored headers; `Result` labels from `resolve_headers` |
| `sankalan/query/catalogue.py` | `run_output.headers` read and written; template snapshot and definitions read as v2 |
| `sankalan/db/catalogue.py` | `SCHEMA_VERSION = 2`; migrations may hold Python steps; version-2 migration (section 11) |
| `sankalan/exporting.py` | Rewritten around `estimate()` and `export()` with chunks, splitter and parts (section 5) |
| `sankalan/exporting_split.py` **New** | The record splitter (5.5), pure Python, no Qt, no DuckDB |
| `sankalan/jobs/job.py` | `set_detail()` and `Progress.detail` (T44) |
| `sankalan/analysis.py`, `analyses.py` | Headers from `resolve_headers`; `write_outputs` returns headers for commit; describe lines in the new wording |
| `sankalan/rowsview.py` **New** | Rows view Job work: run, re-sort, page, export source (no SQL) |
| `sankalan/run/pipeline.py` | Commit stores `run_output.headers` |
| `sankalan/ui/widgets/builder.py` | Measures section replaced by `MeasuresSection`; sections can be hidden (Rows mode) |
| `sankalan/ui/widgets/measures.py` **New** | `MeasuresSection`, `MeasureCardWidget`, `OpChip`, `AddColumnPopup` (8.1) |
| `sankalan/ui/widgets/header_rename.py` **New** | `RenamableHeader` (8.2) |
| `sankalan/ui/widgets/paged_grid.py` | Frozen first column and header-click hook (T43) |
| `sankalan/ui/widgets/progress.py` | Shows `Progress.detail` |
| `sankalan/ui/screens/analysis.py` | Summary \| Rows switch, hosts the Rows view, header rename on the result |
| `sankalan/ui/screens/rows_view.py` **New** | `ColumnsSection`, `RowsResult` panel and states (section 9) |
| `sankalan/ui/screens/template_outputs.py`, `new_template.py` | Previews use `RenamableHeader`; renames mark the tab changed |
| `sankalan/ui/dialogs/export_dialog.py` | Estimate on open, parts line, disk message, overwrite list, Export rows mode (7.9), new banners |

## 5. Feature C · Export in parts

### 5.1 Shape of an export

Every export becomes one or more `ExportSource`s, built inside the Job by `runs.export_items`, the analysis screen
or the Rows view:

```python
@dataclass(frozen=True)
class ExportSource:
    headers: list[str]          # display names, written by Python
    chunks: list[Chunk]         # extracted and split in order
    rows: int                   # N, known before writing

@dataclass(frozen=True)
class Chunk:
    select: str                 # SELECT of text values in export form, no ORDER BY
    order: str                  # "ORDER BY _src_file, _src_row", or "" (results carry their own order)
```

| Export | Chunks | N from |
| --- | --- | --- |
| A run's data | 1 | `count(*)` of `data.parquet` (Parquet metadata, instant) |
| Left-out rows | 1 | `count(*)` of `left_out.parquet` |
| Issue list (committed or Validate step) | 1 | `count(*)` of `issues.parquet` |
| One default output | 1 | rows of the stored output as exported (shown rows + grand total) |
| All outputs | 1 source per output, each split on its own | as above |
| Analysis result | 1 | `count_rows` + grand total row |
| Rows view | 1 per ticked run that has matches, in Run ID order | the match count (ROW-10) |

The SELECTs are today's (`query/export.py`), with T29's `ORDER BY` for run data and left-out rows. The issue list
keeps its `ORDER BY` file, row, rule. Result exports keep `ORDER BY (_depth = 0), …` (grand total last, T32).

### 5.2 Steps

`exporting.export(ctx, temp_dir, sources, folder, names, options, *, replace: set[Path], part_rows=PART_ROWS)`:

1. **Check** (EXP-13, T37). Recompute the plan (5.3) and free space (5.4); fail with the dialog's message if short.
   Open each file in `replace` for append and close it, to catch a file open in Excel.
2. **Extract** chunk *k*: `COPY (<select> <order>) TO '%TEMP%\Sankalan\<job>-<k>.csv' (FORMAT csv, HEADER false,
   DELIMITER …, QUOTE '"', DATEFORMAT '%d-%m-%Y')`. Its returned row count is kept. Stage "Reading rows",
   fraction from DuckDB's query progress.
3. **Split** chunk *k* into the current part (5.5), then delete the chunk file. Stage "Writing files", rows written
   of N, detail "part K of M". Then the next chunk (P6: working space never exceeds one chunk).
4. **Verify.** Records counted in each chunk file equal its `COPY` count, and the total equals N. Otherwise fail
   with "Export check failed: wrote X of N rows" (written to the log as the error class only, SEC-5).
5. **Finish** (T36), with `ctx.set_cancellable(False)`: re-check T37, rename each existing target to
   `<name>.replaced`, rename each `.partial` to its final name, delete the `.replaced` files. On any error, rename
   the `.replaced` files back and delete the `.partial` files.

`ctx.on_abort` deletes every `<job>-<k>.csv`, `.partial` and (after restoring) `.replaced` file. The temp folder is
also emptied after every Job (SEC-4). Start-up removes no files from user folders: a `.partial` left by a power cut
stays, with an honest name.

### 5.3 Plan and names (EXP-9, EXP-10)

`plan(rows, file_name, part_rows)` → the final names:

- N ≤ `part_rows`: one file, the dialog's name.
- Otherwise M = ceil(N / part_rows) parts, `<stem>_partKKofMM.csv`, where `<stem>` is the file name without a final
  `.csv` (any case) and both numbers are zero-padded to `max(2, len(str(M)))` digits.
- Export all outputs: one plan per output, each named from the pattern as today.

The dialog shows the names, lists the existing ones for the overwrite confirmation (all of them, up to 10 then
"and 4 more"), and passes the confirmed set as `replace`. Other files in the folder are never looked at again.

### 5.4 Estimate and free space (EXP-13, T39)

`exporting.estimate(ctx, temp_dir, sources, folder, options)` runs as a short Job ("Checking size") when the dialog
opens; the dialog shows "Checking size…" and keeps Export disabled until it returns.

- **Bytes per row:** `COPY (<first chunk's select> LIMIT 10000)` (no `ORDER BY`, so no sort) to a temp file; size
  ÷ rows. If the first chunk has fewer than 10,000 rows, later chunks are sampled too, up to 10,000 in all. Header
  and BOM bytes are added once per part. Estimate = bytes per row × N × 1.05.
- **Needs:** temp drive = largest chunk's estimate + max(1 GB, 10% of it); destination drive = estimate + max(1 GB,
  10% of the estimate); same drive (compared by `os.path.splitdrive` of the resolved paths) → the sum.
- **Free:** `shutil.disk_usage` of the folder and of `%TEMP%\Sankalan`; read again on the UI thread (no Job) when the
  folder changes and once more in step 1.
- **Message:** the destination's wording is Feature Spec A1's. When the temp drive is the short one: "Not enough free
  space on C: for working files. This export needs about 2.6 GB there; 1.1 GB is free. Free up space on C:."

The estimate result (N, M, names, bytes) also feeds the summary line ("3 CSV files · about 610 MB") and the parts line.

### 5.5 Splitter (`exporting_split.py`)

Chunk files hold only data records, so the splitter's only job is to count records and cut on record boundaries.

| Item | Design |
| --- | --- |
| Input | Chunk files in order, read in 8 MB blocks, binary |
| Record end | `\n` outside quotes. Quote state flips on every `"`; DuckDB doubles a quote inside a value, which flips twice (S7h) |
| Fast path | Outside quotes and `b'"' not in block`: `block.count(b"\n")`. If the part fills inside the block, `bytes.find` steps to the exact `\n` |
| Slow path | Walk the block by `bytes.find` of `"` and `\n`, counting `\n` only outside quotes |
| Quote state across blocks and chunks | Carried across blocks; must be "outside" at the end of every chunk, or the export fails as in 5.2 step 4 |
| New part | Close the part; open `<next>.partial`; write the BOM if chosen, then the header line (`header_line`, as today) |
| Progress | `ctx.set_rows(written, N)` and `ctx.set_detail(f"part {k} of {m}")` at most every 250 ms; `ctx.check_cancelled()` per block |
| Interface | `Splitter(open_part, header, bom, part_rows)`, `.feed(path)`, `.close() -> counts`; no Qt or DuckDB, so it is unit-tested alone |

### 5.6 Dialogs and banners

| Item | Change |
| --- | --- |
| 7.4 Export data / output / analysis | Estimate on open; summary "N rows · CSV file" or "N rows · 3 CSV files · about X"; parts line under the file name; disk message above the buttons |
| Overwrite confirmation | Lists every file that would be replaced (EXP-10), then sets `replace` |
| 7.5 Exporting | Stage, rows written of N, "part K of M" (T44), elapsed, Cancel |
| Success banner | One file: as today. Split: "Exported 2,341,118 rows to 3 files", Open folder (EXP-14) |
| Cancel banner | "Export cancelled. No files were written; files that would have been replaced are unchanged." |

## 6. Feature B · Measures by column

### 6.1 Model (T41)

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
Definition.upgrade_note: str | None             # "1 repeated measure was removed in the upgrade" (3.4 rule 4)

def flat_measures(defn) -> list[FlatMeasure]:   # (column_id or None for Rows, fn, name), cards in order,
                                                # ops in the fixed order Sum, Count, Distinct, Avg, Min, Max
```

JSON is Feature Spec A1 5.6 with `"definition_version": 2`, plus `"upgrade_note"` only when set. Saving clears the
note. `from_dict` reads version 2 only; a version-1 dict raises, so nothing old slips past the upgrade.

### 6.2 Checks (`definition.check`)

In order, each a `DefinitionError` with the screen's wording:

1. Each column appears on at most one card; Rows at most once.
2. A card with no op: "Tick at least one operation for \<column>, or remove it" (MEA-4).
3. Ops fit the type: Number all six; Date count, count_distinct, min, max; Text count, count_distinct; Rows count only.
4. No measure card and no group level: "Add a group level or a measure" (T34).
5. Custom names: trimmed, 1 to 100 characters, unique ignoring case across every header in the result (MEA-8).

The screens run the same checks before Run, Save and Preview (Feature Spec A1 5.8) and show the message under the
section; the Job never starts.

### 6.3 Headers (`query/headers.py`)

`resolve_headers(definition, columns) -> list[str]`, in result order (groups, then `flat_measures()`):

- Group: the column name, plus " (removed)" when removed (T23).
- Measure, custom: its name.
- Measure, default: "\<column name> · \<Sum | Count | Count distinct | Average | Min | Max>", "Rows · Count" for
  the Rows card; " (removed)" after the column name when removed.
- Clashes: group headers and custom names are placed first; then each default in order gets " (2)", " (3)" … if its
  name is already taken, ignoring case. Two group levels on the same column (by Month and by Year) get the same
  treatment.

Hover text for a measure header is the default form "Invoice No · Count", whatever its name (MEA-8).

### 6.4 SQL (`query/compiler.py`)

Unchanged except that the compiler loops over `flat_measures()`: Rows → `count(*)`, Count → `count(col)`, Count
distinct → `count(DISTINCT col)`, Average → today's exact `average_sql`, Sum, Min, Max as today. Subtotals use
`ROLLUP` as today.

**No measures (T34).** `SELECT CAST(n AS INTEGER) AS _depth, g1 … gn FROM (…) GROUP BY g1 … gn`: no `ROLLUP`, so no
subtotal or grand total rows. The screen disables Show subtotals and hides the pinned total row; `grand_total()`
returns None; the export has no "Grand total" row. The summary line counts result rows as today.

### 6.5 Names in saved analyses, default outputs and runs

- **Unsaved analysis (6.2).** A rename sets `Op.name` on the screen's definition and redraws the header; it never
  marks the result stale and never re-runs (MEA-8). Unticking an op drops it with its name; re-ticking adds a new
  `Op` with `name=None` (MEA-9).
- **Saved (6.3).** Saved with the definition; no ✎. Locked summary per op: "Invoice No: Count, shown as Invoices",
  or "Invoice No: Count" for a default name.
- **Default outputs (3.2, 2.5).** A rename in the preview sets the name on that output's definition and marks the
  tab changed (Save / Discard / Stay).
- **Committed runs (T35).** At the Outputs step `analysis.write_outputs` returns `resolve_headers()` for each output
  with the template's columns at that moment; the commit transaction stores them in `run_output.headers`.
  `layer.open_output` takes the stored headers instead of rebuilding them. Template column renames and default-output
  renames after the commit never change them.

## 7. Feature A · Rows view engine

### 7.1 Spec

```python
@dataclass
class RowSpec:                     # in memory only, never stored (ROW-3); same shape as V3-2 definitions
    template_id: str
    filters: list[Filter]          # the builder's filters, compiled exactly as for Analysis
    columns: list[str]             # ticked column IDs, in order
    show_source: bool              # Show them on screen (ROW-8)
    sort: tuple[str, bool] | None  # (key, ascending); None = stored order (T31)
```

Sort keys: a column ID, or `_run`, `_file`, `_sheet`, `_row` for the source columns.

The runs are passed as `RunRef(id, number, label, data_path, file_names)`, in Run ID order, read from the catalogue
at Run (file names from `run_file`).

### 7.2 Queries (`query/rows.py`)

All read `read_parquet([data.parquet of each ticked run], union_by_name = true)` through the compiler's shared
`filtered_base()`, which selects every needed column as itself or a typed NULL (MAP-11, ROW-15) and applies the
filters. Left-out rows are in their own file, never read (ROW-14). Removed columns are never offered or selected.

| Entry point | SQL |
| --- | --- |
| `count_rows(con, spec, columns, runs)` | `SELECT count(*) FROM base WHERE <filters>`. With no filters, the sum of `rows_loaded` from the catalogue (no scan). Rows searched (ROW-10) is always that sum |
| `fetch_rows(con, spec, columns, runs, table)` | Two steps (7.3); fills `table` with `_pos` 1…≤100,000, every non-removed template column, `run_id`, `_src_file`, `_src_sheet`, `_src_row` |
| `rows_page(con, table, keys, first, count)` | `SELECT <keys> FROM table WHERE _pos > first AND _pos <= first + count ORDER BY _pos` |
| `export_source(con, spec, columns, runs)` | One chunk per run with matches (7.5) |

### 7.3 Two-step fetch (T30)

**Sorted** (`spec.sort` set):

1. Keys: `CREATE TEMP TABLE _k AS SELECT run_id, _src_file, _src_row, row_number() OVER (ORDER BY <keys>) AS _pos
   FROM (SELECT run_id, _src_file, _src_row, <sort expr> FROM base WHERE <filters> ORDER BY <keys> LIMIT 100000)`.
2. Rows: `CREATE TEMP TABLE <table> AS SELECT k._pos, s.* FROM base s JOIN _k k USING (run_id, _src_file,
   _src_row)`, then `DROP TABLE _k`.

`<keys>` = `<sort expr> ASC|DESC NULLS LAST, <run number>, _src_file, _src_row`, where:

| Key | Sort expression |
| --- | --- |
| Text column | `col COLLATE NOCASE` (blank text is already NULL, T14) |
| Number, Date column | `col` |
| `_run` | `CASE run_id WHEN '<id>' THEN <number> … END` |
| `_file` | `CASE` on (run_id, `_src_file`) → file name, `COLLATE NOCASE` |
| `_sheet` | `nullif(_src_sheet, '') COLLATE NOCASE` (CSV rows have no sheet; blanks last) |
| `_row` | `_src_row` |

**Stored order** (`spec.sort` is None, the default): the same two steps, run per run in Run ID order with key
`_src_file, _src_row` and `LIMIT` set to the rows still needed, stopping at 100,000. The first run usually fills it,
so later runs are never read.

Both steps run in one Job with stages "Counting rows", "Finding the first 100,000" and "Reading rows". Cancel
interrupts DuckDB; `ctx.on_abort` drops `_k` and the new table.

### 7.4 Run, re-sort, columns

| Action | Work |
| --- | --- |
| Run | `count_rows`, then `fetch_rows` into a new `_rows_<uuid>`; only then the previous table is dropped, so Cancel keeps it (2.4) |
| Header click (ROW-13) | A cancellable Job: `fetch_rows` with the new sort into a new table; the count is kept. Done → swap tables, drop the old one; cancelled → nothing changes |
| Tick, untick, reorder columns, Show them on screen (P1) | No Job against the runs: the grid's columns change and pages are read again from the same table (`rows_page`, PERF-11) |
| Leave, switch to Summary, change template | The table goes to `window.drop_results` (T40) |

Display values for the page's rows are mapped in Python: `run_id` → "R-0003", (`run_id`, `_src_file`) → file name,
numbers and dates as UI-7 (`formats`).

### 7.5 Export chunks (ROW-12)

For each ticked run, in Run ID order, one chunk over that run's file alone:

```sql
SELECT <text of each ticked column, in order>, <file name CASE>, _src_sheet, _src_row, '<R-0003>'
FROM (SELECT <columns or typed NULLs>, _src_file, _src_sheet, _src_row
      FROM read_parquet('<run>/data.parquet') WHERE <filters>)
ORDER BY _src_file, _src_row
```

Text values follow `query/export.py`'s `_text` (numbers at the column's decimals, dates DD-MM-YYYY). Headers: the
ticked columns' names, then Source File, Source Sheet, Source Row, Run ID (ROW-8). Runs with no matches are skipped;
the per-run match counts come from one `SELECT run_id, count(*) … GROUP BY run_id` in the estimate Job. The grid's
sort never applies.

## 8. Measures UI

### 8.1 Measures section (`ui/widgets/measures.py`)

| Widget | Build |
| --- | --- |
| `MeasuresSection` | Heading "Measures", "+ Add column" on the right, the cards, the note under them (Feature Spec A1 3.2). Emits `changed` on add, remove, move and tick |
| `MeasureCardWidget` | Bordered frame, 6 px corners. Line 1: name (medium), type (grey), ↑ ↓ ✕ (`icon_button`). Line 2: chips. An error label under the card for MEA-4 |
| `OpChip` | Checkable `QPushButton`, 26 px, pill; theme QSS for ticked (#0E6B6B on #E3F1F0) and unticked; tooltip with the full name |
| `AddColumnPopup` | A popup frame: a search box when the template has more than 12 columns, then a list of Rows and unused columns with their types. Picking adds the card with no op ticked (Rows: Count ticked) |

`DefinitionBuilder` swaps its measure rows for `MeasuresSection` and gains `set_sections(filters=…, groups=…,
measures=…, subtotals=…)`, used by the Rows mode. `definition()` keeps each op's name from the previous definition
when the same (column, fn) is still ticked.

### 8.2 Header rename (`ui/widgets/header_rename.py`)

`RenamableHeader(QHeaderView)`:

- `set_renamable(callback)` says which sections have ✎ (measure columns of an unsaved result or preview).
- Paints a ✎ in the right 20 px of those sections; a click there starts editing, a click elsewhere sorts as before.
- Editing: a `QLineEdit` over the section, text selected. Enter emits `rename_requested(section, text)`; the screen
  validates (6.2 rule 5) and either calls `finish()` or `show_error("Another column is already called …")`, which
  keeps the box open with a small error label below it. Esc or focus loss cancels.
- Tooltips per section from a callback (6.3 hover text).

Used by `PagedGrid` (6.2) and by the `QTableWidget` previews in `template_outputs.py` (3.2) and `new_template.py`
(2.5).

## 9. Rows view UI

### 9.1 Analysis screen

- A two-way switch "Summary | Rows" beside the title; hidden for a saved analysis (ROW-4).
- **Rows mode** keeps the same `DefinitionBuilder` with groups, measures and subtotals hidden, so filters carry
  over and Summary's settings come back on switching back (ROW-2). The settings panel adds `ColumnsSection`; Save is
  hidden; the header reads "Row views aren't saved".
- The result area is a `QStackedWidget`: today's Summary result, or `RowsResult`.
- `leave_guard()` returns None in Rows mode (ROW-3: no prompt). `closing()` cancels a running Rows Job and drops
  the table (T40).
- Settings changes (client, template, runs, filters) grey the result with "Settings changed: Run again" and disable
  Export rows (ROW-9). Column changes don't.

### 9.2 `ui/screens/rows_view.py`

| Part | Build |
| --- | --- |
| `ColumnsSection` | Every non-removed template column with a tick and ↑ ↓; "N of M ticked"; the tick "Show them on screen". Emits `columns_changed` (no Run) |
| `RowsResult` header | "2,341,118 rows match · 3 runs · 28,796,813 rows searched · 0.9 s"; Export rows (.csv) |
| Grid | `PagedGrid` over `RowsSource` (a `PageSource` reading `rows_page`), frozen first column, 40 px rows, read-only, widths from type, resizable, reset on leave |
| Header click | Hook (T43) → re-sort Job with progress and Cancel in the result panel; arrow on the sorted column |
| Footer | N ≤ 100,000: "Showing all N rows". Else: "Showing the first 100,000 of N rows, sorted by \<column>." or, in stored order, "…of N rows, in the order they were loaded." Then "Export gets all of them, in the order they were loaded." |
| States | Feature Spec A1 2.4, using the existing empty, progress and error panels |

### 9.3 Export rows (7.9)

The Export dialog with `ExportRequest(kind="rows", items=…)`: title "Export N rows"; summary line; a box with the
filters in words (`analyses.describe`), the columns line and the row-order line; folder and encoding from the
template's export defaults; file name `{Client}_{Template}_Rows_{DD-MM-YYYY}.csv` built with `csv_file_name`;
estimate, parts line and disk message as 5.6.

## 10. Stored order (T29)

- `convert.write_data`: `COPY (<UNION ALL> ORDER BY _src_file, _src_row) TO data.parquet`. `split.py` already sorts
  when it rewrites.
- Run data, left-out rows and Rows view chunks: `ORDER BY _src_file, _src_row` on a single run's file.
- Rows view and run-data exports therefore come out in Run ID, file-and-sheet load order, Source Row, whatever the
  DuckDB version does with unordered scans. Feature Spec A1's risk R7 is retired; AC-ROW-12b stays as the check.
- Runs committed before this change are exported correctly (the `ORDER BY` sorts them); their Parquet files are
  not rewritten.

## 11. Catalogue version 2

`MIGRATIONS` becomes `dict[int, list[str | Callable[[con], None]]]`. Version 2, in one transaction after the start-up
backup (T10):

1. `ALTER TABLE run_output ADD COLUMN headers VARCHAR DEFAULT '[]'`.
2. Python step:
   - `saved_analysis.definition`, `default_output.definition`, and the default outputs inside each
     `template_version` snapshot: version 1 → 2 by `model/upgrade.py` (Feature Spec A1 3.4 rules 1 to 4; a repeated
     measure sets `upgrade_note`).
   - `run_output.definition`: converted the same way, and `headers` filled with the headers that run showed before
     the upgrade: the old labels, or the old defaults ("Sum of Taxable Value", "Count of rows") with the column
     names at upgrade time. So committed runs look exactly as before (rule 5, D58).
3. Parquet files are not touched. `schema_version` gets row 2.

`model/upgrade.py` is pure Python with its own unit tests (the AC-MEA-11 example, repeated measures, Count of rows
position, labels equal to the new default).

## 12. Performance

The design avoids sorting all matching rows anywhere except T29's per-run export sort, which the spike put at +20%.
Expected times are scaled from the dev-PC spikes; the release suite measures them on the 16 GB, 4-core laptop and
reports misses without blocking (T4).

| ID | Target | Expected from the spikes | Note |
| --- | --- | --- | --- |
| PERF-7 | ≤ 5 s | ~1–2 s in stored order (count + first run only); ~3–6 s sorted | Stored-order default (T31) helps most |
| PERF-8 | ≤ 30 s | ~5 s stored order; 35–40 s sorted by a Date (12 runs) | Sorted case may miss |
| PERF-9 | ≤ 30 s | 35–40 s by a Date; ~75 s by Text (NOCASE) | Likely miss on Text (R11) |
| PERF-10 | ≤ 100 ms | `_pos` range on a 100,000-row table | |
| PERF-11 | ≤ 200 ms | Page reads from the temp table only | |
| PERF-12 | ≤ 60 s | ~11 s extract + split at disk speed for 2.4 GB | |
| PERF-13 | ≤ 12 min | 12 × (~11 s extract + ~2.4 GB split) | SSD-bound (R10) |
| PERF-14 | ≤ 2 s | 10,000-row sample + metadata counts; Rows view adds one grouped count | |

Convert gains the T29 sort: measure PERF-1 and PERF-2 again.

## 13. Tests

| Area | Tests |
| --- | --- |
| Splitter (unit) | Random CSV with quotes, doubled quotes, `\r`, `\n` and delimiters planted on and around part and block boundaries; records per part checked with Python's `csv`; parts joined without headers byte-identical to the input; BOM and header on every part; unbalanced quote at chunk end fails |
| Plan and names (unit) | 1,000,000 → one file; 1,000,001 → 2 parts; `_part01of03`; `_part001of120`; `.CSV` stem |
| Export engine | `part_rows=1000` on small fixtures: every export kind in Feature Spec A1 table 4.2; cancel during extract, split and before finish (no `.partial`, chunk or `.replaced` file; replaced files keep their SHA-256); forced failure during finish restores originals; a target held open (T37); count mismatch via a test hook; free-space refusal via a patched `disk_usage` |
| Stored order | A multi-file load large enough to run in parallel (≥ 2M rows, marked slow): `data.parquet` ascending in `_src_file, _src_row`; Rows export Run ID never goes back; two exports after different grid sorts byte-identical (AC-ROW-12b) |
| Measures | Model round trip; checks 6.2; `resolve_headers` defaults, clashes, removed columns; compiler with Rows and no-measure results; AC-MEA-1 to AC-MEA-10 |
| Upgrade | Version-1 catalogue fixture → version 2: definitions, snapshot outputs, `run_output.headers` equal to the old headers; AC-MEA-11 |
| Rows view engine | Count vs independent `count(*)`; sorted fetch: first row is the true max over all matches, blanks last, case ignored, ties in stored order; stored-order fetch across runs; paging; re-sort cancel keeps the old table; AC-ROW-10 to AC-ROW-15 |
| GUI | Switch, Columns section, grid redraw without a Job, header rename (Enter, Esc, blank, clash), chips and Add column popup, export dialog parts line and overwrite list; screen fit at 1366×768 |
| Release only | PERF-7 to PERF-14 on TPL-R at full size, and a 120M-row Rows export |

**TPL-R fixture.** `tests/fixtures/generate.py` gains TPL-R with a scale argument: full size (3 × 2,500,000 rows,
Feature Spec A1 section 7) for slow and performance tests, and a small size (3 × 2,500 rows, same shape, same
left-out rows and blank Invoice No ratio) for the normal suite with `part_rows=1000`. Acceptance figures that depend
on full size (7,499,937 rows searched, 400,000 blank Invoice No) are checked in the slow tests only.

**Existing tests that change.** Default measure headers ("Sum of Taxable Value" → "Taxable Value · Sum", "Count of
rows" → "Rows · Count"), the destination part name (`.part` → `.partial`), the cancel banner text, and every test
that builds a version-1 definition. Expected figures do not change.

## 14. Changes to other docs

### 14.1 Feature Spec A1

| Item | Change | From |
| --- | --- | --- |
| 5.4 step 3 | Chunk files go to `%TEMP%\Sankalan`, not the chosen folder; they have no header | T28 |
| 5.4 step 1 | Working space is needed on the temp drive; a single plain UTF-8 file also needs it (no rename shortcut) | T39 |
| 5.5 Header row | Not needed: Python writes the header to each part | T28 |
| 5.3, R7 | Convert sorts; stored-order exports add `ORDER BY`; R7 retired | T29 |
| 5.2 | Two-step fetch; stored-order default; tie-break by stored order | T30, T31 |
| 5.6 Source File | `CASE` on `_src_file` (today's helper) instead of a list literal | Code |
| ROW-11, ROW-13 | Default order is stored order; footer wording for it (9.2) | T31 |
| EXP-12, AC-EXP-12 | Grand total last: last row of the last part | T32 |
| MEA, ANA-7 | Group levels with no measures allowed; then no subtotals or grand total | T34 |
| 5.7 | `upgrade_note` in the definition JSON, no new column | T33 |
| 10.1 | OA-1, OA-3, OA-4 closed; OA-2 closed with P2 refined | Section 2 |

### 14.2 Technical Spec v1.0

Feature Spec A1 section 9.2 applies, plus: Decisions gain T28 to T44; Ingestion 4. Convert writes `data.parquet`
sorted by `_src_file, _src_row`; Exports describe the temp chunks, splitter, `.partial`/`.replaced` finish and the
two-drive check; Architecture → Jobs gains the progress detail line; Storage → catalogue upgrades may run Python
steps.

### 14.3 Test cases

Add one case per Feature Spec A1 acceptance criterion (38), corrected for T31 (AC-ROW-11 footer), T32 (AC-EXP-12)
and T34 (a new AC: a Summary with only group levels lists distinct values, no totals). Update existing cases whose
expected headers use the old default names. Keep `docs/specs/test-cases.md` and the live sheet in step.

## 15. Suggested build order

Each phase ends with the full suite passing, as today. C comes first because A's export depends on it; B is
independent of both.

| Phase | Scope | Depends on |
| --- | --- | --- |
| A1-0 | TPL-R generator (both sizes); confirm S7 findings as tests; record PERF-1/PERF-2 baseline before T29 | — |
| A1-1 | Stored order (T29) and the export engine: `ExportSource`, plan, estimate, splitter, finish and rollback, progress detail | A1-0 |
| A1-2 | Export dialogs: estimate, parts line, disk message, overwrite list, banners | A1-1 |
| A1-3 | Measures v2: model, checks, `resolve_headers`, compiler, no-measure results, `run_output.headers`, catalogue v2 upgrade | — |
| A1-4 | Measures UI: section, cards, chips, Add column popup, `RenamableHeader` on 6.2, 3.2, 2.5; 6.3 wording | A1-3 |
| A1-5 | Rows view engine: `RowSpec`, `query/rows.py`, `rowsview.py`, export chunks | A1-1 |
| A1-6 | Rows view UI: switch, Columns section, grid with frozen column and sort hook, states, Export rows dialog | A1-2, A1-5 |
| A1-7 | Spec and test-sheet updates (section 14), slow tests at full size, performance suite additions | All |

## 16. Risks and open items

| # | Risk or open item | Impact | Plan |
| --- | --- | --- | --- |
| R8 | Working space: a Rows export needs one run's chunk (about 2.4 GB) on the temp drive, usually C:, even when exporting to another drive | Blocked exports on a full C: | T39 states it up front, with the drive named |
| R9 | Splitter mistakes near a part boundary | A record cut across parts | Unit tests with planted values (section 13); per-chunk count check (5.2 step 4) |
| R10 | PERF-13 depends on disk write speed (about 29 GB for 120M rows) | Missed on slow disks | Measured, reported (T4) |
| R11 | Sorted Rows view across 12 runs, especially by Text, is likely slower than PERF-8/PERF-9's 30 s | Long waits for a re-sort | Cancellable with progress; stored order is the default. The plan tries `lower(col)` keys against `COLLATE NOCASE` in A1-0 |
| R12 | T29 adds a sort to every load | PERF-1/PERF-2 a few seconds slower per 10M rows | Measured in A1-0 against today's baseline |
| R13 | Output headers differ between committed runs before and after the upgrade ("Sum of Taxable Value" vs "Taxable Value · Sum") | Mixed wording across runs | By design (D58); runs keep the headers they were committed with |
| R14 | Today's run-data exports from multi-file runs may already be out of order (S7a) | Wrong order in files already exported | Fixed by T29 for all future exports; no action on files already written |
