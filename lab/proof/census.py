#!/usr/bin/env python3
"""What do today's analyses already prove about real Python code?  (`docs/design/SAFETY_PROOF.md`)

    python3 lab/proof/census.py [--jobs 2] [--limit N] [-o lab/proof/census.json] [--quiet]

For every typed function of three corpora this asks the compiler's own analyses three questions and
writes one JSON record per function plus a summary:

  ownership  `ir/borrow.py` (rc2): which reference parameters take no entry retain and no exit
             release.  A parameter is a *reference* when its annotation names a class, `dict`, `set`,
             `bytearray` or a list of non-scalars.  A reference parameter that is not borrowed needs
             two runtime RC operations (retain on entry, release on exit); a borrowed one needs none.
             `rc_elided = 2 * borrowed_refs`, `rc_needed = 2 * (refs - borrowed_refs)`.
             Status: `full` (no reference parameter needs an RC pair), `part` (some do), `none`
             (every reference parameter does).

  bounds     `ir/passes/ranges.py` (job `bce`), through the pass statistics `ir/driver.py` records
             per function in `AIL_IR_STATS`: `idx_total` index sites, of which
             `idx_legacy_proven + idx_ssa_proven` had their bound check removed.  A function the IR
             does not lower has no such record; its index sites are counted from the AST and marked
             `kept` because no API reports them (that is blocker `no-index-api`).

  races      the compile-time half of typed parallel: `typedpar.rewrite_text` and
             `parallel._Body`.  Every access to shared state inside a parallel region is classified
             `safe`, `refused` (with rule D1-D5) or `unknown`.  See `RULES` below for what each rule
             is and where it lives in the source.

Nothing here edits the compiler: the analyses are imported and called.  Where an analysis has no API
to ask, the question is recorded as a blocker instead of being patched (`NO_API` below).
"""
import argparse
import ast
import collections
import json
import multiprocessing
import os
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AIL = ROOT / 'AIL_CURRENT'
PKG = AIL / 'python' / 'pkg-v12'

#: The race rules, as the census names them.  Each is a distinct decision the existing source
#: already makes; the census only counts accesses on each side of it.
RULES = collections.OrderedDict([
    ('D1', 'a parallel body writes a name it does not assign itself (a shared scalar or global) '
           '-- parallel.py `_Body` store rule; refused, so the program runs under the lock'),
    ('D2', 'a parallel body calls a function that is not a top-level int/float-only pure function '
           '-- parallel.py `check_callee`; refused'),
    ('D3', 'a parallel body appends to, pops or resizes a shared list (no distinct-shape element '
           'write) -- parallel.py `_Body` / `check_owned`; refused'),
    ('D4', 'a parallel body handles a str, bytes or object value, or reads an attribute of one '
           '-- parallel.py `_Body._expr`; refused'),
    ('D5', 'the fork-join shape is not one typedpar lowers at all (a future read outside its block, '
           'an executor used as a value, `Thread` not started and joined in one block, a `Queue`) '
           '-- typedpar.py `rewrite_text`; the whole region runs under the general path lock'),
])

#: Questions the existing source cannot be asked.  Each is reported as a blocker with its count.
NO_API = collections.OrderedDict([
    ('no-index-api', 'the range pass reports index sites per IR function only; a function the IR '
                     'does not lower gets no per-site record, so its bounds checks cannot be split '
                     'into removed/kept (they are counted as kept here)'),
    ('no-rc-api', 'the emitter exposes no per-function count of the RC operations it emits '
                  '(`ail_obj_store`, `ail_obj_release`, ...); ownership is therefore measured at the '
                  'parameter-reference level, not per emitted call site'),
    ('no-kind-api', '`pyfunc._param_kinds` needs a compiler context, so a parameter with no '
                    'annotation is counted as a value even when the emitter derived a reference kind '
                    'for it from the body'),
])

SCALARS = {'int', 'float', 'bool', 'str', 'bytes', 'None', 'object'}
REF_CONTAINERS = {'dict', 'set', 'frozenset', 'bytearray', 'list', 'deque', 'OrderedDict', 'defaultdict'}
VALUE_CONTAINERS = {'tuple', 'range', 'memoryview'}


def _setup():
    sys.path[:0] = [str(PKG), str(AIL)]
    os.environ.setdefault('AIL_SURFACE', 'python')
    # the census is compile-only: the C compiler is replaced by a no-op so a build is the Python
    # front end, the IR and the emitter and nothing else (the .c is written before it is called)
    os.environ.setdefault('PIPE_CC', '/bin/true')
    # one compiler process per build: the front end's own multiprocessing pool cannot start inside
    # a daemonic census worker, and a fixed job count keeps the measurement reproducible
    os.environ['AIL_FE_JOBS'] = '1'
    os.environ.pop('AIL_NO_GENERAL', None)
    os.environ.pop('AIL_UNIFIED_FORCE', None)
    os.environ.pop('AIL_UNIFIED', None)
    import fastwalk
    fastwalk.install()


# ---------------------------------------------------------------- corpora

def corpora(limit=None):
    """{corpus name: [program path, ...]} for the three code corpora, in a fixed order."""
    def rel(p):
        return str(p.relative_to(ROOT))

    compare = sorted(ROOT.glob('lab/compare/src/*/typed.py')) + \
        sorted(ROOT.glob('lab/compare/src/*/main.py'))
    pyproof = []
    for row in (ROOT / 'lab/pyproof/programs.txt').read_text().splitlines():
        if row.strip():
            pyproof.append(row.split('\t')[0].strip())
    gdev = sorted(ROOT.glob('corpus/gdev/*.py'))[:200]
    out = {
        'compare': [rel(p) for p in compare],
        'pyproof': pyproof,
        'gdev': [rel(p) for p in gdev],
    }
    if limit:
        out = {k: v[:limit] for k, v in out.items()}
    return out


def race_programs():
    """The parallel probes that ship with the repository (lab/race), plus any program of the three
    corpora that names a threaded module (found per program by `race_info`)."""
    return sorted(ROOT.glob('lab/race/safe/*.py')) + sorted(ROOT.glob('lab/race/racy/*.py'))


# ---------------------------------------------------------------- annotations

def _ann_kind(node, classes):
    """`ref`, `value` or `unknown` for one annotation expression."""
    if node is None:
        return 'unknown'
    if isinstance(node, ast.Constant):
        return 'value'
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        kinds = {_ann_kind(node.left, classes), _ann_kind(node.right, classes)}
        return 'ref' if 'ref' in kinds else ('value' if kinds == {'value'} else 'unknown')
    if isinstance(node, ast.Name):
        name = node.id
        if name in SCALARS:
            return 'value'
        if name in classes:
            return 'ref'
        if name in REF_CONTAINERS:
            return 'ref'
        if name in VALUE_CONTAINERS:
            return 'value'
        if name in ('Optional', 'Union', 'Any', 'Iterable', 'Iterator', 'Sequence', 'Mapping'):
            return 'unknown'
        return 'ref'            # an imported class or an alias: treat as a reference
    if isinstance(node, ast.Attribute):
        base = ast.unparse(node)
        name = base.split('.')[-1]
        if name in SCALARS:
            return 'value'
        if name in VALUE_CONTAINERS:
            return 'value'
        return 'ref' if name in REF_CONTAINERS or name[:1].isupper() else 'unknown'
    if isinstance(node, ast.Subscript):
        if _ann_kind(node.value, classes) == 'value':
            return 'value'
        name = node.value.id if isinstance(node.value, ast.Name) else ast.unparse(node.value).split('.')[-1]
        if name in ('list', 'List'):
            inner = node.slice
            if isinstance(inner, ast.Tuple) and inner.elts:
                inner = inner.elts[0]
            # a list of scalars is owned by value (int64/double cells, no reference); a list of
            # strings is the packed string list, which owns no reference either as far as the
            # borrow rule is concerned -- both are `value` here
            element = _ann_kind(inner, classes)
            return 'value' if element == 'value' else 'ref'
        if name in ('dict', 'Dict', 'set', 'Set', 'frozenset', 'FrozenSet', 'deque'):
            return 'ref'
        if name in ('tuple', 'Tuple'):
            return 'value'
        if name in ('Optional', 'Union'):
            return 'unknown'
        return 'unknown'
    if isinstance(node, ast.Constant) and node.value is None:
        return 'value'
    return 'unknown'


def _param_spec(fn):
    a = fn.args
    spec = []
    for p in list(a.posonlyargs) + list(a.args):
        spec.append((p.arg, p.annotation))
    if a.vararg is not None:
        spec.append((a.vararg.arg, a.vararg.annotation))
    for p in a.kwonlyargs:
        spec.append((p.arg, p.annotation))
    if a.kwarg is not None:
        spec.append((a.kwarg.arg, a.kwarg.annotation))
    return spec


def _functions(tree):
    """Every function of the module, methods included, in source order, with its parent class."""
    out = []

    def walk(body, owner):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append((node, owner))
            elif isinstance(node, ast.ClassDef):
                walk(node.body, node.name)
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                for field in ('body', 'orelse', 'finalbody'):
                    walk(getattr(node, field, []) or [], owner)
                for handler in getattr(node, 'handlers', []) or []:
                    walk(handler.body, owner)
    walk(tree.body, None)
    return out


# ---------------------------------------------------------------- blockers

def _mentions(node, names):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in names:
            return True
    return False


def _store_targets(node):
    """The expressions a parameter reference can be stored into by `node`."""
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return targets
    return []


def _param_blocker(fn, param, tree_fns, owned):
    """Why `ir/borrow.py` refuses to borrow `param` of `fn`, one label.

    The *decision* is the analysis' (`ir/borrow.py`); this only names the rule that produced it, by
    the same predicates the module's own docstring states, in the same order."""
    names = {param}
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == param:
            return 'parameter rebound inside the function'
        if isinstance(node, (ast.Global, ast.Nonlocal)) and param in node.names:
            return 'parameter is a global or nonlocal'
        if isinstance(node, ast.ExceptHandler) and node.name == param:
            return 'parameter bound by an except handler'
    for node in ast.walk(fn):
        if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)) and node.value is not None \
                and _mentions(node.value, names):
            return 'parameter returned (or yielded) to the caller'
        if isinstance(node, ast.Raise) and node.exc is not None and _mentions(node.exc, names):
            return 'parameter raised as an exception'
    for node in ast.walk(fn):
        for target in _store_targets(node):
            value = getattr(node, 'value', None)
            if value is not None and _mentions(value, names) \
                    and isinstance(target, (ast.Attribute, ast.Subscript)):
                return 'parameter stored into a field, list or dict'
    for node in ast.walk(fn):
        if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.ListComp, ast.SetComp,
                             ast.GeneratorExp, ast.DictComp)) and _mentions(node, names):
            return 'parameter stored into a container literal'
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id != param and node.value is not None \
                        and _mentions(node.value, names):
                    return 'parameter aliased into a second local name'
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and any(_mentions(a, names) for a in node.args) or \
                isinstance(node, ast.Call) and any(_mentions(k.value, names) for k in node.keywords):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ('print', 'len', 'int', 'float', 'str', 'bool'):
                continue
            if isinstance(func, ast.Attribute):
                return 'parameter passed to a method call or passed as a receiver'
            return 'parameter passed to a call that stores or forwards it'
    for node in ast.walk(fn):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and node is not fn \
                and _mentions(node, names):
            return 'parameter captured by a closure'
    if fn.name in owned:
        return 'function is an entry point or used as a value (its parameters are owned)'
    return None


# ---------------------------------------------------------------- measurement

def _load(path):
    """The source as the real build presents it: `ail_chatgpt.py compile --syntax python` runs the
    Python surface pass (`_load_sources`), and the census must measure the same program it builds.
    A program the surface pass cannot read at all is measured from its text, and the build decides."""
    import contextlib
    import io
    import ail_chatgpt
    from pyfront import Unsupported
    import shadowing
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            text, _, _ = ail_chatgpt._load_sources(ROOT / path, (), 'python', local_imports=True)
        return shadowing.rename_all(text, Unsupported)[0]
    except Exception:
        return (ROOT / path).read_text(encoding='utf-8')


def _ir_stats(stats_path):
    """The last record per source function: a program may be built several times (typed, then the
    exact general path, then a legacy retry) and only the final attempt describes the artifact."""
    out = {}
    if not os.path.exists(stats_path):
        return out
    with open(stats_path) as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            out[entry.get('fn')] = entry
    return out


def _bce_reasons(path):
    """`AIL_BCE_EXPLAIN`: why each index site the range pass left checked is still checked.
    Deduplicated by (function, op, index) so the retries of one program count once."""
    out = collections.defaultdict(collections.Counter)
    seen = set()
    if not os.path.exists(path):
        return {}
    with open(path) as handle:
        for line in handle:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            key = (rec.get('fn'), rec.get('op'), (rec.get('index') or {}).get('name'))
            if key in seen:
                continue
            seen.add(key)
            out[rec.get('fn') or '?'][rec.get('reason') or 'no reason recorded'] += 1
    return {fn: dict(counts) for fn, counts in out.items()}


def _index_sites(fn):
    """`(reads, writes)` subscript sites of a function's own AST (nested defs excluded)."""
    reads = writes = 0
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Subscript):
            if isinstance(node.ctx, ast.Store):
                writes += 1
            elif isinstance(node.ctx, ast.Load):
                reads += 1
        stack.extend(ast.iter_child_nodes(node))
    return reads, writes


def measure(path, corpus):
    """One program: its build outcome and one record per typed function."""
    import pyc
    from ir import borrow
    rec = {'path': path, 'corpus': corpus, 'ok': True, 'error': None,
           'built': False, 'boxed': [], 'functions': [], 'race': None}
    raw = (ROOT / path).read_text(encoding='utf-8')
    text = _load(path)
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        rec.update(ok=False, error='SyntaxError: %s' % error)
        return rec
    classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    try:
        borrowed = borrow.analyze(tree)
    except Exception as error:                      # no API answer: record, never patch
        borrowed = {}
        rec['borrow_error'] = '%s: %s' % (type(error).__name__, error)
    tmp = tempfile.mkdtemp(prefix='ail-proof-')
    stats_path = os.path.join(tmp, 'ir-stats.jsonl')
    os.environ['AIL_IR_STATS'] = stats_path
    explain_path = os.path.join(tmp, 'bce-explain.jsonl')
    os.environ['AIL_BCE_EXPLAIN'] = explain_path
    report = {}
    error = None
    try:
        pyc.build(text, os.path.join(tmp, 'prog'), strict=True, report=report)
        rec['built'] = True
        rec['fallback'] = pyc.last_fallback_reason
        rec['fallback_line'] = pyc.last_fallback_line
    except Exception as exc:
        error = '%s: %s' % (type(exc).__name__, str(exc).splitlines()[0])
        rec.update(ok=False, error=error)
        rec['fallback'] = pyc.last_fallback_reason or error
        rec['fallback_line'] = pyc.last_fallback_line
    stats = _ir_stats(stats_path)
    rec['bce_reasons'] = _bce_reasons(explain_path)
    boxed = sorted(set(report.get('boxed') or ()))
    rec['boxed'] = boxed
    owned_names = {'main'} | _used_as_value(tree)
    fn_nodes = _functions(tree)
    by_name = {}
    for fn, _ in fn_nodes:
        by_name.setdefault(fn.name, fn)
    for fn, owner in fn_nodes:
        spec = _param_spec(fn)
        annotated = fn.returns is not None or any(a is not None for _, a in spec)
        refs = []
        values = []
        unknown = []
        for name, ann in spec:
            kind = 'ref' if (name == 'self' and owner) else _ann_kind(ann, classes)
            if kind == 'ref':
                refs.append(name)
            elif kind == 'value':
                values.append(name)
            else:
                unknown.append(name)
        got = borrowed.get(fn.name, frozenset())
        # same-named methods and helpers are merged by intersection by the analysis; attribute the
        # per-function answer from the passed set only when the name is unique
        unique = sum(1 for f, _ in fn_nodes if f.name == fn.name) == 1
        got = set(got) if unique else set(got) & set(n for n, _ in spec)
        borrowed_refs = [n for n in refs if n in got]
        needed_refs = [n for n in refs if n not in got]
        entry = stats.get(fn.name) or {}
        passes = entry.get('passes') or {}
        if refs:
            if not needed_refs:
                status = 'full'
            elif borrowed_refs:
                status = 'part'
            else:
                status = 'none'
        else:
            status = 'n/a'
        reads, writes = _index_sites(fn)
        function = {
            'program': path, 'corpus': corpus, 'name': fn.name, 'line': fn.lineno,
            'owner': owner, 'annotated': annotated, 'boxed': fn.name in boxed,
            'params': len(spec), 'ref_params': refs, 'value_params': values,
            'unknown_params': unknown, 'borrowed': sorted(got),
            'rc_elided': 2 * len(borrowed_refs), 'rc_needed': 2 * len(needed_refs),
            'ownership': status,
            'ir_path': entry.get('path'), 'ir_reason': entry.get('reason') or None,
            'idx_total': passes.get('idx_total'),
            'idx_removed': (None if 'idx_total' not in passes
                            else passes.get('idx_legacy_proven', 0) + passes.get('idx_ssa_proven', 0)),
            'index_sites': reads + writes,
            'blockers': [],
        }
        if function['idx_total'] is not None:
            function['idx_kept'] = function['idx_total'] - function['idx_removed']
        else:
            function['idx_kept'] = reads + writes        # no API: count every site as kept
        for param in needed_refs:
            label = _param_blocker(fn, param, by_name, owned_names)
            if label:
                function['blockers'].append({'kind': 'ownership', 'reason': label,
                                             'detail': '%s: %s' % (fn.name, param)})
        for reason, count in (rec.get('bce_reasons', {}).get(fn.name) or {}).items():
            function['blockers'].append({'kind': 'bounds', 'reason': 'index bound not proved: ' + reason,
                                         'detail': '%s: %d site(s)' % (fn.name, count)})
            function['bounds_blocked'] = function.get('bounds_blocked', 0) + count
        if not rec['built']:
            function['blockers'].append({'kind': 'program', 'reason': 'program refused by both paths',
                                         'detail': error})
        elif function['ir_path'] == 'legacy':
            function['blockers'].append({'kind': 'lowering', 'reason': 'function stays on the legacy emitter',
                                         'detail': entry.get('reason') or 'no IR record'})
        elif function['idx_total'] is None and reads + writes:
            function['blockers'].append({'kind': 'no-api', 'reason': 'no-index-api',
                                         'detail': '%s: %d index site(s)' % (fn.name, reads + writes)})
        if function['ownership'] in ('part', 'none'):
            pass
        rec['functions'].append(function)
    try:
        rec['race'] = race_info(raw, tree)
    except Exception as error:
        rec['race'] = {'error': '%s: %s' % (type(error).__name__, error)}
    return rec


def _used_as_value(tree):
    """Function names that occur anywhere except as the direct callee of a call (borrow.py's rule)."""
    names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    called = {id(n.func) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in names and id(n) not in called:
            out.add(n.id)
    return out


# ---------------------------------------------------------------- races

def _shared_accesses(body, loop_var, assigned):
    """Every access to state outside the body's own locals, with the race rule it hits (or None)."""
    out = []

    def local(name):
        return name in assigned or name == loop_var

    def visit(nodes):
        for node in nodes:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    if isinstance(sub.ctx, ast.Load) and not local(sub.id):
                        out.append(('read', None, sub))
                    elif isinstance(sub.ctx, (ast.Store, ast.Del)) and not local(sub.id):
                        out.append(('write', 'D1', sub))
                elif isinstance(sub, ast.Subscript):
                    indexes = sub.slice.elts if isinstance(sub.slice, ast.Tuple) else [sub.slice]
                    distinct = any(_mentions(i, {loop_var}) for i in indexes)
                    if isinstance(sub.ctx, ast.Store):
                        out.append(('write', None if distinct else 'D1', sub))
                    else:
                        out.append(('read', None, sub))
                elif isinstance(sub, ast.Attribute):
                    out.append(('attr', 'D4', sub))
                elif isinstance(sub, ast.Call):
                    f = sub.func
                    if isinstance(f, ast.Attribute):
                        if f.attr in ('append', 'pop', 'insert', 'extend', 'clear', 'sort', 'reverse', 'remove'):
                            out.append(('call', 'D3', sub))
                        else:
                            out.append(('call', 'D4', sub))
                    elif isinstance(f, ast.Name) and f.id in ('print', 'open', 'input'):
                        out.append(('call', 'D2', sub))
                elif isinstance(sub, ast.Constant) and isinstance(sub.value, (str, bytes)):
                    out.append(('str', 'D4', sub))
    visit(body)
    return out


class _U(Exception):
    source_line = None


MARKERS = ('map', 'submit', 'Thread')


def _region_targets(tree):
    """The functions a program hands to a thread, an executor or a pool: the parallel regions."""
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in ('map', 'submit') and node.args \
                and isinstance(node.args[0], ast.Name):
            names.add(node.args[0].id)
        elif (isinstance(f, ast.Name) and f.id == 'Thread') or \
                (isinstance(f, ast.Attribute) and f.attr == 'Thread'):
            # `from threading import Thread` is a bare name; `threading.Thread(...)` and
            # `t.Thread(...)` are attributes -- both are the same constructor
            for kw in node.keywords:
                if kw.arg == 'target' and isinstance(kw.value, ast.Name):
                    names.add(kw.value.id)
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]


def race_info(text, tree):
    """Classify the parallel regions of one program: what the race rules already accept."""
    import typedpar
    import parallel
    del tree
    words = any(w in text for w in typedpar.WORDS) or 'par_range' in text
    if not words:
        return None
    notes, done = [], []
    try:
        rewritten = typedpar.rewrite_text(text, notes, done)
    except Exception as error:
        return {'error': '%s: %s' % (type(error).__name__, error)}
    info = {'constructs': len(done), 'refused_constructs': [], 'regions': [],
            'safe': 0, 'refused': 0, 'unknown': 0, 'by_rule': collections.Counter(),
            'lowered_regions': 0, 'refused_regions': 0, 'refused_shapes': len(notes)}
    for line, why in notes:
        # D5 is a refused *shape*, not an access: it is counted in `refused_shapes`, never added
        # to `by_rule`, which counts accesses.
        info['refused_constructs'].append({'line': line, 'note': why})
    if notes:
        # the shape was not lowered, so the region runs under the general path's lock: every access
        # in it is refused *by the proof*, even though the program stays safe under the lock
        for fn in _region_targets(ast.parse(text)):
            assigned = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)
                        and isinstance(n.ctx, ast.Store)}
            accesses = _shared_accesses(fn.body, '', assigned)
            info['refused_regions'] += 1
            info['refused'] += len(accesses)
            info['regions'].append({'kind': 'refused_region', 'line': fn.lineno,
                                    'verdict': 'refused', 'reason': notes[0][1],
                                    'accesses': len(accesses),
                                    'rules': dict(collections.Counter(r for _, r, _ in accesses if r))})
            for _, rule, _sub in accesses:
                if rule is None:
                    info['unknown'] += 1
                else:
                    info['by_rule'][rule] += 1
    try:
        new_tree = ast.parse(rewritten)
    except SyntaxError:
        return info
    funcs = {n.name: n for n in ast.walk(new_tree) if isinstance(n, ast.FunctionDef)}
    for node in ast.walk(new_tree):
        if not isinstance(node, ast.For) or not parallel.is_par(node):
            continue
        target = node.target
        loop_var = target.id if isinstance(target, ast.Name) else ''
        assigned = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)
                    and isinstance(n.ctx, ast.Store)} | {loop_var}
        try:
            trial = __import__('copy').deepcopy(node)
            check = parallel._Body(trial, funcs, _U)
            check.block(trial.body, {check.var})
            check.check_owned()
            verdict, why = 'safe', None
        except Exception as error:
            verdict, why = 'refused', str(error)
        accesses = _shared_accesses(node.body, loop_var, assigned)
        region = {'kind': 'par_range', 'line': getattr(node, 'lineno', None), 'verdict': verdict,
                  'reason': why, 'accesses': len(accesses),
                  'rules': dict(collections.Counter(r for _, r, _ in accesses if r))}
        info['regions'].append(region)
        if verdict == 'safe':
            info['lowered_regions'] += 1
            info['safe'] += len(accesses)
        else:
            info['refused_regions'] += 1
            info['refused'] += len(accesses)
            for _, rule, sub in accesses:
                if rule is None:
                    info['unknown'] += 1
                else:
                    info['by_rule'][rule] += 1
    info['distinct_accesses'] = info['safe'] + info['refused']
    info['by_rule'] = dict(info['by_rule'])
    return info


# ---------------------------------------------------------------- ranking

def rank(functions):
    """Top reasons a function is not fully proved, one count per function per distinct reason.

    A function can carry several blockers, so these counts overlap and their sum exceeds the number
    of functions with a blocker.  Boxed functions are counted as one row of their own (the general
    path gives no proof at all); their other blockers are not part of the typed-path ranking.
    `example` is the first function, in census order, that carries the reason."""
    counts = collections.Counter()
    examples = {}
    order = []
    boxed = 0
    boxed_example = None

    def note(label, example):
        counts[label] += 1
        if label not in examples:
            examples[label] = example
        if label not in order:
            order.append(label)

    for fn in functions:
        where = '%s:%d %s' % (fn['program'], fn['line'], fn['name'])
        if fn['boxed']:
            boxed += 1
            if boxed_example is None:
                boxed_example = where
            continue
        seen = set()
        for blocker in fn['blockers']:
            label = blocker['reason']
            if label in seen:
                continue
            seen.add(label)
            note(label, '%s -- %s' % (where, blocker['detail']))
    ranked = sorted(order, key=lambda label: -counts[label])
    rows = [{'reason': label, 'count': counts[label], 'example': examples[label]}
            for label in ranked]
    if boxed:
        rows.insert(0, {'reason': 'function compiled on the general (boxed) path: no proof applies',
                        'count': boxed, 'example': boxed_example})
    return rows


#: How a program's recorded typed-path refusal is named in RESULTS' "why boxed" table.  One
#: category per function, first match wins; a function whose program matches none is `other`.
BOXED_GROUPS = collections.OrderedDict([
    ('a `Decimal` format spec in an f-string', lambda s: 'Decimal' in s and 'format spec' in s),
    ('a `bool` parameter given a non-bool', lambda s: 'declared bool' in s),
    ('a dunder other than `__init__`', lambda s: 'dunder method' in s),
    ('a list of `str` given a non-str value', lambda s: 'a list of str' in s),
    ('a generator expression saved as a value', lambda s: 'generator expression' in s),
    ('`d.get(k)` with one argument where an Optional is needed',
     lambda s: 'with one argument' in s and 'get(' in s),
    ('a `str` parameter a caller also supplies an int to',
     lambda s: 'annotated str in the source' in s),
    ('a scalar `None`/Optional value', lambda s: 'only a struct type can be None' in s),
    ('a `statistics` function not built', lambda s: 'statistics.' in s),
    ('`collections` use not built', lambda s: "import of 'collections'" in s),
    ('a set/dict element needing `__eq__`/`__hash__`',
     lambda s: 'as the argument of .add()' in s),
    ('an annotation this compiler has no rule for',
     lambda s: 'which this compiler has no rule for' in s),
    ('a struct-list comprehension not built', lambda s: 'struct-list comprehension' in s),
    ('a module-level constant that is not numeric', lambda s: 'module-level' in s),
    ('the iterator protocol not built', lambda s: 'iterator protocol' in s),
    ('a list parameter that is read-only', lambda s: 'is a list parameter, which is read-only' in s),
    ('`yield`/generators not built', lambda s: 'has no generators' in s),
    ('`threading`/`queue`/`concurrent.futures` (general path by design)',
     lambda s: any(word in s for word in ('threading', 'concurrent.futures', 'queue'))),
])


def boxed_reasons(records):
    """Boxed functions grouped by the typed-path refusal their program recorded.

    The compiler records one `last_fallback_reason` per program (`pyc`), not per function, so every
    boxed function of a program carries that program's reason.  `other` keeps the remainder
    visible; it is not silently dropped."""
    counts = collections.Counter()
    for rec in records:
        if rec['corpus'] == 'race':
            continue
        boxed = [f for f in rec['functions'] if f['boxed']]
        if not boxed:
            continue
        reason = rec.get('fallback') or ''
        label = 'other (a reason not in the named groups)'
        for name, match in BOXED_GROUPS.items():
            if match(reason):
                label = name
                break
        counts[label] += len(boxed)
    return [{'reason': label, 'count': n} for label, n in counts.most_common()]


def _worker(job):
    path, corpus = job
    try:
        return measure(path, corpus)
    except Exception:
        return {'path': path, 'corpus': corpus, 'ok': False,
                'error': 'census crash: %s' % traceback.format_exc().splitlines()[-1],
                'functions': [], 'race': None, 'built': False, 'boxed': []}


# ---------------------------------------------------------------- report

def summarize(records):
    """The numbers RESULTS.md quotes, computed from the per-function records."""
    facts = collections.OrderedDict()
    by_corpus = collections.OrderedDict()
    for rec in records:
        by_corpus.setdefault(rec['corpus'], []).append(rec)
    for corpus, recs in by_corpus.items():
        typed_fns = [f for rec in recs for f in rec['functions'] if not f['boxed']]
        boxed = [f for rec in recs for f in rec['functions'] if f['boxed']]
        on_typed_path = [f for rec in recs if rec['built']
                         for f in rec['functions'] if not f['boxed']]
        in_refused = [f for rec in recs if not rec['built'] for f in rec['functions']]
        with_refs = [f for f in typed_fns if f['ref_params']]
        elided = sum(f['rc_elided'] for f in with_refs)
        needed = sum(f['rc_needed'] for f in with_refs)
        idx_total = sum(f['idx_total'] or 0 for f in typed_fns)
        idx_removed = sum(f['idx_removed'] or 0 for f in typed_fns)
        # index sites of functions the IR does not lower, counted from the AST (kept)
        legacy_sites = sum(f['index_sites'] for f in typed_fns if f['idx_total'] is None)
        b = collections.Counter(f['ownership'] for f in with_refs)
        facts[corpus] = {
            'programs': len(recs), 'programs_built': sum(1 for r in recs if r['built']),
            'programs_refused': sum(1 for r in recs if not r['built']),
            # `functions` is every function record; the three shares below partition it:
            #   typed_path + boxed + refused_program == functions
            'functions': len(typed_fns) + len(boxed),
            'typed_path_functions': len(on_typed_path),
            'boxed_functions': len(boxed),
            'refused_program_functions': len(in_refused),
            'not_boxed_functions': len(typed_fns),
            'functions_with_ref_params': len(with_refs),
            'rc_ops_elided': elided, 'rc_ops_needed': needed,
            'rc_share_elided': round(elided / (elided + needed), 4) if elided + needed else None,
            'ownership_full': b['full'], 'ownership_part': b['part'], 'ownership_none': b['none'],
            'ownership_na': sum(1 for f in typed_fns if not f['ref_params']),
            'index_sites_ir': idx_total, 'index_sites_removed': idx_removed,
            'index_share_removed': round(idx_removed / idx_total, 4) if idx_total else None,
            'index_sites_legacy_unmeasured': legacy_sites,
            'bounds_reasons': dict(collections.Counter(
                reason for rec in recs
                for counts in (rec.get('bce_reasons') or {}).values()
                for reason, n in counts.items() for _ in range(n)).most_common()),
        }
    return facts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--limit', type=int, help='at most N programs per corpus (a quick run)')
    ap.add_argument('-o', '--out', default=str(HERE / 'census.json'))
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args(argv)
    _setup()
    corpus_map = corpora(args.limit)
    jobs = [(path, corpus) for corpus, paths in corpus_map.items() for path in paths]
    races = [str(p.relative_to(ROOT)) for p in race_programs()]
    jobs += [(path, 'race') for path in races]
    if args.jobs > 1:
        with multiprocessing.Pool(args.jobs) as pool:
            records = pool.map(_worker, jobs, chunksize=1)
    else:
        records = [_worker(job) for job in jobs]
    facts = summarize([r for r in records if r['corpus'] != 'race'])
    race_records = [r for r in records if r['corpus'] == 'race']
    race_totals = collections.Counter()
    race_rules = collections.Counter()
    n_race_programs = 0
    for rec in records:
        info = rec.get('race')
        if not info or info.get('error'):
            continue
        n_race_programs += 1
        for key in ('safe', 'refused', 'unknown', 'constructs', 'refused_shapes',
                    'lowered_regions', 'refused_regions', 'distinct_accesses'):
            race_totals[key] += info.get(key, 0)
        for rule, n in (info.get('by_rule') or {}).items():
            race_rules[rule] += n
    functions = [f for rec in records if rec['corpus'] != 'race' for f in rec['functions']]
    data = {
        'generated_by': 'lab/proof/census.py',
        'rules': dict(RULES),
        'no_api': dict(NO_API),
        'corpora': corpus_map,
        'summary': facts,
        'blockers': rank(functions)[:15],
        'boxed_reasons': boxed_reasons(records),
        'races': {'programs_with_a_parallel_construct': n_race_programs,
                  'race_probe_programs': len(race_records),
                  'safe': race_totals['safe'], 'refused': race_totals['refused'],
                  'unknown': race_totals['unknown'],
                  'distinct_accesses': race_totals['distinct_accesses'],
                  'named_rule_refused': race_totals['refused'] - race_totals['unknown'],
                  'constructs_lowered': race_totals['constructs'],
                  'lowered_regions': race_totals['lowered_regions'],
                  'refused_regions': race_totals['refused_regions'],
                  'refused_shapes': race_totals['refused_shapes'],
                  'by_rule': dict(race_rules),
                  'programs': [{'path': r['path'], 'race': r.get('race')} for r in records
                               if r.get('race')]},
        'programs': [{'path': r['path'], 'corpus': r['corpus'], 'ok': r['ok'],
                      'error': r.get('error'), 'built': r.get('built'),
                      'boxed': r.get('boxed'), 'fallback': r.get('fallback'),
                      'fallback_line': r.get('fallback_line')} for r in records],
        'functions': functions,
    }
    Path(args.out).write_text(json.dumps(data, indent=1) + '\n')
    if args.quiet:
        return 0
    n_typed_path = sum(row['typed_path_functions'] for row in facts.values())
    print('%d programs, %d functions (%d on the typed path, %d boxed)'
          % (len(records), len(functions), n_typed_path,
             sum(1 for f in functions if f['boxed'])))
    for corpus, row in facts.items():
        print('\n[%s]' % corpus)
        for key, value in row.items():
            print('  %-32s %s' % (key, value))
    print('\n[races]')
    print('  programs with a parallel construct   %d' % n_race_programs)
    for key in ('safe', 'refused', 'unknown', 'distinct_accesses',
                'constructs', 'lowered_regions', 'refused_regions', 'refused_shapes'):
        print('  %-32s %d' % (key, race_totals[key]))
    print('  %-32s %d' % ('named_rule_refused',
                          race_totals['refused'] - race_totals['unknown']))
    print('  by rule                              %s' % dict(race_rules))
    print('\n[top blockers]')
    for row in data['blockers']:
        print('  %4d  %s\n        e.g. %s' % (row['count'], row['reason'], row['example']))
    print('\n[boxed reasons]')
    for row in data['boxed_reasons']:
        print('  %4d  %s' % (row['count'], row['reason']))
    print('\nwrote %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
