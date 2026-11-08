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
import copy
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


def _constant_value(node):
    """The value of a numeric literal, including its unary sign (`-3`, `+2`)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _constant_value(node.operand)
        if value is not None:
            return -value if isinstance(node.op, ast.USub) else value
    return None


def _nonzero_constant(node):
    """A literal divisor this pass can prove nonzero (`t % 8`, `x // -3`)."""
    value = _constant_value(node)
    return value is not None and value != 0


_SAFE_STR_NOARGS = frozenset({
    'upper', 'lower', 'casefold', 'strip', 'lstrip', 'rstrip', 'capitalize', 'title',
    'swapcase', 'split', 'rsplit', 'splitlines', 'isdigit', 'isalpha', 'isalnum',
    'isspace', 'isupper', 'islower', 'istitle', 'isdecimal', 'isnumeric', 'isidentifier',
    'isprintable', 'isascii',
})
_SAFE_STR_LITERAL_ARGS = frozenset({
    'strip', 'lstrip', 'rstrip', 'split', 'rsplit', 'replace', 'removeprefix',
    'removesuffix', 'find', 'rfind', 'count', 'startswith', 'endswith',
})
_STR_RESULT_NOARGS = frozenset({
    'upper', 'lower', 'casefold', 'strip', 'lstrip', 'rstrip', 'capitalize', 'title',
    'swapcase',
})
_STR_RESULT_ARGS = frozenset({
    'strip', 'lstrip', 'rstrip', 'replace', 'removeprefix', 'removesuffix',
})
_STR_LIST_METHODS = frozenset({'split', 'rsplit', 'splitlines'})


def _str_literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _int_literal(node):
    if isinstance(node, ast.Constant):
        return isinstance(node.value, int) and not isinstance(node.value, bool)
    return (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub))
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int)
            and not isinstance(node.operand.value, bool))


def _safe_str_method_args(method, args):
    """Argument shapes that cannot make a str method raise: only the exact types CPython wants."""
    if method in ('strip', 'lstrip', 'rstrip'):
        return len(args) <= 1 and (not args or _str_literal(args[0])
                                   or (isinstance(args[0], ast.Constant) and args[0].value is None))
    if method in ('split', 'rsplit'):
        if not args:
            return True
        sep = args[0]
        if not ((_str_literal(sep) and sep.value != '')
                or (isinstance(sep, ast.Constant) and sep.value is None)):
            return False
        return len(args) <= 2 and (len(args) < 2 or _int_literal(args[1]))
    if method == 'replace':
        return (1 <= len(args) <= 3 and _str_literal(args[0]) and _str_literal(args[1])
                and (len(args) < 3 or _int_literal(args[2])))
    if method in ('removeprefix', 'removesuffix'):
        return len(args) == 1 and _str_literal(args[0])
    if method in ('find', 'rfind', 'count', 'startswith', 'endswith'):
        return (1 <= len(args) <= 3 and _str_literal(args[0])
                and all(_int_literal(a) for a in args[1:]))
    return False


def _provably_str(node, str_names):
    """A str result proved from a str parameter, a str literal, and the str methods that always
    return str.  CPython does not enforce annotations, so only the body's own evidence counts."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.Name):
        return node.id in str_names
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _provably_str(node.left, str_names) and _provably_str(node.right, str_names)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if not _provably_str(node.func.value, str_names) or node.keywords:
                return False
            if attr == 'join':
                return len(node.args) == 1 and _provably_str_seq(node.args[0], str_names)
            if attr in _STR_RESULT_NOARGS and not node.args:
                return True
            if attr in _STR_RESULT_ARGS and _safe_str_method_args(attr, node.args):
                return True
    return False


def _provably_str_seq(node, str_names):
    """An iterable whose elements are all str, so `join`/`sorted`/`reversed` cannot raise."""
    if _provably_str(node, str_names):
        return True
    if isinstance(node, ast.List):
        return all(_provably_str(e, str_names) for e in node.elts)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == 'reversed' \
                and len(node.args) == 1 and not node.keywords:
            return _provably_str_seq(node.args[0], str_names)
        if isinstance(node.func, ast.Attribute) and node.func.attr in _STR_LIST_METHODS \
                and not node.keywords and _provably_str(node.func.value, str_names):
            return _safe_str_method_args(node.func.attr, node.args)
    return False


def _provably_list(node, list_names):
    if isinstance(node, ast.Name):
        return node.id in list_names
    if isinstance(node, ast.List):
        return True
    return False


def _provably_number(node, num_names, float_names=(), int_names=(), int_result=False):
    """An int/float/bool parameter or literal, or a sign applied to one: `str` of these cannot
    raise.  A unary `-` of an int can overflow on INT64_MIN, so it is safe only when the clone's
    int/bool result routes that through the overflow wrapper; a float negation is always safe.
    (Overflow of a bare int is not an arithmetic result and so is not relevant here.)"""
    if isinstance(node, ast.Name):
        return node.id in num_names
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        if _provably_float(node.operand, float_names):
            return True
        if isinstance(node.op, ast.UAdd):
            return _provably_number(node.operand, num_names, float_names, int_names,
                                    int_result)
        return int_result and _provably_int(node.operand, int_names, int_result)
    return False


def _provably_int(node, int_names, int_result=False, bool_names=(), allow_bool=True):
    """A value `int()` is the identity on: an int/bool parameter or literal (a float is not one;
    `int(<float>)` can raise ValueError/OverflowError, which a clone cannot reproduce here).  A
    unary `-` of an int needs the int/bool result's overflow wrapper, as in `_provably_number`.

    `allow_bool=False` additionally rejects a bool value.  `abs` preserves boolness (and a unary
    `+`/`-` of a bool stays bool in the typed clone), so `abs(<bool>)` returns a bool where CPython
    returns an int; only `int(...)` converts it, so that call resets the flag."""
    if isinstance(node, ast.Name):
        return node.id in int_names and (allow_bool or node.id not in bool_names)
    if isinstance(node, ast.Constant):
        return isinstance(node.value, int) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        if isinstance(node.op, ast.UAdd):
            return _provably_int(node.operand, int_names, int_result, bool_names, allow_bool)
        return int_result and _provably_int(node.operand, int_names, int_result, bool_names,
                                            allow_bool)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ('int', 'abs') and len(node.args) == 1 and not node.keywords:
        if node.func.id == 'int':
            return _provably_int(node.args[0], int_names, int_result, bool_names, True)
        return _provably_int(node.args[0], int_names, int_result, bool_names, False)
    return False


def _provably_float(node, float_names):
    if isinstance(node, ast.Name):
        return node.id in float_names
    if isinstance(node, ast.Constant):
        return isinstance(node.value, float)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _provably_float(node.operand, float_names)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ('int', 'float', 'abs') and len(node.args) == 1 \
            and not node.keywords:
        return _provably_float(node.args[0], float_names)
    return False


def _native_call_ok(node, natives, kinds):
    """obs4: a call of another selected native `g` (or of the function itself, assumed
    optimistically) is as safe as `g`'s own native entry when every argument is passed
    positionally, none is defaulted, and each has exactly the CPython kind `g`'s entry checks.
    `kinds` is the caller's exact-kind pass; the run-time guard re-checks that the global `g`
    is still that def (section 5.2 of OBSERVED_TYPES.md)."""
    func = node.func
    if not natives or kinds is None or not isinstance(func, ast.Name) or node.keywords:
        return False
    sig = natives.get(func.id)
    if sig is None or func.id in kinds.local_names:
        return False
    params = sig['params']
    if len(node.args) != len(params) or any(isinstance(a, ast.Starred) for a in node.args):
        return False
    return all(kinds.kind(a) == k for a, (_p, k) in zip(node.args, params))


def _safe_call(node, str_names, list_names, num_names=(), int_names=(), float_names=(), ret=None,
               bool_names=(), fresh=(), natives=None, kinds=None):
    """A call this pass can prove cannot raise and has no side effect.  Everything else stays a
    refusal: the hybrid must return CPython's value or fall back, never a partial answer.
    `fresh` names the list the function builds and returns (`_list_return_proof`): appending to
    it changes nothing any caller can see before the return."""
    if _native_call_ok(node, natives, kinds):
        return True
    func = node.func
    if isinstance(func, ast.Attribute):
        receiver = func.value
        if isinstance(receiver, ast.Name) and receiver.id in fresh and func.attr == 'append' \
                and len(node.args) == 1 and not node.keywords:
            return True
        if _provably_str(receiver, str_names):
            if not node.keywords:
                if not node.args and func.attr in _SAFE_STR_NOARGS:
                    return True
                if func.attr in _SAFE_STR_LITERAL_ARGS and \
                        _safe_str_method_args(func.attr, node.args):
                    return True
                if func.attr == 'join' and len(node.args) == 1 \
                        and _provably_str_seq(node.args[0], str_names):
                    return True
            return False
        if _provably_list(receiver, list_names) and func.attr == 'copy' \
                and not node.args and not node.keywords:
            return True
        return False
    if not isinstance(func, ast.Name) or node.keywords:
        return False
    args = node.args
    if func.id == 'len' and len(args) == 1:
        return (_provably_str(args[0], str_names) or _provably_list(args[0], list_names)
                or isinstance(args[0], ast.List))
    if func.id == 'reversed' and len(args) == 1:
        return _provably_str_seq(args[0], str_names) or _provably_list(args[0], list_names)
    if func.id == 'abs' and len(args) == 1:
        # float abs is fabs; int abs can overflow only on INT64_MIN, which an int/bool result
        # routes through the clone's overflow wrapper (and so back to CPython).  A str/list
        # result has no such wrapper, so an int abs stays refused there.
        return (_provably_float(args[0], float_names)
                or (ret in ('int', 'bool')
                    and _provably_int(args[0], int_names, True, bool_names, False)))
    if func.id == 'int' and len(args) <= 1:
        # int(<int/bool>) is the identity; int(<float>) can raise ValueError/OverflowError,
        # which this clone cannot reproduce without an overflow wrapper for every result kind.
        # A unary minus of an int is the same overflow question as in `str`.
        return not args or _provably_int(args[0], int_names, ret in ('int', 'bool'))
    if func.id == 'str' and len(args) <= 1:
        # `str(-x)` overflows on INT64_MIN unless the int/bool result's wrapper can fall back.
        return not args or _provably_number(args[0], num_names, float_names, int_names,
                                             ret in ('int', 'bool')) \
            or _provably_str(args[0], str_names)
    return False


def _variable_division_ok(node, kinds):
    """obs5: `/`, `//`, `%` by a divisor that is not a nonzero literal.  When both operands are
    exactly int/bool/float (the exact-kind pass; never a str, whose `%` formats), the typed clone
    computes CPython's value: floor `//`/`%` for ints and floats (`pydiv`/`pymod`,
    `ail_ffloormod`, written after CPython's float_divmod), a correctly rounded int `/`
    (`ail_fdiv_i`), and an int64 overflow (`INT64_MIN // -1`) takes the overflow stop.  A zero
    divisor stops the clone with a ZeroDivisionError message, which `_TRAP_DIES` turns into a
    fallback: CPython re-runs the call and raises its own exception.  `**` stays refused (a
    negative float base gives a complex result)."""
    if kinds is None or not isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
        return False
    if isinstance(node, ast.BinOp):
        left, right = node.left, node.right
    else:
        left, right = node.target, node.value
    return kinds.kind(left) in _NUM_KINDS and kinds.kind(right) in _NUM_KINDS


def _has_variable_division(fn):
    """The body divides by something other than a nonzero literal (a zero-division stop is
    reachable, so the unit needs the trap pad)."""
    for node in _own_nodes(fn):
        if isinstance(node, (ast.BinOp, ast.AugAssign)) \
                and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            right = node.right if isinstance(node, ast.BinOp) else node.value
            if not _nonzero_constant(right):
                return True
    return False


def _unsafe_body(fn, params=(), ret=None, fresh=(), natives=None, kinds=None):
    """Operations whose typed form traps or leaves Python's exception model.  A hybrid call must
    either return CPython's value or fall back, so a body that can raise stays in CPython: a
    subscript (IndexError/KeyError), division or power (ZeroDivisionError, complex results), an
    arbitrary call, and `raise`/`assert`/`try`/`with`/import are all outside this pass.  A division
    by a literal nonzero divisor cannot raise, and a call to a pure str method (or `len`,
    `reversed`) whose receiver and arguments are provably the right type cannot raise either, so
    both stay eligible.  This is deliberately conservative; a missed speed-up is safe."""
    str_names = {p for p, kind in params if kind == 'str'}
    list_names = {p for p, kind in params if kind in _LIST} | set(fresh)
    num_names = {p for p, kind in params if kind in ('int', 'float', 'bool')}
    int_names = {p for p, kind in params if kind in ('int', 'bool')}
    bool_names = {p for p, kind in params if kind == 'bool'}
    float_names = {p for p, kind in params if kind == 'float'}
    if kinds is not None:
        # obs4: a local the exact-kind pass proves is always a CPython str (`ch = src[i]`,
        # `for ch in src`) is as good a receiver for a pure str method as a str parameter.
        str_names |= {n for n, k in kinds.env.items() if k == 'str'}
    for node in _own_nodes(fn):
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                return 'slice indexing can raise'
            # A non-slice index is allowed: the clone's own IndexError/KeyError stop is
            # turned into a per-call fallback (see _trap_patch), so the Python wrapper
            # re-runs the original function and CPython's exception is the one observed.
            continue
        if isinstance(node, (ast.BinOp, ast.AugAssign)) \
                and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
            right = node.right if isinstance(node, ast.BinOp) else node.value
            if (isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod))
                    and _nonzero_constant(right)):
                continue
            if _variable_division_ok(node, kinds):
                continue
            return 'division or power can raise'
        if isinstance(node, ast.Call) and not _safe_call(node, str_names, list_names, num_names,
                                                          int_names, float_names, ret, bool_names,
                                                          fresh, natives, kinds):
            return 'a call can raise or have side effects'
        if isinstance(node, (ast.Raise, ast.Assert)):
            return 'the function can raise'
        if isinstance(node, (ast.Try, ast.With, ast.Import, ast.ImportFrom)):
            return 'try/with/import is not safe to clone'
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return 'a global assignment is not safe to clone'
        if isinstance(node, ast.Delete):
            return 'delete is not safe to clone'
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            return 'attribute assignment is not safe to clone'
        if isinstance(node, (ast.Await, ast.Yield, ast.YieldFrom)):
            return 'coroutine/generator code stays in CPython'
    return None


# Builtins that only read a list argument: passing a list parameter to one of these is not a
# mutation (`n = len(xs)` used to refuse every such function as "the list parameter is mutated").
# Trusted only while the module does not rebind the name (`_module_bindings`).
_READ_ONLY_BUILTINS = frozenset({'len', 'sum', 'min', 'max', 'sorted', 'any', 'all'})


def _module_bindings(tree):
    """Every name the module binds at top level (a def, a class, an assignment, an import): a
    builtin of that name is not the builtin."""
    names = set()
    for node in getattr(tree, 'body', ()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split('.')[0])
        else:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                    names.add(sub.id)
    return names


def _module_constants(tree):
    """{name: kind} for a module-level name bound exactly once, by `NAME = <int/float/str/bool
    literal>`, and never declared `global` anywhere: the typed emitter reads such a name as that
    constant, so its kind is the literal's."""
    counts = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            counts[node.id] = counts.get(node.id, 0) + 1
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                counts[name] = counts.get(name, 0) + 2
    out = {}
    for node in getattr(tree, 'body', ()):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Constant) \
                and counts.get(node.targets[0].id) == 1:
            v = node.value.value
            kind = ('bool' if isinstance(v, bool) else 'int' if isinstance(v, int) else
                    'float' if isinstance(v, float) else 'str' if isinstance(v, str) else None)
            if kind:
                out[node.targets[0].id] = kind
    return out


_INT64 = (-(1 << 63), (1 << 63) - 1)
# A recursive typed function checks its depth against this macro (pyfunc).  The hybrid turns it
# into a per-call thread-local bound derived from CPython's own remaining recursion budget.
_RECURSION_CAP = re.compile(r'(?m)^#define AIL_MAX_RECURSION_DEPTH (\d+)[ \t]*$')


def _guardable_constant(value):
    """A module constant the C entry can re-check by exact type and value (section 5.1)."""
    import math
    if isinstance(value, bool):
        return False                      # to_c refuses a bool module constant (whole slice)
    if isinstance(value, int):
        return _INT64[0] <= value <= _INT64[1]
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, str):
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            return False
        return True
    return False


def _module_constant_values(tree):
    """{name: value} for `_module_constants`."""
    kinds = _module_constants(tree)
    out = {}
    for node in getattr(tree, 'body', ()):
        if isinstance(node, ast.Assign) and len(node.targets) == 1                 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in kinds:
            out[node.targets[0].id] = node.value.value
    return out


def _bound_names(fn):
    """A function's own local names: parameters and every name it stores."""
    names = {a.arg for a in fn.args.args + fn.args.posonlyargs + fn.args.kwonlyargs}
    for extra in (fn.args.vararg, fn.args.kwarg):
        if extra is not None:
            names.add(extra.arg)
    for node in _own_nodes(fn):
        if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
            names.add(node.id)
    return names


def _link_natives(chosen, rejected, funcs, consts, values, csrcs=None, methods=None):
    """obs4: settle the call graph between selected natives and the guards each unit needs.

    A unit is the entry plus every native it reaches; `to_c` compiled them all into it.  Refused
    (with the callers that reach them): mutual recursion and more than one recursive function in
    a unit (the depth bound of section 5.2 needs one recursive chain), and a module constant whose
    value the entry cannot re-check.  Each remaining item gets `callees` (guarded functions, the
    entry itself when it recurses), `consts` (guarded constants), `nfuncs` (frames bound) and
    `recursive`."""
    def calls_of(name):
        fn = funcs[name]
        local = _bound_names(fn)
        return {n.func.id for n in _own_nodes(fn) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name) and n.func.id not in local
                and n.func.id in funcs}

    def consts_of(name):
        fn = funcs[name]
        local = _bound_names(fn)
        return {n.id for n in _own_nodes(fn) if isinstance(n, ast.Name)
                and isinstance(n.ctx, ast.Load) and n.id in consts and n.id not in local}

    while True:
        calls = {n: calls_of(n) for n in chosen}
        closure = {}
        for n in chosen:
            seen, todo = set(), list(calls[n])
            while todo:
                m = todo.pop()
                if m in seen:
                    continue
                seen.add(m)
                todo.extend(calls.get(m, ()))
            closure[n] = seen
        drop = {}
        for n in chosen:
            unit = closure[n] | {n}
            missing = sorted(m for m in closure[n] if m not in chosen)
            if missing:
                drop[n] = 'calls %s, which stays in CPython' % missing[0]
                continue
            if any(m != k and m in closure.get(k, ()) and k in closure.get(m, ())
                   for k in unit for m in unit):
                drop[n] = 'mutual recursion stays in CPython'
                continue
            if sum(1 for m in unit if m in calls.get(m, ())) > 1:
                drop[n] = 'more than one recursive function in one unit stays in CPython'
                continue
            if any(m in calls.get(m, ()) for m in unit) and csrcs is not None                     and not _RECURSION_CAP.search(csrcs.get(n, '')):
                drop[n] = 'recursion without a depth check in the typed clone'
                continue
            bad = sorted(c for m in unit for c in consts_of(m)
                         if not _guardable_constant(values.get(c)))
            if bad:
                drop[n] = 'module constant %s cannot be guarded, stays in CPython' % bad[0]
        if not drop:
            break
        for n, why in drop.items():
            del chosen[n]
            rejected[n] = why
    methods = methods or {}
    for n, item in chosen.items():
        unit = closure[n] | {n}
        recursive = any(m in calls[m] for m in unit)
        # A method's calls of other methods (itself included) are guarded through the class
        # (section 5.3), not as module globals: the synthetic names never exist at run time.
        item['callees'] = sorted(m for m in closure[n] if m not in methods)
        item['mcalls'] = sorted(m for m in closure[n] if m in methods)
        if n in methods:
            item['method'] = methods[n]
        item['consts'] = sorted({c for m in unit for c in consts_of(m)})
        item['const_values'] = {c: values[c] for c in item['consts']}
        item['nfuncs'] = len(unit)
        item['recursive'] = recursive
        if item['callees'] or recursive:
            item['trap'] = True
        # obs5: a zero divisor anywhere in the unit (a callee's or a self-called method's body
        # included) stops the clone; the trap pad turns that into a fallback.
        if any(chosen[m].get('vardiv') for m in unit if m in chosen):
            item['trap'] = True


# ---- exact CPython result types (obs3) ---------------------------------------------------------
#
# `pymix` kinds are hypotheses: `_merge` turns int+bool evidence into `int` and int+float into
# `float`, which is right for a C slot but not for the Python object a list element or a `bool`
# result must be.  The hybrid returns real CPython objects, so a list's element type and an
# `a and b` result are accepted only when this pass proves CPython's exact type: 'int' (never a
# bool), 'float', 'bool', 'str', 'list[int]', 'list[float]', 'list[str]', or None (unknown).
# Parameters are exact because the C entry checks them (`PyLong_CheckExact`, `PyFloat_CheckExact`,
# `PyBool_Check`, every list element).  Locals take the join of every assignment, solved
# optimistically ('top' = no evidence yet), so `acc = 0; acc += a[i]` is 'int' while
# `x = 0; x = x * 1.5` is None (CPython holds an int or a float there).

_TOP = 'top'
_NUM_KINDS = ('int', 'float', 'bool')
_STR_METHOD_RESULT = {
    'isdigit': 'bool', 'isalpha': 'bool', 'isalnum': 'bool', 'isspace': 'bool', 'isupper': 'bool',
    'islower': 'bool', 'istitle': 'bool', 'isdecimal': 'bool', 'isnumeric': 'bool',
    'isidentifier': 'bool', 'isprintable': 'bool', 'isascii': 'bool', 'startswith': 'bool',
    'endswith': 'bool', 'find': 'int', 'rfind': 'int', 'count': 'int', 'upper': 'str',
    'lower': 'str', 'casefold': 'str', 'strip': 'str', 'lstrip': 'str', 'rstrip': 'str',
    'capitalize': 'str', 'title': 'str', 'swapcase': 'str', 'replace': 'str',
    'removeprefix': 'str', 'removesuffix': 'str', 'join': 'str',
}


def _binop_kind(op, left, right):
    if _TOP in (left, right):
        other = right if left == _TOP else left
        if other == _TOP:
            return _TOP
        if other is None:
            return None
        left = right = other
    if left is None or right is None:
        return None
    if left in _NUM_KINDS and right in _NUM_KINDS:
        has_float = 'float' in (left, right)
        if isinstance(op, ast.Div):
            return 'float'
        if isinstance(op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)):
            return 'float' if has_float else 'int'
        if isinstance(op, (ast.LShift, ast.RShift)):
            return None if has_float else 'int'
        if isinstance(op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
            if has_float:
                return None
            return 'bool' if left == right == 'bool' else 'int'
        return None                       # `**` can make a float from ints; `@`
    if left == right == 'str' and isinstance(op, ast.Add):
        return 'str'
    return None


class _Kinds:
    """Exact kinds of one function's names (see the section comment above)."""

    def __init__(self, fn, params, shadowed=frozenset(), skip=frozenset(), consts=None,
                 calls=None, fields=None, selfname=None):
        self.shadowed = set(shadowed)
        self.consts = dict(consts or {})
        # obs4 methods: `self.<field>` kinds while guessing a class's field kinds (a hypothesis
        # the C entry checks; never used for a proof about a synthetic function's own body).
        self.fields = fields or {}
        self.selfname = selfname
        # obs4: {name: exact result kind} of the selected natives this body may call.
        self.calls = dict(calls or {})
        self.env = {}
        sources = {}
        for p, k in params:
            sources.setdefault(p, []).append(('kind', k))
        for node in _own_nodes(fn):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        sources.setdefault(target.id, []).append(('expr', node.value))
                    elif not isinstance(target, (ast.Subscript, ast.Attribute)):
                        for sub in ast.walk(target):
                            if isinstance(sub, ast.Name):
                                sources.setdefault(sub.id, []).append(('bad', None))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                sources.setdefault(node.target.id, []).append(
                    ('expr', node.value) if node.value is not None else ('bad', None))
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                sources.setdefault(node.target.id, []).append(('aug', node))
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                if isinstance(node.target, ast.Name) and isinstance(node, ast.For):
                    sources.setdefault(node.target.id, []).append(('iter', node.iter))
                else:
                    for sub in ast.walk(node.target):
                        if isinstance(sub, ast.Name):
                            sources.setdefault(sub.id, []).append(('bad', None))
            elif isinstance(node, ast.NamedExpr):
                sources.setdefault(node.target.id, []).append(('expr', node.value))
            elif isinstance(node, ast.comprehension):
                # A comprehension variable lives in its own scope; this flat map cannot tell
                # it apart from a local of the same name, so that name is simply unknown.
                for sub in ast.walk(node.target):
                    if isinstance(sub, ast.Name):
                        sources.setdefault(sub.id, []).append(('bad', None))
            elif isinstance(node, (ast.With, ast.AsyncWith, ast.ExceptHandler, ast.Import,
                                   ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Delete)):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                        sources.setdefault(sub.id, []).append(('bad', None))
                if isinstance(node, ast.ExceptHandler) and node.name:
                    sources.setdefault(node.name, []).append(('bad', None))
                if isinstance(node, (ast.Global, ast.Nonlocal)):
                    for name in node.names:
                        sources.setdefault(name, []).append(('bad', None))
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        sources.setdefault((alias.asname or alias.name).split('.')[0],
                                           []).append(('bad', None))
        for name in skip:
            sources.pop(name, None)
        self.local_names = set(sources)
        self.sources = sources
        self.extra = {}                   # names solved by the caller (a returned fresh list)
        self.solve()

    def solve(self, rounds=64):
        env = {name: _TOP for name in self.sources}
        env.update(self.extra)
        for _ in range(rounds):
            self.env = env
            new = dict(self.extra)
            for name, srcs in self.sources.items():
                known = []
                bad = False
                for tag, value in srcs:
                    if tag == 'kind':
                        k = value
                    elif tag == 'bad':
                        k = None
                    elif tag == 'expr':
                        k = self.kind(value)
                    elif tag == 'aug':
                        k = _binop_kind(value.op, env.get(value.target.id), self.kind(value.value))
                    else:
                        k = self.iter_kind(value)
                    if k is None:
                        bad = True
                        break
                    if k != _TOP:
                        known.append(k)
                if bad or (known and any(k != known[0] for k in known)):
                    new[name] = None
                else:
                    new[name] = known[0] if known else _TOP
            if new == env:
                break
            env = new
        self.env = {name: (None if k == _TOP else k) for name, k in env.items()}
        self.env.update(self.extra)

    def builtin(self, name):
        return name not in self.shadowed and name not in self.local_names

    def iter_kind(self, it):
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range' \
                and self.builtin('range') and not it.keywords:
            return 'int'
        k = self.kind(it)
        if k == _TOP:
            return _TOP
        if k == 'str':
            return 'str'
        if k in ('list[int]', 'list[float]', 'list[str]'):
            return k[5:-1]
        return None

    def kind(self, e):
        env = self.env
        if isinstance(e, ast.Constant):
            v = e.value
            if isinstance(v, bool):
                return 'bool'
            if isinstance(v, int):
                return 'int'
            if isinstance(v, float):
                return 'float'
            if isinstance(v, str):
                return 'str'
            return None
        if isinstance(e, ast.Name):
            if e.id in env:
                return env[e.id]
            return self.consts.get(e.id)
        if isinstance(e, ast.BinOp):
            return _binop_kind(e.op, self.kind(e.left), self.kind(e.right))
        if isinstance(e, ast.Attribute) and self.selfname is not None \
                and isinstance(e.value, ast.Name) and e.value.id == self.selfname:
            return self.fields.get(e.attr)
        if isinstance(e, ast.UnaryOp):
            if isinstance(e.op, ast.Not):
                return 'bool'
            k = self.kind(e.operand)
            if k == _TOP:
                return _TOP
            if isinstance(e.op, (ast.UAdd, ast.USub)):
                return {'int': 'int', 'bool': 'int', 'float': 'float'}.get(k)
            return 'int' if k in ('int', 'bool') else None
        if isinstance(e, ast.Compare):
            ok = ('int', 'float', 'bool', 'str', 'list[int]', 'list[float]', 'list[str]', _TOP)
            if all(self.kind(x) in ok for x in [e.left] + list(e.comparators)):
                return 'bool'
            return None
        if isinstance(e, (ast.BoolOp, ast.IfExp)):
            # `a and b` / `a or b` return one of the operands, never a converted bool.
            values = e.values if isinstance(e, ast.BoolOp) else [e.body, e.orelse]
            ks = [self.kind(v) for v in values]
            if None in ks:
                return None
            known = [k for k in ks if k != _TOP]
            if not known:
                return _TOP
            return known[0] if all(k == known[0] for k in known) else None
        if isinstance(e, ast.Subscript):
            b = self.kind(e.value)
            if b == _TOP:
                return _TOP
            if isinstance(e.slice, ast.Slice):
                return b if b in ('str', 'list[int]', 'list[float]', 'list[str]') else None
            if b == 'str':
                return 'str'
            if b in ('list[int]', 'list[float]', 'list[str]'):
                return b[5:-1]
            return None
        if isinstance(e, ast.Call):
            if e.keywords or any(isinstance(a, ast.Starred) for a in e.args):
                return None
            func, args = e.func, e.args
            if isinstance(func, ast.Attribute):
                if self.kind(func.value) == 'str':
                    return _STR_METHOD_RESULT.get(func.attr)
                return None
            if isinstance(func, ast.Name) and func.id in self.calls \
                    and func.id not in self.local_names:
                return self.calls[func.id]
            if not isinstance(func, ast.Name) or not self.builtin(func.id):
                return None
            name = func.id
            ks = [self.kind(a) for a in args]
            if name in ('len', 'ord') and len(args) == 1:
                return 'int'
            if name in ('int', 'float', 'str', 'bool') and len(args) <= 1:
                return name
            if name == 'chr' and len(args) == 1:
                return 'str'
            if name == 'round' and len(args) == 1:
                return 'int'
            if name == 'abs' and len(args) == 1:
                return {'int': 'int', 'bool': 'int', 'float': 'float', _TOP: _TOP}.get(ks[0])
            if name in ('min', 'max'):
                if len(args) == 1:
                    return {'list[int]': 'int', 'list[float]': 'float', 'list[str]': 'str',
                            _TOP: _TOP}.get(ks[0])
                if len(args) >= 2 and None not in ks:
                    known = [k for k in ks if k != _TOP]
                    if not known:
                        return _TOP
                    return known[0] if all(k == known[0] for k in known) else None
                return None
            if name == 'sum' and len(args) == 1:
                # sum([]) is the int 0, so only an int list has one result type.
                return {'list[int]': 'int', _TOP: _TOP}.get(ks[0])
            return None
        return None


def _parents(fn):
    out = {}
    for node in ast.walk(fn):
        for child in ast.iter_child_nodes(node):
            out[id(child)] = node
    return out


# ---- methods (obs4, OBSERVED_TYPES.md section 5.3) ----------------------------------------------
#
# A read-only method of a plain class becomes a synthetic top-level function: each `self.<field>`
# read is a parameter, each `self.<method>(...)` a call of that method's synthetic function with
# its fields passed through.  The existing selection, `to_c` and wrapper machinery handle it like
# any function; the C entry reads the fields from `self` after the type/MRO/instance guards.

_FIELD_PREFIX = '__ail_f_'
_KIND_ANN = {'int': 'int', 'float': 'float', 'str': 'str', 'bool': 'bool',
             'list[int]': 'list[int]', 'list[float]': 'list[float]'}


def _synthetic_name(cls, attr):
    return '__ail_m%d_%s_%s' % (len(cls), cls, attr)


def _ann_text_kind(node):
    if node is None:
        return None
    try:
        text = ast.unparse(node).replace(' ', '')
    except Exception:
        return None
    return _KIND_ANN.get(text)


def _simple_class(node):
    """A class the method guards can describe: no decorators, no keywords (so no metaclass), no
    bases but `object`, and a body of plain defs, a docstring or `pass` only."""
    if node.decorator_list or node.keywords:
        return False
    if any(not (isinstance(b, ast.Name) and b.id == 'object') for b in node.bases):
        return False
    for i, stmt in enumerate(node.body):
        if isinstance(stmt, ast.FunctionDef):
            continue
        if isinstance(stmt, ast.Pass):
            continue
        if i == 0 and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) \
                and isinstance(stmt.value.value, str):
            continue
        return False
    return True


def _self_name(fn):
    a = fn.args
    if a.posonlyargs or a.vararg or a.kwarg or a.kwonlyargs or a.defaults or not a.args:
        return None
    return a.args[0].arg


def _is_self_attr(node, selfname):
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
        and node.value.id == selfname


def _field_kinds(cls_node):
    """{field: kind} guessed from the class's own stores (a hypothesis: the C entry checks every
    value it reads, so a wrong guess costs fallbacks only)."""
    sources = {}
    for fn in cls_node.body:
        if not isinstance(fn, ast.FunctionDef) or not fn.args.args:
            continue
        selfname = fn.args.args[0].arg
        params = [(a.arg, _ann_text_kind(a.annotation)) for a in fn.args.args[1:]]
        params = [(p, k) for p, k in params if k is not None]
        for node in ast.walk(fn):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                for t in targets:
                    if _is_self_attr(t, selfname):
                        tag = 'aug' if isinstance(node, ast.AugAssign) else 'expr'
                        sources.setdefault(t.attr, []).append((tag, fn, params, node))
                    elif isinstance(t, ast.Subscript) and _is_self_attr(t.value, selfname):
                        tag = 'item_aug' if isinstance(node, ast.AugAssign) else 'item'
                        sources.setdefault(t.value.attr, []).append((tag, fn, params, node))
                    else:
                        for sub in ast.walk(t):
                            if _is_self_attr(sub, selfname) and isinstance(sub.ctx, ast.Store):
                                sources.setdefault(sub.attr, []).append(('bad', fn, params, node))
                del value
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == 'append' and _is_self_attr(node.func.value, selfname) \
                    and len(node.args) == 1 and not node.keywords:
                sources.setdefault(node.func.value.attr, []).append(('item', fn, params, node))
            elif _is_self_attr(node, selfname) and isinstance(node.ctx, ast.Del):
                sources.setdefault(node.attr, []).append(('bad', fn, params, node))
    env = {f: _TOP for f in sources}
    for _ in range(16):
        new = {}
        for f, srcs in sources.items():
            scalars, elems, is_list, bad = [], [], False, False
            for tag, fn, params, node in srcs:
                kinds = _Kinds(fn, params, fields=env, selfname=fn.args.args[0].arg)
                if tag == 'bad':
                    bad = True
                elif tag == 'expr':
                    v = node.value
                    if v is None:
                        bad = True
                    elif isinstance(v, ast.List):
                        is_list = True
                        elems.extend(kinds.kind(e) for e in v.elts)
                    elif isinstance(v, ast.BinOp) and isinstance(v.op, ast.Mult) and (
                            isinstance(v.left, ast.List) or isinstance(v.right, ast.List)):
                        lst = v.left if isinstance(v.left, ast.List) else v.right
                        is_list = True
                        elems.extend(kinds.kind(e) for e in lst.elts)
                    else:
                        scalars.append(kinds.kind(v))
                elif tag == 'aug':
                    scalars.append(_binop_kind(node.op, env.get(f), kinds.kind(node.value)))
                elif tag == 'item':
                    is_list = True
                    elems.append(kinds.kind(node.args[0] if isinstance(node, ast.Call)
                                            else node.value))
                elif tag == 'item_aug':
                    is_list = True
            if bad or (is_list and scalars):
                new[f] = None
                continue
            if is_list:
                known = {k for k in elems if k != _TOP}
                if None in known or len(known) > 1:
                    new[f] = None
                elif not known:
                    new[f] = _TOP
                else:
                    e = known.pop()
                    new[f] = 'list[%s]' % e if e in ('int', 'float') else None
                continue
            known = {k for k in scalars if k != _TOP}
            if None in known or len(known) > 1:
                new[f] = None
            else:
                new[f] = known.pop() if known else _TOP
        if new == env:
            break
        env = new
    return {f: k for f, k in env.items() if k in _KIND_ANN}


class _Desugar(ast.NodeTransformer):
    def __init__(self, cls, selfname, fields_of):
        self.cls = cls
        self.selfname = selfname
        self.fields_of = fields_of

    def visit_Call(self, node):
        func = node.func
        if _is_self_attr(func, self.selfname) and func.attr in self.fields_of:
            args = [ast.Name(id=_FIELD_PREFIX + f, ctx=ast.Load())
                    for f in self.fields_of[func.attr]]
            return ast.copy_location(ast.Call(
                func=ast.Name(id=_synthetic_name(self.cls, func.attr), ctx=ast.Load()),
                args=args + [self.visit(a) for a in node.args], keywords=[]), node)
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        if _is_self_attr(node, self.selfname):
            return ast.copy_location(ast.Name(id=_FIELD_PREFIX + node.attr, ctx=ast.Load()), node)
        return self.generic_visit(node)


def _method_synthetics(tree):
    """[(synthetic FunctionDef, meta)] for the read-only methods of simple top-level classes;
    meta = {'cls', 'attr', 'fields': [(field, kind)], 'nown', 'end'}; plus {qualname: reason}
    for every other method of a top-level class."""
    out, refusals = [], {}
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        defs = [fn for fn in cls.body if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))]
        methods = {fn.name: fn for fn in defs if isinstance(fn, ast.FunctionDef)}
        why_cls = None
        if not _simple_class(cls):
            why_cls = 'method of a class with decorators, bases, a metaclass or class attributes'
        elif len(methods) != len(defs):
            why_cls = 'method of a class that defines a name twice'
        if why_cls:
            for fn in defs:
                refusals['%s.%s' % (cls.name, fn.name)] = why_cls + ', stays in CPython'
            continue
        fkinds = _field_kinds(cls)
        own_fields, self_calls = {}, {}
        for name, fn in methods.items():
            selfname = _self_name(fn)
            qual = '%s.%s' % (cls.name, name)
            if fn.decorator_list or selfname is None or name.startswith('__'):
                refusals[qual] = ('a decorated, dunder or non-plain-signature method stays '
                                  'in CPython')
                continue
            if any(isinstance(n, ast.Name) and n.id.startswith('__ail_') for n in ast.walk(fn)):
                refusals[qual] = 'a name starting with __ail_ stays in CPython'
                continue
            parents = _parents(fn)
            fields, calls, ok = set(), set(), True
            for node in ast.walk(fn):
                if not (isinstance(node, ast.Name) and node.id == selfname):
                    continue
                if node is fn.args.args[0]:
                    continue
                parent = parents.get(id(node))
                if not isinstance(node.ctx, ast.Load) or not isinstance(parent, ast.Attribute) \
                        or not isinstance(parent.ctx, ast.Load) or parent.attr.startswith('__'):
                    ok = 'self is stored to or used other than by reading an attribute'
                    break
                holder = parents.get(id(parent))
                if isinstance(holder, ast.Call) and holder.func is parent:
                    if parent.attr not in methods or holder.keywords:
                        ok = 'calls self.%s, not a plain method of the class' % parent.attr
                        break
                    calls.add(parent.attr)
                elif parent.attr in methods or parent.attr not in fkinds:
                    ok = 'field self.%s has no scalar or int/float list kind' % parent.attr
                    break
                else:
                    fields.add(parent.attr)
            # `self` inside a nested def or lambda would be a closure: refused above only if
            # it is not an attribute read; refuse any nested scope that mentions it at all.
            for sub in ast.walk(fn):
                if sub is not fn and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                      ast.Lambda, ast.ClassDef)):
                    if any(isinstance(n, ast.Name) and n.id == selfname for n in ast.walk(sub)):
                        ok = 'a nested scope uses self'
            if ok is True:
                own_fields[name] = fields
                self_calls[name] = calls
            else:
                refusals[qual] = 'method: %s, stays in CPython' % ok
        cands = set(own_fields)
        while True:
            drop = {m for m in cands if not self_calls[m] <= cands}
            if not drop:
                break
            cands -= drop
            for m in drop:
                refusals['%s.%s' % (cls.name, m)] = ('method: calls a method that stays in '
                                                     'CPython, stays in CPython')
        fields_of = {}
        for m in cands:
            seen, todo, acc = set(), [m], set()
            while todo:
                k = todo.pop()
                if k in seen:
                    continue
                seen.add(k)
                acc |= own_fields[k]
                todo.extend(self_calls[k])
            fields_of[m] = sorted(acc)
        for m in sorted(cands):
            fn = methods[m]
            selfname = _self_name(fn)
            # The entry copies every list field (as for list parameters).  A body with no loop
            # and no method call cannot pay for that O(n) copy (`Frame.rows` = `len(self.key)`
            # measured 0.508 -> 0.517 on dataframe_group), so it stays in CPython.
            if any(fkinds[f] in _LIST for f in fields_of[m]) and not self_calls[m] and not any(
                    isinstance(n, (ast.For, ast.While, ast.comprehension)) for n in _own_nodes(fn)):
                refusals['%s.%s' % (cls.name, m)] = ('method: a loop-free body would copy a list '
                                                     'field on every call, stays in CPython')
                continue
            body = [_Desugar(cls.name, selfname, fields_of).visit(ast.fix_missing_locations(
                    copy.deepcopy(stmt))) for stmt in fn.body]
            args = [ast.arg(arg=_FIELD_PREFIX + f, annotation=ast.parse(fkinds[f], mode='eval').body)
                    for f in fields_of[m]]
            args += [copy.deepcopy(a) for a in fn.args.args[1:]]
            extra = {'type_params': []} if sys.version_info >= (3, 12) else {}
            syn = ast.FunctionDef(
                name=_synthetic_name(cls.name, m),
                args=ast.arguments(posonlyargs=[], args=args, vararg=None, kwonlyargs=[],
                                   kw_defaults=[], kwarg=None, defaults=[]),
                body=body, decorator_list=[], returns=copy.deepcopy(fn.returns), **extra)
            ast.fix_missing_locations(syn)
            out.append((syn, {'cls': cls.name, 'attr': m,
                              'fields': [(f, fkinds[f]) for f in fields_of[m]],
                              'nown': len(fn.args.args) - 1, 'end': cls.end_lineno}))
    return out, refusals


def _list_return_proof(fn, params, shadowed=frozenset(), consts=None, calls=None):
    """(kind, name) when `fn` returns a list it built itself whose elements are all CPython
    `int` (never bool) or all `float`; otherwise (None, reason).

    The returned list must be a fresh local: created by `[]`, a literal or `[c] * n`, then only
    appended to, indexed, stored into (`out[i] = e`, `out[i] += e`) or measured with `len`, and
    returned by every `return`.  Nothing else can hold a reference to it, so a new CPython list
    with the same elements (what the native entry hands back) cannot be told apart from the
    original object."""
    pk = dict(params)
    if not fn.body or not isinstance(fn.body[-1], ast.Return):
        return None, 'a path can fall off the end (returns None)'
    returns = [n for n in _own_nodes(fn) if isinstance(n, ast.Return)]
    if any(not isinstance(r.value, ast.Name) for r in returns):
        return None, 'a return is not a local list name'
    names = {r.value.id for r in returns}
    if len(names) != 1:
        return None, 'returns more than one name'
    var = names.pop()
    if var in pk:
        return None, 'returns a parameter'
    own = set(id(n) for n in _own_nodes(fn))
    parents = _parents(fn)
    creations, elements, aug_elements = [], [], []
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Name) and node.id == var):
            continue
        if id(node) not in own:
            return None, 'the list is used by a nested function'
        parent = parents.get(id(node))
        if isinstance(node.ctx, ast.Store):
            if isinstance(parent, ast.Assign) and len(parent.targets) == 1 \
                    and parent.targets[0] is node:
                creations.append(parent.value)
                continue
            return None, 'the list name is rebound in an unsupported way'
        if isinstance(node.ctx, ast.Del):
            return None, 'the list is deleted'
        if isinstance(parent, ast.Return):
            continue
        if isinstance(parent, ast.Attribute) and parent.attr == 'append':
            call = parents.get(id(parent))
            stmt = parents.get(id(call))
            if isinstance(call, ast.Call) and call.func is parent and len(call.args) == 1 \
                    and not call.keywords and isinstance(stmt, ast.Expr) \
                    and not isinstance(call.args[0], ast.Starred):
                elements.append(call.args[0])
                continue
            return None, 'an unsupported use of append'
        if isinstance(parent, ast.Subscript) and parent.value is node \
                and not isinstance(parent.slice, ast.Slice):
            holder = parents.get(id(parent))
            if isinstance(parent.ctx, ast.Load):
                continue
            if isinstance(parent.ctx, ast.Store):
                if isinstance(holder, ast.Assign) and parent in holder.targets:
                    elements.append(holder.value)
                    continue
                if isinstance(holder, ast.AugAssign) and holder.target is parent:
                    aug_elements.append(holder)
                    continue
            return None, 'an unsupported store into the list'
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) \
                and parent.func.id == 'len' and parent.args == [node] and not parent.keywords \
                and 'len' not in shadowed:
            continue
        return None, 'the list escapes or is used in an unsupported way'
    if not creations:
        return None, 'the list is not created here'
    for value in creations:
        if isinstance(value, ast.List):
            elements.extend(value.elts)
        elif isinstance(value, ast.BinOp) and isinstance(value.op, ast.Mult):
            lst, count = ((value.left, value.right) if isinstance(value.left, ast.List)
                          else (value.right, value.left))
            if not (isinstance(lst, ast.List) and len(lst.elts) == 1):
                return None, 'an unsupported list creation'
            elements.append(lst.elts[0])
            aug_elements.append(('count', count))
        else:
            return None, 'an unsupported list creation'
    if any(isinstance(e, ast.Starred) for e in elements):
        return None, 'a starred element'
    kinds = _Kinds(fn, params, shadowed, skip={var}, consts=consts, calls=calls)
    elem = None
    for _ in range(8):
        found = set()
        for e in elements:
            found.add(kinds.kind(e))
        for holder in aug_elements:
            if isinstance(holder, tuple):
                if kinds.kind(holder[1]) not in ('int', 'bool'):
                    found.add(None)
                continue
            found.add(_binop_kind(holder.op, elem or _TOP, kinds.kind(holder.value)))
        found.discard(_TOP)
        if len(found) != 1:
            return None, 'the element types are mixed or unknown'
        new = found.pop()
        if new not in ('int', 'float'):
            return None, 'the elements are %s' % (new or 'of unknown type')
        if new == elem:
            break
        elem = new
        kinds.extra = {var: 'list[%s]' % elem}
        kinds.solve()
    else:
        return None, 'the element type does not settle'
    return 'list[%s]' % elem, var


def _return_kinds(fn, params, shadowed=frozenset(), consts=None, calls=None):
    """The exact kind of every `return` value (None where unknown, 'none' for a bare return or
    falling off the end)."""
    kinds = _Kinds(fn, params, shadowed, consts=consts, calls=calls)
    out = []
    for node in _own_nodes(fn):
        if isinstance(node, ast.Return):
            out.append('none' if node.value is None else kinds.kind(node.value))
    if not fn.body or not isinstance(fn.body[-1], ast.Return):
        out.append('none')
    return out


def _list_param_mutated(fn, list_params, shadowed=frozenset(), natives=None):
    """A list argument is copied into the typed call, so a function that mutates it must stay in
    CPython (mutation would otherwise not be visible to the caller).  This also refuses passing a
    list parameter on to another user function, which may mutate it one step away."""
    if not list_params:
        return False
    # A local assigned straight from a list parameter aliases it in CPython, so mutating the
    # local is mutating the caller's list.  Follow that simple assignment closure before the
    # mutation scan; the typed clone copies the parameter into a C buffer, so such a write would
    # not be visible to the caller.
    aliases = set(list_params)
    nodes = list(_own_nodes(fn))
    changed = True
    while changed:
        changed = False
        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = getattr(node, 'value', None)
                if isinstance(value, ast.Name) and value.id in aliases:
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id not in aliases:
                            aliases.add(target.id)
                            changed = True
    for node in nodes:
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
    local_bound = {a.arg for a in fn.args.args} | {
        n.id for n in nodes if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load)}
    for node in nodes:
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _READ_ONLY_BUILTINS \
                    and node.func.id not in shadowed and node.func.id not in local_bound \
                    and not node.keywords \
                    and not any(isinstance(a, ast.Starred) for a in node.args):
                continue                  # len(xs), sum(xs), ...: a read, not a mutation
            if natives and isinstance(node.func, ast.Name) and node.func.id in natives \
                    and node.func.id not in local_bound:
                continue                  # obs4: a selected native never mutates a list param
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(arg, ast.Name) and arg.id in aliases:
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
sys.path.insert(0, %r)
try:
    import ail_cpython_hybrid as _hy
except Exception:
    _hy = None
# obs4: module constants (`NAME = <literal>`, bound once) are part of the typed slice, so `to_c`
# emits them as `static const` instead of refusing "read before it is assigned".  The hybrid's C
# entry re-checks every constant a unit reads in the module's globals before each call.
def _with_constants(old):
    def _defs_only(tree):
        text = old(tree)
        if _hy is None:
            return text
        try:
            values = _hy._module_constant_values(tree)
            lines = [name + ' = ' + repr(value) for name, value in values.items()
                     if _hy._guardable_constant(value)]
        except Exception:
            return text
        return '\n'.join(lines) + '\n' + text if lines else text
    return _defs_only
pyboxed2._mix_defs_only_source = _with_constants(pyboxed2._mix_defs_only_source)
pymix._defs_only_source = _with_constants(pymix._defs_only_source)
# obs3: the IR lowers `xs[i] op= v` as a checked get and then an UNCHECKED set at the same raw
# index.  The checked get accepts a negative index (it normalises it internally), so `out[-1] += 1`
# then writes before the buffer (heap corruption: found with a list result, reproduced in the
# default build too; reported for a core fix).  The hybrid's clones keep the set checked whenever
# the get was, so the set normalises the index itself; a proven-in-range subscript is unchanged.
try:
    import ir.lower as _ir_lower
    _old_aug_target = _ir_lower.Lowering.aug_target
    _old_builder_emit = _ir_lower._Builder.emit
    _aug_ck = []
    def _builder_emit(self, op, operands=(), types=(), attrs=None, regions=()):
        if _aug_ck and op == 'list.set' and attrs == {'mode': 'nck'}:
            attrs = {'mode': 'ck'}
        return _old_builder_emit(self, op, operands, types, attrs, regions)
    def _aug_target(self, s):
        t = s.target
        if isinstance(t, ast.Subscript) and not isinstance(t.slice, ast.Slice) \
                and self.index_mode(t) != 'nck':
            _aug_ck.append(1)
            try:
                return _old_aug_target(self, s)
            finally:
                _aug_ck.pop()
        return _old_aug_target(self, s)
    _ir_lower._Builder.emit = _builder_emit
    _ir_lower.Lowering.aug_target = _aug_target
except Exception:
    pass
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
# A local dict/list literal has a resolvable element kind even though pymix's base vocabulary
# stops at one container level.  Keep this inference in the hybrid's own analysis process so the
# default (non-hybrid) build path is byte-for-byte unchanged.
_old_expr_kind = pymix._expr_kind
_DICT_PREFIX = '__ail_hybrid_dict__'
# obs3: a return value whose exact type the hybrid proved (`_seed_returns` below).  Keyed by node
# id and checked by identity, so a later tree reusing an id is never mistaken for it.
_SEEDED = {}
def _hybrid_expr_kind(e, facts, rets):
    seeded = _SEEDED.get(id(e))
    if seeded is not None and seeded[0] is e:
        return seeded[1]
    if isinstance(e, ast.Dict):
        vk = None
        for v in e.values:
            k = _hybrid_expr_kind(v, facts, rets)
            if k is None:
                return None
            vk = k if vk is None else pymix._merge(vk, k)
            if vk is None:
                return None
        return None if vk is None else _DICT_PREFIX + vk
    if isinstance(e, ast.List):
        ek = None
        for el in e.elts:
            k = _hybrid_expr_kind(el, facts, rets)
            if k is None:
                return None
            ek = k if ek is None else pymix._merge(ek, k)
            if ek is None:
                return None
        if ek is None:
            return None
        if ek in (pymix.INT, pymix.FLOAT, pymix.STR):
            return pymix.LIST_OF.get(ek)
        if ek.startswith('list[') or ek.startswith(_DICT_PREFIX):
            return 'list[' + ek + ']'
        return None
    if isinstance(e, ast.Subscript) and not isinstance(e.slice, ast.Slice):
        base = _hybrid_expr_kind(e.value, facts, rets)
        if isinstance(base, str):
            if base.startswith(_DICT_PREFIX):
                return base[len(_DICT_PREFIX):]
            if base.startswith('list[') and base.endswith(']'):
                inner = base[5:-1]
                if inner.startswith(_DICT_PREFIX):
                    inner = inner[len(_DICT_PREFIX):]
                return inner
    return _old_expr_kind(e, facts, rets)
pymix._expr_kind = _hybrid_expr_kind
# A subscript's IndexError/KeyError is now reproduced by the wrapper re-running the original
# Python function, so it no longer needs pymix's exception-escape rejection in the hybrid.
_old_raise_site = pymix._raise_site_exc
def _raise_site_exc(node):
    if isinstance(node, ast.Subscript):
        return None
    # obs5: a zero divisor traps the same way (`_TRAP_DIES`), and `_select` admits a variable
    # divisor only with exact numeric operands, so the ZeroDivisionError is always CPython's own.
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
        return None
    return _old_raise_site(node)
pymix._raise_site_exc = _raise_site_exc
# obs3: pymix cannot type `out = []; out.append(x); return out` (an empty literal has no element
# kind, and an append is not evidence).  `_list_return_proof` proves the exact element type from
# the body; the result kind and the local are seeded, every return node is marked so pymix's own
# "one tag on every return" check agrees, and the fixed point runs again so callers see it.
# `_select` repeats the proof on the original source; this only lets the candidate exist.
_seeded_names = {}
_old_fixed_point = pymix._fixed_point
def _seed_returns(tree, fn_facts):
    shadowed = _hy._module_bindings(tree)
    consts = _hy._module_constants(tree)
    seeded = {}
    for name, f in fn_facts.items():
        if name == pymix.MODULE_SCOPE or f.ret is not None:
            continue
        if any(k is None for k in f.params.values()):
            continue
        kind, var = _hy._list_return_proof(f.node, list(f.params.items()), shadowed, consts)
        if kind is None:
            # obs3 task 2: a scalar return annotation (hand-written, or written by
            # `ail_observe annotate` from the observed kinds) seeds the result kind only when
            # every return value has exactly that CPython type, e.g. `return a and b` with two
            # bool operands.  The annotation itself is never trusted.
            want = _ann_kind(f.node.returns) if f.node.returns is not None else None
            if want not in (pymix.INT, pymix.FLOAT, pymix.BOOL, pymix.STR):
                continue
            kinds = _hy._return_kinds(f.node, list(f.params.items()), shadowed, consts)
            if not kinds or any(k != want for k in kinds):
                continue
            kind = want
            f.is_bool_ret = want == pymix.BOOL
        else:
            f.locals[var] = kind
        f.ret = kind
        for node in ast.walk(f.node):
            if isinstance(node, ast.Return) and node.value is not None:
                _SEEDED[id(node.value)] = (node.value, kind)
        seeded[name] = kind
    return seeded
def _fixed_point(tree):
    fn_facts = _old_fixed_point(tree)
    if _hy is None:
        return fn_facts
    try:
        seeded = _seed_returns(tree, fn_facts)
        if seeded:
            owner = pymix._scope_owner(fn_facts)
            for _ in range(pymix.MAX_ROUNDS):
                if not pymix._one_pass(fn_facts, pymix._collect_calls(tree, fn_facts, owner)):
                    break
            _seeded_names.update(seeded)
    except Exception:
        pass
    return fn_facts
pymix._fixed_point = _fixed_point
# A candidate the base mixed mode does not wire -- a list result, or a `list[float]` parameter
# `to_c` passes as `ail_flist` -- gets its clone here, for the hybrid only: it is captured beside
# the base units and never added to the analysis build's own boxed program (whose call sites do
# not know these ABIs).  The hybrid's `_unit_abi` reads the prototype and its wrapper calls it.
_extra_units = []
_old_setup_mix = pyboxed2.Compiler._setup_mix
def _extra_mix_units(self, source, tree):
    if pymix is None or os.environ.get('AIL_NO_MIX') or not self.allow_mix or _hy is None:
        return
    import walkmemo, bigcap
    report = walkmemo.mix_report(pymix, source)
    defs_src = pyboxed2._mix_defs_only_source(tree)
    big_hard = bigcap.marked(tree, local=False)
    big_local = bigcap.marked(tree)
    for name, cand in sorted(report.candidates.items()):
        if name in self.mix_typed or name in big_hard:
            continue
        facts = getattr(report, 'function_ir', {}).get(name)
        if facts is None or not facts.matches(source, name):
            continue
        cand = facts.signature()
        params = list(cand['params'].items())
        ret = cand['ret']
        if ret not in ('int', 'bool', 'float', 'str', 'list[int]', 'list[float]'):
            continue
        if not (ret in ('list[int]', 'list[float]') or any(k == 'list[float]' for _, k in params)):
            continue
        if ret in ('int', 'bool') and name in big_local:
            continue
        if any(k not in ('int', 'bool', 'float', 'str', 'list[int]', 'list[float]')
               for _, k in params):
            continue
        info = self.functions.get(name)
        if info is None or info.get('vararg') or info.get('kwarg') or info.get('kwonly'):
            continue
        mangled = pyfunc._mangle_csym(name) + '__typed'
        info2 = {'_checked_arrays': True, '_mixed_clone': True}
        try:
            csrc = pyfunc.to_c(defs_src, entry=name, sig=pymix._scalar_sig(cand['params']),
                               name=mangled, info=info2)
        except Exception:
            continue
        if info2.get('io'):
            continue
        csrc = re.sub(r'__attribute__\(\(always_inline\)\) static inline\r?\n'
                      r'(?=\S[^\n]*\b' + re.escape(mangled) + r'\s*\()', '', csrc)
        if _hy._unit_abi(csrc, mangled, params, ret) is None:
            continue
        csrc = pyboxed2._mix_drain_before_exit(csrc)
        if csrc is None:
            continue
        _extra_units.append([mangled, name, '/* AIL_MIXED_TYPED: ' + name + ' */\n' + csrc])
def _setup_mix(self, source, tree):
    _old_setup_mix(self, source, tree)
    try:
        _extra_mix_units(self, source, tree)
    except Exception:
        pass
pyboxed2.Compiler._setup_mix = _setup_mix
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
def _pymix_rejected():
    analysis = _last.get('analysis')
    if analysis is None:
        return {}
    try:
        return {str(name): [str(part) for part in why]
                for name, why in (analysis.rejected or {}).items()}
    except Exception:
        return {}
def _dump(report):
    try:
        data = {'mix_units': [list(u) for u in (report.get('mix_units') or [])] + _extra_units,
                'seeded': dict(_seeded_names),
                'typed_inline': list(report.get('typed_inline') or []),
                'facts': _facts(), 'pymix_rejected': _pymix_rejected(),
                'note': str(report.get('note') or '')}
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
""" % (str(_PKG), str(_HERE)), encoding='utf-8')
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
                'import os, pyboxed2\n'
                'pyboxed2.build(open(os.environ["AIL_HYBRID_SRC"], encoding="utf-8").read(), {}, allow_mix=True)\n',
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
              'pymix_rejected': data.get('pymix_rejected') or {},
              'seeded': data.get('seeded') or {},
              'note': data.get('note') or ''}
    return report, facts

def _select(src, tree, report, facts, methods=None):
    """The units worth wrapping, with the safety filters the design names."""
    import bigcap
    import pymix
    import pyboxed2
    import unified

    funcs = _top_level_functions(tree)
    big_hard = bigcap.marked(tree, local=False)
    big_local = bigcap.marked(tree)
    id_reach, id_any = pyboxed2._mix_identity_unsafe(tree)
    shadowed = _module_bindings(tree)
    consts = _module_constants(tree)
    seeded = report.get('seeded') or {}
    chosen = {}
    rejected = {}
    dup_defs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and sum(1 for m in tree.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                               ast.ClassDef))
                        and m.name == n.name) > 1}
    units = [u for u in report.get('mix_units') or []
             if u[1] in funcs and facts.get(u[1]) is not None]

    def consider(mangled, pyname, csrc, natives):
        info = facts.get(pyname)
        params = [(p, k) for p, k in info.get('params') or []]
        ret = info.get('ret')
        if pyname in dup_defs:
            return None, 'the module defines this name more than once'
        # obs4: the natives this body may call, itself included (self-recursion is assumed
        # optimistically: if the body is safe given that its own calls are, it is safe).
        natives = dict(natives)
        natives[pyname] = {'params': params, 'ret': ret}
        calls = {n: sig['ret'] for n, sig in natives.items()}
        kinds = _Kinds(funcs[pyname], params, shadowed, consts=consts, calls=calls)
        fresh = ()
        if ret in _LIST:
            # obs3: a returned list becomes a new CPython list of exact ints or floats; the
            # body must prove that element type itself (pymix's own kind may merge int/bool).
            kind, why = _list_return_proof(funcs[pyname], params, shadowed, consts, calls)
            if kind != ret:
                return None, 'list result: %s' % (why if kind is None else
                                                        'elements are %s, not %s' % (kind, ret))
            fresh = (why,)
        elif ret not in _SCALAR:
            return None, 'result kind %s stays in CPython' % ret
        elif pyname in seeded or any(isinstance(n, ast.Return) and isinstance(n.value, ast.BoolOp)
                                     for n in _own_nodes(funcs[pyname])):
            # obs3 task 2: `a and b` returns an operand, not a bool; the result kind (seeded
            # from an annotation, or pymix's own) must be every return value's exact type.
            rkinds = _return_kinds(funcs[pyname], params, shadowed, consts, calls)
            if not rkinds or any(k != ret for k in rkinds):
                return None, 'a return value is not always %s (%s)' % (
                    ret, ', '.join(sorted(set(str(k) for k in rkinds))))
        abi = _unit_abi(csrc, mangled, params, ret)
        if abi is None:
            return None, "the typed clone's C signature is not one the hybrid calls"
        if pyname in big_hard:
            return None, 'needs an int beyond int64'
        if pyname in big_local and ret not in ('int', 'bool'):
            return None, 'may overflow but does not return an int'
        if ret in ('int', 'bool') and pyname in big_local \
                and ('%s__mix_overflow' % mangled) not in csrc:
            return None, 'may overflow and has no overflow signal'
        if id_any and (pyname in id_reach or any(k == 'float' for _, k in params) or ret == 'float'):
            return None, 'the program compares numbers with `is`'
        bad = [k for _, k in params if k not in _SCALAR and k not in _LIST]
        if bad:
            return None, 'parameter kind %s stays in CPython' % bad[0]
        unsafe = _unsafe_body(funcs[pyname], params, ret, fresh, natives, kinds)
        if unsafe:
            return None, unsafe
        list_params = {p for p, k in params if k in _LIST}
        if _list_param_mutated(funcs[pyname], list_params, shadowed, natives):
            return None, 'the list parameter is mutated'
        indexes = any(isinstance(n, ast.Subscript) and not isinstance(n.slice, ast.Slice)
                      for n in _own_nodes(funcs[pyname]))
        mix_ovf = ('int %s__mix_overflow = 0;' % mangled) in csrc
        return {
            'name': pyname, 'mangled': mangled, 'params': params,
            'ret': ret, 'is_bool_ret': bool(info.get('is_bool_ret')),
            'indexes': indexes, 'abi': abi, 'mix_ovf': mix_ovf,
            'loops': any(isinstance(n, (ast.For, ast.While, ast.comprehension))
                         for n in _own_nodes(funcs[pyname])),
            # The trap landing pad turns an index/key stop, an uncaught AIL exception and an
            # int64 overflow stop into "run the original in CPython".  An int result with the
            # mixed-mode overflow signal already handles its overflow stops.
            'vardiv': _has_variable_division(funcs[pyname]),
            'trap': bool(indexes or ret in _LIST or _overflow_stop_reachable(csrc, mangled)
                         or _has_variable_division(funcs[pyname])),
        }, None

    # obs4: a body that calls other natives is selectable only once they are, so selection runs
    # to a fixed point.  A refusal that names a callee may be lifted in a later round.
    while True:
        natives = {n: {'params': it['params'], 'ret': it['ret']} for n, it in chosen.items()}
        grew = False
        for mangled, pyname, csrc in units:
            if pyname in chosen:
                continue
            item, why = consider(mangled, pyname, csrc, natives)
            if item is None:
                rejected[pyname] = why
            else:
                rejected.pop(pyname, None)
                chosen[pyname] = item
                grew = True
                natives[pyname] = {'params': item['params'], 'ret': item['ret']}
        if not grew:
            break
    _link_natives(chosen, rejected, funcs, consts, _module_constant_values(tree),
                  {u[1]: u[2] for u in units}, methods or {})
    # wedge1: a function refused before it reaches _select (pymix or the emitter) used to leave
    # no trace, so most refusals were silent.  Name every remaining top-level function too.
    pymix_rejected = report.get('pymix_rejected') or {}
    for pyname in sorted(funcs):
        if pyname in chosen or pyname in rejected:
            continue
        info = facts.get(pyname)
        why = pymix_rejected.get(pyname)
        if info is None:
            if why:
                detail = ': %s' % why[1] if len(why) > 1 and why[1] else ''
                rejected[pyname] = '%s%s stays in CPython' % (why[0], detail)
            else:
                rejected[pyname] = 'not a typed candidate, stays in CPython'
        else:
            rejected[pyname] = ('the typed clone is not wired to the hybrid ABI, stays in CPython')
    return chosen, rejected


_TRAP_DIES = re.compile(
    r'ail_die\("(?:list index out of range|list assignment index out of range|'
    r'pop index out of range|pop from empty list|key error|string index out of range|'
    r'bytes index out of range|grid row index out of range|grid column index out of range|'
    r'maximum recursion depth exceeded|MemoryError|OverflowError: integer overflow[^"\\]*|'
    # obs5: a zero divisor (selected only with exact numeric operands, `_variable_division_ok`)
    r'integer division or modulo by zero|integer modulo by zero|division by zero|'
    r'float division by zero|float modulo|float divmod\(\))"\)')
# A checked int64 operation (`ck_mul`, `ck_add`, ...) stops the process with this message.  In a
# hybrid unit that would kill the CPython process (obs3: found for list results; a float or str
# result with int arithmetic inside had the same hole), so the trap pad turns it into a fallback.
_OVERFLOW_DIE = re.compile(r'ail_die\("(?:OverflowError: integer overflow|MemoryError")')
_C_IDENT = re.compile(r'[A-Za-z_]\w*')


def _c_definitions(csrc):
    """{name: body text} for the unit's top-level C functions and `#define` macros, plus the text
    outside all of them.  A small scanner (strings, chars and comments skipped for brace counting);
    enough for the emitter's own regular output."""
    defs = {}
    outside = []
    i, n = 0, len(csrc)
    head = re.compile(r'(?m)^(?:#define[ \t]+([A-Za-z_]\w*)|[A-Za-z_][^;{}()#\n]*?\b([A-Za-z_]\w*)'
                      r'\s*\([^;{}]*\)\s*\{)')
    while i < n:
        m = head.search(csrc, i)
        if m is None:
            outside.append(csrc[i:])
            break
        outside.append(csrc[i:m.start()])
        if m.group(1):                                  # a macro, with its continuation lines
            j = m.end()
            while True:
                e = csrc.find('\n', j)
                if e < 0:
                    e = n
                    break
                if csrc[e - 1:e] != '\\':
                    break
                j = e + 1
            defs.setdefault(m.group(1), []).append(csrc[m.start():e])
            i = e
            continue
        depth, j = 1, m.end()
        while j < n and depth:
            c = csrc[j]
            if c in '"\'':
                q = c
                j += 1
                while j < n and csrc[j] != q:
                    j += 2 if csrc[j] == '\\' else 1
            elif csrc.startswith('/*', j):
                e = csrc.find('*/', j + 2)
                j = n if e < 0 else e + 1
            elif csrc.startswith('//', j):
                e = csrc.find('\n', j)
                j = n if e < 0 else e
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
            j += 1
        defs.setdefault(m.group(2), []).append(csrc[m.start():j])
        i = j
    return {k: '\n'.join(v) for k, v in defs.items()}, ''.join(outside)


def _overflow_stop_reachable(csrc, entry):
    """Whether the unit's entry can reach an int64-overflow or MemoryError stop.

    Every typed unit carries the whole runtime prelude, whose checked helpers (`ck_mul`, ...) stop
    the process on overflow; most entries never call them.  The trap pad (a `setjmp` per call) is
    only needed when a stop is reachable: names are tainted by containing a stop or by mentioning
    a tainted name, to a fixed point.  A stop outside every recognised definition counts as
    reachable."""
    if not _OVERFLOW_DIE.search(csrc):
        return False
    defs, outside = _c_definitions(csrc)
    if _OVERFLOW_DIE.search(outside):
        return True
    mentions = {name: set(_C_IDENT.findall(body)) - {name} for name, body in defs.items()}
    tainted = {name for name, body in defs.items() if _OVERFLOW_DIE.search(body)}
    changed = True
    while changed:
        changed = False
        for name, used in mentions.items():
            if name not in tainted and used & tainted:
                tainted.add(name)
                changed = True
    return entry in tainted


def _unit_abi(csrc, mangled, params, ret):
    """{param: 'scalar' | 'arr' | 'flist'} read from the clone's own C prototype, or None when the
    prototype is not one the wrapper knows how to call.  A `list[float]` parameter comes either as
    `const double *v_x, int64_t v_x_len` or, when `to_c` settles it as a float list, as the
    `ail_flist v_x` struct by value (obs1: "list[float] ABI defect", 2.8% of corpus time)."""
    m = re.search(r'^([A-Za-z_][\w ]*\*?\s*\b' + re.escape(mangled) + r'\s*\([^\n{;]*\))\s*\{',
                  csrc, re.MULTILINE)
    if m is None:
        return None
    sig = m.group(1)
    name_at = re.search(r'\b' + re.escape(mangled) + r'\s*\(', sig).start()
    rtype = re.sub(r'^(?:(?:static|inline|extern)\s+)+', '', sig[:name_at].strip())
    if rtype != ('double' if ret == 'float' else 'int64_t'):
        return None
    inside = sig[sig.index('(') + 1:sig.rindex(')')].strip()
    parts = [x.strip() for x in inside.split(',')] if inside and inside != 'void' else []
    abi = {}
    idx = 0
    for p, kind in params:
        cn = 'v_' + p
        if kind in ('int', 'bool'):
            options = ((['int64_t ' + cn], 'scalar'),)
        elif kind == 'float':
            options = ((['double ' + cn], 'scalar'),)
        elif kind == 'str':
            options = ((['ail_str ' + cn], 'scalar'),)
        elif kind == 'list[int]':
            options = ((['const int64_t *' + cn, 'int64_t %s_len' % cn], 'arr'),)
        elif kind == 'list[float]':
            options = ((['const double *' + cn, 'int64_t %s_len' % cn], 'arr'),
                       (['ail_flist ' + cn], 'flist'))
        else:
            return None
        for want, tag in options:
            if parts[idx:idx + len(want)] == want:
                abi[p] = tag
                idx += len(want)
                break
        else:
            return None
    tail = {'str': ['uint8_t *_out', 'int64_t _cap'],
            'list[int]': ['int64_t *_out', 'int64_t _cap'],
            'list[float]': ['double *_out', 'int64_t _cap']}.get(ret, [])
    if parts[idx:idx + len(tail)] != tail:
        return None
    idx += len(tail)
    return abi if idx == len(parts) else None


def _trap_patch(csrc, mangled):
    """Turn a clone's index/key runtime stops into a per-call fallback.

    The mixed-mode overflow mechanism already has a `setjmp` landing pad for an int result; this
    adds an independent one (its own flag and jump buffer) for every result kind, so an
    out-of-range list index or a missing dict key abandons the clone and the Python wrapper runs
    the original function.  CPython then supplies the exact IndexError/KeyError, message and
    caller-visible `try/except` behaviour.  Only the unit's own text is changed; no global build
    path is touched.  Returns the patched source, or the original when no prototype is found.
    """
    marker = '#include <stdint.h>\n'
    if marker not in csrc:
        return csrc
    base = mangled + '__hybrid'
    flag, jmp = base + '_trap', base + '_jmp'
    save, savep, hit, call = base + '_save', base + '_savep', base + '_hit', base + '_call'
    match = re.search(r'^([A-Za-z_][\w ]*\*?\s*\b' + re.escape(mangled) +
                      r'\s*\([^\n{;]*\))\s*\{', csrc, re.MULTILINE)
    if match is None:
        return csrc
    proto = match.group(1)
    name_at = re.search(r'\b' + re.escape(mangled) + r'\s*\(', proto).start()
    rtype = re.sub(r'^(?:(?:static|inline|extern)\s+)+', '', proto[:name_at].strip())
    inside = proto[proto.index('(') + 1:proto.rindex(')')]
    args = []
    for arg in inside.split(','):
        arg = arg.strip()
        if arg:
            args.append(re.split(r'[\s*]+', arg)[-1])

    state = {}
    for name in ('ail_depth', 'ail_cleanup_top', 'ail_exc_top'):
        state[name] = bool(re.search(r'^AIL_LINK_STATE\([^;\n]*\b' + name + r'\b', csrc, re.M))
    fields, inits, restores = [], [], []
    if state['ail_depth']:
        fields.append('int64_t depth;')
        inits.append('ail_depth')
        restores.append('        ail_depth = s->depth;')
    if state['ail_cleanup_top']:
        fields.append('ail_cleanup_frame *cleanup;')
        inits.append('ail_cleanup_top')
        restores.extend((
            '        while (ail_cleanup_top && ail_cleanup_top != s->cleanup) {',
            '            ail_cleanup_frame *f = ail_cleanup_top;',
            '            ail_cleanup_top = f->previous;',
            '            f->release(f->resources);',
            '        }',
            '        ail_cleanup_top = s->cleanup;'))
    if state['ail_exc_top']:
        fields.append('int exc_top;')
        inits.append('ail_exc_top')
        restores.append('        ail_exc_top = s->exc_top;')

    # The flag has external linkage: the wrapper (another translation unit of the same `.so`)
    # reads it through `extern __thread int`.  A `static` here left that reference undefined, so
    # every indexing unit's extension failed to import (obs1).  `_verify_import` now catches that.
    decl = ('\n#include <setjmp.h>\n'
            '__thread int %s = 0;\n'
            'static __thread jmp_buf %s;\n'
            'static inline void %s(void);\n' % (flag, jmp, hit))
    if fields:
        helper = ('\ntypedef struct { %s } %s;\n'
                  'static __thread %s *%s;\n'
                  'static inline void %s(void) {\n'
                  '    %s *s = %s;\n'
                  '    if (s) {\n'
                  '%s\n'
                  '    }\n'
                  '    %s = 1;\n'
                  '    longjmp(%s, 1);\n'
                  '}\n' % (' '.join(fields), save, save, savep, hit, save, savep,
                            '\n'.join(restores), flag, jmp))
    else:
        helper = ('\nstatic inline void %s(void) { %s = 1; longjmp(%s, 1); }\n'
                  % (hit, flag, jmp))
    body = [proto.replace(mangled, call, 1) + ' {\n', '    %s = 0;\n' % flag]
    if fields:
        body.extend((
            '    %s saved = {%s};\n' % (save, ', '.join(inits)),
            '    %s *previous = %s;\n' % (save, savep),
            '    %s = &saved;\n' % savep,
            '    if (setjmp(%s) != 0) { %s = previous; return 0; }\n' % (jmp, savep)))
    else:
        body.append('    if (setjmp(%s) != 0) return 0;\n' % jmp)
    body.append('    %s result = %s(%s);\n' % (rtype, mangled, ', '.join(args)))
    if fields:
        body.append('    %s = previous;\n' % savep)
    body.extend(('    return result;\n', '}\n'))
    csrc = _TRAP_DIES.sub(hit + '()', csrc)
    # Some runtime helpers raise instead of dying (`ail_olist_index` -> `ail_raise_named(
    # AIL_EXC_INDEX)` for `a[n][m]`).  A hybrid unit never runs under an AIL `try` (the selection
    # refuses `try`), so such a raise is always uncaught and would print a name and `_Exit(1)` the
    # whole CPython process.  Turn the uncaught path into the same per-call fallback: CPython
    # re-runs the original and raises the exact exception.  (Found once obs2 made the units load.)
    uncaught = 'static void ail_exception_uncaught(ail_exception *value) {\n'
    if uncaught in csrc:
        csrc = csrc.replace(uncaught, uncaught +
                            '    ail_exception_store(&ail_exc_value, NULL, 1);\n'
                            '    ail_exc_code = 0;\n'
                            '    %s();\n' % hit, 1)
    csrc = csrc.replace(marker, marker + decl, 1)
    return csrc + helper + ''.join(body)


def _c_proto(item, symbol=None):
    args = []
    abi = item.get('abi') or {}
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
        elif kind == 'list[float]' and abi.get(p) == 'flist':
            args.append('ail_flist ' + cn)
        elif kind == 'list[float]':
            args.extend(['const double *' + cn, 'int64_t ' + cn + '_len'])
    if item['ret'] == 'str':
        args.extend(['uint8_t *_out', 'int64_t _cap'])
    elif item['ret'] == 'list[int]':
        args.extend(['int64_t *_out', 'int64_t _cap'])
    elif item['ret'] == 'list[float]':
        args.extend(['double *_out', 'int64_t _cap'])
    rtype = 'double' if item['ret'] == 'float' else 'int64_t'
    return '%s %s(%s)' % (rtype, symbol or item['mangled'], ', '.join(args))


_VECTORCALL_HELPERS = r'''
#if PY_VERSION_HEX >= 0x030C0000
/* obs2: the native entry is the original function object itself.  `_ail_install` sets its
   vectorcall (PyFunction_SetVectorcall, the CPython 3.12 hook for JITs) to a per-unit C entry
   that runs the scalar/list guards in C and calls the native code; on any guard failure, keyword
   arguments, a wrong argument count, an int64 overflow or a trap it calls the unaltered
   `_PyFunction_Vectorcall`, i.e. the original Python code with the very same arguments.  The
   function object, its code, defaults, annotations and identity stay CPython's own.  A changed
   `__code__` is not one of the codes recorded at install time, so it runs in CPython too. */
#define AIL_CODES 4
static int ail_known_code(PyObject *const *slots, PyObject *code) {
    for (int i = 0; i < AIL_CODES; i++) if (slots[i] == code) return 1;
    return 0;
}
/* Fewer positional arguments than parameters: take the rest from the function's current
   `__defaults__`, as CPython would.  Returns a new reference to the defaults tuple (kept alive
   while the native call may run without the GIL), or NULL when the call must run in CPython. */
static PyObject *ail_fill_defaults(PyObject *func, PyObject *const *args, Py_ssize_t nargs,
                                   Py_ssize_t n, PyObject **o) {
    PyObject *d = PyFunction_GET_DEFAULTS(func);
    Py_ssize_t nd = d ? PyTuple_GET_SIZE(d) : 0;
    if (nargs > n || nargs < n - nd) return NULL;
    for (Py_ssize_t i = 0; i < nargs; i++) o[i] = args[i];
    for (Py_ssize_t i = nargs; i < n; i++) o[i] = PyTuple_GET_ITEM(d, nd - (n - i));
    Py_INCREF(d);
    return d;
}
#endif
'''


def _guarded(item):
    """obs4: the entry depends on module globals (constants, callees) or on CPython's recursion
    budget; only the 3.12+ vectorcall entry can check those, the Python wrapper path falls back."""
    return bool(item.get('consts') or item.get('callees') or item.get('rlimit')
                or item.get('method'))


def _c_string(text):
    data = text.encode('utf-8')
    return ('"%s"' % '""'.join('\\x%02x' % b for b in data)) if data else '""', len(data)


def _guard_names(items):
    names = {}
    for item in items:
        for c in item.get('consts') or ():
            names[c] = ('const', item['const_values'][c])
        for g in item.get('callees') or ():
            names[g] = ('func', None)
    return sorted(names.items())


def _guard_source(items):
    """The guarded-globals table (section 5.1/5.2): names, expected values, a dict watcher on the
    functions' globals that clears a name's "verified" flag when it is stored or deleted, and the
    verification itself.  3.12+ only, like the vectorcall entries that use it."""
    names = _guard_names(items)
    if not names:
        return []
    kinds = []
    for _n, (tag, value) in names:
        if tag == 'func':
            kinds.append(0)
        elif isinstance(value, bool):
            kinds.append(3)
        elif isinstance(value, int):
            kinds.append(1)
        elif isinstance(value, float):
            kinds.append(2)
        else:
            kinds.append(4)
    return [
        '#if PY_VERSION_HEX >= 0x030C0000',
        '#define AIL_NG %d' % len(names),
        'static const char *const ail_gname_s[AIL_NG] = {%s};'
        % ', '.join('"%s"' % n for n, _v in names),
        '/* 0 function (a native def), 1 int, 2 float, 3 bool, 4 str */',
        'static const int ail_gkind[AIL_NG] = {%s};' % ', '.join(str(k) for k in kinds),
        'static PyObject *ail_gname[AIL_NG], *ail_gval[AIL_NG], *ail_gfunc[AIL_NG];',
        'static vectorcallfunc ail_gentry[AIL_NG];',
        'static PyObject **ail_gcodes[AIL_NG];',
        'static char ail_gok[AIL_NG];',
        '/* The watched globals (borrowed; forgotten when the watcher reports its deallocation). */',
        'static PyObject *ail_gdict;',
        'static int ail_gwid = -1, ail_gwatched;',
        'static int ail_gcb(PyDict_WatchEvent ev, PyObject *d, PyObject *key, PyObject *nv) {',
        '    (void)nv;',
        '    if (d != ail_gdict) return 0;',
        '    if (ev == PyDict_EVENT_DEALLOCATED) { ail_gdict = NULL; ail_gwatched = 0; }',
        '    if (key == NULL || !PyUnicode_CheckExact(key)) { memset(ail_gok, 0, sizeof ail_gok); return 0; }',
        '    for (int i = 0; i < AIL_NG; i++)',
        '        if (ail_gok[i] && (key == ail_gname[i] || PyUnicode_Compare(key, ail_gname[i]) == 0))',
        '            ail_gok[i] = 0;',
        '    return 0;',
        '}',
        '/* The first globals seen are watched; any other globals dict is verified on every call. */',
        'static void ail_gadopt(PyObject *g) {',
        '    ail_gdict = g; ail_gwatched = 0; memset(ail_gok, 0, sizeof ail_gok);',
        '    if (ail_gwid == -1) { ail_gwid = PyDict_AddWatcher(ail_gcb); if (ail_gwid < 0) { PyErr_Clear(); ail_gwid = -2; } }',
        '    if (ail_gwid >= 0) { if (PyDict_Watch(ail_gwid, g) == 0) ail_gwatched = 1; else PyErr_Clear(); }',
        '}',
        '/* Is globals[name i] what the unit was compiled against?  A constant: exact type and value.',
        '   A callee: a function of these globals running this module\'s native entry for that def',
        '   (its code is then checked on every call by the caller). */',
        'static int ail_gverify(int i, PyObject *g, PyObject **fout) {',
        '    PyObject *v = PyDict_GetItemWithError(g, ail_gname[i]);',
        '    if (!v) { PyErr_Clear(); return 0; }',
        '    switch (ail_gkind[i]) {',
        '    case 0:',
        '        if (!PyFunction_Check(v) || ((PyFunctionObject *)v)->vectorcall != ail_gentry[i]',
        '                || PyFunction_GET_GLOBALS(v) != g) return 0;',
        '        *fout = v;',
        '        return 1;',
        '    case 1: {',
        '        if (!PyLong_CheckExact(v)) return 0;',
        '        int r = PyObject_RichCompareBool(v, ail_gval[i], Py_EQ);',
        '        if (r < 0) { PyErr_Clear(); return 0; }',
        '        return r;',
        '    }',
        '    case 2: {',
        '        if (!PyFloat_CheckExact(v)) return 0;',
        '        double a = PyFloat_AS_DOUBLE(v), b = PyFloat_AS_DOUBLE(ail_gval[i]);',
        '        return memcmp(&a, &b, sizeof a) == 0;',
        '    }',
        '    case 3: return v == ail_gval[i];',
        '    case 4: return PyUnicode_CheckExact(v) && PyUnicode_Compare(v, ail_gval[i]) == 0;',
        '    }',
        '    return 0;',
        '}',
        'static int ail_gcheck(PyObject *func, const int *idx, int n) {',
        '    PyObject *g = PyFunction_GET_GLOBALS(func);',
        '    if (!ail_gdict) ail_gadopt(g);',
        '    int cache = g == ail_gdict && ail_gwatched;',
        '    for (int k = 0; k < n; k++) {',
        '        int i = idx[k];',
        '        PyObject *f = NULL;',
        '        if (cache && ail_gok[i]) f = ail_gfunc[i];',
        '        else {',
        '            if (!ail_gverify(i, g, &f)) return 0;',
        '            if (cache) { Py_XINCREF(f); Py_XSETREF(ail_gfunc[i], f); ail_gok[i] = 1; }',
        '        }',
        '        if (ail_gkind[i] == 0 && !ail_known_code(ail_gcodes[i], PyFunction_GET_CODE(f))) return 0;',
        '    }',
        '    return 1;',
        '}',
        '#endif',
    ]


def _guard_init(items):
    names = _guard_names(items)
    if not names:
        return []
    out = ['#if PY_VERSION_HEX >= 0x030C0000']
    for i, (n, (tag, value)) in enumerate(names):
        out.append('    ail_gname[%d] = PyUnicode_InternFromString(ail_gname_s[%d]);' % (i, i))
        if tag == 'func':
            out.append('    ail_gentry[%d] = ail_v_%s; ail_gcodes[%d] = ail_code_%s;' % (i, n, i, n))
            continue
        if isinstance(value, bool):
            out.append('    ail_gval[%d] = Py_NewRef(%s);' % (i, 'Py_True' if value else 'Py_False'))
        elif isinstance(value, int):
            lit = '(-9223372036854775807LL - 1)' if value == _INT64[0] else '%dLL' % value
            out.append('    ail_gval[%d] = PyLong_FromLongLong(%s);' % (i, lit))
        elif isinstance(value, float):
            out.append('    ail_gval[%d] = PyFloat_FromDouble(%s);' % (i, value.hex()))
        else:
            lit, size = _c_string(value)
            out.append('    ail_gval[%d] = PyUnicode_DecodeUTF8(%s, %d, NULL);' % (i, lit, size))
    out.append('    for (int i = 0; i < AIL_NG; i++)')
    out.append('        if (!ail_gname[i] || (ail_gkind[i] && !ail_gval[i])) { Py_DECREF(m); return NULL; }')
    out.append('#endif')
    return out


def _vectorcall_entry(item):
    """The METH_FASTCALL-style vectorcall entry installed on the original function (3.12+).

    obs4: CPython raises RecursionError when it pushes a frame with no recursion budget left; the
    entry needs one frame per function the unit may stack (`nfuncs`) or runs the original, and a
    recursive unit's depth bound is set from the same budget.  Guarded globals are checked last."""
    name, n = item['name'], len(item['params'])
    frames = int(item.get('nfuncs') or 1)
    out = ['#if PY_VERSION_HEX >= 0x030C0000',
           'static PyObject *ail_v_%s(PyObject *func, PyObject *const *args, size_t nargsf, '
           'PyObject *kwnames) {' % name]
    cond = ['kwnames == NULL', 'ail_known_code(ail_code_%s, PyFunction_GET_CODE(func))' % name,
            'PyThreadState_GET()->py_recursion_remaining >= %d' % frames]
    if _guard_names([item]):
        cond.append('ail_guard_%s(func)' % name)
    out.append('    if (%s) {' % '\n            && '.join(cond))
    if item.get('rlimit'):
        out.append('        int64_t budget = (int64_t)PyThreadState_GET()->py_recursion_remaining - %d;'
                   % (frames - 1))
        out.append('        %s__hybrid_rlimit = budget < %d ? budget : %d;'
                   % (item['mangled'], item['rlimit'], item['rlimit']))
    out.extend([
        '        Py_ssize_t nargs = PyVectorcall_NARGS(nargsf);',
        '        PyObject *r;',
        '        if (nargs == %d) {' % n,
        '            r = ail_core_%s(args);' % name,
        '        } else {',
        '            PyObject *o[%d];' % max(1, n),
        '            PyObject *d = ail_fill_defaults(func, args, nargs, %d, o);' % n,
        '            if (!d) goto original;',
        '            r = ail_core_%s(o);' % name,
        '            Py_DECREF(d);',
        '        }',
        '        if (r || PyErr_Occurred()) return r;',
        '    }',
        'original:',
        '    return _PyFunction_Vectorcall(func, args, nargsf, kwnames);',
        '}',
        '#endif',
    ])
    return out


def _method_source(item, items_by_name):
    """obs4 (section 5.3): the class/instance guard and the vectorcall entry of a method.

    `ail_mguard_<n>` runs before any native work and only reads: `type(self)` is the class the
    method was installed from; the class has no metaclass, is a heap type with the generic
    getattr; no class attribute anywhere in the MRO is named like a field (so the read below only
    sees the instance dict and runs no Python code); every method the body calls on `self`
    resolves to its installed function with a recorded code and is not shadowed on the instance.
    It then reads every field (new references in `held`), which the core checks and converts like
    parameters.  Any failure runs the original method."""
    name, meta = item['name'], item['method']
    fields = [f for f, _k in meta['fields']]
    nf, nown = len(fields), meta['nown']
    mcalls = item.get('mcalls') or []
    frames = int(item.get('nfuncs') or 1)
    out = ['#if PY_VERSION_HEX >= 0x030C0000',
           'static PyObject *ail_cls_%s, *ail_mfunc_%s;' % (name, name),
           'static PyObject *ail_mname_%s;' % name]
    if nf:
        out.append('static PyObject *ail_mf_%s[%d];' % (name, nf))
    out.append('static int ail_mguard_%s(PyObject *self, PyObject **held) {' % name)
    out.extend([
        '    PyTypeObject *t = Py_TYPE(self);',
        '    if (ail_cls_%s == NULL || (PyObject *)t != ail_cls_%s) return 0;' % (name, name),
        '    if (Py_TYPE(t) != &PyType_Type || !(t->tp_flags & Py_TPFLAGS_HEAPTYPE)',
        '            || t->tp_getattro != PyObject_GenericGetAttr) return 0;',
    ])
    for i in range(nf):
        out.append('    if (_PyType_Lookup(t, ail_mf_%s[%d]) != NULL) return 0;' % (name, i))
    for callee in mcalls:
        out.extend([
            '    {',
            '        PyObject *f = _PyType_Lookup(t, ail_mname_%s);' % callee,
            '        if (f == NULL || f != ail_mfunc_%s' % callee,
            '                || !ail_known_code(ail_code_%s, PyFunction_GET_CODE(f))) return 0;' % callee,
            '        PyObject *b = PyObject_GetAttr(self, ail_mname_%s);' % callee,
            '        if (b == NULL) { PyErr_Clear(); return 0; }',
            '        int same = PyMethod_Check(b) && PyMethod_GET_FUNCTION(b) == f',
            '                   && PyMethod_GET_SELF(b) == self;',
            '        Py_DECREF(b);',
            '        if (!same) return 0;',
            '    }',
        ])
    for i in range(nf):
        out.extend([
            '    held[%d] = PyObject_GetAttr(self, ail_mf_%s[%d]);' % (i, name, i),
            '    if (held[%d] == NULL) {' % i,
            '        PyErr_Clear();',
        ])
        for j in range(i):
            out.append('        Py_DECREF(held[%d]);' % j)
        out.extend(['        return 0;', '    }'])
    out.extend(['    return 1;', '}'])
    cond = ['kwnames == NULL', 'ail_known_code(ail_code_%s, PyFunction_GET_CODE(func))' % name,
            'PyVectorcall_NARGS(nargsf) == %d' % (nown + 1),
            'PyThreadState_GET()->py_recursion_remaining >= %d' % frames]
    if _guard_names([item]):
        cond.append('ail_guard_%s(func)' % name)
    out.extend([
        'static PyObject *ail_v_%s(PyObject *func, PyObject *const *args, size_t nargsf, '
        'PyObject *kwnames) {' % name,
        '    if (%s) {' % '\n            && '.join(cond),
        '        PyObject *held[%d];' % max(1, nf),
        '        if (ail_mguard_%s(args[0], held)) {' % name,
        '            PyObject *o[%d];' % max(1, nf + nown),
    ])
    for i in range(nf):
        out.append('            o[%d] = held[%d];' % (i, i))
    for i in range(nown):
        out.append('            o[%d] = args[%d];' % (nf + i, i + 1))
    if item.get('rlimit'):
        out.append('            int64_t budget = (int64_t)PyThreadState_GET()->py_recursion_remaining'
                   ' - %d;' % (frames - 1))
        out.append('            %s__hybrid_rlimit = budget < %d ? budget : %d;'
                   % (item['mangled'], item['rlimit'], item['rlimit']))
    out.append('            PyObject *r = ail_core_%s(o);' % name)
    for i in range(nf):
        out.append('            Py_DECREF(held[%d]);' % i)
    out.extend([
        '            if (r || PyErr_Occurred()) return r;',
        '        }',
        '    }',
        '    return _PyFunction_Vectorcall(func, args, nargsf, kwnames);',
        '}',
        '#endif',
    ])
    return out


def _method_init(items):
    out = ['#if PY_VERSION_HEX >= 0x030C0000']
    for item in items:
        meta = item.get('method')
        if not meta:
            continue
        name = item['name']
        out.append('    ail_mname_%s = PyUnicode_InternFromString("%s");' % (name, meta['attr']))
        out.append('    if (!ail_mname_%s) { Py_DECREF(m); return NULL; }' % name)
        for i, (f, _k) in enumerate(meta['fields']):
            out.append('    ail_mf_%s[%d] = PyUnicode_InternFromString("%s");' % (name, i, f))
            out.append('    if (!ail_mf_%s[%d]) { Py_DECREF(m); return NULL; }' % (name, i))
    out.append('#endif')
    return out


def _install_method_source(items):
    """`_ail_install_method(name, cls, attr)`: install a method's native entry on the plain def
    in `cls.__dict__` (same checks as `_ail_install`) and remember the class for the guards."""
    out = [
        'static PyObject *ail_install_method(PyObject *self, PyObject *args) {',
        '    const char *name, *attr; PyObject *cls;',
        '    if (!PyArg_ParseTuple(args, "sOs", &name, &cls, &attr)) return NULL;',
        '#if PY_VERSION_HEX >= 0x030C0000',
        '    if (!PyType_Check(cls)) Py_RETURN_FALSE;',
        '    PyObject *dict = ((PyTypeObject *)cls)->tp_dict;',
        '    PyObject *func = dict ? PyDict_GetItemString(dict, attr) : NULL;',
        '    if (!func || !PyFunction_Check(func)) Py_RETURN_FALSE;',
        '    PyCodeObject *co = (PyCodeObject *)PyFunction_GET_CODE(func);',
        '    if (co->co_flags & (CO_VARARGS | CO_VARKEYWORDS | CO_GENERATOR | CO_COROUTINE |',
        '                        CO_ASYNC_GENERATOR | CO_ITERABLE_COROUTINE)) Py_RETURN_FALSE;',
        '    if (co->co_kwonlyargcount != 0) Py_RETURN_FALSE;',
        '    if (PyUnicode_CompareWithASCIIString(co->co_name, attr) != 0) Py_RETURN_FALSE;',
        '    PyObject **slots = NULL, **clsp = NULL, **funcp = NULL; vectorcallfunc entry = NULL;',
        '    int n = -1;',
    ]
    for item in items:
        meta = item.get('method')
        if not meta:
            continue
        nm = item['name']
        out.append('    if (!strcmp(name, "%s") && !strcmp(attr, "%s")) { slots = ail_code_%s; '
                   'entry = ail_v_%s; n = %d; clsp = &ail_cls_%s; funcp = &ail_mfunc_%s; }'
                   % (nm, meta['attr'], nm, nm, meta['nown'] + 1, nm, nm))
    out.extend([
        '    if (!slots || co->co_argcount != n) Py_RETURN_FALSE;',
        '    vectorcallfunc now = ((PyFunctionObject *)func)->vectorcall;',
        '    if (now != _PyFunction_Vectorcall && now != entry) Py_RETURN_FALSE;',
        '    int i = 0;',
        '    while (i < AIL_CODES && slots[i] && slots[i] != (PyObject *)co) i++;',
        '    if (i == AIL_CODES) Py_RETURN_FALSE;',
        '    if (!slots[i]) { Py_INCREF(co); slots[i] = (PyObject *)co; }',
        '    Py_INCREF(cls); Py_XSETREF(*clsp, cls);',
        '    Py_INCREF(func); Py_XSETREF(*funcp, func);',
        '    PyFunction_SetVectorcall((PyFunctionObject *)func, entry);',
        '    Py_RETURN_TRUE;',
        '#else',
        '    (void)name; (void)attr; (void)cls;',
        '    Py_RETURN_FALSE;',
        '#endif',
        '}',
        '',
    ])
    return out


def _guard_fn(item, index):
    names = [g for g, _v in _guard_names([item])]
    if not names:
        return []
    return ['#if PY_VERSION_HEX >= 0x030C0000',
            'static int ail_guard_%s(PyObject *func) {' % item['name'],
            '    static const int idx[] = {%s};' % ', '.join(str(index[g]) for g in names),
            '    return ail_gcheck(func, idx, %d);' % len(names),
            '}',
            '#endif']


def _install_source(items, methods_too=None):
    out = [
        'static PyObject *ail_install(PyObject *self, PyObject *args) {',
        '    const char *name; PyObject *func;',
        '    if (!PyArg_ParseTuple(args, "sO", &name, &func)) return NULL;',
        '#if PY_VERSION_HEX >= 0x030C0000',
        '    if (!PyFunction_Check(func)) Py_RETURN_FALSE;',
        '    PyCodeObject *co = (PyCodeObject *)PyFunction_GET_CODE(func);',
        '    /* Only a plain positional signature of the native arity: no *args/**kw, no keyword-only',
        '       parameters, not a generator/coroutine, and the code of the def itself (a decorator\'s',
        '       inner function has another name).  Anything else keeps the Python wrapper path. */',
        '    if (co->co_flags & (CO_VARARGS | CO_VARKEYWORDS | CO_GENERATOR | CO_COROUTINE |',
        '                        CO_ASYNC_GENERATOR | CO_ITERABLE_COROUTINE)) Py_RETURN_FALSE;',
        '    if (co->co_kwonlyargcount != 0) Py_RETURN_FALSE;',
        '    if (PyUnicode_CompareWithASCIIString(co->co_name, name) != 0) Py_RETURN_FALSE;',
        '    PyObject **slots = NULL; vectorcallfunc entry = NULL; int n = -1;',
    ]
    for item in items:
        out.append('    if (!strcmp(name, "%s")) { slots = ail_code_%s; entry = ail_v_%s; n = %d; }'
                   % (item['name'], item['name'], item['name'], len(item['params'])))
    out.extend([
        '    if (!slots || co->co_argcount != n) Py_RETURN_FALSE;',
        '    vectorcallfunc now = ((PyFunctionObject *)func)->vectorcall;',
        '    if (now != _PyFunction_Vectorcall && now != entry) Py_RETURN_FALSE;',
        '    int i = 0;',
        '    while (i < AIL_CODES && slots[i] && slots[i] != (PyObject *)co) i++;',
        '    if (i == AIL_CODES) Py_RETURN_FALSE;',
        '    if (!slots[i]) { Py_INCREF(co); slots[i] = (PyObject *)co; }',
        '    PyFunction_SetVectorcall((PyFunctionObject *)func, entry);',
        '    Py_RETURN_TRUE;',
        '#else',
        '    (void)name; (void)func;',
        '    Py_RETURN_FALSE;',
        '#endif',
        '}',
        '/* True when `func` runs through one of this module\'s native entries (tests, probes). */',
        'static PyObject *ail_is_native(PyObject *self, PyObject *func) {',
        '#if PY_VERSION_HEX >= 0x030C0000',
        '    if (PyFunction_Check(func)) {',
        '        vectorcallfunc v = ((PyFunctionObject *)func)->vectorcall;',
    ])
    for item in items:
        out.append('        if (v == ail_v_%s) Py_RETURN_TRUE;' % item['name'])
    for item in methods_too or ():
        out.append('        if (v == ail_v_%s) Py_RETURN_TRUE;' % item['name'])
    out.extend([
        '    }',
        '#endif',
        '    (void)func;',
        '    Py_RETURN_FALSE;',
        '}',
        '',
    ])
    return out


def _wrapper_source(module, items):
    out = [
        '#include <Python.h>',
        '#include <stdint.h>',
        '#include <stdlib.h>',
        '#include <string.h>',
        '',
        'typedef struct { const uint8_t *p; int64_t n; _Bool bytes; } ail_str;',
        'typedef struct { double *p; int64_t n, cap; } ail_flist;',
        'static PyObject *AilHybridFallback;',
        'void ail_mix_drain_out(void) { }',
        'static PyObject *ail_hybrid_fallback(void) {',
        '    PyErr_SetString(AilHybridFallback, "argument or result does not fit the AIL ABI");',
        '    return NULL;',
        '}',
        _VECTORCALL_HELPERS,
    ]
    out.append('#if PY_VERSION_HEX >= 0x030C0000')
    for item in items:
        out.append('static PyObject *ail_code_%s[AIL_CODES];' % item['name'])
        out.append('static PyObject *ail_v_%s(PyObject *, PyObject *const *, size_t, PyObject *);'
                   % item['name'])
        if item.get('method'):
            out.append('static PyObject *ail_cls_{0}, *ail_mfunc_{0}, *ail_mname_{0};'
                       .format(item['name']))
    out.append('#endif')
    out.extend(_guard_source(items))
    gindex = {g: i for i, (g, _v) in enumerate(_guard_names(items))}
    for item in items:
        out.extend(_guard_fn(item, gindex))
    for item in items:
        callee = item['mangled'] + '__hybrid_call' if item.get('trap') else item['mangled']
        out.append('extern %s;' % _c_proto(item, callee))
        if item.get('rlimit'):
            out.append('extern __thread int64_t %s__hybrid_rlimit;' % item['mangled'])
        if item['ret'] in _LIST:
            elem = 'int64_t' if item['ret'] == 'list[int]' else 'double'
            out.append('extern int64_t %s__hybrid_spill(const %s **p);' % (item['mangled'], elem))
            out.append('extern void %s__hybrid_spill_free(void);' % item['mangled'])
        out.append('static PyObject *ail_core_%s(PyObject *const *o);' % item['name'])
    out.append('')
    for item in items:
        name = item['name']
        params = item['params']
        ret = item['ret']
        abi = item.get('abi') or {}
        callee = item['mangled'] + '__hybrid_call' if item.get('trap') else item['mangled']
        trap = item['mangled'] + '__hybrid_trap'
        # Owner decision D4 (2026-11-05): a call whose arguments include a container keeps the GIL.
        # The list is copied into a C buffer first, but the safe default is not to release while
        # other CPython threads may hold and mutate a container.  Scalar-only calls still release.
        # A list result keeps it too: the unit's one spill slot for a long result is shared.
        # obs3: a body without a loop finishes in well under the ~40 ns a GIL release and
        # re-acquire costs (tokenizer's one-line `is_ident_char` got slower than CPython), so it
        # keeps the GIL as well.
        # obs4: a unit that reads guarded globals keeps the GIL, so no other thread can rebind a
        # constant or a callee while the native body runs on what it verified.
        hold = any(kind in _LIST for _p, kind in params) or ret in _LIST \
            or not item.get('loops', True) or _guarded(item)
        begin = [] if hold else ['    Py_BEGIN_ALLOW_THREADS']
        end = [] if hold else ['    Py_END_ALLOW_THREADS']
        n = len(params)
        # The METH_VARARGS entry (`_ail_hybrid_native.<name>`) is kept for the Python-wrapper
        # path (CPython < 3.12, or a signature `_ail_install` refuses); it raises Fallback.
        out.append('static PyObject *ail_w_%s(PyObject *self, PyObject *args) {' % name)
        if _guarded(item):
            out.append('    (void)args;')
            out.append('    return ail_hybrid_fallback();')
            out.append('}')
        else:
            out.append('    if (PyTuple_GET_SIZE(args) != %d) return ail_hybrid_fallback();' % n)
            out.append('    PyObject *r = ail_core_%s(((PyTupleObject *)args)->ob_item);' % name)
            out.append('    if (!r && !PyErr_Occurred()) return ail_hybrid_fallback();')
            out.append('    return r;')
            out.append('}')
        # The core: argument checks, conversion and the native call.  It returns the result, or
        # NULL with no exception set when the call must run in CPython instead (a guard failed,
        # an int64 overflow, an index/key trap), or NULL with an exception (MemoryError only).
        # Every check runs before any native work, so a fallback has nothing to undo.
        out.append('static PyObject *ail_core_%s(PyObject *const *o) {' % name)
        if item.get('trap'):
            out.append('    extern __thread int %s;' % trap)
        # Every conversion failure after the declarations below must free whatever buffers an
        # earlier list argument already filled; `fallback:` does that.  When there are no buffers
        # the label is not emitted, so keep the direct return in that case.
        bufs = ['b%d' % i for i, (_p, kind) in enumerate(params)
                if kind in ('list[int]', 'list[float]')]
        fail = 'goto fallback' if bufs else 'return NULL'
        for i, (p, kind) in enumerate(params):
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
                    out.append('    int64_t a%d = %s == Py_True;' % (i, o))
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
                if abi.get(p) == 'flist':
                    # The clone reads an `ail_flist` by value and never frees or grows a
                    # parameter; the buffer stays ours.
                    call.append('(ail_flist){b%d, (int64_t)n%d, (int64_t)n%d}' % (i, i, i))
                else:
                    call.append('b%d' % i)
                    call.append('(int64_t)n%d' % i)
        cargs = ', '.join(call)
        if ret == 'str':
            out.append('    int64_t need;')
            out.extend(begin)
            out.append('    need = %s(%s%sNULL, 0);' % (callee, cargs, ', ' if cargs else ''))
            out.extend(end)
            if item.get('trap'):
                out.append('    if (%s) %s;' % (trap, fail))
            out.append('    if (need < 0) %s;' % fail)
            out.append('    uint8_t *sb = (uint8_t *)PyMem_Malloc((size_t)(need > 0 ? need : 1));')
            out.append('    if (!sb) {')
            for b in bufs:
                out.append('        PyMem_Free(%s);' % b)
            out.append('        return PyErr_NoMemory();')
            out.append('    }')
            out.extend(begin)
            out.append('    if (need > 0) %s(%s%s(void *)sb, need);' % (callee, cargs, ', ' if cargs else ''))
            out.extend(end)
            if item.get('trap'):
                out.append('    if (%s) { PyMem_Free(sb); %s; }' % (trap, fail))
            out.append('    PyObject *res = PyUnicode_DecodeUTF8((const char *)sb, (Py_ssize_t)need, NULL);')
            out.append('    PyMem_Free(sb);')
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    if (!res) { PyErr_Clear(); return NULL; }')
            out.append('    return res;')
        elif ret == 'float':
            out.append('    double r;')
            out.extend(begin)
            out.append('    r = %s(%s);' % (callee, cargs))
            out.extend(end)
            if item.get('trap'):
                out.append('    if (%s) %s;' % (trap, fail))
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    return PyFloat_FromDouble(r);')
        elif ret in _LIST:
            # obs3: a list result comes back through the clone's own buffer ABI (`_out`, `_cap`,
            # the true length as the C result).  A short list fits the stack buffer; a long one
            # is kept whole in the unit's spill slot and read from there, never by calling the
            # clone twice.  The CPython list is built fresh from exact ints / floats.
            elem = 'int64_t' if ret == 'list[int]' else 'double'
            box = 'PyLong_FromLongLong((long long)lp[k])' if ret == 'list[int]' \
                else 'PyFloat_FromDouble(lp[k])'
            out.append('    %s lb[64]; const %s *lp = lb; int64_t ln; int sp = 0;' % (elem, elem))
            out.extend(begin)
            out.append('    ln = %s(%s%slb, 64);' % (callee, cargs, ', ' if cargs else ''))
            out.extend(end)
            if item.get('trap'):
                out.append('    if (%s) %s;' % (trap, fail))
            out.append('    if (ln < 0) %s;' % fail)
            out.append('    if (ln > 64) {')
            out.append('        int64_t sn = %s__hybrid_spill(&lp);' % item['mangled'])
            out.append('        sp = 1;')
            out.append('        if (sn != ln || !lp) { %s__hybrid_spill_free(); %s; }'
                       % (item['mangled'], fail))
            out.append('    }')
            out.append('    PyObject *res = PyList_New((Py_ssize_t)ln);')
            out.append('    if (res) {')
            out.append('        for (Py_ssize_t k = 0; k < (Py_ssize_t)ln; k++) {')
            out.append('            PyObject *e = %s;' % box)
            out.append('            if (!e) { Py_CLEAR(res); break; }')
            out.append('            PyList_SET_ITEM(res, k, e);')
            out.append('        }')
            out.append('    }')
            out.append('    if (sp) %s__hybrid_spill_free();' % item['mangled'])
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    return res;')
        else:
            mix_ovf = item.get('mix_ovf', True)
            if mix_ovf:
                out.append('    extern __thread int %s__mix_overflow;' % item['mangled'])
            out.append('    int64_t r; int ovf = 0;')
            out.extend(begin)
            out.append('    r = %s(%s);' % (callee, cargs))
            if mix_ovf:
                out.append('    ovf = %s__mix_overflow;' % item['mangled'])
            out.extend(end)
            if item.get('trap'):
                out.append('    if (%s) %s;' % (trap, fail))
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    if (ovf) return NULL;')
            if ret == 'bool':
                out.append('    return PyBool_FromLong((long)r);')
            else:
                out.append('    return PyLong_FromLongLong((long long)r);')
        if bufs:
            out.append('fallback:')
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    return NULL;')
        out.append('}')
        out.extend(_method_source(item, None) if item.get('method') else _vectorcall_entry(item))
        out.append('')
    out.extend(_install_source([i for i in items if not i.get('method')],
                               [i for i in items if i.get('method')]))
    out.extend(_install_method_source(items))
    out.append('static PyMethodDef ail_methods[] = {')
    for item in items:
        out.append('    {"%s", ail_w_%s, METH_VARARGS, NULL},' % (item['name'], item['name']))
    out.append('    {"_ail_install", ail_install, METH_VARARGS, NULL},')
    out.append('    {"_ail_install_method", ail_install_method, METH_VARARGS, NULL},')
    out.append('    {"_ail_is_native", ail_is_native, METH_O, NULL},')
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
    out.extend(_guard_init(items))
    out.extend(_method_init(items))
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
        'def _ail_hybrid_make(_native, _original, _name=None):\n'
        '    if _native is None or _original is None:\n'
        '        return _original\n'
        '    # CPython 3.12+: the C entry is installed on the original function object itself\n'
        '    # (vectorcall); it falls back to the original code in C.  No Python frame is added.\n'
        '    _install = getattr(_ail_hybrid_native, "_ail_install", None)\n'
        '    if _install is not None and _name is not None:\n'
        '        try:\n'
        '            if _install(_name, _original):\n'
        '                return _original\n'
        '        except Exception:\n'
        '            pass\n'
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
        '    def _ail_hybrid_make(_native, _original, _name=None):\n'
        '        return _original\n'
        '# --- original program follows ---\n\n'
    )
    return _text.replace('__AIL_MODULE__', module).replace('__AIL_SOURCE__', repr(str(original_path)))


def _hybrid_source(source, tree, module, names, original_path, methods=()):
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
                    '    %s = _ail_hybrid_make(_ail_hybrid_native.%s, %s, %r)\n'
                    'except Exception:\n'
                    '    pass\n' % (name, name, name, name))
            edits.append((fn.end_lineno, 0, text))
    for syn, meta in methods:
        text = ('try:\n'
                '    _ail_hybrid_native._ail_install_method(%r, %s, %r)\n'
                'except Exception:\n'
                '    pass\n' % (syn, meta['cls'], meta['attr']))
        edits.append((meta['end'], 1, text))
    edits.sort(key=lambda e: (e[0], -e[1]), reverse=True)
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
        # Runtime entry points a typed unit exports by name (`ail_ret_spill_take`, ...) would be
        # defined once per unit in the same `.so`; give each unit's copy its own name.
        for export in sorted(set(re.findall(r'(?m)^AIL_LINK_EXPORT\s+[\w \*]*?\b(ail_\w+)\s*\(',
                                            csrc))):
            csrc = re.sub(r'\b%s\b' % re.escape(export), '%s__%s' % (item['mangled'], export),
                          csrc)
        if item['ret'] in _LIST:
            # The unit's spill slot (static) holds a returned list longer than the wrapper's
            # buffer; the wrapper reads it in place and frees it (it is a malloc'd array).
            spill = 'ail_ret_spill' if item['ret'] == 'list[int]' else 'ail_fret_spill'
            elem = 'int64_t' if item['ret'] == 'list[int]' else 'double'
            if not re.search(r'\b%s_p\b' % spill, csrc):
                raise RuntimeError('typed unit %r: no list return slot' % item['name'])
            csrc += ('\nint64_t %s__hybrid_spill(const %s **p) { *p = %s_p; return %s_n; }\n'
                     'void %s__hybrid_spill_free(void) { free(%s_p); %s_p = NULL; %s_n = 0; }\n'
                     % (item['mangled'], elem, spill, spill, item['mangled'], spill, spill,
                        spill))
        cap = _RECURSION_CAP.search(csrc)
        if cap:
            # obs4: the depth bound becomes a thread-local the C entry sets before every call
            # to min(cap, CPython's remaining frames - other functions in the unit); exceeding
            # it traps, and CPython re-runs the call (and raises RecursionError if it must).
            item['rlimit'] = int(cap.group(1))
            item['trap'] = True
            var = item['mangled'] + '__hybrid_rlimit'
            csrc = (csrc[:cap.start()]
                    + '__thread int64_t %s = 0;\n#define AIL_MAX_RECURSION_DEPTH (%s)' % (var, var)
                    + csrc[cap.end():])
        if item.get('trap'):
            csrc = _trap_patch(csrc, item['mangled'])
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


_VERIFY = r'''
import importlib.util, json, sys
name, path, wanted = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
spec = importlib.util.spec_from_file_location(name, path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
missing = [n for n in wanted if not callable(getattr(mod, n, None))]
if missing:
    raise SystemExit('the extension lacks ' + ', '.join(missing))
'''


def _verify_import(so, module, names):
    """Import the freshly linked extension in a separate interpreter (the same one that will run
    the program) and return None, or the reason it cannot be used.

    The generated preamble treats an import failure as "run on CPython" so that a moved or
    mismatched `.so` never breaks the program.  Without this check a unit that links but cannot
    load (obs1: an undefined trap symbol) silently ran everything on CPython while build.json
    listed the functions as accelerated."""
    try:
        r = subprocess.run([sys.executable, '-I', '-B', '-c', _VERIFY, module, str(so),
                            json.dumps(list(names))],
                           capture_output=True, text=True, timeout=120)
    except Exception as error:
        return 'import check failed: %s' % error
    if r.returncode != 0:
        lines = [l for l in (r.stderr or r.stdout or '').strip().splitlines() if l.strip()]
        return (lines[-1] if lines else 'exit status %d' % r.returncode)[:600]
    return None


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
        'schema': 'ail.cpython_hybrid/2',
        'source': str(source_path),
        'python': sys.version.split()[0],
        'module': module,
        'accelerated': [],
        'rejected': {},
        'extension': None,
        'run_file': stem + '_run.py',
        'python_file': stem + '.py',
    }
    chosen = {}
    methods = {}
    try:
        # obs4: read-only methods enter the analysis as synthetic top-level functions; the
        # program that runs is still the original text (section 5.3).
        try:
            synth, method_refusals = _method_synthetics(tree)
        except Exception as error:                     # never let the method pass break a build
            synth, method_refusals = [], {}
            report['note_methods'] = 'method pass failed: %s' % error
        analysis_source = source
        if synth:
            analysis_source = source.rstrip('\n') + '\n\n\n' + '\n\n\n'.join(
                ast.unparse(fn) for fn, _m in synth) + '\n'
        methods = {fn.name: meta for fn, meta in synth}
        analysis_tree = ast.parse(analysis_source) if synth else tree
        units_report, facts = _analysis(analysis_source)
        chosen, report['rejected'] = _select(analysis_source, analysis_tree, units_report, facts,
                                             methods)
        for name in list(report['rejected']):
            if name in methods:
                meta = methods[name]
                report['rejected']['%s.%s' % (meta['cls'], meta['attr'])] = \
                    report['rejected'].pop(name)
        report['rejected'].update(method_refusals)
        units = units_report.get('mix_units') or []
        items = [chosen[name] for name in sorted(chosen)
                 if any(u[1] == name for u in units)]
        if items:
            so = _compile(items, units, module, output_dir)
            names = sorted(i['name'] for i in items)
            broken = _verify_import(so, module, names)
            if broken is None:
                report['extension'] = so.name
                report['accelerated'] = sorted(
                    '%s.%s' % (methods[n]['cls'], methods[n]['attr']) if n in methods else n
                    for n in names)
            else:
                # Never claim native for code that does not load: drop the extension, keep the
                # program on CPython, name the reason per function and say so on stderr.
                try:
                    so.unlink()
                except OSError:
                    pass
                why = 'the extension did not import (%s), stays in CPython' % broken
                for name in names:
                    report['rejected'][name] = why
                report['note'] = 'no extension: ' + why
                print('ail build --cpython: WARNING: %s; %d function(s) run in CPython'
                      % (why, len(names)), file=sys.stderr)
        elif units:
            report['note'] = 'the typed functions were not safe to wrap; the program runs in CPython'
    except Exception as error:
        report['note'] = 'no extension: %s' % error

    # Always keep an unmodified copy and a runnable hybrid copy.  `prog_run.py` is the file the
    # task names; the `<stem>.py` copy stays for callers of the earlier --cpython prototype.
    (output_dir / (stem + '.orig.py')).write_text(source, encoding='utf-8')
    installed = [n for n in report['accelerated'] if n in _top_level_functions(tree)]
    method_installs = [(n, methods[n]) for n in sorted(methods)
                       if '%s.%s' % (methods[n]['cls'], methods[n]['attr']) in report['accelerated']]
    hybrid = _hybrid_source(source, tree, module, installed, source_path, method_installs)
    (output_dir / report['run_file']).write_text(hybrid, encoding='utf-8')
    legacy = output_dir / report['python_file']
    if legacy.resolve() != source_path:
        legacy.write_text(hybrid, encoding='utf-8')
    launcher = output_dir / stem
    launcher.write_text('#!/bin/sh\nexec "${AIL_PYTHON:-python3}" "$(dirname "$0")/%s" "$@"\n'
                        % report['run_file'], encoding='utf-8')
    launcher.chmod(0o755)
    (output_dir / 'build.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n',
                                           encoding='utf-8')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='build a CPython hybrid: typed functions become an extension module, '
                    'everything else runs in CPython')
    parser.add_argument('source', metavar='SOURCE')
    parser.add_argument('-o', '--out', metavar='DIR')
    args = parser.parse_args()
    source = Path(args.source)
    output = Path(args.out) if args.out else source.parent / (source.stem + '_hybrid')
    report = build(source, output)
    print('built %s: %d function(s) accelerated' % (output, len(report.get('accelerated') or [])))
    print('run %s' % (output / report['run_file']))
