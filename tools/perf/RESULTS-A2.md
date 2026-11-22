# A2 performance results

22-11-2026, phase A2-6 (plan `docs/plans/a2-implementation-plan.md`, step 4–5). Raw figures:
`tools/perf/_results/a2_perf.json`; tables from `python tools\perf\report_a2.py`.

**Status: two targets missed (PERF-5, PERF-14), accepted as measured by the user on 22-11-2026; nothing tuned.**

## Machine and settings

| Item | Value |
| --- | --- |
| Machine | Dev PC: 13th Gen Intel Core i5-1340P (12 cores, 16 threads), 13.7 GB usable RAM, Samsung NVMe SSD, Windows 11, on AC power (Balanced plan) |
| Pinned (plan A2-O3) | DuckDB `threads = 4`, `memory_limit = 8GB`; 3 reader workers |
| Method | Each target once untimed (warm-up), then 3 timed runs: median, min, max |
| Release laptop | Not run: the 16 GB, 4-core laptop run stays a manual release step (T4) |

## Data

Built by `tools/perf/build_a2_data.py` into `C:\SankalanPerf` (outside OneDrive).

| Set | Size |
| --- | --- |
| Template "Perf R" (TPL-R's 20 columns and rules) | 12 committed runs × 10,000,000 rows = 120,000,000 rows; 0.31 GB of Parquet per run (3.7 GB). Each run is a real `RunSession` on small seed files whose staged `data.parquet` is replaced by DuckDB-generated rows in the same schema and stored order, then committed by the real commit. Planted text: ~1,510 Taxable Value and ~306 Invoice Date cells per run; GSTIN has 1,000,000 distinct values |
| `TPLR_10M.csv` (PERF-14) | 10,000,000 rows in TPL-R's shape, 1.8 GB; 1,510 / 306 text values |
| P01 file 1, P02 (PERF-1, PERF-2) | Built (P02: 10 × 1,000,000-row .xlsx, 21 min) but not measured, see below |

## Results

| ID | Operation | Median | Min | Max | Target | Result |
| --- | --- | --- | --- | --- | --- | --- |
| PERF-7 | Rows view Run on 1 run (10M), 2 filters: count + first 100,000 | 1.3 s | 1.2 s | 1.4 s | ≤ 5 s | Met |
| PERF-8 | The same across 12 runs | 3.1 s | 3.1 s | 3.6 s | ≤ 30 s | Met |
| PERF-9 | Next page of 200 rows from the Rows table | 20 ms | 20 ms | 21 ms | ≤ 100 ms | Met |
| PERF-10 untick | Untick a column (grid redraw, offscreen, 100,000 rows) | 18 ms | 18 ms | 19 ms | ≤ 200 ms | Met |
| PERF-10 tick | Tick a column | 14 ms | 14 ms | 14 ms | ≤ 200 ms | Met |
| PERF-10 reorder | Move a column | 13 ms | 13 ms | 13 ms | ≤ 200 ms | Met |
| PERF-11 | Export 10M rows, 20 columns, UTF-8 with BOM, 10 parts (2.1 GB) | 31.6 s | 28.5 s | 41.7 s | ≤ 60 s | Met |
| PERF-12 | Rows view export of 120M rows, 120 parts | — | — | — | ≤ 12 min | **Not measured** (user's choice, 22-11-2026) |
| PERF-13 run data | Export dialog estimate, 10M-row run | 95 ms | 90 ms | 95 ms | ≤ 2 s | Met |
| PERF-13 rows view | Export dialog estimate, Rows view over 12 runs (its counts reused) | 142 ms | 139 ms | 145 ms | ≤ 2 s | Met |
| PERF-14 | Load step without checks: 10M-row CSV including text counts | **385.9 s** | 220.0 s | 404.9 s | ≤ 120 s | **Missed** |
| PERF-1 | Load 10M rows from CSV with validation and totals | — | — | — | ≤ 2 min | **Not measured** (stopped at the user's request) |
| PERF-2 | Load 10M rows from 10 .xlsx | — | — | — | ≤ 5 min | **Not measured** (stopped at the user's request) |
| PERF-3 | Analysis on 1 run (State › Branch › Invoice Date month; Sum, Count, Avg; subtotals) | 0.53 s | 0.52 s | 0.55 s | ≤ 3 s | Met |
| PERF-4 | The same across 12 runs | 8.0 s | 7.8 s | 9.0 s | ≤ 15 s | Met |
| PERF-5 | ~1M groups across 12 runs (State › GSTIN; Count distinct Invoice No; subtotals): 990,006 rows | **187.3 s** | 172.2 s | 220.7 s | ≤ 60 s | **Missed** |
| PERF-6 | Export that ~1M-row result | 0.78 s | 0.77 s | 0.81 s | ≤ 5 s | Met |

Other figures: PERF-7 matches 1,299,804 of 10,000,000 (count alone 0.09 s); PERF-8 matches 15,597,648 of
120,000,000 (count alone 1.3 s); PERF-14's Probe 2.9 s, text counts Taxable Value 1,510, Invoice Date 306.

**AC-EXP-9a (Excel check): verified.** `tools/perf/excel_open_check.ps1` opened both parts of a 1,999,698-row Rows
export (run 1, State is one of Maharashtra AND Taxable Value between 1,000 and 1,835) in Excel 16.0: part 1 has
1,000,001 rows with the header, part 2 999,699, both equal to the records Python's `csv` module counts (Narration
holds commas, quotes and line breaks). The plan's 2,100,000-row export gave 3 parts; this filter gave 2.

## The misses: what is known

| ID | What is known | Not yet known |
| --- | --- | --- |
| PERF-5 | First measurement ever (Phase 4 listed it under Not verified). Not caused by A2: GSTIN is a Text column (no companion), Count distinct on Text is unchanged. 120,000,000 input rows into ~1,000,000 groups plus subtotals, Count distinct of a value unique on every row, within 4 threads / 8 GB, so DuckDB spills. The three timed runs grew 172 → 187 → 221 s | Which part dominates: the Count distinct, the subtotal grouping sets, or spilling. Not split by stage |
| PERF-14 | Probe is 2.9 s; the rest is the Load Job (read with 3 workers, convert with companions, the T32 sort, text counts). Large spread: 405, 386, then 220 s. While a load ran, the process held about 6.7 GB, near the 8 GB limit, and used little CPU during the sort | Stage split of the Load Job; whether the spread comes from spilling near the memory limit. PERF-1 (the same load with checks) wasn't measured, and the pre-A2 comparison was skipped, so the cost of the A2 sort and companions (R13) isn't measured |

The data builder showed a related pattern: committing each 10M-row run in one long-lived process went from 37 s
(run 1) to 124 s (run 12).

## Skipped on 22-11-2026 (user's choice)

- PERF-12 (needs about 29 GB of output).
- The pre-A2 before/after comparison (R13, R14): `tools/perf/load_timing.py` is ready and was checked on small data
  against a worktree at `25f4d98`.
- PERF-1 and PERF-2: the run was stopped before them.
