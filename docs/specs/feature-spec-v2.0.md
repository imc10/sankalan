# Sankalan — Feature Spec (v2.0, final version)

Nov 16, 2026 · @Chetan Mundhada

## Purpose and scope

The final version keeps v1's merge-and-validate core. It adds a local dataset per template, default outputs saved with each run, analysis with CSV export, and validation rules that users set themselves. It stays fully offline on one Windows laptop. v1 (Feature Spec v1.0, 14-11-2026) was demonstrated to the customer and accepted; this spec replaces it.

| Area | v1 | Final version |
| --- | --- | --- |
| Core operation | Merge files into one output file | Merge and validate files, generate the template's default outputs, then commit each run to the template's local dataset |
| Storage | None; output file only | Local database: about 10M rows per run, about 120M rows per template per year |
| Validation | Fixed rule list including GSTIN and PAN checks | Users pick single-column rules from a predefined set, per template column |
| Per-run outputs | None | Default outputs defined in the template, generated on every run and saved with it |
| Analysis | None | Saved and ad-hoc analyses: AND filters, multi-level grouping, optional subtotals |
| Output files | .xlsx or .csv written on every run | Export on demand, CSV only |
| UI | One 5-step wizard; screens taller than a laptop screen | Clients → Templates → Runs, plus an Analysis area; every screen fits one laptop screen |
| Minimum machine | 8 GB RAM | 16 GB RAM with SSD |
| Connectivity | None | None (unchanged) |
| Chat with the data | — | Planned for V3; this version keeps the data ready for it |

## Users and environment

One accounting executive uses Sankalan on one 16 GB Windows laptop, with no network.

| ID | Item | Requirement |
| --- | --- | --- |
| ENV-1 | Users | Accounting executives, non-technical, working across many clients. No new user types |
| ENV-2 | Operating system | Windows 10 and 11, 64-bit |
| ENV-3 | Minimum machine | 16 GB RAM, SSD, 4 or more CPU cores |
| ENV-4 | Screen | Designed for 1366×768 at 100% scaling as the minimum; 1920×1080 at 125% and 150% must also work |
| ENV-5 | Use | Single laptop, single user. No shared datasets, network storage, logins or roles |
| ENV-6 | Connectivity | None: no internet, telemetry or LLM |

## App structure and flows

The app has two areas in a left rail: Clients (Clients → Client → Template → Run, one level per screen) and Analysis. Every screen is drawn at 1366×768 on the [Sankalan UI screens](https://claude.ai/artifact/U522ApcDroz6pGW3VKMvaD) design canvas and indexed in the project doc Sankalan\_UX\_Context.md (section 8).

### UI principles

| ID | Principle |
| --- | --- |
| UI-1 | Minimal, light only, with good spacing: deep teal accent (#0E6B6B), IBM Plex Sans bundled with the app (tabular figures for numbers), a Devanagari "सं" monogram, 40 px grid rows |
| UI-2 | Every screen fits one laptop screen (ENV-4). The window never scrolls; long grids scroll inside their own panel |
| UI-3 | No dark mode |
| UI-4 | App name "Sankalan" in the title bar and installer; no publisher name on any screen |
| UI-5 | Every long operation (load, validate, outputs, query, export, delete) shows progress and, where safe, Cancel inside the step, panel or dialog that started it; the window never freezes |
| UI-6 | Plain-language messages naming file, sheet and row, e.g. "Mar.xlsx, Sheet1, row 214: value is not a number" |
| UI-7 | Numbers shown with international grouping (9,812,345); dates as DD-MM-YYYY |
| UI-8 | Deleting a client, template or run lists exactly what will be deleted and needs an "I understand" tick |

### Screens

| ID | Screen | Contents |
| --- | --- | --- |
| UX-1 | Clients | Client list: templates, runs, rows stored, last load. New client, rename, delete. Storage footer with a low-disk warning |
| UX-2 | Client | Its templates: columns, default outputs, runs, rows stored, last load, modified. New template, New run on each row, rename, duplicate, delete |
| UX-3 | New template | Six-step wizard from one sample file: Sample file, Sheets, Columns, Rules, Default outputs, Review (TPL-3) |
| UX-4 | Template › Runs | Run ID, loaded on, files, rows, issues, status, comment. Open, export data, export issue list, delete |
| UX-5 | Template › Default outputs | Ordered list of default outputs and the builder, previewed on the latest committed run (DO) |
| UX-6 | Template › Columns & rules | Columns, types, aliases, rules; test the rules on the latest run |
| UX-7 | Template › Settings | Template name, sheets to read, CSV settings, export defaults |
| UX-8 | New run | Five steps: Files, Mapping, Validate, Outputs, Commit (F2) |
| UX-9 | Run | Tabs: Summary, Issues, Outputs, Source files. Export data, delete |
| UX-10 | Analysis | Saved analyses list, and the analysis builder with its result (ANA) |
| UX-11 | App settings | Data folder (Change… moves the data) and app version |

### Flows

- **F1 New template:** one sample file → sheets to read → columns and types → rules, tested on 100,000 sample rows → default outputs, previewed on the sample → review → Save, or Save and start the first run. Nothing is loaded into the dataset.
- **F2 Monthly run:** drawn below.
- **F3 Analyse:** Analysis area → open a saved analysis (settings locked, tick the runs) or start a new one (client, template, runs) → AND filters → group levels → measures → Run → result → export CSV → save.
- **F4 Manage runs:** Template › Runs → open a run → summary, issues, saved outputs and source files → export its data or outputs, or delete it.

&#91;embedded content: F2 monthly run · stage, validate, commit\]

With no errors the run goes straight to Outputs. With errors the user fixes the source files and re-checks, or continues with a reason, which marks the run Committed with override. A totals mismatch always blocks the commit.

## Templates

A template holds every setting for one client task and owns that task's dataset, so next month's run is: New run, add files, commit.

| ID | Feature | Detail |
| --- | --- | --- |
| TPL-1 | Contents | Sheets to read, CSV delimiter and encoding, columns (name, type, aliases, order, totals-check tick), validation rules, default outputs, export defaults (folder, file-name pattern, CSV delimiter and encoding) |
| TPL-2 | Organisation | Clients → Templates. A client has a name only (required, unique) and can be added, renamed or deleted; deleting a client deletes its templates, runs and saved analyses. A template stays with its client |
| TPL-3 | Create | New template wizard from one sample file (F1). It reads up to 100,000 rows for previews, finds the header row, detects each column's type with a % note, dry-runs the rules on the sample and previews the default outputs on it. Nothing is loaded. A template can also be created by duplicating another |
| TPL-4 | Manage | Rename, duplicate (copies columns, aliases, types, rules, settings and default outputs, not runs), delete. Deleting a template deletes its runs, rows and saved analyses after an "I understand" confirmation. Search by template name within a client |
| TPL-5 | Storage | Kept in the app's local data folder on the laptop, with the datasets. The v1 shared-network-folder option is dropped (ENV-5) |
| TPL-6 | Fast rerun | If every header in the new files matches, the mapping step is skipped; a new header opens the mapping grid with only that column highlighted (unchanged) |
| TPL-7 | Change record | Created date, last-modified date, and a version number that increases on every save. The version is stored with each run but not shown on screen |
| TPL-8 | Changes during a run | A change to mapping or rules made in a run applies to that run only, unless the user picks "Save to template" |
| TPL-9 | Column types fixed | A column's type is fixed once the template's first run is committed; data already loaded is never modified (MAP-12) |

## Input

A run reads the files the user adds. Each .xlsx sheet holds at most 1,048,576 rows, so a 10M-row run arrives as 10 or more Excel files, or as large CSV files. There is no run period.

| ID | Feature | Detail |
| --- | --- | --- |
| IN-1 | Add files | File picker (multi-select) or drag-and-drop. No folder import |
| IN-3 | Formats | .xlsx, .xlsm, .xlsb, .xls (Excel 97-2003), .csv. No .txt, .ods or Excel templates. **Changed** 20-11-2026: .xlsb and .xls added (D38) |
| IN-4 | CSV reading | Auto-detect encoding (UTF-8, UTF-8 with BOM, Windows-1252) and delimiter (comma, semicolon, tab, pipe); override in the template's settings |
| IN-5 | Sheets to read | Set in the template: by name (one or more), first visible sheet, or all visible sheets. Each file and sheet read is a row in the file list |
| IN-6 | Header row | Found automatically in each sheet; no manual override. A sheet whose header can't be found is an error for that file (IN-15) |
| IN-7 | Rows read | Every row with data below the header is read; there are no trailer rules |
| IN-8 | Blank rows | Drop rows where every cell is empty |
| IN-9 | Password-protected files | An error for that file (IN-15); the user excludes it or removes the password at source |
| IN-10 | Skipped files | Ignore Excel lock files (`~$...`) and the same file added twice; list them as skipped |
| IN-11 | File list | One row per file and sheet: file, sheet, size, header row found, rows, status (Ready, warning or error) |
| IN-13 | Hidden rows and sheets | Always skipped; listed in the file list and the run summary |
| IN-15 | Files in error | A file that can't be read (open in Excel, password-protected, sheet or header not found) blocks the run until it is excluded from the run, or fixed and re-checked |

## Column mapping

Mapping is as in v1, with additions for datasets that grow run by run (MAP-11 to MAP-13). Every decision is made before validation starts.

| ID | Feature | Detail |
| --- | --- | --- |
| MAP-1 | Target columns | From the template's columns |
| MAP-2 | Auto-match | Ignore case, spaces, dots, underscores and hyphens ("GST No." = "gst\_no") |
| MAP-3 | Aliases | Each template column lists other names it accepts |
| MAP-4 | Mapping grid | Rows = template columns, columns = each file and sheet, each cell a dropdown of that sheet's headers. Headers matched by alias are marked; undecided cells are highlighted |
| MAP-5 | Learn alias | A new header mapped by hand: "Map and save as alias" or "This run only" |
| MAP-6 | Missing column | A template column with no header in a file and sheet needs a decision: pick a header, or Leave as null for that sheet. If a default output uses the column, the decision warns that those rows show as (Null) there. There is no Required flag; use the Not blank rule (VAL-1) |
| MAP-7 | Extra source columns | A file column not in the template: Leave out, or Add as new column (name and type; the type is fixed once the run is committed). Earlier runs show null for it |
| MAP-8 | Template columns | Rename, reorder, add or remove in the template (Columns & rules) |
| MAP-9 | Leading zeros | Text columns keep values exactly as typed, e.g. 00123 |
| MAP-10 | Column types | Text, Number or Date. Number reads 1,23,456.00, ₹ 500 and (1,234) as −1,234. Date reads DD-MM-YYYY, DD/MM/YYYY and Excel dates; the template sets the date format for text dates |
| MAP-11 | Columns added or removed | A run may add or drop template columns; it proceeds after validation. Earlier runs show null for a new column; a removed column stays in earlier runs. A column used by a default output can't be removed until the output stops using it |
| MAP-12 | Type change | A column's type can't change once the template's first run is committed; data already loaded is never modified |
| MAP-13 | Decisions first | Every new header, missing column and extra column is decided before validation. Next with decisions left goes to the first undecided one |

## Runs and local storage

Each run is staged, validated, its default outputs generated, and then committed (appended) to its template's dataset together with those outputs. Nothing reaches the dataset until the commit, and the dataset grows by about 10M rows per run.

| ID | Feature | Detail |
| --- | --- | --- |
| RUN-1 | Dataset | One dataset per template, stored locally. Holds every committed run; sized for about 10M rows per run and about 120M rows per year |
| RUN-2 | Run record | Run ID, date and time, source file and sheet names with a content fingerprint, rows read, rows loaded, status (Committed, or Committed with override), issue counts, comment, saved default outputs, template version used |
| RUN-3 | Stage, validate, commit | Files are read into a holding area and validated; default outputs are generated on the staged rows (DO); the run is appended only on commit |
| RUN-4 | Errors block the run | Any Error-level failure stops the run at Validate. "Continue despite errors…" asks for a reason (required), which becomes the run's comment, and the run is saved as Committed with override |
| RUN-5 | All or nothing | A failed or cancelled load, output or commit leaves the dataset exactly as it was. Data and outputs commit together; the commit itself can't be cancelled |
| RUN-6 | Totals check | Grand total of each column ticked for the totals check in the template: all input files vs the rows to be loaded. A mismatch blocks the commit, with no override. No per-file totals |
| RUN-7 | Duplicate warning | Warn when a file has the same contents as one loaded in an earlier run, naming that run and its date: Remove file, or Load anyway |
| RUN-9 | Delete a run | Removes the run's rows, issue list and saved outputs after an "I understand" confirmation. Saved analyses that used the run no longer include its data |
| RUN-10 | Run detail | Tabs: Summary, Issues, Outputs, Source files. Export data, export issue list, delete |
| RUN-11 | Traceability | Source File, Source Sheet and Source Row are stored with every row and included, with Run ID, in run data exports |
| RUN-12 | Run summary | Files and sheets read, rows read, rows loaded, rows left out, errors and warnings, hidden rows and sheets skipped, totals check, comment, mapping decisions, rule changes made for this run only |
| RUN-13 | Comment | Plain text, up to 500 characters. Optional, but required and prefilled with the reason when errors were overridden. Can't be edited after commit |
| RUN-14 | No drafts | A run exists only once committed. Leaving the run wizard asks "Leave and discard this run?" and keeps nothing |

## Default outputs

Default outputs are analyses defined in the template that run on every new run's rows before the commit, and are saved with the run.

| ID | Feature | Detail |
| --- | --- | --- |
| DO-1 | Definition | The analysis builder (ANA-4 to ANA-7) plus a required name; several per template, in a set order. Defined in the New template wizard or the template's Default outputs tab |
| DO-2 | Scope | This run's rows only |
| DO-3 | Date filters | Relative only: latest month, quarter or year in this run. Fixed dates are allowed in ad-hoc analyses only |
| DO-4 | When they run | The run's Outputs step, after Validate, on the staged rows, with a status per output and Cancel. Skipped when the template has none |
| DO-5 | Failure | A failed or cancelled output shows Retry; the run can't be committed until every output is generated |
| DO-6 | Saved with the run | Results are committed with the data and never recalculated. Editing a default output affects future runs only |
| DO-7 | Viewing and export | On the Run's Outputs tab, with Show subtotals. Export one output, or all outputs as one CSV file each, only after commit |
| DO-8 | Preview | While editing: on the latest committed run. In the New template wizard: on the 100,000 sample rows |

## Validation

Users attach rules to each template column, picking from 9 predefined single-column rules. The rules run on every run of that template. v1's GSTIN and PAN rules are removed.

### Rule set

| ID | Rule | Settings |
| --- | --- | --- |
| VAL-1 | Not blank | — |
| VAL-2 | Is a number | — |
| VAL-3 | Number range | Min, max, or "not negative" |
| VAL-4 | Is a date | — |
| VAL-5 | Date range | Fixed from and to dates |
| VAL-6 | Allowed values | List of values, e.g. B2B / B2C / Export |
| VAL-7 | Text length | Exact, min or max characters |
| VAL-8 | Character pattern | A = letter, 9 = digit, other characters literal, e.g. AAAAA9999A |
| VAL-9 | Unique within the run | One or more key columns, e.g. GSTIN + Invoice No |

### Behaviour

| ID | Feature | Detail |
| --- | --- | --- |
| VR-1 | Where rules live | Per column in the template (Columns & rules); a column can have several rules |
| VR-2 | Severity | Each rule is Error or Warning |
| VR-3 | Errors | Any failure stops the run at Validate (RUN-4); no percentage threshold |
| VR-4 | Warnings | The commit goes ahead; warnings are stored with the run |
| VR-5 | Changing rules in a run | Add, remove or edit rules for this run; "Save to template" carries them forward (TPL-8) |
| VR-6 | Re-check | After source files are fixed, re-read and re-validate without leaving the run |
| VR-7 | Type rules | "Is a number" and "Is a date" are added automatically to Number and Date columns as Errors; they can be set to Warning but not removed |
| VR-8 | Testing rules | In the New template wizard, each rule shows its failure count on the sample rows and the first 20 failing rows. In Columns & rules, "Test rules on latest run" shows counts on the latest run without storing anything |

### Issues

| ID | Feature | Detail |
| --- | --- | --- |
| ISS-1 | Summary | Count of issues per rule and per file |
| ISS-2 | Detail grid | File, sheet, source row, column, value, rule, severity; filter and sort. Shows the first 10,000 issues per rule |
| ISS-3 | Export | The full issue list exports to .csv, to send back to the client |
| ISS-4 | Stored | The full issue list is kept with the run and viewable from Run detail (RUN-10) |

Not included: rules that compare two columns, rules that check against earlier runs, and regular expressions.

## Analysis

An analysis groups one template's data at one or more levels, with a grand total and optional subtotals. Analyses live in the Analysis area of the left rail and can be saved.

| ID | Feature | Detail |
| --- | --- | --- |
| ANA-1 | Saved analyses | Saved with a name, unique within its template. Reopening one locks its filters, groups, measures and subtotal setting: only the runs can be chosen, and none start ticked. Duplicate copies the settings into a new, editable, unsaved analysis. Rename, delete |
| ANA-2 | Ad-hoc analyses | New analysis: pick client, template and runs. Not kept when the user switches area; leaving with an unsaved result asks Save…, Leave without saving or Stay |
| ANA-3 | Choose runs | Tick runs in a list that shows Run ID and the run's file names, with Select all. Changing the template clears the settings after a confirmation |
| ANA-4 | Filters | Combined with AND only. Date columns: year, quarter or month is (calendar year), between dates, blank, not blank. Text columns: is one of (the 1,000 most frequent values with counts, plus a search across the whole column), contains, blank, not blank. Number columns: equals, between, blank, not blank |
| ANA-5 | Group levels | One or more columns in a chosen order; a date column is grouped by day, month, quarter or year (calendar year) |
| ANA-6 | Measures | Sum, Count, Count distinct, Average, Min, Max on chosen columns; each can be renamed |
| ANA-7 | Result | A flat table of aggregated values with the grand total pinned; subtotal rows when Show subtotals is on. Shows the first 100,000 rows, with a note when there are more; columns sort |
| ANA-8 | Running and Cancel | A Run button; progress and Cancel while running (UI-5). Changing a setting greys the result until it is run again |
| ANA-9 | Export | The full result, to CSV (EXP) |

Not included: charts, calculated columns, drill-down to rows, a raw-row browsing grid, and joins between datasets.

## Export

Files are written only when the user asks, and every export is a CSV file.

| ID | Feature | Detail |
| --- | --- | --- |
| EXP-1 | What can be exported | A run's data, a run's issue list, one default output or all of a run's outputs, an analysis result |
| EXP-2 | Format | CSV only; there is no .xlsx export |
| EXP-3 | CSV options | UTF-8 with BOM (default, opens correctly in Excel) or plain UTF-8; delimiter comma, semicolon, tab or pipe. Numbers without grouping; dates as DD-MM-YYYY |
| EXP-4 | File naming | Folder and name pattern from the template's export defaults, e.g. `{Client}_{Template}_{RunID}_{Output}`; both editable in the Export dialog. Confirm before overwriting an existing file |
| EXP-6 | Traceability columns | Run data exports include Source File, Source Sheet, Source Row and Run ID |
| EXP-7 | During and after | Progress with Cancel; a cancelled export deletes the part-written file. When done, an Open folder button |

## Offline, security and non-functional requirements

The app still makes no network connection. Client data is now kept on the laptop in the app's data folder, unencrypted, which replaces v1's promise that nothing is copied.

### Offline and data handling

| ID | Requirement |
| --- | --- |
| SEC-1 | No network code: no internet calls, auto-update, telemetry, crash upload, licence check, LLM, or database extension downloads |
| SEC-2 | Source files are opened read-only and never changed |
| SEC-3 | Loaded data, templates, saved analyses and issue lists are stored in the app's local data folder on the laptop. **Changed from v1.** No encryption; laptop disk protection (e.g. BitLocker) is IT's responsibility |
| SEC-4 | Temporary files live in the user's temp folder and are deleted when the operation ends |
| SEC-5 | The app's log records technical errors only (file name, error type), never cell values |
| SEC-6 | Updates arrive as a new installer or package, installed by hand or by IT |
| SEC-7 | IT can confirm offline behaviour with a Windows Firewall outbound block on the app; the app works unchanged |

### Non-functional

| ID | Requirement | Target |
| --- | --- | --- |
| NF-1 | Operating system | Windows 10 and 11, 64-bit |
| NF-2 | Install | Per-user, without admin rights |
| NF-3 | Responsiveness | The window never freezes; every long operation has progress and Cancel (UI-5) |
| NF-4 | Display | Readable at 100%, 125% and 150% Windows scaling (ENV-4) |
| NF-5 | Error messages | Plain language naming file, sheet and row (UI-6) |
| NF-6 | Branding | "Sankalan" (संकलन: compilation) in the title bar and installer; no publisher name in the app's screens |
| NF-7 | Distribution | Signed installer vs running from source is an open item |
| NF-8 | Technology | Python with PySide6 (Qt), unchanged. The proposed storage and query engine is DuckDB 2.0 LTS, to be confirmed in the technical spec |
| NF-9 | Disk space | Disk use per run to be measured in the benchmark |

### Performance targets

These are targets for a 16 GB laptop with SSD and about 20 columns per template. A 2–3 day benchmark on one of the customer's laptops confirms them before the technical spec is final.

| ID | Operation | Target |
| --- | --- | --- |
| PERF-1 | Load 10M rows from CSV, including validation and totals check | ≤ 2 min |
| PERF-2 | Load 10M rows from .xlsx (10 or more files) | Set from the benchmark |
| PERF-3 | Analysis on 1 run (10M rows), up to 3 levels, under 10,000 groups | ≤ 3 s |
| PERF-4 | Same analysis across 12 runs (about 120M rows) | ≤ 15 s |
| PERF-5 | Analysis with about 1M groups across 12 runs | ≤ 60 s, cancellable |
| PERF-6 | Export an analysis result of up to 1M rows to .csv | ≤ 5 s |

## Room for V3 (proposed, not yet discussed)

V3 adds chat with the data: a conversation agent plus an agent that turns questions into SQL. This version builds nothing for it, but V3-1, V3-2 and V3-4 below keep V3 from needing rework. They were not covered in the brainstorm and need your confirmation.

| ID | Proposal | Why |
| --- | --- | --- |
| V3-1 | Data stays queryable with standard SQL through one query layer, which the UI also uses | A text-to-SQL agent can then run the same queries as the Analysis screen |
| V3-2 | Saved analyses are stored as structured definitions (runs, filters, group levels, measures), not only as SQL | An agent can read, explain and reuse them |
| V3-3 | Deferred to V3 (decided 16-11-2026): each template column could carry an optional plain-language description | Gives the agent the meaning of each column |
| V3-4 | The query layer has a read-only mode | Chat can never change or delete data |

Because the app is offline (SEC-1), V3 will need an LLM that runs on the laptop. A model that size on a 16 GB machine is a constraint V3 must test.

## Out of scope

- Chat with the data (V3), and column descriptions for it (V3-3, deferred)
- Charts, calculated columns, drill-down to rows, a raw-row browsing grid
- Joining or matching two datasets, e.g. purchase register vs GSTR-2B
- Validation rules across columns or across runs; regular expressions; GSTIN and PAN rules
- Per-file totals (grand totals only, RUN-6)
- Run periods, excluding runs, and draft runs
- .txt, .ods and Excel template files, folder import, choosing the header row by hand, trailer rules, file preview, password prompts
- Excel (.xlsx) export
- Shared datasets, network folders, logins, roles, audit trail of who ran what
- Encryption of stored data
- Dark mode
- macOS and Linux builds

## Decisions

D8–D19 were settled in the feature brainstorm and D20–D37 in the UX discussion, both on 16-11-2026. v1's D1–D7 are kept unless marked changed.

| # | Date | Decision | Spec item |
| --- | --- | --- | --- |
| D37 | 16-11-2026 | Rule changes in a run apply to that run only unless saved to the template | TPL-8, VR-5 |
| D36 | 16-11-2026 | Template version kept internal; column descriptions deferred to V3 | TPL-7, V3-3 |
| D35 | 16-11-2026 | Mapping: no Required flag; a missing column is picked or left as null; an extra column is left out or added to the template; every decision is made before Validate | MAP-6, MAP-7, MAP-13 |
| D34 | 16-11-2026 | Input: files only, .xlsx, .xlsm and .csv; header found automatically with no override; no trailer rules; several sheets per file; password-protected files are errors; a file in error can be excluded from the run | IN |
| D33 | 16-11-2026 | Saved analyses lock their settings; only the runs change, none ticked; Duplicate to edit; the run list shows Run ID and file names | ANA-1, ANA-3 |
| D32 | 16-11-2026 | Analysis result is a flat table with optional subtotals; calendar-year date grouping; first 100,000 rows on screen; distinct-value lists for text filters | ANA-4, ANA-5, ANA-7 |
| D38 | 20-11-2026 | .xls (Excel 97-2003) and .xlsb (Excel Binary) files are read like .xlsx: hidden rows and sheets skipped, error cells read as text, password-protected files an error | IN-3 |
| D31 | 16-11-2026 | Every export is a CSV file | EXP-2 |
| D30 | 16-11-2026 | Deleting a template deletes its runs and saved analyses | TPL-4 |
| D29 | 16-11-2026 | A column's type is fixed after the first committed run; data already loaded is never modified | MAP-12, TPL-9 |
| D28 | 16-11-2026 | New templates are set up in a wizard from one sample file (100,000 preview rows); nothing is loaded | TPL-3, F1 |
| D27 | 16-11-2026 | Totals check on the columns ticked in the template; a mismatch blocks the commit, with no override | RUN-6 |
| D26 | 16-11-2026 | An override needs a reason, which becomes the run's comment; comments can't be edited after commit | RUN-4, RUN-13 |
| D25 | 16-11-2026 | Run steps on separate pages: Files, Mapping, Validate, Outputs, Commit | F2 |
| D24 | 16-11-2026 | Default outputs per template, run on the current run before commit and saved with it; a failed output blocks the commit; relative date filters only | DO |
| D23 | 16-11-2026 | No draft runs; leaving the run wizard discards the run | RUN-14 |
| D22 | 16-11-2026 | Runs can't be excluded; revised files replace a run by deleting it and loading again | RUN-9 |
| D21 | 16-11-2026 | No run period; dates come from the data's date columns | IN, RUN-2, VAL-5 |
| D20 | 16-11-2026 | Clients → Client → Template → Run, one level per screen, plus an Analysis area; a distinct Sankalan look (teal, IBM Plex Sans, 40 px rows) | UI-1, UX |
| D19 | 16-11-2026 | UI minimal and polished, every screen fits one laptop screen, no dark mode; screens designed in a separate UX discussion | UI-1 to UI-3 |
| D18 | 16-11-2026 | DuckDB 2.0 LTS proposed as the engine; targets PERF-1 to PERF-6, confirmed by a benchmark | NF-8, PERF |
| D17 | 16-11-2026 | Analysis: saved and ad hoc, AND filters, multi-level groups with subtotals, .csv export; no charts, calculated columns, drill-down or joins. **Changed:** subtotals optional (D32) | ANA |
| D16 | 16-11-2026 | Issue grid shows the first 10,000 per rule; full list exports to .csv and is kept with the run; any Error stops the commit | ISS-2 to ISS-4, VR-3 |
| D15 | 16-11-2026 | Validation rules set per template column from 9 predefined single-column rules; GSTIN and PAN rules removed | VAL, VR |
| D14 | 16-11-2026 | Minimum machine 16 GB RAM with SSD | ENV-3 |
| D13 | 16-11-2026 | Single laptop use; stored data not encrypted | ENV-5, SEC-3 |
| D12 | 16-11-2026 | Files written only on request; .csv by default. **Changed:** CSV only (D31) | EXP |
| D11 | 16-11-2026 | Runs are staged, validated, then committed; Errors block the commit with an override | RUN-3, RUN-4 |
| D10 | 16-11-2026 | Columns added or removed across runs: the run proceeds after validation | MAP-11 |
| D9 | 16-11-2026 | Every run gets a Run ID; warn on repeated file or period; runs can be excluded or deleted. **Changed:** no period and no exclude (D21, D22) | RUN-2, RUN-7, RUN-9 |
| D8 | 16-11-2026 | One local dataset per template; runs appended | RUN-1 |
| D7 | 14-11-2026 | No publisher name in the app | NF-6 |
| D6 | 14-11-2026 | Sign the installer. **Reopened:** signed installer vs running from source | NF-7 |
| D5 | 14-11-2026 | Hidden rows and sheets skipped and listed | IN-13 |
| D4 | 14-11-2026 | Errors stop the run, with an override. **Changed:** errors now block the commit (D11) | RUN-4 |
| D3 | 14-11-2026 | Grand totals check only; now input files vs loaded rows | RUN-6 |
| D2 | 14-11-2026 | Convert each column to Text, Number or Date | MAP-10 |
| D1 | 14-11-2026 | Python + PySide6 (Qt); pandas replaced by the storage engine for loading (D18) | NF-8 |

## Open items

4 items need a decision before the technical spec is final. O1–O8 and O13 were settled in the UX discussion (D20–D37).

| # | Question | Spec item |
| --- | --- | --- |
| O9 | Benchmark on a customer laptop to confirm PERF-1 to PERF-6, PERF-2's target, and disk use per run | PERF, NF-9 |
| O10 | Distribution: signed installer, or running from source until a code-signing certificate is available? | NF-7 |
| O11 | Confirm the remaining V3 proposals | V3-1, V3-2, V3-4 |
| O12 | Confirm the customer accepts client data being kept on the laptop, unencrypted | SEC-3 |
