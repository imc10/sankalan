# Sankalan — Test Cases (snapshot)

Snapshot of the "Sankalan Test Cases" sheet (https://claude.ai/artifact/GzEbdCbadKjdHdG9oTXEuF), taken 16-11-2026; A2 (Feature-Updates) cases added 22-11-2026 from Feature Spec A2 §9–§10 and Technical Spec A2 §15 (the live sheet doesn't have them yet). The live sheet is the source of truth and holds test status; this copy is for reading during development. Expected figures here are the acceptance oracle for engine tests.

## Read me

Sankalan final version: test cases for a local Windows deployment  
Built 16-11-2026 from Sankalan_UX_Context.md, Sankalan_UI_Screens.md (30 screens) and the canvas; expected results include the changes in Technical Spec v1.0 (decimals, left-out rows, Input = Loaded + Left out, Export left-out rows, Run IDs never reused).  
A2 cases added 22-11-2026: one per acceptance criterion of Feature Spec A2 §10.2–10.8 (71), one per performance target PERF-7 to PERF-14 (8, named A2-PERF-07 to A2-PERF-14 because PERF-07 and PERF-08 are already used), and 3 from Technical Spec A2 §15.3 (A2-EXP-13b, A2-CAT-01, A2-SHT-10). Where Technical Spec A2 §15.1 corrects Feature Spec A2 (T38, T39, T45, T46, T47, T33), the expected result follows the Technical Spec and the Spec field names the T-number. Existing cases changed by A2 (expected figures unchanged): RUNF-07, C3-13, C3-14, RUNV-12, A1-03, A1-04, A1-05, A1-12, EXP-08, PERF-01, PERF-02.  
How to run  
1. Test laptop: Windows 11 (and Windows 10 22H2 for DEP-02), 64-bit, 16 GB RAM, SSD, 4+ cores, display 1366×768 at 100% unless a case says otherwise. Sign in as a standard user (not an administrator).  
2. Copy the fixture pack (Fixtures tab) to C:\SankalanTest\Fixtures. F07 must be openable in Excel; F06's password is Sankalan@123.  
3. Run the phases in order: the TPL-A runs build on each other and many expected figures assume the exact run sequence below.  
4. Set Status (Not run / Pass / Fail / Blocked / N/A), Build, Tester and Run date for each case. Put the defect ID and what you saw in Notes.  
5. Where an expected result says "record", the spec does not fix the behaviour: write down what the app does and raise it as a spec question if it looks wrong.  
Phases  
P1 Install · DEP-01 to DEP-06, GEN-01 to GEN-03, C1-01 to C1-08  
P2 Templates · C3-01 to C3-22 (creates TPL-A in Acme Traders; TPL-C, TPL-D and the 1252 template in Bharat Foods), C2-01, C2-04, C2-05  
P3 TPL-A runs · RUNF-01 to RUNF-12 and the run sequence R-0001 to R-0006 below, with the Validate, Outputs and Commit cases at each run; C4 cases at the points stated; GEN-04 to GEN-07  
P4 Run detail and export · C6-01 to C6-08, C6-10, EXP-01 to EXP-07, CONV-01 to CONV-05, DEP-07 to DEP-09  
P5 Analysis · A1-01 to A1-10, A1-13, A1-14, A0-01 to A0-05; then C6-09 (delete R-0006), RUNC-08 (R-0007), C2-06 to C2-08, C1-09 to C1-11  
P6 Last · C4-16 (removes GSTIN), DEP-10 to DEP-13  
P7 Performance laptop · PERF-01 to PERF-08, then RUNV-12, RUNO-06, A1-11, A1-12, A1-15, EXP-08, SH-01 to SH-04 (they need the 10M-row data)  
P8 A2 features · Setup: create TPL-R from F-A2-01 and commit R-0001 to R-0003 (A2-BUG-1c, run sequence below). Then, in this order: A2-ROW-01 to A2-ROW-S2 · A2-MEA-01 to A2-MEA-11 (A2-MEA-09 commits TPL-R R-0004) · A2-EXP-08a to A2-EXP-14c (A2-EXP-08a uses the TPL-P run from P7; A2-EXP-13, A2-EXP-13b and A2-EXP-14b need the LOW-DISK setup) · A2-SHT-01 to A2-SHT-10 (create TPL-S first) · A2-TXT-01 to A2-TXT-10 · A2-NCK-01 to A2-NCK-10 (A2-NCK-01 creates TPL-N; A2-NCK-07 commits TPL-R R-0005) · A2-BUG-1a to A2-BUG-1c · A2-CAT-01  
P9 A2 performance · A2-PERF-07 to A2-PERF-14 on the performance laptop, with 12 committed 10M-row runs in TPL-R's shape (built by tools\perf\build_a2_data.py). The same targets are measured by tests\perf\test_a2_perf.py on the development PC with DuckDB pinned to 4 threads and 8 GB and 3 reader workers; the laptop run is a manual release step (T4)  
Any time · FIT-01 to FIT-04 once TPL-A has R-0001 to R-0005; C1-10 and RUNF-14 need the LOW-DISK setup  
TPL-A run sequence · File · Rows loaded · Rows stored after · Key cases  
R-0001 · F02 Sales_Oct.xlsx · 5,000 · 5,000 · RUNF-02, RUNF-12, RUNV-01, RUNO-01, RUNC-01, RUNC-04, RUNC-05  
R-0002 · F03 Sales_Nov.xlsx · 4,000 · 9,000 · RUNF-04, RUNV-02, RUNC-03  
(discarded) · F04 Sales_Errors.xlsx · — · 9,000 · RUNV-09, then RUNC-07  
R-0003 · F04 Sales_Errors.xlsx · 1,937 (63 left out) · 10,937 · RUNV-03 to RUNV-07, RUNV-13, RUNO-03, RUNC-02, RUNC-06  
R-0004 · F08 Sales_Renamed_Headers.xlsx · 1,000 · 11,937 · RUNM-01 to RUNM-05, RUNV-08, RUNO-04; then C2-06, C4-06, C4-11  
(discarded) · F12 Sales_ManyIssues.csv · — · 11,937 · RUNV-06  
R-0005 · F13 Sales_Dec_NewCol.xlsx · 3,000 · 14,937 · RUNM-07, RUNV-10  
R-0006 · F14 Sales_NoDates.xlsx · 500 · 15,437 · RUNO-05; deleted in C6-09 (back to 14,937)  
R-0007 · F15 Sales_Jan.xlsx · 2,000 · 16,937 · RUNC-08  
Reference templates  
TPL-A Sales Register · Client Acme Traders. Sample F01. Sheets: by name "Sales". Columns: Invoice No (Text) · Invoice Date (Date, Excel dates) · Customer (Text) · GSTIN (Text) · State (Text) · Taxable Value (Number, 2 decimals, totals check ticked) · GST Rate (Number, 0 decimals) · Tax Amount (Number, 2 decimals, totals check ticked). Branch (Text) is added in R-0005.  
TPL-A rule set · Invoice No: Not blank (Error), Character pattern AAA-99999 (Error), Unique within the run (Error). Invoice Date: Is a date (auto, Error), Date range 01-04-2026 to 31-03-2027 (Warning). Customer: Not blank (Warning; changed to Error in RUNV-10). GSTIN: Text length exactly 15 (Error). State: Allowed values Maharashtra, Gujarat, Karnataka, Delhi (Warning). Taxable Value: Is a number (auto, Error), Number range not negative (Error). GST Rate: Is a number (auto, Error), Allowed values 0, 5, 12, 18, 28 (Error). Tax Amount: Is a number (auto, Error).  
TPL-A outputs · DO1 "State-wise sales": group State; Sum Taxable Value as "Taxable", Sum Tax Amount as "Tax", Count Invoice No as "Invoices". DO2 "Latest month by GST rate": filter Invoice Date = latest month in this run; group Invoice Date (Month) › GST Rate; Sum Taxable Value; Show subtotals on.  
TPL-C Conversion check · Client Bharat Foods. Sample F17 (CSV). Columns: Case (Text) · Amount (Number, 2 decimals) · Amount0 (Number, 0 decimals) · Doc Date (Date, DD-MM-YYYY) · Due Date (Date, DD/MM/YYYY) · Code (Text). Is a number / Is a date set to Warning. No outputs. Sheets: first visible sheet (for F19).  
TPL-D Regional Sales · Client Bharat Foods. Sample F16. Sheets: all visible sheets. TPL-A columns, no rules beyond the automatic ones, no outputs.  
TPL-P Perf 20 col · Client Perf Test. Sample P01 (20 columns, see Fixtures). Rules: Invoice No Not blank and Unique (Error); GSTIN Text length 15 (Error); State Allowed values (Warning); Taxable Value not negative (Error); GST Rate Allowed values (Error). Totals check on Taxable Value and Tax Amount. No outputs (one is added only for RUNO-06).  
TPL-R Sales Register R (A2, with checks) · Client Rao & Co. Sample: TPLR_R1_Sales.xlsx from F-A2-01. Sheets: all visible sheets. 20 columns (Feature Spec A2 §10.1: 8 Text, 8 Number with 2 decimals, 4 Date), in this order: Invoice No (Text) · Invoice Date (Date) · Customer (Text) · GSTIN (Text) · State (Text) · Taxable Value (Number, totals check ticked) · CGST · SGST · IGST · Cess · Discount · Freight (Number) · Invoice Value (Number, totals check ticked) · Due Date · Dispatch Date · Payment Date (Date) · Branch · HSN Code · Salesperson · Narration (Text). Date columns read Excel dates and text dates DD-MM-YYYY. Place of Supply (Text) is added in R-0002 (21 columns in all).  
TPL-R rule set · Is a number on Taxable Value and Is a date on Invoice Date set to **Warning**, so text rows load (the other automatic type rules stay Error). Invoice No: Character pattern INV-99999999 (Error). Default output "Latest month by State": filter Invoice Date = latest month in this run; group State; measures Rows (Count) and Taxable Value (Sum), headers "Rows · Count" and "Taxable Value · Sum".  
TPL-R run sequence · Files · Rows loaded · Rows stored after · Key cases  
R-0001 · F-A2-01 (October 2026) · 2,500,000 · 2,500,000 · A2-TXT-01 to A2-TXT-05, A2-TXT-08, A2-ROW-14  
R-0002 · F-A2-02 (November 2026): Place of Supply, Add as new column (Text); 63 rows fail Character pattern, Continue despite errors… with reason "Client confirmed errors; revised file next month" · 2,499,937 (63 left out) · 4,999,937 · A2-ROW-13, A2-TXT-04, A2-TXT-05, A2-TXT-09  
R-0003 · F-A2-03 (December 2026): Invoice No in TPLR_R3_NoInvoiceNo.csv, Leave as null (MAP-6) · 2,500,000 (400,000 without Invoice No) · 7,499,937 · A2-ROW-10, A2-MEA-10, A2-EXP-09a, A2-EXP-12  
(discarded) · F-A2-01 again, with run-only rules · — · 7,499,937 · A2-TXT-07  
R-0004 · F-A2-01 again (duplicate warning: Load anyway; Place of Supply: Leave as null) · 2,500,000 · 9,999,937 · A2-MEA-09, A2-NCK-10  
R-0005 · F-A2-01 again, loaded without checks (Load anyway; Place of Supply: Leave as null) · 2,500,000 · 12,499,937 · A2-NCK-07, A2-NCK-10  
TPL-N Purchase Register N (A2, without checks) · Client Rao & Co. Sample F-A2-04 (CSV). TPL-R's 20 columns (no Place of Supply), types and totals ticks as TPL-R. Check data before loading = **No** (set in A2-NCK-01), so no rules. Default output "Taxable by State": group State; Rows (Count), Taxable Value (Sum).  
TPL-N run sequence · R-0001 · F-A2-04 + F-A2-05 · Rows read 1,000,010, blank rows skipped 10, rows loaded 1,000,000 (2,000 repeated rows included) · A2-NCK-02, A2-NCK-04, A2-NCK-06, A2-NCK-08  
TPL-S Branch Sales (A2, sheet files) · Client Acme Traders. Sample F-A2-08 (West). Sheets to read: by name, "Sales" and "Sales Returns". TPL-A columns, only the automatic rules, no default outputs. TPL-S R-0001 · F-A2-06 (sheets chosen: Sales Nov, Returns Nov) + F-A2-08 (by the rule) · 470 rows · A2-SHT-07, A2-SHT-08  
Full and small sizes · F-A2-01 to F-A2-05 come in a full size (the figures in these cases) and a small size for the automated normal suite (Fixtures tab). The automated tests check the same relations on the small sets; the full-size figures (7,499,937 rows searched, 400,000, 1,510, 305, 6,802, 120) are checked by the slow tests.  
LOW-DISK setup · Needs admin once: Disk Management > Create VHD, 30 GB, NTFS, letter V:. Move the data folder to V:\Sankalan with Change…. Fill with: fsutil file createnew V:\filler.bin <bytes> so free space is below one 10M-row load (PERF-08). Remove filler afterwards.  
Behaviour the spec leaves open (cases say "record")  
C1-04 client-name case rule · RUNF-06 message wording (UX doc vs Tech spec) · RUNV-02 Rows read with blank rows · SH-02 how a second long job is refused · C2-08 whether the duplicate-contents check spans templates · RUNC-10 needs a fault-injection build  
A2 · A2-EXP-09b, A2-EXP-14b and A2-BUG-1a need a test build (automated)  

## Test cases

### DEP-01 — Install per user without admin rights

- **Area:** Deployment · **Priority:** P1 · **Screen:** — · **Spec:** NF-2, UI-4, NF-6, T3 · **Type:** Deployment
- **Preconditions:** Clean Windows 11 laptop (16 GB, SSD). Tester signed in as a STANDARD user (not an administrator). Sankalan installer .exe copied to Downloads.
- **Steps:**

    1. Double-click the installer.
    2. Complete the installer with default options.
    3. Open File Explorer at %LOCALAPPDATA%\Programs\Sankalan.
    4. Open the Start menu and search "Sankalan".

- **Expected:** No UAC / administrator prompt at any point. Installer windows show the name "Sankalan". App files are in %LOCALAPPDATA%\Programs\Sankalan (nothing written to C:\Program Files). A Start menu entry "Sankalan" exists.

### DEP-02 — Install on Windows 10

- **Area:** Deployment · **Priority:** P1 · **Screen:** — · **Spec:** ENV-2, NF-1 · **Type:** Deployment
- **Preconditions:** Clean Windows 10 22H2 64-bit laptop, standard user.
- **Steps:**

    1. Run DEP-01 steps on Windows 10.
    2. Launch Sankalan and run the smoke set: C1-02, C3-18, RUNF-01, RUNF-02, RUNV-01, RUNO-01, RUNC-01 and RUNC-05 with F02.

- **Expected:** Install and smoke set pass on Windows 10 exactly as on Windows 11.

### DEP-03 — First launch creates the data folder

- **Area:** Deployment · **Priority:** P1 · **Screen:** 1.1 · **Spec:** T25, UX-11, TPL-5 · **Type:** Deployment
- **Preconditions:** DEP-01 done. Sankalan never started on this user profile.
- **Steps:**

    1. Start Sankalan from the Start menu.
    2. In Explorer, open %LOCALAPPDATA%\Sankalan.
    3. Open settings.json in Notepad.

- **Expected:** App opens on Clients (C1). %LOCALAPPDATA%\Sankalan\Data exists and contains catalogue.duckdb. settings.json holds the data folder path %LOCALAPPDATA%\Sankalan\Data. A logs folder exists under %LOCALAPPDATA%\Sankalan.

### DEP-04 — Title bar and no publisher name

- **Area:** Deployment · **Priority:** P2 · **Screen:** All · **Spec:** UI-4, NF-6, UX-11 · **Type:** Deployment
- **Preconditions:** App running.
- **Steps:**

    1. Read the window title bar.
    2. Open every screen and dialog in the Coverage tab and look for "Ollyver", "Vyazen" or any company name.
    3. Open App settings (gear).

- **Expected:** Title bar reads exactly "Sankalan". No publisher or company name appears on any screen or dialog. App settings shows only the data folder (with Change…) and the app version.

### DEP-05 — Only one copy of the app runs

- **Area:** Deployment · **Priority:** P2 · **Screen:** — · **Spec:** Tech spec: One copy of the app · **Type:** Deployment
- **Preconditions:** App running and minimised.
- **Steps:**

    1. Start Sankalan again from the Start menu.
    2. Open Task Manager > Details and count Sankalan.exe processes while no run is in progress.

- **Expected:** No second window opens; the existing window comes to the front and is restored. Exactly one Sankalan.exe process (reader worker processes only appear during file reading).

### DEP-06 — App settings shows data folder and version

- **Area:** Deployment · **Priority:** P2 · **Screen:** Not drawn · **Spec:** UX-11 · **Type:** Deployment
- **Preconditions:** App running.
- **Steps:**

    1. Click the gear at the bottom of the left rail.

- **Expected:** App settings dialog shows the data folder path (%LOCALAPPDATA%\Sankalan\Data) with a Change… button, and the app version matching the installer build number.

### DEP-07 — Move the data folder with Change…

- **Area:** Deployment · **Priority:** P1 · **Screen:** Not drawn · **Spec:** UX-11, UI-5, T25 · **Type:** Deployment
- **Preconditions:** TPL-A has runs R-0001 to R-0003. A second local drive or folder D:\SankalanData (empty) exists.
- **Steps:**

    1. App settings > Change… > pick D:\SankalanData.
    2. Watch the progress.
    3. When done, open C1, C4 Runs for Sales Register and the A0 list.
    4. Check the old and new folders in Explorer.
    5. Open settings.json.

- **Expected:** A progress panel shows stage, progress and elapsed time; the window stays responsive. Afterwards: all clients, templates, runs, rows stored and saved analyses are unchanged. New folder holds catalogue.duckdb and t\…; the old %LOCALAPPDATA%\Sankalan\Data is deleted. settings.json points to D:\SankalanData.

### DEP-08 — Change… refuses network paths

- **Area:** Deployment · **Priority:** P2 · **Screen:** Not drawn · **Spec:** ENV-5, T25 · **Type:** Deployment
- **Preconditions:** A network share is reachable (e.g. \\fileserver\share) and mapped as Z:.
- **Steps:**

    1. App settings > Change… > type \\fileserver\share\Sankalan.
    2. Repeat with Z:\Sankalan.

- **Expected:** Both are refused with a plain message that network folders can't be used. The data folder is unchanged.

### DEP-09 — Change… warns for a OneDrive folder

- **Area:** Deployment · **Priority:** P3 · **Screen:** Not drawn · **Spec:** T25, R6 · **Type:** Deployment
- **Preconditions:** OneDrive signed in on the laptop.
- **Steps:**

    1. App settings > Change… > pick a folder inside %USERPROFILE%\OneDrive.

- **Expected:** A warning about synced folders appears before the move; the user can cancel and the data folder stays unchanged.

### DEP-10 — Update over an older version keeps data

- **Area:** Deployment · **Priority:** P1 · **Screen:** — · **Spec:** SEC-6, T10 · **Type:** Deployment
- **Preconditions:** Older build installed with at least TPL-A and 3 runs. Newer installer available.
- **Steps:**

    1. Close Sankalan.
    2. Run the newer installer.
    3. Start Sankalan; open App settings; open C1, C4 and a run's Outputs tab.

- **Expected:** Install completes without admin rights. App settings shows the new version. All clients, templates, runs, outputs and saved analyses are present and open. catalogue-backups holds a copy taken at this start.

### DEP-11 — Uninstall and keep the data folder

- **Area:** Deployment · **Priority:** P1 · **Screen:** — · **Spec:** T26, SEC-6 · **Type:** Deployment
- **Preconditions:** App installed with data. App closed.
- **Steps:**

    1. Settings > Apps > Sankalan > Uninstall.
    2. When asked whether to delete the data folder, choose to keep it.
    3. Check %LOCALAPPDATA%\Programs\Sankalan and the data folder.
    4. Reinstall and start Sankalan.

- **Expected:** The uninstaller asks about the data folder. App folder removed; data folder untouched. After reinstall, all clients and runs are shown again.

### DEP-12 — Uninstall and delete the data folder

- **Area:** Deployment · **Priority:** P2 · **Screen:** — · **Spec:** T26 · **Type:** Deployment
- **Preconditions:** App installed with data. App closed.
- **Steps:**

    1. Uninstall Sankalan.
    2. Choose to delete the data folder.
    3. Check %LOCALAPPDATA%\Sankalan.

- **Expected:** App folder and data folder are both removed.

### DEP-13 — Full flow with no network

- **Area:** Deployment · **Priority:** P2 · **Screen:** — · **Spec:** ENV-6, SEC-1 · **Type:** Deployment
- **Preconditions:** Laptop in Airplane mode (Wi-Fi and Ethernet off).
- **Steps:**

    1. Start Sankalan.
    2. Create a client, a template from F01, and commit a run with F02.
    3. Run an analysis and export it.

- **Expected:** Everything works with no network; no error or message mentions connectivity.

### GEN-01 — Left rail

- **Area:** App-wide · **Priority:** P2 · **Screen:** 1.1, 6.1 · **Spec:** UX §3 · **Type:** Functional
- **Preconditions:** App running.
- **Steps:**

    1. Look at the left edge of the window.
    2. Click Clients, then Analysis, then the gear.

- **Expected:** A 64 px rail with Clients and Analysis at the top and a gear at the bottom. Clients opens C1, Analysis opens A0, the gear opens App settings. The selected item is highlighted in teal.

### GEN-02 — Light look only, even with Windows in dark mode

- **Area:** App-wide · **Priority:** P2 · **Screen:** All · **Spec:** UI-1, UI-3 · **Type:** Functional
- **Preconditions:** App running.
- **Steps:**

    1. Windows Settings > Personalisation > Colours > choose Dark.
    2. Return to Sankalan and open C1, C4, C5 step 3 and A1.

- **Expected:** Sankalan stays in its light look. Primary buttons use teal #0E6B6B; selected/tinted areas use #E3F1F0 with text #0A4F4F. Error text #B42318, warning #B54708, success #067647 (check with a colour picker on a screenshot).

### GEN-03 — Bundled fonts and monogram

- **Area:** App-wide · **Priority:** P3 · **Screen:** 1.1 · **Spec:** UI-1 · **Type:** Functional
- **Preconditions:** IBM Plex Sans NOT installed in Windows (check C:\Windows\Fonts and %LOCALAPPDATA%\Microsoft\Windows\Fonts).
- **Steps:**

    1. Open C1 and C4 Runs.
    2. Compare the digits in the Rows column across rows.
    3. Look at the app mark.

- **Expected:** Text renders in IBM Plex Sans. Digits in number columns line up vertically (tabular figures). The app mark shows the Devanagari "सं" on a teal rounded square, not boxes or question marks.

### GEN-04 — Number and date formats ignore Windows region

- **Area:** App-wide · **Priority:** P1 · **Screen:** 1.1, 3.1, 5.1 · **Spec:** UI-7 · **Type:** Functional
- **Preconditions:** TPL-A with R-0001 committed.
- **Steps:**

    1. Windows region = English (India). Open C1, C4 Runs and R-0001 Outputs.
    2. Change region to English (United States) and restart Sankalan; repeat.
    3. Change region to German (Germany); repeat.

- **Expected:** In every case numbers show international grouping (7,536,875.00; 5,000) and dates DD-MM-YYYY (e.g. Loaded on 16-11-2026). No screen switches to 75,36,875 or MM/DD/YYYY or 7.536.875,00.

### GEN-05 — Grid density and spacing

- **Area:** App-wide · **Priority:** P3 · **Screen:** 1.1, 3.1 · **Spec:** UX §2 · **Type:** Functional
- **Preconditions:** Display at 1366×768, 100% scaling. TPL-A with runs.
- **Steps:**

    1. Take a screenshot of C1 and C4 Runs.
    2. Measure grid row height, grid header height, panel padding and gap between sections in an image editor.

- **Expected:** Grid rows and grid header rows are 40 px. Grid text 13 px, body text 14 px. 24 px between sections, 16 px panel padding, 8–12 px between controls.

### GEN-06 — Breadcrumbs and one level per screen

- **Area:** App-wide · **Priority:** P2 · **Screen:** 1.2, 3.1, 5.1 · **Spec:** UX §3 · **Type:** Functional
- **Preconditions:** TPL-A with R-0001.
- **Steps:**

    1. Navigate C1 > Acme Traders > Sales Register > R-0001.
    2. On the Run screen click each breadcrumb part in turn.

- **Expected:** Each screen shows only one level (clients, a client's templates, a template's runs, one run). Breadcrumb on C6 reads Clients › Acme Traders › Sales Register › R-0001 and each part opens that level.

### GEN-07 — Data messages name file, sheet, row and column

- **Area:** App-wide · **Priority:** P1 · **Screen:** 4.3 · **Spec:** UI-6, NF-5 · **Type:** Functional
- **Preconditions:** RUNV-04 in progress (F04 at Validate).
- **Steps:**

    1. In the issue grid, find source row 214.
    2. Export the issue list and find row 214.

- **Expected:** Message reads exactly: "Sales_Errors.xlsx, Sales, row 214, Taxable Value: value is not a number".

### C1-01 — Empty state

- **Area:** C1 Clients · **Priority:** P1 · **Screen:** Not drawn · **Spec:** UX C1 · **Type:** Functional
- **Preconditions:** Fresh install (DEP-03).
- **Steps:**

    1. Open Clients.

- **Expected:** Grid area shows: "No clients yet. Add a client, then set up its first template from a sample file." with a New client button. Footer reads "Data stored: 0 rows · 0 GB · N GB free on C:".

### C1-02 — Create a client

- **Area:** C1 Clients · **Priority:** P1 · **Screen:** 1.1 · **Spec:** TPL-2 · **Type:** Functional
- **Preconditions:** C1-01.
- **Steps:**

    1. Click New client.
    2. Enter "Acme Traders" and save.

- **Expected:** Acme Traders appears in the grid: Templates 0, Runs 0, Rows stored 0, Last loaded on blank. The client has a name field only.

### C1-03 — Client name is required

- **Area:** C1 Clients · **Priority:** P2 · **Screen:** 1.1 · **Spec:** TPL-2 · **Type:** Functional
- **Preconditions:** C1 open.
- **Steps:**

    1. New client > leave name empty > try to save.
    2. Enter only spaces > try to save.

- **Expected:** Save is refused in both cases with a message that a name is required; no client is created.

### C1-04 — Client name must be unique

- **Area:** C1 Clients · **Priority:** P1 · **Screen:** 1.1 · **Spec:** TPL-2 · **Type:** Functional
- **Preconditions:** Acme Traders exists.
- **Steps:**

    1. New client > "Acme Traders" > save.
    2. New client > "acme traders" > save.
    3. Rename Bharat Foods (after C1-05) to "Acme Traders".

- **Expected:** Steps 1 and 3 are refused with a message that the name is in use. Step 2: record whether it is accepted (case rule is not stated in the spec; raise a spec question if accepted).

### C1-05 — Sorting

- **Area:** C1 Clients · **Priority:** P2 · **Screen:** 1.1 · **Spec:** UX C1 · **Type:** Functional
- **Preconditions:** Create clients Bharat Foods, Zenith Exports, Chopra & Co in that order.
- **Steps:**

    1. Open C1.
    2. Click each column header twice.

- **Expected:** Default order A–Z: Acme Traders, Bharat Foods, Chopra & Co, Zenith Exports. Each header sorts ascending then descending; numbers sort numerically and dates by date.

### C1-06 — Search by client name

- **Area:** C1 Clients · **Priority:** P2 · **Screen:** 1.1 · **Spec:** UX C1 · **Type:** Functional
- **Preconditions:** C1-05.
- **Steps:**

    1. Type "bha" in search.
    2. Type "xyz".
    3. Clear search.

- **Expected:** 1: only Bharat Foods. 2: no rows (with a no-match message). 3: all 4 clients.

### C1-07 — Rename a client

- **Area:** C1 Clients · **Priority:** P2 · **Screen:** 1.1 · **Spec:** TPL-2, Tech spec Storage · **Type:** Functional
- **Preconditions:** Acme Traders has TPL-A with runs and saved analysis AN-1 (A1-14).
- **Steps:**

    1. … > Rename > "Acme Traders Pvt".
    2. Check C2 breadcrumb, A0 Client column and the data folder t\ subfolders.
    3. Rename back to "Acme Traders".

- **Expected:** Name changes everywhere it is shown. No folder under the data folder is renamed or moved (folders are named by internal ID).

### C1-08 — Open a client

- **Area:** C1 Clients · **Priority:** P1 · **Screen:** 1.1 · **Spec:** UX C1 · **Type:** Functional
- **Preconditions:** Acme Traders exists.
- **Steps:**

    1. Click the Acme Traders row.

- **Expected:** Client screen C2 opens for Acme Traders.

### C1-09 — Grid figures and storage footer

- **Area:** C1 Clients · **Priority:** P1 · **Screen:** 1.1 · **Spec:** UX-1, Tech spec Figures on screen · **Type:** Functional
- **Preconditions:** TPL-A runs R-0001 to R-0003 committed; no other runs exist.
- **Steps:**

    1. Open C1.
    2. Compare the footer with Explorer: data folder size (Properties) and C: free space.

- **Expected:** Acme Traders row: Templates 1, Runs 3, Rows stored 10,937, Last loaded on = R-0003's date and time. Footer: "Data stored: 10,937 rows · X GB · Y GB free on C:" where X matches the data folder size and Y the C: free space (to 0.1 GB).

### C1-10 — Footer turns amber when disk is low

- **Area:** C1 Clients · **Priority:** P2 · **Screen:** 1.1 · **Spec:** UX-1 · **Type:** Functional
- **Preconditions:** LOW-DISK setup (Read me): data folder on a VHD with free space below the size of one 10M-row load (from PERF-08).
- **Steps:**

    1. Open C1.

- **Expected:** Footer text is amber (#B54708) and states the free space.

### C1-11 — Delete a client

- **Area:** C1 Clients · **Priority:** P1 · **Screen:** 7.3 · **Spec:** TPL-2, UI-8 · **Type:** Functional
- **Preconditions:** Client "Delete Me Ltd" with template "Temp" (from F01), one committed run (F01 as the run file, 1,000 rows) and one saved analysis.
- **Steps:**

    1. … > Delete on Delete Me Ltd.
    2. Read the dialog; try Delete without ticking.
    3. Tick "I understand" and Delete.
    4. Check C1, A0 and the data folder.

- **Expected:** Dialog lists 1 template, 1 run, 1,000 rows and 1 saved analysis to be deleted. Delete stays disabled until "I understand" is ticked. Afterwards the client is gone from C1, its analysis is gone from A0, its t\<template-id> folder is removed, and the footer row count drops by 1,000.

### C2-01 — Empty state

- **Area:** C2 Client · **Priority:** P2 · **Screen:** Not drawn · **Spec:** UX C2 · **Type:** Functional
- **Preconditions:** Acme Traders has no templates.
- **Steps:**

    1. Open Acme Traders.

- **Expected:** Shows "No templates for Acme Traders yet. A template is set up from one sample file." with a New template button. Breadcrumb Clients › Acme Traders.

### C2-02 — Template grid figures

- **Area:** C2 Client · **Priority:** P1 · **Screen:** 1.2 · **Spec:** UX-2, TPL-2 · **Type:** Functional
- **Preconditions:** TPL-A with R-0001 committed.
- **Steps:**

    1. Open Acme Traders.

- **Expected:** Sales Register row: Columns 8, Default outputs 2, Runs 1, Rows stored 5,000, Last loaded on = R-0001 date and time, Modified = last template save. A New run button sits on the row; … menu has Rename, Duplicate, Delete only (no Move).

### C2-03 — Search by template name

- **Area:** C2 Client · **Priority:** P3 · **Screen:** 1.2 · **Spec:** TPL-4 · **Type:** Functional
- **Preconditions:** Acme Traders has Sales Register and its copy (C2-06).
- **Steps:**

    1. Type "copy" in search.

- **Expected:** Only the duplicated template is listed.

### C2-04 — New run from the template row

- **Area:** C2 Client · **Priority:** P1 · **Screen:** 1.2 · **Spec:** UX C2 · **Type:** Functional
- **Preconditions:** TPL-A exists.
- **Steps:**

    1. Click New run on the Sales Register row.
    2. Cancel the confirmation, then click again and confirm.

- **Expected:** A confirmation appears first; cancelling keeps you on C2. Confirming opens the New run wizard step 1 (Files) for Sales Register.

### C2-05 — Rename a template

- **Area:** C2 Client · **Priority:** P2 · **Screen:** 1.2 · **Spec:** UX C3 step 1, TPL-4 · **Type:** Functional
- **Preconditions:** Acme Traders and Bharat Foods each exist; Bharat Foods has TPL-C.
- **Steps:**

    1. Rename Sales Register to "Conversion check" (TPL-C's name, other client).
    2. Rename it back to "Sales Register".
    3. Create a second template in Acme and try renaming it to "Sales Register".

- **Expected:** 1 is accepted (unique within a client only). 3 is refused as a duplicate within the client.

### C2-06 — Duplicate a template

- **Area:** C2 Client · **Priority:** P1 · **Screen:** 1.2 · **Spec:** TPL-4, UX C2 · **Type:** Functional
- **Preconditions:** TPL-A after R-0004 (has alias "Inv No", 2 default outputs, rules).
- **Steps:**

    1. … > Duplicate on Sales Register.
    2. Open the copy: Columns & rules, Default outputs, Settings, Runs.

- **Expected:** A new template appears in Acme Traders with Runs 0 and Rows stored 0. Columns, types, decimals, aliases (incl. Inv No), rules with severities, settings, export defaults and both default outputs match the original. Runs tab is empty.

### C2-07 — Type is editable in a duplicate with no runs

- **Area:** C2 Client · **Priority:** P2 · **Screen:** 3.3 · **Spec:** TPL-9 · **Type:** Functional
- **Preconditions:** C2-06.
- **Steps:**

    1. In the copy, Columns & rules > Customer > change Type to Number, then back to Text.

- **Expected:** Type can be changed (no committed run yet). The original's types stay locked.

### C2-08 — Delete a template

- **Area:** C2 Client · **Priority:** P1 · **Screen:** Not drawn (same as 7.2) · **Spec:** TPL-4, UI-8, D30 · **Type:** Functional
- **Preconditions:** The copy from C2-06 has one committed run (F02, 5,000 rows; if a duplicate-contents warning names R-0001, choose Load anyway and note it) and saved analysis AN-3.
- **Steps:**

    1. … > Delete on the copy.
    2. Tick "I understand" and Delete.
    3. Check C2, A0 and the data folder.

- **Expected:** Dialog lists 1 run, 5,000 rows and 1 saved analysis. Delete is disabled until ticked. Template, its runs folder and AN-3 are gone. The original template is unaffected.

### C3-01 — Wizard steps and cancel

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.1 · **Spec:** UX C3 · **Type:** Functional
- **Preconditions:** Acme Traders open.
- **Steps:**

    1. New template.
    2. Enter a name and pick F01; go to step 3.
    3. Click Cancel > choose to keep editing.
    4. Cancel again > confirm discard.

- **Expected:** Steps shown: 1 Sample file · 2 Sheets · 3 Columns · 4 Rules · 5 Default outputs · 6 Review. Cancel asks "Discard this template?". Keeping returns to step 3 with entries intact; confirming returns to C2 with no new template.

### C3-02 — Sample file and preview row count

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.1 · **Spec:** TPL-3 · **Type:** Functional
- **Preconditions:** Acme Traders.
- **Steps:**

    1. New template > name "Sales Register" > pick F01 Sample_Sales.xlsx.

- **Expected:** File accepted; the screen states 1,000 rows read for preview. Nothing is written to the data folder's t\ area.

### C3-03 — Preview stops at 100,000 rows

- **Area:** C3 New template · **Priority:** P2 · **Screen:** 2.1 · **Spec:** TPL-3 · **Type:** Functional
- **Preconditions:** P01 Perf_10M_01.csv available.
- **Steps:**

    1. New template under client Perf Test > pick P01.

- **Expected:** Exactly 100,000 rows are read for previews (stated on screen); the step completes without reading the whole 10M-row file.

### C3-04 — Allowed sample file types

- **Area:** C3 New template · **Priority:** P2 · **Screen:** 2.1 · **Spec:** IN-3 · **Type:** Functional
- **Preconditions:** F29 Sales_Notes.txt, F11 Sales_Old.xls, F20 Sales_Macro.xlsm.
- **Steps:**

    1. Open the file picker and check the file-type filter.
    2. Drag F29 onto the step.
    3. Pick F11, then F20.

- **Expected:** Picker offers .xlsx, .xlsm, .xlsb, .xls and .csv only. F29 is refused with a plain message that only .xlsx, .xlsm, .xlsb, .xls and .csv files can be added. F11 and F20 are accepted. (Changed 20-11-2026, D38: .xls was refused.)

### C3-05 — Template name unique within client

- **Area:** C3 New template · **Priority:** P2 · **Screen:** 2.1 · **Spec:** UX C3 step 1 · **Type:** Functional
- **Preconditions:** Sales Register exists in Acme Traders.
- **Steps:**

    1. New template in Acme Traders > name "Sales Register".

- **Expected:** Refused with a message that the name is in use in this client.

### C3-06 — Header row found automatically

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.2 · **Spec:** IN-6, IN-7 · **Type:** Functional
- **Preconditions:** C3-02 (F01 has two title rows; header in row 3).
- **Steps:**

    1. Go to step 2.

- **Expected:** Preview marks row 3 as the header. There is no header-row or trailer setting on the screen.

### C3-07 — Sheets to read options and hidden sheets

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.2 · **Spec:** IN-5, IN-13 · **Type:** Functional
- **Preconditions:** F16 Sales_Regions.xlsx (North, South visible; Archive hidden).
- **Steps:**

    1. New template "Regional Sales" in Bharat Foods > pick F16 > step 2.
    2. Try each option: by name (pick North and South), first visible sheet, all visible sheets.
    3. Save with All visible sheets (finish wizard with no rules/outputs).

- **Expected:** Options offered: by name (one or more), first visible sheet, all visible sheets. Archive is listed as hidden and skipped. First visible = North. All visible = North and South.

### C3-08 — CSV encoding and delimiter detected

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.2 · **Spec:** IN-4 · **Type:** Functional
- **Preconditions:** F18 Conversion_1252.csv (Windows-1252, semicolon).
- **Steps:**

    1. New template in Bharat Foods > pick F18 > step 2.

- **Expected:** Encoding shows Windows-1252 and delimiter semicolon, both changeable. Preview shows Café, Müller, Señor correctly (no Ã© characters).

### C3-09 — Columns grid and type detection

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.3 · **Spec:** TPL-3, MAP-10 · **Type:** Functional
- **Preconditions:** C3-06 (F01).
- **Steps:**

    1. Go to step 3.

- **Expected:** Grid columns: Include · Source header · Column name · Type · Date format · Sample values. Detected: Invoice No Text, Invoice Date Date, Customer Text, GSTIN Text, State Text, Taxable Value Number, GST Rate Number, Tax Amount Number, each with a % note (100% for F01). No "Required" checkbox.

### C3-10 — Decimals on Number columns

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.3 · **Spec:** T13 (TPL-1, MAP-10 change) · **Type:** Functional
- **Preconditions:** C3-09.
- **Steps:**

    1. Check the Decimals field on Taxable Value, GST Rate, Tax Amount.
    2. Set GST Rate to 0; try 7 and -1.

- **Expected:** Each Number column has Decimals, default 2, range 0–6; 7 and -1 are refused. Text and Date columns have no Decimals field.

### C3-11 — Date format only for text dates

- **Area:** C3 New template · **Priority:** P2 · **Screen:** 2.3 · **Spec:** MAP-10 · **Type:** Functional
- **Preconditions:** C3-09 (F01 Invoice Date holds Excel dates); F17 for a second template.
- **Steps:**

    1. Check the Date format field on Invoice Date.
    2. In a new template from F17, check Doc Date and Due Date (text dates).

- **Expected:** 1: no date format needed for Excel dates (field hidden or disabled). 2: Date format offered with DD-MM-YYYY and DD/MM/YYYY.

### C3-12 — Include, rename and reorder columns

- **Area:** C3 New template · **Priority:** P2 · **Screen:** 2.3 · **Spec:** TPL-3 · **Type:** Functional
- **Preconditions:** C3-09.
- **Steps:**

    1. Move Customer above Invoice Date with ↑, then back with ↓.
    2. Untick Include on GSTIN, then tick it again.
    3. Keep all 8 columns with source names.

- **Expected:** Order changes immediately in the grid and in step 6. An unticked column is excluded from steps 4–6.

### C3-13 — Type rules are added automatically

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.4 · **Spec:** VR-7, NCK-2 · **Type:** Functional
- **Preconditions:** C3-12 done; step 4.
- **Steps:**

    1. Read the bar at the top of the step.
    2. Select Taxable Value, then Invoice Date.
    3. Try to remove "Is a number" / "Is a date".
    4. Switch one to Warning and back to Error.

- **Expected:** The step starts with the Check data before loading bar, Yes / No, with Yes selected and "Applies to every run of this template. Can be changed later in Settings." (A2, NCK-2); the rule editor is shown below it. "Is a number" is present on every Number column and "Is a date" on Invoice Date, both Error. They have no remove control; severity can be set to Warning.

### C3-14 — Rule types offered per column type

- **Area:** C3 New template · **Priority:** P2 · **Screen:** 2.4 · **Spec:** VAL-1..9, T16, NCK-2 · **Type:** Functional
- **Preconditions:** Step 4, with Check data before loading = Yes (the default, selected in the bar at the top).
- **Steps:**

    1. For a Text, a Number and a Date column open Add rule.

- **Expected:** The Yes / No bar shows Yes selected (A2, NCK-2). Text: Not blank, Allowed values, Text length, Character pattern, Unique within the run. Number: Not blank, Number range, Allowed values, Unique. Date: Not blank, Date range, Unique. No between-column or across-run rules.

### C3-15 — Set up the TPL-A rule set

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.4 · **Spec:** VR-1, VR-2, VR-8 · **Type:** Functional
- **Preconditions:** Step 4 with F01.
- **Steps:**

    1. Add the rules in Read me > TPL-A rule set (Invoice No: Not blank E, Pattern AAA-99999 E, Unique E; Invoice Date: Date range 01-04-2026–31-03-2027 W; Customer: Not blank W; GSTIN: Text length exactly 15 E; State: Allowed values W; Taxable Value: Not negative E; GST Rate: Allowed values 0,5,12,18,28 E).

- **Expected:** Every rule shows its settings, an Error/Warning toggle and a dry-run count of 0 on the 1,000 sample rows.

### C3-16 — Dry-run counts and Show on a sample with failures

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.4 · **Spec:** VR-8, T16, T17 · **Type:** Functional
- **Preconditions:** F04 Sales_Errors.xlsx. TPL-A rule set to hand.
- **Steps:**

    1. New template "Rules dry run" > sample F04 > steps 2–3 defaults (GST Rate decimals 0).
    2. Step 4: add the TPL-A rule set.
    3. Click Show on State Allowed values and on Taxable Value Is a number.
    4. Cancel and discard the wizard.

- **Expected:** Counts: Invoice No Not blank 12, Pattern 8, Unique 6; Invoice Date Is a date 4; GSTIN Text length 10; Taxable Value Is a number 15, Not negative 5; GST Rate Allowed values 6; State Allowed values 25 (Warning); Customer Not blank 7 (Warning). Show on State lists the first 20 failing rows (of 25); Show on Is a number lists all 15, starting at row 214.

### C3-17 — Default outputs are optional

- **Area:** C3 New template · **Priority:** P2 · **Screen:** 2.5 · **Spec:** UX C3 step 5 · **Type:** Functional
- **Preconditions:** TPL-A wizard at step 5.
- **Steps:**

    1. Click Next with no outputs, then Back.

- **Expected:** Next works with no outputs; Review shows 0 default outputs.

### C3-18 — Create the two TPL-A default outputs with preview

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.5 · **Spec:** DO-1, DO-8, ANA-4..7 · **Type:** Functional
- **Preconditions:** TPL-A wizard (F01) at step 5.
- **Steps:**

    1. Add DO1 "State-wise sales": Group by State; measure cards Taxable Value (Sum), Tax Amount (Sum), Invoice No (Count); in the preview rename the headers with ✎ to "Taxable", "Tax" and "Invoices" (MEA-8; changed 22-11-2026, A2).
    2. Add DO2 "Latest month by GST rate": filter Invoice Date = latest month in this run; Group by Invoice Date (Month) then GST Rate; Sum Taxable Value; Show subtotals on.
    3. Try saving an output with no name.

- **Expected:** No name is refused. DO1 preview (1,000 sample rows): Delhi 250 · 380,687.50 · 48,131.00; Gujarat 250 · 375,562.50 · 47,977.00; Karnataka 250 · 378,125.00 · 48,361.50; Maharashtra 250 · 373,000.00 · 46,875.00; grand total 1,000 · 1,507,375.00 · 191,344.50. DO2 preview: August 2026, rates 0/5/12/18/28 with 297,375.00 / 299,425.00 / 301,475.00 / 303,525.00 / 305,575.00; month subtotal 1,507,375.00.

### C3-19 — Default output date filters are relative only

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.5 · **Spec:** DO-3 · **Type:** Functional
- **Preconditions:** Step 5 builder, DO2.
- **Steps:**

    1. Open the Invoice Date filter options.

- **Expected:** Only latest month / latest quarter / latest year in this run (plus Blank / Not blank if offered). No Year is, Between dates or fixed-date options.

### C3-20 — Review and Save template

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.6 · **Spec:** F1, TPL-3 · **Type:** Functional
- **Preconditions:** Steps 1–5 complete for TPL-A.
- **Steps:**

    1. Step 6: read the summary.
    2. Click Save template.
    3. Check C2 and the data folder.

- **Expected:** Summary lists name, sheet setting (by name: Sales), 8 columns with types, rule count per column, 2 default outputs. After Save: C2 shows Sales Register with Runs 0, Rows stored 0; no runs folder exists under t\<template-id>.

### C3-21 — Save and start first run

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.6 · **Spec:** F1 · **Type:** Functional
- **Preconditions:** TPL-C wizard (F17, Bharat Foods) at step 6; Is a number and Is a date set to Warning in step 4; no outputs.
- **Steps:**

    1. Click Save and start first run.

- **Expected:** Template saved and New run wizard step 1 opens for Conversion check.

### C3-22 — Back keeps entries

- **Area:** C3 New template · **Priority:** P3 · **Screen:** 2.1, 2.2, 2.3, 2.4, 2.5 · **Spec:** UX C3 · **Type:** Functional
- **Preconditions:** Wizard at step 5.
- **Steps:**

    1. Back to step 1, then Next to step 5.

- **Expected:** Name, sample file, sheet choice, column settings and rules are unchanged; the file is not re-read from scratch unless it changed.

### C4-01 — Header and summary line

- **Area:** C4 Template · **Priority:** P1 · **Screen:** 3.1 · **Spec:** UX-4, UX C4 · **Type:** Functional
- **Preconditions:** TPL-A after R-0001 to R-0003.
- **Steps:**

    1. Open Sales Register.

- **Expected:** Breadcrumb Clients › Acme Traders › Sales Register; title; New run (primary); summary "3 runs · 10,937 rows · X GB · last loaded DD-MM-YYYY HH:MM" matching R-0003; tabs Runs · Default outputs · Columns & rules · Settings.

### C4-02 — Runs grid

- **Area:** C4 Template · **Priority:** P1 · **Screen:** 3.1 · **Spec:** UX-4, RUN-2 · **Type:** Functional
- **Preconditions:** C4-01.
- **Steps:**

    1. Read the Runs grid.
    2. Hover the Files count and the Comment of R-0003.

- **Expected:** Columns: Run ID · Loaded on · Files · Rows · Issues · Status · Comment · …; newest first: R-0003, R-0002, R-0001. R-0001: 1 file, 5,000, 0 · 0, Committed. R-0002: 1 file, 4,000, 0 · 0, Committed. R-0003: 1 file, 1,937, 66 · 32, Committed with override, comment = the override reason. Hover shows file names and the full comment. No period or Exclude column.

### C4-03 — Search runs by comment and file name

- **Area:** C4 Template · **Priority:** P2 · **Screen:** 3.1 · **Spec:** UX C4 · **Type:** Functional
- **Preconditions:** C4-02.
- **Steps:**

    1. Search "Errors".
    2. Search "Oct".
    3. Search a word from R-0003's comment.

- **Expected:** 1: R-0003. 2: R-0001. 3: R-0003.

### C4-04 — Run row actions

- **Area:** C4 Template · **Priority:** P2 · **Screen:** 3.1 · **Spec:** UX-4, T19 · **Type:** Functional
- **Preconditions:** C4-02.
- **Steps:**

    1. Open the … menu of R-0003.

- **Expected:** Items: Open, Export data, Export issue list, Export left-out rows, Delete. No Exclude.

### C4-05 — Default outputs tab and preview on latest run

- **Area:** C4 Template · **Priority:** P1 · **Screen:** 3.2 · **Spec:** UX-5, DO-8 · **Type:** Functional
- **Preconditions:** TPL-A after R-0001 (latest run).
- **Steps:**

    1. Default outputs tab.
    2. Select DO1 and read the preview.

- **Expected:** List shows DO1 then DO2 in order. Preview runs on R-0001: Delhi 1,250 · 1,903,437.50 · 240,655.00; Gujarat 1,250 · 1,877,812.50 · 239,885.00; Karnataka 1,250 · 1,890,625.00 · 241,807.50; Maharashtra 1,250 · 1,865,000.00 · 234,375.00; total 5,000 · 7,536,875.00 · 956,722.50.

### C4-06 — Editing a default output affects future runs only

- **Area:** C4 Template · **Priority:** P1 · **Screen:** 3.2 · **Spec:** DO-6 · **Type:** Functional
- **Preconditions:** TPL-A after R-0004; before R-0005.
- **Steps:**

    1. Read the note on the tab.
    2. Edit DO1: add a Customer card with Distinct; rename its preview header with ✎ to "Customers" (MEA-8; changed 22-11-2026, A2). Save.
    3. Open R-0001 > Outputs > DO1.

- **Expected:** Note reads "Changes apply to future runs. Outputs already saved with earlier runs don't change." R-0001's saved DO1 still has 3 measures (no Customers). R-0005 (later) shows Customers = 10 per state.

### C4-07 — Reorder default outputs

- **Area:** C4 Template · **Priority:** P3 · **Screen:** 3.2 · **Spec:** DO-1 · **Type:** Functional
- **Preconditions:** TPL-A.
- **Steps:**

    1. Move DO2 above DO1; save. 2. Start a new run to the Outputs step and look at the order; discard. 3. Restore the order.

- **Expected:** Outputs run and display in the saved order.

### C4-08 — Unsaved changes on a template tab

- **Area:** C4 Template · **Priority:** P2 · **Screen:** 3.2 · **Spec:** UX §5 Leaving · **Type:** Functional
- **Preconditions:** TPL-A Default outputs tab.
- **Steps:**

    1. Change a measure name; don't save.
    2. Click the Runs tab. Choose Stay.
    3. Click Runs again; choose Discard.
    4. Repeat with Save.

- **Expected:** A prompt offers Save / Discard / Stay. Stay keeps the edit; Discard reverts it; Save keeps it.

### C4-09 — Columns & rules layout

- **Area:** C4 Template · **Priority:** P2 · **Screen:** 3.3 · **Spec:** UX-6 · **Type:** Functional
- **Preconditions:** TPL-A after R-0001.
- **Steps:**

    1. Columns & rules tab.
    2. Select Invoice No.

- **Expected:** List shows name · type · rules · aliases for each column, with Add column and ↑ ↓. Detail panel shows name, type, decimals (Number), aliases and rules, and a "Test rules on latest run" button.

### C4-10 — Type and decimals are fixed after the first commit

- **Area:** C4 Template · **Priority:** P1 · **Screen:** 3.3 · **Spec:** TPL-9, MAP-12, T13 · **Type:** Functional
- **Preconditions:** TPL-A after R-0001.
- **Steps:**

    1. Select Taxable Value; try to change Type and Decimals.
    2. Select Customer; try to change Type.

- **Expected:** Type and Decimals are locked (read-only) for all columns, with an explanation.

### C4-11 — Aliases

- **Area:** C4 Template · **Priority:** P2 · **Screen:** 3.3 · **Spec:** MAP-3, MAP-5 · **Type:** Functional
- **Preconditions:** TPL-A after R-0004.
- **Steps:**

    1. Select Invoice No.
    2. Add alias "Bill No"; save.
    3. Remove "Bill No"; save.

- **Expected:** Invoice No lists alias "Inv No" (learned in R-0004). Bill No can be added and removed.

### C4-12 — Test rules on latest run

- **Area:** C4 Template · **Priority:** P1 · **Screen:** 3.3 · **Spec:** VR-8 · **Type:** Functional
- **Preconditions:** TPL-A; latest committed run is R-0003.
- **Steps:**

    1. Click Test rules on latest run.
    2. Check the Runs tab issue counts afterwards.

- **Expected:** Counts only (no row list): State Allowed values 25, Customer Not blank 7; every Error rule 0 (error rows were left out). Nothing is stored: R-0003 still shows 66 · 32.

### C4-13 — Rename a column

- **Area:** C4 Template · **Priority:** P2 · **Screen:** 3.3 · **Spec:** MAP-8 · **Type:** Functional
- **Preconditions:** TPL-A with runs.
- **Steps:**

    1. Rename Customer to "Customer Name"; save.
    2. Export R-0001 data; open AN-1 result.
    3. Note the modified time of a data.parquet file under t\…\runs\ before and after.

- **Expected:** Export header and analysis show "Customer Name" for all runs. Parquet files are not rewritten (modified time unchanged).

### C4-14 — Add a column in the template

- **Area:** C4 Template · **Priority:** P2 · **Screen:** 3.3 · **Spec:** MAP-8, MAP-11 · **Type:** Functional
- **Preconditions:** TPL-A with runs.
- **Steps:**

    1. Add column "Region Code" (Text); save.
    2. Run an analysis on R-0001 grouped by Region Code.
    3. Remove the column again.

- **Expected:** New column can have its type set; older runs show (Null) for it.

### C4-15 — Remove a column blocked while used by an output

- **Area:** C4 Template · **Priority:** P1 · **Screen:** 3.3 · **Spec:** MAP-11 · **Type:** Functional
- **Preconditions:** TPL-A; DO1 groups by State.
- **Steps:**

    1. Try to remove State.

- **Expected:** Refused with a message naming DO1 as the output that uses State.

### C4-16 — Remove a column used only in a saved analysis

- **Area:** C4 Template · **Priority:** P2 · **Screen:** 3.3 · **Spec:** MAP-11, T23 · **Type:** Functional
- **Preconditions:** Run LAST in the sequence. Saved analysis AN-2 uses GSTIN.
- **Steps:**

    1. Remove GSTIN from TPL-A; save.
    2. Open AN-2, tick R-0001, Run.

- **Expected:** Removal is allowed. AN-2 still runs; its GSTIN measure is labelled "(removed)" and still returns R-0001 values (Count distinct = 5,000).

### C4-17 — Settings tab fields

- **Area:** C4 Template · **Priority:** P1 · **Screen:** 3.4 · **Spec:** UX-7, TPL-1, EXP-4 · **Type:** Functional
- **Preconditions:** TPL-A.
- **Steps:**

    1. Settings tab.

- **Expected:** Fields: template name; sheets to read (by name one or more / first visible / all visible) set to by name: Sales; CSV delimiter and encoding; export defaults: folder, file name {Client}_{Template}_{RunID}_{Output}, CSV delimiter, UTF-8 with BOM. Date format DD-MM-YYYY shown as fixed. No header-row, trailer or number-grouping setting.

### C4-18 — Export defaults prefill the Export dialog

- **Area:** C4 Template · **Priority:** P2 · **Screen:** 3.4, 7.4 · **Spec:** EXP-4 · **Type:** Functional
- **Preconditions:** TPL-A.
- **Steps:**

    1. Settings: export folder D:\Exports, delimiter semicolon; save.
    2. Open R-0001 > Export data.

- **Expected:** Export dialog is prefilled with D:\Exports, the name pattern resolved for R-0001, and semicolon.

### RUNF-01 — Add files by picker and drag-and-drop

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1 · **Spec:** IN-1 · **Type:** Functional
- **Preconditions:** TPL-A saved, no runs. F02 and F20 on the Desktop.
- **Steps:**

    1. New run.
    2. Add files > multi-select F02 and F20.
    3. Remove F20 with ✕.
    4. Drag F20 from Explorer onto the step.
    5. Drag folder F21 Run_Folder onto the step.

- **Expected:** Both methods add files. ✕ removes a row. Dropping a folder is refused with a message that folders can't be added (no folder import).

### RUNF-02 — File grid contents

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1 · **Spec:** IN-11 · **Type:** Functional
- **Preconditions:** RUNF-01 with F02 only.
- **Steps:**

    1. Read the F02 row.

- **Expected:** One row: File Sales_Oct.xlsx · Sheet Sales · Size (matches Explorer) · Header 1 · Rows ≈5,000 (approximate until Validate) · Status Ready.

### RUNF-03 — .xlsm and .xls accepted, .txt refused

- **Area:** C5 Run · Files · **Priority:** P2 · **Screen:** 4.1 · **Spec:** IN-3 · **Type:** Functional
- **Preconditions:** New run on TPL-A.
- **Steps:**

    1. Add F20 Sales_Macro.xlsm.
    2. Add F11 Sales_Old.xls.
    3. Add F29 Sales_Notes.txt.

- **Expected:** F20 is Ready. F11 is Ready (100 rows). F29 is refused with a plain message that only .xlsx, .xlsm, .xlsb, .xls and .csv files can be added. (Changed 20-11-2026, D38: .xls was refused.)

### RUNF-04 — Header row detected per file

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1 · **Spec:** IN-6, IN-13, IN-5 · **Type:** Functional
- **Preconditions:** New run on TPL-A with F03.
- **Steps:**

    1. Add F03 Sales_Nov.xlsx.

- **Expected:** Row Sales_Nov.xlsx · Sales · Header 2 · Ready. Sheet Notes is not listed (template reads sheet Sales by name). Info: hidden data skipped (hidden sheet Old; hidden rows).

### RUNF-05 — Password-protected file

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1a · **Spec:** IN-9, IN-15 · **Type:** Functional
- **Preconditions:** New run with F02 and F06.
- **Steps:**

    1. Add F06 Sales_Protected.xlsx.
    2. Try Next.

- **Expected:** F06 status Error: password-protected. Offers Exclude file and Re-check. No password prompt. Next is disabled.

### RUNF-06 — File open in Excel

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1a · **Spec:** IN-10, IN-15, UI-6 · **Type:** Functional
- **Preconditions:** F07 open in Excel (this also creates ~$Sales_Locked.xlsx).
- **Steps:**

    1. New run > add F07 and the ~$Sales_Locked.xlsx lock file.
    2. Read F07's message.
    3. Close Excel; click Re-check.

- **Expected:** Lock file is listed as skipped. F07 shows Error with "Sales_Locked.xlsx is open in another program. Close it, then Re-check." (UX doc wording: "…is open in Excel…"; either is acceptable, record which). After Re-check F07 is Ready.

### RUNF-07 — Sheet not found

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1a, 4.1b · **Spec:** IN-15, SHT-6, T47 · **Type:** Functional
- **Preconditions:** New run with F10.
- **Steps:**

    1. Add F10 Sales_WrongSheet.xlsx (only sheet "Data").

- **Expected:** Error: sheet Sales not found, as one error row for the file (T47), naming the sheets it has ("Sheets found: Data"). Choose sheets… and Exclude file offered (SHT-6); the footer reads "Choose sheets for 1 file, or exclude it, to continue"; Next disabled. (A2 changed: was "Exclude file / Re-check offered".)

### RUNF-08 — Header not found

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1a · **Spec:** IN-6, IN-15 · **Type:** Functional
- **Preconditions:** New run with F09.
- **Steps:**

    1. Add F09 Sales_NoHeader.xlsx.

- **Expected:** Error: header not found or doesn't match. No option to pick the header row by hand.

### RUNF-09 — Exclude a file in error

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1a · **Spec:** IN-15 · **Type:** Functional
- **Preconditions:** Run with F02, F06, F09, F10 added.
- **Steps:**

    1. Click Exclude file on F06, F09 and F10.
    2. Click Next.

- **Expected:** Excluded files are marked excluded and won't be read. Next becomes enabled only after the last error is excluded and goes on with F02 only.

### RUNF-10 — Same file added twice

- **Area:** C5 Run · Files · **Priority:** P2 · **Screen:** 4.1 · **Spec:** IN-10 · **Type:** Functional
- **Preconditions:** New run.
- **Steps:**

    1. Add F02.
    2. Add F02 again from the same path.

- **Expected:** Second copy is listed as skipped (same file); only one Ready row.

### RUNF-11 — Duplicate contents warning

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1 · **Spec:** RUN-7 · **Type:** Functional
- **Preconditions:** R-0001 (F02) committed.
- **Steps:**

    1. New run on TPL-A > add F05 Sales_Oct_copy.xlsx.
    2. Read the warning.
    3. Click Remove.
    4. Add F05 again; click Load anyway; then leave and discard the run.

- **Expected:** Warning names R-0001 and its loaded date. Remove drops the row. Load anyway keeps it as Ready.

### RUNF-12 — Mapping skipped when all headers match

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1 · **Spec:** TPL-6 · **Type:** Functional
- **Preconditions:** New run with F02 (R-0001 run).
- **Steps:**

    1. Click Next on Files.

- **Expected:** Wizard goes straight to Validate; Mapping shows as skipped in the step bar.

### RUNF-13 — One row per file and sheet

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1 · **Spec:** IN-5, IN-11, IN-13 · **Type:** Functional
- **Preconditions:** TPL-D Regional Sales (all visible sheets).
- **Steps:**

    1. New run > add F16.

- **Expected:** Two rows: Sales_Regions.xlsx · North and Sales_Regions.xlsx · South, both Ready; info that hidden sheet Archive is skipped.

### RUNF-15 — .xls and .xlsb read like .xlsx

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1 · **Spec:** IN-3, IN-13, T11 · **Type:** Functional
- **Preconditions:** A template with TPL-A columns reading sheet Sales by name (added 20-11-2026, D38).
- **Steps:**

    1. Run with F22 Sales_Nov.xls alone; Validate.
    2. Discard; run with F23 Sales_Nov.xlsb alone; Validate.

- **Expected:** Each file: Sales · Header 2 · Ready; info lines for hidden rows and hidden sheet Old. Rows loaded 4,000; blank rows 10; hidden rows 25. Taxable Value 6,029,500.00; Tax Amount 765,378.00 (as RUNV-02 and RUNC-03 for F03).

### RUNF-16 — Password-protected .xls and .xlsb

- **Area:** C5 Run · Files · **Priority:** P2 · **Screen:** 4.1a · **Spec:** IN-9, IN-15 · **Type:** Functional
- **Preconditions:** New run on TPL-A (added 20-11-2026, D38).
- **Steps:**

    1. Add F26 Sales_Protected.xls and F27 Sales_Protected.xlsb.

- **Expected:** Both Error: password-protected, as RUNF-05. No password prompt.

### RUNF-17 — Web page saved with an .xls name

- **Area:** C5 Run · Files · **Priority:** P3 · **Screen:** 4.1a · **Spec:** IN-15 · **Type:** Functional
- **Preconditions:** New run on TPL-A (added 20-11-2026, D38).
- **Steps:**

    1. Add F28 Sales_Export.xls.

- **Expected:** Error: "Sales_Export.xls is a web page or XML file with an Excel name. Open it in Excel and save it as .xlsx."

### RUNF-14 — Low-disk warning

- **Area:** C5 Run · Files · **Priority:** P2 · **Screen:** 4.1 · **Spec:** UX C5 step 1 · **Type:** Functional
- **Preconditions:** LOW-DISK setup.
- **Steps:**

    1. New run on TPL-A > add F02.

- **Expected:** A low-disk warning is shown on the Files step.

### RUNM-01 — Mapping grid and auto-match

- **Area:** C5 Run · Mapping · **Priority:** P1 · **Screen:** 4.2 · **Spec:** MAP-2, MAP-4, TPL-6 · **Type:** Functional
- **Preconditions:** TPL-A after R-0003. New run with F08 Sales_Renamed_Headers.xlsx.
- **Steps:**

    1. Next from Files.

- **Expected:** Mapping grid: rows = template columns, column = Sales_Renamed_Headers.xlsx · Sales. Auto-matched without highlight: invoice_date→Invoice Date, CUSTOMER→Customer, G.S.T.I.N→GSTIN, GST-Rate→GST Rate, Taxable Value, Tax Amount. Highlighted amber: Invoice No (new header Inv No), State (missing). Remarks shown as a file column not in the template.

### RUNM-02 — Next goes to the first undecided cell

- **Area:** C5 Run · Mapping · **Priority:** P2 · **Screen:** 4.2 · **Spec:** MAP-13 · **Type:** Functional
- **Preconditions:** RUNM-01.
- **Steps:**

    1. Click Next before deciding anything.

- **Expected:** Wizard stays on Mapping and moves focus to the first undecided cell (Invoice No).

### RUNM-03 — New header: Map and save as alias

- **Area:** C5 Run · Mapping · **Priority:** P1 · **Screen:** 4.2 · **Spec:** MAP-5 · **Type:** Functional
- **Preconditions:** RUNM-01.
- **Steps:**

    1. Invoice No cell: pick Inv No > Map and save as alias.

- **Expected:** Cell is decided and marked as alias. After commit, C4 Columns & rules shows alias Inv No on Invoice No.

### RUNM-04 — Missing column: Leave as null with output warning

- **Area:** C5 Run · Mapping · **Priority:** P1 · **Screen:** 4.2 · **Spec:** MAP-6 · **Type:** Functional
- **Preconditions:** RUNM-01.
- **Steps:**

    1. State cell: choose Leave as null.

- **Expected:** Warning that DO1 "State-wise sales" will show these rows as (Null). Cell becomes decided.

### RUNM-05 — Extra column: Leave out

- **Area:** C5 Run · Mapping · **Priority:** P1 · **Screen:** 4.2 · **Spec:** MAP-7 · **Type:** Functional
- **Preconditions:** RUNM-01.
- **Steps:**

    1. Remarks: choose Leave out.
    2. Next.

- **Expected:** All decisions made; Next starts Validate (R-0004 continues in RUNV-08).

### RUNM-06 — New header: This run only

- **Area:** C5 Run · Mapping · **Priority:** P2 · **Screen:** 4.2 · **Spec:** MAP-5, TPL-8 · **Type:** Functional
- **Preconditions:** A new run with F08 (after R-0004, on the duplicate from C2-06 which has no Bill No alias), or before RUNM-03 in a run you will discard.
- **Steps:**

    1. Map Inv No with "This run only".
    2. Complete Validate, then leave and discard the run.
    3. Check aliases in Columns & rules.

- **Expected:** Alias is not saved to the template.

### RUNM-07 — Extra column: Add as new column

- **Area:** C5 Run · Mapping · **Priority:** P1 · **Screen:** 4.2 · **Spec:** MAP-7, MAP-11 · **Type:** Functional
- **Preconditions:** TPL-A after R-0004. New run with F13 Sales_Dec_NewCol.xlsx.
- **Steps:**

    1. Branch: Add as new column, name Branch, type Text.
    2. Continue to commit (R-0005).
    3. Analysis on R-0001 and R-0005 grouped by Branch, Count Invoice No.

- **Expected:** After commit the template has Branch (Text, locked). Analysis: (Null) 5,000; Nagpur 1,000; Nashik 1,000; Pune 1,000.

### RUNM-08 — Leave the run wizard from Mapping

- **Area:** C5 Run · Mapping · **Priority:** P1 · **Screen:** 7.6 · **Spec:** RUN-14 · **Type:** Functional
- **Preconditions:** RUNM-01 with some decisions made.
- **Steps:**

    1. Click Clients in the rail.
    2. In "Leave and discard this run?" choose Stay.
    3. Click Clients again; choose Leave.
    4. Check C4 Runs and the data folder's _staging.

- **Expected:** Stay keeps all decisions. Leave returns to C1; no run is created; _staging holds nothing for this run.

### RUNV-01 — Clean run counts

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3 · **Spec:** RUN-3, UI-5 · **Type:** Functional
- **Preconditions:** R-0001: new run on TPL-A with F02, mapping skipped.
- **Steps:**

    1. Wait for Validate to finish.

- **Expected:** Progress shows stage, rows done of total, bar, elapsed and Cancel. Result banner success; counts Errors 0 · Warnings 0 · Rows read 5,000 · Hidden data skipped 0. Next enabled.

### RUNV-02 — Hidden rows, hidden sheet, blank rows

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3 · **Spec:** IN-8, IN-13, T14 · **Type:** Functional
- **Preconditions:** R-0002: new run with F03.
- **Steps:**

    1. Wait for Validate.

- **Expected:** Hidden data skipped: 25 rows and 1 sheet (Old). 10 blank rows (8 empty, 2 spaces-only) are dropped and reported as blank rows. 0 errors, 0 warnings; 4,000 rows go on to load. Record whether Rows read shows 4,000 or 4,010 (RUN-12 counts blank rows under rows left out, which implies 4,010).

### RUNV-03 — Errors and warnings by rule

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3 · **Spec:** RUN-4, ISS-1, VR-3 · **Type:** Functional
- **Preconditions:** R-0003: new run with F04.
- **Steps:**

    1. Wait for Validate.
    2. Read banner, counts and by-rule table.

- **Expected:** Banner shows errors. Counts: Errors 66 · Warnings 32 · Rows read 2,000 · Hidden 0. By rule: Not blank (Invoice No) 12 E; Character pattern 8 E; Unique within the run 6 E; Is a date 4 E; Text length (GSTIN) 10 E; Is a number (Taxable Value) 15 E; Number range not negative 5 E; Allowed values (GST Rate) 6 E; Allowed values (State) 25 W; Not blank (Customer) 7 W. Next disabled.

### RUNV-04 — Issue grid rows, order, filter, sort

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3 · **Spec:** ISS-2, T17, UI-6 · **Type:** Functional
- **Preconditions:** RUNV-03.
- **Steps:**

    1. Read the first rows of the issue grid.
    2. Filter Severity = Warning.
    3. Sort by Column.

- **Expected:** Columns: File · Sheet · Row · Column · Value · Rule · Severity (with message). Ordered by file, sheet, row. Row 214: Taxable Value, value "abc", Is a number, Error. Each duplicate row's message names the first occurrence (e.g. row 705 names row 704). Filter shows 32 rows; sort works.

### RUNV-05 — Unique within the run flags every row in a group

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3 · **Spec:** VAL-9, T17 · **Type:** Functional
- **Preconditions:** RUNV-03.
- **Steps:**

    1. Filter the issue grid by rule Unique within the run.

- **Expected:** 6 rows: source rows 702–707 (all 3 pairs, both rows of each pair).

### RUNV-06 — Issue grid shows first 10,000 per rule

- **Area:** C5 Run · Validate · **Priority:** P2 · **Screen:** 4.3 · **Spec:** ISS-2, ISS-3, VR-4 · **Type:** Functional
- **Preconditions:** Before R-0005. New run on TPL-A with F12 Sales_ManyIssues.csv (15,000 rows, Customer all blank).
- **Steps:**

    1. Validate.
    2. Scroll to the end of the issue grid.
    3. Export the full issue list.
    4. Leave and discard the run.

- **Expected:** Not blank (Customer) shows 15,000 warnings; the grid holds 10,000 rows for that rule with a note that only the first 10,000 are shown. Export holds all 15,000. Warnings only, so Next is enabled.

### RUNV-07 — Export the full issue list from Validate

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3 · **Spec:** ISS-3 · **Type:** Functional
- **Preconditions:** RUNV-03.
- **Steps:**

    1. Export issue list (.csv) > Save.
    2. Open in Excel and a text editor.

- **Expected:** 98 data rows + header. Columns: File, Sheet, Row, Column, Value, Rule, Severity, Message. Row 214 line carries the GEN-07 message.

### RUNV-08 — Mapping decisions applied (R-0004)

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3 · **Spec:** MAP-6, T16 · **Type:** Functional
- **Preconditions:** RUNM-05 done.
- **Steps:**

    1. Wait for Validate.

- **Expected:** Rows read 1,000, 0 errors. State Allowed values reports 0 (null State is blank, so skipped). Next enabled.

### RUNV-09 — Edit rules for this run only

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3 · **Spec:** VR-5, TPL-8 · **Type:** Functional
- **Preconditions:** A new run on TPL-A with F04 (to be discarded).
- **Steps:**

    1. Validate.
    2. Edit rules for this run: GST Rate Allowed values add 15; don't tick Save to template.
    3. Read counts.
    4. Leave and discard; open Columns & rules.

- **Expected:** Only validation reruns. Errors drop from 66 to 60; Allowed values (GST Rate) 0. Template rule still lists 0,5,12,18,28.

### RUNV-10 — Save a rule change to the template

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3, 5.1 · **Spec:** VR-5, TPL-7, TPL-8 · **Type:** Functional
- **Preconditions:** R-0005 run (F13) at Validate.
- **Steps:**

    1. Edit rules: Customer Not blank from Warning to Error; tick Save to template.
    2. Finish R-0005.
    3. Open Columns & rules, and R-0005 Summary.

- **Expected:** Template shows Customer Not blank = Error. R-0005 Summary lists the rule change.

### RUNV-11 — Re-check after fixing the source

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3 · **Spec:** VR-6 · **Type:** Functional
- **Preconditions:** Copy F04 to Sales_Errors_work.xlsx. New run with that copy (to be discarded).
- **Steps:**

    1. Validate: Is a number = 15.
    2. Open the copy in Excel, set F214 (Taxable Value, row 214) to 1000, save, close Excel.
    3. Click Re-check files.

- **Expected:** Re-read and re-validate without leaving the run: Is a number = 14; total Errors 65.

### RUNV-12 — Cancel Validate

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 4.3 · **Spec:** UX §5 Cancel, RUN-5 · **Type:** Functional
- **Preconditions:** TPL-P; new run with P01 (10M rows).
- **Steps:**

    1. During Validate click Cancel.
    2. Check the screen and %LOCALAPPDATA%\…\Data\_staging and %TEMP%\Sankalan.

- **Expected:** Within a few seconds the wizard returns to Mapping (or Files when Mapping was skipped) and nothing is kept: _staging has no folder for this job. (A2: the step is still named "Validate" for a template with checks, as TPL-P; for a template without checks the third step is Load instead, and its Cancel is A2-NCK-03.)

### RUNV-13 — Continue despite errors

- **Area:** C5 Run · Validate · **Priority:** P1 · **Screen:** 7.1 · **Spec:** RUN-4, T18 · **Type:** Functional
- **Preconditions:** RUNV-03 (R-0003).
- **Steps:**

    1. Click Continue despite errors….
    2. Try to confirm with an empty reason.
    3. Enter reason "Client confirmed errors; revised file next month" and confirm.

- **Expected:** Dialog states "63 rows with errors will be left out". Empty reason is refused. Confirm goes to Outputs.

### RUNO-01 — Default outputs on the staged rows (R-0001)

- **Area:** C5 Run · Outputs · **Priority:** P1 · **Screen:** 4.4 · **Spec:** DO-2, DO-4, DO-7 · **Type:** Functional
- **Preconditions:** R-0001 after Validate.
- **Steps:**

    1. Next to Outputs.
    2. Read DO1 and DO2; toggle Show subtotals on DO2.

- **Expected:** Per-output status Done for both. DO1: Delhi 1,250 · 1,903,437.50 · 240,655.00; Gujarat 1,250 · 1,877,812.50 · 239,885.00; Karnataka 1,250 · 1,890,625.00 · 241,807.50; Maharashtra 1,250 · 1,865,000.00 · 234,375.00; total 5,000 · 7,536,875.00 · 956,722.50. DO2 (October 2026): 0% 1,486,875.00; 5% 1,497,125.00; 12% 1,507,375.00; 18% 1,517,625.00; 28% 1,527,875.00; month subtotal 7,536,875.00 (hidden when Show subtotals is off).

### RUNO-02 — No export before commit

- **Area:** C5 Run · Outputs · **Priority:** P1 · **Screen:** 4.4 · **Spec:** DO-7 · **Type:** Functional
- **Preconditions:** RUNO-01.
- **Steps:**

    1. Look for Export on the Outputs step.

- **Expected:** No export control on any output before commit.

### RUNO-03 — Outputs exclude left-out rows (R-0003)

- **Area:** C5 Run · Outputs · **Priority:** P1 · **Screen:** 4.4 · **Spec:** DO-2, T18 · **Type:** Functional
- **Preconditions:** RUNV-13.
- **Steps:**

    1. Read DO1 and DO2.

- **Expected:** DO1: Delhi 480 · 739,448.00 · 93,038.02; Goa 25 · 28,075.00 · 3,572.83; Gujarat 476 · 725,157.00 · 93,821.11; Karnataka 480 · 734,282.00 · 94,229.23; Maharashtra 476 · 720,032.00 · 90,333.16; total 1,937 · 2,946,994.00 · 374,994.35. DO2 (September 2026): 0% 578,776.25; 5% 583,835.25; 12% 590,089.00; 18% 594,117.25; 28% 600,176.25.

### RUNO-04 — Column left as null shows (Null) (R-0004)

- **Area:** C5 Run · Outputs · **Priority:** P1 · **Screen:** 4.4 · **Spec:** MAP-6 · **Type:** Functional
- **Preconditions:** RUNV-08.
- **Steps:**

    1. Read DO1.

- **Expected:** One group (Null): 1,000 · 1,507,375.00 · 191,344.50.

### RUNO-05 — No dates in this run (R-0006)

- **Area:** C5 Run · Outputs · **Priority:** P1 · **Screen:** 4.4 · **Spec:** T21, DO-3 · **Type:** Functional
- **Preconditions:** New run on TPL-A with F14 Sales_NoDates.xlsx; Validate done (Invoice Date blank everywhere; no Not blank rule on it).
- **Steps:**

    1. Next to Outputs.

- **Expected:** DO2 status Done with an empty result and the note "No dates in this run". DO1 normal (500 rows, 753,687.50). Next enabled.

### RUNO-06 — Cancel and Retry an output

- **Area:** C5 Run · Outputs · **Priority:** P2 · **Screen:** 4.4 · **Spec:** DO-5, UX §5 Cancel · **Type:** Functional
- **Preconditions:** TPL-P after PERF tests, with a default output added (Group by Customer ID, Count distinct Invoice No). New run with P01 at Outputs.
- **Steps:**

    1. Click Cancel while the output runs.
    2. Try Next.
    3. Click Retry.

- **Expected:** Cancelled output (and any not started) shows Retry; Next is disabled. After Retry finishes, Next is enabled.

### RUNO-07 — Outputs step skipped with no default outputs

- **Area:** C5 Run · Outputs · **Priority:** P2 · **Screen:** 4.4 · **Spec:** DO-4 · **Type:** Functional
- **Preconditions:** TPL-C (no outputs). Run with F17.
- **Steps:**

    1. Next from Validate.

- **Expected:** Wizard goes from Validate straight to Commit; Outputs shows as skipped.

### RUNC-01 — Totals check passes (R-0001)

- **Area:** C5 Run · Commit · **Priority:** P1 · **Screen:** 4.5 · **Spec:** RUN-6, T20 · **Type:** Functional
- **Preconditions:** RUNO-01. Totals check ticked on Taxable Value and Tax Amount in TPL-A.
- **Steps:**

    1. Next to Commit.

- **Expected:** Summary of what will be committed. Totals check per ticked column, Input = Loaded + Left out: Taxable Value 7,536,875.00 = 7,536,875.00 + 0.00; Tax Amount 956,722.50 = 956,722.50 + 0.00. Commit enabled.

### RUNC-02 — Totals reconciliation with left-out rows (R-0003)

- **Area:** C5 Run · Commit · **Priority:** P1 · **Screen:** 4.5 · **Spec:** RUN-6, T20 · **Type:** Functional
- **Preconditions:** RUNO-03.
- **Steps:**

    1. Next to Commit.

- **Expected:** Taxable Value: Input 2,986,623.75 = Loaded 2,946,994.00 + Left out 39,629.75. Tax Amount: Input 381,662.10 = Loaded 374,994.35 + Left out 6,667.75. Check passes.

### RUNC-03 — Hidden rows are in no total (R-0002)

- **Area:** C5 Run · Commit · **Priority:** P1 · **Screen:** 4.5 · **Spec:** T20, IN-13 · **Type:** Functional
- **Preconditions:** R-0002 at Commit.
- **Steps:**

    1. Read the totals check.

- **Expected:** Taxable Value 6,029,500.00 = 6,029,500.00 + 0.00; Tax Amount 765,378.00 = 765,378.00 + 0.00 (hidden rows of 99,999.99 are not in any total).

### RUNC-04 — Comment rules

- **Area:** C5 Run · Commit · **Priority:** P2 · **Screen:** 4.5 · **Spec:** RUN-13 · **Type:** Functional
- **Preconditions:** R-0001 at Commit.
- **Steps:**

    1. Paste 501 characters into Comment.
    2. Clear it and enter "October sales, first load".

- **Expected:** Comment accepts at most 500 characters (501st refused or trimmed with a counter); plain text only. Optional: Commit is enabled with it empty.

### RUNC-05 — Commit and open the run

- **Area:** C5 Run · Commit · **Priority:** P1 · **Screen:** 4.5, 5.1 · **Spec:** RUN-5, T22 · **Type:** Functional
- **Preconditions:** R-0001 at Commit.
- **Steps:**

    1. Click Commit.

- **Expected:** Commit takes about a second with no Cancel. Run screen opens for R-0001 with a brief success banner. C4 Runs lists R-0001.

### RUNC-06 — Overridden run needs its comment

- **Area:** C5 Run · Commit · **Priority:** P1 · **Screen:** 4.5 · **Spec:** RUN-4, RUN-13 · **Type:** Functional
- **Preconditions:** RUNC-02.
- **Steps:**

    1. Read the Comment field.
    2. Clear it.
    3. Restore text and Commit.

- **Expected:** Comment is prefilled with the override reason and required: Commit is disabled while it is empty. Committed status: Committed with override (R-0003).

### RUNC-07 — Discarded runs don't use a Run ID

- **Area:** C5 Run · Commit · **Priority:** P2 · **Screen:** 4.5 · **Spec:** RUN-14, T22 · **Type:** Functional
- **Preconditions:** After R-0002, discard one run (e.g. RUNV-09) before committing F04.
- **Steps:**

    1. Commit F04.

- **Expected:** It gets R-0003 (not R-0004).

### RUNC-08 — Run IDs are never reused

- **Area:** C5 Run · Commit · **Priority:** P1 · **Screen:** 4.5 · **Spec:** T22 · **Type:** Functional
- **Preconditions:** R-0006 committed (F14).
- **Steps:**

    1. Delete R-0006 (C6-09).
    2. New run with F15 Sales_Jan.xlsx; commit.

- **Expected:** The new run is R-0007.

### RUNC-09 — Leave from Validate, Outputs or Commit discards

- **Area:** C5 Run · Commit · **Priority:** P2 · **Screen:** 7.6 · **Spec:** RUN-14 · **Type:** Functional
- **Preconditions:** A run at Commit (to be discarded).
- **Steps:**

    1. Click a breadcrumb.
    2. Choose Leave.

- **Expected:** "Leave and discard this run?"; Leave keeps nothing (no run in C4, _staging empty).

### RUNC-10 — Totals mismatch blocks commit

- **Area:** C5 Run · Commit · **Priority:** P2 · **Screen:** 4.5 · **Spec:** RUN-6 · **Type:** Dev-assisted
- **Preconditions:** DEV-ASSISTED: needs a test build with a fault hook that alters Loaded totals. Skip if not available.
- **Steps:**

    1. Enable the hook; run F02 to Commit.

- **Expected:** Totals check shows mismatch; Commit disabled with no override option.

### CONV-01 — Number conversion and rounding

- **Area:** C5 Run · Conversion · **Priority:** P1 · **Screen:** 4.3, 7.4 · **Spec:** MAP-10, T13, T14 · **Type:** Functional
- **Preconditions:** TPL-C (F17, Amount 2 decimals, Amount0 0 decimals, Is a number = Warning). Run with F17 committed.
- **Steps:**

    1. Export the run data (plain UTF-8, comma).
    2. Compare Amount and Amount0 per Case with Fixtures > F17 expected column.

- **Expected:** C01 123456.79 / 123457; C02 1234567.50 / 1234568; C03 -1234.00 / -1234; C04 2.35 / 2; C05 -2.35 / -2; C06 2.50 / 3; C07 -2.50 / -3; C08 500.00 / 500; C09 750.00 / 750; C10 0.01 / 0; C11 blank / blank (2 warnings: value is not a number, original text 12abc in the issue list); C12 and C13 blank with no issue.

### CONV-02 — Text dates in two formats

- **Area:** C5 Run · Conversion · **Priority:** P1 · **Screen:** 4.3 · **Spec:** MAP-10 · **Type:** Functional
- **Preconditions:** CONV-01 run.
- **Steps:**

    1. Compare Doc Date (DD-MM-YYYY) and Due Date (DD/MM/YYYY) in the export with F17 expected.

- **Expected:** Valid dates export as DD-MM-YYYY (05/11/2026 → 05-11-2026). 31-11-2026, 29-02-2027 and 32/01/2027 are blank with Is a date warnings keeping the original text; 29-02-2028 is valid.

### CONV-03 — Text kept exactly as typed

- **Area:** C5 Run · Conversion · **Priority:** P1 · **Screen:** — · **Spec:** MAP-9, T14 · **Type:** Functional
- **Preconditions:** CONV-01 run.
- **Steps:**

    1. Open the export in a text editor; check Code.

- **Expected:** 00123 keeps its leading zeros; " A1 " keeps both spaces; spaces-only becomes blank; MIXED Case unchanged.

### CONV-04 — Windows-1252 CSV

- **Area:** C5 Run · Conversion · **Priority:** P1 · **Screen:** 7.4 · **Spec:** IN-4, T12, EXP-3 · **Type:** Functional
- **Preconditions:** Template from F18 (C3-08). Run with F18 committed.
- **Steps:**

    1. Export data as UTF-8 with BOM.
    2. Open the export in Excel.

- **Expected:** Café, Müller, Señor show correctly in Excel.

### CONV-05 — Excel values: formulas, errors, times

- **Area:** C5 Run · Conversion · **Priority:** P1 · **Screen:** — · **Spec:** T11, MAP-10 · **Type:** Functional
- **Preconditions:** TPL-C Settings: sheets = first visible sheet. Run with F19 Conversion_Values.xlsx.
- **Steps:**

    1. Validate and commit; export data.

- **Expected:** Formula cell =100*1.5 → 150.00 (last calculated value). #N/A cell → blank with Is a number warning, value "#N/A". Excel date-time 05-11-2026 14:30 → 05-11-2026. Text cell 00123 → 00123.

### CONV-06 — Excel values in .xls and .xlsb

- **Area:** C5 Run · Conversion · **Priority:** P2 · **Screen:** — · **Spec:** T11, MAP-10 · **Type:** Functional
- **Preconditions:** As CONV-05 (added 20-11-2026, D38).
- **Steps:**

    1. Run with F24 Conversion_Values.xls; validate and commit; export data.
    2. Run with F25 Conversion_Values.xlsb; validate and commit; export data.

- **Expected:** Each run as CONV-05.

### C6-01 — Run header

- **Area:** C6 Run · **Priority:** P1 · **Screen:** 5.1 · **Spec:** UX-9, T19 · **Type:** Functional
- **Preconditions:** R-0003 committed.
- **Steps:**

    1. Open R-0003.

- **Expected:** Breadcrumb; "R-0003" with badge Committed with override; Export data; … menu with Export issue list, Export left-out rows, Delete run; a summary line.

### C6-02 — Summary tab with override (R-0003)

- **Area:** C6 Run · **Priority:** P1 · **Screen:** 5.1 · **Spec:** RUN-12, T18 · **Type:** Functional
- **Preconditions:** R-0003.
- **Steps:**

    1. Summary tab.

- **Expected:** Shows: files and sheets read (1); rows read 2,000; rows loaded 1,937; rows left out 63 (rows with errors 60, later duplicates 3, blank rows 0); errors 66, warnings 32; totals check as RUNC-02; comment and override reason.

### C6-03 — Summary shows hidden and blank rows (R-0002)

- **Area:** C6 Run · **Priority:** P2 · **Screen:** 5.1 · **Spec:** RUN-12, IN-13 · **Type:** Functional
- **Preconditions:** R-0002.
- **Steps:**

    1. Summary tab.

- **Expected:** Rows loaded 4,000; rows left out 10, all blank rows; hidden rows 25 and hidden sheet Old skipped. Rows read as recorded in RUNV-02.

### C6-04 — Summary shows mapping and alias (R-0004)

- **Area:** C6 Run · **Priority:** P2 · **Screen:** 5.1 · **Spec:** RUN-12 · **Type:** Functional
- **Preconditions:** R-0004.
- **Steps:**

    1. Summary tab.

- **Expected:** Lists the alias Inv No saved for Invoice No, State left as null, Remarks left out.

### C6-05 — Issues tab

- **Area:** C6 Run · **Priority:** P1 · **Screen:** 5.1 · **Spec:** ISS-4 · **Type:** Functional
- **Preconditions:** R-0003.
- **Steps:**

    1. Issues tab.

- **Expected:** 98 stored issues, same rows and order as at Validate; filter and sort work.

### C6-06 — Outputs tab and Export all outputs

- **Area:** C6 Run · **Priority:** P1 · **Screen:** 5.1 · **Spec:** DO-7, EXP-1 · **Type:** Functional
- **Preconditions:** R-0001.
- **Steps:**

    1. Outputs tab; toggle Show subtotals on DO2.
    2. Export one output.
    3. Export all outputs to an empty folder.

- **Expected:** Saved outputs match RUNO-01. Export all writes exactly 2 CSV files (one per output) named by the template pattern.

### C6-07 — Source files tab

- **Area:** C6 Run · **Priority:** P1 · **Screen:** 5.1 · **Spec:** UX-9, RUN-2 · **Type:** Functional
- **Preconditions:** R-0002.
- **Steps:**

    1. Source files tab.

- **Expected:** Row: Sales_Nov.xlsx · full path · size · modified date · sheet Sales · header row 2 · rows loaded 4,000 · hidden data skipped (25 rows, sheet Old).

### C6-08 — Comment can't be edited after commit

- **Area:** C6 Run · **Priority:** P2 · **Screen:** 5.1 · **Spec:** RUN-13 · **Type:** Functional
- **Preconditions:** R-0001.
- **Steps:**

    1. Try to edit the comment on Summary.

- **Expected:** Comment is read-only.

### C6-09 — Delete a run

- **Area:** C6 Run · **Priority:** P1 · **Screen:** 7.2 · **Spec:** RUN-9, UI-8 · **Type:** Functional
- **Preconditions:** R-0006 committed. AN-1 saved.
- **Steps:**

    1. C4 Runs > R-0006 … > Delete.
    2. Read the dialog; tick I understand; Delete.
    3. Check C4, C1 footer, AN-1 runs list, data folder.

- **Expected:** Dialog lists 500 rows, the issue list and 2 saved outputs. After delete: R-0006 gone; rows stored drops by 500; R-0006 no longer listed in AN-1; t\…\runs\<id> folder removed.

### C6-10 — Saved outputs are never recalculated

- **Area:** C6 Run · **Priority:** P1 · **Screen:** 5.1 · **Spec:** DO-6 · **Type:** Functional
- **Preconditions:** C4-06 done.
- **Steps:**

    1. Open R-0001 > Outputs > DO1.

- **Expected:** Still the original 3 measures and values (RUNO-01).

### A0-01 — List and search

- **Area:** A0 Saved analyses · **Priority:** P2 · **Screen:** 6.1 · **Spec:** UX-10, ANA-1 · **Type:** Functional
- **Preconditions:** AN-1 and AN-2 saved on TPL-A; one analysis on TPL-D.
- **Steps:**

    1. Open Analysis.
    2. Search "Regional", then "Acme", then "State".

- **Expected:** Header "Analyses", search, New analysis. Grid Name · Client · Template · Saved on · … (Rename, Duplicate, Delete). Search matches name, client and template.

### A0-02 — Open a saved analysis: settings locked

- **Area:** A0 Saved analyses · **Priority:** P1 · **Screen:** 6.3 · **Spec:** ANA-1, D33 · **Type:** Functional
- **Preconditions:** AN-1 saved.
- **Steps:**

    1. Open AN-1.
    2. Try to change a filter, group, measure or Show subtotals.
    3. Click Run with nothing ticked.

- **Expected:** Settings are locked; only the runs list can change; no run is ticked; Run is unavailable until at least one run is ticked.

### A0-03 — Duplicate a saved analysis

- **Area:** A0 Saved analyses · **Priority:** P2 · **Screen:** 6.3 · **Spec:** ANA-1 · **Type:** Functional
- **Preconditions:** AN-1.
- **Steps:**

    1. … > Duplicate.
    2. Change a measure; Run; click Clients in the rail.

- **Expected:** Duplicate opens as a new, editable, unsaved analysis with AN-1's settings. Leaving with a result prompts Save… / Leave without saving / Stay.

### A0-04 — Rename and name uniqueness

- **Area:** A0 Saved analyses · **Priority:** P2 · **Screen:** 6.1 · **Spec:** ANA-1 · **Type:** Functional
- **Preconditions:** AN-1, AN-2.
- **Steps:**

    1. Rename AN-2 to AN-1's name.
    2. Rename AN-2 to "GSTIN check v2".

- **Expected:** 1 refused (unique within template). 2 accepted.

### A0-05 — Delete a saved analysis

- **Area:** A0 Saved analyses · **Priority:** P2 · **Screen:** Not drawn · **Spec:** UX §5 Destructive · **Type:** Functional
- **Preconditions:** A spare analysis.
- **Steps:**

    1. … > Delete.

- **Expected:** A plain confirmation (no "I understand" tick); analysis removed.

### A1-01 — Layout and data selection

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-2, ANA-3 · **Type:** Functional
- **Preconditions:** TPL-A R-0001 to R-0006 committed (before C6-09).
- **Steps:**

    1. New analysis.
    2. Client Acme Traders > Template Sales Register.
    3. Hover a run's file names; click Select all.

- **Expected:** Settings panel 380 px on the left, result on the right. Runs list shows Run ID and file names only, with Select all; label "6 of 6 runs selected" after Select all.

### A1-02 — Changing template clears settings

- **Area:** A1 Analysis · **Priority:** P2 · **Screen:** 6.2 · **Spec:** ANA-3 · **Type:** Functional
- **Preconditions:** A1-01 with a group and a measure set.
- **Steps:**

    1. Change Template to the duplicate (C2-06). Cancel. 2. Change again, confirm.

- **Expected:** A confirmation appears; cancel keeps everything; confirm clears filters, groups, measures and runs.

### A1-03 — Basic result with grand total

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-5..7, MEA-1, MEA-7 · **Type:** Functional
- **Preconditions:** R-0001 ticked only.
- **Steps:**

    1. Group by State. Measures: + Add column Taxable Value, tick Sum; + Add column Invoice No, tick Count. Run.

- **Expected:** Headers "State", "Taxable Value · Sum", "Invoice No · Count" (A2, MEA-7). Flat table: Delhi 1,903,437.50 · 1,250; Gujarat 1,877,812.50 · 1,250; Karnataka 1,890,625.00 · 1,250; Maharashtra 1,865,000.00 · 1,250; grand total pinned 7,536,875.00 · 5,000.

### A1-04 — Measures and renaming

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-6, MEA-1 to MEA-8 · **Type:** Functional
- **Preconditions:** R-0001 ticked.
- **Steps:**

    1. No group. Measures: + Add column Taxable Value, tick Sum, Count, Avg, Min, Max; + Add column Customer, tick Distinct; + Add column GSTIN, tick Distinct. Run.
    2. Click ✎ on the "Taxable Value · Average" header, type "Avg value", press Enter.

- **Expected:** Step 1 headers, in order: "Taxable Value · Sum", "Taxable Value · Count", "Taxable Value · Average", "Taxable Value · Min", "Taxable Value · Max", "Customer · Count distinct", "GSTIN · Count distinct" (A2, MEA-6, MEA-7). Step 2: the header reads "Avg value"; the result is not re-run or greyed (MEA-8). Sum 7,536,875.00; Count 5,000; Avg value 1,507.38; Min 1,000.00; Max 2,014.75; Count distinct Customer 10; Count distinct GSTIN 5,000.

### A1-05 — Subtotals and sorting within groups

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-7, T23, MEA-7 · **Type:** Functional
- **Preconditions:** R-0001 ticked.
- **Steps:**

    1. Group State then GST Rate; + Add column Taxable Value, tick Sum (header "Taxable Value · Sum"); Show subtotals on; Run.
    2. Sort "Taxable Value · Sum" descending.

- **Expected:** 20 detail rows, 4 subtotal rows, pinned grand total 7,536,875.00. Maharashtra: 0% 352,500.00; 5% 393,500.00; 12% 383,250.00; 18% 373,000.00; 28% 362,750.00; subtotal 1,865,000.00. After sort, rows sort within each state (Maharashtra: 5%, 12%, 18%, 28%, 0%), subtotals stay with their state.

### A1-06 — Group levels reorder and date grain

- **Area:** A1 Analysis · **Priority:** P2 · **Screen:** 6.2 · **Spec:** ANA-5 · **Type:** Functional
- **Preconditions:** R-0001 ticked.
- **Steps:**

    1. Group by Invoice Date (Day); Count Invoice No; Run.
    2. Switch grain to Month, Quarter, Year; Run each.
    3. Add State; move it above Invoice Date with ↑; Run.

- **Expected:** Day: 31 rows; 01-10-2026 = 162, 31-10-2026 = 161. Month/Quarter/Year: one row of 5,000. Reordering changes the grouping order.

### A1-07 — Date filters

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-4 · **Type:** Functional
- **Preconditions:** R-0001 and R-0002 ticked.
- **Steps:**

    1. Invoice Date Month is October 2026; Count; Run.
    2. Quarter is Q4 2026.
    3. Between 01-11-2026 and 15-11-2026.
    4. Blank (then tick R-0006 only).

- **Expected:** 1: 5,000 (7,536,875.00). 2: 9,000. 3: 2,005 (R-0002 rows dated 01-11-2026 to 15-11-2026). 4: 0 for R-0001/2; 500 for R-0006.

### A1-08 — Text filters

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-4, T23 · **Type:** Functional
- **Preconditions:** R-0001 ticked (then R-0003).
- **Steps:**

    1. Customer Is one of: open the list.
    2. Customer Contains "patel".
    3. R-0003 only: Customer Blank; then State Is one of Goa.

- **Expected:** 1: list shows the 10 customers with counts (500 each) and a search box. 2: 500 rows (ignores case). 3: Blank = 7; Goa = 25.

### A1-09 — Number filters and AND

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-4 · **Type:** Functional
- **Preconditions:** R-0001 ticked.
- **Steps:**

    1. GST Rate Equals 18 AND State Is one of Maharashtra; Sum Taxable Value; Run.
    2. Taxable Value Between 1000 and 1010.25.

- **Expected:** No dropdown for Number filters. 1: 250 rows, 373,000.00. 2: 100 rows (values 1,000.00 and 1,010.25).

### A1-10 — Count counts non-blank values only

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** T23, T18 · **Type:** Functional
- **Preconditions:** R-0003 ticked.
- **Steps:**

    1. Count Customer and Count Invoice No; Run.

- **Expected:** Count Customer 1,930; Count Invoice No 1,937 (left-out rows are never in analyses).

### A1-11 — Run, Cancel and changed settings

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-8, UI-5 · **Type:** Functional
- **Preconditions:** TPL-P with 12 runs.
- **Steps:**

    1. Start PERF-05's analysis; click Cancel.
    2. Change any setting after a result.

- **Expected:** Progress with Cancel; after Cancel the previous result is greyed. Changing a setting greys the result with "Settings changed: Run again".

### A1-12 — Result capped at 100,000 rows on screen

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-7, ANA-9 · **Type:** Functional
- **Preconditions:** TPL-P, one run ticked.
- **Steps:**

    1. Group by Customer ID; Count Invoice No; Run.
    2. Export the result.

- **Expected:** Grid shows the first 100,000 rows with a note that there are more; the grand total is pinned. Export has all ~1,000,000 group rows plus total, which is over 1,000,000 data rows, so it is written as 2 parts (A2, EXP-8): _part01of02 with 1,000,000 data rows and _part02of02 with the rest; the grand total is the last data row of the last part (T38).

### A1-13 — Save an analysis

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 7.8 · **Spec:** ANA-1 · **Type:** Functional
- **Preconditions:** A1-03 result.
- **Steps:**

    1. Save… > empty name. 2. Name "State sales" (AN-1); save. 3. Create AN-2 "GSTIN check": Group by State; Count distinct GSTIN; save.

- **Expected:** Name required and unique within the template. Saved analyses appear in A0 with Saved on date.

### A1-14 — Leaving an unsaved result

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 7.7 · **Spec:** ANA-2 · **Type:** Functional
- **Preconditions:** A new analysis with a result, unsaved.
- **Steps:**

    1. Click Clients. Choose Stay. 2. Again; Leave without saving. 3. Return to Analysis.

- **Expected:** Prompt Save… / Leave without saving / Stay. After leaving, the ad-hoc analysis is gone (not kept when switching rails).

### A1-15 — Distinct value picker on a large column

- **Area:** A1 Analysis · **Priority:** P2 · **Screen:** 6.2 · **Spec:** ANA-4 · **Type:** Functional
- **Preconditions:** TPL-P with 12 runs ticked.
- **Steps:**

    1. Filter Customer ID Is one of: open the list.
    2. Search a customer ID; Cancel during loading once.

- **Expected:** Spinner while loading with Cancel; shows the top 1,000 values by count; search finds values beyond the top 1,000.

### EXP-01 — Export dialog contents

- **Area:** Export · **Priority:** P1 · **Screen:** 7.4 · **Spec:** EXP-2..4 · **Type:** Functional
- **Preconditions:** R-0001.
- **Steps:**

    1. Export data.

- **Expected:** Folder and file name prefilled from template defaults; delimiter (comma, semicolon, tab, pipe); encoding (UTF-8 with BOM default, plain UTF-8). Only CSV is offered (no .xlsx).

### EXP-02 — Run data export columns and formats

- **Area:** Export · **Priority:** P1 · **Screen:** 7.4 · **Spec:** EXP-3, EXP-6, RUN-11 · **Type:** Functional
- **Preconditions:** R-0002, default options.
- **Steps:**

    1. Export; open in a text editor.

- **Expected:** Header: 8 template columns (+ Branch once added) + Source File, Source Sheet, Source Row, Run ID. 4,000 data rows. Numbers without grouping (1000.00); dates DD-MM-YYYY; first data row has Source Row 3 (header row 2); Run ID R-0002.

### EXP-03 — BOM and delimiters

- **Area:** Export · **Priority:** P1 · **Screen:** 7.4 · **Spec:** EXP-3 · **Type:** Functional
- **Preconditions:** R-0001.
- **Steps:**

    1. Export with UTF-8 with BOM; run PowerShell: Format-Hex <file> -Count 3.
    2. Export plain UTF-8; check the same.
    3. Export with semicolon, tab, pipe.

- **Expected:** 1: EF BB BF. 2: no BOM (first byte of the header). 3: correct delimiter in each file.

### EXP-04 — Left-out rows export

- **Area:** Export · **Priority:** P1 · **Screen:** 7.4 · **Spec:** T19, EXP-1 · **Type:** Functional
- **Preconditions:** R-0003.
- **Steps:**

    1. … > Export left-out rows.

- **Expected:** 63 rows with the data columns + Source File/Sheet/Row + Run ID + Reason (rule names that caused it).

### EXP-05 — Issue list export from the run

- **Area:** Export · **Priority:** P2 · **Screen:** 7.4 · **Spec:** ISS-3 · **Type:** Functional
- **Preconditions:** R-0003.
- **Steps:**

    1. … > Export issue list.

- **Expected:** 98 rows; columns File, Sheet, Row, Column, Value, Rule, Severity, Message.

### EXP-06 — Overwrite confirmation

- **Area:** Export · **Priority:** P2 · **Screen:** 7.4 · **Spec:** EXP-4 · **Type:** Functional
- **Preconditions:** An export file already exists.
- **Steps:**

    1. Export to the same name. Cancel at the prompt. 2. Repeat and confirm.

- **Expected:** Confirmation before overwriting; cancel keeps the old file.

### EXP-07 — Invalid file-name characters

- **Area:** Export · **Priority:** P3 · **Screen:** 7.4 · **Spec:** Tech spec Exports · **Type:** Functional
- **Preconditions:** Template renamed "GST: Q3/Q4" (if names allow), else set the file name to that in the dialog.
- **Steps:**

    1. Export.

- **Expected:** Characters Windows doesn't allow (: / \ * ? " < > |) become _.

### EXP-08 — Export progress, Cancel and Open folder

- **Area:** Export · **Priority:** P1 · **Screen:** 7.5 · **Spec:** EXP-7, UI-5, EXP-10, EXP-11, EXP-14, T33, T35 · **Type:** Functional
- **Preconditions:** TPL-P run with 10M rows.
- **Steps:**

    1. Export data; Cancel midway; check the folder and %TEMP%\Sankalan.
    2. Export again to completion; click Open folder.

- **Expected:** Progress with Cancel, showing the stage, rows written of 10,000,000 and "part K of 10" (A2, EXP-11). After Cancel no part file and no .partial file remains in the folder, and no chunk file in %TEMP%\Sankalan (A2, EXP-14). When done, the export is 10 files, _part01of10 to _part10of10 (EXP-10), and the banner reads "Exported 10,000,000 rows to 10 files" with Open folder; Open folder opens Explorer at the folder.

### SH-01 — Window never freezes during long operations

- **Area:** Shared states · **Priority:** P1 · **Screen:** 4.3 · **Spec:** UI-5, NF-3 · **Type:** Functional
- **Preconditions:** TPL-P run with P01 at Validate.
- **Steps:**

    1. While validating: drag and resize the window, hover grids, open the rail items.

- **Expected:** Window repaints and responds throughout; progress keeps moving.

### SH-02 — One long job at a time

- **Area:** Shared states · **Priority:** P2 · **Screen:** — · **Spec:** T6 · **Type:** Functional
- **Preconditions:** A validate in progress on TPL-P.
- **Steps:**

    1. Go to Analysis and try to Run an analysis (or Export from another run).

- **Expected:** The second long operation is not started alongside; record how the app tells the user (not specified).

### SH-03 — Closing during a cancellable job

- **Area:** Shared states · **Priority:** P1 · **Screen:** — · **Spec:** Tech spec Closing · **Type:** Functional
- **Preconditions:** A validate or export in progress.
- **Steps:**

    1. Click the window's close button. Choose not to close. 2. Close again and confirm.

- **Expected:** Prompt "Cancel [operation] and close?". No keeps working; Yes cancels and closes; on restart nothing partial remains.

### SH-04 — Closing during commit waits

- **Area:** Shared states · **Priority:** P2 · **Screen:** — · **Spec:** RUN-5, Tech spec Closing · **Type:** Functional
- **Preconditions:** TPL-P run at Commit.
- **Steps:**

    1. Click Commit; immediately click the close button.

- **Expected:** App waits for the commit to finish, then closes; after restart the run is committed.

### SH-05 — Success banners

- **Area:** Shared states · **Priority:** P3 · **Screen:** 5.1 · **Spec:** UX §5 Success · **Type:** Functional
- **Preconditions:** Any commit and export.
- **Steps:**

    1. Commit a run. 2. Finish an export.

- **Expected:** A brief banner on the next screen; the export banner has Open folder.

### FIT-01 — All screens at 1366×768, 100%

- **Area:** Screen fit · **Priority:** P1 · **Screen:** All · **Spec:** UI-2, ENV-4 · **Type:** Screen fit
- **Preconditions:** Display 1366×768, scaling 100%. App maximised.
- **Steps:**

    1. Open every screen/dialog in the Coverage tab with realistic data (TPL-A after R-0005).
    2. Mark column "1366×768 100%" per screen.

- **Expected:** No window scrollbar on any screen; nothing clipped; grids and long panels scroll inside themselves.

### FIT-02 — All screens at 1920×1080, 125%

- **Area:** Screen fit · **Priority:** P1 · **Screen:** All · **Spec:** UI-2, NF-4 · **Type:** Screen fit
- **Preconditions:** Display 1920×1080, scaling 125%.
- **Steps:**

    As FIT-01; mark column "1920×1080 125%".

- **Expected:** As FIT-01. Grids show more rows than at 1366×768; buttons and settings panel keep their size.

### FIT-03 — All screens at 1920×1080, 150%

- **Area:** Screen fit · **Priority:** P1 · **Screen:** All · **Spec:** UI-2, NF-4 · **Type:** Screen fit
- **Preconditions:** Display 1920×1080, scaling 150%.
- **Steps:**

    As FIT-01; mark column "1920×1080 150%".

- **Expected:** As FIT-01; text stays sharp (no bitmap scaling blur).

### FIT-04 — Minimum window size

- **Area:** Screen fit · **Priority:** P2 · **Screen:** — · **Spec:** UX §1 · **Type:** Screen fit
- **Preconditions:** 1920×1080 at 100%.
- **Steps:**

    1. Restore the window and drag its corner to make it as small as possible.

- **Expected:** Window can't be made smaller than 1366×768.

### PERF-01 — Load 10M rows from CSV ≤ 2 min

- **Area:** Performance · **Priority:** P1 · **Screen:** 4.1, 4.2, 4.3, 4.4, 4.5 · **Spec:** PERF-1, T4, T7 · **Type:** Performance
- **Preconditions:** PERF laptop: 16 GB RAM, 4 cores, SSD, Windows 11, fresh install, nothing else running. TPL-P "Perf 20 col" from P01 with the TPL-P rules, no default outputs.
- **Steps:**

    1. New run > add P01.
    2. Start a stopwatch when you click Next on Files; stop when the Commit step shows the totals check.
    3. Commit; record commit time.
    4. Repeat 3 times.

- **Expected:** Median ≤ 2 min (PERF-1, includes validation and totals check). Commit about 1 s. Record peak memory of Sankalan.exe (DuckDB capped at 8 GB). Misses are reported, not blocking. (A2: the load now also includes the Convert sort of data.parquet by file and row (T32) and writing the text companions of Number and Date columns (T41); A2-6 compares it with the pre-A2 build.)

### PERF-02 — Load 10M rows from 10 .xlsx ≤ 5 min

- **Area:** Performance · **Priority:** P1 · **Screen:** 4.1, 4.2, 4.3, 4.4, 4.5 · **Spec:** PERF-2, T15, T5 · **Type:** Performance
- **Preconditions:** PERF laptop: 16 GB RAM, 4 cores, SSD, Windows 11, fresh install, nothing else running. TPL-P "Perf 20 col" from P01 with the TPL-P rules, no default outputs.
- **Steps:**

    1. New run > add P02-01 … P02-10.
    2. Time as PERF-01.

- **Expected:** Median ≤ 5 min (provisional target). Task Manager shows reader worker processes (up to cores − 1) during reading. (A2: the load now also includes the Convert sort (T32) and the text companions (T41), as PERF-01.)

### PERF-03 — Analysis on one run ≤ 3 s

- **Area:** Performance · **Priority:** P1 · **Screen:** 6.2 · **Spec:** PERF-3 · **Type:** Performance
- **Preconditions:** TPL-P with one 10M-row run.
- **Steps:**

    1. Group State › Category › Invoice Date (Month); Sum Taxable Value, Count Invoice No, Average Rate; subtotals on.
    2. Time Run click → result shown; 3 times.

- **Expected:** Median ≤ 3 s; groups under 10,000 (4 × 20 × 1 = 80 + subtotals).

### PERF-04 — Same analysis across 12 runs ≤ 15 s

- **Area:** Performance · **Priority:** P1 · **Screen:** 6.2 · **Spec:** PERF-4 · **Type:** Performance
- **Preconditions:** TPL-P with 12 runs (P01-01…12, or P01 loaded 12 times with Load anyway).
- **Steps:**

    1. Tick all 12 runs; run PERF-03's analysis; 3 times.

- **Expected:** Median ≤ 15 s.

### PERF-05 — ~1M groups across 12 runs ≤ 60 s, cancellable

- **Area:** Performance · **Priority:** P1 · **Screen:** 6.2 · **Spec:** PERF-5, R3 · **Type:** Performance
- **Preconditions:** PERF-04 data.
- **Steps:**

    1. Group State › Customer ID; Count distinct Invoice No; subtotals on; Run; time it.
    2. Run again and Cancel at 10 s; time until the panel is usable.

- **Expected:** Completes ≤ 60 s. Cancel stops within a few seconds; previous result greyed; app responsive.

### PERF-06 — Export a 1M-row result ≤ 5 s

- **Area:** Performance · **Priority:** P1 · **Screen:** 7.4 · **Spec:** PERF-6 · **Type:** Performance
- **Preconditions:** PERF-05 result (about 1M rows).
- **Steps:**

    1. Export (UTF-8 with BOM); time OK → done.

- **Expected:** ≤ 5 s; file row count equals the result rows (+ header).

### PERF-07 — Responsiveness under load

- **Area:** Performance · **Priority:** P2 · **Screen:** 4.3 · **Spec:** NF-3, UI-5 · **Type:** Performance
- **Preconditions:** PERF-01 in progress.
- **Steps:**

    1. Drag the window; click tabs; press Cancel and time the response.

- **Expected:** Window responds immediately; Cancel takes effect within about 3 s (workers stopped after 2 s).

### PERF-08 — Disk use per 10M-row run

- **Area:** Performance · **Priority:** P2 · **Screen:** 1.1 · **Spec:** NF-9 · **Type:** Performance
- **Preconditions:** PERF-01 done.
- **Steps:**

    1. Record data folder size before and after each committed 10M-row run.

- **Expected:** Record GB per run (feeds the low-disk threshold in C1-10 / RUNF-14).

## Test cases A2 (Feature-Updates)

One case per acceptance criterion of Feature Spec A2 §10 (the Spec field names the AC and its feature items), one per performance target of Feature Spec A2 §9, and three extra cases from Technical Spec A2 §15.3. Where Technical Spec A2 §15.1 corrects Feature Spec A2, the expected result follows the Technical Spec and the Spec field names the T-number. Reference templates TPL-R, TPL-N and TPL-S and their run sequences are in the Read me; figures are for the full-size fixtures F-A2-01 to F-A2-05.

### A2-ROW-01 — Summary | Rows switch and Rows mode

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.2, 6.4 · **Spec:** AC-ROW-1, ROW-1, ROW-3 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed (P8 setup).
- **Steps:**

    1. Open Analysis > New analysis.
    2. Read the switch next to the title.
    3. Choose Rows.

- **Expected:** New analysis opens in Summary (switch Summary | Rows, Summary selected). In Rows the builder shows a Columns section and a Run button; there are no group levels, no measures and no Save button; the header reads "Row views aren't saved".

### A2-ROW-02 — Switching keeps runs and filters, and Summary's settings

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.2, 6.4 · **Spec:** AC-ROW-2, ROW-2 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis in Summary: Client Rao & Co, template TPL-R; tick R-0001 and R-0002.
    2. Filters: State is one of Maharashtra, Gujarat; Taxable Value Not blank.
    3. Group by State, then Invoice Date (Month). + Add column Rows; + Add column Taxable Value, tick Sum and Max. Run.
    4. Switch to Rows.
    5. Switch back to Summary.

- **Expected:** In Rows, R-0001 and R-0002 are still ticked and both filters are kept; the result is cleared ("Pick runs and filters, then press Run"). Back in Summary the two group levels and the three measures (Rows · Count, Taxable Value · Sum, Taxable Value · Max) are as set; the result is cleared.

### A2-ROW-03 — Leaving clears the Rows view and cancels its Job

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4 · **Spec:** AC-ROW-3, ROW-3 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis > Rows; TPL-R; tick R-0001; Run and wait for the result.
    2. Click Clients on the left rail, then Analysis > New analysis.
    3. Rows; tick R-0001 to R-0003; Run. While the progress panel shows "Counting rows" or "Fetching the first 100,000", click Clients.
    4. Return to Analysis > New analysis.

- **Expected:** Step 2: no prompt; the builder is empty (no client, template, runs, filters or result). Step 3: no prompt; the Rows Job is cancelled at once (the rail shows no running Job and another long operation can start). Step 4: the builder is empty.

### A2-ROW-04 — No switch on a saved analysis

- **Area:** A2 Rows view · **Priority:** P2 · **Screen:** 6.3 · **Spec:** AC-ROW-4, ROW-4 · **Type:** Functional
- **Preconditions:** A saved analysis exists (AN-1 "State sales" from A1-13).
- **Steps:**

    1. Analysis > open AN-1.

- **Expected:** No Summary | Rows switch is shown; the saved analysis is a Summary.

### A2-ROW-06 — Is not a number and Is not a date in the Rows view

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4, 6.5, 6.6 · **Spec:** AC-ROW-6, ROW-6, TXT-6, TXT-7, T55 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. Rows; TPL-R; tick R-0001. Add filter on Taxable Value; read the operators and the help text under Is not a number; choose Is not a number. Run.
    2. Switch to Summary (same run and filter); + Add column Rows; Run.
    3. Rows; tick R-0002 only. Replace the filter with Invoice Date Is not a date (read the operators and help text). Run.
    4. Switch to Summary; Run.

- **Expected:** The Taxable Value filter offers Equals, Between, Blank, Not blank, Is not a number, with help text "Cells with text such as NA or Nil instead of a number". The Invoice Date filter offers Year is, Quarter is, Month is, Between, Blank, Not blank, Is not a date, with help text "Cells with text such as NA instead of a date". Step 1: "1,510 rows match"; step 2: Rows · Count 1,510. Step 3: "305 rows match"; step 4: Rows · Count 305.

### A2-ROW-07 — Columns section

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4 · **Spec:** AC-ROW-7, ROW-7, 8.9 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. Rows; TPL-R; tick R-0001 to R-0003. Read the Columns section.
    2. Untick every column; press Run.

- **Expected:** Columns lists all 21 TPL-R columns in template order (Place of Supply last), each ticked, with ↑ ↓; the header reads "21 of 21 ticked". With none ticked, Run shows "Tick at least one column" under Columns and nothing runs (no progress panel, no result).

### A2-ROW-08 — Source columns on screen and in every export

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4, 7.9 · **Spec:** AC-ROW-8, ROW-8, D40 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. Empty folder C:\SankalanTest\Out\Rows.
- **Steps:**

    1. Rows; TPL-R; tick R-0001; filter Taxable Value Is not a number; Run. Read the grid's columns.
    2. Tick Show them on screen; read the columns. Untick it.
    3. Export rows (.csv) to C:\SankalanTest\Out\Rows; open the file in Notepad.
    4. Tick only Taxable Value, Invoice No and State, in that order (↑ ↓); export again under another name; open it.
    5. Tick Show them on screen; export a third time; open it.

- **Expected:** Step 1: only the 21 ticked columns; no source columns. Step 2: Source File, Source Sheet, Source Row and Run ID follow the ticked columns, in that order. Every export (steps 3–5) has the ticked columns in their order, then Source File, Source Sheet, Source Row, Run ID, whether or not Show them on screen is ticked. Source Sheet is "Sales A" or "Sales B" for rows from TPLR_R1_Sales.xlsx and empty for rows from TPLR_R1_Part1.csv; Run ID is "R-0001".

### A2-ROW-09a — Settings changes grey the result

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4 · **Spec:** AC-ROW-9a, ROW-9, ROW-5 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed; TPL-N exists (or any second template of Rao & Co).
- **Steps:**

    1. Rows; TPL-R; tick R-0001 and R-0002; filter State is one of Maharashtra; Run.
    2. Change the filter to Maharashtra, Gujarat.
    3. Run; then untick R-0002.
    4. Run; then change the template to TPL-N and continue at the confirmation.

- **Expected:** After steps 2 and 3 the result is greyed with "Settings changed: Run again" and Export rows is disabled. Step 4: a confirmation first (ROW-5); Cancel keeps everything; continuing clears the settings and the result, as in Summary, so no greyed result is left (interpretation recorded in docs/PROGRESS.md, A2-5, 22-11-2026, where AC-ROW-9a's "the template greys the result" and ROW-5 differ).

### A2-ROW-09b — Column changes redraw the grid without a Job

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4 · **Spec:** AC-ROW-9b, ROW-9, P1 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. Rows; TPL-R; tick R-0001; Run. Note the result header.
    2. Untick Customer. Tick it again.
    3. Move Taxable Value to the top of Columns with ↑.
    4. Tick Show them on screen.

- **Expected:** Each change redraws the grid at once: Customer goes and comes back; Taxable Value becomes the first (frozen) column; the source columns appear after the ticked columns. The result is never greyed, no progress panel or Cancel appears (no Job), and the result header (match count, rows searched, time) is unchanged.

### A2-ROW-10 — Match count and rows searched

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4 · **Spec:** AC-ROW-10, ROW-10 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. Rows; TPL-R; tick R-0001, R-0002 and R-0003; filters State is one of Maharashtra; Taxable Value Not blank. Run.
    2. Switch to Summary with the same runs and filters; + Add column Rows; Run.
    3. Back in Rows, remove both filters; Run.

- **Expected:** Step 1: the header reads "N rows match · 3 runs · 7,499,937 rows searched · T s". N equals Rows · Count in step 2 (the automated test also compares it with an independent count(*)). Step 3: "7,499,937 rows match · 3 runs · 7,499,937 rows searched · T s". Rows searched is the rows loaded in the ticked runs (2,500,000 + 2,499,937 + 2,500,000).

### A2-ROW-11a — First 100,000 rows and the footer

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4 · **Spec:** AC-ROW-11a, ROW-11, D42 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. Rows; TPL-R; tick R-0001 to R-0003; no filters; Run. Scroll to the end of the grid.
    2. Tick R-0001 only; filter Taxable Value Is not a number; Run.

- **Expected:** Step 1: the grid holds exactly 100,000 rows and the footer reads "Showing the first 100,000 of 7,499,937 rows, in the order they were loaded. Export gets all of them." Step 2: the grid holds 1,510 rows and the footer reads "Showing all 1,510 rows".

### A2-ROW-11b — No sorting; the grid is the start of the export

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4, 7.9 · **Spec:** AC-ROW-11b, ROW-11, D71, T52 · **Type:** Functional
- **Preconditions:** A2-ROW-11a step 1 result on screen (R-0001 to R-0003, no filters), Show them on screen ticked.
- **Steps:**

    1. Click several column headers, including Invoice No and Taxable Value.
    2. Note Source File, Source Sheet, Source Row and Run ID of grid rows 1, 2 and 100,000.
    3. Export rows; open part 1 in Excel and read data rows 1, 2 and 100,000 (sheet rows 2, 3 and 100,001).

- **Expected:** Clicking a header changes nothing and no sort arrow appears. Data rows 1, 2 and 100,000 of part 1 hold the same values as grid rows 1, 2 and 100,000. (The automated test compares all 100,000 rows: the grid's rows equal the first 100,000 data rows of the export, in the same order.)

### A2-ROW-12a — The export holds every matching row

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 7.9 · **Spec:** AC-ROW-12a, ROW-12, EXP-8 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. Empty folder C:\SankalanTest\Out\Rows12a.
- **Steps:**

    1. Rows; TPL-R; tick R-0001 to R-0003; filter State is one of Maharashtra, Gujarat; Run. Note N.
    2. Export rows (.csv) to the folder; read the dialog.
    3. Count the data records in each part (Excel: used rows − 1, or PowerShell `(Import-Csv <part>).Count`) and add them up.

- **Expected:** The dialog title is "Export N rows" and the summary line says "K CSV files", K = N ÷ 1,000,000 rounded up. The data records of all K parts add up to N.

### A2-ROW-12b — Stored order, and repeatable exports

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 7.9 · **Spec:** AC-ROW-12b, ROW-12, 8.7, T32 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. Empty folders C:\SankalanTest\Out\OrderA and \OrderB (each export is about 2 GB).
- **Steps:**

    1. Rows; TPL-R; tick R-0001 to R-0003; no filters; Run. Export rows to OrderA.
    2. Without changing anything, export again to OrderB with the same file name.
    3. In the parts, read Run ID, Source File, Source Sheet and Source Row down the file (at least: the first and last rows of each part, and the rows where Run ID or Source File changes).
    4. Get-FileHash each part in OrderA and OrderB.

- **Expected:** Each folder holds 8 parts, _part01of08 to _part08of08 (7,499,937 rows). Run ID never goes back to an earlier run (R-0001 rows, then R-0002, then R-0003). Within each run the rows follow the run's file and sheet load order (files in the order they were added, sheets Sales A then Sales B) with Source Row ascending within each file and sheet. Each part in OrderA has the same SHA-256 as its namesake in OrderB.

### A2-ROW-13 — Left-out rows never appear

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4, 7.9 · **Spec:** AC-ROW-13, ROW-13, T18, D54 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed (R-0002 has 63 left-out rows).
- **Steps:**

    1. Open R-0002 > Export left-out rows; note the 63 rows' Source File and Source Row.
    2. Rows; TPL-R; tick R-0002 only; no filters; Run.
    3. Export rows; search the export for the 63 (Source File, Source Row) pairs.

- **Expected:** The left-out export has 63 rows. The Rows view reads "2,499,937 rows match · 1 run · 2,499,937 rows searched". None of the 63 pairs is in the export, so none is in the grid (the grid is the start of the export, A2-ROW-11b).

### A2-ROW-14 — A column added in a later run is blank for older runs

- **Area:** A2 Rows view · **Priority:** P1 · **Screen:** 6.4, 7.9 · **Spec:** AC-ROW-14, ROW-14, MAP-11 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed; the OrderA export from A2-ROW-12b.
- **Steps:**

    1. Rows; TPL-R; tick R-0001; filter Place of Supply Not blank; Run.
    2. Remove the filter; Run; scroll the grid right to Place of Supply.
    3. In the OrderA export, check Place of Supply on every row with Run ID R-0001.

- **Expected:** Step 1: "No rows match these filters." Step 2: Place of Supply is empty on every row. Step 3: Place of Supply is empty on every R-0001 row.

### A2-ROW-S1 — No matching rows

- **Area:** A2 Rows view · **Priority:** P2 · **Screen:** 6.4 · **Spec:** AC-ROW-S1, Feature Spec A2 2.4 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. Rows; TPL-R; tick R-0001; filter Place of Supply Not blank; Run.

- **Expected:** The result panel reads "No rows match these filters." and there is no Export rows button.

### A2-ROW-S2 — Cancel during Run

- **Area:** A2 Rows view · **Priority:** P2 · **Screen:** 6.4 · **Spec:** AC-ROW-S2, Feature Spec A2 2.4, UI-5 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. Rows; TPL-R; tick R-0001; Run and wait for the result.
    2. Tick R-0002 and R-0003; Run; press Cancel while the progress shows "Counting rows" or "Fetching the first 100,000".

- **Expected:** The progress panel shows the stage and Cancel; Cancel stops the Job within a few seconds. The previous result (R-0001) stays on screen, greyed, with "Cancelled: Run again".

### A2-MEA-01 — Add column list

- **Area:** A2 Measures · **Priority:** P1 · **Screen:** 6.2 · **Spec:** AC-MEA-1, MEA-1 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis (Summary); TPL-R; tick R-0001. In Measures click + Add column; read the list.
    2. Pick Taxable Value. Click + Add column again; read the list.
    3. Pick Rows. Click + Add column again; read the list.

- **Expected:** Step 1: Rows first, then the 21 columns in template order (Invoice No, Invoice Date, Customer, … Narration, Place of Supply), each with its type; a search box is shown (more than 12 columns). Step 2: Taxable Value is no longer listed. Step 3: Rows is no longer listed. Each column, and Rows, can be added once.

### A2-MEA-03 — Operations offered by column type

- **Area:** A2 Measures · **Priority:** P1 · **Screen:** 6.2 · **Spec:** AC-MEA-3, MEA-3, D70 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis; TPL-R; + Add column Taxable Value, Invoice Date and Customer.
    2. Read each card's chips.
    3. Hover the Distinct chip on Customer and the Avg chip on Taxable Value.

- **Expected:** Taxable Value (Number): Sum, Count, Avg, Min, Max, and no Distinct. Invoice Date (Date): Count, Distinct, Min, Max. Customer (Text): Count, Distinct. Hovering shows "Count distinct" and "Average".

### A2-MEA-04 — A card with no operation ticked

- **Area:** A2 Measures · **Priority:** P1 · **Screen:** 6.2, 3.2 · **Spec:** AC-MEA-4, MEA-4, Feature Spec A2 8.9 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis; TPL-R; tick R-0001; group State; + Add column Taxable Value and tick nothing on it. Keep editing: add a filter, + Add column Rows, move a card.
    2. Press Run.
    3. Press Save….
    4. TPL-R > Default outputs: open "Latest month by State"; + Add column Invoice No and tick nothing. Press Preview, then Save. Then Discard.

- **Expected:** Editing goes on normally with the empty card. Run and Save… (step 2, 3) each show "Tick at least one operation for Taxable Value, or remove it" under that card and start nothing (no Job, no Save dialog). Preview and Save in step 4 show "Tick at least one operation for Invoice No, or remove it" and start nothing.

### A2-MEA-05 — Average at the column's decimal places

- **Area:** A2 Measures · **Priority:** P1 · **Screen:** 6.2, 7.4 · **Spec:** AC-MEA-5, MEA-5, T13 · **Type:** Functional
- **Preconditions:** TPL-A with R-0001 (F02) committed.
- **Steps:**

    1. New analysis; TPL-A; tick R-0001; no group; + Add column Taxable Value, tick Avg; Run.
    2. Export the result (UTF-8 with BOM); open it in Notepad.

- **Expected:** "Taxable Value · Average" shows 1,507.38 (the exact mean 7,536,875.00 ÷ 5,000 = 1,507.375, rounded half away from zero to 2 places). The export holds 1507.38.

### A2-MEA-06 — Result column order follows the cards

- **Area:** A2 Measures · **Priority:** P2 · **Screen:** 6.2 · **Spec:** AC-MEA-6, MEA-6 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis; TPL-R; tick R-0001; group State; + Add column Invoice No, tick Count; + Add column Taxable Value, tick Max, then Sum. Run.
    2. Move the Taxable Value card above Invoice No with ↑; Run.

- **Expected:** Step 1 columns: State, Invoice No · Count, Taxable Value · Sum, Taxable Value · Max (Sum before Max, whatever order they were ticked). Step 2: State, Taxable Value · Sum, Taxable Value · Max, Invoice No · Count.

### A2-MEA-07 — Default headers follow column renames

- **Area:** A2 Measures · **Priority:** P1 · **Screen:** 6.2, 6.3, 3.3 · **Spec:** AC-MEA-7, MEA-7, MEA-8 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis; TPL-R; tick R-0001; group State; + Add column Rows; + Add column Invoice No, tick Distinct; + Add column Taxable Value, tick Sum and Max. Run; read the headers.
    2. ✎ on "Taxable Value · Max": type "Top value", Enter. Save… as "A2 headers".
    3. TPL-R > Columns & rules: rename Taxable Value to Taxable Amt; Save.
    4. Open the saved analysis "A2 headers"; Run.
    5. Rename Taxable Amt back to Taxable Value; Save.

- **Expected:** Step 1 headers read exactly "State", "Rows · Count", "Invoice No · Count distinct", "Taxable Value · Sum", "Taxable Value · Max". Step 4: "Taxable Amt · Sum" (the default name follows the rename) and "Top value" (the custom name stays). After step 5 the default header reads "Taxable Value · Sum" again.

### A2-MEA-08 — Renaming a result column

- **Area:** A2 Measures · **Priority:** P1 · **Screen:** 6.2, 6.3 · **Spec:** AC-MEA-8, MEA-8, D59, D60 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed; saved analysis "A2 headers" (A2-MEA-07).
- **Steps:**

    1. New analysis; TPL-R; tick R-0001; group State; + Add column Invoice No, tick Count; + Add column Taxable Value, tick Sum; Run. Note the time in the result header.
    2. ✎ on "Invoice No · Count": type "Invoices", Enter. Hover the header.
    3. ✎ on "Taxable Value · Sum": type "Taxable value", press Esc.
    4. ✎ on "Taxable Value · Sum": type "invoices", Enter. Then Esc.
    5. ✎ on "Taxable Value · Sum": type "state", Enter (the group header is "State"). Then Esc.
    6. ✎ on "Invoices": clear the text, Enter.
    7. Open the saved analysis "A2 headers".

- **Expected:** Step 2: the header reads "Invoices"; the result is not greyed and its time is unchanged; hovering shows "Invoice No · Count". Step 3: the header stays "Taxable Value · Sum". Steps 4 and 5: refused with "Another column is already called …" naming the clashing name; the box stays open. Step 6: the header returns to "Invoice No · Count". Step 7: no header has ✎.

### A2-MEA-09 — Default output names in committed runs

- **Area:** A2 Measures · **Priority:** P1 · **Screen:** 3.2, 4.4, 5.1 · **Spec:** AC-MEA-9, MEA-9, DO-6, T50 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed (default output "Latest month by State").
- **Steps:**

    1. TPL-R > Default outputs: open "Latest month by State"; Preview; ✎ on "Taxable Value · Sum": type "Taxable", Enter. Save.
    2. New run on TPL-R: add F-A2-01 again; Load anyway at the duplicate warning; Mapping: Place of Supply, Leave as null; Validate; Outputs; Commit (R-0004).
    3. Open R-0004 > Outputs; export "Latest month by State"; read the CSV header.
    4. Open R-0001 > Outputs; export the same output; read the CSV header.
    5. TPL-R > Default outputs: untick Sum on the Taxable Value card, tick it again; Preview. Save.

- **Expected:** Step 1 marks the tab changed until Save. R-0004's Outputs tab and CSV use "Taxable" (with "Rows · Count"); R-0001's keep "Taxable Value · Sum". Step 5: the preview header reads "Taxable Value · Sum" again (re-ticking starts from the default name).

### A2-MEA-10 — The Rows card counts every row

- **Area:** A2 Measures · **Priority:** P1 · **Screen:** 6.2 · **Spec:** AC-MEA-10, MEA-10, D57 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed (R-0003 has 400,000 rows without Invoice No).
- **Steps:**

    1. New analysis; TPL-R; tick R-0003; no group; + Add column Rows; + Add column Invoice No, tick Count. Run.
    2. Group by State; Run; add up Rows · Count over the groups.

- **Expected:** Step 1: Rows · Count 2,500,000 (R-0003's rows loaded); Invoice No · Count 2,100,000, i.e. 400,000 lower. Step 2: Rows · Count per State (including "(Null)") adds up to the grand total, 2,500,000.

### A2-MEA-11 — A result with no measures

- **Area:** A2 Measures · **Priority:** P1 · **Screen:** 6.2 · **Spec:** AC-MEA-11, MEA-11, D76, T39 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis; TPL-R; tick R-0001; group GSTIN; no measure cards. Look at Show subtotals. Run.
    2. Export the result; open it.
    3. Remove the group level; press Run.

- **Expected:** Show subtotals is disabled. The result lists each GSTIN once, with "(Null)" once for blank GSTINs, and has **no subtotal or grand total rows** (Technical Spec A2 T39; not Feature Spec A2 MEA-11's grand total row). The export has the same rows and no grand total row. Step 3: "Add a group level or a measure" and nothing runs.

### A2-EXP-08a — 1,000,000 rows is one file; 1,000,001 rows is two parts

- **Area:** A2 Export in parts · **Priority:** P1 · **Screen:** 7.4, 7.9 · **Spec:** AC-EXP-8a, EXP-8, EXP-9, T38 · **Type:** Functional
- **Preconditions:** TPL-P with its 10M-row run R-0001 from P01 (P7): each of the 20 categories has 500,000 rows and Customer ID has 1,000,000 values. Empty folder C:\SankalanTest\Out\Exp8a.
- **Steps:**

    1. Analysis > New analysis > Rows; TPL-P; tick R-0001; filter Category is one of CAT-01, CAT-02; Run. Export rows to the folder; read the dialog.
    2. Summary; tick R-0001; no filter; group Customer ID; + Add column Invoice No, tick Count; Run. Export to the folder; read the dialog.
    3. Count the records in each file.

- **Expected:** Step 1: "1,000,000 rows match"; the dialog says "CSV file" with no parts line; one file with the dialog's name and no _part suffix, 1,000,001 records with the header. Step 2: 1,000,000 group rows + grand total = 1,000,001 data rows; the parts line is shown; two files, _part01of02 with 1,000,000 data rows and _part02of02 with 1 data row (the grand total, T38). Also automated at the real part size (tests\engine\test_export_big.py, slow).

### A2-EXP-08b — Every kind of export splits

- **Area:** A2 Export in parts · **Priority:** P1 · **Screen:** 3.1, 5.1, 6.2, 7.4, 7.9 · **Spec:** AC-EXP-8b, EXP-8, Feature Spec A2 4.2, T37 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. For the kinds that stay under 1,000,000 rows in the fixtures (left-out rows 63, issue list 1,510, default outputs), the automated test with lowered part sizes (tests\engine\test_export.py, part size passed as an argument, T37).
- **Steps:**

    1. Template TPL-R > Runs > R-0001 > Export data.
    2. New analysis; R-0003; filter Invoice No Not blank; group Invoice No; + Add column Rows; Run; Export.
    3. Rows; R-0001 to R-0003; no filters; Run; Export rows (or reuse A2-ROW-12b).
    4. Automated: left-out rows (R-0002), issue list (R-0001), one default output, all outputs of R-0001 and R-0002.

- **Expected:** Step 1: 2,500,000 rows in 3 parts. Step 2: 2,100,000 group rows + grand total in 3 parts. Step 3: 7,499,937 rows in 8 parts. Step 4: each export splits at the lowered part size; "All outputs" splits each output on its own.

### A2-EXP-09a — Every part opens fully in Excel

- **Area:** A2 Export in parts · **Priority:** P1 · **Screen:** 7.9 · **Spec:** AC-EXP-9a, EXP-9, EXP-3 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. Excel 365 installed. Empty folders C:\SankalanTest\Out\Bom and \NoBom.
- **Steps:**

    1. Rows; TPL-R; tick R-0003; filter Invoice No Not blank; Run ("2,100,000 rows match"). Export rows to Bom, UTF-8 with BOM.
    2. Export again to NoBom with UTF-8 (no BOM).
    3. Open each part in Excel 365; press Ctrl+End; read the last row number.
    4. Open each part in Notepad; read the first line and the encoding in the status bar.

- **Expected:** Each export is 3 parts, _part01of03 to _part03of03. Excel opens every part with no "file not loaded completely" message: parts 1 and 2 have 1,000,001 rows (header + 1,000,000), part 3 has 100,001. Every part starts with the same header row. Parts in Bom show "UTF-8 with BOM"; parts in NoBom show "UTF-8". Also automated with Excel by tools\perf\excel_open_check.ps1 (A2-6).

### A2-EXP-09b — Records are never split across parts

- **Area:** A2 Export in parts · **Priority:** P1 · **Screen:** 7.9 · **Spec:** AC-EXP-9b, EXP-9, Feature Spec A2 8.6, T33 · **Type:** Functional
- **Preconditions:** Test build (automated): tests\unit\test_export_split.py (records with quotes, doubled quotes, \r, \n and delimiters planted on and around part and block boundaries) and tests\engine\test_export.py (TPL-R small, lowered part sizes). Manual part: the Bom export of A2-EXP-09a.
- **Steps:**

    1. Run the automated tests.
    2. In Excel, read the last data row of each part and the first data row of the next; check Narration, which holds commas, double quotes and line breaks.

- **Expected:** Every part parses as valid CSV with the expected record count. No value with a line break, quote or delimiter is cut at a part boundary. The data rows of all parts, joined in order, are byte-identical to the same export written as one file (test build). Step 2: each boundary row is whole.

### A2-EXP-10 — Part names and the overwrite list

- **Area:** A2 Export in parts · **Priority:** P1 · **Screen:** 7.4 · **Spec:** AC-EXP-10, EXP-10, T36 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. Folder C:\SankalanTest\Out\Names holding two small CSV files named <name>_part02of03.csv and <name>_part04of04.csv, where <name> is R-0001's default export file name without .csv; SHA-256 of both noted (Get-FileHash).
- **Steps:**

    1. R-0001 > Export data; keep the file name; folder Names. Read the parts line.
    2. Export; read the overwrite confirmation; confirm.
    3. List the folder; Get-FileHash <name>_part04of04.csv.

- **Expected:** The parts line reads "Saved as 3 files of up to 1,000,000 rows each, so each opens fully in Excel: <name>_part01of03.csv to …_part03of03.csv". The confirmation lists exactly <name>_part02of03.csv. Afterwards the folder holds _part01of03 to _part03of03 and the untouched _part04of04 (same SHA-256). A 120-part export is named _part001of120 to _part120of120 (A2-PERF-12, and tests\unit\test_export_plan.py).

### A2-EXP-11 — Progress shows the part

- **Area:** A2 Export in parts · **Priority:** P2 · **Screen:** 7.5, 7.9 · **Spec:** AC-EXP-11, EXP-11, T53 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. R-0001 > Export data; watch the progress dialog to the end.
    2. Rows; R-0001 to R-0003; Run; Export rows; watch the progress.

- **Expected:** The progress shows the stage ("Reading rows", then "Writing files"), rows written of N (2,500,000; 7,499,937), "part K of M" (of 3; of 8), elapsed time and Cancel. The figures change at least every second.

### A2-EXP-12 — Grand total is last in a split result

- **Area:** A2 Export in parts · **Priority:** P1 · **Screen:** 6.2, 7.4 · **Spec:** AC-EXP-12, EXP-12, T38 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis; TPL-R; tick R-0003; filter Invoice No Not blank; group State, then Invoice No; + Add column Taxable Value, tick Sum; Show subtotals on; Run.
    2. Export the result.
    3. Open the parts in Excel; find "Grand total" in each; read the rows around each State subtotal and at each part boundary.
    4. Compare the first rows of part 1 with the first rows on screen.

- **Expected:** The result has 2,100,000 Invoice No rows plus one subtotal row per State and the grand total (about 2,100,000 rows): 3 parts. The grand total is the **last data row of the last part** (Technical Spec A2 T38, not the first row of part 1 as Feature Spec A2 EXP-12 says) and appears in no other part. Rows and subtotals across all parts, in order, follow the on-screen order: each subtotal sits next to its State's rows as on screen, and a State's rows may run across two parts.

### A2-EXP-13 — Not enough free space on the destination drive

- **Area:** A2 Export in parts · **Priority:** P1 · **Screen:** 7.4 · **Spec:** AC-EXP-13, EXP-13, T34 · **Type:** Functional
- **Preconditions:** The V: drive of the LOW-DISK setup (the data folder stays on C:), filled so its free space is below one R-0001 data export (about 1 GB free); %TEMP% on C: with plenty of space. TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. R-0001 > Export data; choose folder V:\Out. Wait for the size check.
    2. Read the message above the buttons.
    3. Change… to C:\SankalanTest\Out.

- **Expected:** Steps 1–2: Export is disabled and the message reads "Not enough free space on V:. This export needs about X GB, including working space; Y GB is free. Free up space or choose a folder on another drive.", with both sizes. Step 3: the check runs again and Export is enabled.

### A2-EXP-13b — Not enough free space for working files

- **Area:** A2 Export in parts · **Priority:** P2 · **Screen:** 7.4 · **Spec:** T34, EXP-13, Technical Spec A2 8.4 · **Type:** Functional
- **Preconditions:** The V: drive of the LOW-DISK setup (the data folder stays on C:), filled to about 1 GB free. Sankalan started from a Command Prompt after `set TEMP=V:\Temp` and `set TMP=V:\Temp`, so %TEMP%\Sankalan is on V:. Destination C:\SankalanTest\Out with plenty of space. TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. R-0001 > Export data to C:\SankalanTest\Out; wait for the size check; read the message.
    2. Delete the filler on V:; choose the folder again.

- **Expected:** Step 1: Export is disabled with "Not enough free space on V: for working files. This export needs about X GB there; Y GB is free. Free up space on V:." Step 2: Export is enabled. (Also automated with a patched free-space reading in tests\engine\test_export.py.)

### A2-EXP-14a — Cancel leaves nothing behind

- **Area:** A2 Export in parts · **Priority:** P1 · **Screen:** 7.5 · **Spec:** AC-EXP-14a, EXP-14, T33, T35 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. Folder C:\SankalanTest\Out\Cancel holding a small CSV named <name>_part01of03.csv (<name> as A2-EXP-10); its SHA-256 noted.
- **Steps:**

    1. R-0001 > Export data to the folder; confirm replacing <name>_part01of03.csv.
    2. When the progress shows "part 2 of 3", press Cancel.
    3. List the folder (with hidden files) and %TEMP%\Sankalan.
    4. Get-FileHash <name>_part01of03.csv.

- **Expected:** The export stops with the banner "Export cancelled. No files were written; files that would have been replaced are unchanged." The folder holds only the original <name>_part01of03.csv: no new part and no .partial file (parts are written as <name>.partial until the finish step, T35). %TEMP%\Sankalan holds no chunk file (chunks are extracted there, T33); only duckdb_temp_<pid>_… files may remain (T54). The SHA-256 is unchanged.

### A2-EXP-14b — A failed export cleans up

- **Area:** A2 Export in parts · **Priority:** P1 · **Screen:** 7.5 · **Spec:** AC-EXP-14b, EXP-14, Feature Spec A2 8.5, T35 · **Type:** Functional
- **Preconditions:** The V: drive of the LOW-DISK setup (the data folder stays on C:), with free space a little above what R-0001's data export needs (the size check passes); V:\Out holding a small <name>_part01of03.csv with its SHA-256 noted. For the count mismatch, a test build (automated test hook in tests\engine\test_export.py).
- **Steps:**

    1. R-0001 > Export data to V:\Out; confirm the replacement.
    2. While the progress shows "part 2 of 3", fill V: (`fsutil file createnew V:\filler2.bin <free bytes>`).
    3. Read the message; list V:\Out and %TEMP%\Sankalan; Get-FileHash the old file. Delete filler2.bin.
    4. Automated: force a row-count mismatch.

- **Expected:** Step 3: the export fails with a plain message saying the drive became full and what to do (UI-6); the clean-up is as A2-EXP-14a (no part, .partial or chunk file; the replaced file keeps its SHA-256). Step 4: "Export check failed: wrote X of N rows", with the same clean-up.

### A2-EXP-14c — Done banner for a split export

- **Area:** A2 Export in parts · **Priority:** P1 · **Screen:** 7.5, 5.1 · **Spec:** AC-EXP-14c, EXP-14, EXP-7 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. Empty folder C:\SankalanTest\Out\Done.
- **Steps:**

    1. R-0001 > Export data to the folder; let it finish.
    2. Click Open folder on the banner.

- **Expected:** The banner reads "Exported 2,500,000 rows to 3 files" with Open folder. Open folder opens Explorer at C:\SankalanTest\Out\Done.

### A2-SHT-01 — Where Choose sheets… is offered

- **Area:** A2 Choose sheets · **Priority:** P1 · **Screen:** 4.1, 4.1a · **Spec:** AC-SHT-1, SHT-2, T46, D65 · **Type:** Functional
- **Preconditions:** TPL-S created (Read me). TPL-A from P3. F07 Sales_Locked.xlsx open in Excel.
- **Steps:**

    1. New run on TPL-S: add F-A2-08 West (matches the rule), F-A2-06 Central .xlsx, F-A2-09 Central .xlsb and F-A2-10 Central .xls. Read the action column.
    2. Leave and discard the run.
    3. New run on TPL-A: add F02 Sales_Oct.xlsx (matches "Sales"), F20 Sales_Macro.xlsm, F12 Sales_ManyIssues.csv, F07 (open in Excel), F06 Sales_Protected.xlsx (password) and F09 Sales_NoHeader.xlsx (Header not found). Read the action column.
    4. Leave and discard the run.

- **Expected:** Choose sheets… appears next to ✕ on the first row of every .xlsx, .xlsm, .xlsb and .xls file that can be read: West, the three Central files, F02 and F20, including West and F02 whose sheets match the rule. It does not appear for F12 (CSV), F07 (open in Excel), F06 (password-protected) or F09 (Header not found). (.xlsb and .xls follow Technical Spec A2 T46; Feature Spec A2 SHT-2 names only .xlsx and .xlsm.)

### A2-SHT-02 — The Choose sheets dialog

- **Area:** A2 Choose sheets · **Priority:** P1 · **Screen:** 4.1c · **Spec:** AC-SHT-2, SHT-4, SHT-5 · **Type:** Functional
- **Preconditions:** TPL-S created.
- **Steps:**

    1. New run on TPL-S: add F-A2-06 Central .xlsx.
    2. Click Choose sheets… on Central; read the dialog.
    3. Tick Sales Nov and Returns Nov; read the button and the total. Cancel.

- **Expected:** The title reads "Choose sheets for Sales_Nov-2026_Central.xlsx" with the file size. Sheets in workbook order: Sales Nov (about 300 rows), Returns Nov (about 50 rows), Notes (disabled, "Hidden, skipped"). The note reads "The header row is found in each sheet. Headers that don't match the template's columns are handled in Mapping." Nothing is ticked and the Read button is disabled. After ticking two: "Read 2 sheets" and the total "2 sheets · about 350 rows".

### A2-SHT-03 — Sheet not found, then choose the sheets

- **Area:** A2 Choose sheets · **Priority:** P1 · **Screen:** 4.1b, 4.1c · **Spec:** AC-SHT-3, SHT-6, SHT-7, T47, IN-15 · **Type:** Functional
- **Preconditions:** TPL-S created.
- **Steps:**

    1. New run on TPL-S: add F-A2-06 Central .xlsx only. Read the grid, the error banner and the footer; try Next.
    2. Choose sheets…; tick Sales Nov; Cancel.
    3. Choose sheets…; tick Sales Nov and Returns Nov; Read 2 sheets.

- **Expected:** Step 1: Central is **one** error row for the file (T47), Sheet not found, naming "Sheets found: Sales Nov, Returns Nov"; the actions are Choose sheets… and Exclude file; the footer reads "Choose sheets for 1 file, or exclude it, to continue"; Next is disabled. Step 2: the file stays in error as before. Step 3: the file's row is replaced by two Ready rows, Sales Nov (300 rows) and Returns Nov (50 rows), each with its header row found; Next is enabled.

### A2-SHT-04 — A file with some of the named sheets

- **Area:** A2 Choose sheets · **Priority:** P1 · **Screen:** 4.1b, 4.1c · **Spec:** AC-SHT-4, SHT-6, SHT-5, T47 · **Type:** Functional
- **Preconditions:** TPL-S created.
- **Steps:**

    1. New run on TPL-S: add F-A2-07 East (sheet Sales only). Read the grid.
    2. Choose sheets…; read the ticks. Cancel; Exclude file; leave and discard the run.

- **Expected:** East is one error row, Sheet not found ("Sheets found: Sales"), although Sales matches, because Sales Returns is missing. The dialog opens with Sales ticked.

### A2-SHT-05 — A chosen sheet with no header row

- **Area:** A2 Choose sheets · **Priority:** P1 · **Screen:** 4.1, 4.1a, 4.1c · **Spec:** AC-SHT-5, SHT-8, D68 · **Type:** Functional
- **Preconditions:** TPL-S created.
- **Steps:**

    1. New run on TPL-S: add F-A2-08 West. It reads Sales and Sales Returns by the rule.
    2. Choose sheets…; also tick Cover; Read 3 sheets. Read the file's actions.
    3. Remove West with ✕; add it again; read its rows and actions; open Choose sheets… and read the ticks. Cancel.

- **Expected:** Step 2: West is in Header not found (Cover has no header row); the only action is Exclude file and Choose sheets… is gone. Step 3: West is back to two Ready rows by the rule (Sales 100 rows, Sales Returns 20 rows) and Choose sheets… is offered again, with Sales and Sales Returns ticked (starting from the rule).

### A2-SHT-06 — The choice through Re-check

- **Area:** A2 Choose sheets · **Priority:** P1 · **Screen:** 4.1b, 4.1c · **Spec:** AC-SHT-6, SHT-9 · **Type:** Functional
- **Preconditions:** TPL-S created. A working copy of F-A2-06 at C:\SankalanTest\Work\Sales_Nov-2026_Central.xlsx.
- **Steps:**

    1. New run on TPL-S: add the working copy; Choose sheets…; tick Sales Nov and Returns Nov; Read 2 sheets.
    2. Re-check.
    3. Replace the working copy with F-A2-11 (Sales Nov renamed Sales November), keeping the name Sales_Nov-2026_Central.xlsx. Re-check.
    4. Choose sheets…; read the ticks. Cancel; leave and discard the run.

- **Expected:** Step 2: the two Ready rows stay (the choice is kept). Step 3: Central returns to Sheet not found, naming "Sheets found: Sales November, Returns Nov". Step 4: the dialog opens with Returns Nov ticked and Sales November unticked.

### A2-SHT-07 — The choice is for this run only

- **Area:** A2 Choose sheets · **Priority:** P1 · **Screen:** 4.1, 4.1b, 3.4 · **Spec:** AC-SHT-7, SHT-3 · **Type:** Functional
- **Preconditions:** TPL-S created; no TPL-S runs.
- **Steps:**

    1. New run on TPL-S: add F-A2-06 Central and F-A2-08 West. Central: Choose sheets…, tick Sales Nov and Returns Nov, Read 2 sheets. Go on to Commit and commit (TPL-S R-0001, 470 rows).
    2. TPL-S > Settings: read Sheets to read.
    3. New run on TPL-S: add F-A2-06 Central again. Then leave and discard the run.

- **Expected:** R-0001 commits with 470 rows (Sales Nov 300, Returns Nov 50, Sales 100, Sales Returns 20). Sheets to read is still by name, "Sales" and "Sales Returns". In the new run Central is in Sheet not found again (the template's rule applies; the choice was not kept).

### A2-SHT-08 — Chosen sheets in the committed run

- **Area:** A2 Choose sheets · **Priority:** P2 · **Screen:** 5.1, 6.4, 4.1 · **Spec:** AC-SHT-8, SHT-10, D66 · **Type:** Functional
- **Preconditions:** TPL-S R-0001 (A2-SHT-07).
- **Steps:**

    1. Rows view: TPL-S; tick R-0001; Show them on screen; Run. Read Source File and Source Sheet.
    2. Open R-0001 > Source files.
    3. Look for any "Chosen" marker in the Files grid and footer (A2-SHT-07 step 1), and in Source files.

- **Expected:** Central's rows have Source Sheet "Sales Nov" or "Returns Nov"; West's have "Sales" or "Sales Returns". No "Chosen" label appears in the Files grid, the footer or Run > Source files. run_file.sheets_chosen is true for Central only (not shown on screen; checked by the automated test).

### A2-SHT-09 — Mapping for chosen sheets

- **Area:** A2 Choose sheets · **Priority:** P2 · **Screen:** 4.1, 4.2 · **Spec:** AC-SHT-9, SHT-10, TPL-6, MAP-4 · **Type:** Functional
- **Preconditions:** TPL-S created. A copy of F-A2-06 with the header Taxable Value in sheet Returns Nov changed to Taxable Amt in Excel, saved as C:\SankalanTest\Work\Central_NewHeader.xlsx.
- **Steps:**

    1. New run on TPL-S: add F-A2-06 Central; choose Sales Nov and Returns Nov; Next.
    2. Leave and discard. New run: add Central_NewHeader.xlsx; choose Sales Nov and Returns Nov; Next.
    3. Leave and discard the run.

- **Expected:** Step 1: Mapping is skipped (every header of the chosen sheets matches) and Next goes to Validate. Step 2: Mapping opens with one column per file and sheet; only the Returns Nov column's Taxable Amt cell is highlighted as undecided.

### A2-SHT-10 — Choose sheets on .xlsb and .xls files

- **Area:** A2 Choose sheets · **Priority:** P1 · **Screen:** 4.1b, 4.1c · **Spec:** T46, SHT-2, SHT-4, SHT-6, SHT-7, T47 · **Type:** Functional
- **Preconditions:** TPL-S created.
- **Steps:**

    1. New run on TPL-S: add F-A2-09 Central .xlsb. Read its row.
    2. Choose sheets…; read the dialog; tick Sales Nov and Returns Nov; Read 2 sheets.
    3. Repeat steps 1–2 with F-A2-10 Central .xls in a new run. Leave and discard.

- **Expected:** For each file: one Sheet not found row naming "Sheets found: Sales Nov, Returns Nov", with Choose sheets… and Exclude file. The dialog lists Sales Nov (about 300 rows), Returns Nov (about 50 rows) and Notes (disabled, "Hidden, skipped"), nothing ticked. After Read 2 sheets: two Ready rows of 300 and 50 rows, as for the .xlsx file.

### A2-TXT-01 — Text in Number and Date cells shown and exported as typed

- **Area:** A2 Text in Number/Date · **Priority:** P1 · **Screen:** 6.4, 7.9 · **Spec:** AC-TXT-1, TXT-2, TXT-3, TXT-4 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. Rows; TPL-R; tick R-0001; filter Taxable Value Is not a number; Run. Read Taxable Value and its alignment.
    2. Export rows; open the file in Notepad.
    3. Tick R-0002 only; filter Invoice Date Is not a date; Run. Read Invoice Date and its alignment.
    4. Export rows; open the file in Notepad.

- **Expected:** Step 1: Taxable Value shows "NA", "Nil" and "12,000/-" exactly as typed, right-aligned like the numbers. Step 3: Invoice Date shows "NA" and "31-02-2026" as typed, left-aligned like the dates. In the exports the same text appears as typed in the same column, quoted where CSV needs it ("12,000/-" is quoted because of the comma); numbers are at 2 decimals with no grouping and dates are DD-MM-YYYY.

### A2-TXT-02 — Sum, Average, Min and Max use values only

- **Area:** A2 Text in Number/Date · **Priority:** P1 · **Screen:** 6.2 · **Spec:** AC-TXT-2, TXT-9, T13 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. The fixture manifest tpl_r_full.json (written by the generator with F-A2-01 to F-A2-03) at hand.
- **Steps:**

    1. New analysis; TPL-R; tick R-0001; no group; + Add column Taxable Value, tick Sum, Avg, Min, Max; Run.
    2. Tick R-0002 only; replace the card with Invoice Date, tick Min and Max; Run.

- **Expected:** Step 1: Sum, Min and Max equal the manifest's R-0001 taxable_sum, taxable_min and taxable_max (numeric cells only); Average equals taxable_sum ÷ taxable_count (numeric cells), rounded half away from zero to 2 places. Step 2: Min and Max of Invoice Date are real dates (DD-MM-YYYY) in November 2026; neither is "NA" or "31-02-2026".

### A2-TXT-03 — Count includes text; Distinct on a Date column counts dates only

- **Area:** A2 Text in Number/Date · **Priority:** P1 · **Screen:** 6.2 · **Spec:** AC-TXT-3, TXT-8, TXT-9, D70 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed; manifest tpl_r_full.json.
- **Steps:**

    1. New analysis; TPL-R; tick R-0001; + Add column Taxable Value, tick Count; Run.
    2. Tick R-0002 only; replace the card with Invoice Date, tick Count and Distinct; Run.
    3. Add filter Invoice Date Not blank; + Add column Rows; Run.

- **Expected:** Step 1: Count of Taxable Value = the manifest's R-0001 taxable_count (numeric cells) + 1,510. Step 2: Count of Invoice Date includes the 305 text cells (it equals Rows · Count in step 3); Distinct of Invoice Date equals the number of different dates (manifest date_distinct for R-0002), text not counted.

### A2-TXT-04 — Filters on Number and Date columns with text

- **Area:** A2 Text in Number/Date · **Priority:** P1 · **Screen:** 6.2, 6.5, 6.6 · **Spec:** AC-TXT-4, TXT-5, TXT-6, TXT-7, TXT-8 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis; TPL-R; tick R-0001; + Add column Rows. Filter Taxable Value Is not a number; Run.
    2. Change the filter to Taxable Value Between 0 and 999,999,999; Run. Then Equals 1,000.00; Run. In Rows mode, run both and look for text in Taxable Value.
    3. Filter Taxable Value Not blank; Run. Then Blank; Run; in Rows mode check Taxable Value on the matching rows.
    4. Tick R-0002 only; filter Invoice Date Is not a date; Run.

- **Expected:** Step 1: Rows · Count 1,510. Step 2: no matching row holds text in Taxable Value (Equals and Between never return a text row). Step 3: Not blank includes the 1,510 text rows (its count = Count of Taxable Value from A2-TXT-03); Blank returns only empty cells. Step 4: Rows · Count 305.

### A2-TXT-05 — "(Not a number)" and "(Not a date)" groups

- **Area:** A2 Text in Number/Date · **Priority:** P1 · **Screen:** 6.2 · **Spec:** AC-TXT-5, TXT-10, T42 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed.
- **Steps:**

    1. New analysis; TPL-R; tick R-0001; group Taxable Value; + Add column Rows; Run. Find "(Not a number)" and "(Null)" (export the result if they are past the first 100,000 rows).
    2. Tick R-0002 only; group Invoice Date (Month); Run.
    3. Change the grain to Year; Run.

- **Expected:** Step 1: "(Not a number)" has Rows · Count 1,510, as its own group separate from "(Null)". Steps 2 and 3: "(Not a date)" has Rows · Count 305, separate from "(Null)".

### A2-TXT-06 — Sorting puts text groups after the values

- **Area:** A2 Text in Number/Date · **Priority:** P2 · **Screen:** 6.2 · **Spec:** AC-TXT-6, TXT-11, P8 (confirmed), T42 · **Type:** Functional
- **Preconditions:** A2-TXT-05 results.
- **Steps:**

    1. R-0002 grouped by Invoice Date (Month): sort by Invoice Date ascending, then descending; read the order.
    2. R-0001 grouped by Taxable Value: sort by Taxable Value ascending, then descending; read the last groups (export if needed).

- **Expected:** In both directions the values come first in the chosen order, then "(Not a date)" or "(Not a number)", then "(Null)" last.

### A2-TXT-07 — Rules on text cells (run with checks)

- **Area:** A2 Text in Number/Date · **Priority:** P1 · **Screen:** 4.3 · **Spec:** AC-TXT-7, TXT-13, VR-5 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. A new run to be discarded. Automated: tests\engine\test_text_values.py and the validation tests check every rule on TPL-R small.
- **Steps:**

    1. New run on TPL-R: add F-A2-01 and F-A2-02 again (Load anyway at the duplicate warnings; Place of Supply: Leave as null for F-A2-01's files). Validate; read the counts per rule.
    2. Edit rules for this run only (Warning): Taxable Value Number range minimum 0, Allowed values 1000, Not blank and Unique within the run; Invoice Date Date range 01-10-2026 to 30-11-2026. Read the counts.
    3. In the issue grid, pick 3 rows listed under Taxable Value Is a number (two of them "NA") and look at the other rules' issues for those rows.
    4. Leave the run and discard it.

- **Expected:** Step 1: Taxable Value Is a number 1,510 and Invoice Date Is a date 305: exactly one issue per text cell. Step 2: Date range has no issue on a text cell (every real date is in October or November 2026); Number range, Allowed values and Not blank give no issue on the text rows (Not blank passes on text), so the 3 rows have no issue from them; two "NA" rows are both flagged by Unique within the run as duplicates. No Run ID is used.

### A2-TXT-08 — Totals check with text values

- **Area:** A2 Text in Number/Date · **Priority:** P1 · **Screen:** 4.5, 5.1 · **Spec:** AC-TXT-8, TXT-14, T20 · **Type:** Functional
- **Preconditions:** TPL-R R-0001 committed (P8 setup; its Commit step seen).
- **Steps:**

    1. Read the totals check at R-0001's Commit step (or R-0001 > Summary).

- **Expected:** The totals check passes for Taxable Value and Invoice Value: Input = Loaded. The 1,510 text cells count as 0 in Input and are null in Loaded.

### A2-TXT-09 — Latest month ignores text dates

- **Area:** A2 Text in Number/Date · **Priority:** P1 · **Screen:** 5.1, 6.2 · **Spec:** AC-TXT-9, TXT-12, DO-3 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed (default output "Latest month by State").
- **Steps:**

    1. Open R-0002 > Outputs > "Latest month by State"; read the period and the grand total Rows · Count.
    2. New analysis; TPL-R; tick R-0002; filter Invoice Date Month is November 2026; + Add column Rows; Run.

- **Expected:** The output uses November 2026, the latest real date in R-0002 ("NA" and "31-02-2026" are ignored). Its grand total Rows · Count equals step 2's Rows · Count: the 305 text rows (and blank dates) are outside the period.

### A2-TXT-10 — Type detection notes the text share

- **Area:** A2 Text in Number/Date · **Priority:** P2 · **Screen:** 2.3 · **Spec:** AC-TXT-10, Feature Spec A2 6.2, Technical Spec A2 5.9 · **Type:** Functional
- **Preconditions:** A CSV sample C:\SankalanTest\Work\Text2pct.csv made in Notepad: header Case,Amount; 100 data rows; Amount holds a number on 98 rows and "NA" on 2; no blank Amount.
- **Steps:**

    1. New template from Text2pct.csv; go to Columns; read Amount's type and note.
    2. Cancel the wizard.

- **Expected:** Amount is detected as Number with the note "98% numbers · 2% aren't numbers and are kept as text" (amber). (Feature Spec A2 6.2's example reads "Number · 98% · 2% aren't numbers and are kept as text"; the wording follows Technical Spec A2 5.9.)

### A2-NCK-01 — Check data before loading in the Rules step

- **Area:** A2 Without checks · **Priority:** P1 · **Screen:** 2.4, 2.4b · **Spec:** AC-NCK-1, NCK-2, NCK-3, D72 · **Type:** Functional
- **Preconditions:** Client Rao & Co. New template wizard with sample F-A2-04 (creates TPL-N).
- **Steps:**

    1. Name "Purchase Register N"; set the columns as TPL-R (Read me); go to step 4 Rules. Read the bar at the top.
    2. Add a rule: Customer Not blank (Warning).
    3. Choose No. Read the step.
    4. Choose Yes. Read the rules.
    5. Choose No again; finish the wizard with the default output "Taxable by State" (Read me) and save.

- **Expected:** Step 1: a Yes / No bar "Check data before loading", Yes selected, with "Applies to every run of this template. Can be changed later in Settings."; the wizard has 6 steps. Step 3: the rule editor is replaced by an explanation of what No means and a table of the sample's values that aren't numbers (per Number column) and aren't dates (per Date column), e.g. "Taxable Value · N of 100,000" and "Invoice Date · N of 100,000"; columns with none aren't listed; footer "No rules will be set for this template". Step 4: the Customer Not blank rule is back. Step 5: TPL-N is saved with Check data before loading = No.

### A2-NCK-02 — A run without checks loads every row

- **Area:** A2 Without checks · **Priority:** P1 · **Screen:** 4.1, 4.3b, 4.5b · **Spec:** AC-NCK-2, NCK-4, NCK-6, T44, T45 · **Type:** Functional
- **Preconditions:** TPL-N created (A2-NCK-01), no runs.
- **Steps:**

    1. New run on TPL-N; read the step bar. Add F-A2-04 and F-A2-05; Next.
    2. When Load finishes, read the banner and the stat cards.
    3. Next to Outputs; Next to Commit; Commit (TPL-N R-0001).
    4. Open the run folder in Explorer (<data folder>\…\R-0001).

- **Expected:** The step bar reads Files · Mapping · Load · Outputs · Commit; with every header matching, Next on Files goes straight to Load. Rows read 1,000,010, with "Blank rows skipped: 10"; rows to load and Rows loaded 1,000,000 = Rows read − blank rows (Technical Spec A2 T45; Feature Spec A2 says Rows loaded = rows read), including the 2,000 repeated rows. The run folder has data.parquet and no issues.parquet or left_out.parquet.

### A2-NCK-03 — Cancel and Back during Load

- **Area:** A2 Without checks · **Priority:** P1 · **Screen:** 4.3b · **Spec:** AC-NCK-3, NCK-7, T44 · **Type:** Functional
- **Preconditions:** TPL-N created. A copy of F-A2-04 with the header Taxable Value changed to Taxable Amt in Notepad, saved as C:\SankalanTest\Work\TPLN_NewHeader.csv.
- **Steps:**

    1. New run on TPL-N: add F-A2-04 and F-A2-05; Next (Mapping is skipped). While Load shows its progress (stage, files done of total, rows read), press Cancel. Look in <data folder>\_staging.
    2. Next again; when Load finishes, press Back.
    3. Remove both files; add TPLN_NewHeader.csv; Next; in Mapping map Taxable Amt to Taxable Value (This run only); Next. During Load press Cancel. Look in _staging.
    4. Leave and discard the run.

- **Expected:** Load shows the stage, files done of total, rows read and Cancel. Step 1: the wizard returns to Files and _staging is empty. Step 2: Back returns to Files, _staging empty. Step 3: Cancel returns to Mapping and _staging is empty.

### A2-NCK-04 — Values that aren't numbers or dates at Load

- **Area:** A2 Without checks · **Priority:** P1 · **Screen:** 4.3b · **Spec:** AC-NCK-4, NCK-8, D75 · **Type:** Functional
- **Preconditions:** TPL-N R-0001's Load step (A2-NCK-02, before Commit) or a new TPL-N run with F-A2-04 and F-A2-05 at Load (discard afterwards).
- **Steps:**

    1. Read the table of columns with values that aren't numbers or dates.
    2. Select Taxable Value; read the values list.
    3. Select Invoice Date; read the values list.

- **Expected:** Taxable Value 6,802; Invoice Date 120; no other column listed. Taxable Value lists, most frequent first: "NA" 4,000; "Nil" 2,000; "-" 790; "12,000/-" 10; " NA " 2 (with its spaces, as typed): at most 1,000 values, each with its count and where it first appears (file, sheet blank for CSV, row), matching the fixture manifest. Invoice Date: "NA" 100; "31-02-2026" 20.

### A2-NCK-05 — What still applies without checks

- **Area:** A2 Without checks · **Priority:** P1 · **Screen:** 4.1, 4.1a, 4.2 · **Spec:** AC-NCK-5, NCK-5, IN-15, MAP-13, RUN-7 · **Type:** Functional
- **Preconditions:** TPL-N R-0001 committed. TPLN_NewHeader.csv (A2-NCK-03).
- **Steps:**

    1. New run on TPL-N: add F06 Sales_Protected.xlsx; try Next.
    2. Exclude F06. Add TPLN_NewHeader.csv; Next; try Next on Mapping without deciding Taxable Amt.
    3. Back to Files; remove it; add F-A2-04.
    4. Leave and discard the run.

- **Expected:** Step 1: F06 is a password-protected file error and Next is disabled. Step 2: Mapping opens with Taxable Amt undecided and Next stays blocked until it is decided. Step 3: F-A2-04 shows the duplicate-file warning naming TPL-N R-0001.

### A2-NCK-06 — Commit step without checks

- **Area:** A2 Without checks · **Priority:** P1 · **Screen:** 4.5b · **Spec:** AC-NCK-6, NCK-9, NCK-10, T45 · **Type:** Functional
- **Preconditions:** TPL-N R-0001 at its Commit step (A2-NCK-02 step 3).
- **Steps:**

    1. Read the summary and the totals check.
    2. Leave the comment empty; read the Commit button.

- **Expected:** The summary shows "Data checks: Not checked · template setting", "Rows left out: None", "Blank rows skipped: 10" (T45), "Taxable Value: 6,802 values aren't numbers and are left out of sums" and "Invoice Date: 120 values aren't dates and are left out of date filters and groups". The totals check passes (Input = Loaded) with the note "Values that aren't numbers count as 0 on both sides". Commit is enabled with no comment; the counts never block it.

### A2-NCK-07 — Changing the setting in Template > Settings

- **Area:** A2 Without checks · **Priority:** P1 · **Screen:** 3.4, 3.3, 3.1, 4.3b, 5.1 · **Spec:** AC-NCK-7, NCK-11, NCK-13, TPL-7, D73 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0004 committed. Note TPL-R's template version.
- **Steps:**

    1. TPL-R > Settings: under Template name read Check data before loading; choose No; read the note; Save. Read the version.
    2. Columns & rules: read the rules; try to edit or add one; look for Test rules on latest run.
    3. New run on TPL-R: add F-A2-01 (Load anyway; Place of Supply: Leave as null); read the step bar; go on to Commit and commit (R-0005).
    4. Open R-0001 and R-0005.
    5. Settings: choose Yes; Save. Open Columns & rules.

- **Expected:** Step 1: Yes / No with "A change applies from the next run. Runs already loaded don't change."; the template version goes up by one. Step 2: the rules are greyed with "Not in use: this template loads without checks"; they can't be edited, added or tested; Test rules on latest run is not offered. Step 3: the run has a Load step (Files · Mapping · Load · Outputs · Commit). Step 4: R-0001 keeps its Issues tab; R-0005 has none. Step 5: the rules are back in use and editable (Character pattern and the Warning type rules as before); the version goes up by one again.

### A2-NCK-08 — Runs without checks in the Runs list and Run detail

- **Area:** A2 Without checks · **Priority:** P1 · **Screen:** 3.1, 5.1 · **Spec:** AC-NCK-8, NCK-12, D74 · **Type:** Functional
- **Preconditions:** TPL-N R-0001 committed.
- **Steps:**

    1. TPL-N > Runs: read the Issues column; open the row's actions.
    2. Open R-0001: read the tabs and the Summary; look for Export issue list and Export left-out rows.

- **Expected:** Issues reads "Not checked". Run detail has no Issues tab; the Summary says "Data checks: Not checked" (with "Blank rows skipped: 10"). Export issue list and Export left-out rows are not offered, neither in the Runs list nor in Run detail.

### A2-NCK-09 — Duplicate keeps the setting

- **Area:** A2 Without checks · **Priority:** P2 · **Screen:** 1.2, 3.4 · **Spec:** AC-NCK-9, NCK-1, T43 · **Type:** Functional
- **Preconditions:** TPL-N created.
- **Steps:**

    1. Client Rao & Co: … > Duplicate on Purchase Register N.
    2. Open the copy > Settings.

- **Expected:** Check data before loading = No in the copy.

### A2-NCK-10 — Runs with and without checks analysed together

- **Area:** A2 Without checks · **Priority:** P1 · **Screen:** 6.2 · **Spec:** AC-NCK-10, NCK-14 · **Type:** Functional
- **Preconditions:** TPL-R R-0004 (with checks) and R-0005 (without checks) committed.
- **Steps:**

    1. New analysis; TPL-R; tick R-0004 and R-0005; group State; + Add column Rows; + Add column Taxable Value, tick Sum and Count; Run.
    2. Run the same with R-0004 only, then with R-0005 only.

- **Expected:** Each figure of step 1 (per State and grand total) equals the sum of the two single-run results. Nothing in the result shows how a run was loaded.

### A2-BUG-1a — A spilled temporary table survives the next Job's clean-up

- **Area:** A2 Bug fix · **Priority:** P1 · **Screen:** — · **Spec:** AC-BUG-1a, BUG-1, T54, SEC-4 · **Type:** Functional
- **Preconditions:** Test build (automated): tests\engine\test_bug1.py, with a small DuckDB memory limit.
- **Steps:**

    1. In one Job, create a temporary table large enough to spill to %TEMP%\Sankalan.
    2. Let the Job end (the temp folder is cleaned).
    3. In the next Job, read the whole table.
    4. Run the same test on the pre-A2 code (commit 25f4d98).

- **Expected:** Step 3 reads every row back. On the old code the test fails (the spill files were deleted while still in use).

### A2-BUG-1b — Temp folder after Jobs, after closing the data folder and after a restart

- **Area:** A2 Bug fix · **Priority:** P1 · **Screen:** 6.4, ND-1 · **Spec:** AC-BUG-1b, BUG-1, T54, SEC-4 · **Type:** Functional
- **Preconditions:** TPL-R with R-0001 to R-0003 committed. Task Manager > Details shows Sankalan.exe's PID.
- **Steps:**

    1. Rows; TPL-R; tick R-0001 to R-0003; Run. Then a Summary on the same runs grouped by Invoice No with Rows; Run.
    2. After each Job ends, list %TEMP%\Sankalan.
    3. Close Sankalan; list %TEMP%\Sankalan.
    4. Start Sankalan; list %TEMP%\Sankalan.
    5. Automated: the data-folder move (Change…) closes the data folder; the SEC-4 no-leftovers test.

- **Expected:** Step 2: the folder holds nothing but files named duckdb_temp_<PID>_…, where <PID> is the running Sankalan.exe's (it may be empty). Steps 3 and 4: the folder is empty. Step 5: after the data folder is closed the folder is empty.

### A2-BUG-1c — A full-size load commits all three runs

- **Area:** A2 Bug fix · **Priority:** P1 · **Screen:** 4.1–4.5 · **Spec:** AC-BUG-1c, BUG-1, T54 · **Type:** Functional
- **Preconditions:** Fresh data folder; full-size F-A2-01 to F-A2-03. Automated: tests\engine\test_stored_order.py (slow).
- **Steps:**

    1. Create TPL-R and commit R-0001, R-0002 and R-0003 as in the Read me's run sequence.

- **Expected:** All three runs commit: rows loaded 2,500,000, 2,499,937 (63 left out) and 2,500,000; rows stored 7,499,937. No Job fails on a missing temp file.

### A2-CAT-01 — A data folder from a test build is refused

- **Area:** A2 Catalogue · **Priority:** P2 · **Screen:** ND-6 · **Spec:** T40, D77, Technical Spec A2 12.2 · **Type:** Deployment
- **Preconditions:** A data folder C:\SankalanTest\OldData created by a pre-A2 build (catalogue schema version 1, e.g. run from source at commit 25f4d98), with one client. Note the folder's file list with sizes and dates (and Get-FileHash catalogue.duckdb). settings.json points to it.
- **Steps:**

    1. Start Sankalan.
    2. Read the message; close it without choosing a folder.
    3. Compare C:\SankalanTest\OldData with the notes.
    4. Start again; in the data-folder chooser create a new data folder (or pick an empty one).

- **Expected:** Step 1: no backup and no upgrade; the message reads "This data folder was made by a test build of Sankalan and can't be opened by this version. Choose another folder, or create a new one.", with the data-folder chooser. Step 3: the folder is unchanged (same files, sizes, dates and hash). Step 4: the app opens on Clients with the new, empty data folder at schema version 2.

### A2-PERF-07 — Rows view Run on one 10M-row run ≤ 5 s

- **Area:** A2 Performance · **Priority:** P1 · **Screen:** 6.4 · **Spec:** PERF-7, T4, T48 · **Type:** Performance
- **Preconditions:** Performance laptop (16 GB RAM, 4 cores, SSD, Windows 11), nothing else running. A template in TPL-R's shape with 12 committed runs of 10,000,000 rows (tools\perf\build_a2_data.py; about 3.2 GB of Parquet), with TPL-R's planted text values. Automated on the development PC: tests\perf\test_a2_perf.py (DuckDB 4 threads, 8 GB).
- **Steps:**

    1. Rows; tick one run; 2 filters (e.g. State is one of Maharashtra, Gujarat; Taxable Value Not blank).
    2. Run once as a warm-up. Then time Run → match count and grid shown, 3 times.

- **Expected:** Median ≤ 5 s (count and first 100,000 rows). Record median, min and max. Misses are reported, not blocking (T4).

### A2-PERF-08 — Rows view Run across 12 runs ≤ 30 s

- **Area:** A2 Performance · **Priority:** P1 · **Screen:** 6.4 · **Spec:** PERF-8, T4 · **Type:** Performance
- **Preconditions:** As A2-PERF-07.
- **Steps:**

    1. Rows; tick all 12 runs (about 120M rows); the same 2 filters.
    2. Warm-up once; then time Run 3 times.

- **Expected:** Median ≤ 30 s. Record median, min and max; misses are reported, not blocking.

### A2-PERF-09 — Grid scrolling: next page of 200 rows ≤ 100 ms

- **Area:** A2 Performance · **Priority:** P2 · **Screen:** 6.4 · **Spec:** PERF-9, T4 · **Type:** Performance
- **Preconditions:** A2-PERF-08's result on screen (100,000 rows held).
- **Steps:**

    1. Scroll down past the rows already shown (Page Down, then drag the scroll bar to the middle and the end). The automated suite times the next 200-row page read.
    2. Warm-up once; then 3 timed pages.

- **Expected:** Each next page of 200 rows appears with no visible wait; median ≤ 100 ms. Misses are reported, not blocking.

### A2-PERF-10 — Ticking, unticking or reordering a column ≤ 200 ms

- **Area:** A2 Performance · **Priority:** P2 · **Screen:** 6.4 · **Spec:** PERF-10, T4, P1 · **Type:** Performance
- **Preconditions:** A2-PERF-08's result on screen.
- **Steps:**

    1. Untick a column; tick it again; move a column with ↑ (grid redraw). Warm-up once; then 3 timed changes of each.

- **Expected:** Median ≤ 200 ms for each kind of change; no Job runs. Misses are reported, not blocking.

### A2-PERF-11 — Export 10M rows in 10 parts ≤ 60 s

- **Area:** A2 Performance · **Priority:** P1 · **Screen:** 7.4, 7.5 · **Spec:** PERF-11, T4, EXP-8 · **Type:** Performance
- **Preconditions:** As A2-PERF-07. An empty folder on the SSD with at least 5 GB free.
- **Steps:**

    1. Export data of one 10M-row run (20 columns), UTF-8 with BOM.
    2. Warm-up once (delete the files after each export); then time Export → banner, 3 times.

- **Expected:** 10 parts, _part01of10 to _part10of10; median ≤ 60 s. Record median, min and max; misses are reported, not blocking.

### A2-PERF-12 — Rows view export of 120M rows in 120 parts ≤ 12 min, cancellable

- **Area:** A2 Performance · **Priority:** P1 · **Screen:** 7.9, 7.5 · **Spec:** PERF-12, T4, EXP-10, EXP-14 · **Type:** Performance
- **Preconditions:** As A2-PERF-07. About 29 GB free on the destination drive plus one run's chunk (about 2.4 GB) on the %TEMP% drive (both on the same drive: the sum). If space is short, ask before scaling anything down; a scaled run is reported as scaled.
- **Steps:**

    1. Rows; tick all 12 runs; no filters; Run; Export rows (UTF-8 with BOM).
    2. Once, press Cancel midway; time until the dialog closes; list the folder and %TEMP%\Sankalan.
    3. Warm-up once, then time Export → banner 3 times (delete the parts between runs).

- **Expected:** 120 parts named _part001of120 to _part120of120; median ≤ 12 min. Cancel stops within a few seconds and leaves no part, .partial or chunk file. Record median, min and max; misses are reported, not blocking.

### A2-PERF-13 — Size and free-space estimate ≤ 2 s

- **Area:** A2 Performance · **Priority:** P2 · **Screen:** 7.4, 7.9 · **Spec:** PERF-13, T4, EXP-13, T34 · **Type:** Performance
- **Preconditions:** As A2-PERF-07.
- **Steps:**

    1. Open Export data for one 10M-row run; time from opening until "Checking size…" is replaced by the summary and Export is enabled.
    2. The same for Export rows on A2-PERF-08's result (12 runs).
    3. Warm-up once; then 3 timed openings of each.

- **Expected:** Median ≤ 2 s for each. Misses are reported, not blocking.

### A2-PERF-14 — Load step without checks: 10M rows from CSV ≤ 2 min

- **Area:** A2 Performance · **Priority:** P1 · **Screen:** 4.3b · **Spec:** PERF-14, PERF-1, T4, T44 · **Type:** Performance
- **Preconditions:** As A2-PERF-07, plus a template in TPL-N's shape (Check data before loading = No) and the 10M-row CSV from tools\perf\build_a2_data.py (about 1.2 GB).
- **Steps:**

    1. New run; add the CSV. Start a stopwatch on Next on Files; stop when the Load result (stat cards and text-value table) shows.
    2. Leave and discard; warm-up once, then 3 timed runs.

- **Expected:** Median ≤ 2 min, including the Convert sort, the text companions and the text-value summary. Record median, min and max; misses are reported, not blocking.

## Fixtures

| ID | File | Format | Structure | Contents (data row n = 1, 2, …) | Planted conditions and expected counts | Used by |
|---|---|---|---|---|---|---|
| F00 | (common rule) | — | — | TPL-A columns in order A–H: Invoice No, Invoice Date, Customer, GSTIN, State, Taxable Value, GST Rate, Tax Amount. Row n: Invoice No INV-{base+n, 5 digits}; Invoice Date = month start + ((n−1) mod days); Customer = list[(n−1) mod 10] (Shree Ganesh Traders, Patel Agencies, Mehta & Sons, Kaveri Distributors, Sai Enterprises, Laxmi Stores, Om Sai Wholesale, Krishna Retail, Annapurna Foods, Ganga Suppliers); GSTIN 27ABCDE{n mod 10000, 4 digits}F1Z5; State = [Maharashtra, Gujarat, Karnataka, Delhi][(n−1) mod 4]; Taxable Value = 1000 + ((n−1) mod 100) × 10.25; GST Rate = [0, 5, 12, 18, 28][(n−1) mod 5]; Tax Amount = Taxable × Rate / 100 rounded to 2 places (half away from zero). Dates are real Excel dates. | — | All TPL-A fixtures |
| F01 | Sample_Sales.xlsx | .xlsx | Sheet Sales; rows 1–2 title text ("Acme Traders — Sales Register", "Sample"); header row 3 | 1,000 rows; base 60000; August 2026 (31 days) | Taxable 1,507,375.00; Tax 191,344.50; 250 rows per state; 200 per rate | C3, C1-11 |
| F02 | Sales_Oct.xlsx | .xlsx | Sheet Sales; header row 1 | 5,000 rows; base 10000; October 2026 (31 days) | Taxable 7,536,875.00; Tax 956,722.50; 1,250 per state; 1,000 per rate; days 1–9 have 162 rows, days 10–31 have 161 | R-0001, RUNF, A1 |
| F03 | Sales_Nov.xlsx | .xlsx | Sheets: Sales (visible; row 1 title, header row 2), Notes (visible, free text), Old (hidden, 500 rows TPL-A layout) | 4,000 data rows; base 20000; November 2026 (30 days). After data rows 150, 300 … 3,750: one hidden row each (25), Taxable 99,999.99. After data rows 400, 800 … 4,000: one blank row each (10); the ones after 2,000 and 4,000 hold only spaces | Taxable 6,029,500.00; Tax 765,378.00; hidden 25 rows + sheet Old; blank rows 10 | R-0002 |
| F04 | Sales_Errors.xlsx | .xlsx | Sheet Sales; header row 1 (sheet row = n + 1) | 2,000 rows; base 40000; September 2026 (30 days); planted values on the rows listed | Errors: n 101–112 Invoice No blank (12); n 201–208 Invoice No INV4xxxx without hyphen (8); n 213–227 Taxable "abc" (15, sheet rows 214–228); n 301–305 Taxable negative, Tax recalculated (5); n 401–410 GSTIN cut to 14 chars (10); n 501–504 Invoice Date text "31-02-2026" (4); n 601–606 GST Rate 15, Tax at 15% (6); n 702, 704, 706 repeat the Invoice No of n 701, 703, 705 (6 rows flagged, 3 left out). Warnings: n 801–825 State Goa (25); n 901–907 Customer blank (7). Totals: Taxable Input 2,986,623.75 / Loaded 2,946,994.00 / Left out 39,629.75; Tax Input 381,662.10 / Loaded 374,994.35 / Left out 6,667.75 | R-0003, C3-16, RUNV |
| F05 | Sales_Oct_copy.xlsx | .xlsx | Byte-identical copy of F02 | — | Same SHA-256 as F02 | RUNF-11 |
| F06 | Sales_Protected.xlsx | .xlsx (encrypted) | F02 layout, 100 rows | Password Sankalan@123 to open | Error: password-protected | RUNF-05, RUNF-09 |
| F07 | Sales_Locked.xlsx | .xlsx | Sheet Sales; header row 1 | 1,000 rows; base 16000; October 2026 | Opened in Excel during the test | RUNF-06 |
| F08 | Sales_Renamed_Headers.xlsx | .xlsx | Sheet Sales; headers: Inv No, invoice_date, CUSTOMER, G.S.T.I.N, Taxable Value, GST-Rate, Tax Amount, Remarks (no State column) | 1,000 rows; base 70000; November 2026; Remarks = "ok" | Taxable 1,507,375.00; Tax 191,344.50 | R-0004, RUNM |
| F09 | Sales_NoHeader.xlsx | .xlsx | Sheet Sales holding only numbers, 100 rows × 8 columns, no text row | Random integers 1–999 | Error: header not found | RUNF-08 |
| F10 | Sales_WrongSheet.xlsx | .xlsx | One sheet named Data; header row 1 | 100 rows; base 17000 | Error: sheet Sales not found | RUNF-07 |
| F11 | Sales_Old.xls | .xls (Excel 97-2003) | F02 layout, 100 rows | — | Ready, 100 rows (changed 20-11-2026, D38) | C3-04, RUNF-03 |
| F12 | Sales_ManyIssues.csv | .csv UTF-8, comma | Header row 1, TPL-A columns | 15,000 rows; base 25000; October 2026; Customer empty on every row | 15,000 warnings (Customer Not blank) | RUNV-06 |
| F13 | Sales_Dec_NewCol.xlsx | .xlsx | Sheet Sales; TPL-A headers + Branch | 3,000 rows; base 50000; December 2026; Branch = [Pune, Nashik, Nagpur][(n−1) mod 3] | Taxable 4,522,125.00; Tax 574,033.50; 1,000 per branch | R-0005 |
| F14 | Sales_NoDates.xlsx | .xlsx | As F13 | 500 rows; base 80000; Invoice Date empty on every row | Taxable 753,687.50; Tax 95,672.25 | R-0006 |
| F15 | Sales_Jan.xlsx | .xlsx | As F13 | 2,000 rows; base 85000; January 2027 | Taxable 3,014,750.00; Tax 382,689.00 | R-0007 |
| F16 | Sales_Regions.xlsx | .xlsx | Sheets North (visible), South (visible), Archive (hidden); header row 1 each | North 1,500 rows base 90000; South 2,500 rows base 91500; Archive 300 rows; October 2026 | North 2,261,062.50; South 3,768,437.50; total 6,029,500.00 | C3-07, RUNF-13 |
| F17 | Conversion_Values.csv | .csv UTF-8, comma | Header: Case, Amount, Amount0, Doc Date, Due Date, Code | 13 rows C01–C13. Amount and Amount0 hold the same raw text: C01 "₹1,23,456.789"; C02 "1,234,567.5"; C03 "(1,234)"; C04 "2.345"; C05 "-2.345"; C06 "2.5"; C07 "-2.5"; C08 "₹ 500"; C09 "  750  "; C10 "0.005"; C11 "12abc"; C12 empty; C13 three spaces. Doc Date: C01 05-11-2026, C02 31-12-2026, C03 31-11-2026, C04 29-02-2028, C05 29-02-2027, others 01-01-2027. Due Date: C01 05/11/2026, C02 31/12/2026, C03 32/01/2027, others 15/01/2027. Code: C01 00123, C02 " A1 ", C03 three spaces, C04 MIXED Case, others X | Expected as CONV-01 to CONV-03. Warnings: Amount 1 + Amount0 1 (C11), Doc Date 2 (C03, C05), Due Date 1 (C03) | TPL-C, CONV |
| F18 | Conversion_1252.csv | .csv Windows-1252, semicolon | F17 header | 3 rows; Code = Café, Müller, Señor; Amount 1234.50, 10, 20 | Encoding Windows-1252 and delimiter ; detected | C3-08, CONV-04 |
| F19 | Conversion_Values.xlsx | .xlsx | Sheet Data (first visible); F17 header | Rows: Amount cell number 2.345; Amount formula =100*1.5; Amount #N/A error cell; Doc Date Excel date-time 05-11-2026 14:30; Code text cell 00123 | 150.00; blank + warning "#N/A"; 05-11-2026; 00123 | CONV-05 |
| F20 | Sales_Macro.xlsm | .xlsm | Sheet Sales; header row 1; one empty VBA module | 500 rows; base 15000; October 2026 | Ready | C3-04, RUNF-01, RUNF-03 |
| F21 | Run_Folder (a folder) | Folder | Contains a copy of F02 | — | Dropping a folder is refused | RUNF-01 |
| F22 | Sales_Nov.xls | .xls (Excel 97-2003), saved by Excel | F03 opened and saved as .xls | As F03 | As F03 | RUNF-15 |
| F23 | Sales_Nov.xlsb | .xlsb, saved by Excel | F03 opened and saved as .xlsb | As F03 | As F03 | RUNF-15 |
| F24 | Conversion_Values.xls | .xls, saved by Excel | F19 saved as .xls | As F19 | As F19 | CONV-06 |
| F25 | Conversion_Values.xlsb | .xlsb, saved by Excel | F19 saved as .xlsb | As F19 | As F19 | CONV-06 |
| F26 | Sales_Protected.xls | .xls (encrypted), saved by Excel | F06 contents | Password Sankalan@123 to open | Error: password-protected | RUNF-16 |
| F27 | Sales_Protected.xlsb | .xlsb (encrypted), saved by Excel | F06 contents | Password Sankalan@123 to open | Error: password-protected | RUNF-16 |
| F28 | Sales_Export.xls | HTML text named .xls | An HTML table with TPL-A headers and 10 rows | — | Error: web page or XML file with an Excel name | RUNF-17 |
| F29 | Sales_Notes.txt | Plain text | One line of text | — | Refused (only .xlsx, .xlsm, .xlsb, .xls and .csv) | C3-04, RUNF-03 |
| P01 | Perf_10M_01.csv … Perf_10M_12.csv | .csv UTF-8, comma (~2.2 GB each) | 20 columns: Invoice No (INV-{9 digits}), Invoice Date (DD-MM-YYYY text), Customer ID (CUST-{7 digits}), Customer Name, GSTIN, State, Category (CAT-01…CAT-20), HSN, Branch, Salesperson (50 names), Qty (0 dp), Rate, Taxable Value, GST Rate, CGST, SGST, IGST, Tax Amount, Place of Supply, Remarks (blank on 90%) | 10,000,000 rows each; file k uses month k of 2026; Customer ID = ((n−1) mod 1,000,000) + 1; Category = (n−1) mod 20; State and rates as F00; all rows clean | 0 errors; ~1M distinct Customer IDs per file | PERF, RUNV-12, A1-11/12/15, EXP-08, SH |
| P02 | Perf_xlsx_01.xlsx … Perf_xlsx_10.xlsx | .xlsx | Sheet Sales; P01 columns | 1,000,000 rows each, invoice numbers continuing across files | 10,000,000 rows in total | PERF-02 |
| F-A2-01 | TPLR_R1_Sales.xlsx, TPLR_R1_Part1.csv | .xlsx + .csv UTF-8, comma (tests\fixtures\tpl_r.py; `--full` for the full size) | Workbook sheets Sales A and Sales B, header row 1 each; CSV header row 1. TPL-R's 20 columns | October 2026. Full: Sales A 60,000, Sales B 40,000, CSV 2,400,000 rows (2,500,000); small: 900, 600, 1,000 (2,500). About 1% of cells blank, except Invoice No. Narration values with commas, double quotes and line breaks (\n in the workbook; \r\n and \n in the CSV) | Taxable Value text "NA" 1,000 / "Nil" 500 / "12,000/-" 10 = 1,510 (small 10 / 5 / 1 = 16): Is a number Warnings. No errors | TPL-R R-0001, R-0004, R-0005; A2-ROW, A2-TXT, A2-EXP |
| F-A2-02 | TPLR_R2_Sales.xlsx, TPLR_R2_Part1.csv, TPLR_R2_Part2.csv | .xlsx + 2 .csv | As F-A2-01, plus the column Place of Supply (21 columns) | November 2026. Full: 60,000, 40,000, 1,200,000, 1,200,000 (2,500,000); small: 900, 600, 500, 500 | 63 rows with an Invoice No failing Character pattern (Error; left out on override, both sizes). Invoice Date text "NA" 300 / "31-02-2026" 5 = 305 (small 3 / 2 = 5): Is a date Warnings. Rows loaded 2,499,937 | TPL-R R-0002; A2-ROW-13, A2-TXT |
| F-A2-03 | TPLR_R3_Sales.xlsx, TPLR_R3_Part1.csv, TPLR_R3_NoInvoiceNo.csv | .xlsx + 2 .csv | As F-A2-02; TPLR_R3_NoInvoiceNo.csv has no Invoice No column | December 2026. Full: 60,000, 40,000, 2,000,000, 400,000 (2,500,000); small: 900, 700, 500, 400 | 400,000 rows (small 400) with Invoice No left as null (MAP-6). Rows searched over R-0001 to R-0003: 7,499,937 (small 7,437) | TPL-R R-0003; A2-MEA-10, A2-EXP-09a, A2-EXP-12 |
| F-A2-04 | TPLN_Purchases_Part1.csv | .csv UTF-8, comma (tests\fixtures\tpl_n.py) | Header row 1, TPL-R's 20 columns | 500,000 data rows (small 5,000) plus its share of the blank rows. Values from TPL-R's generator | Across F-A2-04 and F-A2-05: Taxable Value text "NA" 4,000 / "Nil" 2,000 / "-" 790 / "12,000/-" 10 / " NA " 2 = 6,802 (small 68); Invoice Date text "NA" 100 / "31-02-2026" 20 = 120 (small 12); blank rows 10 (small 3), split over the two files | TPL-N sample and R-0001; A2-NCK |
| F-A2-05 | TPLN_Purchases_Part2.csv | .csv UTF-8, comma | As F-A2-04 | 500,000 data rows (small 5,000) plus the rest of the blank rows; its first 2,000 rows (small 20) are exact copies of rows of F-A2-04 | With F-A2-04: Rows read 1,000,010, blank rows skipped 10, rows loaded 1,000,000 including the 2,000 repeated rows (small 10,003 / 3 / 10,000 / 20) | TPL-N R-0001; A2-NCK |
| F-A2-06 | Sales_Nov-2026_Central.xlsx | .xlsx (tests\fixtures\generate.py) | Sheets Sales Nov (visible), Returns Nov (visible), Notes (hidden, free text); header row 1 | TPL-A columns (F00), November 2026. Sales Nov 300 rows base 100000; Returns Nov 50 rows base 100300. The sheet files F-A2-06 to F-A2-11 have one size only | With TPL-S's rule (Sales, Sales Returns): one Sheet not found row, "Sheets found: Sales Nov, Returns Nov". Dialog: about 300 / about 50 rows; Notes "Hidden, skipped" | TPL-S; A2-SHT |
| F-A2-07 | Sales_Nov-2026_East.xlsx | .xlsx | Sheet Sales; header row 1 | 200 rows; base 101000; November 2026 | Sheet not found (no Sales Returns); the dialog opens with Sales ticked | A2-SHT-04 |
| F-A2-08 | Sales_Nov-2026_West.xlsx | .xlsx | Sheets Sales, Sales Returns, Cover (title text, no header row); header row 1 on Sales and Sales Returns | Sales 100 rows base 102000; Sales Returns 20 rows base 102100; November 2026 | Ready by the rule (120 rows). Choosing Cover gives Header not found | TPL-S sample and R-0001; A2-SHT-01, A2-SHT-05 |
| F-A2-09 | Sales_Nov-2026_Central.xlsb | .xlsb, saved by Excel (tests\fixtures\static, make_static_formats.ps1) | F-A2-06 opened and saved as .xlsb | As F-A2-06 | As F-A2-06 | A2-SHT-01, A2-SHT-10 |
| F-A2-10 | Sales_Nov-2026_Central.xls | .xls (Excel 97-2003), saved by Excel | F-A2-06 opened and saved as .xls | As F-A2-06 | As F-A2-06 | A2-SHT-01, A2-SHT-10 |
| F-A2-11 | Sales_Nov-2026_Central_Renamed.xlsx | .xlsx | As F-A2-06 with sheet Sales Nov renamed Sales November | As F-A2-06 | Copied over Central (keeping Central's name) before Re-check: Sheet not found, "Sheets found: Sales November, Returns Nov" | A2-SHT-06 |

## Coverage (screen → test cases)

| # | Screen | Canvas file | Test cases |
|---|---|---|---|
| 1.1 | Clients | Main.dc.html | DEP-03, GEN-01, GEN-03, GEN-04, GEN-05, C1-02, C1-03, C1-04, C1-05, C1-06, C1-07, C1-08, C1-09, C1-10, PERF-08 |
| 1.2 | Client | Client.dc.html | GEN-06, C2-02, C2-03, C2-04, C2-05, C2-06, A2-NCK-09 |
| 2.1 | New template · Sample file | NewTemplate1.dc.html | C3-01, C3-02, C3-03, C3-04, C3-05, C3-22 |
| 2.2 | New template · Sheets | NewTemplate2.dc.html | C3-06, C3-07, C3-08, C3-22 |
| 2.3 | New template · Columns | NewTemplate3.dc.html | C3-09, C3-10, C3-11, C3-12, C3-22, A2-TXT-10 |
| 2.4 | New template · Rules | NewTemplate4.dc.html | C3-13, C3-14, C3-15, C3-16, C3-22, A2-NCK-01 |
| 2.4b | New template · Rules, data not checked | Not drawn in the repo canvas | A2-NCK-01 |
| 2.5 | New template · Default outputs | NewTemplate5.dc.html | C3-17, C3-18, C3-19, C3-22 |
| 2.6 | New template · Review | NewTemplate6.dc.html | C3-20, C3-21 |
| 3.1 | Template · Runs | Template.dc.html | GEN-04, GEN-05, GEN-06, C4-01, C4-02, C4-03, C4-04, A2-EXP-08b, A2-NCK-07, A2-NCK-08 |
| 3.2 | Template · Default outputs | TemplateOutputs.dc.html | C4-05, C4-06, C4-07, C4-08, A2-MEA-04, A2-MEA-09 |
| 3.3 | Template · Columns and rules | TemplateColumns.dc.html | C2-07, C4-09, C4-10, C4-11, C4-12, C4-13, C4-14, C4-15, C4-16, A2-MEA-07, A2-NCK-07 |
| 3.4 | Template · Settings | TemplateSettings.dc.html | C4-17, C4-18, A2-SHT-07, A2-NCK-07, A2-NCK-09 |
| 4.1 | Run · Files | RunFiles.dc.html | RUNF-01, RUNF-02, RUNF-03, RUNF-04, RUNF-10, RUNF-11, RUNF-12, RUNF-13, RUNF-14, RUNF-15, PERF-01, PERF-02, A2-SHT-01, A2-SHT-05, A2-SHT-07, A2-SHT-08, A2-SHT-09, A2-NCK-02, A2-NCK-05, A2-BUG-1c |
| 4.1a | Run · Files, a file can't be read | RunFilesError.dc.html | RUNF-05, RUNF-06, RUNF-07, RUNF-08, RUNF-09, RUNF-16, RUNF-17, A2-SHT-01, A2-SHT-05, A2-NCK-05 |
| 4.1b | Run · Files, a file has no matching sheet | Not drawn in the repo canvas | RUNF-07, A2-SHT-03, A2-SHT-04, A2-SHT-06, A2-SHT-07, A2-SHT-10 |
| 4.1c | Choose sheets for a file (dialog) | Not drawn in the repo canvas | A2-SHT-02, A2-SHT-03, A2-SHT-04, A2-SHT-05, A2-SHT-06, A2-SHT-10 |
| 4.2 | Run · Mapping | RunMapping.dc.html | RUNM-01, RUNM-02, RUNM-03, RUNM-04, RUNM-05, RUNM-06, RUNM-07, PERF-01, PERF-02, A2-SHT-09, A2-NCK-05, A2-BUG-1c |
| 4.3 | Run · Validate | RunValidate.dc.html | GEN-07, RUNV-01, RUNV-02, RUNV-03, RUNV-04, RUNV-05, RUNV-06, RUNV-07, RUNV-08, RUNV-09, RUNV-10, RUNV-11, RUNV-12, CONV-01, CONV-02, SH-01, PERF-01, PERF-02, PERF-07, A2-TXT-07, A2-BUG-1c |
| 4.3b | New run without checks · Load | Not drawn in the repo canvas | A2-NCK-02, A2-NCK-03, A2-NCK-04, A2-NCK-07, A2-PERF-14 |
| 4.4 | Run · Outputs | RunOutputs.dc.html | RUNO-01, RUNO-02, RUNO-03, RUNO-04, RUNO-05, RUNO-06, RUNO-07, PERF-01, PERF-02, A2-MEA-09, A2-BUG-1c |
| 4.5 | Run · Commit | RunCommit.dc.html | RUNC-01, RUNC-02, RUNC-03, RUNC-04, RUNC-05, RUNC-06, RUNC-07, RUNC-08, RUNC-10, PERF-01, PERF-02, A2-TXT-08, A2-BUG-1c |
| 4.5b | New run without checks · Commit | Not drawn in the repo canvas | A2-NCK-02, A2-NCK-06 |
| 5.1 | Run (Summary, Issues, Outputs, Source files) | Run.dc.html | GEN-04, GEN-06, RUNV-10, RUNC-05, C6-01, C6-02, C6-03, C6-04, C6-05, C6-06, C6-07, C6-08, C6-10, SH-05, A2-MEA-09, A2-EXP-08b, A2-EXP-14c, A2-SHT-08, A2-TXT-08, A2-TXT-09, A2-NCK-07, A2-NCK-08 |
| 6.1 | Saved analyses | Analyses.dc.html | GEN-01, A0-01, A0-04 |
| 6.2 | New analysis with result | Analysis.dc.html | A1-01, A1-02, A1-03, A1-04, A1-05, A1-06, A1-07, A1-08, A1-09, A1-10, A1-11, A1-12, A1-15, PERF-03, PERF-04, PERF-05, A2-ROW-01, A2-ROW-02, A2-MEA-01, A2-MEA-03, A2-MEA-04, A2-MEA-05, A2-MEA-06, A2-MEA-07, A2-MEA-08, A2-MEA-10, A2-MEA-11, A2-EXP-08b, A2-EXP-12, A2-TXT-02, A2-TXT-03, A2-TXT-04, A2-TXT-05, A2-TXT-06, A2-TXT-09, A2-NCK-10 |
| 6.3 | Saved analysis, settings locked | AnalysisSaved.dc.html | A0-02, A0-03, A2-ROW-04, A2-MEA-07, A2-MEA-08 |
| 6.4 | Rows view | Not drawn in the repo canvas | A2-ROW-01, A2-ROW-02, A2-ROW-03, A2-ROW-06, A2-ROW-07, A2-ROW-08, A2-ROW-09a, A2-ROW-09b, A2-ROW-10, A2-ROW-11a, A2-ROW-11b, A2-ROW-13, A2-ROW-14, A2-ROW-S1, A2-ROW-S2, A2-SHT-08, A2-TXT-01, A2-BUG-1b, A2-PERF-07, A2-PERF-08, A2-PERF-09, A2-PERF-10 |
| 6.5 | Filter on a Number column | Not drawn in the repo canvas | A2-ROW-06, A2-TXT-04 |
| 6.6 | Filter on a Date column | Not drawn in the repo canvas | A2-ROW-06, A2-TXT-04 |
| 7.1 | Override errors | DlgOverride.dc.html | RUNV-13 |
| 7.2 | Delete a run | DlgDeleteRun.dc.html | C2-08, C6-09 |
| 7.3 | Delete a client | DlgDeleteClient.dc.html | C1-11 |
| 7.4 | Export data | DlgExport.dc.html | C4-18, CONV-01, CONV-04, EXP-01, EXP-02, EXP-03, EXP-04, EXP-05, EXP-06, EXP-07, PERF-06, A2-MEA-05, A2-EXP-08a, A2-EXP-08b, A2-EXP-10, A2-EXP-12, A2-EXP-13, A2-EXP-13b, A2-PERF-11, A2-PERF-13 |
| 7.5 | Export in progress | DlgExporting.dc.html | EXP-08, A2-EXP-11, A2-EXP-14a, A2-EXP-14b, A2-EXP-14c, A2-PERF-11, A2-PERF-12 |
| 7.6 | Leave the run wizard | DlgLeaveRun.dc.html | RUNM-08, RUNC-09 |
| 7.7 | Leave an unsaved analysis | DlgLeaveAnalysis.dc.html | A1-14 |
| 7.8 | Save an analysis | DlgSaveAnalysis.dc.html | A1-13 |
| 7.9 | Export rows | Not drawn in the repo canvas | A2-ROW-08, A2-ROW-11b, A2-ROW-12a, A2-ROW-12b, A2-ROW-13, A2-ROW-14, A2-EXP-08a, A2-EXP-08b, A2-EXP-09a, A2-EXP-09b, A2-EXP-11, A2-TXT-01, A2-PERF-12, A2-PERF-13 |
| ND-1 | App settings dialog (not drawn) | C1/DEP | DEP-04, DEP-06, DEP-07, DEP-08, DEP-09, A2-BUG-1b |
| ND-2 | Empty states (not drawn) | — | C1-01, C2-01 |
| ND-3 | Delete template confirmation (not drawn) | — | C2-08 |
| ND-4 | Delete saved analysis confirmation (not drawn) | — | A0-05 |
| ND-5 | Export overwrite confirmation (not drawn) | — | EXP-06, A2-EXP-10, A2-EXP-14a |
| ND-6 | Data folder from a test build refused at start-up (not drawn) | — | A2-CAT-01 |
