"""Build and measure the lab/pyperf programs with AIL against CPython 3.12.

For every program in bench/: build it with the default command in a scratch
directory (AIL_NO_CACHE=1, address space capped at 1.5 GB), classify the build
as typed, general or refused, run it beside `python3` at the default size and
compare stdout and exit status, and take the median of three wall times for
each.  Instruction counts use tools/icount.c when perf_event_open is allowed;
when it is not, the column is left empty and the reason is recorded.

    python3 lab/pyperf/run.py                # build, compare and time
    python3 lab/pyperf/run.py --small        # small sizes only, no timing
    python3 lab/pyperf/run.py --unified      # also build with AIL_UNIFIED_FORCE=1
    python3 lab/pyperf/run.py --only nbody   # one program

The JSON result and the markdown table are written beside this file unless
--out names another directory.
"""
import argparse
import json
import math
import os
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BENCH = HERE / "bench"
CLI = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
ICOUNT_C = ROOT / "tools" / "icount.c"

SMALL = {
    "nbody": 200,
    "fannkuch": 8,
    "spectral_norm": 60,
    "nqueens": 7,
    "float_bench": 20000,
    "richards": 2000,
    "raytrace": 16,
    "generators": 50000,
    "scimark_sor": 40,
    "scimark_fft": 256,
}

MEMORY = 1500000 * 1024
BUILD_TIMEOUT = 300
RUN_TIMEOUT = 300


def cpu_name():
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except OSError:
        return ""


def build_icount(work):
    cc = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
    if not cc:
        return None, "no C compiler"
    exe = work / "icount"
    made = subprocess.run([cc, "-O2", "-w", "-include", "signal.h", "-include", "stdlib.h",
                           "-o", str(exe), str(ICOUNT_C)],
                          capture_output=True, text=True, timeout=120)
    if made.returncode != 0:
        return None, "icount build failed: " + made.stderr.strip()[:200]
    probe = subprocess.run([str(exe), "/bin/true"], capture_output=True, text=True, timeout=60)
    if probe.returncode != 0:
        return None, "perf_event_open denied: " + probe.stderr.strip()[:200]
    return exe, ""


def limit_memory():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))


def clean_env(extra=None):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["AIL_NO_CACHE"] = "1"
    if extra:
        env.update(extra)
    return env


def build(source, work, name, unified=False):
    program = work / source.name
    shutil.copyfile(source, program)
    out = work / (name + ".out")
    if out.exists():
        out.unlink()
    env = clean_env({"AIL_UNIFIED_FORCE": "1"} if unified else None)
    try:
        proc = subprocess.run([sys.executable, "-B", str(CLI), "compile", program.name,
                               "-o", out.name],
                              cwd=str(work), env=env, capture_output=True, text=True,
                              timeout=BUILD_TIMEOUT, preexec_fn=limit_memory)
    except subprocess.TimeoutExpired:
        return {"path": "refused", "note": "build timed out after %d s" % BUILD_TIMEOUT,
                "exe": None}
    text = (proc.stderr or "") + (proc.stdout or "")
    if proc.returncode != 0:
        first = ""
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("{"):
                first = line
                break
        return {"path": "refused", "note": first or "build failed", "exe": None}
    note = ""
    kind = "typed"
    for line in text.splitlines():
        if "built on the general path" in line:
            kind = "general"
            note = line.strip()
            break
    return {"path": kind, "note": note, "exe": str(out)}


def run(exe, args, timeout=RUN_TIMEOUT, cwd=None, env=None):
    started = time.perf_counter()
    try:
        proc = subprocess.run([str(exe)] + [str(a) for a in args], cwd=cwd,
                              capture_output=True, text=True, timeout=timeout,
                              env=env if env is not None else clean_env(),
                              preexec_fn=limit_memory)
        return {"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode,
                "wall": time.perf_counter() - started, "timeout": False}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout after %d s" % timeout, "returncode": -1,
                "wall": time.perf_counter() - started, "timeout": True}


def python_run(source, args):
    env = clean_env()
    env.pop("AIL_NO_CACHE", None)
    started = time.perf_counter()
    proc = subprocess.run([sys.executable, "-B", source.name] + [str(a) for a in args],
                          cwd=str(source.parent), capture_output=True, text=True,
                          timeout=RUN_TIMEOUT, env=env)
    return {"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode,
            "wall": time.perf_counter() - started}


def measure(exe, args, rounds, work):
    walls = []
    last = None
    for _ in range(rounds):
        last = run(exe, args, cwd=str(work))
        walls.append(last["wall"])
        if last["timeout"]:
            break
    return last, walls


def icount_run(icount, exe, args, cwd):
    if icount is None:
        return None
    proc = subprocess.run([str(icount), str(exe)] + [str(a) for a in args], cwd=cwd,
                          capture_output=True, text=True, timeout=RUN_TIMEOUT,
                          env=clean_env())
    if proc.returncode != 0:
        return None
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return None


def one(source, icount, small, unified, scratch):
    name = source.stem
    work = scratch / name
    work.mkdir()
    info = {"program": name, "default_size": None, "small_size": SMALL[name]}
    built = build(source, work, name)
    info.update({"path": built["path"], "note": built["note"]})
    if unified:
        uni = build(source, work, name + "_uni", unified=True)
        info["unified_path"] = uni["path"]
        info["unified_note"] = uni["note"]
    args = [SMALL[name]] if small else []
    expected = python_run(source, args)
    info["matches"] = False
    if built["exe"]:
        actual, walls = measure(built["exe"], args, 1 if small else 3, work)
        info["exit_cpython"] = expected["returncode"]
        info["exit_ail"] = actual["returncode"]
        info["stdout_equal"] = actual["stdout"] == expected["stdout"]
        info["matches"] = (actual["returncode"] == expected["returncode"]
                           and actual["stdout"] == expected["stdout"])
        if not info["matches"]:
            info["cpython_stdout"] = expected["stdout"][:400]
            info["ail_stdout"] = actual["stdout"][:400]
        if unified and uni.get("exe"):
            uni_actual, _ = measure(uni["exe"], args, 1, work)
            info["unified_matches"] = (uni_actual["returncode"] == expected["returncode"]
                                       and uni_actual["stdout"] == expected["stdout"])
            if not info["unified_matches"]:
                info["unified_stdout"] = uni_actual["stdout"][:400]
        if not small:
            info["wall_cpython"] = [round(expected["wall"], 3)]
            info["wall_ail"] = [round(w, 3) for w in walls]
            info["wall_cpython_median"] = round(expected["wall"], 3)
            info["wall_ail_median"] = round(statistics.median(walls), 3)
            info["instructions_cpython"] = icount_run(icount, sys.executable,
                                                      ["-B", source.name] + [str(a) for a in args],
                                                      source.parent)
            info["instructions_ail"] = icount_run(icount, built["exe"], args, work)
            if info["instructions_cpython"] and info["instructions_ail"]:
                info["ratio"] = round(info["instructions_cpython"]
                                      / info["instructions_ail"], 3)
    return info


def geomean(values):
    values = [v for v in values if v]
    if not values:
        return None
    total = 0.0
    for v in values:
        total += math.log(v)
    return round(math.exp(total / len(values)), 3)


def markdown(result):
    lines = ["| program | path | matches | CPython instructions | AIL instructions | ratio | CPython wall (s) | AIL wall (s) |",
             "|---|---|---|---|---|---|---|---|"]
    for p in result["programs"]:
        def cell(key):
            value = p.get(key)
            return "n/a" if value is None else str(value)
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            p["program"], p["path"], "yes" if p.get("matches") else "no",
            cell("instructions_cpython"), cell("instructions_ail"), cell("ratio"),
            cell("wall_cpython_median"), cell("wall_ail_median")))
    gi = geomean([p.get("ratio") for p in result["programs"]])
    gw = geomean([p["wall_cpython_median"] / p["wall_ail_median"]
                  for p in result["programs"]
                  if p.get("wall_ail_median") and p.get("wall_cpython_median")])
    lines.append("")
    lines.append("Geomean instruction ratio CPython/AIL: %s" % ("n/a" if gi is None else gi))
    lines.append("Geomean wall ratio CPython/AIL: %s" % ("n/a" if gw is None else gw))
    lines.append("")
    lines.append("Programs matching CPython at the default size: %d of %d" % (
        sum(1 for p in result["programs"] if p.get("matches")), len(result["programs"])))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--small", action="store_true", help="small sizes only, skip timing")
    ap.add_argument("--unified", action="store_true",
                    help="also build with AIL_UNIFIED_FORCE=1 and compare stdout")
    ap.add_argument("--only", action="append", default=None, help="program name (repeatable)")
    ap.add_argument("--out", default=str(HERE), help="directory for results.json and results.md")
    args = ap.parse_args()

    sources = sorted(BENCH.glob("*.py"))
    if args.only:
        wanted = set(args.only)
        sources = [s for s in sources if s.stem in wanted]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="ail-pyperf-"))
    result = {"date": time.strftime("%Y-%m-%d"), "commit": commit(), "cpu": cpu_name(),
              "small": args.small, "programs": []}
    try:
        icount, why = build_icount(scratch)
        result["icount"] = {"available": icount is not None, "note": why}
        for source in sources:
            print("[pyperf] %s" % source.stem, flush=True)
            result["programs"].append(one(source, icount, args.small, args.unified, scratch))
            print("[pyperf]   %s %s" % (result["programs"][-1]["path"],
                                       "match" if result["programs"][-1]["matches"] else "diff"),
                  flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    (out_dir / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    table = markdown(result)
    (out_dir / "results.md").write_text(table + "\n")
    print()
    print(table)


if __name__ == "__main__":
    main()
