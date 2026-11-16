# Sankalan V2 — Progress

The hand-over file between build sessions. Read it at the start of every session; update it at the end.

## Phase status

| Session | Phase | Status | Branch / commit | Notes |
| --- | --- | --- | --- | --- |
| 1 | 0 — Branch, toolchain, spikes, fixtures | Not started | | Do first; spike results can change later phases |
| 2 | 1 — Storage, catalogue, Job runner | Not started | | |
| 3 | 2 — Ingestion: probe, read, convert | Not started | | |
| 4 | 3 + 4 — Validation and issues; query layer and export | Not started | | Split into two sessions if it runs long |
| 5 | 5 — Run pipeline end-to-end (headless) | Not started | | Gate: TPL-A run sequence R-0001…R-0007 passes with no UI |
| 6 | 6 — UI shell and design system | Not started | | Can run in parallel with sessions 4–5 (own worktree, `sankalan/ui/` only) once Phase 1's Job interface is fixed |
| 7 | 7 — Clients, Client, Template screens | Not started | | |
| 8 | 8 — New template wizard | Not started | | |
| 9 | 9 — New run wizard and Run detail | Not started | | Largest UI phase; split wizard / Run detail if needed |
| 10 | 10 — Analysis and export dialogs | Not started | | |
| 11 | 11 — Packaging, signing, install/uninstall | Not started | | Signing needs the RSA OV certificate (R1) |
| 12 | 12 — Hardening and release acceptance | Not started | | Partly manual on the 16 GB test laptop |

Status values: Not started · In progress · Done · Blocked (say why).

## Decisions

Behaviours the specs leave open (the test sheet says "record"). **Proposed** defaults need the user's confirmation
before the phase that relies on them; mark them **Confirmed** with the date when settled.

| Item | Default | State | Needed by |
| --- | --- | --- | --- |
| C1-04 client-name uniqueness | Unique ignoring case ("acme traders" refused when "Acme Traders" exists) | Proposed | Phase 7 |
| RUNF-06 message wording | "<file> is open in another program. Close it, then Re-check" (Tech spec) | Proposed | Phase 2 |
| RUNV-02 Rows read with blank rows | Rows read includes blank rows (4,010 for F03); blank rows counted under rows left out (RUN-12) | Proposed | Phase 3 |
| SH-02 second long Job | Controls that start a long Job are disabled with tooltip "Another operation is running" | Proposed | Phase 6 |
| C2-08 duplicate-contents check scope | Within the same template only | Proposed | Phase 2 |
| RUNC-10 totals mismatch test | Fault-injection hook behind an environment variable, test builds only | Proposed | Phase 5 |
| Run-from-source route (V1 `packaging/source_install`) | Keep as a dev-only fallback until the certificate arrives, then retire (T3) | Proposed | Phase 11 |
| O12 unencrypted local data | Customer still to confirm (SEC-3); no code impact | Open (customer) | — |

## Known issues carried in

- `README.md` on `main` has unresolved merge-conflict markers (lines 1, 108, 110). Fix in Phase 0.
- The UI mockups don't yet show: the Decimals field (2.3, 3.3), the Input = Loaded + Left out totals table (4.5),
  and "Export left-out rows" (3.1, 5.1). Build them from the Tech Spec.
- Certificate (R1) not yet bought: develop with Smart App Control off; the SAC check waits for a signed build.

## Session log

Newest first. One entry per session: date, phase, what was done, deviations from the plan, what's next.

### 16-11-2026 — Planning (no code)
- Wrote `docs/IMPLEMENTATION_PLAN.md` from the Feature Spec v2.0, Technical Spec v1.0, UI screens canvas and Test Cases.
- Created the `v2` branch, `CLAUDE.md`, this file, and local spec copies in `docs/specs/`.
- Next: Session 1, Phase 0.

## Starting a session

Open a new Claude Code session in this folder on the `v2` branch and paste (change N):

```
Implement Phase N of docs/IMPLEMENTATION_PLAN.md.
Start by reading CLAUDE.md, docs/PROGRESS.md and the spec sections that phase needs.
Ask me before relying on any decision still marked Proposed.
Finish with the full test suite passing, docs/PROGRESS.md updated, and a commit on v2.
```

## Refreshing the spec copies

`docs/specs/` is a snapshot from 16-11-2026. If the live docs change (Feature Spec, Technical Spec, UI screens canvas,
Test Cases), ask Claude to re-export them into `docs/specs/` and note the date in the session log.
