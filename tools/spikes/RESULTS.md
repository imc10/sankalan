# Phase 0 spike results (16-11-2026)

Measured on the development PC: Windows 11, 16 logical cores, SSD, Python 3.13, DuckDB 2.0.0, python-calamine 0.9.1,
PySide6 6.12.0, PyInstaller 6.22.3. This PC is much faster than the 16 GB / 4-core acceptance laptop, so read the
timings as early signals only; the performance suite (Phase 12) gives the real figures.

Scripts (rerun any time): `spike_duckdb.py`, `spike_calamine.py`, `spike_read_speed.py`, `spike_workers.py`
(`--build` for the PyInstaller check).

## Summary: what changes for later phases

| # | Finding | Impact | Phase |
| --- | --- | --- | --- |
| S1 | **Locking the DuckDB config does not stop an explicit `INSTALL`.** With autoinstall/autoload off, community extensions off and `lock_configuration = true`, `INSTALL httpfs` still downloaded a 52 MB extension from extensions.duckdb.org (deleted afterwards). Adding `enable_external_access = false` with `allowed_directories` = data folder + temp folder refuses `INSTALL`, `INSTALL … FROM core`, `LOAD` and `https://` reads, while reads and `COPY` inside the allowed folders still work | `db/connection.py` must set `enable_external_access=false` + `allowed_directories` before the lock (and `extension_directory` to an empty folder, `custom_extension_repository` to a missing local path as a second guard). A guard test now fails if any app source contains `INSTALL`/`LOAD` | 1 |
| S2 | With external access off, DuckDB can't `COPY` to a folder the user picks at export time | Export writes `<name>.part` inside an allowed folder (temp or `_staging`), then Python streams it to the destination (adding the BOM if needed) and renames. This is close to the planned BOM splice anyway. Cross-volume exports need the copy, not `os.replace` | 4 |
| S3 | **python-calamine 0.9.1 returns `''` for error cells** (`#N/A`, `#REF!`, `#DIV/0!`), the same as an empty cell; the file itself is correct (`t="e"`, `<v>#N/A</v>`) | The sheet-XML scan that finds hidden rows also collects error cells (`t="e"` → cell ref + text) and patches them into the staged text, so CONV-05 ("#N/A" kept for the issue list) works. One streaming pass does both | 2 |
| S4 | calamine does not report hidden rows (R5 confirmed): a hidden row comes back as an ordinary row | XML scan needed, as planned (T11) | 2 |
| S5 | DuckDB accepts exponent text: `TRY_CAST('1e3' AS DECIMAL(38,2))` = 1000.00. V1 `to_number` also accepts `1e3`, `12%`, a trailing minus and `Rs.`/`INR` | Decide in Phase 2 whether the SQL Number rule accepts these (Tech spec lists only ₹, spaces, grouping, brackets). Ask the user then | 2 |
| S6 | calamine gives Excel numbers as binary floats: `12345678901234567` → `1.234567890123457e+16` | Staged text form needs `format(Decimal(repr(f)), "f")` (no exponent) as in `spike_read_speed.canon` | 2 |

## DuckDB 2.0.0 (`spike_duckdb.py`)

- **T13 rounding: confirmed.** `CAST('<text>' AS DECIMAL(38,d))` rounds half away from zero for d = 0, 2, 6 and
  negative values: 2.345 → 2.35, −2.345 → −2.35, 2.5 → 3 (d=0), −2.5 → −3, 0.005 → 0.01, 123456.789 → 123457 (d=0),
  1.0000005 → 1.000001 (d=6). No explicit `round()` needed. `TRY_CAST('12abc')` and `TRY_CAST('')` give NULL.
  (DECIMAL(38,6) → DECIMAL(38,2) also rounds half away. Casting from DOUBLE gave 2.35 for 2.345 here, but convert
  from the staged text, never from DOUBLE.)
- **`interrupt()`:** a running aggregate over 500M rows stopped **1 ms** after `con.interrupt()` from another thread,
  raising `duckdb.InterruptException`; the connection stayed usable.
- **`COPY … TO` CSV:** 10M rows × 8 columns (654 MB, `DATEFORMAT '%d-%m-%Y'`) in **1.2–1.8 s**; the same table to
  Parquet in 0.9 s (126 MB).
- **`read_parquet([...], union_by_name=true)`:** an older run without a newer column returns NULL for it. Works.
- **Config lock:** after `lock_configuration = true`, every `SET` is refused (`InvalidInputException`). See S1 for the
  extension finding. `duckdb_extensions()` itself is refused once external access is off, so don't call it at runtime.
  Built-in (statically linked) extensions present: core_functions, icu, json, parquet.

## python-calamine 0.9.1 (`spike_calamine.py`)

- `sheets_metadata` gives every sheet with `visible` = `Visible` / `Hidden` / `VeryHidden`, in workbook order.
- Values: numbers as `float`, text exactly as typed (`'00123'`, `' A1 '`, `'   '`), booleans as `bool`,
  dates as `datetime.date`, date-times as `datetime.datetime` (CONV-05: drop the time).
- Formulas give the cached value (`=100*1.5` → 150.0).
- Error cells → `''` (S3). Hidden rows → returned as normal rows (S4).
- `iter_rows()` streams rows; `height`/`width` from the dimension record, usable for the approximate row count.
- An empty sheet gives `[]`.

## Reader workers (`spike_workers.py`)

- `multiprocessing` with the `spawn` context: 4 workers each reading a 20,000-row sheet with calamine: **1.2 s**
  total including process start-up.
- Cancel: a worker that checks the stop flag stopped in 0.02 s; one that ignored it was killed after **2.0 s**
  (`join(2)` then `kill()`), exit code −15.
- **PyInstaller one-folder exe** (22 s build, `--collect-binaries python_calamine`): the same results; with
  `multiprocessing.freeze_support()` first in `__main__`, the spawned children ran as workers and did not start a
  second app. T5 design confirmed.

## Read speed, one core (`spike_read_speed.py`)

| Case | Result | Early signal |
| --- | --- | --- |
| .xlsx, 1M rows × 8 columns (45 MB): calamine open + read + write staged text | 13.6 s (open 7.4 s) = **73,700 rows/s** | PERF-2 (10M rows from 10 files): ~0.8 min on 3 workers at this speed; P02 has 20 columns, so expect ~2–2.5× longer, and the laptop is slower. Still well inside 5 minutes here, so R2 looks manageable |
| Streaming sheet-XML scan (hidden rows + error cells) of the same file | 3.9 s | Adds ~30% per .xlsx file; can run in the same worker before/after the calamine read |
| CSV, 10M rows × 20 columns (1.6 GB): `csv` module read + blank check + write staged text | **64 s** = 156,000 rows/s | PERF-1 limit is 2 minutes for the whole load. R4 is real: on the laptop this stage alone may approach the limit. Phase 2 should measure on the laptop early and consider letting DuckDB read clean UTF-8 CSVs directly |
| DuckDB re-reading the 10M-row staged text (`read_csv`, all VARCHAR) | 0.9 s | Convert stage is cheap compared with reading |
