"""Build the run-from-source package: Sankalan-<version>-Windows.zip. DEVELOPMENT AND TEST FALLBACK ONLY until the
signed installer is in use (decision confirmed 17-11-2026, T3); used meanwhile for manual testing on a PC with Smart
App Control off. Smart App Control blocks the unsigned duckdb and python-calamine files, so it can't run on customer
laptops with SAC on.

    python packaging/make_source_package.py --out dist --download     # fetch Windows packages (needs internet)
    python packaging/make_source_package.py --out dist --wheels path  # use already downloaded packages
    python packaging/make_source_package.py --out dist --no-wheels    # installer downloads packages itself

The zip holds: Install/Uninstall Sankalan.bat, README.txt, app\\ (Sankalan.pyw + the sankalan package),
wheels\\ (Windows packages for Python 3.13, so the PC needs no internet) and demo-data\\ (the self-test's sample
.xlsx and .csv).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "packaging" / "source_install"
sys.path.insert(0, str(ROOT / "packaging"))
from version import version  # noqa: E402

VERSION = version()


def crlf(src: Path, dst: Path):
    """Windows batch files must have CRLF line endings, or labels and goto can misbehave."""
    text = src.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\n", "\r\n")
    dst.write_bytes(text.encode("utf-8"))


def download_wheels(dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "download", "-q", "-r", str(ROOT / "requirements-lock.txt"),
                    "-d", str(dest), "--only-binary=:all:", "--platform", "win_amd64", "--python-version", "3.13",
                    "--implementation", "cp", "--abi", "cp313", "--abi", "abi3", "--abi", "none"], check=True)


def build(out: Path, wheels: Path | None = None, download=False, demo=True) -> Path:
    name = f"Sankalan-{VERSION}"
    stage = out / name
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "app").mkdir(parents=True)
    for f in ("Install Sankalan.bat", "Uninstall Sankalan.bat"):
        crlf(SRC / f, stage / f)
    readme = (SRC / "README.txt").read_text(encoding="utf-8").replace("{VERSION}", VERSION)
    (stage / "README.txt").write_bytes(readme.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
    shutil.copy(SRC / "shortcuts.py", stage / "app" / "shortcuts.py")
    shutil.copy(SRC / "Sankalan.pyw", stage / "app" / "Sankalan.pyw")
    shutil.copy(ROOT / "packaging" / "sankalan.ico", stage / "app" / "sankalan.ico")
    shutil.copy(ROOT / "requirements-lock.txt", stage / "app" / "requirements.txt")
    shutil.copytree(ROOT / "sankalan", stage / "app" / "sankalan",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if download:
        download_wheels(stage / "wheels")
    elif wheels:
        shutil.copytree(wheels, stage / "wheels")
    if demo:
        sys.path.insert(0, str(ROOT))
        from sankalan.selftest import write_samples
        write_samples(stage / "demo-data")
    zpath = out / f"{name}-Windows.zip"
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(out))
    return zpath


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"))
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--download", action="store_true")
    g.add_argument("--wheels")
    g.add_argument("--no-wheels", action="store_true")
    ap.add_argument("--no-demo", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    z = build(out, Path(a.wheels) if a.wheels else None, a.download, not a.no_demo)
    print(z)
