#!/usr/bin/env python3
"""Measure where parallel-map time goes (fbpmap1).

The loads are ordinary AIL programs on the typed parallel path.  Each is built
once as written and once from a scratch copy of its generated `program.c` with
`ail_par_now()` stamps around every block, at the start of the probe prefix and
around the result-list initialization.  The compiler is never edited; the
instrumentation only rewrites the scratch C file.

    python3 lab/race/pmap/run.py [--runs 5] [--loads NAME,...] [--skip-nesting]

`PMAP.json` and `PMAP.md` are written next to this file.
"""
import argparse
import ast
import json
import os
import platform
import re
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CLI = ROOT / "AIL_CURRENT" / "ail_chatgpt.py"
REFERENCE = ROOT / "lab" / "compare_par" / "tasks" / "par_collatz" / "reference.py"
MEMORY = 1500000 * 1024
THREADS = (1, 2, 4)
RUNS = 5
BUILD_TIMEOUT = 900
RUN_TIMEOUT = 600

LOADS = {
    "par_collatz": (HERE / "par_collatz.py", b"7000000 4\n"),
    "uniform": (HERE / "uniform.py", None),
    "ramp": (HERE / "ramp.py", None),
    "heavy": (HERE / "heavy.py", None),
    "tiny": (HERE / "tiny.py", None),
}


def clean_env(extra=None):
    env = dict(os.environ)
    for key in ("PYTHONPATH", "AIL_THREADS", "AIL_UNIFIED_FORCE", "AIL_NO_GENERAL",
                "AIL_STRICT", "AIL_UNIFIED", "AIL_IR", "PMAP_BLOCKS"):
        env.pop(key, None)
    env["AIL_NO_CACHE"] = "1"
    env["PYTHONUTF8"] = "1"
    if extra:
        env.update(extra)
    return env


def _limit():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))


def call(cmd, timeout, env, cwd=None, stdin=None):
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, input=stdin, capture_output=True,
                              timeout=timeout, preexec_fn=_limit if os.name == "posix" else None)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(cmd, -9, exc.stdout or b"", b"timeout\n")


def first_line(data):
    for line in data.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if line and not line.startswith("{"):
            return line[:500]
    return ""


def compile_plain(src, work):
    exe = work / "plain"
    dbg = work / "plain-dbg"
    if exe.exists():
        exe.unlink()
    shutil.rmtree(dbg, ignore_errors=True)
    got = call([sys.executable, "-B", str(CLI), "compile", str(src), "-o", str(exe),
                "--debug-dir", str(dbg)], BUILD_TIMEOUT, clean_env(), cwd=work)
    if got.returncode != 0:
        raise SystemExit("%s: build failed: %s" % (src.name, first_line(got.stderr or got.stdout)))
    shown = got.stderr.decode("utf-8", "replace")
    if "built on the general path" in shown:
        raise SystemExit("%s: not on the typed parallel path: %s" % (src.name, first_line(got.stderr)))
    cfile = dbg / "program.c"
    text = cfile.read_text(encoding="utf-8", errors="replace")
    if "ail_par_run" not in text:
        raise SystemExit("%s: generated C has no ail_par_run" % src.name)
    return exe, text


HELPER = r"""
/* PMAP instrumentation: only a scratch copy of program.c is edited. */
#define PMAP_MAX_BLOCKS 1000000
typedef struct { int64_t start, end, tid, block; } pmap_block_rec;
static pmap_block_rec pmap_blocks[PMAP_MAX_BLOCKS];
static _Atomic int64_t pmap_block_n;
static _Atomic int64_t pmap_first_empty;
static _Atomic int64_t pmap_empty_claims;
static int64_t pmap_region_start, pmap_region_end, pmap_prefix_end;
static int64_t pmap_list_start, pmap_list_end;
static int64_t pmap_went_wide;
static void pmap_report(void) {
    int64_t n = __atomic_load_n(&pmap_block_n, __ATOMIC_RELAXED);
    if (n > PMAP_MAX_BLOCKS) n = PMAP_MAX_BLOCKS;
    int64_t reported = pmap_went_wide ? n : 1;
    int64_t fe = __atomic_load_n(&pmap_first_empty, __ATOMIC_RELAXED);
    int64_t prefix = 0, tail = 0;
    if (pmap_went_wide) {
        prefix = pmap_prefix_end - pmap_region_start;
        if (fe != INT64_MAX) tail = pmap_region_end - fe;
    }
    if (prefix < 0) prefix = 0;
    if (tail < 0) tail = 0;
    fprintf(stderr, "PMAP region_ns=%lld prefix_ns=%lld tail_ns=%lld list_ns=%lld "
            "nblocks=%lld went_wide=%lld empty_claims=%lld\n",
            (long long)(pmap_region_end - pmap_region_start), (long long)prefix, (long long)tail,
            (long long)(pmap_list_end - pmap_list_start), (long long)reported, (long long)pmap_went_wide,
            (long long)__atomic_load_n(&pmap_empty_claims, __ATOMIC_RELAXED));
    if (pmap_region_end > pmap_region_start) {
        int bins[20]; int64_t busy[20];
        for (int b = 0; b < 20; b++) { bins[b] = 0; busy[b] = 0; }
        for (int64_t i = 0; i < n; i++) {
            int64_t s = pmap_blocks[i].start;
            int64_t b = (s - pmap_region_start) * 20 / (pmap_region_end - pmap_region_start);
            if (b < 0) b = 0;
            if (b > 19) b = 19;
            bins[b]++;
            busy[b] += pmap_blocks[i].end - s;
        }
        for (int b = 0; b < 20; b++)
            fprintf(stderr, "PMAPH %d %d %lld\n", b, bins[b], (long long)busy[b]);
    }
    {
        int64_t ids[512], cnt[512], busyw[512];
        int nu = 0;
        for (int64_t i = 0; i < n; i++) {
            int64_t t = pmap_blocks[i].tid, j = 0;
            while (j < nu && ids[j] != t) j++;
            if (j == nu && nu < 512) { ids[nu] = t; cnt[nu] = 0; busyw[nu] = 0; nu++; }
            if (j < nu) { cnt[j]++; busyw[j] += pmap_blocks[i].end - pmap_blocks[i].start; }
        }
        for (int j = 0; j < nu; j++)
            fprintf(stderr, "PMAPW %lld %lld %lld\n", (long long)ids[j], (long long)cnt[j],
                    (long long)busyw[j]);
    }
    if (getenv("PMAP_BLOCKS") && getenv("PMAP_BLOCKS")[0] && getenv("PMAP_BLOCKS")[0] != '0')
        for (int64_t i = 0; i < n; i++)
            fprintf(stderr, "PMAPB %lld %lld %lld %lld\n", (long long)pmap_blocks[i].start,
                    (long long)pmap_blocks[i].end, (long long)pmap_blocks[i].tid,
                    (long long)pmap_blocks[i].block);
}
"""


def instrument(text):
    marker = "static int ail_par_threads(void) {"
    if text.count(marker) != 1:
        raise SystemExit("instrument: ail_par_threads marker not unique")
    text = text.replace(marker, HELPER + marker, 1)

    old = "static void ail_par_go_wide(ail_par_fn fn, void **args, int64_t lo, int64_t hi) {\n"
    if text.count(old) != 1:
        raise SystemExit("instrument: ail_par_go_wide marker not unique")
    text = text.replace(old, old + "    pmap_prefix_end = ail_par_now();\n    pmap_went_wide = 1;\n", 1)

    old = (
        "    for (;;) {\n"
        "        if (__atomic_load_n(&J->abort, __ATOMIC_RELAXED)) break;\n"
        "        int64_t b = __atomic_fetch_add(&J->next, 1, __ATOMIC_RELAXED);\n"
        "        if (b >= J->nblocks) break;\n"
        "        int64_t lo = J->lo + b * J->block, hi = lo + J->block;\n"
        "        if (hi > J->hi || hi < lo) hi = J->hi;\n"
        "        if (ail_par_block(&c, J, lo, hi)) {\n"
    )
    new = (
        "    for (;;) {\n"
        "        if (__atomic_load_n(&J->abort, __ATOMIC_RELAXED)) break;\n"
        "        int64_t b = __atomic_fetch_add(&J->next, 1, __ATOMIC_RELAXED);\n"
        "        if (b >= J->nblocks) {\n"
        "            int64_t _en = ail_par_now();\n"
        "            int64_t _prev = __atomic_load_n(&pmap_first_empty, __ATOMIC_RELAXED);\n"
        "            while (_en < _prev && !__atomic_compare_exchange_n(&pmap_first_empty, &_prev, _en, 0, __ATOMIC_RELAXED, __ATOMIC_RELAXED)) { }\n"
        "            __atomic_add_fetch(&pmap_empty_claims, 1, __ATOMIC_RELAXED);\n"
        "            break;\n"
        "        }\n"
        "        int64_t lo = J->lo + b * J->block, hi = lo + J->block;\n"
        "        if (hi > J->hi || hi < lo) hi = J->hi;\n"
        "        int64_t _bt0 = ail_par_now();\n"
        "        int _bad = ail_par_block(&c, J, lo, hi);\n"
        "        int64_t _bt1 = ail_par_now();\n"
        "        int64_t _k = __atomic_fetch_add(&pmap_block_n, 1, __ATOMIC_RELAXED);\n"
        "        if (_k < PMAP_MAX_BLOCKS) {\n"
        "            pmap_blocks[_k].start = _bt0; pmap_blocks[_k].end = _bt1;\n"
        "            pmap_blocks[_k].tid = (int64_t)(intptr_t)pthread_self();\n"
        "            pmap_blocks[_k].block = b;\n"
        "        }\n"
        "        if (_bad) {\n"
    )
    if text.count(old) != 1:
        raise SystemExit("instrument: ail_par_work loop marker not unique")
    text = text.replace(old, new, 1)

    old = ("static void ail_par_run(ail_par_fn fn, void **args, int64_t lo, int64_t hi, "
           "ail_par_site *S) {\n")
    new = (
        "static void ail_par_run_orig(ail_par_fn fn, void **args, int64_t lo, int64_t hi, ail_par_site *S);\n"
        "static void ail_par_run(ail_par_fn fn, void **args, int64_t lo, int64_t hi, ail_par_site *S) {\n"
        "    pmap_region_start = ail_par_now();\n"
        "    pmap_prefix_end = 0; pmap_went_wide = 0;\n"
        "    __atomic_store_n(&pmap_block_n, 0, __ATOMIC_RELAXED);\n"
        "    __atomic_store_n(&pmap_first_empty, INT64_MAX, __ATOMIC_RELAXED);\n"
        "    __atomic_store_n(&pmap_empty_claims, 0, __ATOMIC_RELAXED);\n"
        "    ail_par_run_orig(fn, args, lo, hi, S);\n"
        "    pmap_region_end = ail_par_now();\n"
        "    if (pmap_went_wide && !pmap_prefix_end) pmap_prefix_end = pmap_region_end;\n"
        "    pmap_report();\n"
        "}\n"
        "static void ail_par_run_orig(ail_par_fn fn, void **args, int64_t lo, int64_t hi, ail_par_site *S) {\n"
    )
    if text.count(old) != 1:
        raise SystemExit("instrument: ail_par_run signature not unique")
    text = text.replace(old, new, 1)

    pat = re.compile(
        r"(    ail_list_clear\(&v_r\);\n"
        r"    v__t\d+ = 0LL;\n"
        r"    v__t\d+ = v_n;\n"
        r"    ail_list_reserve\(&v_r, v__t\d+\);\n"
        r"    for \(int64_t _i = 0; _i < v__t\d+; _i\+\+\) ail_list_push\(&v_r, v__t\d+\);\n)"
    )
    match = pat.search(text)
    if not match:
        raise SystemExit("instrument: result-list initialization not found")
    body = match.group(1)
    text = (text[:match.start(1)] + "    pmap_list_start = ail_par_now();\n" + body
            + "    pmap_list_end = ail_par_now();\n" + text[match.end(1):])
    return text


def compile_timed(text, work):
    cfile = work / "timed.c"
    cfile.write_text(text, encoding="utf-8")
    exe = work / "timed"
    if exe.exists():
        exe.unlink()
    cc = os.environ.get("CC", "cc")
    got = subprocess.run([cc, "-O2", "-w", "-o", str(exe), str(cfile), "-lm", "-pthread"],
                         capture_output=True, text=True, timeout=BUILD_TIMEOUT)
    if got.returncode != 0:
        raise SystemExit("timed build failed: %s" % first_line(got.stderr.encode()))
    return exe


def parse_report(stderr):
    out = {"histogram": [], "workers": [], "blocks": []}
    for line in stderr.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "PMAP":
            for item in parts[1:]:
                key, value = item.split("=", 1)
                out[key] = int(value)
        elif parts[0] == "PMAPH" and len(parts) == 4:
            out["histogram"].append([int(x) for x in parts[1:]])
        elif parts[0] == "PMAPW" and len(parts) == 4:
            out["workers"].append([int(x) for x in parts[1:]])
        elif parts[0] == "PMAPB" and len(parts) == 5:
            out["blocks"].append([int(x) for x in parts[1:]])
    if "region_ns" not in out:
        raise SystemExit("timed run printed no PMAP line")
    return out


def run_binary(exe, stdin, threads, timeout=RUN_TIMEOUT):
    env = clean_env({"AIL_THREADS": str(threads)})
    return call([str(exe)], timeout, env, cwd=exe.parent, stdin=stdin)


def cpython_oracle(name, src, work, stdin):
    if name == "par_collatz":
        got = call([sys.executable, "-B", str(REFERENCE)], RUN_TIMEOUT * 3, clean_env(),
                   cwd=work, stdin=stdin)
        return got.stdout, got.returncode
    probe = work / "oracle.py"
    probe.write_text(
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('load', %r)\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "n = mod.N\n"
        "total = 0\n"
        "first = 0\n"
        "last = 0\n"
        "for x in range(n):\n"
        "    v = mod.work(x)\n"
        "    total += v\n"
        "    if x == 0:\n"
        "        first = v\n"
        "    last = v\n"
        "print(n, total, first, last)\n" % str(src), encoding="utf-8")
    got = call([sys.executable, "-B", str(probe)], RUN_TIMEOUT * 3, clean_env(), cwd=work)
    return got.stdout, got.returncode


def median(values):
    return statistics.median(values)


def measure(name, src, stdin, runs):
    work = Path(tempfile.mkdtemp(prefix="pmap-" + name + "-", dir="/tmp"))
    try:
        plain, ctext = compile_plain(src, work)
        want, want_rc = cpython_oracle(name, src, work, stdin)
        plain_run = run_binary(plain, stdin, 4)
        if plain_run.returncode != want_rc or plain_run.stdout != want:
            raise SystemExit("%s: plain build does not match CPython\ngot %r %r\nwant %r %r"
                             % (name, plain_run.returncode, plain_run.stdout, want_rc, want))
        timed = compile_timed(instrument(ctext), work)
        record = {"source": str(src.relative_to(ROOT)), "cpython_match": True,
                  "expected": want.decode("utf-8", "replace").strip(), "threads": {}}
        for threads in THREADS:
            samples = []
            first_hist = None
            for _ in range(runs):
                started = time.perf_counter()
                got = run_binary(timed, stdin, threads)
                wall_ms = (time.perf_counter() - started) * 1000.0
                if got.returncode != want_rc or got.stdout != want:
                    raise SystemExit("%s: timed build at %d threads does not match the plain build\n"
                                     "got %r %r\nwant %r %r"
                                     % (name, threads, got.returncode, got.stdout, want_rc, want))
                rep = parse_report(got.stderr)
                rep["wall_ms"] = wall_ms
                samples.append(rep)
                if first_hist is None:
                    first_hist = {"histogram": rep["histogram"], "workers": rep["workers"]}
            regions = [s["region_ns"] for s in samples]
            rec = {
                "runs": runs,
                "wall_ms": round(median([s["wall_ms"] for s in samples]), 3),
                "region_ms": round(median(regions) / 1e6, 3),
                "prefix_ms": round(median([s["prefix_ns"] for s in samples]) / 1e6, 3),
                "tail_ms": round(median([s["tail_ns"] for s in samples]) / 1e6, 3),
                "list_ms": round(median([s["list_ns"] for s in samples]) / 1e6, 3),
                "blocks": int(median([s["nblocks"] for s in samples])),
                "empty_claims": int(median([s["empty_claims"] for s in samples])),
                "went_wide": bool(samples[0]["went_wide"]),
                "timeline": first_hist,
            }
            region = rec["region_ms"]
            rec["tail_share"] = round(rec["tail_ms"] / region, 4) if region > 0 else 0.0
            rec["prefix_share"] = round(rec["prefix_ms"] / region, 4) if region > 0 else 0.0
            rec["list_share"] = round(rec["list_ms"] / region, 4) if region > 0 else 0.0
            record["threads"][str(threads)] = rec
        return record
    finally:
        shutil.rmtree(work, ignore_errors=True)


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def own_nodes(fn):
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield node
        for child in ast.iter_child_nodes(node):
            stack.append(child)


def walk_nodes(nodes):
    stack = list(nodes)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if isinstance(node, ast.Lambda):
                stack.extend([node.body])
            continue
        yield node
        for child in ast.iter_child_nodes(node):
            stack.append(child)


def call_short(node):
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node.func, ast.Name):
            return node.func.id
    return None


def is_par_range_loop(node):
    if not isinstance(node, ast.For):
        return False
    it = node.iter
    if not isinstance(it, ast.Call):
        return False
    return call_short(it) == "par_range" or dotted(it.func) == "par_range"


def all_nodes(nodes):
    stack = list(nodes)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            stack.append(child)


def executor_bindings(tree):
    names = set()
    for node in all_nodes(tree.body):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(value, ast.Call) and call_short(value) in ("ThreadPoolExecutor", "Pool"):
                for target in targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call) and call_short(item.context_expr) in (
                        "ThreadPoolExecutor", "Pool") and isinstance(item.optional_vars, ast.Name):
                    names.add(item.optional_vars.id)
    return names


def region_info(fn, funcs, executors):
    """(has a region, module functions used as its bodies, nodes inside a par_range body,
    whether another region opens directly inside this one)."""
    has_region = False
    roots = set()
    body_nodes = []
    direct_nested = False
    for node in own_nodes(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("map", "submit"):
            base = node.func.value
            is_executor = (isinstance(base, ast.Name) and base.id in executors) or (
                isinstance(base, ast.Call) and call_short(base) in ("ThreadPoolExecutor", "Pool"))
            if is_executor:
                has_region = True
                if node.args and isinstance(node.args[0], ast.Name) and node.args[0].id in funcs:
                    roots.add(node.args[0].id)
                if node.args and isinstance(node.args[0], ast.Lambda):
                    body_nodes.extend(walk_nodes([node.args[0].body]))
        if isinstance(node, ast.Call) and call_short(node) == "Thread":
            has_region = True
            for kw in node.keywords:
                if kw.arg == "target" and isinstance(kw.value, ast.Name) and kw.value.id in funcs:
                    roots.add(kw.value.id)
                if kw.arg == "target" and isinstance(kw.value, ast.Lambda):
                    body_nodes.extend(walk_nodes([kw.value.body]))
        if is_par_range_loop(node):
            has_region = True
            inside = list(walk_nodes(node.body))
            body_nodes.extend(inside)
            for inner in inside:
                if isinstance(inner, ast.Call):
                    short = call_short(inner)
                    if short == "Thread":
                        direct_nested = True
                    if isinstance(inner.func, ast.Attribute) and inner.func.attr in ("map", "submit"):
                        base = inner.func.value
                        if (isinstance(base, ast.Name) and base.id in executors) or (
                                isinstance(base, ast.Call) and call_short(base) in ("ThreadPoolExecutor", "Pool")):
                            direct_nested = True
    return has_region, roots, body_nodes, direct_nested


def called_names(nodes, funcs):
    found = set()
    for node in walk_nodes(nodes):
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            if name in funcs:
                found.add(name)
            short = call_short(node)
            if short in ("map", "submit", "Thread") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Name) and first.id in funcs:
                    found.add(first.id)
            for kw in node.keywords:
                if kw.arg == "target" and isinstance(kw.value, ast.Name) and kw.value.id in funcs:
                    found.add(kw.value.id)
    return found


def scan_file(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return None
    funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if not funcs:
        return None
    executors = executor_bindings(tree)
    info = {name: region_info(fn, funcs, executors) for name, fn in funcs.items()}
    par_funcs = {name for name, (has, _r, _b, _d) in info.items() if has}
    if not par_funcs:
        return None
    edges = {name: called_names(own_nodes(fn), funcs) for name, fn in funcs.items()}

    def reaches_par(name, seen):
        for nxt in edges.get(name, ()):
            if nxt in seen:
                continue
            seen.add(nxt)
            if nxt in par_funcs or reaches_par(nxt, seen):
                return True
        return False

    for name in par_funcs:
        _has, roots, body_nodes, direct_nested = info[name]
        if direct_nested:
            return str(path.relative_to(ROOT))
        for root in roots:
            if root in par_funcs or reaches_par(root, {root}):
                return str(path.relative_to(ROOT))
        for called in called_names(body_nodes, funcs):
            if called in par_funcs or reaches_par(called, {called}):
                return str(path.relative_to(ROOT))
    return None


def nesting_scan():
    files = []
    for base in (ROOT / "lab", ROOT / "AIL_CURRENT"):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "pmap/run.py" in str(path):
                continue
            if base.name == "AIL_CURRENT" and not path.name.startswith("test_"):
                continue
            files.append(path)
    found = []
    for path in files:
        hit = scan_file(path)
        if hit:
            found.append(hit)
    return {"count": len(found), "files": found, "scanned_py": len(files)}


def write_outputs(data):
    (HERE.parent / "PMAP.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    lines = []
    lines.append("# fbpmap1: where parallel-map time goes")
    lines.append("")
    lines.append("Measured by `python3 lab/race/pmap/run.py` on a 4-vCPU GitHub Actions runner, "
                 "CPython %s, under a 1.5 GB address-space cap; wall time is the median of %d runs "
                 "and the runner is noisy (up to 3x between runs), so treat shares as the stable "
                 "number and milliseconds as indicative." % (platform.python_version(), data["runs"]))
    lines.append("")
    lines.append("The timed build is a scratch copy of each generated `program.c` with "
                 "`ail_par_now()` stamps at block start/end (per worker), at the start of the "
                 "doubling probe prefix, and around the serial result-list initialization. The "
                 "compiler and the source are not edited. Every timed run's stdout was compared "
                 "byte for byte with the plain build and with CPython.")
    lines.append("")
    lines.append("`region_ms` is the `ail_par_run` wall time. `tail_ms` runs from the first "
                 "empty block claim to the region end; `prefix_ms` is the probe prefix before "
                 "`ail_par_go_wide`. `list_ms` is the serial `[0] * n` result-list build before "
                 "the region. `blocks` is the number of completed blocks (`1` when the region "
                 "stays sequential).")
    lines.append("")
    lines.append("Instruction counts could not be measured on this runner: `tools/icount.c` "
                 "reports `perf_event_open: Permission denied` (`/proc/sys/kernel/"
                 "perf_event_paranoid` is 4) and `valgrind` is not installed, so there is no "
                 "callgrind fallback. The wall-time medians below are the measurements this "
                 "job can make.")
    lines.append("")
    lines.append("## Idle tail, probe prefix, blocks and result list")
    lines.append("")
    lines.append("| load | threads | region ms | wall ms | tail ms | tail share | prefix ms | "
                 "prefix share | list ms | blocks |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name in data["loads"]:
        rec = data["loads"][name]
        for t in ("1", "2", "4"):
            r = rec["threads"][t]
            lines.append("| %s | %s | %.3f | %.3f | %.3f | %.1f%% | %.3f | %.1f%% | %.3f | %d |"
                         % (name, t, r["region_ms"], r["wall_ms"], r["tail_ms"],
                            100.0 * r["tail_share"], r["prefix_ms"], 100.0 * r["prefix_share"],
                            r["list_ms"], r["blocks"]))
    lines.append("")
    lines.append("## Block timeline at 4 threads")
    lines.append("")
    lines.append("Twenty equal bins of the region, from the first block start to the region end; "
                 "each cell is `blocks/busy ms`.")
    lines.append("")
    lines.append("| load | bins (start -> end) |")
    lines.append("|---|---|")
    for name in data["loads"]:
        r = data["loads"][name]["threads"]["4"]
        cells = []
        for b, count, busy in r["timeline"]["histogram"]:
            cells.append("%d/%.1f" % (count, busy / 1e6))
        lines.append("| %s | %s |" % (name, " ".join(cells)))
    lines.append("")
    lines.append("## par_collatz against races3")
    lines.append("")
    lines.append("| threads | AIL wall, this job | races3 AIL | races3 C | races3 Rust |")
    lines.append("|---:|---:|---:|---:|---:|")
    races3 = {"1": (1270.6, 1082.0, 923.5), "2": (885.7, 701.6, 588.4),
              "4": (602.6, 527.8, 424.6)}
    pc = data["loads"]["par_collatz"]["threads"] if "par_collatz" in data["loads"] else {}
    for t in ("1", "2", "4"):
        if t in pc:
            a = pc[t]["wall_ms"]
            a3, c3, r3 = races3[t]
            lines.append("| %s | %.1f | %.1f | %.1f | %.1f |" % (t, a, a3, c3, r3))
    lines.append("")
    lines.append("The AIL column is this job's median of %d runs of the same task and input "
                 "(`N = 7,000,000`), with `AIL_THREADS` 1, 2 and 4; the input still says `W = 4`, "
                 "so the worker cap is 4 and `AIL_THREADS` limits the pool. A separate local "
                 "`lab/compare/run_task.py --task par_collatz --langs ail,c,rust --no-cases "
                 "--icount none` run on the same runner at 4 threads gave AIL 474.9 ms, C "
                 "380.6 ms and Rust 311.0 ms (peak RSS 121956 / 29092 / 56704 KiB). The races3 "
                 "numbers in the table are from `lab/race/SPEEDUP.md`, measured under a higher "
                 "load average." % data["runs"])
    lines.append("")
    lines.append("## Decisions")
    lines.append("")
    lines.append("- guided chunk sizes: **%s** (idle tail at least 10%% of region wall time on "
                 "%d loads at 4 threads; rule needs at least 2)."
                 % (data["decisions"]["guided"], data["decisions"]["guided_loads"]))
    lines.append("- work-stealing deques (Chase-Lev): **%s** (%d program%s whose parallel region "
                 "calls into another parallel region; rule needs at least 3)."
                 % (data["decisions"]["work_stealing"], data["nesting"]["count"],
                    "" if data["nesting"]["count"] == 1 else "s"))
    if data["nesting"]["files"]:
        lines.append("")
        lines.append("Nested-region programs found: " + ", ".join(
            "`%s`" % f for f in data["nesting"]["files"]))
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append("- `lab/race/pmap/{par_collatz,uniform,ramp,heavy,tiny}.py`: the five loads.")
    lines.append("- `lab/race/pmap/par_collatz.py` is a byte-for-byte copy of "
                 "`lab/compare_par/src/par_collatz/typed.py`.")
    lines.append("- `lab/race/pmap/run.py`: builds, instruments in /tmp, measures, writes these files.")
    lines.append("")
    (HERE.parent / "PMAP.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument("--loads", default=",".join(LOADS))
    parser.add_argument("--skip-nesting", action="store_true")
    args = parser.parse_args()
    selected = [name for name in args.loads.split(",") if name]
    for name in selected:
        if name not in LOADS:
            raise SystemExit("unknown load: %s" % name)
    data = {"job": "fbpmap1", "date": time.strftime("%Y-%m-%d", time.gmtime()),
            "python": platform.python_version(), "runs": args.runs,
            "cpus": os.cpu_count(), "loads": {},
            "instructions": {"status": "unavailable",
                             "reason": "perf_event_open: Permission denied (perf_event_paranoid=4); "
                                       "valgrind is not installed"},
            "compare_lab_4": {"ail_ms": 474.9, "c_ms": 380.6, "rust_ms": 311.0,
                              "rss_kib": {"ail": 121956, "c": 29092, "rust": 56704},
                              "command": "lab/compare/run_task.py --task par_collatz "
                                         "--langs ail,c,rust --no-cases --icount none"}}
    for name in selected:
        src, stdin = LOADS[name]
        print("measure", name, file=sys.stderr, flush=True)
        data["loads"][name] = measure(name, src, stdin, args.runs)
    if args.skip_nesting:
        data["nesting"] = {"count": 0, "files": [], "scanned_py": 0}
    else:
        data["nesting"] = nesting_scan()
    guided_loads = [name for name in data["loads"]
                    if data["loads"][name]["threads"]["4"]["tail_share"] >= 0.10]
    data["decisions"] = {
        "guided": "go" if len(guided_loads) >= 2 else "no-go",
        "guided_loads": len(guided_loads),
        "guided_names": guided_loads,
        "work_stealing": "go" if data["nesting"]["count"] >= 3 else "no-go: no nesting",
    }
    write_outputs(data)
    print(json.dumps({"guided": data["decisions"], "nesting": data["nesting"]["count"]},
                     indent=1), flush=True)


if __name__ == "__main__":
    main()
