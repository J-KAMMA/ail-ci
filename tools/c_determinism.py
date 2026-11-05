#!/usr/bin/env python3
"""Measure whether today's compiler emits byte-identical C for the same program.

    python3 tools/c_determinism.py [--json OUT] [-j 2] [--builds 3] [--filter SUBSTR]

For 30 programs (10 from lab/stdlib/, 10 from examples/, the 10 lab/compare/src/*/main.py)
this builds the program three times in both the default (general) and the --strict (typed)
build.  Each build gets its own working directory, its own output directory and its own
PYTHONHASHSEED (0, 1, random), with AIL_NO_CACHE=1.  The generated DIR/program.c files are
compared byte for byte; the first differing line and a difference class are recorded.

A difference class is one of: hash order (same lines, different order), absolute path,
temporary name, time, counter, other.  No compiler file is edited: this is measure-only.

All builds run under a 1.5 GB address-space limit, at most two at a time.  If two builds of
the same program also produce different stdout when run, that is recorded as WRONG OUTPUT
(a separate bug class, not a determinism class) and the run stops.
"""
import argparse
import concurrent.futures
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMPILER = REPO / "AIL_CURRENT" / "ail_chatgpt.py"
LIMIT = 1500000 * 1024
SEEDS = ("0", "1", "random")

STDLIB = (
    "shlex/01_command_line.py",
    "json/01_config_roundtrip.py",
    "csv/basic_roundtrip.py",
    "base64/altchars_filesystem.py",
    "heapq/closest_points.py",
    "bisect/alias_import.py",
    "collections/config_layers.py",
    "decimal/basic_arith.py",
    "getopt/01_short_options.py",
    "string/csv_punctuation_report.py",
)
EXAMPLES = (
    "tutorial_project/step1.py",
    "tutorial_project/step2.py",
    "tutorial_project/step3.py",
    "tutorial_project/step4.py",
    "tutorial_project/step5.py",
    "tutorial_project/step6.py",
    "algos/dijkstra.py",
    "algos/levenshtein.py",
    "algos/mandelbrot.py",
    "algos/rpn.py",
)


def limit_memory():
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT, LIMIT))


def programs():
    items = [("stdlib/" + rel, REPO / "lab" / "stdlib" / rel) for rel in STDLIB]
    items += [("examples/" + rel, REPO / "examples" / rel) for rel in EXAMPLES]
    items += [("compare/" + path.parent.name, path)
              for path in sorted((REPO / "lab" / "compare" / "src").glob("*/main.py"))]
    return items


def build(compiler, source, work, seed, strict):
    work.mkdir(parents=True, exist_ok=True)
    src = work / source.name
    shutil.copyfile(source, src)
    out = work / "prog"
    debug = work / "debug"
    env = {k: v for k, v in os.environ.items()
           if k not in ("AIL_CACHE", "AIL_NO_CACHE", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE",
                        "PYTHONHASHSEED")}
    env.update(AIL_NO_CACHE="1", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONHASHSEED=seed)
    cmd = [sys.executable, "-B", str(compiler), "compile", str(src), "-o", str(out),
           "--debug-dir", str(debug)]
    if strict:
        cmd.append("--strict")
    done = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=900,
                          preexec_fn=limit_memory)
    program_c = debug / "program.c"
    return {
        "seed": seed,
        "returncode": done.returncode,
        "stderr": done.stderr,
        "program_c": program_c.read_bytes() if program_c.is_file() else None,
        "binary": out if out.is_file() else None,
        "work": work,
    }


def run_binary(result):
    if result["binary"] is None:
        return None
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)}
    env.update(PYTHONUTF8="1")
    try:
        done = subprocess.run([str(result["binary"])], cwd=result["work"], env=env,
                              input=b"", capture_output=True, timeout=120,
                              preexec_fn=limit_memory)
    except subprocess.TimeoutExpired:
        return {"returncode": "timeout", "stdout": b""}
    return {"returncode": done.returncode, "stdout": done.stdout}


def first_difference(left, right):
    a = left.decode("utf-8", "replace").splitlines()
    b = right.decode("utf-8", "replace").splitlines()
    for index, (x, y) in enumerate(zip(a, b), 1):
        if x != y:
            return index, x, y
    if len(a) != len(b):
        index = min(len(a), len(b)) + 1
        return index, a[index - 1] if index <= len(a) else "<eof>", \
            b[index - 1] if index <= len(b) else "<eof>"
    return None


TIME = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b|\b\d{4}-\d{2}-\d{2}\b|\b20\d\d\b.*\b(GMT|UTC)\b")
TEMP = re.compile(r"\b(tmp|temp)[a-z0-9_]{4,}\b|[A-Za-z0-9_]+\.tmp\b")


def classify(left, right, line_left, line_right, work_root):
    if sorted(left.decode("utf-8", "replace").splitlines()) == \
            sorted(right.decode("utf-8", "replace").splitlines()):
        return "hash order"
    hay = line_left + "\n" + line_right
    if str(work_root) in hay or "/tmp/" in hay or re.search(r"[A-Za-z]:\\\\", hay):
        return "absolute path"
    if TIME.search(hay):
        return "time"
    if TEMP.search(hay):
        return "temporary name"
    if re.sub(r"\d+", "#", line_left) == re.sub(r"\d+", "#", line_right):
        return "counter"
    return "other"


def one(program, source, mode, builds, work_root):
    strict = mode == "typed"
    results = []
    for index in range(builds):
        work = work_root / program.replace("/", "_") / mode / ("b%d" % index)
        try:
            results.append(build(COMPILER, source, work, SEEDS[index % len(SEEDS)], strict))
        except subprocess.TimeoutExpired:
            results.append({"seed": SEEDS[index % len(SEEDS)], "returncode": "timeout",
                            "program_c": None, "binary": None, "work": work})
    out = {"program": program, "source": str(source.relative_to(REPO)), "mode": mode,
           "builds": len(results), "built": 0, "identical": True, "class": None,
           "first_diff_line": None, "diff_a": None, "diff_b": None, "wrong_output": None}
    ok = [r for r in results if r["returncode"] == 0 and r["program_c"] is not None]
    out["built"] = len(ok)
    if len(ok) < 2:
        out["identical"] = None   # cannot compare
        return out
    base = ok[0]
    for other in ok[1:]:
        if other["program_c"] == base["program_c"]:
            continue
        out["identical"] = False
        found = first_difference(base["program_c"], other["program_c"])
        if found:
            line, left, right = found
            out["first_diff_line"] = line
            out["diff_a"] = left.strip()[:200]
            out["diff_b"] = right.strip()[:200]
            out["class"] = classify(base["program_c"], other["program_c"], left, right,
                                    work_root)
        else:
            out["class"] = "other"
        break
    ran = [run_binary(r) for r in ok]
    if ran and any(r is not None for r in ran):
        first = next(r for r in ran if r is not None)
        for later in ran:
            if later is None:
                continue
            if later["stdout"] != first["stdout"] or later["returncode"] != first["returncode"]:
                out["wrong_output"] = {"a": first["returncode"], "b": later["returncode"]}
                break
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", help="write the full result as JSON here")
    parser.add_argument("-j", "--jobs", type=int, default=2)
    parser.add_argument("--builds", type=int, default=3)
    parser.add_argument("--filter", default=None, help="only programs whose name contains this")
    parser.add_argument("--summarize", metavar="JSON", default=None,
                        help="print the summary for an earlier --json run and stop")
    args = parser.parse_args()

    if args.summarize:
        return summarize(json.loads(Path(args.summarize).read_text()), args.summarize)

    items = programs()
    if args.filter:
        items = [(name, path) for name, path in items if args.filter in name]
    work_root = Path(tempfile.mkdtemp(prefix="ail-cdet-"))
    tasks = [(name, path, mode) for name, path in items for mode in ("general", "typed")]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {pool.submit(one, name, path, mode, args.builds, work_root): (name, mode)
                   for name, path, mode in tasks}
        for future in concurrent.futures.as_completed(futures):
            name, mode = futures[future]
            try:
                record = future.result()
            except Exception as exc:  # a crash is a finding, not a reason to lose the run
                record = {"program": name, "mode": mode, "identical": None,
                          "class": "other", "error": repr(exc)}
            results.append(record)
            verdict = {True: "identical", False: "DIFF", None: "unbuilt"}[record.get("identical")]
            print("%-45s %-7s %s" % (name, mode, verdict), flush=True)

    results.sort(key=lambda r: (r["program"], r["mode"]))
    work_root_str = str(work_root)
    for record in results:
        for key in ("diff_a", "diff_b"):
            if record.get(key):
                record[key] = record[key].replace(work_root_str, "<work>")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1) + "\n")

    return summarize(results, None)


def summarize(results, json_path):
    """Print the counts this task reports; a program counts only when every mode that built is
    identical in all its builds (a refused mode is deterministic but emits no C)."""
    names = []
    for row in results:
        if row["program"] not in names:
            names.append(row["program"])
    identical_programs = 0
    general = [0, 0]
    typed = [0, 0]
    pairs = 0
    identical_pairs = 0
    classes = {}
    examples = {}
    wrong = []
    for name in names:
        rows = [r for r in results if r["program"] == name]
        pairs += len(rows)
        identical_pairs += sum(1 for r in rows if r.get("identical") is True)
        built = [r for r in rows if r.get("identical") is not None]
        if built and all(r.get("identical") is True for r in built):
            identical_programs += 1
        for row in rows:
            if row["mode"] == "general" and row.get("identical") is not None:
                general[0] += row.get("identical") is True
                general[1] += 1
            if row["mode"] == "typed" and row.get("identical") is not None:
                typed[0] += row.get("identical") is True
                typed[1] += 1
            if row.get("identical") is False:
                key = row.get("class")
                classes[key] = classes.get(key, 0) + 1
                examples.setdefault(key, row)
            if row.get("wrong_output"):
                wrong.append(row)

    print()
    print("identical programs: %d / %d" % (identical_programs, len(names)))
    print("identical program-mode pairs: %d / %d" % (identical_pairs, pairs))
    print("  general build identical: %d / %d compared" % tuple(general))
    print("  typed build identical:   %d / %d compared" % tuple(typed))
    for key in sorted(classes):
        row = examples[key]
        print("  class %-14s %d  e.g. %s %s line %s" %
              (key, classes[key], row["program"], row["mode"], row.get("first_diff_line")))
    if wrong:
        print("WRONG OUTPUT:", ", ".join("%s %s" % (r["program"], r["mode"]) for r in wrong))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
