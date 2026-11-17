# Sankalan V2 — Phase-wise Implementation Plan

## Context

Sankalan 1.0.0 (this repo, `main`) is a 5-step merge-and-validate wizard that writes one .xlsx/.csv per run. The customer accepted it, and on 16-11-2026 four documents defined the final version:

| Doc | What it fixes |
| --- | --- |
| **Feature Spec v2.0** (claude.ai/artifact/NGA281HjAfaYXVHNwNCqh8) | Local dataset per template (~10M rows/run, ~120M/yr), stage → validate → default outputs → commit, 9 user-set rules, analysis with CSV export, Clients → Client → Template → Run UI. IDs ENV, UI, UX, TPL, IN, MAP, RUN, DO, VAL, VR, ISS, ANA, EXP, SEC, NF, PERF, V3 |
| **Technical Spec v1.0** (…/1goYPZmA7FNhrLA9Zu7Szc) | Decisions T1–T27: DuckDB 2.0 LTS + Parquet per run + DuckDB catalogue, python-calamine, worker processes, Job runner, signed PyInstaller + NSIS installer, 21 feature-spec amendments |
| **UI screens canvas** (…/U522ApcDroz6pGW3VKMvaD) | 30 artboards at 1366×768: 1.1–1.2, 2.1–2.6, 3.1–3.4, 4.1–4.5 (+4.1a), 5.1, 6.1–6.3, dialogs 7.1–7.8. Teal #0E6B6B, IBM Plex Sans, 64 px rail, 40 px rows |
| **Test Cases** (…/GzEbdCbadKjdHdG9oTXEuF) | 191 manual cases (DEP, GEN, C1–C6, RUNF/M/V/O/C, CONV, A0/A1, EXP, SH, FIT, PERF), fixture pack F00–F21, P01–P02, TPL-A run sequence R-0001…R-0007 with exact expected figures |

T1 says **new codebase**: carry over only header detection, CSV encoding/delimiter detection, mapping normalisation + aliases, number/date reading rules, the hidden-row scan, packaging scripts and security tests. The V1 pipeline, validation (GSTIN/PAN), writers and screens are dropped.

**Agreed:** tag current `main` as `v1.0.0`, build V2 on a `v2` branch in this repo replacing the `sankalan/` package, merge to `main` at release.

**How this plan is executed:** one Claude Code session per phase, in order (see the table in `docs/PROGRESS.md`). Each session reads `CLAUDE.md`, `docs/PROGRESS.md` and the local spec copies in `docs/specs/`, and ends with tests passing, `PROGRESS.md` updated and a commit.

---

## Guiding approach

- **Engine first, headless, test-driven** (Phases 1–5), then UI on top (Phases 6–10), then packaging and release (11–12). The UI shell (Phase 6) can start in parallel with Phase 3 once the Job interface from Phase 1 is fixed.
- **The test sheet is the acceptance oracle.** Phase 0 builds a fixture generator that reproduces F00–F21 exactly, so the TPL-A expected figures (e.g. R-0003 Input 2,986,623.75 = Loaded 2,946,994.00 + Left out 39,629.75) become automated assertions, not just manual checks.
- **All SQL lives in one query module** (V3-1). Screens never write SQL; DuckDB is touched only inside Jobs.
- **Compiled packages allowed:** PySide6/shiboken6, duckdb, python-calamine only. The existing `test_only_allowed_compiled_addons_load` is updated to this list on day one so drift is caught immediately.
- Development runs on a PC with Smart App Control **off** until the RSA OV certificate (R1) arrives.

## Target package layout (new)

```
sankalan/
  __main__.py          entry; multiprocessing.freeze_support(); --worker / --self-test modes
  app.py               QApplication, single-instance (QLocalServer), close handling
  paths.py             %LOCALAPPDATA%\Sankalan, settings.json, data folder, %TEMP%\Sankalan
  log.py               rotated log; operation + file name + error class only (SEC-5)
  jobs/                Job (running/cancelling/done/failed, stage, rows done/total, elapsed, cancel()), JobRunner (one at a time, T6)
  db/                  connection.py (memory 50%, threads, temp dir, extensions off + lock, T7/SEC-1)
                       catalogue.py (schema, schema_version, migrations, backups ×5 T10)
                       datafolder.py (layout, _staging, commit/delete protocols, start-up recovery, move folder)
  model/               client, template (+ template_version snapshots), column (stable IDs c001…, type, decimals, aliases, totals tick, removed), rule, default_output, run
  ingest/              detect.py (V1 header + CSV encoding/delimiter detection), probe.py, excel.py (calamine + hidden-row XML scan), csvread.py,
                       canonical.py (staged-text form), workers.py (spawn pool, stop after 2 s), convert.py (SQL Number/Date/Text rules)
  mapping.py           V1 norm/auto_map + decisions (map, alias, this-run-only, leave null, leave out, add column)
  validation/          rules.py (VAL-1..9 → SQL predicates), scan.py (one pass + unique grouping), issues.py
  query/               compiler.py (definition JSON → SQL, ROLLUP), layer.py (run_definition, distinct_values, export, select_only), export.py (COPY, BOM splice, .part)
  run/                 pipeline.py (probe → read → convert → validate → split → outputs → totals → commit)
  ui/                  theme.py + fonts/ (IBM Plex Sans, Plex Sans Devanagari, OFL), widgets/ (PagedGrid, StepBar, Banner, ProgressPanel, DeleteConfirm, Rail, Breadcrumb),
                       screens/ (clients, client, template_runs, template_outputs, template_columns, template_settings, new_template/1–6, new_run/1–5, run, analyses, analysis), dialogs/
  selftest.py
tests/  unit/ · engine/ · gui/ · security/ · packaging/ · perf/ (release only) · fixtures/generate.py
```

---

## Phase 0 — Branch, toolchain, spikes, fixtures

**Goal:** a clean `v2` branch with the new dependency set, the risky assumptions measured, and the fixture pack generated.

1. Tag `main` as `v1.0.0`; create `v2`. Fix the unresolved merge markers in `README.md` (lines 1, 108, 110) on `main` first.
2. Move V1 code to `legacy/` on `v2` (reference only, excluded from packaging) and create the empty layout above.
3. `requirements-lock.txt`: PySide6-Essentials, shiboken6, duckdb 2.0.x, python-calamine (pinned). Dev: pytest, pytest-qt, pyinstaller, XlsxWriter, msoffcrypto-tool (only to *create* F06). Drop xlrd, xlwt, cryptography, olefile, cffi.
4. **Spikes** (short scripts in `tools/spikes/`, results recorded in the doc):
   - DuckDB: `CAST(... AS DECIMAL(38,d))` rounds half away from zero (T13) — if not, use explicit `round()` semantics; `interrupt()` latency; `COPY … TO` speed; `read_parquet([...], union_by_name=true)`; config lock + extensions disabled offline.
   - python-calamine: visible/hidden sheet list, formula cached values, error cells as text, date-times (CONV-05); confirm it does **not** expose hidden rows (R5) so the XML scan is required.
   - Worker processes under `spawn` and later under a PyInstaller exe (`freeze_support`).
   - Rough timing of 1M-row .xlsx read per core (early signal for PERF-2/R2) and one 10M-row CSV on one core (R4).
5. `tests/fixtures/generate.py`: deterministic F00–F21 (formulae from the Fixtures tab: invoice bases, months, hidden rows, blank/space rows, planted errors, encrypted F06 with password `Sankalan@123`, .xls F11 via legacy writer or a checked-in binary, .xlsm F20) and P01/P02 behind a `--perf` flag. Assert the generated totals equal the Fixtures tab (e.g. F02 Taxable 7,536,875.00).

**Reuse:** `tests/conftest.py` patterns, `sankalan/demo.py` generators as a starting point.
**Exit:** fixtures generate and self-verify; spike notes written; CI-style `pytest` runs (empty suite + updated security tests).

## Phase 1 — Storage, catalogue and Job runner

**Spec:** T5–T10, T22, T25, RUN-1, RUN-5, RUN-9, SEC-4, UX-11, ENV-5.

- `paths.py` + `settings.json`; default data folder `%LOCALAPPDATA%\Sankalan\Data`.
- `db/connection.py`: single app connection, `memory_limit` 50% RAM, `threads` = logical cores, `temp_directory=%TEMP%\Sankalan`, no extensions, `lock_configuration`; temp emptied at start and at every Job end.
- `db/catalogue.py`: tables client, template, template_version, column, rule, default_output, run, run_file, run_issue_count, run_output, run_id_counter, saved_analysis, schema_version. Definitions stored as JSON text. Backup on start, keep last 5 (T10); upgrade by `schema_version`.
- `db/datafolder.py`: folders by internal ID (`t\<template-id>\runs\<run-id>\`); `_staging\<job-id>\`; **commit protocol** (flush, delete raw\, rename, one transaction issuing Run ID + inserts); **delete protocol** (catalogue first, then folders); **start-up recovery** (empty staging, delete orphan run folders, mark missing as damaged); data-folder **move Job** (copy, verify, switch settings, delete old; refuse UNC/mapped network drives; warn for OneDrive).
- `jobs/`: Job states + progress + cancel; JobRunner enforces one long Job app-wide (T6), progress poll every 250 ms.
- Run IDs per template from `run_id_counter`, never reused (T22).

**Tests (automated):** crash during commit at each step (kill a subprocess) → only committed runs remain (Tech spec "Crash during commit"); recovery cases; backups rotate to 5; move folder; network path refusal; Run ID never reused after delete/discard (RUNC-07, RUNC-08 logic).
**Exit:** a fake run (hand-written Parquet) can be staged, committed, listed, deleted and recovered.

## Phase 2 — Ingestion: probe, read, convert

**Spec:** IN-1…IN-15, MAP-9, MAP-10, T11–T14, RUN-7.

- **Probe** (workers): file type sniffed from content (ZIP → xlsx/xlsm, encrypted OLE → "password-protected" error, text → CSV; `.xls`/`.txt`/folders refused); lock `~$` files and same path twice skipped; sharing violation → "…is open in another program. Close it, then Re-check" (choose one wording for RUNF-06); sheet list with visibility; sheet selection by name(s) / first visible / all visible; V1 `detect_header` on first rows (no manual override, not-found → error); CSV encoding/delimiter on first 64 KB with template override; approximate row count; SHA-256 vs `run_file` for duplicate-contents warning.
- **Read** (workers, parallel, `min(file-sheets, cores−1)`): calamine values + hidden-row XML scan (port from V1 `core/xlsx.py` `XlsxBook.read` hidden handling); CSV via `csv` module, cp1252 → UTF-8; drop and count all-blank rows (blank = empty or only spaces, T14); write canonical UTF-8 CSV per file-sheet with `_src_row` first (numbers shortest exact decimal, never exponent; Excel dates `YYYY-MM-DD`; text as typed). Cancel: signal, kill after 2 s, delete partial files.
- **Convert** (DuckDB): one SELECT per file-sheet aligned to column IDs via mapping (missing → NULL), `UNION ALL`, write `data.parquet`. Number: strip ₹/Rs./spaces/grouping, `(x)` → −x, `DECIMAL(38,d)` half away from zero; Date: ISO or template text format (DD-MM-YYYY / DD/MM/YYYY), time dropped; Text exactly as typed, spaces-only → NULL. Failed conversions → NULL + original text to the issue list.
- **Behaviour change vs V1:** V1 `convert.to_text` strips spaces; V2 must keep them (CONV-03 `" A1 "`). V1 `convert.to_number`/`to_date` become the **Python oracle** used in tests and in wizard type guessing, while the SQL versions are authoritative.

**Reuse:** `legacy/core/readers.py` (`detect_header`, `_make_headers`, CSV detection in `_init_csv`), `legacy/core/xlsx.py` (hidden rows, date-format detection), `legacy/core/convert.py` (rules + test vectors), `legacy/core/mapping.py` (`norm`, `auto_map`).
**Tests:** CONV-01…05 expected values as asserts (C01–C13 for 2 and 0 decimals, both date formats, 1252, formula/#N/A/date-time); RUNF-02…13 probe outcomes; RUNV-02 hidden/blank counts on F03.
**Exit:** F02, F03, F04, F16, F17, F18, F19 stage to correct `data.parquet` + issues for conversion failures.

## Phase 3 — Validation and issues

**Spec:** VAL-1…9, VR-1…8, ISS-1…4, T16, T17.

- `validation/rules.py`: each rule → SQL predicate per the Tech spec rule table (blank handling, inclusive ranges after rounding, Allowed values case-insensitive for text / numeric equality for numbers, Text length on value as typed, Character pattern A/9 → regex, Unique: one grouping pass, blank key skipped, every row in a group flagged, message names first occurrence).
- Automatic Is a number / Is a date on Number/Date columns (Error, can be Warning, not removable).
- One scan writes `issues.parquet` (file, sheet, row, column ID, rule ID, severity, value as typed); counts by rule and by file-sheet.
- Run-only rule edits rerun only the scan; "Save to template" creates a new template version (TPL-7/8).
- Rule testing: wizard path (100,000 sample rows into in-memory DuckDB, first 20 failures kept) and "Test rules on latest run" (counts only, nothing stored).
- Message format (UI-6): `"Sales_Errors.xlsx, Sales, row 214, Taxable Value: value is not a number"`.

**Tests:** RUNV-03 (66 errors · 32 warnings and each per-rule count on F04), RUNV-05 (rows 702–707), RUNV-08 (null State skipped), RUNV-09 (66 → 60), C3-16 dry-run counts, C4-12 counts on R-0003, GEN-07 message.

## Phase 4 — Query layer, compiler and export

**Spec:** V3-1/2/4, DO definitions, ANA-4…9, EXP-1…7, T21, T23.

- `query/compiler.py`: definition JSON `{template_id, filters, groups, measures, subtotals}` → SQL. Date filters (year/quarter/month is, between, blank/not blank, relative latest month/quarter/year for DO with "No dates in this run"); text (is one of, contains ILIKE, blank incl. spaces-only); number (equals, between at column decimals); groups with date grain via `date_trunc`, NULL → "(Null)"; measures Sum, Count (non-blank), Count distinct, Average (display at column decimals), Min, Max; `ROLLUP` with level marker and pinned grand total; sort within parent group when subtotals on; removed columns labelled "(removed)".
- `query/layer.py`: `run_definition(spec, runs)` → temp table (spillable) + paged fetch (first 100,000 rows); `distinct_values(column, runs, search)` top 1,000 by count + full search; `select_only(sql)` accepting exactly one SELECT (parser check).
- `query/export.py`: `COPY … TO <name>.part` with delimiter, `DATEFORMAT '%d-%m-%Y'`, numbers at column decimals without grouping, display-name headers; BOM by streaming into final file after EF BB BF, else rename; Cancel deletes `.part`; Windows-illegal characters → `_`; overwrite needs confirmation (UI). Export kinds: run data (+ Source File/Sheet/Row, Run ID), left-out rows (+ Reason), issue list, outputs, analysis result.

**Tests:** A1-03…A1-10 figures on R-0001/R-0003 data; DO1/DO2 previews (C3-18, RUNO-01, RUNO-03); EXP-02…EXP-07 byte-level checks (BOM, delimiters, DD-MM-YYYY, `.part` removed on cancel); columns across runs (add/rename/remove, nulls in older runs).

## Phase 5 — Run pipeline end-to-end (headless)

**Spec:** RUN-2…14, DO-1…8, T18–T21, MAP-5…7, MAP-11…13, TPL-6, TPL-9.

- Mapping decisions API: auto-match, alias learn vs this-run-only, Leave as null (warn if a default output uses the column), extra column Leave out / Add as new column (type fixed on commit), Next → first undecided; skip Mapping when all headers match.
- Split Job after Validate: rows with Error issues and later duplicates → `left_out.parquet` with `_reason`; no rewrite when nothing is left out; override count for the dialog.
- Default outputs Job: per-output status, Cancel/Retry, stored `outputs\<n>.parquet` + definition used.
- Totals reconciliation for ticked columns: Input (from raw staged text, per-value rounding, unreadable = 0) = Loaded (`data.parquet` read back) + Left out; mismatch blocks commit; a test-only fault hook for RUNC-10.
- Commit enablement (totals pass, outputs done, comment for override ≤ 500 chars, free disk space) and Commit Job; RUN-12 summary fields (rows left out split into blank rows / errors / later duplicates, mapping decisions, run-only rule changes).
- Template model: versions on every save, type + decimals locked after first commit, column removal blocked while a default output uses it, duplicate template copies everything except runs.

**Tests:** script the full TPL-A sequence R-0001…R-0007 (including discarded runs) and assert every figure in the test sheet's run table, RUNC-01…03, C6-02…04, DO-6 immutability (C4-06/C6-10), RUN-7 duplicate warning.
**Exit:** the engine passes the whole TPL-A, TPL-C, TPL-D scenario without any UI.

## Phase 6 — UI shell and design system

**Spec:** UI-1…8, UX §2–5, NF-3, NF-4, ENV-4; canvas shared chrome.

- `theme.py` tokens from the canvas (teal #0E6B6B, tint #E3F1F0/#0A4F4F, text #1C2128/#5B636E, borders #E6E8EB, error #B42318, warning #B54708, success #067647), bundled IBM Plex Sans + Devanagari "सं" monogram, tabular figures, light only even under Windows dark mode, 40 px rows, 13/14 px text.
- Main window: min size 1366×768, never scrolls; 64 px rail (Clients, Analysis, gear); breadcrumbs; one level per screen; leave-guards (unsaved edits Save/Discard/Stay; run wizard "Leave and discard this run?").
- Widgets: `PagedGrid` (QAbstractTableModel fetching pages from Jobs, sortable headers), `StepBar` (with "skipped" state), `Banner` (success/error, Open folder), `ProgressPanel` bound to the Job interface (stage, rows done/total, elapsed, Cancel), `DeleteConfirm` (lists exactly what is deleted + "I understand" tick).
- Formatting helpers: international grouping and DD-MM-YYYY regardless of Windows region (GEN-04).
- App settings dialog (data folder + Change…, version), single instance, close-during-Job prompts, commit wait.

**Tests (pytest-qt offscreen):** GEN-01…06 checks that are automatable, FIT at 1366×768/100% and 1920×1080 at 125%/150% (no window scrollbars, layout fits), SH-03/SH-04 logic.

## Phase 7 — Clients, Client and Template screens

**Screens:** 1.1 Main, 1.2 Client, 3.1 Template Runs, 3.2 Default outputs, 3.3 Columns and rules, 3.4 Settings, dialogs 7.2, 7.3 (+ undrawn: empty states, delete template, delete saved analysis).
**Spec:** UX-1/2/4–7, TPL-2/4/7/9, MAP-3/8/11/12, DO-1/6/8, VR-8, EXP-4.

- C1: grid (templates, runs, rows stored, last loaded), search, sort, New client/rename/delete, storage footer (rows, data-folder GB, free space, amber when low), empty state.
- C2: templates grid, New run per row (with confirmation), rename (unique within client), duplicate, delete.
- C4: header summary, Runs grid (newest first, hover file names/comment, search comments + file names, row menu Open / Export data / Export issue list / Export left-out rows / Delete); Default outputs list + builder + preview on latest run with the "future runs only" note; Columns & rules (types/decimals locked after first commit, aliases, rules, Test rules on latest run, add/rename/reorder/remove with output guard); Settings (sheets, CSV, export defaults).

**Test cases:** C1-01…11, C2-01…08, C4-01…18.

## Phase 8 — New template wizard

**Screens:** 2.1–2.6. **Spec:** TPL-3, F1, IN-3…6, MAP-10, VR-7/8, DO-3/8, T13.

- Sample file (.xlsx/.xlsm/.csv; .xls refused), up to 100,000 preview rows, nothing written to `t\`.
- Sheets step (options, hidden sheets listed, CSV encoding/delimiter shown and changeable).
- Columns step: Include, source header, name, type with % note, Decimals 0–6 (Number only), date format only for text dates, reorder.
- Rules step: per-type rule menu, auto type rules, Error/Warning, dry-run counts + Show (first 20).
- Default outputs step: builder (shared with Phase 7/10), relative date filters only, preview on sample.
- Review → Save / Save and start first run; Back keeps entries; Cancel → "Discard this template?".

**Test cases:** C3-01…22.

## Phase 9 — New run wizard and Run detail

**Screens:** 4.1, 4.1a, 4.2, 4.3, 4.4, 4.5, 5.1, dialogs 7.1, 7.6. **Spec:** F2, IN, MAP, RUN, DO, ISS, UX-8/9.

- Files: picker + drag-and-drop (folders refused), grid (file, sheet, size, header, ≈rows, status), skipped list, error rows with Exclude / Re-check, duplicate-contents warning (Remove / Load anyway), low-disk warning, Next disabled while errors remain.
- Mapping grid (MAP-4…7, 13) with alias marks and amber undecided cells.
- Validate: progress, banner, tiles, by-rule table, issue grid (10,000 per rule note, filters, sort), Export issue list, Edit rules for this run (+ Save to template), Re-check files, Continue despite errors (7.1: count + required reason), Cancel returns to Mapping/Files with staging deleted.
- Outputs: per-output status, Show subtotals, Cancel/Retry, no export before commit, skipped when none.
- Commit: summary, totals table Input = Loaded + Left out, comment (≤500, required+prefilled after override), Commit (no cancel) → Run screen with success banner.
- Run (5.1): header + badge, Summary / Issues / Outputs / Source files tabs, Export data, Export issue list, Export left-out rows, Export one/all outputs, Delete run; comment read-only.

**Test cases:** RUNF-01…14, RUNM-01…08, RUNV-01…13, RUNO-01…07, RUNC-01…10, CONV-01…05, C6-01…10.

## Phase 10 — Analysis and export dialogs

**Screens:** 6.1, 6.2, 6.3, dialogs 7.4, 7.5, 7.7, 7.8. **Spec:** ANA-1…9, EXP-1…7, UX-10.

- Saved analyses list (search name/client/template, rename unique within template, duplicate, delete with plain confirm).
- Builder: client → template → runs (Run ID + file names, Select all, "N of M runs selected"), AND filters with distinct-value picker (spinner + Cancel), group levels with grain and reorder, measures with rename, Show subtotals, Run/Cancel, result grid (100,000-row cap note, pinned total, greyed when settings change: "Settings changed: Run again").
- Saved analysis opens locked (only runs choosable, none ticked); leaving unsaved result → Save… / Leave without saving / Stay; changing template clears settings after confirm.
- Export dialog (folder + name pattern `{Client}_{Template}_{RunID}_{Output}` prefilled, delimiter, encoding, CSV only), progress dialog with Cancel, overwrite confirm, Open folder banner.

**Test cases:** A0-01…05, A1-01…15, EXP-01…08.

## Phase 11 — Packaging, signing, install/uninstall

**Spec:** T2, T3, T26, NF-2, NF-7, SEC-6, DEP-*.

- Update `packaging/sankalan.spec` for folder build with duckdb, calamine, fonts; workers are the same exe in worker mode.
- `packaging/sign_files.ps1`: sign every unsigned .exe/.dll/.pyd with the RSA cert + CA timestamp; verify with `Get-AuthenticodeSignature`.
- `packaging/installer.nsi`: per-user to `%LOCALAPPDATA%\Programs\Sankalan`, no admin, Start menu entry "Sankalan", upgrade-in-place, uninstall asks whether to delete the data folder.
- `build_windows.bat`: tests → PyInstaller → sign → self-test of built app → NSIS → sign installer.
- `selftest.py`: small pipeline on generated data, DuckDB + calamine load, signature check; first start after update backs up and migrates the catalogue.
- Retire the run-from-source route (`packaging/source_install`, `make_source_package.py`) per T3, or keep it as a dev-only fallback until the certificate arrives — decide when R1 is resolved.

**Test cases:** DEP-01…13 (manual on Windows 10 and 11), automated packaging tests updated from `tests/test_e2e_packaging.py`.

## Phase 12 — Hardening and release acceptance

- Security suite (from V1, updated): no network imports + run with network blocked, sources unchanged (hashes), no leftovers in temp/_staging after each Job and restart, planted marker values absent from the log (DuckDB error text never logged), allowed compiled packages only.
- Performance suite (release only, 16 GB/4-core laptop): PERF-01…08 with P01/P02; misses reported, not blocking (T4). Feeds the low-disk threshold (C1-10, RUNF-14).
- Smart App Control check on a signed build (needs R1).
- Full manual pass of the test sheet in its phase order P1–P7, statuses recorded in the sheet.
- Update Feature Spec v2.0 with the 21 Tech-spec changes; update README and CHANGELOG; merge `v2` → `main`, tag `v2.0.0`.

---

## Open behaviours to settle (test sheet marks these "record")

Proposed defaults, to confirm before the phase that needs them:

| Item | Proposed default | Phase |
| --- | --- | --- |
| C1-04 client name case | Unique ignoring case ("acme traders" refused) | 7 |
| RUNF-06 wording | Tech spec: "…is open in another program. Close it, then Re-check" | 2 |
| RUNV-02 Rows read with blank rows | Rows read = 4,010; blank rows shown under rows left out (matches RUN-12) | 3/9 |
| SH-02 second long Job | Start controls disabled with tooltip "Another operation is running"; Job progress visible from the rail | 6 |
| C2-08 duplicate-contents check scope | Per template only | 2 |
| RUNC-10 | Fault-injection hook behind an env var in test builds only | 5 |
| O12 | Customer still to confirm unencrypted local data (SEC-3) — no code impact | — |

## Risks carried into the plan

R1 certificate (blocks SAC testing; develop with SAC off), R2/R4 read speed (Phase 0 spikes measure early), R3 PERF-5 spilling (measure in Phase 4 on P01 data), R5 hidden rows (XML scan + F03 tests), R6 synced folders (T25 guard in Phase 1).

## Verification

- Every phase ends with `python -m pytest tests -q` green (`QT_QPA_PLATFORM=offscreen` for GUI tests); engine phases assert the exact figures from the Test Cases sheet using generated fixtures.
- From Phase 9: `python -m sankalan --self-test` runs the TPL-A smoke set (RUNF-01/02, RUNV-01, RUNO-01, RUNC-01/05).
- Manual: run the Test Cases sheet phases on a Windows 11 laptop (and Windows 10 for DEP-02) as each UI phase lands; FIT-01…04 at the three display settings; PERF suite and SAC check before release.
