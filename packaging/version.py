"""The build's version, read from ``sankalan/__init__.py`` (the one place it is set), so Sankalan.exe's version
resource, the installer, its file name and App settings (DEP-06) always agree.

    python packaging/version.py            2.0.0
    python packaging/version.py --numeric  2.0.0.0   (Windows needs four numbers)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def version() -> str:
    text = (ROOT / "sankalan" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE).group(1)


def numeric(v: str | None = None) -> tuple[int, int, int, int]:
    """'2.0.0' → (2, 0, 0, 0); a pre-release such as '2.0.0.dev3' or '2.1.0rc1' keeps its leading numbers."""
    nums = [int(n) for n in re.findall(r"\d+", re.match(r"[\d.]*\d", v or version()).group(0))][:4]
    return tuple(nums + [0] * (4 - len(nums)))


if __name__ == "__main__":
    print(".".join(map(str, numeric())) if "--numeric" in sys.argv else version())
