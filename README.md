<<<<<<< HEAD
# Sankalan

Offline Windows desktop app that merges many Excel/CSV files with the same or similar columns into one
validated Excel or CSV file for reporting. Built for accounting executives working across clients.
No internet, no telemetry, no LLM.

Version 1.0.0 · Python 3.13 · PySide6 (Qt) · Windows 10/11

## What it does

1. **Templates** – one saved setup per client and task (JSON file), rerun every month.
2. **Add files** – folder or files (.xlsx, .xlsm, .xls, .csv, .txt); finds the header row, skips
   hidden rows/sheets, total rows, blank rows and Excel lock files; opens password-protected files.
3. **Map columns** – matches headers across files, learns aliases ("GST No" → GSTIN), converts each
   column to Text, Number (Indian grouping, ₹, (negatives)) or Date.
4. **Validate** – not blank, GSTIN format / state code / check character, PAN, number and date
   ranges, allowed values, duplicates across files. Errors stop the run (with an override);
   every issue names the file, sheet and row; export the issue list to Excel.
5. **Output** – .xlsx or .csv with Source File/Sheet/Row columns, Indian number format, an Issues
   sheet, and a grand-totals check that re-reads the written file and compares it with the inputs.

## Install on a laptop (no certificate needed)

Works with Windows 11 Smart App Control on, needs no admin rights and no internet on the laptop.

1. Build the package once (needs internet to fetch the Windows packages):
   ```bat
   py -3.13 packaging\make_source_package.py --out dist --download
   ```
   This writes `dist\Sankalan-1.0.0-Windows.zip` with the app, the pinned Windows packages
   (`wheels\`), demo data and the installer scripts.
2. On each laptop: install Python 3.13 (64-bit, "Add python.exe to PATH" ticked).
3. Right-click the zip → Properties → tick **Unblock** → OK, then unzip it. (Smart App Control blocks
   double-clicking `.bat` files from a downloaded zip that hasn't been unblocked.)
4. Double-click **Install Sankalan.bat**. It installs to `%LOCALAPPDATA%\Programs\Sankalan`, runs a
   self-test and creates Start menu and desktop shortcuts. **Uninstall Sankalan.bat** removes it.

The app runs through Python's own signed `pythonw.exe`; the only compiled add-ons it loads are Qt
(PySide6) and `cryptography` (password-protected files). A test fails if any other appears.

## Signed installer (optional, needs a code-signing certificate)

On a Windows PC with Python 3.13 and NSIS (`makensis` on PATH):

```bat
set SANKALAN_PFX=C:\certs\codesign.pfx
set SANKALAN_PFX_PASSWORD=********
packaging\build_windows.bat
```

It runs all tests, builds `Sankalan.exe` with PyInstaller, signs every unsigned `.exe`/`.dll`/`.pyd`
(`packaging\sign_files.ps1`), self-tests the packaged app and writes a signed
`dist\Sankalan-Setup-1.0.0.exe` (per-user install). Without a certificate, Smart App Control blocks
the packaged app; use the package above instead.

## Development

```bat
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-lock.txt -r requirements-dev.txt
python -m sankalan                     # start the app
python -m sankalan --self-test         # built-in end-to-end check
set QT_QPA_PLATFORM=offscreen
python -m pytest tests -q              # all end-to-end tests (~3–5 minutes)
```

`requirements-lock.txt` pins the exact versions shipped to laptops; `requirements.txt` lists the
compatible ranges.

| Tests | Cover |
| --- | --- |
| `tests/test_e2e_engine.py` | Input, mapping, conversion, validation, output and templates on dummy files |
| `tests/test_e2e_gui.py` | The real window, driven off-screen: full run, override, new consolidation, password, drag-and-drop, editor, cancel, display scaling |
| `tests/test_e2e_security_perf.py` | No network code, run with network blocked, sources untouched, no temp files, log without cell values, allowed compiled add-ons, 500,000 rows under 60 s |
| `tests/test_e2e_source_install.py` | Laptop package: layout, installer steps, launcher self-test, bundled packages |
| `tests/test_e2e_packaging.py` | PyInstaller build, packaged-app self-test, installer compile, signing steps |

Dummy data comes from `sankalan/demo.py` (invented companies and GSTINs).

## Layout

```
sankalan/
  core/        readers, xlsx (reader), xlsx_writer, mapping, convert, validation,
               output, template, session  - no UI, standard library + small pure-Python libs
  ui/          PySide6 window: Templates, Add files, Map columns, Validate, Output; template editor
  demo.py      dummy data for tests and the self-test
  selftest.py  `--self-test`
packaging/
  source_install/          laptop installer: Install/Uninstall .bat, Sankalan.pyw, shortcuts.py, README.txt
  make_source_package.py   builds Sankalan-1.0.0-Windows.zip
  sankalan.spec, installer.nsi, build_windows.bat, sign_files.ps1, version_info.txt, sankalan.ico
tests/
```

Templates: `Documents\Sankalan\Templates` by default (changeable; can be a shared folder).
Log (technical only, no cell values): `%LOCALAPPDATA%\Sankalan\logs\sankalan.log`.

## Known limits

- `.xlsx` output holds at most 1,048,575 rows; larger runs must use CSV.
- Indian number grouping applies to zero and positive values; negatives use standard grouping, because
  Excel's conditional number formats don't reliably show the minus sign.
- GSTIN checks are offline: they can't confirm a GSTIN is registered or active.
- Hidden rows are detected in .xlsx/.xlsm/.xls; CSV has no hidden rows.
=======
# sankalan
>>>>>>> dfb416cb975f0d28fda9e51f24302e82ef8f4302
