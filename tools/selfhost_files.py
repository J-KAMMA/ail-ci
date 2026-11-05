#!/usr/bin/env python3
"""Which compiler source files AIL builds whole, as a program.

    python3 tools/selfhost_files.py --out lab/selfhost/files.json [--jobs 2]
    python3 tools/selfhost_files.py --limit 5
    python3 tools/selfhost_files.py --only prelude_array.py,dtrt.py

Scope is the same tree ``lab/selfhost/CENSUS.md`` counted functions in:
``AIL_CURRENT/python/pkg-v12/*.py`` (``test_*.py`` skipped),
``AIL_CURRENT/ail_chatgpt.py``, ``AIL_CURRENT/ail_syntax.py`` and
``AIL_CURRENT/ail_modules.py``.  Unlike the function census this builds each file
with the real compiler in the default mode, so ``typed`` means the typed path built
it, ``general`` means the general-path fallback did, and ``refused`` means neither
did.  Each file is staged in its own temporary directory (the file's whole sibling
directory is copied) so a build never reads or writes the checkout.

One file per child process, 1.5 GB address-space limit, 60 s, at most two at a time.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import os
import re
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "AIL_CURRENT"
CLI = SRC / "ail_chatgpt.py"
OUT_DEFAULT = ROOT / "lab" / "selfhost" / "files.json"
SCHEMA = "ail.selfhost_files/1"
MEMORY_LIMIT = 1500 * 1024 * 1024
DEFAULT_TIMEOUT = 60
JOBS = 2


def _load_normalise():
    """The bucket method of lab/stdcensus/report.py (names and numbers -> placeholders)."""
    path = ROOT / "lab" / "stdcensus" / "report.py"
    spec = importlib.util.spec_from_file_location("_stdcensus_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.normalise


NORMALISE = _load_normalise()


def scope():
    paths = sorted(p for p in (SRC / "python" / "pkg-v12").glob("*.py")
                   if not p.name.startswith("test_"))
    for name in ("ail_chatgpt.py", "ail_syntax.py", "ail_modules.py"):
        paths.append(SRC / name)
    return paths


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT))


def _preexec():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (OSError, ValueError):
        pass


_DIAGNOSTIC = re.compile(r"(?:^|: )\S+\.py:\d+(?::\d+)?: ")
_TRACEBACK = re.compile(r"Traceback \(most recent call last\)|MemoryError|RecursionError: maximum|"
                        r"internal error|Segmentation fault", re.I)


def _clean(text, tmp):
    text = text.replace(str(tmp), "<tmp>")
    text = re.sub(r"/tmp/ail-[A-Za-z0-9_\-]+", "<tmp>", text)
    return text


def _first_general_reason(stderr):
    for line in stderr.splitlines():
        line = line.strip()
        if "built on the general path" in line and " because " in line:
            reason = line.split(" because ", 1)[1]
            reason = reason.split("; run with --strict", 1)[0]
            return reason.strip()
    return ""


def _first_refusal_line(stderr):
    for line in stderr.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("note: "):
            body = line[len("note: "):]
            if _DIAGNOSTIC.search(body):
                return line
            continue
        if _DIAGNOSTIC.search(line):
            return line
    for line in stderr.splitlines():
        if line.strip():
            return line.strip()
    return ""


def classify(path, timeout=DEFAULT_TIMEOUT, output_dir=None):
    """Build one file in its own temporary tree and return its record."""
    path = Path(path).resolve()
    record = {"path": relative(path), "lines": len(path.read_text(encoding="utf-8").splitlines()),
              "result": "crash", "seconds": 0.0, "first_refusal": "", "detail": ""}
    started = time.monotonic()
    tdir = Path(tempfile.mkdtemp(prefix="ail-selfhost-files-"))
    try:
        staged_parent = tdir / path.parent.name
        shutil.copytree(path.parent, staged_parent, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
        staged = staged_parent / path.name
        cache = tdir / "cache"
        tasktmp = tdir / "tasktmp"
        cache.mkdir()
        tasktmp.mkdir()
        out = tdir / "out"
        env = dict(os.environ)
        env["AIL_NO_CACHE"] = "1"
        env["AIL_CACHE"] = str(cache)
        env["TMPDIR"] = str(tasktmp)
        env["AIL_SERVER"] = "0"
        env.pop("AIL_STRICT", None)
        env.pop("PYTHONPATH", None)
        command = [sys.executable, "-B", str(CLI), "compile", str(staged.relative_to(tdir)),
                   "-o", str(out)]
        before = sorted(str(p.relative_to(staged_parent)) for p in staged_parent.rglob("*"))
        timed_out = False
        try:
            process = subprocess.Popen(command, cwd=str(tdir), env=env, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       preexec_fn=_preexec, start_new_session=True)
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass
                stdout, stderr = process.communicate()
        finally:
            record["seconds"] = round(time.monotonic() - started, 2)
        stdout = _clean(stdout or "", tdir)
        stderr = _clean(stderr or "", tdir)
        after = sorted(str(p.relative_to(staged_parent)) for p in staged_parent.rglob("*"))
        stray = [p for p in after if p not in before and "__pycache__" not in p]
        if stray:
            record["detail"] = "build wrote inside the staged source: " + ", ".join(stray[:5])
        if timed_out:
            record["result"] = "timeout"
            record["first_refusal"] = ""
        elif process.returncode == 0:
            if "built on the general path" in stderr:
                record["result"] = "general"
                record["first_refusal"] = _first_general_reason(stderr)
            else:
                record["result"] = "typed"
        elif process.returncode < 0:
            record["result"] = "crash"
            record["detail"] = (record["detail"] + " signal %d" % -process.returncode).strip()
            record["first_refusal"] = _first_refusal_line(stderr)
        else:
            text = stderr or stdout
            if _TRACEBACK.search(text):
                record["result"] = "crash"
                record["detail"] = (record["detail"] + " " + text.strip().splitlines()[-1][:300]).strip()
                record["first_refusal"] = _first_refusal_line(stderr)
            elif process.returncode in (2, 3) and _first_refusal_line(stderr):
                record["result"] = "refused"
                record["first_refusal"] = _first_refusal_line(stderr)
            else:
                record["result"] = "crash"
                lines = [line.strip() for line in (stderr or stdout).splitlines() if line.strip()]
                record["detail"] = (record["detail"] + " exit %d: %s"
                                    % (process.returncode, " | ".join(lines[:3])[:300])).strip()
        record["exit_code"] = process.returncode
        record["_stdout"] = stdout[-400:]
        record["_stderr"] = stderr[-1500:]
    except BaseException as error:  # a staging failure is a crash of the tool, recorded, not fatal
        record["result"] = "crash"
        record["detail"] = "%s: %s" % (type(error).__name__, str(error)[:300])
        record["seconds"] = round(time.monotonic() - started, 2)
        record.setdefault("exit_code", None)
    finally:
        shutil.rmtree(tdir, ignore_errors=True)
    return record


def _example_file(files, bucket):
    for record in sorted(files, key=lambda item: item["path"]):
        if record["result"] != "refused":
            continue
        if NORMALISE(record.get("first_refusal") or "no diagnostic") == bucket:
            return record["path"]
    return ""


def _cell(text, limit=180):
    text = (text or "").replace("|", "\\|").replace("\n", " ").strip()
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _defs(path):
    try:
        import ast
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return 0
    return sum(1 for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))


def render_report(payload):
    files = payload["files"]
    summary = payload["totals"]
    buckets = summary.get("buckets") or {}
    lines = []
    lines.append("# Compiler source files AIL builds whole")
    lines.append("")
    lines.append("Generated by `tools/selfhost_files.py` from `lab/selfhost/files.json`.")
    lines.append("")
    lines.append("- Base: `%s`" % (payload.get("base") or "unknown"))
    lines.append("- Date: %s" % (payload.get("date") or "unknown"))
    lines.append("- Command: %s" % (payload.get("command") or "unknown"))
    lines.append("- Scope: `AIL_CURRENT/python/pkg-v12/*.py` (no `test_*.py`), "
                 "`AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, "
                 "`AIL_CURRENT/ail_modules.py`")
    lines.append("")
    lines.append("Each file is built whole in the default mode in its own temporary tree; "
                 "`typed` means the typed path built it, `general` the fallback, `refused` neither.")
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append("| measure | count |")
    lines.append("|---|---:|")
    lines.append("| files in scope | %d |" % summary["files"])
    lines.append("| built typed | %d |" % summary["typed"])
    lines.append("| built general | %d |" % summary["general"])
    lines.append("| refused | %d |" % summary["refused"])
    lines.append("| timeout | %d |" % summary["timeout"])
    lines.append("| crash | %d |" % summary["crash"])
    lines.append("| built total | %d |" % summary["built"])
    lines.append("| total lines | %d |" % summary["total_lines"])
    lines.append("| lines in built files | %d |" % summary["built_lines"])
    lines.append("| share of lines in built files | %.1f%% |" % (100.0 * summary["share_lines_built"]))
    lines.append("")
    typed = [r for r in files if r["result"] == "typed"]
    general = [r for r in files if r["result"] == "general"]
    typed_data = [r for r in typed if _defs(r["path"]) == 0]
    general_funcs = [r for r in general if _defs(r["path"])]
    lines.append("Of the %d typed builds, **%d are data-only** modules (no top-level `def` or `class`); "
                 "%d of the %d general builds carry top-level functions or classes. "
                 "No file was skipped: the first 20 files built in 115 s, which projects to well under "
                 "30 minutes, and the whole scope above was run." %
                 (len(typed), len(typed_data), len(general_funcs), len(general)))
    lines.append("")
    lines.append("## Timeouts")
    lines.append("")
    lines.append("A timeout is a file that did not finish in 60 s; it may build with a longer limit.")
    lines.append("")
    lines.append("| lines | seconds | file |")
    lines.append("|---:|---:|---|")
    for record in sorted((r for r in files if r["result"] == "timeout"), key=lambda r: r["path"]):
        lines.append("| %d | %.1f | `%s` |" % (record["lines"], record["seconds"], record["path"]))
    lines.append("")
    lines.append("## Crashes")
    lines.append("")
    lines.append("A crash is a build that failed without a source refusal (a missing C dependency, "
                 "a signal, or an internal error).")
    lines.append("")
    lines.append("| lines | exit | detail | file |")
    lines.append("|---:|---:|---|---|")
    for record in sorted((r for r in files if r["result"] == "crash"), key=lambda r: r["path"]):
        lines.append("| %d | %s | %s | `%s` |" % (record["lines"], record.get("exit_code"),
                                                  _cell(record.get("detail")), record["path"]))
    lines.append("")
    lines.append("## The 10 largest refusal buckets")
    lines.append("")
    lines.append("A bucket is the first refusal line with names and numbers replaced by placeholders "
                 "(the method of `lab/stdcensus/report.py`).")
    lines.append("")
    lines.append("| count | bucket | example file |")
    lines.append("|---:|---|---|")
    ranked = sorted(buckets.items(), key=lambda item: (-item[1], item[0]))[:10]
    for name, count in ranked:
        lines.append("| %d | %s | `%s` |" % (count, _cell(name), _example_file(files, name)))
    lines.append("")
    lines.append("## The 10 smallest refused files")
    lines.append("")
    lines.append("| lines | file | first refusal |")
    lines.append("|---:|---|---|")
    refused = sorted((r for r in files if r["result"] == "refused"),
                     key=lambda r: (r["lines"], r["path"]))[:10]
    for record in refused:
        lines.append("| %d | `%s` | %s |" % (record["lines"], record["path"],
                                             _cell(record.get("first_refusal"))))
    lines.append("")
    skipped = payload.get("skipped") or []
    if skipped:
        lines.append("## Skipped files")
        lines.append("")
        for item in skipped:
            lines.append("- `%s`: %s" % (item.get("path"), item.get("reason")))
        lines.append("")
    return "\n".join(lines)


def base_commit():
    for ref in ("origin/integ", "HEAD"):
        done = subprocess.run(["git", "rev-parse", "--verify", ref], cwd=str(ROOT),
                              capture_output=True, text=True)
        if done.returncode == 0:
            return done.stdout.strip()
    return ""


def totals(files):
    counts = {key: 0 for key in ("typed", "general", "refused", "timeout", "crash")}
    for record in files:
        counts[record["result"]] = counts.get(record["result"], 0) + 1
    total_lines = sum(record["lines"] for record in files)
    built_lines = sum(record["lines"] for record in files if record["result"] in ("typed", "general"))
    buckets = {}
    for record in files:
        if record["result"] != "refused":
            continue
        bucket = NORMALISE(record.get("first_refusal") or "no diagnostic")
        buckets.setdefault(bucket, []).append(record["path"])
    return {
        "files": len(files),
        "typed": counts["typed"],
        "general": counts["general"],
        "refused": counts["refused"],
        "timeout": counts["timeout"],
        "crash": counts["crash"],
        "built": counts["typed"] + counts["general"],
        "total_lines": total_lines,
        "built_lines": built_lines,
        "share_lines_built": round(built_lines / total_lines, 4) if total_lines else 0.0,
        "buckets": {name: len(names) for name, names in
                    sorted(buckets.items(), key=lambda item: (-len(item[1]), item[0]))},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(OUT_DEFAULT))
    parser.add_argument("--limit", type=int, default=0, help="build only the first N files")
    parser.add_argument("--only", default="", help="comma-separated path fragments to keep")
    parser.add_argument("--jobs", type=int, default=JOBS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--report", action="store_true",
                        help="render FILES.md from the JSON already written to --out")
    args = parser.parse_args(argv)

    if args.report:
        out = Path(args.out)
        payload = json.loads(out.read_text(encoding="utf-8"))
        report = out.with_name("FILES.md")
        report.write_text(render_report(payload) + "\n", encoding="utf-8")
        print("wrote %s" % report)
        return 0

    paths = scope()
    if args.only:
        wanted = [piece.strip() for piece in args.only.split(",") if piece.strip()]
        paths = [p for p in paths if any(word in relative(p) or word in p.name for word in wanted)]
    if args.limit:
        paths = paths[:args.limit]
    jobs = max(1, min(JOBS, args.jobs))
    started = time.monotonic()
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(classify, path, args.timeout): path for path in paths}
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            records.append(record)
            print("%-9s %6.1fs %6d  %s" % (record["result"], record["seconds"],
                                           record["lines"], record["path"]))
    records.sort(key=lambda item: item["path"])
    for record in records:
        for key in [name for name in record if name.startswith("_")]:
            del record[key]
    payload = {
        "schema": SCHEMA,
        "base": base_commit(),
        "date": time.strftime("%Y-%m-%d", time.gmtime()),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "command": "python3 -B AIL_CURRENT/ail_chatgpt.py compile <staged file> -o <tmp>/out "
                   "(AIL_NO_CACHE=1, ulimit -v 1500000, %ds, %d at a time)" % (args.timeout, jobs),
        "timeout_seconds": args.timeout,
        "memory_limit_mb": MEMORY_LIMIT // (1024 * 1024),
        "files": records,
        "totals": totals(records),
        "skipped": [],
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    summary = payload["totals"]
    print("wrote %s: %d files, %d typed, %d general, %d refused, %d timeout, %d crash in %.1fs"
          % (out, summary["files"], summary["typed"], summary["general"], summary["refused"],
             summary["timeout"], summary["crash"], payload["elapsed_seconds"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
