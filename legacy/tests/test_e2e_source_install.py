"""Run-from-source package (works without a code-signing certificate, also under Smart App Control)."""
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from conftest import spec

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))


@pytest.fixture(scope="module")
def package(tmp_path_factory):
    from make_source_package import build
    out = tmp_path_factory.mktemp("srcpkg")
    wheels = os.environ.get("SANKALAN_WHEELS")
    z = build(out, Path(wheels) if wheels else None, download=False, demo=True)
    ex = tmp_path_factory.mktemp("unzipped")
    with zipfile.ZipFile(z) as zf:
        zf.extractall(ex)
    return ex / "Sankalan-1.0.0", z


@spec("DEP-1")
def test_package_layout(package):
    """The zip holds the installer, uninstaller, readme, the app with a launcher, pinned packages and demo data."""
    root, z = package
    for f in ("Install Sankalan.bat", "Uninstall Sankalan.bat", "README.txt", "app/Sankalan.pyw",
              "app/shortcuts.py", "app/requirements.txt", "app/sankalan/__init__.py",
              "app/sankalan/core/xlsx.py", "app/sankalan/ui/sankalan.ico",
              "demo-data/templates", "demo-data/Acme Traders sales FY26-27/Sales_Jul-2026.xlsx"):
        assert (root / f).exists(), f
    assert not list(root.rglob("__pycache__"))
    req = (root / "app" / "requirements.txt").read_text()
    pins = dict(re.findall(r"^([A-Za-z0-9_.-]+)==(\S+)", req, re.M))
    assert pins["PySide6-Essentials"] == "6.12.0" and "python-calamine" not in req and "lxml" not in req
    for name in ("XlsxWriter", "xlrd", "xlwt", "msoffcrypto-tool"):
        assert name in pins
    # batch files need Windows line endings
    for f in ("Install Sankalan.bat", "Uninstall Sankalan.bat"):
        raw = (root / f).read_bytes()
        assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")


@spec("DEP-2", "NF-2")
def test_installer_steps(package):
    """Per-user install, no admin; offline from the bundled packages; self-test before shortcuts;
    shortcuts start the signed pythonw.exe; uninstall keeps templates."""
    root, _ = package
    bat = (root / "Install Sankalan.bat").read_text(encoding="utf-8")
    assert "%LOCALAPPDATA%\\Programs\\Sankalan" in bat and "runas" not in bat.lower()
    assert "py -3.13 -m venv" in bat
    assert '--no-index --find-links "%~dp0wheels"' in bat
    assert bat.index("--self-test") < bat.index("shortcuts.py")
    assert "powershell" not in bat.lower()          # PowerShell is restricted under Smart App Control
    assert '"result\\": \\"PASS\\""' in bat
    sc = (root / "app" / "shortcuts.py").read_text(encoding="utf-8")
    assert '"pythonw.exe"' in sc and "Sankalan.pyw" in sc and "sankalan.ico" in sc and "IPersistFile" in sc
    un = (root / "Uninstall Sankalan.bat").read_text(encoding="utf-8")
    assert "Documents" not in un.replace("Documents\\Sankalan\\Templates are kept", "")
    assert 'rmdir /s /q "%DEST%"' in un and 'if exist "%DEST%\\app\\Sankalan.pyw"' in un
    assert "shortcuts.py" in un and "--remove" in un and "powershell" not in un.lower()


@spec("DEP-3", "SEC-7")
def test_launcher_runs_packaged_source_self_test(package, tmp_path):
    """The launcher in the unzipped package runs the full self-test from the package's own copy of the app."""
    root, _ = package
    pyw = root / "app" / "Sankalan.pyw"
    report = tmp_path / "selftest.json"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env.pop("PYTHONPATH", None)
    out = subprocess.run([sys.executable, str(pyw), "--self-test", "--report", str(report)], env=env,
                         cwd=tmp_path, capture_output=True, text=True, timeout=300)
    r = json.loads(report.read_text(encoding="utf-8"))
    assert out.returncode == 0 and r["result"] == "PASS", [c for c in r["checks"] if not c["passed"]]
    where = subprocess.run([sys.executable, "-c",
                            f"import sys; sys.path.insert(0, {str(pyw.parent)!r}); import sankalan; print(sankalan.__file__)"],
                           env=env, cwd=tmp_path, capture_output=True, text=True)
    assert str(root) in where.stdout


@spec("DEP-4")
def test_bundled_windows_packages(package):
    """When packages are bundled, they are exactly the pinned versions, built for 64-bit Windows and Python 3.13."""
    root, _ = package
    wheels = root / "wheels"
    if not wheels.exists():
        pytest.skip("package built without bundled packages (set SANKALAN_WHEELS)")
    names = [p.name for p in wheels.glob("*.whl")]
    for n in names:
        tags = n[:-4].split("-")[-3:]
        py, abi, plat = tags
        assert plat in ("win_amd64", "any"), n
        assert abi in ("none", "abi3", "cp313"), n
    req = (root / "app" / "requirements.txt").read_text()
    for name, ver in re.findall(r"^([A-Za-z0-9_.-]+)==(\S+)", req, re.M):
        norm = name.lower().replace("-", "_")
        assert any(n.lower().startswith(f"{norm}-{ver}-") for n in names), (name, ver)
    assert not any("calamine" in n or "lxml" in n for n in names)


@spec("DEP-2")
def test_shortcut_helper_is_safe_off_windows(package):
    """The shortcut helper only acts on Windows; elsewhere it says so and exits without changes."""
    root, _ = package
    out = subprocess.run([sys.executable, str(root / "app" / "shortcuts.py"), "--dest", str(root)],
                         capture_output=True, text=True)
    if os.name == "nt":
        pytest.skip("runs for real on Windows")
    assert out.returncode == 2 and "only be made on Windows" in out.stdout
