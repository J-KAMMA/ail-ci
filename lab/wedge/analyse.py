#!/usr/bin/env python3
"""Rank the hybrid's refusal reasons by the hot-path time they keep on CPython.

    python3 lab/wedge/analyse.py [-o lab/wedge/analysis.json]

Inputs are the other three scripts' output: `census.json` (paths, native names, byte-identical
check), `boundary.json` (the gate and message per function) and `measure.json` (wall times and the
cProfile self-time per function).  A function's `tottime` is the time spent in its own bytecode, so
summing it over the functions that stayed on CPython, plus the driver's module-level time, is the
profiled time the CPython boundary keeps.  Each reason family is then ranked by that sum, and by
the number of functions and of modules it touches.

The first gate is only a ceiling: `_select` also applies `_unsafe_body` and then
`_list_param_mutated`, so a function fixed at its first gate can still be refused for indexing,
a call, an index store, a division or passing a list parameter to a call.  Each family therefore
also carries the `solo` time (functions with no other body gate) and the `with_w4` time (solo once
the indexing/index-store rule is also fixed).
"""
import argparse
import ast
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT / 'AIL_CURRENT'), str(ROOT / 'AIL_CURRENT' / 'python' / 'pkg-v12')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_BODY_OWN = {
    'indexing-can-raise': 'indexing',
    'call-can-raise': 'call',
    'division-can-raise': 'division',
    'list-parameter-mutated': 'list-param',
}


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


def _annotation_kind(text):
    """The parameter kinds `_unsafe_body` can reason about, from the printed annotation."""
    return text if text in ('int', 'float', 'bool', 'str', 'list[int]', 'list[float]') else None


def _body_blockers(fn, params=(), ret=None):
    """Every body gate `_select` would apply to this function, not only the first one.

    The first gate in `boundary.json` is where a refusal stops today; a function fixed at that
    gate can still be refused by an independent `_select` body rule.  This scan mirrors
    `ail_cpython_hybrid._unsafe_body` plus the `_list_param_mutated` gate that `_select` applies
    after it, collecting every category so the report can say which fixes a function needs
    together.
    """
    import ail_cpython_hybrid as hybrid
    str_names = {p for p, k in params if k == 'str'}
    list_names = {p for p, k in params if k in hybrid._LIST}
    num_names = {p for p, k in params if k in ('int', 'float', 'bool')}
    int_names = {p for p, k in params if k in ('int', 'bool')}
    float_names = {p for p, k in params if k == 'float'}
    bool_names = {p for p, k in params if k == 'bool'}
    cats = set()
    for node in hybrid._own_nodes(fn):
        if isinstance(node, ast.Subscript):
            cats.add('indexing')
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod,
                                                               ast.Pow)):
            if not (isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod))
                    and hybrid._nonzero_constant(node.right)):
                cats.add('division')
        if isinstance(node, ast.Call) and not hybrid._safe_call(
                node, str_names, list_names, num_names, int_names, float_names, ret, bool_names):
            cats.add('call')
        if isinstance(node, (ast.Raise, ast.Assert)):
            cats.add('raise')
        if isinstance(node, (ast.Try, ast.With, ast.Import, ast.ImportFrom)):
            cats.add('try')
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            cats.add('global')
        if isinstance(node, ast.Delete):
            cats.add('delete')
        if isinstance(node, (ast.Attribute, ast.Subscript)) \
                and isinstance(node.ctx, (ast.Store, ast.Del)):
            cats.add('store')
        if isinstance(node, (ast.Await, ast.Yield, ast.YieldFrom)):
            cats.add('yield')
    # `_select` applies `_list_param_mutated` after `_unsafe_body`: a function that mutates or
    # passes a list parameter on to any call (including `len`) stays in CPython even if its body
    # rule is otherwise satisfied.  Model the real predicate so `solo`/`+W4` do not count those.
    if hybrid._list_param_mutated(fn, list_names):
        cats.add('list-param')
    return cats


def _module_functions(module):
    src = (HERE / 'corpus' / module / (module + '.py')).read_text()
    tree = ast.parse(src)
    return {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


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
    fam_solo_time = defaultdict(float)
    fam_solo_funcs = defaultdict(int)
    fam_solo_examples = defaultdict(list)
    fam_w4_time = defaultdict(float)
    fam_w4_funcs = defaultdict(int)
    fam_w4_examples = defaultdict(list)
    fam_body_blockers = defaultdict(lambda: defaultdict(int))
    rows = []
    total_self = 0.0
    native_self = 0.0
    for module in sorted(census):
        m = measure[module]
        prof = m.get('profile') or {}
        b = boundary[module]
        funcs = _module_functions(module)
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
            node = funcs.get(fn)
            params = [(p, _annotation_kind(k)) for p, k in (row.get('annotations') or {}).items()]
            params = [(p, k) for p, k in params if k]
            ret = row.get('returns') if row.get('returns') in ('int', 'float', 'bool', 'str') else None
            cats = _body_blockers(node, params, ret) if node is not None else set()
            remaining = cats - ({_BODY_OWN[fam]} if fam in _BODY_OWN else set())
            with_w4 = remaining - {'indexing', 'store'}
            solo = not remaining
            rec['reasons'][fn] = {'family': fam, 'gate': row.get('gate'),
                                  'reason': row.get('reason'), 'self_s': round(t, 4),
                                  'body_blockers': sorted(remaining),
                                  'solo': solo, 'with_w4': not with_w4}
            fam_time[fam] += t
            fam_funcs[fam] += 1
            fam_modules[fam].add(module)
            if len(fam_examples[fam]) < 6:
                fam_examples[fam].append('%s:%s' % (module, fn))
            for cat in remaining:
                fam_body_blockers[fam][cat] += 1
            if solo:
                fam_solo_time[fam] += t
                fam_solo_funcs[fam] += 1
                if len(fam_solo_examples[fam]) < 8:
                    fam_solo_examples[fam].append('%s:%s' % (module, fn))
            if not with_w4:
                fam_w4_time[fam] += t
                fam_w4_funcs[fam] += 1
                if len(fam_w4_examples[fam]) < 8:
                    fam_w4_examples[fam].append('%s:%s' % (module, fn))
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
        solo_share = fam_solo_time[fam] / total_self if total_self else 0.0
        w4_share = fam_w4_time[fam] / total_self if total_self else 0.0
        ranked.append({'family': fam, 'self_s': round(fam_time[fam], 4),
                       'share_of_kept': round(fam_time[fam] / total_self, 4) if total_self else 0.0,
                       'functions': fam_funcs[fam], 'modules': sorted(fam_modules[fam]),
                       'examples': fam_examples[fam],
                       'body_blockers': dict(sorted(fam_body_blockers[fam].items())),
                       'solo_self_s': round(fam_solo_time[fam], 4),
                       'solo_share_of_kept': round(solo_share, 4),
                       'solo_functions': fam_solo_funcs[fam],
                       'solo_examples': fam_solo_examples[fam],
                       'with_w4_self_s': round(fam_w4_time[fam], 4),
                       'with_w4_share_of_kept': round(w4_share, 4),
                       'with_w4_functions': fam_w4_funcs[fam],
                       'with_w4_examples': fam_w4_examples[fam]})
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
