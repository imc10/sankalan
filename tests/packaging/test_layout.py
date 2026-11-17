"""Phase 0: the V2 package layout, the entry point and the build spec."""
import subprocess
import sys

from conftest import ROOT

PACKAGES = ["jobs", "db", "model", "ingest", "validation", "query", "run", "ui", "ui/widgets", "ui/screens",
            "ui/dialogs"]


def test_v2_layout_exists():
    for p in PACKAGES:
        assert (ROOT / "sankalan" / p / "__init__.py").exists(), p
    assert (ROOT / "legacy" / "core" / "readers.py").exists(), "V1 code kept in legacy/ for reference"


def test_entry_point_runs():
    out = subprocess.run([sys.executable, "-m", "sankalan", "--version"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith("Sankalan 2.")


def test_build_spec_ships_v2_only():
    spec = (ROOT / "packaging" / "sankalan.spec").read_text(encoding="utf-8")
    assert '"sankalan" / "__main__.py"' in spec
    assert '"legacy"' in spec.split("EXCLUDES = [")[1].split("]")[0]       # legacy/ excluded from the bundle
    assert "hiddenimports=[]" in spec                                      # no xlrd / xlwt / msoffcrypto
