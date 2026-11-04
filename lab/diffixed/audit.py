#!/usr/bin/env python3
"""List `fixed` rows of DIFFERENCES.md that cite no test or lab file, and probe them.

Usage:
    python3 lab/diffixed/audit.py          # print `id | area | status` for every listed row
    python3 lab/diffixed/audit.py --run    # build and run lab/diffixed/<slug>.py in the default
                                           # build and with AIL_UNIFIED_FORCE=1, compare CPython

A row is listed when its status cell (trimmed) starts with `fixed` and the whole row text
contains neither `test_ail_` nor `lab/`.  One probe per row: the id with every character
outside [A-Za-z0-9_] replaced by `_`.
"""
import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIFF = ROOT / "DIFFERENCES.md"
PROBES = Path(__file__).resolve().parent
CLI = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
PY = sys.executable
TIMEOUT = 120


def table_rows():
    rows = []
    for line in DIFF.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] == "id" or set(cells[0]) <= set("- "):
            continue
        rows.append(cells)
    return rows


def audited_rows():
    return [r for r in table_rows()
            if r[3].startswith("fixed")
            and "test_ail_" not in "|".join(r)
            and "lab/" not in "|".join(r)]


def slug(row_id):
    return re.sub(r"[^A-Za-z0-9_]", "_", row_id)


def limited(cmd):
    return ["bash", "-c", "ulimit -v 1500000; exec \"$@\"", "--"] + cmd


def clean_env(extra=None):
    env = dict(os.environ)
    for key in ("AIL_UNIFIED_FORCE", "AIL_UNIFIED", "AIL_NO_GENERAL", "PYTHONPATH",
                "AIL_EXACT_INT", "AIL_UNIFIED_EXACT", "AIL_NO_MIX"):
        env.pop(key, None)
    env["AIL_NO_CACHE"] = "1"
    if extra:
        env.update(extra)
    return env


def run(cmd, cwd, env):
    return subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
                          timeout=TIMEOUT)


def one(probe, mode, workdir):
    work = Path(workdir) / (probe.stem + "_" + mode)
    work.mkdir()
    src = work / probe.name
    shutil.copyfile(probe, src)
    exe = work / "prog.out"
    env = clean_env({"AIL_UNIFIED_FORCE": "1"} if mode == "force" else None)
    build = run(limited([PY, "-B", str(CLI), "compile", str(src), "-o", str(exe)]), work, env)
    if build.returncode != 0:
        return {"verdict": "refused", "build": build, "src": src, "mode": mode}
    cpython = run([PY, "-B", str(src)], work, clean_env())
    native = run(limited([str(exe)]), work, env)
    ok = native.stdout == cpython.stdout and native.returncode == cpython.returncode
    return {"verdict": "matches" if ok else "differs", "cpython": cpython,
            "native": native, "src": src, "mode": mode, "build": build}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    rows = audited_rows()
    if not args.run:
        for row in rows:
            print("%s | %s | %s" % (row[0], row[1], row[3]))
        print("count: %d" % len(rows), file=sys.stderr)
        return 0

    missing = [r[0] for r in rows if not (PROBES / (slug(r[0]) + ".py")).exists()]
    if missing:
        print("missing probes: %s" % ", ".join(missing))
    results = {}
    with tempfile.TemporaryDirectory(prefix="ail-diffixed-") as tmp:
        tasks = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for row in rows:
                probe = PROBES / (slug(row[0]) + ".py")
                if not probe.exists():
                    continue
                for mode in ("default", "force"):
                    tasks[pool.submit(one, probe, mode, tmp)] = (row[0], mode)
            for future in concurrent.futures.as_completed(tasks):
                row_id, mode = tasks[future]
                try:
                    results[(row_id, mode)] = future.result()
                except Exception as exc:  # noqa: BLE001 - report, do not abort the audit
                    results[(row_id, mode)] = {"verdict": "error", "error": str(exc)}

    for row in rows:
        row_id = row[0]
        probe = slug(row_id) + ".py"
        verdicts = []
        for mode in ("default", "force"):
            res = results.get((row_id, mode))
            verdicts.append("missing" if res is None else res["verdict"])
        print("%s\t%s\t%s\t%s" % (row_id, probe, verdicts[0], verdicts[1]))
        for mode in ("default", "force"):
            res = results.get((row_id, mode))
            if res and res["verdict"] == "differs":
                print("  [%s] cpython rc=%d stdout=%r" % (
                    mode, res["cpython"].returncode, res["cpython"].stdout[:400]))
                print("  [%s] ail     rc=%d stdout=%r" % (
                    mode, res["native"].returncode, res["native"].stdout[:400]))
            if res and res["verdict"] == "refused":
                print("  [%s] refused: %s" % (mode, res["build"].stderr.strip().splitlines()[-1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
