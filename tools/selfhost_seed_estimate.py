#!/usr/bin/env python3
"""Estimate the size of the C seed a self-hosting AIL compiler would commit.

    python3 tools/selfhost_seed_estimate.py --run --jobs 2
    python3 tools/selfhost_seed_estimate.py --report-only
    python3 tools/selfhost_seed_estimate.py --write-md lab/selfhost/SEED.md

``--run`` builds a corpus of programs that build today (default mode, ``--debug-dir``) and
records, per program: source lines without blank and comment lines, AST node count, top-level
functions and classes, typed/general path, generated ``program.c`` bytes, its gzip size and the
stripped binary bytes.  Two bare programs (one typed, one general) give the fixed runtime part.

``--report-only`` reads the corpus JSON, subtracts the fixed runtime part, fits C bytes per AST
node and per source line through the origin (separately for typed and general builds), and prints
the low/mid/high estimates as JSON.  It builds nothing.  The compiler's own lines and AST nodes
(over the scope of ``lab/selfhost/CENSUS.md``, never compiled) are part of the corpus, recorded
by ``--run``, so a later compiler edit does not silently change the committed estimate.

Measurement only: no compiler file is edited.  Builds run under a 1.5 GB address-space limit and
at most two at a time.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import gzip
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AIL = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
CORPUS = ROOT / "lab" / "selfhost" / "seed_corpus.json"
SEED_MD = ROOT / "lab" / "selfhost" / "SEED.md"
SCHEMA = "ail.selfhost_seed/1"
MEMORY_LIMIT = 1500 * 1024 * 1024
BUILD_TIMEOUT = 900

# Programs that build today, chosen across the four named trees plus the compare labs.  The
# stdlib entries import a bundled module (shlex, stat, quopri, keyword, sched, difflib, tomllib,
# colorsys, getopt, token) so the measurement sees bundled-module code too.
CANDIDATES = (
    "examples/mdlite/mdlite.py",
    "examples/mdlite/make_big.py",
    "examples/algos/run.py",
    "examples/algos/rpn.py",
    "examples/algos/sudoku.py",
    "examples/algos/huffman.py",
    "examples/algos/lcs.py",
    "examples/algos/levenshtein.py",
    "examples/algos/dijkstra.py",
    "examples/algos/life.py",
    "examples/algos/knapsack.py",
    "examples/algos/mandelbrot.py",
    "examples/algos/topo.py",
    "examples/algos/wordfreq.py",
    "examples/textcli/csvcut.py",
    "examples/textcli/tsort.py",
    "examples/textcli/uniqc.py",
    "examples/textcli/gen_big.py",
    "lab/compare/src/berth_sim/typed.py",
    "lab/compare/src/berth_sim/main.py",
    "lab/compare/src/chain_relax/typed.py",
    "lab/compare/src/chain_relax/main.py",
    "lab/compare/src/echo_pack/typed.py",
    "lab/compare/src/echo_pack/main.py",
    "lab/compare/src/ledger_bin/typed.py",
    "lab/compare/src/ledger_bin/main.py",
    "lab/compare/src/rail_transfer/typed.py",
    "lab/compare/src/rail_transfer/main.py",
    "lab/compare/src/scar_life/typed.py",
    "lab/compare/src/scar_life/main.py",
    "lab/compare/src/tally_lang/typed.py",
    "lab/compare/src/tally_lang/main.py",
    "lab/compare/src/term_rank/typed.py",
    "lab/compare/src/term_rank/main.py",
    "lab/compare/src/ticket_audit/typed.py",
    "lab/compare/src/ticket_audit/main.py",
    "lab/compare/src/tree_fold/typed.py",
    "lab/compare/src/tree_fold/main.py",
    "lab/compare_cand/src/csv_rollup/typed.py",
    "lab/compare_cand/src/csv_rollup/main.py",
    "lab/compare_cand/src/log_scan/typed.py",
    "lab/compare_cand/src/log_scan/main.py",
    "lab/compare_cand/src/tsv_join/typed.py",
    "lab/compare_cand/src/tsv_join/main.py",
    "lab/stdlib/tomllib/06_config.py",
    "lab/stdlib/shlex/12_shell_tokens.py",
    "lab/stdlib/stat/12_permission_report.py",
    "lab/stdlib/keyword/05_identifier_checker.py",
    "lab/stdlib/sched/08_exception_then_resume.py",
    "lab/stdlib/difflib/11_diff_bytes.py",
    "lab/stdlib/quopri/10_large.py",
    "lab/stdlib/colorsys/bench_pixels.py",
    "lab/stdlib/getopt/08_errors_long.py",
    "lab/stdlib/token/12_token_table.py",
)

BARE_TYPED = 'print("ok")\n'
BARE_GENERAL = 'def main(x):\n    print("ok", x)\n\nmain([1, 2])\n'

# Scope of lab/selfhost/CENSUS.md: every pkg-v12 module plus the three top-level compiler sources.
COMPILER_GLOB = "AIL_CURRENT/python/pkg-v12/*.py"
COMPILER_EXTRA = ("AIL_CURRENT/ail_chatgpt.py", "AIL_CURRENT/ail_syntax.py",
                  "AIL_CURRENT/ail_modules.py")


def _source_stats(text):
    """Lines that are neither blank nor whole-line comments; AST nodes; top-level defs/classes."""
    lines = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            lines += 1
    tree = ast.parse(text)
    nodes = sum(1 for _ in ast.walk(tree))
    functions = sum(1 for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    classes = sum(1 for node in tree.body if isinstance(node, ast.ClassDef))
    return {"lines": lines, "ast_nodes": nodes, "top_functions": functions,
            "top_classes": classes}


def _limit():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (OSError, ValueError):
        pass


def _build(source, workdir, label):
    """Compile one source in the default mode and measure the C and stripped binary."""
    out = workdir / (label + ".bin")
    debug = workdir / (label + ".dbg")   # must not exist: --debug-dir makes a new directory
    command = [sys.executable, "-B", str(AIL), "compile", str(source),
               "-o", str(out), "--debug-dir", str(debug)]
    started = time.time()
    try:
        done = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                              preexec_fn=_limit, timeout=BUILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "timeout after %ds" % BUILD_TIMEOUT, ""
    stderr = done.stderr or ""
    if done.returncode != 0:
        return None, stderr.strip().splitlines()[-1][:400] if stderr.strip() else \
            "exit %d" % done.returncode, stderr
    program_c = debug / "program.c"
    if not program_c.is_file():
        return None, "no program.c", stderr
    stripped = workdir / (label + ".stripped")
    strip = subprocess.run(["strip", "-o", str(stripped), str(out)],
                           capture_output=True, text=True)
    if strip.returncode != 0:
        return None, "strip failed: %s" % strip.stderr.strip()[:200], stderr
    return {
        "c_bytes": program_c.stat().st_size,
        "c_gzip_bytes": len(gzip.compress(program_c.read_bytes(), mtime=0)),
        "binary_bytes": stripped.stat().st_size,
        "mode": "general" if "built on the general path" in stderr else "typed",
        "seconds": round(time.time() - started, 3),
    }, "", stderr


def _measure(source, text, workdir, label):
    record = {"path": str(source), "kind": "program"}
    record.update(_source_stats(text))
    built, error, _ = _build(source, workdir, label)
    if built is None:
        return None, {"path": str(source), "error": error}
    record.update(built)
    return record, None


def _bare(source_text, workdir, label, expected):
    path = workdir / (label + ".py")
    path.write_text(source_text, encoding="utf-8")
    record = {"path": "<bare:%s>" % expected, "kind": "fixed", "expected_mode": expected}
    record.update(_source_stats(source_text))
    built, error, _ = _build(path, workdir, label)
    if built is None:
        return None, {"path": record["path"], "error": error}
    record.update(built)
    return record, None


def _one(task):
    kind, source, workdir = task
    workdir = Path(workdir)
    if kind == "bare":
        text, label, expected = source
        single = workdir / (label + ".py")
        single.write_text(text, encoding="utf-8")
        record = {"path": "<bare:%s>" % expected, "kind": "fixed", "expected_mode": expected}
        record.update(_source_stats(text))
        built, error, _ = _build(single, workdir, label)
        if built is None:
            return None, {"path": record["path"], "error": error}
        record.update(built)
        return record, None
    source = Path(source)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as error:
        return None, {"path": str(source), "error": "read: %s" % error}
    try:
        return _measure(source, text, workdir, source.stem + "_" + str(abs(hash(str(source))) % 100000))
    except SyntaxError as error:
        return None, {"path": str(source), "error": "parse: %s" % error}


def run(jobs):
    workdir = Path(tempfile.mkdtemp(prefix="ail-seed-"))
    tasks = []
    for index, name in enumerate(CANDIDATES):
        tasks.append(("program", ROOT / name, workdir / ("p%03d" % index)))
    tasks.append(("bare", (BARE_TYPED, "bare_typed", "typed"), workdir / "bare_typed"))
    tasks.append(("bare", (BARE_GENERAL, "bare_general", "general"), workdir / "bare_general"))
    for _, _, directory in tasks:
        directory.mkdir(parents=True, exist_ok=True)
    rows, fixed, failures = [], [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(2, jobs))) as pool:
        for record, failure in pool.map(_one, tasks):
            if failure is not None:
                failures.append(failure)
            elif record["kind"] == "fixed":
                fixed.append(record)
            else:
                rows.append(record)
    rows.sort(key=lambda item: item["path"])
    fixed.sort(key=lambda item: item["path"])
    failures.sort(key=lambda item: item["path"])
    corpus = {
        "schema": SCHEMA,
        "base_commit": _git_commit(),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memory_limit_bytes": MEMORY_LIMIT,
        "jobs": max(1, min(2, jobs)),
        "rows": rows,
        "fixed": fixed,
        "failures": failures,
        "compiler": _compiler_stats(),
    }
    return corpus


def _git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def _fixed_for(corpus, mode):
    for record in corpus.get("fixed", []):
        if record.get("mode") == mode:
            return record
    return None


def _fit(points, fixed_bytes):
    """Least squares through the origin on (x, y - fixed); uncentered R^2 and median |err|%."""
    xs = [item[0] for item in points]
    ys = [item[1] - fixed_bytes for item in points]
    denominator = sum(x * x for x in xs)
    slope = sum(x * y for x, y in zip(xs, ys)) / denominator if denominator else 0.0
    residuals = [y - slope * x for x, y in zip(xs, ys)]
    total = sum(y * y for y in ys)
    r2 = 1.0 - sum(r * r for r in residuals) / total if total else 1.0
    errors = []
    for x, actual in zip(xs, [item[1] for item in points]):
        predicted = slope * x + fixed_bytes
        if actual:
            errors.append(abs(predicted - actual) / actual * 100.0)
    errors.sort()
    if errors:
        middle = len(errors) // 2
        mae = errors[middle] if len(errors) % 2 else (errors[middle - 1] + errors[middle]) / 2
    else:
        mae = 0.0
    return {"slope": round(slope, 6), "r2": round(r2, 6), "median_abs_error_pct": round(mae, 3),
            "n": len(points)}


def _worst_decile(points, fixed_bytes):
    """Mean bytes per AST node of the worst tenth (the general path's pessimistic ratio)."""
    ratios = sorted(((item[1] - fixed_bytes) / item[0] for item in points if item[0]), reverse=True)
    if not ratios:
        return 0.0
    count = max(1, len(ratios) // 10)
    return sum(ratios[:count]) / count


def _compiler_stats():
    paths = sorted(ROOT.glob(COMPILER_GLOB)) + [ROOT / name for name in COMPILER_EXTRA]
    total = {"files": 0, "lines": 0, "ast_nodes": 0, "top_functions": 0, "top_classes": 0}
    for path in paths:
        stats = _source_stats(path.read_text(encoding="utf-8"))
        total["files"] += 1
        for key in ("lines", "ast_nodes", "top_functions", "top_classes"):
            total[key] += stats[key]
    return total


def report(corpus):
    typed = [item for item in corpus["rows"] if item["mode"] == "typed"]
    general = [item for item in corpus["rows"] if item["mode"] == "general"]
    fixed_typed = _fixed_for(corpus, "typed")
    fixed_general = _fixed_for(corpus, "general")
    if fixed_typed is None or fixed_general is None:
        raise SystemExit("corpus has no fixed typed/general bare build")
    fits = {}
    for name, rows, fixed in (("typed", typed, fixed_typed),
                              ("general", general, fixed_general)):
        node = [(item["ast_nodes"], item["c_bytes"]) for item in rows]
        line = [(item["lines"], item["c_bytes"]) for item in rows]
        binary_node = [(item["ast_nodes"], item["binary_bytes"]) for item in rows]
        binary_line = [(item["lines"], item["binary_bytes"]) for item in rows]
        fits[name] = {
            "c_per_node": _fit(node, fixed["c_bytes"]),
            "c_per_line": _fit(line, fixed["c_bytes"]),
            "binary_per_node": _fit(binary_node, fixed["binary_bytes"]),
            "binary_per_line": _fit(binary_line, fixed["binary_bytes"]),
            "worst_decile_c_per_node": round(_worst_decile(node, fixed["c_bytes"]), 6),
            "worst_decile_binary_per_node": round(
                _worst_decile(binary_node, fixed["binary_bytes"]), 6),
            "fixed_c_bytes": fixed["c_bytes"],
            "fixed_binary_bytes": fixed["binary_bytes"],
        }
    compiler = corpus.get("compiler")
    if not compiler:
        raise SystemExit("corpus has no compiler stats; re-run --run to record them")
    nodes = compiler["ast_nodes"]
    lines = compiler["lines"]

    def best(mode, metric):
        candidates = (("per_node", fits[mode][metric + "_per_node"]),
                      ("per_line", fits[mode][metric + "_per_line"]))
        return max(candidates, key=lambda item: item[1]["r2"])

    chosen = {metric: {"typed": best("typed", metric), "general": best("general", metric)}
              for metric in ("c", "binary")}

    def value(mode, metric):
        unit, fit = chosen[metric][mode]
        count = nodes if unit == "per_node" else lines
        return fit["slope"] * count + (fixed_typed if mode == "typed" else fixed_general)[
            metric + "_bytes"]

    typed_nodes = sum(item["ast_nodes"] for item in typed)
    general_nodes = sum(item["ast_nodes"] for item in general)
    total_nodes = typed_nodes + general_nodes
    mix_typed = typed_nodes / total_nodes if total_nodes else 0.0
    mix_general = 1.0 - mix_typed

    estimates = {}
    for metric in ("c", "binary"):
        low = value("typed", metric)
        high = fits["general"]["worst_decile_" + metric + "_per_node"] * nodes + \
            fixed_general[metric + "_bytes"]
        mid = (mix_typed * value("typed", metric) +
               mix_general * value("general", metric))
        estimates[metric + "_bytes"] = {"low": int(round(low)), "mid": int(round(mid)),
                                        "high": int(round(high))}
    total_c = sum(item["c_bytes"] for item in corpus["rows"])
    total_gzip = sum(item["c_gzip_bytes"] for item in corpus["rows"])
    gzip_ratio = total_gzip / total_c if total_c else 0.0
    gzip_estimates = {key: int(round(value * gzip_ratio))
                      for key, value in estimates["c_bytes"].items()}
    return {
        "schema": SCHEMA,
        "corpus": {
            "rows": len(corpus["rows"]),
            "failures": len(corpus.get("failures", [])),
            "typed": len(typed),
            "general": len(general),
            "typed_ast_nodes": typed_nodes,
            "general_ast_nodes": general_nodes,
            "typed_share_by_nodes": round(mix_typed, 4),
            "c_bytes": total_c,
            "c_gzip_bytes": total_gzip,
            "gzip_ratio": round(gzip_ratio, 6),
            "source_lines_total": sum(item["lines"] for item in corpus["rows"]),
            "ast_nodes_total": sum(item["ast_nodes"] for item in corpus["rows"]),
        },
        "fixed": {
            "typed": {"c_bytes": fixed_typed["c_bytes"],
                      "binary_bytes": fixed_typed["binary_bytes"]},
            "general": {"c_bytes": fixed_general["c_bytes"],
                        "binary_bytes": fixed_general["binary_bytes"]},
        },
        "fits": fits,
        "chosen": {metric: {mode: {"unit": unit, "slope": fit["slope"], "r2": fit["r2"],
                                   "median_abs_error_pct": fit["median_abs_error_pct"]}
                            for mode, (unit, fit) in modes.items()}
                   for metric, modes in chosen.items()},
        "compiler": compiler,
        "estimates": {
            "c_bytes": estimates["c_bytes"],
            "gzip_bytes": gzip_estimates,
            "binary_bytes": estimates["binary_bytes"],
        },
        "reference": {
            "github_file_limit_bytes": 100 * 1000 * 1000,
            "python_source_lines": 205201,
        },
    }


def _fmt(value):
    return format(value, ",")


def _write_md(payload, path, corpus_json):
    summary = payload["corpus"]
    rows = corpus_json["rows"]
    compiler = payload["compiler"]
    fits = payload["fits"]
    est = payload["estimates"]
    chosen = payload["chosen"]
    limit = payload["reference"]["github_file_limit_bytes"]
    lines = []
    add = lines.append
    add("# Estimate of the committed C seed")
    add("")
    add("Measured on `%s` (base commit `%s`). Measurement only: no compiler source was edited."
        % (time.strftime("%Y-%m-%d"), payload.get("base_commit", "")))
    add("")
    add("The self-hosting plan commits the generated C of the AIL-written compiler so a user can")
    add("build AIL with only a C compiler. This estimates how large that C seed would be, from a")
    add("corpus of programs that build today.")
    add("")
    add("## Corpus")
    add("")
    add("%d programs built (plus the two bare builds); %d failed to build and are listed only in"
        % (summary["rows"], summary["failures"]))
    add("`seed_corpus.json`. %d built on the typed path and %d on the general path; by AST nodes the"
        % (summary["typed"], summary["general"]))
    add("mix is %.1f%% typed / %.1f%% general." %
        (100 * summary["typed_share_by_nodes"], 100 * (1 - summary["typed_share_by_nodes"])))
    add("")
    add("| mode | programs | AST nodes | C bytes | gzip bytes | binary bytes (stripped) |")
    add("|------|----------|-----------|---------|------------|--------------------------|")
    for mode in ("typed", "general"):
        selected = [item for item in rows if item["mode"] == mode]
        add("| %s | %d | %d | %s | %s | %s |" % (
            mode, len(selected), sum(item["ast_nodes"] for item in selected),
            _fmt(sum(item["c_bytes"] for item in selected)),
            _fmt(sum(item["c_gzip_bytes"] for item in selected)),
            _fmt(sum(item["binary_bytes"] for item in selected))))
    add("")
    add("Fixed runtime part (bare build, subtracted before every fit): typed C %s bytes / binary"
        % _fmt(payload["fixed"]["typed"]["c_bytes"]))
    add("%s bytes; general C %s bytes / binary %s bytes." %
        (_fmt(payload["fixed"]["typed"]["binary_bytes"]),
         _fmt(payload["fixed"]["general"]["c_bytes"]),
         _fmt(payload["fixed"]["general"]["binary_bytes"])))
    add("")
    add("## Fits (least squares through the origin)")
    add("")
    add("| model | slope | R^2 | median abs error |")
    add("|-------|-------|-----|------------------|")
    for mode in ("typed", "general"):
        for key, label in (("c_per_node", mode + " C per AST node"),
                           ("c_per_line", mode + " C per source line"),
                           ("binary_per_node", mode + " binary per AST node"),
                           ("binary_per_line", mode + " binary per source line")):
            fit = fits[mode][key]
            add("| %s | %.2f | %.3f | %.1f%% |" % (label, fit["slope"], fit["r2"],
                                                   fit["median_abs_error_pct"]))
    add("")
    add("The general per-line C fit is weak (R^2 %.3f); the per-node fit is used where it is"
        % fits["general"]["c_per_line"]["r2"])
    add("the better one. The worst-decile ratio is dominated by the small stdlib programs, whose")
    add("generated C carries per-module glue the bare build does not include, so it is a bound.")
    add("")
    add("The estimate uses the better-fitting unit per mode and metric (C: typed %s, general %s;"
        % (chosen["c"]["typed"]["unit"], chosen["c"]["general"]["unit"]))
    add("binary: typed %s, general %s)." % (chosen["binary"]["typed"]["unit"],
                                            chosen["binary"]["general"]["unit"]))
    add("")
    add("## Compiler scope (counted with `ast`, never compiled)")
    add("")
    add("`AIL_CURRENT/python/pkg-v12/*.py` plus `ail_chatgpt.py`, `ail_syntax.py` and")
    add("`ail_modules.py`: %d files, %s source lines (no blank/comment lines), %s AST nodes,"
        % (compiler["files"], _fmt(compiler["lines"]), _fmt(compiler["ast_nodes"])))
    add("%s top-level functions." % _fmt(compiler["top_functions"]))
    add("")
    add("## Estimates")
    add("")
    add("| bytes | low (all typed, best fit) | mid (corpus typed/general mix) | high (all general, worst decile) |")
    add("|-------|---------------------------|-------------------------------|----------------------------------|")
    for key, label in (("c_bytes", "C source"), ("gzip_bytes", "C gzipped"),
                       ("binary_bytes", "binary, stripped")):
        row = est[key]
        add("| %s | %s | %s | %s |" % (label, _fmt(row["low"]), _fmt(row["mid"]),
                                      _fmt(row["high"])))
    add("")
    add("The gzip estimate applies the corpus ratio %.3f (gzip bytes / C bytes) to the C estimate."
        % summary["gzip_ratio"])
    add("")
    add("## How the numbers compare")
    add("")
    for key, label in (("c_bytes", "C source"), ("gzip_bytes", "gzipped C"),
                       ("binary_bytes", "binary")):
        row = est[key]
        add("- %s: low %.1f MB, mid %.1f MB, high %.1f MB; mid is %.2fx GitHub's 100 MB file"
            % (label, row["low"] / 1e6, row["mid"] / 1e6, row["high"] / 1e6,
               row["mid"] / limit))
        add("  limit and high is %.2fx it." % (row["high"] / limit))
    add("- The mid C estimate (%.1f MB) does not fit GitHub's 100 MB file limit as one file; the"
        % (est["c_bytes"]["mid"] / 1e6))
    add("  gzipped mid estimate (%.1f MB) does, so committing the C gzipped or split into files is"
        % (est["gzip_bytes"]["mid"] / 1e6))
    add("  required by the mid case, and the high case fits neither.")
    add("- Today's Python sources of the compiler are %s lines in %d files; the C seed's mid"
        % (_fmt(payload["reference"]["python_source_lines"]), compiler["files"]))
    add("  estimate is %.1f bytes per Python source line."
        % (est["c_bytes"]["mid"] / payload["reference"]["python_source_lines"]))
    add("")
    add("## What could make this wrong")
    add("")
    largest = max((item["ast_nodes"] for item in rows), default=0)
    add("- The corpus is small (%d programs) and much smaller than the compiler: the largest row is"
        % summary["rows"])
    add("  %s AST nodes against %s for the compiler. The fit is a per-node ratio, so a compiler"
        % (_fmt(largest), _fmt(compiler["ast_nodes"])))
    add("  that emits disproportionately more C per node (long functions, many string literals,")
    add("  large constant tables) lands above it.")
    add("- The corpus is written for AIL's current subset. A self-hosting compiler is one huge")
    add("  module with module-level state and many small helpers; C emitted per AST node for a")
    add("  program of 200k lines may differ from small programs because the runtime is shared.")
    add("- The self-hosted compiler is not written yet, so its AST node count is the Python")
    add("  compiler's. A different implementation or AST shape moves the estimate directly.")
    add("- The typed/general mix is unknown before the rewrite. The low estimate assumes the whole")
    add("  compiler becomes typed code; the high estimate uses the general path's worst decile")
    add("  ratio, which is a deliberately pessimistic bound, not a prediction.")
    add("- Generated C is counted once per program. The real seed links the compiler's own modules")
    add("  plus the C runtime; duplicates of the runtime across translation units are not modeled.")
    add("")
    add("<!-- estimates: %s -->" % json.dumps(est, sort_keys=True, separators=(",", ":")))
    add("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", action="store_true", help="build the corpus and write the JSON")
    parser.add_argument("--report-only", action="store_true", help="fit and estimate from the JSON")
    parser.add_argument("--write-md", help="write the report markdown here")
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--out", default=str(CORPUS))
    args = parser.parse_args(argv)

    if args.run:
        corpus = run(args.jobs)
        Path(args.out).write_text(json.dumps(corpus, indent=2, sort_keys=True) + "\n",
                                  encoding="utf-8")
        print("rows %d  fixed %d  failures %d" %
              (len(corpus["rows"]), len(corpus["fixed"]), len(corpus["failures"])))
        if corpus["failures"]:
            for failure in corpus["failures"]:
                print("failed: %s: %s" % (failure["path"], failure["error"]))
        return 0 if len(corpus["rows"]) >= 25 else 1

    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    payload = report(corpus)
    payload["base_commit"] = corpus.get("base_commit", "")
    if args.write_md:
        _write_md(payload, Path(args.write_md), corpus)
    print(json.dumps(payload["estimates"], indent=2, sort_keys=True))
    if args.write_md:
        print("wrote %s" % args.write_md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
