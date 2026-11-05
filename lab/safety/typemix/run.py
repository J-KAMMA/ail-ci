"""Classify the type-mixing programs against CPython in four build modes.

Usage: python3 lab/safety/typemix/run.py

Each program mixes ints, floats, bools, strs and None, prints several values, and sometimes raises.
Every program is built four ways (typed, default, general, hybrid), run under a 1.5 GB address-space
limit and a 20 s timeout, and compared with CPython 3.12.  The table is written to RESULTS.md beside
this file.  This runner only measures; no compiler file is edited.
"""
import datetime
import os
import shutil
import signal
import subprocess
import sys
import sysconfig
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
CLI = REPO / "AIL_CURRENT" / "ail_chatgpt.py"
RESULTS = ROOT / "RESULTS.md"
PYTHON = sys.executable
MODES = ("typed", "default", "general", "hybrid")
LIMIT_KB = 1_500_000
TIMEOUT = 20
BUILD_TIMEOUT = 600
CLASSES = ("match", "loud-stop", "silent-wrong", "crash", "refused", "n/a")


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


def run_limited(cmd, cwd, env):
    wrapped = ["bash", "-c",
               'ulimit -v %d 2>/dev/null; exec timeout %d "$@"' % (LIMIT_KB, TIMEOUT),
               "bash"] + [str(part) for part in cmd]
    started = time.monotonic()
    try:
        got = subprocess.run(wrapped, cwd=str(cwd), stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=TIMEOUT + 15, env=env)
        timed_out = got.returncode == 124 and time.monotonic() - started >= TIMEOUT
        return {"returncode": got.returncode, "stdout": got.stdout, "stderr": got.stderr,
                "timed_out": timed_out}
    except subprocess.TimeoutExpired as error:
        return {"returncode": 124,
                "stdout": (error.stdout or b"").decode("utf-8", "replace"),
                "stderr": (error.stderr or b"").decode("utf-8", "replace"),
                "timed_out": True}


def build(source, mode, work):
    out = work / mode / "bin"
    out.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    env["AIL_NO_CACHE"] = "1"
    if mode == "typed":
        cmd = [PYTHON, "-B", str(CLI), "compile", str(source), "-o", str(out), "--strict"]
    elif mode == "default":
        cmd = [PYTHON, "-B", str(CLI), "compile", str(source), "-o", str(out)]
    elif mode == "general":
        cmd = [PYTHON, "-B", str(CLI), "compile", str(source), "-o", str(out)]
        env["AIL_UNIFIED_FORCE"] = "1"
    else:
        cmd = [PYTHON, "-B", str(CLI), "build", "--cpython", str(source), "-o", str(out)]
    try:
        got = subprocess.run(cmd, cwd=str(work), stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=BUILD_TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        return False, out, "build timed out"
    detail = last_line(got.stderr) if got.returncode != 0 else ""
    return got.returncode == 0, out, detail


def executable(out, source, mode):
    if mode == "hybrid":
        return out / source.stem
    return out


def classify(cpython, actual):
    """match / loud-stop / silent-wrong / crash for one run against CPython."""
    if actual["timed_out"]:
        return "crash"
    code = actual["returncode"]
    if code is not None and (code < 0 or code >= 128):
        return "crash"
    if code != 0 and last_line(actual["stderr"]) == "(no stderr)":
        return "crash"
    want = cpython["returncode"]
    if want == 0 and code == 0:
        if cpython["stdout"] == actual["stdout"] \
                and last_line(cpython["stderr"]) == last_line(actual["stderr"]):
            return "match"
        return "silent-wrong"
    if want != 0 and code != 0:
        if cpython["stdout"] != actual["stdout"]:
            return "silent-wrong"
        if last_line(cpython["stderr"]) == last_line(actual["stderr"]):
            return "match"
        return "loud-stop"
    if want == 0 and code != 0:
        return "loud-stop"
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
    return (text or "").replace("|", "\\|")


def one_line(text):
    return cell((text or "").replace("\n", "\\n"))


def build_command(prog, mode, out):
    rel = prog.relative_to(REPO)
    if mode == "typed":
        return "python3 -B AIL_CURRENT/ail_chatgpt.py compile %s -o %s --strict" % (rel, out)
    if mode == "general":
        return "AIL_UNIFIED_FORCE=1 python3 -B AIL_CURRENT/ail_chatgpt.py compile %s -o %s" \
            % (rel, out)
    if mode == "hybrid":
        return "python3 -B AIL_CURRENT/ail_chatgpt.py build --cpython %s -o %s" % (rel, out)
    return "python3 -B AIL_CURRENT/ail_chatgpt.py compile %s -o %s" % (rel, out)


def repro(prog, mode):
    out = "/tmp/safetype1-%s-%s" % (prog.stem, mode)
    run = "%s/%s" % (out, prog.stem) if mode == "hybrid" else out
    return "`rm -rf %s && %s && (ulimit -v %d; timeout %d %s)`" % (
        out, build_command(prog, mode, out), LIMIT_KB, TIMEOUT, run)


def main():
    sources = sorted(ROOT.glob("t[0-9][0-9]_*.py"))
    if len(sources) < 30:
        print("expected at least 30 programs, found %d" % len(sources), file=sys.stderr)
        return 1
    include = Path(sysconfig.get_paths().get("include", "/nonexistent"))
    header = include / "Python.h"
    hybrid_error = None if header.is_file() else "%s: No such file or directory" % header

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    results = {}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="ail-safety-typemix-") as tmp:
        work = Path(tmp)
        for source in sources:
            print("probing", source.name, flush=True)
            wdir = work / source.stem
            wdir.mkdir()
            copy = wdir / source.name
            shutil.copyfile(source, copy)
            cpython = run_limited([PYTHON, "-B", str(copy)], wdir, env)
            row = {"cpython": cpython, "modes": {}}
            for mode in MODES:
                if mode == "hybrid" and hybrid_error:
                    row["modes"][mode] = {"class": "n/a", "build": hybrid_error, "run": None}
                    continue
                built, out, detail = build(copy, mode, wdir)
                if not built:
                    row["modes"][mode] = {"class": "refused", "build": detail, "run": None}
                    continue
                run = run_limited([str(executable(out, copy, mode))], wdir, env)
                row["modes"][mode] = {"class": classify(cpython, run), "build": detail,
                                      "run": run}
            results[source.name] = row
    elapsed = time.monotonic() - started

    commit, rev = base_commit()
    lines = []
    lines.append("# Type-mixing table: AIL vs CPython 3.12")
    lines.append("")
    lines.append("Base commit: `%s` (`%s`); date: %s. %d probes touching bool/int/float/str/None "
                 "mixing, each run in four build modes. Binaries run under `ulimit -v %d` and "
                 "`timeout %d`; runner wall time %.1fs."
                 % (commit, rev, datetime.date.today().isoformat(), len(sources), LIMIT_KB,
                    TIMEOUT, elapsed))
    lines.append("")
    lines.append("Classes: `match` = same stdout and exit status, and same last stderr line on an "
                 "error; `loud-stop` = AIL exits non-zero with a named error where CPython printed "
                 "a value (e.g. beyond int64) or the same error with another text; `refused` = the "
                 "build fails with a reason; `crash` = signal/timeout or no error line; "
                 "`silent-wrong` = exit 0 or same exit, different stdout.")
    lines.append("")

    totals = {name: 0 for name in CLASSES}
    mode_totals = {mode: 0 for mode in MODES}
    for source in sources:
        for mode in MODES:
            klass = results[source.name]["modes"][mode]["class"]
            totals[klass] += 1
            mode_totals[mode] += 1

    bad = []
    for source in sources:
        row = results[source.name]
        cpython = row["cpython"]
        for mode in MODES:
            entry = row["modes"][mode]
            if entry["class"] not in ("silent-wrong", "crash"):
                continue
            run = entry["run"]
            bad.append((source, mode, entry, cpython, run))

    lines.append("## Silent-wrong and crash first")
    lines.append("")
    if not bad:
        lines.append("(none)")
    else:
        lines.append("| program | mode | class | CPython stdout | AIL stdout | CPython last "
                     "stderr | AIL last stderr | AIL status |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for source, mode, entry, cpython, run in bad:
            lines.append("| %s | %s | %s | `%s` (%s) | `%s` (%s) | `%s` | `%s` | %s |"
                         % (source.name, mode, entry["class"],
                            one_line(cpython["stdout"]), status_text(cpython),
                            one_line(run["stdout"]), status_text(run),
                            cell(last_line(cpython["stderr"])),
                            cell(last_line(run["stderr"])), status_text(run)))
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
    lines.append("| class | typed | default | general | hybrid | all |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for name in CLASSES:
        per_mode = [sum(1 for source in sources
                        if results[source.name]["modes"][mode]["class"] == name)
                    for mode in MODES]
        total = sum(per_mode)
        if total:
            lines.append("| %s | %s | %d |"
                         % (name, " | ".join(str(value) for value in per_mode), total))
    lines.append("| **all** | %s | **%d** |"
                 % (" | ".join(str(mode_totals[mode]) for mode in MODES),
                    sum(mode_totals.values())))
    lines.append("")
    if hybrid_error:
        lines.append("Hybrid column is `n/a`: %s" % hybrid_error)
        lines.append("")

    lines.append("## Follow-ups")
    lines.append("")
    lines.append("Every `loud-stop`, `refused` and `silent-wrong`/`crash` cell follows, with a "
                 "minimal repro. CPython's last stderr line is the oracle.")
    lines.append("")
    any_followup = False
    for source in sources:
        row = results[source.name]
        cpython = row["cpython"]
        for mode in MODES:
            entry = row["modes"][mode]
            klass = entry["class"]
            if klass in ("match", "n/a"):
                continue
            any_followup = True
            if klass == "refused":
                lines.append("- `%s` / **%s**: refused. Build: `%s`. Repro: %s"
                             % (source.name, mode, cell(entry["build"]), repro(source, mode)))
                continue
            run = entry["run"]
            lines.append("- `%s` / **%s**: %s. CPython: `%s` (%s). AIL: `%s` (%s)."
                         % (source.name, mode, klass,
                            cell(last_line(cpython["stderr"])), status_text(cpython),
                            cell(last_line(run["stderr"])), status_text(run)))
            if run["stdout"] != cpython["stdout"]:
                lines.append("  - stdout CPython: `%s`; AIL: `%s`."
                             % (one_line(cpython["stdout"]), one_line(run["stdout"])))
            lines.append("  - repro: %s" % repro(source, mode))
    if not any_followup:
        lines.append("(none)")
    lines.append("")
    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", RESULTS)
    for name in CLASSES:
        if totals[name]:
            print("%-14s %d" % (name, totals[name]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
