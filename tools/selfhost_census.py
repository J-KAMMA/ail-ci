#!/usr/bin/env python3
"""Census of a Python source tree against the CPython hybrid's typed selection.

    python3 tools/selfhost_census.py --run-all --out lab/selfhost/census.json FILE...

The unit is one top-level ``def``.  Each file is analysed whole with
``ail_cpython_hybrid._analysis`` and ``_select`` (no extension is built); a top-level
function is accepted only when the same selection the hybrid uses chooses it.  Methods are
counted separately ("in a class") without a per-method verdict.

``--run-all`` runs one file per child process under a 1.5 GB address-space limit and a
per-file timeout.  A file that does not finish is retried as line-range chunks; a chunk is
the file's leading module preamble plus the top-level functions whose ``def`` line falls in
that range.  Chunked files say so in the JSON.
"""

from __future__ import annotations

import argparse
import ast
import json
import multiprocessing
import os
import resource
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "AIL_CURRENT"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MEMORY_LIMIT = 1500 * 1024 * 1024
DEFAULT_TIMEOUT = 300
DEFAULT_CHUNK_LINES = 3000
SCHEMA = "ail.selfhost_census/1"


class _Timeout(Exception):
    pass


def _alarm(_signum, _frame):
    raise _Timeout()


def _relative(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(path).resolve())


def _first_line(text):
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:400]
    return ""


def _top_level(tree):
    return [node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _classes(tree):
    out = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        methods = []
        for body_node in node.body:
            if isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append({
                    "name": body_node.name,
                    "line": body_node.lineno,
                    "length": (getattr(body_node, "end_lineno", body_node.lineno)
                               or body_node.lineno) - body_node.lineno + 1,
                })
        out.append({"name": node.name, "line": node.lineno, "methods": methods})
    return out


def _node_start(node):
    starts = [node.lineno]
    for decorator in getattr(node, "decorator_list", ()):
        starts.append(decorator.lineno)
    return min(starts)


def _function_text(lines, node):
    start = _node_start(node)
    end = getattr(node, "end_lineno", node.lineno) or node.lineno
    return "".join(lines[start - 1:end])


def _preamble_text(lines, functions):
    if not functions:
        return ""
    first = min(_node_start(fn) for fn in functions)
    return "".join(lines[:first - 1])


def _classify(text, label):
    import ail_cpython_hybrid as hybrid

    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return {"error": "parse: %s" % error, "chosen": {}, "rejected": {},
                "units": [], "facts": set(), "note": "", "label": label}
    try:
        report, facts = hybrid._analysis(text)
    except _Timeout:
        raise
    except BaseException as error:
        return {"error": "%s: %s" % (type(error).__name__, str(error)[:300]),
                "chosen": {}, "rejected": {}, "units": [], "facts": set(),
                "note": "", "label": label}
    try:
        chosen, rejected = hybrid._select(text, tree, report, facts)
    except _Timeout:
        raise
    except BaseException as error:
        return {"error": "%s: %s" % (type(error).__name__, str(error)[:300]),
                "chosen": {}, "rejected": {}, "units": [], "facts": set(),
                "note": _first_line(report.get("note")), "label": label}
    units = [unit[1] for unit in (report.get("mix_units") or []) if len(unit) > 1]
    return {
        "error": "",
        "chosen": chosen,
        "rejected": rejected,
        "units": units,
        "facts": set(facts),
        "note": _first_line(report.get("note")),
        "label": label,
    }


def _function_verdict(name, result):
    if name in result["chosen"]:
        return "accept", ""
    reason = result["rejected"].get(name)
    if reason:
        return "reject", reason
    if name in result["units"] and name not in result["facts"]:
        return "reject", "the typed emitter produced no signature"
    if result["error"]:
        return "reject", result["error"]
    if result["note"]:
        return "reject", result["note"]
    return "reject", "not emitted by the typed path"


def _function_records(path, functions, result, verdicts=None):
    records = []
    for node in functions:
        if verdicts is not None:
            verdict, reason = verdicts[node.name]
        else:
            verdict, reason = _function_verdict(node.name, result)
        records.append({
            "file": path,
            "name": node.name,
            "line": node.lineno,
            "length": (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1,
            "verdict": verdict,
            "reason": reason,
        })
    return records


def classify_file(path, start=None, end=None, timeout=None):
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source, filename=str(path))
    functions = _top_level(tree)
    if start is not None or end is not None:
        selected = [fn for fn in functions
                    if (start is None or fn.lineno >= start)
                    and (end is None or fn.lineno <= end)]
        text = _preamble_text(lines, selected) + "".join(_function_text(lines, fn)
                                                         for fn in selected)
        label = "%s:%s-%s" % (path.name, start, end)
    else:
        selected = functions
        text = source
        label = path.name
    if timeout:
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(timeout)
    try:
        result = _classify(text, label)
    finally:
        if timeout:
            signal.alarm(0)
    records = _function_records(str(path), selected, result)
    return {
        "file": str(path),
        "label": label,
        "start": start,
        "end": end,
        "functions": records,
        "classes": _classes(tree) if start is None and end is None else [],
        "note": result["note"],
        "error": result["error"],
        "units": sorted(set(result["units"])),
        "chosen": sorted(result["chosen"]),
        "rejected": dict(sorted(result["rejected"].items())),
    }


def _file_record(path, chunk_records, error=""):
    functions = []
    classes = []
    notes = []
    units = set()
    chosen = set()
    for record in chunk_records:
        functions.extend(record["functions"])
        classes.extend(record["classes"])
        if record["note"]:
            notes.append(record["note"])
        units.update(record["units"])
        chosen.update(record["chosen"])
    functions.sort(key=lambda item: (item["line"], item["name"]))
    classes.sort(key=lambda item: item["line"])
    methods = sum(len(item["methods"]) for item in classes)
    accepted = sum(1 for item in functions if item["verdict"] == "accept")
    return {
        "path": _relative(path),
        "lines": len(Path(path).read_text(encoding="utf-8").splitlines()),
        "functions": functions,
        "classes": classes,
        "top_level_functions": len(functions),
        "accepted": accepted,
        "rejected": len(functions) - accepted,
        "methods": methods,
        "chunked": len(chunk_records) > 1 or bool(chunk_records and chunk_records[0].get("start")),
        "chunks": [{key: record[key] for key in
                    ("label", "start", "end", "note", "error", "chosen", "rejected")}
                   for record in chunk_records],
        "accepted_names": sorted(chosen),
        "units": sorted(units),
        "note": notes[0] if notes else "",
        "error": error,
    }


def _chunk_ranges(functions, chunk_lines):
    ranges = []
    current = []
    current_start = None
    for node in functions:
        start = _node_start(node)
        span = (getattr(node, "end_lineno", node.lineno) or node.lineno) - start + 1
        if current and (start - current_start) > chunk_lines:
            ranges.append((current_start, current[-1][1]))
            current = []
        if not current:
            current_start = start
        current.append((node, getattr(node, "end_lineno", node.lineno) or node.lineno))
    if current:
        ranges.append((current_start, current[-1][1]))
    return ranges


def classify_chunked(path, timeout, chunk_lines):
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = _top_level(tree)
    if not functions:
        return [_file_record(path, [classify_file(path, timeout=timeout)])]
    records = []
    covered = set()
    for start, end in _chunk_ranges(functions, chunk_lines):
        try:
            record = classify_file(path, start, end, timeout=timeout)
        except _Timeout:
            record = {
                "file": str(path), "label": "%s:%s-%s" % (path.name, start, end),
                "start": start, "end": end,
                "functions": [{
                    "file": str(path), "name": node.name, "line": node.lineno,
                    "length": (getattr(node, "end_lineno", node.lineno) or node.lineno)
                              - node.lineno + 1,
                    "verdict": "reject", "reason": "chunk timed out after %ss" % timeout,
                } for node in functions if start <= node.lineno <= end],
                "classes": [], "note": "", "error": "timeout",
                "units": [], "chosen": [], "rejected": {},
            }
        records.append(record)
        covered.update(node.name for node in functions if start <= node.lineno <= end)
    missing = [node for node in functions if node.name not in covered]
    if missing:
        fake = {"chosen": {}, "rejected": {}, "units": [], "facts": set(),
                "note": "", "error": "not covered by a chunk"}
        records.append({
            "file": str(path), "label": "%s:missing" % path.name, "start": None, "end": None,
            "functions": _function_records(str(path), missing, fake),
            "classes": [], "note": "", "error": "not covered by a chunk",
            "units": [], "chosen": [], "rejected": {},
        })
    return records


def _preexec():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (OSError, ValueError):
        pass


def _run_child(arguments, timeout):
    command = [sys.executable, "-B", str(Path(__file__).resolve()), *arguments]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, preexec_fn=_preexec, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        process.communicate()
        return None, "timeout"
    if process.returncode:
        return None, (stderr or stdout or "exit %d" % process.returncode)[-800:]
    try:
        return json.loads(stdout), ""
    except ValueError:
        return None, (stdout or stderr or "no JSON")[-800:]


def _census_one(task):
    path, timeout, chunk_lines, chunk = task
    if chunk:
        return classify_chunked(path, timeout, chunk_lines)
    record = classify_file(path, timeout=timeout)
    return [record]


def _spawn_census(task):
    path, timeout, chunk_lines, chunk = task
    arguments = ["--one", str(path), "--timeout", str(timeout)]
    if chunk:
        arguments += ["--chunk", "--chunk-lines", str(chunk_lines)]
    return path, _run_child(arguments, timeout), chunk


def run_all(paths, timeout, chunk_lines, jobs):
    tasks = [(str(Path(path)), timeout, chunk_lines, False) for path in paths]
    with multiprocessing.Pool(max(1, min(2, jobs))) as pool:
        first = list(pool.imap_unordered(_spawn_census, tasks))
    records = []
    for path, (payload, error), _chunked in first:
        if payload is None and error == "timeout":
            try:
                chunks = classify_chunked(path, timeout, chunk_lines)
            except BaseException as failure:
                chunks = [_file_record(path, [], error="chunking failed: %s" % failure)]
            records.append(_file_record(path, chunks))
        elif payload is None:
            records.append(_file_record(path, [], error=error))
        else:
            records.extend(payload if isinstance(payload, list) else [payload])
    records.sort(key=lambda item: item["path"])
    functions = [item for record in records for item in record["functions"]]
    accepted = sum(1 for item in functions if item["verdict"] == "accept")
    return {
        "schema": SCHEMA,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "root": str(ROOT),
        "timeout_seconds": timeout,
        "chunk_lines": chunk_lines,
        "files": records,
        "totals": {
            "files": len(records),
            "top_level_functions": len(functions),
            "accepted": accepted,
            "rejected": len(functions) - accepted,
            "methods": sum(record["methods"] for record in records),
            "chunked_files": sum(1 for record in records if record["chunked"]),
            "error_files": sum(1 for record in records if record["error"]),
        },
    }


def _summary(census):
    totals = census["totals"]
    print("files %(files)d  functions %(top_level_functions)d  accepted %(accepted)d  "
          "rejected %(rejected)d  methods %(methods)d  chunked %(chunked_files)d  "
          "errors %(error_files)d" % totals)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="*")
    parser.add_argument("--one", action="store_true", help="classify one file and print JSON")
    parser.add_argument("--run-all", action="store_true", help="run one child per file")
    parser.add_argument("--out", help="write the census JSON here")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--chunk-lines", type=int, default=DEFAULT_CHUNK_LINES)
    parser.add_argument("--chunk", action="store_true", help="classify in line-range chunks")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--summary", help="print totals from an existing census")
    args = parser.parse_args(argv)

    if args.summary:
        census = json.loads(Path(args.summary).read_text(encoding="utf-8"))
        _summary(census)
        return 0
    if not args.files:
        parser.error("give at least one FILE")
    if args.one:
        path = args.files[0]
        if args.chunk:
            payload = [_file_record(path, classify_chunked(path, args.timeout, args.chunk_lines))]
        else:
            payload = [_file_record(path, [classify_file(path, args.start, args.end,
                                                         timeout=args.timeout)])]
        text = json.dumps(payload, indent=2, sort_keys=True)
        if args.out:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
        else:
            print(text)
        return 0
    if args.chunk:
        payload = [_file_record(path, classify_chunked(path, args.timeout, args.chunk_lines))
                   for path in args.files]
        census = {
            "schema": SCHEMA,
            "files": payload,
            "totals": {
                "files": len(payload),
                "top_level_functions": sum(item["top_level_functions"] for item in payload),
                "accepted": sum(item["accepted"] for item in payload),
                "rejected": sum(item["rejected"] for item in payload),
                "methods": sum(item["methods"] for item in payload),
                "chunked_files": sum(1 for item in payload if item["chunked"]),
                "error_files": sum(1 for item in payload if item["error"]),
            },
        }
    elif args.run_all:
        census = run_all(args.files, args.timeout, args.chunk_lines, args.jobs)
    else:
        payload = [_file_record(path, [classify_file(path, timeout=args.timeout)])
                   for path in args.files]
        census = {
            "schema": SCHEMA,
            "files": payload,
            "totals": {
                "files": len(payload),
                "top_level_functions": sum(item["top_level_functions"] for item in payload),
                "accepted": sum(item["accepted"] for item in payload),
                "rejected": sum(item["rejected"] for item in payload),
                "methods": sum(item["methods"] for item in payload),
                "chunked_files": sum(1 for item in payload if item["chunked"]),
                "error_files": sum(1 for item in payload if item["error"]),
            },
        }
    text = json.dumps(census, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    _summary(census)
    return 0


if __name__ == "__main__":
    sys.exit(main())
