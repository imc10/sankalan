"""Phase 11: self-test, uninstall data removal, build scripts, installer and the run-from-source fallback
(T2, T3, T10, T26, NF-2, NF-6, NF-7, SEC-6; DEP-01, DEP-03, DEP-06, DEP-10 to DEP-12 as far as they can be checked
without installing).

The PyInstaller build, the packaged self-test and the installer compile take minutes, so they run only with
SANKALAN_BUILD_TESTS=1 (build_windows.bat runs the same steps on every release build).
"""
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from conftest import ROOT, make_paths, spec
from sankalan import __version__

PKG = ROOT / "packaging"
BUILD_TESTS = os.environ.get("SANKALAN_BUILD_TESTS") == "1"
build_only = pytest.mark.skipif(not BUILD_TESTS, reason="set SANKALAN_BUILD_TESTS=1 to build the exe and installer")


def read(name: str) -> str:
    return (PKG / name).read_text(encoding="utf-8")


def isolated_env(tmp_path: Path) -> dict:
    """%LOCALAPPDATA% and %TEMP% inside the test folder, so nothing touches this PC's real Sankalan data."""
    local, temp = tmp_path / "LocalAppData", tmp_path / "Temp"
    local.mkdir()
    temp.mkdir()
    return dict(os.environ, LOCALAPPDATA=str(local), TEMP=str(temp), TMP=str(temp), QT_QPA_PLATFORM="offscreen")


def self_test(cmd: list[str], env: dict, report: Path) -> dict:
    out = subprocess.run([*cmd, "--self-test", "--report", str(report)], env=env, capture_output=True, text=True,
                         timeout=600)
    r = json.loads(report.read_text(encoding="utf-8"))
    assert out.returncode == (0 if r["passed"] else 1)
    return r


def failed(report: dict) -> list:
    return [c for c in report["checks"] if not c["passed"]]


# ---------------------------------------------------------------------------------------------- self-test
@spec("T3", "T10", "SEC-1", "SEC-4", "DEP-10")
def test_self_test_passes_from_source_without_touching_user_data(tmp_path):
    """``python -m sankalan --self-test`` runs a small run end to end in a temporary folder (reader workers,
    override, outputs, totals, commit, export, catalogue backup on re-open, window) and passes. The %LOCALAPPDATA%
    it was given is left untouched and its temp folder is cleaned up."""
    env = isolated_env(tmp_path)
    r = self_test([sys.executable, "-m", "sankalan"], env, tmp_path / "report.json")
    assert r["result"] == "PASS" and failed(r) == [], failed(r)
    assert r["version"] == __version__ and r["frozen"] is False
    names = {c["check"] for c in r["checks"]}
    assert {"DuckDB 2.0 loads", "python-calamine reads .xlsx", "DuckDB offline and locked", "Read in reader workers",
            "Totals reconcile", "Run committed", "CSV export", "Staging and temp emptied", "Window opens",
            "Catalogue backed up and upgraded at start", "Only allowed compiled packages",
            "Program files signed"} <= names
    sig = next(c for c in r["checks"] if c["check"] == "Program files signed")
    assert sig["skipped"] and "source" in sig["detail"]
    assert list(Path(env["LOCALAPPDATA"]).iterdir()) == []
    assert [p for p in Path(env["TEMP"]).iterdir() if p.name.startswith("sankalan-selftest-")] == []
    assert (tmp_path / "report.png").stat().st_size > 1000          # the window as drawn, for the build log


@spec("T3")
def test_self_test_reports_a_failure(tmp_path, monkeypatch):
    """A failing step makes the report FAIL with exit code 1, naming the error class."""
    from sankalan import selftest

    def broken(_folder):
        raise OSError("disk full")
    monkeypatch.setattr(selftest, "write_samples", broken)
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    report = tmp_path / "r.json"
    assert selftest.run_self_test(["--self-test", "--no-window", "--report", str(report)]) == 1
    r = json.loads(report.read_text(encoding="utf-8"))
    assert r["result"] == "FAIL" and failed(r)[0]["detail"].startswith("OSError")


def test_self_test_sample_xlsx_has_a_hidden_row(tmp_path):
    """The generated workbook (no writer package ships with the app) reads back with calamine, with the
    "SLF-HIDDEN" row marked hidden in the sheet XML (the self-test then checks the app skips it)."""
    import python_calamine
    from sankalan import selftest
    s = selftest.write_samples(tmp_path)
    rows = python_calamine.CalamineWorkbook.from_path(str(s["xlsx"])).get_sheet_by_name("Sales").to_python()
    assert rows[0] == selftest.HEADERS and len(rows) == selftest.XLSX_ROWS + 2
    hidden_at = selftest.HIDDEN_AFTER + 2                      # 1-based sheet row
    assert rows[hidden_at - 1][0] == "SLF-HIDDEN"
    sheet = zipfile.ZipFile(s["xlsx"]).read("xl/worksheets/sheet1.xml").decode()
    assert re.findall(r'<row r="(\d+)" hidden="1"', sheet) == [str(hidden_at)]
    assert s["loaded"] == selftest.XLSX_ROWS + selftest.CSV_ROWS


def test_signature_check_only_fails_when_signing_was_expected(monkeypatch, tmp_path):
    """Packaged build: unsigned files fail the check only with --expect-signed (the build passes it after
    signing); otherwise they are reported and the check is marked skipped."""
    from sankalan import selftest
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(selftest, "unsigned_files", lambda _d: [str(tmp_path / "x.pyd")])
    c = selftest.Checks()
    selftest.check_signatures(c, expect_signed=False)
    assert c.passed and c.items[0]["skipped"] and "1 unsigned" in c.items[0]["detail"]
    c = selftest.Checks()
    selftest.check_signatures(c, expect_signed=True)
    assert not c.passed
    monkeypatch.setattr(selftest, "unsigned_files", lambda _d: [])
    c = selftest.Checks()
    selftest.check_signatures(c, expect_signed=True)
    assert c.passed and not c.items[0]["skipped"]


# ---------------------------------------------------------------------------------------------- uninstall (T26)
def _installed(tmp_path, data=None):
    """A profile after some use: settings.json, logs, the data folder (default or moved), %TEMP%\\Sankalan."""
    from sankalan import paths as app_paths
    paths = make_paths(tmp_path)
    folder = Path(data) if data else paths.default_data_folder
    (folder / "t" / "tpl1").mkdir(parents=True)
    (folder / "catalogue.duckdb").write_bytes(b"x")
    (folder / "t" / "tpl1" / "data.parquet").write_bytes(b"x")
    paths.logs.mkdir(parents=True)
    (paths.logs / "sankalan.log").write_text("start", encoding="utf-8")
    paths.temp.mkdir(parents=True)
    (paths.temp / "spill.tmp").write_bytes(b"x")
    app_paths.save_settings(paths, {"data_folder": str(folder)})
    return paths, folder


@spec("T26", "DEP-12")
def test_remove_data_default_folder(tmp_path):
    from sankalan.uninstall import DONE, remove_data
    paths, folder = _installed(tmp_path)
    assert remove_data(paths) == DONE
    assert not paths.root.exists() and not folder.exists() and not paths.temp.exists()


@spec("T26", "DEP-12", "DEP-07")
def test_remove_data_moved_folder(tmp_path):
    """After Change… moved the data elsewhere, the folder settings.json names is deleted too."""
    from sankalan.uninstall import DONE, remove_data
    paths, folder = _installed(tmp_path, tmp_path / "D" / "SankalanData")
    assert remove_data(paths) == DONE
    assert not folder.exists() and not paths.root.exists()
    assert (tmp_path / "D").is_dir()                     # only the data folder itself, not its parent


@spec("T26")
def test_remove_data_leaves_a_folder_that_isnt_sankalans(tmp_path):
    """A settings.json pointing at a folder without catalogue.duckdb (edited or damaged) never deletes it."""
    from sankalan import paths as app_paths
    from sankalan.uninstall import NOT_OURS, is_data_folder, remove_data
    paths, _ = _installed(tmp_path)
    other = tmp_path / "Documents"
    other.mkdir()
    (other / "budget.xlsx").write_bytes(b"x")
    app_paths.save_settings(paths, {"data_folder": str(other)})
    assert remove_data(paths) == NOT_OURS
    assert (other / "budget.xlsx").exists() and not paths.root.exists()
    assert not is_data_folder(Path(tmp_path.anchor))     # a drive root never counts


def test_remove_data_with_nothing_installed(tmp_path):
    from sankalan.uninstall import DONE, remove_data
    assert remove_data(make_paths(tmp_path)) == DONE


@spec("T26")
def test_remove_data_entry_point(tmp_path):
    """The uninstaller runs ``Sankalan.exe --remove-data``: it reads %LOCALAPPDATA% like the app does."""
    env = isolated_env(tmp_path)
    root = Path(env["LOCALAPPDATA"]) / "Sankalan"
    (root / "Data").mkdir(parents=True)
    (root / "Data" / "catalogue.duckdb").write_bytes(b"x")
    out = subprocess.run([sys.executable, "-m", "sankalan", "--remove-data"], env=env, cwd=ROOT, timeout=60)
    assert out.returncode == 0 and not root.exists()


# ---------------------------------------------------------------------------------------------- build files
@spec("NF-6", "DEP-06")
def test_version_comes_from_the_package():
    """Exe version resource, installer and App settings all show sankalan.__version__."""
    sys.path.insert(0, str(PKG))
    import version
    assert version.version() == __version__
    assert version.numeric("2.0.0") == (2, 0, 0, 0) and version.numeric("2.1.3.dev4") == (2, 1, 3, 0)
    assert version.numeric("2.1.0rc1") == (2, 1, 0, 0)
    vi = read("version_info.txt")
    assert "{numbers}" in vi and "{version}" in vi and "'ProductName', 'Sankalan'" in vi
    assert "CompanyName" not in vi and "LegalCopyright" not in vi


@spec("T3", "T5", "SEC-1")
def test_build_spec():
    spec_text = read("sankalan.spec")
    assert "exclude_binaries=True" in spec_text and "COLLECT(" in spec_text      # folder build, not one exe
    assert "console=False" in spec_text and "upx=False" in spec_text
    assert "sankalan.ico" in spec_text and "version_info.txt" in spec_text and "app_version" in spec_text
    assert '"sankalan" / "ui" / "fonts"' in spec_text
    for mod in ("PySide6.QtNetwork", "PySide6.QtWebEngineCore", "pandas", "numpy", "pyarrow", "openpyxl"):
        assert f'"{mod}"' in spec_text


@spec("UI-1")
def test_icon_is_the_app_mark():
    """sankalan.ico holds the teal सं mark at 16 to 256 px (PNG entries), made by packaging/make_icon.py."""
    from PySide6.QtGui import QColor, QImage
    from sankalan.ui import theme
    data = (PKG / "sankalan.ico").read_bytes()
    _, kind, count = struct.unpack("<HHH", data[:6])
    sizes, first = [], None
    for i in range(count):
        w, _h, _c, _r, _p, _b, size, off = struct.unpack("<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
        sizes.append(w or 256)
        blob = data[off:off + size]
        assert blob[:8] == b"\x89PNG\r\n\x1a\n"
        if (w or 256) == 256:
            first = QImage.fromData(blob)
    assert kind == 1 and {16, 24, 32, 48, 256} <= set(sizes)
    assert first.pixelColor(128, 20) == QColor(theme.TEAL)


@spec("NF-7", "T2", "T3")
def test_build_script_order_and_signing():
    """build_windows.bat: tests → PyInstaller → sign → self-test of the built app → NSIS (signs uninstaller and
    installer) → installer signature check."""
    bat = read("build_windows.bat")
    steps = ["python -m pytest tests", "-m PyInstaller", "sign_files.ps1 -Path dist\\Sankalan",
             "Sankalan.exe --self-test", "packaging\\installer.nsi", "-VerifyOnly"]
    pos = [bat.index(s) for s in steps]
    assert pos == sorted(pos)
    assert "--expect-signed" in bat and "/DSIGN=" in bat and "packaging\\version.py" in bat
    assert "\r\n" in (PKG / "build_windows.bat").read_bytes().decode()          # CRLF for cmd.exe labels
    ps = read("sign_files.ps1")
    assert "Get-AuthenticodeSignature" in ps and '".pyd"' in ps and '".dll"' in ps and '".exe"' in ps
    assert "/fd SHA256 /td SHA256 /tr" in ps and '"RSA"' in ps and "TimeStamperCertificate" in ps
    assert "/sha1" in ps                                       # certificate on the USB token, by thumbprint
    assert "sign_files.ps1" in read("sign_one.bat")


@spec("NF-2", "NF-6", "T26", "SEC-6", "DEP-01", "DEP-10", "DEP-11", "DEP-12")
def test_installer_script():
    nsi = read("installer.nsi")
    assert "RequestExecutionLevel user" in nsi
    assert 'InstallDir "$LOCALAPPDATA\\Programs\\${APP}"' in nsi and '!define APP "Sankalan"' in nsi
    assert '"$SMPROGRAMS\\${APP}.lnk"' in nsi and '"$DESKTOP\\${APP}.lnk"' in nsi
    for word in ("Publisher", "CompanyName", "LegalCopyright", "Ollyver", "Vyazen", "Nullsoft"):
        assert word not in nsi.replace("!pragma warning disable 9100 ; no LegalCopyright", ""), word
    assert 'BrandingText "${APP} ${VERSION}"' in nsi
    # update in place: old program files removed first; the data folder is never named
    assert 'RMDir /r "$INSTDIR\\_internal"' in nsi and "Data" not in re.sub(r"(?s)Section \"Uninstall\".*", "", nsi)
    # running app blocks install/uninstall
    assert "Function .onInit" in nsi and "Function un.onInit" in nsi and "WAIT_UNTIL_CLOSED" in nsi
    # T26: the question, default No, silent uninstall keeps data, data removal by the app itself
    q = re.search(r"MessageBox MB_YESNO\|MB_ICONQUESTION\|MB_DEFBUTTON2 \"([^\"]+)\" /SD IDNO IDNO keep_data", nsi)
    assert q and "delete your Sankalan data" in q.group(1)
    assert "ExecWait '\"$INSTDIR\\${EXE}\" --remove-data' $0" in nsi
    assert "!uninstfinalize" in nsi and "!finalize" in nsi
    assert "\r\n" in (PKG / "installer.nsi").read_bytes().decode()


def _makensis():
    found = shutil.which("makensis")
    if found:
        return found
    p = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "NSIS" / "makensis.exe"
    return str(p) if p.exists() else None


@spec("NF-2")
def test_installer_compiles(tmp_path):
    """makensis compiles the script over a stand-in app folder; with SIGN set it calls the signer for the
    uninstaller and the installer."""
    exe = _makensis()
    if not exe:
        pytest.skip("NSIS not installed")
    src = tmp_path / "app"
    (src / "_internal").mkdir(parents=True)
    (src / "Sankalan.exe").write_bytes(b"MZ stand-in")
    signer = tmp_path / "sign me.bat"
    signed = tmp_path / "signed.txt"
    signer.write_bytes(f'@echo off\r\necho %~1>>"{signed}"\r\nexit /b 0\r\n'.encode())
    out_exe = tmp_path / "Sankalan-Setup-test.exe"
    r = subprocess.run([exe, "-V2", f"-DSRC={src}", f"-DOUT={out_exe}", "-DVERSION=2.0.0", "-DVERSION_NUM=2.0.0.0",
                        f"-DSIGN={signer}", str(PKG / "installer.nsi")], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert out_exe.read_bytes()[:2] == b"MZ"
    lines = signed.read_text().splitlines()
    assert len(lines) == 2 and lines[-1].strip().lower() == str(out_exe).lower()


# ---------------------------------------------------------------------------------------------- run from source
@spec("T3")
def test_source_package_is_a_dev_only_fallback(tmp_path):
    """Run-from-source (decision confirmed 17-11-2026): kept for development PCs until the certificate arrives,
    built from V2 (the sankalan package, requirements-lock, self-test, --remove-data on uninstall)."""
    r = subprocess.run([sys.executable, str(PKG / "make_source_package.py"), "--out", str(tmp_path), "--no-wheels"],
                       capture_output=True, text=True, timeout=300, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    name = f"Sankalan-{__version__}"
    z = zipfile.ZipFile(tmp_path / f"{name}-Windows.zip")
    names = set(z.namelist())
    for f in ("Install Sankalan.bat", "Uninstall Sankalan.bat", "README.txt", "app/Sankalan.pyw",
              "app/shortcuts.py", "app/sankalan.ico", "app/requirements.txt", "app/sankalan/__main__.py",
              "app/sankalan/selftest.py", "demo-data/Sales_Oct.xlsx", "demo-data/Sales_Nov.csv"):
        assert f"{name}/{f}" in names, f
    assert not [n for n in names if "/legacy/" in n or "__pycache__" in n]
    readme = z.read(f"{name}/README.txt").decode()
    assert "DEVELOPMENT AND TEST FALLBACK ONLY" in readme and "Smart App Control" in readme and __version__ in readme
    assert z.read(f"{name}/app/requirements.txt") == (ROOT / "requirements-lock.txt").read_bytes()
    install = z.read(f"{name}/Install Sankalan.bat").decode()
    uninstall = z.read(f"{name}/Uninstall Sankalan.bat").decode()
    assert "\r\n" in install and "--self-test" in install
    assert "sankalan-requirements.txt" in install            # a 1.x (or older) environment is rebuilt
    assert "--remove-data" in uninstall
    assert "from sankalan.__main__ import main" in z.read(f"{name}/app/Sankalan.pyw").decode()


# ---------------------------------------------------------------------------------------------- full build
@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    work = tmp_path_factory.mktemp("pyi")
    out = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath",
                          str(work / "dist"), "--workpath", str(work / "build"), str(PKG / "sankalan.spec")],
                         capture_output=True, text=True, timeout=1800, cwd=ROOT)
    assert out.returncode == 0, out.stderr[-3000:]
    return work / "dist" / "Sankalan"


@build_only
@spec("T2", "T3", "T5", "SEC-1", "DEP-13")
def test_packaged_app_self_test(bundle, tmp_path):
    """The built Sankalan.exe passes its self-test, its reader workers being the same exe in worker mode; only
    the allowed compiled packages ship."""
    exe = bundle / ("Sankalan.exe" if sys.platform == "win32" else "Sankalan")
    r = self_test([str(exe)], isolated_env(tmp_path), tmp_path / "report.json")
    assert r["result"] == "PASS" and r["frozen"] is True, failed(r)
    shipped = [p.name.lower() for p in bundle.rglob("*")]
    assert not [n for n in shipped if re.search(r"qt6network|qt6qml|qt6quick|qvnc|webengine", n)]
    assert not [n for n in shipped if re.search(r"numpy|pandas|pyarrow|lxml|openpyxl", n)]


@build_only
def test_packaged_installer_compiles(bundle, tmp_path):
    exe = _makensis()
    if not exe:
        pytest.skip("NSIS not installed")
    out_exe = tmp_path / "Sankalan-Setup.exe"
    r = subprocess.run([exe, "-V2", f"-DSRC={bundle}", f"-DOUT={out_exe}", f"-DVERSION={__version__}",
                        "-DVERSION_NUM=2.0.0.0", str(PKG / "installer.nsi")], capture_output=True, text=True,
                       timeout=900)
    assert r.returncode == 0, r.stdout[-3000:]
    assert out_exe.stat().st_size > 10_000_000
