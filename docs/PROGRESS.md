# Sankalan V2 — Progress

The hand-over file between build sessions. Read it at the start of every session; update it at the end.

## Phase status

| Session | Phase | Status | Branch / commit | Notes |
| --- | --- | --- | --- | --- |
| 1 | 0 — Branch, toolchain, spikes, fixtures | Done | `v2` (Phase 0 commit) | Spike findings S1–S6 change Phases 1, 2, 4: see `tools/spikes/RESULTS.md` |
| 2 | 1 — Storage, catalogue, Job runner | Done | `v2` (Phase 1 commit) | Job interface fixed (`sankalan/jobs`), so Phase 6 can start |
| 3 | 2 — Ingestion: probe, read, convert | Not started | | |
| 4 | 3 + 4 — Validation and issues; query layer and export | Not started | | Split into two sessions if it runs long |
| 5 | 5 — Run pipeline end-to-end (headless) | Not started | | Gate: TPL-A run sequence R-0001…R-0007 passes with no UI |
| 6 | 6 — UI shell and design system | Not started | | Can run in parallel with sessions 4–5 (own worktree, `sankalan/ui/` only) once Phase 1's Job interface is fixed |
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
| RUNF-06 message wording | "<file> is open in another program. Close it, then Re-check" (Tech spec) | Proposed | Phase 2 |
| RUNV-02 Rows read with blank rows | Rows read includes blank rows (4,010 for F03); blank rows counted under rows left out (RUN-12) | Proposed | Phase 3 |
| SH-02 second long Job | Controls that start a long Job are disabled with tooltip "Another operation is running" | Proposed | Phase 6 |
| C2-08 duplicate-contents check scope | Within the same template only | Proposed | Phase 2 |
| RUNC-10 totals mismatch test | Fault-injection hook behind an environment variable, test builds only | Proposed | Phase 5 |
| Run-from-source route (V1 `packaging/source_install`) | Keep as a dev-only fallback until the certificate arrives, then retire (T3) | Proposed | Phase 11 |
| O12 unencrypted local data | Customer still to confirm (SEC-3); no code impact | Open (customer) | — |
| F20 Sales_Macro.xlsm without a VBA part | Generated as a true macro-enabled workbook (macro content type) with no `vbaProject.bin`; replace with an Excel-saved file if a real module is ever needed | Confirmed 16-11-2026 | — |
| DuckDB offline hardening (spike S1) | `enable_external_access=false` + `allowed_directories` (data folder, `%TEMP%\Sankalan`), empty `extension_directory`, missing local `custom_extension_repository`, then `lock_configuration` | Confirmed 16-11-2026 | Phase 1 |
| Staging lifetime (T9, SEC-4) | `_staging\<id>\` lives for the whole new-run wizard: removed on commit (renamed), discard or leave, a cancelled or failed load Job, and at start-up. `%TEMP%\Sankalan` is emptied after every Job | Confirmed 16-11-2026 | Phase 1 |
| Data-folder move destination (UX-11) | Must be new or empty. Also refused: network paths, the current folder or one inside or containing it, too little free space. OneDrive gives a warning only | Confirmed 16-11-2026 | Phase 1 |
| Export path under S1 (spike S2) | DuckDB writes `<name>.part` in an allowed folder; Python streams it to the chosen folder (adding the BOM), then renames | Proposed | Phase 4 |
| Number text beyond the Tech spec list (spike S5) | `1e3`, `12%`, trailing minus, `Rs.`/`INR`: V1 accepted them; DuckDB `TRY_CAST` accepts `1e3`. Ask the user which the SQL Number rule accepts | Open | Phase 2 |

## Known issues carried in

- The UI mockups don't yet show: the Decimals field (2.3, 3.3), the Input = Loaded + Left out totals table (4.5),
  and "Export left-out rows" (3.1, 5.1). Build them from the Tech Spec.
- Certificate (R1) not yet bought: develop with Smart App Control off; the SAC check waits for a signed build.

## Session log

Newest first. One entry per session: date, phase, what was done, deviations from the plan, what's next.

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
