"""The surface should be Python, because Python is already in the model's weights.

A custom 21-verb notation was built first and measured against the same twelve tasks. It wins on
code and loses on everything once the manual is counted, because a model that has never seen a
notation cannot write it without one: 116 tokens of Python against 89 + a 649-token specification.

So this front end takes the Python a model already writes and lowers it to one fused C loop:

    sum(v*v for v in xs if v % 2)
    max(abs(v) for v in xs)
    sum(1 for v in xs if v < 0)

Twelve expressions written by a model that had never seen this project compiled as they stood and
all twelve were correct.

## Two arithmetics

Compiling to C hands the program C's integer semantics, which are not Python's in two places that
produce wrong answers silently rather than errors:

    %  and //    Python floors toward negative infinity, C truncates toward zero. (-7) % 3 is 2 in
                 Python and -1 in C. They agree when the left operand is non-negative or the
                 division is exact, which is why the twelve all passed without anything below.
    + - * abs    signed overflow is undefined in C; Python's integers do not overflow at all.

`strict=True` closes both: `%` and `//` floor, and the arithmetic traps instead of being undefined.
Only the helpers an expression actually reaches are emitted, so a program that never divides carries
no division helper -- the same property the rest of the layer has.

Strict is not the default because it costs time and the cost should be measured, not assumed.
"""
import ast

from pipeline import PipelineError, shared_object

FOLD_CALLS = {'sum': 'sum', 'max': 'max', 'min': 'min', 'any': 'any', 'all': 'all', 'len': 'count'}

BINOP = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.FloorDiv: '/', ast.Mod: '%',
         ast.BitAnd: '&', ast.BitOr: '|', ast.BitXor: '^', ast.LShift: '<<', ast.RShift: '>>'}
CMPOP = {ast.Eq: '==', ast.NotEq: '!=', ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>='}
BOOLOP = {ast.And: '&&', ast.Or: '||'}

HELPERS = {
    'ail_die': ('static void ail_die(const char *w) {\n'
                '    fputs(w, stderr); fputc(10, stderr); _Exit(1);\n}\n'),
    'pymod': ('static int64_t pymod(int64_t a, int64_t b) {\n'
              '    if (b == 0) ail_die("integer modulo by zero");\n'
              '    if (b == -1) return 0;                      /* INT64_MIN % -1 would overflow */\n'
              '    int64_t r = a % b;\n'
              '    return (r != 0 && ((r < 0) != (b < 0))) ? r + b : r;\n}\n'),
    'pydiv': ('static int64_t pydiv(int64_t a, int64_t b) {\n'
              '    if (b == 0) ail_die("integer division by zero");\n'
              '    if (b == -1) { if (a == INT64_MIN) ail_die("integer overflow"); return -a; }\n'
              '    int64_t q = a / b, r = a % b;\n'
              '    return (r != 0 && ((r < 0) != (b < 0))) ? q - 1 : q;\n}\n'),
    'ck_add': ('static int64_t ck_add(int64_t a, int64_t b) {\n'
               '    int64_t r; if (__builtin_add_overflow(a, b, &r)) ail_die("integer overflow");\n'
               '    return r;\n}\n'),
    'ck_sub': ('static int64_t ck_sub(int64_t a, int64_t b) {\n'
               '    int64_t r; if (__builtin_sub_overflow(a, b, &r)) ail_die("integer overflow");\n'
               '    return r;\n}\n'),
    'ck_mul': ('static int64_t ck_mul(int64_t a, int64_t b) {\n'
               '    int64_t r; if (__builtin_mul_overflow(a, b, &r)) ail_die("integer overflow");\n'
               '    return r;\n}\n'),
    'ck_neg': ('static int64_t ck_neg(int64_t a) {\n'
               '    if (a == INT64_MIN) ail_die("integer overflow");\n    return -a;\n}\n'),
    # Shifts. Python's `<<` widens without limit and its `>>` is an arithmetic shift of an
    # unbounded integer, so BOTH need a guard that C's own operators do not give:
    #   * a negative count is a ValueError in Python and UNDEFINED in C;
    #   * a count >= 64 is defined in Python (`1 << 64` is exact; `1024 >> 64` is 0) and UNDEFINED
    #     in C, which is why `1024 >> 64` answered 1024 here;
    #   * `x << k` can leave int64 even for small k, and `__builtin_mul_overflow` against 2**k is
    #     the exact test -- a shift IS that multiply, so the same guard answers it without a second
    #     rule that could drift from the first.
    # A right shift by 64 or more is not an error: Python's answer is 0 for a non-negative value
    # and -1 for a negative one, which is what an arithmetic shift converges to, so it is computed
    # rather than refused.
    # The FIRST version of this guard built its multiplier as `(int64_t)1 << b` and handed that to
    # `__builtin_mul_overflow`. At b == 63 the multiplier itself overflows, so the guard contained
    # the very defect it was added to stop, and `1 << 63` still answered INT64_MIN. The bound is
    # therefore computed as an UNSIGNED power of two, where every value in range is representable:
    # `a << b` is exact exactly when `a` fits in 64 - b signed bits, i.e. |a| < 2**(63-b) for a
    # non-negative `a` and |a| <= 2**(63-b) for a negative one. `-(a + 1)` is |a| - 1 and is used
    # instead of `-a` because negating INT64_MIN is itself undefined.
    'ck_shl': ('static int64_t ck_shl(int64_t a, int64_t b) {\n'
               '    if (b < 0) ail_raise_value_adopt(ail_exception_new(AIL_EXC_VALUE,\n'
               '        (const uint8_t *)"negative shift count",\n'
               '        (int64_t)sizeof "negative shift count" - 1, 1));\n'
               '    if (b >= 64) { if (a != 0) ail_die("integer overflow"); return 0; }\n'
               '    uint64_t lim = (uint64_t)1 << (63 - b);\n'
               '    uint64_t mag = (a >= 0) ? (uint64_t)a : (uint64_t)(-(a + 1));\n'
               '    if (mag >= lim) ail_die("integer overflow");\n'
               '    return (int64_t)((uint64_t)a << b);\n}\n'),
    # `x << k` with a literal 0 <= k < 64: the same exact test as ck_shl, as a round trip. The shift
    # lost nothing exactly when shifting the result back gives `a` again; that is a compare and a
    # branch beside the shift the program needed anyway, where ck_shl's lim/mag/branch sequence is
    # six instructions even for a constant `b`. It sits in the inner loop of every rolling-key or
    # hash computation.
    'ck_shlk': ('static inline __attribute__((always_inline)) int64_t ck_shlk(int64_t a, int s) {\n'
                '    int64_t r = (int64_t)((uint64_t)a << s);\n'
                '    if (__builtin_expect((r >> s) != a, 0)) ail_die("integer overflow");\n'
                '    return r;\n}\n'),
    'ck_shr': ('static int64_t ck_shr(int64_t a, int64_t b) {\n'
               '    if (b < 0) ail_raise_value_adopt(ail_exception_new(AIL_EXC_VALUE,\n'
               '        (const uint8_t *)"negative shift count",\n'
               '        (int64_t)sizeof "negative shift count" - 1, 1));\n'
               '    if (b >= 64) return a < 0 ? -1 : 0;\n'
               '    return a >> b;\n}\n'),
}
HELPER_ORDER = ('ail_die', 'pymod', 'pydiv', 'ck_add', 'ck_sub', 'ck_mul', 'ck_neg',
                'ck_shl', 'ck_shlk', 'ck_shr')
STRICT_BIN = {ast.Mod: 'pymod', ast.FloorDiv: 'pydiv',
              ast.Add: 'ck_add', ast.Sub: 'ck_sub', ast.Mult: 'ck_mul',
              # `<<` and `>>` were the ONLY binary operators emitting bare C, with no guard at all,
              # until 2026-09-15 -- found by a sanitizer configuration built for something else.
              # Four different wrong answers came out of it, and one is INSIDE the declared int64
              # domain, so it is not even a domain violation, just wrong:
              #     1 << 63     CPython 9223372036854775808    compiled -9223372036854775808
              #     1 << 64     CPython 18446744073709551616   compiled 1
              #     1 << -1     CPython raises ValueError      compiled -9223372036854775808
              #     1024 >> 64  CPython 0                      compiled 1024
              ast.LShift: 'ck_shl', ast.RShift: 'ck_shr'}


class Unsupported(PipelineError):
    """Outside the subset. The message names the construct, so the boundary stays measurable."""


def _number_constant(node):
    """The value of an int/float literal, with any unary signs (`-4.0`, `+(-2)`), else None."""
    sign = 1
    while isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        if isinstance(node.op, ast.USub):
            sign = -sign
        node = node.operand
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return sign * node.value
    return None


_CONST_INT_LIMIT = 1 << 22
_SPECIAL_INT_LIMIT = 1 << 24


def int_constant(node, _limit=_CONST_INT_LIMIT):
    """The exact Python value of an all-integer constant expression, else None.

    Python evaluates `(1 << 63) - 1` and `2**65 - 2**65` exactly, even though an intermediate is
    outside int64.  Folding the whole expression here, with Python's unbounded integers, lets a
    caller emit the one in-range result instead of trapping on the intermediate.  It also keeps a
    constant expression from changing width at each operator, which is what C would do.

    None is returned when the node is not made only of int constants, when an operation would not
    produce an int (`2 ** -1` is a float), when it fails (`1 // 0`), or when the value grows past
    a safe size.  The last case is deliberately not folded: the runtime's own overflow guard is
    the right answer for it, and computing `2 ** 1000000000` here would only cost memory.

    Zero and the base 0/1/-1 of a power are decided before the other operand has to fit the size
    limit: `0 * (1 << 5000)` and `0 ** (1 << 5000)` have int64 results even though the left/right
    operand is large.  The exponent of such a power is retried at a much larger limit so its sign
    and parity are still known.
    """
    if isinstance(node, ast.Constant):
        return node.value if type(node.value) is int else None
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.USub, ast.UAdd)):
            return None
        value = int_constant(node.operand, _limit)
        if value is None:
            return None
        return -value if isinstance(node.op, ast.USub) else value
    if not isinstance(node, ast.BinOp):
        return None
    op = type(node.op)
    if op is ast.Pow:
        right = int_constant(node.right, _limit)
        if right == 0:
            left = int_constant(node.left, _limit)
            if left is None:
                left = int_constant(node.left, _SPECIAL_INT_LIMIT)
            return None if left is None else 1
        left = int_constant(node.left, _limit)
        if left in (0, 1, -1):
            if right is None:
                right = int_constant(node.right, _SPECIAL_INT_LIMIT)
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
        left = int_constant(node.left, _limit)
        right = int_constant(node.right, _limit)
        if left == 0 or right == 0:
            if left is None:
                left = int_constant(node.left, _SPECIAL_INT_LIMIT)
            if right is None:
                right = int_constant(node.right, _SPECIAL_INT_LIMIT)
            if left is None or right is None:
                return None
            return 0
        if left is None or right is None:
            return None
    elif op is ast.LShift:
        left = int_constant(node.left, _limit)
        if left == 0:
            right = int_constant(node.right, _limit)
            if right is None:
                right = int_constant(node.right, _SPECIAL_INT_LIMIT)
            if right is not None and right >= 0:
                return 0
        right = int_constant(node.right, _limit)
        if left is None or right is None:
            return None
    else:
        left = int_constant(node.left, _limit)
        right = int_constant(node.right, _limit)
        if left is None or right is None:
            return None
    try:
        if op is ast.Add:
            result = left + right
        elif op is ast.Sub:
            result = left - right
        elif op is ast.Mult:
            if left and right and left.bit_length() + right.bit_length() > _limit:
                return None
            result = left * right
        elif op is ast.FloorDiv:
            result = left // right
        elif op is ast.Mod:
            result = left % right
        elif op is ast.Pow:
            if right < 0:
                return None
            if right == 0:
                result = 1
            elif left in (0, 1):
                result = left
            elif left == -1:
                result = -1 if right & 1 else 1
            elif left.bit_length() * right > _limit:
                return None
            else:
                result = left ** right
        elif op is ast.LShift:
            if right < 0:
                return None
            if left == 0:
                result = 0
            elif left.bit_length() + right > _limit:
                return None
            else:
                result = left << right
        elif op is ast.RShift:
            if right < 0:
                return None
            result = left >> right
        elif op is ast.BitAnd:
            result = left & right
        elif op is ast.BitOr:
            result = left | right
        elif op is ast.BitXor:
            result = left ^ right
        else:
            return None
    except (ArithmeticError, ValueError):
        return None
    return result if type(result) is int and result.bit_length() <= _limit else None


_I64_MIN = -(1 << 63)
_I64_MAX = (1 << 63) - 1
_CONST_BITS_LIMIT = 100000


def _int_constant_with_overflow(node):
    """The exact Python value of a constant integer expression and whether an AIL int64 would overflow."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, bool):
        value = int(node.value)
        return value, not (_I64_MIN <= value <= _I64_MAX)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        # `-9223372036854775808` is unary minus on the literal `2**63`.  The compiler emits
        # INT64_MIN for exactly that spelling (the literal itself never overflows), so the
        # intermediate is not a reason to refuse it here.  A computed `-(2**63)` is different:
        # it reaches the power first and is still caught.
        if (isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant)
                and type(node.operand.value) is int and node.operand.value == 1 << 63):
            return _I64_MIN, False
        value, overflow = _int_constant_with_overflow(node.operand)
        if value is None:
            return None, overflow
        value = -value if isinstance(node.op, ast.USub) else value
        return value, overflow or not (_I64_MIN <= value <= _I64_MAX)
    if not isinstance(node, ast.BinOp):
        return None, False
    left, left_overflow = _int_constant_with_overflow(node.left)
    right, right_overflow = _int_constant_with_overflow(node.right)
    overflow = left_overflow or right_overflow
    if left is None or right is None:
        return None, overflow
    if isinstance(node.op, ast.Add):
        value = left + right
    elif isinstance(node.op, ast.Sub):
        value = left - right
    elif isinstance(node.op, ast.Mult):
        value = left * right
    elif isinstance(node.op, ast.Pow):
        if right < 0:
            return None, overflow
        if right == 0 or left in (0, 1):
            value = 1
        elif left == -1:
            value = -1 if right & 1 else 1
        else:
            if max(1, abs(left).bit_length()) * right > _CONST_BITS_LIMIT:
                return None, True
            value = left ** right
    elif isinstance(node.op, ast.LShift):
        if right < 0:
            return None, overflow
        if left == 0:
            value = 0
        else:
            if max(1, abs(left).bit_length()) + right > _CONST_BITS_LIMIT:
                return None, True
            value = left << right
    else:
        return None, overflow
    return value, overflow or not (_I64_MIN <= value <= _I64_MAX)


def refuse_unrepresentable_delete_bounds(target):
    """Refuse a `del` whose constant index or slice bound cannot be evaluated as an AIL int64."""
    if isinstance(target.slice, ast.Slice):
        bounds = (target.slice.lower, target.slice.upper, target.slice.step)
        what = 'slice bound'
    else:
        bounds = (target.slice,)
        what = 'index'
    for bound in bounds:
        if bound is None:
            continue
        value, overflow = _int_constant_with_overflow(bound)
        if not overflow and (value is None or _I64_MIN <= value <= _I64_MAX):
            continue
        refusal = Unsupported(
            'del %s: the constant %s %s cannot be evaluated within the 64-bit signed integer range '
            'of an AIL int, so it cannot be used here (CPython\'s int is unbounded)' % (
                ast.unparse(target), what, ast.unparse(bound)))
        refusal.source_line = getattr(target, 'lineno', None)
        raise refusal


def refuse_complex_pow(node):
    """`(-4.0) ** 0.5`: a negative base to a fractional power is a complex number in Python, and this
    language has no complex type. Constant operands are refused here, at compile time; any other
    operands stop the program at run time with the same words (never a quiet nan)."""
    base, exponent = _number_constant(node.left), _number_constant(node.right)
    if (base is not None and exponent is not None and base < 0 and isinstance(exponent, float)
            and exponent == exponent and abs(exponent) != float('inf') and exponent != int(exponent)):
        refusal = Unsupported('a negative number raised to a fractional power is a complex number in Python, '
                              'and AIL has no complex type; take the absolute value first or use an integer exponent')
        refusal.source_line = getattr(node, 'lineno', None)
        raise refusal


def _use(need, *names):
    need.update(names)
    need.add('ail_die')


def _c_expr(node, var, need=None):
    """A Python expression over the loop variable, as C.

    `need` is a set collecting the helpers the expression turns out to require. Passing one selects
    Python's arithmetic; passing None keeps C's and emits nothing.
    """
    rec = lambda n: _c_expr(n, var, need)
    if isinstance(node, ast.Name):
        if node.id != var:
            raise Unsupported('free variable %r; only the loop variable is in scope' % node.id)
        return 'x'
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return '1' if node.value else '0'
        if not isinstance(node.value, int):
            raise Unsupported('non-integer constant %r' % (node.value,))
        return str(node.value)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            if need is not None:
                _use(need, 'ck_neg')
                return 'ck_neg(%s)' % rec(node.operand)
            return '(-%s)' % rec(node.operand)
        if isinstance(node.op, ast.Not):
            return '(!%s)' % rec(node.operand)
        if isinstance(node.op, ast.UAdd):
            return rec(node.operand)
        if isinstance(node.op, ast.Invert):
            return '(~%s)' % rec(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in BINOP:
        if need is not None and type(node.op) in STRICT_BIN:
            h = STRICT_BIN[type(node.op)]
            _use(need, h)
            return '%s(%s, %s)' % (h, rec(node.left), rec(node.right))
        return '(%s %s %s)' % (rec(node.left), BINOP[type(node.op)], rec(node.right))
    if isinstance(node, ast.BoolOp):
        return '(%s)' % (' %s ' % BOOLOP[type(node.op)]).join(rec(v) for v in node.values)
    if isinstance(node, ast.Compare):
        # Python chains: -50 <= v <= 50 is two comparisons and C needs both spelled out.
        parts, left = [], node.left
        for op, right in zip(node.ops, node.comparators):
            if type(op) not in CMPOP:
                raise Unsupported('comparison %s' % type(op).__name__)
            parts.append('(%s %s %s)' % (rec(left), CMPOP[type(op)], rec(right)))
            left = right
        return '(%s)' % ' && '.join(parts)
    if isinstance(node, ast.IfExp):
        return '(%s ? %s : %s)' % (rec(node.test), rec(node.body), rec(node.orelse))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == 'abs' and len(node.args) == 1:
            inner = rec(node.args[0])
            if need is not None:
                # abs(INT64_MIN) has no int64 answer. Python's abs does, because Python's integers
                # do not end; at this width trapping is the only honest option.
                _use(need, 'ck_neg')
                return '(%s < 0 ? ck_neg(%s) : (%s))' % (inner, inner, inner)
            return '(%s < 0 ? -(%s) : (%s))' % (inner, inner, inner)
        if node.func.id == 'int' and len(node.args) == 1:
            return rec(node.args[0])
        raise Unsupported('call to %s() inside the element expression' % node.func.id)
    raise Unsupported(type(node).__name__)


def _fold(call, source, need=None):
    """One fold: the verb, the element expression, the guards, and the array it reads."""
    if (isinstance(call, ast.Compare) and len(call.ops) == 1
            and isinstance(call.ops[0], (ast.In, ast.NotIn))
            and isinstance(call.comparators[0], ast.Name)
            and call.comparators[0].id == source):
        # `0 in xs` is a membership test over the source, i.e. `any(v == 0 for v in xs)`. A model
        # wrote it that way because it is the natural Python; refusing it would make the subset's
        # boundary a fact about this parser rather than about the shape of the computation.
        probe = _c_expr(call.left, '<none>', need)     # not an identifier, so no Name can match it
        eq = '(x == %s)' % probe
        return ('any', eq if isinstance(call.ops[0], ast.In) else '(!%s)' % eq, [])
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
        raise Unsupported('the outermost expression must be a call to one of %s'
                          % ' '.join(sorted(FOLD_CALLS)))
    if call.func.id == 'int' and len(call.args) == 1:
        return _fold(call.args[0], source, need)       # int(any(...)) -- a model wrote this
    if call.func.id not in FOLD_CALLS:
        raise Unsupported('%s() is not a fold; use one of %s'
                          % (call.func.id, ' '.join(sorted(FOLD_CALLS))))
    fold = FOLD_CALLS[call.func.id]
    if len(call.args) != 1:
        raise Unsupported('%s() with %d arguments' % (call.func.id, len(call.args)))
    arg = call.args[0]

    if isinstance(arg, ast.Name):                      # sum(xs), min(xs), max(xs)
        if arg.id != source:
            raise Unsupported('iterating %r; this program reads %r' % (arg.id, source))
        return fold, 'x', []
    if not isinstance(arg, (ast.GeneratorExp, ast.ListComp)):
        raise Unsupported('%s() over %s' % (call.func.id, type(arg).__name__))
    if len(arg.generators) != 1:
        raise Unsupported('%d nested for-clauses; one loop only' % len(arg.generators))
    gen = arg.generators[0]
    if gen.is_async:
        raise Unsupported('async for')
    if not isinstance(gen.target, ast.Name):
        raise Unsupported('tuple unpacking in the for-clause')
    if not isinstance(gen.iter, ast.Name) or gen.iter.id != source:
        raise Unsupported('iterating something other than %r' % source)
    var = gen.target.id
    return fold, _c_expr(arg.elt, var, need), [_c_expr(t, var, need) for t in gen.ifs]


def to_pipeline_c(text, source='xs', name='run', strict=False):
    """One C function: one loop, one accumulator, no allocation. Optionally Python's arithmetic."""
    try:
        tree = ast.parse(text.strip(), mode='eval')
    except SyntaxError as e:
        raise Unsupported('not a Python expression: %s' % e)
    need = set() if strict else None
    fold, elem, guards = _fold(tree.body, source, need)

    from pipeline import FOLDS
    init, step, result = FOLDS[fold]
    init = init.replace('LOW', 'INT64_MIN').replace('HIGH', 'INT64_MAX')
    if strict:
        # the accumulator overflows as readily as the element expression does
        if step == 'a+=x;':
            _use(need, 'ck_add'); step = 'a = ck_add(a, x);'
        elif step == 'a*=x;':
            _use(need, 'ck_mul'); step = 'a = ck_mul(a, x);'
    body = ''.join('        if (!%s) continue;\n' % g for g in guards)
    body += '        x = %s;\n' % elem

    head = '#include <stdint.h>\n#define T int64_t\n'
    if strict and need:
        head += '#include <stdio.h>\n#include <stdlib.h>\n'
        head += ''.join(HELPERS[h] for h in HELPER_ORDER if h in need)
    return (head + 'T %s(const T *src, int64_t n) {\n    %s\n'
            '    for (int64_t k = 0; k < n; k++) { T x = src[k];\n%s        %s\n    }\n'
            '    return %s;\n}\n' % (name, init, body, step, result))


def pipe_py(text, source='xs', strict=False):
    """Compile a Python expression to the leaf function and hand back a ctypes callable."""
    import ctypes
    from pipeline import _address
    c = to_pipeline_c(text, source, strict=strict)
    so = shared_object(c, prefix='z' if strict else 'y')
    fn = ctypes.CDLL(str(so)).run
    fn.restype = ctypes.c_int64

    def call(xs, n=None):
        p = ctypes.POINTER(ctypes.c_int64)
        return fn(ctypes.cast(_address(xs), p), ctypes.c_int64(len(xs) if n is None else n))

    call.c = c
    call.artifact = so
    return call
