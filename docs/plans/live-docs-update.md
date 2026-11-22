# Instructions: bring the live claude.ai docs in step with the repository (after A2-6)

Written 22-11-2026 at the end of phase A2-6. For a Claude session (or a person) updating the **live** docs on
claude.ai. The repository copies in `docs/specs/` were updated in A2-6 and are the reference for what changed; the
live docs were not touched.

## Ground rules

1. **Merge, never overwrite.** The live docs are the source of truth and may hold text the repository snapshots
   don't (the snapshots date from 16-11-2026 to 21-11-2026). Read each live doc first, then apply only the changes
   listed below. Never replace a live doc with a repository file wholesale.
2. **Read before writing.** Open each doc with the tool for its kind (a Claude Docs doc with the docs tools, an HTML
   artifact with the Artifact tool's `read`), never by web fetch.
3. **One doc at a time, with approval.** For each doc: list the edits you will make (section, old wording → new),
   show the list to the user, wait for their yes, apply, then report what changed. Don't publish a new artifact in
   place of an existing one; update it at its own link.
4. **Where the live doc and the repository disagree** in a way this file doesn't cover, stop and ask the user; don't
   choose.
5. **House style:** plain, exact wording; numbers `9,812,345`; dates `DD-MM-YYYY`; no publisher or company names
   added anywhere; dated notes such as "**Changed** 22-11-2026 (A2)" as the docs already use.
6. Don't change the repository in this task except, at the end, a short entry in `docs/PROGRESS.md` saying which live
   docs were updated and when (commit on `Feature-Updates` only if the user asks).

## Docs and their links

| Live doc | Link | Repository copy (reference) |
| --- | --- | --- |
| Feature Spec v2.0 | https://claude.ai/artifact/NGA281HjAfaYXVHNwNCqh8 | `docs/specs/feature-spec-v2.0.md` |
| Technical Spec v1.0 | https://claude.ai/artifact/1goYPZmA7FNhrLA9Zu7Szc | `docs/specs/technical-spec-v1.0.md` |
| Test Cases (main sheet) | https://claude.ai/artifact/GzEbdCbadKjdHdG9oTXEuF | `docs/specs/test-cases.md` |
| Feature Spec A2 | https://claude.ai/artifact/EHyi3RebGVD9WykraDCA43 | `docs/specs/feature-spec-a2.md` |
| Test Cases A2 | https://claude.ai/artifact/KUp93csxqw9abamkgm3JpQ | (merged into `docs/specs/test-cases.md`) |
| Technical Spec A2 | Not recorded in the repository: ask the user for the link | `docs/specs/technical-spec-a2.md` |

To see exactly what changed in a repository copy: `git diff bdbb1e1 -- docs/specs/<file>` (`bdbb1e1` is the last
commit before A2-6).

## 1. Feature Spec v2.0

Apply Feature Spec A2 §12.1 with the corrections in Technical Spec A2 §15.1, as the repository copy now has them
(`git diff bdbb1e1 -- docs/specs/feature-spec-v2.0.md`):

- Header note: A2 folded in 22-11-2026, Feature Spec A2 holds the detail.
- Changed in place with dated notes: UX-3, UX-8, UX-10, F2, IN-3, IN-5, IN-11, IN-15, MAP-10, DO-1, DO-3, DO-6,
  DO-7, the VAL-1…9 text-cell note, VAL-9, ISS-3, ANA-4, ANA-5, ANA-6 (replaced by MEA), ANA-7, ANA-9, the Analysis
  "Not included" note, EXP-1, EXP-3, EXP-4, EXP-7, EXP-13 (two drives), SEC-4 (spill files), Out of scope.
- New rows TPL-10, MAP-14, VR-9, RUN-15; new sections Choose sheets (SHT-1…10), Text in Number and Date columns
  (TXT-1…14), Templates without checks (NCK-1…14), Measures (MEA-1…11), Rows view (ROW-1…14), Export in parts
  (EXP-8…14); PERF-7…14 under Performance targets.
- **Decisions:** the live doc's 21-11-2026 rows **D38 to D41 become D61 to D64** (Feature Spec A2 §12.1). The
  repository's D38 (.xls / .xlsb, 20-11-2026) becomes **D81** (Technical Spec A2 T67); if the live doc has that row,
  renumber it and IN-3's note; if not, add it. Then add D38…D60 and D65…D80 from Feature Spec A2 §11 (P8 confirmed,
  T42). D34 gets "**Changed** 20-11-2026 by D81: .xlsb and .xls are read too".
- Items the repository copy lacked and added as new rows (TPL-10, MAP-14, VR-9, RUN-15; UX-3 "skipped", UX-8 "four
  steps"): if the live doc already has them, **edit** them to the same meaning instead of adding duplicates.
- **Decisions of 22-11-2026** (also in the repository copy):
  - VAL-9: a row is skipped only when **every** key column is blank; blank key parts count as equal.
  - EXP-13: the destination message says "including working space" only when the temp folder is on the same drive.

## 2. Technical Spec v1.0

Apply Feature Spec A2 §12.2 and Technical Spec A2 §15.2, as the repository copy has them
(`git diff bdbb1e1 -- docs/specs/technical-spec-v1.0.md`):

- Header note; Decisions: T23 changed, T32…T56 and T67 as one-line rows pointing to Technical Spec A2 (the live doc
  may have T28–T31 from A1; if so, mark them superseded by the A2 rows rather than deleting them; ask if unsure).
- Architecture (Jobs detail line, DuckDB spill files), Storage (companions, sorted `data.parquet`, catalogue version
  2 and refusal of version 1, `conversion_failures.parquet` retired), Ingestion (sheet choice, Convert sort and
  companions), Validation (rule SQL for text cells; runs without checks), Outputs (`run_output.headers`, g1…/m1…),
  Query layer (new entry points, `_rows_<uuid>` with `_seq`), Exports (chunk → split → finish pipeline, part names,
  estimate and two-drive check), Packaging and security (no upgrade to version 2; spill-file exception), Tests (A2
  areas, PERF-7…14).
- VAL-9 rows and the "Feature spec changes" row: Unique skips a row only when every key column is blank (22-11-2026).
- "Feature spec changes": the A2 note pointing to Feature Spec A2 §12.1 / Technical Spec A2 §15.1.
- "Risks and open items": R2 (still unmeasured), R3 (**happened**: 187 s, accepted 22-11-2026), and new R7 (retired
  by T32) and R8…R15 with their current status.

## 3. Test Cases (main sheet)

The A2 cases now live in the main sheet (`docs/specs/test-cases.md`, section "Test cases A2 (Feature-Updates)"):

- Read me: snapshot note, phases P8 (A2 features) and P9 (A2 performance), reference templates TPL-R, TPL-N, TPL-S
  and their run sequences, the A2 items under "Behaviour the spec leaves open".
- 82 new cases: 71 `A2-<area>-<nn>` cases (one per AC), `A2-PERF-07…14`, `A2-EXP-13b`, `A2-CAT-01`, `A2-SHT-10`.
  Copy them from the repository file with their Status, Build, Tester, Run date and Notes fields empty (Not run).
- Existing cases updated (expected figures unchanged): RUNF-07, C3-13, C3-14, C3-18, C4-06, RUNV-12, A1-03, A1-04,
  A1-05, A1-12, EXP-08, PERF-01, PERF-02.
- Fixtures F-A2-01…11; Coverage rows for 2.4b, 4.1b, 4.1c, 4.3b, 4.5b, 6.4, 6.5, 6.6, 7.9 and ND-6, plus A2 IDs on
  existing screens.
- Where the live sheet holds status already recorded against a case, keep it.

## 4. Feature Spec A2

- §10 lead-in: the test cases are now in the main Test Cases sheet (link above); the A2 sheet is kept for history.
- AC-ROW-9a: "Changing a filter or a run tick greys the result…; changing the template asks first (ROW-5), then
  clears the settings and the result" (corrected 22-11-2026).
- EXP-13: add that "including working space" appears only when the temp folder is on the same drive (22-11-2026).
- R7 (§13.3): marked **Retired** by Technical Spec A2 T32.
- §9: add the measured results and the decision: PERF-5 and PERF-14 missed on the dev PC and accepted as measured
  (22-11-2026); PERF-12, PERF-1, PERF-2 not measured. Figures in `tools/perf/RESULTS-A2.md`.

## 5. Test Cases A2

Add a note at the top: "Merged into the main Test Cases sheet on 22-11-2026 (section Test cases A2); this sheet is
kept for history and is no longer updated." Don't delete it.

## 6. Technical Spec A2 (ask the user for the link)

- §5.4 Unique row: "A row is skipped only when every key part is null; blank parts match (`IS NOT DISTINCT FROM`).
  Confirmed 22-11-2026."
- §8.4 Messages: destination message's "including working space" only when the temp folder is on the same drive.
- §13: the measured results and the 22-11-2026 decision (as in 4); §17 R10, R13, R14: not measured (skipped).

## 7. Not in scope

The UI screens canvas (https://claude.ai/artifact/U522ApcDroz6pGW3VKMvaD) and the UX Context: Feature Spec A2 §12.3
lists screens to change and to draw. That is design work: ask the user before starting it.

## When done

Report to the user, per doc: updated or not, the edits made, anything skipped and why, and any disagreement found.
