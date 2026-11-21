# Sankalan — notes for Claude sessions

Sankalan (संकलन, "compilation") is an offline Windows desktop app for accounting executives. Version 2 (on `main`;
new work on a branch off `main`) merges and validates Excel/CSV files, runs default outputs, and commits each run to a
local per-template dataset (DuckDB + Parquet) that can be analysed and exported to CSV.

## Start every session here

1. Read `docs/PROGRESS.md`: which phase is next, what earlier sessions changed, and the decisions already settled.
2. Read your phase's section of `docs/IMPLEMENTATION_PLAN.md`.
3. Read only the spec sections that phase needs (map below). Don't re-fetch the claude.ai artifacts; the copies
   in `docs/specs/` are the working copies. If a spec looks wrong or two specs disagree, stop and ask the user.

## Where things are specified

| Need | File | Notes |
| --- | --- | --- |
| What to build, by ID (TPL, IN, MAP, RUN, DO, VAL, VR, ISS, ANA, EXP, SEC, NF, PERF, UI, UX) | `docs/specs/feature-spec-v2.0.md` | |
| How to build it (T1–T27, storage, ingestion, rules table, query layer, packaging) | `docs/specs/technical-spec-v1.0.md` | **Wins over the feature spec** where they differ (its "Feature spec changes" table lists the 21 differences) |
| Screen layouts, copy, column sets, colours | `docs/specs/ui-screens/README.md` + `*.dc.html` | 30 artboards at 1366×768; mockups, not app code |
| Acceptance figures, fixtures F00–F21/P01–P02, screen→test coverage | `docs/specs/test-cases.md` | 191 cases. Expected numbers are the oracle for automated tests |
| Feature-Updates: Rows view, measures by column, export in parts, choose sheets, text in Number/Date columns, templates without checks, BUG-1 (ROW, MEA, EXP-8–14, SHT, TXT, NCK) | `docs/specs/feature-spec-a2.md` | Behaviour and acceptance criteria. Replaces Feature Spec A1 |
| How to build A2 (T32–T67) | `docs/specs/technical-spec-a2.md` | **Wins over Feature Spec A2** where they differ (its section 15.1). Replaces Technical Spec A1 |
| Phase order, layout, reuse from V1 | `docs/IMPLEMENTATION_PLAN.md` | V2 phases 0–12 |
| A2 phases A2-1…A2-6: steps, tests, acceptance | `docs/plans/a2-implementation-plan.md` | Replaces Technical Spec A2 section 16's build order (A1 plan superseded) |
| Status, decisions, session log | `docs/PROGRESS.md` | Update at the end of every session |

## Hard rules (break none of these)

- **Offline.** No network code of any kind (SEC-1): no HTTP, sockets to remote hosts, update checks, telemetry,
  DuckDB extension installs or loads. DuckDB config: extensions off, `lock_configuration` after start.
- **Compiled packages allowed at runtime:** PySide6-Essentials/shiboken6, duckdb, python-calamine. Nothing else
  compiled (no pandas, numpy, pyarrow, openpyxl at runtime). `test_only_allowed_compiled_addons_load` guards this.
  Smart App Control on customer laptops blocks anything unsigned.
- **All SQL in `sankalan/query/`** (plus schema DDL in `sankalan/db/`). Screens never write SQL; DuckDB is used only
  inside Jobs, never on the UI thread. One app-wide DuckDB connection; worker processes never open the database.
- **One long Job at a time** (T6); every long operation shows progress and Cancel where safe (UI-5).
- **Source files opened read-only** (SEC-2). Temp files only in `%TEMP%\Sankalan`; staging only in `<data>\_staging`;
  both emptied when the Job ends and at start-up (SEC-4).
- **Logs never contain cell values** (SEC-5): operation, file name and error class only. Never log DuckDB error text.
- **Commit protocol** is folder rename + one catalogue transaction (T8). Runs never become visible half-written.
  Run IDs count up per template and are never reused (T22).
- **Formats on screen** (UI-7): international grouping `9,812,345`, dates `DD-MM-YYYY`, regardless of Windows region.
  CSV exports: no grouping, `DD-MM-YYYY`, UTF-8 with BOM by default.
- **Values:** blank = empty or only spaces (T14); other spaces kept exactly as typed. Numbers are `DECIMAL(38,d)`,
  d = 0–6 per column, rounded half away from zero (T13).
- **Branding:** title "Sankalan"; no publisher or company name anywhere in the app (UI-4, NF-6). Light theme only.
- **Python 3.13**, PySide6. Windows 10/11 64-bit target.

## Code layout

New code goes in `sankalan/` following the layout in `docs/IMPLEMENTATION_PLAN.md`. V1 code is in `legacy/` once
Phase 0 has moved it there: read it for reuse (header detection, CSV detection, mapping `norm`/`auto_map`,
number/date rules, hidden-row XML scan), copy what you need into the new modules, and never import from `legacy/`.
Note that V1 `to_text` strips spaces; V2 must not (T14).

## Commands

```bat
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-lock.txt -r requirements-dev.txt
python -m sankalan                         # run the app
set QT_QPA_PLATFORM=offscreen
python -m pytest tests -q                  # full normal suite (must pass before committing), expected 190 s
python -m pytest -m slow tests             # full-size tests (A2: each phase runs its own once)
python tests\fixtures\generate.py          # (from Phase 0) build fixture pack F00–F21 (+ TPL-R small; --full)
```

## Test time budgets (stop rule)

Every test file has an expected completion time in `tests/time_budgets.py` (measured, plus ~25% headroom). Testing
time is development time, so:

| Run | Expected | Stop above |
| --- | --- | --- |
| Full normal suite `pytest tests` | 190 s (measured 150 s) | 209 s |
| One test file | its entry in `tests/time_budgets.py` (5–21 s for normal files) | entry + 10% |
| `pytest -m slow tests/engine/test_stored_order.py` | 250 s (measured 198 s; building full TPL-R the first time, ~5 min, is not counted) | 275 s |
| Build tests (`SANKALAN_BUILD_TESTS=1`) | installer file + 170 s | + 10% |

- **If a run exceeds its expected time by more than 10%, stop.** Investigate the cause, fix it, then run again. Don't
  wait for a slow or silent run, and don't just rerun it hoping it passes.
- `tests/conftest.py` enforces this: a file more than 10% over budget ends the run at once with
  `TIME BUDGET: <file> took …` (exit code 3); a test that hangs is killed 10 s later with `Timeout (…)!` and every
  thread's stack (the stuck test is in the dump). A run that stops progressing usually means a GUI test failed
  before discarding its edits and left a real modal dialog open: look at the first failure before it.
- Always run long commands with a timeout (or in the background with the budget in mind) and check them when the
  expected time is up.
- A new test file gets its own entry once timed (unlisted files get 30 s). Raise a budget only when a change
  legitimately makes a file slower, and record why in `docs/PROGRESS.md`. `SANKALAN_NO_TIME_BUDGET=1` turns the
  checks off for debugging with breakpoints only, never for the run that decides a commit.

## Working rules

- **Branch:** never commit to `main`. Always commit to the branch off `main` on which the changes are being made
  (currently `Feature-Updates`), or a worktree branch off it. Changes reach `main` only by merging that branch when
  the user asks. Never push unless the user asks.
- **Scope:** one phase per session. If the phase is too large, finish a coherent part, record what's left in
  `docs/PROGRESS.md`, and stop there.
- **Tests first for engine phases:** turn the matching test-case figures into pytest assertions with generated
  fixtures. Don't change an expected figure to make a test pass: either the code or the spec is wrong, so ask.
- **Open behaviours** marked "record" in the test sheet use the defaults in `docs/PROGRESS.md` → Decisions.
  Confirm with the user before relying on one still marked *proposed*.
- **End of session:** full test suite passing → update `docs/PROGRESS.md` (status, what changed, deviations,
  decisions, next steps) → commit with a clear message. Report anything not done or not verified.
- **Working with the user:** ask clarifying questions when a request is ambiguous; give specific, exact details;
  evaluate options neutrally rather than just agreeing.
