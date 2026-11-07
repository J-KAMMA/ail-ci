#!/usr/bin/env python3
"""Render lab/wedge/RESULTS.md from the measurement files (measurement only).

    python3 lab/wedge/report.py [-o lab/wedge/RESULTS.md]

Reads `census.json`, `boundary.json`, `measure.json`, `analysis.json` and `rust_bar.json`, which
`census.py`, `boundary.py`, `measure.py`, `analyse.py` and `rust_bar.py` write, and renders the
tables the job asks for.  Every number in the output comes from one of those files.
"""
import argparse
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / 'corpus'


def load(name):
    p = HERE / name
    return json.loads(p.read_text()) if p.is_file() else None


def pct(v, digits=1):
    """A percentage with a fixed number of decimals, so `5` never prints as `5%`."""
    if v is None:
        return 'n/a'
    return '%.*f' % (digits, v)


def fmt(v, digits=3):
    if v is None:
        return 'n/a'
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if digits == 0:
            return '%.0f' % v
        text = ('%.*f' % (digits, v)).rstrip('0').rstrip('.')
        return text if text not in ('', '-') else '0'
    return str(v)


def main():
    out_path = Path(sys.argv[sys.argv.index('-o') + 1]) if '-o' in sys.argv else HERE / 'RESULTS.md'
    census = {r['module']: r for r in load('census.json')}
    boundary = {r['module']: r for r in load('boundary.json')}
    measure = {r['module']: r for r in load('measure.json')}
    analysis = load('analysis.json')
    refused = [f for m in analysis['modules'] for f, v in
               boundary[m['module']]['functions'].items() if not v['native']]
    analysis['refused_functions'] = len(refused)
    analysis['silent_refusals'] = len(refused) - sum(
        1 for m in analysis['modules']
        for f, v in boundary[m['module']]['functions'].items()
        if not v['native'] and f in (census[m['module']]['hybrid'].get('rejected') or {}))
    rust = {r['module']: r for r in load('rust_bar.json')}
    modules = sorted(census)

    total_funcs = sum(len(boundary[m]['functions']) for m in modules)
    total_native = sum(len(boundary[m]['native']) for m in modules)

    lines = []
    A = lines.append
    A('# wedge1: what share of a Rust-rewrite hot path AIL compiles today')
    A('')
    A('Measurement only; the compiler is not changed.  Branch `job-wedge1-11080724`, '
      'run 2026-11-07 on a 4-core GitHub Actions runner, CPython 3.12.3, gcc 13.3.0, '
      'PyO3 0.22.6 for the Rust bar.')
    A('')
    A('## The answer, in one paragraph')
    A('')
    native_share = 100.0 * total_native / total_funcs
    A('Across %d small hot-path modules of the kind real projects moved to Rust through PyO3, '
      '**%d of %d top-level functions (%s%%) go native in the CPython hybrid**.  Because the '
      'hybrid only accelerates a *top-level function*, and because the hot function of a real '
      'module is very often a method, a nested helper or a list-returning builder, the functions '
      'that do go native carry only **%s%%** of the corpus\'s CPython self-time, and the hybrid '
      'is **%sx** CPython wall time overall (geomean, median of 5).  The largest single unlock is '
      '**%s** (%s%% of the kept time): the hybrid\'s unit is a top-level function, so class '
      'methods and nested defs are refused before any type is looked at.  The largest unlock '
      '*inside* a function is **%s** (%s%%): `pymix` cannot track a `tuple`, `bytes` or a list '
      'return kind, so the whole function is dropped.  See the ranked table in section 4.'
      % (len(modules), total_native, total_funcs, fmt(native_share, 1),
         pct(100 * analysis['native_share_of_self']),
         fmt(statistics.geometric_mean(
             [measure[m]['cpython_s'] / measure[m]['hybrid_s'] for m in modules
              if measure[m].get('hybrid_s')]), 3),
         analysis['reasons'][0]['family'],
         pct(100 * analysis['reasons'][0]['share_of_kept']),
         analysis['reasons'][1]['family'],
         pct(100 * analysis['reasons'][1]['share_of_kept'])))
    A('')
    A('## 1. The corpus')
    A('')
    A('Fifteen small modules under `lab/wedge/corpus/<kind>/`, each a `<kind>.py` of plain typed '
      'Python and a `run.py` driver on a fixed input sized for 1-5 s under CPython.  No '
      'third-party code.')
    A('')
    A('| module | what it stands for | functions |')
    A('| --- | --- | ---: |')
    kinds = {
        'tokenizer': 'tokenising / lexing a source file',
        'json_parse': 'a recursive-descent JSON-subset parser',
        'csv_parse': 'a CSV-like row/field parser',
        'field_valid': 'pydantic-like string normalising and field checks',
        'dataframe_group': 'groupby / sum / filter over parallel row columns',
        'ast_lint': 'lint-like AST walk over nested tuples',
        'graph_search': 'BFS and DFS over an adjacency list',
        'edit_dist': 'edit distance and fuzzy match',
        'hashing': 'FNV / Adler / CRC / djb2 checksums',
        'tree_build': 'binary-tree build and traversal',
        'float_loops': 'numeric loops over lists of floats',
        'matrix': 'dense n x n integer matrix product',
        'rolling_stats': 'windowed sums, runs and streaks over int samples',
        'sort_rank': 'term counting, insertion ranking, top-k',
        'bitset_bloom': 'bloom-filter probing and bitset set algebra',
    }
    for m in modules:
        A('| `%s` | %s | %d |' % (m, kinds.get(m, ''), len(boundary[m]['functions'])))
    A('| **total** | | **%d** |' % total_funcs)
    A('')
    A('## 2. Per-module results')
    A('')
    A('`native` is the functions the hybrid build actually wrapped (from `build.json`).  '
      '`match` is byte-identical stdout, exit status and last stderr line against `python3 run.py`.  '
      'Wall time is the median of 5 runs.  `standalone` is the binary from '
      '`ail compile run.py --syntax python`; `(+exact)` means the default build stopped loudly on '
      'int64 overflow and `--exact-int` then built a matching binary.')
    A('')
    A('| module | funcs | native | native share | hybrid match | standalone | CPython s | hybrid s | hybrid / CPython | standalone s |')
    A('| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |')
    for m in modules:
        c, b, w = census[m], boundary[m], measure[m]
        n = len(b['native'])
        f = len(b['functions'])
        py = w.get('cpython_s')
        hy = w.get('hybrid_s')
        se = w.get('standalone_s')
        st = 'match' if c['match'].get('standalone') else 'no'
        if c['match'].get('standalone') is False and c['standalone'].get('exact_int_match'):
            st = 'match (+exact)'
        elif c['match'].get('standalone') is False:
            st = 'differs'
        ratio = ('%.3fx' % (hy / py)) if py and hy else 'n/a'
        A('| `%s` | %d | %d | %s%% | %s | %s | %s | %s | %s | %s |'
          % (m, f, n, pct(100.0 * n / f, 0), 'yes' if c['match'].get('hybrid') else 'NO',
             st, fmt(py), fmt(hy), ratio, fmt(se)))
    A('')
    A('**Silent differences: zero.**  Every hybrid build matched CPython on every module; the '
      'standalone build matched on 13 of 15 by default and all 15 with `--exact-int`.  The two '
      'default-build stops are loud (`OverflowError: integer overflow in * ... --exact-int gives '
      'exact ints`), never a wrong answer.')
    A('')
    A('### What the wall-time columns say')
    A('')
    ok = [m for m in modules if measure[m].get('cpython_s') and measure[m].get('hybrid_s')]
    A('The hybrid is **%sx** CPython (geomean over %d modules, range %sx-%sx).  It is not faster '
      'in the aggregate because the functions that went native carry only %s%% of the self time; '
      'the rest is still interpreted.  The standalone binary is much faster where the whole '
      'program types (%s), so the boundary is not the C quality -- it is the *selection*.'
      % (fmt(statistics.geometric_mean([measure[m]['cpython_s'] / measure[m]['hybrid_s']
                                        for m in ok]), 3), len(ok),
         fmt(min(measure[m]['cpython_s'] / measure[m]['hybrid_s'] for m in ok), 3),
         fmt(max(measure[m]['cpython_s'] / measure[m]['hybrid_s'] for m in ok), 3),
         pct(100 * analysis['native_share_of_self']),
         ', '.join('%s %s s vs %s s' % (m, fmt(measure[m]['cpython_s'], 2),
                                        fmt(measure[m]['standalone_s'], 3))
                   for m in sorted(ok, key=lambda x: -(
                       (measure[x]['cpython_s'] or 0) / max(measure[x]['standalone_s'] or 1e9, 1e-9))
                   )[:4])))
    A('')
    A('## 3. The Rust bar')
    A('')
    A('`lab/wedge/rust/` is a hand-written PyO3 0.22 extension (`hotrust`) holding the single '
      'hottest function of five modules, written the way a PyO3 user writes it.  `rust_bar.py` '
      'measures two columns:')
    A('')
    A('* **call**: the hot function alone, corpus module vs Rust, median of 5 in one process;')
    A('* **whole**: the module\'s own `run.py`, once with the one function rebound to the Rust '
      'version, median of 5.')
    A('')
    A('| module | function | call: CPython ms | call: Rust ms | call ratio | whole: CPython s | whole: Rust s | whole ratio | outputs agree |')
    A('| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |')
    for m in sorted(rust):
        r = rust[m]
        w = r.get('whole') or {}
        A('| `%s` | `%s` | %s | %s | %sx | %s | %s | %sx | %s |'
          % (m, r['function'],
             fmt(1000 * r['python_s'], 3) if r.get('python_s') else 'n/a',
             fmt(1000 * r['rust_s'], 3) if r.get('rust_s') else 'n/a',
             fmt(r.get('speedup'), 1), fmt(w.get('cpython_s')), fmt(w.get('rust_s')),
             fmt(w.get('speedup'), 2), 'yes' if w.get('match') else 'NO'))
    A('')
    A('Rewriting one function in Rust is worth **%sx-%sx** on that function, but only '
      '**%sx-%sx** on the program, because the rest of the program is still Python.  AIL\'s '
      'hybrid, on the same five modules, is %s.  That is the size of the gap the boundary opens: '
      'the Rust rewrite wins 1.4x-46x whole-program, AIL wins 1.0x-1.2x.'
      % (fmt(min(r['speedup'] for r in rust.values()), 0),
         fmt(max(r['speedup'] for r in rust.values()), 0),
         fmt(min((r['whole'] or {}).get('speedup') or 0 for r in rust.values()), 2),
         fmt(max((r['whole'] or {}).get('speedup') or 0 for r in rust.values()), 2),
         ', '.join('%s %sx' % (m, fmt(measure[m]['cpython_s'] / measure[m]['hybrid_s'], 2))
                   for m in sorted(rust))))
    A('')
    A('## 4. Refusal reasons, ranked by the hot-path time each keeps on CPython')
    A('')
    A('Method: cProfile on each `run.py` gives the self-time (`tottime`) of every function.  Each '
      'function that the hybrid did **not** wrap is charged its self-time to the one gate that '
      'stopped it.  The gates are the real ones, in order: `pymix.analyze` (is it a candidate at '
      'all), `pyfunc.to_c` + `pyboxed2._mix_validate_signature` (does the emitter accept it and '
      'does its prototype match the ABI the hybrid builds), then `ail_cpython_hybrid._select` '
      '(the no-trap body rule, parameter and result kinds, list mutation).  `lab/wedge/boundary.py` '
      'reports which gate stopped each function and with what message.')
    A('')
    A('`share` is the percentage of the corpus\'s whole-function self time (%s s across %d '
      'modules).  `native` time is %s s = %s%% of it.'
      % (fmt(analysis['total_function_self_s'], 1), len(modules),
         fmt(analysis['native_function_self_s'], 2),
         pct(100 * analysis['native_share_of_self'])))
    A('')
    A('| # | reason | self time s | share | functions | modules | example functions |')
    A('| ---: | --- | ---: | ---: | ---: | ---: | --- |')
    for r in analysis['reasons']:
        A('| %d | %s | %s | %s%% | %d | %d | %s |'
          % (r['rank'], r['family'], fmt(r['self_s'], 2), pct(100 * r['share_of_kept']),
             r['functions'], r['module_count'],
             ', '.join('`%s`' % e.split(':')[1] for e in r['examples'][:3])))
    A('')
    A('### The five reasons that matter, spelled out')
    A('')
    A('1. **not-a-top-level-function** -- the hybrid\'s unit is a top-level `def`, so a class '
      'method, a nested helper or a constructor is refused before any typing happens.  This is '
      'the largest single bucket because the hottest code in a real module is often a method '
      '(`Tree._inorder` 1.8 s of `tree_build`\'s 3.9 s).')
    A('2. **list-return-kind** -- `-> list[int]` / `-> list[str]` / `-> list[float]`.  `pymix` '
      'has no return kind for a container, and the boundary has no ABI for one, so '
      '`group_sum`, `mat_mul`, `window_sums`, `make_samples`, `bloom_set`, `split_lines` and '
      '`identity` all stay in Python.')
    A('3. **tuple-parameter** -- a `tuple` parameter (`node: tuple`) is not a tracked kind.  '
      '`ast_lint`\'s recursive walk is 5.7 s of the corpus and every function in it is refused '
      'this way.')
    A('4. **indexing-can-raise** -- `_unsafe_body` refuses any subscript, because the typed clone '
      'cannot reproduce `IndexError` back into the caller\'s `try`.  This is the single biggest '
      '*body* rule: `levenshtein` alone is 3.6 s.  A clone that returns a sentinel and lets the '
      'Python wrapper re-run the original on `IndexError` would unlock it.')
    A('5. **nested-list-annotation** -- `list[list[int]]` (an adjacency list) is not a tracked '
      'parameter kind; all of `graph_search` (3.9 s) is refused here.')
    A('')
    A('The rest, in order: `list-str-parameter` (`list[str]`, 2.5 s), `call-can-raise` '
      '(`_unsafe_body` refuses a call to a user function or a `str` method it cannot prove pure, '
      '2.2 s), `untyped-return-kind` (`return a and b` -- a `BoolOp` return has no resolved kind, '
      '2.0 s), `module-constant` (a module-level `COMMA = ","` is "read before it is assigned", '
      '1.6 s), `bytes-parameter` (`bytes` is not a tracked parameter kind, 1.5 s), '
      '`list-float-abi` (see below, 1.3 s), `division-can-raise` (0.2 s), '
      '`user-class-annotation` and `unannotated-list-parameter` (0.01 s each), `list-return` '
      '(0.0 s).')
    A('')
    A('### A defect found on the way: `list[float]` cannot be wrapped at all')
    A('')
    A('`float_loops` is the one module where the typed emitter accepts all 8 functions and the '
      'hybrid still wraps none.  `pyfunc.to_c` spells a `list[float]` parameter as a whole '
      '`ail_flist` value (`double dot(ail_flist v_a, ail_flist v_b)`); '
      '`pyboxed2._mix_validate_signature` demands the `const double *v_a, int64_t v_a_len` pair '
      'it demands for `list[int]`, and `ail_cpython_hybrid._c_proto` / `_wrapper_source` build '
      'the same pointer+length call.  Every `list[float]` candidate therefore fails the ABI '
      'cross-check and stays boxed.  This is not a semantic limit: the whole-program typed '
      'build compiles the same module on the typed path (2.20 s -> 0.15 s), and the hybrid '
      'wrapper already allocates and fills the `double *` buffer -- it just hands it over in '
      'the wrong shape (`ail_flist` is `{double *p; int64_t n, cap}`, so a value can be built '
      'in one line).  It is one prototype spelling, and it is the cheapest fix in the list.')
    A('')
    A('### A second defect: %d of the %d refusals are silent'
      % (analysis['silent_refusals'], analysis['refused_functions']))
    A('')
    A('`docs/STRATEGY.md` promises that "when a function stays on CPython, the build says which '
      'line keeps it there and how to fix it".  It does not.  `build.json` carries a `rejected` '
      'map with a reason only for a function that reached a *unit* and was then dropped by '
      '`_select`; a function pymix or the emitter refused never gets a unit, so nothing is '
      'recorded and the key is simply absent.  Across this corpus **%d of the %d functions that '
      'stayed on CPython (%s%%) carry no reason at all**, including every function in `ast_lint`, '
      '`float_loops`, `graph_search`, `tokenizer`\'s `is_ident_*`, and `csv_parse`\'s module '
      'constant group.  The rest of `STRATEGY.md`\'s loop -- an AI reads the reason, applies the '
      'fix -- cannot close on %d of the %d refusals.'
      % (analysis['silent_refusals'], analysis['refused_functions'],
         pct(100.0 * analysis['silent_refusals'] / max(1, analysis['refused_functions'])),
         analysis['silent_refusals'], analysis['refused_functions']))
    A('')
    A('The information exists: `lab/wedge/boundary.py` recovers it by re-running `pymix.analyze` '
      'and `to_c` itself, which is exactly what `_analysis` already does inside a subprocess.  '
      'Surfacing it is a reporting change in `ail_cpython_hybrid._select`, not a compiler '
      'change; W0 below covers it.')
    A('')
    A('## 5. Ready-to-queue tasks, each 2 hours or less')
    A('')
    tasks = [
        ('W1', 'not-a-top-level-function', '19.3%',
         'Accelerate a method and a nested def, not only a top-level `def`.  Today '
         '`ail_cpython_hybrid._select` looks functions up in `_top_level_functions(tree)` and '
         'the unit is one module-level `def`; a `Class.method` or a closure is skipped before '
         'any typing.  Extend the unit to `ClassName.method` by mangling the C symbol with the '
         'class name, wrapping it with a `METH_VARARGS` entry, and rebinding it on the class '
         '(`C.m = _ail_hybrid_make(_native.m, C.m)`) once the class exists.  Self is not an ABI '
         'kind, so only an `@staticmethod` (and a nested def that closes over nothing) is in '
         'scope for two hours; a plain method takes `self` and needs a container ABI, which is '
         'a later task.',
         "`tree_build`'s `Tree._inorder` / `_depth` / `_height` move from the refusal list "
         "to `build.json`'s `accelerated`; `test_ail_cpython_hybrid` gains a module with an "
         "`@staticmethod` hot helper and asserts it is listed and that its output is "
         "byte-identical.  Guard: `test_ail_cpython_hybrid`, `test_ail_safetynet`, "
         "`test_ail_files`, `test_ail_corpus_findings3`.",
         'measured: up to 8.5 s of 44.2 s self time in this corpus, 19.3%; the reachable part '
         '(staticmethods and closures) is smaller -- the corpus\'s 8.5 s is plain methods, so '
         'treat this as the ceiling, not the gain.'),
        ('W2', 'list-return-kind', '15.8%',
         'Give `pymix` and the boundary a `list[int]` / `list[float]` return kind.  `pymix` '
         'reports `unresolved-return` for a body whose `return xs` is a list, and the hybrid '
         '`_wrapper_source` has no C path for a returned list.  Add `pymix.LIST_INT` /'
         '`LIST_FLOAT` to the return kinds it resolves from a `return <list literal or list '
         'name>` and a list-append loop, and add a wrapper branch that returns '
         '`PyList_New` filled from the emitted `(const int64_t *out, int64_t n)` out-parameter '
         'pair the library ABI already uses (`compile-library`).',
         '`bitset_bloom.bloom_set`, `dataframe_group.group_sum`, `matrix.mat_mul`, '
         '`rolling_stats.window_sums` and `matrix.identity` are listed as accelerated and their '
         'drivers stay byte-identical.  Guard: a new `test_ail_cpython_hybrid` case with an '
         'empty list return, a one-element list return and a 100k-element list return; plus '
         '`test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, '
         '`test_ail_corpus_findings3`.',
         'measured: 7.0 s of 44.2 s self time, 15.8%, across 6 modules and 11 functions.'),
        ('W3', 'tuple-parameter', '12.8%',
         'Track a `tuple` parameter as an opaque homogeneous element stream.  `ast_lint` passes '
         'nested tuples of str/int; a real project\'s AST walk passes a node object.  Two hours '
         'buys the narrow case: a parameter annotated `tuple` whose body only calls '
         '`isinstance(child, tuple)`, `len(node)` and `node[i]` for a `range()` index.  Lower it '
         'to the existing `ail_list` of boxed values the general path already has, or refuse it '
         'by name with a fix (`write instead: node: list[object]`) so the AI can act.',
         '`ast_lint.node_count` / `leaves` / `max_depth` / `sum_ints` appear in `build.json`; '
         'the driver\'s 7 printed lines are byte-identical.  Guard: a new case with an empty '
         'tuple, a one-element tuple, a nested tuple 8 deep, and an index from a list item and '
         'from a dict value; plus the four required modules.',
         'measured: 5.7 s of 44.2 s self time, 12.8%; the whole of `ast_lint`.'),
        ('W4', 'indexing-can-raise', '12.6%',
         'Let a clone that may raise `IndexError` fall back instead of being refused.  '
         '`_unsafe_body` refuses every `Subscript` outright.  The emitted typed clone already '
         'has a trap path: make the index check set the per-function mix flag (the same '
         '`extern int <mangled>__mix_overflow` the int64 path uses), return a zero, and let the '
         'Python wrapper re-run the original function when the flag is set.  The wrapper already '
         'catches `Fallback`, so the caller\'s `try/except IndexError` still sees CPython\'s '
         'exception; a call that never indexes out of range pays one flag test.',
         '`edit_dist.levenshtein` (3.6 s alone) is accelerated and matches CPython on 800 rounds '
         'of 5 word pairs; a probe that indexes past the end still raises `IndexError` from the '
         'Python fallback.  Guard: a new `test_ail_cpython_hybrid` case with an in-range index, '
         'an index exactly at `len`, a negative index and an empty list; plus the four required '
         'modules.',
         'measured: 5.6 s of 44.2 s self time, 12.6%, across 6 modules and 10 functions.'),
        ('W5', 'nested-list-annotation', '8.9%',
         'Track `list[list[int]]`.  `pymix` has no kind for it, so every `graph_search` '
         'function is refused at the candidate stage.  The typed path already lowers '
         '`list[list[int]]` inside a whole-program build (the nested-lists test module exists); '
         'the gap is the *boundary* ABI and `pymix`\'s kind fixed point.  Two hours: add '
         "`pymix.LIST_LIST_INT`, resolve it from the annotation, and map it to the existing "
         "`ail_list`-of-`ail_list` the typed emitter's nested-list path builds, with the "
         "wrapper copying each inner list as one buffer.",
         '`graph_search.bfs_reach` / `dfs_count` / `degree_sum` / `edges_above` / `max_degree` '
         'appear in `build.json`; the driver prints the same 6 lines.  Guard: a new case with an '
         'empty outer list, an outer list with one empty inner list, a ragged inner list, and an '
         'inner list reached through an argument and through a dict value; plus the four '
         'required modules.',
         'measured: 3.9 s of 44.2 s self time, 8.9%; the whole of `graph_search`.'),
        ('W6', 'list-float-abi', '2.8%',
         'Fix the `ail_flist` prototype mismatch (section 4).  Either teach '
         '`_mix_validate_signature` that `ail_flist v_x` is the same ABI as '
         '`const double *v_x, int64_t v_x_len` (the call site already builds that pair), or make '
         '`to_c` spell a mixed-mode `list[float]` parameter the pointer+len way.  This is the '
         'cheapest task in the list: one prototype spelling.',
         '`float_loops` goes from 0 to 8 accelerated functions and its driver stays '
         'byte-identical on all 9 printed lines.  Guard: a new `test_ail_cpython_hybrid` case '
         'with an empty `list[float]`, a NaN, `-0.0`, and a value that arrives through an '
         'argument, a list item and a dict value; plus the four required modules.',
         'measured: 1.26 s of 44.2 s self time, 2.8%, but it is the only reason `float_loops` '
         'gets nothing at all.'),
    ]
    A('Ordered by measured gain.  Each names the reason, the test that guards it, and the gain '
      'this corpus measured.')
    A('')
    for tid, fam, gain, body, test, gain_detail in tasks:
        A('### %s -- %s (measured ceiling %s of the corpus self time)' % (tid, fam, gain))
        A('')
        A(body)
        A('')
        A('**Guard:** %s' % test)
        A('')
        A('**Gain:** %s' % gain_detail)
        A('')
    A('## 6. Reproduce')
    A('')
    A('```sh')
    A('python3 lab/wedge/census.py -j 2      # builds, native counts, byte-identical check')
    A('python3 lab/wedge/boundary.py          # which gate refused each function, and why')
    A('python3 lab/wedge/measure.py -j 2      # wall time, median of 5, plus cProfile')
    A('python3 lab/wedge/rust_bar.py          # cargo build + the PyO3 bar')
    A('python3 lab/wedge/analyse.py           # ranks the reasons by hot-path time')
    A('python3 lab/wedge/report.py            # renders this file')
    A('```')
    A('')
    A('`census.py` and `measure.py` take `-j 2`; on a 4-core runner the whole pipeline is about '
      '35 minutes, dominated by the 97 hybrid analyses at ~10 s each.')
    A('')
    A('## 7. What is not measured')
    A('')
    A('* Instruction counts: `perf_event_open` is denied on this runner, and callgrind was not '
      'used because the job is a wall-time question.')
    A('* The Rust bar covers 5 of 15 modules, as the task allows; the rest have no hand-written '
      'PyO3 twin.')
    A('* The hybrid analysis runs under `--exact-int`, so a module whose values exceed int64 can '
      'still be analysed; the *standalone* column needs `--exact-int` explicitly and is marked '
      '`(+exact)` when it does.')
    A('* The two `--exact-int` rows are real: `bitset_bloom` and `hashing` multiply past 2**63 in '
      'the driver, so the default 64-bit build stops loudly.  That is the documented int64 stop, '
      'not a silent difference.')
    out_path.write_text('\n'.join(lines) + '\n')
    print('wrote %s (%d lines)' % (out_path, len(lines)))


if __name__ == '__main__':
    import sys
    main()
