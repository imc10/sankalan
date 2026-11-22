# A2-6 — Spec edits for approval

Proposed 22-11-2026 (plan A2-6 step 1). Sources: Feature Spec A2 §10 and §12, Technical Spec A2 §15 (its §15.1
corrections win). Only the repository copies in `docs/specs/` change; the live claude.ai docs are listed for you in
`docs/PROGRESS.md` and are not edited.

## 1. `docs/specs/test-cases.md`

| # | Edit |
| --- | --- |
| 1.1 | Title note: "snapshot 16-11-2026, A2 cases added 22-11-2026". Read me: new phase **P8 A2 features** (TPL-R, TPL-N and sheet-file cases, in the order ROW, MEA, EXP, SHT, TXT, NCK, BUG) and **P9 A2 performance** (A2-PERF cases on the perf machine); reference templates **TPL-R** and **TPL-N** (columns, rules, runs R-0001…R-0003, figures from Feature Spec A2 §10.1) |
| 1.2 | **71 new cases, one per AC** (Feature Spec A2 §10.2–10.8). IDs `A2-<area>-<nn>` after the AC: `A2-ROW-01`…`A2-ROW-14` (with `A2-ROW-09a/09b`, `11a/11b`, `12a/12b`, `A2-ROW-S1/S2`), `A2-MEA-01`…`11`, `A2-EXP-08a`…`14c`, `A2-SHT-01`…`09`, `A2-TXT-01`…`10`, `A2-NCK-01`…`10`, `A2-BUG-1a/1b/1c`. Same fields as today (Area, Priority, Screen, Spec, Type, Preconditions, Steps, Expected); the Spec field names the AC ID and the feature item |
| 1.3 | Four of them follow Tech spec §15.1, not Feature Spec A2: **A2-EXP-12** grand total is the **last row of the last part** (T38); **A2-MEA-11** a result with no measures has **no subtotal or grand total rows** (T39); **A2-NCK-02** Rows loaded = Rows read − blank rows, with a "Blank rows skipped: N" line (T45); **A2-SHT-01** Choose sheets… also on **.xlsb and .xls** (T46). Also A2-SHT-03 / 04: Sheet not found is **one error row per file** (T47); A2-EXP-14a: chunk files live in `%TEMP%\Sankalan`, parts are `.partial` until the finish step (T33) |
| 1.4 | **8 performance cases** `A2-PERF-07`…`A2-PERF-14` (Spec field PERF-7…PERF-14; settled A2-O2), targets as Feature Spec A2 §9 |
| 1.5 | **3 extra cases:** `A2-EXP-13b` short temp drive message (T34); `A2-CAT-01` a version-1 data folder is refused at start-up and left unchanged (T40); `A2-SHT-10` Choose sheets on the .xlsb and .xls copies of Central (T46) |
| 1.6 | **Fixtures F-A2-01…F-A2-11:** 01–03 TPL-R R-0001, R-0002, R-0003 sources (one .xlsx with two sheets + CSV files each); 04–05 TPL-N files 1 and 2; 06 Central .xlsx; 07 East; 08 West; 09 Central .xlsb; 10 Central .xls; 11 Central with Sales Nov renamed Sales November. Full and small sizes, as the plan's Test data tables |
| 1.7 | **Existing cases updated** (expected figures unchanged): **RUNF-07** Sheet not found is one row per file and offers Choose sheets… / Exclude file (SHT-6); **A1-03, A1-04, A1-05** measures set as column cards, default headers "Taxable Value · Sum", "Invoice No · Count", "Taxable Value · Average" etc., A1-04's rename done with ✎ (MEA-7, MEA-8); **A1-12** the ~1,000,000-row result export is 2 parts (EXP-8); **EXP-08** the 10M export is 10 parts, Cancel leaves no part or `.partial`, banner "Exported N rows to 10 files" (EXP-10, EXP-14); **C3-13/C3-14** Rules step has the Yes / No bar, Yes selected (NCK-2); **RUNV-12** names the step "Validate" (unchanged) and notes Load for templates without checks; **PERF-01/PERF-02** note that the load now includes the Convert sort and text companions (T32) |
| 1.8 | **Coverage table:** rows for the A2 screens 2.4b, 4.1b, 4.1c, 4.3b, 4.5b, 6.4, 6.5, 6.6, 7.9 (marked "not drawn in the repo canvas"), and the A2 case IDs added to existing screens 2.4, 3.1–3.4, 4.1, 4.1a, 4.5, 5.1, 6.2, 7.4, 7.5 |

## 2. `docs/specs/feature-spec-v2.0.md` (Feature Spec A2 §12.1, with Tech spec §15.1's corrections)

| # | Edit |
| --- | --- |
| 2.1 | Header note: "A2 (Feature-Updates) folded in 22-11-2026; Feature Spec A2 holds the detail" |
| 2.2 | The 26 rows of §12.1 applied in place: Analysis note and Out of scope (raw-row grid removed; drill-down wording; D79 note); UX-3, UX-8, UX-10; F2; TPL-10; IN-5, IN-11, IN-15; MAP-10, MAP-14; VR-9; RUN-15; VAL-1…9 (text cells as TXT-13); ANA-4, ANA-5, ANA-6 (replaced by MEA-1…11), ANA-7; DO-1, DO-3, DO-6; DO-7, ANA-9, ISS-3 (split over 1,000,000); EXP-1, EXP-3, EXP-4, EXP-7; SEC-4 (BUG-1 wording) |
| 2.3 | New sections (short, with a pointer to Feature Spec A2 for detail): **Rows view** ROW-1…14, **Measures** MEA-1…11, **Export in parts** EXP-8…14, **Choose sheets** SHT-1…10, **Text in Number and Date columns** TXT-1…14, **Templates without checks** NCK-1…14 |
| 2.4 | §15.1 corrections written in, not Feature Spec A2's text: EXP-12 grand total last (T38); MEA-11 no totals without measures (T39); NCK-4/8/9 blank rows line (T45); SHT-2 on .xlsb and .xls (T46); SHT-6 one row per file (T47); TXT-6/7 also in default outputs (T55); EXP-13 working space on the temp drive (T34) |
| 2.5 | Performance targets: add PERF-7…14 |
| 2.6 | Decisions: the repository's D38 (.xls / .xlsb) becomes **D81** (T67; IN-3's "Changed" note too); add D38…D80 from Feature Spec A2 §11 (with P8 / OA-5 closed); Open items unchanged |

## 3. `docs/specs/technical-spec-v1.0.md` (Feature Spec A2 §12.2 + Tech spec A2 §15.2)

| # | Edit |
| --- | --- |
| 3.1 | Header note as 2.1, pointing to Technical Spec A2 |
| 3.2 | Decisions: add T32…T56 and T67 as one-line rows pointing to Technical Spec A2 (T28/T29 extended to Date columns, Is not a date, "(Not a date)", Count distinct rules; T30 Load step) |
| 3.3 | Storage: text companions on Number and Date columns; `data.parquet` sorted by `_src_file, _src_row`; catalogue version 2 (new columns), version-1 refused; `conversion_failures.parquet` retired |
| 3.4 | Ingestion 1 and 2: sheet list for all four Excel kinds and the per-file choice; Ingestion 4 Convert: sort + companions, no failures file |
| 3.5 | Validation: rule SQL for text cells (TXT-13). Outputs: internal names g1…/m1…, headers from `run_output.headers` |
| 3.6 | Query layer: new entry points (`count_rows`, `fetch_rows`, `rows_page`, `text_counts`, …) and the `_rows_<uuid>` table with `_seq` (Tech spec §15.1 replaces the Feature Spec's `rows_view`); definition → SQL as Feature Spec A2 8.8; saved analyses JSON version 2 |
| 3.7 | Exports: the chunk → split → finish pipeline, part names, size estimate and free-space checks (T33–T36) replace the single `.part` flow |
| 3.8 | Architecture → Jobs: the progress detail line. T23: the Rows card counts every row. DuckDB settings / SEC-4 row: the spill-file exception (BUG-1); the no-leftovers test allows the open connection's spill files |
| 3.9 | Tests and release acceptance: the A2 test areas (Tech spec A2 §14.2) and PERF-7…14 in the performance suite |

## 4. Other

| # | Edit |
| --- | --- |
| 4.1 | `docs/PROGRESS.md`: rename D38 → D81 in Decisions (already done in A2-1's table wording; checked) and list what the live docs need |
| 4.2 | Feature Spec A1 / Technical Spec A1: already marked superseded (no change) |
