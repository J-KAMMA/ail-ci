"""Build, compare and time the examples/algos programs against CPython.

For every program this builds three ways: the default command, `--strict` (which
either takes the typed path or refuses and lists the first blocker) and with
AIL_UNIFIED_FORCE=1.  Stdout and exit status are compared with `python3`, the
binary size is recorded, and the default binary and CPython are timed with the
median of three runs under `ulimit -v 1500000`.  Instruction counts use
tools/icount.c when perf_event_open is allowed.  RESULTS.md is written beside this file.

    python3 examples/algos/run.py
    python3 examples/algos/run.py --small     # one short run per program, no timing
"""
import argparse
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
CLI = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
ICOUNT_C = ROOT / "tools" / "icount.c"
MEMORY = 1500000 * 1024
BUILD_TIMEOUT = 600
RUN_TIMEOUT = 300


def limit_memory():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))


def clean_env(extra=None):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["AIL_NO_CACHE"] = "1"
    if extra:
        env.update(extra)
    return env


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


def first_strict_blocker(text):
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line[:1].isdigit() and ". " in line[:5]:
            start = index
            break
    if start is None:
        for line in lines:
            if line.strip().startswith("why not typed:"):
                return line.strip()
        for line in lines:
            if line.strip() and not line.startswith("{"):
                return line.strip()
        return "refused"
    for line in lines[start:]:
        if line.strip().startswith("why not typed:"):
            return line.strip()[len("why not typed:"):].strip()
    return lines[start].strip()


def first_fallback(text):
    for line in text.splitlines():
        if "built on the general path" in line:
            return line.strip()
    return ""


def build(source, work, name, flags=(), extra_env=None):
    program = work / source.name
    if not program.exists():
        shutil.copyfile(source, program)
    out = work / (name + ".out")
    if out.exists():
        out.unlink()
    try:
        proc = subprocess.run([sys.executable, "-B", str(CLI), "compile", program.name,
                               "-o", out.name, "--syntax", "python"] + list(flags),
                              cwd=str(work), env=clean_env(extra_env), capture_output=True,
                              text=True, timeout=BUILD_TIMEOUT, preexec_fn=limit_memory)
    except subprocess.TimeoutExpired:
        return {"kind": "refused", "note": "build timed out after %d s" % BUILD_TIMEOUT,
                "fallback": "", "exe": None}
    text = (proc.stderr or "") + (proc.stdout or "")
    fallback = first_fallback(text)
    if proc.returncode != 0:
        note = first_strict_blocker(text) if "--strict" in flags else ""
        if not note:
            for line in text.splitlines():
                if line.strip() and not line.startswith("{"):
                    note = line.strip()
                    break
        return {"kind": "refused", "note": note or "build failed", "fallback": fallback,
                "exe": None}
    if "--strict" in flags:
        return {"kind": "typed", "note": "typed", "fallback": "", "exe": str(out)}
    kind = "general" if fallback else "typed"
    return {"kind": kind, "note": "typed" if kind == "typed" else fallback,
            "fallback": fallback, "exe": str(out)}


def run(exe, args, cwd, env=None):
    started = time.perf_counter()
    try:
        proc = subprocess.run([str(exe)] + [str(a) for a in args], cwd=str(cwd),
                              capture_output=True, text=True, timeout=RUN_TIMEOUT,
                              env=env if env is not None else clean_env(),
                              preexec_fn=limit_memory)
        return {"stdout": proc.stdout, "stderr": proc.stderr,
                "returncode": proc.returncode, "wall": time.perf_counter() - started}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout after %d s" % RUN_TIMEOUT,
                "returncode": -1, "wall": time.perf_counter() - started}


def python_run(source, args):
    env = clean_env()
    env.pop("AIL_NO_CACHE", None)
    return run(sys.executable, ["-B", source.name] + list(args), source.parent, env)


def measure(exe, args, cwd, rounds):
    walls = []
    last = None
    for _ in range(rounds):
        last = run(exe, args, cwd)
        walls.append(last["wall"])
    return last, walls


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


def icount_run(icount, command, cwd):
    if icount is None:
        return None
    proc = subprocess.run([str(icount)] + [str(part) for part in command], cwd=str(cwd),
                          capture_output=True, text=True, timeout=RUN_TIMEOUT, env=clean_env())
    if proc.returncode != 0:
        return None
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return None


def geomean(values):
    values = [value for value in values if value]
    if not values:
        return None
    total = sum(math.log(value) for value in values)
    return math.exp(total / len(values))


def one(source, icount, small, scratch):
    name = source.stem
    work = scratch / name
    work.mkdir()
    info = {"program": name}
    default = build(source, work, name)
    strict = build(source, work, name + "-strict", ("--strict",))
    forced = build(source, work, name + "-forced", (), {"AIL_UNIFIED_FORCE": "1"})
    info["default"] = default["kind"]
    info["strict"] = strict["kind"]
    info["forced"] = forced["kind"]
    info["fallback"] = default["fallback"]
    info["first_refusal"] = strict["note"] if strict["kind"] == "refused" else ""
    info["binary_bytes"] = (os.path.getsize(default["exe"]) if default["exe"] else None)

    args = ["--small"] if small else []
    expected = python_run(source, args)
    info["matches"] = False
    info["forced_matches"] = False
    info["matches_strict"] = False
    if default["exe"]:
        actual, _ = measure(default["exe"], args, work, 1 if small else 3)
        info["exit_python"] = expected["returncode"]
        info["exit_ail"] = actual["returncode"]
        info["stdout_equal"] = actual["stdout"] == expected["stdout"]
        info["matches"] = (actual["returncode"] == expected["returncode"]
                           and actual["stdout"] == expected["stdout"])
        if not info["matches"]:
            info["python_stdout"] = expected["stdout"][:400]
            info["ail_stdout"] = actual["stdout"][:400]
            info["ail_stderr"] = actual["stderr"][:400]
    if forced["exe"]:
        forced_actual, _ = measure(forced["exe"], args, work, 1)
        info["forced_matches"] = (forced_actual["returncode"] == expected["returncode"]
                                  and forced_actual["stdout"] == expected["stdout"])
    if strict["exe"]:
        strict_actual, _ = measure(strict["exe"], args, work, 1)
        info["matches_strict"] = (strict_actual["returncode"] == expected["returncode"]
                                  and strict_actual["stdout"] == expected["stdout"])

    if default["exe"] and not small:
        _, ail_walls = measure(default["exe"], args, work, 3)
        _, python_walls = measure(sys.executable, ["-B", source.name] + args,
                                  source.parent, 3)
        info["wall_ail_median"] = statistics.median(ail_walls)
        info["wall_python_median"] = statistics.median(python_walls)
        info["speedup"] = (info["wall_python_median"] / info["wall_ail_median"]
                           if info["wall_ail_median"] else None)
        info["instructions_ail"] = icount_run(icount, [default["exe"]] + args, work)
        info["instructions_python"] = icount_run(
            icount, [sys.executable, "-B", source.name] + args, source.parent)
    return info


def markdown(result):
    lines = [
        "# `examples/algos`: plain Python algorithms against CPython",
        "",
        "Built from commit `%s` on %s.  `python3` is the oracle; stdout and exit status must"
        " agree." % (result["commit"], result["cpu"]),
        "",
        "| program | default | strict | match default | match forced | AIL ms | CPython ms |"
        " speed-up | bytes | first refusal / fallback |",
        "|---|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for program in result["programs"]:
        note = program.get("first_refusal") or program.get("fallback") or ""
        note = note.replace("|", "\\|")
        if len(note) > 150:
            note = note[:147] + "..."
        speedup = program.get("speedup")
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            program["program"], program["default"], program["strict"],
            "yes" if program["matches"] else "no",
            "yes" if program["forced_matches"] else "no",
            "%.0f" % (program["wall_ail_median"] * 1000)
            if program.get("wall_ail_median") else "n/a",
            "%.0f" % (program["wall_python_median"] * 1000)
            if program.get("wall_python_median") else "n/a",
            "%.2fx" % speedup if speedup else "n/a",
            program["binary_bytes"] or "n/a", note))
    matching = [p for p in result["programs"] if p["matches"]]
    forced_matching = [p for p in result["programs"] if p["forced_matches"]]
    typed = [p for p in result["programs"] if p["default"] == "typed"]
    general = [p for p in result["programs"] if p["default"] == "general"]
    refused = [p for p in result["programs"] if p["default"] == "refused"]
    speedups = [p.get("speedup") for p in result["programs"] if p.get("speedup")]
    geo = geomean(speedups)
    lines += [
        "",
        "Totals: **%d/12 build and match** in the default build, **%d/12** with"
        " `AIL_UNIFIED_FORCE=1`; **%d typed**, %d general, %d refused."
        % (len(matching), len(forced_matching), len(typed), len(general), len(refused)),
        "",
        "Geomean speed-up over CPython (default build): **%s**."
        % ("n/a" if geo is None else "%.2fx" % geo),
        "",
        "`icount`: %s." % ("available" if result["icount"]["available"]
                           else result["icount"]["note"]),
        "",
        "## Fallback notes",
        "",
    ]
    for program in result["programs"]:
        if program.get("fallback"):
            lines.append("* **%s**: %s" % (program["program"], program["fallback"]))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--small", action="store_true",
                        help="one short run per program, no timing")
    parser.add_argument("--only", action="append", default=None,
                        help="program name (repeatable)")
    parser.add_argument("--out", default=str(HERE), help="directory for RESULTS.md")
    args = parser.parse_args()

    sources = sorted(HERE.glob("*.py"))
    sources = [source for source in sources if source.name != "run.py"]
    if args.only:
        wanted = set(args.only)
        sources = [source for source in sources if source.stem in wanted]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="ail-algos-"))
    result = {"date": time.strftime("%Y-%m-%d"), "commit": commit(), "cpu": cpu_name(),
              "small": args.small, "programs": []}
    try:
        icount, why = build_icount(scratch)
        result["icount"] = {"available": icount is not None, "note": why}
        for source in sources:
            print("[algos] %s" % source.stem, flush=True)
            info = one(source, icount, args.small, scratch)
            result["programs"].append(info)
            print("[algos]   %s %s" % (info["default"],
                                       "match" if info["matches"] else "diff"), flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    table = markdown(result)
    old = out_dir / "RESULTS.md"
    preserved = ""
    if old.exists():
        text = old.read_text(encoding="utf-8")
        marker = "\n## Ranked blockers"
        if marker in text:
            preserved = text[text.index(marker):]
    (out_dir / "RESULTS.md").write_text(table + preserved)
    print()
    print(table)


if __name__ == "__main__":
    main()
