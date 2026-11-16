"""Offline/security (SEC-*) and non-functional (NF-3, NF-6) tests."""
import ast
import hashlib
import os
import socket
import tempfile
import time
from pathlib import Path

import pytest

from conftest import spec
from sankalan.core.session import Session, setup_logging
from sankalan.demo import make_perf_set, make_sales_set, sales_template

PKG = Path(__file__).resolve().parents[1] / "sankalan"
NETWORK_MODULES = {"socket", "urllib", "urllib3", "http", "requests", "httpx", "ftplib", "smtplib", "poplib",
                   "imaplib", "xmlrpc", "webbrowser", "telnetlib", "ssl", "asyncio", "aiohttp"}


def full_run(sales, out_dir, fixed=True):
    if fixed:
        make_sales_set(sales["folder"], rows_per_file=300, fixed=True)
    t = sales_template()
    t.column("Invoice Value")["aliases"].append("Inv Amt")
    t.output["folder"] = str(out_dir)
    s = Session(t)
    s.add([sales["folder"]])
    s.load()
    s.validate()
    return s, s.write(override_errors=True)


@spec("SEC-1", "SEC-5")
def test_no_network_code_in_the_app():
    """No module of the app imports networking, update, telemetry or LLM libraries; no Qt network module."""
    found = []
    for p in PKG.rglob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for n in names:
                if n.split(".")[0] in NETWORK_MODULES or "QtNetwork" in n or "QtWebEngine" in n:
                    found.append((p.name, n))
    assert found == []
    text = " ".join(p.read_text(encoding="utf-8").lower() for p in PKG.rglob("*.py"))
    for word in ("openai", "anthropic", "telemetry", "analytics", "https://", "auto-update"):
        assert word not in text, word
    import re
    urls = set(re.findall(r"http://[^\s\"']+", text))
    assert all(u.startswith(("http://schemas.openxmlformats.org/", "http://purl.oclc.org/ooxml/"))
               for u in urls), urls                       # XML namespace names only, never fetched


@spec("SEC-1", "SEC-6")
def test_full_run_with_network_blocked(sales, out_dir, monkeypatch, qtbot):
    """Like a Windows Firewall outbound block: any socket use fails, and the run still works unchanged."""
    def blocked(*a, **k):
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    s, res = full_run(sales, out_dir)
    assert res.path.exists() and res.totals_match
    from sankalan.ui.app import MainWindow
    w = MainWindow(store_folder=out_dir / "tpl")
    qtbot.addWidget(w)
    w.show()


@spec("SEC-2")
def test_source_files_never_changed(sales, out_dir):
    """Source files keep the same bytes and modified time after a full run."""
    make_sales_set(sales["folder"], rows_per_file=300, fixed=True)
    before = {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
              for p in sales["folder"].iterdir()}
    full_run(sales, out_dir, fixed=False)
    after = {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
             for p in sales["folder"].iterdir()}
    assert before == after


@spec("SEC-3")
def test_no_temp_files_left(sales, out_dir):
    """Temporary files live in the temp folder and are removed, also when writing fails."""
    tmp = Path(tempfile.gettempdir())
    before = set(tmp.glob("sankalan_*"))
    s, res = full_run(sales, out_dir)
    from sankalan.core.output import OutputExists
    with pytest.raises(OutputExists):
        s.write(override_errors=True)
    from sankalan.core.readers import Cancelled
    with pytest.raises(Cancelled):            # cancelled half-way: temp file removed, old output kept
        s.write(override_errors=True, overwrite=True, cancel=lambda: True)
    assert set(tmp.glob("sankalan_*")) == before
    assert sorted(p.name for p in out_dir.iterdir()) == [res.path.name]


@spec("SEC-4")
def test_log_has_no_cell_values(sales, out_dir, tmp_path):
    """The technical log records file names and counts, never cell values."""
    log = setup_logging(tmp_path / "logs")
    s, res = full_run(sales, out_dir, fixed=False)
    text = log.read_text(encoding="utf-8")
    assert "validated" in text and "wrote" in text
    fd = s.sources[0]
    for v in fd.rows[0]:
        sv = str(v)
        if len(sv) > 3:
            assert sv not in text, sv
    assert "INV/26-27" not in text and "Traders" not in text.replace("Acme-Traders", "")


@spec("NF-3")
def test_performance_500k_rows(tmp_path):
    """50 files, 500,000 rows: read, map, validate, write .xlsx and check totals in under 60 seconds."""
    exp = make_perf_set(tmp_path / "perf", files=50, rows=10_000)
    t = sales_template()
    t.input["pattern"] = "Perf_*.xlsx"
    t.output["folder"] = str(tmp_path / "out")
    t0 = time.time()
    s = Session(t)
    s.add([tmp_path / "perf"])
    s.load()
    v = s.validate()
    res = s.write(override_errors=True)
    secs = time.time() - t0
    print(f"\nNF-3: {exp['rows']:,} rows in {secs:.1f} s")
    (Path(__file__).parent / "_artifacts").mkdir(exist_ok=True)
    (Path(__file__).parent / "_artifacts" / "perf.txt").write_text(f"{exp['rows']} rows in {secs:.1f} s\n")
    assert res.rows_written == exp["rows"] == 500_000
    assert round([x for x in res.totals if x.column == "Taxable Value"][0].output_total, 2) == exp["taxable"]
    assert res.totals_match
    assert secs < 60


@spec("NF-6")
def test_error_messages_name_file_sheet_row(sales, out_dir):
    """Every problem names the file, sheet and row in plain language."""
    t = sales_template()
    t.column("Invoice Value")["aliases"].append("Inv Amt")
    s = Session(t)
    s.add([sales["folder"]])
    s.load()
    v = s.validate()
    fmt = next(i for i in v.errors if i.rule == "gstin_format")
    assert fmt.location() == "Sales_Aug-2026.xlsx, Sales, row 301"
    assert fmt.message == "GSTIN has 14 characters; a GSTIN has 15"
    for i in v.issues:
        assert i.file and i.sheet and i.row > 0 and i.message[0].isupper()


@spec("SEC-7")
def test_only_allowed_compiled_addons_load(tmp_path):
    """Smart App Control can block unsigned compiled add-ons. A full run and the window load only
    PySide6/shiboken6 (Qt) and cryptography/cffi (password-protected files); everything else is
    pure Python or part of the signed Python runtime."""
    import subprocess, sys, json
    code = (
        "import sys, json, os; sys.path.insert(0, %r)\n"
        "from sankalan.demo import make_sales_set, make_misc_set, sales_template\n"
        "from sankalan.core.session import Session\n"
        "from pathlib import Path\n"
        "d = Path(%r); make_sales_set(d / 's', rows_per_file=40); m = make_misc_set(d / 'm')\n"
        "t = sales_template(); t.column('Invoice Value')['aliases'].append('Inv Amt'); t.output['folder'] = str(d / 'o')\n"
        "s = Session(t); s.add([d / 's', m['password'], m['xls']]); s.load(); s.set_password(m['password'], 'acme@123')\n"
        "s.validate(); s.write(override_errors=True)\n"
        "from PySide6.QtWidgets import QApplication; from sankalan.ui.app import MainWindow\n"
        "app = QApplication([]); w = MainWindow(store_folder=str(d / 't')); w.show(); app.processEvents()\n"
        "mods = sorted({n.split('.')[0] for n, mo in list(sys.modules.items())\n"
        "               if (getattr(mo, '__file__', '') or '').endswith(('.pyd', '.so'))\n"
        "               and 'site-packages' in (getattr(mo, '__file__', '') or '')})\n"
        "print(json.dumps(mods))\n"
    ) % (str(PKG.parent), str(tmp_path))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    loaded = set(json.loads(out.stdout.strip().splitlines()[-1]))
    assert loaded <= {"PySide6", "shiboken6", "cryptography", "_cffi_backend", "cffi"}, loaded
