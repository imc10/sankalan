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

SUITE = 190                    # the whole normal suite (`pytest tests`): measured 150 s

BUDGETS = {
    # engine
    "tests/engine/test_bug1.py": 5,
    "tests/engine/test_catalogue.py": 5,
    "tests/engine/test_commit_crash.py": 5,
    "tests/engine/test_connection.py": 5,
    "tests/engine/test_convert_sql.py": 5,
    "tests/engine/test_datafolder.py": 5,
    "tests/engine/test_export.py": 12,
    "tests/engine/test_ingest_load.py": 14,
    "tests/engine/test_ingest_probe.py": 5,
    "tests/engine/test_jobs.py": 5,
    "tests/engine/test_move.py": 5,
    "tests/engine/test_query.py": 6,
    "tests/engine/test_rules_sql.py": 5,
    "tests/engine/test_run_pipeline.py": 7,
    "tests/engine/test_template_sample.py": 6,
    "tests/engine/test_text_values.py": 5,
    "tests/engine/test_validation.py": 5,
    # GUI (offscreen)
    "tests/gui/test_analysis.py": 17,
    "tests/gui/test_clients.py": 5,
    "tests/gui/test_dialog_buttons.py": 8,
    "tests/gui/test_new_run.py": 14,
    "tests/gui/test_new_template.py": 21,
    "tests/gui/test_shell.py": 11,
    "tests/gui/test_template.py": 17,
    # packaging, security, unit
    "tests/packaging/test_installer.py": 9,
    "tests/packaging/test_layout.py": 5,
    "tests/security/test_offline.py": 5,
    "tests/unit/test_excel_readers.py": 5,
    "tests/unit/test_fixture_pack.py": 6,
    "tests/unit/test_formats.py": 5,
    "tests/unit/test_ingest_values.py": 5,
    "tests/unit/test_manage.py": 5,
    "tests/unit/test_paths.py": 5,
    # slow tier (`pytest -m slow`): the full TPL-R is built once (~5 min) and then cached in tests/fixtures/_generated
    "tests/engine/test_stored_order.py": 250,          # measured 198 s (3 x 2.5M-row runs committed)
}

# Build-only tests (SANKALAN_BUILD_TESTS=1: PyInstaller build, packaged self-test, installer compile, ~2¼ min).
BUILD_BUDGET = 170
