"""Phase 0 spike: reader workers as spawned processes, from source and from a PyInstaller exe (T5).

From source:  .venv\\Scripts\\python tools\\spikes\\spike_workers.py
Frozen:       .venv\\Scripts\\python tools\\spikes\\spike_workers.py --build   (builds dist and runs the exe)

Checks: spawn start-up time per worker, calamine inside a worker, cancel = signal then stop after 2 s,
and that the frozen exe re-entering in worker mode does not open a second app (freeze_support).
"""
import multiprocessing as mp
import os
import sys
import tempfile
import time
from pathlib import Path


def read_job(path, out, stop):
    """Worker body: read a sheet with calamine and stage it, checking the stop flag between rows."""
    import csv
    import python_calamine as pc
    sh = pc.CalamineWorkbook.from_path(path).get_sheet_by_name("Sales")
    n = 0
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for row in sh.iter_rows():
            if stop.is_set():
                return ("cancelled", n)
            w.writerow(row)
            n += 1
    return ("done", n)


def slow_job(stop, ignore_stop):
    """A worker that is busy in C code / ignores the flag, to exercise the 2-second kill."""
    t0 = time.time()
    while time.time() - t0 < 60:
        if stop.is_set() and not ignore_stop:
            return "cancelled"
        time.sleep(0.01)
    return "done"


def _run(conn, fn, args):
    try:
        conn.send(fn(*args))
    except Exception as e:     # report the class only (SEC-5)
        conn.send(("failed", type(e).__name__))


def make_sample(path, rows=20_000):
    import xlsxwriter
    wb = xlsxwriter.Workbook(str(path))
    ws = wb.add_worksheet("Sales")
    ws.write_row(0, 0, ["Invoice No", "Taxable Value"])
    for n in range(1, rows + 1):
        ws.write_row(n, 0, [f"INV-{n:05d}", 1000 + (n % 100) * 10.25])
    wb.close()


def main():
    ctx = mp.get_context("spawn")
    frozen = getattr(sys, "frozen", False)
    print(f"frozen={frozen} exe={Path(sys.executable).name} pid={os.getpid()} cores={os.cpu_count()}")
    work = Path(tempfile.mkdtemp(prefix="sankalan_spike_"))
    sample = work / "s.xlsx"
    if len(sys.argv) > 1 and sys.argv[1] == "--sample":
        sample = Path(sys.argv[2])
    else:
        make_sample(sample)

    # 1. spawn start-up + parallel read
    n_workers = max(1, min(4, (os.cpu_count() or 2) - 1))
    stop = ctx.Event()
    t0 = time.perf_counter()
    procs = []
    for i in range(n_workers):
        a, b = ctx.Pipe(duplex=False)
        p = ctx.Process(target=_run, args=(b, read_job, (str(sample), str(work / f"o{i}.csv"), stop)), daemon=True)
        p.start()
        procs.append((p, a))
    results = [a.recv() for p, a in procs]
    for p, _ in procs:
        p.join()
    secs = time.perf_counter() - t0
    print(f"{n_workers} workers spawned, each read 20,000 rows: {results} in {secs:.2f} s total")

    # 2. cancel: cooperative stop, then kill after 2 s
    for ignore in (False, True):
        stop = ctx.Event()
        a, b = ctx.Pipe(duplex=False)
        p = ctx.Process(target=_run, args=(b, slow_job, (stop, ignore)), daemon=True)
        p.start()
        time.sleep(1.0)
        t0 = time.perf_counter()
        stop.set()
        p.join(2.0)
        killed = p.is_alive()
        if killed:
            p.kill()
            p.join()
        print(f"cancel (worker {'ignores' if ignore else 'honours'} flag): stopped in "
              f"{time.perf_counter() - t0:.2f} s, killed={killed}, exitcode={p.exitcode}")
    for f in work.iterdir():
        f.unlink()
    work.rmdir()


def build():
    """Build a one-folder exe of this script with PyInstaller and run it."""
    import subprocess
    here = Path(__file__).resolve()
    out = Path(tempfile.mkdtemp(prefix="sankalan_spike_build_"))
    t0 = time.perf_counter()
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--console",
                    "--name", "spike_workers", "--distpath", str(out / "dist"), "--workpath", str(out / "build"),
                    "--specpath", str(out), "--collect-binaries", "python_calamine", str(here)],
                   check=True, capture_output=True)
    print(f"PyInstaller build {time.perf_counter() - t0:.0f} s")
    exe = out / "dist" / "spike_workers" / "spike_workers.exe"
    sample = out / "s.xlsx"
    make_sample(sample)
    r = subprocess.run([str(exe), "--sample", str(sample)], capture_output=True, text=True, timeout=120)
    print(r.stdout.strip())
    if r.returncode:
        print("exit", r.returncode, r.stderr[-1500:])
    print(f"(build folder {out}; delete when done)")


if __name__ == "__main__":
    mp.freeze_support()
    if "--build" in sys.argv:
        build()
    else:
        main()
