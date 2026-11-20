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
| 7 | 7 — Clients, Client, Template screens | Done | `v2` (Phase 7 commit) | C1, C2, C4 with all four tabs; New template / New run / Run / Export open placeholders until Phases 8–10 |
| 8 | 8 — New template wizard | Done | `v2` (Phase 8 commit) | 2.1–2.6; Save and start first run opens the `new_run` route (Phase 9 placeholder) |
| 9 | 9 — New run wizard and Run detail | Done | `v2` (Phase 9 commit) | 4.1–4.5, 5.1, 7.1, 7.6; export buttons build requests, the Export dialog stays Phase 10's placeholder |
| 10 | 10 — Analysis and export dialogs | Done | `v2` (Phase 10 commit) | 6.1–6.3, 7.4/7.5, 7.7, 7.8; every export now runs through the Export dialog |
| 11 | 11 — Packaging, signing, install/uninstall | Done | `v2` (Phase 11 commit) | Built and self-tested unsigned; signing and DEP-01…13 wait for R1 and the test laptop |
| 12 | 12 — Hardening and release acceptance | Not started | | Partly manual on the 16 GB test laptop |
| — | A1-0 — Fixtures, markers, baselines | Not started | | Feature Spec A1 build: plan in `docs/plans/a1-implementation-plan.md` |
| — | A1-1 — Stored order and the export engine | Not started | | |
| — | A1-2 — Export dialogs | Not started | | |
| — | A1-3 — Measures v2 engine and catalogue version 2 | Not started | | |
| — | A1-4 — Measures UI and header rename | Not started | | Fix the known `test_analysis.py` race first |
| — | A1-5 — Rows view engine | Not started | | |
| — | A1-6 — Rows view UI | Not started | | |
| — | A1-7 — Docs, test sheet, performance suite | Not started | | |

Status values: Not started · In progress · Done · Blocked (say why).

## Decisions

Behaviours the specs leave open (the test sheet says "record"). **Proposed** defaults need the user's confirmation
before the phase that relies on them; mark them **Confirmed** with the date when settled.

| Item | Default | State | Needed by |
| --- | --- | --- | --- |
| C1-04 client-name uniqueness | Unique ignoring case and leading/trailing spaces ("acme traders" refused when "Acme Traders" exists); names stored trimmed. Template names follow the same rule within their client (C2-05) | Confirmed 17-11-2026 | Phase 7 |
| Low-disk threshold (C1-10, RUNF-14) | Amber footer / low-disk warning below **10 GB** free on the data folder's drive (`manage.LOW_DISK_BYTES`); revisit after PERF-08 measures one 10M-row load | Confirmed 17-11-2026 | Phase 7 (Phase 9 reuses it) |
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
| Run-from-source route (V1 `packaging/source_install`) | Kept (ported to V2) for development and manual testing on a PC with Smart App Control off, while the certificate is awaited; retire only when the user says so after the signed installer is in use (T3) | Confirmed 17-11-2026 | Phase 11 |
| Uninstall "delete data" scope (T26, DEP-12) | Yes deletes the data folder settings.json names (even if moved; only if it holds `catalogue.duckdb`) plus `%LOCALAPPDATA%\Sankalan` and `%TEMP%\Sankalan`; No (default, and silent uninstall) touches nothing | Confirmed 17-11-2026 | Phase 11 |
| Installer shortcuts | Start menu `Sankalan` and Desktop `Sankalan` | Confirmed 17-11-2026 | Phase 11 |
| O12 unencrypted local data | Customer still to confirm (SEC-3); no code impact | Open (customer) | — |
| F20 Sales_Macro.xlsm without a VBA part | Generated as a true macro-enabled workbook (macro content type) with no `vbaProject.bin`; replace with an Excel-saved file if a real module is ever needed | Confirmed 16-11-2026 | — |
| DuckDB offline hardening (spike S1) | `enable_external_access=false` + `allowed_directories` (data folder, `%TEMP%\Sankalan`), empty `extension_directory`, missing local `custom_extension_repository`, then `lock_configuration` | Confirmed 16-11-2026 | Phase 1 |
| Staging lifetime (T9, SEC-4) | `_staging\<id>\` lives for the whole new-run wizard: removed on commit (renamed), discard or leave, a cancelled or failed load Job, and at start-up. `%TEMP%\Sankalan` is emptied after every Job | Confirmed 16-11-2026 | Phase 1 |
| Data-folder move destination (UX-11) | Must be new or empty. Also refused: network paths, the current folder or one inside or containing it, too little free space. OneDrive gives a warning only | Confirmed 16-11-2026 | Phase 1 |
| Export path under S1 (spike S2) | DuckDB writes `<id>.csv.part` in `%TEMP%\Sankalan`; Python streams it into `<dest>.part` next to the chosen file (BOM + header first), then renames. Cancel or failure deletes both parts | Confirmed 17-11-2026 | Phase 4 |
| EXP-04 Reason text | "Column: Rule" per Error rule that caused it, in rule order, joined by `; ` (e.g. "Invoice No: Character pattern; Taxable Value: Is a number"). `left_out.parquet` `_reason` holds the rule IDs comma-separated | Confirmed 17-11-2026 | Phase 4 |
| Issue message wording (UI-6) | As listed in the Phase 3 session log; duplicates name the first occurrence; CSV messages omit the sheet | Confirmed 17-11-2026 | Phase 3 |
| Input formats (D38, IN-3) | .xlsx, .xlsm, **.xlsb** and **.xls** (BIFF8) plus .csv. Refused: .txt, .ods, Excel templates, other types. Excel 5.0/95 (`Book` stream), other OLE files and web pages/XML with an Excel name are file errors with their own message. Plan: `docs/plans/xls-xlsb-support.md` | Confirmed 20-11-2026 | — |
| Number text beyond the Tech spec list (spike S5) | Tech spec forms (`₹`, spaces, `,` grouping, `(x)`, leading minus) **plus `Rs.`/`Rs`/`INR`** (any case, before the number). Refused as "not a number": `1e3`, `12%`, trailing minus `500-`, leading plus `+500` | Confirmed 17-11-2026 | Phase 2 |

## Known issues carried in

- The UI mockups don't yet show: the Decimals field (2.3; built on 3.3 in Phase 7), the Input = Loaded + Left out
  totals table (4.5), and "Export left-out rows" (5.1; built on 3.1 in Phase 7). Build them from the Tech Spec.
- Certificate (R1) not yet bought: develop with Smart App Control off; the SAC check waits for a signed build.
- (Phase 11) The dev PC has an older Sankalan install (program folder, shortcuts, `%LOCALAPPDATA%\Sankalan`): run the
  installer DEP cases on the test laptop, not here.
- (Phase 8) Test-process crash (access violation) in some test orders, also on the Phase 7 commit
  (`pytest tests/engine tests/gui`): a closed DuckDB connection left in a reference cycle by an earlier test was
  finalised by a garbage collection on the main thread while a Job thread was inside DuckDB on another connection.
  `tests/conftest.py::collect_garbage` now collects after every test (suite ~95 s). In the app only the data-folder
  move closes one connection and opens another: Phase 12 should check the old connection object is released at
  once (no cycle) or collect right after the move, before the next Job.
- (17-11-2026) `tests/gui/test_analysis.py` fails 1–2 tests per run, varying (`test_list_and_search`,
  `test_rename_and_name_uniqueness`, `test_saved_analysis_rename_and_delete_from_its_screen`,
  `test_save_from_the_leave_prompt`), also on the Phase 11 commit: the test reads `storage.con` on the main thread
  while a Job is still on the shared connection, and DuckDB 2.0 raises `ResourceInUseException` instead of waiting.
  Test-side race (the app never queries on the UI thread); fix by settling the bridge before direct catalogue reads.

## Session log

Newest first. One entry per session: date, phase, what was done, deviations from the plan, what's next.

### 20-11-2026 — .xls and .xlsb input (D38)
- **Decision:** after a spike (Excel 16 saved one workbook in every format it offers; read with python-calamine
  0.9.1), the user chose to add .xls (Excel 97-2003) and .xlsb (Excel Binary). Not added: templates, .ods (calamine
  reads `#N/A` as 0), .txt (separate decision), .xml 2003/.prn/.dif/.slk/.htm. Plan in
  `docs/plans/xls-xlsb-support.md`; no new dependency.
- **Specs updated** (with approval): feature spec IN-3, out-of-scope line, decision D38; tech spec T11, File type
  row, Read section, R5; test-cases snapshot: C3-04 and RUNF-03 (.xls accepted, F29 .txt refused), F11 now Ready,
  new RUNF-15/16/17, CONV-06, fixtures F22–F29, coverage rows. **The live test sheet (claude.ai artifact) still has
  the old C3-04/RUNF-03/F11 text: update it to match `docs/specs/test-cases.md`.**
- **Code:** `ingest/cfb.py` (read-only compound-file reader: v3/v4, mini streams, top-level streams only so an
  embedded object's Workbook isn't mistaken for the file's), `ingest/xls.py` (`XlsBook`: BOUNDSHEET8 sheets,
  FILEPASS → `ExcelPassword`, scan of ROW hidden flag / BOOLERR / FORMULA error results / DIMENSIONS, peek via
  calamine `from_filelike`), `ingest/xlsb.py` (`XlsbBook`: chunked record reader, BrtBundleSh sheets, scan of
  BrtRowHdr hidden bit / error cells incl. short records / BrtWsDim, its own first-rows peek with shared strings so
  a large file isn't loaded). `excel.open_book(fh, kind)` picks the reader; `read_sheet(kind=)` is unchanged
  otherwise. `source.file_kind` decides the kind from content (ZIP `workbook.bin` → xlsb; OLE `EncryptionInfo` →
  password, `Workbook` → xls, `Book` → Excel 95 message, other → not a workbook; text named as a workbook starting
  with `<` → web page message). Probe, sample, stage, file pickers and "accepts" notes updated. Problem code
  `not_xlsx` replaced by `not_excel`, `old_excel`, `web_page`.
- **Fixtures:** F22–F27 are Excel-saved binaries in `tests/fixtures/static` made by
  `tests/fixtures/make_static_formats.ps1` (Excel COM, dev only) from F03, F19 and F06; `generate.py` copies them,
  writes F28 (HTML named .xls) and F29 (.txt), and verifies F22–F25 cell-for-cell against their sources.
- **Tests:** probe (F11 ready, F22/F23 = F03 incl. hidden rows/sheet and row count, F26/F27 password, F28, Excel 95
  and other OLE, content beats extension), load (F22/F23 = F03 rows and totals 6,029,500.00 / 765,378.00; F24/F25 =
  CONV-05), sample (inspect + stage), GUI pickers/refusals, and `tests/unit/test_excel_readers.py` (hand-built v3/v4
  CFB, embedded-object streams, damaged chains, synthetic .xlsb with RK and short records).
- **Speed (dev PC):** 300,000 rows × 8 columns: .xlsx probe 1.3 s / read 5.0 s; .xlsb probe 2.4 s / read 4.7 s;
  .xls (65,536-row limit) probe 0.3 s / read 0.6 s.
- **Not done / not verified:** Strict Open XML .xlsx has no fixture or test (a scratch Excel-saved file read
  correctly in the spike); version-4 (4096-byte sector) .xls files and 1-byte "short" .xlsb cell records are
  covered only by hand-built files, not by Excel-saved ones; `selftest.py` still checks .xlsx + CSV only; .xls
  written by non-Excel tools (ERP exports) was tested only with F11 (xlwt). Not tried by hand in the running app
  (GUI tests cover the pickers, refusals and an .xls sample in the New template wizard).
- Suite: 470 passed, 2 skipped, then 1 failure fixed (a wrapped string "load every" tripped
  `test_no_extension_install_or_load_in_sql`) and 1 known flaky `test_analysis.py` failure (Known issues), which
  passed on rerun with the security and New template tests (59 passed).

### 17-11-2026 — Third-party licence notices
- Licence review of everything shipped: Python 3.13 (PSF), Qt 6.12.0 + PySide6/shiboken6 6.12.0 (LGPL-3.0),
  DuckDB 2.0.0 (MIT), python-calamine 0.9.1 (MIT), IBM Plex (OFL-1.1), Mesa llvmpipe `opengl32sw.dll` (MIT), MSVC
  runtime. All allow closed-source commercial use; the gap was that no notices shipped.
- New `THIRD_PARTY_NOTICES.txt` (repo root): summary, the LGPL-3.0 statement for Qt (replaceable DLLs, reverse
  engineering for debugging, source at download.qt.io plus a 3-year offer "from whoever gave you Sankalan" so no
  publisher is named, NF-6), copyright lines per component, full licence texts (LGPL-3.0 + GPL-3.0, Apache-2.0, MIT,
  BSD-2/3, Zlib, BSL-1.0, FTL, IJG, libpng-2.0, libtiff, Unicode-3.0, Unlicense, OFL) and Python's LICENSE.txt.
  Sources: the binaries a PyInstaller build actually ships, Qt's attribution pages for 6.12, DuckDB v2.0.0
  `third_party/` and duckdb-python's build config, python-calamine's bundled CycloneDX SBOM, SPDX licence texts.
  Licence choices where offered: FreeType under FTL, mbedtls and dual MIT/Apache Rust crates under Apache-2.0.
- Shipped: the PyInstaller spec copies it next to `Sankalan.exe` (so the installer installs it); the source package
  puts it at the zip root and in `app\`. New test `test_third_party_notices_cover_every_runtime_package` fails when a
  pinned runtime package or its version changes until the notices are updated.
- **Not verified / gaps:** Wintab, Imlib2 and ICC licence texts are linked, not copied; copyright lines for the
  MIT crates calamine, quick-xml, zip and zlib-rs are taken from SBOM authors, not their LICENSE files; which Qt
  third-party parts are compiled into the PyPI Windows wheels was taken from Qt's docs, not the Qt SBOM. The 3-year
  source offer is a commitment whoever distributes Sankalan must honour (or drop it and rely on the download link).
- **On upgrade of any runtime package:** refresh `THIRD_PARTY_NOTICES.txt` (versions, copyright lines, Qt URLs).
- Suite: 451 passed, 2 skipped, 1 failed (`test_new_template_cancel_keep_editing`: "Read sample failed: JobBusy",
  the start-up "Read clients" Job still running; a timing race like the one under Known issues, passed 3 of 3 runs
  on its own). A PyInstaller build in a scratch folder put `THIRD_PARTY_NOTICES.txt` next to `Sankalan.exe`.

### 17-11-2026 — Fix: prompt buttons did nothing (Discard, Discard run, Leave without saving, …)
- Reported in manual testing: Cancel → "Discard" in New template and New run left the wizard open.
- Cause: `Choice` (every `ask()` prompt) wired its buttons as `lambda k=key: self._pick(k)`; Qt's `clicked(bool)`
  passed `checked=False` into `k`, so every button returned False. Prompts affected: Discard this template?, Leave
  and discard this run?, Save your changes? (Template tabs and leaving the screen), This analysis isn't saved,
  Change template?, Delete saved analysis, Start a new run on …?, Replace file? (export), Use a synced folder?,
  close while a Job runs. Fixed with `lambda _c=False, k=key:` as the rest of the UI does.
- Why tests missed it: every GUI test answered prompts through `base.answer_hook`, which bypasses the buttons.
  New `tests/gui/test_dialog_buttons.py` (15 tests) leaves the hook off and clicks the real buttons at every Discard
  point: New template (Cancel with/without a sample, Keep editing, leaving by the rail), New run (Cancel before and
  after reading files, Stay, leaving by the rail; staging emptied), Template tab bar Discard, switching tab, leaving
  the screen, unsaved analysis "Leave without saving". 14 of the 15 fail on the old code.
- Checked: the `QMenu.addAction(text, lambda t=t: …)` "Add rule" menus are not affected (no `checked` passed).
- Suite: 450 passed, 2 skipped, 1 failed (`test_save_from_the_leave_prompt`, the pre-existing analysis-test race
  under Known issues; it uses the hook, not the changed code).
- Also this session: installed 2.0.0 from source on the dev PC and ran a manual demo (Test Client, 10 × 5,000-row
  files) outside the repo.

### 17-11-2026 — Phase 11 follow-up: version 2.0.0, README, run from source for manual testing
- `__version__ = "2.0.0"` (exe resource, installer name `Sankalan-Setup-2.0.0.exe`, source zip
  `Sankalan-2.0.0-Windows.zip`, App settings).
- README rewritten for V2: features, where data is kept, the two install routes (signed installer for customers;
  run from source for manual testing with Smart App Control off), self-test, development, layout, limits. CHANGELOG
  has a 2.0.0 entry marked "not yet released (manual testing)".
- The user keeps run-from-source to deploy on their own PC (SAC off) for manual testing while the certificate is
  awaited. `Install Sankalan.bat` now rebuilds the Python environment when its pinned packages differ from the
  app's (marker `venv\sankalan-requirements.txt`), so a Sankalan 1.x source install's environment (with
  cryptography, XlsxWriter, …) is replaced, not reused. 1.x JSON templates are not imported.
- Tests: full suite passing (see commit).

### 17-11-2026 — Phase 11: Packaging, signing, install/uninstall
- **Decisions (asked and confirmed 17-11-2026):** run-from-source kept as a **dev-only fallback** until the
  certificate arrives (it can't help customers: SAC blocks the unsigned duckdb/calamine `.pyd` files from source too);
  uninstall **Yes** deletes the data folder settings.json names (even when moved) plus `%LOCALAPPDATA%\Sankalan` and
  `%TEMP%\Sankalan`, **No** (default, and silent uninstall) touches nothing; installer makes **Start menu + Desktop**
  shortcuts.
- **`sankalan/selftest.py`** (`--self-test [--report f.json] [--expect-signed] [--no-window]`): everything in a new
  temp folder standing in for `%LOCALAPPDATA%`/`%TEMP%`, so user data is never opened. Generates a stdlib-only .xlsx
  (one hidden row) + CSV (one later duplicate); checks DuckDB 2.0 + calamine load, config locked
  (`connection.configuration_locked`), files probed, read in **2 reader workers** (from the exe: the same exe in
  worker mode), duplicate found, override, default output, totals Input = Loaded + Left out (hidden value absent),
  commit R-0001, CSV export with BOM, staging/temp empty, re-open backs up the catalogue at the current schema
  version (update path), only allowed compiled packages, window titled "Sankalan" (PNG beside the report), and on a
  packaged Windows build `Get-AuthenticodeSignature` over every .exe/.dll/.pyd (fails only with `--expect-signed`).
  From source 1.6 s, packaged 6 s; both PASS.
- **`sankalan/uninstall.py`** (`--remove-data`, exit 0 / 1 partly / 2 not ours): deletes the data folder only if it
  holds `catalogue.duckdb` and isn't a drive root. `log.close_handlers_under`.
- **packaging/**: `version.py` (single source: `sankalan.__version__` → exe resource, installer name, DEP-06);
  `sankalan.spec` (folder build, upx off, icon, version file generated in the work dir); `version_info.txt` is a
  template; `make_icon.py` + new `sankalan.ico`/`.png` from `theme.monogram_pixmap` (V1's blue "S" replaced);
  `sign_files.ps1` (`-Path` folder or file, `-Thumbprint` for the USB-token certificate or `-Pfx`, `-VerifyOnly`,
  finds signtool in Windows Kits, verifies RSA + timestamp on our signatures); `sign_one.bat` (makensis hook);
  `installer.nsi` (MUI2, per-user `%LOCALAPPDATA%\Programs\Sankalan`, no admin, Start menu `Sankalan.lnk` + desktop,
  removes V1's Start-menu folder, upgrade in place clears `_internal` first, waits for Sankalan to close on install
  and uninstall, T26 question → `Sankalan.exe --remove-data`, `!uninstfinalize`/`!finalize` sign the uninstaller and
  installer when `/DSIGN` is given, BrandingText "Sankalan <version>", no publisher/copyright);
  `build_windows.bat` (tests → PyInstaller → sign → self-test with `--expect-signed` when signing → NSIS → verify
  installer signature; env `SANKALAN_SIGN_THUMBPRINT` or `SANKALAN_PFX`(+password), `SANKALAN_TIMESTAMP_URL`).
  Source route ported to V2: `Sankalan.pyw` → `sankalan.__main__.main` (guarded for spawn), README marked dev-only,
  uninstall asks about data, demo-data = self-test samples, refuses to install over the signed install.
- **Tests:** 436 passed, 2 skipped (`tests/packaging/test_installer.py`, 21 tests). The 2 skipped run with
  `SANKALAN_BUILD_TESTS=1` (PyInstaller build + packaged self-test + installer compile, ~2¼ min): run this session,
  both pass. Installer compile with a stand-in signer checks the uninstaller and installer both go through `SIGN`.
- **Not verified:** signing (no certificate, no signtool on this PC); DEP-01…13 (manual) — the installer was **not
  run** here because this PC already has a Sankalan install (program folder, Start menu and desktop shortcuts, data
  in `%LOCALAPPDATA%\Sankalan`) that it would overwrite; the installer's running-app check, the T26 dialog and
  `--remove-data` from the uninstaller; Windows 10; SAC. Qt ships 113 unsigned files in the build — all get signed
  by `sign_files.ps1`.
- **Next:** Phase 12. The source route stays until the user decides to retire it (see the follow-up entry above).

### 17-11-2026 — Phase 10: Analysis and export dialogs
- **Decisions:** no Proposed decision used (the only one left, run-from-source, belongs to Phase 11). Saved-analysis
  names follow the confirmed C1-04 / C2-05 rule (unique within the template, ignoring case and outer spaces).
- **Query layer (`query/catalogue.py`):** `saved_analysis_rows`, `saved_analysis`, `saved_analysis_names`,
  `rename_saved_analysis`, `delete_saved_analysis`, `template_choices`.
- **`sankalan/analyses.py`** (Job work, no SQL): list + `matches` (name, client, template), `template_data` (runs
  newest first with file names; damaged runs left out), `open_saved`, `save` / `rename` / `delete`, `run` (checks the
  definition, runs into a temp table, drops the previous result only once the new one exists), `ResultSource`
  (first `ROW_CAP` rows, header sort within parent groups, cells formatted, `_depth` last), `total_cells`,
  `distinct_values`, `export_items` (the full result as shown: subtotals and sort, grand total last), `describe`
  (6.3 locked lines). `formats.result_cell` now holds the result-cell format (moved from `template_outputs`).
- **Export model:** `ExportRequest.what` ("R-0013 data", "all outputs of R-0001", the analysis name) and `rows`;
  `prefill(rows=)`; `model.export.describe`. The Run screen passes `rows_loaded` for Export data.
- **Screens and dialogs:** `screens/analyses.py` `AnalysesScreen` (6.1: subtitle, search name/client/template, New
  analysis, grid Name · Client · Template · Saved on · ⋯ Open / Rename / Duplicate / Delete with a plain confirmation,
  empty and no-match states). `screens/analysis.py` `AnalysisScreen` (6.2/6.3: badge Not saved / Saved DD-MM-YYYY,
  Save… or Duplicate to edit + ⋯ Rename / Delete; 380 px settings panel: client and template combos, runs list
  "R-0001    Sales_Oct.xlsx" with file names as tooltip, Select all, "3 of 4 runs selected" / "No runs selected. Tick
  the runs to include.", the builder or the locked summary, Run; result panel: summary line, Export (.csv),
  ProgressPanel with Cancel, PagedGrid with subtotal rows in medium weight, pinned grand total, cap note; empty
  states). `dialogs/export_dialog.py` `ExportDialog` (7.4 → 7.5 in place; folder + Change…, file name or name
  pattern for Export all outputs, delimiter, encoding; replace prompt; banner with Open folder, or "Export
  cancelled…"). `dialogs/values_dialog.py` `ValuesDialog` (Is one of picker: busy bar + Cancel, top 1,000 with
  counts, search of the whole column, ticks kept across searches). Builder `picker` hook; window routes `export`
  (dialog; `last_export` still recorded) and `analysis`; area factory `analysis` → `AnalysesScreen`;
  `MainWindow.drop_results` / `pending_drops` for temp tables of screens that were left. `PagedModel.emphasis` and
  `set_columns`. `Screen.show_banner` shows a banner at once on a visible screen (a layout only showed it on the
  next event loop pass).
- **Tests:** 420 passing, full suite run twice (32 new in `tests/gui/test_analysis.py` on TPL-A with R-0001…R-0004,
  R-0004 being the sheet's F14 R-0006): A0-01…05, A1-01…14 (A1-11 with a run held until Cancel; A1-12 with the cap
  lowered to 1,000 and a 5,000-group result; A1-08 picker on 10 customers × 500 and a search), EXP-01…08 through the
  dialog (EXP-08 holds the stream until Cancel; Open folder target checked), C6-06 by pattern + replace prompt,
  analysis export with subtotals, save from the 7.7 prompt, rename/delete from 6.3, removed column in a saved
  analysis. `test_shell::test_left_rail` now expects the A0 title "Analyses". Screens rendered offscreen at 1366×768
  and looked at.
- **Interpretations** (change if wrong):
  - "Saved on" is the date the analysis was saved; a rename doesn't change it.
  - After Save… the analysis stays on screen locked (6.3) with its result and ticked runs. Save… in 7.7 saves then
    leaves; Cancel in the Save dialog stays.
  - Duplicate to edit (6.3) carries the ticked runs; Duplicate from the list starts with none ticked.
  - Export (.csv) is off while the result is greyed (tooltip "Run again to export."); it exports the result as
    shown (sort, subtotals). `{Output}` is the saved name, else "Analysis"; `{RunID}` drops out.
  - The Export dialog doesn't save a changed folder or options back to the template's defaults. Its info line shows
    rows when known ("5,000 rows · CSV file"); the canvas's "about 1.4 GB" estimate is not shown.
  - While exporting the dialog stops being modal (7.5 "You can keep working in other screens"); Esc does nothing
    then, Cancel export stops it. Export all outputs asks to replace when the first existing file is met.
  - Default outputs (3.2, 2.5) keep typed comma-separated values for Is one of; the picker is on the Analysis screen
    only (no ticked runs to read values from there).
  - A run left running when the screen is closed finishes, but its temp table is only dropped when the app closes.
- **Not verified:** A1-11, A1-12, A1-15, EXP-08 on the 10M-row data (P01; tests hold Jobs open instead); the real
  folder picker; Explorer opening from Open folder; screens at 125% / 150% and on the laptop; menus opened by a real
  click on ⋯.
- **Next:** Phase 11 (Packaging, signing, install/uninstall). Run-from-source is still Proposed: confirm first.

### 17-11-2026 — Phase 9: New run wizard and Run detail
- **Decisions:** no Proposed decision used (the only one left, run-from-source, belongs to Phase 11). Low-disk
  threshold (10 GB) reused for RUNF-14.
- **Engine additions:** `RunSession.recheck_files` (Re-check on the Files step, keeps Load anyway) and
  `drop_staging` (Cancel/Back on Validate: staging deleted, files and mapping kept). `query/validate.rule_lines`
  (by-rule table of a stored issue list), `query/convert.rows_by_file` (rows loaded per file-sheet).
- **`sankalan/runs.py`** (Job work, no SQL): `wizard_start` (template, client, free space, next Run ID),
  `rule_lines` / `stored_rule_lines` (Errors first, then column and rule order; "N other rules passed"),
  `IssueSource` (PageSource over an issue list, first 10,000 per rule, rule/severity filters, sort),
  `stored_output` (an output read back as stored, DO-6), `run_view` (run details, rules that ran = snapshot at the
  run's version + run-only edits, rows loaded per file), `export_items` (data, left-out rows, issue list, one output,
  all outputs → queries and file names), `rule_change_lines`, `mapping_lines`.
- **`model/export.ExportRequest`** gained `output` (position), `subtotals`, `values` (Client/Template/RunID for the
  per-output names of Export all outputs) and `items` (Job work a screen supplies for data not committed yet: the
  Validate step's issue list). `prefill(position=, subtotals=, items=)`.
- **Screens:** `screens/new_run.py` `NewRunScreen` (StepBar with skipped Mapping/Outputs, ProgressPanel, footer:
  Cancel · Back · text · Continue despite errors… · Re-check files · Next / Commit R-00NN), `FilesStep` (Add files…,
  drag and drop, refusals listed, grid File · Sheet · Size · Header · Rows ≈ · Status · ✕, per-file banners: error
  → Exclude file / Re-check, duplicate → Remove file / Load anyway, low-disk warning, summary with hidden data and
  skipped files), `MappingStep` (grid rows = template columns then headers not in the template, columns = file-sheets,
  amber undecided cells, decision panel: pick a header + Map and save as alias / This run only / Leave as null with
  the (Null) output warning; Leave out / Add as new column… dialog). `screens/new_run_steps.py`: `ValidateStep`
  (result banner, tiles Errors · Warnings · Rows read · Hidden data skipped, `IssuesView` = by-rule table + paged issue
  grid with severity filter, "showing the first 10,000 of 15,000", Edit rules for this run, Export issue list),
  `OutputsStep` (per-output status, Retry, Show subtotals, "Export is available after commit", `ResultTable`),
  `CommitStep` (what will be committed, decisions, totals table In the files · Loaded · Left out, comment ≤ 500 with
  counter, required + prefilled after override). `screens/run.py` `RunScreen` (badge, summary line, Export data, ⋯
  Export issue list / Export left-out rows / Delete run; tabs Summary · Issues · Outputs · Source files).
  `dialogs/run_dialogs.py`: `OverrideDialog` (7.1), `AddColumnDialog`, `EditRulesDialog` (the 2.4 rules editor on
  this run's columns + "Also save these rule changes to the template"), `LimitedText`. `widgets/result_table.py`.
  Routes `new_run` and `run` registered (placeholders removed); `Screen.title_row` holds a badge beside the h1.
- **Fixes to earlier code:** `JobBridge.poll` clears busy before delivering callbacks, so a callback can start the
  next Job (the wizard chains Prepare rows → Generate outputs, Commit step → Check totals). `Breadcrumb.set_crumbs`
  hides old parts before deleting them (they were drawn under the new ones until the next loop pass).
  `tests/engine/test_jobs.py::test_cancel_callbacks_and_abort_cleanup` waited a fixed 50 ms for the Job thread to
  register its callbacks; under full-suite load it failed once this session. It now waits on an event (probably the
  unnamed one-off failure Phase 1 recorded).
- **Tests:** 388 passing on the final code (19 new in `tests/gui/test_new_run.py`, the TPL-A sequence through the
  screens on one module storage): RUNF-01…14 (RUNF-06 with an Excel-style handle, Re-check → Ready), RUNM-01…05/07/08,
  RUNV-01…10/12/13 (RUNV-07 and C6-06 write real CSVs through `runs.export_items`), RUNO-01…07 (RUNO-06 holds the
  output write until Cancel), RUNC-01…09, C6-01…10 (C6-09 delete from the Run screen), TPL-C (Outputs skipped),
  TPL-D (one row per sheet), wizard and Run screen fit 1280×640. Rendered offscreen at 1366×768 and looked at.
- **Interpretations** (change if wrong):
  - Mapping lists every header no template column uses as a "Not in the template" row, including one the user will
    pick for a missing column (F08 "Inv No"); it leaves the list once mapped. Next with decisions left selects the
    first undecided item (cells, then extra headers).
  - Back from Validate (and Cancel during it) deletes the staging folder and returns to Mapping, or Files when Mapping
    was skipped. Back from Outputs (or from Commit when Outputs was skipped) validates again, since the rows were
    split. Back from Mapping to Files keeps the decisions while the file list is unchanged.
  - The Commit button and 7.1 name the next Run ID ("Commit R-0003"): last issued + 1; the number is still issued
    only in the commit transaction (T22).
  - Issue grid columns follow RUNV-04 (File · Sheet · Row · Column · Value · Rule · Severity), the full message as the
    row's tooltip; a blank value shows "(blank)". The mockup's Problem column is not drawn.
  - Totals table: Column · In the files · Loaded · Left out (the Tech spec's Input = Loaded + Left out).
  - Output times on the Outputs step are the generate Job's time split evenly over the outputs it made.
  - Export buttons (Validate issue list, Run screen data / issues / left-out / one output / all outputs) open the
    `export` route with an `ExportRequest`; Phase 10's dialog should run `runs.export_items` then `exporting.export`
    or `export_many`. Export left-out rows on a run with none says so (`RunProblem`).
  - Run screen Source files: "Rows loaded" counted per file-sheet from `data.parquet` (`run_file.rows_read`
    includes blank rows).
  - "Load anyway" and "Path at load time" are written as split string literals so the SQL `LOAD` guard in
    `tests/security/test_offline.py` doesn't read them as statements.
- **Not verified:** the real file dialog and drag and drop from Explorer (tests call `add_files`); screens at
  125% / 150% and on the laptop; RUNV-11 with a source really edited in Excel (Re-check runs Validate again, which
  re-reads); RUNV-12 / RUNO-06 cancel speed on P01; the menus opened by a real click on ⋯.
- **Next:** Phase 10 (Analysis and export dialogs): replace the `export` route with the 7.4/7.5 dialogs, resolving
  requests with `runs.export_items`; the builder's "Is one of" still takes typed values.

### 17-11-2026 — Phase 8: New template wizard
- **Decisions:** no Proposed decision used (the only one left, run-from-source, belongs to Phase 11).
- **Readers:** `csvread.read_csv` and `excel.read_sheet` take `limit` (stop after that many data rows; `limited`
  set), so the sample never reads past 100,000 rows (C3-03).
- **`ingest/sample.py`** (no DuckDB): `refusal` (folders, .xls, other types, lock files, missing), `inspect` (read-only
  open; password/old-xls/locked messages; sheets visible/hidden, header row by the run's detection, rows from the
  dimension record, first rows for the preview with dates as DD-MM-YYYY via calamine's row iterator; CSV encoding
  from the first 4 MB and delimiter from the first 64 KB, both overridable), `read_part` worker task.
- **`query/sample.py`:** one scan over the raw sample text per column: filled, Number-rule readable, leading zeros,
  ISO / DD-MM-YYYY / DD/MM/YYYY shapes, readable dates per format, first two distinct values.
- **`newtemplate.py`** (Job work): `inspect`, `check_name`, `default_source`, `sheets_to_read`, `sheets_problem`,
  `stage` (new staging folder per read, previous one removed; sheets in order, 100,000 rows in total; headers in
  several sheets lined up by MAP-2), `detect` + `percent` (% note), `draft_columns`, `columns_problem`,
  `convert_sample` (same convert SQL as a run, cached per column signature), `dry_run` (VR-8 counts + first 20),
  `preview` (DO-8), `build_template` (included columns renumbered c001… in the order shown; rules, Unique keys and
  output definitions re-pointed), `save` (`create_template`, version 1; nothing under `t\`).
- **Screens:** `screens/new_template.py` `NewTemplateScreen` (StepBar, Cancel · Back · footer text · Next / Save
  template + Save and start first run, ProgressPanel with Cancel for reads): 2.1 name + file (Choose…, drag and drop,
  `FILE_FILTER`, "Read 1,000 rows for previews"), 2.2 sheets (three options, sheet list with hidden sheets greyed
  "Hidden, skipped", preview with the header row tinted and "Header found in row 3"; CSV: encoding and delimiter
  combos with what was detected), 2.3 columns grid (Include, header, name, type, Decimals 0–6 on Number only, Date
  format only for text dates — Excel dates show a disabled "Excel dates", Detected % note amber below 100%, sample
  values formatted, ↑↓), 2.6 review (summary lines as the canvas plus a Column · Type · Rules table).
  `screens/new_template_rules.py`: 2.4 `RulesStep` (column list, "Number · Becomes fixed after the first run",
  rule menu per type, `RuleDialog`, Error/Warning, "0 of 1,000 fail" counts as buttons opening `ShowDialog` with the
  first 20 rows: Row · Value · Message), 2.5 `OutputsStep` = `OutputsTab` without its save bar, previewing "On the
  sample · …" (`OutputsTab.preview_work` hook added). Route `new_template` registered; ClientScreen passes the name.
- **Tests:** 369 passing, full suite run twice (27 new: `tests/engine/test_template_sample.py` 9 (C3-03 on a generated 150,000-row
  CSV, limit on Excel and with a real worker, sheets/hidden, 1252 CSV, refusals and password, type detection on F17 =
  TPL-C, dry-run counts on F04 = C3-16, build/renumber/save), `tests/gui/test_new_template.py` 18 (C3-01…C3-22, every
  step fits 1280×640)). C3-18 previews match the sheet exactly (DO1 per state and grand total; DO2 Aug-2026 rates
  and subtotal 1,507,375.00).
- **Interpretations** (change if wrong):
  - Sheets step starts on "By name" with the first visible sheet ticked (canvas 2.2; C3-20 expects "By name: Sales").
  - Type detection: Date when ≥ 80% of filled values are shaped like a date (the format whose shapes cover most,
    Excel/ISO dates preferred on a tie), else Number when ≥ 80% read as numbers and none has a leading zero (codes
    such as 00123 stay Text, MAP-9), else Text. The note gives the share that actually reads ("90.9% numbers",
    "84.61% dates · DD-MM-YYYY", "100% dates · Excel dates", "100% text"), or "N% blank" when half or more are blank;
    shares are floored, never shown as 100% unless exact. Decimals default 2 (C3-10).
  - Detected CSV encoding and delimiter are not stored (runs detect per file); a value the user changes is stored as
    the template's override. "UTF-8 with BOM" is not offered separately (UTF-8 reads both).
  - 100,000 rows means in total across the sheets read, in sheet order. "Read N rows for previews" shows the rows
    actually read (1,000 for F01, 100,000 for P01).
  - Re-reading happens only when the file (path, size, modified time), the sheets read, the encoding or delimiter
    change; entries for headers still present are kept, new headers go last.
  - Dry run runs on entering step 4 and after every rule change, one at a time (a change during a run queues one
    more); counts are on the app connection over the staged sample, not a separate in-memory database (Phase 3 note).
  - Save → the client's screen with "<name> saved."; Cancel / leaving asks "Discard this template?" (Keep editing /
    Discard, "Your entries will be lost. Nothing has been saved."). Saving and discarding remove the staging folder.
  - The step 2 preview comes from calamine and includes hidden rows; header detection (like a run) skips them.
- **Harness fix:** see Known issues (garbage collected after every test; the crash predates this phase).
- **Not verified:** the screens by eye at 1366×768 / 125% / 150%; the real file dialog and a real drag and drop
  (tests call `pick`); C3-03 with the real P01 (a generated 150,000-row CSV stands in); the preview speed of
  calamine's row iterator on a 1M-row sheet.
- **Next:** Phase 9 (New run wizard and Run detail): replace the `new_run` route (`template_id`, `name`); reuse
  `ProgressPanel`, `StepBar`, `ShowDialog`-style lists and `RuleDialog`.

### 17-11-2026 — Phase 7: Clients, Client and Template screens
- **Decisions confirmed by the user:** C1-04 names unique ignoring case; low-disk threshold 10 GB (see Decisions).
  No other Proposed decision used.
- **Query layer (`query/catalogue.py`):** `client_rows`, `client_names`, `client_name`, `rename_client`,
  `template_names`, `template_rows`, `template_header`, `run_rows` (file names per run, newest first), `latest_run`,
  `overview`, `saved_analysis_count`, `run_delete_figures`, `insert_saved_analysis` (Phase 10 builds the screens;
  delete counts need the table now).
- **`manage.py`** (Job work for the screens, no SQL): name checks (`NameRefused`: "Enter a client name.",
  "“Acme Traders” is already in use. Choose another name.", ≤ 100 characters), clients overview + storage
  figures (`StorageFigures.low` below `LOW_DISK_BYTES`), create/rename/delete client, client detail,
  rename/duplicate/delete template (a rename is a save: version + 1), template detail (runs, size of `t\<id>`,
  latest run), `save_template`, delete summaries for dialogs 7.2/7.3 and the undrawn delete-template dialog,
  `output_preview` (DO-8: first 1,000 rows + grand total, temp table dropped), `test_rules` (VR-8).
- **Formats / export model:** `formats.gigabytes` ("41.6 GB", "112 GB", "0 GB"), `formats.count` ("1 template",
  "10,937 rows"); `model/export.ExportDefaults` (template `export` dict: folder, pattern, delimiter, encoding
  `utf-8-sig`/`utf-8`; folder defaults to Documents) and `prefill()` → `ExportRequest` (pattern resolved, C4-18).
- **Widgets:** `PagedGrid` gained `GridColumn.fmt / tooltip / colour / right`, cell kinds `ACTION` (drawn outline
  button, "New run"), `MENU` (⋯) and `LINK` (name), `cellClicked`, Enter opens a row, and `ListSource` (in-memory
  sort and search, blanks last). `controls.py`: SearchBox, icon buttons (↑ ↓ ✕ ⋯ icons added), ChipList (aliases,
  sheet names), CountTabs, SaveBar ("Unsaved changes · Discard · Save", Save guarded). `builder.py`:
  `DefinitionBuilder` (AND filters, group levels with grain and ↑↓, measures "Sum of Taxable Value" + "as" name,
  Show subtotals) shared with Phases 8 and 10; `output=True` offers only latest month/quarter/year + blank/not
  blank on dates. `dialogs/rule_editor.RuleDialog` (settings per rule type, checked with `check_rule`).
- **Screens:** `screens/common.DataScreen` (quiet loads retried when the runner frees up, long Jobs through the
  bridge, `NameDialog`, `confirm_delete`, plain error text; callbacks do nothing once the screen or window is gone).
  `ClientsScreen` (1.1: grid, A–Z, header sort, search with no-match text, New client, row ⋯ Open/Rename/Delete,
  empty state, storage footer amber when low), `ClientScreen` (1.2: grid, New run on the row after "Start a new run
  on …?", ⋯ Rename/Duplicate/Delete only, empty state), `TemplateScreen` (3.1: header summary, New run, tabs with
  the outputs count; Runs grid newest first, hover file names/comment, search comments + file names, ⋯ Open /
  Export data / Export issue list / Export left-out rows / Delete). `OutputsTab` (3.2: run order list with ↑↓ ⋯
  Duplicate/Delete, Add output, builder, Preview on the latest run with progress and Cancel, "Settings changed:
  Preview again"), `ColumnsTab` (3.3: list with rules/aliases counts and ↑↓, Add column, detail with name, type +
  "Fixed after the first run", decimals, date format, totals-check tick, aliases, rules with Error/Warning and test
  counts, Remove column; Test rules on latest run with "Nothing is stored."), `SettingsTab` (3.4). Each editing tab
  saves only its own part onto the template as last saved (no tab overwrites another's settings); switching tab or
  leaving with unsaved edits asks Save / Discard / Stay.
- **Window:** `MainWindow.go(route, …)` with `routes` for client, template, new_template, new_run, run, export.
  Clients is now the real screen. New template (Phase 8), New run and Run (Phase 9) open placeholder screens; Export
  shows "The Export dialog arrives in Phase 10." and keeps the `ExportRequest` in `window.last_export`.
- **Fixes to Phase 6 code:** `PagedModel` connected `jobFinished` with a lambda, so a deleted model was still
  called; it now uses a bound slot and every Job callback checks the model is still valid (shiboken6.isValid).
- **Tests:** 342 passing, full suite (38 new: `tests/gui/test_clients.py` 10, `tests/gui/test_template.py` 20,
  `tests/unit/test_manage.py` 8). C4 runs on TPL-A with R-0001…R-0003 committed through the real pipeline
  (`conftest.tpl_a_template`, `commit_tpl_a_run`). Covered: C1-01…11 (C1-10 by faking the free space), C2-01…08,
  C4-01…05 (preview = RUNO-03 figures, since R-0003 is the latest run), C4-06/07 (R-0001's saved DO1 keeps 3
  measures), C4-08, C4-09…16 (C4-13 parquet mtime unchanged; C4-14 Region Code (Null) 5,000 on R-0001; C4-16
  GSTIN removed, saved analysis labels "(removed)", Count distinct 5,000), C4-17, C4-18, delete run (7.2), tabs fit
  1280×640.
- **Interpretations** (change if wrong):
  - Duplicate names the copy "<name> (copy)", then "(copy 2)", … (C2-03 searches "copy").
  - New run from a C2 row asks "Start a new run on <template>?" (Cancel / Start run); New run on the template
    screen starts without asking.
  - Export settings offer UTF-8 with BOM and UTF-8 only (EXP-3); the mockup's Windows-1252 export option is
    dropped. CSV input encoding offers Detect / UTF-8 / Windows-1252. The example file name ends in `.csv`.
  - Rename and Delete of a client / template, and Delete of a run, are long Jobs (guarded, not cancellable).
  - A column added on the Columns tab stays editable (type, decimals) until saved; once saved on a template with
    runs it is locked like the others. Removing a column on a template with runs sets `removed`; with no runs it is
    deleted. Its rules go, and it is dropped from wider Unique keys.
  - An alias that matches (MAP-2 normalised) another column's name or alias is refused.
  - Rules count in the column list includes the automatic type rule (as the mockup's counts).
  - "Is one of" values in the builder are typed comma-separated until Phase 10 adds the value picker.
  - Status "Files missing" for a run marked damaged by start-up recovery.
- **Not verified:** the screens by eye at 1366×768 / 125% / 150% (offscreen only; the tabs' minimum sizes fit
  1280×640); real Explorer free space vs the footer (C1-09 compares with `shutil.disk_usage`); hover tooltips shown
  by a real mouse; menus opened by clicking ⋯ (tests call `row_menu` directly).
- **Known limits:** while a long Job runs (e.g. a data-folder move), screens wait to load their lists until it ends.
  Delete saved analysis (undrawn) belongs to the Analysis list and is left to Phase 10.
- **Next:** Phase 8 (New template wizard): replace the `new_template` route, reuse `DefinitionBuilder`
  (`output=True`) and `RuleDialog`; "Save and start first run" goes to the `new_run` route.

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
