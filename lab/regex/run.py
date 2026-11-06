"""Build and measure the lab/regex workloads with AIL against CPython 3.12.

For every workload this script generates the two texts if needed, builds the program with
the default AIL command in a scratch directory (address space capped at 1.5 GB), compares
stdout and the exit status with `python3 -B`, takes the median of five wall times and, when
perf_event_open is allowed, an instruction count with tools/icount.c.  The digest is printed
by the workload itself; this script never feeds timing into it.

Rust twins need the `regex` crate.  When no offline copy is in ~/.cargo/registry or a
vendor directory, that half of the experiment is reported as unavailable instead of
fetching anything.

    python3 lab/regex/run.py
    python3 lab/regex/run.py --only w5_logline --rounds 3
    python3 lab/regex/run.py --data /tmp/ffre1-data
"""
import argparse
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
BUILD_TIMEOUT = 300
RUN_TIMEOUT = 300
ROUNDS = 5

WORKLOADS = [
    "w1_literal",
    "w2_alt",
    "w3_digits",
    "w4_ipv4",
    "w5_logline",
    "w6_sub",
    "w7_split",
    "w8_fullmatch",
]

ENGINE = {
    "w1_literal": "DFA for the ASCII literal; Pike VM for the non-ASCII literal",
    "w2_alt": "DFA (ASCII subject, no lookaround)",
    "w3_digits": "DFA (ASCII \\d+)",
    "w4_ipv4": "DFA span, then anchored Pike VM for the four groups",
    "w5_logline": "DFA span, then anchored Pike VM for the five named groups",
    "w6_sub": "DFA span, then anchored Pike VM for the group template",
    "w7_split": "DFA (ASCII, no groups and no lookaround)",
    "w8_fullmatch": "DFA for the ASCII patterns; Pike VM for the non-ASCII café strings",
}


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


def limit_memory():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))


def clean_env(extra=None):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["AIL_NO_CACHE"] = "1"
    if extra:
        env.update(extra)
    return env


def ensure_data(data_dir):
    data = Path(data_dir)
    ascii_path = data / "ascii.txt"
    mixed_path = data / "mixed.txt"
    if ascii_path.is_file() and mixed_path.is_file():
        return data
    sys.path.insert(0, str(HERE))
    import gen_text  # noqa: E402
    info = gen_text.generate(data)
    print("[regex] generated %s (%d bytes, %d lines) and %s (%d bytes, %d lines)" % (
        info["ascii"], info["ascii_bytes"], info["ascii_lines"],
        info["mixed"], info["mixed_bytes"], info["mixed_lines"]))
    return data


def build(source, work, name):
    program = work / source.name
    shutil.copyfile(source, program)
    out = work / (name + ".out")
    if out.exists():
        out.unlink()
    try:
        proc = subprocess.run([sys.executable, "-B", str(CLI), "compile", program.name,
                               "-o", out.name],
                              cwd=str(work), env=clean_env(), capture_output=True, text=True,
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


def run_command(argv, cwd, timeout=RUN_TIMEOUT):
    started = time.perf_counter()
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              env=clean_env(), preexec_fn=limit_memory)
        return {"stdout": proc.stdout, "stderr": proc.stderr,
                "returncode": proc.returncode,
                "wall": time.perf_counter() - started, "timeout": False}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout after %d s" % timeout, "returncode": -1,
                "wall": time.perf_counter() - started, "timeout": True}


def compare(name, expected, actual):
    """Return (matches, digest, note).  w3's 25-digit int() probe stops loudly in AIL."""
    if name == "w3_digits":
        digest_lines = expected["stdout"].splitlines()[:1]
        actual_lines = actual["stdout"].splitlines()[:1]
        digest = "\n".join(digest_lines)
        overflow = (actual["returncode"] != 0
                    and "OverflowError" in (actual["stderr"] or "")
                    and "overflow" in (actual["stderr"] or "").lower())
        if actual["stdout"] == expected["stdout"]:
            return True, digest, "exact, including the 25-digit probe"
        if actual_lines == digest_lines and overflow:
            return True, digest, "digest matches; 25-digit int() stops loudly (OverflowError)"
        return False, digest, "digest or overflow behaviour differs"
    digest = expected["stdout"].strip()
    matches = actual["returncode"] == expected["returncode"] and actual["stdout"] == expected["stdout"]
    return matches, digest, "" if matches else "stdout or exit status differs"


def measure(name, exe, args, work, rounds):
    walls = []
    last = None
    for _ in range(rounds):
        last = run_command([exe] + [str(a) for a in args], work)
        walls.append(last["wall"])
        if last["timeout"]:
            break
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


def rust_offline():
    """Where the regex crate could come from without fetching."""
    candidates = []
    registry = Path.home() / ".cargo" / "registry" / "src"
    if registry.is_dir():
        candidates.extend(str(p) for p in registry.glob("*/regex-*"))
    for vend in (HERE / "rust" / "vendor", ROOT / "vendor"):
        if (vend / "regex").is_dir() or (vend / "regex").is_symlink():
            candidates.append(str(vend / "regex"))
    if candidates:
        return True, "offline regex crate: " + candidates[0]
    return False, ("no regex crate in ~/.cargo/registry/src or a vendor directory; "
                   "fetching is an owner decision, so the Rust column is unavailable")


def markdown(result):
    lines = [
        "# regex: AIL `re` against CPython 3.12 (and Rust `regex`)",
        "",
        "Date: %s  Commit: `%s`  CPU: %s" % (result["date"], result["commit"], result["cpu"]),
        "",
        "Data: `%s` (20 MB log-like ASCII, %d lines) and `%s` (2 MB mixed non-ASCII, "
        "%d lines), generated by `gen_text.py --seed %d`." % (
            result["ascii"], result["ascii_lines"], result["mixed"],
            result["mixed_lines"], result["seed"]),
        "",
        "Every workload prints its digest (counts plus a CRC-32); timing is never printed by "
        "the program.  Wall times are the median of %d runs under `RLIMIT_AS` 1.5 GB."
        % result["rounds"],
        "",
        "Instruction counts: %s" % result["icount_note"],
        "",
        "| workload | digest (AIL = CPython) | AIL wall (s) | CPython wall (s) | Rust wall (s) | "
        "AIL icount | CPython / AIL | engine part |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in result["rows"]:
        lines.append("| `%s` | `%s` | %s | %s | %s | %s | %s | %s |" % (
            row["workload"], row["digest"].replace("|", "\\|"),
            row["ail_wall"], row["cpython_wall"], row["rust_wall"],
            row["icount"], row["ratio"], row["engine"]))
    lines += ["", "## Correctness", ""]
    for row in result["rows"]:
        status = "same digest" if row["matches"] else "DIFFERENT"
        detail = row["note"]
        lines.append("* `%s`: %s, build `%s`%s" % (
            row["workload"], status, row["path"],
            ("; " + detail) if detail else ""))
    lines += ["", "%d/%d workloads give the same digest on AIL and CPython." % (
        sum(1 for r in result["rows"] if r["matches"]), len(result["rows"]))
        if result["all_match"] else "", ""]
    lines += ["## Rust twins", "",
              "* `%s`" % result["rust_note"], ""]
    lines += ["## Slowest workload", ""]
    lines.append(result["slowest"])
    lines += ["", "## Reproduce", "",
              "```",
              "python3 lab/regex/gen_text.py --out /tmp/ffre1-data",
              "python3 lab/regex/run.py --data /tmp/ffre1-data",
              "```", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default="/tmp/ffre1-data", help="directory for ascii.txt/mixed.txt")
    ap.add_argument("--rounds", type=int, default=ROUNDS)
    ap.add_argument("--only", action="append", default=None, help="workload name (repeatable)")
    ap.add_argument("--out", default=str(HERE / "RESULTS.md"))
    args = ap.parse_args()

    data = ensure_data(args.data)
    ascii_path = str(data / "ascii.txt")
    mixed_path = str(data / "mixed.txt")
    ascii_lines = sum(1 for _ in open(data / "ascii.txt", encoding="ascii"))
    mixed_lines = sum(1 for _ in open(data / "mixed.txt", encoding="utf-8"))

    names = list(WORKLOADS)
    if args.only:
        wanted = set(args.only)
        names = [n for n in names if n in wanted]

    scratch = Path(tempfile.mkdtemp(prefix="ail-regex-"))
    try:
        icount, why = build_icount(scratch)
        rust_ok, rust_note = rust_offline()
        rows = []
        for name in names:
            source = HERE / (name + ".py")
            print("[regex] %s" % name, flush=True)
            work = scratch / name
            work.mkdir()
            built = build(source, work, name)
            expected = run_command([sys.executable, "-B", str(source), ascii_path, mixed_path],
                                   HERE)
            row = {"workload": name, "path": built["path"], "note": built["note"],
                   "engine": ENGINE.get(name, ""), "matches": False,
                   "digest": expected["stdout"].splitlines()[0] if expected["stdout"] else "",
                   "icount": "n/a", "rust_wall": "n/a", "ratio": "n/a",
                   "ail_wall": "n/a", "cpython_wall": "n/a"}
            if built["exe"]:
                actual, ail_walls = measure(name, built["exe"], [ascii_path, mixed_path],
                                            work, args.rounds)
                _, py_walls = measure(name, sys.executable,
                                      ["-B", str(source), ascii_path, mixed_path],
                                      HERE, args.rounds)
                matches, digest, note = compare(name, expected, actual)
                row.update({"matches": matches, "digest": digest or row["digest"],
                            "note": note,
                            "ail_wall": round(statistics.median(ail_walls), 3),
                            "cpython_wall": round(statistics.median(py_walls), 3)})
                if row["ail_wall"]:
                    row["ratio"] = round(row["cpython_wall"] / row["ail_wall"], 3)
                count = icount_run(icount, built["exe"], [ascii_path, mixed_path], work)
                if count is not None:
                    row["icount"] = count
            else:
                row["note"] = built["note"] or "build refused"
            rows.append(row)
            print("[regex]   %s %s" % (row["path"], "match" if row["matches"] else "DIFF"),
                  flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    all_match = all(r["matches"] for r in rows)
    slowest = "No workload measured."
    measured = [r for r in rows if isinstance(r["ail_wall"], float)]
    if measured:
        worst = max(measured, key=lambda r: r["ail_wall"])
        slowest = ("`%s` is the slowest AIL workload: %s s wall, %s instructions%s."
                   % (worst["workload"], worst["ail_wall"], worst["icount"],
                      "; Rust is unavailable, so this is the slowest against CPython"
                      if not rust_ok else ""))
    result = {
        "date": time.strftime("%Y-%m-%d"),
        "commit": commit(),
        "cpu": cpu_name(),
        "rounds": args.rounds,
        "ascii": str(data / "ascii.txt"),
        "ascii_lines": ascii_lines,
        "mixed": str(data / "mixed.txt"),
        "mixed_lines": mixed_lines,
        "seed": 20261106,
        "rows": rows,
        "all_match": all_match,
        "icount_note": "available (tools/icount.c)" if icount else "unavailable: " + why,
        "rust_note": rust_note,
        "slowest": slowest,
    }
    text = markdown(result)
    Path(args.out).write_text(text, encoding="utf-8")
    print("[regex] %s: %d/%d workloads match; icount %s"
          % ("ok" if all_match else "DIFF", sum(1 for r in rows if r["matches"]), len(rows),
             "available" if icount else why))
    print(text)


if __name__ == "__main__":
    main()
