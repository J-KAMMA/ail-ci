#!/usr/bin/env python3
"""Re-check open DIFFERENCES.md rows with small probe programs.

Without arguments it prints the rows whose status is ``open``, empty,
``refused`` or starts with ``declared``.  ``--run`` builds every probe in
``lab/diffaudit/*.py`` in the default build and with ``AIL_UNIFIED_FORCE=1``,
runs both and CPython, and prints a verdict for each build.
"""
import argparse
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CLI = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
SOURCES = ("open", "", "refused", "declared")
LIMIT = 1500000 * 1024
TIMEOUT = 120

POSITIVE = {"now-matches", "refused-as-said"}
OVERRIDES = {
    # forced run uses a named runtime limit instead of the 16-bit internal error
    "C__job_pre90_10242040_2": {"forced": "differs-otherwise"},
}
# A single-expression probe is a fused pipeline program: the compiled tool reads int64s
# from a file, so it is run with this input and compared with the Python that catches the
# exception the row is about.
PIPELINE = {
    "C__job_pre138_10250109_2": {
        "input": b"\x01" + b"\x00" * 7 + b"\x00" * 8,
        "oracle": ("try:\n    print(sum(1 % x for x in [1, 0]))\n"
                   "except ZeroDivisionError:\n    print('caught')\n"),
    },
}


def slug(row_id):
    return re.sub(r"[^A-Za-z0-9_]", "_", row_id)


def rows():
    result = []
    for line in (ROOT / "DIFFERENCES.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] == "id" or set(cells[0]) <= set("-"):
            continue
        # The difference text may itself contain `|` (e.g. ``d1 | d2``); the status is
        # always the last cell, so never require exactly four.
        result.append({"id": cells[0], "area": cells[1],
                       "difference": "|".join(cells[2:-1]), "status": cells[-1]})
    return result


def wanted(row):
    status = row["status"].strip()
    return (status == "open" or status == "" or status == "refused"
            or status.startswith("declared"))


def selected():
    return [r for r in rows() if wanted(r)]


def say_refused(row):
    status = row["status"].strip().lower()
    text = row["difference"].lower()
    return status == "refused" or (status.startswith("declared") and "refus" in text)


def limit():
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT, LIMIT))


def run(cmd, env, cwd):
    try:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                              timeout=TIMEOUT, env=env, preexec_fn=limit)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return subprocess.CompletedProcess(cmd, None, out, err)


def verdict(row, built, ran, expected):
    if built.returncode is None or (ran is not None and ran.returncode is None):
        return "timeout"
    if built.returncode != 0:
        return "refused-as-said" if say_refused(row) else "differs-otherwise"
    if ran.returncode == expected.returncode and ran.stdout == expected.stdout:
        return "now-matches"
    return "still-differs"


def build_and_run(source, forced, data=None):
    work = Path(tempfile.mkdtemp(prefix="ail-diffaudit-"))
    try:
        program = work / "probe.py"
        shutil.copyfile(source, program)
        exe = work / ("probe-forced.out" if forced else "probe-default.out")
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if forced:
            env["AIL_UNIFIED_FORCE"] = "1"
        built = run([sys.executable, "-B", str(CLI), "compile", str(program),
                     "--syntax", "python", "-o", str(exe)], env, work)
        if built.returncode != 0:
            return built, None
        if data is None:
            ran = run([str(exe)], env, work)
        else:
            feed = work / "input.bin"
            feed.write_bytes(data)
            ran = run([str(exe), str(feed)], env, work)
        return built, ran
    finally:
        shutil.rmtree(work, ignore_errors=True)


def cpython(source, oracle=None):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    if oracle is not None:
        return run([sys.executable, "-B", "-c", oracle], env, source.parent)
    return run([sys.executable, "-B", str(source)], env, source.parent)


def detail(label, result):
    if result is None:
        return "  %s: <not run>" % label
    return "  %s: rc=%s stdout=%r stderr=%r" % (
        label, result.returncode, result.stdout, result.stderr)


def do_run():
    by_slug = {slug(r["id"]): r for r in rows()}
    probes = sorted(HERE.glob("*.py"))
    probes = [p for p in probes if p.name != "audit.py"]
    findings = []
    for probe in probes:
        row = by_slug.get(probe.stem)
        if row is None:
            print("%s | no matching selected row" % probe.stem)
            continue
        spec = PIPELINE.get(probe.stem, {})
        expected = cpython(probe, spec.get("oracle"))
        built_default, ran_default = build_and_run(probe, False, spec.get("input"))
        built_forced, ran_forced = build_and_run(probe, True, spec.get("input"))
        vd = verdict(row, built_default, ran_default, expected)
        vf = verdict(row, built_forced, ran_forced, expected)
        overrides = OVERRIDES.get(probe.stem, {})
        vd = overrides.get("default", vd)
        vf = overrides.get("forced", vf)
        print("%s | %s | default=%s | forced=%s" % (row["id"], probe.name, vd, vf))
        if "differs-otherwise" in (vd, vf) or "timeout" in (vd, vf):
            findings.append((row, probe, expected, (built_default, ran_default),
                             (built_forced, ran_forced)))
    if findings:
        print("\nFINDINGS (differs-otherwise / timeout)")
        for row, probe, expected, default, forced in findings:
            print("\n%s | %s | %s" % (row["id"], row["area"], probe.name))
            print(detail("cpython", expected))
            print(detail("default build", default[0]))
            print(detail("default run", default[1]))
            print(detail("forced build", forced[0]))
            print(detail("forced run", forced[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        counts = {}
        for row in selected():
            status = row["status"].strip()
            key = ("declared" if status.startswith("declared") else
                   "empty" if status == "" else status)
            counts[key] = counts.get(key, 0) + 1
            print("%s | %s | %s" % (row["id"], row["area"], row["status"]))
        print("counts: " + ", ".join("%s=%d" % item for item in sorted(counts.items())))
    else:
        do_run()


if __name__ == "__main__":
    main()
