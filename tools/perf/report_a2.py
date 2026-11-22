r"""Write the tables of ``tools/perf/RESULTS-A2.md`` from ``tools/perf/_results/a2_perf.json`` (plan A2-6 step 5).

    python tools\perf\report_a2.py            # prints the Markdown tables; paste them into RESULTS-A2.md

Figures are seconds unless marked ms. A target is Met when the median is at or under it.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "_results"
ORDER = ["PERF-7", "PERF-8", "PERF-9", "PERF-10 untick", "PERF-10 tick", "PERF-10 reorder", "PERF-11", "PERF-12",
         "PERF-13 run data", "PERF-13 rows view", "PERF-14", "PERF-1", "PERF-2", "PERF-3", "PERF-4", "PERF-5",
         "PERF-6"]


def fmt(x: float, target: float) -> str:
    return f"{x * 1000:,.0f} ms" if target < 1 else f"{x:,.1f} s"


def targets_table(res: dict) -> list[str]:
    out = ["| ID | Operation | Median | Min | Max | Target | Result |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for key in ORDER:
        r = res.get(key)
        if r is None:
            out.append(f"| {key} | | | | | | Not measured |")
            continue
        t = r["target_s"]
        out.append(f"| {key} | {r['operation']} | {fmt(r['median_s'], t)} | {fmt(r['min_s'], t)} | "
                   f"{fmt(r['max_s'], t)} | ≤ {fmt(t, t)} | {'Met' if r['met'] else '**Missed**'} |")
    return out


def compare_table() -> list[str]:
    a2p, prep = RESULTS / "load_a2.json", RESULTS / "load_pre_a2.json"
    if not (a2p.is_file() and prep.is_file()):
        return ["(no pre-A2 comparison)"]
    a2, pre = json.loads(a2p.read_text(encoding="utf-8")), json.loads(prep.read_text(encoding="utf-8"))
    out = ["| Measure | Stage | Pre-A2 (25f4d98) median | A2 median | Difference |", "| --- | --- | --- | --- | --- |"]
    for key, name in (("perf1", "PERF-1 load (P01 file 1)"), ("perf2", "PERF-2 load (P02)"),
                      ("probe_sheets", "Probe, sheet files"), ("probe_p02", "Probe, P02")):
        if key not in a2 or key not in pre:
            continue
        for stage in ("load", "probe", "validate", "split", "totals"):
            if stage in a2[key] and stage in pre[key]:
                x, y = pre[key][stage]["median"], a2[key][stage]["median"]
                out.append(f"| {name} | {stage} | {x:,.2f} s | {y:,.2f} s | {y - x:+,.2f} s ({(y - x) / x:+.0%}) |")
    return out


def main() -> int:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads((RESULTS / "a2_perf.json").read_text(encoding="utf-8"))
    print("Machine:", json.dumps(data["machine"]))
    print("Settings:", json.dumps(data["settings"]), "\n")
    print("\n".join(targets_table(data["results"])), "\n")
    print("\n".join(compare_table()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
