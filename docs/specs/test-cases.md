# Sankalan — Test Cases (snapshot)

Snapshot of the "Sankalan Test Cases" sheet (https://claude.ai/artifact/GzEbdCbadKjdHdG9oTXEuF), taken 16-11-2026. The live sheet is the source of truth and holds test status; this copy is for reading during development. Expected figures here are the acceptance oracle for engine tests.

## Read me

Sankalan final version: test cases for a local Windows deployment  
Built 16-11-2026 from Sankalan_UX_Context.md, Sankalan_UI_Screens.md (30 screens) and the canvas; expected results include the changes in Technical Spec v1.0 (decimals, left-out rows, Input = Loaded + Left out, Export left-out rows, Run IDs never reused).  
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
LOW-DISK setup · Needs admin once: Disk Management > Create VHD, 30 GB, NTFS, letter V:. Move the data folder to V:\Sankalan with Change…. Fill with: fsutil file createnew V:\filler.bin <bytes> so free space is below one 10M-row load (PERF-08). Remove filler afterwards.  
Behaviour the spec leaves open (cases say "record")  
C1-04 client-name case rule · RUNF-06 message wording (UX doc vs Tech spec) · RUNV-02 Rows read with blank rows · SH-02 how a second long job is refused · C2-08 whether the duplicate-contents check spans templates · RUNC-10 needs a fault-injection build  

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
- **Preconditions:** F11 Sales_Old.xls, F20 Sales_Macro.xlsm.
- **Steps:**

    1. Open the file picker and check the file-type filter.
    2. Drag F11 onto the step.
    3. Pick F20.

- **Expected:** Picker offers .xlsx, .xlsm and .csv only. F11 is refused with a plain message that .xls files are not supported. F20 is accepted.

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

- **Area:** C3 New template · **Priority:** P1 · **Screen:** 2.4 · **Spec:** VR-7 · **Type:** Functional
- **Preconditions:** C3-12 done; step 4.
- **Steps:**

    1. Select Taxable Value, then Invoice Date.
    2. Try to remove "Is a number" / "Is a date".
    3. Switch one to Warning and back to Error.

- **Expected:** "Is a number" is present on every Number column and "Is a date" on Invoice Date, both Error. They have no remove control; severity can be set to Warning.

### C3-14 — Rule types offered per column type

- **Area:** C3 New template · **Priority:** P2 · **Screen:** 2.4 · **Spec:** VAL-1..9, T16 · **Type:** Functional
- **Preconditions:** Step 4.
- **Steps:**

    1. For a Text, a Number and a Date column open Add rule.

- **Expected:** Text: Not blank, Allowed values, Text length, Character pattern, Unique within the run. Number: Not blank, Number range, Allowed values, Unique. Date: Not blank, Date range, Unique. No between-column or across-run rules.

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

    1. Add DO1 "State-wise sales": Group by State; Sum Taxable Value renamed "Taxable"; Sum Tax Amount renamed "Tax"; Count Invoice No renamed "Invoices".
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
    2. Edit DO1: add Count distinct Customer renamed "Customers". Save.
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

### RUNF-03 — .xlsm accepted, .xls refused

- **Area:** C5 Run · Files · **Priority:** P2 · **Screen:** 4.1 · **Spec:** IN-3 · **Type:** Functional
- **Preconditions:** New run on TPL-A.
- **Steps:**

    1. Add F20 Sales_Macro.xlsm.
    2. Add F11 Sales_Old.xls.

- **Expected:** F20 is Ready. F11 is refused with a plain message that .xls isn't supported.

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

- **Area:** C5 Run · Files · **Priority:** P1 · **Screen:** 4.1a · **Spec:** IN-15 · **Type:** Functional
- **Preconditions:** New run with F10.
- **Steps:**

    1. Add F10 Sales_WrongSheet.xlsx (only sheet "Data").

- **Expected:** Error: sheet Sales not found. Exclude file / Re-check offered; Next disabled.

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

- **Expected:** Within a few seconds the wizard returns to Mapping (or Files when Mapping was skipped) and nothing is kept: _staging has no folder for this job.

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

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-5..7 · **Type:** Functional
- **Preconditions:** R-0001 ticked only.
- **Steps:**

    1. Group by State; Sum Taxable Value; Count Invoice No. Run.

- **Expected:** Flat table: Delhi 1,903,437.50 · 1,250; Gujarat 1,877,812.50 · 1,250; Karnataka 1,890,625.00 · 1,250; Maharashtra 1,865,000.00 · 1,250; grand total pinned 7,536,875.00 · 5,000.

### A1-04 — Measures and renaming

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-6 · **Type:** Functional
- **Preconditions:** R-0001 ticked.
- **Steps:**

    1. No group. Measures on Taxable Value: Sum, Count, Average, Min, Max; Count distinct Customer; Count distinct GSTIN. Rename Average to "Avg value". Run.

- **Expected:** Sum 7,536,875.00; Count 5,000; Avg value 1,507.38; Min 1,000.00; Max 2,014.75; Count distinct Customer 10; Count distinct GSTIN 5,000.

### A1-05 — Subtotals and sorting within groups

- **Area:** A1 Analysis · **Priority:** P1 · **Screen:** 6.2 · **Spec:** ANA-7, T23 · **Type:** Functional
- **Preconditions:** R-0001 ticked.
- **Steps:**

    1. Group State then GST Rate; Sum Taxable Value; Show subtotals on; Run.
    2. Sort Sum descending.

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

- **Expected:** Grid shows the first 100,000 rows with a note that there are more; the grand total is pinned. Export file has all ~1,000,000 group rows plus total.

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

- **Area:** Export · **Priority:** P1 · **Screen:** 7.5 · **Spec:** EXP-7, UI-5 · **Type:** Functional
- **Preconditions:** TPL-P run with 10M rows.
- **Steps:**

    1. Export data; Cancel midway; check the folder.
    2. Export again to completion; click Open folder.

- **Expected:** Progress with Cancel; after Cancel neither the file nor a .part file remains. When done, Open folder opens Explorer at the file; a banner with Open folder appears.

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

- **Expected:** Median ≤ 2 min (PERF-1, includes validation and totals check). Commit about 1 s. Record peak memory of Sankalan.exe (DuckDB capped at 8 GB). Misses are reported, not blocking.

### PERF-02 — Load 10M rows from 10 .xlsx ≤ 5 min

- **Area:** Performance · **Priority:** P1 · **Screen:** 4.1, 4.2, 4.3, 4.4, 4.5 · **Spec:** PERF-2, T15, T5 · **Type:** Performance
- **Preconditions:** PERF laptop: 16 GB RAM, 4 cores, SSD, Windows 11, fresh install, nothing else running. TPL-P "Perf 20 col" from P01 with the TPL-P rules, no default outputs.
- **Steps:**

    1. New run > add P02-01 … P02-10.
    2. Time as PERF-01.

- **Expected:** Median ≤ 5 min (provisional target). Task Manager shows reader worker processes (up to cores − 1) during reading.

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
| F11 | Sales_Old.xls | .xls (Excel 97-2003) | F02 layout, 100 rows | — | Refused (.xls not supported) | C3-04, RUNF-03 |
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
| P01 | Perf_10M_01.csv … Perf_10M_12.csv | .csv UTF-8, comma (~2.2 GB each) | 20 columns: Invoice No (INV-{9 digits}), Invoice Date (DD-MM-YYYY text), Customer ID (CUST-{7 digits}), Customer Name, GSTIN, State, Category (CAT-01…CAT-20), HSN, Branch, Salesperson (50 names), Qty (0 dp), Rate, Taxable Value, GST Rate, CGST, SGST, IGST, Tax Amount, Place of Supply, Remarks (blank on 90%) | 10,000,000 rows each; file k uses month k of 2026; Customer ID = ((n−1) mod 1,000,000) + 1; Category = (n−1) mod 20; State and rates as F00; all rows clean | 0 errors; ~1M distinct Customer IDs per file | PERF, RUNV-12, A1-11/12/15, EXP-08, SH |
| P02 | Perf_xlsx_01.xlsx … Perf_xlsx_10.xlsx | .xlsx | Sheet Sales; P01 columns | 1,000,000 rows each, invoice numbers continuing across files | 10,000,000 rows in total | PERF-02 |

## Coverage (screen → test cases)

| # | Screen | Canvas file | Test cases |
|---|---|---|---|
| 1.1 | Clients | Main.dc.html | DEP-03, GEN-01, GEN-03, GEN-04, GEN-05, C1-02, C1-03, C1-04, C1-05, C1-06, C1-07, C1-08, C1-09, C1-10, PERF-08 |
| 1.2 | Client | Client.dc.html | GEN-06, C2-02, C2-03, C2-04, C2-05, C2-06 |
| 2.1 | New template · Sample file | NewTemplate1.dc.html | C3-01, C3-02, C3-03, C3-04, C3-05, C3-22 |
| 2.2 | New template · Sheets | NewTemplate2.dc.html | C3-06, C3-07, C3-08, C3-22 |
| 2.3 | New template · Columns | NewTemplate3.dc.html | C3-09, C3-10, C3-11, C3-12, C3-22 |
| 2.4 | New template · Rules | NewTemplate4.dc.html | C3-13, C3-14, C3-15, C3-16, C3-22 |
| 2.5 | New template · Default outputs | NewTemplate5.dc.html | C3-17, C3-18, C3-19, C3-22 |
| 2.6 | New template · Review | NewTemplate6.dc.html | C3-20, C3-21 |
| 3.1 | Template · Runs | Template.dc.html | GEN-04, GEN-05, GEN-06, C4-01, C4-02, C4-03, C4-04 |
| 3.2 | Template · Default outputs | TemplateOutputs.dc.html | C4-05, C4-06, C4-07, C4-08 |
| 3.3 | Template · Columns and rules | TemplateColumns.dc.html | C2-07, C4-09, C4-10, C4-11, C4-12, C4-13, C4-14, C4-15, C4-16 |
| 3.4 | Template · Settings | TemplateSettings.dc.html | C4-17, C4-18 |
| 4.1 | Run · Files | RunFiles.dc.html | RUNF-01, RUNF-02, RUNF-03, RUNF-04, RUNF-10, RUNF-11, RUNF-12, RUNF-13, RUNF-14, PERF-01, PERF-02 |
| 4.1a | Run · Files, a file can't be read | RunFilesError.dc.html | RUNF-05, RUNF-06, RUNF-07, RUNF-08, RUNF-09 |
| 4.2 | Run · Mapping | RunMapping.dc.html | RUNM-01, RUNM-02, RUNM-03, RUNM-04, RUNM-05, RUNM-06, RUNM-07, PERF-01, PERF-02 |
| 4.3 | Run · Validate | RunValidate.dc.html | GEN-07, RUNV-01, RUNV-02, RUNV-03, RUNV-04, RUNV-05, RUNV-06, RUNV-07, RUNV-08, RUNV-09, RUNV-10, RUNV-11, RUNV-12, CONV-01, CONV-02, SH-01, PERF-01, PERF-02, PERF-07 |
| 4.4 | Run · Outputs | RunOutputs.dc.html | RUNO-01, RUNO-02, RUNO-03, RUNO-04, RUNO-05, RUNO-06, RUNO-07, PERF-01, PERF-02 |
| 4.5 | Run · Commit | RunCommit.dc.html | RUNC-01, RUNC-02, RUNC-03, RUNC-04, RUNC-05, RUNC-06, RUNC-07, RUNC-08, RUNC-10, PERF-01, PERF-02 |
| 5.1 | Run (Summary, Issues, Outputs, Source files) | Run.dc.html | GEN-04, GEN-06, RUNV-10, RUNC-05, C6-01, C6-02, C6-03, C6-04, C6-05, C6-06, C6-07, C6-08, C6-10, SH-05 |
| 6.1 | Saved analyses | Analyses.dc.html | GEN-01, A0-01, A0-04 |
| 6.2 | New analysis with result | Analysis.dc.html | A1-01, A1-02, A1-03, A1-04, A1-05, A1-06, A1-07, A1-08, A1-09, A1-10, A1-11, A1-12, A1-15, PERF-03, PERF-04, PERF-05 |
| 6.3 | Saved analysis, settings locked | AnalysisSaved.dc.html | A0-02, A0-03 |
| 7.1 | Override errors | DlgOverride.dc.html | RUNV-13 |
| 7.2 | Delete a run | DlgDeleteRun.dc.html | C2-08, C6-09 |
| 7.3 | Delete a client | DlgDeleteClient.dc.html | C1-11 |
| 7.4 | Export data | DlgExport.dc.html | C4-18, CONV-01, CONV-04, EXP-01, EXP-02, EXP-03, EXP-04, EXP-05, EXP-06, EXP-07, PERF-06 |
| 7.5 | Export in progress | DlgExporting.dc.html | EXP-08 |
| 7.6 | Leave the run wizard | DlgLeaveRun.dc.html | RUNM-08, RUNC-09 |
| 7.7 | Leave an unsaved analysis | DlgLeaveAnalysis.dc.html | A1-14 |
| 7.8 | Save an analysis | DlgSaveAnalysis.dc.html | A1-13 |
| ND-1 | App settings dialog (not drawn) | C1/DEP | DEP-04, DEP-06, DEP-07, DEP-08, DEP-09 |
| ND-2 | Empty states (not drawn) | — | C1-01, C2-01 |
| ND-3 | Delete template confirmation (not drawn) | — | C2-08 |
| ND-4 | Delete saved analysis confirmation (not drawn) | — | A0-05 |
| ND-5 | Export overwrite confirmation (not drawn) | — | EXP-06 |
