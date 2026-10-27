"""Portable entry for the AIL source snapshot; no implicit model calls."""
import ast
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from ail_syntax import SyntaxErrorAIL, detect, fold_constants, python_surface, python_wording, translate
import ail_sexpr
import ail_modules

sys.path.append(str(Path(__file__).resolve().parent / 'python/pkg-v12'))
import fastwalk
fastwalk.install()      # the same ast.walk in half the time, for every walk this process makes

ROOT = Path(__file__).resolve().parent
_BUILDCACHE = []


def _relpath(path):
    """os.path.relpath that survives the platforms where there is no plain relative form:
    a path on another drive (Windows: temp on C:, cwd on D:) answers the '..' spelling every caller
    already treats as "show it absolute", and a spelling that differs only by aliases (Windows
    8.3 short names such as RUNNER~1, macOS /var -> /private/var) is compared by real path."""
    try:
        relative = os.path.relpath(path)
    except ValueError:
        relative = None
    if relative is None or relative.startswith(os.pardir):
        try:
            relative = os.path.relpath(os.path.realpath(path), os.path.realpath(os.curdir))
        except ValueError:
            return os.pardir + os.sep + str(path)
    return relative


def _build_cache(args=None):
    """The build cache module (python/pkg-v12/buildcache.py), or None when it is switched off
    (AIL_NO_CACHE, --no-cache) or cannot be loaded. Loaded by path so pkg-v12 stays off sys.path."""
    if not _BUILDCACHE:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location('buildcache', ROOT / 'python/pkg-v12/buildcache.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _BUILDCACHE.append(module)
        except (OSError, ImportError, SyntaxError):
            _BUILDCACHE.append(None)
    module = _BUILDCACHE[0]
    return None if module is None or module.disabled() else module


_MERGED_ENTRIES = {}         # entry file -> ail_modules.Merged, for entries whose text merges several modules


def _literal_number(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        node = node.operand
    return isinstance(node, ast.Constant) and type(node.value) in (int, float)


def _module_constant(node):
    if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return False
    value = node.value
    return (isinstance(value, ast.Constant) and type(value.value) in (str, bytes)
            or _literal_number(value) or isinstance(value, (ast.List, ast.Tuple))
            and bool(value.elts) and all(map(_literal_number, value.elts)))


_INT64_MIN, _INT64_MAX = -(1 << 63), (1 << 63) - 1


class _Int64ConstantOverflow(Exception):
    """A constant expression (or one of its steps) left the int64 range."""


def _constant_diagnostic(value):
    """Format a constant for a diagnostic without tripping CPython's int-to-str digit limit."""
    try:
        return str(value)
    except ValueError:
        return 'too large'


def _const_expr_int(node, bounded=True):
    """The int a constant arithmetic expression denotes, or None when it is not one. With
    `bounded`, raises _Int64ConstantOverflow as soon as a step is outside int64: AIL computes such
    a step in int64 and stops with `integer overflow`, where CPython's unbounded int reaches the
    subscript (or the value) and raises IndexError (or keeps the big value). The checks below
    refuse the construct instead of letting the two differ."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        value = node.value
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
        # `-(1 << 63)` and `~(-(1 << 63))` pass through an out-of-int64 POSITIVE operand and
        # come back in range, so the operand is folded unbounded for USub/Invert and only the
        # result is range-checked (pre246: `d[-(1 << 63)]` is a legal index).  UAdd cannot
        # change the sign, so it keeps the per-step bound.  A result that still leaves int64 is
        # refused below, so `-(10 ** 20)` and `~((1 << 63))` keep their refusal.
        if isinstance(node.op, ast.UAdd):
            value = _const_expr_int(node.operand, bounded)
        else:
            value = _const_expr_int(node.operand, False)
        if value is None:
            return None
        if isinstance(node.op, ast.USub):
            value = -value
        elif isinstance(node.op, ast.Invert):
            value = ~value
    elif isinstance(node, ast.BinOp):
        left, right = _const_expr_int(node.left, bounded), _const_expr_int(node.right, bounded)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Pow):
            if not 0 <= right <= 64:
                return None
            value = left ** right
        elif isinstance(node.op, ast.LShift):
            if not 0 <= right < 64:
                return None
            value = left << right
        elif isinstance(node.op, ast.RShift):
            if not 0 <= right < 64:
                return None
            value = left >> right
        elif isinstance(node.op, ast.Mult):
            value = left * right
        elif isinstance(node.op, ast.Add):
            value = left + right
        elif isinstance(node.op, ast.Sub):
            value = left - right
        elif isinstance(node.op, ast.FloorDiv):
            if right == 0:
                return None
            value = left // right
        elif isinstance(node.op, ast.Mod):
            if right == 0:
                return None
            value = left % right
        elif isinstance(node.op, ast.BitAnd):
            value = left & right
        elif isinstance(node.op, ast.BitOr):
            value = left | right
        elif isinstance(node.op, ast.BitXor):
            value = left ^ right
        else:
            return None
    else:
        return None
    if bounded and not _INT64_MIN <= value <= _INT64_MAX:
        raise _Int64ConstantOverflow(value)
    return value


_CONST_FOLD_BITS = 1 << 20
_CONST_FOLD_SPECIAL_BITS = 1 << 24


def _const_fold_int(node, limit=_CONST_FOLD_BITS):
    """The exact int a constant expression denotes under the code generator's fold budget.

    This mirrors the pre190 folders: zero operands and the power bases 0/1/-1 are decided
    before the size guard, and an exponent may use the larger special budget, so
    `0 * (1 << 5000)`, `(-1) ** ((1 << 5000) + 1)` and `(1 << 5000) >> 5000` fold to their
    in-range int64 results.  None means not constant, not an int, or an intermediate wider
    than `limit` bits (the construct is then left to the folder's own refusal)."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
        value = _const_fold_int(node.operand, limit)
        if value is None:
            return None
        if isinstance(node.op, ast.USub):
            value = -value
        elif isinstance(node.op, ast.Invert):
            value = ~value
        return value if value.bit_length() <= limit else None
    if not isinstance(node, ast.BinOp):
        return None
    op = type(node.op)
    if op is ast.Pow:
        right = _const_fold_int(node.right, limit)
        if right == 0:
            left = _const_fold_int(node.left, limit)
            if left is None:
                left = _const_fold_int(node.left, _CONST_FOLD_SPECIAL_BITS)
            return 1 if left is not None else None
        left = _const_fold_int(node.left, limit)
        if left in (0, 1, -1):
            if right is None:
                right = _const_fold_int(node.right, _CONST_FOLD_SPECIAL_BITS)
            if right is not None and right >= 0:
                if right == 0:
                    return 1
                if left == 0:
                    return 0
                if left == 1:
                    return 1
                return 1 if right % 2 == 0 else -1
        if left is None or right is None:
            return None
    elif op is ast.Mult or op is ast.BitAnd:
        left = _const_fold_int(node.left, limit)
        right = _const_fold_int(node.right, limit)
        if left == 0 or right == 0:
            if left is None:
                left = _const_fold_int(node.left, _CONST_FOLD_SPECIAL_BITS)
            if right is None:
                right = _const_fold_int(node.right, _CONST_FOLD_SPECIAL_BITS)
            if left is None or right is None:
                return None
            return 0
        if left is None or right is None:
            return None
    elif op is ast.LShift:
        left = _const_fold_int(node.left, limit)
        if left == 0:
            right = _const_fold_int(node.right, limit)
            if right is None:
                right = _const_fold_int(node.right, _CONST_FOLD_SPECIAL_BITS)
            if right is not None and right >= 0:
                return 0
        right = _const_fold_int(node.right, limit)
        if left is None or right is None:
            return None
    else:
        left = _const_fold_int(node.left, limit)
        right = _const_fold_int(node.right, limit)
        if left is None or right is None:
            return None
    try:
        if op is ast.Pow:
            if right < 0:
                return None
            if left == 0:
                value = 1 if right == 0 else 0
            elif left == 1:
                value = 1
            elif left == -1:
                value = 1 if right % 2 == 0 else -1
            elif right > limit or left.bit_length() * right > limit:
                return None
            else:
                value = left ** right
        elif op is ast.LShift:
            if right < 0:
                return None
            if left == 0:
                value = 0
            elif right > limit or left.bit_length() + right > limit:
                return None
            else:
                value = left << right
        elif op is ast.RShift:
            if right < 0:
                return None
            value = (0 if left >= 0 else -1) if right > limit else left >> right
        elif op is ast.Mult:
            if left == 0 or right == 0:
                value = 0
            elif left.bit_length() + right.bit_length() > limit:
                return None
            else:
                value = left * right
        elif op is ast.Add:
            value = left + right
        elif op is ast.Sub:
            value = left - right
        elif op is ast.FloorDiv:
            if right == 0:
                return None
            value = left // right
        elif op is ast.Mod:
            if right == 0:
                return None
            value = left % right
        elif op is ast.BitAnd:
            value = left & right
        elif op is ast.BitOr:
            value = left | right
        elif op is ast.BitXor:
            value = left ^ right
        else:
            return None
    except (ArithmeticError, ValueError):
        return None
    return value if value.bit_length() <= limit else None


def _check_constant_out_of_range(node, parents, maxsplit, skip_assignment):
    if id(node) in maxsplit:
        return
    value = _const_fold_int(node)
    if value is None or _INT64_MIN <= value <= _INT64_MAX:
        return
    root = node
    while True:
        parent = parents.get(root)
        if parent is None:
            break
        current = _const_fold_int(parent)
        if current is None:
            break
        root = parent
    full = _const_fold_int(root)
    if full is not None and _INT64_MIN <= full <= _INT64_MAX:
        return
    parent = parents.get(root)
    if (skip_assignment and isinstance(parent, ast.Assign) and parent.value is root
            and not isinstance(parents.get(parent), ast.ClassDef)):
        return
    error = ValueError(f'int64 constant out of range: {_constant_diagnostic(value)}')
    error.source_line = node.lineno
    error.source_column = node.col_offset
    raise error


def _check_constant_power(node, parents, maxsplit):
    """Refuse a constant `**` whose value int64 cannot hold, unless the whole enclosing constant
    expression folds to an in-range value (pre113 keeps `2**63 - 1` and `2**64 // 2 - 1`), the
    node is a str.split/rsplit maxsplit constant (pre97 names that), or the expression is the
    whole right-hand side of an assignment (a local or module value keeps its run-time overflow
    trap). Literals are refused by _check_int64_literals; this catches `10 ** 20` written as
    arithmetic, wherever it appears (an argument, a list item, an attribute or a dict value),
    not only as an index."""
    _check_constant_out_of_range(node, parents, maxsplit, skip_assignment=True)

def _check_index_expression(slice_node):
    """Refuse a constant subscript index whose exact value int64 cannot hold. A literal or signed
    literal is already refused by _check_int64_literals with its own message, so only compound
    arithmetic is read here. A step may leave int64 while the exact final index fits
    (`2**63 - 2**63`, `2**63 * 0`, `(1 << 63) >> 62`); the whole expression is folded with the
    code generator's size budget and then with the 4096-bit guarded exact fold, so a result that
    comes back in range is kept. An inconclusive fold or an out-of-int64 result keeps the
    per-step refusal."""
    literal = (isinstance(slice_node, ast.Constant)
               or isinstance(slice_node, ast.UnaryOp) and isinstance(slice_node.op, (ast.UAdd, ast.USub))
               and isinstance(slice_node.operand, ast.Constant))
    if literal:
        return
    try:
        _const_expr_int(slice_node)
        return
    except _Int64ConstantOverflow as overflow:
        value = _const_fold_int(slice_node)
        if value is not None and _INT64_MIN <= value <= _INT64_MAX:
            return
        ok, exact = _constant_int_exact(slice_node)
        if ok and exact is not _CONST_INT_TOO_BIG and _INT64_MIN <= exact <= _INT64_MAX:
            return
        if value is None:
            value = overflow.args[0]
    error = ValueError(f'int64 index out of range: {_constant_diagnostic(value)}')
    error.source_line = slice_node.lineno
    error.source_column = slice_node.col_offset
    raise error


_UNKNOWN = object()


def _shallow_walk(nodes):
    stack = list(nodes)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _binding_counts(nodes):
    counts = {}

    def add(name):
        counts[name] = counts.get(name, 0) + 1

    for node in _shallow_walk(nodes):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add(node.name)
        elif isinstance(node, ast.arg):
            add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                add((alias.asname or alias.name).split('.')[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                add(name)
    return counts


def _function_bindings(fn):
    args = fn.args
    names = [arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    if args.vararg is not None:
        names.append(args.vararg.arg)
    if args.kwarg is not None:
        names.append(args.kwarg.arg)
    return set(names) | set(_binding_counts(fn.body))


def _constant_value(node, lookup, global_name, passthrough):
    if isinstance(node, ast.Constant):
        if type(node.value) in (bool, int, float, str, bytes, type(None)):
            return node.value
        return _UNKNOWN
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _constant_value(node.operand, lookup, global_name, passthrough)
        if type(value) in (int, float):
            return -value if isinstance(node.op, ast.USub) else value
        return _UNKNOWN
    if (isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div))):
        left = _constant_value(node.left, lookup, global_name, passthrough)
        right = _constant_value(node.right, lookup, global_name, passthrough)
        if (type(left) in (int, float) and type(right) in (int, float)
                and (type(left) is float or type(right) is float)):
            try:
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                return left / right
            except (ArithmeticError, ValueError):
                return _UNKNOWN
        return _UNKNOWN
    if isinstance(node, ast.IfExp):
        test = _constant_value(node.test, lookup, global_name, passthrough)
        if type(test) is bool:
            branch = node.body if test else node.orelse
            return _constant_value(branch, lookup, global_name, passthrough)
        return _UNKNOWN
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return lookup(node.id)
    if isinstance(node, ast.List):
        values = []
        for element in node.elts:
            value = _constant_value(element, lookup, global_name, passthrough)
            if value is _UNKNOWN:
                return _UNKNOWN
            values.append(value)
        return values
    if isinstance(node, ast.Tuple):
        values = []
        for element in node.elts:
            value = _constant_value(element, lookup, global_name, passthrough)
            if value is _UNKNOWN:
                return _UNKNOWN
            values.append(value)
        return tuple(values)
    if isinstance(node, ast.Dict):
        values = {}
        for key_node, value_node in zip(node.keys, node.values):
            if key_node is None:
                return _UNKNOWN
            key = _constant_value(key_node, lookup, global_name, passthrough)
            value = _constant_value(value_node, lookup, global_name, passthrough)
            if key is _UNKNOWN or value is _UNKNOWN:
                return _UNKNOWN
            try:
                values[key] = value
            except TypeError:
                return _UNKNOWN
        return values
    if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
            and node.attr.startswith('f') and node.attr[1:].isdigit()):
        base = _constant_value(node.value, lookup, global_name, passthrough)
        if isinstance(base, tuple):
            index = int(node.attr[1:])
            if index < len(base):
                return base[index]
        return _UNKNOWN
    if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
        base = _constant_value(node.value, lookup, global_name, passthrough)
        if base is _UNKNOWN:
            return _UNKNOWN
        key = _constant_value(node.slice, lookup, global_name, passthrough)
        if key is _UNKNOWN:
            return _UNKNOWN
        try:
            if isinstance(base, (list, tuple, dict, str, bytes)):
                return base[key]
        except (IndexError, KeyError, TypeError):
            return _UNKNOWN
        return _UNKNOWN
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and isinstance(node.func.ctx, ast.Load) and not node.keywords
            and node.func.id.startswith('_AilT_')):
        values = []
        for argument in node.args:
            value = _constant_value(argument, lookup, global_name, passthrough)
            if value is _UNKNOWN:
                return _UNKNOWN
            values.append(value)
        return tuple(values)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and isinstance(node.func.ctx, ast.Load) and global_name(node.func.id)
            and node.func.id in passthrough):
        name, index = passthrough[node.func.id]
        argument = _bound_argument(node, name, index)
        if argument is not None:
            return _constant_value(argument, lookup, global_name, passthrough)
        return _UNKNOWN
    return _UNKNOWN


def _outside_int64_float(value):
    return (type(value) is float and math.isfinite(value)
            and not -(1 << 63) <= int(value) < 1 << 63)


def _bound_argument(node, name, index):
    if index is not None and index < len(node.args):
        return node.args[index]
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _passthrough_functions(tree, module_counts):
    functions = {}
    for fn in tree.body:
        if (not isinstance(fn, ast.FunctionDef) or fn.decorator_list
                or module_counts.get(fn.name) != 1
                or len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return)
                or fn.body[0].value is None):
            continue
        value = fn.body[0].value
        if not isinstance(value, ast.Name) or not isinstance(value.ctx, ast.Load):
            continue
        positional = [arg.arg for arg in (*fn.args.posonlyargs, *fn.args.args)]
        keyword_only = [arg.arg for arg in fn.args.kwonlyargs]
        if value.id in positional:
            functions[fn.name] = (value.id, positional.index(value.id))
        elif value.id in keyword_only:
            functions[fn.name] = (value.id, None)
    return functions


def _parameter_source(node, mapped, passthrough, local):
    if isinstance(node, ast.Name) and node.id in mapped:
        return node.id
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and isinstance(node.func.ctx, ast.Load) and node.func.id in passthrough
            and node.func.id not in local):
        name, index = passthrough[node.func.id]
        argument = _bound_argument(node, name, index)
        if argument is not None:
            return _parameter_source(argument, mapped, passthrough, local)
    return None


def _wrapper_int_params(tree, int_shadowed, module_counts, passthrough):
    candidates = {}
    for fn in tree.body:
        if (not isinstance(fn, ast.FunctionDef) or fn.decorator_list
                or module_counts.get(fn.name) != 1):
            continue
        positional = [arg.arg for arg in (*fn.args.posonlyargs, *fn.args.args)]
        keyword_only = [arg.arg for arg in fn.args.kwonlyargs]
        mapped = {name: index for index, name in enumerate(positional)}
        mapped.update((name, None) for name in keyword_only)
        if not mapped:
            continue
        rebound = {name for name in mapped if _binding_counts(fn.body).get(name, 0)}
        candidates[fn.name] = (fn, mapped, rebound)

    functions = {}
    for name, (fn, mapped, rebound) in candidates.items():
        used = {}
        local = _binding_counts(fn.body)
        for sub in _shallow_walk(fn.body):
            if (not int_shadowed and isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == 'int' and len(sub.args) == 1 and not sub.keywords):
                source = _parameter_source(sub.args[0], mapped, passthrough, local)
                if source is not None and source not in rebound:
                    used[source] = mapped[source]
        if used:
            functions[name] = used

    changed = True
    while changed:
        changed = False
        for name, (fn, mapped, rebound) in candidates.items():
            used = dict(functions.get(name, {}))
            local = _binding_counts(fn.body)
            for sub in _shallow_walk(fn.body):
                if not isinstance(sub, ast.Call) or not isinstance(sub.func, ast.Name):
                    continue
                callee = sub.func.id
                if callee in mapped or callee in local or callee not in functions:
                    continue
                for parameter, index in functions[callee].items():
                    argument = _bound_argument(sub, parameter, index)
                    if argument is None:
                        continue
                    source = _parameter_source(argument, mapped, passthrough, local)
                    if source is not None and source not in rebound:
                        used[source] = mapped[source]
            if used != functions.get(name, {}):
                functions[name] = used
                changed = True
    return functions


class _Int64CallChecker(ast.NodeVisitor):
    def __init__(self, known, passthrough, int_params, int_shadowed):
        self.known = known
        self.passthrough = passthrough
        self.int_params = int_params
        self.int_shadowed = int_shadowed
        self.shadow = []

    def _global_name(self, name):
        return not any(name in scope for scope in self.shadow)

    def _lookup(self, name):
        if not self._global_name(name):
            return _UNKNOWN
        return self.known.get(name, _UNKNOWN)

    def _value(self, node):
        return _constant_value(node, self._lookup, self._global_name, self.passthrough)

    def _refuse(self, node, value):
        error = ValueError(f'int() of a float outside int64: {value!r} (CPython makes a big integer)')
        error.source_line = node.lineno
        error.source_column = node.col_offset
        raise error

    def visit_Call(self, node):
        if (not self.int_shadowed and isinstance(node.func, ast.Name) and node.func.id == 'int'
                and self._global_name('int') and len(node.args) == 1 and not node.keywords):
            value = self._value(node.args[0])
            if _outside_int64_float(value):
                self._refuse(node, value)
        if (isinstance(node.func, ast.Name) and node.func.id in self.int_params
                and self._global_name(node.func.id)):
            for name, index in self.int_params[node.func.id].items():
                argument = _bound_argument(node, name, index)
                if argument is not None:
                    value = self._value(argument)
                    if _outside_int64_float(value):
                        self._refuse(node, value)
        self.generic_visit(node)

    def _visit_outer_arguments(self, args):
        for default in (*args.defaults, *[d for d in args.kw_defaults if d is not None]):
            self.visit(default)
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg):
            if arg is not None and arg.annotation is not None:
                self.visit(arg.annotation)

    def _visit_function(self, node):
        for decorator in node.decorator_list:
            self.visit(decorator)
        self._visit_outer_arguments(node.args)
        if node.returns is not None:
            self.visit(node.returns)
        self.shadow.append(_function_bindings(node))
        for statement in node.body:
            self.visit(statement)
        self.shadow.pop()

    def visit_FunctionDef(self, node):
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_function(node)

    def visit_Lambda(self, node):
        self._visit_outer_arguments(node.args)
        names = [arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)]
        if node.args.vararg is not None:
            names.append(node.args.vararg.arg)
        if node.args.kwarg is not None:
            names.append(node.args.kwarg.arg)
        self.shadow.append(set(names) | set(_binding_counts([node.body])))
        self.visit(node.body)
        self.shadow.pop()

    def visit_ClassDef(self, node):
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword)
        self.shadow.append(set(_binding_counts(node.body)))
        for statement in node.body:
            self.visit(statement)
        self.shadow.pop()

    def _visit_comprehension(self, node):
        names = set()
        for generator in node.generators:
            names |= set(_binding_counts([generator.target]))
        self.shadow.append(names)
        self.generic_visit(node)
        self.shadow.pop()

    def visit_ListComp(self, node):
        self._visit_comprehension(node)

    def visit_SetComp(self, node):
        self._visit_comprehension(node)

    def visit_GeneratorExp(self, node):
        self._visit_comprehension(node)

    def visit_DictComp(self, node):
        self._visit_comprehension(node)


def _fold_float_int_text(text):
    """Rewrite `float(<an exact int constant outside int64>)` to a float literal.

    CPython converts an unbounded int to the nearest double, so `float(10 ** 40)` is
    1e+40 even though the int itself does not fit int64.  Without this fold the int
    constant checks and the front end refuse the valid program.  Only the direct,
    unshadowed builtin form is folded, and only when the conversion is finite; the
    int64 range, an overflowing conversion and a rebound `float` are left alone.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) \
                and node.id == 'float':
            return text
        if isinstance(node, ast.arg) and node.arg == 'float':
            return text
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and node.name == 'float':
            return text
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if (alias.asname or alias.name.split('.')[0]) == 'float':
                    return text

    lines = text.splitlines(keepends=True)

    def offset(line, column):
        return sum(len(item) for item in lines[:line - 1]) + len(
            lines[line - 1].encode('utf-8')[:column].decode('utf-8'))

    spans = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'float' and isinstance(node.func.ctx, ast.Load)
                and len(node.args) == 1 and not node.keywords):
            continue
        ok, value = _constant_int_exact(node.args[0])
        if not ok or value is _CONST_INT_TOO_BIG:
            continue
        if _INT64_MIN <= value <= _INT64_MAX:
            continue
        try:
            converted = float(value)
        except (OverflowError, ValueError):
            continue
        if not math.isfinite(converted):
            continue
        replacement = repr(converted)
        if replacement.startswith('-'):
            # The call is a primary expression, so a bare negative literal would let a
            # following ``**`` bind tighter than the unary minus (``float(-(10**40)) ** 2``).
            replacement = '(' + replacement + ')'
        spans.append((offset(node.lineno, node.col_offset),
                      offset(node.end_lineno, node.end_col_offset), replacement))
    for begin, finish, replacement in sorted(spans, reverse=True):
        text = text[:begin] + replacement + text[finish:]
    return text


def _check_int64_literals(tree):
    global_names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            global_names.update(node.names)
    module_counts = _binding_counts(tree.body)
    known = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            name = node.targets[0].id
            if module_counts.get(name) != 1 or name in global_names:
                continue
            value = _constant_value(node.value, lambda name: known.get(name, _UNKNOWN),
                                    lambda unused: True, {})
            if type(value) in (int, float):
                known[name] = value
    int_shadowed = any((isinstance(node, ast.FunctionDef) and node.name == 'int')
                       or (isinstance(node, ast.arg) and node.arg == 'int')
                       or (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == 'int')
                       for node in ast.walk(tree))
    passthrough = _passthrough_functions(tree, module_counts)
    int_params = _wrapper_int_params(tree, int_shadowed, module_counts, passthrough)
    _Int64CallChecker(known, passthrough, int_params, int_shadowed).visit(tree)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    maxsplit = _maxsplit_constant_nodes(tree)
    nodes = [tree]
    while nodes:
        node = nodes.pop()
        if isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
            _check_index_expression(node.slice)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            _check_constant_power(node, parents, maxsplit)
        if (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub))
                and isinstance(node.operand, ast.Constant) and type(node.operand.value) is int):
            value = -node.operand.value if isinstance(node.op, ast.USub) else node.operand.value
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            value = node.value
        else:
            nodes.extend(ast.iter_child_nodes(node))
            continue
        if not _INT64_MIN <= value <= _INT64_MAX:
            error = ValueError(f'int64 literal out of range: {_constant_diagnostic(value)}')
            error.source_line = node.lineno
            error.source_column = node.col_offset
            raise error


_INT_BINARY = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
}


def _constant_int(node, known, shifts=False):
    """The int value of a constant expression, or None when it is not statically known.
    Names resolve only through known module constants; a local of the same name keeps the
    expression out of known, so a shadowed constant is never folded by mistake.  Shift
    folding is opt-in: only the module/class/default pass asks for it, because the unary
    pass must not start refusing `-(1 << 64)` in an unreached function body."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.Name):
        return known.get(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _constant_int(node.operand, known, shifts)
        if value is None:
            return None
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        left = _constant_int(node.left, known, shifts)
        if left is None:
            return None
        if isinstance(node.op, ast.Pow):
            right = _constant_int(node.right, known, shifts)
            if right is None or right < 0:
                return None
            if abs(left) <= 1:
                return left ** right
            if right > 64:
                return 1 << 64 if left > 0 else -(1 << 64)
            return left ** right
        if shifts and isinstance(node.op, ast.LShift):
            right = _constant_int(node.right, known, shifts)
            if right is None or right < 0:
                return None
            if left == 0:
                return 0
            if right > 64:
                return 1 << 64 if left > 0 else -(1 << 64)
            return left << right
        if shifts and isinstance(node.op, ast.RShift):
            right = _constant_int(node.right, known, shifts)
            if right is None or right < 0:
                return None
            return left >> right
        operation = _INT_BINARY.get(type(node.op))
        if operation is None:
            return None
        right = _constant_int(node.right, known, shifts)
        if right is None:
            return None
        return operation(left, right)
    return None


def _maxsplit_constant_nodes(tree):
    """Nodes under a name-free str.split/rsplit maxsplit argument, whose own front end folds a
    constant and reports an out-of-int64 value with the maxsplit wording."""
    handled = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in ('split', 'rsplit')):
            continue
        roots = []
        if len(node.args) > 1:
            roots.append(node.args[1])
        roots.extend(kw.value for kw in node.keywords if kw.arg == 'maxsplit')
        for root in roots:
            if any(isinstance(inner, ast.Name) for inner in ast.walk(root)):
                continue
            handled.update(id(inner) for inner in ast.walk(root))
    return handled


def _function_scope_stores(function):
    """Names stored in a function's own scope, ignoring nested functions, classes and lambdas."""
    stores = {}

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                stores[child.id] = stores.get(child.id, 0) + 1
            visit(child)

    visit(function)
    return stores


def _function_local_int_constants(function, module_known):
    """The int constants a function's own top-level assignments bind, with module constants
    visible unless the function shadows them.  A name stored more than once, a parameter, or a
    global/nonlocal declaration keeps the name out of the map."""
    arguments = function.args
    parameters = {argument.arg for argument in arguments.posonlyargs + arguments.args + arguments.kwonlyargs}
    if arguments.vararg is not None:
        parameters.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        parameters.add(arguments.kwarg.arg)
    stores = _function_scope_stores(function)
    declared = set()
    for node in ast.walk(function):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            declared.update(node.names)
    local = {name: value for name, value in module_known.items()
             if name not in stores and name not in parameters and name not in declared}

    def bind(target, value_node):
        if not isinstance(target, ast.Name):
            return
        name = target.id
        if stores.get(name) != 1 or name in parameters or name in declared:
            return
        value = _constant_int(value_node, local)
        if value is None:
            try:
                value = _const_expr_int(value_node, bounded=False)
            except _Int64ConstantOverflow:
                value = None
        if value is not None:
            local[name] = value

    for statement in function.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            bind(statement.targets[0], statement.value)
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            bind(statement.target, statement.value)
    return local


def _walk_own_scope(function):
    """Nodes in a function's body, not descending into nested functions, classes or lambdas."""
    stack = list(function.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _known_module_constants(tree):
    """Module names bound once to a statically known int, for the constant-expression checks."""
    stores = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stores[node.id] = stores.get(node.id, 0) + 1
    parameters = {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    known = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or stores.get(target.id) != 1 or target.id in parameters:
            continue
        value = _constant_int(node.value, known)
        if value is None:
            try:
                value = _const_expr_int(node.value, bounded=False)
            except _Int64ConstantOverflow:
                value = None
        if value is not None:
            known[target.id] = value
    return known


def _binds_name(tree, name):
    """Does the program bind `name` anywhere? A user definition of a built-in stops its folding."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del)):
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
        if isinstance(node, ast.arg) and node.arg == name:
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if (alias.asname or alias.name.split('.')[0]) == name:
                    return True
        if isinstance(node, ast.ExceptHandler) and node.name == name:
            return True
        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name == name:
            return True
        if isinstance(node, ast.MatchMapping) and node.rest == name:
            return True
    return False


def _scope_nodes_with_parents(scope):
    """Nodes of one scope (module, function, method) with their parent, stopping at nested
    functions, classes and lambdas (a different scope)."""
    stack = [(node, scope) for node in reversed(scope.body)]
    while stack:
        node, parent = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield node, parent
        for child in reversed(list(ast.iter_child_nodes(node))):
            stack.append((child, node))


def _scope_parameters(function):
    arguments = function.args
    parameters = {argument.arg for argument in arguments.posonlyargs + arguments.args + arguments.kwonlyargs}
    if arguments.vararg is not None:
        parameters.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        parameters.add(arguments.kwarg.arg)
    return parameters


def _scope_declared(function):
    declared = set()
    for node in ast.walk(function):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            declared.update(node.names)
    return declared


def _scope_class_aliases(scope, classes, stores, parameters, declared):
    """name -> class for a name this scope's own top-level statements bind once to a class name."""
    aliases = {}
    for statement in scope.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not (isinstance(target, ast.Name) and isinstance(statement.value, ast.Name)):
            continue
        name, value = target.id, statement.value.id
        if name in classes or name in parameters or name in declared or stores.get(name) != 1:
            continue
        if value in stores or value in parameters or value in declared:
            continue
        if value in classes:
            aliases[name] = value
    return aliases


def _literal_container_classes(value, classes):
    """The class name held at each position of a literal list/tuple or string-keyed dict."""
    if isinstance(value, (ast.List, ast.Tuple)):
        return [item.id if isinstance(item, ast.Name) and item.id in classes else None
                for item in value.elts]
    if isinstance(value, ast.Dict):
        entries = {}
        for key, item in zip(value.keys, value.values):
            if (isinstance(key, ast.Constant) and isinstance(key.value, (str, int))
                    and not isinstance(key.value, bool)
                    and isinstance(item, ast.Name) and item.id in classes):
                entries[key.value] = item.id
        return entries
    return None


def _scope_class_containers(scope, nodes, classes, stores, parameters, declared):
    """name -> literal class container, for a name bound once and only ever read by indexing (a
    mutation through the name, a call that could mutate it, or another use stops the record)."""
    containers = {}
    assigned = {}
    for statement in scope.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name):
            continue
        entries = _literal_container_classes(statement.value, classes)
        if not entries or target.id in parameters or target.id in declared or stores.get(target.id) != 1:
            continue
        assigned[target.id] = (target, entries)
    for name, (target, entries) in assigned.items():
        touched = False
        for node, parent in nodes:
            if not (isinstance(node, ast.Name) and node.id == name):
                continue
            if node is target:
                continue
            if (isinstance(parent, ast.Subscript) and parent.value is node
                    and isinstance(parent.ctx, ast.Load)):
                continue
            touched = True
            break
        if not touched:
            containers[name] = entries
    return containers


def _constant_index(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, int)
            and not isinstance(node.operand.value, bool)):
        return -node.operand.value
    return None


def _container_class(entries, slice_node):
    if isinstance(entries, list):
        index = _constant_index(slice_node)
        if index is not None and -len(entries) <= index < len(entries):
            return entries[index]
    elif isinstance(entries, dict):
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, (str, int)) \
                and not isinstance(slice_node.value, bool):
            return entries.get(slice_node.value)
    return None


def _attribute_store_targets(node):
    """The ast.Attribute targets of one statement: plain, tuple/list, for, with and comprehension."""
    targets = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
        targets.append(node.target)
    elif isinstance(node, (ast.For, ast.AsyncFor)):
        targets.append(node.target)
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        targets.extend(item.optional_vars for item in node.items if item.optional_vars is not None)
    elif isinstance(node, ast.comprehension):
        targets.append(node.target)
    stack = list(targets)
    while stack:
        current = stack.pop()
        if isinstance(current, (ast.Tuple, ast.List)):
            stack.extend(current.elts)
        elif isinstance(current, ast.Starred):
            stack.append(current.value)
        elif isinstance(current, ast.Attribute):
            yield current


def _refuse_class_attr_target(target, aliases, containers):
    base = target.value
    if isinstance(base, ast.Name) and base.id in aliases:
        rendered = base.id
    elif isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name) \
            and _container_class(containers.get(base.value.id), base.slice) is not None:
        rendered = ast.unparse(base)
    else:
        return
    error = ValueError('assigning the class attribute %s.%s; a class attribute here is a constant'
                       % (rendered, target.attr))
    error.source_line = target.lineno
    error.source_column = target.col_offset
    raise error


def _check_class_attribute_assignment(tree):
    """Refuse a class-attribute store whose base is statically a class, by name.

    The general path keeps a class attribute in a slot it only reads (an instance gets a copy at
    construction), so ``alias.attr = v`` raised AttributeError where CPython updates the class
    object.  A direct class name is refused by the emitters themselves, which leaves the typed
    path's class-attribute support untouched; here an alias of a class, or a class read out of a
    literal list/tuple/dict, is refused at compile time on both builds.  A base that only holds a
    class at run time (a parameter, an attribute, a non-literal container) is refused by the
    runtime under the same name."""
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    if not classes:
        return
    module_stores = _function_scope_stores(tree)
    module_aliases = _scope_class_aliases(tree, classes, module_stores, set(), set())
    module_nodes = list(_scope_nodes_with_parents(tree))
    module_containers = _scope_class_containers(tree, module_nodes, classes, module_stores, set(), set())
    for node, _parent in module_nodes:
        for target in _attribute_store_targets(node):
            _refuse_class_attr_target(target, module_aliases, module_containers)
    for function in (node for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        parameters = _scope_parameters(function)
        declared = _scope_declared(function)
        stores = _function_scope_stores(function)
        shadowed = set(stores) | parameters | declared
        aliases = {name: owner for name, owner in module_aliases.items() if name not in shadowed}
        aliases.update(_scope_class_aliases(function, classes, stores, parameters, declared))
        nodes = list(_scope_nodes_with_parents(function))
        containers = {name: entries for name, entries in module_containers.items()
                      if name not in shadowed}
        containers.update(_scope_class_containers(function, nodes, classes, stores, parameters, declared))
        for node, _parent in nodes:
            for target in _attribute_store_targets(node):
                _refuse_class_attr_target(target, aliases, containers)


def _check_bound_method_values(tree):
    """Refuse reading a user method as a value (a bound method), by name.

    The general path keeps instance fields and looks a method up only for a call, so ``d.g`` as
    a value (stored in a variable or field, printed, or passed on) compiled and then raised
    ``AttributeError: 'D' object has no attribute 'g'`` where CPython makes a bound method.
    Rather than model that object, the read is refused on both builds; a direct ``d.g(...)``
    call, a property, a field of the same name and ``callable(d.g)`` are unchanged.
    """
    classes = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods, bases = set(), []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorators = []
            for decorator in item.decorator_list:
                if isinstance(decorator, ast.Name):
                    decorators.append(decorator.id)
                elif isinstance(decorator, ast.Attribute):
                    decorators.append(decorator.attr)
            if any(name in ('property', 'cached_property', 'getter', 'setter', 'deleter')
                   or name.endswith('_property') for name in decorators):
                continue
            methods.add(item.name)
        classes[node.name] = {'methods': methods, 'fields': set(),
                              'field_values': {}, 'bases': bases}
    if not classes:
        return

    scope_of, scope_parent, func_owner, ctx_of = {}, {}, {}, {}

    def _mark_scope(node, scope, cls_name, func):
        scope_of[id(node)] = scope
        ctx_of[id(node)] = (cls_name, func)
        inner, inner_cls, inner_func = None, cls_name, func
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_owner[id(child)] = node.name
            inner, inner_cls, inner_func = node, node.name, None
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            inner, inner_func = node, node
        if inner is not None:
            scope_parent[inner] = scope
            scope = inner
        for child in ast.iter_child_nodes(node):
            _mark_scope(child, scope, inner_cls, inner_func)

    _mark_scope(tree, tree, None, None)

    assignments = {}

    def _add_assign(targets, value, scope):
        if len(targets) == 1 and isinstance(targets[0], (ast.Tuple, ast.List)) \
                and isinstance(value, (ast.Tuple, ast.List)) \
                and len(targets[0].elts) == len(value.elts):
            for target, val in zip(targets[0].elts, value.elts):
                _add_assign([target], val, scope)
            return
        for target in targets:
            if isinstance(target, ast.Name):
                assignments.setdefault(scope, []).append((target.id, value))

    for item in ast.walk(tree):
        if isinstance(item, ast.Assign):
            _add_assign(item.targets, item.value, scope_of.get(id(item), tree))
        elif isinstance(item, ast.AnnAssign) and item.value is not None:
            _add_assign([item.target], item.value, scope_of.get(id(item), tree))

    def _inherited(name, key, seen):
        info = classes.get(name)
        if info is None or name in seen:
            return set()
        found = set(info[key])
        for base in info['bases']:
            found |= _inherited(base, key, seen | {name})
        return found

    def _bases_of(name, seen=frozenset()):
        info = classes.get(name)
        if info is None or name in seen:
            return set()
        found = set(info['bases'])
        for base in info['bases']:
            found |= _bases_of(base, seen | {name})
        return found

    def _descendants(name):
        return {other for other in classes if other == name or name in _bases_of(other)}

    calls_by_name, calls_by_attr = {}, {}
    for item in ast.walk(tree):
        if not isinstance(item, ast.Call):
            continue
        if isinstance(item.func, ast.Name):
            calls_by_name.setdefault(item.func.id, []).append(item)
        elif isinstance(item.func, ast.Attribute):
            calls_by_attr.setdefault(item.func.attr, []).append(item)

    def _param_names(func):
        args = func.args
        return [arg.arg for arg in args.posonlyargs + args.args]

    def _field_values(name, attr, seen=frozenset()):
        info = classes.get(name)
        if info is None or name in seen:
            return []
        values = list(info['field_values'].get(attr, ()))
        for base in info['bases']:
            values.extend(_field_values(base, attr, seen | {name}))
        return values

    def _classes_of(node, ctx=None, seen=frozenset()):
        if ctx is None:
            ctx = ctx_of.get(id(node), (None, None))
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in classes:
                return {node.func.id}
            return set()
        if isinstance(node, ast.Name):
            cls_name, func = ctx
            if func is not None:
                params = _param_names(func)
                if node.id in params:
                    index = params.index(node.id)
                    if index == 0 and cls_name is not None:
                        return _descendants(cls_name)
                    key = ('param', id(func), node.id)
                    if key in seen:
                        return set()
                    calls = []
                    if id(func) in func_owner:
                        owner = func_owner[id(func)]
                        static = any(isinstance(decorator, ast.Name)
                                     and decorator.id == 'staticmethod'
                                     for decorator in func.decorator_list)
                        if func.name == '__init__':
                            for call in calls_by_name.get(owner, ()):
                                calls.append((call, 1))
                        else:
                            for call in calls_by_name.get(func.name, ()):
                                calls.append((call, 0))
                            for call in calls_by_attr.get(func.name, ()):
                                receiver = call.func.value
                                explicit = isinstance(receiver, ast.Name) \
                                    and receiver.id in classes
                                calls.append((call, 0 if static or explicit else 1))
                    else:
                        func_name = getattr(func, 'name', '')
                        for call in (calls_by_name.get(func_name, ()) if func_name else ()):
                            calls.append((call, 0))
                    found = set()
                    for call, offset in calls:
                        index = params.index(node.id) - offset
                        if index < 0:
                            continue
                        value = None
                        if index < len(call.args):
                            value = call.args[index]
                        else:
                            for keyword in call.keywords:
                                if keyword.arg == node.id:
                                    value = keyword.value
                        if value is not None:
                            found |= _classes_of(value, ctx_of.get(id(call), (None, None)),
                                                 seen | {key})
                    return found
            scope = scope_of.get(id(node), tree)
            key = ('name', id(scope), node.id)
            if key in seen:
                return set()
            seen = set(seen) | {key}
            found = set()
            lookup = scope
            while lookup is not tree:
                values = [value for name, value in assignments.get(lookup, ())
                          if name == node.id]
                if values:
                    for value in values:
                        found |= _classes_of(value, ctx, seen)
                    return found
                parent = scope_parent.get(lookup)
                if parent is None:
                    break
                lookup = parent
            for name, value in assignments.get(tree, ()):
                if name == node.id:
                    found |= _classes_of(value, ctx, seen)
            for item in ast.walk(tree):
                if isinstance(item, ast.arg) and item.arg == node.id \
                        and isinstance(item.annotation, ast.Name) and item.annotation.id in classes \
                        and scope_of.get(id(item)) is scope:
                    found.add(item.annotation.id)
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) \
                        and item.target.id == node.id and isinstance(item.annotation, ast.Name) \
                        and item.annotation.id in classes \
                        and scope_of.get(id(item)) is scope:
                    found.add(item.annotation.id)
            return found
        if isinstance(node, ast.Attribute):
            key = ('attr', id(node))
            if key in seen:
                return set()
            found = set()
            for cls_name in _classes_of(node.value, ctx, seen | {key}):
                for value in _field_values(cls_name, node.attr, frozenset()):
                    found |= _classes_of(value, ctx_of.get(id(value), ctx), seen | {key})
            return found
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            found = set()
            index = _constant_index(node.slice)
            for item in ast.walk(tree):
                if not isinstance(item, ast.Assign):
                    continue
                if not any(isinstance(t, ast.Name) and t.id == node.value.id for t in item.targets):
                    continue
                if isinstance(item.value, (ast.List, ast.Tuple)):
                    elements = item.value.elts
                    if index is not None and -len(elements) <= index < len(elements):
                        found |= _classes_of(elements[index], ctx, seen)
                    else:
                        for elt in elements:
                            found |= _classes_of(elt, ctx, seen)
                elif isinstance(item.value, ast.Dict) and isinstance(node.slice, ast.Constant):
                    for key, value in zip(item.value.keys, item.value.values):
                        if isinstance(key, ast.Constant) and key.value == node.slice.value:
                            found |= _classes_of(value, ctx, seen)
            return found
        return set()

    def _store_attributes(target, value):
        if isinstance(target, ast.Attribute):
            yield target, value
        elif isinstance(target, (ast.Tuple, ast.List)):
            if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts):
                for element, element_value in zip(target.elts, value.elts):
                    yield from _store_attributes(element, element_value)
            else:
                for element in target.elts:
                    yield from _store_attributes(element, None)
        elif isinstance(target, ast.Starred):
            yield from _store_attributes(target.value, None)

    store_targets = []
    setattr_shadowed = _binds_name(tree, 'setattr')
    for item in ast.walk(tree):
        if isinstance(item, ast.Assign):
            for target in item.targets:
                for attribute, value in _store_attributes(target, item.value):
                    store_targets.append((attribute.value, attribute.attr, value))
        elif isinstance(item, ast.AnnAssign) and item.value is not None:
            for attribute, value in _store_attributes(item.target, item.value):
                store_targets.append((attribute.value, attribute.attr, value))
        elif isinstance(item, ast.AugAssign):
            for attribute, value in _store_attributes(item.target, None):
                store_targets.append((attribute.value, attribute.attr, value))
        elif isinstance(item, (ast.For, ast.AsyncFor)):
            for attribute, value in _store_attributes(item.target, None):
                store_targets.append((attribute.value, attribute.attr, value))
        elif isinstance(item, (ast.With, ast.AsyncWith)):
            for entry in item.items:
                if entry.optional_vars is not None:
                    for attribute, value in _store_attributes(entry.optional_vars, None):
                        store_targets.append((attribute.value, attribute.attr, value))
        elif isinstance(item, ast.comprehension):
            for attribute, value in _store_attributes(item.target, None):
                store_targets.append((attribute.value, attribute.attr, value))
        elif (not setattr_shadowed and isinstance(item, ast.Call)
              and isinstance(item.func, ast.Name) and item.func.id == 'setattr'
              and len(item.args) >= 2 and not item.keywords
              and isinstance(item.args[1], ast.Constant)
              and isinstance(item.args[1].value, str)):
            value = item.args[2] if len(item.args) > 2 else None
            store_targets.append((item.args[0], item.args[1].value, value))

    def _add_field(cls_name, attr, value):
        info = classes.get(cls_name)
        if info is None:
            return False
        changed = attr not in info['fields']
        info['fields'].add(attr)
        if value is not None:
            values = info['field_values'].setdefault(attr, [])
            if all(existing is not value for existing in values):
                values.append(value)
                changed = True
        return changed

    for _pass in range(2):
        changed = False
        for base, attr, value in store_targets:
            for cls_name in _classes_of(base, ctx_of.get(id(base), (None, None))):
                changed = _add_field(cls_name, attr, value) or changed
        if not changed:
            break

    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    callable_shadowed = _binds_name(tree, 'callable')
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)):
            continue
        if node.attr in ('__name__', '__class__', '__dict__', '__cause__', '__context__',
                         '__suppress_context__', '__traceback__'):
            continue
        parent = parents.get(id(node))
        if isinstance(parent, ast.Call) and parent.func is node:
            continue
        if (not callable_shadowed and isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Name) and parent.func.id == 'callable'
                and node in parent.args):
            continue
        owners = _classes_of(node.value, ctx_of.get(id(node), (None, None)))
        for owner in owners:
            if node.attr in _inherited(owner, 'methods', frozenset()) \
                    and node.attr not in _inherited(owner, 'fields', frozenset()):
                error = ValueError('not in the subset: a bound method value (%s.%s); reading '
                                   'a method as a value is not kept here, call it directly'
                                   % (owner, node.attr))
                error.source_line = node.lineno
                error.source_column = node.col_offset
                raise error


def _check_int64_abs_constants(tree, known):
    """Refuse a constant ``abs`` whose exact value int64 cannot hold, by name.

    ``abs(-(1 << 63))`` and the literal spelling ``abs(-9223372036854775808)`` used to compile
    and then stop with ``integer overflow`` at run time, where CPython prints the bignum.  The
    argument is folded exactly here; an in-range result keeps the ordinary abs lowering, and a
    program that binds its own ``abs`` is left alone."""
    if _binds_name(tree, 'abs') or 'abs' in known:
        return

    def check(node, scope_known):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'abs'):
            return
        if len(node.args) != 1 or node.keywords or isinstance(node.args[0], ast.Starred):
            return
        value = _constant_int(node.args[0], scope_known)
        if value is None:
            try:
                value = _const_expr_int(node.args[0], bounded=False)
            except _Int64ConstantOverflow:
                value = None
        if value is None:
            return
        result = abs(value)
        if not _INT64_MIN <= result <= _INT64_MAX:
            error = ValueError(f'int64 constant expression out of range: {_constant_diagnostic(result)}')
            error.source_line = node.lineno
            error.source_column = node.col_offset
            raise error

    for node in ast.walk(tree):
        check(node, known)
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = _function_local_int_constants(function, known)
        for node in _walk_own_scope(function):
            check(node, local)


def _pow_aliases(body, initial, stores, parameters):
    """Add names bound once in ``body`` to the builtin ``pow`` (or to an existing alias)."""
    names = set(initial)
    changed = True
    while changed:
        changed = False
        for statement in body:
            if not (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    and isinstance(statement.value, ast.Name)):
                continue
            target, source = statement.targets[0].id, statement.value.id
            if (source in names and target not in names and stores.get(target) == 1
                    and target not in parameters):
                names.add(target)
                changed = True
    return names


def _pow_alias_names(tree):
    """The builtin ``pow`` and names bound once to it in the module scope (``p = pow``)."""
    if _binds_name(tree, 'pow'):
        return set()
    stores = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            stores[node.id] = stores.get(node.id, 0) + 1
    parameters = {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    return _pow_aliases(tree.body, {'pow'}, stores, parameters)


def _walk_module_scope(tree):
    """Nodes at module scope, not descending into functions, classes or lambdas."""
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _check_int64_pow_constants(tree, known):
    """Refuse ``pow(base, exp)`` on constant ints whose exact result leaves int64, by name.

    AIL ints are fixed width, so ``pow(2, 63)`` compiled and then stopped with ``integer
    overflow`` where CPython keeps the bignum.  The two-argument form is folded here (the
    three-argument form reduces modulo its modulus and stays in range); an in-range result,
    a negative exponent (CPython's float answer) and a program that binds its own ``pow``
    are left alone."""
    names = _pow_alias_names(tree)
    if not names:
        return

    def check(node, scope_known, scope_names):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in scope_names):
            return
        if len(node.args) != 2 or node.keywords or any(
                isinstance(argument, ast.Starred) for argument in node.args):
            return
        base = _constant_int(node.args[0], scope_known)
        exponent = _constant_int(node.args[1], scope_known)
        if base is None:
            try:
                base = _const_expr_int(node.args[0], bounded=False)
            except _Int64ConstantOverflow:
                base = None
        if exponent is None:
            try:
                exponent = _const_expr_int(node.args[1], bounded=False)
            except _Int64ConstantOverflow:
                exponent = None
        if base is None or exponent is None or exponent < 0:
            return
        if exponent == 0:
            result = 1
        elif base == 0:
            result = 0
        elif base == 1:
            result = 1
        elif base == -1:
            result = 1 if exponent % 2 == 0 else -1
        elif exponent > 64:
            result = None
        else:
            result = base ** exponent
        if result is not None and _INT64_MIN <= result <= _INT64_MAX:
            return
        shown = 'too large' if result is None else _constant_diagnostic(result)
        error = ValueError(f'int64 constant expression out of range: {shown}')
        error.source_line = node.lineno
        error.source_column = node.col_offset
        raise error

    for node in _walk_module_scope(tree):
        check(node, known, names)
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = _function_local_int_constants(function, known)
        parameters = {argument.arg for argument in
                      function.args.posonlyargs + function.args.args + function.args.kwonlyargs}
        if function.args.vararg is not None:
            parameters.add(function.args.vararg.arg)
        if function.args.kwarg is not None:
            parameters.add(function.args.kwarg.arg)
        scope_names = _pow_aliases(function.body, names,
                                   _function_scope_stores(function), parameters)
        for node in _walk_own_scope(function):
            check(node, local, scope_names)


def _check_int64_unary_constants(tree):
    """Refuse a statically known unary integer constant expression outside int64 by name.
    `-MIN` on a module constant or a nested literal compiles to the fixed-width trap on the
    default build, while CPython prints a bignum; the runtime trap stays for values that only
    reach the unary operation as variables."""
    maxsplit = _maxsplit_constant_nodes(tree)
    known = _known_module_constants(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.UnaryOp) or not isinstance(node.op, (ast.UAdd, ast.USub)):
            continue
        if id(node) in maxsplit:
            continue
        value = _constant_int(node, known)
        if value is not None and not -(1 << 63) <= value < 1 << 63:
            error = ValueError(f'int64 constant expression out of range: {_constant_diagnostic(value)}')
            error.source_line = node.lineno
            error.source_column = node.col_offset
            raise error
    _check_int64_abs_constants(tree, known)


def _int64_holds(value):
    return value is not _CONST_INT_TOO_BIG and _INT64_MIN <= value <= _INT64_MAX


def _names_a_known_constant(node, known):
    return any(isinstance(inner, ast.Name) and inner.id in known for inner in ast.walk(node))


def _known_names_fit_int64(node, known):
    """Whether every statically known name read by the expression is itself within int64."""
    return all(_int64_holds(known[inner.id]) for inner in ast.walk(node)
               if isinstance(inner, ast.Name) and inner.id in known)


class _ReplaceKnownNames(ast.NodeTransformer):
    """Copy an expression with every load of a statically known int replaced by its value."""

    def __init__(self, known):
        self.known = known

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.known:
            return ast.copy_location(ast.Constant(self.known[node.id]), node)
        return node


def _constant_int_exact_with_known(node, known):
    """The exact int a constant expression denotes once known names are substituted, or the
    (False, None) / (True, _CONST_INT_TOO_BIG) answers of _constant_int_exact."""
    expression = _ReplaceKnownNames(known).visit(copy.deepcopy(node))
    return _constant_int_exact(ast.fix_missing_locations(expression))


def _check_int64_local_cancellation(node, known):
    """Refuse a function-local constant expression whose final value fits int64 but a step
    does not.  `a = 2**62; b = a * 2 - 1` computes `a * 2` in int64 and stops with
    `integer overflow` at run time, where CPython's unbounded int prints INT64_MAX.  Only an
    operation step that actually reads a statically known local or module constant is
    considered, so the ordinary literal fold (`2**63 - 1`) and run-time arithmetic are
    unchanged.  A leaf name that is itself out of int64 is left to the ordinary constant
    check, which keeps its existing wording."""
    if not _names_a_known_constant(node, known) or not _known_names_fit_int64(node, known):
        return
    ok, value = _constant_int_exact_with_known(node, known)
    if not ok or not _int64_holds(value):
        return
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.BinOp, ast.UnaryOp)) or not _names_a_known_constant(child, known):
            continue
        child_ok, child_value = _constant_int_exact_with_known(child, known)
        if child_ok and not _int64_holds(child_value):
            shown = 'too large' if child_value is _CONST_INT_TOO_BIG else child_value
            error = ValueError(f'int64 constant expression out of range: {shown}')
            error.source_line = child.lineno
            error.source_column = child.col_offset
            raise error


def _check_int64_local_cancellations(tree):
    """Refuse the local-constant cancellation that used to trap at run time, in every function
    body.  Module constants visible from the function count as known; a name the function
    stores more than once, a parameter, or a global/nonlocal declaration does not."""
    module_known = _known_module_constants(tree)
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = _function_local_int_constants(function, module_known)
        for node in _walk_own_scope(function):
            if isinstance(node, (ast.BinOp, ast.UnaryOp)):
                _check_int64_local_cancellation(node, local)


_CONST_TEXT_LIMIT = 1 << 20


def _constant_container(node, known_text, known_int, known_containers=None):
    """The text values of a literal list/tuple/dict of constant strings, or None."""
    if isinstance(node, (ast.List, ast.Tuple)):
        values = []
        for item in node.elts:
            if isinstance(item, ast.Starred):
                return None
            text = _constant_text(item, known_text, known_int, known_containers)
            if text is None:
                return None
            values.append(text)
        return 'seq', tuple(values)
    if isinstance(node, ast.Dict):
        pairs = []
        for key_node, value_node in zip(node.keys, node.values):
            if key_node is None:
                return None
            key = _constant_text(key_node, known_text, known_int, known_containers)
            if key is None:
                key = _constant_int(key_node, known_int)
            if key is None or not isinstance(key, (str, bytes, int)):
                return None
            text = _constant_text(value_node, known_text, known_int, known_containers)
            if text is None or len(text) > _CONST_TEXT_LIMIT:
                return None
            pairs.append((key, text))
        return 'dict', tuple(pairs)
    return None


def _constant_text(node, known_text, known_int, known_containers=None):
    """The str/bytes a constant expression builds, or None when it is not statically known.
    Only the shapes that cannot have a side effect are folded, and a result above the size
    limit is left to the run-time parser."""
    if isinstance(node, ast.Constant) and type(node.value) in (str, bytes):
        return node.value
    if isinstance(node, ast.Name) and node.id in known_text:
        return known_text[node.id]
    if isinstance(node, ast.Attribute):
        fields = []
        base = node
        while isinstance(base, ast.Attribute):
            field = re.fullmatch(r'f(\d+)', base.attr)
            if field is None:
                break
            fields.append(int(field.group(1)))
            base = base.value
        if (fields and isinstance(base, ast.Call) and isinstance(base.func, ast.Name)
                and base.func.id.startswith('_AilT_') and not base.keywords):
            value_node = base
            for index in reversed(fields):
                if (not isinstance(value_node, ast.Call) or not isinstance(value_node.func, ast.Name)
                        or not value_node.func.id.startswith('_AilT_') or value_node.keywords
                        or index >= len(value_node.args)
                        or any(isinstance(arg, ast.Starred) for arg in value_node.args)):
                    value_node = None
                    break
                value_node = value_node.args[index]
            if value_node is not None:
                return _constant_text(value_node, known_text, known_int, known_containers)
    if isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
        if isinstance(node.value, ast.Name):
            container = (known_containers or {}).get(node.value.id)
        else:
            container = _constant_container(node.value, known_text, known_int, known_containers)
        if container is None:
            return None
        kind, values = container
        if kind == 'seq':
            index = _constant_int(node.slice, known_int)
            if index is None or not -len(values) <= index < len(values):
                return None
            return values[index]
        key = _constant_text(node.slice, known_text, known_int, known_containers)
        if key is None:
            key = _constant_int(node.slice, known_int)
        for found, text in reversed(values):
            if type(found) is type(key) and found == key:
                return text
        return None
    if not isinstance(node, ast.BinOp):
        return None
    if isinstance(node.op, ast.Add):
        left = _constant_text(node.left, known_text, known_int, known_containers)
        right = _constant_text(node.right, known_text, known_int, known_containers)
        if type(left) is not type(right) or type(left) not in (str, bytes):
            return None
        if len(left) + len(right) > _CONST_TEXT_LIMIT:
            return None
        return left + right
    if isinstance(node.op, ast.Mult):
        text = _constant_text(node.left, known_text, known_int, known_containers)
        count = _constant_int(node.right, known_int) if text is not None else None
        if text is None:
            text = _constant_text(node.right, known_text, known_int, known_containers)
            count = _constant_int(node.left, known_int)
        if text is None or count is None or count < 0:
            return None
        if len(text) * count > _CONST_TEXT_LIMIT:
            return None
        return text * count
    return None


def _check_int64_int_base_constants(tree):
    """Refuse `int(<constant text>[, <constant base>])` when the parsed value leaves int64.
    AIL ints are fixed width, so the conversion would stop with `integer overflow` where
    CPython keeps the bignum; a value that fits keeps its run-time parse.  A call with no
    explicit base uses CPython's base 10."""
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.alias):
            bound.add(node.asname or node.name.split('.')[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
    if 'int' in bound:
        return
    stores = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            stores[node.id] = stores.get(node.id, 0) + 1
    parameters = {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    escaped = set()
    pure_calls = {'len', 'print', 'str', 'repr'}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)):
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.Subscript) and parent.value is node and isinstance(parent.ctx, ast.Load):
            continue
        if (isinstance(parent, ast.Call) and node in parent.args
                and isinstance(parent.func, ast.Name) and parent.func.id in pure_calls
                and parent.func.id not in bound):
            continue
        if (isinstance(parent, ast.Assign) and parent.value is node and len(parent.targets) == 1
                and isinstance(parent.targets[0], ast.Name)):
            continue
        escaped.add(node.id)
    aliases = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Name)):
            continue
        aliases.setdefault(node.targets[0].id, set()).add(node.value.id)
    changed = bool(aliases)
    while changed:
        changed = False
        for target, sources in aliases.items():
            for source in sources:
                if target in escaped and source not in escaped:
                    escaped.add(source)
                    changed = True
                if source in escaped and target not in escaped:
                    escaped.add(target)
                    changed = True
    known_text, known_int, known_containers = {}, {}, {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or stores.get(target.id) != 1 or target.id in parameters:
            continue
        container = _constant_container(node.value, known_text, known_int, known_containers)
        if container is None and isinstance(node.value, ast.Name):
            container = known_containers.get(node.value.id)
        if container is not None and target.id not in escaped:
            known_containers[target.id] = container
        text = _constant_text(node.value, known_text, known_int, known_containers)
        if text is not None:
            known_text[target.id] = text
        value = _constant_int(node.value, known_int)
        if value is not None:
            known_int[target.id] = value
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'int'):
            continue
        if len(node.args) == 2 and not node.keywords:
            text_node, base_node = node.args
        elif (len(node.args) == 1 and len(node.keywords) == 1
              and node.keywords[0].arg == 'base'):
            text_node, base_node = node.args[0], node.keywords[0].value
        elif len(node.args) == 1 and not node.keywords:
            text_node, base_node = node.args[0], None
        else:
            continue
        if isinstance(text_node, ast.Starred):
            continue
        if base_node is None:
            base = 10
        else:
            base = _constant_int(base_node, known_int)
            if base is None or base != 0 and not 2 <= base <= 36:
                continue
        text = _constant_text(text_node, known_text, known_int, known_containers)
        if text is None:
            continue
        try:
            value = int(text, base)
        except (ValueError, TypeError, OverflowError, MemoryError):
            continue
        if _INT64_MIN <= value <= _INT64_MAX:
            continue
        shown = value if -10 ** 99 < value < 10 ** 99 else 'too large'
        error = ValueError(f'int64 constant expression out of range: {shown}')
        error.source_line = node.lineno
        error.source_column = node.col_offset
        raise error


_CONST_INT_TOO_BIG = object()
_CONST_INT_BITS = 1 << 20
_CONST_INT_SPECIAL_BITS = 1 << 24


def _constant_int_exact(node, _limit=_CONST_INT_BITS):
    """The exact int a constant expression denotes, with a guard against huge intermediates.
    An absorbing zero, a zero left shift and the pow bases 0/1/-1 are decided before the
    fold-limit guard (the same 2**20-bit width as the shared int and maxsplit folders), as in
    pyfront.int_constant; the other operand of such a power is retried at the special-exponent
    limit, so a huge exponent still yields its sign and parity."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return True, node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
        ok, value = _constant_int_exact(node.operand, _limit)
        if not ok:
            return False, None
        if value is _CONST_INT_TOO_BIG:
            return True, _CONST_INT_TOO_BIG
        if isinstance(node.op, ast.USub):
            return True, -value
        if isinstance(node.op, ast.UAdd):
            return True, value
        return True, ~value
    if not isinstance(node, ast.BinOp) or type(node.op) not in (
            ast.Add, ast.Sub, ast.Mult, ast.Pow, ast.LShift, ast.RShift,
            ast.FloorDiv, ast.Mod, ast.BitAnd, ast.BitOr, ast.BitXor):
        return False, None
    left_ok, left = _constant_int_exact(node.left, _limit)
    right_ok, right = _constant_int_exact(node.right, _limit)
    if not (left_ok and right_ok):
        return False, None
    try:
        if isinstance(node.op, ast.Pow):
            if right is _CONST_INT_TOO_BIG:
                if left not in (0, 1, -1):
                    return True, _CONST_INT_TOO_BIG
                right_ok, right = _constant_int_exact(node.right, _CONST_INT_SPECIAL_BITS)
                if not right_ok:
                    return False, None
                if right is _CONST_INT_TOO_BIG:
                    return True, _CONST_INT_TOO_BIG
            if right < 0:
                return False, None
            if right == 0:
                value = 1
            elif left is _CONST_INT_TOO_BIG:
                return True, _CONST_INT_TOO_BIG
            elif left == 0:
                value = 0
            elif left == 1:
                value = 1
            elif left == -1:
                value = 1 if right % 2 == 0 else -1
            elif left.bit_length() * right > _limit:
                return True, _CONST_INT_TOO_BIG
            else:
                value = left ** right
        elif left is _CONST_INT_TOO_BIG or right is _CONST_INT_TOO_BIG:
            if isinstance(node.op, (ast.Mult, ast.BitAnd)) and (left == 0 or right == 0):
                value = 0
            else:
                return True, _CONST_INT_TOO_BIG
        elif isinstance(node.op, ast.LShift):
            if right < 0:
                return False, None
            if left == 0:
                value = 0
            elif right > _limit or left.bit_length() + right > _limit:
                return True, _CONST_INT_TOO_BIG
            else:
                value = left << right
        elif isinstance(node.op, ast.RShift):
            if right < 0:
                return False, None
            value = (0 if left >= 0 else -1) if right > _limit else left >> right
        elif isinstance(node.op, (ast.FloorDiv, ast.Mod)):
            if right == 0:
                return False, None
            value = left // right if isinstance(node.op, ast.FloorDiv) else left % right
        elif isinstance(node.op, ast.Mult):
            if left == 0 or right == 0:
                value = 0
            elif left.bit_length() + right.bit_length() > _limit:
                return True, _CONST_INT_TOO_BIG
            else:
                value = left * right
        elif isinstance(node.op, ast.Add):
            value = left + right
        elif isinstance(node.op, ast.Sub):
            value = left - right
        elif isinstance(node.op, ast.BitAnd):
            value = left & right
        elif isinstance(node.op, ast.BitOr):
            value = left | right
        else:
            value = left ^ right
    except (ArithmeticError, ValueError, OverflowError):
        return True, _CONST_INT_TOO_BIG
    return True, value


def _check_int64_constants(tree):
    """Refuse a constant integer expression outside int64 in a module/class assignment or a
    default argument, where the construct used to compile and trap at run time. Function and
    lambda bodies are left to the existing run-time stop and to _check_int64_literals, and a
    class body keeps _check_constant_power's own wording for a bare `**` value it can fold;
    `_const_expr_int` cannot fold an exponent above 64, so that case is checked here."""
    def check_value(node):
        ok, value = _constant_int_exact(node)
        if not ok:
            return
        if value is not _CONST_INT_TOO_BIG and -(1 << 63) <= value < 1 << 63:
            return
        if value is _CONST_INT_TOO_BIG:
            shown = 'too large'
        else:
            try:
                shown = str(value)
            except ValueError:
                shown = 'too large'
        error = ValueError(f'int64 constant expression out of range: {shown}')
        error.source_line = getattr(node, 'lineno', None)
        error.source_column = getattr(node, 'col_offset', None)
        raise error

    def defers_to_power(value, in_class):
        return (in_class and isinstance(value, ast.BinOp) and isinstance(value.op, ast.Pow)
                and _const_expr_int(value, bounded=False) is not None)

    def walk(node, in_class=False):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for default in list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]:
                check_value(default)
            return
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                walk(base)
            for keyword in node.keywords:
                walk(keyword.value)
            if node.bases:
                return
            for statement in node.body:
                walk(statement, True)
            return
        if isinstance(node, ast.Assign):
            if not defers_to_power(node.value, in_class):
                check_value(node.value)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if not defers_to_power(node.value, in_class):
                check_value(node.value)
        for child in ast.iter_child_nodes(node):
            walk(child, in_class)

    for statement in tree.body:
        walk(statement)


def _check_int64_constant_positions(tree):
    """Refuse an out-of-int64 integer constant written in a module, class or default position.
    A module constant, a class attribute or a default is evaluated when the module is built, so
    `X = 1 << 64` leaves the fixed-width run with `integer overflow` while CPython keeps a bignum.
    Only the outermost constant expression of each such value is checked, so an expression whose
    intermediate leaves int64 but whose result fits (for example `(1 << 63) - 1`) is unchanged."""
    maxsplit = _maxsplit_constant_nodes(tree)
    stores = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stores[node.id] = stores.get(node.id, 0) + 1
    parameters = {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    known = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or stores.get(target.id) != 1 or target.id in parameters:
            continue
        value = _constant_int(node.value, known, shifts=True)
        if value is not None:
            known[target.id] = value

    def roots(node):
        if isinstance(node, (ast.BinOp, ast.UnaryOp)):
            yield node
            return
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for item in node.elts:
                yield from roots(item)
            return
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is not None:
                    yield from roots(key)
                yield from roots(value)
            return
        if isinstance(node, ast.IfExp):
            yield from roots(node.body)
            yield from roots(node.orelse)
            return
        if isinstance(node, ast.Call):
            for item in node.args:
                yield from roots(item)
            for keyword in node.keywords:
                yield from roots(keyword.value)
            return
        if isinstance(node, ast.Starred):
            yield from roots(node.value)

    def scope(body):
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(stmt, ast.ClassDef):
                yield from scope(stmt.body)
                continue
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                if stmt.value is not None:
                    yield stmt.value
            elif isinstance(stmt, ast.Expr):
                yield stmt.value
            for field in ('body', 'orelse', 'finalbody'):
                block = getattr(stmt, field, None)
                if isinstance(block, list) and block and all(isinstance(item, ast.stmt) for item in block):
                    yield from scope(block)
            if isinstance(stmt, ast.Try):
                for handler in stmt.handlers:
                    yield from scope(handler.body)

    values = list(scope(tree.body))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            values.extend(node.args.defaults)
            values.extend(item for item in node.args.kw_defaults if item is not None)
    for value in values:
        for node in roots(value):
            if id(node) in maxsplit:
                continue
            number = _constant_int(node, known, shifts=True)
            if number is not None and not -(1 << 63) <= number < 1 << 63:
                error = ValueError(f'int64 constant expression out of range: {number}')
                error.source_line = node.lineno
                error.source_column = node.col_offset
                raise error


_GENEXPR_HASH_REFUSAL = (
    'a generator expression used as a hash key is not supported: '
    'AIL stores it as a list (no generator identity hash or repr)')


def _hashed_genexpr(node, shadowed):
    """The generator expression in a value a set or dict must hash, or None.

    A tuple is hashed element by element, and a tuple()/frozenset() call hashes the elements of a
    collection argument; a generator-expression argument to either is consumed, not hashed. A list,
    set or dict nested in a key is itself unhashable in CPython, so nothing beneath it is reached.
    `shadowed` names are bound by the program, so a call of that name is not the builtin."""
    if isinstance(node, ast.GeneratorExp):
        return node
    if isinstance(node, ast.Tuple):
        for elt in node.elts:
            found = _hashed_genexpr(elt, shadowed)
            if found is not None:
                return found
    if isinstance(node, ast.IfExp):
        return _hashed_genexpr(node.body, shadowed) or _hashed_genexpr(node.orelse, shadowed)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ('tuple', 'frozenset') and node.func.id not in shadowed):
        for arg in node.args:
            if isinstance(arg, (ast.List, ast.Tuple, ast.Set)):
                for elt in arg.elts:
                    found = _hashed_genexpr(elt, shadowed)
                    if found is not None:
                        return found
    return None


def _bound_names(tree):
    """Every name the program binds anywhere (a conservative over-approximation).

    A name bound in any scope may resolve to that binding where a checked call appears, so the
    static refusal must not treat such a call as the builtin. Over-approximating only moves a
    genuinely-builtin case to the run-time refusal, which names the same construct."""
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name != '*':
                    bound.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bound.add(node.rest)
    return bound


def _check_genexpr_hash_keys(tree):
    """Refuse a generator expression that a set or dict must hash, by name.

    Both emitters materialise a generator expression as an eager list (pre166), so the object is
    unhashable where CPython hashes the generator by identity, and showing it prints the list
    instead of `<generator object <genexpr> at 0x...>`. A static display/`hash` form is refused
    here on both builds; a value reaching the hash at run time is refused by the runtime."""
    def refuse(node):
        error = ValueError(_GENEXPR_HASH_REFUSAL)
        error.source_line = node.lineno
        error.source_column = node.col_offset
        raise error

    shadowed = _bound_names(tree) & {'hash', 'set', 'frozenset', 'tuple'}

    def check_key(key):
        found = _hashed_genexpr(key, shadowed)
        if found is not None:
            refuse(found)

    for node in ast.walk(tree):
        if isinstance(node, ast.Set):
            for elt in node.elts:
                check_key(elt)
        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if key is not None:
                    check_key(key)
        elif isinstance(node, ast.SetComp):
            check_key(node.elt)
        elif isinstance(node, ast.DictComp):
            check_key(node.key)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == 'hash' and node.func.id not in shadowed:
                for arg in node.args:
                    check_key(arg)
            elif node.func.id in ('set', 'frozenset') and node.func.id not in shadowed:
                for arg in node.args:
                    if isinstance(arg, (ast.List, ast.Tuple, ast.Set)):
                        for elt in arg.elts:
                            check_key(elt)


def _returns_on_every_path(statements):
    def loop_exit(body):
        pending = list(body)
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.Break, ast.Continue)):
                return True
            if isinstance(node, (ast.For, ast.While)):
                pending.extend(node.orelse)
            elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                pending.extend(ast.iter_child_nodes(node))
        return False

    return any(
        isinstance(node, (ast.Return, ast.Raise))
        or (isinstance(node, ast.If) and bool(node.orelse)
            and _returns_on_every_path(node.body)
            and _returns_on_every_path(node.orelse))
        or (isinstance(node, ast.Try)
            and (_returns_on_every_path(node.finalbody)
                 or not loop_exit(node.finalbody)
                 and all(_returns_on_every_path(handler.body) for handler in node.handlers)
                 and (_returns_on_every_path(node.body)
                      or bool(node.orelse) and _returns_on_every_path(node.orelse))))
        for node in statements)


ZIG_TARGETS = {'linux': 'x86_64-linux-gnu', 'linux-arm64': 'aarch64-linux-gnu',
               'windows': 'x86_64-windows-gnu', 'macos': 'aarch64-macos', 'macos-x86_64': 'x86_64-macos'}


def _zig_compiler(target):
    """A one-file C compiler command that runs `zig cc -target <triple>`, for $PIPE_CC.

    zig bundles the C libraries of every target, so one install builds Linux, Windows and macOS
    executables from any host. The wrapper lives in a temporary directory for this process."""
    import atexit, shutil, stat, tempfile
    zig = os.environ.get('AIL_ZIG') or shutil.which('zig')
    if not zig:
        local = Path.home() / 'tools' / 'zig' / ('zig.exe' if os.name == 'nt' else 'zig')
        zig = str(local) if local.is_file() else None
    if not zig:
        raise SystemExit('--target needs zig: set $AIL_ZIG, put zig on PATH, or unpack it to ~/tools/zig')
    directory = Path(tempfile.mkdtemp(prefix='ail-zigcc-'))
    atexit.register(shutil.rmtree, directory, True)
    triple = ZIG_TARGETS[target]
    if os.name == 'nt':
        wrapper = directory / 'zigcc.cmd'
        wrapper.write_text('@"%s" cc -target %s %%*\r\n' % (zig, triple), encoding='utf-8')
    else:
        wrapper = directory / 'zigcc'
        wrapper.write_text('#!/bin/sh\nexec "%s" cc -target %s "$@"\n' % (zig, triple), encoding='utf-8')
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return str(wrapper)


def _check_main_called(tree):
    """Python-surface programs: CPython runs nothing for a `main` that is defined and never
    called, so this compiler (whose entry convention would call it) refuses instead of printing
    what CPython would not. `main()`, `sys.exit(main())` and `raise SystemExit(main())` count as
    calls; a call inside `main` itself (recursion) does not."""
    mains = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main']
    if not mains:
        return
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'main'
                and not any(m.lineno <= node.lineno <= m.end_lineno for m in mains)):
            return
    error = ValueError('main() is defined but never called, so CPython would run nothing and this '
                       'compiler refuses rather than run it.\n'
                       '  write instead: add `main()` as the last line of the file '
                       '(or `if __name__ == "__main__": main()`)')
    error.source_line, error.source_column = mains[0].lineno, mains[0].col_offset
    raise error


# third-party modules whose refusal elsewhere names the standard-library replacement (regex -> re)
_IMPORT_HINTS = {'regex'}


def _check_importable(tree):
    """A top-level `import X` / `from X import ...` whose X is neither in the standard library nor on the search
    path (a third-party package, a typo): CPython stops with ModuleNotFoundError at that line, and a program that
    never uses the name would otherwise be built and run. (Local modules were merged away before this; an import
    inside `try:`, a function or `if` is not looked at, so `try: import numpy ... except ImportError` keeps its
    meaning. `_ail_*` names are the compiler's own markers, such as the one the threads rewrite adds.)"""
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            root = name.split('.')[0]
            if root in sys.stdlib_module_names or root in ail_modules.MODELLED or root == 'ail_ffi' or root.startswith('_ail_') or root in _IMPORT_HINTS:
                continue
            error = ValueError(
                "import of %r is not available: it is not part of the standard library and no module of that name "
                "is on the search path, so CPython stops here with ModuleNotFoundError.\n"
                "  write instead: drop the import and write what you need by hand with plain lists, dicts and "
                "loops" % name)
            error.source_line, error.source_column = node.lineno, node.col_offset
            raise error


def _ffi_session(args):
    """The G4 session that lowers `@extern` stubs (ail_ffi_lower.py), closed when the process ends."""
    import atexit
    import ail_ffi_lower
    session = ail_ffi_lower.Session(forbid=getattr(args, 'no_ffi', False))
    atexit.register(session.close)
    return session


def _refuse_load(error):
    """Print a load-time refusal as `path:line:col: message` (no argparse usage dump) and exit 2.
    The position comes from the failing check (`error.refusal`) when the loader found one."""
    refusal = getattr(error, 'refusal', None)
    if refusal is None:
        message = str(error)
    else:
        path, line, column, text = refusal
        where = _relpath(path)
        message = '%s:%d:%d: %s' % (path if where.startswith('..') else where, line, column, text)
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _load_sources(source, extra_modules=(), source_syntax='auto', *, module_only=False,
                  separate=False, module_paths=(), origins=None, source_map=None, declarations_only=False, source_bytes=None,
                  notes=None, local_imports=False, ffi=None, prelower=None):
    """Resolve source imports once and validate their shared declaration scope.

    `prelower` rewrites the entry's text right after it is read (ail_export.lower for `--lib`); the
    classes it leaves behind are then allowed in a module-only Python source.

    `local_imports` lets a Python-syntax entry import sibling modules (ail_modules, stage G1): their
    bodies are merged into the entry's text before everything below sees it."""
    search_paths = tuple(dict.fromkeys(Path(path).resolve() for path in module_paths))
    if any(not path.is_dir() for path in search_paths):
        raise ValueError('each --module-path must name an existing directory')
    standard = ROOT / 'language_examples'
    modules = []
    names = set()
    seen = set()
    active = []
    contracts = []
    constants = set()
    functions = []
    unit_map = {}
    unit_locations = {}

    def load(path, *, entry=False):
        path = path.resolve()
        if path in active:
            raise ValueError('AIL module cycle: ' + ' -> '.join(p.name for p in [*active, path]))
        if path in seen:
            return None
        if path.suffix.lower() not in (('.ail', '.py') if entry else ('.ail',)) or not path.is_file():
            raise ValueError(f'AIL module not found: {path}')
        # set before decoding: the error handler below reads it when the bytes are not UTF-8
        syntax = 'python' if path.suffix.lower() == '.py' else source_syntax
        try:
            if source_bytes is None:
                text = path.read_text(encoding='utf-8-sig')
            else:
                data=path.read_bytes();source_bytes[path]=data
                text=data.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
            if prelower is not None and entry:
                text = prelower(text)
            if source_syntax in ('auto', 'ail') and ail_sexpr.detect(text):
                # The S-expression surface is converted to block syntax and then checked exactly
                # like it; positions in diagnostics refer to that block text.
                text = ail_sexpr.to_block(text)
            syntax = ('ail' if detect(text) else 'python') if source_syntax == 'auto' else source_syntax
            if path.suffix.lower() == '.py':
                syntax = 'python'
            merged = None
            if ffi is not None and syntax == 'python':
                # G4: `@extern` stubs become ordinary functions over a generated C object (ail_ffi_lower.py);
                # a file that does not mention ail_ffi is returned untouched
                text = ffi.lower(path, text)
            if local_imports and entry and syntax == 'python' and not module_only:
                merged = ail_modules.merge_program(path, text, **({} if ffi is None else {'read': ffi.read}))
                if merged is not None:
                    _MERGED_ENTRIES[str(path)] = merged
                    text = merged.text
                    for line in merged.notes:
                        print(line, file=sys.stderr)
            imports = []
            declarations = {}
            locations = {}
            if syntax == 'ail':
                text = translate(text, module=module_only or not entry, imports=imports, declarations=declarations, source_map=locations)
            else:
                # Python spellings of built-ins and result contracts (ail_syntax.python_surface);
                # every statement stays on its own line, so positions below are unchanged.
                text = python_surface(text, None if notes is None else notes.setdefault(str(path), []),
                                     library=module_only)
            text = fold_constants(text)
            text = _fold_float_int_text(text)
            tree = ast.parse(text, filename=str(path))
            if syntax == 'python' and entry and not module_only and not declarations_only:
                _check_main_called(tree)
                if local_imports:
                    _check_importable(tree)
            if not declarations_only:
                _check_int64_constants(tree)
                _check_int64_literals(tree)
                _check_int64_constant_positions(tree)
                _check_int64_unary_constants(tree)
                _check_int64_local_cancellations(tree)
                _check_int64_int_base_constants(tree)
                _check_int64_pow_constants(tree, _known_module_constants(tree))
                _check_class_attribute_assignment(tree)
                _check_bound_method_values(tree)
                _check_genexpr_hash_keys(tree)
            if merged is not None and merged.positions:
                locations = dict(merged.positions)
            if source_map is not None:
                if syntax == 'python' and merged is None:
                    for node in ast.walk(tree):
                        if isinstance(node, ast.stmt):
                            position = (node.lineno, len(text.splitlines()[node.lineno - 1].encode('utf8')[:node.col_offset].decode('utf8')) + 1)
                            locations[node.lineno] = None if node.lineno in locations else position
                    locations = {line: position for line, position in locations.items() if position is not None}
                unit_locations[text] = ({line: position for line, position in locations.items()}
                                        if merged is not None and merged.positions else
                                        {line: (str(path), *position) for line, position in locations.items()})
            if origins is not None:
                if syntax == 'python' and merged is None:
                    for owner, fn in ((node.name if isinstance(node, ast.ClassDef) else None, member)
                                      for node in tree.body for member in
                                      (node.body if isinstance(node, ast.ClassDef) else [node])
                                      if isinstance(member, ast.FunctionDef)):
                        key = f'{owner}__{fn.name}' if owner else fn.name
                        column = len(text.splitlines()[fn.lineno - 1].encode('utf8')[:fn.col_offset].decode('utf8')) + 1
                        declarations[key] = None if key in declarations else (fn.lineno, column, f'{owner}.{fn.name}' if owner else fn.name)
                if merged is not None:
                    for owner, fn in ((node.name if isinstance(node, ast.ClassDef) else None, member)
                                      for node in tree.body for member in
                                      (node.body if isinstance(node, ast.ClassDef) else [node])
                                      if isinstance(member, ast.FunctionDef)):
                        key = f'{owner}__{fn.name}' if owner else fn.name
                        where = merged.positions.get(fn.lineno)
                        shown = merged.names.get(fn.name, fn.name)
                        declarations[key] = None if key in declarations or where is None else (
                            where[0], where[1], where[2], f'{owner}.{shown}' if owner else shown)
                for key, declaration in declarations.items():
                    if merged is not None:
                        origins[key] = None if declaration is None or key in origins else declaration
                    else:
                        origins[key] = None if declaration is None or key in origins else (str(path), *declaration)
        except ail_modules.ModuleRefusal:
            raise
        except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
            if hasattr(exc, 'source_line') and merged is not None and exc.source_line in (merged.positions or {}):
                where = merged.positions[exc.source_line]
                exc.source_position = where
                located = ValueError(f'AIL source {where[0]}: line {where[1]}: {exc}')
                located.refusal = (where[0], where[1], where[2], str(exc))
                raise located from exc
            if hasattr(exc, 'source_line'):
                position = locations.get(exc.source_line)
                if syntax == 'python':
                    prefix = text.splitlines()[exc.source_line - 1].encode('utf8')[:exc.source_column]
                    position = (exc.source_line, len(prefix.decode('utf8')) + 1)
                if position is not None:
                    exc.source_position = (str(path), *position)
                if syntax == 'python' and position is not None:
                    # `compile` prints only this message: name the line the check report has.
                    located = ValueError(f'AIL {"source" if entry else "module"} {path}: line {position[0]}: {exc}')
                    located.refusal = (str(path), position[0], position[1], str(exc))
                    raise located from exc
            elif ((isinstance(exc, SyntaxErrorAIL) or syntax == 'python' and type(exc) is SyntaxError)
                  and getattr(exc, 'lineno', None)):
                # a block-syntax or Python syntax error carries its own position
                located = ValueError(f'AIL {"source" if entry else "module"} {path}: {exc}')
                located.refusal = (str(path), exc.lineno, exc.offset or 1,
                                   exc.msg if type(exc) is SyntaxError else str(exc))
                raise located from exc
            raise ValueError(f'AIL {"source" if entry else "module"} {path}: {exc}')
        if syntax == 'ail' and any(isinstance(node, ast.Assign)
                and not _module_constant(node) for node in tree.body):
            raise ValueError('AIL const must be a literal number, string, bytes, or numeric list')
        if syntax == 'ail' and not declarations_only:
            if any(isinstance(node, ast.ClassDef) for node in tree.body):
                contracts.append(path)
            def contract_error(fn, owner, message):
                error = ValueError(message)
                error.source_function = f'{owner}__{fn.name}' if owner else fn.name
                error.diagnostic_code = 'contract'
                return error

            for owner, fn in ((node.name if isinstance(node, ast.ClassDef) else None, member)
                              for node in tree.body for member in
                              (node.body if isinstance(node, ast.ClassDef) else [node])
                              if isinstance(member, ast.FunctionDef)):
                if isinstance(fn.returns, ast.Name) and fn.returns.id == '__ail_checked_void__':
                    if any(isinstance(node, ast.Return) and node.value is not None for node in ast.walk(fn)):
                        raise contract_error(fn, owner, f'AIL function {fn.name}: void function cannot return a value')
                elif fn.returns is not None:
                    if any(isinstance(node, ast.Return) and node.value is None
                           for node in ast.walk(fn)) or not _returns_on_every_path(fn.body):
                        raise contract_error(fn, owner, f'AIL function {fn.name}: annotated return needs a value '
                                     'on every path')
                if fn.returns is not None or any(arg.annotation is not None
                                                  for arg in fn.args.args):
                    contracts.append(path)
        if (module_only or not entry) and ((not tree.body and not imports) or any(not (isinstance(node, ast.FunctionDef)
                or (syntax == 'ail' or prelower is not None) and isinstance(node, ast.ClassDef))
                and not _module_constant(node) for node in tree.body)):
            raise ValueError(f'AIL module needs functions, structs, or literal constants only: {path}')
        if separate and not entry and any(
                isinstance(node, ast.FunctionDef)
                for fn in tree.body if isinstance(fn, ast.FunctionDef)
                for node in ast.walk(fn) if node is not fn):
            raise ValueError(f'AIL separate module cannot contain nested functions: {path}')
        for node in tree.body:
            # a Python-syntax script rebinds a module-level name freely (`values = ...` twice is
            # ordinary Python); only AIL consts and definitions must be unique
            name = (node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else
                    node.targets[0].id if isinstance(node, ast.Assign) and syntax == 'ail'
                    and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) else None)
            if name is not None:
                if name in names:
                    raise ValueError(f'duplicate AIL name: {name}')
                names.add(name)
            if isinstance(node, ast.FunctionDef):
                functions.append(node)
            elif syntax == 'ail' and isinstance(node, ast.Assign) and _module_constant(node):
                constants.add(node.targets[0].id)
        active.append(path)
        for name in imports:
            directories = tuple(dict.fromkeys((path.parent, *search_paths, standard)))
            candidate = next((directory / (name + '.ail') for directory in directories
                              if (directory / (name + '.ail')).exists()
                              or (directory / (name + '.ail')).is_symlink()), None)
            if candidate is None:
                raise ValueError('AIL module not found: %s; searched: %s' % (
                    name, ', '.join(map(str, directories))))
            load(candidate)
        active.pop()
        seen.add(path)
        if not entry:
            modules.append(text)
            if separate:
                unit_map.update({node.name: len(modules) for node in tree.body
                                 if isinstance(node, ast.FunctionDef)})
        return text

    source_text = load(source, entry=True)
    explicit = set()
    for module_arg in extra_modules:
        module = module_arg.resolve()
        if module == source or module in explicit or module.suffix.lower() != '.ail' or not module.is_file():
            raise ValueError('each --module must name a distinct existing .ail file')
        explicit.add(module)
        load(module)
    for fn in functions:
        shadowed = constants.intersection(arg.arg for arg in fn.args.args)
        shadowed.update(node.id for node in ast.walk(fn)
                        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
                        and node.id in constants)
        if shadowed:
            raise ValueError(f'AIL const {min(shadowed)} cannot be rebound or shadowed in a function')
    units = [*modules, source_text]
    if source_map is not None:
        offset = 0
        for text in units:
            source_map.update({offset + line: position for line, position in unit_locations[text].items()})
            offset += text.count('\n') + 2
    return '\n\n'.join(units), bool(contracts), unit_map


def _hand_over_toolchain(cache, environment):
    """Tell the compiler subprocess which toolchain the parent already identified (saves a probe)."""
    if cache is not None:
        compiler = cache.resolve_compiler()
        identity = cache.toolchain(compiler) if compiler else None
        if identity:
            environment['AIL_CACHE_TOOLCHAIN'] = identity + ':' + compiler
    return environment


def _compile_c_key(cache, args, source, text):
    """Cache key of a `compile-c` object: the C source, the interface, every declared header,
    source, assembly file and archive (read the way compile_c reads them), the C API name. None
    when anything is unreadable or outside the source directory; the real build then reports it."""
    try:
        interface = args.interface.resolve(strict=True).read_bytes()
        declared = json.loads(interface)
        root = source.parent
        parts = []
        for field in ('headers', 'sources', 'asm_sources', 'archives'):
            for name in declared.get(field, []):
                path = (root / name).resolve(strict=True)
                if not path.is_relative_to(root) or path == source:
                    return None
                parts += [field, name, path.read_bytes()]
    except (OSError, ValueError, AttributeError, TypeError, RuntimeError):
        return None
    return cache.frontend_key(ROOT / 'python/pkg-v12', 'compile-c', text.encode('utf8'), interface,
                              args.c_api_name or '', *parts)


def _doctor_build_check(report):
    """Check a representative SDK build/run through the public CLI."""
    if not report['python_supported']:
        return {'status': 'failed', 'phase': 'configuration',
                'message': 'AIL compilation requires Python 3.10 or newer'}
    if not report['c_compiler_available']:
        return {'status': 'failed', 'phase': 'configuration',
                'message': 'C compiler is unavailable: ' + str(report['c_compiler_configured'])}
    source = r'''fn main()->int {
 let values:list[int]=[1,2,3]; if sum(values)!=6 { return 1; }
 let buffer=bytearray(b"x"); let buffers:list[bytearray]=[buffer];
 buffers[0].append(121); if bytes(buffer)!=b"xy" { return 2; }
 let listener=tcp_listen("127.0.0.1",0,1);
 try {
  let peers:list[tcpsocket]=[listener]; let flags=tcp_poll(peers,[0],0);
  if len(flags)!=1 or flags[0]!=0 { return 3; }
 } finally { listener.close(); }
 write_stdout_bytes(b"AIL environment\n"); return 0;
}'''
    phase = 'compile'
    try:
        with tempfile.TemporaryDirectory(prefix='ail-doctor-') as directory:
            path = Path(directory)
            input_path = path / 'environment.ail'
            output_path = path / ('environment.exe' if os.name == 'nt' else 'environment')
            input_path.write_text(source, encoding='utf-8')
            result = subprocess.run(
                [sys.executable, '-X', 'utf8', '-B', str(ROOT / 'ail_chatgpt.py'),
                 'compile', str(input_path), '-o', str(output_path)],
                capture_output=True, cwd=ROOT, env={**os.environ, 'AIL_NO_CACHE': '1'}, timeout=120)
            if result.returncode:
                detail = (result.stderr or result.stdout)[:4096].decode('utf-8', errors='replace')
                return {'status': 'failed', 'phase': phase,
                        'message': f'compile exit {result.returncode}: {detail}'}
            if not output_path.is_file():
                return {'status': 'failed', 'phase': phase,
                        'message': 'compile returned success without an executable'}
            phase = 'run'
            result = subprocess.run([str(output_path)], capture_output=True,
                                    cwd=path, timeout=10)
            if result.returncode:
                detail = (result.stderr or result.stdout)[:4096].decode('utf-8', errors='replace')
                return {'status': 'failed', 'phase': phase,
                        'message': f'run exit {result.returncode}: {detail}'}
            if result.stdout != b'AIL environment\n':
                return {'status': 'failed', 'phase': phase,
                        'message': 'stdout mismatch: expected AIL environment followed by LF; actual '
                        + repr(result.stdout[:4096])}
            if result.stderr:
                return {'status': 'failed', 'phase': phase,
                        'message': 'unexpected stderr: '
                        + result.stderr[:4096].decode('utf-8', errors='replace')}
    except subprocess.TimeoutExpired as error:
        detail = (error.stderr or b'')[:4096]
        if isinstance(detail, bytes):
            detail = detail.decode('utf-8', errors='replace')
        return {'status': 'failed', 'phase': phase,
                'message': f'{phase} timed out after {error.timeout} seconds: {detail}'}
    except OSError as error:
        return {'status': 'failed', 'phase': phase, 'message': str(error)[:4096]}
    return {'status': 'passed', 'phase': 'run',
            'message': 'Representative SDK compile/runtime check passed'}


def _source_interface(tree, symbols=(), types_used=False):
    """Declared signatures only; absent annotations remain unknown, never inferred."""
    def annotation(node):
        if node is None:
            return None
        text = ast.unparse(node)
        if text.startswith('__ail_checked_'):
            text = text[len('__ail_checked_'):]
            if text.endswith('__'):
                text = text[:-2]
        return 'list[float]' if text == 'flist' else text

    def function(node):
        positional = [*node.args.posonlyargs, *node.args.args]
        defaults = [None] * (len(positional) - len(node.args.defaults)) + node.args.defaults
        parameters = [dict(name=arg.arg, type=annotation(arg.annotation),
                           kind='positional_only' if i < len(node.args.posonlyargs) else 'positional',
                           default=ast.unparse(default) if default is not None else None)
                      for i, (arg, default) in enumerate(zip(positional, defaults))]
        for arg, kind, default in [
                *((arg, 'keyword_only', default) for arg, default in
                  zip(node.args.kwonlyargs, node.args.kw_defaults)),
                *((arg, kind, None) for arg, kind in
                  ((node.args.vararg, 'variadic'), (node.args.kwarg, 'variadic_keyword')) if arg)]:
            parameters.append(dict(name=arg.arg, type=annotation(arg.annotation), kind=kind,
                                   default=ast.unparse(default) if default is not None else None))
        return dict(name=node.name, parameters=parameters, returns=annotation(node.returns))

    structs = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            constructor = next((fn for fn in node.body if isinstance(fn, ast.FunctionDef)
                                and fn.name == '__init__'), None)
            parameters = {} if constructor is None else {arg.arg: arg.annotation for arg in constructor.args.args[1:]}
            fields = {} if constructor is None else {
                stmt.targets[0].attr: annotation(parameters.get(stmt.value.id)) if isinstance(stmt.value, ast.Name) else None
                for stmt in constructor.body if isinstance(stmt, ast.Assign)}
            structs.append(dict(name=node.name,
                                constructor_parameters=[] if constructor is None else function(constructor)['parameters'][1:],
                                fields=[dict(name=name, type=kind) for name, kind in fields.items()],
                                methods=[function(fn) for fn in node.body
                                         if isinstance(fn, ast.FunctionDef) and fn.name != '__init__']))
    functions = [function(node) for node in tree.body if isinstance(node, ast.FunctionDef)]
    if symbols:
        missing = set(symbols) - {item['name'] for item in functions}
        if missing:
            raise ValueError('unknown interface function: ' + ', '.join(sorted(missing)))
        functions = [item for item in functions if item['name'] in symbols]
    result = dict(scope='loaded_sources', types='declared_annotations', functions=functions, structs=structs)
    if types_used:
        by_name = {item['name']: item for item in structs}
        needed = set()
        pending = [kind for item in functions for kind in
                   [item['returns'], *(param['type'] for param in item['parameters'])]]
        unknown = False
        while pending:
            kind = pending.pop()
            if kind is None:
                unknown = True
                break
            try:
                nodes = list(ast.walk(ast.parse(kind, mode='eval')))
                names = {node.id for node in nodes if isinstance(node, ast.Name)}
                builtins = {'int','float','bool','str','bytes','bytearray','binaryfile','tcpsocket','exception','void','list','dict','tuple','Callable'}
                if (names - builtins - set(by_name) or any(
                        not isinstance(node, (ast.Expression, ast.Name, ast.Load, ast.Subscript, ast.Tuple, ast.List))
                        and not (isinstance(node, ast.Constant) and node.value is None) for node in nodes)):
                    unknown = True
                    break
            except SyntaxError:
                unknown = True
                break
            for name in names.intersection(by_name).difference(needed):
                needed.add(name)
                item = by_name[name]
                pending.extend(field['type'] for field in item['fields'])
                pending.extend(param['type'] for param in item['constructor_parameters'])
                for method in item['methods']:
                    pending.append(method['returns'])
                    pending.extend(param['type'] for index, param in enumerate(method['parameters'])
                                   if index != 0 or param['name'] != 'self')
        result['struct_selection'] = 'all_when_unknown' if unknown else 'reachable_declared_types'
        if not unknown:
            result['structs'] = [item for item in structs if item['name'] in needed]
    return result

def _check_repair_context(args, report, source, original, snapshots):
    """Bind a repair body only to the bytes used by this source check."""
    unavailable = lambda reason: dict(status='unavailable', reason=reason)
    if report['status'] == 'passed':
        return dict(status='not_needed')
    if args.module or args.object:
        return unavailable('explicit_module_or_object')
    diagnostic = report['diagnostics'][0]
    if diagnostic['code'] not in ('type', 'contract'):
        return unavailable('unsupported_diagnostic')
    if not diagnostic['function'] or not diagnostic['path']:
        return unavailable('missing_function_location')
    # Membership precedes any access to a diagnostic path.
    target = next((path for path in snapshots if str(path) == diagnostic['path']), None)
    if target is None:
        return unavailable('source_not_loaded')
    try:
        data = snapshots[target]
        syntax = ('ail' if detect(data.decode('utf8')) else 'python') if args.syntax == 'auto' else args.syntax
        if syntax != 'ail':
            return unavailable('python_source')
        def unchanged():
            return snapshots.get(source) == original and all(
                path.read_bytes() == data for path, data in snapshots.items())
        if not unchanged():
            return unavailable('source_changed')
        from ail_source_context import context
        result = context(data, diagnostic['function'], include_body=True,
                         source_path=target, module_paths=args.module_path, resolve_imports=True)
        if not unchanged():
            return unavailable('source_changed')
        checked_hashes = {str(path): hashlib.sha256(data).hexdigest() for path, data in snapshots.items()}
        if any(checked_hashes.get(path) != digest for path, digest in result['dependency_sha256'].items()):
            return unavailable('source_dependencies_changed')
        result['source_path'] = str(target)
        return result
    except (OSError, UnicodeError, SyntaxError, ValueError, RuntimeError, ImportError, KeyError) as error:
        return unavailable('context_collection_failed: ' + str(error))

def _slow_patterns(text, source_map):
    """Advisory `file:line: slow: ...` lines (ail_slow_patterns); never raises, never fails a build."""
    if os.environ.get('AIL_NO_SLOW_HINTS') or not source_map:
        return []
    try:
        import ail_slow_patterns
        found = ail_slow_patterns.scan(text, source_map, skip_prefixes=(str(ROOT / 'language_examples'),))
        return [ail_slow_patterns.format_warning(item, Path.cwd()) for item in found]
    except Exception:
        return []


_FALLBACK_NOTE = 'note: built on the general path'
_FALLBACK_HINT = '; run with --strict to see why'
_LINE_MARKER = re.compile(r'^ail-source-line: (\d+)\r?\n?', re.M)


def _split_line_marker(text):
    """(text without the compiler's `ail-source-line: N` line, N or None)."""
    found = _LINE_MARKER.search(text or '')
    return (_LINE_MARKER.sub('', text), int(found.group(1))) if found else (text, None)


def _marker_where(source_map, line):
    """`path:line:col` of the combined-source line the compiler named, or None."""
    position = source_map.get(line) if line is not None else None
    if not position:
        return None
    where = _relpath(position[0])
    where = position[0] if where.startswith('..') else where
    return '%s:%s:%s' % (where, position[1], position[2]) if len(position) > 2 and position[2] is not None else '%s:%s' % (where, position[1])


def _fallback_notes(args, source, stderr, locate=True, source_map=None):
    """The compile-time `note: file:line:col: built on the general path (about 20x slower)
    because <typed refusal>; run with --strict ...` lines the compiler printed, positioned like a refusal. Advisory only:
    stdout and the exit status are never affected; AIL_QUIET_FALLBACK=1 silences it."""
    if os.environ.get('AIL_QUIET_FALLBACK') or not stderr or _FALLBACK_NOTE not in stderr:
        return []
    notes = []
    stderr, marked = _split_line_marker(stderr)
    try:
        python = _python_source(args, source.read_bytes())
        for line in stderr.splitlines():
            if not line.startswith(_FALLBACK_NOTE):
                continue
            hint = _FALLBACK_HINT if line.endswith(_FALLBACK_HINT) else ''
            line = line[:len(line) - len(hint)]       # the position lookup reads the refusal text alone
            if python:
                line = python_wording(line)
            if str(source) in _MERGED_ENTRIES:
                line = ail_modules.unmangle(line, _MERGED_ENTRIES[str(source)].names)
            if locate:
                reason = line.split(' because ', 1)[-1]
                located = _locate_refusal(args, source, reason)
                if located != reason and located.endswith(reason):
                    where = located[:-len(reason)].rstrip(': ')
                else:
                    where = _marker_where(source_map or {}, marked)
                if where:
                    line = 'note: %s: built on the general path%s' % (where, line[len(_FALLBACK_NOTE):])
            notes.append(line + hint)
    except Exception:
        return notes
    return notes


def _strict_requested(args):
    """`--strict` or AIL_STRICT=1: build on the typed path or refuse (never the general path)."""
    return bool(getattr(args, 'strict', False)) or str(os.environ.get('AIL_STRICT', '')).strip().lower() not in (
        '', '0', 'off', 'no', 'false')


def _strict_blockers(args, source, objects, python):
    """(blockers, incomplete): every typed-path blocker of the program, with file:line:col, ranked."""
    origins, source_map = {}, {}
    text, _, _ = _load_sources(source, args.module, args.syntax, module_paths=args.module_path,
                               origins=origins, source_map=source_map, local_imports=True)
    names = _MERGED_ENTRIES[str(source)].names if str(source) in _MERGED_ENTRIES else None

    def reword(message):
        if names:
            message = ail_modules.unmangle(message, names)
        return python_wording(message) if python else message

    compiler_path = str(ROOT / 'python/pkg-v12')
    previous_path, previous_bytecode = sys.path[:], sys.dont_write_bytecode
    saved_surface = os.environ.get('AIL_SURFACE')
    try:
        sys.dont_write_bytecode = True
        sys.path.insert(0, compiler_path)
        from pyfunc import Unsupported, to_c
        import strictmode
        external = None
        if objects:
            from module_object import load_objects
            external = load_objects(list(objects))
        if python:
            os.environ['AIL_SURFACE'] = 'python'
        else:
            os.environ.pop('AIL_SURFACE', None)
        blockers, incomplete = strictmode.collect(text, to_c, Unsupported, external=external, reword=reword)
    finally:
        if saved_surface is None:
            os.environ.pop('AIL_SURFACE', None)
        else:
            os.environ['AIL_SURFACE'] = saved_surface
        sys.path[:] = previous_path
        sys.dont_write_bytecode = previous_bytecode
    for blocker in blockers:
        position = source_map.get(blocker.get('line'))
        origin = origins.get(blocker.get('function'))
        path = line = column = None
        if position is not None:
            path, line = position[0], position[1]
            column = position[2] if len(position) > 2 and position[2] is not None else blocker.get('column')
        elif origin is not None:
            path, line, column = origin[0], origin[1], origin[2]
        else:
            path, line, column = str(source), blocker.get('line'), blocker.get('column')
        shown = _relpath(path)
        blocker['path'] = path if shown.startswith('..') else shown
        blocker['line'], blocker['column'] = line, column
        if names:
            for key in ('function', 'statement', 'construct', 'why', 'write_instead'):
                if isinstance(blocker.get(key), str):
                    blocker[key] = ail_modules.unmangle(blocker[key], names)
            blocker['blocks_functions'] = [ail_modules.unmangle(name, names) for name in blocker['blocks_functions']]
    return blockers, incomplete


def _strict_text(blockers, incomplete):
    count = len(blockers)
    lines = ['strict: %d typed-path blocker%s; nothing was built (ranked by the code each one keeps off the typed path)'
             % (count, '' if count == 1 else 's')]
    for blocker in blockers:
        where = blocker['path'] + (':%s' % blocker['line'] if blocker.get('line') else '') + (
            ':%s' % blocker['column'] if blocker.get('line') and blocker.get('column') else '')
        lines.append('')
        lines.append('%d. %s  blocks %d line%s%s' % (
            blocker['rank'], where, blocker['blocks_lines'], '' if blocker['blocks_lines'] == 1 else 's',
            ' (' + ', '.join(blocker['blocks_functions']) + ')' if blocker['blocks_functions'] else ''))
        if blocker.get('statement'):
            lines.append('   code:          ' + blocker['statement'])
        lines.append('   construct:     ' + blocker['construct'])
        lines.append('   why not typed: ' + blocker['why'])
        lines.append('   write instead: ' + blocker['write_instead'])
    if incomplete:
        lines += ['', 'strict: the list may be incomplete (%s)' % incomplete]
    return '\n'.join(lines) + '\n'


def _strict_json(args, source, blockers, incomplete):
    return json.dumps(dict(
        schema='ail.strict/1', status='refused', strict=True, command=args.command, source=str(source),
        exit_code=3, blocker_count=len(blockers), incomplete=incomplete,
        blockers=[{key: blocker.get(key) for key in (
            'rank', 'path', 'line', 'column', 'function', 'statement', 'construct', 'why', 'write_instead',
            'blocks_lines', 'blocks_functions', 'message')} for blocker in blockers]), ensure_ascii=False)


def _strict_refusal(args, source, objects, first_message):
    """Print every blocker (text on stderr, or `ail.strict/1` JSON on stdout with --json); the exit status
    is the refusal's, 3. None when the blockers cannot be collected (the caller prints the first refusal)."""
    try:
        python = _python_source(args, source.read_bytes())
        blockers, incomplete = _strict_blockers(args, source, objects, python)
    except Exception:
        if os.environ.get('AIL_STRICT_DEBUG'):
            import traceback
            traceback.print_exc()
        return None
    if not blockers:
        return None
    if getattr(args, 'json', False):
        print(_strict_json(args, source, blockers, incomplete))
    else:
        sys.stderr.write(_strict_text(blockers, incomplete))
    return 3


def _source_check(args):
    """Read-only strict type/code-generation check; no C build or runtime proof."""
    report = dict(schema='ail.check/1', status='failed', stage='loader', diagnostics=[],
                  link_verified=False, runtime_verified=False, source_sha256=None,
                  checked_functions=None)
    source = args.source
    origins = {}
    source_map = {}
    stage = 'loader'
    dependency = False
    repair_context = getattr(args, 'repair_context', False)
    snapshots = {} if repair_context or getattr(args, 'contracts', False) else None
    original = None
    try:
        if getattr(args, 'api_module', None) is not None:
            name = args.api_module
            if not re.fullmatch(r'[A-Za-z_]\w*', name):
                raise ValueError('invalid bundled API module name: ' + name)
            try:
                manifest = json.loads((ROOT / 'MANIFEST.json').read_text(encoding='utf8'))
            except (json.JSONDecodeError, UnicodeError) as error:
                raise ValueError('invalid bundled API manifest: ' + str(error)) from error
            selected = manifest.get('sdk_files') if isinstance(manifest, dict) else None
            if not isinstance(selected, list) or not all(isinstance(path, str) for path in selected):
                raise ValueError('invalid bundled API manifest: sdk_files must be a list of paths')
            if 'language_examples/' + name + '.ail' not in selected:
                raise ValueError('unknown bundled API module: ' + name)
        source = source.resolve()
        original = source.read_bytes()
        report['source_sha256'] = hashlib.sha256(original).hexdigest()
        if getattr(args, 'contracts', False) and not args.interface:
            raise ValueError('--contracts requires --interface')
        if args.types_used and (not args.interface or not args.symbol):
            raise ValueError('--types-used requires --interface and --symbol')
        if args.symbol and not args.interface:
            raise ValueError('--symbol requires --interface')
        ffi = _ffi_session(args)
        text, _, _ = _load_sources(source, args.module, args.syntax,
                                  module_only=args.library, module_paths=args.module_path, origins=origins, source_map=source_map,
                                  local_imports=True, ffi=ffi,
                                  **({'source_bytes': snapshots} if snapshots is not None else {}))
        check_objects = list(args.object)
        if getattr(args, 'ffi', False):
            report['ffi'] = ffi.listing()
        if ffi.decls:
            dependency = True
            check_objects.append(ffi.build(ROOT / 'ail_chatgpt.py'))
            os.environ['AIL_FFI_SYMBOLS'] = ' '.join(ffi.symbols())
            dependency = False
        report['checked_functions'] = sum(isinstance(node, ast.FunctionDef)
                                          for node in ast.walk(ast.parse(text)))
        compiler_path = str(ROOT / 'python/pkg-v12')
        previous_path = sys.path[:]
        previous_bytecode = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            sys.path.insert(0, compiler_path)
            from pyfunc import Unsupported, to_c
            external = None
            if check_objects:
                dependency = True
                from module_object import load_objects
                external = load_objects(check_objects)
                dependency = False
            stage = 'type'
            saved_surface = os.environ.get('AIL_SURFACE')
            if _python_source(args, original):
                os.environ['AIL_SURFACE'] = 'python'
            else:
                os.environ.pop('AIL_SURFACE', None)
            try:
                to_c(text, strict=True, info={'_want_units': True, '_checked_arrays': True},
                     library=args.library, external=external)
            finally:
                if saved_surface is None:
                    os.environ.pop('AIL_SURFACE', None)
                else:
                    os.environ['AIL_SURFACE'] = saved_surface
        finally:
            sys.path[:] = previous_path
            sys.dont_write_bytecode = previous_bytecode
        if args.interface:
            report['interface'] = _source_interface(ast.parse(text), args.symbol, args.types_used)
            from ail_source_context import language_rules
            report['language_rules'] = language_rules()
            if getattr(args, 'contracts', False):
                from ail_api_contracts import build_contracts
                report['contracts'] = build_contracts(ast.parse(text), report['interface'], source_sha256=report['source_sha256'], snapshots=snapshots, imports_resolved=True)
                if snapshots.get(source) != original or any(path.read_bytes() != data for path, data in snapshots.items()):
                    raise ValueError('source or dependency changed while collecting API contracts')
        report.update(status='passed', stage='type')
        slow = _slow_patterns(text, source_map)
        if slow:
            report['slow_patterns'] = slow
        status = 0
    except (OSError, UnicodeError, SyntaxError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as error:
        # Unsupported inherits the compiler's error type; inspect it without a fallback.
        status = 2 if dependency or isinstance(error, (OSError, ImportError, subprocess.SubprocessError)) else 1
        message = error.refusal[3] if isinstance(error, ail_modules.ModuleRefusal) else str(error)
        if str(source) in _MERGED_ENTRIES:
            message = ail_modules.unmangle(message, _MERGED_ENTRIES[str(source)].names)
        if _python_source(args, original):
            message = python_wording(message)
        configuration = ('each --module-path', 'each --module must', 'AIL module not found:', '--symbol requires --interface', '--contracts requires --interface', '--types-used requires --interface and --symbol', 'unknown interface function:', 'invalid bundled API module name:', 'unknown bundled API module:', 'invalid bundled API manifest:')
        if any(marker in message for marker in configuration):
            status = 2
        code = 'dependency' if dependency or 'AIL module not found:' in message else (
            'io' if isinstance(error, OSError) else 'configuration' if status == 2 else
            'syntax' if stage == 'loader' else 'type')
        path = None
        line = column = None
        if stage == 'loader':
            if isinstance(error, OSError):
                path = str(source)
            current = error
            while current is not None:
                for prefix in ('AIL source ', 'AIL module '):
                    if str(current).startswith(prefix) and ': ' in str(current):
                        candidate = str(current)[len(prefix):].split(': ', 1)[0]
                        if Path(candidate).is_file():
                            path = candidate
                if isinstance(current, SyntaxErrorAIL):
                    line = getattr(current, 'lineno', None)
                    column = getattr(current, 'offset', None)
                elif isinstance(current, SyntaxError) and current.filename:
                    candidate = Path(current.filename)
                    if candidate.is_file():
                        try:
                            original = candidate.read_text(encoding='utf8')
                            syntax = ('ail' if detect(original) else 'python') if args.syntax == 'auto' else args.syntax
                        except (OSError, UnicodeError):
                            syntax = None
                        if syntax == 'python':
                            path, line, column = str(candidate), current.lineno, current.offset
                if getattr(current, 'source_position', None) is not None:
                    path, line, column = current.source_position
                current = current.__cause__ or current.__context__
        function = getattr(error, 'source_function', None)
        location_kind = 'source' if line is not None else None
        origin = origins.get(function)
        if origin is not None:
            path, line, column, function = origin
            location_kind = 'function_declaration'
        position = source_map.get(getattr(error, 'source_line', None))
        if position is not None:
            path, line, column = position
            location_kind = 'source_statement'
        code = getattr(error, 'diagnostic_code', code)
        report.update(stage=stage, diagnostics=[dict(code=code, message=message,
                                                    path=path, line=line, column=column, function=function,
                                                    location_kind=location_kind)])
        if hasattr(error, 'type_details'):
            details = dict(error.type_details)
            callee_origin = origins.get(details.get('callee'))
            if callee_origin is not None:
                details['callee'] = callee_origin[3]
            report['diagnostics'][0]['type_details'] = details
        if hasattr(error, 'repair_hint'):
            report['diagnostics'][0]['repair_hint'] = error.repair_hint
    if repair_context:
        report['repair_context'] = _check_repair_context(args, report, source, original, snapshots)
    print(json.dumps(report, ensure_ascii=False))
    return status

def _surface_env(args, source, env=None):
    """The environment for a compiler run: `AIL_SURFACE=python` for a def-syntax entry, which makes
    the compiler refuse list/dict/set sharing it would otherwise copy (pkg-v12/aliasrefuse.py)."""
    env = dict(os.environ if env is None else env)
    try:
        python = (Path(source).suffix.lower() in ('.ail', '.py')
                  and (Path(source).suffix.lower() == '.py' or _python_source(args, Path(source).read_bytes())))
    except OSError:
        python = False
    if python:
        env['AIL_SURFACE'] = 'python'
    else:
        env.pop('AIL_SURFACE', None)
    return env


def _python_source(args, data):
    """Whether the entry source is written in the Python syntax (refusals are respelled for it)."""
    if getattr(args, 'syntax', 'auto') != 'auto':
        return args.syntax == 'python'
    try:
        text = data.decode('utf8') if isinstance(data, bytes) else data
        return text is not None and not ail_sexpr.detect(text) and not detect(text)
    except Exception:
        return False


def _python_notes(message, notes, source):
    """A Python-syntax refusal followed by what the Python front end left as written."""
    message = message.rstrip('\n')
    if "'math' is read before it is assigned" in message:
        # a math name the Python front end could not map was left as written; say so, not this
        for entries in notes.values():
            named = [text.split(';')[0] for _, text in entries if text.startswith('math.')]
            if named:
                message = message.replace("'math' is read before it is assigned", named[0] + " (see the note below)")
                break
    for entries in notes.values():
        # `import time` followed by a time name the front end could not map: name that, not the import
        named = [text.split(';')[0] for _, text in entries if re.match(r'(time|string|os|operator)\.', text)]
        found = re.search(r"import of '(time|string|os|operator)' is not available[^\n]*\n  write instead: [^\n]*", message)
        if named and found and any(text.startswith(found.group(1) + '.') for _, text in entries):
            message = message.replace(found.group(0), next(n for n in named if n.startswith(found.group(1) + '.'))
                                      + ' (see the note below)')
            break
    # library batch 4 (csv, datetime, ...): the import is refused because a use was not built; say which
    found = re.search(r"import of '(csv|datetime|decimal|fractions|unicodedata|statistics|textwrap|enum|string)'; [^\n]*?by hand",
                      message)
    if found:
        for entries in notes.values():
            named = [text.split(';')[0] for _, text in entries if found.group(1) in text.split(':')[0]]
            if named:
                message = message.replace(found.group(0), named[0] + ' (see the note below)')
                break
    shown = _relpath(source)
    shown = str(source) if shown.startswith('..') else shown
    for path, entries in notes.items():
        where = shown if Path(path) == source else path
        for line, text in entries:
            message += '\nnote: %s:%d: %s' % (where, line, text)
    return message + '\n'


def _text_position(source, message, function=None):
    """(line, column) of the construct a refusal names, found by reading the source text. This is
    the fallback for refusals the type check cannot map to a statement (a signature, an
    annotation): the position of the def, parameter or annotation the message quotes."""
    try:
        lines = Path(source).read_text(encoding='utf8').splitlines()
    except (OSError, UnicodeError):
        return None
    head = message.split('\n', 1)[0]
    head = re.sub(r'^not in the subset: ', '', head)

    def find(pattern, only_defs=False):
        compiled = re.compile(pattern)
        for number, line in enumerate(lines, 1):
            if line.lstrip().startswith(('#', '//')):
                continue
            if only_defs and not re.match(r'\s*(?:def|fn)\s', line):
                continue
            found = compiled.search(line)
            if found:
                return number, found.start() + 1
        return None

    def name_in(pattern):
        found = re.search(pattern, head)
        return re.escape(found.group(1)) if found else None

    named_line = re.match(r'line (\d+): ', head)
    if named_line and int(named_line[1]) <= len(lines):
        at = int(named_line[1])
        return at, len(lines[at - 1]) - len(lines[at - 1].lstrip()) + 1
    nullable = name_in(r'^(\w+) \| None')
    if nullable:
        return find(r'\b%s\s*\|\s*None|Optional\s*\[\s*%s' % (nullable, nullable))
    if 'must take plain positional arguments' in head:
        return find(r'(?:def|fn)\s+\w+\s*\([^)]*(?:\*|,\s*/|/\s*[,)])', only_defs=True)
    default_for = re.search(r"^(\w+)\(\): the default for '(\w+)'", head)
    if default_for:
        at = find(r'(?:def|fn)\s+%s\s*\([^)]*\b%s\b[^)]*=' % default_for.groups(), only_defs=True)
        if at is not None:
            line = lines[at[0] - 1]
            named = re.search(r'\b%s\b\s*[:=]' % re.escape(default_for[2]), line[line.find('('):])
            return (at[0], line.find('(') + named.start() + 1) if named else at
        return find(r'(?:def|fn)\s+%s\b' % default_for[1], only_defs=True)
    annotation = re.search(r'unsupported local annotation (.+?)\.?$', head)
    if annotation:
        squeezed = re.sub(r'\s+', '', annotation[1].rstrip('.'))
        for number, line in enumerate(lines, 1):
            at = re.sub(r'\s+', '', line).find(squeezed)
            if at >= 0:
                return number, max(1, len(line) - len(line.lstrip()) + 1)
        return None
    parameter = name_in(r"^'(\w+)' is annotated")
    if parameter:
        return find(r'\b%s\s*:' % parameter, only_defs=True)
    if head.startswith('a function with no parameters'):
        return find(r'(?:def|fn)\s+\w+\s*\(\s*\)', only_defs=True)
    callee = re.search(r'^(\w+)\(\):', head)
    if callee:
        return find(r'(?:def|fn)\s+%s\b' % callee[1], only_defs=True)
    if function:
        return find(r'(?:def|fn)\s+%s\b' % re.escape(function.split('.')[-1]), only_defs=True)
    return None


def _construct_position(source, message):
    """The position of a construct whose refusal names it, read off the source text. It overrides
    the check's statement mapping, which can point at a later use (the call that reaches a class)."""
    try:
        lines = Path(source).read_text(encoding='utf8').splitlines()
    except (OSError, UnicodeError):
        return None
    head = re.sub(r'^not in the subset: ', '', message.split('\n', 1)[0])
    patterns = ((r"^inheritance \(class '(\w+)'", r'class\s+%s\b'),
                (r"^class '(\w+)' has no __init__", r'class\s+%s\b'),
                (r"^a decorator on class '(\w+)'", r'class\s+%s\b'),
                (r"^a decorator on \w+\.(\w+)", r'def\s+%s\b'),
                (r"^dunder method \w+\.(\w+)", r'def\s+%s\b'),
                (r"^(nonlocal) in a nested function", r'\b%s\b'),
                (r"^(global) in a nested function", r'\b%s\b'))
    for refusal, wanted in patterns:
        found = re.match(refusal, head)
        if found:
            compiled = re.compile(wanted % re.escape(found[1]))
            for number, line in enumerate(lines, 1):
                at = compiled.search(line)
                if at and not line.lstrip().startswith(('#', '//')):
                    return number, at.start() + 1
    return None


def _locate_refusal(args, source, message):
    """Prefix a compile refusal with path:line:col, found by the type check (which maps statements)."""
    command = [sys.executable, '-B', str(Path(__file__).resolve()), 'check', str(source),
               '--syntax', args.syntax]
    for path in args.module_path:
        command += ['-I', str(path)]
    for path in args.module:
        command += ['--module', str(path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        diagnostic = json.loads(result.stdout)['diagnostics'][0]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, TypeError):
        diagnostic = None
    text = (diagnostic or {}).get('message') or ''
    if diagnostic is not None and (not text or text not in message):
        diagnostic = None
    where = (diagnostic or {}).get('path') or str(source)
    relative = _relpath(where)
    if not relative.startswith('..'):
        where = relative
    merged = str(Path(source).resolve()) in _MERGED_ENTRIES      # the entry text alone does not hold the code
    named = None if merged else _construct_position(source, message)
    if named is not None:
        return '%s:%d:%d: %s' % (where, named[0], named[1], message)
    if diagnostic is not None and diagnostic.get('line') is not None:
        where += ':%d' % diagnostic['line']
        if diagnostic.get('column') is not None:
            where += ':%d' % diagnostic['column']
        return '%s: %s' % (where, message)
    # the check could not map the refusal to a statement: read the position off the source text
    position = None if merged else _text_position(source, message, (diagnostic or {}).get('function'))
    if position is None:
        if diagnostic is not None and diagnostic.get('function'):
            return '%s (in %s): %s' % (where, diagnostic['function'], message)
        return message
    return '%s:%d:%d: %s' % (where, position[0], position[1], message)


def _compile_freestanding(args, parser, native_build):
    """`compile --freestanding`: one module to C or an object with no runtime and no libc (python/pkg-v12/freestanding.py)."""
    if args.module or args.object or args.separate or args.static or args.target or args.module_path:
        parser.error('--freestanding builds one module alone; drop --module, --object, --separate, --static, --target and -I')
    source = args.source.resolve()
    output = Path(os.path.abspath(args.output))
    if source.suffix.lower() != '.py' or not source.is_file():
        parser.error('--freestanding takes an existing Python-syntax .py module')
    if output.suffix not in ('.c', '.o'):
        parser.error('--freestanding output must end in .c (C source) or .o (object)')
    header = output.with_suffix('.h')
    for path in (output, header):
        if path.exists() or path.is_symlink():
            parser.error('output already exists: %s' % path)
    if source in (output, header) or not output.parent.is_dir():
        parser.error('output must differ from source, in an existing directory')
    sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
    import freestanding
    try:
        report = freestanding.build(source, output, target='i386' if args.m32 else 'x86_64')
    except freestanding.Refusal as error:
        return native_build.emit(args, {}, 3, 'type', error.text(_relpath(source)))
    except SyntaxError as error:
        return native_build.emit(args, {}, 3, 'syntax', 'AIL freestanding: %s:%s: %s' % (_relpath(source), error.lineno, error.msg))
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        return native_build.emit(args, {}, 2, 'backend', 'AIL freestanding: %s' % error)
    return native_build.emit(args, report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check_cmd = sub.add_parser('check', help='strict source/type check without a C build; exit 0 passed, 1 source error, 2 configuration/I/O/dependency')
    check_cmd.add_argument('source', type=Path)
    check_cmd.add_argument('--syntax', choices=('auto', 'ail', 'python'), default='auto')
    check_cmd.add_argument('-I', '--module-path', action='append', type=Path, default=[])
    check_cmd.add_argument('--module', action='append', type=Path, default=[])
    check_cmd.add_argument('--object', action='append', type=Path, default=[], help='typed object metadata; may query compiler identity, never builds or links')
    check_cmd.add_argument('--library', action='store_true')
    check_cmd.add_argument('--ffi', action='store_true', help='list the C FFI declarations (@extern stubs) of the program')
    check_cmd.add_argument('--no-ffi', action='store_true', help='refuse a program that declares C FFI functions')
    check_cmd.add_argument('--repair-context', action='store_true', help='include SHA-bound failing AIL function body and declared import/API context')
    check_cmd.add_argument('--interface', action='store_true', help='include checked source declarations without function bodies; absent types are null')
    check_cmd.add_argument('--symbol', action='append', default=[], help='select top-level function declarations with --interface; repeatable; struct declarations retained')
    api_cmd = sub.add_parser('api', help='check a bundled source module and return its typed API without compiling C')
    api_cmd.add_argument('api_module', help='bundled module name, without path or .ail suffix')
    builtin_cmd = sub.add_parser('api-builtin', help='query intrinsic signatures and declared ownership without building or running code')
    builtin_cmd.add_argument('symbol', nargs='?', help='builtin name or typed receiver.method; omitted lists the available inventory')
    api_cmd.add_argument('--object', action='append', type=Path, default=[], help='typed object metadata; may query compiler identity, never builds or links')
    api_cmd.add_argument('--symbol', action='append', default=[], help='select top-level functions; structs retained')
    check_cmd.add_argument('--types-used', action='store_true', help='retain structs reachable through selected declared types; unknown types retain all')
    api_cmd.add_argument('--types-used', action='store_true', help='retain structs needed by selected declared types; requires --symbol')
    check_cmd.add_argument('--contracts', action='store_true', help='include declared ownership and conservative static call contracts; requires --interface')
    api_cmd.add_argument('--contracts', action='store_true', help='include declared ownership and conservative static call contracts')
    context_cmd = sub.add_parser('context', help='read a local function declaration and call candidates without type checking')
    context_cmd.add_argument('source', type=Path)
    context_cmd.add_argument('--symbol', required=True)
    context_cmd.add_argument('--include-body', action='store_true')
    context_cmd.add_argument('--contracts', action='store_true', help='include syntax-derived ownership/call contracts without binding or runtime proof')
    context_cmd.add_argument('--compact', action='store_true', help='encode context parameter rows in reversible compact JSON')
    context_cmd.add_argument('--resolve-imports', action='store_true')
    context_cmd.add_argument('-I', '--module-path', action='append', type=Path, default=[])
    edit_cmd = sub.add_parser('edit', help='replace function bodies in a new source/type-checked candidate')
    edit_cmd.add_argument('source', type=Path)
    edit_cmd.add_argument('--symbol')
    edit_cmd.add_argument('--base-sha256', required=True)
    body_input = edit_cmd.add_mutually_exclusive_group(required=True)
    body_input.add_argument('--body', type=Path)
    body_input.add_argument('--body-text', help='replacement body directly; no temporary body file needed')
    body_input.add_argument('--edits-text', help='JSON array of symbol/body strings, checked together')
    edit_cmd.add_argument('--context', type=Path, help='bind the resolved source context and dependency hashes')
    edit_cmd.add_argument('-o', '--output', required=True, type=Path)
    edit_cmd.add_argument('--library', action='store_true')
    edit_cmd.add_argument('-I', '--module-path', action='append', type=Path, default=[])
    edit_cmd.add_argument('--module', action='append', type=Path, default=[])
    edit_cmd.add_argument('--object', action='append', type=Path, default=[])
    doctor_cmd = sub.add_parser('doctor')
    doctor_cmd.add_argument('--check', action='store_true',
                            help='compile and run a representative SDK program to check the C/OS runtime')
    sub.add_parser('integrity')
    sdk_cmd = sub.add_parser('export-sdk', help='copy the verified language compiler and standard sources to a new SDK directory')
    sdk_cmd.add_argument('-o', '--output', type=Path, required=True)
    http_cmd = sub.add_parser('compare-http', help='compare local read-only HTTP commands with exact output checks')
    http_cmd.add_argument('manifest', type=Path)
    http_cmd.add_argument('-o', '--output', required=True, type=Path)
    snapshot_cmd = sub.add_parser('snapshot-http', help='copy declared HTTP inputs for relocated comparison')
    snapshot_cmd.add_argument('manifest', type=Path)
    snapshot_cmd.add_argument('-o', '--output', required=True, type=Path)
    snapshot_cmd.add_argument('--compare', action='store_true',
        help='compare the copied inputs and save result.json inside the new snapshot')
    build_http_cmd = sub.add_parser('build-http', help='build a declared HTTP candidate beside a frozen reference')
    build_http_cmd.add_argument('manifest', type=Path)
    build_http_cmd.add_argument('--recipe', required=True, type=Path)
    build_http_cmd.add_argument('-o', '--output', required=True, type=Path)
    build_http_cmd.add_argument('--compare', action='store_true')
    compile_cmd = sub.add_parser('compile', help='compile AIL source to a standalone executable')
    compile_cmd.add_argument('source', type=Path)
    compile_cmd.add_argument('-o', '--output', required=True, type=Path)
    compile_cmd.add_argument('--module', action='append', type=Path, default=[],
        help='additional .ail file containing functions and literal numeric constants')
    compile_cmd.add_argument('--no-ffi', action='store_true', help='refuse a program that declares C FFI functions (@extern)')
    compile_cmd.add_argument('--debug', action='store_true',
                             help='build for gdb: -g -O0, #line directives back to the .py/.ail source (same code generator as a release build), and an uncaught exception names the last statement run (stderr is then not CPython-compatible)')
    compile_cmd.add_argument('--link', action='append', default=[], metavar='LIB',
                             help='link this library as well, like link("LIB") in the source (a name, or a path to a shared library); repeatable')
    compile_cmd.add_argument('--separate', action='store_true',
        help='compile each typed source into a C object, then link the objects')
    compile_cmd.add_argument('--object', action='append', type=Path, default=[],
        help='link an existing typed .o and its adjacent .o.json without its source')
    compile_cmd.add_argument('--syntax', choices=('auto', 'python', 'ail'), default='auto',
        help='source syntax; auto detects fn/const/use/struct declarations, ail uses brace-delimited blocks')
    compile_cmd.add_argument('--strict', action='store_true',
        help='build on the typed path or refuse, listing every blocker with a rewrite (also AIL_STRICT=1); '
             'with --json the blockers are printed as ail.strict/1 JSON')
    compile_cmd.add_argument('--static', action='store_true',
        help='link the C library statically (larger binary that runs on any Linux); default is dynamic')
    compile_cmd.add_argument('--lib', metavar='NAME',
        help='build the @export functions of the source as a C library: -o DIR receives lib<NAME>.so, '
             'lib<NAME>.a and <NAME>.h (error codes, NAME_last_error(), NAME_free(); see NATIVE_LIBRARIES.md)')
    compile_cmd.add_argument('--target', choices=sorted(ZIG_TARGETS),
        help='cross-compile with zig cc for another OS/CPU (needs zig: $AIL_ZIG, PATH, or ~/tools/zig/zig)')
    compile_cmd.add_argument('--freestanding', action='store_true',
        help='compile one Python-syntax module to C (-o x.c) or an object (-o x.o) that needs no runtime and no libc, '
             'plus a header x.h; see docs/design/FREESTANDING.md')
    compile_cmd.add_argument('--m32', action='store_true',
        help='with --freestanding: target 32-bit x86 (usize is 32 bits, gcc -m32); see docs/design/FREESTANDING.md')
    object_cmd = sub.add_parser('compile-module', help='compile typed functions, scalar structs and scalar constants to a reusable object')
    object_cmd.add_argument('source', type=Path)
    object_cmd.add_argument('-o', '--output', required=True, type=Path)
    object_cmd.add_argument('--syntax', choices=('auto', 'python', 'ail'), default='auto')
    object_cmd.add_argument('--object', action='append', type=Path, default=[],
        help='typed dependency objects; entry linking requires their full object closure')
    object_cmd.add_argument('--c-api-name', help='build a dependency dedicated to this C library name')
    library_cmd = sub.add_parser('compile-library', help='build a C callable library with owned results and error returns')
    library_cmd.add_argument('source', type=Path)
    library_cmd.add_argument('--name', required=True)
    library_cmd.add_argument('-o', '--output', required=True, type=Path)
    library_cmd.add_argument('--syntax', choices=('auto', 'python', 'ail'), default='auto')
    library_cmd.add_argument('--module', action='append', type=Path, default=[],
        help='additional typed .ail source, combined with transitive use dependencies')
    library_cmd.add_argument('--export', action='append',
        help='public function name; repeat to select the C API (default: all functions)')
    library_cmd.add_argument('--object', action='append', type=Path, default=[],
        help='complete closure of objects built with --c-api-name matching --name')
    for command in (compile_cmd, object_cmd, library_cmd):
        command.add_argument('-I', '--module-path', action='append', type=Path, default=[],
            help='use module search directory; local, then -I in order, then bundled standard modules')
    c_cmd = sub.add_parser('compile-c', help='compile trusted C functions to a typed reusable object')
    c_cmd.add_argument('source', type=Path)
    c_cmd.add_argument('--interface', required=True, type=Path)
    c_cmd.add_argument('-o', '--output', required=True, type=Path)
    c_cmd.add_argument('--c-api-name', help='build a dependency dedicated to this C library name')
    for command in (compile_cmd, object_cmd, library_cmd, c_cmd):
        command.add_argument('--json', action='store_true', help='return structured build diagnostics without running the generated program')
        command.add_argument('--debug-dir', type=Path, help='keep native diagnostic reports and generated sources in a new directory')
    for command in (compile_cmd, object_cmd, library_cmd, c_cmd):
        command.add_argument('--no-cache', action='store_true', help='do not read or write the build cache (same as AIL_NO_CACHE=1)')
    cache_cmd = sub.add_parser('cache', help='build cache in $AIL_CACHE (default ~/.cache/ail): stats, path or clear')
    cache_cmd.add_argument('action', choices=('stats', 'path', 'clear'))
    smoke = sub.add_parser('selftest'); smoke.add_argument('--out', required=True)
    build = sub.add_parser('build'); build.add_argument('--project', required=True)
    build.add_argument('--out', required=True); build.add_argument('--candidate-patch')
    build.add_argument('--mode', choices=['original','balanced','speed','memory'], default='original')
    args = parser.parse_args(argv)
    if getattr(args, 'no_cache', False):
        os.environ['AIL_NO_CACHE'] = '1'
    if getattr(args, 'static', False):
        if sys.platform == 'darwin' and not getattr(args, 'target', None):
            parser.error('--static is not supported on macOS: Apple ships no static C library, so the '
                         'linker fails on crt0.o (build a static Linux binary with --target linux, or '
                         'drop --static)')
        os.environ['AIL_STATIC'] = '1'
    if getattr(args, 'target', None):
        os.environ['PIPE_CC'] = _zig_compiler(args.target)
        if args.target == 'windows':
            os.environ['AIL_TARGET_OS'] = 'windows'
        os.environ['AIL_TARGET'] = args.target      # os.path takes the flavour of the target (filelib.target_windows)
    if args.command in ('compile', 'compile-module', 'compile-library', 'compile-c'):
        import ail_native_build as native_build
        if native_build.enabled(args):
            native_build.prepare(args, parser)
    if args.command == 'edit':
        if args.edits_text is None and args.symbol is None:
            parser.error('--symbol is required for a single body edit')
        if args.edits_text is not None and args.symbol is not None:
            parser.error('--symbol cannot be combined with --edits-text')
    if args.command == 'context':
        from ail_source_context import context
        try:
            if args.source.suffix.lower()!='.ail':
                raise ValueError('context source must use .ail suffix')
            source=args.source.resolve(strict=True)
            report=context(source.read_bytes(),args.symbol,args.include_body,
                           source_path=source,module_paths=args.module_path,resolve_imports=args.resolve_imports,contracts=args.contracts)
            report['source']=str(source)
            if args.compact:
                from ail_source_context import compact_context
                report=compact_context(report)
            print(json.dumps(report,ensure_ascii=False,**({'separators':(',', ':')} if args.compact else {})));return 0
        except (OSError,UnicodeError,SyntaxError,ValueError) as error:
            print(json.dumps(dict(schema='ail.context/1',status='failed',error=str(error)),ensure_ascii=False));return 2
    if args.command == 'edit':
        from ail_source_edit import run
        status, report = run(args, _source_check)
        print(json.dumps(report, ensure_ascii=False))
        return status
    if args.command == 'api':
        args.source = ROOT / 'language_examples' / (args.api_module + '.ail')
        args.module = args.module_path = []
        args.syntax, args.library, args.interface = 'auto', True, True
        return _source_check(args)
    if args.command == 'check':
        return _source_check(args)
    if args.command == 'api-builtin':
        from ail_builtin_api import query
        try:
            report = query(args.symbol, source_root=ROOT)
        except (OSError, UnicodeError, SyntaxError, ValueError) as error:
            print(json.dumps(dict(schema='ail.builtin_api/1', status='failed', error=str(error)), ensure_ascii=False))
            return 2
        print(json.dumps(report, ensure_ascii=False))
        return 0
    manifest_path = ROOT/'MANIFEST.json'
    if ((ROOT/'SDK_README_JA.md').is_file() and manifest_path.is_file()
            and json.loads(manifest_path.read_text(encoding='utf8')).get('kind') == 'ail_language_sdk'):
        supported = ('doctor', 'integrity', 'cache', 'compile', 'compile-module', 'compile-library', 'compile-c', 'export-sdk', 'check', 'api', 'api-builtin', 'edit', 'context')
        if args.command not in supported:
            parser.error('this language SDK supports: ' + ', '.join(supported))
    if args.command == 'cache':
        module = _BUILDCACHE[0] if _BUILDCACHE else None
        if module is None:
            _build_cache()
            module = _BUILDCACHE[0]
        if module is None:
            print('AIL ERROR: build cache module unavailable', file=sys.stderr)
            return 2
        if args.action == 'path':
            print(module.root())
        elif args.action == 'stats':
            print(json.dumps(module.stats(), indent=2))
        else:
            print(json.dumps({'removed': module.clear(), 'path': str(module.root())}))
        return 0
    if args.command == 'export-sdk':
        from ail_sdk import export_sdk
        try:
            result = export_sdk(ROOT, args.output)
        except (OSError, ValueError, RuntimeError) as error:
            parser.error(str(error))
        print(json.dumps({key: value for key, value in result.items() if key != 'sha256'}, ensure_ascii=False))
        return 0
    if args.command == 'doctor':
        requested = os.environ.get('PIPE_CC') or next(filter(None, (shutil.which(name)
            for name in ('cc', 'clang', 'gcc'))), None)
        resolved = shutil.which(requested) if requested else None
        report = {'python':sys.version, 'platform':platform.platform(),
            'python_supported':sys.version_info >= (3,10),
            'c_compiler':resolved, 'c_compiler_configured':requested,
            'c_compiler_available':resolved is not None,
            'source_root':str(ROOT), 'external_model_required_for_selftest':False}
        if args.check:
            report['build_check'] = _doctor_build_check(report)
        print(json.dumps(report, indent=2))
        return 2 if not report['python_supported'] or args.check and report['build_check']['status'] != 'passed' else 0
    if args.command == 'integrity':
        manifest = json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf8'))
        pins = manifest['sha256']
        is_sdk = manifest.get('kind') == 'ail_language_sdk'
        # A source checkout's sha256 map also holds pins of files from earlier archive layouts that
        # no longer exist; only the shipped sdk_files and the pins of files present are checked
        # (the same set ail_check and tools/update_manifest.py --check verify).
        names = list(pins) if is_sdk else [n for n in pins if (ROOT/n).is_file() or n in manifest.get('sdk_files', [])]
        bad = [name for name in names
               if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=pins[name]]
        report = {'status':'verified' if not bad else 'failed','checked':len(names),'mismatches':bad}
        if not is_sdk:
            report['historical_pins_skipped'] = len(pins) - len(names)
        print(json.dumps(report,indent=2))
        return 1 if bad else 0
    if args.command == 'compare-http':
        from ail_http_compare import main as compare_http
        return compare_http([str(args.manifest), '-o', str(args.output)])
    if args.command == 'snapshot-http':
        from ail_http_snapshot import main as snapshot_http
        return snapshot_http([str(args.manifest), '-o', str(args.output)]
                             + (['--compare'] if args.compare else []))
    if args.command == 'build-http':
        from ail_http_build import main as build_http
        return build_http([str(args.manifest), '--recipe', str(args.recipe), '-o', str(args.output)]
                          + (['--compare'] if args.compare else []))
    if args.command in ('compile-module', 'compile-c'):
        if sys.version_info < (3, 10):
            parser.error('AIL compilation requires Python 3.10 or newer')
        source, output = args.source.resolve(), Path(os.path.abspath(args.output))
        metadata = Path(str(output) + '.json')
        is_c = args.command == 'compile-c'
        if source.suffix.lower() != ('.c' if is_c else '.ail') or not source.is_file():
            parser.error('source must be an existing ' + ('.c' if is_c else '.ail') + ' file')
        if is_c and (not args.interface.is_file() or args.interface.resolve() in (output, metadata)):
            parser.error('interface must be an existing file distinct from outputs')
        if output.exists() or metadata.exists() or output.is_symlink() or metadata.is_symlink():
            parser.error('object output or metadata already exists')
        if not output.parent.is_dir() or source in (output, metadata):
            parser.error('object output requires an existing directory and must differ from source')
        try:
            text = source.read_text(encoding='utf8') if is_c else _load_sources(
                source, source_syntax=args.syntax, module_only=True, module_paths=args.module_path, **native_build.loading(args))[0]
        except (OSError, UnicodeError, SyntaxError, ValueError) as error:
            parser.error(str(error))
        with tempfile.TemporaryDirectory(prefix='ail-module-') as directory:
            prepared, target = Path(directory) / ('module.c' if is_c else 'module.py'), Path(directory) / 'module.o'
            prepared.write_text(text, encoding='utf8')
            command = [sys.executable, '-B', str(ROOT/'python/pkg-v12/pyc.py'),
                       '--file', str(source if is_c else prepared), str(target), '--strict']
            command += ['--compile-c', str(args.interface.resolve())] if is_c else ['--compile-object']
            if args.c_api_name is not None:
                command += ['--c-api-name', args.c_api_name]
            if is_c and _build_cache(args) is not None and not native_build.enabled(args):
                command.append('--cache')
            for object_path in ([] if is_c else args.object):
                command += ['--object', str(object_path.resolve())]
            cache = _build_cache(args) if is_c and not native_build.enabled(args) else None
            key = _compile_c_key(cache, args, source, text) if cache is not None else None
            payload = cache.get('fe', key) if key else None
            result = None
            if payload is not None:
                try:
                    meta, blob = cache.unpack(payload)
                    target.write_bytes(blob)
                    Path(str(target) + '.json').write_text(meta['metadata'], encoding='utf8')
                    result = subprocess.CompletedProcess(command, 0, '', '')
                except (OSError, ValueError, KeyError):
                    result = None
            if result is None:
                result = native_build.invoke(args, command, directory,
                                        capture_output=True, text=True, timeout=180,
                                        env=_hand_over_toolchain(cache, _surface_env(args, source)))
                if key and result.returncode == 0 and target.is_file() and Path(str(target) + '.json').is_file():
                    cache.put('fe', key, cache.pack({'metadata': Path(str(target) + '.json').read_text(encoding='utf8')},
                                                    target.read_bytes()))
            if result.returncode:
                return native_build.emit(args, {}, result.returncode, message=result.stderr or result.stdout)
            created = metadata_created = False
            try:
                with output.open('xb') as destination:
                    created = True
                    destination.write(target.read_bytes())
                with metadata.open('xb') as destination:
                    metadata_created = True
                    destination.write(Path(str(target) + '.json').read_bytes())
            except Exception:
                if metadata_created:
                    metadata.unlink()
                if created:
                    output.unlink()
                raise
        return native_build.emit(args, {'output': str(output), 'metadata': str(metadata),
                          'sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
    if args.command == 'compile' and args.m32 and not args.freestanding:
        parser.error('--m32 is part of --freestanding (a 32-bit x86 kernel target)')
    if args.command == 'compile' and args.freestanding:
        return _compile_freestanding(args, parser, native_build)
    if args.command in ('compile', 'compile-library'):
        export_lib = args.command == 'compile' and getattr(args, 'lib', None)
        library = args.command == 'compile-library' or bool(export_lib)
        lowered = {}
        objects = getattr(args, 'object', [])
        separate = getattr(args, 'separate', False)
        source = args.source.resolve()
        output = Path(os.path.abspath(args.output))
        if sys.version_info < (3, 10):
            parser.error('AIL compilation requires Python 3.10 or newer')
        if source.suffix.lower() not in ('.ail', '.py') or not source.is_file():
            parser.error('source must be an existing .ail or .py file')
        notes = {}
        loading = native_build.loading(args) or {'source_map': {}}
        ffi = None if library else _ffi_session(args)
        if export_lib and (separate or args.target):
            parser.error('--lib cannot be combined with --separate or --target')

        def lower_exports(text):
            import ail_export
            lowered_text, lowered['manifest'] = ail_export.lower(text)
            return lowered_text
        try:
            source_text, contracts, unit_map = _load_sources(
                source, args.module, args.syntax, module_only=library, separate=separate,
                module_paths=args.module_path, notes=notes, local_imports=not library, ffi=ffi,
                prelower=lower_exports if export_lib else None, **loading)
        except (OSError, UnicodeError, SyntaxError, ValueError) as error:
            _refuse_load(error)
        if export_lib:
            if not output.is_dir():
                parser.error('--lib output must be an existing directory (-o DIR)')
            with tempfile.TemporaryDirectory(prefix='ail-export-source-') as temporary:
                prepared, manifest = Path(temporary) / 'library.py', Path(temporary) / 'exports.json'
                prepared.write_text(source_text, encoding='utf8')
                manifest.write_text(json.dumps(lowered['manifest']), encoding='utf8')
                result = native_build.invoke(args, [sys.executable, '-B', str(ROOT/'python/pkg-v12/c_export.py'),
                                       str(prepared), '--manifest', str(manifest), '--name', args.lib, '-o', str(output)],
                                      temporary, timeout=240)
                if not native_build.enabled(args):
                    return result.returncode
                if result.returncode:
                    return native_build.emit(args, {}, result.returncode, message=result.stderr or result.stdout)
                return native_build.emit(args, json.loads(result.stdout))
        ffi_objects, ffi_env = [], {}
        if ffi is not None:
            ffi.extra_libs = list(getattr(args, 'link', None) or [])      # --link LIB is link("LIB") for the whole program
        if ffi is not None and not ffi.decls and ffi.extra_libs:
            ffi_env = {'AIL_FFI_LINK': shlex.join(ffi._link_args())}
        if ffi is not None and ffi.decls:
            try:
                ffi_objects = [ffi.build(ROOT / 'ail_chatgpt.py')]
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                return native_build.emit(args, {}, 2, 'ffi', str(error))
            ffi_env = {'AIL_FFI_LINK': shlex.join(ffi.link_args), 'AIL_FFI_SYMBOLS': ' '.join(ffi.symbols())}
        if library:
            if output.exists() or output.is_symlink() or not output.parent.is_dir():
                parser.error('library output requires a new directory in an existing parent')
            with tempfile.TemporaryDirectory(prefix='ail-library-source-') as temporary:
                prepared = Path(temporary) / 'library.py'
                prepared.write_text(source_text, encoding='utf8')
                result = native_build.invoke(args, [sys.executable, '-B', str(ROOT/'python/pkg-v12/c_api.py'),
                                       str(prepared), '--name', args.name, '-o', str(output),
                                       *(arg for name in args.export or [] for arg in ('--export', name)),
                                       *(arg for obj in objects for arg in ('--object', str(obj.resolve())))],
                                      temporary, timeout=240)
                if not native_build.enabled(args):
                    return result.returncode
                if result.returncode:
                    return native_build.emit(args, {}, result.returncode, message=result.stderr or result.stdout)
                return native_build.emit(args, json.loads(result.stdout))
        if output.exists() or output.is_symlink() or (sys.platform == 'win32' and
                (Path(str(output) + '.exe').exists() or Path(str(output) + '.exe').is_symlink())):
            parser.error('output already exists')
        if source == output or source == Path(str(output) + '.exe'):
            parser.error('output must differ from source')
        if not output.parent.is_dir():
            parser.error('output directory does not exist')
        if separate and not unit_map:
            parser.error('--separate needs a module with at least one function')
        with tempfile.TemporaryDirectory(prefix='ailc-') as tmp:
            target = Path(tmp) / 'program'
            build_source = Path(tmp) / 'combined.ail'
            build_source.write_text(source_text, encoding='utf-8')
            strict = _strict_requested(args)
            command = [sys.executable, '-B', str(ROOT/'python/pkg-v12/pyc.py'),
                       '--file', str(build_source), str(target), '--strict']
            for object_path in [*objects, *ffi_objects]:
                command += ['--object', str(object_path.resolve())]
            if separate:
                unit_map_path = Path(tmp) / 'units.json'
                unit_map_path.write_text(json.dumps(unit_map), encoding='utf-8')
                command += ['--link-units', str(unit_map_path)]
            debug = bool(getattr(args, 'debug', False))
            link = bool(getattr(args, 'link', None)) and ffi is not None
            debug_env = {}
            if debug:
                line_map = Path(tmp) / 'lines.json'
                line_map.write_text(json.dumps({str(key): [value[0], value[1]]
                                                for key, value in loading['source_map'].items()}), encoding='utf-8')
                debug_env = {'AIL_DEBUG': '1', 'AIL_LINE_MAP': str(line_map)}
            environment = _surface_env(args, source, {**os.environ, 'AIL_REPORT_SOURCE_LINE': '1',
                                                **({'AIL_NO_GENERAL': '1'} if contracts or strict else {}), **ffi_env, **debug_env})
            cache = None if separate or getattr(args, 'target', None) else _build_cache(args)
            frontend = None
            if cache is not None and not native_build.enabled(args):
                # A finished build is a function of the merged source, the objects it links, the
                # compiler sources, the toolchain and the environment; nothing else is read.
                frontend = cache.frontend_key(
                    ROOT / 'python/pkg-v12', 'compile', source_text,
                    *[part for object_path in [*objects, *ffi_objects] for part in (
                        hashlib.sha256(object_path.read_bytes()).hexdigest(),
                        hashlib.sha256(Path(str(object_path) + '.json').read_bytes()).hexdigest()
                        if Path(str(object_path) + '.json').is_file() else '-')],
                    environment.get('AIL_SURFACE', ''), environment.get('AIL_NO_GENERAL', ''),
                    *[hashlib.sha256(Path(a).read_bytes()).hexdigest() for a in shlex.split(ffi_env.get('AIL_FFI_LINK', '')) if Path(a).is_file()],
                    *(['link', ffi_env['AIL_FFI_LINK']] if link else []),
                    *(['debug', hashlib.sha256(line_map.read_bytes()).hexdigest()] if debug else []))
            _hand_over_toolchain(cache, environment)
            result = None
            payload = cache.get('fe', frontend) if frontend else None
            if payload is not None:
                try:
                    meta, blob = cache.unpack(payload)
                    cache.write_output(target, blob, True)
                    result = subprocess.CompletedProcess(command, 0, '', meta['stderr'])
                except (OSError, ValueError, KeyError):
                    result = None
            if result is None:
                if cache is not None and not native_build.enabled(args):
                    command.append('--cache')
                result = native_build.invoke(args, command, tmp, capture_output=True, text=True,
                    timeout=660, env=environment)
                if frontend and result.returncode == 0 and target.is_file():
                    cache.put('fe', frontend, cache.pack({'stderr': result.stderr or ''}, target.read_bytes()))
            if result.returncode == 3 and strict and not separate and not ffi_objects:
                refused = _strict_refusal(args, source, objects, result.stderr or result.stdout)
                if refused is not None:
                    return refused
            if result.returncode:
                message, marked = _split_line_marker(result.stderr or result.stdout)
                python = result.returncode == 3 and _python_source(args, source.read_bytes())
                if python:
                    message = python_wording(message)
                if str(source) in _MERGED_ENTRIES:
                    message = ail_modules.unmangle(message, _MERGED_ENTRIES[str(source)].names)
                if result.returncode == 3 and not args.json and not objects and not separate:
                    located = _locate_refusal(args, source, message)
                    where = _marker_where(loading['source_map'], marked) if located == message else None
                    message = '%s: %s' % (where, message) if where else located
                if python and any(notes.values()):
                    message = _python_notes(message, notes, source)
                return native_build.emit(args, {}, result.returncode, message=message)
            built = target if target.is_file() else Path(str(target) + '.exe')
            if not built.is_file():
                return native_build.emit(args, {}, 2, 'artifact', 'AIL ERROR: compiler returned success without an executable')
            if sys.platform == 'win32' and not output.suffix:
                output = Path(str(output) + '.exe')
            created = False
            try:
                with output.open('xb') as dst, built.open('rb') as src:
                    created = True
                    shutil.copyfileobj(src, dst)
                shutil.copymode(built, output)
            except Exception:
                if created:
                    output.unlink()
                raise
            for line in [] if args.json else _slow_patterns(source_text, loading['source_map']):
                print(line, file=sys.stderr)
            if not args.json:
                for line in _fallback_notes(args, source, result.stderr, locate=not objects and not separate,
                                             source_map=loading['source_map']):
                    print(line, file=sys.stderr)
                # typedpar.py: why a thread / executor / pool use runs under the general path's lock
                for path, entries in notes.items():
                    for line, text in entries:
                        if text.startswith('not run in parallel'):
                            print('note: %s:%d: %s' % (_relpath(Path(path)) if Path(path) == source else path,
                                                       line, text), file=sys.stderr)
            return native_build.emit(args, {'output': str(output), 'bytes': output.stat().st_size,
                'sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
    project = ROOT/'example' if args.command == 'selftest' else Path(args.project).resolve()
    output = Path(args.out).resolve()
    command = [sys.executable,'-B',str(ROOT/'workflow/vibe/vibe.py'),'build',
        '--project',str(project),'--selector',str(ROOT/'workflow/selector'),
        '--out',str(output),'--mode',getattr(args,'mode','original'),'--budget-seconds','600']
    if getattr(args,'candidate_patch',None):
        if args.mode == 'original':
            parser.error('candidate-patch requires a measured mode')
        command += ['--candidate-patch',str(Path(args.candidate_patch).resolve())]
    subprocess.run(command,check=True,timeout=660)
    config = json.loads((project/'project.json').read_text(encoding='utf8'))
    checker = config.get('specification_checker')
    if checker:
        subprocess.run([sys.executable,'-B',str(ROOT/'workflow/vibe/vibe.py'),'verify',
            str(output/'app/result.json'),'--checker',str(project/checker)],check=True,timeout=180)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
