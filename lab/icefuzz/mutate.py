#!/usr/bin/env python3
"""Seeded AST mutator for compiler crash fuzzing.

    python3 lab/icefuzz/mutate.py --seed 7 -o /tmp/m.py
    python3 lab/icefuzz/mutate.py --seed 7 --show

A seed always selects and mutates the same corpus program.  Every candidate is
parsed again and executed by CPython 3.12 with a 5 s limit; candidates that do
not parse or finish are discarded and the next deterministic attempt is tried.
"""
import argparse
import ast
import builtins
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CAP = 1 << 20

# Corpus groups named by the job.  Heavy lowering paths (regular expressions,
# decimal, datetime) are left out: one mutant can spend the whole 60 s compile
# limit there, which would crowd out the rest of a 2000-mutant run.  Long
# compare programs are capped for the same reason.  The cap and exclusions are
# recorded in RESULTS.md.
EXCLUDED_STDLIB = {'re', 'decimal', 'datetime'}
# Modules whose lowering is known to fit the per-mutant compile budget.  This
# keeps 2000 mutants inside the job's 60 minutes; it still spans many language
# and stdlib surfaces (arrays, text, numbers, files, sqlite, graph, heap, ...).
FAST_STDLIB = {'array', 'base64', 'bisect', 'collections', 'graphlib', 'hashlib',
               'heapq', 'keyword', 'math', 'numbers', 'random', 'sqlite3', 'stat',
               'statistics', 'string', 'token'}
EXCLUDED_COMPARE = {'term_rank'}
MAX_STDLIB_LINES = 18
MAX_COMPARE_LINES = 120
MAX_LIMIT_LINES = 40
HEAVY_IMPORT = re.compile(r'(?m)^\s*(?:from|import)\s+(?:re|decimal|datetime|tomllib)\b')

BUILTIN_NAMES = set(dir(builtins))

MUTATORS = []


def mutator(fn):
    MUTATORS.append((fn.__name__, fn))
    return fn


def _line_count(path):
    try:
        return sum(1 for _ in path.open('rb'))
    except OSError:
        return 1 << 30


def _group_files(group, pattern, max_lines, excluded=(), allowed=None):
    out = []
    for p in sorted(ROOT.glob(pattern)):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in excluded for part in rel.parts):
            continue
        if allowed is not None and rel.parent.name not in allowed:
            continue
        if _line_count(p) > max_lines:
            continue
        try:
            if HEAVY_IMPORT.search(p.read_text(encoding='utf-8')):
                continue
        except (OSError, UnicodeDecodeError):
            continue
        out.append(p)
    return out


def corpus_groups():
    return {
        'stdlib': _group_files('stdlib', 'lab/stdlib/*/*.py',
                               MAX_STDLIB_LINES, EXCLUDED_STDLIB, FAST_STDLIB),
        'compare': _group_files('compare', 'lab/compare/src/*/main.py',
                                MAX_COMPARE_LINES, EXCLUDED_COMPARE),
        'limits': _group_files('limits', 'lab/limits/*.py', MAX_LIMIT_LINES),
    }


CORPUS = corpus_groups()


def corpus_files():
    """All corpus files used by the mutator (for tests and reporting)."""
    return [p for g in ('stdlib', 'compare', 'limits') for p in CORPUS[g]]


def _pick_file(rng):
    group = rng.choices(('stdlib', 'compare', 'limits'), weights=(75, 5, 20))[0]
    return rng.choice(CORPUS[group])


def _names(tree):
    seen = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            seen.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            seen.add(n.name)
        elif isinstance(n, ast.arg):
            seen.add(n.arg)
    return seen


def _fresh(tree, base):
    used = _names(tree)
    name = base
    n = 0
    while name in used:
        n += 1
        name = '%s%d' % (base, n)
    return name


def _expr_nodes(tree):
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.expr)
            and not (isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)))]


def _stmt_lists(tree):
    """(owner, field, list) for every statement list in the tree."""
    out = []
    for node in ast.walk(tree):
        for field, value in ast.iter_fields(node):
            if (isinstance(value, list) and value
                    and all(isinstance(x, ast.stmt) for x in value)):
                out.append((node, field, value))
    return out


def _body_lists(tree):
    out = [(n, f, v) for n, f, v in _stmt_lists(tree)
           if f in ('body', 'orelse', 'finalbody')]
    return out


def _arguments(args):
    return ast.arguments(posonlyargs=[], args=args, vararg=None,
                         kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])


def _replace(tree, target, replacement):
    class Replace(ast.NodeTransformer):
        def generic_visit(self, node):
            if node is target:
                return replacement
            return super().generic_visit(node)
    return Replace().visit(tree)


@mutator
def swap_operands(tree, rng):
    cands = [n for n in ast.walk(tree)
             if isinstance(n, ast.BinOp)
             or (isinstance(n, ast.BoolOp) and len(n.values) >= 2)
             or (isinstance(n, ast.Compare) and len(n.ops) == 1)]
    if not cands:
        return False
    n = rng.choice(cands)
    if isinstance(n, ast.BinOp):
        n.left, n.right = n.right, n.left
    elif isinstance(n, ast.BoolOp):
        n.values[0], n.values[1] = n.values[1], n.values[0]
    else:
        n.left, n.comparators[0] = n.comparators[0], n.left
    return True


@mutator
def change_literal(tree, rng):
    cands = [n for n in ast.walk(tree)
             if isinstance(n, ast.Constant)
             and not isinstance(n.value, (type(None), bool))]
    if not cands:
        return False
    n = rng.choice(cands)
    v = n.value
    if isinstance(v, int):
        choice = rng.randrange(3)
        if choice == 0:
            n.value = repr(v)
        elif choice == 1:
            n.value = 9223372036854775808 + rng.randrange(0, 1000)
        else:
            n.value = -(9223372036854775808 + rng.randrange(0, 1000))
    elif isinstance(v, float):
        if rng.random() < 0.5:
            n.value = -0.0
        else:
            return _replace(tree, n, ast.Call(
                func=ast.Name(id='float', ctx=ast.Load()),
                args=[ast.Constant(value='nan')], keywords=[])) is not None
    elif isinstance(v, (str, bytes)):
        if rng.random() < 0.5:
            n.value = 7
        else:
            n.value = (v + b'!') if isinstance(v, bytes) else (v + '!')
    else:
        return False
    return True


@mutator
def wrap_in_try(tree, rng):
    lists = _body_lists(tree)
    if not lists:
        return False
    _, _, body = rng.choice(lists)
    idx = rng.randrange(len(body))
    stmt = body[idx]
    body[idx] = ast.Try(
        body=[stmt],
        handlers=[ast.ExceptHandler(type=ast.Name(id='Exception', ctx=ast.Load()),
                                    name=None, body=[ast.Pass()])],
        orelse=[], finalbody=[])
    return True


@mutator
def add_global(tree, rng):
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.body]
    rng.shuffle(funcs)
    for fn in funcs:
        params = {a.arg for a in fn.args.posonlyargs + fn.args.args
                  + fn.args.kwonlyargs}
        if fn.args.vararg:
            params.add(fn.args.vararg.arg)
        if fn.args.kwarg:
            params.add(fn.args.kwarg.arg)
        declared = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Global):
                declared.update(n.names)
            elif isinstance(n, ast.Nonlocal):
                declared.update(n.names)
        annotated = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.AnnAssign):
                for t in ast.walk(n.target):
                    if isinstance(t, ast.Name):
                        annotated.add(t.id)
        assigned = {n.id for n in ast.walk(fn)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        names = sorted(assigned - params - declared - annotated)
        if names:
            name = rng.choice(names)
            fn.body.insert(0, ast.Global(names=[name]))
            return True
    return False


@mutator
def shadow_builtin(tree, rng):
    defs = {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    params = {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
    stored = {n.id for n in ast.walk(tree)
              if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    candidates = sorted(stored - defs - params)
    if not candidates:
        return False
    old = rng.choice(candidates)
    used = _names(tree)
    free = sorted(BUILTIN_NAMES - used - {'__name__', '__file__'})
    if not free:
        free = ['list', 'len', 'min', 'max', 'sum', 'id']
    new = rng.choice(free)
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id == old:
            n.id = new
    return True


@mutator
def nest_comprehension(tree, rng):
    cands = [n for n in ast.walk(tree)
             if isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp,
                               ast.DictComp))]
    if not cands:
        lists = [(n, f, v) for n, f, v in _body_lists(tree) if f == 'body']
        if not lists:
            return False
        _, _, body = rng.choice(lists)
        v = _fresh(tree, '__ice_v')
        inner = ast.ListComp(
            elt=ast.Name(id=v, ctx=ast.Load()),
            generators=[ast.comprehension(
                target=ast.Name(id=v, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id='range', ctx=ast.Load()),
                              args=[ast.Constant(value=3)], keywords=[]),
                ifs=[], is_async=0)])
        outer = ast.ListComp(
            elt=ast.Name(id=v + '_o', ctx=ast.Load()),
            generators=[ast.comprehension(
                target=ast.Name(id=v + '_o', ctx=ast.Store()),
                iter=inner, ifs=[], is_async=0)])
        body.insert(0, ast.Assign(targets=[ast.Name(id=v, ctx=ast.Store())],
                                  value=outer))
        return True
    old = rng.choice(cands)
    v = _fresh(tree, '__ice_v')
    repl = ast.ListComp(
        elt=ast.Name(id=v, ctx=ast.Load()),
        generators=[ast.comprehension(
            target=ast.Name(id=v, ctx=ast.Store()), iter=old,
            ifs=[], is_async=0)])
    _replace(tree, old, repl)
    return True


@mutator
def insert_del(tree, rng):
    choices = []
    for _, _, body in _body_lists(tree):
        names = set()
        for stmt in body:
            for n in ast.walk(stmt):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    names.add(n.id)
                elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.discard(n.name)
        if names:
            choices.append((body, sorted(names)))
    if not choices:
        return False
    body, names = rng.choice(choices)
    name = rng.choice(names)
    body.append(ast.Delete(targets=[ast.Name(id=name, ctx=ast.Del())]))
    return True


@mutator
def insert_lambda(tree, rng):
    exprs = _expr_nodes(tree)
    if not exprs:
        return False
    old = rng.choice(exprs)
    v = _fresh(tree, '__ice_l')
    lam = ast.Lambda(args=_arguments([ast.arg(arg=v, annotation=None)]),
                     body=ast.Name(id=v, ctx=ast.Load()))
    _replace(tree, old, ast.Call(func=lam, args=[old], keywords=[]))
    return True


@mutator
def insert_star_args(tree, rng):
    fn_name = _fresh(tree, '__ice_star')
    fn = ast.FunctionDef(
        name=fn_name,
        args=ast.arguments(posonlyargs=[], args=[], vararg=ast.arg(arg='args', annotation=None),
                           kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=[ast.Return(value=ast.Call(
            func=ast.Name(id='len', ctx=ast.Load()),
            args=[ast.Name(id='args', ctx=ast.Load())], keywords=[]))],
        decorator_list=[], returns=None, type_comment=None, type_params=[])
    tree.body.append(fn)
    tree.body.append(ast.Expr(value=ast.Call(
        func=ast.Name(id=fn_name, ctx=ast.Load()),
        args=[ast.Constant(value=1), ast.Constant(value=2)], keywords=[])))
    return True


@mutator
def insert_walrus(tree, rng):
    lists = [(n, f, v) for n, f, v in _body_lists(tree) if f == 'body']
    if not lists:
        return False
    _, _, body = rng.choice(lists)
    v = _fresh(tree, '__ice_w')
    body.insert(0, ast.If(
        test=ast.NamedExpr(target=ast.Name(id=v, ctx=ast.Store()),
                           value=ast.Constant(value=1)),
        body=[ast.Pass()], orelse=[]))
    return True


@mutator
def insert_match(tree, rng):
    lists = [(n, f, v) for n, f, v in _body_lists(tree) if f == 'body']
    if not lists:
        return False
    _, _, body = rng.choice(lists)
    match = ast.Match(
        subject=ast.Constant(value=0),
        cases=[
            ast.match_case(pattern=ast.MatchValue(value=ast.Constant(value=0)),
                           guard=None, body=[ast.Pass()]),
            ast.match_case(pattern=ast.MatchAs(pattern=None, name=None),
                           guard=None, body=[ast.Pass()]),
        ])
    body.insert(0, match)
    return True


@mutator
def add_decorator(tree, rng):
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not funcs:
        return False
    fn = rng.choice(funcs)
    deco = _fresh(tree, '__ice_deco')
    d = ast.FunctionDef(
        name=deco,
        args=_arguments([ast.arg(arg='f', annotation=None)]),
        body=[ast.Return(value=ast.Name(id='f', ctx=ast.Load()))],
        decorator_list=[], returns=None, type_comment=None, type_params=[])
    tree.body.insert(0, d)
    fn.decorator_list.append(ast.Name(id=deco, ctx=ast.Load()))
    return True


def _run_cpython(source, timeout=5.0):
    with tempfile.TemporaryDirectory(prefix='icefuzz-mut-') as d:
        p = Path(d) / 'prog.py'
        p.write_text(source, encoding='utf-8')
        try:
            subprocess.run([sys.executable, '-B', str(p)],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=timeout, cwd=d)
            return True
        except (subprocess.TimeoutExpired, OSError, ValueError):
            return False


def generate(seed, detail=False):
    """Return a validated mutant for *seed*, or None.

    With detail=True return (source, [mutation names]) instead of just source.
    Deterministic for a given seed (barring CPython timeouts).
    """
    rng = random.Random(seed)
    for _attempt in range(24):
        path = _pick_file(rng)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        ops = []
        for _ in range(rng.choice([1, 1, 2, 2, 3])):
            name, fn = rng.choice(MUTATORS)
            try:
                ok = fn(tree, rng)
            except (AttributeError, ValueError, TypeError, IndexError, KeyError):
                ok = False
            if ok:
                ops.append(name)
        if not ops:
            continue
        try:
            ast.fix_missing_locations(tree)
            source = ast.unparse(tree)
            ast.parse(source)
            compile(source, '<icefuzz-mutant>', 'exec')
        except (SyntaxError, ValueError, RecursionError):
            continue
        if not _run_cpython(source):
            continue
        return (source, ops, str(path.relative_to(ROOT))) if detail else source
    return (None, [], '') if detail else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int)
    ap.add_argument('-o', '--out')
    ap.add_argument('--show', action='store_true', help='print mutation names on stderr')
    ap.add_argument('--list-corpus', action='store_true')
    args = ap.parse_args()
    if args.list_corpus:
        for p in corpus_files():
            print(p.relative_to(ROOT))
        return 0
    if args.seed is None:
        ap.error('--seed is required')
    src, ops, rel = generate(args.seed, detail=True)
    if src is None:
        print('seed %d: no valid mutant' % args.seed, file=sys.stderr)
        return 1
    if args.show:
        print(' '.join(ops), file=sys.stderr)
    if args.out:
        Path(args.out).write_text(src, encoding='utf-8')
    else:
        sys.stdout.write(src)
    return 0


if __name__ == '__main__':
    sys.exit(main())
