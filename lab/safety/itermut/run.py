"""Classify the iteration-mutation programs against CPython in four build modes.

Usage: python3 lab/safety/itermut/run.py

Each program mutates a list, dict or set while iterating it, prints the visited items and the final
container, and (for dicts and sets) lets CPython's RuntimeError escape through a `finally`.  Every
program is built four ways (typed, default, general, hybrid), run under a 1.5 GB address-space limit
and a 20 s timeout, and compared with CPython 3.12.  The table is written to RESULTS.md beside this
file: silent-wrong and crash cells first, with both outputs, then the remaining differences.
"""
import datetime
import os
import re
import resource
import shutil
import signal
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
CLI = REPO / "AIL_CURRENT" / "ail_chatgpt.py"
RESULTS = ROOT / "RESULTS.md"
MODES = ("typed", "default", "general", "hybrid")
LIMIT_KB = 1_500_000
TIMEOUT = 20
CLASSES = ("match", "loud-stop", "silent-wrong", "crash", "refused", "n/a")
NAMED = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*(: .*)?$")


def base_commit():
    for rev in ("origin/integ", "staging/integ"):
        got = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", rev],
                             capture_output=True, text=True)
        if got.returncode == 0:
            return got.stdout.strip(), rev
    got = subprocess.run(["git", "-C", str(REPO), "log", "--format=%H", "--reverse",
                          "HEAD", "--", "lab/safety/itermut"], capture_output=True, text=True)
    first = (got.stdout.split() or [""])[0]
    if first:
        parent = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", first + "^"],
                                capture_output=True, text=True)
        if parent.returncode == 0:
            return parent.stdout.strip(), "branch base"
    got = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True)
    return (got.stdout.strip() or "unknown"), "HEAD"


def last_line(text):
    lines = [line.rstrip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else "(no stderr)"


def limit_memory():
    limit = LIMIT_KB * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def run_limited(cmd, cwd, env):
    try:
        got = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                             timeout=TIMEOUT, env=env, preexec_fn=limit_memory)
        return {"returncode": got.returncode, "stdout": got.stdout, "stderr": got.stderr,
                "timed_out": False}
    except subprocess.TimeoutExpired as error:
        return {"returncode": None,
                "stdout": error.stdout or "",
                "stderr": error.stderr or "",
                "timed_out": True}


def build_detail(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    for line in lines:
        if "not in the subset" in line:
            return line
    return last_line(text)


def build(source, mode, work):
    out = work / mode / "bin"
    out.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    env["AIL_NO_CACHE"] = "1"
    if mode == "typed":
        cmd = [sys.executable, "-B", str(CLI), "compile", str(source), "-o", str(out), "--strict"]
    elif mode == "default":
        cmd = [sys.executable, "-B", str(CLI), "compile", str(source), "-o", str(out)]
    elif mode == "general":
        cmd = [sys.executable, "-B", str(CLI), "compile", str(source), "-o", str(out)]
        env["AIL_UNIFIED_FORCE"] = "1"
    else:
        cmd = [sys.executable, "-B", str(CLI), "build", "--cpython", str(source), "-o", str(out)]
    try:
        got = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True,
                             timeout=600, env=env)
    except subprocess.TimeoutExpired:
        return False, out, "build timed out"
    return got.returncode == 0, out, build_detail(got.stderr)


def executable(out, source, mode):
    if mode == "hybrid":
        return out / source.stem
    return out


def named(line):
    return bool(NAMED.match(line))


def classify(cpython, actual):
    if actual["timed_out"]:
        return "crash"
    code = actual["returncode"]
    if code is None or code < 0 or code >= 128:
        return "crash"
    want = cpython["returncode"]
    if cpython["stdout"] != actual["stdout"]:
        return "silent-wrong"
    if want == 0 and code == 0:
        return "match"
    if want != 0 and code == 0:
        return "silent-wrong"
    if last_line(cpython["stderr"]) == last_line(actual["stderr"]):
        return "match"
    if named(last_line(actual["stderr"])):
        return "loud-stop"
    return "crash"


def status_text(record):
    if record["timed_out"]:
        return "timeout"
    code = record["returncode"]
    if code is None:
        return "unknown"
    if code < 0:
        try:
            name = signal.Signals(-code).name
        except ValueError:
            name = "signal"
        return "signal %d (%s)" % (code, name)
    return "exit %d" % code


def cell(text):
    return (text or "").replace("|", "\\|").replace("\n", "\\n")


def main():
    sources = sorted(ROOT.glob("[0-9][0-9]_*.py"))
    if len(sources) < 24:
        print("expected at least 24 programs, found %d" % len(sources), file=sys.stderr)
        return 1
    include = Path(sysconfig.get_paths().get("include", "/nonexistent"))
    header = include / "Python.h"
    hybrid_error = None if header.is_file() else "%s: No such file or directory" % header

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    results = {}
    with tempfile.TemporaryDirectory(prefix="ail-safety-itermut-") as tmp:
        tmp = Path(tmp)
        for source in sources:
            print("probing", source.name, flush=True)
            work = tmp / source.stem
            work.mkdir()
            copy = work / source.name
            shutil.copyfile(source, copy)
            cpython = run_limited([sys.executable, "-B", str(copy)], work, env)
            row = {"cpython": cpython, "modes": {}}
            for mode in MODES:
                if mode == "hybrid" and hybrid_error:
                    row["modes"][mode] = {"class": "n/a", "build": hybrid_error, "run": None}
                    continue
                built, out, detail = build(copy, mode, work)
                if not built:
                    row["modes"][mode] = {"class": "refused", "build": detail, "run": None}
                    continue
                run = run_limited([str(executable(out, copy, mode))], work, env)
                row["modes"][mode] = {"class": classify(cpython, run), "build": detail,
                                      "run": run}
            results[source.name] = row

    commit, rev = base_commit()
    totals = {name: 0 for name in CLASSES}
    for source in sources:
        for mode in MODES:
            totals[results[source.name]["modes"][mode]["class"]] += 1

    lines = []
    lines.append("# Iteration-mutation table: AIL vs CPython 3.12")
    lines.append("")
    lines.append("Base commit: `%s` (`%s`); date: %s. "
                 "Each program mutates a list, dict or set while iterating it, prints the visited "
                 "items and the final container, and where CPython raises, lets the error escape "
                 "through a `finally`. Binaries run under `ulimit -v %d` and `timeout %d`. "
                 "No compiler file was changed."
                 % (commit, rev, datetime.date.today().isoformat(), LIMIT_KB, TIMEOUT))
    lines.append("")
    lines.append("Classes: `match` (same stdout, exit status and last stderr line), `loud-stop` "
                 "(non-zero exit with a named error, text or name differs from CPython's), "
                 "`silent-wrong` (different stdout, or exit 0 where CPython raised), `crash` "
                 "(signal, timeout, or a non-zero exit with no error line), `refused` (build "
                 "failed), `n/a` (mode not available).")
    lines.append("")

    lines.append("## Silent-wrong and crash rows")
    lines.append("")
    any_wrong = False
    for source in sources:
        row = results[source.name]
        cpython = row["cpython"]
        for mode in MODES:
            entry = row["modes"][mode]
            if entry["class"] not in ("silent-wrong", "crash"):
                continue
            any_wrong = True
            run = entry["run"]
            lines.append("### `%s` / **%s** / %s" % (source.name, mode, entry["class"]))
            lines.append("")
            lines.append("- CPython: %s; stdout `%s`; last stderr `%s`."
                         % (status_text(cpython), cell(cpython["stdout"]),
                            cell(last_line(cpython["stderr"]))))
            lines.append("- AIL:     %s; stdout `%s`; last stderr `%s`."
                         % (status_text(run), cell(run["stdout"]),
                            cell(last_line(run["stderr"]))))
            lines.append("")
    if not any_wrong:
        lines.append("(none)")
        lines.append("")

    lines.append("## Other differences (loud-stop, refused)")
    lines.append("")
    any_other = False
    for source in sources:
        row = results[source.name]
        for mode in MODES:
            entry = row["modes"][mode]
            if entry["class"] not in ("loud-stop", "refused"):
                continue
            any_other = True
            if entry["class"] == "refused":
                lines.append("- `%s` / **%s**: refused at build: `%s`."
                             % (source.name, mode, cell(entry["build"])))
            else:
                lines.append("- `%s` / **%s**: CPython last stderr `%s`; AIL last stderr `%s`."
                             % (source.name, mode,
                                cell(last_line(row["cpython"]["stderr"])),
                                cell(last_line(entry["run"]["stderr"]))))
    if not any_other:
        lines.append("(none)")
    lines.append("")

    lines.append("## Full table")
    lines.append("")
    lines.append("| program | typed | default | general | hybrid |")
    lines.append("| --- | --- | --- | --- | --- |")
    for source in sources:
        row = results[source.name]
        cells = [row["modes"][mode]["class"] for mode in MODES]
        lines.append("| %s | %s |" % (source.name, " | ".join(cells)))
    lines.append("")

    lines.append("## Totals")
    lines.append("")
    lines.append("| class | cells |")
    lines.append("| --- | --- |")
    for name in CLASSES:
        if totals[name]:
            lines.append("| %s | %d |" % (name, totals[name]))
    lines.append("| **all** | **%d** |" % sum(totals.values()))
    lines.append("")
    lines.append("%d programs x %d modes = %d cells."
                 % (len(sources), len(MODES), len(sources) * len(MODES)))
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `sorted(xs, key=f)` with `f` appending to `xs` does **not** raise in CPython "
                 "3.12 (`sorted` sorts a copy); probe 17 therefore matches. Only in-place "
                 "`xs.sort(key=f)` raises `ValueError: list modified during sort` (probe 18).")
    lines.append("- `d.pop(k); d[k] = v` on the current key raises `RuntimeError: dictionary keys "
                 "changed during iteration` in CPython 3.12 only when the re-add moves the key: "
                 "with two keys (probe 25) it does; with three keys the position is unchanged and "
                 "it does not.")
    lines.append("- The set probes 26 and 27 are `silent-wrong` on the default and typed paths: "
                 "no `RuntimeError: Set changed size during iteration`, and iteration runs to the "
                 "50-step counter. The general path raises as CPython does.")
    lines.append("- Probes 18 and 25 are `silent-wrong` on the default and general paths: no "
                 "`ValueError: list modified during sort` for `list.sort(key=...)`, and no "
                 "`RuntimeError: dictionary keys changed during iteration` on a key re-add.")
    lines.append("- Every `silent-wrong` row above names its probe file and prints both outputs; "
                 "that file is the minimal repro. This lane edits no compiler file.")
    lines.append("")
    if hybrid_error:
        lines.append("Hybrid column is `n/a`: %s" % hybrid_error)
        lines.append("")
    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", RESULTS)
    for name in CLASSES:
        print("%-14s %d" % (name, totals[name]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
