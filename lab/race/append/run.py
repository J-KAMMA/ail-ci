#!/usr/bin/env python3
"""D3 append probes: with `par_range` and with the `range` it stands for.

    python3 lab/race/append/run.py [--quick]

Every probe p01..p09 is built twice (par_range, range) and run at AIL_THREADS 1, 2, 4 and 16,
three runs each, with AIL_PAR_SCHED unset and with `guided`. stdout and the exit status must agree
between the two builds; the exception probe (p04) also compares the last stderr line. p10 is the
append variant of lab/race/pmap/par_collatz.py; its 1-thread and 4-thread wall time and peak RSS are
measured (median of three) for the speedup and the memory bound.
"""
import argparse
import os
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CLI = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
MEM = 1500000 * 1024
THREADS = (1, 2, 4, 16)
RUNS = 3
PROBES = ["p%02d_%s" % (i, n) for i, n in (
    (1, "conditional"), (2, "two_appends"), (3, "str"), (4, "exception"),
    (5, "empty"), (6, "more_workers"), (7, "sixteen"), (8, "guided"), (9, "float"))]
# p11 wraps the loop in a `try` that prints `out`: the typed build refuses it by name (a parallel
# loop cannot live in a function with try/except), so the probe asserts the refusal and checks the
# state the join leaves against CPython through the `range` twin.
REFUSED = [("p11_try", "parallel for cannot be inside try")]


def env(extra=None, limit=True):
    e = dict(os.environ)
    for k in ("PYTHONPATH", "AIL_THREADS", "AIL_UNIFIED_FORCE", "AIL_NO_GENERAL", "AIL_STRICT",
              "AIL_UNIFIED", "AIL_IR", "AIL_PAR_SCHED"):
        e.pop(k, None)
    e["AIL_NO_CACHE"] = "1"
    e["AIL_QUIET_FALLBACK"] = "1"
    if extra:
        e.update(extra)
    return e


def run(cmd, e, timeout=600, input=None, limit=True):
    pre = None
    if limit and os.name == "posix":
        def pre():
            resource.setrlimit(resource.RLIMIT_AS, (MEM, MEM))
    return subprocess.run(cmd, env=e, capture_output=True, timeout=timeout, input=input,
                          preexec_fn=pre)


def build(src, out, sequential):
    if sequential:
        text = src.read_text().replace("par_range(", "range(")
        src = out.with_suffix(".seq.py")
        src.write_text(text)
    exe = out.with_suffix(".exe")
    if exe.exists():
        exe.unlink()
    got = run([sys.executable, "-B", str(CLI), "compile", str(src), "--syntax", "python",
               "-o", str(exe)], env())
    return exe if got.returncode == 0 else None, got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    global RUNS
    if args.quick:
        RUNS = 1
    work = Path(tempfile.mkdtemp(prefix="ail-append-"))
    rows, bad = [], []
    try:
        for name in PROBES:
            src = HERE / (name + ".py")
            par, got = build(src, work / name, False)
            seq, got2 = build(src, work / (name + "_seq"), True)
            if par is None or seq is None:
                rows.append((name, "BUILD FAIL", (got.stderr or got2.stderr)[-400:]))
                bad.append(name)
                continue
            ok = True
            detail = []
            for sched in (None, "guided"):
                extra = {"AIL_PAR_SCHED": "guided"} if sched else None
                for t in THREADS:
                    for _ in range(RUNS):
                        a = run([str(par)], env(dict(extra or {}, AIL_THREADS=str(t))))
                        b = run([str(seq)], env(dict(extra or {}, AIL_THREADS=str(t))))
                        same = a.returncode == b.returncode and a.stdout == b.stdout
                        if name.startswith("p04"):
                            same = same and a.stderr.splitlines()[-1:] == b.stderr.splitlines()[-1:]
                        if not same:
                            ok = False
                            detail.append("sched=%s t=%d rc=%d/%d out=%r/%r" % (
                                sched, t, a.returncode, b.returncode,
                                a.stdout[:80], b.stdout[:80]))
                            break
                    if not ok:
                        break
                if not ok:
                    break
            rows.append((name, "match" if ok else "MISMATCH", "; ".join(detail[:2])))
            if not ok:
                bad.append(name)
        for name, needle in REFUSED:
            src = HERE / (name + ".py")
            par, got = build(src, work / name, False)
            seq, got2 = build(src, work / (name + "_seq"), True)
            text = (got.stderr or b"").decode("utf-8", "replace")
            if par is not None or needle not in text or seq is None:
                rows.append((name, "REFUSAL MISSING", text[-300:]))
                bad.append(name)
                continue
            ok, detail = True, []
            for sched in (None, "guided"):
                extra = {"AIL_PAR_SCHED": "guided"} if sched else None
                for t in THREADS:
                    for _ in range(RUNS):
                        b = run([str(seq)], env(dict(extra or {}, AIL_THREADS=str(t))))
                        c = run([sys.executable, str(work / (name + "_seq.seq.py"))], env())
                        if b.returncode != c.returncode or b.stdout != c.stdout:
                            ok = False
                            detail.append("sched=%s t=%d rc=%d/%d out=%r/%r" % (
                                sched, t, b.returncode, c.returncode, b.stdout[:80], c.stdout[:80]))
                            break
                    if not ok:
                        break
                if not ok:
                    break
            rows.append((name, "refused/seq match" if ok else "SEQ MISMATCH", "; ".join(detail[:2])))
            if not ok:
                bad.append(name)
        speed = None
        if not bad:
            speed = measure(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    for name, verdict, detail in rows:
        print("%-20s %-9s %s" % (name, verdict, detail))
    if speed:
        print(speed)
    print("MISMATCH" if bad else "all probes match")
    return 1 if bad else 0


def measure(work):
    src = HERE / "p10_collatz_append.py"
    par, got = build(src, work / "p10_par", False)
    seq, got2 = build(src, work / "p10_seq", True)
    if par is None or seq is None:
        return "p10 BUILD FAIL " + ((got.stderr or got2.stderr)[-300:].decode("utf-8", "replace"))
    n = 4000000
    data = ("%d 4\n" % n).encode()
    out = {}
    for label, exe, threads in (("seq", seq, 1), ("t1", par, 1), ("t4", par, 4)):
        walls, rss = [], []
        for _ in range(3):
            t0 = time.monotonic()
            p = run(["/usr/bin/time", "-v", str(exe)], env({"AIL_THREADS": str(threads)}), input=data)
            walls.append(time.monotonic() - t0)
            line = [x for x in p.stderr.decode("utf-8", "replace").splitlines()
                    if "Maximum resident set size" in x]
            rss.append(int(line[-1].split(":")[-1]) * 1024 if line else 0)
            last_out = p.stdout
        out[label] = (statistics.median(walls), max(rss), last_out)
    speed = out["seq"][0] / out["t4"][0] if out["t4"][0] else 0.0
    rss_ratio = out["t4"][1] / out["seq"][1] if out["seq"][1] else 0.0
    return ("p10 (n=%d): seq %.3fs %.1fMB | t1 %.3fs %.1fMB | t4 %.3fs %.1fMB | "
            "speedup(4 vs seq) %.2fx | t4/seq RSS %.2fx | out=%r" % (
                n, out["seq"][0], out["seq"][1] / 1e6, out["t1"][0], out["t1"][1] / 1e6,
                out["t4"][0], out["t4"][1] / 1e6, speed, rss_ratio, out["t4"][2][:40]))


if __name__ == "__main__":
    sys.exit(main())
