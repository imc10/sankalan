# Sankalan V2 — Progress

The hand-over file between build sessions. Read it at the start of every session; update it at the end.

## Phase status

| Session | Phase | Status | Branch / commit | Notes |
| --- | --- | --- | --- | --- |
| 1 | 0 — Branch, toolchain, spikes, fixtures | Done | `v2` (Phase 0 commit) | Spike findings S1–S6 change Phases 1, 2, 4: see `tools/spikes/RESULTS.md` |
| 2 | 1 — Storage, catalogue, Job runner | Done | `v2` (Phase 1 commit) | Job interface fixed (`sankalan/jobs`), so Phase 6 can start |
| 3 | 2 — Ingestion: probe, read, convert | Done | `v2` (Phase 2 commit) | Conversion failures go to `conversion_failures.parquet` until Phase 3 folds them into `issues.parquet` |
| 4 | 3 — Validation and issues | Done | `v2` (Phase 3 commit) | Phase 4 (query layer and export) split into its own session |
| 4b | 4 — Query layer, compiler and export | Done | `v2` (Phase 4 commit) | Split of left-out rows written as `query/split.py` for Phase 5 to wrap in a Job |
| 5 | 5 — Run pipeline end-to-end (headless) | Done | `v2` (Phase 5 commit) | TPL-A R-0001…R-0007 (+ discarded runs), TPL-C and TPL-D pass headless (`run/pipeline.py`) |
| 6 | 6 — UI shell and design system | Done | `v2` (Phase 6 commit) | Window, rail, theme, shared widgets, App settings; Clients/Analysis are placeholders until Phases 7/10 |
| 7 | 7 — Clients, Client, Template screens | Not started | | |
| 8 | 8 — New template wizard | Not started | | |
| 9 | 9 — New run wizard and Run detail | Not started | | Largest UI phase; split wizard / Run detail if needed |
| 10 | 10 — Analysis and export dialogs | Not started | | |
| 11 | 11 — Packaging, signing, install/uninstall | Not started | | Signing needs the RSA OV certificate (R1) |
| 12 | 12 — Hardening and release acceptance | Not started | | Partly manual on the 16 GB test laptop |

Status values: Not started · In progress · Done · Blocked (say why).

## Decisions

Behaviours the specs leave open (the test sheet says "record"). **Proposed** defaults need the user's confirmation
before the phase that relies on them; mark them **Confirmed** with the date when settled.

| Item | Default | State | Needed by |
| --- | --- | --- | --- |
| C1-04 client-name uniqueness | Unique ignoring case ("acme traders" refused when "Acme Traders" exists) | Proposed | Phase 7 |
| RUNF-06 message wording | "<file> is open in another program. Close it, then Re-check." (Tech spec) | Confirmed 17-11-2026 | Phase 2 |
| RUNV-02 Rows read with blank rows | Rows read includes blank rows (4,010 for F03); blank rows counted under rows left out (RUN-12) | Confirmed 17-11-2026 | Phase 3 |
| SH-02 second long Job | Controls that start a long Job are disabled with tooltip "Another operation is running"; the running Job shows on the rail (click opens the screen that started it) | Confirmed 17-11-2026 | Phase 6 |
| FIT-04 minimum window size | 1366×768 including the frame, **capped to the screen's work area** (1920×1080 at 150% is 1280×720 logical; a 1366×768 laptop minus the taskbar is smaller too). Layouts must fit down to 1280×640 (`theme.MIN_LAYOUT`) | Confirmed 17-11-2026 | Phase 6 |
| Title bar (canvas draws a custom 32 px bar) | Native Windows frame titled "Sankalan" with the सं icon; Qt colour scheme forced Light so it stays light in dark mode | Confirmed 17-11-2026 | Phase 6 |
| Fonts | IBM Plex Sans Regular + Medium and Plex Sans Devanagari Medium TTFs from IBM's official release (`@ibm/plex-sans@1.1.0`, `v6.4.0`), OFL licence alongside, in `sankalan/ui/fonts/` | Confirmed 17-11-2026 | Phase 6 |
| C2-08 duplicate-contents check scope | Within the same template only | Confirmed 17-11-2026 | Phase 2 |
| RUNC-10 totals mismatch test | `SANKALAN_FAULT_TOTALS=<column id>:<amount>[,…]` adds the amount to Loaded; read only when running from source (`sys.frozen` false), so the packaged exe ignores it. Automated tests pass the fault as an argument | Confirmed 17-11-2026 | Phase 5 |
| Commit free-space check (Tech spec, Commit) | Commit needs at least 100 MB free on the data folder's drive (`COMMIT_FREE_BYTES`); revisit after PERF-08 | Confirmed 17-11-2026 | Phase 5 |
| C4-06 Customers per state on R-0005 | **5** per state, not the sheet's 10: under F00, Customer cycles mod 10 and State mod 4, so each state sees 5 customers. Update the live test sheet | Confirmed 17-11-2026 | Phase 5 |
| Run-from-source route (V1 `packaging/source_install`) | Keep as a dev-only fallback until the certificate arrives, then retire (T3) | Proposed | Phase 11 |
| O12 unencrypted local data | Customer still to confirm (SEC-3); no code impact | Open (customer) | — |
| F20 Sales_Macro.xlsm without a VBA part | Generated as a true macro-enabled workbook (macro content type) with no `vbaProject.bin`; replace with an Excel-saved file if a real module is ever needed | Confirmed 16-11-2026 | — |
| DuckDB offline hardening (spike S1) | `enable_external_access=false` + `allowed_directories` (data folder, `%TEMP%\Sankalan`), empty `extension_directory`, missing local `custom_extension_repository`, then `lock_configuration` | Confirmed 16-11-2026 | Phase 1 |
| Staging lifetime (T9, SEC-4) | `_staging\<id>\` lives for the whole new-run wizard: removed on commit (renamed), discard or leave, a cancelled or failed load Job, and at start-up. `%TEMP%\Sankalan` is emptied after every Job | Confirmed 16-11-2026 | Phase 1 |
| Data-folder move destination (UX-11) | Must be new or empty. Also refused: network paths, the current folder or one inside or containing it, too little free space. OneDrive gives a warning only | Confirmed 16-11-2026 | Phase 1 |
| Export path under S1 (spike S2) | DuckDB writes `<id>.csv.part` in `%TEMP%\Sankalan`; Python streams it into `<dest>.part` next to the chosen file (BOM + header first), then renames. Cancel or failure deletes both parts | Confirmed 17-11-2026 | Phase 4 |
| EXP-04 Reason text | "Column: Rule" per Error rule that caused it, in rule order, joined by `; ` (e.g. "Invoice No: Character pattern; Taxable Value: Is a number"). `left_out.parquet` `_reason` holds the rule IDs comma-separated | Confirmed 17-11-2026 | Phase 4 |
| Issue message wording (UI-6) | As listed in the Phase 3 session log; duplicates name the first occurrence; CSV messages omit the sheet | Confirmed 17-11-2026 | Phase 3 |
| Number text beyond the Tech spec list (spike S5) | Tech spec forms (`₹`, spaces, `,` grouping, `(x)`, leading minus) **plus `Rs.`/`Rs`/`INR`** (any case, before the number). Refused as "not a number": `1e3`, `12%`, trailing minus `500-`, leading plus `+500` | Confirmed 17-11-2026 | Phase 2 |

## Known issues carried in

- The UI mockups don't yet show: the Decimals field (2.3, 3.3), the Input = Loaded + Left out totals table (4.5),
  and "Export left-out rows" (3.1, 5.1). Build them from the Tech Spec.
- Certificate (R1) not yet bought: develop with Smart App Control off; the SAC check waits for a signed build.

## Session log

Newest first. One entry per session: date, phase, what was done, deviations from the plan, what's next.

### 17-11-2026 — Phase 6: UI shell and design system
- **Decisions confirmed by the user:** SH-02 (as proposed), FIT-04 minimum size capped to the work area, native
  title bar forced light, downloading the IBM Plex fonts (see Decisions). No other Proposed decision used.
- **`ui/theme.py`:** canvas colour and size tokens, bundled fonts (`ui/fonts/`, OFL), `font()` with tabular figures
  (`tnum`), the "सं" monogram drawn with QPainter (window icon), Fusion + light palette + one style sheet keyed on
  the `kind` property (buttons primary / secondary / plain / destructive; labels h1 / h2 / subtitle / body / small /
  error / warning), `apply()` forces `Qt.ColorScheme.Light`.
- **`ui/jobs.py` `JobBridge`:** the window's side of the Job interface. Polls every 250 ms on the UI thread and
  delivers `on_done` / `on_failed` / `on_cancelled` there. Long Jobs vs **quiet Jobs** (grid pages, counts): a quiet
  Job disables nothing; a long Job cancels a running quiet Job first (waits ≤ 2 s). `guard(widget)` /
  `set_allowed()` implement SH-02. `origin` callback per Job for the rail indicator.
- **Widgets:** `Rail` (Clients, Analysis, running-Job item, gear), `Breadcrumb` (`Crumb(label, open)`), `Banner`
  (success / warning / error / info, actions such as Open folder → `explorer /select,`; success without actions
  hides after 8 s), `StepBar` (done / current / pending / **skipped**: dashed dot with "–"; ✓ drawn as an icon,
  Plex has no ✓ glyph), `ProgressPanel` (stage, bar or busy indicator, "1,000 of 4,000 rows", "0:42 elapsed",
  Cancel hidden for non-cancellable Jobs), `PagedGrid` + `PagedModel` (`PageSource.count/page` run as quiet Jobs,
  200-row pages fetched on demand, header-click sort per `GridColumn.sortable`, values via `formats`, 40 px rows and
  header), `icons.py` (canvas SVG paths rendered with QtSvg).
- **Dialogs:** `base.Dialog` / `Choice` / `ask()` (500 px, 24 px padding; tests answer through `answer_hook`),
  `DeleteConfirm` (list + "I understand this can't be undone"; red button off until ticked), `AppSettingsDialog`
  (data folder read-only + Change…, version only; refusal message inline, OneDrive warning "Use a synced folder?",
  move Job with its ProgressPanel; Close/Esc held during the move). `Storage.move_work(dest)` added so the window
  starts the move through the bridge.
- **Screens and window:** `screens/base.Screen` (breadcrumbs, banner slot, h1 + subtitle, actions, content;
  `crumbs()`, `leave_guard()`, `shown()`, `closing()`), `LeaveGuard.unsaved` / `.discard_run` (7.6 copy) /
  `.unsaved_analysis` (7.7 copy), `PlaceholderScreen` for Clients and Analysis. `MainWindow`: one screen at a time
  in a stack (old one deleted), leave guards asked before switching, `factories` per area for Phases 7/10 to
  replace, minimum size (FIT-04 rule), closing: cancellable Job → "Cancel <operation> and close?" (No keeps
  working; Yes cancels and closes when stopped), non-cancellable → "Finishing commit… Sankalan closes when it's
  done", then closes. Quiet Jobs are cancelled on close.
- **`app.py`:** `SankalanApp`: single instance (`ui/single_instance.py`: `QSharedMemory` holding the window handle,
  not QLocalServer, which is QtNetwork and banned by SEC-1; second copy restores and fronts the first via user32),
  window shown with "Opening your data…" while `Storage.open()` runs on a **background thread** (no DuckDB on the UI
  thread), failure → "Sankalan can't open its data folder…" and exit 1. `python -m sankalan` opens the window;
  `--version` prints the version (used by the layout test). PyInstaller spec now ships `ui/fonts`.
- **Tests:** 304 passing (30 new in `tests/gui/test_shell.py`; GUI fixtures `app`, `answers`, `runner`, `gate` in
  `tests/conftest.py`), full suite run 3 times. GEN-01 rail, GEN-02 (palette, painted button colours, and on the real
  Windows platform Dark → Light after `apply`), GEN-03 fonts/monogram/tnum, GEN-04 under a German Qt and Python
  locale, GEN-05 40 px rows/header and font sizes, GEN-06 breadcrumbs at four levels, leave guards, FIT-04 size
  rule at 100/125/150% and laptop work areas, shell fits 1280×640 with no window scroll area, SH-02, SH-03, SH-04,
  rail Job item, ProgressPanel, PagedGrid paging/format/sort, DeleteConfirm, StepBar, banners, DEP-05 single
  instance, DEP-06/07/08/09 App settings (real move), start-up off the UI thread and its failure path. The
  compiled-add-ons guard now opens the real `MainWindow` (QtSvg is part of PySide6).
- **Interpretations** (change if wrong):
  - Closing after "Yes" (or after a commit) does not also ask the screen's leave guard; the user already chose to
    close. Without a Job, closing asks the leave guard like any navigation.
  - The window opens maximised. Rail click opens the area's top screen (C1 / A0), not the last screen visited.
  - The move's progress counts bytes ("… of … bytes"); Phase 10 may reword it.
  - The quiet Job name is "Fetch rows" ("Load rows" trips the extension-LOAD guard regex).
- **Not verified:** real 125% / 150% scaling and a 1366×768 laptop (FIT-01…03 are manual; the offscreen screen is
  800×800); DEP-05 window activation across two real processes (tested in one process: handle published and read);
  Windows dark mode by eye (GEN-02 checked through the colour-scheme API); Open folder launching Explorer.
- **Next:** Phase 7 (Clients, Client, Template screens): register real screens in `MainWindow.factories`, build
  grids on `PagedGrid` with `PageSource`s over the query layer, use `DeleteConfirm`, `LeaveGuard.unsaved`,
  `bridge.guard()` for every control that starts a long Job. C1-04 (client-name case) is still Proposed: ask first.

### 17-11-2026 — Phase 5: run pipeline end to end (headless)
- **Decisions confirmed by the user:** RUNC-10 fault hook (env var, source runs only), commit free space 100 MB, C4-06
  expected figure 5 Customers per state (test sheet slip; see Decisions). No other Proposed decision used.
- **`model/template.py`:** `Template` (id, client, name, `SourceSettings`, columns, rules, `DefaultOutput`s, export
  defaults, version), `snapshot()` for `template_version`, `next_column_id`, `outputs_using`, `check_change`
  (`TemplateError`): type or decimals changed once the template has a committed run (TPL-9, MAP-12); a removed
  column still used by a default output, naming it (C4-15); columns can't be deleted outright once data exists.
- **Catalogue:** `template_column` gained `date_format` (schema still v1, nothing shipped). `create_template`,
  `save_template` (own transaction) / `save_template_in` (caller's transaction), `load_template`,
  `duplicate_template` (everything but runs and saved analyses; output definitions re-pointed; version 1),
  `template_has_runs`, `run_details` (run row + JSON parsed + files + outputs), `run_outputs`, `run_issue_counts`.
  The older `insert_template` / `save_rules` stay for the earlier tests.
- **`mapping.py`:** `MappingPlan` over `Sheet`s (one per file-sheet): auto-match by name/alias, `map(...,
  save_alias=)` (MAP-5), `leave_null` returning the "(Null)" warnings for outputs using the column (MAP-6),
  `leave_out` / `add_column` for extra headers (MAP-7; the same header in other sheets maps to the new column,
  sheets without it get null; changing the decision undoes it), `first_undecided` (MAP-13), `skip` (TPL-6),
  `result()` (mappings, run columns, aliases to save, decisions for RUN-12), `apply_to_template`, `describe`.
- **`query/totals.py`:** Input from the raw staged text with the Number rule, per value, unreadable = 0; Loaded
  from `data.parquet`; Left out from `left_out.parquet`; exact equality (T20). **`query/split.py`:**
  `left_out_breakdown` (a row left out only by Unique rules = later duplicate, else errors).
- **`db/datafolder.commit`:** new `in_transaction(con)` callback, run inside the commit transaction before the run
  insert: the pipeline saves learned aliases and added columns there, so they commit with the run (a discarded run
  changes nothing) and the run records that template version.
- **`run/pipeline.py`:** `RunSession`, steps as Job work: `add_files` / `remove_file` / `load_anyway` /
  `files_blockers` / `files_next`; `mapping_next`; `validate` (= `recheck`); `edit_rules(save_to_template=)`
  (scan only; saving makes a new template version at once and is listed in the run's `rules_saved`);
  `leave_validate(reason)` (split; a reason is required when there are errors); `run_outputs` (per-output status
  pending/running/done/failed/cancelled, partial file removed, run again = Retry; `outputs_skipped` with none);
  `check_totals`; `commit_blockers(comment, free_bytes)`; `commit` (not cancellable; deletes
  `conversion_failures.parquet` first); `discard`. Going back to a step drops everything after it.
  `run_changes` JSON = `{mapping, rules_run_only, rules_saved, override_reason}`; `left_out_by_reason` =
  `{blank, errors, duplicates}`; rows left out include blank rows (RUN-12), rows read = loaded + left out.
- **Tests:** 274 passing (26 new in `tests/engine/test_run_pipeline.py`), full suite run 3 times. The whole TPL-A
  sequence in one module fixture: run table (loaded and stored after each run, R-0006 delete → 14,937, R-0007 →
  16,937, staging empty), RUNF-11/12, RUNV-01/02/03/08/09/10/13, RUNO-01/03/04/05, RUNC-01…08, RUNM-01…07,
  C2-06/07, C4-06/10/11/15, C6-02/03/04/07/09/10; plus RUNC-10 (env hook) and the frozen check, RUNO-06 cancel
  and Retry, TPL-C (RUNO-07, 5 warnings, R-0001 per template), TPL-D (North + South, Archive skipped), mapping
  unit cases.
- **Interpretations** (change if wrong):
  - "Types fixed after the first commit" = while the template has at least one committed run; if every run is
    deleted the types are editable again (no data holds the old type). Date format stays editable (it only affects
    new reads). Removing a column sets its `removed` flag; deleting it outright is refused once data exists.
  - Learned aliases and added columns are saved at commit, not when picked (RUNM-03 checks after commit).
  - A duplicate-contents file (RUN-7) blocks Next on Files until Remove or Load anyway; Load anyway sets it Ready
    and stores `duplicate_decision = "load_anyway"` in `run_file`.
  - Override reason ≤ 500 characters (it prefills the comment); "Continue despite errors" with a blank-only reason
    is refused.
  - Editing rules after the split re-reads the files (the split rewrote `data.parquet`).
- **Not verified:** speed on P01/P02 (outputs, totals and split at 10M rows); RUNV-11 Re-check with a really fixed
  source file (it is `validate` again, which re-reads the files, but probe results are not refreshed); RUNO-06 with
  a long-running output (tested with a cancel that lands at once).
- **Next:** Phase 6 (UI shell) or later UI phases. Phase 9 drives `RunSession` from the New run wizard; Phase 7
  uses `load_template` / `save_template` / `duplicate_template` and `TemplateError` messages.

### 17-11-2026 — Phase 4: query layer, compiler and export
- **Decisions confirmed by the user:** S2 export path and the EXP-04 Reason wording (see Decisions). No other
  Proposed decision used.
- **`model/definition.py`:** `Definition` (`template_id`, `filters`, `groups`, `measures`, `subtotals`; JSON via
  `to_dict`/`from_dict`), `Filter`/`Group`/`Measure`, operators per column type, `check()` (`DefinitionError`).
  Default outputs (`output=True`) allow only latest month/quarter/year plus Blank/Not blank on dates (C3-19);
  analyses refuse the relative ones. Count with no column = Count of rows (the mockups' "Count of rows").
- **`query/compiler.py`:** definition → one SELECT over `read_parquet([...], union_by_name = true)`; a column no
  ticked run has becomes a typed null. `GROUP BY ROLLUP` always; `_depth` = levels grouped by (detail = n,
  subtotal 1..n-1, grand total 0). Date grain via `date_trunc` cast to DATE. Average is exact: sum in 10^-d integer
  units, rounded half away from zero, cast back to DECIMAL(38,d) (DuckDB `avg` of a DECIMAL is a DOUBLE).
  Relative filters use the latest date in the run; none → empty result + note "No dates in this run" (T21).
- **`query/layer.py`:** `run_definition` (temp table `_result_<uuid>`), `rows` (pages, capped at 100,000; export
  passes `cap=None`), `count_rows`, `grand_total` (pinned, read on its own), `order_by` (default group order,
  "(Null)" last, subtotal after its rows; with subtotals on, a sort runs within each parent group by the
  ancestor's value, T23), `write_output`/`open_output` (`outputs\<n>.parquet`, read with the definition used),
  `distinct_values` (top 1,000 by count; search = contains, ignoring case, over the whole column), `select_only`
  (`con.extract_statements`: exactly one SELECT, else `NotASelect`).
- **`query/split.py`:** `split(con, folder, issues, rule_order)` writes `left_out.parquet` (+ `_reason`) and
  rewrites `data.parquet` only when rows are left out (T18). Phase 5 wraps it in the Validate → Next Job.
- **`query/export.py`** (SQL) + **`exporting.py`** (Job work) + **`model/export.py`** (options, names): run data
  (+ Source File/Sheet/Row, Run ID), left-out rows (+ Reason), issue list (UI-6 message built in SQL), output /
  analysis result ("(Null)", "Total" on subtotal rows, "Grand total" last). Header written by Python with the
  same quoting as DuckDB; numbers as `CAST(decimal AS VARCHAR)` (column decimals, no grouping); dates
  DD-MM-YYYY. `export` refuses an existing file unless `overwrite=True` (`ExportExists`); `export_many` checks
  every destination first (C6-06). `safe_file_name`, `fill_pattern` (an empty placeholder drops out with its
  `_`), `csv_file_name`. **`analysis.py`:** Job work for analysis, preview, distinct values, `write_outputs`.
  **`formats.py`:** UI-7 number/date text and period labels.
- **Tests:** 248 passing (34 new), full suite run 3 times. A1-03…A1-10 on R-0001/R-0002/R-0003/R-0006 (every
  figure, incl. Avg 1,507.38, A1-05 sort within state, A1-07 2,005), C3-18 on F01, RUNO-01/C4-05, RUNO-03,
  RUNO-04, RUNO-05 (stored and preview), DO-3 checks, columns across runs (Branch added in R-0005: (Null) for
  R-0004; renamed; removed → "Branch (removed)"; in no run → null), select_only, row cap. Exports: EXP-02, EXP-03
  (BOM bytes, `;` tab `|`), EXP-04 (63 rows, reasons), EXP-05 (98 rows; F12 CSV message without sheet, row
  10,001 grouped), EXP-06, EXP-07, cancel mid-stream and during the COPY (no file, no `.part`, temp empty),
  analysis export with subtotals and full rows, C6-06 Export all outputs (2 files by pattern).
- **Interpretations** (change if wrong):
  - Period labels: month `Oct-2026` (as the mockups), quarter `Q4-2026`, year `2026`, day `DD-MM-YYYY`; same in
    CSV. Default measure headers "Sum of Taxable Value", "Count of rows", "Count distinct of Customer".
  - Export result rows: subtotal row's first rolled-up group cell "Total", grand total "Grand total" in the first
    group column; the export follows the screen's sort and Show subtotals setting.
  - Number filters round the typed value to the column's decimals (half away); Is one of is exact (case
    matters), Contains ignores case. Min/Max allowed on Number and Date columns only.
  - `{Output}` for non-output exports: "Data", "Left-out rows", "Issues" (`model/export.py`), the analysis name for
    an analysis; `{RunID}` empty for analyses.
  - The data export relies on `data.parquet` already being in file/row order (no ORDER BY, so 10M-row exports
    don't sort).
- **Not verified:** speed and spilling on P01/P02 (PERF-5, R3, EXP-08 at 10M rows); `Open folder` (UI, Phase 10);
  Windows-locale independence of `strftime('%b')` beyond this PC.
- **Next:** Phase 5 (run pipeline end-to-end). Wrap `split` and `write_outputs` in the run Jobs (per-output status,
  Retry), store `run_output` rows, delete `conversion_failures.parquet` before commit.

### 17-11-2026 — Phase 3: validation and issues
- **No Proposed decision used.** RUNV-02 (confirmed) is honoured: Rows read = data rows + blank rows (F03: 4,010).
- **`model/rule.py`:** `Rule` (stable ID, owner column, type VAL-1…9, settings JSON, severity Error/Warning).
  User rules are `r1`, `r2`, …; the automatic Is a number / Is a date rule is `<column-id>.type`.
  `with_type_rules` adds one per Number/Date column as an Error, keeps a Warning setting, drops it when the column
  goes (VR-7). `rule_changes(template, run)` lists added/changed/removed rules for RUN-12.
- **`validation/rules.py`:** which column types each rule fits, `check_rule` (`RuleError` with a plain message),
  `pattern_regex` (A = letter of either case, 9 = digit, punctuation escaped), problem wording, `describe` (one
  line for the rule list and run summary). **`validation/issues.py`:** UI-6 `message()` and `Issue` for grid/export.
- **`query/validate.py`:** one SQL scan → `issues.parquet` (`_src_file, _src_sheet, _src_row, column_id, rule_id,
  rule_type, severity, value, problem, duplicate_first`), ordered by file, row, rule. Per-row rules are flags on one
  pass, unnested only for failing rows; Is a number / Is a date come from `conversion_failures.parquet`; each
  Unique rule is one GROUP BY … HAVING count > 1 joined back. Also `totals`, `rule_counts`, `issue_counts`
  (per rule, file and sheet, for `run_issue_count`), `left_out_rows` (T18), `grid_count` / `grid_page`
  (first 10,000 per rule, filter by rule/severity/column, sort), `read_issues`, `dry_run` (counts + first N).
- **`validation/scan.py`** (Job work): `validate` (writes `issues.parquet.part`, renames; rerun for run-only edits
  rewrites only the issue list), `dry_run` (wizard, nothing written), `test_rules_on_run` (counts only).
- **Catalogue:** `rule` table gained an `id` column (schema still v1: no catalogue has shipped). `load_rules`,
  `save_rules` (new template version with a snapshot that carries the rules), `template_version`,
  `template_snapshot`.
- **Tests:** 214 passing (25 new), full suite run 3 times. F04: RUNV-03 66 · 32 and every per-rule count, ISS-1
  counts, RUNV-04 order/filter/sort and the GEN-07 message, RUNV-05 rows 702–707, RUNV-07 98 issues with values,
  RUNV-13 63 rows left out, RUNV-09 66 → 60 with the template rule unchanged, RUNV-10 saved as a new version,
  C3-16 counts + first 20 / all 15 from row 214, C4-12 on a hand-built R-0003 (1,937 rows: State 25, Customer 7,
  errors 0, nothing written). RUNV-01 (F02), RUNV-02 (F03), RUNV-08 (F08, null State skipped), RUNV-06 (F12:
  15,000 warnings, grid 10,000, row 10,001 message). Rule edge cases on hand-written rows.
- **Interpretations** (change if wrong):
  - Problem wording (confirmed by the user 17-11-2026; after "file, sheet, row N, Column: "): "value is blank", "value is not a number", "value is
    not a date", "value is negative", "value is not between 10 and 20" / "less than" / "more than", "date is not
    between 01-04-2026 and 31-03-2027" / "before" / "after", "value is not one of the allowed values", "value has
    14 characters; expected exactly 15", "value doesn't match the pattern AAA-99999". Unique: the first row "same
    Invoice No in 2 rows; this is the first"; later rows "same Invoice No as row 704" (or "as <file>, <sheet>, row
    N" when the first is in another file or sheet). CSV messages leave the sheet out.
  - Errors / Warnings on the Validate step count failures (issues), not rows; the override dialog uses
    `left_out` (rows).
  - Number range and Allowed values compare at the column's decimals, or at the setting's if it has more, so a
    setting is never rounded (min 10.005 on a 2-decimal column fails 10.00). Settings allow at most 6 decimals.
  - Allowed values (Text) uses DuckDB `lower()` on both sides; Text length counts characters (code points).
  - A value that failed conversion is not blank for Not blank and is skipped by Unique (its key is unknown).
  - Issue `value`: text as typed; a stored number as plain decimal text (`-1234.00`); a stored date DD-MM-YYYY.
  - A rule column missing from an older `data.parquet` (added later) reads as blank (Test rules on latest run).
  - The wizard dry run uses the staged sample on the app connection (no separate in-memory database), so the
    one-connection rule holds; Phase 8 decides how the 100,000-row sample is staged.
- **Left for later phases:** `conversion_failures.parquet` stays in staging for reruns; Phase 5 should delete it
  before commit (issues.parquet then holds the original text). Issue-list CSV export (SQL message) is Phase 4.
  `run_issue_count` rows come from `ScanResult.counts` at commit (Phase 5). Re-check (VR-6 after a fixed source)
  is load + validate again, wired in Phase 5.
- **Not verified:** scan speed on 10M rows (PERF) and cancel mid-scan on large data (RUNV-12, needs P01).
- **Next:** Phase 4 (query layer, compiler and export).

### 17-11-2026 — Phase 2: ingestion (probe, read, convert)
- **Decisions confirmed by the user:** RUNF-06 Tech-spec wording, C2-08 duplicate check per template only, S5
  Number forms = Tech spec + `Rs.`/`INR` (see Decisions).
- **`model/template.py`:** `Column` (id, name, type, decimals 0–6 default 2, `date_format` None = Excel dates or
  `DD-MM-YYYY` / `DD/MM/YYYY`, aliases, totals tick, removed) and `SourceSettings` (sheets by name / first visible /
  all visible, CSV encoding and delimiter overrides).
- **`ingest/`:** `detect.py` (V1 header detection, now returning None = "header not found"; `make_headers`;
  UTF-8 check over the whole file, else Windows-1252; delimiter sniffing), `source.py` (read-only open; on
  Windows a deny-write share mode, so a file held open for writing gives the RUNF-06 message; type from content;
  encrypted OLE = password-protected; SHA-256), `excel.py` (workbook parts and first rows read with the standard
  library, so the probe never loads a whole sheet; one streaming regex scan of the sheet XML for hidden rows and
  error cells; full read with calamine, column offset from `sheet.start`), `csvread.py`, `canonical.py` (raw
  staged text), `probe.py` (`screen_paths` + `probe_file` → `FileSheet` rows: ready / warning / error / skipped /
  refused, with `problem` code, notes, `headers_match`, `duplicate_of`), `workers.py` (spawn processes,
  `min(tasks, cores − 1)`, rows progress, stop then kill after 2 s, `TaskFailed`, crashed-worker detection;
  `workers=0` runs inline), `values.py` (Python oracle for the Number/Date/Text rules), `stage.py` (`probe` and
  `load` as Job work). `mapping.py`: `known_names`, `auto_map` (name then alias), `headers_match` (TPL-6).
- **`query/convert.py`:** the SQL rules (the authoritative ones), one SELECT per file-sheet + `UNION ALL` →
  `data.parquet` (`run_id` = staging ID, `_src_file`, `_src_sheet`, `_src_row`, then column IDs typed
  `DECIMAL(38,d)` / `DATE` / `VARCHAR`), and `conversion_failures.parquet` (file, sheet, row, column ID, value as
  typed). Fast paths (plain number → CAST, ISO date → CAST) before the full regex rule made convert ~8× faster.
  `query/catalogue.runs_with_sha256` for RUN-7.
- **Tests:** 189 passing (113 new). Oracle vectors for CONV-01/02/03 and S5 forms; SQL = oracle on ~360 number
  vectors × 5 decimal settings and ~30 date vectors × 3 formats; probe RUNF-01…13 (RUNF-06 with a handle held the
  way Excel holds it; RUNF-11 against a committed run, and not across templates); load F02, F03 (25 hidden, 10
  blank), F04 (failures: Taxable rows 214–228 "abc", 4 × "31-02-2026"; Input sums 2,986,623.75 / 381,662.10),
  F08, F16 (in 2 workers), F17 (CONV-01…03 every case), F18 (Café/Müller/Señor), F19 (CONV-05, raw text checked);
  cancel (workers gone, staging deleted), failed load, re-check, inline = workers. Ran the full suite 3 times.
- **Interpretations and deviations** (change if wrong):
  - Conversion failures are kept in `conversion_failures.parquet`; Phase 3's scan should turn them into Is a
    number / Is a date issues with the column's severity and fold them into `issues.parquet`.
  - The Validate counts are reported separately (data rows, blank rows, hidden rows), so the Proposed RUNV-02
    "Rows read" choice is still open for Phase 3.
  - A date-time cell is staged as `YYYY-MM-DD HH:MM:SS` (text exactly as Excel holds it); the Date rule drops the
    time. ISO text dates are read in every Date column; an "Excel dates" column reads only ISO.
  - CSV `_src_row` is the record number (header record = 1), which is the row Excel shows.
  - Only columns up to the last filled header cell are read; data in unnamed columns to its right is ignored.
  - Sheets by name: names are matched ignoring case; a named hidden sheet is an error ("…is hidden, so it isn't
    read").
  - The probe counts hidden rows (regex scan) so RUNF-04's "hidden rows" info shows on the Files step; blank rows
    are only known after Validate, so "Rows ≈" includes them (F03 ≈ 4,010).
  - Content decides the type: a ZIP named `.csv` is read as a workbook; text named `.xlsx` is an error.
- **Speed (dev PC, early signal):** a 300,000-row .xlsx probes in 1.2 s and loads in 4.5 s with one worker
  (read 3.1 s, convert ~0.8 s). Not measured on the laptop, nor with P01/P02.
- **Not verified:** RUNF-06 against a real Excel window (tested with a simulated Excel-style handle); F06 and
  F20 still not opened in Excel; performance on the 4-core laptop.
- **Next:** Phase 3 (validation and issues). RUNV-02 confirmed 17-11-2026: Rows read = data rows + blank rows (F03: 4,010). Phase 6 can still run in
  parallel.

### 16-11-2026 — Phase 1: storage, catalogue and Job runner
- **Decisions confirmed by the user:** S1 hardening, staging lifetime, move destination must be empty (see Decisions).
- **`paths.py`:** `AppPaths` (`%LOCALAPPDATA%\Sankalan`, `%TEMP%\Sankalan`, read from the environment so tests
  redirect them), `settings.json` (atomic write; a bad file falls back to the default data folder), `empty_folder`,
  `is_network_path` (UNC, `\\?\UNC\`, drive letters whose `GetDriveTypeW` is remote), `is_onedrive_path` (under the
  `OneDrive*` environment folders, or a path part `OneDrive` / `OneDrive - <org>`).
- **`log.py`:** rotated log (1 MB × 5) in `logs\`; `failed()` records operation + error class only (SEC-5).
- **`db/connection.py`:** S1 hardening; memory 50% of RAM in **MiB** (DuckDB reads `MB` as 10^6 bytes, which gave
  47%); threads = logical cores; temp folder; progress bar on with `progress_bar_time = 0`; then locked.
- **`db/catalogue.py`:** schema v1 (all 13 tables), upgrades by `schema_version` (one transaction per step; a newer
  catalogue is refused), backup before the connection opens (copies a leftover `.wal` too), last 5 kept.
- **`query/catalogue.py`:** all catalogue SQL outside the DDL (V3-1): clients and templates (minimal, for tests and
  later phases), `insert_run` (issues the Run ID inside the commit transaction from `run_id_counter`), list runs,
  deletes, rows stored, per-table counts, a `Transaction` context manager. `model/run.py`: `NewRun`, `RunFile`,
  `IssueCount`, `RunOutput`, `RunRow`, `run_label` (R-0001).
- **`db/datafolder.py`:** layout; staging (its ID becomes the run's internal ID and folder name); **commit protocol**
  (check `data.parquet`, delete `raw\`, fsync, rename, one transaction; if the transaction fails without a crash
  the folder is renamed back to staging); **delete protocol** (catalogue first, then folders; the Run ID counter is
  never lowered); **recovery** (empty staging, delete run and template folders with no catalogue record, mark
  missing runs damaged and clear the mark if the folder comes back); destination checks; copy with progress and
  cancel; copy check.
- **`db/storage.py`:** `Storage.open()` start-up order (settings → folders → temp emptied → log → backup → connect →
  schema → recovery → JobRunner), `close()`, `check_move()` and the **move Job** (checkpoint, close, copy, check
  file list + sizes + catalogue row counts on a new connection, switch `settings.json`, delete the old folder; a
  cancel or failure before the switch removes the copy and reopens the old folder).
- **`jobs/`:** `Job` (state, stage, rows done/total, fraction, elapsed, `cancel()`, error class), `JobContext`
  (`set_stage`, `set_rows`, `add_rows`, `check_cancelled`, `on_cancel`, `on_abort`, `set_cancellable`, `cursor`),
  `JobRunner` (one Job at a time, else `JobBusy`; `on_job_end` empties temp; logs the outcome by class only).
  `POLL_INTERVAL_MS = 250` for the window's poll.
- **Tests:** 76 passing (61 new): paths and folder checks; hardened connection (tests never execute `INSTALL`);
  schema, upgrades, backups; commit, list, query, delete; Run IDs (RUNC-07 and RUNC-08 logic, per template);
  recovery; **crash during commit** (a subprocess killed with `os._exit` before the commit and after each of its 3
  steps); Jobs (states, progress, cancel including DuckDB interrupt, one at a time, temp emptied, SEC-5 log
  checks); move (DEP-07, DEP-08, non-empty refusal, cancel). New guards: SQL calls only in `query/` and `db/`;
  only `db/` calls `duckdb.connect`. Fake runs come from `tests/conftest.py::stage_fake_run`.
- **Findings and deviations:**
  - DuckDB's query progress is a per-connection setting that the locked config refuses on new cursors, so a Job's
    `ctx.cursor()` returns the **app connection itself** (safe: one Job at a time and nothing else uses it). An
    `interrupt()` with no query running is lost, so `cancel()` keeps interrupting every 50 ms until the Job ends
    (under the Job lock, so it can never hit the next Job's query).
  - Job states are the spec's four plus `cancelled`, the outcome of an honoured cancel.
  - The spec's `column` table is `template_column` (COLUMN is an SQL keyword). No foreign keys and no UNIQUE on
    names (DuckDB can't cascade; C1-04 is still Proposed and will be checked in code in Phase 7).
  - The move check compares file lists, sizes and catalogue row counts, not file hashes (hashing would double the
    time on large datasets).
  - The crash tests use a `commit(on_step=...)` callback, not an environment variable, so RUNC-10 (still Proposed)
    is untouched.
- **Not verified:** one full-suite run out of about 35 had a single failure that did not recur in 33 further runs;
  its name wasn't captured. It is most likely a timing-sensitive Job test; watch for it. Network shares, mapped
  drives and OneDrive folders were checked only with simulated drive types and environment variables. Nothing was
  run on the 4-core laptop.
- **Next:** Phase 2 (ingestion). Before it: answer the open S5 question (Number text forms) and confirm the RUNF-06
  wording and C2-08 scope (both Proposed). Phase 6 can start in parallel now that the Job interface is fixed.

### 16-11-2026 — Phase 0: branch, toolchain, spikes, fixtures
- **main:** removed the merge-conflict markers from `README.md` (kept the V1 text), committed, tagged `v1.0.0`
  (local, not pushed; user approved), merged `main` into `v2`.
- **Layout:** V1 package moved to `legacy/` (`legacy/core`, `legacy/ui`, `demo.py`, `selftest.py`) and V1 tests to
  `legacy/tests/` (not collected: `pytest.ini` sets `testpaths = tests`). Empty V2 packages created under `sankalan/`
  per the plan layout; `python -m sankalan` prints a placeholder and calls `freeze_support()`. Test folders
  `tests/{unit,engine,gui,security,packaging,fixtures}`; spikes in `tools/spikes/`.
- **Dependencies:** `requirements-lock.txt` = PySide6-Essentials 6.12.0, shiboken6 6.12.0, duckdb 2.0.0,
  python-calamine 0.9.1. Dev = pytest, pytest-qt, pyinstaller, XlsxWriter, msoffcrypto-tool. xlrd, xlwt, cryptography,
  olefile, openpyxl dropped. `packaging/sankalan.spec` minimally repointed (no V1 hidden imports, `legacy` excluded,
  calamine no longer excluded); full rework stays in Phase 11.
- **Spikes:** results and six findings in `tools/spikes/RESULTS.md`. Headlines: T13 rounding confirmed with a plain
  `CAST`; `interrupt()` 1 ms; workers fine under spawn and in a PyInstaller exe; **S1** a locked DuckDB config still
  lets `INSTALL` download (fix: external access off + allowed directories; the spike downloaded httpfs twice into
  `~/.duckdb` / temp before this was found; both copies deleted); **S3** calamine reads error cells as `''`, so the
  XML scan must also collect error cells; CSV read of 10M rows takes 64 s on one fast core (R4 is real).
- **Fixtures:** `tests/fixtures/generate.py` builds F01–F21 in ~5 s and `verify()` reads them back
  (calamine + XML scan + csv) and asserts every Fixtures-tab figure, including F04 Input = Loaded + Left out for
  Taxable and Tax, F03 hidden/blank counts and per-state/rate/day counts. Deterministic except F06. `--perf` builds
  P01/P02 (smoke-tested at 1,000 rows only; the full 26 GB pack was not generated). F11 is a checked-in binary
  (`tests/fixtures/static/Sales_Old.xls`, built once by `make_static_xls.py` with xlwt from a scratch install).
- **Tests:** 15 passing: fixture pack (generate, verify, determinism, tamper check), security (no network imports,
  no `INSTALL`/`LOAD` in app SQL, UI never imports duckdb, no publisher name, no `legacy` imports, only the four
  allowed compiled packages load, lock file pins exactly those), layout/entry point/build spec.
- **Interpretations where the Fixtures tab is silent** (change in `generate.py` if wrong):
  F03 hidden rows hold `INV-29001…29025`, Taxable 99,999.99, GST 18%; where a hidden and a blank row follow the same
  data row (1200, 2400, 3600) the hidden row comes first; spaces-only blank rows have three spaces in all 8 cells;
  sheet Old uses base 21000. F04 rows with Taxable "abc" keep their normal Tax Amount (this is what makes Tax Input
  381,662.10). F10 is October 2026. F12 dates are ISO text (`2026-10-01`). F16 Archive uses base 95000.
  F19 has three data rows: C01 (Amount 2.345, Doc Date 05-11-2026 14:30, Code 00123), C02 (=100*1.5), C03 (#N/A).
  P01 unspecified columns: Customer Name = customer list + ID, HSN from 5 codes, Branch from F13's 3, 50 salespeople,
  Qty 1–10, Rate = Taxable/Qty, CGST/SGST split for Maharashtra else IGST, Remarks "Checked" on every 10th row.
- **Deviations:** F20 has no VBA module (approved, see Decisions). No CI configuration exists; "CI-style" here means
  `python -m pytest tests -q` from a clean venv.
- **Not verified:** F06 and F20 were not opened in Excel; the full-size P01/P02 pack was not generated; spike timings are
  from the 16-core dev PC, not the 4-core laptop.
- **Next:** Phase 1. Apply S1 in `db/connection.py` and confirm the *Proposed* S1 decision first.

### 16-11-2026 — Planning (no code)
- Wrote `docs/IMPLEMENTATION_PLAN.md` from the Feature Spec v2.0, Technical Spec v1.0, UI screens canvas and Test Cases.
- Created the `v2` branch, `CLAUDE.md`, this file, and local spec copies in `docs/specs/`.
- Next: Session 1, Phase 0.

## Starting a session

Open a new Claude Code session in this folder on the `v2` branch and paste (change N):

```
Implement Phase N of docs/IMPLEMENTATION_PLAN.md.
Start by reading CLAUDE.md, docs/PROGRESS.md and the spec sections that phase needs.
Ask me before relying on any decision still marked Proposed.
Finish with the full test suite passing, docs/PROGRESS.md updated, and a commit on v2.
```

## Refreshing the spec copies

`docs/specs/` is a snapshot from 16-11-2026. If the live docs change (Feature Spec, Technical Spec, UI screens canvas,
Test Cases), ask Claude to re-export them into `docs/specs/` and note the date in the session log.
