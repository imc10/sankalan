# Sankalan V2 — Progress

The hand-over file between build sessions. Read it at the start of every session; update it at the end.

## Phase status

| Session | Phase | Status | Branch / commit | Notes |
| --- | --- | --- | --- | --- |
| 1 | 0 — Branch, toolchain, spikes, fixtures | Done | `v2` (Phase 0 commit) | Spike findings S1–S6 change Phases 1, 2, 4: see `tools/spikes/RESULTS.md` |
| 2 | 1 — Storage, catalogue, Job runner | Not started | | |
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
| DuckDB offline hardening (spike S1) | `enable_external_access=false` + `allowed_directories` (data folder, `%TEMP%\Sankalan`), empty `extension_directory`, missing local `custom_extension_repository`, then `lock_configuration` | Proposed | Phase 1 |
| Export path under S1 (spike S2) | DuckDB writes `<name>.part` in an allowed folder; Python streams it to the chosen folder (adding the BOM), then renames | Proposed | Phase 4 |
| Number text beyond the Tech spec list (spike S5) | `1e3`, `12%`, trailing minus, `Rs.`/`INR`: V1 accepted them; DuckDB `TRY_CAST` accepts `1e3`. Ask the user which the SQL Number rule accepts | Open | Phase 2 |

## Known issues carried in

- The UI mockups don't yet show: the Decimals field (2.3, 3.3), the Input = Loaded + Left out totals table (4.5),
  and "Export left-out rows" (3.1, 5.1). Build them from the Tech Spec.
- Certificate (R1) not yet bought: develop with Smart App Control off; the SAC check waits for a signed build.

## Session log

Newest first. One entry per session: date, phase, what was done, deviations from the plan, what's next.

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
