#!/usr/bin/env python3
"""Per-function boundary census: why each top-level function stays on CPython.

    python3 lab/wedge/boundary.py [-o lab/wedge/boundary.json]

Runs the hybrid's own analysis stack in-process (`_analysis`, `_select`) and, for every
top-level function that did not become a unit, walks the same gates `pymix.analyze`,
`pyboxed2._setup_mix` and `ail_cpython_hybrid._select` apply, so the record says which gate
stopped it and with which message.  The compiler is not changed.
"""
import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AIL = ROOT / 'AIL_CURRENT'
PKG = AIL / 'python' / 'pkg-v12'
for p in (str(AIL), str(PKG)):
    if p not in sys.path:
        sys.path.insert(0, p)

CORPUS = HERE / 'corpus'


def _ann_kind(node, pymix):
    if isinstance(node, ast.Name):
        return {'int': pymix.INT, 'float': pymix.FLOAT, 'str': pymix.STR,
                'bool': pymix.BOOL}.get(node.id)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
            and node.value.id == 'list':
        item = node.slice
        if isinstance(item, ast.Name) and item.id == 'int':
            return pymix.LIST_INT
        if isinstance(item, ast.Name) and item.id == 'float':
            return pymix.LIST_FLOAT
    return None


def _annotated_tree(source):
    """The functions grouped by the annotation kinds the hybrid seeds."""
    tree = ast.parse(source)
    return {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _to_c_reason(source, name, params, ret, pymix, pyfunc):
    """Why the typed emitter refuses this one function, or None when it accepts it.

    Returns (text, emitted_signature); the signature lets the caller name the ABI mismatch when
    the emitter accepted the function but `_mix_validate_signature` would reject its parameter
    spelling.
    """
    try:
        sig = pymix._scalar_sig(dict(params))
        csrc = pyfunc.to_c(source, entry=name, sig=sig)
    except Exception as error:
        return '%s: %s' % (type(error).__name__, str(error).strip().splitlines()[0][:300]), None
    if not csrc:
        return 'the typed emitter produced no unit', None
    emitted = None
    import re
    m = re.search(r'^([A-Za-z_][\w ]*\*?\s*\b%s\s*\([^\n{;]*\))\s*\{' % re.escape(name),
                  csrc, re.MULTILINE)
    if m:
        emitted = m.group(1)
    return None, emitted


def _validate_reason(emitted, params, ret, pymix, pyboxed2):
    """`_mix_validate_signature`'s own verdict on the emitted prototype, and the mismatch text."""
    if emitted is None:
        return 'no prototype found in the emitted unit'
    mangled = re.search(r'\b(\w+)\s*\(', emitted)
    name = mangled.group(1) if mangled else ''
    if pyboxed2._mix_validate_signature(emitted, name, params, ret):
        return None
    inside = emitted[emitted.index('(') + 1:emitted.rindex(')')]
    return 'the emitted prototype is %r' % inside.strip()


def _ann_text(node):
    try:
        return ast.unparse(node)
    except Exception:
        return '?'


def census_one(kind_dir):
    import ail_cpython_hybrid as hybrid
    import pymix
    import pyboxed2
    import pyfunc
    kind = kind_dir.name
    source = (kind_dir / (kind + '.py')).read_text()
    rec = {'module': kind, 'functions': {}, 'native': [], 'no_unit': []}
    tree = ast.parse(source)
    funcs = _annotated_tree(source)
    report, facts = hybrid._analysis(source)
    units = {u[1] for u in report.get('mix_units') or []}
    chosen, rejected = hybrid._select(source, tree, report, facts)
    # pymix's own view, with the hybrid's annotation seeding applied
    _old = pymix._FnFacts.__init__

    def _init(self, node):
        _old(self, node)
        for arg in node.args.args:
            k = _ann_kind(arg.annotation, pymix)
            if k is not None:
                self.params[arg.arg] = k
    pymix._FnFacts.__init__ = _init
    try:
        analysis = pymix.analyze(source)
    finally:
        pymix._FnFacts.__init__ = _old
    for name in sorted(funcs):
        info = facts.get(name)
        row = {'unit': name in units, 'native': name in chosen}
        if name in chosen:
            row['reason'] = None
            rec['native'].append(name)
        elif name in rejected:
            row['gate'] = 'select'
            row['reason'] = rejected[name]
        elif info is None:
            row['gate'] = 'pymix'
            why = analysis.rejected.get(name)
            row['reason'] = ('%s: %s' % (why[0], why[1])) if why else 'not a typed candidate'
            row['annotations'] = {
                a.arg: _ann_text(a.annotation) for a in funcs[name].args.args if a.annotation}
            row['returns'] = _ann_text(funcs[name].returns) if funcs[name].returns else ''
        else:
            row['gate'] = 'typed-emitter'
            params = [(p, k) for p, k in info.get('params') or []]
            reason, emitted = _to_c_reason(source, name, params, info.get('ret'), pymix, pyfunc)
            if reason is None:
                mismatch = _validate_reason(emitted, params, info.get('ret'), pymix, pyboxed2)
                if mismatch is None:
                    row['gate'] = 'no-unit'
                    reason = ('the typed emitter accepts it and its prototype matches, but the '
                              'hybrid analysis produced no unit')
                else:
                    row['gate'] = 'abi-mismatch'
                    reason = mismatch
                    row['emitted'] = emitted
            row['reason'] = reason
            row['annotations'] = {
                a.arg: _ann_text(a.annotation) for a in funcs[name].args.args if a.annotation}
            rec['no_unit'].append(name)
        rec['functions'][name] = row
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default=str(HERE / 'boundary.json'))
    args = ap.parse_args()
    dirs = sorted(p for p in CORPUS.iterdir() if (p / 'run.py').is_file())
    rows = []
    for d in dirs:
        rec = census_one(d)
        rows.append(rec)
        native = len(rec['native'])
        print('%-16s %d/%d native' % (rec['module'], native, len(rec['functions'])))
        for name, row in rec['functions'].items():
            if not row['native']:
                print('   %-22s %-13s %s' % (name, row['gate'], (row['reason'] or '')[:110]))
    Path(args.out).write_text(json.dumps(rows, indent=1) + '\n')
    total = sum(len(r['functions']) for r in rows)
    nat = sum(len(r['native']) for r in rows)
    print('%d modules, %d functions, %d native (%.1f%%)' % (len(rows), total, nat,
                                                           100.0 * nat / max(1, total)))


if __name__ == '__main__':
    main()
