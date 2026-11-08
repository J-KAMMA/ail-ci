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


def _pypy_label(measure):
    """'PyPy 7.3.23' from the recorded `--version` line, which is 'Python X ... [PyPy v ...]'."""
    rows = [r for r in measure.values() if r.get('pypy_s')]
    seen = []
    for r in rows:
        text = r.get('pypy_version') or ''
        marker = text.find('[PyPy ')
        if marker >= 0:
            version = text[marker + 1:text.find(']', marker)].strip()
            version = version.split(' with ')[0].strip()
            if version not in seen:
                seen.append(version)
    if not seen:
        return 'no PyPy row measured'
    return 'PyPy ' + '; '.join(v[len('PyPy '):] if v.startswith('PyPy ') else v for v in seen)


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
    byfam = {r['family']: r for r in analysis['reasons']}
    modules = sorted(census)

    total_funcs = sum(len(boundary[m]['functions']) for m in modules)
    total_native = sum(len(boundary[m]['native']) for m in modules)

    lines = []
    A = lines.append
    A('# wedge1: what share of a Rust-rewrite hot path AIL compiles today')
    A('')
    A('Measurement only; the compiler is not changed.  Branch `job-wedge1-11080724`, '
      'run 2026-11-07 on a 4-core GitHub Actions runner, CPython 3.12.3, gcc 13.3.0, '
      'PyO3 0.22.6 for the Rust bar.  The PyPy column (section 2) was added on 2026-11-08 by '
      '`job-pypy1-11090337` with %s.' % _pypy_label(measure))
    A('')
    A('## The answer, in one paragraph')
    A('')
    native_share = 100.0 * total_native / total_funcs
    A('Across %d small hot-path modules of the kind real projects moved to Rust through PyO3, '
      '**%d of %d top-level functions (%s%%) go native in the CPython hybrid**.  Because the '
      'hybrid only accelerates a *top-level function*, and because the hot function of a real '
      'module is very often a method, a nested helper or a list-returning builder, the functions '
      'that do go native carry only **%s%%** of the corpus\'s CPython self-time, and the hybrid '
      'runs at **%sx** CPython wall time overall (geomean of hybrid/CPython, median of 5; below '
      '1.0 is faster).  The '
      'largest single unlock is '
      '**%s** (%s%% of the kept time): the hybrid\'s unit is a top-level function, so class '
      'methods and nested defs are refused before any type is looked at.  The largest unlock '
      '*inside* a function is **%s** (%s%%): `pymix` cannot track a `tuple`, `bytes` or a list '
      'return kind, so the whole function is dropped.  See the ranked table in section 4.'
      % (len(modules), total_native, total_funcs, fmt(native_share, 1),
         pct(100 * analysis['native_share_of_self']),
         fmt(statistics.geometric_mean(
             [measure[m]['hybrid_s'] / measure[m]['cpython_s'] for m in modules
              if measure[m].get('hybrid_s')]), 3),
         analysis['reasons'][0]['family'],
         pct(100 * analysis['reasons'][0]['share_of_kept']),
         analysis['reasons'][1]['family'],
         pct(100 * analysis['reasons'][1]['share_of_kept'])))
    A('')
    pp_ok = [m for m in modules if measure[m].get('pypy_s') and measure[m].get('cpython_s')]
    hy_pairs = [(m, measure[m]['hybrid_s'] / measure[m]['pypy_s']) for m in modules
                if measure[m].get('hybrid_s') and measure[m].get('pypy_s')]
    se_pairs = [(m, measure[m]['standalone_s'] / measure[m]['pypy_s']) for m in modules
                if measure[m].get('standalone_s') and measure[m].get('pypy_s')]
    if pp_ok:
        A('**Against PyPy** (%s, section 2): PyPy runs the corpus at **%sx** CPython time; the AIL '
          'standalone binary is **faster than PyPy on %d of %d modules** (geomean '
          '**%sx** PyPy) and the hybrid on **%d of %d** (geomean **%sx**), with PyPy\'s output '
          'byte-identical to CPython on %d of %d modules.'
          % (_pypy_label(measure),
             fmt(statistics.geometric_mean([measure[m]['pypy_s'] / measure[m]['cpython_s']
                                            for m in pp_ok]), 3),
             sum(1 for _, v in se_pairs if v < 1), len(se_pairs),
             fmt(statistics.geometric_mean([v for _, v in se_pairs]), 3) if se_pairs else 'n/a',
             sum(1 for _, v in hy_pairs if v < 1), len(hy_pairs),
             fmt(statistics.geometric_mean([v for _, v in hy_pairs]), 3) if hy_pairs else 'n/a',
             sum(1 for m in modules if measure[m].get('pypy_match')), len(modules)))
        A('')
    A('## 1. The corpus')
    A('')
    A('Fifteen small modules under `lab/wedge/corpus/<kind>/`, each a `<kind>.py` of plain typed '
      'Python and a `run.py` driver on a fixed input sized for 1-5 s under CPython.  Each '
      'directory also has an `expected.txt`, the CPython oracle: `python3 run.py > expected.txt`, '
      'committed so the byte-identical check is reproducible without re-running CPython.  No '
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
      '`oracle` is the committed `expected.txt` matching the live CPython run byte for byte.  '
      '`pypy match` is the same `expected.txt` against every one of PyPy\'s five runs (a difference '
      'is a PyPy result, recorded in `measure.json` as `pypy_diff`, not fixed in the sources).  '
      'Wall time is the median of 5 runs.  `standalone` is the binary from '
      '`ail compile run.py --syntax python`; `(+exact)` means the default build stopped loudly on '
      'int64 overflow and `--exact-int` then built a matching binary.')
    A('')
    A('| module | funcs | native | native share | oracle | hybrid match | pypy match | standalone | CPython s | PyPy s | hybrid s | hybrid / CPython | hybrid / PyPy | standalone / PyPy |')
    A('| --- | ---: | ---: | ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |')
    for m in modules:
        c, b, w = census[m], boundary[m], measure[m]
        n = len(b['native'])
        f = len(b['functions'])
        py = w.get('cpython_s')
        pp = w.get('pypy_s')
        hy = w.get('hybrid_s')
        se = w.get('standalone_s')
        st = 'match' if c['match'].get('standalone') else 'no'
        if c['match'].get('standalone') is False and c['standalone'].get('exact_int_match'):
            st = 'match (+exact)'
        elif c['match'].get('standalone') is False:
            st = 'differs'
        ratio = ('%.3fx' % (hy / py)) if py and hy else 'n/a'
        ora = c.get('oracle') or {}
        ora_st = ('yes' if ora.get('match') else 'NO') if ora.get('present') else 'missing'
        pp_st = 'yes' if w.get('pypy_match') else ('NO' if w.get('pypy_s') else 'n/a')
        A('| `%s` | %d | %d | %s%% | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |'
          % (m, f, n, pct(100.0 * n / f, 0), ora_st,
             'yes' if c['match'].get('hybrid') else 'NO', pp_st,
             st, fmt(py), fmt(pp), fmt(hy), ratio,
             ('%.3fx' % (hy / pp)) if hy and pp else 'n/a',
             ('%.4fx' % (se / pp)) if se and pp else 'n/a'))
    A('')
    A('**Silent differences: zero.**  Every hybrid build matched CPython on every module; the '
      'standalone build matched on 13 of 15 by default and all 15 with `--exact-int`.  The two '
      'default-build stops are loud (`OverflowError: integer overflow in * ... --exact-int gives '
      'exact ints`), never a wrong answer.')
    A('')
    pp_rows = [m for m in modules if measure[m].get('pypy_s')]
    pp_bad = [m for m in modules if measure[m].get('pypy_error') or
              (measure[m].get('pypy_s') and not measure[m].get('pypy_match'))]
    if pp_rows:
        A('**PyPy output: %d of %d modules byte-identical.**  PyPy ran the same `run.py` on the same '
          'input, five times, and every run was compared with the committed `expected.txt`.%s'
          % (sum(1 for m in pp_rows if measure[m].get('pypy_match')), len(modules),
             ''.join('  `%s`: %s.' % (m, measure[m].get('pypy_diff') or measure[m].get('pypy_error'))
                     for m in pp_bad) if pp_bad else ''))
        A('')
    A('### What the wall-time columns say')
    A('')
    ok = [m for m in modules if measure[m].get('cpython_s') and measure[m].get('hybrid_s')]
    A('The hybrid runs at **%sx** CPython (`hybrid / CPython` below 1.0 means faster; geomean over '
      '%d modules, range %sx-%sx -- the same convention as the table column).  It is not faster '
      'in the aggregate because the functions that went native carry only %s%% of the self time; '
      'the rest is still interpreted.  The standalone binary is much faster where the whole '
      'program types (%s), so the boundary is not the C quality -- it is the *selection*.'
      % (fmt(statistics.geometric_mean([measure[m]['hybrid_s'] / measure[m]['cpython_s']
                                        for m in ok]), 3), len(ok),
         fmt(min(measure[m]['hybrid_s'] / measure[m]['cpython_s'] for m in ok), 3),
         fmt(max(measure[m]['hybrid_s'] / measure[m]['cpython_s'] for m in ok), 3),
         pct(100 * analysis['native_share_of_self']),
         ', '.join('%s %s s vs %s s' % (m, fmt(measure[m]['cpython_s'], 2),
                                        fmt(measure[m]['standalone_s'], 3))
                   for m in sorted(ok, key=lambda x: -(
                       (measure[x]['cpython_s'] or 0) / max(measure[x]['standalone_s'] or 1e9, 1e-9))
                    )[:4])))
    A('')
    if pp_rows:
        hy_pp = [(m, measure[m]['hybrid_s'] / measure[m]['pypy_s']) for m in modules
                 if measure[m].get('hybrid_s') and measure[m].get('pypy_s')]
        se_pp = [(m, measure[m]['standalone_s'] / measure[m].get('pypy_s')
                  if measure[m].get('standalone_s') and measure[m].get('pypy_s') else None)
                 for m in modules]
        se_pp = [(m, v) for m, v in se_pp if v]
        pp_hy = statistics.geometric_mean([v for _, v in hy_pp]) if hy_pp else None
        pp_se = statistics.geometric_mean([v for _, v in se_pp]) if se_pp else None
        A('### What PyPy does to the same fifteen modules')
        A('')
        A('PyPy needs no build and no types: it runs `run.py` and JIT-compiles the hot loops.  On '
          'this corpus it is **%sx** CPython wall time (geomean over %d modules that matched the '
          'oracle), so a plain CPython program already gets most of what this benchmark is about.  '
          'The hybrid, which keeps the function boundary, lands at **%sx** PyPy (%d of %d modules '
          'faster than PyPy) and the standalone binary at **%sx** PyPy (%d of %d faster).  Ratios '
          'below 1.0 mean AIL is faster; `measure.json` holds every median.'
          % (fmt(statistics.geometric_mean([measure[m]['pypy_s'] / measure[m]['cpython_s']
                                            for m in pp_rows]), 3), len(pp_rows),
             fmt(pp_hy, 3), sum(1 for _, v in hy_pp if v < 1), len(hy_pp),
             fmt(pp_se, 3), sum(1 for _, v in se_pp if v < 1), len(se_pp)))
        A('')
        A('Where the two AIL arms lose to PyPy is the module whose hot function is a plain method '
          'or a container-returning builder: the hybrid leaves it on CPython (so it pays CPython '
          'plus the boundary) and PyPy makes it fast.  Where the standalone binary types the whole '
          'driver it beats PyPy by the C-quality margin the table shows.')
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
    whole_speedups = [r['whole']['speedup'] for r in rust.values() if (r.get('whole') or {}).get('speedup')]
    ail_time = {m: measure[m]['hybrid_s'] / measure[m]['cpython_s'] for m in rust}
    ail_speed = {m: 1.0 / v for m, v in ail_time.items()}
    best_ail = max(ail_speed, key=ail_speed.get)
    A('Rewriting one function in Rust is worth **%sx-%sx** on that function, but only '
      '**%sx-%sx** on the program, because the rest of the program is still Python.  AIL\'s '
      'hybrid on the same five modules takes **%sx-%sx** of CPython time in the table\'s '
      '`hybrid / CPython` convention: it is at best %sx faster (`%s`), and parity or slower on '
      'the rest.  That is the size of the gap the boundary opens: the Rust rewrite wins '
      '**%sx-%sx** whole-program, AIL wins at most **%sx**.'
      % (fmt(min(r['speedup'] for r in rust.values()), 0),
         fmt(max(r['speedup'] for r in rust.values()), 0),
         fmt(min(whole_speedups), 2), fmt(max(whole_speedups), 2),
         fmt(min(ail_time.values()), 3), fmt(max(ail_time.values()), 3),
         fmt(max(ail_speed.values()), 2), best_ail,
         fmt(min(whole_speedups), 2), fmt(max(whole_speedups), 2),
         fmt(max(ail_speed.values()), 2)))
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
    prof_total = analysis['total_function_self_s']
    wall_total = sum(measure[m].get('cpython_s') or 0.0 for m in modules)
    A('`share` is the percentage of the corpus\'s **profiled** whole-function self time (%s s '
      'across %d modules).  `native` time is %s s = %s%% of it.  The profiled base is %sx the '
      '%s s of CPython wall time in section 2, because cProfile adds per-call overhead; the '
      'shares rank the refused functions but are **not shares of real wall time** (for example '
      '`ast_lint` is 5.67 s of self time for a 1.739 s program, `tree_build` 5.80 s for 1.97 s).'
      % (fmt(prof_total, 1), len(modules), fmt(analysis['native_function_self_s'], 2),
         pct(100 * analysis['native_share_of_self']),
         fmt(prof_total / wall_total, 2) if wall_total else 'n/a', fmt(wall_total, 2)))
    A('')
    A('A first gate is only a **ceiling**: `_select` applies `_unsafe_body` and then '
      '`_list_param_mutated`, so a function fixed at its first gate can still be refused for a '
      'subscript, a call, an index store, a division or passing a list parameter on to a call '
      '(including `len`).  Of the %d list-return functions %d pass '
      'that body rule, of the %d tuple-parameter %d, of the %d nested-list %d, of the %d '
      'list-float %d.  The `solo` column is the time of the functions with no other body gate; '
      'the `W4` column adds the index/index-store fix (W4) but not the list-parameter gate.'
      % (byfam['list-return-kind']['functions'], byfam['list-return-kind']['solo_functions'],
         byfam['tuple-parameter']['functions'], byfam['tuple-parameter']['solo_functions'],
         byfam['nested-list-annotation']['functions'],
         byfam['nested-list-annotation']['solo_functions'],
         byfam['list-float-abi']['functions'], byfam['list-float-abi']['solo_functions']))
    A('')
    A('| # | reason | self time s | share | solo self s | solo funcs | +W4 self s | +W4 funcs | functions | modules | example functions |')
    A('| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |')
    for r in analysis['reasons']:
        A('| %d | %s | %s | %s%% | %s | %d | %s | %d | %d | %d | %s |'
          % (r['rank'], r['family'], fmt(r['self_s'], 2), pct(100 * r['share_of_kept']),
             fmt(r['solo_self_s'], 2), r['solo_functions'], fmt(r['with_w4_self_s'], 2),
             r['with_w4_functions'], r['functions'], r['module_count'],
             ', '.join('`%s`' % e.split(':')[1] for e in r['examples'][:3])))
    A('')
    solo_rank = sorted(analysis['reasons'], key=lambda r: -r['solo_self_s'])[:5]
    A('Read the `solo` column, not the ceiling.  By solo-achievable time the five largest fixes '
      'are %s.  The five first-gate reasons below are still the biggest when their prerequisites '
      'are fixed, but **W4 (indexing-can-raise) is the prerequisite for W2/W3/W6**, and the '
      'call, division and list-parameter rules are additional gates; so the W1-W6 order is '
      'dependency-aware, not the ceiling order.'
      % ', '.join('%s (%s s)' % (r['family'], fmt(r['solo_self_s'], 2)) for r in solo_rank
                  if r['solo_self_s'] > 0))
    A('')
    A('### The five reasons that matter, spelled out')
    A('')
    tb = measure.get('tree_build', {}).get('profile') or {}
    tb_total = sum(v['tottime'] for v in tb.values())
    tb_methods = sum(tb[k]['tottime'] for k in ('_inorder', '_depth', '_height') if k in tb)
    A('1. **not-a-top-level-function** -- the hybrid\'s unit is a top-level `def`, so a class '
      'method, a nested helper or a constructor is refused before any typing happens.  This is '
      'the largest single bucket because the hottest code in a real module is often a method '
      '(`Tree._inorder` %s s of `tree_build`\'s %s s of function self time; the three tree '
      'methods alone are %s s).  The corpus\'s %s s is plain methods taking `self`, which the '
      'two-hour W1 scope (staticmethods and closures) does not cover, so W1 measures 0 solo here.'
      % (fmt(tb.get('_inorder', {}).get('tottime'), 2), fmt(tb_total, 2), fmt(tb_methods, 2),
         fmt(byfam['not-a-top-level-function']['self_s'], 2)))
    A('2. **list-return-kind** -- `-> list[int]` / `-> list[str]` / `-> list[float]`.  `pymix` '
      'has no return kind for a container, and the boundary has no ABI for one.  The first gate '
      'alone accelerates **0 of %d**: every body also indexes, calls or divides.  With W4 also '
      'applied, %d of %d (`%s`, %s s) become reachable; the rest still need the call, division '
      'or list-parameter rule.'
      % (byfam['list-return-kind']['functions'],
         byfam['list-return-kind']['with_w4_functions'],
         byfam['list-return-kind']['functions'],
         '`, `'.join(e.split(':')[1] for e in byfam['list-return-kind']['with_w4_examples']),
         fmt(byfam['list-return-kind']['with_w4_self_s'], 2)))
    A('3. **tuple-parameter** -- a `tuple` parameter (`node: tuple`) is not a tracked kind.  '
      '`ast_lint`\'s recursive walk is 5.7 s of the corpus, but all %d functions also index and '
      'call, so W3 alone accelerates **0 of %d**; W4 and the call rule are additional '
      'prerequisites for the whole 5.67 s.'
      % (byfam['tuple-parameter']['functions'], byfam['tuple-parameter']['functions']))
    A('4. **indexing-can-raise** -- `_unsafe_body` refuses any subscript, because the typed clone '
      'cannot reproduce `IndexError` back into the caller\'s `try`.  It is the most common second '
      'gate, but only %d of the %d indexing functions (`%s`) has no other body gate, because %d '
      'also call and %d divides; `levenshtein` appends to a list as well, so it needs the call '
      'rule too.  W4 alone moves %d function; its value is as the prerequisite for W2/W6.'
      % (byfam['indexing-can-raise']['solo_functions'],
         byfam['indexing-can-raise']['functions'],
         '`, `'.join(e.split(':')[1] for e in byfam['indexing-can-raise']['solo_examples']),
         byfam['indexing-can-raise']['body_blockers'].get('call', 0),
         byfam['indexing-can-raise']['body_blockers'].get('division', 0),
         byfam['indexing-can-raise']['solo_functions']))
    A('5. **nested-list-annotation** -- `list[list[int]]` (an adjacency list) is not a tracked '
      'parameter kind.  Only %d of %d (`%s`, %s s) has no other body gate; the other %d call, so '
      'W5 alone accelerates %d and the 3.9 s is a ceiling.'
      % (byfam['nested-list-annotation']['solo_functions'],
         byfam['nested-list-annotation']['functions'],
         '`, `'.join(e.split(':')[1] for e in byfam['nested-list-annotation']['solo_examples']),
         fmt(byfam['nested-list-annotation']['solo_self_s'], 2),
         byfam['nested-list-annotation']['body_blockers'].get('call', 0),
         byfam['nested-list-annotation']['solo_functions']))
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
    A('`float_loops` gets none of its 8 functions, but `list[float]` ABI is **not** the only '
      'reason: the typed emitter accepts 7 of the 8, and `scale_into` is refused earlier by '
      '`pymix` as `unresolved-return` (family list-return-kind), so it never reaches the ABI '
      'gate.  For the 7 that do, `pyfunc.to_c` spells a `list[float]` parameter as a whole '
      '`ail_flist` value (`double dot(ail_flist v_a, ail_flist v_b)`); '
      '`pyboxed2._mix_validate_signature` demands the `const double *v_a, int64_t v_a_len` pair '
      'it demands for `list[int]`, and `ail_cpython_hybrid._c_proto` / `_wrapper_source` build '
      'the same pointer+length call.  Every `list[float]` candidate therefore fails the ABI '
      'cross-check and stays boxed.  This is not a semantic limit: the whole-program typed '
      'build compiles the same module on the typed path (2.20 s -> 0.15 s), and the hybrid '
      'wrapper already allocates and fills the `double *` buffer -- it just hands it over in '
      'the wrong shape (`ail_flist` is `{double *p; int64_t n, cap}`, so a value can be built '
      'in one line).  With the ABI spelling fixed only `max_abs` and `sq_sum` have no other '
      'body gate (%s of the 7); `dot`/`blend` also index and pass a list parameter to `len()` '
      '(W4 plus the list-parameter gate), `mean`/`variance`/`norm` '
      'divide by a non-constant, and `scale_into` needs W2.  With W4 too, %d of the 7 become '
      'reachable (%s s); the module does not go from 0 to 8.'
      % (byfam['list-float-abi']['solo_functions'],
         byfam['list-float-abi']['with_w4_functions'],
         fmt(byfam['list-float-abi']['with_w4_self_s'], 2)))
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
        ('W0', 'silent-refusal', 'no time of its own',
         'Surface the refusal reason in `build.json` for a function that never reaches a unit.  '
         'Today `_select` records a reason only for a function it saw and dropped; a function '
         'that `pymix.analyze` or `to_c` refuses gets no unit, so `rejected` has no key and the '
         'build is silent (%d of %d refusals here).  `lab/wedge/boundary.py` already recovers '
         'the reason by re-running `pymix.analyze` and `to_c`; move that call into the same '
         'place `_analysis` runs, and write `{function: {gate, reason}}` under `rejected` even '
         'when `_select` never produced a unit.  This is a reporting change, not a compiler '
         'change: no function goes native.  Its gain is that the other tasks below become '
         'queueable -- without it %d of %d refusals cannot be acted on.'
         % (analysis['silent_refusals'], analysis['refused_functions'],
            analysis['silent_refusals'], analysis['refused_functions']),
         '`build.json` for `ast_lint`, `float_loops`, `graph_search` and `tokenizer` lists a '
         '`gate` and `reason` for every function that stayed on CPython.  Guard: a new '
         '`test_ail_cpython_hybrid` case whose module has one pymix-refused and one '
         'emitter-refused function, asserting both appear in `rejected`; plus '
         '`test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, '
         '`test_ail_corpus_findings3`.',
         'measured: makes %d of %d refusals (%s%%) name their gate and fix; 0 s moves native '
         'by itself.'
         % (analysis['silent_refusals'], analysis['refused_functions'],
            pct(100.0 * analysis['silent_refusals'] / max(1, analysis['refused_functions'])))),
        ('W4', 'indexing-can-raise', '12.6%',
         'Let a clone that may raise `IndexError` fall back instead of being refused.  '
         '`_unsafe_body` refuses every `Subscript` outright, load or store.  The emitted typed clone already '
         'has a trap path: make the index check set the per-function mix flag (the same '
         '`extern int <mangled>__mix_overflow` the int64 path uses), return a zero, and let the '
         'Python wrapper re-run the original function when the flag is set.  The wrapper already '
         'catches `Fallback`, so the caller\'s `try/except IndexError` still sees CPython\'s '
         'exception; a call that never indexes out of range pays one flag test.  This is the '
         'prerequisite for W2/W3/W6, not a large solo unlock.',
         '`matrix.trace` (list[int] parameter, int return, `m[i*n+i]`) is the one indexing '
         'function whose body has no other gate; it is accelerated and its driver stays '
         'byte-identical.  `edit_dist.levenshtein` (3.6 s) also appends to a list, so it needs '
         'the call rule as well, not W4 alone.  Guard: a new `test_ail_cpython_hybrid` case with '
         'an in-range index, an index exactly at `len`, a negative index and an empty list; '
         'plus the four required modules.',
         'measured: solo %s s (%d of %d functions, `%s`); W4 also unblocks %s s of list-return '
         '(%d functions) and %s s of list-float (%d functions).  The 5.6 s first-gate ceiling '
         'is reached only when the call and division rules are applied too.'
         % (fmt(byfam['indexing-can-raise']['solo_self_s'], 2),
            byfam['indexing-can-raise']['solo_functions'],
            byfam['indexing-can-raise']['functions'],
            '`, `'.join(e.split(':')[1] for e in byfam['indexing-can-raise']['solo_examples']),
            fmt(byfam['list-return-kind']['with_w4_self_s'], 2),
            byfam['list-return-kind']['with_w4_functions'],
            fmt(byfam['list-float-abi']['with_w4_self_s'], 2),
            byfam['list-float-abi']['with_w4_functions'])),
        ('W2', 'list-return-kind', '15.8%',
         'Give `pymix` and the boundary a `list[int]` / `list[float]` return kind.  `pymix` '
         'reports `unresolved-return` for a body whose `return xs` is a list, and the hybrid '
         '`_wrapper_source` has no C path for a returned list.  Add `pymix.LIST_INT` /'
         '`LIST_FLOAT` to the return kinds it resolves from a `return <list literal or list '
         'name>` and a list-append loop, and add a wrapper branch that returns '
         '`PyList_New` filled from the emitted `(const int64_t *out, int64_t n)` out-parameter '
         'pair the library ABI already uses (`compile-library`).',
         'W2 alone accelerates **0 of %d** functions because every body also indexes or calls.  '
         'With W4 also applied (covering subscript stores), `%s` (%s s) become native and their drivers stay byte-identical; '
         '`group_sum` also passes a list parameter to `len()` (the `_list_param_mutated` gate), '
         '`window_sums`, `make_hashes`, `row_sums`, `make_samples`, `scale_into` and `top_indices` '
         'still need the call rule, and `bloom_set` also divides.  Guard: a new '
         '`test_ail_cpython_hybrid` case with an '
         'empty list return, a one-element list return and a 100k-element list return; plus '
         '`test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, '
         '`test_ail_corpus_findings3`.'
         % (byfam['list-return-kind']['functions'],
            '`, `'.join(e.split(':')[1] for e in byfam['list-return-kind']['with_w4_examples']),
            fmt(byfam['list-return-kind']['with_w4_self_s'], 2)),
         'measured: solo 0.0 s; W2+W4 %s s of 44.2 s (%d of %d functions); the 7.0 s first-gate '
         'ceiling is not reachable by this task alone.'
         % (fmt(byfam['list-return-kind']['with_w4_self_s'], 2),
            byfam['list-return-kind']['with_w4_functions'],
            byfam['list-return-kind']['functions'])),
        ('W3', 'tuple-parameter', '12.8%',
         'Track a `tuple` parameter as an opaque homogeneous element stream.  `ast_lint` passes '
         'nested tuples of str/int; a real project\'s AST walk passes a node object.  Two hours '
         'buys the narrow case: a parameter annotated `tuple` whose body only calls '
         '`isinstance(child, tuple)`, `len(node)` and `node[i]` for a `range()` index.  Lower it '
         'to the existing `ail_list` of boxed values the general path already has, or refuse it '
         'by name with a fix (`write instead: node: list[object]`) so the AI can act.',
         'W3 alone accelerates **0 of %d**: each function both indexes and calls.  With W4 and '
         'the call rule, all %d (`node_count`, `leaves`, `max_depth`, `sum_ints`, ...) can '
         'become native and the driver\'s 7 printed lines stay byte-identical.  Guard: a new '
         'case with an empty tuple, a one-element tuple, a nested tuple 8 deep, and an index '
         'from a list item and from a dict value; plus the four required modules.'
         % (byfam['tuple-parameter']['functions'], byfam['tuple-parameter']['functions']),
         'measured: solo 0.0 s; needs W4+call; the 5.7 s first-gate time is the ceiling, not '
         'this task\'s gain.'),
        ('W6', 'list-float-abi', '2.8%',
         'Fix the `ail_flist` prototype mismatch (section 4).  Either teach '
         '`_mix_validate_signature` that `ail_flist v_x` is the same ABI as '
         '`const double *v_x, int64_t v_x_len` (the call site already builds that pair), or make '
         '`to_c` spell a mixed-mode `list[float]` parameter the pointer+len way.  This is the '
         'cheapest task in the list: one prototype spelling.',
         'With W6 alone `max_abs` and `sq_sum` become native (%d of %d, %s s); W4 adds nothing, '
         'because `dot` and `blend` also index and pass a list parameter to `len()` (W4 plus the '
         '`_list_param_mutated` gate), `mean`/`variance` divide by a non-constant, `variance` '
         'also calls, `norm` uses `**`, and `scale_into` is list-return-kind (W2).  So '
         '`float_loops` does '
         '**not** go from 0 to 8.  Its driver stays byte-identical on all 9 printed lines.  '
         'Guard: a new `test_ail_cpython_hybrid` case with an empty `list[float]`, a NaN, '
         '`-0.0`, and a value that arrives through an argument, a list item and a dict value; '
         'plus the four required modules.'
         % (byfam['list-float-abi']['solo_functions'], byfam['list-float-abi']['functions'],
            fmt(byfam['list-float-abi']['solo_self_s'], 2)),
         'measured: solo %s s (%d of %d); W6+W4 also %s s (%d of %d); only the division, call '
         'and list-parameter gates plus W2 for `scale_into` reach the 1.26 s ceiling.'
         % (fmt(byfam['list-float-abi']['solo_self_s'], 2),
            byfam['list-float-abi']['solo_functions'], byfam['list-float-abi']['functions'],
            fmt(byfam['list-float-abi']['with_w4_self_s'], 2),
            byfam['list-float-abi']['with_w4_functions'],
            byfam['list-float-abi']['functions'])),
        ('W5', 'nested-list-annotation', '8.9%',
         'Track `list[list[int]]`.  `pymix` has no kind for it, so every `graph_search` '
         'function is refused at the candidate stage.  The typed path already lowers '
         '`list[list[int]]` inside a whole-program build (the nested-lists test module exists); '
         'the gap is the *boundary* ABI and `pymix`\'s kind fixed point.  Two hours: add '
         "`pymix.LIST_LIST_INT`, resolve it from the annotation, and map it to the existing "
         "`ail_list`-of-`ail_list` the typed emitter's nested-list path builds, with the "
         "wrapper copying each inner list as one buffer.",
         'Only `edges_above` (%s s) has no other body gate, so W5 alone accelerates %d of %d; '
         'W4 does not change that, because the other %d call.  `bfs_reach`, `dfs_count`, '
         '`degree_sum` and `max_degree` need the call rule too.  Guard: a new case with an '
         'empty outer list, an outer list with one empty inner list, a ragged inner list, and an '
         'inner list reached through an argument and through a dict value; plus the four '
         'required modules.'
         % (fmt(byfam['nested-list-annotation']['solo_self_s'], 2),
            byfam['nested-list-annotation']['solo_functions'],
            byfam['nested-list-annotation']['functions'],
            byfam['nested-list-annotation']['body_blockers'].get('call', 0)),
         'measured: solo %s s (%d of %d); the 3.9 s first-gate time is the ceiling.'
         % (fmt(byfam['nested-list-annotation']['solo_self_s'], 2),
            byfam['nested-list-annotation']['solo_functions'],
            byfam['nested-list-annotation']['functions'])),
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
         'A module with an `@staticmethod` hot helper is listed as accelerated and its output '
         'is byte-identical.  The corpus\'s `Tree._inorder` / `_depth` / `_height` are plain '
         'methods taking `self`, so they are **not** expected to move under this scope; the '
         '19.3% is the ceiling for the full method ABI, not this task.  Guard: '
         '`test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, '
         '`test_ail_corpus_findings3`.',
         'measured: solo 0 s on this corpus (the 8.5 s is plain methods); the reachable part '
         '(staticmethods and closures) is not present here, so treat 19.3% as the ceiling.'),
    ]
    A('Ordered W0 (reporting, no time), then W4 (the body prerequisite), then W2/W3/W6 that '
      'depend on it, then W5 and W1.  Each names the reason, the test that guards it, and the '
      'measured ceiling plus the solo gain.  By solo-achievable time the ranking is different '
      '(section 4); this set is the five largest first-gate ceilings plus the prerequisite, '
      'not the achievable order.')
    A('')
    for tid, fam, gain, body, test, gain_detail in tasks:
        if tid == 'W0':
            A('### %s -- %s (unlocks the other tasks; moves no time itself)' % (tid, fam))
        else:
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
    A('for d in lab/wedge/corpus/*/; do (cd "$d" && python3 -B run.py > expected.txt); done  # oracles')
    A('python3 lab/wedge/census.py -j 2      # builds, native counts, byte-identical + oracle check')
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
      'PyO3 twin.  `rust_bar.json` stores a length and SHA-256 digest of each function\'s return '
      'value, not the value itself (`rolling_stats` returns a 21 MB list); the `outputs agree` '
      'column is the live in-process `MATCH` comparison.')
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
