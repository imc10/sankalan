"""Expected completion times of the test files (seconds), enforced by ``tests/conftest.py``.

Measured on the dev PC on 21-11-2026 (full normal suite 150 s), then rounded up with about 25% headroom for normal
run-to-run variation, minimum 5 s. A file's time includes its fixtures (storage, committed runs, generated data).

**Rule (CLAUDE.md → Test time budgets):** when a file runs more than 10% over its expected time (``OVERRUN``), the
run stops at once with a message naming the file. Investigate the cause, fix it, then run again. A single test that
hangs is killed by a watchdog 10 s after that limit, with every thread's stack printed. Change a budget only when a
change makes a file legitimately slower (new tests, a bigger fixture); say so in docs/PROGRESS.md.

``SANKALAN_NO_TIME_BUDGET=1`` turns the checks off (debugging with breakpoints only; never for a suite run that
decides a commit).
"""

OVERRUN = 1.10                 # stop at expected time + 10%
DEFAULT = 30                   # a file not listed yet: add it here once it has been timed

SUITE = 215                    # the whole normal suite (`pytest tests`): measured 150 s; 190 s with A2-5 (2 new files)

BUDGETS = {
    # engine
    "tests/engine/test_bug1.py": 8,                    # A2-2: the old-code proof may try its scenario 3 times
    "tests/engine/test_catalogue.py": 5,
    "tests/engine/test_choose_sheets.py": 10,          # A2-2: measured 7 s (on battery)
    "tests/engine/test_commit_crash.py": 5,
    "tests/engine/test_connection.py": 5,
    "tests/engine/test_convert_sql.py": 5,
    "tests/engine/test_datafolder.py": 5,
    "tests/engine/test_export.py": 16,                 # A2-3: + 9 export-in-parts tests, measured 12 s
    "tests/engine/test_ingest_load.py": 14,
    "tests/engine/test_ingest_probe.py": 5,
    "tests/engine/test_jobs.py": 5,
    "tests/engine/test_move.py": 5,
    "tests/engine/test_query.py": 6,
    "tests/engine/test_rows_view.py": 8,               # A2-5: commits TPL-R small R-0001…R-0003, measured 6 s
    "tests/engine/test_rules_sql.py": 5,
    "tests/engine/test_run_pipeline.py": 9,            # A2-4: AC-MEA-9 commits a third run, measured 9.1 s on battery
    "tests/engine/test_template_sample.py": 6,
    "tests/engine/test_text_values.py": 5,
    "tests/engine/test_unchecked.py": 10,               # A2-2: measured 8 s
    "tests/engine/test_validation.py": 5,
    # GUI (offscreen)
    "tests/gui/test_analysis.py": 23,                  # A2-4: + rename and checks tests (2 runs), measured 20.8 s
    "tests/gui/test_choose_sheets_screens.py": 12,       # A2-2: measured 8 s (on battery)
    "tests/gui/test_clients.py": 5,
    "tests/gui/test_dialog_buttons.py": 8,
    "tests/gui/test_export_dialog.py": 8,              # A2-3: measured 5 s
    "tests/gui/test_measures.py": 5,                   # A2-4: measured 1 s
    "tests/gui/test_new_run.py": 16,                   # A2-3: settles for the Export dialog size check
    "tests/gui/test_new_template.py": 21,
    "tests/gui/test_rows_view_screen.py": 21,          # A2-5: commits TPL-R small, 11 tests, measured 16.6 s
    "tests/gui/test_shell.py": 11,
    "tests/gui/test_template.py": 19,                  # A2-4: + preview rename test, measured 19.4 s (wall)
    "tests/gui/test_unchecked_screens.py": 15,                 # A2-2: measured 11 s
    # packaging, security, unit
    "tests/packaging/test_installer.py": 9,
    "tests/packaging/test_layout.py": 5,
    "tests/security/test_offline.py": 5,
    "tests/unit/test_definition_v2.py": 5,             # A2-4
    "tests/unit/test_excel_readers.py": 5,
    "tests/unit/test_export_plan.py": 5,
    "tests/unit/test_export_split.py": 5,              # A2-3: measured 2 s
    "tests/unit/test_fixture_pack.py": 8,              # A2-2: + TPL-N small generated twice
    "tests/unit/test_formats.py": 5,
    "tests/unit/test_headers.py": 5,                   # A2-4
    "tests/unit/test_ingest_values.py": 5,
    "tests/unit/test_manage.py": 5,
    "tests/unit/test_paths.py": 5,
    # slow tier (`pytest -m slow`): the full TPL-R is built once (~5 min) and then cached in tests/fixtures/_generated
    "tests/engine/test_stored_order.py": 300,          # measured 198 s; 209 s with A2-3's export; 252 s with A2-5's Rows view
    "tests/engine/test_export_big.py": 10,             # A2-3: measured 2 s
    "tests/engine/test_unchecked_full.py": 30,         # A2-2: measured 16 s on battery (generation not counted)
    # perf tier (`pytest -m perf tests/perf`, A2-6 and release only): needs tools/perf/build_a2_data.py data
    "tests/perf/test_a2_perf.py": 5400,
}

# Build-only tests (SANKALAN_BUILD_TESTS=1: PyInstaller build, packaged self-test, installer compile, ~2¼ min).
BUILD_BUDGET = 170
