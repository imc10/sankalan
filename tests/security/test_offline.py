"""Offline and packaging guards that hold from Phase 0 on (SEC-1, SEC-7, NF-6, UI-4)."""
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from conftest import ROOT, spec

PKG = ROOT / "sankalan"
NETWORK_MODULES = {"socket", "urllib", "urllib3", "http", "requests", "httpx", "ftplib", "smtplib", "poplib",
                   "imaplib", "xmlrpc", "webbrowser", "telnetlib", "ssl", "asyncio", "aiohttp", "websocket",
                   "websockets"}
# top-level names of compiled modules loaded from site-packages (duckdb's binary is the top-level `_duckdb`)
ALLOWED_COMPILED = {"PySide6", "shiboken6", "_duckdb", "duckdb", "python_calamine"}


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
            yield from (f"{node.module}.{a.name}" for a in node.names)


def _sources():
    return sorted(PKG.rglob("*.py"))


@spec("SEC-1")
def test_no_network_code_in_the_app():
    """No module imports networking, update, telemetry or LLM libraries, or a Qt network module."""
    found = [(p.relative_to(ROOT).as_posix(), n) for p in _sources() for n in _imports(p)
             if n.split(".")[0] in NETWORK_MODULES or "QtNetwork" in n or "QtWebEngine" in n]
    assert found == []
    text = " ".join(p.read_text(encoding="utf-8").lower() for p in _sources())
    for word in ("openai", "anthropic", "telemetry", "https://", "auto-update", "update check"):
        assert word not in text, word
    urls = set(re.findall(r"http://[^\s\"']+", text))
    assert all(u.startswith(("http://schemas.openxmlformats.org/", "http://purl.oclc.org/ooxml/"))
               for u in urls), urls                       # XML namespace names only, never fetched


@spec("SEC-1", "T7")
def test_no_extension_install_or_load_in_sql():
    """DuckDB extensions are never installed or loaded. The Phase 0 spike showed an explicit INSTALL downloads
    even with autoinstall off and the configuration locked, so no app source may contain one."""
    pat = re.compile(r"\b(?:FORCE\s+)?INSTALL\s+\w+|\bLOAD\s+\w+\s*(?:;|['\"]|$)", re.IGNORECASE | re.MULTILINE)
    bad = [(p.relative_to(ROOT).as_posix(), m.group(0).strip()) for p in _sources()
           for m in pat.finditer(p.read_text(encoding="utf-8"))]
    assert bad == []


@spec("V3-1")
def test_screens_never_touch_duckdb():
    """DuckDB is used only by db/, query/ and Jobs; the window code never imports it."""
    found = [p.relative_to(ROOT).as_posix() for p in (PKG / "ui").rglob("*.py")
             if any(n.split(".")[0] in ("duckdb", "_duckdb") for n in _imports(p))]
    assert found == []


@spec("NF-6", "UI-4")
def test_no_publisher_name_in_the_app():
    """No publisher or company name anywhere in the app."""
    text = " ".join(p.read_text(encoding="utf-8").lower() for p in _sources())
    assert "ollyver" not in text and "analytics pvt" not in text


def test_app_never_imports_legacy():
    """V1 code in legacy/ is reference only."""
    found = [(p.relative_to(ROOT).as_posix(), n) for p in _sources() for n in _imports(p)
             if n.split(".")[0] == "legacy"]
    assert found == []


@spec("SEC-7", "T2")
def test_only_allowed_compiled_addons_load(tmp_path):
    """Smart App Control blocks unsigned compiled add-ons. Importing every app module and using DuckDB,
    python-calamine and a Qt window loads only PySide6/shiboken6, duckdb and python-calamine from site-packages.
    Later phases extend this to a full run."""
    sample = tmp_path / "s.xlsx"
    import xlsxwriter                      # dev-only: make a sample in this process, not in the checked one
    wb = xlsxwriter.Workbook(str(sample))
    wb.add_worksheet("S").write(0, 0, "x")
    wb.close()
    code = r"""
import importlib, json, pkgutil, sys
sys.path.insert(0, %r)
import sankalan
for m in pkgutil.walk_packages(sankalan.__path__, "sankalan."):
    if m.name != "sankalan.__main__":
        importlib.import_module(m.name)
import duckdb, python_calamine
con = duckdb.connect(); con.execute("SELECT sum(i) FROM range(1000) t(i)").fetchone(); con.close()
python_calamine.CalamineWorkbook.from_path(%r).get_sheet_by_name("S").to_python()
from PySide6.QtWidgets import QApplication, QLabel
app = QApplication([]); w = QLabel("Sankalan"); w.show(); app.processEvents()
mods = sorted({n.split(".")[0] for n, mo in list(sys.modules.items())
               if (getattr(mo, "__file__", "") or "").lower().endswith((".pyd", ".so"))
               and "site-packages" in (getattr(mo, "__file__", "") or "")})
print(json.dumps(mods))
""" % (str(ROOT), str(sample))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    loaded = set(json.loads(out.stdout.strip().splitlines()[-1]))
    assert loaded <= ALLOWED_COMPILED, loaded - ALLOWED_COMPILED
    assert {"_duckdb", "python_calamine", "PySide6"} <= loaded


@spec("T2", "T3")
def test_runtime_dependencies_are_exactly_the_allowed_set():
    """requirements-lock.txt pins only the runtime packages; the V1 extras are gone."""
    lines = [ln.split("#")[0].strip() for ln in (ROOT / "requirements-lock.txt").read_text().splitlines()]
    lines = [ln for ln in lines if ln]
    pins = dict(ln.lower().split("==") for ln in lines)
    assert set(pins) == {"pyside6-essentials", "shiboken6", "duckdb", "python-calamine"}
    assert pins["duckdb"].startswith("2.0.")


@spec("V3-1")
def test_sql_only_in_query_and_db():
    """All SQL lives in sankalan/query/ (plus schema DDL and connection set-up in sankalan/db/). Jobs and screens
    call those modules; nothing else executes SQL."""
    pat = re.compile(r"\.(?:execute|executemany|sql|query)\(")
    allowed = {"query", "db"}
    found = [p.relative_to(ROOT).as_posix() for p in _sources()
             if p.relative_to(PKG).parts[0] not in allowed and pat.search(p.read_text(encoding="utf-8"))]
    assert found == []


@spec("SEC-1")
def test_no_duckdb_cursor_bypasses_the_job_interface():
    """Only db/ opens DuckDB connections."""
    found = [p.relative_to(ROOT).as_posix() for p in _sources()
             if "duckdb.connect(" in p.read_text(encoding="utf-8") and p.relative_to(PKG).parts[0] != "db"]
    assert found == []
