# Sankalan — notes for Claude sessions

Sankalan (संकलन, "compilation") is an offline Windows desktop app for accounting executives. Version 2 (being
built on the `v2` branch) merges and validates Excel/CSV files, runs default outputs, and commits each run to a
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
| Phase order, layout, reuse from V1 | `docs/IMPLEMENTATION_PLAN.md` | |
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
python -m pytest tests -q                  # full suite (must pass before committing)
python tests\fixtures\generate.py          # (from Phase 0) build fixture pack F00–F21
```

## Working rules

- **Branch:** work on `v2` (or a worktree branch off it). Never commit to `main` except the v1 hotfixes the user asks
  for. Never push unless the user asks.
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
