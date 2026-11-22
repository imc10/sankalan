# Plan: Feature Spec A1 — Rows view, Measures by column, Export in parts

> **Superseded** (21-11-2026): A1 was never started; Feature Spec A2 and Technical Spec A2 replace it. The A2 plan is `docs/plans/a2-implementation-plan.md` (phases A2-1 to A2-6).

Status: **planned** (20-11-2026). Not started. Sessions record progress in `docs/PROGRESS.md` (phases A1-0 to A1-7).

## Context

| Doc | What it fixes |
| --- | --- |
| `docs/specs/feature-spec-a1.md` (live: claude.ai/artifact/XPkLZi1qkLeKqzwgLgxioa) | Behaviour and IDs: ROW-1…15, MEA-1…11, EXP-8…14, PERF-7…14, AC-ROW/MEA/EXP, D38–D60, P1–P7 |
| `docs/specs/technical-spec-a1.md` (live: claude.ai/artifact/UnHqNXxcu3FQf3LMFgH5rm) | How to build it: decisions T28–T44, spike findings S7a–S7i, module map, build order. **Wins over Feature Spec A1** where they differ (its section 14.1 lists the corrections) |

Settled on 20-11-2026: grand total last in result exports (T32); catalogue upgrade kept (T33); Rows view opens in
stored order (T31); a Summary may have group levels and no measures (T34); P1, P3–P7 confirmed, P2 refined by T31.

**How this plan is executed.** One Claude Code session per phase, in order, on `v2` (as `docs/IMPLEMENTATION_PLAN.md`).
Each session reads `CLAUDE.md`, `docs/PROGRESS.md`, this plan's phase, and only the spec sections named in it; it ends
with the full suite passing, `PROGRESS.md` updated, and a commit. If a phase is too big, finish a coherent part and
record the rest.

---

## Guiding approach

- **Export in parts first** (A1-0 to A1-2): the Rows view's export depends on it, and T29 fixes a real ordering bug
  in today's run-data export (S7a), so it is worth landing early.
- **Engine before UI** in each feature: A1-1 before A1-2, A1-3 before A1-4, A1-5 before A1-6. Every engine phase
  is headless and test-driven; the app keeps working at the end of every phase (interim adapters where noted).
- **Small fixtures, small parts.** The normal suite uses TPL-R at small size and `part_rows=1000`, so splitting is
  exercised in seconds. Full-size TPL-R and real 1,000,000-row parts run in tests marked `slow`; PERF-7…14 are
  marked `perf` (release only, T4).
- **Expected figures are the oracle.** Feature Spec A1 section 7 figures (as corrected by Technical Spec A1 14.3)
  become assertions. Don't change one to make a test pass: ask.
- **Hard rules unchanged:** offline, all SQL in `sankalan/query/` (+ DDL in `sankalan/db/`), DuckDB only inside
  Jobs, one long Job at a time, temp files only in `%TEMP%\Sankalan`, no cell values in logs, no new packages.

## Files by phase

New files in **bold**. A1-3/A1-4 share few files with A1-1/A1-2/A1-5/A1-6 (marked †), so the measures track could
run in its own worktree branch if the user wants it in parallel; otherwise keep the order below.

| Phase | Main files |
| --- | --- |
| A1-0 | **`tests/fixtures/tpl_r.py`**, `tests/conftest.py`, `pytest.ini`, **`tools/spikes/a1_baseline.py`**, `tools/spikes/RESULTS.md` |
| A1-1 | `query/convert.py`, `query/export.py`, `exporting.py`, **`exporting_split.py`**, `model/export.py`, `jobs/job.py`, `ui/widgets/progress.py`, `runs.py`†, `analyses.py`†, `ui/dialogs/export_dialog.py` (wiring only) |
| A1-2 | `ui/dialogs/export_dialog.py`, `ui/screens/run.py`, `ui/screens/template.py`, `ui/screens/new_run_steps.py` (export entry points) |
| A1-3 | `model/definition.py`, **`model/upgrade.py`**, **`query/headers.py`**, `query/compiler.py`†, `query/layer.py`, `query/export.py`† (result export), `query/catalogue.py`, `db/catalogue.py`, `analysis.py`, `analyses.py`†, `run/pipeline.py`, `manage.py`, `newtemplate.py`, `ui/widgets/builder.py` (interim adapter) |
| A1-4 | **`ui/widgets/measures.py`**, **`ui/widgets/header_rename.py`**, `ui/widgets/builder.py`, `ui/widgets/paged_grid.py`†, `ui/screens/analysis.py`†, `ui/screens/template_outputs.py`, `ui/screens/new_template.py`, `ui/theme.py` |
| A1-5 | **`model/rowspec.py`**, **`query/rows.py`**, `query/compiler.py` (`filtered_base`), **`rowsview.py`**, `ui/window.py` (drops) |
| A1-6 | `ui/screens/analysis.py`, **`ui/screens/rows_view.py`**, `ui/widgets/paged_grid.py`, `ui/widgets/builder.py` (`set_sections`), `ui/dialogs/export_dialog.py` (Export rows) |
| A1-7 | `docs/specs/*`, `docs/specs/test-cases.md`, **`tests/perf/test_a1_perf.py`** |

---

## Phase A1-0 — Fixtures, markers, baselines

**Spec:** Feature Spec A1 §7 (TPL-R); Technical Spec A1 §3, §12, §13, R11, R12.

1. `pytest.ini`: add marker `slow` ("full-size data; run before release and when touching export or Convert").
2. `tests/fixtures/tpl_r.py`: `generate_tpl_r(out, scale)` writing CSV source files for runs R-0001…R-0003, and
   `expected(scale)` with the figures. Shape (Feature Spec A1 §7): 20 columns (8 Text incl. Invoice No, 8 Number
   with 2 decimals, 4 Date); 1% blank cells except Invoice No; text values with commas, double quotes and line
   breaks; R-0002 adds Place of Supply (21 columns) and has 63 rows that fail an Error rule; in R-0003 one file has
   no Invoice No column (mapped "leave as null", MAP-6).
   - `scale="small"`: 3 × 2,500 rows, 400 rows with null Invoice No in R-0003 → rows searched 7,437.
   - `scale="full"`: 3 × 2,500,000 rows in 5 files per run, 400,000 null Invoice No → rows searched 7,499,937.
   - Deterministic (seeded), written with Python's `csv` module so quoting is real.
3. `tests/conftest.py`: `tpl_r_storage(scale)` fixture that creates the TPL-R template (with the Error rule that
   leaves the 63 rows out), loads and commits the three runs through `run/pipeline.py` (R-0002 with Continue despite
   errors and a comment), and returns storage, template ID and run IDs. Small scale per test; full scale cached per
   session for `slow` tests.
4. `tools/spikes/a1_baseline.py` (dev only, results appended to `tools/spikes/RESULTS.md` as S7):
   - Convert time for one 10M-row, 4-file CSV run **before** T29 (baseline for R12).
   - Two-step top-N sort keys: `col COLLATE NOCASE` vs `lower(col)`, on 30M rows (R11). Record which is faster and
     whether results are identical for TPL-R text (Unicode letters included).
   - Re-run S7a on the current `write_data` to confirm the interleaving on real staged parts.
5. `tests/unit/test_fixture_pack.py`: small TPL-R generates and its figures self-check (row counts, blank ratio,
   quoted values present, the 63 failing rows).

**Exit:** TPL-R small builds in under ~10 s and commits three runs; baselines recorded; suite green.

## Phase A1-1 — Stored order and the export engine

**Spec:** Technical Spec A1 T28, T29, T36–T39, T44, §5, §10; Feature Spec A1 EXP-8…14, §4.2.

1. **Stored order (T29).** `convert.write_data`: `COPY (<UNION ALL> ORDER BY _src_file, _src_row) TO data.parquet`.
   `query/export.py`: run data and left-out rows add `ORDER BY _src_file, _src_row`.
2. **Sources.** `query/export.py`: `Chunk(select, order)`, `ExportSource(headers, chunks, rows)`; `run_data`,
   `left_out`, `issue_list`, `result` return sources with N (Parquet `count(*)`, or `count_rows` + grand total for
   results). `copy_csv(con, chunk, path, delimiter, limit=None)` (limit for the size sample).
3. **Splitter.** `sankalan/exporting_split.py`: `Splitter(open_part, header, bom, part_rows)`, `.feed(path,
   on_progress, check_cancelled)`, `.close() -> per-chunk and total record counts`; 8 MB blocks, fast and slow
   paths, quote state carried, error if a chunk ends inside quotes (Technical Spec A1 §5.5). No Qt, no DuckDB.
4. **Engine.** `sankalan/exporting.py` rewritten:
   - `PART_ROWS = 1_000_000`; `plan(rows, file_name, part_rows) -> list[str]` (names, §5.3); `model/export.py`
     gains `part_names(file_name, parts)`.
   - `estimate(ctx, temp_dir, sources, folder, options) -> Estimate(rows, parts, names, existing, bytes_total,
     bytes_largest_chunk, need_dest, need_temp, free_dest, free_temp, same_drive)` (§5.4).
   - `free_space(folder, temp_dir, estimate) -> SpaceCheck(ok, message)`, plain OS calls (UI thread allowed).
   - `export(ctx, temp_dir, items: list[(ExportSource, file_name)], folder, options, *, replace: set[Path],
     part_rows=PART_ROWS) -> list[ExportResult(paths, rows)]`: steps 1–5 of §5.2 for every item, then one Finish for
     all items (so Export all outputs is all-or-nothing on Cancel, EXP-14). `export_many` is removed.
   - `check_writable(paths)` (T37): open for append and close; a sharing violation → `FileInUse(path)`.
   - Test hooks like today's `_after_chunk`: `_after_block`, `_before_finish`, `_during_finish(i)`, and
     `_count_fault` (adds 1 to the verified count). Hooks are module functions the tests monkeypatch; nothing reads
     the environment.
5. **Progress detail (T44).** `JobContext.set_detail(text)`, `Progress.detail`; `ui/widgets/progress.py` shows it
   under the stage. Stages "Reading rows", "Writing files"; detail "part K of M".
6. **Callers, interim.** `runs.export_items` and `analyses.export_items` return `(ExportSource, file_name)` items;
   `ExportDialog._work` calls the new `export()` with `replace` = the files it confirmed today (single file or the
   outputs' names) and the default `part_rows`. Dialog UI is unchanged until A1-2.
7. **Tests** (`tests/unit/test_export_split.py` **new**, `tests/engine/test_export.py`):
   - Splitter: random records with quotes, doubled quotes, `\r`, `\n`, delimiters planted at part and 8 MB block
     boundaries (use a small block size argument); parse each part with `csv`; parts joined without headers are
     byte-identical to the input; header and BOM per part; unbalanced quote fails. (AC-EXP-9a/9b, R9)
   - Plan and names: 1,000,000 → one file; 1,000,001 → 2 parts (also as a `slow` engine test with real rows,
     AC-EXP-8a); `_part01of03`, `_part001of120`, `.CSV` stem (AC-EXP-10).
   - Every export kind of Feature Spec A1 §4.2 except the Rows view, on small TPL-R with `part_rows=1000`
     (AC-EXP-8b partly); result export: grand total only in the last part, subtotals next to their rows (AC-EXP-12
     as corrected by T32).
   - Cancel during extract, during split and at `_before_finish`: no chunk, `.partial` or `.replaced` file left;
     replaced files keep their SHA-256 (AC-EXP-14a). Failure in `_during_finish(1)`: originals restored.
     `_count_fault`: "Export check failed" and clean-up (AC-EXP-14b). Free-space refusal with a patched
     `shutil.disk_usage`, both drives (AC-EXP-13 engine part).
   - File held open: open the target with `CreateFileW` and share mode 0 via `ctypes` (as Excel does) → `FileInUse`.
   - Stored order (`slow`): a 4-file, ≥ 2,000,000-row load; `data.parquet` ascending in `_src_file, _src_row`; run
     data export ascending.
   - Existing export tests updated: `.part` → `.partial`, `export_many` → `export`.

**Exit:** all exports go through the new engine and split above `part_rows`; stored order holds; suite green. Record
the Convert time after T29 against the A1-0 baseline.

## Phase A1-2 — Export dialogs

**Spec:** Technical Spec A1 §5.4, §5.6; Feature Spec A1 §2.3 (parts line, disk space), §4.3, EXP-10, EXP-11,
EXP-13, EXP-14; screens 7.4, 7.5.

1. `ExportDialog`: on open, start the estimate as a short Job ("Checking size"); Export disabled with "Checking
   size…" until it returns. If another Job is running, show today's busy message and keep Export disabled (SH-02).
2. Summary line ("N rows · CSV file" / "N rows · 3 CSV files · about X"), parts line under the file name when
   M > 1, the disk-space message above the buttons (both wordings of §5.4). Folder change → `free_space` again with
   no Job; file name change → names recomputed from the estimate.
3. Overwrite confirmation lists every existing target (up to 10, then "and N more"); its answer is the `replace`
   set. `FileInUse` → "\<file> is open in another program. Close it, then export again." in the dialog.
4. Progress: stage, rows written of N, detail "part K of M", elapsed, Cancel. Banners: "Exported N rows to M files"
   with Open folder; the new cancel banner text.
5. Export all outputs: estimate per output; parts lines per output that splits; one overwrite list for all.
6. **Tests** (`tests/gui/test_export_dialog.py` **new**, or extend the existing export GUI tests): parts line and
   summary with `part_rows` patched small; overwrite list contents; disk message with a patched `disk_usage` and
   re-enable on folder change (AC-EXP-13); progress detail (AC-EXP-11); banner and Open folder target
   (AC-EXP-14c); dialog fits 1366×768.

**Exit:** every export dialog shows size, parts and space; suite green; one manual export of a full-size run opened
in Excel (each part opens with all rows).

## Phase A1-3 — Measures v2 engine and catalogue version 2

**Spec:** Technical Spec A1 T33–T35, T41, §6.1–§6.5, §11; Feature Spec A1 MEA-5…MEA-11, §3.4, §5.6, §5.7.

1. **Model** (`model/definition.py`): `ROWS`, `Op`, `MeasureCard`, `Definition.measures: list[MeasureCard]`,
   `upgrade_note`, `flat_measures()`, `FN_NAMES` (Sum, Count, Count distinct, Average, Min, Max) and short chip
   names; `to_dict` writes `definition_version: 2` with ops in fixed order; `from_dict` refuses version 1; checks of
   §6.2 in order, including T34 and name rules (trim, ≤ 100, unique ignoring case).
2. **Upgrade** (`model/upgrade.py`): `measures_v1_to_v2(list) -> (cards, removed_count)`,
   `definition_v1_to_v2(dict)`, `snapshot_v1_to_v2(dict)` (default outputs inside a template snapshot),
   `old_headers(definition_v1, columns)` ("Sum of Taxable Value", "Count of rows", labels).
3. **Headers** (`query/headers.py`): `resolve_headers(definition, columns)` and `source_text(...)` for hover (§6.3).
4. **Compiler**: loop over `flat_measures()`; `_rows` → `count(*)`; no-measure results as `GROUP BY` without
   `ROLLUP` (T34); `OutColumn.label` from `resolve_headers`. `layer.grand_total` returns None with no measures;
   `query/export.result` writes no grand total then.
5. **Committed headers (T35):** `analysis.write_outputs` returns headers per output; `run/pipeline.py` passes them to
   the commit; `query/catalogue.py` writes and reads `run_output.headers`; `layer.open_output(definition, headers,
   stored)` uses them; `runs.export_items` passes them.
6. **Catalogue v2** (`db/catalogue.py`): `MIGRATIONS` may hold callables; `SCHEMA_VERSION = 2`; migration 2 =
   `ALTER TABLE run_output ADD COLUMN headers VARCHAR DEFAULT '[]'` + Python step converting `saved_analysis`,
   `default_output`, `template_version` snapshots and `run_output` (definition + headers from `old_headers`).
7. **Interim UI adapter:** `DefinitionBuilder.definition()` turns today's measure rows into cards with
   `measures_v1_to_v2` (repeats dropped), so 6.2, 3.2 and 2.5 keep working until A1-4. Default names change on screen
   now ("Taxable Value · Sum").
8. Every other place that builds or reads measures (`manage.py`, `newtemplate.py`, `analyses.describe`, saved
   analysis open/duplicate) moves to v2. `analyses.describe` gives "Invoice No: Count, shown as Invoices".
9. **Tests:** model round trip and checks; `resolve_headers` (defaults, custom, clashes " (2)", removed columns, two
   groups on one column); compiler with Rows and with no measures; AC-MEA-5 (Average 2 decimals, half away),
   AC-MEA-6 (Sum before Max whatever tick order; card order moves groups), AC-MEA-7 (column rename changes default,
   not custom), AC-MEA-9 (new run uses the new header, older runs keep theirs; untick/re-tick restores default),
   AC-MEA-10 (on small TPL-R: Rows · Count = rows loaded, Invoice No · Count lower by the null rows; group counts add
   up), AC-MEA-11 and the upgrade: build a version-1 catalogue with `ensure_schema(con, 1)` and v1 rows, upgrade,
   check every table, `upgrade_note`, and that committed runs show their old headers. Update header strings in
   `tests/engine/test_query.py`, `test_export.py`, `tests/gui/test_analysis.py`, `test_template.py`. Expected
   figures don't change.

**Exit:** all definitions are v2 in memory and on disk; committed runs read stored headers; suite green.

## Phase A1-4 — Measures UI and header rename

**Spec:** Technical Spec A1 T42, §6.5, §8; Feature Spec A1 MEA-1…MEA-10, §3.2, §3.3; screens 6.2, 6.3, 3.2, 2.5.

0. **First, fix the known GUI test race** (`docs/PROGRESS.md` Known issues: `tests/gui/test_analysis.py` reads
   `storage.con` while a Job runs): settle the bridge before direct catalogue reads. This phase and A1-6 add many
   analysis GUI tests, so do it before adding more.
1. `ui/widgets/measures.py`: `MeasuresSection`, `MeasureCardWidget`, `OpChip`, `AddColumnPopup` (search box above 12
   columns). Chip styles in `ui/theme.py` QSS (ticked #0E6B6B on #E3F1F0). Validation message under a card (MEA-4).
2. `DefinitionBuilder` uses `MeasuresSection` (the interim adapter and `MeasureRow` go); keeps op names across edits
   (§8.1); `validate()` returns the first problem and the widget to show it under (Feature Spec A1 §5.8 order).
3. `ui/widgets/header_rename.py`: `RenamableHeader` (✎ hit area, editor, Enter/Esc/focus-out, error label, hover
   tooltips). `PagedGrid` accepts a header instance.
4. Analysis 6.2: measure headers renamable on an unsaved result; rename updates the screen's definition and redraws
   headers without greying or a Job; uniqueness against all headers. With no measures (T34): Show subtotals disabled,
   pinned total hidden.
5. Saved analysis 6.3: no ✎; locked summary lines in the new wording; the upgrade note shown until next save.
6. Template › Default outputs 3.2 and New template 2.5: `RenamableHeader` on the preview `QTableWidget`; a rename
   marks the tab changed (Save / Discard / Stay).
7. **Tests (gui):** AC-MEA-1 (Add column list: Rows first, unused columns, search above 12), AC-MEA-3 (chips by
   type, tooltips), AC-MEA-4 (Run, Save, Preview blocked with the message), AC-MEA-6 (UI order), AC-MEA-8 (Enter,
   Esc, blank restores default, "invoices" refused, no greying, time unchanged, no ✎ on 6.3), preview rename marks
   3.2 changed; screen fit (FIT) for 6.2 and 3.2 at 1366×768 and 1280×640.

**Exit:** measures by column on every builder screen; suite green; manual check of 6.2, 6.3, 3.2, 2.5.

## Phase A1-5 — Rows view engine

**Spec:** Technical Spec A1 T30, T31, T40, §7; Feature Spec A1 ROW-6, ROW-8, ROW-10…ROW-15, §5.2.

1. `model/rowspec.py`: `RowSpec`, sort keys (`_run`, `_file`, `_sheet`, `_row`), `RunRef`.
2. `query/compiler.py`: extract `filtered_base(con, filters, columns, sources, select)` from `compile_definition`
   (existing analysis tests guard the refactor).
3. `query/rows.py`: `count_rows`, `fetch_rows` (two steps; stored order per run with a shrinking `LIMIT`; sort keys
   and ties per §7.3, using the faster of NOCASE / `lower()` from A1-0), `rows_page`, `export_source` (one chunk
   per run with matches, §7.5; per-run counts from one grouped count).
4. `sankalan/rowsview.py`: Job work with no SQL: `run(ctx, folder, template, spec, run_ids, drop) -> RowsOutcome`
   (stages "Counting rows", "Finding the first 100,000", "Reading rows"; new table before dropping the old one),
   `resort(...)`, `page(...)` with display mapping (Run ID label, file name, UI-7 formats), `export_items(...)`.
5. `ui/window.py`: `drop_results` / `pending_drops` accept Rows tables as well as analysis results (T40).
6. **Tests** (`tests/engine/test_rows.py` **new**, small TPL-R): AC-ROW-10 (count = independent `count(*)`; rows
   searched); AC-ROW-11 engine (exactly 100,000 cap with a test cap argument on small data); AC-ROW-12a/12b (parts
   sum to the count; Run ID never goes back; Source Row ascending within file and sheet; two exports after
   different sorts byte-identical); AC-ROW-13 engine (descending: first row is the true max over all matches; blanks
   last both ways; "abc"/"ABC" together; ties in stored order; cancel during re-sort keeps the old table);
   AC-ROW-14 (63 left-out rows nowhere); AC-ROW-15 (Place of Supply blank for R-0001 in page and export); AC-ROW-8
   engine (export ends with the four source columns; Source Sheet blank for CSV); paging by `_pos`; temp tables
   dropped (no `_rows_%` table left after drop). `slow`: the same counts on full TPL-R (7,499,937).

**Exit:** the Rows view works headless end to end, export included; suite green.

## Phase A1-6 — Rows view UI

**Spec:** Technical Spec A1 T43, §9; Feature Spec A1 ROW-1…ROW-13, §2.2–§2.4; screens 6.2, 6.4, dialog 7.9.

1. `PagedGrid`: optional frozen first column (overlaid view sharing the model and selection, synced scroll and
   widths), header-click hook (`set_sort_handler`), sort indicator set by the screen.
2. `DefinitionBuilder.set_sections(...)` to hide groups, measures and subtotals.
3. `ui/screens/rows_view.py`: `ColumnsSection` (ticks, ↑ ↓, "N of M ticked", Show them on screen), `RowsResult`
   (header line, Export rows, grid, footer wordings incl. stored order, all states of Feature Spec A1 §2.4).
4. `ui/screens/analysis.py`: Summary | Rows switch (hidden on saved analyses), `QStackedWidget` result area, Save
   hidden and "Row views aren't saved" in Rows mode, stale handling (settings grey; column changes don't),
   `leave_guard()` None in Rows mode, `closing()` cancels a Rows Job and drops the table, template change and
   switching to Summary drop it.
5. Export rows (7.9): `ExportRequest(kind="rows")`, title "Export N rows", filters/columns/row-order box, file name
   `{Client}_{Template}_Rows_{DD-MM-YYYY}.csv`, estimate and parts line from A1-2.
6. **Tests (gui, small TPL-R):** AC-ROW-1, 2, 3 (leave clears with no prompt; leaving during a Job cancels it), 4, 7,
   8 (grid hides source columns until ticked), 9a, 9b (column changes redraw without a Job: assert no Job started),
   11 (footer texts), 13 (header click ascending then descending, arrow, Cancel keeps order), S1, S2; Export rows
   dialog contents; FIT for 6.4 and 7.9 at 1366×768 and 1280×640; frozen column stays put on horizontal scroll.

**Exit:** the Rows view is usable in the app; suite green; manual pass on full-size TPL-R (Run, sort, export, open a
part in Excel).

## Phase A1-7 — Docs, test sheet, performance suite, acceptance

**Spec:** Feature Spec A1 §9; Technical Spec A1 §14, §12.

1. With the user's approval, update the working copies: `feature-spec-v2.0.md` (A1 §9.1), `technical-spec-v1.0.md`
   (A1 §9.2 and Tech A1 §14.2), `feature-spec-a1.md` (Tech A1 §14.1 corrections). Tell the user which live docs
   need the same edits.
2. `docs/specs/test-cases.md`: one case per Feature Spec A1 acceptance criterion (38), corrected for T31, T32, T34,
   plus the T34 case; TPL-R generation rules; update old default headers in existing cases. Remind the user to
   update the live sheet.
3. `docs/specs/ui-screens/README.md`: note screens not drawn (Rows view states, rename box, Add column list,
   disk-space message, split banner).
4. `tests/perf/test_a1_perf.py` (marker `perf`): PERF-7…PERF-14 on full TPL-R, and a 12-run copy for PERF-8/9/13
   (runs duplicated by folder copy and catalogue rows to save load time). Report times; misses don't fail (T4).
5. Run the `slow` tests and the whole suite; record results, Convert time vs baseline (R12) and PERF figures in
   `PROGRESS.md`.

**Exit:** docs in step, slow suite green, performance figures recorded for the release run on the test laptop.

---

## Decisions for PROGRESS.md

Add when A1-0 starts (all **Confirmed 20-11-2026**): T31 stored-order default and tie-break; T32 grand total last;
T33 upgrade kept; T34 group-only summaries; P1, P3–P7 confirmed. Record new ones as phases make them (for example
the NOCASE vs `lower()` choice in A1-0).

## Behaviour changes users will notice

- Default measure headers read "Taxable Value · Sum", "Rows · Count" (was "Sum of Taxable Value", "Count of rows").
  Committed runs keep their old headers.
- A template column rename no longer changes committed runs' output headers (T35).
- Run-data exports from multi-file runs come out in file and row order (T29; S7a showed they may not today).
- Export all outputs: Cancel now removes every file of that export, finished outputs included (EXP-14).
- A destination file open in Excel stops the export before writing, with a plain message (T37).

## Risks carried into the plan

R8 working space on C: (A1-2 message names the drive); R9 splitter boundaries (A1-1 planted tests); R10/R11 PERF-9
and PERF-13 likely misses on the release laptop (A1-0 picks the faster sort key, A1-7 measures); R12 Convert slower
after T29 (A1-0 baseline, A1-1 re-measure); R14 files already exported out of order (no action, note in release
notes).

## Verification

- Every phase: `python -m pytest tests -q` green with `QT_QPA_PLATFORM=offscreen`; engine phases assert Feature Spec
  A1 §7 figures on small TPL-R.
- Export and Convert phases (A1-1, A1-2, A1-5): also `python -m pytest tests -q -m slow`.
- Manual after A1-2, A1-4 and A1-6: the screens in the app at 1366×768, and one split export opened in Excel 365.
- Release: `-m perf` on the 16 GB, 4-core laptop (T4).
