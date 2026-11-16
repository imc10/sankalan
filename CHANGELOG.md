# Changelog

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
