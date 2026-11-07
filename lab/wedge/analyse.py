#!/usr/bin/env python3
"""Rank the hybrid's refusal reasons by the hot-path time they keep on CPython.

    python3 lab/wedge/analyse.py [-o lab/wedge/analysis.json]

Inputs are the other three scripts' output: `census.json` (paths, native names, byte-identical
check), `boundary.json` (the gate and message per function) and `measure.json` (wall times and the
cProfile self-time per function).  A function's `tottime` is the time spent in its own bytecode, so
summing it over the functions that stayed on CPython, plus the driver's module-level time, is the
wall time the CPython boundary keeps.  Each reason family is then ranked by that sum, and by the
number of functions and of modules it touches.
"""
import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _first_blocker(annotations, returns):
    """The annotation spelling that stopped pymix, from the function's own annotations.

    `unresolved-param`/`unresolved-return` are the analysis's summary; the actionable fix is the
    annotation kind behind it, so this names that instead of a catch-all.
    """
    kinds = set((annotations or {}).values())
    if returns:
        kinds.add(returns)
    if any(k.startswith('list[list') for k in kinds):
        return 'nested-list-annotation'
    if 'bytes' in kinds:
        return 'bytes-parameter'
    if 'tuple' in kinds:
        return 'tuple-parameter'
    if any(k.startswith('list[str]') for k in kinds):
        return 'list-str-parameter'
    if 'list' in kinds:
        return 'unannotated-list-parameter'
    if 'Tree' in kinds:
        return 'user-class-annotation'
    if any(k.startswith('list[') for k in kinds):
        return 'list-return-kind'
    return None


def family(reason, gate, annotations=None, returns=''):
    """Collapse one function's raw reason into the boundary fix that would unlock it."""
    r = reason or ''
    if gate == 'select':
        if r == 'indexing can raise':
            return 'indexing-can-raise'
        if r == 'division or power can raise':
            return 'division-can-raise'
        if r == 'a call can raise or have side effects':
            return 'call-can-raise'
        if r == 'the list parameter is mutated':
            return 'list-parameter-mutated'
        if r.startswith('result kind'):
            return 'result-kind'
        if r.startswith('parameter kind'):
            return 'parameter-kind'
        return 'select:' + r
    if gate == 'pymix':
        if r.startswith('unresolved-param') or r.startswith('unresolved-return'):
            named = _first_blocker(annotations, returns)
            return named or 'untyped-return-kind'
        if 'to_c-refused' in r:
            if 'read before it is assigned' in r:
                return 'module-constant'
            if 'annotated tuple in the source' in r:
                return 'tuple-parameter'
            if 'returning Subscript as a list' in r:
                return 'list-return'
            if 'bool' in r:
                return 'bool-expression-return'
            return 'typed-emitter:' + r.split(':', 1)[1].strip()[:60]
        return 'pymix:' + r[:60]
    if gate == 'abi-mismatch':
        if 'ail_flist' in r:
            return 'list-float-abi'
        return 'abi-mismatch'
    if gate in ('typed-emitter', 'no-unit'):
        return 'no-unit-wired'
    return gate + ':' + r[:60]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default=str(HERE / 'analysis.json'))
    args = ap.parse_args()
    census = {r['module']: r for r in json.loads((HERE / 'census.json').read_text())}
    boundary = {r['module']: r for r in json.loads((HERE / 'boundary.json').read_text())}
    measure = {r['module']: r for r in json.loads((HERE / 'measure.json').read_text())}
    fam_time = defaultdict(float)
    fam_funcs = defaultdict(int)
    fam_modules = defaultdict(set)
    fam_examples = defaultdict(list)
    rows = []
    total_self = 0.0
    native_self = 0.0
    for module in sorted(census):
        m = measure[module]
        prof = m.get('profile') or {}
        b = boundary[module]
        rec = {'module': module, 'functions': len(b['functions']),
               'native': sorted(b['native']), 'reasons': {}, 'self_s': {}}
        for fn, info in prof.items():
            if fn == '<module>':
                continue
            total_self += info['tottime']
        for fn, row in b['functions'].items():
            t = (prof.get(fn) or {}).get('tottime', 0.0)
            rec['self_s'][fn] = round(t, 4)
            if row['native']:
                native_self += t
                continue
            fam = family(row.get('reason'), row.get('gate'), row.get('annotations'), row.get('returns'))
            rec['reasons'][fn] = {'family': fam, 'gate': row.get('gate'),
                                  'reason': row.get('reason'), 'self_s': round(t, 4)}
            fam_time[fam] += t
            fam_funcs[fam] += 1
            fam_modules[fam].add(module)
            if len(fam_examples[fam]) < 6:
                fam_examples[fam].append('%s:%s' % (module, fn))
        # profile rows that are not top-level functions of the module: methods, nested defs,
        # constructors.  The hybrid's unit is a top-level function, so these stay on CPython
        # for a structural reason rather than a body one.
        known = set(b['functions'])
        for fn, info in prof.items():
            if fn == '<module>' or fn in known:
                continue
            fam_time['not-a-top-level-function'] += info['tottime']
            fam_funcs['not-a-top-level-function'] += 1
            fam_modules['not-a-top-level-function'].add(module)
            if len(fam_examples['not-a-top-level-function']) < 8:
                fam_examples['not-a-top-level-function'].append('%s:%s' % (module, fn))
            rec['reasons'].setdefault(fn, {'family': 'not-a-top-level-function',
                                           'gate': 'unit-shape',
                                           'reason': 'a method, nested def or constructor',
                                           'self_s': round(info['tottime'], 4)})
            rec['self_s'][fn] = round(info['tottime'], 4)
        rows.append(rec)
    # time outside any module function (driver loop, builtins) is CPython's too, but it is not
    # attributable to one refusal; report it separately
    ranked = []
    for fam in fam_time:
        ranked.append({'family': fam, 'self_s': round(fam_time[fam], 4),
                       'share_of_kept': round(fam_time[fam] / total_self, 4) if total_self else 0.0,
                       'functions': fam_funcs[fam], 'modules': sorted(fam_modules[fam]),
                       'examples': fam_examples[fam]})
    ranked.sort(key=lambda r: -r['self_s'])
    for i, r in enumerate(ranked, 1):
        r['rank'] = i
        r['module_count'] = len(r['modules'])
    doc = {'total_function_self_s': round(total_self, 4),
           'native_function_self_s': round(native_self, 4),
           'native_share_of_self': round(native_self / total_self, 4) if total_self else 0.0,
           'reasons': ranked, 'modules': rows,
           'census': {k: {'functions': len(v.get('functions') or []),
                          'native': len((v.get('hybrid') or {}).get('accelerated') or []),
                          'hybrid_match': v['match'].get('hybrid'),
                          'standalone_match': v['match'].get('standalone'),
                          'standalone_exact_int_match': (v.get('standalone') or {}).get(
                              'exact_int_match')} for k, v in census.items()}}
    Path(args.out).write_text(json.dumps(doc, indent=1) + '\n')
    print('total function self time %.3f s' % total_self)
    for r in ranked:
        print('%2d %-24s self=%7.3fs share=%5.1f%% funcs=%-3d modules=%d  %s'
              % (r['rank'], r['family'], r['self_s'], 100 * r['share_of_kept'], r['functions'],
                 r['module_count'], ','.join(r['examples'][:3])))
    print('wrote %s' % args.out)


if __name__ == '__main__':
    main()
