"""Shared test set-up. GUI tests run with QT_QPA_PLATFORM=offscreen."""
import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))

RESULTS = []


def spec(*ids):
    """Tag a test with the spec items or test-case IDs it proves."""
    return pytest.mark.spec(*ids)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    out = yield
    rep = out.get_result()
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        m = item.get_closest_marker("spec")
        RESULTS.append({"test": item.nodeid, "spec": list(m.args) if m else [], "outcome": rep.outcome,
                        "seconds": round(rep.duration, 2), "doc": (item.function.__doc__ or "").strip()})


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("SANKALAN_TEST_REPORT")
    if path:
        Path(path).write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory):
    """The fixture pack F01-F21, generated once per test session and verified against the Fixtures tab."""
    import generate
    out = generate.generate(tmp_path_factory.mktemp("fixtures"))
    generate.verify(out)
    return out
