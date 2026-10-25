# -*- coding: utf-8 -*-
"""bigcap.py -- which functions are "big-int capable" (docs/design/BIGINT.md section 5).

The typed path keeps C int64 and stops loudly on overflow ("integer overflow", exit 1); the general path has exact big ints.
The default build keeps a function on the typed path only when it is unlikely to need a big int. A function is MARKED, and
stays off the typed path (the whole program goes to the general path, and mixed mode makes no typed clone of the function),
when any of these holds:

  1. it contains an int literal outside int64;
  2. it contains `**` (or `**=`, or the two-argument `pow`) with a non-constant exponent, or with a constant exponent where the
     result can exceed int64: a literal base b with |b| ** e >= 2**63, any other base with e >= 4 (a base that is not a literal is
     unknown here, and e >= 4 is where a 16-bit base already overflows; squares and cubes of int64 values stay typed);
  3. it contains `<<` (or `<<=`) by a non-constant amount;
  4. it calls math.factorial / comb / perm with arguments whose value is not a constant (or whose constant result is beyond
     int64), `int(s)` on a constant string of more than 18 digits, or `int.from_bytes`;
  5. it calls a marked function (transitively; a method is matched by its name).

`<module>` is the module-level code outside any def; when it is marked the whole program is.
"""
import ast
import math
import os

_I64 = 1 << 63
_MATH_BIG = frozenset(('factorial', 'comb', 'perm', 'isqrt', 'gcd', 'lcm', 'prod', 'floor', 'ceil', 'trunc'))
_MATH_HARD = frozenset(('factorial', 'comb', 'perm'))
_MATH_HELPERS = frozenset(('_ail_math_factorial', '_ail_math_comb', '_ail_math_perm'))
_MATH_HARD_HELPERS = frozenset(('_ail_math_factorial', '_ail_math_comb', '_ail_math_perm'))   # what math.factorial(...) is rewritten to


def _const_int(node):
    """The int value of a constant integer expression (a literal, a sign, arithmetic of literals), or None."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _const_int(node.operand)
        return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
        a, b = _const_int(node.left), _const_int(node.right)
        if a is None or b is None:
            return None
        return a + b if isinstance(node.op, ast.Add) else a - b if isinstance(node.op, ast.Sub) else a * b
    return None


def _const_str_len(node):
    """The length of a constant string expression (a literal, `s * n`, `n * s`, `s + t` of constants, str of an int constant), or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return len(node.value.strip().replace('_', '').lstrip('+-'))
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Mult):
            for a, b in ((node.left, node.right), (node.right, node.left)):
                n = _const_int(b)
                if n is not None and isinstance(a, ast.Constant) and isinstance(a.value, str):
                    return len(a.value.strip().replace('_', '').lstrip('+-')) * max(n, 0) if len(a.value.strip()) == len(a.value) else None
        if isinstance(node.op, ast.Add):
            a, b = _const_str_len(node.left), _const_str_len(node.right)
            if a is not None and b is not None and isinstance(node.left, (ast.Constant, ast.BinOp)):
                return a + b
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'str' and len(node.args) == 1 \
            and not node.keywords:
        v = _const_int(node.args[0])
        if v is not None:
            return len(str(abs(v)))
    return None


def _pow_reason(base, exp, module_values=None):
    e = _const_int(exp)
    if e is None:
        if isinstance(exp, ast.Constant):      # a float or other constant exponent: not an int power
            return None
        if isinstance(base, ast.Constant) and isinstance(base.value, float):
            return None                        # a float base: the result is a float (possibly inf), never a big int
        return 'an exponent that is not a constant'
    if e < 2:
        return None
    b = _const_int(base)
    if b is None and module_values is not None and isinstance(base, ast.Name):
        # A module variable starts at its one module-level literal. `e = 2` then `e **= 5` is the
        # same constant power as `2 ** 5`; without the value the rule would mark it for every
        # exponent >= 4. The variable is still an int64 static (checked on every store), so a value
        # that does not fit stops loudly instead of needing the big-int runtime.
        b = module_values.get(base.id)
    if b is not None:
        return ('%d ** %d beyond int64' % (b, e)) if abs(b) > 1 and abs(b) ** e >= _I64 else None
    if isinstance(base, ast.Constant):         # a float base
        return None
    return ('a power with the constant exponent %d' % e) if e >= 4 else None


def _own_reason(fn_nodes, defined, module_values=None):
    """The first reason a function's own code (not its callees) can need a big int, or None."""
    if module_values:
        # The module literal is only the value at the power when nothing in this function stored the
        # variable before it. A store later in the function (the other `e |= ...` of an accumulator)
        # does not change the first power; a store before it makes the literal irrelevant.
        first_pow = {}
        for n in fn_nodes:
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow):
                base = n.left
            elif isinstance(n, ast.AugAssign) and isinstance(n.op, ast.Pow):
                base = n.target
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'pow' \
                    and len(n.args) == 2 and not n.keywords:
                base = n.args[0]
            else:
                continue
            if isinstance(base, ast.Name):
                line = getattr(n, 'lineno', 1 << 30)
                first_pow[base.id] = min(first_pow.get(base.id, line), line)
        safe = {}
        for name, value in module_values.items():
            line = first_pow.get(name)
            if line is None:
                continue
            if any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Store)
                   and getattr(n, 'lineno', 1 << 30) < line for n in fn_nodes):
                continue
            safe[name] = value
        module_values = safe
    neg = set()
    for n in fn_nodes:
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)) \
                and isinstance(n.operand, ast.Constant) and type(n.operand.value) is int:
            neg.add(id(n.operand))
            v = -n.operand.value if isinstance(n.op, ast.USub) else n.operand.value
            if not -_I64 <= v < _I64:
                return 'an int literal beyond int64'
    for n in fn_nodes:
        if isinstance(n, ast.Constant) and type(n.value) is int and id(n) not in neg \
                and not -_I64 <= n.value < _I64:
            return 'an int literal beyond int64'
        if isinstance(n, ast.BinOp):
            if isinstance(n.op, ast.Pow):
                r = _pow_reason(n.left, n.right, module_values)
                if r:
                    return '`**` with ' + r
            elif isinstance(n.op, ast.LShift) and _const_int(n.right) is None and not isinstance(n.right, ast.Constant):
                return '`<<` by an amount that is not a constant'
        elif isinstance(n, ast.AugAssign):
            if isinstance(n.op, ast.Pow):
                r = _pow_reason(n.target, n.value, module_values)
                if r:
                    return '`**=` with ' + r
            elif isinstance(n.op, ast.LShift) and _const_int(n.value) is None and not isinstance(n.value, ast.Constant):
                return '`<<=` by an amount that is not a constant'
        elif isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            if (name in _MATH_HARD and name not in defined) or name in _MATH_HARD_HELPERS:
                base = name.replace('_ail_math_', '')
                return 'a call of math.%s' % base
            if isinstance(f, ast.Attribute) and f.attr == 'from_bytes' and isinstance(f.value, ast.Name) and f.value.id == 'int':
                return 'a call of int.from_bytes'
            if isinstance(f, ast.Name) and f.id == 'pow' and 'pow' not in defined and len(n.args) == 2 and not n.keywords:
                r = _pow_reason(n.args[0], n.args[1], module_values)
                if r:
                    return 'pow() with ' + r
            if isinstance(f, ast.Name) and f.id == 'int' and 'int' not in defined and n.args:
                a = n.args[0]
                ln = _const_str_len(a)
                if ln is not None and ln > 18:
                    return 'int() of a string of more than 18 digits'
    return None


def _walk_own(body):
    """Every node of a function body, without entering a nested def or class (they are units of their own)."""
    stack = list(body)
    while stack:
        n = stack.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if not isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                stack.append(c)
            elif isinstance(c, ast.Lambda):
                stack.append(c)



# ---------------------------------------------------------------------------------------------------------------------------
# local proofs (BIGINT.md rules 2-4).  A function is big-int capable unless every int value it makes is proven, from the
# function itself, to fit int64 (and every + - * to stay within 2**62).  No call site, field or other function is consulted:
# a parameter, an attribute, a container item and a call result are unproven unless they come from a rule below.
_LP_LIMIT = 1 << 62
_LP_I64_MIN = -(1 << 63)
_LP_I64_MAX = (1 << 63) - 1
_LP_LEN = 1 << 48
_LP_FLOAT = ('float', None, None)
_LP_BOOL = ('bool', 0, 1)
_LP_STR = ('str', None, None)
_LP_OTHER = ('other', None, None)
_LP_NONE = ('none', None, None)
_LP_UNKNOWN = ('unknown', None, None)
_LP_INTS = ('int', 'bool')
_NONINT_STR_METHODS = frozenset((
    'lower', 'upper', 'strip', 'lstrip', 'rstrip', 'replace', 'join', 'format', 'capitalize', 'title', 'swapcase',
    'zfill', 'ljust', 'rjust', 'center', 'removeprefix', 'removesuffix', 'decode', 'partition', 'rpartition'))
_LP_MATH_FLOAT = frozenset((
    'sqrt', 'log', 'log2', 'log10', 'log1p', 'exp', 'expm1', 'pow', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan',
    'atan2', 'sinh', 'cosh', 'tanh', 'asinh', 'acosh', 'atanh', 'degrees', 'radians', 'hypot', 'copysign', 'fabs',
    'fmod', 'modf', 'frexp', 'ldexp', 'erf', 'erfc', 'gamma', 'lgamma', 'dist', 'remainder', 'nextafter', 'ulp'))
_LP_STR_CALLS = frozenset(('str', 'repr', 'ascii', 'format', 'chr', 'hex', 'oct', 'bin', 'input'))
_LP_OTHER_CALLS = frozenset((
    'list', 'dict', 'set', 'frozenset', 'tuple', 'bytes', 'bytearray', 'memoryview', 'complex', 'open', 'iter',
    'sorted', 'reversed', 'zip', 'map', 'filter', 'type', 'range', 'super', 'object', 'slice'))
_LP_BOOL_CALLS = frozenset(('isinstance', 'issubclass', 'hasattr', 'callable'))
_LP_NONE_CALLS = frozenset(('print', 'setattr', 'delattr'))
_LP_EXC_CALLS = frozenset((
    'BaseException', 'Exception', 'ArithmeticError', 'AssertionError', 'AttributeError', 'BufferError',
    'EOFError', 'ImportError', 'LookupError', 'IndexError', 'KeyError', 'MemoryError', 'NameError',
    'OverflowError', 'RuntimeError', 'NotImplementedError', 'RecursionError', 'ReferenceError',
    'StopIteration', 'StopAsyncIteration', 'SyntaxError', 'SystemError', 'TypeError', 'ValueError',
    'UnicodeError', 'UnicodeDecodeError', 'UnicodeEncodeError', 'ZeroDivisionError', 'OSError',
    'FileNotFoundError', 'PermissionError', 'IsADirectoryError', 'NotADirectoryError', 'FileExistsError',
    'TimeoutError', 'ConnectionError', 'Warning'))
_LP_STR_METHODS = frozenset(_NONINT_STR_METHODS | {'readline'})
_LP_OTHER_METHODS = frozenset((
    'split', 'rsplit', 'splitlines', 'keys', 'values', 'items', 'copy', 'encode', 'read', 'readlines', 'readinto',
    'getbuffer', 'popitem', '__enter__'))
_LP_NONE_METHODS = frozenset((
    'append', 'extend', 'insert', 'remove', 'clear', 'reverse', 'sort', 'close', 'write', 'flush', 'seek', 'update',
    'add', 'discard', '__exit__'))
_LP_INT_RESULT_METHODS = frozenset(('get', 'pop', 'setdefault', 'next', '__next__', 'tell', 'fileno', 'recv'))


class _Defined(set):
    """The program's function names, plus the class names (a class call builds a non-int object)."""
    classes = frozenset()


def _lp_int(lo=None, hi=None):
    return ('int', lo, hi)


def _lp_join(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a[0] in _LP_INTS and b[0] in _LP_INTS:
        lo = None if a[1] is None or b[1] is None else min(a[1], b[1])
        hi = None if a[2] is None or b[2] is None else max(a[2], b[2])
        return ('int', lo, hi)
    return a if a[0] == b[0] else _LP_UNKNOWN


def _lp_bad(bad, why):
    if bad is not None:
        bad.append(why)


def _lp_fits(lo, hi):
    return lo is not None and hi is not None and -_LP_LIMIT <= lo and hi <= _LP_LIMIT


def _lp_seq(node):
    return isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.ListComp, ast.SetComp, ast.DictComp,
                             ast.GeneratorExp, ast.JoinedStr))


def _lp_eval(node, env, defined, bad):
    """One expression's local value: ('int', lo, hi), float, bool, str, other or unknown.  `bad` is a list while the proof is
    being checked (an unproven int operation is appended there); None during the fixed-point iteration."""
    if node is None:
        return _LP_NONE
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool):
            return _LP_BOOL
        if isinstance(v, int):
            return _lp_int(v, v)
        if isinstance(v, float):
            return _LP_FLOAT
        if isinstance(v, str):
            return _LP_STR
        if v is None:
            return _LP_NONE
        return _LP_OTHER
    if isinstance(node, ast.Name):
        return env.get(node.id) or _LP_UNKNOWN
    if isinstance(node, ast.UnaryOp):
        v = _lp_eval(node.operand, env, defined, bad)
        if isinstance(node.op, ast.Not):
            return _LP_BOOL
        if isinstance(node.op, (ast.USub, ast.UAdd)):
            if v[0] == 'float':
                return _LP_FLOAT
            if v[0] in _LP_INTS:
                if v[1] is None:
                    _lp_bad(bad, 'an operand not proven to fit int64')
                    return _lp_int()
                lo, hi = v[1], v[2]
                if isinstance(node.op, ast.USub):
                    lo, hi = -hi, -lo
                if not _lp_fits(lo, hi):
                    _lp_bad(bad, 'an int operation beyond int64')
                return _lp_int(lo, hi)
            _lp_bad(bad, 'an operand not proven int or float')
            return _lp_int()
        if isinstance(node.op, ast.Invert):
            if v[0] in _LP_INTS and v[1] is not None:
                lo, hi = -v[2] - 1, -v[1] - 1
                if not _lp_fits(lo, hi):
                    _lp_bad(bad, 'an int operation beyond int64')
                return _lp_int(lo, hi)
            if v[0] in ('float', 'str', 'other', 'none'):
                return _LP_OTHER
            _lp_bad(bad, 'an operand not proven int')
            return _lp_int()
        return _LP_UNKNOWN
    if isinstance(node, ast.BinOp):
        lv = _lp_eval(node.left, env, defined, bad)
        rv = _lp_eval(node.right, env, defined, bad)
        op = node.op
        lk, rk = lv[0], rv[0]
        if isinstance(op, (ast.Add, ast.Sub, ast.Mult)):
            if lk == 'float' or rk == 'float':
                return _LP_FLOAT
            if isinstance(op, ast.Add) and (lk == 'str' or rk == 'str'):
                return _LP_STR
            if isinstance(op, ast.Mult) and ((lk == 'str' and rk in _LP_INTS + ('unknown',)) or
                                             (rk == 'str' and lk in _LP_INTS + ('unknown',))):
                return _LP_STR
            if lk not in _LP_INTS or rk not in _LP_INTS:
                if lk in ('str', 'other', 'none') or rk in ('str', 'other', 'none'):
                    return _LP_OTHER
                _lp_bad(bad, 'an operand not proven int or float')
                return _lp_int()
            if lv[1] is None or rv[1] is None:
                _lp_bad(bad, 'an operand not proven to fit int64')
                return _lp_int()
            a, b, c, d = lv[1], lv[2], rv[1], rv[2]
            if isinstance(op, ast.Add):
                lo, hi = a + c, b + d
            elif isinstance(op, ast.Sub):
                lo, hi = a - d, b - c
            else:
                vals = (a * c, a * d, b * c, b * d)
                lo, hi = min(vals), max(vals)
            if not _lp_fits(lo, hi):
                _lp_bad(bad, 'an int operation beyond 2**62')
            return _lp_int(lo, hi)
        if isinstance(op, ast.Div):
            return _LP_FLOAT
        if isinstance(op, (ast.FloorDiv, ast.Mod)):
            if lk == 'float' or rk == 'float':
                return _LP_FLOAT
            if lk not in _LP_INTS or rk not in _LP_INTS:
                if lk in ('str', 'other', 'none') or rk in ('str', 'other', 'none'):
                    return _LP_OTHER
                _lp_bad(bad, 'an operand not proven int')
                return _lp_int()
            if rv[1] is None or rv[1] != rv[2] or rv[1] == 0:
                _lp_bad(bad, '// or %% not by a proven nonzero literal')
                return _lp_int()
            b = rv[1]
            if isinstance(op, ast.FloorDiv):
                if lv[1] is None:
                    _lp_bad(bad, '// of a value not proven to fit int64')
                    return _lp_int()
                # a conservative enclosure: floor division is monotone in the dividend
                lo, hi = min(lv[1] // b, lv[2] // b), max(lv[1] // b, lv[2] // b)
            else:
                # x % b is in [0, b) for b > 0 and (b, 0] for b < 0, whatever x is (Python's sign).
                lo, hi = (0, b - 1) if b > 0 else (b + 1, 0)
            if not _lp_fits(lo, hi):
                _lp_bad(bad, 'an int operation beyond 2**62')
            return _lp_int(lo, hi)
        if isinstance(op, ast.Pow):
            if lk == 'float' or rk == 'float':
                return _LP_FLOAT
            base, exp = _const_int(node.left), _const_int(node.right)
            if exp is not None and exp < 0:
                return _LP_FLOAT
            if base is not None and exp is not None:
                if exp == 0 or base in (0, 1, -1):
                    v = pow(base, exp)
                    return _lp_int(v, v) if _lp_fits(v, v) else (_lp_bad(bad, 'an int operation beyond 2**62') or _lp_int(v, v))
                bits = abs(base).bit_length() * exp
                if bits <= 512:
                    v = pow(base, exp)
                    if _lp_fits(v, v):
                        return _lp_int(v, v)
                _lp_bad(bad, 'an int power beyond 2**62')
                return _lp_int()
            if lk in ('str', 'other', 'none') or rk in ('str', 'other', 'none'):
                return _LP_OTHER
            _lp_bad(bad, 'an int power on an unproven value')
            return _lp_int()
        if isinstance(op, (ast.LShift, ast.RShift)):
            if lk not in _LP_INTS or rk not in _LP_INTS:
                if lk in ('str', 'other', 'none') or rk in ('str', 'other', 'none'):
                    return _LP_OTHER
                _lp_bad(bad, 'a shift of an unproven value')
                return _lp_int()
            if lv[1] is None or rv[1] is None or rv[1] != rv[2] or rv[1] < 0:
                _lp_bad(bad, 'a shift by an unproven amount')
                return _lp_int()
            s = rv[1]
            if isinstance(op, ast.LShift):
                if s > 200:
                    _lp_bad(bad, 'a shift beyond 2**62')
                    return _lp_int()
                lo, hi = lv[1] << s, lv[2] << s
            else:
                if s > 200:
                    lo, hi = -1, 0
                    if lv[1] < 0:
                        lo, hi = -1, -1
                else:
                    lo, hi = lv[1] >> s, lv[2] >> s
                    lo, hi = min(lo, hi), max(lo, hi)
            if not _lp_fits(lo, hi):
                _lp_bad(bad, 'an int shift beyond 2**62')
            return _lp_int(lo, hi)
        if isinstance(op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
            if lk not in _LP_INTS or rk not in _LP_INTS:
                if lk in ('str', 'other', 'none') or rk in ('str', 'other', 'none'):
                    return _LP_OTHER
                _lp_bad(bad, 'a bit operation on an unproven value')
                return _lp_int()
            if lv[1] is None or rv[1] is None:
                _lp_bad(bad, 'a bit operation on an unproven value')
                return _lp_int()
            m = 1 << max(abs(lv[1]), abs(lv[2]), abs(rv[1]), abs(rv[2])).bit_length()
            if m > _LP_LIMIT:
                _lp_bad(bad, 'a bit operation beyond 2**62')
            return _lp_int(-m, m)
        return _LP_UNKNOWN
    if isinstance(node, ast.BoolOp):
        v = None
        for x in node.values:
            v = _lp_join(v, _lp_eval(x, env, defined, bad))
        return v or _LP_BOOL
    if isinstance(node, ast.Compare):
        _lp_eval(node.left, env, defined, bad)
        for x in node.comparators:
            _lp_eval(x, env, defined, bad)
        return _LP_BOOL
    if isinstance(node, ast.IfExp):
        _lp_eval(node.test, env, defined, bad)
        return _lp_join(_lp_eval(node.body, env, defined, bad), _lp_eval(node.orelse, env, defined, bad))
    if isinstance(node, ast.Attribute):
        _lp_eval(node.value, env, defined, bad)
        if isinstance(node.value, ast.Name) and node.value.id == 'math' \
                and node.attr in ('pi', 'e', 'tau', 'inf', 'nan'):
            return _LP_FLOAT
        return _LP_UNKNOWN
    if isinstance(node, ast.Subscript):
        _lp_eval(node.value, env, defined, bad)
        if not isinstance(node.slice, ast.Slice):
            _lp_eval(node.slice, env, defined, bad)
        return _LP_UNKNOWN
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for x in node.elts:
            _lp_eval(x.value if isinstance(x, ast.Starred) else x, env, defined, bad)
        return _LP_OTHER
    if isinstance(node, ast.Dict):
        for k in node.keys:
            if k is not None:
                _lp_eval(k, env, defined, bad)
        for v in node.values:
            _lp_eval(v, env, defined, bad)
        return _LP_OTHER
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        sub = dict(env)
        for gen in node.generators:
            it = gen.iter
            if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range' \
                    and 'range' not in defined and not it.keywords and 1 <= len(it.args) <= 3 \
                    and not any(isinstance(a, ast.Starred) for a in it.args):
                vals = [_lp_eval(a, sub, defined, bad) for a in it.args]
                if all(v[0] in _LP_INTS and v[1] is not None for v in vals):
                    _lp_assign(gen.target, _lp_int(min(v[1] for v in vals), max(v[2] for v in vals)), sub, defined)
                else:
                    _lp_bad(bad, 'a loop over an unproven range')
                    _lp_assign(gen.target, _lp_int(), sub, defined)
            else:
                _lp_eval(it, sub, defined, bad)
                _lp_assign(gen.target, _LP_UNKNOWN, sub, defined)
            for cond in gen.ifs:
                _lp_eval(cond, sub, defined, bad)
        if isinstance(node, ast.DictComp):
            _lp_eval(node.key, sub, defined, bad)
            _lp_eval(node.value, sub, defined, bad)
        else:
            _lp_eval(node.elt, sub, defined, bad)
        return _LP_OTHER
    if isinstance(node, ast.Call):
        args = [_lp_eval(a.value if isinstance(a, ast.Starred) else a, env, defined, bad) for a in node.args]
        kw = [_lp_eval(k.value, env, defined, bad) for k in node.keywords]
        f = node.func
        if isinstance(f, ast.Name):
            name = f.id
            if name.startswith('_ail_math_'):
                helper = name[len('_ail_math_'):]
                if helper in _LP_MATH_FLOAT:
                    return _LP_FLOAT
                if helper in _MATH_BIG:
                    _lp_bad(bad, 'a call of math.%s' % helper)
                    return _lp_int()
            if name in getattr(defined, 'classes', ()):
                return _LP_OTHER
            if name in _LP_EXC_CALLS:
                return _LP_OTHER
            if name in defined:
                return _LP_UNKNOWN
            if name in _LP_STR_CALLS:
                return _LP_STR
            if name in _LP_OTHER_CALLS:
                return _LP_OTHER
            if name in _LP_BOOL_CALLS:
                return _LP_BOOL
            if name in _LP_NONE_CALLS:
                return _LP_NONE
            if name == 'len':
                if '__len__' in defined and node.args and not _lp_builtin_len_arg(node.args[0]):
                    _lp_bad(bad, 'len() of a value whose __len__ is the program\'s')
                    return _lp_int()
                return _lp_int(0, _LP_LEN)
            if name == 'ord':
                return _lp_int(0, 0x10FFFF)
            if name == 'bool':
                return _LP_BOOL
            if name == 'float':
                return _LP_FLOAT
            if name == 'str':
                return _LP_STR
            if name == 'int':
                c = _const_int(node.args[0]) if len(node.args) == 1 and not node.keywords else None
                if c is not None:
                    return _lp_int(c, c)
                _lp_bad(bad, 'a call of int()')
                return _lp_int()
            if name in ('abs', 'min', 'max') and args:
                if all(v[0] in _LP_INTS and v[1] is not None for v in args):
                    if name == 'abs':
                        a, b = args[0][1], args[0][2]
                        lo, hi = (max(0, a), max(abs(a), abs(b))) if b >= 0 else (-b, -a)
                    elif name == 'min':
                        lo, hi = min(v[1] for v in args), min(v[2] for v in args)
                    else:
                        lo, hi = max(v[1] for v in args), max(v[2] for v in args)
                    if not _lp_fits(lo, hi):
                        _lp_bad(bad, '%s() beyond 2**62' % name)
                    return _lp_int(lo, hi)
                _lp_bad(bad, '%s() of an unproven value' % name)
                return _lp_int()
            if name in ('sum', 'divmod', 'pow'):
                _lp_bad(bad, 'a call of %s()' % name)
                return _lp_int()
            return _LP_UNKNOWN
        if isinstance(f, ast.Attribute):
            attr = f.attr
            _lp_eval(f.value, env, defined, bad)
            if isinstance(f.value, ast.Name) and f.value.id == 'math':
                if attr in _LP_MATH_FLOAT:
                    return _LP_FLOAT
                if attr in _MATH_BIG:
                    _lp_bad(bad, 'a call of math.%s' % attr)
                    return _lp_int()
            if attr not in defined:
                if attr in _LP_STR_METHODS:
                    return _LP_STR
                if attr in _LP_OTHER_METHODS:
                    return _LP_OTHER
                if attr in _LP_NONE_METHODS:
                    return _LP_NONE
                if attr in ('count',):
                    return _lp_int(0, _LP_LEN)
                if attr in ('find', 'rfind'):
                    return _lp_int(-1, _LP_LEN)
                if attr == 'index':
                    return _lp_int(0, _LP_LEN)
                if attr in ('bit_length', 'bit_count'):
                    return _lp_int(0, 1 << 31)
                if attr in _LP_MATH_FLOAT:
                    return _LP_FLOAT
                if attr in _MATH_BIG:
                    _lp_bad(bad, 'a call of math.%s' % attr)
                    return _lp_int()
            return _LP_UNKNOWN
        _lp_eval(f, env, defined, bad)
        return _LP_UNKNOWN
    return _LP_UNKNOWN


def _lp_locals(stmts):
    """Every local name bound in these statements (not in a nested def/class/lambda body)."""
    out = set()
    stack = list(stmts)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.update(x.id for x in ast.walk(n) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store))
            continue
        if isinstance(n, ast.Lambda):
            continue
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        stack.extend(ast.iter_child_nodes(n))
    return out


def _lp_globals(stmts):
    out = set()
    for n in _walk_own(stmts):
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            out.update(n.names)
    return out


def _lp_params(fn):
    a = fn.args
    return [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs
            + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else [])]


def _lp_nonint_value(node, names):
    """A value that is definitely not an int (an element of a container we may iterate)."""
    if isinstance(node, ast.Constant):
        return not isinstance(node.value, (int, bool)) and not isinstance(node.value, (bytes, bytearray))
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _lp_nonint_value(node.operand, names)
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Div):
            return True
        if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            return _lp_nonint_value(node.left, names) or _lp_nonint_value(node.right, names)
        return False
    if isinstance(node, ast.IfExp):
        return _lp_nonint_value(node.body, names) and _lp_nonint_value(node.orelse, names)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return _lp_nonint_seq(node, names)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id in ('float', 'str', 'repr', 'ascii', 'format', 'chr', 'input', 'complex', 'list',
                                'dict', 'set', 'frozenset', 'tuple')
    if isinstance(node, ast.Attribute):
        return node.attr in ('pi', 'e', 'tau', 'inf', 'nan')
    return False


def _lp_nonint_seq(node, names):
    """A container whose iterated items are all definitely not ints (so `for x in it` binds a non-int)."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)       # bytes iterate ints
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_lp_nonint_value(x, names) for x in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and _lp_nonint_value(k, names) for k in node.keys)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _lp_nonint_seq(node.left, names) and _lp_nonint_seq(node.right, names)
    if isinstance(node, ast.IfExp):
        return _lp_nonint_seq(node.body, names) and _lp_nonint_seq(node.orelse, names)
    return False


def nonint_containers(tree):
    """Names bound only to containers whose iterated items are all non-int (sound for `for x in name`)."""
    names = set()
    assigns = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    assigns.append((t.id, node.value))
    for _ in range(4):
        before = len(names)
        for name, value in assigns:
            if _lp_nonint_seq(value, names):
                names.add(name)
        if len(names) == before:
            break
    return names


def _lp_annotation_kind(node, defined):
    """The local-proof kind of a non-int annotation, or None.  An annotation is a promise of the parameter or
    local's type, so a `float`, `str`, `bytes` (or any other non-int type) cannot be an int here."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            node = ast.parse(node.value, mode='eval').body
        except SyntaxError:
            return None
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.Attribute):
        name = node.attr
    else:
        return None
    if name == 'float':
        return _LP_FLOAT
    if name == 'str':
        return _LP_STR
    if name == 'bool':
        return _LP_BOOL
    if name in ('bytes', 'bytearray', 'memoryview', 'complex', 'list', 'dict', 'set', 'frozenset',
                'tuple', 'object', 'range'):
        return _LP_OTHER
    if name in getattr(defined, 'classes', ()):
        return _LP_OTHER
    return None


def _lp_fixed(fn, defined):
    """Names whose annotation proves the kind, so a later assignment cannot turn them back into an int."""
    out = {}
    if fn is None:
        return out
    a = fn.args
    for arg in a.posonlyargs + a.args + a.kwonlyargs + ([a.vararg] if a.vararg else []) \
            + ([a.kwarg] if a.kwarg else []):
        kind = _lp_annotation_kind(arg.annotation, defined)
        if kind is not None:
            out[arg.arg] = kind
    for node in _walk_own(fn.body):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            kind = _lp_annotation_kind(node.annotation, defined)
            if kind is not None:
                out[node.target.id] = kind
    return out


def _lp_assign(target, value, env, defined, fixed=None):
    if isinstance(target, ast.Name):
        if target.id in env:
            env[target.id] = fixed[target.id] if fixed and target.id in fixed \
                else _lp_join(env.get(target.id), value)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for e in target.elts:
            _lp_assign(e.value if isinstance(e, ast.Starred) else e, _LP_UNKNOWN, env, defined)
    elif isinstance(target, ast.Subscript):
        _lp_eval(target.value, env, defined, None)
        if not isinstance(target.slice, ast.Slice):
            _lp_eval(target.slice, env, defined, None)
    elif isinstance(target, ast.Attribute):
        _lp_eval(target.value, env, defined, None)


def _lp_iter_value(it, env, defined):
    """The joined value of a `for` target over a literal sequence (or a name bound once to one)."""
    if isinstance(it, (ast.List, ast.Tuple, ast.Set)):
        els = [_lp_eval(x, env, defined, None) for x in it.elts]
        v = None
        for e in els:
            v = _lp_join(v, e)
        return v
    if isinstance(it, ast.Dict):
        v = None
        for k in it.keys:
            if k is not None:
                v = _lp_join(v, _lp_eval(k, env, defined, None))
        return v
    return None


def _lp_safe_literal_seqs(fn):
    """Names assigned exactly once from a literal sequence of constants and never stored again or
    passed to a method (which could change what iteration yields)."""
    if fn is None:
        return {}
    assigned = {}
    unsafe = set()
    for node in _walk_own(fn.body):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            for t in targets:
                if isinstance(t, ast.Name):
                    if t.id in assigned or not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                        unsafe.add(t.id)
                    else:
                        assigned[t.id] = value
                elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                    unsafe.add(t.value.id)
                elif isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
                    unsafe.add(t.value.id)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                unsafe.add(node.target.id)
            elif isinstance(node.target, ast.Subscript) and isinstance(node.target.value, ast.Name):
                unsafe.add(node.target.value.id)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            tg = node.target
            for n in ast.walk(tg):
                if isinstance(n, ast.Name):
                    unsafe.add(n.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name):
            unsafe.add(node.func.value.id)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    for n in ast.walk(item.optional_vars):
                        if isinstance(n, ast.Name):
                            unsafe.add(n.id)
    out = {}
    for name, value in assigned.items():
        if name in unsafe:
            continue
        vals = []
        ok = True
        for x in value.elts:
            if not isinstance(x, (ast.Constant, ast.UnaryOp, ast.BinOp)):
                ok = False
                break
            v = _lp_eval(x, {}, _Defined(), None)
            if v is None or v[0] not in _LP_INTS or v[1] is None:
                ok = False
                break
            vals.append(v)
        if ok and vals:
            out[name] = vals
    return out


def _lp_run(stmts, env, defined, fixed=None, seqmap=None):
    if seqmap is None:
        seqmap = {}
    for s in stmts:
        if isinstance(s, ast.Assign):
            v = _lp_eval(s.value, env, defined, None)
            for t in s.targets:
                _lp_assign(t, v, env, defined, fixed)
        elif isinstance(s, ast.AnnAssign):
            if s.value is not None:
                _lp_assign(s.target, _lp_eval(s.value, env, defined, None), env, defined, fixed)
        elif isinstance(s, ast.AugAssign):
            if isinstance(s.target, ast.Name):
                old = env.get(s.target.id)
                virt = ast.BinOp(left=ast.Name(id=s.target.id, ctx=ast.Load()), op=s.op, right=s.value)
                v = _lp_join(old, _lp_eval(virt, env, defined, None))
                if s.target.id in env:
                    env[s.target.id] = fixed[s.target.id] if fixed and s.target.id in fixed else v
            else:
                _lp_eval(ast.BinOp(left=s.target, op=s.op, right=s.value), env, defined, None)
        elif isinstance(s, (ast.For, ast.AsyncFor)):
            it = s.iter
            if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range' \
                    and 'range' not in defined and not it.keywords and 1 <= len(it.args) <= 3 \
                    and not any(isinstance(a, ast.Starred) for a in it.args):
                vals = [_lp_eval(a, env, defined, None) for a in it.args]
                if all(v[0] in _LP_INTS and v[1] is not None for v in vals):
                    lo = min(v[1] for v in vals)
                    hi = max(v[2] for v in vals)
                    iv = _lp_int(lo, hi)
                else:
                    iv = _lp_int()
            else:
                lit = _lp_iter_value(it, env, defined)
                if lit is not None:
                    iv = lit
                elif isinstance(it, ast.Name) and it.id in seqmap:
                    iv = None
                    for v in seqmap[it.id]:
                        iv = _lp_join(iv, v)
                else:
                    _lp_eval(it, env, defined, None)
                    iv = _LP_OTHER if _lp_nonint_seq(it, getattr(defined, 'containers', ())) else _LP_UNKNOWN
            _lp_assign(s.target, iv, env, defined, fixed)
            _lp_run(s.body, env, defined, fixed, seqmap)
            _lp_run(s.orelse, env, defined, fixed, seqmap)
        elif isinstance(s, ast.While):
            _lp_eval(s.test, env, defined, None)
            _lp_run(s.body, env, defined, fixed, seqmap)
            _lp_run(s.orelse, env, defined, fixed, seqmap)
        elif isinstance(s, ast.If):
            _lp_eval(s.test, env, defined, None)
            _lp_run(s.body, env, defined, fixed, seqmap)
            _lp_run(s.orelse, env, defined, fixed, seqmap)
        elif isinstance(s, ast.Try):
            _lp_run(s.body, env, defined, fixed, seqmap)
            _lp_run(s.orelse, env, defined, fixed, seqmap)
            for h in s.handlers:
                _lp_eval(h.type, env, defined, None)
                if h.name:
                    env[h.name] = _lp_join(env.get(h.name), _LP_OTHER)
                _lp_run(h.body, env, defined, fixed, seqmap)
            _lp_run(s.finalbody, env, defined, fixed, seqmap)
        elif isinstance(s, (ast.With, ast.AsyncWith)):
            for item in s.items:
                _lp_eval(item.context_expr, env, defined, None)
                if item.optional_vars is not None:
                    _lp_assign(item.optional_vars, _LP_UNKNOWN, env, defined, fixed)
            _lp_run(s.body, env, defined, fixed, seqmap)
        elif isinstance(s, ast.Return):
            _lp_eval(s.value, env, defined, None)
        elif isinstance(s, ast.Raise):
            _lp_eval(s.exc, env, defined, None)
            _lp_eval(s.cause, env, defined, None)
        elif isinstance(s, ast.Assert):
            _lp_eval(s.test, env, defined, None)
            _lp_eval(s.msg, env, defined, None)
        elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        else:
            for c in ast.iter_child_nodes(s):
                if isinstance(c, ast.expr):
                    _lp_eval(c, env, defined, None)


def _lp_reason(defs, module_stmts, defined):
    """The first local-proof failure among these defs (or the module code when `defs` is None), or None."""
    for fn in (defs if defs is not None else [None]):
        if fn is None:
            stmts = module_stmts
            params = ()
        else:
            stmts = fn.body
            params = _lp_params(fn)
        names = (set(params) | _lp_locals(stmts)) - _lp_globals(stmts)
        env = {n: None for n in names}
        fixed = _lp_fixed(fn, defined) if fn is not None else {}
        for p in params:
            env[p] = fixed.get(p, _LP_UNKNOWN)
        seqmap = _lp_safe_literal_seqs(fn)
        for _pass in range(12):
            old = dict(env)
            _lp_run(stmts, env, defined, fixed, seqmap)
            changed = False
            for n, v in list(env.items()):
                if v != old.get(n):
                    changed = True
                    if _pass >= 1 and v is not None:
                        if v[0] in _LP_INTS:
                            env[n] = _lp_int()
                        elif v[0] == 'unknown':
                            env[n] = _LP_UNKNOWN
            if not changed:
                break
        for n, v in env.items():
            if v is not None and v[0] in _LP_INTS:
                if v[1] is None or v[2] is None:
                    return 'the int local %s is not proven to fit int64' % n
                if v[1] < _LP_I64_MIN or v[2] > _LP_I64_MAX:
                    return 'the int local %s is not proven to fit int64' % n
        discarded = set()
        for node in _walk_own(stmts):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                discarded.add(id(node.value))
        bad = []
        for node in _walk_own(stmts):
            if isinstance(node, ast.AugAssign):
                _lp_eval(ast.BinOp(left=node.target, op=node.op, right=node.value), env, defined, bad)
            elif isinstance(node, (ast.BinOp, ast.UnaryOp)):
                _lp_eval(node, env, defined, bad)
            elif isinstance(node, ast.Call) and id(node) not in discarded:
                v = _lp_eval(node, env, defined, bad)
                if v is _LP_UNKNOWN and _lp_unproven_call(node, defined):
                    _lp_bad(bad, 'a call result not proven to fit int64')
            if bad:
                return bad[0]
    return None


def _lp_builtin_len_arg(node):
    """The argument shapes whose len() is a built-in container length, not a program class's __len__."""
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.JoinedStr)):
        return True
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (str, bytes, bytearray))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _lp_builtin_len_arg(node.left) and _lp_builtin_len_arg(node.right)
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name) and f.id in ('str', 'list', 'tuple', 'set', 'dict', 'frozenset', 'bytes', 'bytearray',
                                               'sorted', 'reversed'):
            return True
        if isinstance(f, ast.Attribute) and f.attr in ('split', 'rsplit', 'splitlines', 'keys', 'values', 'items',
                                                       'copy', 'encode'):
            return _lp_builtin_len_arg(f.value)
    return False


def _lp_unproven_call(node, defined):
    """True when this call's result is not proven to be non-int or to fit int64. A call of the program's own function is
    left to the transitive marked-function rule; a class call builds an object, and the known builtins/methods are typed
    by _lp_eval, so what remains here is a builtin or method that can return an int (round, hash, get, ...)."""
    f = node.func
    if isinstance(f, ast.Name):
        return f.id not in defined and f.id not in getattr(defined, 'classes', ())
    if isinstance(f, ast.Attribute):
        return f.attr not in defined and f.attr in _LP_INT_RESULT_METHODS
    return False


# Is there any int at all?  A program whose whole text contains no construct that can make an int has no int arithmetic by
# rule 3 ("values known to be float, which need no bigint at all"): every parameter, item, attribute and call result is then
# non-int, so the local-proof demotion of an ambiguous `a * b` would be a false positive and would move a float-only program
# off the typed path.  This is one-sided: a construct this scan does not recognise as int-producing counts as one (the scan
# never proves a value int, so a miss only keeps the more conservative local-proof rules).
def enabled():
    """The marking is for programs written in Python (AIL_SURFACE=python, set by ail_chatgpt for a Python-syntax entry): their
    int is Python's. A program written in the AIL syntax has the language's own int64 (catchable OverflowError, wrapping_*)."""
    return os.environ.get('AIL_SURFACE') == 'python'


def marked(tree, local=True):
    """{unit name: reason} for every marked unit of the module: each def (by its own name; a method by the method name, a nested
    def by its own name) and '<module>' for the module-level code. A unit that contains a marked nested def is marked too.
    `local=False` keeps only the constructs that make a big int without an overflow (the pre-B1 hard marks); it is used to
    let a program that only the typed path can build keep the typed path instead of failing on a rule-4 demotion."""
    if not enabled():
        return {}
    module_values = {}
    written = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            written.update(node.names)
    for stmt in getattr(tree, 'body', ()):
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id in written:
            value = _const_int(stmt.value)
            if value is not None:
                module_values[stmt.targets[0].id] = value
    units = {}                     # name -> list of bodies (several defs may share a name: methods)
    parent_of = {}
    defined = set()
    classes = set()

    def collect(body, owner):
        for s in body:
            stack = [s]
            while stack:
                n = stack.pop()
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined.add(n.name)
                    units.setdefault(n.name, []).append(n)
                    parent_of.setdefault(n.name, set()).add(owner)
                    collect(n.body, n.name)
                elif isinstance(n, ast.ClassDef):
                    classes.add(n.name)
                    for c in n.body:
                        stack.append(c)
                else:
                    stack.extend(ast.iter_child_nodes(n))
    top = getattr(tree, 'body', [])
    collect(top, '<module>')
    defined = _Defined(defined)
    defined.classes = frozenset(classes)
    reason, calls = {}, {}
    helper_big = {}
    for m in ast.walk(tree):
        if isinstance(m, ast.Call) and isinstance(m.func, ast.Name) and m.func.id in _MATH_HELPERS:
            helper_big[m.func.id] = m.func.id.replace('_ail_math_', '')
    for h in _MATH_HELPERS & defined:
        if h in helper_big:
            reason[h] = 'a call of math.%s' % helper_big[h]
    module_body = [s for s in top if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    module_nodes = list(_walk_own(module_body))
    units['<module>'] = None
    store_units = {}
    for unit, defs in units.items():
        body = module_nodes if defs is None else [m for d in defs for m in _walk_own(d.body)]
        for node in body:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                store_units.setdefault(node.id, set()).add(unit)
    for name, defs in units.items():
        nodes = module_nodes if defs is None else [m for d in defs for m in _walk_own(d.body)]
        # Another unit storing the variable can make it big before this one's power: then the
        # module literal says nothing about the value there. Stores in this same unit are filtered
        # by source line inside _own_reason.
        values = {g: v for g, v in module_values.items()
                  if store_units.get(g, set()) - {'<module>'} <= {name}}
        r = _own_reason(nodes, defined, values)
        if r:
            reason[name] = r
        if local:
            lr = _lp_reason(defs, module_body if defs is None else None, defined)
            if lr and name not in reason:
                reason[name] = lr
        cs = set()
        for m in nodes:
            if isinstance(m, ast.Call):
                f = m.func
                nm = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                if nm in defined:
                    cs.add(nm)
        calls[name] = cs
    changed = True
    while changed:                 # callers of a marked unit, and the unit around a marked nested def
        changed = False
        for name in units:
            if name in reason:
                continue
            hit = next((c for c in sorted(calls[name]) if c in reason), None)
            if hit is not None:
                reason[name] = 'it calls %s(), which can need a big int (%s)' % (hit, reason[hit]); changed = True
        for name, owners in parent_of.items():
            if name in reason:
                for o in owners:
                    if o != '<module>' and o not in reason:
                        reason[o] = 'it contains %s(), which can need a big int (%s)' % (name, reason[name]); changed = True
    return reason


def local_int_bounds(fn, defined):
    """The fixed-point local value of every name of `fn` (the same environment `_lp_reason` checks), or an
    empty dict when this is not a function.  A name with an int value whose bounds are complete and fit
    int64 is proven; every other int local is the caller's tint candidate."""
    stmts = fn.body if fn is not None else []
    params = _lp_params(fn) if fn is not None else ()
    names = (set(params) | _lp_locals(stmts)) - _lp_globals(stmts)
    env = {n: None for n in names}
    fixed = _lp_fixed(fn, defined)
    for p in params:
        env[p] = fixed.get(p, _LP_UNKNOWN)
    seqmap = _lp_safe_literal_seqs(fn)
    for _pass in range(12):
        old = dict(env)
        _lp_run(stmts, env, defined, fixed, seqmap)
        changed = False
        for n, v in list(env.items()):
            if v != old.get(n):
                changed = True
                if _pass >= 1 and v is not None:
                    if v[0] in _LP_INTS:
                        env[n] = _lp_int()
                    elif v[0] == 'unknown':
                        env[n] = _LP_UNKNOWN
        if not changed:
            break
    return env


def proven_int_names(fn, defined):
    """The int locals of `fn` the local rules prove fit int64 (complete bounds inside the int64 range)."""
    out = set()
    for n, v in local_int_bounds(fn, defined).items():
        if v is not None and v[0] in _LP_INTS and v[1] is not None and v[2] is not None \
                and v[1] >= _LP_I64_MIN and v[2] <= _LP_I64_MAX:
            out.add(n)
    return out


def _range_nonneg(iter_node):
    """A `range(start, stop, step)` whose start is a non-negative constant and whose step is positive."""
    if not (isinstance(iter_node, ast.Call) and isinstance(iter_node.func, ast.Name)
            and iter_node.func.id == 'range' and not iter_node.keywords):
        return False
    args = iter_node.args
    if not 1 <= len(args) <= 3 or any(isinstance(a, ast.Starred) for a in args):
        return False
    start = 0 if len(args) == 1 else _const_int(args[0])
    step = 1 if len(args) < 3 else _const_int(args[2])
    return start is not None and start >= 0 and step is not None and step > 0


def range_nonneg_names(fn):
    """Names that are non-negative at every use because the function binds them only as the counter of a
    `for` over a range with a non-negative start and a positive step.  A name that is also a parameter, a
    global, or the target of any other store (an assignment, an augmented assignment, another loop, a
    comprehension) may hold a negative value, so it is excluded."""
    if fn is None:
        return set()
    targets = {}
    counters = set()
    for node in _walk_own(fn.body):
        if isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name) \
                and _range_nonneg(node.iter):
            counters.add(node.target.id)
            targets[id(node.target)] = node.target.id
    other = set()
    for node in _walk_own(fn.body):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) \
                and targets.get(id(node)) is None:
            other.add(node.id)
    return counters - other - set(_lp_params(fn)) - _lp_globals(fn.body)
