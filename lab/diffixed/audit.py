#!/usr/bin/env python3
"""Audit `fixed` rows of DIFFERENCES.md that cite no test or lab file.

Usage:
    python3 lab/diffixed/audit.py          # print `id | area | status` for every listed row
    python3 lab/diffixed/audit.py --run    # build and run lab/diffixed/<slug>.py in the default
                                           # build and with AIL_UNIFIED_FORCE=1, compare CPython,
                                           # write AUDIT.md and exit non-zero on a difference

A row is listed when its last table cell (the status/disposition column) starts with `fixed`
and the whole row text contains neither `test_ail_` nor `lab/`.  Cells are split on `|` only
outside backtick code spans, so a difference that quotes a `|` operator stays one cell.  One
probe per row: the id with every character outside [A-Za-z0-9_] replaced by `_`.
"""
import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIFF = ROOT / "DIFFERENCES.md"
PROBES = Path(__file__).resolve().parent
AUDIT = PROBES / "AUDIT.md"
CLI = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
PY = sys.executable
TIMEOUT = 120

# Rows whose text is not enough to write a probe: id -> one-line reason.
NO_REPRO = {}

# Verdicts that are not a regression for a row whose status already documents them.
EXPECTED_REFUSAL = ("fixed in range; out-of-range refused by name",
                    "fixed / refused by name")


def split_cells(line):
    """Split a markdown table row on `|` outside backtick code spans."""
    cells, cur, in_code, i = [], [], False, 0
    text = line.strip()
    text = text[1:-1] if text.endswith("|") else text[1:]
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            cur.append(text[i:i + 2])
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
            cur.append(ch)
        elif ch == "|" and not in_code:
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def table_rows():
    rows = []
    for line in DIFF.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = split_cells(line)
        if not cells or cells[0].lower() == "id":
            continue
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        rows.append((line, cells))
    return rows


def audited_rows():
    rows = []
    for line, cells in table_rows():
        status = cells[-1]
        if not status.startswith("fixed"):
            continue
        if "test_ail_" in line or "lab/" in line:
            continue
        rows.append((cells[0], cells[1] if len(cells) > 1 else "", status))
    return rows


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


def collecting_commit(row_id):
    try:
        out = subprocess.run(["git", "log", "--oneline", "-S", row_id, "--", "DIFFERENCES.md"],
                             cwd=str(ROOT), capture_output=True, text=True, timeout=30)
        return out.stdout.strip()
    except Exception:  # noqa: BLE001 - diagnostics only
        return ""


def audit(rows):
    results = {}
    with tempfile.TemporaryDirectory(prefix="ail-diffixed-") as tmp:
        tasks = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for row_id, _area, _status in rows:
                probe = PROBES / (slug(row_id) + ".py")
                if not probe.exists():
                    continue
                for mode in ("default", "force"):
                    tasks[pool.submit(one, probe, mode, tmp)] = (row_id, mode)
            for future in concurrent.futures.as_completed(tasks):
                row_id, mode = tasks[future]
                try:
                    results[(row_id, mode)] = future.result()
                except Exception as exc:  # noqa: BLE001 - report, do not abort the audit
                    results[(row_id, mode)] = {"verdict": "error", "error": str(exc)}
    return results


def verdicts_for(row_id, results):
    out = []
    for mode in ("default", "force"):
        res = results.get((row_id, mode))
        if res is None:
            out.append("no-repro")
        else:
            out.append(res["verdict"])
    return out


def write_audit(rows, results, elapsed):
    counts = {}
    findings = []
    no_repro = []
    lines = []
    for row_id, area, status in rows:
        default, forced = verdicts_for(row_id, results)
        counts[default] = counts.get(default, 0) + 1
        counts[forced] = counts.get(forced, 0) + 1
        if row_id in NO_REPRO:
            no_repro.append((row_id, NO_REPRO[row_id]))
        elif not (PROBES / (slug(row_id) + ".py")).exists():
            no_repro.append((row_id, "no probe file in lab/diffixed/"))
        for mode, verdict in (("default", default), ("force", forced)):
            res = results.get((row_id, mode))
            if verdict == "differs":
                findings.append((row_id, mode, res, status))
            elif verdict == "error":
                findings.append((row_id, mode, None, status))
            elif verdict == "refused" and not status.startswith(EXPECTED_REFUSAL):
                findings.append((row_id, mode, res, status))

    lines.append("# diffixed audit: `fixed` rows that cite no test\n")
    lines.append("Rows of `DIFFERENCES.md` whose last-cell status starts with `fixed` and whose")
    lines.append("whole row text contains neither `test_ail_` nor `lab/`.  Every listed row has")
    lines.append("one probe in `lab/diffixed/`; each probe is built in the default build and with")
    lines.append("`AIL_UNIFIED_FORCE=1` (fresh temp dir, `AIL_NO_CACHE=1`, 120 s timeout,"
                 " `ulimit -v 1500000`), run, and compared with `python3` on stdout and exit status.\n")
    lines.append("Generated by `python3 lab/diffixed/audit.py --run` in %.1f s.\n" % elapsed)

    lines.append("## Findings\n")
    if not findings:
        lines.append("None: every probe matches CPython in both builds, or is refused where the")
        lines.append("row already says the construct is refused by name.\n")
    else:
        for row_id, mode, res, status in findings:
            lines.append("### %s (%s build)\n" % (row_id, mode))
            lines.append("Row status: `%s`\n" % status)
            if res is None:
                lines.append("Probe raised an error while auditing.\n")
                continue
            if res["verdict"] == "refused":
                lines.append("Build was refused, but the row says the construct works:\n")
                lines.append("```\n%s\n```\n" % res["build"].stderr.strip()[-2000:])
            else:
                cp, nat = res["cpython"], res["native"]
                lines.append("```")
                lines.append("cpython rc=%d" % cp.returncode)
                lines.append("stdout: %r" % cp.stdout[:2000])
                lines.append("stderr: %r" % cp.stderr[-1000:])
                lines.append("ail     rc=%d" % nat.returncode)
                lines.append("stdout: %r" % nat.stdout[:2000])
                lines.append("stderr: %r" % nat.stderr[-1000:])
                lines.append("```\n")
            searched = collecting_commit(row_id)
            if searched:
                lines.append("Commit range to search (`git log -S %s -- DIFFERENCES.md`):\n" % row_id)
                lines.append("```\n%s\n```\n" % searched)

    lines.append("## No-repro rows\n")
    if not no_repro:
        lines.append("None.\n")
    else:
        for row_id, reason in no_repro:
            lines.append("- `%s`: %s" % (row_id, reason))
        lines.append("")

    lines.append("## The list\n")
    lines.append("| id | area | status |")
    lines.append("| --- | --- | --- |")
    for row_id, area, status in rows:
        lines.append("| %s | %s | %s |" % (row_id, area.replace("|", "\\|"), status))
    lines.append("\ncount: %d\n" % len(rows))

    lines.append("## Verdicts\n")
    lines.append("| id | area | verdict default | verdict forced | probe file |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row_id, area, _status in rows:
        default, forced = verdicts_for(row_id, results)
        lines.append("| %s | %s | %s | %s | `%s.py` |"
                     % (row_id, area.replace("|", "\\|"), default, forced, slug(row_id)))
    lines.append("")
    for verdict in sorted(counts):
        lines.append("- %s: %d" % (verdict, counts[verdict]))
    lines.append("")
    AUDIT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    rows = audited_rows()
    if not args.run:
        for row_id, area, status in rows:
            print("%s | %s | %s" % (row_id, area, status))
        print("count: %d" % len(rows), file=sys.stderr)
        return 0

    start = time.time()
    results = audit(rows)
    elapsed = time.time() - start
    for row_id, area, status in rows:
        probe = slug(row_id) + ".py"
        default, forced = verdicts_for(row_id, results)
        print("%s\t%s\t%s\t%s" % (row_id, probe, default, forced))
        for mode in ("default", "force"):
            res = results.get((row_id, mode))
            if res and res["verdict"] == "differs":
                print("  [%s] cpython rc=%d stdout=%r" % (
                    mode, res["cpython"].returncode, res["cpython"].stdout[:400]))
                print("  [%s] ail     rc=%d stdout=%r" % (
                    mode, res["native"].returncode, res["native"].stdout[:400]))
            if res and res["verdict"] == "refused":
                tail = res["build"].stderr.strip().splitlines()[-1:]
                print("  [%s] refused: %s" % (mode, tail))
    write_audit(rows, results, elapsed)
    bad = [key for key, res in results.items() if res["verdict"] in ("differs", "error")]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
