"""Classify the runtime-stop programs against CPython in four build modes.

Usage: python3 lab/safety/stops/run.py

Each program prints some values and then raises one uncaught error.  Every program is built four
ways (typed, default, general, hybrid), run under a 1.5 GB address-space limit and a 20 s timeout,
and compared with CPython.  The table is written to RESULTS.md beside this file.
"""
import datetime
import os
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
CLASSES = ("match", "stop-differs", "silent-wrong", "crash", "refused", "n/a")


def base_commit():
    for rev in ("origin/integ", "HEAD"):
        got = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", rev],
                             capture_output=True, text=True)
        if got.returncode == 0:
            return got.stdout.strip(), rev
    return "unknown", "unknown"


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


def build(source, mode, work):
    out = work / (mode if mode != "hybrid" else "hybrid") / "bin"
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
    detail = last_line(got.stderr)
    return got.returncode == 0, out, detail


def executable(out, source, mode):
    if mode == "hybrid":
        return out / source.stem
    return out


def classify(cpython, actual):
    if actual["timed_out"]:
        return "crash"
    code = actual["returncode"]
    if code is not None and code < 0:
        return "crash"
    if code is not None and code >= 128:
        return "crash"
    want = cpython["returncode"]
    if want == 0 and code == 0 and cpython["stdout"] == actual["stdout"] \
            and last_line(cpython["stderr"]) == last_line(actual["stderr"]):
        return "match"
    if want != 0 and code != 0:
        if cpython["stdout"] != actual["stdout"]:
            return "silent-wrong"
        if last_line(cpython["stderr"]) == last_line(actual["stderr"]):
            return "match"
        return "stop-differs"
    return "silent-wrong"


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
    return text.replace("|", "\\|")


def main():
    sources = sorted(ROOT.glob("[0-9][0-9]_*.py"))
    if len(sources) != 20:
        print("expected 20 programs, found %d" % len(sources), file=sys.stderr)
        return 1
    include = Path(sysconfig.get_paths().get("include", "/nonexistent"))
    header = include / "Python.h"
    hybrid_error = None if header.is_file() else "%s: No such file or directory" % header

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    results = {}
    with tempfile.TemporaryDirectory(prefix="ail-safety-stops-") as tmp:
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
                    row["modes"][mode] = {"class": "n/a", "build": hybrid_error,
                                          "run": None}
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
    lines = []
    lines.append("# Runtime-stop table: AIL vs CPython 3.12")
    lines.append("")
    lines.append("Base commit: `%s` (`%s`); date: %s. "
                 "Each program prints values and then raises one uncaught error. "
                 "Binaries run under `ulimit -v %d` and `timeout %d`."
                 % (commit, rev, datetime.date.today().isoformat(), LIMIT_KB, TIMEOUT))
    lines.append("")
    lines.append("| program | typed | default | general | hybrid |")
    lines.append("| --- | --- | --- | --- | --- |")
    totals = {name: 0 for name in CLASSES}
    for source in sources:
        row = results[source.name]
        cells = []
        for mode in MODES:
            klass = row["modes"][mode]["class"]
            totals[klass] += 1
            cells.append(klass)
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
    if hybrid_error:
        lines.append("Hybrid column is `n/a`: %s" % hybrid_error)
        lines.append("")
    lines.append("## Follow-ups")
    lines.append("")
    lines.append("Every `crash`, `silent-wrong` and `stop-differs` cell follows. "
                 "CPython's last line is the oracle.")
    lines.append("")
    any_followup = False
    for source in sources:
        row = results[source.name]
        cpython = row["cpython"]
        for mode in MODES:
            entry = row["modes"][mode]
            klass = entry["class"]
            if klass not in ("crash", "silent-wrong", "stop-differs"):
                continue
            any_followup = True
            run = entry["run"]
            lines.append("- `%s` / **%s**: %s. CPython: `%s` (%s). AIL: `%s` (%s)."
                         % (source.name, mode,
                            klass,
                            cell(last_line(cpython["stderr"])), status_text(cpython),
                            cell(last_line(run["stderr"])), status_text(run)))
            if run["stdout"] != cpython["stdout"]:
                lines.append("  - stdout CPython: `%s`; AIL: `%s`."
                             % (cell(cpython["stdout"].replace("\n", "\\n")),
                                cell(run["stdout"].replace("\n", "\\n"))))
    if not any_followup:
        lines.append("(none)")
    lines.append("")
    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", RESULTS)
    for name in CLASSES:
        print("%-14s %d" % (name, totals[name]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
