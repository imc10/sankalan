"""Packaging: build the app with PyInstaller, run the packaged app's self-test, compile the installer."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import spec

ROOT = Path(__file__).resolve().parents[1]
ART = Path(__file__).parent / "_artifacts"


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    pytest.importorskip("PyInstaller")
    work = tmp_path_factory.mktemp("pyi")
    # through python -m: Smart App Control blocks the unsigned pyinstaller.exe launcher
    out = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(work / "dist"),
                          "--workpath", str(work / "build"), str(ROOT / "packaging" / "sankalan.spec")],
                         capture_output=True, text=True, timeout=900, cwd=ROOT)
    assert out.returncode == 0, out.stderr[-3000:]
    return work / "dist" / "Sankalan"


@spec("NF-10", "NF-1", "SEC-1")
def test_packaged_app_runs_self_test(bundle, tmp_path):
    """The packaged app runs its built-in end-to-end self-test (read, map, validate, block, override,
    re-check, write xlsx/csv, totals, save template, open window) and passes every check."""
    exe = bundle / ("Sankalan.exe" if sys.platform == "win32" else "Sankalan")
    report = tmp_path / "selftest.json"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", LANG="C.UTF-8")
    out = subprocess.run([str(exe), "--self-test", "--report", str(report)], env=env, capture_output=True,
                         text=True, timeout=300)
    r = json.loads(report.read_text(encoding="utf-8"))
    ART.mkdir(exist_ok=True)
    shutil.copy(report, ART / "packaged_selftest.json")
    if report.with_suffix(".png").exists():
        shutil.copy(report.with_suffix(".png"), ART / "packaged_selftest_window.png")
    assert out.returncode == 0 and r["passed"] and r["result"] == "PASS", [c for c in r["checks"] if not c["passed"]]
    assert len(r["checks"]) >= 18
    # SEC-1: no Qt networking, QML or VNC libraries shipped
    shipped = [p.name.lower() for p in bundle.rglob("*")]
    assert not [n for n in shipped if re.search(r"qt6network|qt6qml|qt6quick|qvnc|webengine", n)]
    # no compiled add-ons beyond the allowed set (each one is a file Smart App Control may block)
    assert not [n for n in shipped if re.search(r"calamine|lxml", n)]


@spec("NF-2", "NF-8", "SEC-5")
def test_installer_script_compiles_per_user(bundle, tmp_path):
    """The NSIS installer installs per user without admin rights, shows no publisher, and compiles."""
    nsi = (ROOT / "packaging" / "installer.nsi").read_text(encoding="utf-8")
    assert "RequestExecutionLevel user" in nsi and "$LOCALAPPDATA\\Programs" in nsi
    assert "CompanyName" not in nsi and "Publisher" not in nsi
    if not shutil.which("makensis"):
        pytest.skip("makensis not installed")
    out_exe = tmp_path / "Sankalan-Setup-test.exe"
    r = subprocess.run(["makensis", f"-DSRC={bundle}", f"-DOUT={out_exe}", str(ROOT / "packaging" / "installer.nsi")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-3000:]
    assert out_exe.exists() and out_exe.read_bytes()[:2] == b"MZ"     # a Windows executable


@spec("NF-7")
def test_build_script_signs_exe_and_installer():
    """The Windows build script signs both the exe and the installer with the certificate (SHA-256)."""
    bat = (ROOT / "packaging" / "build_windows.bat").read_text(encoding="utf-8")
    assert "signtool sign /fd SHA256" in bat
    ps = (ROOT / "packaging" / "sign_files.ps1").read_text(encoding="utf-8")
    assert "Get-AuthenticodeSignature" in ps and "*.pyd" in ps and "*.dll" in ps
    assert "Sankalan.exe --self-test" in bat and "pytest tests" in bat
    assert "-m PyInstaller" in bat and "sign_files.ps1" in bat
    vi = (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
    assert "CompanyName" not in vi and "'ProductName', 'Sankalan'" in vi
