# Changelog

## 2.0.0 – not yet released (manual testing)

A new codebase built on the Feature Spec v2.0 and Technical Spec v1.0 (16-11-2026).

- Local dataset per template (DuckDB catalogue + Parquet per run); runs R-0001, R-0002, … committed whole or not
  at all; catalogue backed up at every start.
- Clients → Client → Template → Run screens and an Analyses area; every screen fits a 1366×768 laptop screen.
- New template wizard from a sample file; columns with Number decimals (0–6) and Date formats; nine user-set rules
  (Error or Warning).
- New run wizard: Files, Mapping (aliases), Validate (issues by file, sheet and row; override with a reason leaves
  rows with errors out), default outputs, totals check Input = Loaded + Left out, Commit.
- Analyses with filters, grouping, measures and subtotals across runs; saved analyses; CSV export of run data,
  issues, left-out rows, outputs and analyses.
- Signed per-user installer (PyInstaller + NSIS) built by `packaging\build_windows.bat`; uninstall asks whether to
  delete the data. Run-from-source package kept for development and manual testing until the certificate arrives.
- Input files: .xlsx, .xlsm, .xlsb (Excel Binary), .xls (Excel 97-2003) and .csv; hidden rows and sheets skipped
  and error cells read as text in every Excel format.
- Dropped from 1.x: .xlsx output, GSTIN/PAN checks, .txt and password-protected input, JSON templates.

## 1.0.0 – 2026-11-16

First release.

- Consolidation: folder/file input (.xlsx, .xlsm, .xls, .csv, .txt), header detection, hidden
  rows/sheets, total and blank rows, password-protected files, per-file sheet and header overrides.
- Column mapping with aliases learned per template; Text/Number/Date conversion.
- Validation: not blank, GSTIN format/state/check character, PAN, number and date ranges, allowed
  values, duplicates across files; errors stop the run with an override; issue export.
- Output: .xlsx/.csv, traceability columns, Indian number format, Issues sheet, grand-totals check.
- Saved templates per client and task (JSON), template editor.
- Smart App Control: standard-library .xlsx reader and writer; laptop package that runs on the
  signed Python runtime without a code-signing certificate; optional signed PyInstaller build.
