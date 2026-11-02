# -*- coding: utf-8 -*-
"""CPython hybrid builds (`ail build --cpython prog.py -o DIR`).

The prototype compiles the functions that the typed emitter can compile as a real CPython
extension module, and leaves the original Python module in place for everything else.  The
extension is loaded only by the generated copy of the program: a native call that cannot take its
arguments (an int outside int64, a bool where an int was hypothesised, a dict/tuple/None, ...) or
that reports an int64 overflow raises a private `Fallback` exception, and the Python wrapper calls
the original function.  This is deliberately behind an explicit flag; the default build is never
touched.

The unit of acceleration is a top-level function that `pymix.analyze` selects and `pyboxed2`'s
existing mixed-mode machinery accepts (the same candidates a standalone mixed-mode build wires).
Only the C ABI of that machinery is reused; no general-path executable is produced.

Design and the wider semantics are in docs/design/CPYTHON_HYBRID.md (AIL_CURRENT/docs/design).
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PKG = _HERE / 'python' / 'pkg-v12'
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

_SCALAR = ('int', 'float', 'bool', 'str')
_LIST = ('list[int]', 'list[float]')
_LIST_RET = ('list[int]', 'list[float]')
# Calls whose typed form is pure and cannot mutate anything the caller can observe, so a later
# overflow fallback cannot repeat a side effect.  Only `range` and `int` are needed by the reached
# hot functions.  `int` is safe because pymix tracks its ValueError and the int64/overflow patch
# turns `int(inf)` into the boxed fallback; conversions like `float(s)`/`ord(s)` raise types pymix
# does not track, so a boxed caller's `try` would be bypassed and they stay refused.  Constructing
# an exception object is pure; the tracked `raise` form is allowed by pymix's exception rule.
# A name bound by the module or by the function shadows the builtin and is not in this set.
_PURE_CALLS = frozenset({
    'range', 'int',
    'BaseException', 'Exception', 'ArithmeticError', 'AssertionError', 'AttributeError',
    'EOFError', 'IndexError', 'KeyError', 'LookupError', 'MemoryError', 'NameError',
    'NotImplementedError', 'OSError', 'OverflowError', 'RuntimeError', 'StopIteration',
    'TypeError', 'ValueError', 'ZeroDivisionError',
})
_MUTATORS = frozenset({
    'append', 'extend', 'insert', 'pop', 'remove', 'clear', 'sort', 'reverse',
    'update', 'add', 'discard', '__setitem__', '__delitem__', 'setdefault',
})
_EXT_SUFFIX = sysconfig.get_config_var('EXT_SUFFIX') or '.so'


def _module_name(stem):
    clean = re.sub(r'[^A-Za-z0-9_]', '_', stem)
    if not clean or clean[0].isdigit():
        clean = '_' + clean
    return '_ail_%s_fast' % clean


def _top_level_functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _own_nodes(fn):
    """Walk one function's body without entering a nested def (that def is its own candidate)."""
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def _local_names(fn):
    """Names the function itself binds: parameters plus every `Name` store in its own body.
    A subscript store is safe when its base is one of these (a local list, not module state)."""
    names = {a.arg for a in fn.args.args}
    names.update(a.arg for a in fn.args.posonlyargs)
    names.update(a.arg for a in fn.args.kwonlyargs)
    if fn.args.vararg:
        names.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        names.add(fn.args.kwarg.arg)
    for node in _own_nodes(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
    return names


def _module_bound_names(tree):
    """Top-level names a call could resolve to instead of the builtin (a module function, class,
    import or assignment shadows the same spelling)."""
    names = set()
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(stmt.name)
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for node in ast.walk(stmt):
                if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                    names.add(node.id)
        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            for alias in stmt.names:
                names.add(alias.asname or alias.name.split('.')[0])
    return names


def _unsafe_body(fn, module_names=frozenset()):
    """Operations a hybrid clone cannot repeat or cannot leave to the typed runtime.

    The exception rule is pymix's: only functions whose escaping exception is not caught by a
    boxed caller `try` become units at all, and an uncaught one exits 1 as CPython does.  So
    indexing, division/modulo and `raise` are allowed here.  A call is allowed only when it is a
    pure builtin the module/function does not shadow; a user call, method call, print or any
    import/try/with stays boxed because a later overflow fallback could repeat its side effect.
    Attribute stores and stores into a name the function does not bind stay boxed for the same
    reason.  A local list store is fine: the clone owns that list.
    """
    locals_ = _local_names(fn)
    for node in _own_nodes(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Name) and f.id in _PURE_CALLS
                    and f.id not in locals_ and f.id not in module_names):
                continue
            return 'a call can raise or have side effects'
        if isinstance(node, (ast.Try, ast.With, ast.Import, ast.ImportFrom)):
            return 'try/with/import is not safe to clone'
        if isinstance(node, ast.Assert):
            return 'assert can raise and is not tracked by the exception rule'
        if isinstance(node, ast.Raise):
            # pymix records `raise Name(...)`; a raise of a variable or an arbitrary expression
            # can escape a boxed caller's `try` unseen, so only the tracked constructor form is
            # safe to clone.
            exc = node.exc
            if not (isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name)):
                return 'raise of an expression is not tracked by the exception rule'
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return 'a global assignment is not safe to clone'
        if isinstance(node, ast.Delete):
            return 'delete is not safe to clone'
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            return 'attribute or index assignment is not safe to clone'
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)):
            base = node.value
            if isinstance(base, ast.Name) and base.id in locals_:
                continue
            return 'attribute or index assignment is not safe to clone'
        if isinstance(node, (ast.Await, ast.Yield, ast.YieldFrom)):
            return 'coroutine/generator code stays in CPython'
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            return 'power can raise or produce a complex result'
    return None


def _list_aliases(fn, list_params):
    """List parameter names plus locals assigned straight from one, to a fixed point.  In CPython
    such a local is another name for the caller's list; the typed clone got a copy.  A rebinding
    away from the alias later only makes this answer more conservative."""
    aliases = set(list_params)
    while True:
        grown = False
        for node in _own_nodes(fn):
            if (isinstance(node, (ast.Assign, ast.AnnAssign))
                    and isinstance(node.value, ast.Name) and node.value.id in aliases):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id not in aliases:
                        aliases.add(target.id)
                        grown = True
        if not grown:
            break
    return aliases


def _list_param_mutated(fn, list_params):
    """A list argument is copied into the typed call, so a function that mutates it must stay in
    CPython (mutation would otherwise not be visible to the caller).  This also refuses passing a
    list parameter on to another user function, which may mutate it one step away."""
    if not list_params:
        return False
    aliases = _list_aliases(fn, list_params)
    for node in _own_nodes(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in aliases and node.func.attr in _MUTATORS):
            return True
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id in aliases
                and isinstance(node.ctx, (ast.Store, ast.Del))):
            return True
        if isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id in aliases:
                return True
            if (isinstance(node.target, ast.Subscript) and isinstance(node.target.value, ast.Name)
                    and node.target.value.id in aliases):
                return True
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return True
    for node in _own_nodes(fn):
        if isinstance(node, ast.Call):
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(arg, ast.Name) and arg.id in aliases:
                    return True
    return False


def _list_param_returned(fn, list_params):
    """A list result is boxed into a fresh Python list, so returning a list parameter or a local
    alias of one would lose CPython's identity and later aliasing between caller and result.  A
    return that mentions such a name anywhere is refused conservatively (a fresh list expression
    containing the name is not accelerated either)."""
    if not list_params:
        return False
    aliases = _list_aliases(fn, list_params)
    for node in _own_nodes(fn):
        if isinstance(node, ast.Return) and node.value is not None:
            for sub in ast.walk(node.value):
                if (isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load)
                        and sub.id in aliases):
                    return True
    return False


def _analysis(src):
    """Build the program once through the real CLI and capture its mixed-mode units.

    A direct `pyc.build` call sees the raw Python source; the CLI first runs the Python-surface
    translation, merges local imports and applies the prelude, and that is the source the mixed
    mode analyses.  A subprocess with a temporary `sitecustomize.py` therefore patches the same
    `pyboxed2` and `pymix` objects the CLI uses, lets the CLI do a normal `--syntax python
    --exact-int` build, and writes the captured units to a JSON file.  The exact-int build is
    deliberate: the hybrid promises CPython's answers, so an int literal beyond int64 must not be
    truncated.  If the exact build is refused, a direct `pyboxed2.build` on the same temporary
    source is tried; if that also emits nothing, the hybrid runs as CPython.

    Details loosened only in that subprocess: the entry prototype regex requires a word boundary
    (`ail_unwind_<name>` must not match), the documented str ABI's `uint8_t *_out` result
    parameter is accepted by the existing validator (which writes through `int32_t *`), and
    parameter annotations seed `pymix`'s kinds.  The selection pass below still requires the body
    to have no operation that can trap.
    """
    import tempfile
    fd, name = tempfile.mkstemp(prefix='ail-hybrid-src-', suffix='.py')
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(src)
    source_path = Path(name)
    remove_source = True
    run_dir = Path(tempfile.mkdtemp(prefix='ail-cpython-analysis-'))
    capture_path = run_dir / 'capture.json'
    cli = _HERE / 'ail_chatgpt.py'
    site = run_dir / 'sitecustomize.py'
    site.write_text(r"""
import ast, json, os, re, sys
sys.path.insert(0, %r)
try:
    import pyboxed2, pyfunc, pymix
except Exception:
    raise SystemExit(0)
# The CLI's Python-surface pass marks every annotated return with a `__ail_checked_*__` contract
# (dunders.py), which `to_c` treats as a request for a checked outer contract and refuses for a
# str entry.  Mixed mode never asked for that contract; the body's own proof is the gate and the
# Python wrapper checks the value coming back, so drop only the return marker here.
_old_to_c = pyfunc.to_c
def _to_c(source, *args, **kwargs):
    source = re.sub(r'\s*->\s*__ail_checked_[A-Za-z0-9_]+__', '', source)
    return _old_to_c(source, *args, **kwargs)
pyfunc.to_c = _to_c
# CPython does not enforce annotations, but they are useful hints: the boundary still checks every
# value (a non-int for `x: int` falls back before the native call), and the existing emitter is
# asked to compile the function as usual.  Seeding only the parameter kinds lets a helper such as
# `def byte_length(word: str) -> int` reach to_c, whose own acceptance test remains the gate.
_old_fn_init = pymix._FnFacts.__init__
def _ann_kind(node):
    if isinstance(node, ast.Name):
        return {'int': pymix.INT, 'float': pymix.FLOAT, 'str': pymix.STR,
                'bool': pymix.BOOL, '__ail_checked_int__': pymix.INT,
                '__ail_checked_float__': pymix.FLOAT, '__ail_checked_str__': pymix.STR,
                '__ail_checked_bool__': pymix.BOOL}.get(node.id)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'list':
        item = node.slice
        if isinstance(item, ast.Name) and item.id == 'int':
            return pymix.LIST_INT
        if isinstance(item, ast.Name) and item.id == 'float':
            return pymix.LIST_FLOAT
    return None
def _fn_init(self, node):
    _old_fn_init(self, node)
    for arg in node.args.args:
        kind = _ann_kind(arg.annotation)
        if kind is not None:
            self.params[arg.arg] = kind
pymix._FnFacts.__init__ = _fn_init
_old_extract = pyboxed2._mix_extract_signature
_old_validate = pyboxed2._mix_validate_signature
_old_build = pyboxed2.build
_old_analyze = pymix.analyze
_last = {}
def _extract(csrc, mangled):
    m = re.search(r'^([A-Za-z_][\w ]*\*?\s*\b' + re.escape(mangled) + r'\s*\([^\n{;]*\))\s*\{', csrc, re.MULTILINE)
    return m.group(1) if m else None
def _validate(sig_text, mangled, params, ret):
    return _old_validate(sig_text.replace('uint8_t *_out', 'int32_t *_out'), mangled, params, ret)
def _facts():
    facts = {}
    analysis = _last.get('analysis')
    if analysis is None:
        return facts
    try:
        irs = analysis.function_ir
    except Exception:
        return facts
    for name, ir in irs.items():
        try:
            sig = ir.signature()
            facts[str(name)] = {'params': [[str(p), str(k)] for p, k in sig['params'].items()],
                                'ret': str(sig['ret']), 'is_bool_ret': bool(sig.get('is_bool_ret'))}
        except Exception:
            pass
    return facts
def _dump(report):
    try:
        data = {'mix_units': [list(u) for u in (report.get('mix_units') or [])],
                'typed_inline': list(report.get('typed_inline') or []),
                'facts': _facts(), 'note': str(report.get('note') or '')}
        with open(os.environ['AIL_HYBRID_CAPTURE'], 'w', encoding='utf-8') as handle:
            json.dump(data, handle)
    except Exception:
        pass
def _build(source, report, *args, **kwargs):
    # The mixed-mode ABI is int64 with an overflow -> Python fallback; exact-int lowering makes
    # `to_c` spell parameters as `ail_tint`, which that ABI (and the boxed caller) cannot call.
    # The general build still runs with the CLI's exact setting; only the unit generation below
    # is the int64 ABI. Any value that does not fit falls back to the original Python function.
    saved = os.environ.pop('AIL_EXACT_INT', None)
    try:
        result = _old_build(source, report, *args, **kwargs)
    finally:
        if saved is not None:
            os.environ['AIL_EXACT_INT'] = saved
    _dump(report)
    return result
def _analyze(source, *args, **kwargs):
    result = _old_analyze(source, *args, **kwargs)
    _last['analysis'] = result
    return result
pyboxed2._mix_extract_signature = _extract
pyboxed2._mix_validate_signature = _validate
pyboxed2.build = _build
pymix.analyze = _analyze
""" % str(_PKG), encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=str(run_dir) + os.pathsep + os.environ.get('PYTHONPATH', ''),
               AIL_HYBRID_CAPTURE=str(capture_path), AIL_NO_CACHE='1', AIL_CACHE=str(run_dir / 'cache'),
               AIL_EXACT_INT='1', AIL_SURFACE='python', AIL_GENERAL='v2')
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_NO_MIX', None)
    try:
        proc = subprocess.run([sys.executable, '-B', str(cli), 'compile', str(source_path),
                               '--syntax', 'python', '--exact-int', '-o', str(run_dir / 'analysis-only')],
                              env=env, capture_output=True, text=True, timeout=900)
        if proc.returncode != 0 or not capture_path.exists():
            # The CLI may refuse a program the raw mixed-mode emitter can still slice (a module
            # loop over a tuple, an unsupported import used only by `main`, ...).  A direct
            # pyboxed2 build analyses the original source and can still wire the independent
            # helpers; if that also fails, CPython fallback is the answer.
            capture_path.unlink(missing_ok=True)   # never reuse a partial capture from a failed CLI
            runner = run_dir / 'direct.py'
            runner.write_text(
                'import contextlib, io, os, sys\n'
                'from pathlib import Path\n'
                'sys.path.insert(0, %r)\n'
                'import ail_chatgpt, pyboxed2\n'
                'with contextlib.redirect_stderr(io.StringIO()):\n'
                '    text, _, _ = ail_chatgpt._load_sources(\n'
                '        Path(os.environ["AIL_HYBRID_SRC"]), (), "python", local_imports=True)\n'
                'pyboxed2.build(text, {}, allow_mix=True)\n' % str(_HERE),
                encoding='utf-8')
            direct_env = dict(env, AIL_HYBRID_SRC=str(source_path))
            try:
                subprocess.run([sys.executable, '-B', str(runner)], env=direct_env,
                               capture_output=True, text=True, timeout=900)
            except Exception:
                pass
        if not capture_path.exists():
            note = [line for line in (proc.stderr or proc.stdout or '').strip().splitlines() if line.strip()]
            text = note[-1] if note else 'the analysis build was refused'
            return {'mix_units': [], 'typed_inline': [], 'note': text[:600]}, {}
        data = json.loads(capture_path.read_text(encoding='utf-8'))
    except Exception as error:
        return {'mix_units': [], 'typed_inline': [], 'note': ('analysis failed: ' + str(error))[:600]}, {}
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
        if remove_source:
            source_path.unlink(missing_ok=True)
    facts = data.get('facts') or {}
    report = {'mix_units': data.get('mix_units') or [], 'typed_inline': data.get('typed_inline') or [],
              'note': data.get('note') or ''}
    return report, facts

def _select(src, tree, report, facts):
    """The units worth wrapping, with the safety filters the design names."""
    import bigcap
    import pymix
    import pyboxed2
    import unified

    funcs = _top_level_functions(tree)
    module_names = _module_bound_names(tree)
    big_hard = bigcap.marked(tree, local=False)
    big_local = bigcap.marked(tree)
    id_reach, id_any = pyboxed2._mix_identity_unsafe(tree)
    chosen = {}
    rejected = {}
    for mangled, pyname, csrc in report.get('mix_units') or []:
        if pyname not in funcs:
            continue
        info = facts.get(pyname)
        if info is None:
            continue
        params = [(p, k) for p, k in info.get('params') or []]
        ret = info.get('ret')
        if ret not in _SCALAR and ret not in _LIST_RET:
            rejected[pyname] = 'result kind %s stays in CPython' % ret
            continue
        if pyname in big_hard:
            rejected[pyname] = 'needs an int beyond int64'
            continue
        if pyname in big_local and ret not in ('int', 'bool'):
            rejected[pyname] = 'may overflow but does not return an int'
            continue
        if id_any and (pyname in id_reach or any(k == 'float' for _, k in params) or ret == 'float'):
            rejected[pyname] = 'the program compares numbers with `is`'
            continue
        bad = [k for _, k in params if k not in _SCALAR and k not in _LIST]
        if bad:
            rejected[pyname] = 'parameter kind %s stays in CPython' % bad[0]
            continue
        unsafe = _unsafe_body(funcs[pyname], module_names)
        if unsafe:
            rejected[pyname] = unsafe
            continue
        list_params = {p for p, k in params if k in _LIST}
        if _list_param_mutated(funcs[pyname], list_params):
            rejected[pyname] = 'the list parameter is mutated'
            continue
        if ret in _LIST_RET and _list_param_returned(funcs[pyname], list_params):
            rejected[pyname] = 'the result can be a list parameter (identity would be lost)'
            continue
        chosen[pyname] = {
            'name': pyname, 'mangled': mangled, 'params': params,
            'ret': ret, 'is_bool_ret': bool(info.get('is_bool_ret')),
        }
    return chosen, rejected


def _c_proto(item):
    args = []
    for p, kind in item['params']:
        cn = 'v_' + p
        if kind in ('int', 'bool'):
            args.append('int64_t ' + cn)
        elif kind == 'float':
            args.append('double ' + cn)
        elif kind == 'str':
            args.append('ail_str ' + cn)
        elif kind == 'list[int]':
            args.extend(['const int64_t *' + cn, 'int64_t ' + cn + '_len'])
        elif kind == 'list[float]':
            args.extend(['const double *' + cn, 'int64_t ' + cn + '_len'])
    if item['ret'] == 'str':
        args.extend(['uint8_t *_out', 'int64_t _cap'])
    elif item['ret'] == 'list[int]':
        args.extend(['int64_t *_out', 'int64_t _cap'])
    elif item['ret'] == 'list[float]':
        args.extend(['double *_out', 'int64_t _cap'])
    rtype = 'double' if item['ret'] == 'float' else 'int64_t'
    return '%s %s(%s)' % (rtype, item['mangled'], ', '.join(args))


def _wrapper_source(module, items):
    out = [
        '#include <Python.h>',
        '#include <stdint.h>',
        '#include <stdlib.h>',
        '#include <string.h>',
        '',
        'typedef struct { const uint8_t *p; int64_t n; _Bool bytes; } ail_str;',
        'static PyObject *AilHybridFallback;',
        # A clone\'s trap path calls this just before `_Exit(1)`.  The boxed program is CPython, so
        # its earlier `print()` text is in Python\'s sys.stdout buffer, not the typed runtime\'s
        # C buffer: flush it (and the C stream) first, exactly as CPython\'s normal exit would.
        'static void ail_hybrid_drain_stdout(void) {',
        '    PyGILState_STATE state = PyGILState_Ensure();',
        '    PyObject *sys = PyImport_ImportModule("sys");',
        '    if (sys != NULL) {',
        '        PyObject *out = PyObject_GetAttrString(sys, "stdout");',
        '        if (out != NULL) {',
        '            PyObject *res = PyObject_CallMethod(out, "flush", NULL);',
        '            Py_XDECREF(res);',
        '            Py_DECREF(out);',
        '        }',
        '        Py_DECREF(sys);',
        '    }',
        '    PyErr_Clear();',
        '    PyGILState_Release(state);',
        '    fflush(stdout);',
        '}',
        'void ail_mix_drain_out(void) { ail_hybrid_drain_stdout(); }',
        'static PyObject *ail_hybrid_fallback(void) {',
        '    PyErr_SetString(AilHybridFallback, "argument or result does not fit the AIL ABI");',
        '    return NULL;',
        '}',
        '',
    ]
    for item in items:
        out.append('extern %s;' % _c_proto(item))
    out.append('')
    for item in items:
        name = item['name']
        params = item['params']
        ret = item['ret']
        out.append('static PyObject *ail_w_%s(PyObject *self, PyObject *args) {' % name)
        out.append('    PyObject *o[%d];' % max(1, len(params)))
        out.append('    if (PyTuple_GET_SIZE(args) != %d) return ail_hybrid_fallback();' % len(params))
        # Every conversion failure after the declarations below must free whatever buffers an
        # earlier list argument already filled; `fallback:` does that.  When there are no buffers
        # the label is not emitted, so keep the direct return in that case.
        bufs = ['b%d' % i for i, (_p, kind) in enumerate(params)
                if kind in ('list[int]', 'list[float]')]
        fail = 'goto fallback' if bufs else 'return ail_hybrid_fallback()'
        for i, (p, kind) in enumerate(params):
            out.append('    o[%d] = PyTuple_GET_ITEM(args, %d);' % (i, i))
            # Declare every list buffer before any conversion loop.  A later loop can `goto
            # fallback` before its own declaration would have run; the label frees all of them,
            # so each must already be a valid pointer (NULL frees are no-ops).
            if kind == 'list[int]':
                out.append('    int64_t *b%d = NULL;' % i)
            elif kind == 'list[float]':
                out.append('    double *b%d = NULL;' % i)
        call = []
        for i, (p, kind) in enumerate(params):
            o = 'o[%d]' % i
            if kind in ('int', 'bool'):
                if kind == 'bool':
                    out.append('    if (!PyBool_Check(%s)) %s;' % (o, fail))
                    out.append('    int64_t a%d = PyObject_IsTrue(%s) ? 1 : 0;' % (i, o))
                else:
                    out.append('    if (!PyLong_CheckExact(%s)) %s;' % (o, fail))
                    out.append('    int ovf%d = 0; long long a%d = PyLong_AsLongLongAndOverflow(%s, &ovf%d);' % (i, i, o, i))
                    out.append('    if (ovf%d) %s;' % (i, fail))
                    out.append('    if (a%d == -1 && PyErr_Occurred()) { PyErr_Clear(); %s; }' % (i, fail))
                    out.append('    a%d = (int64_t)a%d;' % (i, i))
                call.append('a%d' % i)
            elif kind == 'float':
                out.append('    if (!PyFloat_CheckExact(%s)) %s;' % (o, fail))
                out.append('    double a%d = PyFloat_AsDouble(%s);' % (i, o))
                out.append('    if (a%d == -1.0 && PyErr_Occurred()) { PyErr_Clear(); %s; }' % (i, fail))
                call.append('a%d' % i)
            elif kind == 'str':
                out.append('    if (!PyUnicode_CheckExact(%s)) %s;' % (o, fail))
                out.append('    Py_ssize_t n%d = 0; const char *p%d = PyUnicode_AsUTF8AndSize(%s, &n%d);' % (i, i, o, i))
                out.append('    if (!p%d) { PyErr_Clear(); %s; }' % (i, fail))
                out.append('    ail_str a%d; a%d.p = (const uint8_t *)p%d; a%d.n = (int64_t)n%d; a%d.bytes = 1;' % (i, i, i, i, i, i))
                out.append('    for (Py_ssize_t k%d = 0; k%d < n%d; k%d++) if ((unsigned char)p%d[k%d] >= 0x80) { a%d.bytes = 0; break; }' % (i, i, i, i, i, i, i))
                call.append('a%d' % i)
            elif kind == 'list[int]':
                out.append('    if (!PyList_CheckExact(%s)) %s;' % (o, fail))
                out.append('    Py_ssize_t n%d = PyList_GET_SIZE(%s);' % (i, o))
                out.append('    b%d = n%d ? (int64_t *)PyMem_Malloc((size_t)n%d * sizeof(int64_t)) : NULL;' % (i, i, i))
                out.append('    if (n%d && !b%d) goto fallback;' % (i, i))
                out.append('    for (Py_ssize_t k%d = 0; k%d < n%d; k%d++) {' % (i, i, i, i))
                out.append('        PyObject *e%d = PyList_GET_ITEM(%s, k%d);' % (i, o, i))
                out.append('        if (!PyLong_CheckExact(e%d)) goto fallback;' % i)
                out.append('        int ovf%d = 0; long long v%d = PyLong_AsLongLongAndOverflow(e%d, &ovf%d);' % (i, i, i, i))
                out.append('        if (ovf%d) goto fallback;' % i)
                out.append('        if (v%d == -1 && PyErr_Occurred()) { PyErr_Clear(); goto fallback; }' % i)
                out.append('        b%d[k%d] = (int64_t)v%d;' % (i, i, i))
                out.append('    }')
                call.append('b%d' % i)
                call.append('(int64_t)n%d' % i)
            elif kind == 'list[float]':
                out.append('    if (!PyList_CheckExact(%s)) %s;' % (o, fail))
                out.append('    Py_ssize_t n%d = PyList_GET_SIZE(%s);' % (i, o))
                out.append('    b%d = n%d ? (double *)PyMem_Malloc((size_t)n%d * sizeof(double)) : NULL;' % (i, i, i))
                out.append('    if (n%d && !b%d) goto fallback;' % (i, i))
                out.append('    for (Py_ssize_t k%d = 0; k%d < n%d; k%d++) {' % (i, i, i, i))
                out.append('        PyObject *e%d = PyList_GET_ITEM(%s, k%d);' % (i, o, i))
                out.append('        if (!PyFloat_CheckExact(e%d)) goto fallback;' % i)
                out.append('        double v%d = PyFloat_AsDouble(e%d);' % (i, i))
                out.append('        if (v%d == -1.0 && PyErr_Occurred()) { PyErr_Clear(); goto fallback; }' % i)
                out.append('        b%d[k%d] = v%d;' % (i, i, i))
                out.append('    }')
                call.append('b%d' % i)
                call.append('(int64_t)n%d' % i)
        cargs = ', '.join(call)
        if ret == 'str':
            out.append('    int64_t need;')
            out.append('    Py_BEGIN_ALLOW_THREADS')
            out.append('    need = %s(%s%sNULL, 0);' % (item['mangled'], cargs, ', ' if cargs else ''))
            out.append('    Py_END_ALLOW_THREADS')
            out.append('    if (need < 0) %s;' % fail)
            out.append('    uint8_t *sb = (uint8_t *)PyMem_Malloc((size_t)(need > 0 ? need : 1));')
            out.append('    if (!sb) {')
            for b in bufs:
                out.append('        PyMem_Free(%s);' % b)
            out.append('        return PyErr_NoMemory();')
            out.append('    }')
            out.append('    Py_BEGIN_ALLOW_THREADS')
            out.append('    if (need > 0) %s(%s%s(void *)sb, need);' % (item['mangled'], cargs, ', ' if cargs else ''))
            out.append('    Py_END_ALLOW_THREADS')
            out.append('    PyObject *res = PyUnicode_DecodeUTF8((const char *)sb, (Py_ssize_t)need, NULL);')
            out.append('    PyMem_Free(sb);')
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    if (!res) { PyErr_Clear(); return ail_hybrid_fallback(); }')
            out.append('    return res;')
        elif ret in ('list[int]', 'list[float]'):
            is_int = ret == 'list[int]'
            elem = 'int64_t' if is_int else 'double'
            sep = ', ' if cargs else ''
            out.append('    int64_t need;')
            out.append('    Py_BEGIN_ALLOW_THREADS')
            out.append('    need = %s(%s%sNULL, 0);' % (item['mangled'], cargs, sep))
            out.append('    Py_END_ALLOW_THREADS')
            out.append('    if (need < 0) %s;' % fail)
            out.append('    %s *rb = (%s *)PyMem_Malloc((size_t)(need > 0 ? need : 1) * sizeof(%s));' % (elem, elem, elem))
            out.append('    if (!rb) {')
            for b in bufs:
                out.append('        PyMem_Free(%s);' % b)
            out.append('        return PyErr_NoMemory();')
            out.append('    }')
            out.append('    Py_BEGIN_ALLOW_THREADS')
            out.append('    if (need > 0) %s(%s%srb, need);' % (item['mangled'], cargs, sep))
            out.append('    Py_END_ALLOW_THREADS')
            out.append('    PyObject *res = PyList_New((Py_ssize_t)need);')
            out.append('    if (!res) {')
            out.append('        PyMem_Free(rb);')
            for b in bufs:
                out.append('        PyMem_Free(%s);' % b)
            out.append('        return PyErr_NoMemory();')
            out.append('    }')
            out.append('    for (Py_ssize_t i = 0; i < (Py_ssize_t)need; i++) {')
            if is_int:
                out.append('        PyObject *v = PyLong_FromLongLong((long long)rb[i]);')
            else:
                out.append('        PyObject *v = PyFloat_FromDouble(rb[i]);')
            out.append('        if (!v) { Py_DECREF(res); PyMem_Free(rb);')
            for b in bufs:
                out.append('            PyMem_Free(%s);' % b)
            out.append('            return NULL; }')
            out.append('        PyList_SET_ITEM(res, i, v);')
            out.append('    }')
            out.append('    PyMem_Free(rb);')
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    return res;')
        elif ret == 'float':
            out.append('    double r;')
            out.append('    Py_BEGIN_ALLOW_THREADS')
            out.append('    r = %s(%s);' % (item['mangled'], cargs))
            out.append('    Py_END_ALLOW_THREADS')
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    return PyFloat_FromDouble(r);')
        else:
            out.append('    extern __thread int %s__mix_overflow;' % item['mangled'])
            out.append('    int64_t r; int ovf;')
            out.append('    Py_BEGIN_ALLOW_THREADS')
            out.append('    r = %s(%s);' % (item['mangled'], cargs))
            out.append('    ovf = %s__mix_overflow;' % item['mangled'])
            out.append('    Py_END_ALLOW_THREADS')
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    if (ovf) return ail_hybrid_fallback();')
            if ret == 'bool':
                out.append('    return PyBool_FromLong((long)r);')
            else:
                out.append('    return PyLong_FromLongLong((long long)r);')
        if bufs:
            out.append('fallback:')
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    return ail_hybrid_fallback();')
        out.append('}')
        out.append('')
    out.append('static PyMethodDef ail_methods[] = {')
    for item in items:
        out.append('    {"%s", ail_w_%s, METH_VARARGS, NULL},' % (item['name'], item['name']))
    out.append('    {NULL, NULL, 0, NULL}')
    out.append('};')
    out.append('static struct PyModuleDef ail_module = {PyModuleDef_HEAD_INIT, "%s", NULL, -1, ail_methods};' % module)
    out.append('PyMODINIT_FUNC PyInit_%s(void) {' % module)
    out.append('    PyObject *m = PyModule_Create(&ail_module);')
    out.append('    if (!m) return NULL;')
    out.append('    AilHybridFallback = PyErr_NewException("%s.Fallback", NULL, NULL);' % module)
    out.append('    if (!AilHybridFallback) { Py_DECREF(m); return NULL; }')
    out.append('    Py_INCREF(AilHybridFallback);')
    out.append('    PyModule_AddObject(m, "Fallback", AilHybridFallback);')
    out.append('    return m;')
    out.append('}')
    return '\n'.join(out) + '\n'


def _insertion_point(tree):
    """After the module docstring and any `from __future__` imports, so the preamble is legal."""
    body = tree.body
    at = 0
    i = 0
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        at = body[0].end_lineno or 0
        i = 1
    while i < len(body) and isinstance(body[i], ast.ImportFrom) and body[i].module == '__future__':
        at = body[i].end_lineno or at
        i += 1
    return at


def _preamble(module, original_path):
    _text = (
        '\n# --- AIL CPython hybrid (generated preamble) ---\n'
        'import os as _ail_hybrid_os\n'
        'import sys as _ail_hybrid_sys\n'
        '_ail_hybrid_source = __AIL_SOURCE__\n'
        '_ail_hybrid_source_dir = _ail_hybrid_os.path.dirname(_ail_hybrid_source)\n'
        'if _ail_hybrid_source_dir and _ail_hybrid_source_dir not in _ail_hybrid_sys.path:\n'
        '    _ail_hybrid_sys.path.insert(0, _ail_hybrid_source_dir)\n'
        'if __name__ == "__main__" and _ail_hybrid_sys.argv:\n'
        '    _ail_hybrid_sys.argv[0] = _ail_hybrid_source\n'
        '__file__ = _ail_hybrid_source\n'
        'try:\n'
        '    import __AIL_MODULE__ as _ail_hybrid_native\n'
        'except Exception:\n'
        '    _ail_hybrid_native = None\n'
        'def _ail_hybrid_invoke(_native, _original, _pos, _kw, _varargs, _varkw):\n'
        '    if _native is not None and not _varkw:\n'
        '        try:\n'
        '            return _native(*_pos, *_kw.values(), *_varargs)\n'
        '        except _ail_hybrid_native.Fallback:\n'
        '            pass\n'
        '    return _original(*_pos, *_varargs, **_kw, **_varkw)\n'
        'def _ail_hybrid_make(_native, _original):\n'
        '    if _native is None or _original is None:\n'
        '        return _original\n'
        '    try:\n'
        '        import inspect as _ail_hybrid_inspect\n'
        '        _params = list(_ail_hybrid_inspect.signature(_original).parameters.values())\n'
        '    except Exception:\n'
        '        return _original\n'
        '    _posonly, _pos, _kwonly = [], [], []\n'
        '    _vararg = _varkw = None\n'
        '    for _p in _params:\n'
        '        if _p.kind == _ail_hybrid_inspect.Parameter.POSITIONAL_ONLY:\n'
        '            _posonly.append(_p)\n'
        '        elif _p.kind == _ail_hybrid_inspect.Parameter.POSITIONAL_OR_KEYWORD:\n'
        '            _pos.append(_p)\n'
        '        elif _p.kind == _ail_hybrid_inspect.Parameter.KEYWORD_ONLY:\n'
        '            _kwonly.append(_p)\n'
        '        elif _p.kind == _ail_hybrid_inspect.Parameter.VAR_POSITIONAL:\n'
        '            _vararg = _p\n'
        '        elif _p.kind == _ail_hybrid_inspect.Parameter.VAR_KEYWORD:\n'
        '            _varkw = _p\n'
        '    _decl = [p.name for p in _posonly]\n'
        '    if _posonly:\n'
        '        _decl.append("/")\n'
        '    _decl.extend(p.name for p in _pos)\n'
        '    if _vararg is not None:\n'
        '        _decl.append("*" + _vararg.name)\n'
        '    elif _kwonly:\n'
        '        _decl.append("*")\n'
        '    _decl.extend(p.name for p in _kwonly)\n'
        '    if _varkw is not None:\n'
        '        _decl.append("**" + _varkw.name)\n'
        '    _posnames = [p.name for p in _posonly + _pos]\n'
        '    if len(_posnames) == 1:\n'
        '        _postuple = "(" + _posnames[0] + ",)"\n'
        '    else:\n'
        '        _postuple = "(" + ", ".join(_posnames) + ")"\n'
        '    _kwtext = "{" + ", ".join("%r: %s" % (p.name, p.name) for p in _kwonly) + "}"\n'
        '    _varkwtext = _varkw.name if _varkw is not None else "{}"\n'
        '    _varargtext = _vararg.name if _vararg is not None else "()"\n'
        '    # The generated body needs three helper names from its globals.  A parameter may have\n'
        '    # any of the obvious names, so pick spellings the parameter list cannot shadow.\n'
        '    _taken = {p.name for p in _params}\n'
        '    _helpers = {}\n'
        '    for _role in ("invoke", "native", "original"):\n'
        '        _nm = "__ail_hybrid_" + _role\n'
        '        while _nm in _taken:\n'
        '            _nm += "_"\n'
        '        _taken.add(_nm)\n'
        '        _helpers[_role] = _nm\n'
        '    _src = ("def _ail_hybrid_call(%s):\\n"\n'
        '            "    return %s(%s, %s, %s, %s, %s, %s)\\n"\n'
        '            % (", ".join(_decl), _helpers["invoke"], _helpers["native"],\n'
        '               _helpers["original"], _postuple, _kwtext, _varargtext, _varkwtext))\n'
        '    _namespace = {_helpers["invoke"]: _ail_hybrid_invoke,\n'
        '                  _helpers["native"]: _native,\n'
        '                  _helpers["original"]: _original}\n'
        '    exec(_src, _namespace)\n'
        '    _call = _namespace["_ail_hybrid_call"]\n'
        '    _call.__name__ = _original.__name__\n'
        '    _call.__qualname__ = _original.__qualname__\n'
        '    _call.__doc__ = _original.__doc__\n'
        '    _call.__module__ = _original.__module__\n'
        '    _call.__annotations__ = getattr(_original, "__annotations__", {})\n'
        '    _call.__defaults__ = getattr(_original, "__defaults__", None)\n'
        '    _call.__kwdefaults__ = getattr(_original, "__kwdefaults__", None)\n'
        '    try:\n'
        '        _call.__dict__.update(_original.__dict__)\n'
        '    except Exception:\n'
        '        pass\n'
        '    # CPython introspection sees the original code layout, including its local names.\n'
        '    # `co_nlocals` must be updated with `co_varnames` (CodeType rejects a mismatch); only\n'
        '    # the wrapper\'s parameter slots are ever loaded, so the extra locals are inert.\n'
        '    try:\n'
        '        _oc = _original.__code__\n'
        '        _kw = {"co_name": _oc.co_name, "co_varnames": _oc.co_varnames,\n'
        '               "co_nlocals": len(_oc.co_varnames),\n'
        '               "co_filename": _oc.co_filename, "co_firstlineno": _oc.co_firstlineno}\n'
        '        if hasattr(_oc, "co_qualname"):\n'
        '            _kw["co_qualname"] = _oc.co_qualname\n'
        '        _call.__code__ = _call.__code__.replace(**_kw)\n'
        '    except Exception:\n'
        '        pass\n'
        '    return _call\n'
        'if _ail_hybrid_native is None:\n'
        '    def _ail_hybrid_make(_native, _original):\n'
        '        return _original\n'
        '# --- original program follows ---\n\n'
    )
    return _text.replace('__AIL_MODULE__', module).replace('__AIL_SOURCE__', repr(str(original_path)))


def _hybrid_source(source, tree, module, names, original_path):
    """Original text plus a preamble and one rebinding after each accelerated top-level def."""
    lines = source.splitlines(keepends=True)
    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'
    funcs = _top_level_functions(tree)
    edits = []
    at = _insertion_point(tree)
    edits.append((at, 0, _preamble(module, original_path)))
    for name in names:
        fn = funcs.get(name)
        if fn is not None and getattr(fn, 'end_lineno', None):
            text = ('try:\n'
                    '    %s = _ail_hybrid_make(_ail_hybrid_native.%s, %s)\n'
                    'except Exception:\n'
                    '    pass\n' % (name, name, name))
            edits.append((fn.end_lineno, 0, text))
    edits.sort(key=lambda e: e[0], reverse=True)
    for at, _off, text in edits:
        lines.insert(at, text)
    return ''.join(lines)


def _compile(items, units, module, out_dir):
    from pipeline import compiler, opt_flags
    cc = compiler()
    extra = ['-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd',
             '-fno-asynchronous-unwind-tables']
    include = sysconfig.get_paths().get('include') or sysconfig.get_path('include')
    cflags = [cc, *opt_flags(), *extra, '-fPIC', '-pthread', '-I' + include]
    objects = []
    for i, item in enumerate(items):
        csrc = next(u[2] for u in units if u[1] == item['name'])
        # The mixed-mode overflow signal is a per-function global.  The hybrid releases the GIL
        # around every native call, so two threads can otherwise reset/read each other's flag and
        # a truncated int could escape.  Give the hybrid's copy of the unit a thread-local flag;
        # the wrapper's matching `extern` below is thread-local too.
        csrc = re.sub(r'(?m)^extern int (%s__mix_overflow);$' % re.escape(item['mangled']),
                      r'extern __thread int \1;', csrc)
        csrc = re.sub(r'(?m)^int (%s__mix_overflow) = 0;$' % re.escape(item['mangled']),
                      r'__thread int \1 = 0;', csrc)
        # The int64-overflow escape is per-call as well: the buffer and the save pointer must
        # belong to the calling thread, or two concurrent overflow fallbacks restore each
        # other's cleanup state or longjmp through the other thread's frame (SIGABRT).
        csrc = re.sub(r'(?m)^static jmp_buf (%s__mix_jmp);$' % re.escape(item['mangled']),
                      r'static __thread jmp_buf \1;', csrc)
        csrc = re.sub(r'(?m)^static ([A-Za-z_][A-Za-z0-9_]* \*%s__mix_savep);$'
                      % re.escape(item['mangled']), r'static __thread \1;', csrc)
        cpath = out_dir / ('%s_unit%d.c' % (module, i))
        opath = out_dir / ('%s_unit%d.o' % (module, i))
        cpath.write_text(csrc, encoding='utf-8')
        r = subprocess.run([*cflags, '-c', '-o', str(opath), str(cpath)], capture_output=True, text=True)
        if r.returncode:
            for p in out_dir.glob(module + '_unit*'):
                try: p.unlink()
                except OSError: pass
            raise RuntimeError('typed unit %r: %s' % (item['name'], r.stderr[-1500:]))
        objects.append(str(opath))
    wrapper = out_dir / ('%s_wrapper.c' % module)
    wrapper.write_text(_wrapper_source(module, items), encoding='utf-8')
    so = out_dir / (module + _EXT_SUFFIX)
    r = subprocess.run([cc, *opt_flags(), *extra, '-fPIC', '-pthread', '-I' + include, '-shared', '-o', str(so),
                        str(wrapper)] + objects + ['-lm'], capture_output=True, text=True)
    if r.returncode:
        for p in list(out_dir.glob(module + '_unit*')) + [wrapper]:
            try: p.unlink()
            except OSError: pass
        raise RuntimeError('extension link: %s' % r.stderr[-1500:])
    for p in out_dir.glob(module + '_unit*'):
        try:
            p.unlink()
        except OSError:
            pass
    try:
        wrapper.unlink()
    except OSError:
        pass
    return so


def build(source_path, output_dir):
    """Build a CPython hybrid for `source_path` into `output_dir`; return the report dict."""
    source_path = Path(source_path).resolve()
    output_dir = Path(output_dir).resolve()
    source = source_path.read_text(encoding='utf-8')
    tree = ast.parse(source, filename=str(source_path))
    stem = source_path.stem
    module = _module_name(stem)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        'schema': 'ail.cpython_hybrid/1',
        'source': str(source_path),
        'python': sys.version.split()[0],
        'module': module,
        'accelerated': [],
        'rejected': {},
        'extension': None,
    }
    chosen = {}
    try:
        units_report, facts = _analysis(source)
        chosen, report['rejected'] = _select(source, tree, units_report, facts)
        units = units_report.get('mix_units') or []
        items = [chosen[name] for name in sorted(chosen)
                 if any(u[1] == name for u in units)]
        if items:
            so = _compile(items, units, module, output_dir)
            report['extension'] = so.name
            report['accelerated'] = sorted(i['name'] for i in items)
        elif units:
            report['note'] = 'the typed functions were not safe to wrap; the program runs in CPython'
    except Exception as error:
        report['note'] = 'no extension: %s' % error

    # Always keep an unmodified copy and a runnable hybrid copy.
    (output_dir / (stem + '.orig.py')).write_text(source, encoding='utf-8')
    hybrid = _hybrid_source(source, tree, module, report['accelerated'], source_path)
    (output_dir / (stem + '.py')).write_text(hybrid, encoding='utf-8')
    launcher = output_dir / stem
    launcher.write_text('#!/bin/sh\nexec "${AIL_PYTHON:-python3}" "$(dirname "$0")/%s.py" "$@"\n' % stem,
                        encoding='utf-8')
    launcher.chmod(0o755)
    (output_dir / 'build.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n',
                                           encoding='utf-8')
    return report
