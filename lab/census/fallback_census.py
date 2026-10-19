#!/usr/bin/env python3
"""Fallback census: where the typed path refuses a program, and what function-level mixed mode
would recover (docs/design/MIXED_MODE.md section 6).

    python3 tools/fallback_census.py [--jobs 8] [--timeout 90] -o census.jsonl PROGRAM.py ...
    python3 tools/fallback_census.py --summary census.jsonl

For each program, one JSON record:
  typed         the default typed path builds the whole program
  first         the first typed refusal: reason, line, enclosing top-level unit (def / class /
                module statement / main), its size
  islands       the simulation of typed-host mixed mode: the function holding each refusal is cut
                out of the typed source and offered back to it as an external function with a
                scalar/str signature (`pyfunc.to_c(external=...)`, the mechanism separately
                compiled typed objects already use); repeated until the rest compiles or the
                refusal sits where a function island cannot go (main, module code, a class, a
                boundary that is not int/float/str)
  general       whether the general (boxed) path builds the program at all

Compile-only: no C compiler runs, nothing is executed. The source is prepared exactly as
`ail_chatgpt.py compile --syntax python` prepares it (python_surface, constant folding, local
imports), then shadowed built-ins are renamed as pyc.build does.
"""
import argparse
import ast
import collections
import contextlib
import io
import json
import multiprocessing
import os
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / 'AIL_CURRENT'
SCALAR = {'int', 'float', 'str'}


class _Timeout(Exception):
    pass


def _alarm(*_):
    raise _Timeout()


def _setup():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
    sys.setrecursionlimit(20000)
    signal.signal(signal.SIGALRM, _alarm)


def _prepare(path):
    import ail_chatgpt
    with contextlib.redirect_stderr(io.StringIO()):
        text, _, _ = ail_chatgpt._load_sources(Path(path), (), 'python', local_imports=True)
    import shadowing
    from pyfront import Unsupported
    return shadowing.rename_all(text, Unsupported)[0]


def _ann_kind(a):
    if a is None:
        return None
    if isinstance(a, ast.Constant) and a.value is None:
        return 'none'
    if isinstance(a, ast.Name):
        name = a.id
        if name == '__ail_checked_void__':
            return 'none'
        if name.startswith('__ail_checked_') and name.endswith('__'):
            name = name[len('__ail_checked_'):-2]
        return name if name in ('int', 'float', 'str', 'bool') else 'other:' + name
    return 'other:' + ast.unparse(a)[:40]


def _top_unit(tree, line):
    if line is None:
        return None
    for node in tree.body:
        if node.lineno <= line <= getattr(node, 'end_lineno', node.lineno):
            return node
    return None


def _unit_kind(node):
    if node is None:
        return 'noline'
    if isinstance(node, ast.FunctionDef):
        return 'main' if node.name == 'main' else 'def'
    return 'class' if isinstance(node, ast.ClassDef) else 'module'


def _signature(fn, facts):
    """(params, result) kinds: the annotation when there is one, else pymix's hypothesis."""
    f = facts.get(fn.name)
    params = []
    for a in fn.args.args:
        k = _ann_kind(a.annotation)
        if k is None and f is not None:
            k = f.params.get(a.arg)
        params.append((a.arg, k))
    if fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or fn.args.defaults:
        return params, 'other:defaults-or-varargs'
    r = _ann_kind(fn.returns)
    if r is None:
        returns_value = any(isinstance(n, ast.Return) and n.value is not None
                            and not (isinstance(n.value, ast.Constant) and n.value.value is None)
                            for n in ast.walk(fn))
        r = (f.ret if f is not None else None) if returns_value else 'none'
    return params, r


def _only_statement_calls(tree, name):
    parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    return all(isinstance(parents.get(n), ast.Expr) for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name)


def _globals_read(fn, tree):
    module = {x.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign))
              for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
              for x in ast.walk(t) if isinstance(x, ast.Name)}
    local = {a.arg for a in fn.args.args} | {n.id for n in ast.walk(fn)
                                            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    return sorted({n.id for n in ast.walk(fn) if isinstance(n, ast.Name)} & module - local)


def _islands(src, to_c, Unsupported):
    import pymix
    tree = ast.parse(src)
    try:
        facts = pymix._fixed_point(tree)
    except Exception:
        facts = {}
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    islands, exports, steps = [], {}, []
    for _ in range(10):
        body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name in islands)]
        rest = ast.unparse(ast.Module(body=body, type_ignores=[]))
        try:
            to_c(rest, strict=True, info={'_checked_arrays': True},
                 external={'exports': exports} if exports else None)
            return dict(result='typed', islands=islands, steps=steps)
        except Unsupported as e:
            reason = str(e).splitlines()[0][:160] if str(e) else ''
            line = getattr(e, 'source_line', None)
        node = _top_unit(ast.parse(rest), line)
        where = _unit_kind(node)
        stop = dict(result='stuck', where=where, reason=reason, line=line, islands=islands, steps=steps)
        if where != 'def':
            return stop
        fn = defs.get(node.name)
        if fn is None or node.name in islands:
            return dict(stop, where='repeat-or-nested')
        params, ret = _signature(fn, facts)
        steps.append(dict(fn=fn.name, lines=fn.end_lineno - fn.lineno + 1, params=params, ret=ret,
                          globals=_globals_read(fn, tree), reason=reason))
        if any(k not in SCALAR for _, k in params) or ret not in SCALAR | {'none'}:
            return dict(stop, where='boundary')
        if ret == 'none':
            if not _only_statement_calls(tree, fn.name):
                return dict(stop, where='boundary')
            ret = 'int'
        islands.append(fn.name)
        exports[fn.name] = dict(params=params, result=ret, symbol='ail_mixb_' + fn.name,
                                owned_str=ret == 'str', owned_bytes=False)
    return dict(result='stuck', where='limit', islands=islands, steps=steps)


def census_one(args):
    path, timeout = args
    import pyc
    import pyboxed2
    from pyfront import Unsupported
    rec = {'path': path}
    signal.alarm(timeout)
    try:
        src = _prepare(path)
        rec['lines'] = src.count('\n') + 1
        try:
            pyc.to_c(src, strict=True, info={'_checked_arrays': True})
            rec['typed'] = True
            return rec
        except Unsupported as e:
            rec['typed'] = False
            line = getattr(e, 'source_line', None)
            node = _top_unit(ast.parse(src), line)
            rec['first'] = dict(reason=str(e).splitlines()[0][:200] if str(e) else '', line=line,
                                unit=getattr(node, 'name', None) if node is not None else None,
                                kind=_unit_kind(node),
                                unit_lines=(node.end_lineno - node.lineno + 1) if node is not None else None)
        rec['islands'] = _islands(src, pyc.to_c, Unsupported)
        try:
            report = {}
            pyboxed2.build(src, report)
            rec['general'] = True
            rec['typed_clones'] = report.get('typed_inline', [])
        except Unsupported as e:
            rec['general'] = False
            rec['general_reason'] = str(e).splitlines()[0][:160] if str(e) else ''
    except _Timeout:
        rec['error'] = 'timeout'
    except Exception as e:  # a crash in the census must not stop the census
        rec['error'] = '%s: %s' % (type(e).__name__, str(e)[:200])
    finally:
        signal.alarm(0)
    return rec


def summary(path):
    rs = [json.loads(line) for line in open(path, encoding='utf-8')]
    c = collections.Counter()
    for r in rs:
        if 'error' in r:
            c['error'] += 1
        elif r['typed']:
            c['typed'] += 1
        else:
            c['general' if r.get('general') else 'refused by both paths'] += 1
    print('programs:', len(rs), dict(c))
    fallen = [r for r in rs if r.get('typed') is False and 'error' not in r]
    print('first refusal by unit:', dict(collections.Counter(r['first']['kind'] for r in fallen)))
    print('function islands, end state:', dict(collections.Counter(
        r['islands']['result'] + ':' + r['islands'].get('where', '') for r in fallen)))
    for r in fallen:
        if r['islands']['result'] == 'typed':
            print('  typed host with islands:', r['path'], r['islands']['islands'])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('programs', nargs='*')
    ap.add_argument('-o', '--output')
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--timeout', type=int, default=90)
    ap.add_argument('--summary')
    a = ap.parse_args()
    if a.summary:
        summary(a.summary)
        return 0
    if not a.output or not a.programs:
        ap.error('give -o OUTPUT and at least one program')
    with open(a.output, 'a', encoding='utf-8') as out, \
            multiprocessing.Pool(a.jobs, initializer=_setup, maxtasksperchild=8) as pool:
        for rec in pool.imap_unordered(census_one, [(p, a.timeout) for p in a.programs]):
            out.write(json.dumps(rec) + '\n')
            out.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
