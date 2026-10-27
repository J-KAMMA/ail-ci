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


_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1


class _IntConstTooLarge(Exception):
    """A constant expression too large to evaluate safely at compile time."""


def _int_const_value(node):
    """The exact value of a purely integer constant expression, else None.

    Uses the generic folder's own exact evaluation, including its zero/base shortcuts and its
    wide shift budget, so this pass keeps the later constant-folding fixes rather than imposing a
    narrower limit.  Raises _IntConstTooLarge rather than allocating an arbitrarily large integer
    for `2 ** 10**9` or `1 << 10**9`.  A bool result (`True & True`) is left to the run time so
    it still prints as True.
    """
    import pyfunc as _pyfunc
    value = _pyfunc._const_int_expr(node)
    if value is _pyfunc._CONST_INT_NOT or isinstance(value, bool):
        return None
    if value is _pyfunc._CONST_INT_BIG:
        raise _IntConstTooLarge
    return int(value)


def fold_int_constants(source):
    """Fold integer constant expressions to int64 literals and refuse out-of-range ones by name.

    A constant expression Python evaluates exactly but whose result does not fit int64 is the one
    case where a *constant* is still a difference: emitting the arithmetic would stop at run time
    with `integer overflow` even when the outer expression, as in `-(-2)**63`, is what Python's
    unbounded int can represent. Folding also keeps `2**63 - 1` and `-2**63` correct by building
    them as one literal instead of overflowing inside the expression. INT64_MIN is always folded
    as well, because the pipeline emitter cannot spell that one value as a unary minus safely.
    Plain in-range arithmetic and non-constant expressions are left exactly as written, so the
    typed/general path choice and the context-specific diagnostics still see them.
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
    _too_large = object()
    values = {}
    inside = {}

    def const_value(node):
        key = id(node)
        if key not in values:
            try:
                values[key] = _int_const_value(node)
            except _IntConstTooLarge:
                values[key] = _too_large
        value = values[key]
        if value is _too_large:
            raise _IntConstTooLarge
        return value

    def overflows_inside(node):
        """True when a nested constant expression is outside int64 while `node` itself may fit."""
        key = id(node)
        if key not in inside:
            found = False
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.BinOp, ast.UnaryOp)):
                    try:
                        value = const_value(child)
                    except _IntConstTooLarge:
                        found = True
                    else:
                        if value is not None and not _INT64_MIN <= value <= _INT64_MAX:
                            found = True
                if not found and overflows_inside(child):
                    found = True
            inside[key] = found
        return inside[key]

    def refuse(node):
        refusal = Unsupported(
            'a constant integer expression overflows int64: its exact value is outside the '
            'signed 64-bit range and does not fit in a 64-bit signed integer (CPython computes '
            "it exactly because its int is unbounded, while this language's int is int64, "
            'SEMANTICS section 1)')
        refusal.source_line = getattr(node, 'lineno', None)
        raise refusal

    def is_maxsplit_argument(node, parent, grandparent):
        # The str.split/rsplit folder has its own, more specific refusal; leave that expression
        # to it so the existing maxsplit diagnostics are unchanged.
        if isinstance(parent, ast.keyword) and isinstance(grandparent, ast.Call):
            call, keyword = grandparent, parent
        elif isinstance(parent, ast.Call):
            call, keyword = parent, None
        else:
            return False
        if not (isinstance(call.func, ast.Attribute) and call.func.attr in ('split', 'rsplit')):
            return False
        if keyword is not None:
            return keyword.arg == 'maxsplit'
        return node in call.args[1:2]

    def visit(node, parent=None, grandparent=None):
        if isinstance(node, ast.JoinedStr):
            # An f-string's source text is observable in a debug field (`f"{expr=}"`), so leave
            # its expressions exactly as written; the emitters' own constant folders still run.
            return
        if isinstance(node, (ast.BinOp, ast.UnaryOp)):
            if is_maxsplit_argument(node, parent, grandparent):
                return
            try:
                value = const_value(node)
            except _IntConstTooLarge:
                refuse(node)
            if value is not None:
                if not _INT64_MIN <= value <= _INT64_MAX:
                    refuse(node)
                # Fold only when the arithmetic would overflow an int64 intermediate (as in
                # `2**63 - 1`) or when the value itself does not fit (refused above). Ordinary
                # in-range constants are left as written so the typed/general path choice and
                # context-specific diagnostics that read the expression tree are unchanged.
                if value != _INT64_MIN and not overflows_inside(node):
                    return
                start = starts[node.lineno - 1] + node.col_offset
                end = starts[node.end_lineno - 1] + node.end_col_offset
                edits.append((start, end, str(value).encode('ascii')))
                return
        for child in ast.iter_child_nodes(node):
            visit(child, node, parent)

    def identifier_byte(byte):
        return (48 <= byte <= 57 or 65 <= byte <= 90 or 97 <= byte <= 122
                or byte == 95 or byte >= 128)

    visit(tree)
    if not edits:
        return source
    for start, end, replacement in sorted(edits, reverse=True):
        # `1 and+(1 << 62)` becomes `1 and 461...`, not `1 and461...`: a rewritten expression
        # that starts or ends with a digit must not fuse with an adjacent name or keyword.
        if (start and 48 <= replacement[0] <= 57 and identifier_byte(encoded[start - 1])):
            replacement = b' ' + replacement
        if (end < len(encoded) and 48 <= replacement[-1] <= 57
                and identifier_byte(encoded[end])):
            replacement = replacement + b' '
        encoded = encoded[:start] + replacement + encoded[end:]
    return encoded.decode('utf-8')


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
_CONST_BITS_LIMIT = _CONST_INT_LIMIT


def _int_constant_with_overflow(node):
    """The exact Python value of a constant integer expression, and whether it leaves int64.

    The whole expression is folded with Python's unbounded integers, so an intermediate that is
    outside int64 is not a reason to refuse when the final value fits (the pre269 constant-index
    pass folds the same way).  The second item is True only for a constant expression whose exact
    final value leaves int64 or is too large to fold; a non-constant expression returns
    (None, False).  Bool leaves count as 0/1, as CPython uses them.
    """
    if isinstance(node, ast.Constant) and type(node.value) in (int, bool):
        value = int(node.value)
        return value, not (_I64_MIN <= value <= _I64_MAX)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value, uncomputable = _int_constant_with_overflow(node.operand)
        if value is None:
            return None, uncomputable
        value = -value if isinstance(node.op, ast.USub) else value
        return value, not (_I64_MIN <= value <= _I64_MAX)
    if not isinstance(node, ast.BinOp):
        return None, False
    op = type(node.op)
    left, left_bad = _int_constant_with_overflow(node.left)
    right, right_bad = _int_constant_with_overflow(node.right)
    unable = left_bad or right_bad
    if left is None or right is None:
        # `0 * x`, `0 & x` and `0 << x` have a decided result even when the other operand is too
        # large to fold.  A genuinely variable operand is still left for the compiler.
        if op in (ast.Mult, ast.BitAnd):
            if left == 0:
                return (0, False) if right_bad else (None, False)
            if right == 0:
                return (0, False) if left_bad else (None, False)
        if op is ast.LShift and left == 0:
            return (None, False) if not right_bad else (None, True)
        if op is ast.Pow and left == 1:
            return 1, False
        return None, unable
    try:
        if op is ast.Add:
            value = left + right
        elif op is ast.Sub:
            value = left - right
        elif op is ast.Mult:
            if (left and right
                    and abs(left).bit_length() + abs(right).bit_length() > _CONST_BITS_LIMIT):
                return None, True
            value = left * right
        elif op is ast.FloorDiv:
            value = left // right
        elif op is ast.Mod:
            value = left % right
        elif op is ast.Pow:
            if right < 0:
                return None, True
            if right == 0:
                value = 1
            elif left in (0, 1):
                value = left
            elif left == -1:
                value = -1 if right & 1 else 1
            elif max(1, abs(left).bit_length()) * right > _CONST_BITS_LIMIT:
                return None, True
            else:
                value = left ** right
        elif op is ast.LShift:
            if right < 0:
                return None, True
            if left == 0:
                value = 0
            elif max(1, abs(left).bit_length()) + right > _CONST_BITS_LIMIT:
                return None, True
            else:
                value = left << right
        elif op is ast.RShift:
            if right < 0:
                return None, True
            value = left >> right
        elif op is ast.BitAnd:
            value = left & right
        elif op is ast.BitOr:
            value = left | right
        elif op is ast.BitXor:
            value = left ^ right
        else:
            return None, unable
    except (ArithmeticError, ValueError):
        return None, True
    if type(value) is not int:
        return None, True
    return value, not (_I64_MIN <= value <= _I64_MAX)

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


def refuse_int_float_literal(node):
    """`int(<float literal>)` where the truncated value cannot fit int64.

    CPython returns an exact big integer for `int(1e300)`; an int here is 64-bit (SEMANTICS
    section 1), so the value is known now and refusing it here, by name, is the same
    compile-time outcome an out-of-range integer literal already gets. Values that fit int64
    take the ordinary conversion, and a non-literal argument is unaffected.
    """
    value = _number_constant(node)
    if isinstance(value, float) and not (-9223372036854775808.0 <= value < 9223372036854775808.0):
        raise Unsupported(
            'the float literal %r converted with int() does not fit in a 64-bit signed integer, '
            'and an integer here is one (SEMANTICS section 1). CPython computes a finite value '
            'exactly because its int is unbounded, raises OverflowError for an infinity and '
            'ValueError for a NaN; AIL has no big integer type' % value)


def refuse_field_method_call(tree, allow_owners=False):
    """Refuse a call through a name that a class defines BOTH as a method and as an instance field.

    CPython resolves an instance attribute before the class, so ``self.f = lambda: 101`` makes
    ``c.f()`` call the stored lambda even when the class also has ``def f``.  This compiler has no
    route for a callable held in an instance field, and its method dispatch silently picked the
    method instead (``102 102`` where CPython prints ``101 102``).  Such a call is refused by name
    rather than mis-compiled.  The refusal is only raised when the receiver can actually be the
    colliding class: a receiver that resolves to an unrelated class (or to a list/dict, or to an
    unknown value) keeps its old behaviour, so an unrelated type with a same-named method is not
    caught by a collision elsewhere in the program.

    ``allow_owners`` is for the general emitter, which now looks in the instance table before a
    method of the receiver's own class: a receiver that can only be a colliding class is handled
    there, so only a receiver whose static class is a base of the colliding class (``self.f()`` in
    a base method, with the field stored by a subclass) is still refused.  A field holding a
    bound method (``self.f = self.g``, another object's method, a builtin method, a
    classmethod/staticmethod, or such a value reaching the field through an argument, list item,
    dict value, attribute or alias) is refused too: the instance-table route only calls plain
    functions, classes and ``__call__`` instances, so letting that receiver through compiled the
    class method instead.
    """
    def _own_nodes(node):
        stack = list(ast.iter_child_nodes(node))
        while stack:
            child = stack.pop()
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef, ast.Lambda)):
                continue
            yield child
            stack.extend(ast.iter_child_nodes(child))

    classes = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods, field_values, bases = set(), {}, []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            methods.add(item.name)
            args = item.args.posonlyargs + item.args.args
            if not args:
                continue
            self_name = args[0].arg
            for sub in _own_nodes(item):
                if isinstance(sub, ast.Assign):
                    targets, value = sub.targets, sub.value
                elif isinstance(sub, ast.AnnAssign):
                    targets, value = [sub.target], sub.value
                elif isinstance(sub, ast.AugAssign):
                    targets, value = [sub.target], None
                else:
                    continue
                for target in targets:
                    if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                            and target.value.id == self_name):
                        values = field_values.setdefault(target.attr, [])
                        if value is not None:
                            values.append(value)
        classes[node.name] = {'methods': methods, 'fields': set(field_values),
                              'field_values': field_values, 'bases': bases}

    # Name resolution follows Python's scopes: an assignment to a local name in b() must not make
    # an unrelated local x in a() look like a possible class for b's x.
    scope_of, scope_parent, func_owner = {}, {}, {}

    def _mark_scope(node, scope):
        scope_of[id(node)] = scope
        inner = None
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_owner[id(child)] = node.name
            inner = node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            inner = node
        if inner is not None:
            scope_parent[inner] = scope
            scope = inner
        for child in ast.iter_child_nodes(node):
            _mark_scope(child, scope)

    _mark_scope(tree, tree)

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
        return {other for other in classes
                if other == name or name in _bases_of(other)}

    collisions = {}
    for name in classes:
        both = _inherited(name, 'methods', frozenset()) & _inherited(name, 'fields', frozenset())
        if both:
            collisions[name] = both
    if not collisions:
        return
    all_names = set().union(*collisions.values())

    calls_by_name, calls_by_attr = {}, {}
    for item in ast.walk(tree):
        if isinstance(item, ast.Call):
            if isinstance(item.func, ast.Name):
                calls_by_name.setdefault(item.func.id, []).append(item)
            elif isinstance(item.func, ast.Attribute):
                calls_by_attr.setdefault(item.func.attr, []).append(item)

    def _param_names(func):
        args = func.args
        return [arg.arg for arg in args.posonlyargs + args.args]

    call_ctx = {}

    def _visit(node, cls_name, func):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                _visit(child, node.name, None)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in node.body:
                _visit(child, cls_name, node)
            return
        if isinstance(node, ast.Call):
            call_ctx[id(node)] = (cls_name, func)
        for child in ast.iter_child_nodes(node):
            _visit(child, cls_name, func)

    _visit(tree, None, None)

    def _classes_of(node, ctx=(None, None), seen=frozenset()):
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
                    found = set()
                    for call in calls_by_name.get(func.name, ()):
                        value = None
                        if index < len(call.args):
                            value = call.args[index]
                        else:
                            for keyword in call.keywords:
                                if keyword.arg == node.id:
                                    value = keyword.value
                        if value is not None:
                            found |= _classes_of(value, call_ctx.get(id(call), (None, None)),
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
                info = classes.get(cls_name)
                if info is None:
                    continue
                for value in info['field_values'].get(node.attr, ()):
                    found |= _classes_of(value, ctx, seen | {key})
            return found
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            found = set()
            for item in ast.walk(tree):
                if not isinstance(item, ast.Assign):
                    continue
                if not any(isinstance(t, ast.Name) and t.id == node.value.id for t in item.targets):
                    continue
                if isinstance(item.value, (ast.List, ast.Tuple)):
                    for elt in item.value.elts:
                        found |= _classes_of(elt, ctx, seen)
                elif isinstance(item.value, ast.Dict) and isinstance(node.slice, ast.Constant):
                    for key, value in zip(item.value.keys, item.value.values):
                        if isinstance(key, ast.Constant) and key.value == node.slice.value:
                            found |= _classes_of(value, ctx, seen)
            return found
        return set()

    def _field_values(name, attr, seen=frozenset()):
        info = classes.get(name)
        if info is None or name in seen:
            return []
        values = list(info['field_values'].get(attr, ()))
        for base in info['bases']:
            values.extend(_field_values(base, attr, seen | {name}))
        return values

    def _may_be_bound(node, seen=frozenset()):
        """Whether a value stored in the colliding field can be a bound method.

        pre279's instance-table route calls a function/class/instance value it finds there, but a
        bound method (`self.g`, `d.g`, `[1, 2].append`, a classmethod/staticmethod) has no route
        and used to fall through to the class method.  Such a field still needs pre278's refusal;
        only the values the instance-table route handles (lambdas, plain function/class names,
        builtins, `__call__` instances, list/dict items holding those) are let through.
        """
        if isinstance(node, ast.Attribute):
            return True
        if isinstance(node, (ast.Lambda, ast.Constant)):
            return False
        if isinstance(node, ast.Name):
            if node.id in classes:
                return False
            key = ('bound-name', id(node))
            if key in seen:
                return False
            seen = seen | {key}
            scope = scope_of.get(id(node), tree)
            if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = _param_names(scope)
                if node.id in params:
                    index = params.index(node.id)
                    if index == 0:
                        return False
                    if id(scope) in func_owner:
                        calls = calls_by_name.get(func_owner[id(scope)], ())
                        offset = 0 if any(
                            isinstance(decorator, ast.Name) and decorator.id == 'staticmethod'
                            for decorator in scope.decorator_list) else 1
                    else:
                        calls = list(calls_by_name.get(scope.name, ())) + \
                            list(calls_by_attr.get(scope.name, ()))
                        offset = 0
                    index -= offset
                    if index < 0:
                        return False
                    for call in calls:
                        value = None
                        if index < len(call.args):
                            value = call.args[index]
                        else:
                            for keyword in call.keywords:
                                if keyword.arg == node.id:
                                    value = keyword.value
                        if value is not None and _may_be_bound(value, seen):
                            return True
                    return False
            if any(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and item.name == node.id for item in ast.walk(tree)):
                return False
            lookup = scope
            while True:
                values = [value for name, value in assignments.get(lookup, ())
                          if name == node.id]
                if values:
                    return any(_may_be_bound(value, seen) for value in values)
                if lookup is tree:
                    return False
                parent = scope_parent.get(lookup)
                if parent is None:
                    return False
                lookup = parent
        if isinstance(node, ast.Subscript):
            key = ('bound-sub', id(node))
            if key in seen:
                return False
            seen = seen | {key}
            if not isinstance(node.value, ast.Name):
                return True
            lookup = scope_of.get(id(node), tree)
            while True:
                for name, value in assignments.get(lookup, ()):
                    if name != node.value.id:
                        continue
                    if isinstance(value, (ast.List, ast.Tuple)):
                        for elt in value.elts:
                            if _may_be_bound(elt, seen):
                                return True
                    elif isinstance(value, ast.Dict) and isinstance(node.slice, ast.Constant):
                        for key_node, item in zip(value.keys, value.values):
                            if isinstance(key_node, ast.Constant) \
                                    and key_node.value == node.slice.value \
                                    and _may_be_bound(item, seen):
                                return True
                if lookup is tree:
                    return False
                parent = scope_parent.get(lookup)
                if parent is None:
                    return False
                lookup = parent
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id not in classes:
                key = ('bound-call', id(node))
                if key not in seen:
                    seen = seen | {key}
                    functions = [item for item in ast.walk(tree)
                                 if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                                 and item.name == node.func.id]
                    for func in functions:
                        for item in _own_nodes(func):
                            if isinstance(item, ast.Return) and item.value is not None \
                                    and _may_be_bound(item.value, seen):
                                return True
            return False
        if isinstance(node, (ast.List, ast.Tuple, ast.Dict)):
            return False
        return True

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        attr = node.func.attr
        if attr not in all_names:
            continue
        recv = node.func.value
        if isinstance(recv, ast.Name) and recv.id in classes:
            continue
        if isinstance(recv, ast.Call) and isinstance(recv.func, ast.Name) and recv.func.id == 'super':
            continue
        owners = {name for name, names in collisions.items() if attr in names}
        possible = _classes_of(recv, call_ctx.get(id(node), (None, None)))
        if not (possible & owners):
            continue
        if allow_owners and possible <= owners:
            if not any(_may_be_bound(value) for cls_name in possible
                       for value in _field_values(cls_name, attr)):
                continue
        raise Unsupported('the method .%s() on an instance whose class also stores an instance '
                          'field named %s (CPython calls the field)' % (attr, attr))


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


_POW_CONSTANT_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
                      ast.Pow, ast.LShift, ast.RShift, ast.BitAnd, ast.BitOr, ast.BitXor)


def _pow_exponent_is_constant(node):
    """Whether the exponent is a constant expression, so the existing constant folders decide it.

    Bool leaves count: CPython uses them as 0/1. The check is syntactic on purpose: it must not
    evaluate a huge constant here, only tell a fixed expression from a value computed later."""
    if isinstance(node, ast.Constant):
        return type(node.value) in (int, float, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd, ast.Invert, ast.Not)):
        return _pow_exponent_is_constant(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in _POW_CONSTANT_OPS:
        return _pow_exponent_is_constant(node.left) and _pow_exponent_is_constant(node.right)
    return False


def refuse_variable_int_pow(node):
    """A constant integer base raised to a computed exponent is refused by name here.

    CPython's int is unbounded, so `2 ** n` answers exactly even when n is 63 or more; this
    compiler's int is int64, and `ail_ipow` could only stop the program at run time with
    `integer overflow` (or spin for a huge exponent). The value cannot be known while compiling,
    so the construct is refused at compile time instead. A constant exponent is still folded (and
    refused only when its exact result leaves int64), and the safe bases 0, 1 and -1 are admitted
    because every int64 exponent keeps their result in range."""
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow)):
        return
    base = int_constant(node.left)
    if base is None or abs(base) < 2 or not -(1 << 63) <= base < (1 << 63):
        return
    if _pow_exponent_is_constant(node.right):
        return
    refusal = Unsupported(
        'a power with the integer constant base %d and an exponent computed at run time can leave '
        'the signed 64-bit range of an AIL int (SEMANTICS section 1), so it is refused by name at '
        'compile time; CPython computes it exactly with an unbounded int. Write the exponent as a '
        "constant, or use float(%d) ** exponent for CPython's float answer" % (base, base))
    refusal.source_line = getattr(node, 'lineno', None)
    raise refusal


INT_POW_DIFF = 'C?-job-rbrbrbrbpre33-10271808-1'


def refuse_int_pow_overflow(node):
    """`10 ** 40`: CPython's int is unbounded, this language's is int64 (DIFFERENCES
    C?-job-rbrbrbrbpre33-10271808-1). A constant integer power whose exact result does not fit is refused
    here, before any emitter sees it, rather than wrapping or stopping at run time. Bases -1, 0 and
    1 are always in range, so a huge exponent on one of them is not even evaluated."""
    base, exponent = _number_constant(node.left), _number_constant(node.right)
    if type(base) is not int or type(exponent) is not int or exponent < 0 or -1 <= base <= 1:
        return
    if exponent > 63:
        overflow = True          # |base| >= 2, so the magnitude is at least 2 ** 64
    else:
        value = base ** exponent
        overflow = not -(1 << 63) <= value < (1 << 63)
    if not overflow:
        return
    refusal = Unsupported(
        'the integer power %d ** %d does not fit in a 64-bit signed integer '
        '(int64 constant out of range; DIFFERENCES %s): CPython computes it exactly because its '
        "int is unbounded, while this language's int is int64; use float() when a float answer "
        'is wanted' % (base, exponent, INT_POW_DIFF))
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
