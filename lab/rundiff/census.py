"""The `ail run --diff` census: every program run natively and under CPython, same input.

    python3 lab/rundiff/census.py                 # both sets, writes RESULTS.md
    python3 lab/rundiff/census.py --compare       # the ten lab/compare/src/*/main.py public cases only
    python3 lab/rundiff/census.py --corpus 50     # the first 50 corpus/gdev programs
    python3 lab/rundiff/census.py --json out.json # also write the raw rows

Each run is one `ail run --diff --json` invocation (packaging/ail_lang/cli.py), so the census measures
exactly what the command reports: agree / differ / loud stop by design / timeout. A "differ" is a
compiler bug candidate, not something this directory fixes.
"""
import argparse
import importlib.util
import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PACKAGING = REPO / "packaging"
SDK = REPO / "AIL_CURRENT"
CORPUS = REPO / "corpus" / "gdev"
COMPARE = REPO / "lab" / "compare"


def load_generator(task):
    """The task's gen.py: cases(rng) -> (public, hidden, perf), plus its STDIN flag."""
    path = COMPARE / "tasks" / task / "gen.py"
    spec = importlib.util.spec_from_file_location("census_gen_" + task, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compare_cases():
    """[(label, source, stdin bytes, args)] for every public case of the ten compare programs."""
    rows, work = [], Path(tempfile.mkdtemp(prefix="ail-census-"))
    for task in sorted((COMPARE / "src").iterdir()):
        source = task / "main.py"
        if not source.is_file():
            continue
        module = load_generator(task.name)
        public, _hidden, _perf = module.cases(random.Random("%s-20261012" % task.name))
        stdin_on = bool(getattr(module, "STDIN", False))
        for name, data, args in public:
            path = work / ("%s-%s.bin" % (task.name, name))
            path.write_bytes(data)
            argv = [str(a).replace("{input}", str(path)) for a in args]
            rows.append(("%s/%s" % (task.name, name), source, data if stdin_on else b"", argv))
    return rows


def corpus_cases(count):
    """[(label, source, stdin bytes, args)] for the first `count` corpus programs, in name order."""
    sources = sorted(CORPUS.glob("*.py"))[:count]
    return [("corpus/" + source.name, source, b"", []) for source in sources]


def census_one(label, source, stdin, args):
    environment = dict(os.environ, PYTHONPATH=str(PACKAGING), AIL_SDK_DIR=str(SDK), PYTHONUTF8="1")
    command = [sys.executable, "-B", "-m", "ail_lang", "run", "--diff", "--json", str(source), *args]
    try:
        done = subprocess.run(command, cwd=str(source.parent), env=environment, input=stdin,
                              capture_output=True, timeout=900)
    except subprocess.TimeoutExpired:
        return dict(label=label, outcome="timeout: harness", exit=None, detail="the census harness timed out")
    lines = done.stdout.decode("utf-8", "replace").splitlines()
    report = None
    for line in reversed(lines):
        if line.startswith("{"):
            try:
                report = json.loads(line)
            except ValueError:
                report = None
            break
    if report is None:
        return dict(label=label, outcome="no report", exit=done.returncode,
                    detail=(done.stderr.decode("utf-8", "replace").strip().splitlines() or [""])[-1])
    kind = report.get("outcome") or "?"
    native, cpython = report.get("native"), report.get("cpython")
    if kind == "agree":
        summary = "stdout and exit code match"
    elif kind == "differ" and report.get("line") is not None:
        summary = "stdout line %d: native %r, cpython %r" % (report["line"], native, cpython)
    elif kind == "differ" and all(isinstance(one, int) for one in (native, cpython)):
        summary = "exit code %d vs %d" % (native, cpython)
    elif kind == "differ" and isinstance(native, str) and native.startswith("build stopped"):
        summary = "the build stopped where CPython exited %s: %s" % (cpython, native[len("build stopped: "):])
    elif kind == "differ":
        summary = "native %r vs cpython %r" % (native, cpython)
    elif kind == "loud stop by design":
        summary = str(native)
    else:
        summary = kind
    return dict(label=label, outcome=kind, exit=done.returncode, detail=summary)


def run(rows, verbose=True):
    results = []
    for index, (label, source, stdin, args) in enumerate(rows, 1):
        one = census_one(label, source, stdin, args)
        results.append(one)
        if verbose:
            print("%3d/%d %-40s %-24s %s" % (index, len(rows), label, one["outcome"], one["detail"]),
                  file=sys.stderr, flush=True)
    return results


def tally(results):
    counts = {}
    for one in results:
        counts[one["outcome"]] = counts.get(one["outcome"], 0) + 1
    return counts


def markdown(title, results, note):
    counts = tally(results)
    order = ["agree", "differ", "loud stop by design", "timeout: native", "timeout: cpython"]
    keys = order + sorted(k for k in counts if k not in order)
    lines = ["## %s" % title, "", "| outcome | count |", "| --- | --- |"]
    lines += ["| %s | %d |" % (key, counts[key]) for key in keys if key in counts]
    lines += ["| **total** | **%d** |" % len(results), ""]
    if note:
        lines += [note, ""]
    differ = [one for one in results if one["outcome"] == "differ"]
    if differ:
        lines += ["### Differ (a bug list for the compiler; not fixed here)", "",
                  "| program | what differed |", "| --- | --- |"]
        for one in differ:
            lines.append("| `%s` | %s |" % (one["label"], one["detail"].replace("|", "\\|")))
        lines.append("")
    loud = [one for one in results if one["outcome"] == "loud stop by design"]
    if loud:
        lines += ["### Loud stop by design", "", "| program | reason |", "| --- | --- |"]
        for one in loud:
            lines.append("| `%s` | %s |" % (one["label"], one["detail"].replace("|", "\\|")))
        lines.append("")
    other = [one for one in results if one["outcome"] not in
             ("agree", "differ", "loud stop by design")]
    if other:
        lines += ["### Other outcomes", "", "| program | outcome | detail |", "| --- | --- | --- |"]
        for one in other:
            lines.append("| `%s` | %s | %s |" % (one["label"], one["outcome"],
                                                 one["detail"].replace("|", "\\|")))
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--compare", action="store_true", help="only lab/compare/src/*/main.py public cases")
    parser.add_argument("--corpus", type=int, default=0, help="only the first N corpus/gdev programs")
    parser.add_argument("--json", help="also write the raw rows here")
    parser.add_argument("--out", default=str(HERE / "RESULTS.md"), help="the report to write")
    arguments = parser.parse_args()
    both = not arguments.compare and not arguments.corpus
    sections, everything = [], []

    if both or arguments.compare:
        rows = compare_cases()
        results = run(rows)
        everything += results
        sections.append(markdown("lab/compare/src/*/main.py, public cases", results,
                                 "Ten programs, every public case of the task's `gen.py`, run as the task "
                                 "runs them (stdin when the task reads stdin, both builds' arguments)."))
    if both or arguments.corpus:
        count = arguments.corpus or 50
        rows = corpus_cases(count)
        results = run(rows)
        everything += results
        sections.append(markdown("%d corpus/gdev programs" % len(rows), results,
                                 "The first programs of `corpus/gdev` in name order, no arguments and empty "
                                 "stdin."))

    header = ["# `ail run --diff` census", "",
              "Every program is built once and run twice (natively, then under CPython) with the same input, "
              "through `ail run --diff --json`; the outcomes are the command's own. A **differ** means the "
              "compiler and CPython disagree, which is a bug in one of them (usually the compiler); this "
              "census only lists them.", ""]
    text = "\n".join(header) + "\n" + "\n\n".join(sections)
    Path(arguments.out).write_text(text + "\n", encoding="utf-8")
    if arguments.json:
        Path(arguments.json).write_text(json.dumps(everything, indent=1), encoding="utf-8")
    print("\n".join(text.splitlines()[:40]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
