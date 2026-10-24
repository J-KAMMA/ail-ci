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
               '    if (b < 0) ail_raise_named(AIL_EXC_VALUE);\n'
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
               '    if (b < 0) ail_raise_named(AIL_EXC_VALUE);\n'
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


_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1
_INT_FOLD_BITS = 4096


class _IntConstTooLarge(Exception):
    """A constant expression too large to evaluate safely at compile time."""


def _int_const_value(node):
    """The exact value of a purely integer constant expression, else None.

    Raises _IntConstTooLarge rather than allocating an arbitrarily large integer for `2 ** 10**9`
    or `1 << 10**9`; every value kept is at most _INT_FOLD_BITS bits.
    """
    if isinstance(node, ast.Constant):
        value = node.value if type(node.value) is int else None
        if value is not None and value.bit_length() > _INT_FOLD_BITS:
            raise _IntConstTooLarge
        return value
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.UAdd):
            return _int_const_value(node.operand)
        value = _int_const_value(node.operand)
        if value is None:
            return None
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.Invert):
            return ~value
        return None
    if not isinstance(node, ast.BinOp):
        return None
    left = _int_const_value(node.left)
    if left is None:
        return None
    right = _int_const_value(node.right)
    if right is None:
        return None
    op = node.op
    if isinstance(op, ast.Add):
        value = left + right
    elif isinstance(op, ast.Sub):
        value = left - right
    elif isinstance(op, ast.Mult):
        value = left * right
    elif isinstance(op, ast.FloorDiv):
        if right == 0:
            return None
        value = left // right
    elif isinstance(op, ast.Mod):
        if right == 0:
            return None
        value = left % right
    elif isinstance(op, ast.Pow):
        if right < 0:
            return None
        if left == 0:
            value = 1 if right == 0 else 0
        elif left == 1:
            value = 1
        elif left == -1:
            value = -1 if right & 1 else 1
        else:
            if right > _INT_FOLD_BITS:
                raise _IntConstTooLarge
            value = left ** right
    elif isinstance(op, ast.LShift):
        if right < 0:
            return None
        if left == 0:
            value = 0
        else:
            if left.bit_length() + right > _INT_FOLD_BITS:
                raise _IntConstTooLarge
            value = left << right
    elif isinstance(op, ast.RShift):
        if right < 0:
            return None
        value = left >> right
    elif isinstance(op, ast.BitAnd):
        value = left & right
    elif isinstance(op, ast.BitOr):
        value = left | right
    elif isinstance(op, ast.BitXor):
        value = left ^ right
    else:
        return None
    if value.bit_length() > _INT_FOLD_BITS:
        raise _IntConstTooLarge
    return value


def fold_int_constants(source):
    """Fold integer constant expressions to int64 literals and refuse out-of-range ones by name.

    A constant expression Python evaluates exactly but whose result does not fit int64 is the one
    case where a *constant* is still a difference: emitting the arithmetic would stop at run time
    with `integer overflow` even when the outer expression, as in `-(-2)**63`, is what Python's
    unbounded int can represent. Folding also keeps `2**63 - 1` and `-2**63` correct by building
    them as one literal instead of overflowing inside the expression. Non-constant expressions are
    left exactly as written for the run-time guards.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    encoded = source.encode('utf-8')
    starts = [0]
    for line in encoded.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    edits = []

    def refuse(node):
        refusal = Unsupported(
            'a constant integer expression overflows int64: its exact value does not fit in a '
            '64-bit signed integer (CPython computes it exactly because its int is unbounded; '
            "this language's int is int64, SEMANTICS section 1)")
        refusal.source_line = getattr(node, 'lineno', None)
        raise refusal

    def visit(node):
        if isinstance(node, (ast.BinOp, ast.UnaryOp)):
            try:
                value = _int_const_value(node)
            except _IntConstTooLarge:
                refuse(node)
            if value is not None:
                if not _INT64_MIN <= value <= _INT64_MAX:
                    refuse(node)
                start = starts[node.lineno - 1] + node.col_offset
                end = starts[node.end_lineno - 1] + node.end_col_offset
                edits.append((start, end, str(value).encode('ascii')))
                return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    if not edits:
        return source
    for start, end, replacement in sorted(edits, reverse=True):
        encoded = encoded[:start] + replacement + encoded[end:]
    return encoded.decode('utf-8')


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
        if not _INT64_MIN <= node.value <= _INT64_MAX:
            raise Unsupported('an integer literal outside int64: %d' % node.value)
        return str(node.value)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            # Python parses the literal -9223372036854775808 as a unary minus over the positive
            # literal 9223372036854775808, which does not fit any signed C type. The folded source
            # for INT64_MIN therefore reaches here as that spelling, and `ck_neg` would trap on the
            # very value the constant is meant to denote. Build it as INT64_MIN's two's-complement
            # definition instead; pyboxed, pyboxed2 and pyfunc already accept the same spelling.
            if (isinstance(node.operand, ast.Constant)
                    and type(node.operand.value) is int
                    and node.operand.value == 1 << 63):
                return '(-9223372036854775807LL - 1)'
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
