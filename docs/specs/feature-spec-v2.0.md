# Sankalan — Feature Spec (v2.0, final version)

Nov 16, 2026 · @Chetan Mundhada

**A2 (Feature-Updates) folded in 22-11-2026; Feature Spec A2 (`docs/specs/feature-spec-a2.md`) holds the detail.** Items it changes carry a dated **Changed** 22-11-2026 (A2) note; its new items (ROW, MEA, EXP-8 to EXP-14, SHT, TXT, NCK, PERF-7 to PERF-14) are summarised in their sections below. Where Feature Spec A2 and Technical Spec A2 differ, the Technical Spec A2 wording (its section 15.1) is the one written here.

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
| UX-3 | New template | Six-step wizard from one sample file: Sample file, Sheets, Columns, Rules, Default outputs, Review (TPL-3). **Changed** 22-11-2026 (A2): the Rules step opens with the Check data before loading Yes / No bar; with No it shows the sample's values that aren't numbers or dates instead of the rule editor, and the wizard keeps its six steps (NCK-2, NCK-3) |
| UX-4 | Template › Runs | Run ID, loaded on, files, rows, issues, status, comment. Open, export data, export issue list, delete |
| UX-5 | Template › Default outputs | Ordered list of default outputs and the builder, previewed on the latest committed run (DO) |
| UX-6 | Template › Columns & rules | Columns, types, aliases, rules; test the rules on the latest run |
| UX-7 | Template › Settings | Template name, sheets to read, CSV settings, export defaults |
| UX-8 | New run | Five steps: Files, Mapping, Validate, Outputs, Commit (F2). **Changed** 22-11-2026 (A2): five steps for every template, Files, Mapping, Validate or Load, Outputs, Commit; Load takes Validate's place for a template without checks (NCK-6) |
| UX-9 | Run | Tabs: Summary, Issues, Outputs, Source files. Export data, delete |
| UX-10 | Analysis | Saved analyses list, and the analysis builder with its result (ANA). **Changed** 22-11-2026 (A2): a Summary \| Rows switch in New analysis adds the Rows view (ROW) |
| UX-11 | App settings | Data folder (Change… moves the data) and app version |

### Flows

- **F1 New template:** one sample file → sheets to read → columns and types → rules, tested on 100,000 sample rows → default outputs, previewed on the sample → review → Save, or Save and start the first run. Nothing is loaded into the dataset.
- **F2 Monthly run:** drawn below.
- **F3 Analyse:** Analysis area → open a saved analysis (settings locked, tick the runs) or start a new one (client, template, runs) → AND filters → group levels → measures → Run → result → export CSV → save.
- **F4 Manage runs:** Template › Runs → open a run → summary, issues, saved outputs and source files → export its data or outputs, or delete it.

&#91;embedded content: F2 monthly run · stage, validate, commit\]

With no errors the run goes straight to Outputs. With errors the user fixes the source files and re-checks, or continues with a reason, which marks the run Committed with override. A totals mismatch always blocks the commit.

**Changed** 22-11-2026 (A2): a template without checks goes Files → Mapping → Load → Outputs → Commit. Load reads and converts every file, runs no rules and stores no issues; file errors, mapping decisions and the totals check still apply (NCK-4 to NCK-8).

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
| TPL-10 | Check data before loading | **Added** 22-11-2026 (A2). Yes (default) or No, per template, for every run; not chosen per run. Set at the top of the wizard's Rules step, changed in Template › Settings from the next run (a new template version); runs already loaded don't change. Rules are kept, greyed "Not in use", while it is No. Duplicate copies it (NCK-1, NCK-2, NCK-11) |

## Input

A run reads the files the user adds. Each .xlsx sheet holds at most 1,048,576 rows, so a 10M-row run arrives as 10 or more Excel files, or as large CSV files. There is no run period.

| ID | Feature | Detail |
| --- | --- | --- |
| IN-1 | Add files | File picker (multi-select) or drag-and-drop. No folder import |
| IN-3 | Formats | .xlsx, .xlsm, .xlsb, .xls (Excel 97-2003), .csv. No .txt, .ods or Excel templates. **Changed** 20-11-2026: .xlsb and .xls added (D81, numbered D38 until 22-11-2026) |
| IN-4 | CSV reading | Auto-detect encoding (UTF-8, UTF-8 with BOM, Windows-1252) and delimiter (comma, semicolon, tab, pipe); override in the template's settings |
| IN-5 | Sheets to read | Set in the template: by name (one or more), first visible sheet, or all visible sheets. Each file and sheet read is a row in the file list. **Changed** 22-11-2026 (A2): in a run, the user can choose other sheets for one Excel file, for that file and that run only; the template's rule stays the default (SHT) |
| IN-6 | Header row | Found automatically in each sheet; no manual override. A sheet whose header can't be found is an error for that file (IN-15) |
| IN-7 | Rows read | Every row with data below the header is read; there are no trailer rules |
| IN-8 | Blank rows | Drop rows where every cell is empty |
| IN-9 | Password-protected files | An error for that file (IN-15); the user excludes it or removes the password at source |
| IN-10 | Skipped files | Ignore Excel lock files (`~$...`) and the same file added twice; list them as skipped |
| IN-11 | File list | One row per file and sheet: file, sheet, size, header row found, rows, status (Ready, warning or error). **Changed** 22-11-2026 (A2): Choose sheets… on the first row of each readable .xlsx, .xlsm, .xlsb and .xls file, next to ✕ (SHT-2) |
| IN-13 | Hidden rows and sheets | Always skipped; listed in the file list and the run summary |
| IN-15 | Files in error | A file that can't be read (open in Excel, password-protected, sheet or header not found) blocks the run until it is excluded from the run, or fixed and re-checked. **Changed** 22-11-2026 (A2): Sheet not found is one error row per file, naming its visible sheets, with Choose sheets… or Exclude file (SHT-6); Header not found is resolved only by Exclude file, or by fixing the file and Re-check (SHT-8) |

### Choose sheets for a file

**Added** 22-11-2026 (A2). In the Files step the user can choose which sheets of an Excel file to read, for that file and that run only, so a client's differently named sheets need no renaming in Excel. Detail, screens 4.1, 4.1a, 4.1b and 4.1c: Feature Spec A2 section 5; build: Technical Spec A2 section 7.

| ID | Feature | Detail |
| --- | --- | --- |
| SHT-1 | Default | Each file is read with the template's Sheets to read rule (IN-5) until the user chooses sheets for it |
| SHT-2 | Where it's offered | Choose sheets… on the first row of every .xlsx, .xlsm, .xlsb and .xls file, next to ✕, even when its sheets match the rule (D65, T46). Not offered for CSV files, files that can't be read (open in Excel, password-protected) or a file in Header not found (SHT-8) |
| SHT-3 | Scope | That file in this run only. The template isn't changed and there is no Save to template |
| SHT-4 | Dialog (4.1c) | "Choose sheets for \<file name>": every sheet in workbook order with a checkbox and its approximate row count; hidden sheets listed, disabled, "Hidden, skipped" (IN-13); a total line; Cancel and Read N sheets, disabled when nothing is ticked |
| SHT-5 | Ticks when it opens | First time: the sheets the template's rule selects (none when nothing matches). Later: the file's current choice |
| SHT-6 | Sheet not found (4.1b) | The rule finds none, or only some, of its named sheets. The file shows **one** error row (T47) naming its visible sheets, e.g. "Sheets found: Sales Nov, Returns Nov", with Choose sheets… and Exclude file. Footer: "Choose sheets for 1 file, or exclude it, to continue". Next stays disabled until each such file is resolved (IN-15) |
| SHT-7 | After Read N sheets | The file's rows become one row per chosen sheet, in workbook order, each with its header row found (IN-6), row count and status. Cancel leaves the file as it was |
| SHT-8 | Header not found | The file is in error as today (IN-15): Exclude file, or fix at source and Re-check (D68). Choose sheets… isn't offered; to choose again, remove the file with ✕ and add it again |
| SHT-9 | Re-check and removal | A choice is kept through Re-check. A chosen sheet that is gone or now hidden returns the file to Sheet not found, with the remaining chosen sheets ticked. Removing or excluding the file drops the choice |
| SHT-10 | Later steps | Chosen sheets go through Mapping like any sheet (MAP-4, TPL-6); Source Sheet stores the sheet's own name; the duplicate-file warning (RUN-7) is per file. No "Chosen" marker anywhere (D66) |

Applying one file's choice to other files in the run is deferred (D67).

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
| MAP-10 | Column types | Text, Number or Date. Number reads 1,23,456.00, ₹ 500 and (1,234) as −1,234. Date reads DD-MM-YYYY, DD/MM/YYYY and Excel dates; the template sets the date format for text dates. **Changed** 22-11-2026 (A2): a Number or Date cell that isn't blank and can't be read keeps its original text (MAP-14, TXT-1) |
| MAP-11 | Columns added or removed | A run may add or drop template columns; it proceeds after validation. Earlier runs show null for a new column; a removed column stays in earlier runs. A column used by a default output can't be removed until the output stops using it |
| MAP-12 | Type change | A column's type can't change once the template's first run is committed; data already loaded is never modified |
| MAP-13 | Decisions first | Every new header, missing column and extra column is decided before validation. Next with decisions left goes to the first undecided one |
| MAP-14 | Text in Number and Date columns | **Added** 22-11-2026 (A2). Number and Date columns keep the original text of cells that aren't numbers or dates, shown and exported in the same column as the values; maths and number and date filters use the values only. Applies to every template, with or without checks; Text columns are unchanged (TXT, D61, D69) |

### Text in Number and Date columns

**Added** 22-11-2026 (A2). A cell in a Number or Date column that isn't blank and can't be read, such as "NA", "Nil", "12,000/-" or "31-02-2026", keeps its text as typed. Detail and screens 6.5, 6.6: Feature Spec A2 section 6; storage and SQL: Technical Spec A2 section 5.

| ID | Area | Rule |
| --- | --- | --- |
| TXT-1 | What's kept | Number: a non-blank cell (T14) that MAP-10's number reading can't convert. Date: a non-blank cell that isn't an Excel date or a text date in the template's format. Excel error cells (#N/A, #REF!) count as text. Kept exactly as typed |
| TXT-2 | Display | One column everywhere data is shown: the number with grouping at the column's decimal places, or the date as DD-MM-YYYY, else the text as typed |
| TXT-3 | Alignment | Text in a Number column right-aligned; text in a Date column left-aligned |
| TXT-4 | Export | One column: the number at the column's decimal places without grouping, or the date as DD-MM-YYYY, else the text as typed, quoted where CSV needs it (EXP-3) |
| TXT-5 | Number filters | Equals and Between match numbers only; text never matches |
| TXT-6 | Is not a number | New Number filter: rows where the column holds text. Offered in Analysis, the Rows view and default outputs (T55) |
| TXT-7 | Date filters | Year, quarter or month is, and Between, match dates only. New Date filter Is not a date: rows where the column holds text. Offered in Analysis, the Rows view and default outputs (T55) |
| TXT-8 | Blank and Count | A cell with text is Not blank; Blank is an empty cell or only spaces. Count counts every non-blank cell, text included |
| TXT-9 | Other measures | Sum, Avg, Min and Max use numbers or dates only. Distinct on a Date column counts different dates, not text (D70). Number columns have no Distinct (MEA-3) |
| TXT-10 | Grouping | Text values form one group, "(Not a number)" or "(Not a date)" at any date grain; blank stays "(Null)" |
| TXT-11 | Sorting a result | Values first in the chosen direction, then "(Not a number)" or "(Not a date)", then "(Null)", in both directions (P8, confirmed by T42) |
| TXT-12 | Default output date filters | A relative date filter (DO-3) takes the latest date in the column, ignoring text; a row with text there is outside every relative and fixed period |
| TXT-13 | Rules | With checks: Is a number and Is a date fail on text, which goes to the issue list. Number range, Date range and Allowed values skip text like a blank, so each text cell gives one issue. Not blank passes. Unique within the run compares the value shown, so two "NA" cells are equal |
| TXT-14 | Totals check | Text counts as 0 in Input and is null in Loaded and Left out, so the check balances (T20). Only Number columns are totalled |

The New template wizard's type note states the sample's share kept as text, e.g. "2% aren't numbers and are kept as text" (TPL-3).

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
| RUN-15 | Text counts at Commit | **Added** 22-11-2026 (A2). For a run without checks, the Commit summary shows "Data checks: Not checked · template setting", "Rows left out: None", "Blank rows skipped: N" when non-zero (T45), and per column how many values aren't numbers ("…are left out of sums") or aren't dates ("…are left out of date filters and groups"). Information only; never blocks the commit (NCK-9) |

## Default outputs

Default outputs are analyses defined in the template that run on every new run's rows before the commit, and are saved with the run.

| ID | Feature | Detail |
| --- | --- | --- |
| DO-1 | Definition | The analysis builder (ANA-4 to ANA-7) plus a required name; several per template, in a set order. Defined in the New template wizard or the template's Default outputs tab. **Changed** 22-11-2026 (A2): measures are picked by column (MEA), and result columns are renamed from the preview header (MEA-8) |
| DO-2 | Scope | This run's rows only |
| DO-3 | Date filters | Relative only: latest month, quarter or year in this run. Fixed dates are allowed in ad-hoc analyses only. **Changed** 22-11-2026 (A2): the latest date ignores text kept in the column, and a row with text there is in no period (TXT-12); Is not a number and Is not a date are offered (T55) |
| DO-4 | When they run | The run's Outputs step, after Validate, on the staged rows, with a status per output and Cancel. Skipped when the template has none |
| DO-5 | Failure | A failed or cancelled output shows Retry; the run can't be committed until every output is generated |
| DO-6 | Saved with the run | Results are committed with the data and never recalculated. Editing a default output affects future runs only. **Changed** 22-11-2026 (A2): each committed run also keeps its outputs' column headers; later renames never change them (MEA-9) |
| DO-7 | Viewing and export | On the Run's Outputs tab, with Show subtotals. Export one output, or all outputs as one CSV file each, only after commit. **Changed** 22-11-2026 (A2): an output over 1,000,000 rows is exported in parts, each output on its own (EXP-8) |
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
| VAL-9 | Unique within the run | One or more key columns, e.g. GSTIN + Invoice No. **Changed** 22-11-2026: a row is skipped only when every key column is blank; blank parts count as equal |

**Changed** 22-11-2026 (A2): text kept in a Number or Date cell (TXT-1) fails only Is a number or Is a date, so it gives one issue; Number range, Date range and Allowed values skip it like a blank; Not blank passes; Unique within the run compares the value shown, so two "NA" cells are equal (TXT-13). A template without checks runs no rules (VR-9).

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
| VR-9 | Templates without checks | **Added** 22-11-2026 (A2). With Check data before loading = No (TPL-10), no rules run: Load takes Validate's place, every row read is loaded except blank rows, no issues are stored and nothing is left out. Test rules on latest run and run-only rule changes are not offered (NCK-4 to NCK-7, NCK-13) |

### Issues

| ID | Feature | Detail |
| --- | --- | --- |
| ISS-1 | Summary | Count of issues per rule and per file |
| ISS-2 | Detail grid | File, sheet, source row, column, value, rule, severity; filter and sort. Shows the first 10,000 issues per rule |
| ISS-3 | Export | The full issue list exports to .csv, to send back to the client. **Changed** 22-11-2026 (A2): over 1,000,000 issues it is exported in parts (EXP-8); not offered for a run without checks (NCK-12) |
| ISS-4 | Stored | The full issue list is kept with the run and viewable from Run detail (RUN-10) |

Not included: rules that compare two columns, rules that check against earlier runs, and regular expressions.

### Templates without checks

**Added** 22-11-2026 (A2). A template can load its data with no validation rules: Check data before loading = No (TPL-10). Detail and screens 2.4, 2.4b, 3.4, 4.3b, 4.5b: Feature Spec A2 section 7; build: Technical Spec A2 section 6.

| ID | Feature | Detail |
| --- | --- | --- |
| NCK-1 | Setting | Yes (default) or No, per template, not per run. A run uses the setting saved when it starts. Duplicate copies it |
| NCK-2 | Where it's set | A Yes / No bar at the top of the New template wizard's Rules step: "Applies to every run of this template. Can be changed later in Settings." The wizard keeps 6 steps |
| NCK-3 | Rules step with No (2.4b) | The rule editor is replaced by an explanation and the sample's count of values that aren't numbers per Number column and aren't dates per Date column; footer "No rules will be set for this template". Rules entered before No come back on Yes |
| NCK-4 | Rows loaded | No rules run, no issues are stored, nothing is left out and no left-out file is written; duplicates are loaded. Blank rows are still dropped (IN-8) and hidden rows and sheets skipped (IN-13). Rows read includes blank rows, and Rows loaded = Rows read − blank rows; Load, Commit and the Run summary show "Blank rows skipped: N" (T45) |
| NCK-5 | What still applies | File errors (IN-15), Choose sheets (SHT), mapping decisions (MAP-13), the duplicate-file warning (RUN-7), the totals check (RUN-6, Input = Loaded) and default outputs (DO) |
| NCK-6 | Run steps | Files · Mapping · Load · Outputs · Commit (UX-8). When every header matches (TPL-6), Next on Files goes to Load |
| NCK-7 | Load step: reading | One Job reads and converts every file and sheet, with progress and Cancel. Cancel or Back discards the staged rows and returns to Mapping, or to Files when Mapping was skipped |
| NCK-8 | Load step: result (4.3b) | Banner, e.g. "3 files read · 3,126,480 rows to load". Four stat cards: files and sheets read, rows read (with "Blank rows skipped: N" under it when non-zero, T45), rows to load, values that aren't numbers or dates. A table of Number and Date columns with such values; selecting one lists up to 1,000 values as typed, most frequent first, with count and first file, sheet and row. Re-check files; Next goes to Outputs |
| NCK-9 | Commit step (4.5b) | As RUN-15: "Data checks: Not checked · template setting", "Rows left out: None", "Blank rows skipped: N" (T45), the per-column lines for Number and Date columns, and under the totals check "Values that aren't numbers count as 0 on both sides". These counts never block the commit |
| NCK-10 | Comment | Optional, as for a run with no override (RUN-13) |
| NCK-11 | Changing the setting | In Template › Settings: Yes / No, "A change applies from the next run. Runs already loaded don't change." Saving makes a new template version (TPL-7). Yes → No keeps the rules, greyed in Columns & rules as "Not in use: this template loads without checks", not editable or testable. No → Yes puts them back in use; a template created with No starts with the automatic Is a number and Is a date rules only (VR-7) |
| NCK-12 | Runs without checks | The run stores that it was loaded without checks. Runs list: Issues shows "Not checked". Run detail: no Issues tab; Summary shows "Data checks: Not checked". Export issue list and Export left-out rows aren't offered |
| NCK-13 | Rule tools | Test rules on latest run (VR-8) and run-only rule changes (VR-5) aren't offered while the setting is No |
| NCK-14 | Analysis | Runs with and without checks can be ticked together in Analysis and the Rows view; nothing in a result shows how a run was loaded |

## Analysis

An analysis groups one template's data at one or more levels, with a grand total and optional subtotals. Analyses live in the Analysis area of the left rail and can be saved.

| ID | Feature | Detail |
| --- | --- | --- |
| ANA-1 | Saved analyses | Saved with a name, unique within its template. Reopening one locks its filters, groups, measures and subtotal setting: only the runs can be chosen, and none start ticked. Duplicate copies the settings into a new, editable, unsaved analysis. Rename, delete |
| ANA-2 | Ad-hoc analyses | New analysis: pick client, template and runs. Not kept when the user switches area; leaving with an unsaved result asks Save…, Leave without saving or Stay |
| ANA-3 | Choose runs | Tick runs in a list that shows Run ID and the run's file names, with Select all. Changing the template clears the settings after a confirmation |
| ANA-4 | Filters | Combined with AND only. Date columns: year, quarter or month is (calendar year), between dates, blank, not blank. Text columns: is one of (the 1,000 most frequent values with counts, plus a search across the whole column), contains, blank, not blank. Number columns: equals, between, blank, not blank. **Changed** 22-11-2026 (A2): Number columns add Is not a number and Date columns add Is not a date (rows holding text); Equals, Between and the date filters match values only, never text (TXT-5 to TXT-7) |
| ANA-5 | Group levels | One or more columns in a chosen order; a date column is grouped by day, month, quarter or year (calendar year). **Changed** 22-11-2026 (A2): text kept in a Number or Date column forms one group, "(Not a number)" or "(Not a date)"; blank stays "(Null)" (TXT-10) |
| ANA-6 | Measures | Sum, Count, Count distinct, Average, Min, Max on chosen columns; each can be renamed. **Replaced** 22-11-2026 (A2) by MEA-1 to MEA-11: measures are picked by column, with a Rows card to count rows (Measures, below) |
| ANA-7 | Result | A flat table of aggregated values with the grand total pinned; subtotal rows when Show subtotals is on. Shows the first 100,000 rows, with a note when there are more; columns sort. **Changed** 22-11-2026 (A2): measure column order and names follow MEA-6 to MEA-8; text groups sort after the values and before "(Null)" (TXT-11); a result with no measures has no subtotal or grand total rows (MEA-11) |
| ANA-8 | Running and Cancel | A Run button; progress and Cancel while running (UI-5). Changing a setting greys the result until it is run again |
| ANA-9 | Export | The full result, to CSV (EXP). **Changed** 22-11-2026 (A2): over 1,000,000 rows it is exported in parts, in on-screen order (EXP-8, EXP-12) |

Not included: charts, calculated columns, drill-down from a summary row to its rows, and joins between datasets. (**Changed** 22-11-2026 (A2): the raw-row browsing grid is now the Rows view, ROW.)

### Measures

**Added** 22-11-2026 (A2); replaces ANA-6. Measures are picked by column: add a column card, then tick its operations. Applies wherever the analysis builder is used: New analysis (6.2), Template › Default outputs (3.2), New template › Default outputs (2.5); a saved analysis (6.3) shows them read-only. Detail and layout: Feature Spec A2 section 3; build: Technical Spec A2 section 9.

| ID | Feature | Detail |
| --- | --- | --- |
| MEA-1 | Add a column | + Add column lists Rows first (MEA-10), then the template's columns not yet used as measures. Each column, and Rows, appears once |
| MEA-2 | Column card | Column name, type, ↑ ↓ to reorder, ✕ to remove, and a row of operation chips |
| MEA-3 | Operations by type | Number: Sum, Count, Avg, Min, Max (no Distinct, D70). Date: Count, Distinct, Min, Max. Text: Count, Distinct. Hover shows the full name (Count distinct, Average) |
| MEA-4 | Ticking | Chips toggle; a card with nothing ticked is allowed while editing, but Run, Save and Preview show "Tick at least one operation for \<column>, or remove it" and do nothing else |
| MEA-5 | Operation meaning | Sum and Avg on numbers only. Count = non-blank values, text included (TXT-8). Distinct on Text = different non-blank values; on Date = different dates, text not counted. Min and Max on numbers and dates only. Avg at the column's decimal places |
| MEA-6 | Result column order | After the group-level columns, grouped by card in card order; within a card always Sum, Count, Distinct, Avg, Min, Max |
| MEA-7 | Default names | "\<Column> · \<Operation>" with the full operation name, e.g. "Taxable Value · Sum", "Invoice No · Count distinct", "Rows · Count". A default name follows later renames of the template column; a custom name doesn't |
| MEA-8 | Rename | ✎ on each measure header of an unsaved result (6.2) and the Default outputs previews (3.2, 2.5): Enter saves, Esc cancels; trimmed, up to 100 characters; blank returns to the default; unique ignoring case, group headers included ("Another column is already called \<name>"). Renaming never re-runs or greys the result. Saved analyses have no ✎ |
| MEA-9 | Where names are used | Kept with the analysis or default output and used as CSV headers. A default output's names apply to runs committed after the change; each committed run keeps the headers it was committed with (DO-6). Unticking an operation drops its name |
| MEA-10 | Rows card | A fixed entry, Rows, with a single Count chip: counts every row that passes the filters, blank or not, in each group. Default name "Rows · Count"; renamable, movable and removable like any card |
| MEA-11 | No measures | A Summary or default output may have no measures when it has at least one group level (D76). It lists each group combination once, with **no subtotal or grand total rows**, and Show subtotals is disabled (T39). With neither a group level nor a measure: "Add a group level or a measure" |

### Rows view

**Added** 22-11-2026 (A2). A Summary \| Rows switch turns the analysis builder into a filtered row grid: the exact match count, the first 100,000 matching rows in stored order, and an export of every matching row in that order. Detail, layout (6.4), the Export rows dialog (7.9) and states: Feature Spec A2 section 2; build: Technical Spec A2 section 10.

| ID | Feature | Detail |
| --- | --- | --- |
| ROW-1 | Entry | A Summary \| Rows switch beside the title in New analysis (6.2); Summary is the default |
| ROW-2 | Switching | Keeps client, template, ticked runs and filters, and clears the result. Summary's group levels and measures come back on switching back |
| ROW-3 | Not saved | No Save; the header reads "Row views aren't saved". Leaving clears it with no prompt and cancels a running Rows Job |
| ROW-4 | Saved analyses | No switch on a saved analysis (6.3); saved analyses are always Summary |
| ROW-5 | Data | As ANA-2 and ANA-3: client, template, runs with Select all |
| ROW-6 | Filters | As ANA-4, combined with AND, including Is not a number and Is not a date |
| ROW-7 | Columns | Every template column that isn't removed, each with a tick and ↑ ↓; all ticked by default, "N of M ticked". At least one must be ticked to Run or export |
| ROW-8 | Source columns | Source File, Source Sheet, Source Row and Run ID are always exported after the ticked columns; on screen only with Show them on screen. Source Sheet is blank for CSV files |
| ROW-9 | Run | Run, with progress and Cancel. Changing client, template, runs or filters greys the result with "Settings changed: Run again" and disables Export; column ticks, order and Show them on screen redraw the grid at once with no Run |
| ROW-10 | Match count | The exact number of matching rows, runs, rows searched (rows loaded in the ticked runs) and time, e.g. "2,341,118 rows match · 3 runs · 7,499,937 rows searched · 0.9 s" |
| ROW-11 | Grid | Read-only, the first 100,000 matching rows in stored order; no sorting (D71). Footer "Showing the first 100,000 of N rows, in the order they were loaded. Export gets all of them.", or "Showing all N rows" |
| ROW-12 | Export and stored order | Export rows (.csv) writes every matching row in stored order: Run ID, then file and sheet in the run's load order, then Source Row; the grid shows the same order. Over 1,000,000 rows it is written in parts (EXP-8) |
| ROW-13 | Left-out rows | Rows left out on override (T18) are not shown or exported, as in Analysis |
| ROW-14 | Columns across runs | A column added after an older run is blank for that run's rows (MAP-11); removed columns aren't offered |

## Export

Files are written only when the user asks, and every export is a CSV file.

| ID | Feature | Detail |
| --- | --- | --- |
| EXP-1 | What can be exported | A run's data, a run's issue list, one default output or all of a run's outputs, an analysis result. **Changed** 22-11-2026 (A2): also a run's left-out rows (T19) and the Rows view (ROW-12); runs without checks offer no issue list or left-out rows (NCK-12) |
| EXP-2 | Format | CSV only; there is no .xlsx export |
| EXP-3 | CSV options | UTF-8 with BOM (default, opens correctly in Excel) or plain UTF-8; delimiter comma, semicolon, tab or pipe. Numbers without grouping; dates as DD-MM-YYYY. **Changed** 22-11-2026 (A2): a Number or Date cell holding text exports its text as typed (TXT-4) |
| EXP-4 | File naming | Folder and name pattern from the template's export defaults, e.g. `{Client}_{Template}_{RunID}_{Output}`; both editable in the Export dialog. Confirm before overwriting an existing file. **Changed** 22-11-2026 (A2): the confirmation lists every file, parts included, that would be replaced (EXP-10) |
| EXP-6 | Traceability columns | Run data exports include Source File, Source Sheet, Source Row and Run ID |
| EXP-7 | During and after | Progress with Cancel; a cancelled export deletes the part-written file. When done, an Open folder button. **Changed** 22-11-2026 (A2): Cancel deletes every part and working file; the banner names the file count when split (EXP-14) |

### Export in parts

**Added** 22-11-2026 (A2). Excel opens at most 1,048,576 rows and silently drops the rest, so every export over 1,000,000 data rows is written as numbered CSV files of up to 1,000,000 rows, each with its own header. Always on, with no option. Detail and dialog changes (7.4, 7.5, 7.9): Feature Spec A2 section 4; pipeline: Technical Spec A2 section 8.

| ID | Feature | Detail |
| --- | --- | --- |
| EXP-8 | When | Every export in EXP-1 is split when it has more than 1,000,000 data rows; exactly 1,000,000 is one file. "All of a run's outputs" splits each output on its own |
| EXP-9 | Part size | 1,000,000 data rows per part, the last holding the remainder (2,341,118 rows → 3 parts). Each part starts with the header row, and with the BOM when UTF-8 with BOM is chosen |
| EXP-10 | Names and folder | In the chosen folder, \<name>\_part01of03.csv; both numbers zero-padded to the same width, at least 2 digits (\_part001of120). The overwrite confirmation lists every file to be replaced; other files in the folder, including parts of an earlier export, are never touched |
| EXP-11 | Progress | In the dialog that started it: stage ("Reading rows", "Writing files"), rows written of N, "part K of M", elapsed time, Cancel |
| EXP-12 | Row order | Parts follow the export's own order, cut every 1,000,000 rows. Analysis results and default outputs are cut in on-screen order: the grand total is the **last row of the export, so of the last part when split** (T38); subtotal rows stay next to their group's rows, so a group can run across two parts |
| EXP-13 | Disk space | When the dialog opens it estimates the export's size and checks free space on two drives (T34): the destination needs the whole export plus a margin; the temp drive needs working space for the largest chunk plus a margin, also for a single file; on one drive the needs add up. When either is short, Export is disabled with a message naming the drive and both sizes, with its own wording for the temp drive ("…for working files…"); the destination message says "including working space" only when both are on one drive (22-11-2026). Checked again when the folder changes and when the export starts |
| EXP-14 | Cancel, failure, done | Cancel deletes every part and working file written so far; files the export would have replaced are left as they were. A failure (disk full, folder removed, a file to replace open in another program) does the same and says what happened (UI-6). When done: "Exported 2,341,118 rows to 3 files" with Open folder |

Not included: splitting by a column's values, choosing the part size, turning splitting off, zipping the parts, exporting only some parts.

## Offline, security and non-functional requirements

The app still makes no network connection. Client data is now kept on the laptop in the app's data folder, unencrypted, which replaces v1's promise that nothing is copied.

### Offline and data handling

| ID | Requirement |
| --- | --- |
| SEC-1 | No network code: no internet calls, auto-update, telemetry, crash upload, licence check, LLM, or database extension downloads |
| SEC-2 | Source files are opened read-only and never changed |
| SEC-3 | Loaded data, templates, saved analyses and issue lists are stored in the app's local data folder on the laptop. **Changed from v1.** No encryption; laptop disk protection (e.g. BitLocker) is IT's responsibility |
| SEC-4 | Temporary files live in the user's temp folder and are deleted when the operation ends, except the database engine's own spill files still in use, which it deletes itself; the folder is emptied completely at close and start-up. **Changed** 22-11-2026 (A2): the spill-file exception fixes BUG-1, where emptying the folder after an operation deleted spill files the open connection still used (T54) |
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
| PERF-7 | Rows view Run on 1 run (10M rows), 2 filters: count and first 100,000 rows | ≤ 5 s |
| PERF-8 | The same across 12 runs (about 120M rows) | ≤ 30 s |
| PERF-9 | Rows view grid scrolling: the next page of 200 rows | ≤ 100 ms |
| PERF-10 | Ticking, unticking or reordering a column in the Rows view | ≤ 200 ms |
| PERF-11 | Export 10M rows, 20 columns, UTF-8 with BOM, 10 parts | ≤ 60 s |
| PERF-12 | Rows view export of 120M rows, 120 parts | ≤ 12 min, cancellable |
| PERF-13 | Size and free-space estimate when an export dialog opens | ≤ 2 s |
| PERF-14 | Load step of a template without checks: 10M rows from CSV, including the text-value summary | ≤ 2 min, as PERF-1 |

**Added** 22-11-2026 (A2): PERF-7 to PERF-14 are provisional and, like the rest, measured by the release performance suite and reported, not blocking (D55, T4). PERF-1 and PERF-2 now include sorting the rows at Convert and writing the text kept in Number and Date columns; PERF-3 to PERF-5 are not affected (Feature Spec A2 section 9).

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
- Charts, calculated columns, drill-down from a summary row to its rows (**Changed** 22-11-2026 (A2): a raw-row browsing grid is now in scope as the Rows view, ROW)
- Joining or matching two datasets, e.g. purchase register vs GSTR-2B
- Validation rules across columns or across runs; regular expressions; GSTIN and PAN rules
- Per-file totals (grand totals only, RUN-6)
- Run periods, excluding runs, and draft runs
- .txt, .ods and Excel template files, folder import, choosing the header row by hand, trailer rules, file preview, password prompts
- Excel (.xlsx) export
- Shared datasets, network folders, logins, roles, audit trail of who ran what
- Encryption of stored data
- Dark mode
- macOS and Linux builds (macOS deferred until there is an Apple Developer Program membership, a Developer ID certificate and a Mac to build on, D79)

## Decisions

D8–D19 were settled in the feature brainstorm and D20–D37 in the UX discussion, both on 16-11-2026. v1's D1–D7 are kept unless marked changed. **Added** 22-11-2026 (A2), from Feature Spec A2 section 11: D38–D60 from Addendum A1 and its brainstorm (20-11-2026), D61–D64 from the UX discussion of 21-11-2026, and D65–D80 from the review of 21-11-2026. D81 (.xls and .xlsb input, 20-11-2026) was numbered D38 in this copy until A2 reused D38–D60 (T67).

| # | Date | Decision | Spec item |
| --- | --- | --- | --- |
| D81 | 20-11-2026 | .xls (Excel 97-2003) and .xlsb (Excel Binary) files are read like .xlsx: hidden rows and sheets skipped, error cells read as text, password-protected files an error. Numbered D38 until 22-11-2026 (T67) | IN-3 |
| D80 | 21-11-2026 | Feature Spec A2 replaces A1 and the UX changes note, and is merged into this spec and Technical Spec v1.0 after development | — |
| D79 | 21-11-2026 | macOS deferred until there is an Apple Developer Program membership, a Developer ID certificate and a Mac to build on | Out of scope |
| D78 | 21-11-2026 | A1's proposals P1 and P3 to P6 confirmed; P2 removed with sorting; P7 dropped with D77 | ROW-9, MEA-8, MEA-9, EXP-14 |
| D77 | 21-11-2026 | No upgrade steps: v2.0 is not built and no client data exists. **Applied** by T40: catalogue version 2, version-1 data folders refused | — |
| D76 | 21-11-2026 | A Summary may have no measures when it has at least one group level; it then has no subtotal or grand total rows (T39) | MEA-11 |
| D75 | 21-11-2026 | Load and Commit show values that aren't numbers and values that aren't dates | NCK-8, NCK-9, RUN-15 |
| D74 | 21-11-2026 | Runs without checks show "Not checked", have no Issues tab, and offer no issue or left-out export | NCK-12 |
| D73 | 21-11-2026 | The setting changes in Template › Settings, from the next run; rules are kept, not in use | NCK-11, TPL-10 |
| D72 | 21-11-2026 | Without checks, the Rules step stays with Yes / No at its top, and a run has five steps with Load in Validate's place | NCK-2, NCK-6, UX-3, UX-8 |
| D71 | 21-11-2026 | The Rows view can't be sorted; its grid shows stored order, as its export does. Sorting a Summary result is unchanged | ROW-11 |
| D70 | 21-11-2026 | No Distinct on Number columns; Distinct on a Date column counts dates only | MEA-3, MEA-5, TXT-9 |
| D69 | 21-11-2026 | Date columns keep the original text of cells that aren't dates, like Number columns; new filter Is not a date; one "(Not a date)" group | TXT, MAP-14 |
| D68 | 21-11-2026 | A file whose header row can't be found must be excluded, or fixed and re-checked; Choose sheets is not offered on it | SHT-8 |
| D67 | 21-11-2026 | Applying a sheet choice to other files in the run is deferred | SHT |
| D66 | 21-11-2026 | No "Chosen" marker on any screen | SHT-10 |
| D65 | 21-11-2026 | Choose sheets per file, for this run only, one dialog per file, offered on every readable Excel file (.xlsx, .xlsm, .xlsb, .xls, T46) even when its sheets match the rule | SHT-2, SHT-3 |
| D64 | 21-11-2026 | For a template without checks, Commit shows per column how many values aren't numbers (and, by D75, aren't dates); it never blocks | NCK-9, RUN-15 |
| D63 | 21-11-2026 | A template can load without checks: no rules, every row loaded (blank rows still dropped, T45); set per template, not per run | NCK-1, NCK-4, TPL-10, VR-9 |
| D62 | 21-11-2026 | Text in a Number column: maths and number filters use numbers only; Count includes text; text is Not blank; new filter Is not a number; one "(Not a number)" group; numbers sort before text | TXT-5 to TXT-11 |
| D61 | 21-11-2026 | Every Number column keeps the original text of cells that aren't numbers, shown and exported as one column with the numbers | TXT-1 to TXT-4, MAP-14 |
| P8 | 21-11-2026 | **Confirmed** (T42; closes Feature Spec A2's OA-5): when a result is sorted by a Number or Date group column, "(Not a number)" or "(Not a date)" follows the values and "(Null)" comes last, in both directions | TXT-11 |
| D60 | 20-11-2026 | Result names are unique, group-level headers included | MEA-8 |
| D59 | 20-11-2026 | No renaming on saved analyses | MEA-8 |
| D58 | 20-11-2026 | Committed runs keep their output headers after a rename | MEA-9, DO-6 |
| D57 | 20-11-2026 | A fixed Rows card counts rows | MEA-10 |
| D56 | 20-11-2026 | An export is blocked when free space is below its estimated size plus a margin (on two drives, T34) | EXP-13 |
| D55 | 20-11-2026 | Speed: the best that is feasible without complex code; targets are provisional and reported | PERF-7 to PERF-14 |
| D54 | 20-11-2026 | The Rows view leaves out left-out rows | ROW-13 |
| D53 | 20-11-2026 | The Rows view exports in stored order | ROW-12 |
| D52 | 20-11-2026 | Analysis results split like every other export, in on-screen order (grand total last, T38) | EXP-12 |
| D51 | 20-11-2026 | No splitting by a column's values | Export in parts |
| D50 | 20-11-2026 | Parts go in the chosen folder | EXP-10 |
| D49 | 20-11-2026 | Parts of 1,000,000 data rows each | EXP-9 |
| D48 | 20-11-2026 | Splitting applies to every export, through the shared export function | EXP-8 |
| D47 | 20-11-2026 | Exports over 1,000,000 data rows are always split, with no option | EXP-8 |
| D46 | 20-11-2026 | Result columns are renamed from the result header | MEA-8 |
| D45 | 20-11-2026 | Result measure columns grouped by column, in card order | MEA-6 |
| D44 | 20-11-2026 | All six operations kept. **Changed** by D70: no Distinct on Number columns | MEA-3 |
| D43 | 20-11-2026 | Measures are picked by column, then operations ticked | MEA-1 to MEA-4, ANA-6 |
| D42 | 20-11-2026 | Show the first 100,000 matching rows; export all | ROW-11, ROW-12 |
| D41 | 20-11-2026 | No row detail panel | Rows view |
| D40 | 20-11-2026 | Source File, Source Sheet, Source Row and Run ID are always exported; hidden on screen by default | ROW-8 |
| D39 | 20-11-2026 | Row views are never saved | ROW-3 |
| D38 | 20-11-2026 | A Rows view, as a Summary \| Rows switch in the analysis builder | ROW-1, ROW-2 |
| D37 | 16-11-2026 | Rule changes in a run apply to that run only unless saved to the template | TPL-8, VR-5 |
| D36 | 16-11-2026 | Template version kept internal; column descriptions deferred to V3 | TPL-7, V3-3 |
| D35 | 16-11-2026 | Mapping: no Required flag; a missing column is picked or left as null; an extra column is left out or added to the template; every decision is made before Validate | MAP-6, MAP-7, MAP-13 |
| D34 | 16-11-2026 | Input: files only, .xlsx, .xlsm and .csv; header found automatically with no override; no trailer rules; several sheets per file; password-protected files are errors; a file in error can be excluded from the run. **Changed** 20-11-2026 by D81: .xlsb and .xls are read too (IN-3) | IN |
| D33 | 16-11-2026 | Saved analyses lock their settings; only the runs change, none ticked; Duplicate to edit; the run list shows Run ID and file names | ANA-1, ANA-3 |
| D32 | 16-11-2026 | Analysis result is a flat table with optional subtotals; calendar-year date grouping; first 100,000 rows on screen; distinct-value lists for text filters | ANA-4, ANA-5, ANA-7 |
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

The proposals confirmed by D78 and T42, for reference: P1, column changes redraw the Rows grid with no Run; P3, result names trimmed, up to 100 characters, unique ignoring case, a clashing default name gets " (2)"; P4, each run stores its output headers at commit; P5, parts written as .partial and renamed at the end; P6, extract and split alternate per run; P8, as in the table.

## Open items

4 items need a decision before the technical spec is final. O1–O8 and O13 were settled in the UX discussion (D20–D37).

| # | Question | Spec item |
| --- | --- | --- |
| O9 | Benchmark on a customer laptop to confirm PERF-1 to PERF-6, PERF-2's target, and disk use per run | PERF, NF-9 |
| O10 | Distribution: signed installer, or running from source until a code-signing certificate is available? | NF-7 |
| O11 | Confirm the remaining V3 proposals | V3-1, V3-2, V3-4 |
| O12 | Confirm the customer accepts client data being kept on the laptop, unencrypted | SEC-3 |
