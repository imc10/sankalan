# Sankalan — Feature Spec A2: Feature-Updates

21-11-2026 · Chetan Mundhada · Live doc: https://claude.ai/artifact/EHyi3RebGVD9WykraDCA43 (this file is a copy; the live doc is the source of truth)

## 1. Purpose and scope

This spec defines the six features and one bug fix built on the Feature-Updates branch. It merges Feature Spec Addendum A1 (20-11-2026) with the UX changes agreed on 21-11-2026 and the decisions taken in the review of 21-11-2026. It replaces Feature Spec A1 and the UX changes note. Feature Spec v2.0 and Technical Spec v1.0 are not built yet and no client data has been loaded, so nothing here needs an upgrade step. This spec and its test cases file are merged into those specs once development is done (section 12).

| # | Feature | In one line | IDs |
| --- | --- | --- | --- |
| A | Rows view | A Rows mode in the analysis builder: pick client, template and runs, filter, choose columns, see the first 100,000 matching rows in stored order and export all of them | ROW-1 to ROW-14 |
| B | Measures by column | Add a column card, then tick the operations to apply to it; a fixed Rows card counts rows; rename result columns from the result header | MEA-1 to MEA-11 |
| C | Export in parts | Any export over 1,000,000 data rows is written as numbered CSV files of up to 1,000,000 rows, each with its own header | EXP-8 to EXP-14 |
| D | Choose sheets for a file | In a run, choose which sheets of an Excel file to read, for that file and that run only | SHT-1 to SHT-10 |
| E | Number and Date columns keep text | A cell in a Number or Date column that can't be read keeps its original text, shown and exported with the values | TXT-1 to TXT-14 |
| F | Template without checks | A template setting, Check data before loading: No loads every row with no rules and no Validate step | NCK-1 to NCK-14 |
| — | Bug fix: temp clean-up | Emptying the temp folder after a Job must not delete DuckDB spill files that the open connection still uses | BUG-1 |

**Why C is needed.** Excel opens at most 1,048,576 rows, header included, and silently drops the rest. A run holds about 10M rows, so a run's data, its issue list or a Rows export routinely goes past that. Parts of 1,000,000 data rows plus a header stay under Excel's limit.

| Source | What this spec takes from it |
| --- | --- |
| Feature Spec A1 (20-11-2026) | Features A, B, C and BUG-1, amended by the 21-11 review |
| Sankalan UX changes (21-11-2026) | Features D, E (Number columns) and F; screens 4.1, 4.1a, 4.1b, 4.1c, 6.5, 2.4, 2.4b, 3.4, 4.3b, 4.5b |
| Review of 21-11-2026 | Text kept in Date columns; no Distinct on Number columns; no sorting in the Rows view; Choose sheets on every Excel file; decisions D65 to D80 |
| Feature Spec v2.0 (claude/Sankalan\_Feature\_Spec\_v2.0.md) | ENV, UI, TPL, IN, MAP, RUN, DO, VR, ANA, EXP, PERF and their IDs |
| Technical Spec v1.0 (claude/Sankalan\_Technical\_Spec\_v1.0.md) | Query layer, storage layout, ingestion, Jobs, export pipeline, T1 to T31 |
| Sankalan UI screens canvas | Screen and dialog numbers |

**Unchanged.** The app stays offline (SEC-1), Windows only (ENV-2), runs one long Job at a time (T6), exports CSV only (EXP-2) and keeps every UI rule (UI-1 to UI-8). IDs in brackets point to Feature Spec v2.0; T-numbers point to Technical Spec v1.0. macOS was discussed and deferred (D79).

**Decision numbers.** The 21-11 rows in the project copy of Feature Spec v2.0 used D38 to D41, which A1 also used. A1 keeps D38 to D60; those four become D61 to D64; this review's decisions are D65 to D80.

## 2. Feature A · Rows view

The Rows view turns the analysis builder into a filtered row grid. It gives the exact match count, shows the first 100,000 matching rows in stored order, and exports every matching row in that same order. The grid can't be sorted (D71). Changes from A1 are marked Changed.

### 2.1 Behaviour

| ID | Feature | Detail |
| --- | --- | --- |
| ROW-1 | Entry | In New analysis (6.2), a two-way switch Summary \| Rows sits next to the title. Summary is the default. Rows turns the same builder into the Rows view (6.4) |
| ROW-2 | Switching | Switching keeps client, template, ticked runs and filters, and clears the result. Summary's group levels and measures are kept while the user is in Rows and come back on switching back |
| ROW-3 | Not saved | Row views can't be saved. There is no Save button; the header reads "Row views aren't saved". Leaving the view or the Analysis area clears it with no prompt, and cancels a Rows Job that is running |
| ROW-4 | Saved analyses | The switch is not shown when a saved analysis is open (6.3); saved analyses are always Summary |
| ROW-5 | Data | As ANA-2 and ANA-3: Client ▾, Template ▾, a runs list showing Run ID and file names, Select all, "N of M runs selected". Changing the template clears the settings after a confirmation |
| ROW-6 | Filters | Changed. The same filters and operators as ANA-4, combined with AND, including Is not a number and Is not a date (TXT-6, TXT-7); Contains ignores case (T23). The "Is one of" list comes from the ticked runs |
| ROW-7 | Columns | A Columns section lists every template column that isn't removed, each with a tick and ↑ ↓ to reorder. All are ticked by default; the header shows "N of M ticked". At least one column must be ticked to Run or export |
| ROW-8 | Source columns | Source File, Source Sheet, Source Row and Run ID are always in the export, after the ticked columns. On screen they are hidden by default; the tick Show them on screen adds them to the grid after the ticked columns. Source Sheet is blank for CSV files |
| ROW-9 | Run | A Run button at the foot of the settings panel; progress with Cancel while it runs (UI-5). Changing the client, template, runs or filters greys the result with "Settings changed: Run again" and disables Export. Ticking, unticking or reordering columns, and Show them on screen, update the grid at once with no Run |
| ROW-10 | Match count | The result header shows the exact number of matching rows, the runs and rows searched, and the time, e.g. "2,341,118 rows match · 3 runs · 7,499,937 rows searched · 0.9 s". Rows searched is the rows loaded in the ticked runs |
| ROW-11 | Grid | Changed. One row per matching data row, ticked columns in the chosen order; read-only. Shows the first 100,000 matching rows in stored order (ROW-12). Column headers have no sort arrows and clicking them does nothing. When N > 100,000 the footer reads "Showing the first 100,000 of N rows, in the order they were loaded. Export gets all of them." When N ≤ 100,000 it reads "Showing all N rows" |
| ROW-12 | Export and stored order | Export rows (.csv) in the result header opens Export rows (7.9). The export holds every matching row in stored order: by Run ID, then file and sheet in the run's load order, then Source Row. The grid shows the same order. Over 1,000,000 rows it is written in parts (EXP-8) |
| ROW-13 | Left-out rows | Rows left out of a run on override (T18) are not in the Rows view or its export, as in Analysis. Runs of a template without checks have none (NCK-4) |
| ROW-14 | Columns across runs | A column added after an older run shows blank for that run's rows (MAP-11); removed columns are not offered |

A1's ROW-13 (sorting by a column header) is removed (D71).

### 2.2 Grid layout (6.4)

| Item | Rule |
| --- | --- |
| Row height | 40 px, header 40 px (UI-1) |
| First column | Frozen on the left while the others scroll sideways; medium weight |
| Scrolling | The grid scrolls inside its panel in both directions; the window never scrolls (UI-2) |
| Alignment | Text and dates left; numbers right, with international grouping and the column's decimal places (UI-7, T13). Text in a Number column is right-aligned; text in a Date column is left-aligned (TXT-3) |
| Dates | DD-MM-YYYY, or the text as typed (TXT-2) |
| Blank values | Empty cell |
| Long text | One line, cut with an ellipsis; full value on hover |
| Column widths | Set from the column type; the user can drag a header edge to resize; widths are not kept after leaving |

### 2.3 Export rows dialog (7.9)

| Item | Detail |
| --- | --- |
| Title | "Export N rows" |
| Summary line | Client · Template · number of runs · number of filters · approximate size · "CSV file", or "K CSV files" when split (EXP-8) |
| Filters and columns box | The filters in words; then "Columns: the N ticked columns, in their order, then Source File, Source Sheet, Source Row and Run ID"; then "Rows in the order they were loaded: by Run ID, then file, sheet and row" |
| Folder | From the template's export defaults, with Change… |
| File name | Default {Client}\_{Template}\_Rows\_{DD-MM-YYYY}.csv, editable. Confirm before overwriting (EXP-4, EXP-10) |
| Delimiter and encoding | From the template's export defaults (EXP-3) |
| Parts line | Shown when N > 1,000,000 (EXP-9) |
| Disk space | Blocks Export when free space is short (EXP-13) |
| Buttons | Cancel · Export (primary) |
| While exporting | As EXP-11: stage, rows written of N, part K of M, elapsed, Cancel. When done, a banner with Open folder |

### 2.4 States

| State | What the user sees |
| --- | --- |
| Before the first Run | Result panel: "Pick runs and filters, then press Run" |
| No runs ticked | Run is clickable; clicking it shows "Tick at least one run" under the runs list |
| No columns ticked | Clicking Run shows "Tick at least one column" under Columns. After a Run, unticking every column empties the grid with the same message and disables Export |
| Running | Progress and Cancel in the result panel, stages "Counting rows" and "Fetching the first 100,000"; the previous result stays greyed |
| No matching rows | "No rows match these filters." Export rows is not offered |
| Cancelled | The previous result stays greyed with "Cancelled: Run again" |
| Error | A plain message saying what to do (UI-6) |

### 2.5 Not included

Sorting the grid, a row detail panel, saving row views, editing data, quick filters in column headers, OR filters, a different order for the source columns, exporting only the rows on screen.

## 3. Feature B · Measures by column

Measures are picked by column: the user adds a column card, then ticks the operations to apply. A fixed Rows card counts every row. This applies wherever the analysis builder is used: New analysis (6.2), Template › Default outputs (3.2) and New template › Default outputs (2.5). A saved analysis (6.3) shows its measures read-only. It replaces ANA-6.

### 3.1 Behaviour

| ID | Feature | Detail |
| --- | --- | --- |
| MEA-1 | Add a column | + Add column in the Measures section opens a list: Rows first (MEA-10), then the template's columns not yet used as measures. Picking one adds its card. Each column, and Rows, can appear once |
| MEA-2 | Column card | Shows the column name, its type, ↑ ↓ to reorder, ✕ to remove, and a row of operation chips |
| MEA-3 | Operations by type | Changed. Number: Sum, Count, Avg, Min, Max. Date: Count, Distinct, Min, Max. Text: Count, Distinct. Only the operations that fit are shown; Number columns have no Distinct (D70). Hovering a chip shows its full name (Count distinct, Average) |
| MEA-4 | Ticking | Each chip toggles on and off; a ticked chip is teal with medium weight. A card with no operation ticked is allowed while editing, but Run, Save and Preview show "Tick at least one operation for \<column>, or remove it" under that card, and do nothing else |
| MEA-5 | Operation meaning | Changed. Sum and Avg on numbers only. Count = non-blank values in the column (T23); text kept in a Number or Date column counts (TXT-8). Distinct on Text = number of different non-blank values; Distinct on Date = number of different dates, text not counted (D70). Min and Max on numbers and dates only; text is ignored. Avg is shown and exported at the column's decimal places. To count rows, add Rows (MEA-10) |
| MEA-6 | Result column order | Measure columns come after the group-level columns, grouped by card in card order. Within a card, operations always appear in the fixed order Sum, Count, Distinct, Avg, Min, Max, whatever order they were ticked. Moving a card moves its group |
| MEA-7 | Default names | Each result column is named "\<Column> · \<Operation>", using the full operation name, e.g. "Taxable Value · Sum", "Invoice No · Count distinct", "Rows · Count". A default name follows later renames of the template column; a custom name does not |
| MEA-8 | Rename | Each measure column header in an unsaved result (6.2) and in the Default outputs preview (3.2, 2.5) has a ✎ button. It turns the header into a text box: Enter saves, Esc cancels. Leading and trailing spaces are trimmed; up to 100 characters. A blank name returns to the default. Names must be unique within the result, ignoring case, including the group-level headers: a clash shows "Another column is already called \<name>" and keeps the box open. Renaming never re-runs or greys the result. Hovering a header shows its source, e.g. "Invoice No · Count". Saved analyses (6.3) have no ✎; to rename, Duplicate it |
| MEA-9 | Where names are used | Names are kept with the analysis or default output: saved with it, used on the Run's Outputs tab and as CSV headers in exports. A default output's names apply to runs committed after the change; each committed run keeps the headers it was committed with (DO-6). Unticking an operation removes its column and its name; ticking it again starts from the default name |
| MEA-10 | Rows card | A fixed entry, Rows, type "All rows", with a single Count chip, ticked when added. It counts every row that passes the filters, blank or not, within each group. Default name "Rows · Count"; renamable like any measure; ↑ ↓ ✕ like any card |
| MEA-11 | No measures | New. A Summary or default output may have no measure cards when it has at least one group level (D76). Its result lists each group once, with the grand total row showing nothing in the group columns. With neither a group level nor a measure, Run, Save and Preview show "Add a group level or a measure" |

A1's MEA-11 and its section 3.4 (upgrading old measure definitions) are dropped: no definition in the old format exists (D77).

### 3.2 Measures section layout

| Item | Rule |
| --- | --- |
| Section header | "Measures" with + Add column on the right |
| Card | Bordered, 6 px corners. Line 1: name (medium) · type (grey) · ↑ ↓ ✕. Line 2: chips |
| Chips | 26 px high, pill shaped; ticked = teal border and tint (#0E6B6B on #E3F1F0); unticked = grey border, white |
| Note under the cards | "Results show each column's ticked operations together, in this order. Rename a result column from its header." |
| Empty section | "No measures. Add a column, or Rows to count rows." |
| Add column list | Rows first, then columns in template order, each with its type; a search box when the template has more than 12 columns |

### 3.3 Related screens

| Screen | Change |
| --- | --- |
| 6.2 New analysis | New Measures section; result headers with ✎. Example: Invoice No Count → "Invoices"; Taxable Value Sum → "Taxable value", Max → "Taxable Value · Max". Number cards show five chips, no Distinct |
| 3.2 Template › Default outputs | Same Measures section; preview headers with ✎. A rename marks the tab as changed (Save / Discard / Stay on leaving) |
| 2.5 New template › Default outputs | Same as 3.2, preview on the 100,000 sample rows |
| 6.3 Saved analysis | Locked summary reads "Invoice No: Count, shown as Invoices" per ticked operation; default names read "Invoice No: Count"; no ✎ |
| 4.4 Outputs, 5.1 Run › Outputs | No layout change; headers are the ones stored with the run (MEA-9) |

Sorting a Summary result by its columns is unchanged (ANA-7, T23); TXT-11 sets where text values fall.

## 4. Feature C · Export in parts

Every export with more than 1,000,000 data rows is written as parts of 1,000,000 rows each, always, with no option to turn it off. Each part has its own header row, so it opens fully in Excel. An export of 1,000,000 rows or fewer is one file, as today.

### 4.1 Behaviour

| ID | Feature | Detail |
| --- | --- | --- |
| EXP-8 | When | Every export in EXP-1, plus left-out rows (T19) and the Rows view (ROW-12), goes through the shared export() function. When it has more than 1,000,000 data rows it is split. Exactly 1,000,000 rows is one file. "All of a run's outputs" splits each output on its own |
| EXP-9 | Part size | Parts of 1,000,000 data rows; the last part holds the remainder. Parts = N ÷ 1,000,000, rounded up (2,341,118 rows → 3 parts). Each part starts with the header row, and with the BOM when UTF-8 with BOM is chosen (EXP-3). Delimiter and date format as EXP-3 |
| EXP-10 | Names and folder | Parts go in the chosen folder, named \<name>\_part01of03.csv, where \<name> is the file name from the dialog without .csv. Both numbers are zero-padded to the same width, at least 2 digits (\_part001of120). The overwrite confirmation (EXP-4) lists every file that would be replaced. Other files in the folder are never touched, including parts of an earlier export with a different part count |
| EXP-11 | Progress | In the dialog that started it (7.5, 7.9): stage ("Reading rows", "Writing files"), rows written of N, "part K of M", elapsed time, Cancel (UI-5) |
| EXP-12 | Row order | Parts follow the export's own order, cut every 1,000,000 rows (table 4.2). Analysis results and default outputs are cut in on-screen order: the grand total is the first data row of part 1 only; subtotal rows stay next to their group's rows, so a group can run across two parts |
| EXP-13 | Disk space | Before Export is enabled, the dialog estimates the export's size and the free space on the folder's drive. When free space is below what the export needs (8.5, step 1), Export is disabled with "Not enough free space on C:. This export needs about 24.6 GB, including working space; 18.2 GB is free. Free up space or choose a folder on another drive." ("including working space" only when the temp folder is on the same drive, Technical Spec A2 T34; decided 22-11-2026.) It is checked again when the folder changes and when the export starts |
| EXP-14 | Cancel, failure, done | Cancel deletes every part and working file written so far; files the export would have replaced are left as they were. A failure (disk full, folder removed) does the same and says what happened (UI-6). When done, a banner reads "Exported 2,341,118 rows to 3 files" with Open folder (EXP-7) |

### 4.2 Exports and their row order

| Export | Started from | Rows in this order | Often over 1,000,000 rows |
| --- | --- | --- | --- |
| A run's data | 3.1, 5.1 | Stored order: file and sheet in load order, then Source Row | Yes, about 10M per run |
| Left-out rows (T19) | 3.1, 5.1 | Stored order. Not offered for a run without checks (NCK-12) | Sometimes |
| Issue list (ISS-3) | 3.1, 5.1 | File, sheet, row. Not offered for a run without checks (NCK-12) | Yes, when one rule fails widely |
| One default output, or all outputs (one file each) | 5.1 | As stored with the run | Rarely |
| Analysis result (ANA-9) | 6.2, 6.3 | As on screen, with its sort and subtotals | Rarely, e.g. grouped by Invoice No |
| Rows view (ROW-12) | 6.4 | Stored order: Run ID, then file, sheet and row | Yes |

A Number or Date cell that holds text exports its text as typed (TXT-4), in every export above.

### 4.3 Dialog changes

| Dialog | Change |
| --- | --- |
| 7.4 Export data, 7.9 Export rows | When N > 1,000,000, a parts line under the file name: "Saved as 3 files of up to 1,000,000 rows each, so each opens fully in Excel: Acme\_Sales\_R-0003\_part01of03.csv to …\_part03of03.csv". The summary line says "3 CSV files". The disk-space message (EXP-13) sits above the buttons |
| 7.5 Export in progress, 7.9 while exporting | Adds "part K of M" |
| Success banner | "Exported N rows to M files" when split |

### 4.4 Not included

Splitting by a column's values (one file per month or GSTIN), choosing the part size, an option to turn splitting off, zipping the parts, exporting only some parts, .xlsx export.

## 5. Feature D · Choose sheets for a file

In the Files step of a run, the user can choose which sheets of any Excel file to read, for that file and that run only. The template's Sheets to read rule (IN-5) stays the default, so files that match it load as today. This removes the need to rename sheets in Excel when a client's sheet names differ from the template's.

### 5.1 Behaviour

| ID | Feature | Detail |
| --- | --- | --- |
| SHT-1 | Default | Each file is read with the template's Sheets to read rule (by name, first visible sheet, or all visible sheets), as today, until the user chooses sheets for it |
| SHT-2 | Where it's offered | Choose sheets… is on the first row of every .xlsx and .xlsm file in the Files grid, next to ✕, including files that already match the rule (D65). It is not offered for CSV files (no sheets), for files that can't be read (open in Excel, password-protected), because their sheet list can't be read, or for a file in Header not found (SHT-8) |
| SHT-3 | Scope | The choice applies to that file in this run only. The template isn't changed and there is no Save to template. Adding the same file to a later run starts again from the template's rule |
| SHT-4 | Dialog (4.1c) | Title "Choose sheets for \<file name>", with the file size. Every sheet in workbook order, each with a checkbox and its approximate row count from Probe. Hidden sheets are listed, disabled and marked "Hidden, skipped" (IN-13). A note: "The header row is found in each sheet. Headers that don't match the template's columns are handled in Mapping." A total: "2 sheets · about 412,300 rows". Buttons Cancel and Read N sheets ("Read 1 sheet"), disabled when nothing is ticked |
| SHT-5 | Ticks when it opens | The first time: sheets that match the template's rule are ticked; a file with no match opens with nothing ticked. Later: the file's current choice |
| SHT-6 | Sheet not found (4.1b) | A file is in Sheet not found when the template's rule finds none of its named sheets, or only some of them (a file with Sales but no Sales Returns). The error names the file's visible sheets, e.g. "Sheets found: Sales Nov, Returns Nov", with the actions Choose sheets… and Exclude file. The footer reads "Choose sheets for 1 file, or exclude it, to continue". Run Next stays disabled until each such file is resolved (IN-15) |
| SHT-7 | After Read N sheets | The file's rows in the Files grid are replaced by one row per chosen sheet, in workbook order. Each sheet gets its header row found (IN-6), its row count and status, as for any sheet. Cancel leaves the file as it was |
| SHT-8 | Header not found | When a sheet's header row can't be found, the file is in error as today (IN-15) and the only ways on are Exclude file, or fixing the file at source and Re-check (D68). Choose sheets… is not offered on that file. To choose different sheets, the user removes the file with ✕ and adds it again |
| SHT-9 | Re-check and removal | A choice is kept through Re-check. If a chosen sheet is gone or now hidden after Re-check, the file returns to Sheet not found, and the dialog opens with the remaining chosen sheets ticked. Removing the file with ✕ or excluding it drops the choice |
| SHT-10 | Later steps | Chosen sheets go through Mapping like any other sheet: one column per file and sheet in the mapping grid (MAP-4), and Mapping is skipped when every header matches (TPL-6). Source Sheet stores the sheet's own name. The duplicate-file warning (RUN-7) is per file and unchanged. There is no "Chosen" marker in the Files grid, the footer or Run › Source files (D66) |

### 5.2 Screens

| # | Screen | Status | Change |
| --- | --- | --- | --- |
| 4.1 | New run: Files | Changed | Choose sheets… on the first row of each Excel file, next to ✕. The drop-zone hint names the rule: "reads sheets Sales and Sales Returns unless you choose others for a file", "reads the first visible sheet unless…", or "reads every visible sheet unless…". Sample adds Sales\_Nov-2026\_Central.xlsx with sheets Sales Nov and Returns Nov |
| 4.1a | Files, a file can't be read | Changed | Same action column; no action for the file that's open in Excel |
| 4.1b | Files, a file has no matching sheet | New | Error banner names the file's actual sheets; actions Choose sheets… and Exclude file; footer as SHT-6 |
| 4.1c | Choose sheets for a file | New | Dialog over 4.1b as SHT-4 |

### 5.3 Deferred

Applying one file's choice to other files in the run is deferred (D67). The proposed design, not built: files matched by a sheet signature (visible sheet names, trimmed, case ignored, sorted), stored as a run-level rule, with precedence chosen for the file > rule from another file > template rule. Open: same set of sheet names or only the chosen ones, and whether the rule covers files added later. Run\_file records that a file's sheets were chosen by hand (8.4), so this can be added without a catalogue change.

## 6. Feature E · Number and Date columns keep text

A cell in a Number or Date column that isn't blank and can't be read as a number or date keeps its original text, such as "NA", "Nil", "12,000/-" or "31-02-2026". Screens and exports show one column: the value, or the text as typed. Maths and range filters use the values only. This applies to every template, with or without checks (D61, D69); Text columns are unchanged.

### 6.1 Behaviour

| ID | Area | Rule |
| --- | --- | --- |
| TXT-1 | What's kept | Number: any cell that isn't blank (T14) and that MAP-10's number reading can't convert. Date: any cell that isn't blank and isn't an Excel date or a text date in the template's format (MAP-10). Excel error cells (#N/A, #REF!) count as text. The text is kept exactly as typed |
| TXT-2 | Display | One column everywhere data is shown (analysis results, Rows view, default output results, wizard and rule previews): the number with grouping and the column's decimal places, or the date as DD-MM-YYYY, or else the text as typed |
| TXT-3 | Alignment | Text in a Number column is right-aligned, like the numbers. Text in a Date column is left-aligned, like the dates |
| TXT-4 | Export | One column: the number at the column's decimal places with no grouping, or the date as DD-MM-YYYY, or else the text as typed, quoted where CSV needs it (EXP-3) |
| TXT-5 | Number filters | Equals and Between match numbers only; text never matches |
| TXT-6 | Is not a number | New Number filter: rows where the column holds text. Help text: "Cells with text such as NA or Nil instead of a number" (6.5) |
| TXT-7 | Date filters | Year, quarter or month is, and Between, match dates only. New Date filter Is not a date: rows where the column holds text. Help text: "Cells with text such as NA instead of a date" (6.6) |
| TXT-8 | Blank and Count | A cell with text is Not blank; Blank means an empty cell or only spaces (T14). Count counts numbers or dates and text, i.e. every non-blank cell |
| TXT-9 | Other measures | Sum, Avg, Min and Max use numbers or dates only. Distinct on a Date column counts different dates only, not text (D70). Number columns have no Distinct (MEA-3) |
| TXT-10 | Grouping | Grouping by a Number column puts every text value in one group, "(Not a number)". Grouping by a Date column, at any grain, puts every text value in one group, "(Not a date)". Blank stays "(Null)" |
| TXT-11 | Sorting a result | Where results can be sorted (ANA-7), numbers or dates come first, in the chosen direction, then "(Not a number)" or "(Not a date)", then "(Null)", in both directions (P8) |
| TXT-12 | Default output date filters | A relative date filter (DO-3) finds the latest date in the column and ignores text. A row with text in that column is outside every relative and fixed date period |
| TXT-13 | Rules | For a template with checks: Is a number and Is a date fail on text, which goes to the issue list as today. Number range, Date range and Allowed values skip text cells, as they skip blanks, so each text cell gives one issue. Not blank passes. Unique within the run compares the value shown, so two cells of "NA" are equal |
| TXT-14 | Totals check | Text counts as 0 in Input and is null in Loaded and Left out, so the check still balances (T20). Only Number columns are totalled |

### 6.2 Where it shows in the template wizard

Type detection (TPL-3) states how many sample values would be kept as text, e.g. "Number · 98% · 2% aren't numbers and are kept as text". Date columns do the same with "aren't dates". The Rules step with checks off lists those counts (NCK-3).

### 6.3 Screens

| # | Screen | Status | Change |
| --- | --- | --- | --- |
| 6.5 | Filter on a Number column | New (drawn) | Add filter popover over 6.2: Taxable Value; Equals, Between, Blank, Not blank, Is not a number, with help text |
| 6.6 | Filter on a Date column | New (not drawn) | As 6.5 for a Date column: Year is, Quarter is, Month is, Between, Blank, Not blank, Is not a date, with help text |
| 6.2, 6.4, 7.4 | Analysis result, Rows view, Export | Note only | Text in Number and Date cells shown and exported as TXT-2 to TXT-4; "(Not a number)" and "(Not a date)" groups |
| 2.3 | New template: Columns | Changed (not drawn) | Type detection note as 6.2 |

## 7. Feature F · Template without checks

A template can load its data without validation rules. The setting Check data before loading: Yes / No belongs to the template and applies to every run (TPL-10). With No, a run has five steps, Files · Mapping · Load · Outputs · Commit, and every row read is loaded. Counts of values that aren't numbers or dates are shown at Load and Commit as information only.

### 7.1 Behaviour

| ID | Feature | Detail |
| --- | --- | --- |
| NCK-1 | Setting | Check data before loading: Yes (default) or No, per template. It can't be chosen per run. A run uses the setting saved when the run starts. Duplicating a template copies it |
| NCK-2 | Where it's set | At the top of the New template wizard's step 4 Rules (2.4): a Yes / No bar with "Applies to every run of this template. Can be changed later in Settings." The wizard keeps its 6 steps |
| NCK-3 | Rules step with No (2.4b) | The rule editor is replaced by a short explanation of what No means, and a table of the sample's values that aren't numbers per Number column and aren't dates per Date column, e.g. "Tax Amount · 38 of 100,000". Columns with none aren't listed. Footer: "No rules will be set for this template". Rules entered before choosing No come back on choosing Yes |
| NCK-4 | Rows loaded | Every row read is loaded, duplicates included. No rules run, no issues are stored, nothing is left out and no left-out file is written. Blank rows are still dropped (IN-8) and hidden rows and sheets skipped (IN-13) |
| NCK-5 | What still applies | File errors (IN-15), Choose sheets (SHT), mapping decisions (MAP-13), the duplicate-file warning (RUN-7), the totals check (RUN-6, Input = Loaded) and default outputs (DO) |
| NCK-6 | Run steps | Files · Mapping · Load · Outputs · Commit; Load takes Validate's place (F2). When every header matches (TPL-6), Mapping is skipped and Next on Files goes to Load |
| NCK-7 | Load step: reading | Entering Load starts one Job that reads and converts every file and sheet, with progress (stage, files done of total, rows read) and Cancel (UI-5). Cancel discards the staged rows and returns to Mapping, or to Files when Mapping was skipped. Back does the same |
| NCK-8 | Load step: result (4.3b) | A status banner, e.g. "3 files read · 3,126,480 rows to load". Four stat cards: files and sheets read, rows read, rows to load, values that aren't numbers or dates. A table lists each Number and Date column with such values and the count. Selecting a column lists its values as typed, most frequent first, up to 1,000, each with its count and where it first appears (file, sheet, row). Re-check files reads every file again. Next goes to Outputs |
| NCK-9 | Commit step (4.5b) | The summary shows "Data checks: Not checked · template setting", "Rows left out: None", and per column "Taxable Value: 3,412 values aren't numbers and are left out of sums" or "Invoice Date: 120 values aren't dates and are left out of date filters and groups" (RUN-15). The totals check notes "Values that aren't numbers count as 0 on both sides". These counts never block the commit |
| NCK-10 | Comment | Optional, as for a run with no override (RUN-13) |
| NCK-11 | Changing the setting | In Template › Settings (3.4), under Template name: Yes / No with "A change applies from the next run. Runs already loaded don't change." Saving makes a new template version (TPL-7). Yes → No keeps the rules: Columns & rules (3.3) shows them greyed with "Not in use: this template loads without checks" and they can't be edited or tested. No → Yes puts kept rules back in use; a template created with No starts with the automatic Is a number and Is a date rules only (VR-7) |
| NCK-12 | Runs without checks | The run record stores that it was loaded without checks. Runs list (3.1): the Issues column shows "Not checked". Run detail (5.1): no Issues tab; Summary shows "Data checks: Not checked". Export issue list and Export left-out rows are not offered for these runs |
| NCK-13 | Rule tools | Test rules on latest run (VR-8) and run-only rule changes (VR-5) are not offered while the setting is No |
| NCK-14 | Analysis | Runs with and without checks can be ticked together in Analysis and the Rows view; nothing in a result shows how a run was loaded |

### 7.2 Screens

| # | Screen | Status | Change |
| --- | --- | --- | --- |
| 2.4 | New template: Rules | Changed (drawn) | Check data before loading bar at the top, Yes selected |
| 2.4b | Rules, data not checked | New (drawn) | As NCK-3. Needs updating: add Date columns to the table |
| 3.4 | Template: Settings | Changed (drawn) | As NCK-11 |
| 4.3b | New run without checks: Load | New (drawn) | As NCK-8. Needs updating: add Date columns. Sample: Acme Traders › Purchase Register, 3 files, 3,126,480 rows, 6,802 values that aren't numbers |
| 4.5b | New run without checks: Commit | New (drawn) | As NCK-9. Needs updating: add the Date line |
| 4.3b reading | Load while files are read | Not drawn | Progress and Cancel as NCK-7 |
| 3.3 | Columns & rules, without checks | Not drawn | Rules greyed, "Not in use" as NCK-11 |
| 3.1, 5.1 | Runs list and Run for a run without checks | Not drawn | "Not checked" and no Issues tab, as NCK-12 |

## 8. Backend design

Every feature runs inside the query layer and Job runner of Technical Spec v1.0 (T5, T6, V3-1), with no new processes, packages or catalogue tables. The Rows view adds one temporary DuckDB table, exports gain a streaming splitter in Python, Date columns gain a text companion like Number columns, and measures use a version-2 definition. Because nothing is built yet, these are part of the first catalogue schema and need no upgrade (D77).

### 8.1 Query layer entry points

| Entry point | New or changed | Used by |
| --- | --- | --- |
| count\_rows(spec, runs) | New | ROW-10 match count |
| fetch\_rows(spec, runs) | New | ROW-11: fills the temporary table rows\_view with the first 100,000 matching rows in stored order |
| rows\_page(first, count) | New | Grid scrolling, read from rows\_view |
| estimate\_export(source, options) | New | EXP-13 and the dialogs: rows, estimated bytes, parts, file names, bytes needed, bytes free |
| export(source, options) | Changed | Adds the Rows view as a source, per-run chunks, parts (8.5) and the display expression for text companions (8.2) |
| run\_definition(spec, runs) | Changed | Same signature; reads version-2 measures and handles text companions in filters, groups and measures (8.8) |
| resolve\_headers(definition) | New | MEA-7 to MEA-9: the header text of every result column |
| text\_value\_summary(source, column\_id) | New | NCK-3, NCK-8, NCK-9: per Number and Date column, the count of text values; for one column, its values as typed, most frequent first, up to 1,000, with count and first file, sheet and row |

The Rows view spec is held in memory and never stored (ROW-3), with the same shape as saved definitions (V3-2): {template\_id, filters:\[…\], columns:\[column\_id, …\], show\_source}.

### 8.2 Storage: text companions (T28, extended)

- Every Number and Date column cNNN has a companion cNNN\_t (VARCHAR) in every data.parquet and left\_out.parquet. It holds the original text only where the cell isn't blank and can't be converted; on every other row it is null. cNNN and cNNN\_t are never both filled.
- Display and export use one expression: the formatted value when cNNN is not null, else cNNN\_t. Formatting: numbers at the column's decimal places (grouping on screen, none in exports); dates as DD-MM-YYYY.
- A column added after an older run reads as null in both parts for that run, through union\_by\_name (MAP-11).
- Mostly-null companions take very little Parquet space; queries that don't need them never read them.

### 8.3 Ingestion changes

**Sheets per file (SHT).** Probe already lists every sheet with its visibility and approximate row count. The run state gains a per-file sheet choice, {file\_id: \[sheet names\]}. Sheet resolution for a file is its choice when there is one, else the template's rule (IN-5). Read N sheets starts a short Job that finds the header row of each chosen sheet (IN-6) in a reader worker. Re-check probes again and keeps each choice; a chosen sheet that is gone or hidden returns the file to Sheet not found.

**Convert (stage 4).**

| Type | Rule |
| --- | --- |
| Number | As T28: not convertible and not blank → the number is null and cNNN\_t holds the text as typed |
| Date | An Excel date, or text in the template's date format → the date, with any time of day dropped. Not convertible and not blank → the date is null and cNNN\_t holds the text as typed. For a template with checks, the value also goes to the issue list, as today |

**Templates without checks (T30).** Entering the Load step starts one cancellable Job: stage 3 (Read), stage 4 (Convert), then text\_value\_summary over the staged data.parquet. No validation scan runs and no left\_out.parquet or issues.parquet is written. Cancel deletes \_staging\\\<job-id>\\ as today.

### 8.4 Catalogue changes

| Table | Change |
| --- | --- |
| template | checks (Yes / No), as T30 |
| template\_version | Snapshot includes checks; rules are kept when checks is No |
| run | New fields: checks (as used by the run) and text\_counts, a JSON map of column\_id → count of text values, filled at commit for every run |
| run\_file | New field sheets\_chosen (true when the sheets were chosen by hand; not shown, SHT-10) |
| run\_output | New field headers, a JSON list of the resolved headers at commit (MEA-9) |
| saved\_analysis, default\_output, template\_version | definition holds version-2 measures (8.8) |

### 8.5 Export pipeline

Every export follows five steps. A source is cut into chunks: one per run for run data, left-out rows and the Rows view, and a single chunk for everything else.

1. **Estimate (EXP-13).** N is known before the export starts: rows loaded or left out (catalogue), issue counts (run\_issue\_count), rows in the stored output or result table, or the Rows view count. A COPY of the first 10,000 rows, or all if fewer, to %TEMP%\\Sankalan gives bytes per row; estimate = bytes per row × N × 1.05. Bytes needed = estimate + the largest chunk's estimate (working space) + the larger of 1 GB and 10% of the estimate. A single file in plain UTF-8 needs no working space.
2. **Names (EXP-10).** Final names are worked out (one file, or M parts). Existing files with those names are listed for the overwrite confirmation.
3. **Extract.** For each chunk in order, one COPY (SELECT …) TO '\<folder>\\\<name>.tmp\<k>' with header, the chosen delimiter and DATEFORMAT '%d-%m-%Y'. Number and Date columns use the display expression (8.2). In the Rows view, a run that lacks a ticked column selects NULL for it, Source File comes from a list literal of that run's file names indexed by \_src\_file, and Run ID is a literal per run, so the select has no join.
4. **Stream and split.** Python reads each chunk file in order, writes it into the parts (8.6), then deletes the chunk file before the next COPY starts. Working space never exceeds one chunk. Parts are written as \<final name>.partial.
5. **Finish.** The splitter's row count must equal N. If it does, each .partial is renamed to its final name, replacing any file the user confirmed. If not, the export fails with "Export check failed: wrote X of N rows" and cleans up.

One file in plain UTF-8 from a single chunk skips step 4: its chunk file is renamed. Cancel or failure at any step interrupts DuckDB, deletes every .tmp\<k> and .partial file, and leaves existing files untouched (EXP-14).

### 8.6 Splitter

The splitter counts CSV records, not lines, because a value can hold a line break inside quotes. DuckDB quotes such values and doubles any quote inside them.

| Item | Design |
| --- | --- |
| Header | The first record of the first chunk file is the header. The header record of each later chunk file is skipped |
| Record end | A \\n outside quotes. Quote state flips on every "; a doubled quote flips twice, so it needs no special case |
| Fast path | Blocks of 8 MB. A block with no ", read while outside quotes, is counted with bytes.count(b"\\n"). When a part boundary falls inside the block, bytes.find locates the exact line end |
| Slow path | A block with quotes walks quote and line-end positions with bytes.find |
| New part | After 1,000,000 records: close the part, open the next, write the BOM if chosen, then the header |
| Progress | Rows written and part K of M, reported to the Job every 250 ms |
| Runs in | The Job's background thread; I/O and bytes methods release the GIL, so the window stays responsive (NF-3) |

### 8.7 Rows view queries and stored order

- **Source.** Each ticked run's data.parquet, read one run at a time in Run ID order. Left-out rows are in their own file, so they are never read (ROW-13). Filters compile exactly as for Analysis.
- **Match count (ROW-10).** SELECT count(\*) … WHERE \<filters> over read\_parquet(\[…\], union\_by\_name = true). DuckDB reads only the filter columns.
- **First 100,000 rows (ROW-11).** CREATE TEMP TABLE rows\_view, then, run by run in Run ID order, INSERT … SELECT \<every non-removed template column and companion>, run\_id, \_src\_file, \_src\_sheet, \_src\_row FROM read\_parquet('\<run>\\data.parquet') WHERE \<filters> LIMIT \<rows still needed>, with a sequence column \_seq for grid order. It stops once 100,000 rows are held, so it never reads past them.
- **One Job.** Run executes the count, then the fetch, with stages "Counting rows" and "Fetching the first 100,000". Cancel calls interrupt() on the Job's cursor.
- **Paging.** The grid fetches pages of 200 rows from rows\_view by \_seq. The table holds every column, so column ticks, order and Show them on screen redraw from it with no query against the runs (ROW-9).
- **Display values.** Run ID and Source File names come from the catalogue (run, run\_file) and are mapped in Python for the rows on screen.
- **Lifetime.** rows\_view is dropped when the user leaves the Rows view, switches to Summary, or changes template (ROW-3).
- **Stored order.** Convert writes data.parquet in stored order: the UNION ALL of file-and-sheet selects in load order, with DuckDB's preserve\_insertion\_order on (the default). The grid and exports read one run's file per statement, so DuckDB's order guarantee only ever covers a filtered scan of a single file. AC-ROW-12b checks it on every build (R7).

### 8.8 Measures, filters and groups in SQL

Version-2 measures in saved analyses, default outputs and template versions:

```
{"definition_version": 2,
 "measures": [
   {"column_id": "_rows", "ops": [{"fn": "count", "name": null}]},
   {"column_id": "c004", "ops": [{"fn": "count", "name": "Invoices"}]},
   {"column_id": "c007", "ops": [{"fn": "sum", "name": "Taxable value"}, {"fn": "max", "name": null}]}
 ]}
```

fn is one of sum, count, count\_distinct, avg, min, max; count\_distinct is refused on Number columns. Ops are stored in that fixed order on every save (MEA-6). name: null means the default name (MEA-7). measures may be empty when there is at least one group level (MEA-11).

| Part | SQL, for a Number or Date column c with companion c\_t |
| --- | --- |
| Rows | count(\*) |
| Count | count(c) + count(c\_t), since only one of them is ever filled (TXT-8). Text columns: count(c) |
| Count distinct | Date: count(DISTINCT c). Text: count(DISTINCT c) |
| Sum, Avg, Min, Max | On c only; Avg cast to DECIMAL(38, d), rounded half away from zero (T13) |
| Equals, Between, Year / Quarter / Month is | On c only, so text never matches |
| Is not a number, Is not a date | c\_t IS NOT NULL; stored as op "not\_number" or "not\_date" |
| Blank / Not blank | c IS NULL AND c\_t IS NULL / either filled |
| Group by | Key (kind, value): kind 0 with c (date\_trunc for a Date grain) when c is filled, kind 1 for "(Not a number)" or "(Not a date)" when c\_t is filled, kind 2 for "(Null)". Sorting orders by kind first, then value in the chosen direction (TXT-11) |
| Rules (TXT-13) | Is a number / Is a date fail where c\_t IS NOT NULL. Range and Allowed values test c, so text is skipped like a blank. Not blank passes when either is filled. Unique within the run compares coalesce(cast(c AS VARCHAR), c\_t) |

Result columns are named internally g1 … gn (group levels) and m1 … mk (measures, in MEA-6 order); resolve\_headers() turns them into header text at display and export time. A default name that equals another column's name gets " (2)", then " (3)" (P3). At commit, the resolved headers of every default output are stored in run\_output.headers (P4), and the Outputs tab and exports read them from there.

### 8.9 Checks before Run, Save and Preview

Checked in the window, before a Job starts, in this order; the first failure shows under its section and nothing runs:

1. No runs ticked → "Tick at least one run" (Analysis and Rows).
2. Rows view with no columns ticked → "Tick at least one column".
3. Summary with no group level and no measure → "Add a group level or a measure" (MEA-11).
4. A measure card with no operation ticked → "Tick at least one operation for \<column>, or remove it" (MEA-4).
5. A default output with no name → as DO-1 today.

## 9. Performance

Speed comes from the design rather than tuning: nothing in these features sorts all matching rows, the Rows grid stops reading at 100,000 rows, and every export streams. The targets are provisional, measured once by the release performance suite on a 16 GB, 4-core laptop, and a miss is reported, not blocking (T4). A1's PERF-9 (re-sorting the grid) is removed with sorting.

| ID | Operation | Target |
| --- | --- | --- |
| PERF-7 | Rows view Run on 1 run (10M rows), 2 filters: count and first 100,000 rows | ≤ 5 s |
| PERF-8 | The same across 12 runs (about 120M rows) | ≤ 30 s |
| PERF-9 | Grid scrolling: the next page of 200 rows | ≤ 100 ms |
| PERF-10 | Ticking, unticking or reordering a column in the Rows view | ≤ 200 ms |
| PERF-11 | Export 10M rows, 20 columns, UTF-8 with BOM, 10 parts | ≤ 60 s |
| PERF-12 | Rows view export of 120M rows, 120 parts | ≤ 12 min, cancellable |
| PERF-13 | Size and free-space estimate when an export dialog opens | ≤ 2 s |
| PERF-14 | Load step of a template without checks: 10M rows from CSV, including the text-value summary | ≤ 2 min, as PERF-1 |

PERF-1 to PERF-6 are unchanged. Text companions are read only by queries that need them, so PERF-3 to PERF-5 are not affected; PERF-1 and PERF-2 include writing them.

## 10. Acceptance criteria

Each feature item is accepted when every criterion against it passes on a local Windows build; the test cases sheet, [Sankalan — Test Cases A2](https://claude.ai/artifact/KUp93csxqw9abamkgm3JpQ) (copy: claude/Sankalan\_Test\_Cases\_A2.md), has one test case per criterion and per performance target. Speed is accepted by PERF-7 to PERF-14 (section 9).

### 10.1 Test data

| Set | Contents |
| --- | --- |
| TPL-R (with checks) | 20 columns: 8 Text, 8 Number (2 decimals), 4 Date. 3 runs of 2,500,000 rows each (R-0001 to R-0003). 1% of cells blank, except Invoice No. Some text values contain commas, double quotes and line breaks. R-0002 has 63 left-out rows and adds the column Place of Supply. In R-0003 one sheet left Invoice No as null (MAP-6) for 400,000 rows. Is a number on Taxable Value and Is a date on Invoice Date are set to Warning, so text rows load: R-0001 has 1,000 "NA", 500 "Nil" and 10 "12,000/-". Invoice Date: R-0002 has 300 "NA" and 5 "31-02-2026" |
| TPL-N (without checks) | TPL-R's columns, Check data before loading = No. 2 CSV files of 500,000 rows; 2,000 rows repeated exactly; Taxable Value with 6,802 text values; Invoice Date with 120 text values |
| Sheet files | Sales\_Nov-2026\_Central.xlsx: sheets Sales Nov, Returns Nov, and a hidden sheet Notes. Sales\_Nov-2026\_East.xlsx: sheet Sales only. Sales\_Nov-2026\_West.xlsx: sheets Sales, Sales Returns and Cover (no header row). Template rule: sheets Sales and Sales Returns |

### 10.2 Rows view

| AC | Item | Criterion |
| --- | --- | --- |
| AC-ROW-1 | ROW-1 | New analysis opens in Summary. Choosing Rows shows Columns and Run, no group levels, no measures and no Save button; the header reads "Row views aren't saved" |
| AC-ROW-2 | ROW-2 | With 2 runs, 2 filters, 2 group levels and 3 measures set in Summary, switching to Rows keeps the runs and filters and clears the result. Switching back shows the same group levels and measures |
| AC-ROW-3 | ROW-3 | After a Rows result, opening Clients and coming back to Analysis shows an empty builder with no prompt. Leaving while a Rows Job runs cancels it |
| AC-ROW-4 | ROW-4 | A saved analysis (6.3) shows no Summary \| Rows switch |
| AC-ROW-6 | ROW-6 | Is not a number and Is not a date are offered and give the same counts as in Summary |
| AC-ROW-7 | ROW-7 | All 21 TPL-R columns are ticked by default, with "21 of 21 ticked". Unticking all and pressing Run shows "Tick at least one column" and runs nothing |
| AC-ROW-8 | ROW-8 | The grid has no source columns until Show them on screen is ticked, then they follow the ticked columns. Every export ends with Source File, Source Sheet, Source Row, Run ID in that order; Source Sheet is blank for CSV rows |
| AC-ROW-9a | ROW-9 | Changing a filter or a run tick greys the result with "Settings changed: Run again" and disables Export rows. Changing the template asks first (ROW-5), then clears the settings and the result (corrected 22-11-2026: this criterion said the template greys the result) |
| AC-ROW-9b | ROW-9 | Unticking, ticking or moving a column, or Show them on screen, redraws the grid without greying it and without a Job |
| AC-ROW-10 | ROW-10 | The match count equals an independent count(\*) with the same filters. Rows searched equals rows loaded in the ticked runs (7,499,937 for all three) |
| AC-ROW-11a | ROW-11 | With N > 100,000 the grid holds exactly 100,000 rows and the footer reads "Showing the first 100,000 of N rows, in the order they were loaded. Export gets all of them." With N ≤ 100,000 it reads "Showing all N rows" |
| AC-ROW-11b | ROW-11 | Clicking a column header changes nothing and no sort arrow appears. The grid's 100,000 rows equal the first 100,000 data rows of the export, in the same order |
| AC-ROW-12a | ROW-12 | The exported data rows, summed over all parts, equal the match count |
| AC-ROW-12b | ROW-12, 8.7 | In the export, Run ID never goes back to an earlier run, and within each run the rows follow file and sheet load order with Source Row ascending. Two exports with the same settings are byte-identical |
| AC-ROW-13 | ROW-13 | None of R-0002's 63 left-out rows appears in the grid, the count or the export |
| AC-ROW-14 | ROW-14 | Place of Supply is blank for every R-0001 row, in the grid and in the export |
| AC-ROW-S1 | 2.4 | Filters matching nothing show "No rows match these filters." and no Export rows button |
| AC-ROW-S2 | 2.4 | Cancel during Run leaves the previous result greyed with "Cancelled: Run again" |

### 10.3 Measures by column

| AC | Item | Criterion |
| --- | --- | --- |
| AC-MEA-1 | MEA-1 | + Add column lists Rows first, then unused columns in template order. A column or Rows already added is not listed |
| AC-MEA-3 | MEA-3 | A Number card shows Sum, Count, Avg, Min, Max and no Distinct; a Date card Count, Distinct, Min, Max; a Text card Count, Distinct. Hover shows Count distinct and Average |
| AC-MEA-4 | MEA-4 | A card with no operation ticked lets the user keep editing. Run, Save and Preview each show "Tick at least one operation for \<column>, or remove it" and start nothing |
| AC-MEA-5 | MEA-5 | Taxable Value · Average shows and exports with 2 decimal places, rounded half away from zero |
| AC-MEA-6 | MEA-6 | Ticking Max, then Sum, on Taxable Value gives the columns Sum, then Max. Moving the card above Invoice No moves both columns before Invoice No's |
| AC-MEA-7 | MEA-7 | Default headers read exactly "Taxable Value · Sum", "Invoice No · Count distinct", "Rows · Count". Renaming the template column Taxable Value to Taxable Amt changes the default header; a custom header stays |
| AC-MEA-8 | MEA-8 | ✎ then Enter saves a name; Esc cancels; a blank name restores the default. "invoices" is refused when a group header or another measure is "Invoices". A rename doesn't grey the result or change its time. Saved analyses show no ✎ |
| AC-MEA-9 | MEA-9 | Renaming a default output's measure, then committing a new run: the new run's Outputs tab and CSV use the new header, and earlier runs keep their old one. Unticking and re-ticking an operation brings back its default name |
| AC-MEA-10 | MEA-10 | On R-0003, Rows · Count equals the run's rows loaded, while Invoice No · Count is 400,000 lower. In a grouped result, Rows · Count per group adds up to the grand total |
| AC-MEA-11 | MEA-11 | A Summary grouped by GSTIN with no measures runs and lists each GSTIN once. With no group level and no measure, Run shows "Add a group level or a measure" and starts nothing |

### 10.4 Export in parts

| AC | Item | Criterion |
| --- | --- | --- |
| AC-EXP-8a | EXP-8 | 1,000,000 rows give one file with no part suffix; 1,000,001 rows give 2 parts of 1,000,000 and 1 rows |
| AC-EXP-8b | EXP-8, 4.2 | Each export in table 4.2 splits when over 1,000,000 rows: run data, left-out rows, issue list, a default output, all outputs (each separately), an analysis result, the Rows view |
| AC-EXP-9a | EXP-9 | Every part opens in Excel 365 with all its rows: a full part has 1,000,001 records with the header, the last has the remainder plus the header. Each part starts with the same header, and with the BOM when chosen |
| AC-EXP-9b | EXP-9, 8.6 | Values with line breaks, quotes and delimiters next to a part boundary are never split across parts. Every part parses as valid CSV with the expected record count. The data rows of all parts, joined in order, are byte-identical to the same export written as one file (test build) |
| AC-EXP-10 | EXP-10 | 3 parts are named \_part01of03 to \_part03of03; 120 parts \_part001of120 to \_part120of120. The overwrite confirmation lists exactly the files to be replaced. An older \_part04of04 in the folder is untouched |
| AC-EXP-11 | EXP-11 | Progress shows the stage, rows written of N and "part K of M", updated at least every second |
| AC-EXP-12 | EXP-12 | A 2,100,000-row analysis result with subtotals: the grand total is the first data row of part 1 and appears in no other part. Rows and subtotals across all parts, in order, match the on-screen order |
| AC-EXP-13 | EXP-13 | With a destination drive that has less free space than needed, Export is disabled and the message shows both sizes. Choosing a folder on a drive with enough space enables it |
| AC-EXP-14a | EXP-14 | Cancel during part 2 of 3 leaves no part, .tmp or .partial file. A file that would have been replaced keeps its original SHA-256 |
| AC-EXP-14b | EXP-14, 8.5 | Disk full during writing, or a forced row-count mismatch (test build), fails the export with a plain message and the same clean-up |
| AC-EXP-14c | EXP-14 | A split export ends with the banner "Exported N rows to M files" and Open folder opens the chosen folder |

### 10.5 Choose sheets

| AC | Item | Criterion |
| --- | --- | --- |
| AC-SHT-1 | SHT-2 | Choose sheets… appears on the first row of every .xlsx and .xlsm file, including one whose sheets match the rule. It does not appear for a CSV file, a file open in Excel, a password-protected file, or a file in Header not found |
| AC-SHT-2 | SHT-4, SHT-5 | For Central, the dialog lists Sales Nov, Returns Nov and Notes in workbook order with row counts; Notes is disabled and marked "Hidden, skipped". Nothing is ticked and Read is disabled. Ticking two sheets shows "Read 2 sheets" and the total |
| AC-SHT-3 | SHT-6, SHT-7 | Central shows Sheet not found naming "Sales Nov, Returns Nov", and Next is disabled with "Choose sheets for 1 file, or exclude it, to continue". After choosing both sheets the file shows two Ready rows and Next is enabled. Cancel in the dialog leaves the file in error |
| AC-SHT-4 | SHT-6 | East (Sales only) shows Sheet not found; its dialog opens with Sales ticked |
| AC-SHT-5 | SHT-8 | Choosing Cover in West puts the file in Header not found; only Exclude file is offered and Choose sheets… is gone. Removing the file with ✕ and adding it again offers Choose sheets… again, starting from the rule |
| AC-SHT-6 | SHT-9 | After Re-check the choice is kept. Renaming Sales Nov in the file and pressing Re-check returns Central to Sheet not found, with Returns Nov ticked in the dialog |
| AC-SHT-7 | SHT-3 | After committing, the template's Sheets to read is unchanged, and adding Central to a new run gives Sheet not found again |
| AC-SHT-8 | SHT-10 | In the committed run, Source Sheet holds "Sales Nov" and "Returns Nov". No "Chosen" label appears in the Files grid, the footer or Run › Source files; run\_file.sheets\_chosen is true for Central only |
| AC-SHT-9 | SHT-10 | When every header of the chosen sheets matches, Mapping is skipped; a new header in a chosen sheet opens Mapping with only that column highlighted |

### 10.6 Number and Date columns keep text

| AC | Item | Criterion |
| --- | --- | --- |
| AC-TXT-1 | TXT-2 to TXT-4 | "NA", "Nil" and "12,000/-" in Taxable Value, and "NA" and "31-02-2026" in Invoice Date, show as typed in the Rows view, right- and left-aligned respectively, and export as typed |
| AC-TXT-2 | TXT-9 | Sum, Average, Min and Max of Taxable Value equal an independent calculation over its numeric cells only. Min and Max of Invoice Date ignore text |
| AC-TXT-3 | TXT-8, TXT-9 | Count of Taxable Value on R-0001 = numeric cells + 1,510. Count of Invoice Date on R-0002 includes the 305 text cells. Distinct of Invoice Date equals the number of different dates, text not counted |
| AC-TXT-4 | TXT-5 to TXT-8 | On R-0001, Is not a number on Taxable Value returns exactly 1,510 rows; Equals and Between never return a text row; text rows are Not blank and Blank returns empty cells only. On R-0002, Is not a date on Invoice Date returns exactly 305 rows |
| AC-TXT-5 | TXT-10 | Grouped by Taxable Value on R-0001, "(Not a number)" has Rows · Count 1,510, separate from "(Null)". Grouped by Invoice Date month and by year on R-0002, "(Not a date)" has 305 |
| AC-TXT-6 | TXT-11 | Sorting a result by a Number or Date group column, ascending and descending, puts values first, then "(Not a number)" or "(Not a date)", then "(Null)" |
| AC-TXT-7 | TXT-13 | In a run with checks, each text cell gives exactly one issue (Is a number or Is a date), none from Number range, Date range or Allowed values; Not blank passes; two "NA" cells in a Unique key count as duplicates |
| AC-TXT-8 | TXT-14 | The totals check passes on R-0001: text counts as 0 in Input and is null in Loaded |
| AC-TXT-9 | TXT-12 | A default output with Latest month on Invoice Date uses the latest real date in R-0002 and excludes its text rows |
| AC-TXT-10 | 6.2 | In the New template wizard, a sample with 2% text in a Number column shows "2% aren't numbers and are kept as text" |

### 10.7 Template without checks

| AC | Item | Criterion |
| --- | --- | --- |
| AC-NCK-1 | NCK-2, NCK-3 | Step 4 Rules shows the bar with Yes selected. Choosing No replaces the rule editor with the explanation and the sample's counts for Number and Date columns, and the footer "No rules will be set for this template". Choosing Yes again brings back rules entered earlier |
| AC-NCK-2 | NCK-4, NCK-6 | A run of TPL-N shows Files · Mapping · Load · Outputs · Commit. Rows loaded = rows read, including the 2,000 repeated rows; the run folder has no issues.parquet or left\_out.parquet |
| AC-NCK-3 | NCK-7 | Load shows progress and Cancel. Cancel returns to Mapping, or to Files when Mapping was skipped, and leaves \_staging empty |
| AC-NCK-4 | NCK-8 | After Load, the counts are 6,802 for Taxable Value and 120 for Invoice Date. Selecting Taxable Value lists its values most frequent first, at most 1,000, each with the correct count and first file, sheet and row |
| AC-NCK-5 | NCK-5 | A password-protected file still blocks the run; a new header still needs a Mapping decision; a file loaded in an earlier run still shows the duplicate-file warning |
| AC-NCK-6 | NCK-9, NCK-10 | Commit shows "Data checks: Not checked · template setting", "Rows left out: None", the Taxable Value and Invoice Date lines, and a passing totals check. Commit is enabled with no comment |
| AC-NCK-7 | NCK-11, NCK-13 | Changing TPL-R to No in Settings: the next run has a Load step; earlier runs keep their Issues tab; Columns & rules shows the rules greyed as "Not in use" and not editable; Test rules on latest run is not offered; the template version goes up by one. Changing back to Yes puts the rules back in use |
| AC-NCK-8 | NCK-12 | In the Runs list a TPL-N run shows "Not checked" under Issues; Run detail has no Issues tab and its Summary says "Data checks: Not checked"; Export issue list and Export left-out rows are not offered |
| AC-NCK-9 | NCK-1 | Duplicating TPL-N gives a template with Check data before loading = No |
| AC-NCK-10 | NCK-14 | An analysis ticking runs loaded with and without checks returns the same totals as each run analysed alone, summed |

### 10.8 Bug fix

| AC | Criterion |
| --- | --- |
| AC-BUG-1a | A temporary table large enough to spill under a small memory limit, created in one Job and read in the next, reads back in full; the old code fails this test |
| AC-BUG-1b | After every Job the temp folder holds nothing but the open connection's duckdb\_temp\_\<pid>\_… files; after closing the data folder, and after a restart, it is empty |
| AC-BUG-1c | A full-size load (3 runs × 2,500,000 rows) commits all three runs |

## 11. Decisions

D38 to D60 come from Addendum A1 and its brainstorm (20-11-2026), D61 to D64 from the UX discussion of 21-11-2026 (numbered D38 to D41 in the project copy of Feature Spec v2.0), and D65 to D80 from the review of 21-11-2026. P8 is proposed and needs confirmation (section 13).

| # | Date | Decision | Item |
| --- | --- | --- | --- |
| D38 | 20-11-2026 | A Rows view, as a Summary \| Rows switch in the analysis builder | ROW-1, ROW-2 |
| D39 | 20-11-2026 | Row views are never saved | ROW-3 |
| D40 | 20-11-2026 | Source File, Source Sheet, Source Row and Run ID are always exported; hidden on screen by default | ROW-8 |
| D41 | 20-11-2026 | No row detail panel | 2.5 |
| D42 | 20-11-2026 | Show the first 100,000 matching rows; export all | ROW-11, ROW-12 |
| D43 | 20-11-2026 | Measures are picked by column, then operations ticked | MEA-1 to MEA-4 |
| D44 | 20-11-2026 | All six operations kept. **Changed** by D70: no Distinct on Number columns | MEA-3 |
| D45 | 20-11-2026 | Result measure columns grouped by column, in card order | MEA-6 |
| D46 | 20-11-2026 | Result columns are renamed from the result header | MEA-8 |
| D47 | 20-11-2026 | Exports over 1,000,000 data rows are always split, with no option | EXP-8 |
| D48 | 20-11-2026 | Splitting applies to every export, through the shared export() function | EXP-8 |
| D49 | 20-11-2026 | Parts of 1,000,000 data rows each | EXP-9 |
| D50 | 20-11-2026 | Parts go in the chosen folder | EXP-10 |
| D51 | 20-11-2026 | No splitting by a column's values | 4.4 |
| D52 | 20-11-2026 | Analysis results split like every other export, in on-screen order | EXP-12 |
| D53 | 20-11-2026 | The Rows view exports in stored order | ROW-12 |
| D54 | 20-11-2026 | The Rows view leaves out left-out rows | ROW-13 |
| D55 | 20-11-2026 | Speed: the best that is feasible without complex code; targets are provisional and reported | PERF-7 to PERF-14 |
| D56 | 20-11-2026 | An export is blocked when free space is below its estimated size plus a margin | EXP-13 |
| D57 | 20-11-2026 | A fixed Rows card counts rows | MEA-10 |
| D58 | 20-11-2026 | Committed runs keep their output headers after a rename | MEA-9 |
| D59 | 20-11-2026 | No renaming on saved analyses | MEA-8 |
| D60 | 20-11-2026 | Result names are unique, group-level headers included | MEA-8 |
| D61 | 21-11-2026 | Every Number column keeps the original text of cells that aren't numbers, shown and exported as one column with the numbers | TXT-1 to TXT-4 |
| D62 | 21-11-2026 | Text in a Number column: maths and number filters use numbers only; Count includes text; text is Not blank; new filter Is not a number; one "(Not a number)" group; numbers sort before text | TXT-5 to TXT-11 |
| D63 | 21-11-2026 | A template can load without checks: no rules, every row loaded; set per template, not per run | NCK-1, NCK-4 |
| D64 | 21-11-2026 | For a template without checks, Commit shows per column how many values aren't numbers; it never blocks | NCK-9 |
| D65 | 21-11-2026 | Choose sheets per file, for this run only, one dialog per file, offered on every readable Excel file even when its sheets match the rule | SHT-2, SHT-3 |
| D66 | 21-11-2026 | No "Chosen" marker on any screen | SHT-10 |
| D67 | 21-11-2026 | Applying a choice to other files in the run is deferred | 5.3 |
| D68 | 21-11-2026 | A file whose header row can't be found must be excluded, or fixed and re-checked; Choose sheets is not offered on it | SHT-8 |
| D69 | 21-11-2026 | Date columns keep the original text of cells that aren't dates, like Number columns; new filter Is not a date; one "(Not a date)" group | TXT |
| D70 | 21-11-2026 | No Distinct on Number columns; Distinct on a Date column counts dates only | MEA-3, MEA-5, TXT-9 |
| D71 | 21-11-2026 | The Rows view can't be sorted; its grid shows stored order, as its export does (closes A1's OA-3). Sorting a Summary result is unchanged | ROW-11 |
| D72 | 21-11-2026 | Without checks, the Rules step stays with Yes / No at its top, and a run has five steps with Load in Validate's place | NCK-2, NCK-6 |
| D73 | 21-11-2026 | The setting changes in Template › Settings, from the next run; rules are kept, not in use | NCK-11 |
| D74 | 21-11-2026 | Runs without checks show "Not checked", have no Issues tab, and offer no issue or left-out export | NCK-12 |
| D75 | 21-11-2026 | Load and Commit show values that aren't numbers and values that aren't dates | NCK-8, NCK-9 |
| D76 | 21-11-2026 | A Summary may have no measures when it has at least one group level (closes A1's OA-4) | MEA-11 |
| D77 | 21-11-2026 | No upgrade steps: v2.0 is not built and no client data exists (closes A1's OA-1; A1's MEA-11 and section 3.4 dropped) | 8 |
| D78 | 21-11-2026 | A1's proposals P1 and P3 to P6 confirmed; P2 removed with sorting; P7 dropped with D77 (closes A1's OA-2) | ROW-9, MEA-8, MEA-9, 8.5 |
| D79 | 21-11-2026 | macOS deferred until there is an Apple Developer Program membership, a Developer ID certificate and a Mac to build on | 1 |
| D80 | 21-11-2026 | This spec replaces A1 and the UX changes note, and is merged into Feature Spec v2.0 and Technical Spec v1.0 after development | 1, 12 |
| P8 | Proposed | When a result is sorted by a Number or Date group column, "(Not a number)" or "(Not a date)" follows the values and "(Null)" comes last, in both directions | TXT-11 |

The confirmed proposals, for reference: P1, column changes redraw the Rows grid with no Run; P3, names trimmed, up to 100 characters, unique ignoring case, a clashing default name gets " (2)"; P4, each run stores its output headers at commit; P5, parts written as .partial and renamed at the end; P6, extract and split alternate per run.

## 12. Changes to existing docs

After development, Feature Spec v2.0 needs 26 updates, Technical Spec v1.0 needs 17, and the UX Context and canvas need the screen changes below. Until then this spec and its test cases file are the source for the Feature-Updates branch.

### 12.1 Feature Spec v2.0

| v2.0 item | Change |
| --- | --- |
| Analysis note "Not included: … a raw-row browsing grid" | Remove "a raw-row browsing grid" |
| Out of scope | "Charts, calculated columns, drill-down to rows, a raw-row browsing grid" becomes "Charts, calculated columns, drill-down from a summary row to its rows". "macOS and Linux builds" stays, noting D79 |
| UX-3 New template | The Rules step stays for a template without checks, with Yes / No at its top (NCK-2); replaces the copy's "skipped" |
| UX-8 New run | Five steps for every template: Files, Mapping, Validate or Load, Outputs, Commit (NCK-6); replaces the copy's "four steps" |
| UX-10 Analysis | Adds the Rows view (ROW) |
| F2 Monthly run | A template without checks goes Mapping → Load → Outputs |
| TPL-10 | As NCK-1 and NCK-11 |
| IN-5 Sheets to read | Adds the per-file choice in a run (SHT) |
| IN-11 File list | Adds Choose sheets… on each Excel file (SHT-2) |
| IN-15 Files in error | Sheet not found: Choose sheets or Exclude file; Header not found: Exclude, or fix and Re-check (SHT-6, SHT-8) |
| MAP-10, MAP-14 | Extended to Date columns (TXT-1) |
| VR-9 | As NCK-4 to NCK-7 and NCK-13 |
| RUN-15 | Adds Date columns (NCK-9) |
| VAL-1 to VAL-9 | Text cells as TXT-13 |
| ANA-4 Filters | Adds Is not a date; Date filters match dates only (TXT-7) |
| ANA-5 Group levels | Adds "(Not a date)" (TXT-10) |
| ANA-6 Measures | Replaced by MEA-1 to MEA-11 |
| ANA-7 Result | Measure column order and names follow MEA-6 to MEA-8; text groups sort as TXT-11 |
| DO-1, DO-3, DO-6 | Measures follow MEA; relative dates ignore text (TXT-12); committed runs keep their output headers (MEA-9) |
| DO-7, ANA-9, ISS-3 | Exports over 1,000,000 rows are split (EXP-8) |
| EXP-1, EXP-3 | Adds the Rows view and left-out rows; a Number or Date cell with text exports its text (TXT-4) |
| EXP-4, EXP-7 | The overwrite confirmation lists every part; Cancel deletes every part; the banner names the file count (EXP-10, EXP-14) |
| New | EXP-8 to EXP-14 |
| Performance targets | Adds PERF-7 to PERF-14 |
| Decisions | Copy's D38 to D41 become D61 to D64; adds D38 to D60 and D65 to D80 |
| SEC-4 | "Temporary files live in the user's temp folder and are deleted when the operation ends, except the database engine's own spill files still in use, which it deletes itself; the folder is emptied completely at close and start-up" (BUG-1) |

### 12.2 Technical Spec v1.0

| Section | Change |
| --- | --- |
| T28, T29 | Extended to Date columns; adds Is not a date and "(Not a date)"; Count distinct not offered on Number columns and counts dates only on Date columns |
| T30 | Run steps with Load; reading progress shows on the Load step (closes "left to the UI design spec") |
| Query layer | New entry points and the rows\_view temporary table (8.1, 8.7) |
| Storage | Text companions on Date columns (8.2) |
| Ingestion, 1 and 2 | Per-file sheet choice (8.3) |
| Ingestion, 4. Convert | Date text companion; data.parquet written in stored order with preserve\_insertion\_order on (8.3, 8.7) |
| Validation | Rule meanings for text cells (TXT-13, 8.8) |
| Query layer, definition to SQL | As 8.8 |
| Saved analyses (V3-2) | JSON example uses version-2 measures; ops not\_number and not\_date |
| Outputs, default outputs | Internal column names g1…, m1…; headers from run\_output.headers |
| Exports | The pipeline in 8.5 and the splitter in 8.6 replace the single .part flow; adds the size estimate |
| Catalogue tables | As 8.4 |
| T23 | Adds: the Rows card counts every row |
| DuckDB settings, spill files, SEC-4 row | As BUG-1 |
| Tests | Adds: stored-order export, splitter boundaries with quoted line breaks, part names, disk check, headers kept after a rename, Rows view paging, sheet choice, Date text companions, templates without checks |
| No leftovers test | Allows the open connection's spill files (AC-BUG-1b) |
| Performance suite | Adds PERF-7 to PERF-14 |

### 12.3 UX Context, canvas and test cases

| Item | Change |
| --- | --- |
| UX Context | C3 (Rules step with Yes / No), C4 (Settings), C5 step 1 (Choose sheets) and Load step, A1 (Rows view, measures, filters), Export dialog; screen index adds 4.1b, 4.1c, 6.4, 6.5, 6.6, 7.9, 2.4b, 4.3b, 4.5b |
| Canvas: change | 6.4 footer wording and no sort arrows; Number measure cards without Distinct on 6.2, 3.2 and 2.5; Date columns added on 2.4b, 4.3b and 4.5b; Rows at the top of the Add column list |
| Canvas: to draw | 6.6 Date filter; 4.3b while reading; 3.3 rules not in use; 3.1 and 5.1 for a run without checks; Rows view states (2.4); the header rename box; the Add column list; the disk-space message; the split success banner |
| Test cases | Sankalan — Test Cases A2 (live sheet, copy claude/Sankalan\_Test\_Cases\_A2.md): 79 test cases, one per criterion in section 10 (71) and per target PERF-7 to PERF-14 (8), with fixtures F-A2-01 to F-A2-11 and screen coverage; merged into the main test cases after development |

## 13. Bug fix, risks and open items

One item is open: confirm P8. The largest risk is that stored-order exports and the Rows grid depend on DuckDB keeping a single file's row order, which a test checks on every build.

### 13.1 BUG-1 · Temp clean-up deletes DuckDB's live spill files (SEC-4)

Found 20-11-2026 while building full-size test data. It must be fixed on this branch; it is independent of the features and can hit any large load or analysis.

| Item | Detail |
| --- | --- |
| Symptom | A long operation fails with "Failed to delete file …\\Temp\\Sankalan\\duckdb\_temp\_\<pid>\_…storage….tmp". Seen at a run's commit during a 2,500,000-row-per-run load |
| Cause | After every Job, Storage empties %TEMP%\\Sankalan (SEC-4). That also deletes the spill storage the open DuckDB connection still uses (Windows allows the delete). DuckDB's next use of those blocks fails |
| When it happens | Whenever data spilled to disk in one Job is still held for the next: a large load, a large analysis result kept between Jobs, a large temporary table such as rows\_view |
| Fix | After a Job, delete everything in %TEMP%\\Sankalan except the open connection's own spill files (duckdb\_temp\_\<pid>\_…); DuckDB deletes those as blocks free and when the connection closes. Closing the data folder and start-up still empty the folder completely |
| Spec change | SEC-4 as in 12.1; Technical Spec v1.0 as in 12.2 |

Accepted by AC-BUG-1a to AC-BUG-1c (10.8).

### 13.2 Open items

| # | Question | Item |
| --- | --- | --- |
| OA-5 | Confirm P8: in a sorted result, "(Not a number)" or "(Not a date)" follows the values and "(Null)" comes last, ascending and descending | TXT-11 |

A1's OA-1 to OA-4 are closed by D77, D78, D71 and D76.

### 13.3 Risks

| # | Risk | Impact | Plan |
| --- | --- | --- | --- |
| R7 | **Retired** by Technical Spec A2 T32 (Convert sorts; reads order by `_src_file, _src_row`). Stored order relied on DuckDB keeping a single file's row order in a filtered scan and LIMIT (8.7) | Grid and exports out of load order | AC-ROW-11b and AC-ROW-12b on every build. Fallback: ORDER BY \_src\_file, \_src\_sheet, \_src\_row per run, a 10M-row sort that may spill |
| R8 | A split export needs working space of up to one run's share; a single-run export needs about twice its size free | Exports blocked on full laptops | The EXP-13 check states the need up front; choosing another drive is offered |
| R9 | Splitter mistakes on quoted line breaks near a part boundary | A record cut across two parts | AC-EXP-9b with values planted at the boundary |
| R10 | A 120M-row export is about 24 GB at an assumed 200 bytes a row, so PERF-12 depends on SSD write speed | PERF-12 missed on slower disks | Measured in the release suite; reported, not blocking (T4) |
| R11 | A CSV whose text dates use another format than the template's (e.g. 2026-11-01 against DD-MM-YYYY) now loads every date as text instead of failing | Without checks, a whole Date column becomes text with only a count to show it | The Load and Commit counts (NCK-8, NCK-9) and the wizard's type note (6.2) make it visible; with checks, Is a date reports every row |
| R12 | One dialog per file when a client renames sheets in all files of a month | Many dialogs per run (10 or more) | Accepted for now (D65); the deferred rule in 5.3 removes it later |
