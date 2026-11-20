# Sankalan — Feature Spec A1: Rows view, Measures by column, Export in parts

20-11-2026 · Chetan Mundhada · Live doc: https://claude.ai/artifact/XPkLZi1qkLeKqzwgLgxioa (this file is a copy; the live doc is the source of truth)

## 1. Purpose and scope

This spec adds three features to Sankalan's final version: a Rows view in the analysis builder, measures picked by column, and exports split into files of up to 1,000,000 rows so that every file opens fully in Excel. It covers behaviour, screens and states, backend design, performance, acceptance criteria, and the changes these make to Feature Spec v2.0 and Technical Spec v1.0. It replaces Feature Spec Addendum A1 (20-11-2026), with the decisions taken in the brainstorm on 20-11-2026.

| # | Feature | In one line | IDs |
| --- | --- | --- | --- |
| A | Rows view | A Rows mode in the analysis builder: pick client, template and runs, filter, choose columns, see the matching rows and export all of them as CSV | ROW-1 to ROW-15 |
| B | Measures by column | In every analysis builder, add a column, then tick the operations to apply to it; a fixed Rows entry counts rows; rename result columns from the result header | MEA-1 to MEA-11 |
| C | Export in parts | Any export with more than 1,000,000 data rows is written as numbered CSV files of up to 1,000,000 rows each, every one with its own header | EXP-8 to EXP-14 |
| D | Bug fix: temp clean-up | Emptying the temp folder after a Job must not delete DuckDB's spill files that the open connection still uses (section 11) | BUG-1, SEC-4 |

**Why C is needed.** A CSV file has no row limit, and Sankalan already writes every row. Excel opens at most 1,048,576 rows, header included, and silently drops the rest. A run holds about 10M rows, so a run's data, its issue list or a Rows export routinely goes past that. Parts of 1,000,000 data rows plus a header (1,000,001 lines) stay under Excel's limit.

| Source | What this spec takes from it |
| --- | --- |
| Feature Spec Addendum A1 (20-11-2026) | ROW-1 to ROW-13 and MEA-1 to MEA-9, amended here; screens 6.2, 6.3, 6.4, 3.2, 2.5 and dialog 7.9 |
| Feature Spec v2.0 (claude/Sankalan\_Feature\_Spec\_v2.0.md) | ANA, DO, EXP, UI, PERF and their IDs |
| Technical Spec v1.0 (claude/Sankalan\_Technical\_Spec\_v1.0.md) | Query layer, storage layout, Jobs, export pipeline and T1 to T27 |
| Sankalan UI screens canvas (https://claude.ai/artifact/U522ApcDroz6pGW3VKMvaD) | Screen and dialog numbers |

**Unchanged.** The app stays offline (SEC-1), runs one long Job at a time (T6), exports CSV only (EXP-2), and keeps every UI rule (UI-1 to UI-8). IDs in brackets point to Feature Spec v2.0; T-numbers point to Technical Spec v1.0. Decisions marked **Proposed** in section 8 were added while writing this spec and need your confirmation.

## 2. Feature A · Rows view

The Rows view turns the analysis builder into a filtered row grid. It shows the first 100,000 matching rows, gives the exact match count, and exports every matching row in the order the rows were loaded. Changes from Addendum A1 are marked **Changed** or **New**.

### 2.1 Behaviour

| ID | Feature | Detail |
| --- | --- | --- |
| ROW-1 | Entry | In New analysis (6.2), a two-way switch **Summary \| Rows** sits next to the title. Summary is the default. Rows turns the same builder into the Rows view (6.4) |
| ROW-2 | Switching | Switching keeps client, template, ticked runs and filters, and clears the result. Summary's group levels and measures are kept while the user is in Rows and come back on switching back |
| ROW-3 | Not saved | Row views can't be saved. There is no Save button; the header reads "Row views aren't saved". Leaving the view or the Analysis area clears it with no prompt, and cancels a Rows Job that is running |
| ROW-4 | Saved analyses | The switch is not shown when a saved analysis is open (6.3); saved analyses are always Summary |
| ROW-5 | Data | As ANA-2 and ANA-3: Client ▾, Template ▾, a runs list showing Run ID and file names, Select all, "N of M runs selected". Changing the template clears the settings after a confirmation |
| ROW-6 | Filters | The same filters and operators as ANA-4, combined with AND; Contains ignores case (T23). The "Is one of" list comes from the ticked runs |
| ROW-7 | Columns | A Columns section lists every template column that isn't removed, each with a tick and ↑ ↓ to reorder. All are ticked by default; the header shows "N of M ticked". At least one column must be ticked to Run or export |
| ROW-8 | Source columns | Source File, Source Sheet, Source Row and Run ID are always in the export, after the ticked columns. On screen they are hidden by default; the tick **Show them on screen** adds them to the grid after the ticked columns. Source Sheet is blank for CSV files |
| ROW-9 | Run | **Changed.** A Run button at the foot of the settings panel; progress with Cancel while it runs (UI-5). Changing the client, template, runs or filters greys the result with "Settings changed: Run again" and disables Export. Ticking, unticking or reordering columns, and Show them on screen, update the grid at once with no Run (Proposed, P1) |
| ROW-10 | Match count | The result header shows the exact number of matching rows, the runs and rows searched, and the time, e.g. "2,341,118 rows match · 3 runs · 28,796,813 rows searched · 0.9 s". Rows searched is the rows loaded in the ticked runs |
| ROW-11 | Grid | **Changed.** One row per matching data row, ticked columns in the chosen order; read-only. Shows the first 100,000 rows in the current sort. When N > 100,000 the footer reads "Showing the first 100,000 of N rows, sorted by \<column>. Export gets all of them, in the order they were loaded." When N ≤ 100,000 it reads "Showing all N rows" |
| ROW-12 | Export | **Changed.** **Export rows (.csv)** in the result header opens Export rows (7.9). The export holds every matching row, in stored order: by Run ID, then file and sheet in the run's load order, then Source Row. The grid's sort does not apply. Over 1,000,000 rows it is written in parts (EXP-8) |
| ROW-13 | Sorting | **Changed.** Clicking a column header sorts the grid by that column, ascending then descending; an arrow marks the sorted column. The sort covers all matching rows, so the grid shows the first 100,000 in that order. The default sort is the first Date column ascending, else the first ticked column. Ties are broken by Run ID, Source File, Source Sheet, Source Row. Text sorts ignoring case; blanks go last in both directions (Proposed, P2). A re-sort runs as a short Job with Cancel; Cancel keeps the previous order |
| ROW-14 | Left-out rows | **New.** Rows left out of a run on override (T18) are not in the Rows view or its export, as in Analysis |
| ROW-15 | Columns across runs | **New.** A column added after an older run shows blank for that run's rows (MAP-11); removed columns are not offered |

### 2.2 Grid layout (6.4)

| Item | Rule |
| --- | --- |
| Row height | 40 px, header 40 px (UI-1) |
| First column | Frozen on the left while the others scroll sideways; medium weight |
| Scrolling | The grid scrolls inside its panel in both directions; the window never scrolls (UI-2) |
| Alignment | Text and dates left; numbers right, with international grouping and the column's decimal places (UI-7, T13) |
| Dates | DD-MM-YYYY |
| Blank values | Empty cell |
| Long text | One line, cut with an ellipsis; full value on hover |
| Column widths | Set from the column type; the user can drag a header edge to resize; widths are not kept after leaving |

### 2.3 Export rows dialog (7.9)

| Item | Detail |
| --- | --- |
| Title | "Export N rows" |
| Summary line | Client · Template · number of runs · number of filters · approximate size · "CSV file", or "K CSV files" when split (EXP-8) |
| Filters and columns box | The filters in words; then "Columns: the N ticked columns, in their order, then Source File, Source Sheet, Source Row and Run ID"; then "Rows in the order they were loaded: by Run ID, then file, sheet and row" |
| Folder | From the template's export defaults, with **Change…** |
| File name | Default `{Client}_{Template}_Rows_{DD-MM-YYYY}.csv`, editable. Confirm before overwriting (EXP-4, EXP-10) |
| Delimiter and encoding | From the template's export defaults (EXP-3) |
| Parts line | **Changed.** Replaces A1's Excel note. Shown when N > 1,000,000 (EXP-9) |
| Disk space | Blocks Export when free space is short (EXP-13) |
| Buttons | Cancel · Export (primary) |
| While exporting | As EXP-11: stage, rows written of N, part K of M, elapsed, Cancel. When done, a banner with **Open folder** |

### 2.4 States

| State | What the user sees |
| --- | --- |
| Before the first Run | Result panel: "Pick runs and filters, then press Run" |
| No runs ticked | Run is clickable; clicking it shows "Tick at least one run" under the runs list |
| No columns ticked | Clicking Run shows "Tick at least one column" under Columns. After a Run, unticking every column empties the grid with the same message and disables Export |
| Running | Progress and Cancel in the result panel; the previous result stays greyed |
| No matching rows | "No rows match these filters." Export rows is not offered |
| Cancelled | The previous result stays greyed with "Cancelled: Run again" |
| Error | A plain message saying what to do (UI-6) |

### 2.5 Not included

Row detail panel, saving row views, editing data, quick filters in column headers, OR filters, a different order for the source columns, exporting only the rows on screen, exporting in the grid's sort order.

## 3. Feature B · Measures by column

Measures are picked by column: the user adds a column card, then ticks the operations to apply. A fixed Rows card counts every row. This applies wherever the analysis builder is used: New analysis (6.2), Template › Default outputs (3.2) and New template › Default outputs (2.5). A saved analysis (6.3) shows its measures read-only in the new wording. It replaces ANA-6.

### 3.1 Behaviour

| ID | Feature | Detail |
| --- | --- | --- |
| MEA-1 | Add a column | **+ Add column** in the Measures section opens a list: **Rows** first (MEA-10), then the template's columns not yet used as measures. Picking one adds its card. Each column, and Rows, can appear once |
| MEA-2 | Column card | Shows the column name, its type, ↑ ↓ to reorder, ✕ to remove, and a row of operation chips |
| MEA-3 | Operations by type | Number: Sum, Count, Distinct, Avg, Min, Max. Date: Count, Distinct, Min, Max. Text: Count, Distinct. Only the operations that fit are shown. Hovering a chip shows its full name (Count distinct, Average) |
| MEA-4 | Ticking | Each chip toggles on and off; a ticked chip is teal with medium weight. A card with no operation ticked is allowed while editing, but Run, Save and Preview show "Tick at least one operation for \<column>, or remove it" under that card, and do nothing else |
| MEA-5 | Operation meaning | **Changed.** Sum and Avg on numbers. Count = non-blank values in the column (T23). Distinct = number of different non-blank values. Min and Max on numbers and dates. Avg is shown and exported at the column's decimal places. To count rows, add Rows (MEA-10) |
| MEA-6 | Result column order | Measure columns come after the group-level columns, grouped by card in card order. Within a card, operations always appear in the fixed order Sum, Count, Distinct, Avg, Min, Max, whatever order they were ticked. Moving a card moves its group |
| MEA-7 | Default names | Each result column is named "\<Column> · \<Operation>", using the full operation name, e.g. "Taxable Value · Sum", "Invoice No · Count distinct", "Rows · Count". A default name follows later renames of the template column; a custom name does not |
| MEA-8 | Rename | **Changed.** Each measure column header in an unsaved result (6.2) and in the Default outputs preview (3.2, 2.5) has a ✎ button. It turns the header into a text box: Enter saves, Esc cancels. Leading and trailing spaces are trimmed; up to 100 characters. A blank name returns to the default. Names must be unique within the result, ignoring case, including the group-level headers: a clash shows "Another column is already called \<name>" and keeps the box open. Renaming never re-runs or greys the result. Hovering a header shows its source, e.g. "Invoice No · Count". Saved analyses (6.3) have no ✎; to rename, Duplicate it |
| MEA-9 | Where names are used | **Changed.** Names are kept with the analysis or default output: saved with it, used on the Run's Outputs tab and as CSV headers in exports. A default output's names apply to runs committed after the change; each committed run keeps the headers it was committed with (DO-6). Unticking an operation removes its column and its name; ticking it again starts from the default name |
| MEA-10 | Rows card | **New.** A fixed entry, **Rows**, type "All rows", with a single Count chip, ticked when added. It counts every row that passes the filters, blank or not, within each group. Default name "Rows · Count"; renamable like any measure; ↑ ↓ ✕ like any card |
| MEA-11 | Existing definitions | **Changed.** See 3.4. Needed only if a release with the old measures format ships before this spec (open item OA-1) |

### 3.2 Measures section layout

| Item | Rule |
| --- | --- |
| Section header | "Measures" with **+ Add column** on the right |
| Card | Bordered, 6 px corners. Line 1: name (medium) · type (grey) · ↑ ↓ ✕. Line 2: chips |
| Chips | 26 px high, pill shaped; ticked = teal border and tint (#0E6B6B on #E3F1F0); unticked = grey border, white |
| Note under the cards | "Results show each column's ticked operations together, in this order. Rename a result column from its header." |
| Add column list | Rows first, then columns in template order, each with its type; a search box when the template has more than 12 columns |

### 3.3 Related screens

| Screen | Change |
| --- | --- |
| 6.2 New analysis | New Measures section; result headers with ✎. Example: Invoice No Count → "Invoices"; Taxable Value Sum → "Taxable value", Max → "Taxable Value · Max" |
| 3.2 Template › Default outputs | Same Measures section; preview headers with ✎. A rename marks the tab as changed (Save / Discard / Stay on leaving) |
| 2.5 New template › Default outputs | Same as 3.2, preview on the 100,000 sample rows |
| 6.3 Saved analysis | Locked summary reads "Invoice No: Count, shown as Invoices" per ticked operation; default names read "Invoice No: Count"; no ✎ |
| 4.4 Outputs, 5.1 Run › Outputs | No layout change; headers are the ones stored with the run (MEA-9) |

### 3.4 Existing definitions (MEA-11)

Old measures are lists of "\<Operation> of \<Column> as \<Label>". Each maps to the new format as follows:

1. Cards are created in the order each column first appears in the old list.
2. Each old measure ticks its operation on that column's card. A label that differs from the new default name is kept as a custom name.
3. "Count of rows" becomes the Rows card, at the position it had in the old list.
4. The same operation on the same column twice: the first is kept and later ones are dropped. The saved analysis or default output shows "1 repeated measure was removed in the upgrade" until it is next saved.
5. Result column order follows MEA-6, so it can differ from the old order. Outputs of committed runs are not touched.

## 4. Feature C · Export in parts

Every export with more than 1,000,000 data rows is written as parts of 1,000,000 rows each, always, with no option to turn it off. Each part has its own header row, so it opens fully in Excel. An export of 1,000,000 rows or fewer is one file, as today.

### 4.1 Behaviour

| ID | Feature | Detail |
| --- | --- | --- |
| EXP-8 | When | Every export in EXP-1, plus left-out rows (T19) and the Rows view (ROW-12), goes through the shared `export()` function. When it has more than 1,000,000 data rows it is split. Exactly 1,000,000 rows is one file. "All of a run's outputs" splits each output on its own |
| EXP-9 | Part size | Parts of 1,000,000 data rows; the last part holds the remainder. Parts = N ÷ 1,000,000, rounded up (2,341,118 rows → 3 parts). Each part starts with the header row, and with the BOM when UTF-8 with BOM is chosen (EXP-3). Delimiter and date format as EXP-3 |
| EXP-10 | Names and folder | Parts go in the chosen folder, named `<name>_part01of03.csv`, where `<name>` is the file name from the dialog without `.csv`. Both numbers are zero-padded to the same width, at least 2 digits (`_part001of120`). The overwrite confirmation (EXP-4) lists every file that would be replaced. Other files in the folder are never touched, including parts of an earlier export with a different part count |
| EXP-11 | Progress | In the dialog that started it (7.5, 7.9): stage ("Reading rows", "Writing files"), rows written of N, "part K of M", elapsed time, Cancel (UI-5) |
| EXP-12 | Row order | Parts follow the export's own order, cut every 1,000,000 rows (table 4.2). Analysis results and default outputs are cut in on-screen order: the grand total is the first data row of part 1 only; subtotal rows stay next to their group's rows, so a group can run across two parts |
| EXP-13 | Disk space | Before Export is enabled, the dialog estimates the export's size and the free space on the folder's drive. When free space is below what the export needs (5.4, step 1), Export is disabled with "Not enough free space on C:. This export needs about 24.6 GB, including working space; 18.2 GB is free. Free up space or choose a folder on another drive." It is checked again when the folder changes and when the export starts |
| EXP-14 | Cancel, failure, done | Cancel deletes every part and working file written so far; files the export would have replaced are left as they were. A failure (disk full, folder removed) does the same and says what happened (UI-6). When done, a banner reads "Exported 2,341,118 rows to 3 files" with **Open folder** (EXP-7) |

### 4.2 Exports and their row order

| Export | Started from | Rows in this order | Often over 1,000,000 rows |
| --- | --- | --- | --- |
| A run's data | 3.1, 5.1 | Stored order: file and sheet in load order, then Source Row | Yes, about 10M per run |
| Left-out rows (T19) | 3.1, 5.1 | Stored order | Sometimes |
| Issue list (ISS-3) | 3.1, 5.1 | File, sheet, row | Yes, when one rule fails widely |
| One default output, or all outputs (one file each) | 5.1 | As stored with the run | Rarely |
| Analysis result (ANA-9) | 6.2, 6.3 | As on screen, with its sort and subtotals | Rarely, e.g. grouped by Invoice No |
| Rows view (ROW-12) | 6.4 | Stored order: Run ID, then file, sheet and row | Yes |

### 4.3 Dialog changes

| Dialog | Change |
| --- | --- |
| 7.4 Export data, 7.9 Export rows | When N > 1,000,000, a parts line under the file name: "Saved as 3 files of up to 1,000,000 rows each, so each opens fully in Excel: Acme\_Sales\_R-0003\_part01of03.csv to …\_part03of03.csv". The summary line says "3 CSV files". The disk-space message (EXP-13) sits above the buttons |
| 7.5 Export in progress, 7.9 while exporting | Adds "part K of M" |
| Success banner | "Exported N rows to M files" when split |

### 4.4 Not included

Splitting by a column's values (one file per month or GSTIN), choosing the part size, an option to turn splitting off, zipping the parts, exporting only some parts, .xlsx export.

## 5. Backend design

All three features run inside the existing query layer and Job runner (T5, T6, V3-1). There are no new processes, no new packages and no new catalogue tables. The Rows view adds one temporary DuckDB table. Exports gain a streaming splitter in Python. Measures move to a version-2 definition format.

### 5.1 Query layer entry points

| Entry point | New or changed | Used by |
| --- | --- | --- |
| `count_rows(spec, runs)` | New | ROW-10 match count |
| `fetch_rows(spec, runs, sort)` | New | ROW-11, ROW-13: fills the temporary table `rows_view` |
| `rows_page(first, count)` | New | Grid scrolling, read from `rows_view` |
| `estimate_export(source, options)` | New | EXP-13 and the dialogs: rows, estimated bytes, parts, file names, bytes needed, bytes free |
| `export(source, options)` | Changed | Adds the Rows view as a source, per-run chunks, and parts (5.4) |
| `run_definition(spec, runs)` | Changed | Same signature; reads version-2 measures (5.6) |
| `resolve_headers(definition)` | New | MEA-7 to MEA-9: the header text of every result column |

The Rows view spec is held in memory and never stored (ROW-3), but it has the same shape as saved definitions (V3-2): `{template_id, filters:[…], columns:[column_id, …], show_source, sort:{column_id, dir}}`.

### 5.2 Rows view queries

- **Source.** `read_parquet([data.parquet of each ticked run], union_by_name = true)`. Left-out rows are in their own file, so they are never read (ROW-14). Filters compile exactly as for Analysis.
- **Match count (ROW-10).** `SELECT count(*) … WHERE <filters>`. DuckDB reads only the filter columns.
- **First 100,000 rows (ROW-11, ROW-13).** One top-N query into a temporary table:
  - `CREATE OR REPLACE TEMP TABLE rows_view AS SELECT <every non-removed template column>, run_id, _src_file, _src_sheet, _src_row … WHERE <filters> ORDER BY <sort column> <dir> NULLS LAST, run_id, _src_file, _src_sheet, _src_row LIMIT 100000`
  - Text sort keys use `COLLATE NOCASE`, which is built in and needs no extension. Source File sorts by file name, through a join with a small table of the ticked runs' file names.
  - `ORDER BY … LIMIT` is a top-N, so DuckDB keeps a 100,000-row heap and never sorts all matching rows.
- **Both in one Job.** Run executes the count, then the top-N, with stages "Counting rows" and "Fetching the first 100,000". Cancel calls `interrupt()` on the Job's cursor (Tech Spec, Architecture).
- **Paging.** The grid fetches pages of 200 rows from `rows_view` by position. The table holds every column, so changes to column ticks, order and Show them on screen redraw from it with no query against the runs (ROW-9, P1).
- **Re-sort.** A new top-N into `rows_view` with the new order; the count is kept.
- **Display values.** Run ID and Source File names come from the catalogue (`run`, `run_file`) and are mapped in Python for the rows on screen.
- **Lifetime.** `rows_view` is dropped when the user leaves the Rows view, switches to Summary, or changes template (ROW-3).

### 5.3 Stored order

Stored order is the order rows were written to each run's `data.parquet` at Convert: file and sheet in load order, then Source Row. Runs come in Run ID order. Exports in stored order (run data, left-out rows, Rows view) never sort. They depend on two things:

1. Convert writes `data.parquet` in stored order: the `UNION ALL` of file-and-sheet selects in load order, with DuckDB's `preserve_insertion_order` on (the default).
2. An export reads one run's file per `COPY`, so DuckDB's order guarantee only ever covers a filtered scan of a single file.

An acceptance test (AC-ROW-12b) checks that the exported Source Row sequence is ascending within each file and sheet.

### 5.4 Export pipeline

Every export follows the same five steps. A source is cut into chunks: one per run for run data, left-out rows and the Rows view, and a single chunk for everything else.

1. **Estimate (EXP-13).** N is known before the export starts: rows loaded or left out (catalogue), issue counts (`run_issue_count`), rows in the stored output or result table, or the Rows view count. A `COPY` of the first 10,000 rows, or all if fewer, to `%TEMP%\Sankalan` gives bytes per row; estimate = bytes per row × N × 1.05. Bytes needed = estimate + the largest chunk's estimate (working space) + the larger of 1 GB and 10% of the estimate. A single file in plain UTF-8 needs no working space.
2. **Names (EXP-10).** Final names are worked out (one file, or M parts). Existing files with those names are listed for the overwrite confirmation.
3. **Extract.** For each chunk in order, one `COPY (SELECT …) TO '<folder>\<name>.tmp<k>'` with header, the chosen delimiter and `DATEFORMAT '%d-%m-%Y'`. In the Rows view, a run that lacks a ticked column selects `NULL` for it, and Source File comes from a list literal of that run's file names indexed by `_src_file`, so the select has no join. Run ID is a literal per run.
4. **Stream and split.** Python reads each chunk file in order, writes it into the parts (5.5), then deletes the chunk file before the next `COPY` starts. Extract and split alternate per chunk, so working space never exceeds one chunk. Parts are written as `<final name>.partial`.
5. **Finish.** The splitter's row count must equal N. If it does, each `.partial` is renamed to its final name, replacing any existing file the user confirmed. If it does not, the export fails with "Export check failed: wrote X of N rows" and cleans up.

One file in plain UTF-8, from a single chunk, skips step 4: its chunk file is renamed, as in Technical Spec v1.0. Cancel or failure at any step interrupts DuckDB, deletes every `.tmp<k>` and `.partial` file, and leaves existing files untouched (EXP-14).

### 5.5 Splitter

The splitter counts CSV records, not lines, because a value can hold a line break inside quotes. DuckDB quotes such values and doubles any quote inside them.

| Item | Design |
| --- | --- |
| Header | The first record of the first chunk file is the header. The header record of each later chunk file is skipped |
| Record end | A `\n` outside quotes. Quote state flips on every `"`; a doubled quote flips twice, so it needs no special case |
| Fast path | Blocks of 8 MB. A block with no `"`, read while outside quotes, is counted with `bytes.count(b"\n")`. When a part boundary falls inside the block, `bytes.find` locates the exact line end |
| Slow path | A block with quotes walks quote and line-end positions with `bytes.find`. Accounting data rarely has quotes, so most blocks take the fast path |
| New part | After 1,000,000 records: close the part, open the next, write the BOM if chosen, then the header |
| Progress | Rows written and part K of M, reported to the Job every 250 ms |
| Runs in | The Job's background thread; I/O and `bytes` methods release the GIL, so the window stays responsive (NF-3) |

### 5.6 Measures: definition and SQL

Version-2 measures in saved analyses, default outputs and template versions:

```json
{"definition_version": 2,
 "measures": [
   {"column_id": "_rows", "ops": [{"fn": "count", "name": null}]},
   {"column_id": "c004", "ops": [{"fn": "count", "name": "Invoices"}]},
   {"column_id": "c007", "ops": [{"fn": "sum", "name": "Taxable value"}, {"fn": "max", "name": null}]}
 ]}
```

- `fn` is one of `sum`, `count`, `count_distinct`, `avg`, `min`, `max`. Ops are stored in that fixed order on every save (MEA-6). `name: null` means the default name (MEA-7).
- **SQL.** Rows → `count(*)`; Count → `count(col)`, which skips blanks (T14, T23); Count distinct → `count(DISTINCT col)`; Avg → `avg(col)` cast to `DECIMAL(38, d)`, rounded half away from zero as T13. Subtotals use `ROLLUP` as today.
- **Result columns.** Named internally `g1 … gn` (group levels) and `m1 … mk` (measures, in MEA-6 order). `resolve_headers()` turns them into header text at display and export time.
- **Default name clashes.** If a default name equals another column's name, it gets " (2)", then " (3)". Custom names are already unique (MEA-8).
- **Committed outputs (MEA-9, DO-6).** At commit, the resolved headers of every default output are stored in a new `run_output.headers` field (a JSON list). The Outputs tab and exports read headers from there, so later renames of columns or measures never change a committed run.

### 5.7 Catalogue changes

| Table | Change |
| --- | --- |
| saved\_analysis, default\_output, template\_version | `definition` holds version-2 measures |
| run\_output | New field `headers` |
| schema\_version | +1. The upgrade converts version-1 definitions (3.4) and fills `headers` for existing run outputs from their stored definitions. Parquet files are not touched |

### 5.8 Validation before Run, Save and Preview

Checked in the window, before a Job starts, in this order; the first failure shows under its section and nothing runs:

1. No runs ticked → "Tick at least one run" (Analysis and Rows).
2. Rows view with no columns ticked → "Tick at least one column".
3. A measure card with no operation ticked → "Tick at least one operation for \<column>, or remove it" (MEA-4).
4. A default output with no name → as DO-1 today.

## 6. Performance

Speed comes from the design rather than tuning. No operation in these features sorts all matching rows, and every export streams. The targets below are provisional, set from that design. They are measured once by the release performance suite on a 16 GB, 4-core laptop, and a miss is reported, not blocking (T4).

**Design choices that set the speed:**

- The match count reads only the filter columns.
- The grid's first 100,000 rows come from a top-N query, which never sorts all matching rows.
- Grid scrolling and column changes read the 100,000-row temporary table, not the runs.
- Exports run in stored order with no sort, one run per `COPY`, so DuckDB never spills to disk for them.
- Splitting reuses the rewrite pass that the BOM already needs (Technical Spec v1.0), adding only record counting.

| ID | Operation | Target |
| --- | --- | --- |
| PERF-7 | Rows view Run on 1 run (10M rows), 2 filters, default sort: count and first 100,000 rows | ≤ 5 s |
| PERF-8 | The same across 12 runs (about 120M rows) | ≤ 30 s |
| PERF-9 | Re-sort the grid by another column across 12 runs | ≤ 30 s, cancellable |
| PERF-10 | Grid scrolling: the next page of 200 rows | ≤ 100 ms |
| PERF-11 | Ticking, unticking or reordering a column in the Rows view | ≤ 200 ms |
| PERF-12 | Export 10M rows, 20 columns, UTF-8 with BOM, 10 parts | ≤ 60 s |
| PERF-13 | Rows view export of 120M rows, 120 parts | ≤ 12 min, cancellable |
| PERF-14 | Size and free-space estimate when an export dialog opens | ≤ 2 s |

PERF-6 (an analysis result of up to 1M rows to CSV in ≤ 5 s) is unchanged: 1M rows or fewer is still one file.

## 7. Acceptance criteria

Each feature item is accepted when every criterion against it passes on a local Windows build. Speed is accepted by PERF-7 to PERF-14 (section 6).

**Test data TPL-R** (generated):

- 20 columns: 8 Text, 8 Number (2 decimals), 4 Date. 3 runs of 2,500,000 rows each (R-0001 to R-0003).
- 1% of cells are blank, except Invoice No, which is blank only where noted below. Some text values contain commas, double quotes and line breaks.
- R-0002 has 63 left-out rows. R-0002 adds the column Place of Supply. In R-0003, one sheet left Invoice No as null (MAP-6) for 400,000 rows.

### 7.1 Rows view

| AC | Item | Criterion |
| --- | --- | --- |
| AC-ROW-1 | ROW-1 | New analysis opens in Summary. Choosing Rows shows Columns and Run, no group levels, no measures and no Save button; the header reads "Row views aren't saved" |
| AC-ROW-2 | ROW-2 | With 2 runs, 2 filters, 2 group levels and 3 measures set in Summary, switching to Rows keeps the runs and filters and clears the result. Switching back shows the same group levels and measures |
| AC-ROW-3 | ROW-3 | After a Rows result, opening Clients and coming back to Analysis shows an empty builder with no prompt. Leaving while a Rows Job runs cancels it |
| AC-ROW-4 | ROW-4 | A saved analysis (6.3) shows no Summary \| Rows switch |
| AC-ROW-7 | ROW-7 | All 21 TPL-R columns are ticked by default, with "21 of 21 ticked". Unticking all and pressing Run shows "Tick at least one column" and runs nothing |
| AC-ROW-8 | ROW-8 | The grid has no source columns until Show them on screen is ticked, then they follow the ticked columns. Every export ends with Source File, Source Sheet, Source Row, Run ID in that order, whatever is shown; Source Sheet is blank for CSV rows |
| AC-ROW-9a | ROW-9 | Changing a filter, a run tick or the template greys the result with "Settings changed: Run again" and disables Export rows |
| AC-ROW-9b | ROW-9 | Unticking, ticking or moving a column, or Show them on screen, redraws the grid without greying it and without a Job |
| AC-ROW-10 | ROW-10 | The match count equals an independent `count(*)` with the same filters. Rows searched equals rows loaded in the ticked runs (7,499,937 for all three) |
| AC-ROW-11 | ROW-11 | With N > 100,000 the grid holds exactly 100,000 rows and the footer reads "Showing the first 100,000 of N rows, sorted by \<column>. Export gets all of them, in the order they were loaded." With N ≤ 100,000 it reads "Showing all N rows" |
| AC-ROW-12a | ROW-12 | The exported data rows, summed over all parts, equal the match count |
| AC-ROW-12b | ROW-12, 5.3 | In the export, Run ID never goes back to an earlier run, and within each run the rows follow file and sheet load order with Source Row ascending. Two exports after different grid sorts are byte-identical |
| AC-ROW-13 | ROW-13 | A header click sorts ascending, a second descending. After a descending sort, the first grid row holds the largest value among all matching rows, not just those shown. Blanks are last both ways. "abc" and "ABC" sort together. Equal values are ordered by Run ID, Source File, Source Sheet, Source Row. Cancel during a re-sort keeps the previous order |
| AC-ROW-14 | ROW-14 | None of R-0002's 63 left-out rows appears in the grid, the count or the export |
| AC-ROW-15 | ROW-15 | Place of Supply is blank for every R-0001 row, in the grid and in the export |
| AC-ROW-S1 | 2.4 | Filters matching nothing show "No rows match these filters." and no Export rows button |
| AC-ROW-S2 | 2.4 | Cancel during Run leaves the previous result greyed with "Cancelled: Run again" |

### 7.2 Measures by column

| AC | Item | Criterion |
| --- | --- | --- |
| AC-MEA-1 | MEA-1 | + Add column lists Rows first, then unused columns in template order. A column or Rows already added is not listed |
| AC-MEA-3 | MEA-3 | A Number card shows Sum, Count, Distinct, Avg, Min, Max; a Date card Count, Distinct, Min, Max; a Text card Count, Distinct. Hover shows Count distinct and Average |
| AC-MEA-4 | MEA-4 | A card with no operation ticked lets the user keep editing. Run, Save and Preview each show "Tick at least one operation for \<column>, or remove it" and start nothing |
| AC-MEA-5 | MEA-5 | Taxable Value · Average shows and exports with 2 decimal places, rounded half away from zero |
| AC-MEA-6 | MEA-6 | Ticking Max, then Sum, on Taxable Value gives the columns Sum, then Max. Moving the card above Invoice No moves both columns before Invoice No's |
| AC-MEA-7 | MEA-7 | Default headers read exactly "Taxable Value · Sum", "Invoice No · Count distinct", "Rows · Count". Renaming the template column Taxable Value to Taxable Amt changes the default header; a custom header stays |
| AC-MEA-8 | MEA-8 | ✎ then Enter saves a name; Esc cancels; a blank name restores the default. "invoices" is refused when a group header or another measure is "Invoices". A rename doesn't grey the result or change its time. Saved analyses show no ✎ |
| AC-MEA-9 | MEA-9 | Renaming a default output's measure, then committing a new run: the new run's Outputs tab and CSV use the new header, and earlier runs keep their old one. Unticking and re-ticking an operation brings back its default name |
| AC-MEA-10 | MEA-10 | On R-0003, Rows · Count equals the run's rows loaded, while Invoice No · Count is 400,000 lower. In a grouped result, Rows · Count per group adds up to the grand total |
| AC-MEA-11 | MEA-11, 3.4 | Only if OA-1 needs it. Old "Sum of Taxable Value as Taxable", "Count of rows" and "Max of Taxable Value" become a Taxable Value card (Sum named "Taxable", Max default) and a Rows card, in that order. A repeated measure is dropped with the upgrade note |

### 7.3 Export in parts

| AC | Item | Criterion |
| --- | --- | --- |
| AC-EXP-8a | EXP-8 | 1,000,000 rows give one file with no part suffix; 1,000,001 rows give 2 parts of 1,000,000 and 1 rows |
| AC-EXP-8b | EXP-8, 4.2 | Each export in table 4.2 splits when over 1,000,000 rows: run data, left-out rows, issue list, a default output, all outputs (each separately), an analysis result, the Rows view |
| AC-EXP-9a | EXP-9 | Every part opens in Excel 365 with all its rows: a full part has 1,000,001 records with the header, the last has the remainder plus the header. Each part starts with the same header, and with the BOM when chosen |
| AC-EXP-9b | EXP-9, 5.5 | Values with line breaks, quotes and delimiters next to a part boundary are never split across parts. Every part parses as valid CSV with the expected record count. The data rows of all parts, joined in order, are byte-identical to the same export written as one file (test build) |
| AC-EXP-10 | EXP-10 | 3 parts are named `_part01of03` to `_part03of03`; 120 parts `_part001of120` to `_part120of120`. The overwrite confirmation lists exactly the files to be replaced. An older `_part04of04` in the folder is untouched |
| AC-EXP-11 | EXP-11 | Progress shows the stage, rows written of N and "part K of M", updated at least every second |
| AC-EXP-12 | EXP-12 | A 2,100,000-row analysis result with subtotals: the grand total is the first data row of part 1 and appears in no other part. Rows and subtotals across all parts, in order, match the on-screen order |
| AC-EXP-13 | EXP-13 | With a destination drive that has less free space than needed, Export is disabled and the message shows both sizes. Choosing a folder on a drive with enough space enables it |
| AC-EXP-14a | EXP-14 | Cancel during part 2 of 3 leaves no part, `.tmp` or `.partial` file. A file that would have been replaced keeps its original SHA-256 |
| AC-EXP-14b | EXP-14, 5.4 | Disk full during writing, or a forced row-count mismatch (test build), fails the export with a plain message and the same clean-up |
| AC-EXP-14c | EXP-14 | A split export ends with the banner "Exported N rows to M files" and Open folder opens the chosen folder |

## 8. Decisions

D38 to D46 come from Addendum A1, and D47 to D60 from the brainstorm, all on 20-11-2026. P1 to P7 were added while writing this spec and need confirmation (OA-2).

| # | Date | Decision | Item |
| --- | --- | --- | --- |
| D38 | 20-11-2026 | A Rows view, as a Summary \| Rows switch in the analysis builder | ROW-1, ROW-2 |
| D39 | 20-11-2026 | Row views are never saved | ROW-3 |
| D40 | 20-11-2026 | Source File, Source Sheet, Source Row and Run ID are always exported; hidden on screen by default | ROW-8 |
| D41 | 20-11-2026 | No row detail panel | 2.5 |
| D42 | 20-11-2026 | Show the first 100,000 matching rows; export all | ROW-11, ROW-12 |
| D43 | 20-11-2026 | Measures are picked by column, then operations ticked | MEA-1 to MEA-4 |
| D44 | 20-11-2026 | All six operations kept | MEA-3 |
| D45 | 20-11-2026 | Result measure columns grouped by column, in card order | MEA-6 |
| D46 | 20-11-2026 | Result columns are renamed from the result header | MEA-8 |
| D47 | 20-11-2026 | Exports over 1,000,000 data rows are always split, with no option | EXP-8 |
| D48 | 20-11-2026 | Splitting applies to every export, through the shared `export()` function | EXP-8 |
| D49 | 20-11-2026 | Parts of 1,000,000 data rows each | EXP-9 |
| D50 | 20-11-2026 | Parts go in the chosen folder | EXP-10 |
| D51 | 20-11-2026 | No splitting by a column's values | 4.4 |
| D52 | 20-11-2026 | Analysis results split like every other export, in on-screen order | EXP-12 |
| D53 | 20-11-2026 | The Rows view exports in stored order, not the grid's sort | ROW-12 |
| D54 | 20-11-2026 | The Rows view leaves out left-out rows | ROW-14 |
| D55 | 20-11-2026 | Speed: the best that is feasible without complex code; targets are provisional and reported | PERF-7 to PERF-14 |
| D56 | 20-11-2026 | An export is blocked when free space is below its estimated size plus a margin | EXP-13 |
| D57 | 20-11-2026 | A fixed Rows card counts rows | MEA-10 |
| D58 | 20-11-2026 | Committed runs keep their output headers after a rename | MEA-9 |
| D59 | 20-11-2026 | No renaming on saved analyses | MEA-8 |
| D60 | 20-11-2026 | Result names are unique, group-level headers included | MEA-8 |
| P1 | Proposed | Column ticks, column order and Show them on screen redraw the grid with no Run | ROW-9 |
| P2 | Proposed | Sort ties broken by Run ID, Source File, Source Sheet, Source Row; text ignores case; blanks last | ROW-13 |
| P3 | Proposed | Names are trimmed, up to 100 characters, and unique ignoring case; a clashing default name gets " (2)" | MEA-8, 5.6 |
| P4 | Proposed | Each run stores its output headers at commit (`run_output.headers`) | MEA-9, 5.6 |
| P5 | Proposed | Parts are written as `.partial` and renamed at the end, so Cancel never loses a file being replaced | EXP-14, 5.4 |
| P6 | Proposed | Extract and split alternate per run, so working space stays at one run's share | 5.4 |
| P7 | Proposed | A repeated measure in an old definition is dropped in the upgrade | 3.4 |

## 9. Changes to existing docs

Feature Spec v2.0 needs 14 updates and Technical Spec v1.0 needs 9. Six canvas screens change, and dialogs 7.4 and 7.5 gain the parts details.

### 9.1 Feature Spec v2.0

| v2.0 item | Change |
| --- | --- |
| Analysis note "Not included: … a raw-row browsing grid" | Remove "a raw-row browsing grid" |
| Out of scope: "Charts, calculated columns, drill-down to rows, a raw-row browsing grid" | Becomes "Charts, calculated columns, drill-down from a summary row to its rows" |
| UX-10 Analysis | Adds the Rows view (ROW) |
| ANA-6 Measures | Replaced by MEA-1 to MEA-11 |
| ANA-7 Result | Measure column order and names follow MEA-6 to MEA-8 |
| DO-1 Definition | The builder's measures follow MEA |
| DO-6 Saved with the run | Committed runs keep their output headers (MEA-9) |
| DO-7, ANA-9, ISS-3 | Exports over 1,000,000 rows are split (EXP-8) |
| EXP-1 What can be exported | Adds the Rows view (ROW-12) and left-out rows (T19) |
| EXP-4 File naming | The overwrite confirmation lists every part to be replaced (EXP-10) |
| EXP-7 During and after | Cancel deletes every part; the banner names the file count (EXP-14) |
| New | EXP-8 to EXP-14 |
| Performance targets | Adds PERF-7 to PERF-14 |
| Decisions | Adds D38 to D60 |
| SEC-4 | Becomes: "Temporary files live in the user's temp folder and are deleted when the operation ends, except the database engine's own spill files still in use, which it deletes itself; the folder is emptied completely at close and start-up" (BUG-1) |

### 9.2 Technical Spec v1.0

| Section | Change |
| --- | --- |
| Query layer | New entry points and the `rows_view` temporary table (5.1, 5.2) |
| Ingestion, 4. Convert | States that `data.parquet` is written in stored order with `preserve_insertion_order` on (5.3) |
| Query layer, Exports | The pipeline in 5.4 and the splitter in 5.5 replace the single `.part` file flow; adds the size estimate |
| Saved analyses (V3-2) | The JSON example uses version-2 measures (5.6) |
| Outputs, Default outputs | Output files use internal column names `g1…`, `m1…`; headers come from `run_output.headers` |
| Storage, catalogue tables | `run_output` gains `headers`; `schema_version` +1 (5.7) |
| T23 | Adds: the Rows card counts every row |
| Tests | Adds: stored-order export, splitter boundaries with quoted line breaks, part names, disk check, headers kept after a rename, Rows view sort and paging |
| Performance suite | Adds PERF-7 to PERF-14 |

### 9.3 Screens and test cases

| Item | Change |
| --- | --- |
| 6.2, 6.3, 3.2, 2.5 | As Addendum A1, plus Rows at the top of the Add column list |
| 6.4 Rows view | As Addendum A1, with the new footer wording (ROW-11) |
| 7.9 Export rows | Excel note replaced by the parts line; adds the row-order line and the disk-space message |
| 7.4 Export data | Adds the parts line and the disk-space message |
| 7.5 Export in progress | Adds "part K of M" |
| Not drawn | Rows view states (2.4), the header rename box, the Add column list, the disk-space message, the split success banner |
| Test cases sheet | One test case per acceptance criterion in section 7 (38), plus generation rules for the TPL-R data |

## 10. Risks and open items

Four items need a decision before the technical spec update. The largest risk is that stored-order exports depend on DuckDB keeping a single file's row order, which a test checks on every build.

### 10.1 Open items

| # | Question | Item |
| --- | --- | --- |
| OA-1 | Build order. If this spec is built into the first release of the final version, no definition ever uses the old measures format, so MEA-11, section 3.4 and the upgrade step are dropped. Will it ship in the first release? | MEA-11 |
| OA-2 | Confirm the proposed decisions P1 to P7 | Section 8 |
| OA-3 | Grid default sort. A1 sets the first Date column, ascending. Stored order is the alternative: the first page appears with no top-N scan, and the grid matches the export. Keep A1's default? | ROW-13 |
| OA-4 | Can a Summary have no measures, only group levels (e.g. a list of distinct GSTINs)? Neither v2.0 nor A1 says | MEA, ANA-7 |

### 10.2 Risks

| # | Risk | Impact | Plan |
| --- | --- | --- | --- |
| R7 | Stored-order exports rely on DuckDB keeping a single file's row order in a filtered scan (5.3) | Rows exported out of load order | AC-ROW-12b on every build. Fallback: `ORDER BY _src_file, _src_sheet, _src_row` per run, a 10M-row sort that may spill |
| R8 | A split export needs working space of up to one run's share; a single-run export needs about twice its size free | Exports blocked on full laptops | The EXP-13 check states the need up front; choosing another drive is offered |
| R9 | Splitter mistakes on quoted line breaks near a part boundary | A record cut across two parts | AC-EXP-9b with values planted at the boundary |
| R10 | A 120M-row export is about 24 GB at 200 bytes a row (assumed), so PERF-13 depends on SSD write speed | PERF-13 missed on slower disks | Measured in the release suite; reported, not blocking (T4) |

## 11. Bug fixes

### 11.1 BUG-1 · Temp clean-up deletes DuckDB's live spill files (SEC-4)

Found 20-11-2026 while building the full-size TPL-R data (Phase A1-0, since discarded). **Must be fixed** in this build; it is independent of features A to C and can hit any large load or analysis today.

| Item | Detail |
| --- | --- |
| Symptom | A long operation fails with "Failed to delete file …\Temp\Sankalan\duckdb_temp_<pid>_…_storage_….tmp". Seen at a run's commit during a 2,500,000-row-per-run load |
| Cause | After every Job, `Storage` empties `%TEMP%\Sankalan` (SEC-4). That also deletes the spill storage the open DuckDB connection is still using (Windows allows the delete). DuckDB's next use of those blocks fails |
| When it happens | Whenever data spilled to disk in one Job is still held for the next: a large load, a large analysis result kept between Jobs, a large temporary table |
| Fix | After a Job, delete everything in `%TEMP%\Sankalan` **except** the open connection's own spill files (`duckdb_temp_<pid>_…`); DuckDB deletes those as blocks free and when the connection closes. Closing the data folder and start-up still empty the folder completely |
| Spec change | SEC-4 as in 9.1. Technical Spec v1.0: the DuckDB settings (temp folder), "Spill files live in…", the No leftovers row and the SEC-4 row say the same |

| # | Acceptance criterion |
| --- | --- |
| AC-BUG-1a | A temporary table large enough to spill under a small memory limit, created in one Job and read in the next, reads back in full; the old code fails this test |
| AC-BUG-1b | After every Job the temp folder holds nothing but the open connection's `duckdb_temp_<pid>_…` files; after closing the data folder, and after a restart, it is empty |
| AC-BUG-1c | A full-size load (3 runs × 2,500,000 rows) commits all three runs |
