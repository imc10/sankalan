# Sankalan UI screens (snapshot)

Snapshot of the "Sankalan UI screens" design canvas (https://claude.ai/artifact/U522ApcDroz6pGW3VKMvaD), taken 16-11-2026.
Each `.dc.html` file is one 1366×768 artboard: static HTML/CSS with inline styles plus sample data in the `renderVals()` script at the bottom.
Use them for layout, sizes, colours, copy and column sets. They are design mockups, not app code. Dialog files import the screen behind them (`<dc-import name="...">`).

Screens not drawn (see test-cases.md, Coverage ND-1…ND-5): App settings dialog, empty states, delete-template confirmation, delete-saved-analysis confirmation, export overwrite confirmation.

**Not yet drawn — the Tech Spec wins:** a Decimals field on Number columns (2.3, 3.3), the totals table as Input = Loaded + Left out (4.5) and an "Export left-out rows" menu item (3.1, 5.1). Build these from `docs/specs/technical-spec-v1.0.md`, matching the surrounding look.

## Shared look (from the artboards)

- Title bar 32 px, `#F6F7F8`, "सं" monogram on teal 18 px square + "Sankalan"
- Left rail 64 px, `#F6F7F8`; items Clients, Analysis; gear at the bottom; selected item `#E3F1F0` with text `#0A4F4F`
- Main padding 20–28 px top, 32 px sides; h1 22 px/500; subtitle 13 px `#5B636E`
- Primary button 36 px high, teal `#0E6B6B`, white 14 px/500; secondary outline `#9CC7C4` / text `#0A4F4F`
- Grids: 8 px radius, border `#E6E8EB`; header row 40 px `#F8F9FA`, 12 px/500 `#5B636E`; rows 40 px, 13 px, tabular figures, divider `#EEF0F2`
- Text `#1C2128`; muted `#5B636E`/`#444B55`; error `#B42318`; warning `#B54708`; success `#067647`; override badge `#FEF0E1`/`#93370D`
- Dialogs: 500 px wide, 12 px radius, 24 px padding, overlay `rgba(16,24,32,0.45)`; destructive button `#B42318` with an "I understand this can't be undone" tick
- Font: IBM Plex Sans (400/500), IBM Plex Sans Devanagari for the monogram

## Index

| # | Screen | File |
|---|---|---|
| 1.1 | Clients | [Main.dc.html](Main.dc.html) |
| 1.2 | Client: its templates | [Client.dc.html](Client.dc.html) |
| 2.1 | New template: Sample file | [NewTemplate1.dc.html](NewTemplate1.dc.html) |
| 2.2 | New template: Sheets | [NewTemplate2.dc.html](NewTemplate2.dc.html) |
| 2.3 | New template: Columns | [NewTemplate3.dc.html](NewTemplate3.dc.html) |
| 2.4 | New template: Rules | [NewTemplate4.dc.html](NewTemplate4.dc.html) |
| 2.5 | New template: Default outputs | [NewTemplate5.dc.html](NewTemplate5.dc.html) |
| 2.6 | New template: Review | [NewTemplate6.dc.html](NewTemplate6.dc.html) |
| 3.1 | Template: Runs | [Template.dc.html](Template.dc.html) |
| 3.2 | Template: Default outputs | [TemplateOutputs.dc.html](TemplateOutputs.dc.html) |
| 3.3 | Template: Columns and rules | [TemplateColumns.dc.html](TemplateColumns.dc.html) |
| 3.4 | Template: Settings | [TemplateSettings.dc.html](TemplateSettings.dc.html) |
| 4.1 | New run: Files | [RunFiles.dc.html](RunFiles.dc.html) |
| 4.1a | New run: Files, a file can't be read | [RunFilesError.dc.html](RunFilesError.dc.html) |
| 4.2 | New run: Mapping | [RunMapping.dc.html](RunMapping.dc.html) |
| 4.3 | New run: Validate | [RunValidate.dc.html](RunValidate.dc.html) |
| 4.4 | New run: Outputs | [RunOutputs.dc.html](RunOutputs.dc.html) |
| 4.5 | New run: Commit | [RunCommit.dc.html](RunCommit.dc.html) |
| 5.1 | Run: Summary, Issues, Outputs, Source files (tabs work in Play) | [Run.dc.html](Run.dc.html) |
| 6.1 | Saved analyses | [Analyses.dc.html](Analyses.dc.html) |
| 6.2 | New analysis with result | [Analysis.dc.html](Analysis.dc.html) |
| 6.3 | Saved analysis: settings locked | [AnalysisSaved.dc.html](AnalysisSaved.dc.html) |
| 7.1 | Override errors | [DlgOverride.dc.html](DlgOverride.dc.html) |
| 7.2 | Delete a run | [DlgDeleteRun.dc.html](DlgDeleteRun.dc.html) |
| 7.3 | Delete a client | [DlgDeleteClient.dc.html](DlgDeleteClient.dc.html) |
| 7.4 | Export data | [DlgExport.dc.html](DlgExport.dc.html) |
| 7.5 | Export in progress | [DlgExporting.dc.html](DlgExporting.dc.html) |
| 7.6 | Leave the run wizard | [DlgLeaveRun.dc.html](DlgLeaveRun.dc.html) |
| 7.7 | Leave an unsaved analysis | [DlgLeaveAnalysis.dc.html](DlgLeaveAnalysis.dc.html) |
| 7.8 | Save an analysis | [DlgSaveAnalysis.dc.html](DlgSaveAnalysis.dc.html) |
