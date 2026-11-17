# Sankalan

Offline Windows desktop app for accounting executives who work across many clients. It merges and validates
Excel/CSV files, generates each template's default outputs, and commits every run to a local dataset per
template that can be analysed and exported to CSV. No internet, no telemetry, no LLM.

Version 2.0.0 · Python 3.13 · PySide6 (Qt) · DuckDB 2.0 · python-calamine · Windows 10/11 64-bit ·
16 GB RAM with SSD recommended

## What it does

The app has two areas in the left rail: **Clients** (Clients → Client → Template → Run) and **Analyses**.

1. **Clients and templates.** One template per client task. The New template wizard builds it from one sample file:
   sheets to read, columns (Text, Number with 0–6 decimals, Date), rules, default outputs.
2. **Runs.** The New run wizard takes files (.xlsx, .xlsm, .csv) through Files → Mapping → Validate → Outputs →
   Commit:
   - finds the header row, skips hidden rows and sheets, blank rows and Excel lock files, and warns about files
     already loaded;
   - maps columns across files, learning aliases ("Inv No" → Invoice No);
   - checks the template's rules (not blank, text length, character pattern, number and date ranges, allowed
     values, unique within the run, is a number, is a date). Errors stop the run; an override with a reason leaves
     the rows with errors out, and every issue names the file, sheet and row;
   - runs the default outputs, then a totals check: Input = Loaded + Left out for each ticked column;
   - commits the run (R-0001, R-0002, …) to the template's dataset. A run is never visible half-written.
3. **Run detail.** Data, issues, left-out rows and outputs of every committed run, each exportable to CSV.
4. **Analyses.** Filters, multi-level grouping, measures, optional subtotals, across any runs of a template; saved
   or ad hoc, exported to CSV.

Numbers show as `9,812,345` and dates as `DD-MM-YYYY` whatever the Windows region. CSV exports are UTF-8 with BOM
by default.

Where things are kept:

| What | Where |
| --- | --- |
| Data folder (catalogue + one folder of Parquet files per run) | `%LOCALAPPDATA%\Sankalan\Data` (can be moved in App settings, not to a network folder) |
| Settings | `%LOCALAPPDATA%\Sankalan\settings.json` |
| Log (operation, file name and error class only, never cell values) | `%LOCALAPPDATA%\Sankalan\logs\sankalan.log` |
| Catalogue backups (last 5, one per start) | `<data folder>\catalogue-backups` |
| Temporary and spill files (emptied after each operation and at start-up) | `%TEMP%\Sankalan` |

Sankalan 1.x templates (`Documents\Sankalan\Templates\*.json`) are not imported; create the templates again in 2.0.

## Ways to install

| | Signed installer | Run from source |
| --- | --- | --- |
| For | Customer laptops (Smart App Control on) | Development and manual testing on a PC with **Smart App Control off** |
| Needs | The RSA OV code-signing certificate (not yet available) | Python 3.13 64-bit on the PC |
| Build | `packaging\build_windows.bat` | `packaging\make_source_package.py` |
| Installs to | `%LOCALAPPDATA%\Programs\Sankalan` (no admin rights) | `%LOCALAPPDATA%\Programs\Sankalan` (no admin rights) |

Smart App Control blocks unsigned compiled files. DuckDB and python-calamine ship unsigned `.pyd` files, so
**running from source does not work with Smart App Control on**. Use it only where Smart App Control is off,
until the signed installer is available.

### Run from source (manual testing)

1. Check Smart App Control is off: Windows Security → App & browser control → Smart App Control settings.
2. Install Python 3.13 64-bit from python.org with "Add python.exe to PATH" ticked.
3. Build the package from this repository:
   ```bat
   py -3.13 packaging\make_source_package.py --out dist --no-wheels
   ```
   This writes `dist\Sankalan-2.0.0-Windows.zip`. `--no-wheels` makes the installer download the packages, so the
   PC needs internet while installing. Use `--download` instead to put the packages in the zip (`wheels\`) for a PC
   with no internet.
4. Unzip it and double-click **Install Sankalan.bat**. It copies the app to `%LOCALAPPDATA%\Programs\Sankalan`,
   creates its Python environment, installs the pinned packages, runs the self-test, and creates Start menu and
   desktop shortcuts named "Sankalan". If a Sankalan 1.x source install is there, it is replaced, and its Python
   environment is rebuilt.
5. Start Sankalan from the Start menu. Sample files for a first run are in the zip's `demo-data` folder
   (`Sales_Oct.xlsx`, `Sales_Nov.csv`). The test fixture pack F00–F21 used by `docs/specs/test-cases.md` is made
   with `python tests\fixtures\generate.py`.

**Update:** build a new zip and run its Install Sankalan.bat; the data folder is kept.
**Remove:** run **Uninstall Sankalan.bat** from the zip. It asks whether to delete your data too (No keeps it).

### Signed installer (needs the certificate)

On the Windows build PC with Python 3.13, NSIS 3.08+ and the Windows SDK's `signtool`:

```bat
set SANKALAN_SIGN_THUMBPRINT=<certificate thumbprint>
set SANKALAN_TIMESTAMP_URL=<the CA's timestamp server>
packaging\build_windows.bat
```

It runs every test, builds `Sankalan.exe` as a folder with PyInstaller, signs every unsigned `.exe`/`.dll`/`.pyd`
(`packaging\sign_files.ps1`), self-tests the built app, and writes the signed `dist\Sankalan-Setup-2.0.0.exe`. The
installer and the uninstaller it adds are signed as well. Signing needs internet for the timestamp; the app itself
never does. Without a certificate the build still runs but is unsigned, so Smart App Control blocks it.

The installer is per user with no admin rights, and adds Start menu and desktop shortcuts. Running a newer installer
updates in place and keeps the data. Uninstall (Settings → Apps → Sankalan) asks whether to delete the data folder:
No (the default) keeps it; Yes deletes the data folder, settings and logs.

### Self-test

`python -m sankalan --self-test` (or `Sankalan.exe --self-test --report selftest.json`) runs a small run end to end
in a temporary folder and never touches your data. It checks that DuckDB and python-calamine load, that the
database is locked offline, the reader workers, validation, an override, outputs, the totals check, commit and CSV
export, the catalogue backup on start, the window, and on a packaged build the file signatures. Exit code 0 means
every check passed.

## Development

```bat
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-lock.txt -r requirements-dev.txt
python -m sankalan                         # start the app
python -m sankalan --self-test             # built-in end-to-end check
set QT_QPA_PLATFORM=offscreen
python -m pytest tests -q                  # full suite, about 3 minutes
set SANKALAN_BUILD_TESTS=1                 # optional: also build the exe and installer (about 2 more minutes)
```

`requirements-lock.txt` pins the runtime packages: PySide6-Essentials/shiboken6, duckdb, python-calamine. No other
compiled package may load at run time; `tests/security` checks this. `requirements-dev.txt` holds test and build
tools only.

| Tests | Cover |
| --- | --- |
| `tests/unit` | Formats, value rules, paths, client/template management, the fixture pack |
| `tests/engine` | Storage, catalogue, commit and crash recovery, ingestion, conversion, rules, query layer, export, the TPL-A run sequence with the test sheet's figures |
| `tests/gui` | Every screen and dialog, driven off-screen |
| `tests/security` | No network code, DuckDB extensions never loaded, allowed compiled packages only |
| `tests/packaging` | Layout, self-test, uninstall data removal, build scripts, installer, run-from-source package |

Project notes for contributors are in `CLAUDE.md`. Specifications are in `docs/specs/`, the build plan in
`docs/IMPLEMENTATION_PLAN.md`, and progress in `docs/PROGRESS.md`.

## Layout

```
sankalan/
  __main__.py   entry: window, --self-test, --remove-data, --version
  app.py        one copy of the app, start-up and shutdown
  db/           DuckDB connection (offline, locked), catalogue, data folder, commit protocol
  ingest/       probe, Excel and CSV reading in worker processes, staging
  query/        all SQL: conversion, validation, split, totals, analysis, export
  run/          the run pipeline (Files → Commit)
  model/        templates, rules, runs, analysis definitions, exports
  validation/   rule scan
  ui/           theme, fonts, widgets, screens, dialogs
  selftest.py   --self-test
  uninstall.py  --remove-data (used by the uninstallers)
packaging/
  sankalan.spec, build_windows.bat, sign_files.ps1, sign_one.bat, installer.nsi, version.py, make_icon.py
  source_install/, make_source_package.py   run-from-source package
legacy/         Sankalan 1.x code, kept for reference only (never imported or shipped)
tests/
docs/
```

## Known limits

- Inputs are .xlsx, .xlsm and .csv. Password-protected and .xls files are refused with a message.
- Exports are CSV only.
- The performance targets (10M rows per run, about 120M per template per year) are measured on the 16 GB release
  test laptop before release.
