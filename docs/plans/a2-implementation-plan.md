# Plan: Feature Spec A2 — Feature-Updates

Status: **planned** (21-11-2026). Not started. Sessions record progress in `docs/PROGRESS.md` (phases A2-1 to A2-6).

## Context

| Doc | What it fixes |
| --- | --- |
| `docs/specs/feature-spec-a2.md` | Behaviour and IDs: ROW-1…14, MEA-1…11, EXP-8…14, SHT-1…10, TXT-1…14, NCK-1…14, BUG-1, PERF-7…14, AC-*, D38–D80 |
| `docs/specs/technical-spec-a2.md` | How to build it: T32–T56 and T67, spikes S8a–S8i, module map (§4), tests (§14), doc changes (§15). **It wins over Feature Spec A2** where they differ (its §15.1) |
| `docs/specs/feature-spec-v2.0.md`, `technical-spec-v1.0.md` | Base behaviour and architecture. A2 changes them only as listed in Feature Spec A2 §12 and Tech spec A2 §15.2 |

**This plan replaces the build order in Technical Spec A2 §16.** That section has eleven phases (A2-0 to A2-10). This
plan groups them into **six phases**, each sized to be built and tested in one Claude Code session:

| This plan | Scope | Tech spec §16 phases |
| --- | --- | --- |
| **A2-1** | Groundwork and Feature E (text in Number and Date columns) | A2-0 (except perf baselines, TPL-N and the sheet files), A2-1 |
| **A2-2** | Feature F (template without checks), then Feature D (choose sheets) | A2-2, A2-3, plus TPL-N and the sheet files from A2-0 |
| **A2-3** | Feature C (export in parts): engine and dialogs | A2-4, A2-5 |
| **A2-4** | Feature B (measures by column): engine and UI | A2-6, A2-7 |
| **A2-5** | Feature A (Rows view): engine and UI | A2-8, A2-9 |
| **A2-6** | Doc updates, full-size checks, **performance suite** and report | A2-10, plus the PERF-1/PERF-2 baselines moved from A2-0 |

**Answered on 21-11-2026** (in `docs/PROGRESS.md` → Decisions): T38 grand total last; T39 no total rows without
measures; T40 version-1 folders refused; T45 blank rows line; T46 Choose sheets on all four Excel kinds; P8 / TXT-11
sort order; T67 D38 → D81.

**How this plan is executed.** One session per phase, in order, on `Feature-Updates` (never `main`). Each session
reads `CLAUDE.md`, `docs/PROGRESS.md`, its phase below, and **only** the spec sections the phase names. It ends with
the normal suite passing, `PROGRESS.md` updated and a commit. If a phase runs long, finish the coherent part the
phase names as its **cut line**, record the rest in `PROGRESS.md`, and stop.

---

## Guiding approach

- **Storage first.** Feature E changes `data.parquet` (text companions, sorted rows) and the catalogue becomes version
  2. Every later feature reads them, so they land in A2-1.
- **Engine before UI in every phase.** Engine work is headless and test-first. The figures in Feature Spec A2 §10
  (as corrected by Tech spec A2 §15.1) are the oracle. If a test fails, don't change an expected figure: either the
  code or the spec is wrong, so ask.
- **The app works at the end of every phase.** No feature is left half-wired across a phase boundary. Where a later
  phase replaces something (for example measure headers), the earlier phase keeps today's behaviour.
- **Small data in the normal suite.** The normal suite uses the small fixture sets and `part_rows = 1000`, so it stays
  near today's run time (~95 s, plus the new tests).
- **Three test tiers.**

  | Tier | Marker | When it runs |
  | --- | --- | --- |
  | Normal | none | Every phase, the full suite, before each commit |
  | Slow (full-size correctness) | `slow` | Each phase runs **its own** slow tests once before committing. A2-6 runs all of them |
  | Performance | `perf` | **Only in A2-6.** No phase before A2-6 measures or tunes speed |

- **Hard rules unchanged:** offline; all SQL in `sankalan/query/` (DDL in `sankalan/db/`); DuckDB only inside Jobs;
  one long Job at a time; temp files only in `%TEMP%\Sankalan`; no cell values in logs; no new runtime packages; UI-7
  formats; no publisher name.
- **No A2 artboards in the repo.** The A2 screens (4.1b, 4.1c, 6.4–6.6, 7.9, 2.4b, 4.3b, 4.5b) are not in
  `docs/specs/ui-screens`. Build them from Feature Spec A2's wording and the existing screens' look, and render each
  new screen offscreen at 1366×768 to look at it.

## Phase overview

| Phase | Depends on | Main files (new in **bold**) | Size guide |
| --- | --- | --- | --- |
| A2-1 | — | **`tests/fixtures/tpl_r.py`**, `db/catalogue.py`, `db/storage.py`, `paths.py`, `app.py`, **`ui/dialogs/data_folder_refused.py`**, `query/convert.py`, `query/validate.py`, `query/split.py`, **`query/textvalues.py`**, `query/compiler.py`, `query/layer.py`, `query/export.py`, `query/catalogue.py`, `formats.py`, `model/definition.py`, `model/run.py`, `run/pipeline.py`, `newtemplate.py`, `validation/scan.py`, `ui/widgets/builder.py`, `ui/widgets/result_table.py` | Largest engine phase |
| A2-2 | A2-1 | **`tests/fixtures/tpl_n.py`**, sheet fixtures, `model/template.py`, `model/run.py`, `model/export.py`, `run/pipeline.py`, `runs.py`, `manage.py`, `newtemplate.py`, `ingest/probe.py`, `ingest/stage.py`, `ingest/excel.py`/`xlsb.py`/`xls.py` (dimension only), `ui/screens/new_template_rules.py`, `template_settings.py`, `template_columns.py`, `new_run.py`, `new_run_steps.py`, `run.py`, `template.py`, **`ui/dialogs/choose_sheets.py`** | Largest UI phase; has a cut line |
| A2-3 | A2-1 | `exporting.py`, **`exporting_split.py`**, `query/export.py`, `model/export.py`, `jobs/job.py`, `runs.py`, `analyses.py`, `ui/widgets/progress.py`, `ui/dialogs/export_dialog.py` | Medium |
| A2-4 | A2-1 (A2-3 for headers in exports) | `model/definition.py`, **`query/headers.py`**, `query/compiler.py`, `query/layer.py`, `query/export.py`, `analysis.py`, `analyses.py`, `run/pipeline.py`, `manage.py`, `newtemplate.py`, `ui/widgets/builder.py`, **`ui/widgets/measures.py`**, **`ui/widgets/header_rename.py`**, `ui/widgets/paged_grid.py`, `ui/screens/analysis.py`, `template_outputs.py`, `new_template.py` | Large; has a cut line |
| A2-5 | A2-3, A2-4 | **`model/rowspec.py`**, **`query/rows.py`**, **`rowsview.py`**, `query/compiler.py` (shared `filter_sql`), `ui/widgets/paged_grid.py`, `ui/widgets/builder.py`, `ui/screens/analysis.py`, **`ui/screens/rows_view.py`**, `ui/dialogs/export_dialog.py`, `model/export.py`, `ui/window.py` | Medium |
| A2-6 | All | `docs/specs/*`, `docs/specs/test-cases.md`, **`tests/perf/test_a2_perf.py`**, **`tools/perf/build_a2_data.py`**, **`tools/perf/RESULTS-A2.md`**, **`tools/perf/excel_open_check.ps1`** | Docs and measurement, no feature code |

A2-2's Feature D part touches different files from A2-3. If you want them built at the same time, A2-2 Part B
(Feature D) can run in its own worktree branch after A2-1. Otherwise keep the order above.

---

## Test data

Built by `tests/fixtures/generate.py` (new modules alongside it). Every generator is deterministic, so expected
figures are fixed. The small sets are the normal-suite oracle. The full sets run only in `slow` and `perf` tests,
built on demand into `tests/fixtures/_generated/` and cached by a content hash of the generator.

### TPL-R (with checks), built in A2-1

Feature Spec A2 §10.1. 20 template columns: 8 Text, 8 Number (2 decimals), 4 Date. R-0002 adds **Place of Supply**
(21 columns in all, AC-ROW-7). Type rules: Is a number on Taxable Value and Is a date on Invoice Date are **Warning**,
so text rows load. One Error rule (Character pattern on Invoice No) leaves out R-0002's 63 rows on override. About 1%
of cells are blank, except Invoice No. Some text values contain commas, double quotes, `\r\n` and `\n`.

Each run has one `.xlsx` with two sheets and one or more CSV files, so stored order crosses files and sheets, and
Source Sheet is blank for CSV rows.

| Figure | Full (slow / perf) | Small (normal suite) |
| --- | --- | --- |
| Rows per run (R-0001, R-0002, R-0003) | 2,500,000 each | 2,500 each |
| R-0001 Taxable Value text: "NA" / "Nil" / "12,000/-" | 1,000 / 500 / 10 (1,510) | 10 / 5 / 1 (16) |
| R-0002 Invoice Date text: "NA" / "31-02-2026" | 300 / 5 (305) | 3 / 2 (5) |
| R-0002 rows left out (Character pattern, override) | 63 | 63 |
| R-0003 rows from the source without Invoice No (Leave as null, MAP-6) | 400,000 | 400 |
| Rows searched, all three runs (ROW-10) | 7,499,937 | 7,437 |

A module fixture commits R-0001…R-0003 through the real `RunSession` pipeline, the same way
`conftest.tpl_a_template` / `commit_tpl_a_run` do for TPL-A.

### TPL-N (without checks), built in A2-2

TPL-R's 20 columns, Check data before loading = No, 2 CSV files.

| Figure | Full | Small |
| --- | --- | --- |
| Rows per file | 500,000 | 5,000 |
| Rows repeated exactly | 2,000 | 20 |
| Taxable Value text values | 6,802 | 68 |
| Invoice Date text values | 120 | 12 |
| Blank rows (for "Blank rows skipped") | 10 | 3 |

### Sheet files, built in A2-2

`Sales_Nov-2026_Central.xlsx` (Sales Nov, Returns Nov, hidden Notes), `Sales_Nov-2026_East.xlsx` (Sales),
`Sales_Nov-2026_West.xlsx` (Sales, Sales Returns, Cover with no header row). Template rule: sheets Sales and Sales
Returns. Central is also saved as `.xlsb` and `.xls` by `tests/fixtures/make_static_formats.ps1` (Excel COM, dev
only) and checked in under `tests/fixtures/static`, like F22–F27. A renamed-sheet copy of Central (Sales Nov →
Sales November) for AC-SHT-6.

### Performance data, built in A2-6

See A2-6 step 4.

---

## Phase A2-1 — Groundwork and Feature E (text in Number and Date columns)

**Goal.** A green baseline. Catalogue version 2 with every A2 column. BUG-1 fixed. TPL-R fixtures. Convert writes text
companions in sorted order, and every engine path (validation, split, totals, query layer, exports, previews) reads
them.

**Read.** Tech spec A2 §2 (T32, T40, T41, T42, T50, T54, T55, T56), §3, §5, §11, §12, §14. Feature Spec A2 §6,
§8.2, §8.8 (filters, groups and rules rows only), §10.6, §10.8, §13.1.

### Steps

0. **Green baseline first.** Two known test problems (PROGRESS → Known issues and the 21-11-2026 log):
   - `tests/gui/test_new_run.py::test_many_issues_first_10000_then_discard` fails every time: after "Leave and
     discard this run?", `q.list_runs` returns `[]`. Find the cause. If it is a product bug, not a test bug, stop and
     report it before fixing.
   - The `tests/gui/test_analysis.py` race (a test reads `storage.con` while a Job holds the connection). Fix it on
     the test side by settling the bridge before direct catalogue reads.
1. **Test tiers.** Add marker `slow` to `pytest.ini`. A `--full` switch for `generate.py`. Session fixtures for small
   and full TPL-R.
2. **TPL-R generator** (`tests/fixtures/tpl_r.py`) and the committed-runs fixture (Test data above). Self-check: the
   generator asserts its planted counts by reading its own files back, like `verify()` does for F01–F21.
3. **Catalogue version 2** (T40, §12):
   - `SCHEMA_VERSION = 2`, `MIGRATIONS = {2: _V2}`. `_V2` is the whole schema: `run.checks BOOLEAN NOT NULL`,
     `run.text_counts VARCHAR NOT NULL`, `run_file.sheets_chosen BOOLEAN NOT NULL`, `run_output.headers VARCHAR NOT
     NULL`.
   - `ensure_schema` raises `CatalogueFromTestBuild` on version 1. The version is read **before** the start-up backup
     and before any write, so the folder is left exactly as it was.
   - Start-up today has no data-folder chooser (`app._failed` shows `OPEN_FAILED` and closes). Add
     `ui/dialogs/data_folder_refused.py`. It shows the §12.2 message with "Choose folder…", "Create new folder…" and
     "Close". Choosing or creating a folder writes `settings.json` and opens it, with the same checks as Change… in
     App settings. The opening runs on the background thread as today.
   - `query/catalogue.py` writes the new fields:
     - `checks` = True (A2-2 sets False);
     - `sheets_chosen` = False (A2-2 sets it);
     - `text_counts` from `textvalues.text_counts` in the commit Job (T56);
     - `headers` = the output headers the current code shows (A2-4 changes the producer to `resolve_headers`).
   - `layer.open_output` takes the stored headers (T50), so a later column rename no longer changes a committed run.
4. **BUG-1** (T54): `paths.empty_folder(path, keep=None)`. `Storage._job_end` keeps `duckdb_temp_<this pid>_*`.
   `open` and `close` still empty the folder completely. Update the SEC-4 "no leftovers" checks (in tests and in
   `selftest.py`) to allow only this process's spill files after a Job.
5. **Convert** (§5.1, §5.2):
   - Two-level `part_select` with `cNNN_t` companions for every Number and Date column.
   - `write_data` adds `ORDER BY _src_file, _src_row` (T32).
   - `write_failures`, `failure_counts`, `read_failures` and `conversion_failures.parquet` are removed; so is the
     delete in `commit`.
   - `convert_values` (the oracle helper) returns `(value, text)`.
   - `newtemplate.convert_sample` uses the same path; `StagedSample.failures` is removed.
6. **Validation** (§5.4): the `fl` CTE reads companions; Not blank is `c IS NULL AND c_t IS NULL` (the `_bad` list
   goes); the Unique key part is `coalesce(CAST(c AS VARCHAR), c_t)`. The same applies in `newtemplate.dry_run` and
   `scan.test_rules_on_run`.
7. **Split** (`query/split.py`): `left_out.parquet` and the rewritten `data.parquet` keep the companions (`SELECT *`)
   and the sort.
8. **Totals** (§5.5): no code change; tests only.
9. **Text counts** (`query/textvalues.py`): `text_counts(con, data, columns)`. (`text_values` comes in A2-2, where it
   is first used.)
10. **Query layer** (§5.6):
    - `companion_expr`.
    - Filter ops `not_number` and `not_date` (T55).
    - Typed Blank / Not blank; Count = `count(c) + count(c_t)`; Count distinct on Date reads `c` only.
    - Kind columns `k1…kn` with `GROUP BY ROLLUP((k1, g1), …)` (T42). Stored outputs include the kinds.
    - `layer.order_by` sorts `k{i}` first (P8).
    - Relative dates take `max(c)`.
    - Labels "(Not a number)" / "(Not a date)" / "(Null)" in `result_table`, the analysis grid and result exports.
11. **Display and export** (§5.3):
    - `formats.cell_text(col, value, text)`.
    - `query/export._text` becomes `coalesce(<formatted c>, c_t)` for run data and left-out rows.
    - Run data and left-out exports add `ORDER BY _src_file, _src_row` (T32).
12. **UI.**
    - `FILTER_OPS[NUMBER] += not_number`; `FILTER_OPS[DATE]` and `OUTPUT_DATE_OPS += not_date`.
    - `FilterRow` shows each op's help text (§5.8).
    - `analyses.describe` wording: "Taxable Value is not a number".
    - `newtemplate.detect` adds the text share to the type note (§5.9).

### Tests (new)

| File | Covers |
| --- | --- |
| `tests/unit/test_fixture_pack.py` (extend) | TPL-R small generates, verifies itself, is deterministic |
| `tests/engine/test_catalogue.py` (extend) | New folder created at version 2 with the four new columns; version-1 catalogue raises `CatalogueFromTestBuild`, with no backup written and the folder's files unchanged (hashes) |
| `tests/gui/test_shell.py` (extend) | Start-up on a version-1 folder shows the message; Create new folder opens a fresh folder; Close exits without changes |
| `tests/engine/test_bug1.py` **new** | AC-BUG-1a: a temp table forced to spill (small `memory_limit`), created in Job 1 and read in full in Job 2. It must fail on the old `_job_end` (checked once by hand with the fix reverted; note it in PROGRESS). AC-BUG-1b: after a Job only `duckdb_temp_<pid>_*` remain; after `close()` and after reopening, the folder is empty |
| `tests/engine/test_convert_sql.py` (extend) | Companions: text kept exactly as typed (`"  NA "`, `#N/A`, `12,000/-`, `31-02-2026`); `c` and `c_t` never both filled; blank or spaces-only → both null; a column with no source (MAP-6) or added later (MAP-11) → both null; `data.parquet` ascending in `(_src_file, _src_row)` for a multi-file load |
| `tests/engine/test_text_values.py` **new** | On small TPL-R: AC-TXT-2 (Sum, Avg, Min, Max = Python over numeric cells only; Date Min/Max ignore text); AC-TXT-3 (Count = numeric + 16; Invoice Date Count includes 5; Distinct = distinct dates only); AC-TXT-4 (Is not a number = 16 rows; Equals/Between never return text rows; Blank = empty cells only; Is not a date = 5); AC-TXT-5 ("(Not a number)" count 16, separate from "(Null)"; "(Not a date)" 5 at month and year grain); AC-TXT-6 (ascending and descending: values, then the text group, then "(Null)"); AC-TXT-9 (Latest month uses the latest real date and leaves text rows out); `text_counts` = independent `count(c_t)`; `run.text_counts` stored at commit |
| `tests/engine/test_validation.py` (extend) | AC-TXT-7: one issue per text cell (from the type rule only, none from Number range, Date range or Allowed values); Not blank passes on text; two "NA" in a Unique key are duplicates; Test rules on latest run now finds type failures in committed text |
| `tests/engine/test_run_pipeline.py` (extend) | AC-TXT-8: totals pass on R-0001 (text = 0 in Input, null in Loaded); left-out rows keep companions; `run_output.headers` stored and unchanged after a template column rename |
| `tests/engine/test_export.py` (extend) | AC-TXT-1 export half: "NA", "Nil", "12,000/-" and "31-02-2026" exported as typed; values with commas, quotes and line breaks quoted (S7h); run data in stored order; result export kind labels |
| `tests/unit/test_formats.py` (extend) | `cell_text` for Number (grouping, decimals, text kept, right-aligned flag) and Date (DD-MM-YYYY or text, left-aligned) |
| `tests/gui/test_analysis.py` (extend) | Is not a number / Is not a date offered with help text; result grid shows text-group labels; AC-TXT-1 display half for the Summary grid |
| `tests/gui/test_new_template.py` (extend) | AC-TXT-10: a sample with 2% text in a Number column shows "98% numbers · 2% aren't numbers and are kept as text" |
| `tests/engine/test_stored_order.py` **new**, `slow` | A full-size TPL-R load (≥ 2M rows, parallel Convert): `data.parquet` strictly ascending; run-data export rows in the same order; AC-BUG-1c (all three full-size runs commit) |

### Existing tests that change

- Tests of `conversion_failures.parquet` (8 references).
- Tests that expect a type-rule Warning row to load as null (it now loads with its text).
- The SEC-4 no-leftovers checks (spill-file exception after a Job only).
- Every expected figure stays as it is.

### Acceptance

- AC-TXT-2 to AC-TXT-10, and AC-TXT-1 for the Summary grid and exports (the Rows view half is in A2-5).
- AC-BUG-1a, AC-BUG-1b, AC-BUG-1c (slow).
- Version-1 refusal (Tech spec §15.3 extra case).
- Normal suite green, including the two fixed tests; this phase's `slow` tests pass once.
- The app runs: a TPL-A run and an analysis work as before (spot-check by hand, `python -m sankalan`).

**Cut line.** Steps 0–9 (storage, BUG-1, Convert, validation) are one coherent part. If time runs out, query layer
and UI (steps 10–12) carry over. Storage must not be committed without the validation changes.

---

## Phase A2-2 — Feature F (template without checks), then Feature D (choose sheets)

**Goal.** Templates can load without checks (Load step, counts, commit, run screens). Then users can choose sheets
per Excel file in a run.

**Read.** Tech spec A2 §2 (T43–T47), §5.7, §6, §7, §12.1. Feature Spec A2 §5, §7, §10.5, §10.7.

### Part A — Feature F

1. **Fixtures:** TPL-N small and full (`tests/fixtures/tpl_n.py`).
2. **Model** (§6.1):
   - `Template.checks: bool = True`, stored in `settings` JSON; carried by `copy()`, `snapshot()` and Duplicate.
   - `load_template` reads `settings.get("checks", True)`.
   - `RunSession.checks` is fixed when the session starts.
3. **Wizard step 4** (§6.2):
   - A Yes / No bar on `new_template_rules.py`.
   - No shows the 2.4b panel: the explanation, a text-count table from `text_counts` on the converted sample, and
     the footer.
   - Rules entered stay in memory and come back on Yes.
   - `build_template` saves `checks` and, with No, no rules.
4. **Template screens** (§6.3):
   - 3.4: Check data before loading, with its note. Saving makes a new version; No → Yes applies `with_type_rules`.
   - 3.3 with No: rules greyed; banner "Not in use: this template loads without checks"; add, edit and delete
     disabled; Test rules on latest run hidden; column edits still allowed.
5. **Run steps** (T44, §6.4): `STEPS` stays five long. The third label and the Next labels come from `sess.checks`.
   Page 2 is `ValidateStep` or `LoadStep`. With Mapping skipped, Files → Load.
6. **Load Job** (§6.5): `RunSession.load_unchecked(ctx) -> LoadSummary`.
   - It runs Read, then Convert, then `text_counts`. No scan, no `issues.parquet`, no `left_out.parquet`.
   - Cancel or Back deletes staging and returns to Mapping, or to Files.
7. **Load step** (§6.6, 4.3b):
   - Banner and four stat cards, with the blank-rows and hidden-rows lines (T45).
   - A text-count table.
   - Selecting a column starts a "Read values" Job: `textvalues.text_values` (≤ 1,000 values, count, first file,
     sheet and row).
   - Re-check files (new problem → Files; new header → Mapping; else load again). Next → Outputs.
8. **Commit** (§6.7, 4.5b):
   - The summary lines (Data checks: Not checked · template setting; Rows left out: None; Blank rows skipped; per
     column text lines; the totals note).
   - Totals check with Input = Loaded. Comment optional.
   - Run row: `checks = false`, errors and warnings 0, `rows_left_out = 0`, `left_out_by_reason` all 0, `rows_read`
     including blank rows.
9. **Elsewhere** (§6.8):
   - Runs list: Issues "Not checked".
   - Run detail: no Issues tab; summary lines; no Export issue list or left-out rows.
   - `model/export` and `runs.export_items` refuse `issues` and `left_out` for these runs.
   - Edit rules for this run is not offered (NCK-13).

### Part B — Feature D

10. **Sheet fixtures** (Test data above), including the `.xlsb` / `.xls` copies via `make_static_formats.ps1`.
11. **Probe** (§7.1, T47):
    - `SheetEntry(name, visible, rows_approx)` for every sheet. `rows_approx` comes from each reader's dimension
      record: `xlsx`/`xlsm` sheet XML, `.xlsb` BrtWsDim, `.xls` DIMENSIONS. No header scan; hidden sheets have no
      count.
    - `probe_file(..., chosen=None)` resolves sheets from the choice or the rule.
    - Sheet not found is **one** ERROR row per file (`problem = "sheet"`), with the "Sheets found: …" or "no visible
      sheet" message.
12. **Session** (§7.2):
    - `sheet_choice`, `choose_sheets(path, names)` (re-probes one path in a "Check files" Job and invalidates from
      Files).
    - `can_choose_sheets(path)`.
    - `add_files`, `recheck_files`, `remove_file` and Exclude honour the choice.
    - `stage.probe(..., choices)`.
13. **Files step** (§7.3): the "Choose sheets…" link on a file's first row; the Sheet not found banner (Choose
    sheets… and Exclude file); the footer wording; the drop-zone hint.
14. **Dialog** (`ui/dialogs/choose_sheets.py`, §7.4): built from `FileSheet.sheets`, with no Job. Rows with "about N
    rows"; hidden rows disabled ("Hidden, skipped"); the note; the total; "Read N sheets". Ticks on open as §7.4.
15. **Commit:** `run_file.sheets_chosen` is true for the rows of a chosen path (§7.5).

### Tests (new)

| File | Covers |
| --- | --- |
| `tests/unit/test_fixture_pack.py` (extend) | TPL-N small and the sheet files generate and verify |
| `tests/engine/test_unchecked.py` **new** | `Template.checks` round trip, snapshot, Duplicate (AC-NCK-9). `load_unchecked` on small TPL-N: Rows loaded = Rows read − blank rows, repeated rows kept, no `issues`/`left_out` files (AC-NCK-2). Cancel empties staging (AC-NCK-3). Text counts 68 / 12, and `text_values` order, counts and first file/sheet/row (AC-NCK-4, against an independent query). Commit fields; totals Input = Loaded. Password file, new header and duplicate-file warning still apply (AC-NCK-5). Export of issues or left-out rows refused. AC-NCK-10: an analysis over a checked and an unchecked run = the sum of each alone |
| `tests/gui/test_new_template.py` (extend) | AC-NCK-1: the bar defaults to Yes; No shows 2.4b with Number and Date counts and the footer; Yes restores earlier rules; a template saved with No has no user rules |
| `tests/gui/test_template.py` (extend) | AC-NCK-7: Settings Yes → No makes a new version; 3.3 rules greyed with the banner and not editable; Test rules hidden; No → Yes restores rules; earlier runs keep their Issues tab |
| `tests/gui/test_new_run.py` (extend) | AC-NCK-2 (step bar reads Files · Mapping · Load · Outputs · Commit); AC-NCK-3 (progress, Cancel → Mapping, or → Files when Mapping was skipped); AC-NCK-4 (Load cards, table, values list); AC-NCK-6 (Commit lines; Commit enabled with no comment); Re-check paths from Load |
| `tests/gui/test_template.py`, `tests/gui/test_new_run.py` (run screen) | AC-NCK-8: "Not checked" in the Runs list; no Issues tab; summary line; export items hidden |
| `tests/engine/test_ingest_probe.py` (extend) | Sheet lists with visibility and `rows_approx` for `.xlsx`, `.xlsm`, `.xlsb` and `.xls` (Central). One error row per file (East, Central) with the message naming visible sheets. Resolution from a choice (case-insensitive, workbook order); a chosen sheet missing or hidden → Sheet not found. Cover → `problem = "header"` |
| `tests/engine/test_run_pipeline.py` (extend) | Session: `can_choose_sheets` for each case; choice kept through Re-check; removed by ✕ or Exclude; mapping invalidated; `sheets_chosen` true for Central only (AC-SHT-8 engine part); template's Sheets to read unchanged after commit (AC-SHT-7) |
| `tests/gui/test_new_run.py` (extend) | AC-SHT-1 (link on all four Excel kinds; not on CSV, a locked file, a password file or Header not found); AC-SHT-2 (dialog rows, hidden Notes, nothing ticked, "Read 2 sheets" and the total); AC-SHT-3 (banner, footer, Next disabled; two Ready rows after choosing; Cancel leaves the error); AC-SHT-4 (East opens with Sales ticked); AC-SHT-5 (Cover → Header not found, only Exclude, link gone; ✕ and re-add starts from the rule); AC-SHT-6 (renamed copy → Sheet not found with Returns Nov ticked); AC-SHT-9 (Mapping skipped when headers match; a new header highlights only that column) |
| GUI fit | Load step, Commit for runs without checks, Settings, 2.4b, Files with the banner, and the dialog all fit 1280×640 |

### Existing tests that change

- Sheet not found expectations: one row per file instead of one per missing sheet.
- Any test that hard-codes the third step's label.

### Acceptance

- AC-NCK-1 to AC-NCK-10.
- AC-SHT-1 to AC-SHT-9, AC-SHT-1 with `.xlsb` and `.xls` (T46).
- Normal suite green; `slow` TPL-N full load once (AC-NCK-2/4 at 6,802 / 120 and 2,000 repeated rows).

**Cut line.** Part A (Feature F) is complete on its own. If the session runs long, commit Part A and record Part B as
the first work of the next session, before A2-3.

---

## Phase A2-3 — Feature C (export in parts)

**Goal.** Every export goes through one chunked, splitting, verifiable engine with a size estimate, disk check, safe
finish and rollback. The dialogs show the estimate, parts and progress detail.

**Read.** Tech spec A2 §2 (T33–T38, T53), §8. Feature Spec A2 §4, §10.4. Today's `exporting.py`, `query/export.py`,
`model/export.py`, `ui/dialogs/export_dialog.py`.

### Steps

1. **Progress detail** (T53): `ctx.set_detail()`, `Progress.detail`, and the line in `ui/widgets/progress.py`.
2. **Splitter** (`exporting_split.py`, §8.5): `Splitter(open_part, header, bom, part_rows)`, `.feed(path)` and
   `.close() -> counts`.
   - Fast path with `block.count(b"\n")`; slow path with `bytes.find`.
   - Quote state carried across blocks; it must be "outside" at the end of every chunk.
   - 8 MB blocks; progress at most every 250 ms; `check_cancelled` per block.
3. **Plan** (§8.3): `PART_ROWS = 1_000_000` (T37); `plan(rows, file_name, part_rows)` gives the names (`_partKKofMM`,
   width `max(2, len(str(M)))`, stem without a final `.csv` of any case).
4. **Sources** (§8.1): `ExportSource(headers, chunks, rows)` and `Chunk(select, rows)`.
   - `runs.export_items` and `analyses.export_items` build them inside the Job: run data, left-out rows, issue list
     (committed and Validate step), one output, all outputs (one source each) and the analysis result.
   - The analysis result's grand total stays last (T38).
   - `export_many` is folded into `export` (a list of sources).
5. **Estimate** (§8.4, T34): `exporting.estimate(...)`.
   - A 10,000-row sample `COPY` gives bytes per row × N × 1.05, with header and BOM bytes per part.
   - Needs on the temp drive and the destination drive, added together when both are the same drive.
   - Free space from `shutil.disk_usage`.
6. **Export** (§8.2): five steps.
   - Check: free space and T36 open-for-write.
   - Extract each chunk to `%TEMP%\Sankalan\<job>-<k>.csv` with no header.
   - Split into `.partial` parts, deleting each chunk before the next `COPY`.
   - Verify per-chunk and total counts ("Export check failed: wrote X of N rows"; error class only in the log).
   - Finish (T35) not cancellable: `.replaced` swap, rename, delete; restore on any error.
   - `ctx.on_abort` removes chunks and `.partial` files and restores `.replaced` files.
   - Test hooks are arguments (`part_rows`, a count-mismatch fault); the app never sets them.
7. **Dialog** (§8.6, 7.4/7.5):
   - A "Checking size" quiet Job on open; Export disabled until it returns.
   - Summary line "N rows · CSV file" or "N rows · 3 CSV files · about X".
   - Parts line under the file name; disk message above the buttons (destination wording, or temp-drive wording).
   - Free space re-read when the folder changes, with no Job (no DuckDB).
   - Overwrite confirmation lists every file (≤ 10, then "and N more") and passes `replace`.
   - Progress shows "part K of M". Split success banner "Exported N rows to M files" with Open folder. New cancel
     banner text.

### Tests (new)

| File | Covers |
| --- | --- |
| `tests/unit/test_export_split.py` **new** | Seeded random CSV records with quotes, doubled quotes, `\r`, `\n` and delimiters planted on and around part boundaries and 8 MB block boundaries (use a small block size argument too). Each part parses with `csv` to the expected record count. Joined data rows are byte-identical to the input. BOM and header on every part. An unbalanced quote at a chunk end fails |
| `tests/unit/test_export_plan.py` **new** | AC-EXP-8a / AC-EXP-10 names: 1,000,000 → one file with no suffix; 1,000,001 → 2 parts; `_part01of03`; `_part001of120`; `.CSV` stem; all-outputs plans |
| `tests/engine/test_export.py` (rework) | Every kind in §8.1 with `part_rows = 1000` on small TPL-R (AC-EXP-8b). AC-EXP-9a: each part has header + ≤ 1,000 records, BOM when chosen, same header. AC-EXP-9b: joined parts = one-file export, byte for byte. AC-EXP-12 (T38): a result with subtotals split across parts, grand total only as the last row of the last part, order = on-screen order. AC-EXP-14a: cancel during extract, during split (part 2 of 3) and just before finish → no chunk, `.partial` or `.replaced` left; replaced files keep their SHA-256. A forced failure during finish restores the originals. AC-EXP-14b: count mismatch hook and a simulated disk-full write (patched writer raising `OSError(ENOSPC)`) → plain message, same clean-up. T36: a target held open the way Excel holds it → the "open in another program" message. EXP-13: patched `disk_usage` → refusal with both sizes; temp-drive message; same-drive needs added |
| `tests/engine/test_jobs.py` (extend) | `set_detail` reaches `Progress.detail` |
| `tests/gui/test_export_dialog.py` **new** (or extend `test_analysis.py`) | Estimate on open (Export disabled until done); parts line and summary for a 3-part export (lowered `part_rows`); AC-EXP-13 (disk message with both sizes; choosing a roomy folder enables Export); AC-EXP-10 overwrite list (3 parts replaced, an older `_part04of04` untouched); AC-EXP-11 (stage, rows of N, "part K of M" shown and refreshed by the poll); AC-EXP-14c (split banner and Open folder target); cancel banner text; runs without checks offer no issue/left-out export |
| `tests/engine/test_export_big.py` **new**, `slow` | Real `PART_ROWS`: 1,000,000 rows → one file; 1,000,001 → 2 parts (AC-EXP-8a); a full-size TPL-R run export splits into 3 parts with records ≤ 1,048,576 per file |

### Existing tests that change

- `.part` → `.partial`.
- The cancel banner text.
- `export_many` callers.
- EXP-02…07 tests keep their expected bytes, apart from row order where data was not yet sorted.

### Acceptance

- AC-EXP-8a, 8b, 9a (record counts; opening in Excel is checked in A2-6), 9b, 10, 11, 12 (as T38), 13, 14a, 14b, 14c.
- Normal suite green; this phase's `slow` tests pass once.

**Cut line.** Steps 1–6 (engine, with the dialog still working through the old summary text) are coherent. Step 7
can carry over.

---

## Phase A2-4 — Feature B (measures by column)

**Goal.** Version-2 measures (cards and ops) everywhere a definition lives. Resolved headers. Rows card. Results with
no measures. Committed runs keep their headers. The new Measures section and header rename in 6.2, 3.2 and 2.5.

**Read.** Tech spec A2 §2 (T39, T49, T50, T51), §9. Feature Spec A2 §3, §8.8 (measures), §8.9, §10.3.

### Engine

1. **Model** (§9.1): `Op`, `MeasureCard`, `ROWS`, `flat_measures()` in MEA-6 order; `definition_version: 2`;
   `from_dict` reads version 2 only (`DefinitionError` otherwise).
2. **Checks** (§9.2): the order-of-checks list (screen checks 1–2 stay in the screens), and the programming-error
   refusals (a column on two cards, an op that doesn't fit the type, name length and uniqueness).
3. **Headers** (`query/headers.py`, §9.3): `resolve_headers(definition, columns)`: defaults "<Column> · <Op>", "Rows
   · Count", " (removed)", clash suffixes " (2)", hover text.
4. **Compiler** (§9.4): loops over `flat_measures()`; Rows → `count(*)`; no measures → `GROUP BY k…, g…` with no
   ROLLUP and `grand_total()` None.
5. **Where headers flow** (§9.5):
   - `layer.Result` headers from `resolve_headers`.
   - `analysis.write_outputs` returns headers; the commit stores them in `run_output.headers` (replacing A2-1's
     interim producer).
   - Result exports use them.
   - `analyses.describe` gives "Invoice No: Count, shown as Invoices".
   - `manage` / `newtemplate` default outputs build version 2.

### UI

6. **`ui/widgets/measures.py`** (§9.6): `MeasuresSection`, `MeasureCardWidget`, `OpChip` (theme QSS for ticked and
   unticked), `AddColumnPopup` (search box when there are more than 12 columns; Rows first).
7. **`DefinitionBuilder`:** uses `MeasuresSection`; `set_sections(filters=, groups=, measures=, subtotals=)` (for
   A2-5); `definition()` keeps names while the same (column, fn) stays ticked.
8. **`ui/widgets/header_rename.py`** (§9.7): `RenamableHeader` with the ✎ area, edit box, Enter / Esc / focus-out,
   `rename_requested`, `finish()` / `show_error()` and tooltips.
   - Wired into `PagedGrid` (6.2) and the `QTableWidget` previews in `template_outputs.py` (3.2) and
     `new_template.py` (2.5).
   - A rename never re-runs or greys the result. In 3.2 it marks the tab changed.
9. **Screens:** the 6.3 locked summary wording; no ✎ on saved analyses. No-measure results disable Show subtotals and
   hide the pinned total. Check messages show under their sections.

### Tests (new)

| File | Covers |
| --- | --- |
| `tests/unit/test_definition_v2.py` **new** | Round trip; version 1 refused; ops stored in MEA-6 order; type rules (no Count distinct on Number, D70; Rows count only); duplicate cards refused; name rules |
| `tests/unit/test_headers.py` **new** | AC-MEA-7 (exact defaults "Taxable Value · Sum", "Invoice No · Count distinct", "Rows · Count"; a default follows a column rename, a custom name doesn't); clashes " (2)"/" (3)" with groups and custom names first; removed columns; two group levels on one column |
| `tests/engine/test_query.py` (extend) | AC-MEA-5 (Average at 2 decimals, half away from zero); AC-MEA-6 (Max then Sum ticked → Sum, Max; card move moves the pair); AC-MEA-10 (on R-0003, Rows · Count = rows loaded and Invoice No · Count is 400 lower on small, 400,000 on full; per-group Rows · Count sums to the grand total); AC-MEA-11 (grouped by GSTIN with no measures: each value once, no subtotal or grand total rows, `grand_total()` None, export has no Grand total row); every A1-03…A1-10 figure unchanged under version-2 definitions |
| `tests/engine/test_run_pipeline.py` (extend) | AC-MEA-9: rename a default output's measure, commit a new run → its stored headers and CSV use the new name; earlier runs keep theirs |
| `tests/gui/test_measures.py` **new** | AC-MEA-1 (popup lists Rows first then unused columns; used ones are gone); AC-MEA-3 (chips per type, tooltips "Count distinct", "Average"); AC-MEA-4 (a card with nothing ticked: Run, Save and Preview show the message and start no Job); untick → re-tick restores the default name; empty-section text; 12+ columns show a search box |
| `tests/gui/test_analysis.py` (extend) | AC-MEA-8 (✎ → Enter saves; Esc cancels; blank restores the default; "invoices" refused against "Invoices" with the message, box stays open; result not greyed, time unchanged; saved analysis has no ✎); 6.3 wording; "Add a group level or a measure"; Show subtotals disabled with no measures |
| `tests/gui/test_template.py`, `tests/gui/test_new_template.py` (extend) | 3.2 and 2.5 preview rename marks the tab changed (Save / Discard / Stay); 2.5 builder uses cards |
| GUI fit | Builder with 4 cards, the popup and the rename box fit 1280×640 |

### Existing tests that change

- Every test that builds a version-1 definition (helpers in `tests/conftest.py` first, then call sites).
- Default header strings: "Sum of Taxable Value" → "Taxable Value · Sum", "Count of rows" → "Rows · Count".
- Expected figures do not change.

### Acceptance

- AC-MEA-1, 3, 4, 5, 6, 7, 8, 9, 10, 11 (as T39).
- Normal suite green.

**Cut line.** The engine (steps 1–5), with the builder adapted to build version-2 cards from its current rows, is
coherent. The new widgets (steps 6–9) can carry over, but must land before A2-5.

---

## Phase A2-5 — Feature A (Rows view)

**Goal.** A Summary | Rows switch in New analysis. A Rows mode with columns, the exact match count, the first
100,000 rows in stored order in a frozen-column, unsortable grid, and Export rows through the A2-3 engine.

**Read.** Tech spec A2 §2 (T48, T52), §10. Feature Spec A2 §2, §8.7 (as corrected by Tech spec §15.1), §10.2.

### Engine

1. **`model/rowspec.py`:** `RowSpec(template_id, filters, columns, show_source)` and `RunRef(id, number, label,
   data_path, rows_loaded, file_names)`.
2. **`query/rows.py`** (§10.2–§10.4):
   - `count_rows` (per-run counts; with no filters, rows loaded from the catalogue).
   - `fetch_rows`: `CREATE TEMP TABLE _rows_<uuid>`, then per run in Run ID order one `ORDER BY _src_file, _src_row
     LIMIT <rows still needed>` with `_seq`.
   - `rows_page` reads a `_seq` range.
   - `export_source`: one chunk per run with matches, ordered, Source File by `CASE`, Run ID literal, headers per
     ROW-8.
   - Filters through the compiler's shared `filter_sql`.
   - The row cap is a parameter (`ROWS_CAP = 100_000`), so tests can lower it.
3. **`rowsview.py`** (Job work, no SQL):
   - The Run Job: stages "Counting rows" then "Fetching the first 100,000"; `on_abort` drops the new table; the
     previous table goes to `window.drop_results` when the Job finishes.
   - `RowsSource` (a `PageSource` over `rows_page`, mapping run labels, file names and `cell_text`).
   - The export source.

### UI

4. **`PagedGrid`** (T52): an optional frozen first column (overlaid view, medium weight); sorting off (no arrows,
   header clicks ignored).
5. **`ui/screens/rows_view.py`:**
   - `ColumnsSection`: ticks, ↑ ↓, "N of M ticked", Show them on screen; `columns_changed` with no Job.
   - `RowsResult`: header line, Export rows (.csv), footer wording, and the states of Feature Spec A2 §2.4.
6. **`ui/screens/analysis.py`:**
   - The Summary | Rows switch, hidden for saved analyses.
   - Rows mode via `builder.set_sections`, so filters carry over and Summary settings come back.
   - Save hidden; header "Row views aren't saved"; `leave_guard()` returns None; `closing()` cancels the Job and
     drops the table.
   - Settings changes grey the result and disable Export; column changes re-read pages only.
   - A template change drops the table.
7. **Export rows (7.9):**
   - `ExportRequest(kind="rows")`; title "Export N rows".
   - Summary line; box with the filters (`analyses.describe`), the columns line and the order line.
   - File name `{Client}_{Template}_Rows_{DD-MM-YYYY}.csv`.
   - The estimate reuses the counts.

### Tests (new)

| File | Covers |
| --- | --- |
| `tests/engine/test_rows_view.py` **new** | AC-ROW-10: per-run and total counts = an independent `count(*)` with the same filters (including Is not a number); rows searched = 7,437 on small. Fetch with the cap lowered to 1,000 crosses from R-0001 into R-0002 and holds exactly 1,000 rows in stored order. Paging by `_seq`. Cancel keeps the old table and drops the new one. AC-ROW-11b engine half: grid rows = the export's first rows, in order. AC-ROW-12a: exported rows over all parts (`part_rows = 1000`) = match count. AC-ROW-12b: Run ID never goes back; within a run rows follow file, sheet and row load order; two exports byte-identical. AC-ROW-13: none of R-0002's 63 left-out rows in count, grid or export. AC-ROW-14: Place of Supply blank for every R-0001 row. AC-ROW-8 export half: last four headers Source File, Source Sheet, Source Row, Run ID; Source Sheet blank for CSV rows. AC-TXT-1 Rows half: text values as typed in the grid cells and the export |
| `tests/gui/test_rows_view.py` **new** | AC-ROW-1 (opens in Summary; Rows shows Columns and Run, no groups, measures or Save, header text); AC-ROW-2 (2 runs, 2 filters, 2 groups, 3 cards kept across switches; result cleared); AC-ROW-3 (leave to Clients and back → empty builder, no prompt; leaving during a Run cancels it and leaves no table); AC-ROW-4 (no switch on a saved analysis); AC-ROW-6 (Is not a number / Is not a date counts equal Summary's); AC-ROW-7 ("21 of 21 ticked"; untick all + Run → "Tick at least one column", no Job); AC-ROW-8 (source columns only after Show them on screen, after the ticked columns); AC-ROW-9a (filter, run tick or template change greys with "Settings changed: Run again" and disables Export rows); AC-ROW-9b (column tick, move and Show them on screen redraw with no Job started and no greying); AC-ROW-11a (footer wording above and below the cap, cap lowered); AC-ROW-11b (header click changes nothing, no sort indicator); AC-ROW-S1 (no match → "No rows match these filters.", no Export rows); AC-ROW-S2 (Cancel → previous result greyed with "Cancelled: Run again"); TXT-3 alignment of text cells; Export rows dialog contents and file name; fit at 1280×640 |
| `tests/engine/test_rows_view_big.py` **new**, `slow` | Full TPL-R: rows searched 7,499,937; fetch of 100,000 in stored order; AC-ROW-12b over all three runs (3 × 2.5M rows, split export, Run ID monotonic, rows ascending per run) |

### Acceptance

- AC-ROW-1, 2, 3, 4, 6, 7, 8, 9a, 9b, 10, 11a, 11b, 12a, 12b, 13, 14, S1, S2.
- AC-TXT-1 (Rows half).
- Normal suite green; this phase's `slow` tests pass once.
- Every feature is now built.

**Cut line.** The engine (steps 1–3) and the grid change (step 4) are coherent. The screen and dialog (steps 5–7)
can carry over to the start of A2-6, before its measurements.

---

## Phase A2-6 — Docs, full-size checks, performance

**Goal.** The specs and test sheet catch up with A2. Every `slow` test passes at full size. Parts open in Excel. The
performance targets are measured. **If any target is missed, the measured figures go to the user, who decides
whether to proceed.**

**Read.** Tech spec A2 §13, §14, §15. Feature Spec A2 §9, §12. `docs/specs/test-cases.md` (structure and the PERF
section).

### Steps

1. **Docs** (Tech spec §15, Feature Spec A2 §12):
   - **First show the user the list of spec edits and get approval**, as for the D81 (.xls) change.
   - Then update `docs/specs/test-cases.md`:
     - one case per AC (71) and per PERF target (8), corrected for T38, T39, T45 and T46;
     - extra cases for the temp-drive message (T34), the version-1 refusal (T40), and Choose sheets on `.xlsb` and
       `.xls`;
     - fixtures F-A2-01…11 (TPL-R, TPL-N, sheet files);
     - existing cases with old default headers and Sheet not found rows updated.
   - Fold Feature Spec A2 §12.1 (with Tech spec §15.1's corrections) into `feature-spec-v2.0.md`, and Tech spec A2
     §15.2 into `technical-spec-v1.0.md`.
   - The live claude.ai docs are **not** edited. List what they need in PROGRESS for the user.
2. **Full-size correctness.** Build TPL-R and TPL-N full. Run every `slow` test: AC-BUG-1c, stored order, the
   7,499,937 / 400,000 / 1,510 / 305 / 6,802 / 120 figures, the big exports.
3. **Excel check** (AC-EXP-9a). `tools/perf/excel_open_check.ps1` (Excel COM, dev only, like
   `make_static_formats.ps1`) opens every part of a 2,100,000-row export and checks each sheet's used rows = records
   in the file (1,000,001 for full parts). Skipped, and noted as not verified, if Excel isn't installed.
4. **Performance suite** (`tests/perf/test_a2_perf.py`, marker `perf`, data from `tools/perf/build_a2_data.py`):

   **Data.**
   - 12 committed runs of 10M rows in TPL-R's shape, written straight to `data.parquet` by DuckDB and committed
     through the real commit protocol (about 3.2 GB of Parquet). Planted text values and 2-filter selectivity as
     TPL-R.
   - A 10M-row CSV for PERF-14 and PERF-1 (about 1.2 GB).
   - PERF-2 uses the existing P02 pack (`generate.py --perf`), if it can be generated.
   - Before building, check free space. PERF-12 alone needs about 29 GB on the destination plus one run's chunk (about
     2.4 GB) on the temp drive. If space is short, **ask the user** before scaling anything down. A scaled run is
     reported as scaled, never as the target figure.

   **Machine.** The dev PC is faster than the 16 GB, 4-core release laptop, so the suite pins DuckDB to `threads = 4`
   and `memory_limit = 8 GB` (50% of 16 GB) and uses 3 reader workers. The report states the dev PC's CPU, RAM and
   disk. A laptop run stays a manual release step (T4).

   **Method.** Each target is run 3 times after one warm-up; the report gives the median, min and max.

   | ID | Measured operation | Target |
   | --- | --- | --- |
   | PERF-7 | Rows view Run on 1 run (10M), 2 filters: count + first 100,000 | ≤ 5 s |
   | PERF-8 | The same across 12 runs | ≤ 30 s |
   | PERF-9 | Next page of 200 rows from the Rows table | ≤ 100 ms |
   | PERF-10 | Tick, untick or reorder a column (grid redraw, offscreen) | ≤ 200 ms |
   | PERF-11 | Export 10M rows, 20 columns, UTF-8 with BOM, 10 parts | ≤ 60 s |
   | PERF-12 | Rows view export of 120M rows, 120 parts (Cancel checked once mid-way) | ≤ 12 min |
   | PERF-13 | Export dialog estimate (run data, and Rows view with its counts) | ≤ 2 s |
   | PERF-14 | Load step without checks: 10M-row CSV including text counts | ≤ 2 min |
   | PERF-1 (re-measure) | Load 10M rows from CSV with validation and totals | ≤ 2 min |
   | PERF-2 (re-measure) | Load 10M rows from 10 .xlsx | Benchmark (test sheet: ≤ 5 min) |
   | PERF-3…6 (regression) | Analysis on 1 and 12 runs, 1M groups, 1M-row result export | ≤ 3 s / 15 s / 60 s / 5 s |

   **Before and after Convert (R13, R14).** The Convert sort and companions are measured against the code before A2.
   A temporary `git worktree` at commit `25f4d98` (the last pre-A2 commit, never modified) runs the same PERF-1
   load, and the PERF-2 load if P02 exists, on the same data and settings. The report gives both times and the
   difference. The same is done for Probe time on the sheet files and P02 (R14). The worktree is removed afterwards.
   This replaces Tech spec §16's "record PERF-1/PERF-2 baselines in A2-0", so that no earlier phase runs performance
   tests.

5. **Report.** Write `tools/perf/RESULTS-A2.md`: machine, settings, data sizes, and per target the median, min, max,
   target and Met / **Missed**.
   - **All met:** record in PROGRESS and finish the phase.
   - **Any missed:** stop. Show the user the table and what dominates each miss (the stage timings the suite logs),
     and ask whether it is acceptable to proceed. Don't tune anything without the user's go-ahead. The phase status
     stays "Blocked: awaiting decision on PERF misses" until they answer. The decision is recorded in PROGRESS →
     Decisions.
6. **Close.** Normal suite green. PROGRESS: the A2 status, the "Not verified" list (laptop run, 125% / 150% scaling,
   real Explorer and drag and drop, live docs). Commit. Merging `Feature-Updates` into `main` only when the user
   asks.

### Acceptance

- Every AC in Feature Spec A2 §10 has a passing automated test, or is listed under Not verified with the reason.
- `slow` suite green at full size.
- PERF-7…14 measured and reported, with PERF-1…6 re-measured, and the user's decision recorded for any miss.
- Spec copies and `test-cases.md` updated (after approval).

---

## Session checklist (every phase)

1. Read `CLAUDE.md`, `docs/PROGRESS.md`, this phase, and only the spec sections it names.
2. Engine steps test-first. Expected figures come from the spec or the Test data tables above, never from the code's
   output.
3. Keep context small: grep the large UI files (`new_run.py`, `new_template.py`, `analysis.py`) for the parts you need
   rather than reading them whole. Use an Explore subagent for wide searches.
4. Normal suite green (`QT_QPA_PLATFORM=offscreen`), within its time budget (CLAUDE.md → Test time budgets: more than 10% over → stop, find the cause, fix, rerun). Run this phase's `slow` tests once. **No `perf` tests before
   A2-6.**
5. Render new or changed screens offscreen at 1366×768 and look at them; check they fit 1280×640.
6. Update `docs/PROGRESS.md`: status, what changed, interpretations, deviations, Not verified, next. Then commit on
   `Feature-Updates` with the attribution lines.

## Settled items

Confirmed by the user on 21-11-2026 (also in `docs/PROGRESS.md` → Decisions).

| # | Item | Decision | Needed by |
| --- | --- | --- | --- |
| A2-O1 | Small fixture figures (TPL-R 16 / 5 / 63 / 400 / 7,437; TPL-N 68 / 12 / 20 / 3) | **Confirmed:** as in Test data | A2-1, A2-2 |
| A2-O2 | Test-case IDs for PERF-7…14: `test-cases.md` already has PERF-07 (Responsiveness) and PERF-08 (Disk use) for v2.0, which clash with A2's PERF-7 and PERF-8 | **Confirmed:** name the A2 cases **A2-PERF-07…A2-PERF-14**, with the feature ID in the Spec column | A2-6 |
| A2-O3 | Performance machine | **Confirmed:** dev PC with DuckDB pinned to 4 threads and 8 GB; laptop run as a manual release step | A2-6 |
| A2-O4 | Pre-A2 comparison point for R13/R14 | **Confirmed:** worktree at `25f4d98` | A2-6 |

## Risks carried into the plan

| # | Risk | Where handled |
| --- | --- | --- |
| R9 | Splitter cuts a record at a part boundary | A2-3 planted-boundary unit tests and per-chunk count check |
| R10, R13 | PERF-12 is disk-bound; the Convert sort slows PERF-1/2 | Measured in A2-6 only; misses go to the user |
| R11 | Wrong date format loads a whole Date column as text | A2-2 Load/Commit counts; A2-1 wizard note |
| R14 | Probe reads every sheet's dimension | Dimension only (A2-2); timed in A2-6 against the pre-A2 build |
| R15 | Old dev data folders refused | A2-1 start-up dialog; recreate dev folders by hand |
| — | A2 artboards missing from `docs/specs/ui-screens` | Built from spec wording; offscreen render reviewed each UI phase |
| — | Phase size (A2-2, A2-4) | Each has a cut line; leftovers recorded and done first in the next session |
