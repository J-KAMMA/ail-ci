"""fuzz18: math module and float edge cases that printed a different answer without a diagnostic.

F1  math.fsum used a naive running sum for a non-finite input and for int elements, so
    `fsum([inf, -inf])` and `fsum([1e308, 1e308])` printed nan where CPython raises, and
    `fsum([1, 2])` returned the int 2.  It now follows CPython's math_fsum_impl for every
    element (special_sum / inf_sum bookkeeping, "intermediate overflow in fsum",
    "-inf + inf in fsum") and converts each element to float.

F2  float `//`, `%` and `divmod` used floor(x / y) and a bare fmod sign fix.  The sign of a
    zero result and the infinity cases differed: `-0.0 % 3.0` was -0.0 (0.0), `3.0 // -inf`
    was -0.0 (-1.0) and `inf // 2.0` was inf (nan).  Both the boxed and the general runtime
    now use CPython's float_divmod adjustment and half-even quotient snap.

F3  a math helper that called the C function directly accepted a str / None for a float
    argument and printed garbage (`math.copysign("a", 1)`).  Every float helper now checks
    the argument and raises CPython's TypeError instead; a Fraction or an object with
    `__float__` / `__index__` is converted instead of being rejected.

F4  `math.floor` / `math.ceil` of an infinity were lowered through int(x // 1), whose new
    float `//` gives NaN, so they raised ValueError "cannot convert float NaN to integer".
    They now raise CPython's OverflowError "cannot convert float infinity to integer", keep
    int arguments, and use `__floor__` / `__ceil__` when an object supplies one.

F5  `math.fsum`, `math.sin`, `math.sqrt` and the other float helpers rejected valid numeric
    objects (Fraction, a class with `__float__`) with "must be real number, not ...".
    They now convert them as `float()` does and only reject types without a float conversion.

F6  `math.floor` / `math.ceil` converted an object through `__float__` and ignored its own
    `__floor__` / `__ceil__` (or rejected it when it had no `__float__`).  They now call the
    dunder when it exists and return its result unchanged, falling back to `__float__` /
    `__index__` conversion only when it does not; an int/float is unchanged.

F7  `math.sin` / `sqrt` / `fsum` / `floor` / ... on a class or a function leaked the general
    path's internal `NotImplementedError hasattr() ...`; they now raise CPython's
    `TypeError must be real number, not type` / `... not function`.

F8  the class/function rejection matched the run-time type *name*, so a legal user class named
    `function` (with `__float__`, `__floor__` or `__ceil__`) was rejected.  The numeric
    `hasattr()` probes now answer from the program's classes, so only a real class or function
    value is refused and a user class with that name converts normally.

Each program is built twice (default build, AIL_UNIFIED_FORCE=1 general path) and must print
what CPython 3.12 prints with the same exit status.
"""
import unittest

from test_ail_silent2 import HAVE_CC, check_program

FSUM = r"""import math

def main():
    print(repr(math.fsum([])), repr(math.fsum([0.1, 0.2, 0.3])))
    print(repr(math.fsum([1, 2, 3])), type(math.fsum([1, 2])).__name__)
    print(repr(math.fsum([1e16, 1.0, 1.0, -1e16])))
    print(repr(math.fsum([1e308, -1e308])), repr(math.fsum([-0.0])))
    print(repr(math.fsum([float('inf'), 1.0])), repr(math.fsum([float('-inf'), -1.0])))
    print(repr(math.fsum([float('nan'), 1.0])))
    for xs in ([float('inf'), float('-inf')], [1e308, 1e308],
               [1e308, 1e308, -1e308, -1e308], [-1e308, -1e308]):
        try:
            print(repr(math.fsum(xs)))
        except Exception as e:
            print(type(e).__name__, str(e))
    for xs in (['a'], [None], [1.0, 'a']):
        try:
            print(math.fsum(xs))
        except Exception as e:
            print(type(e).__name__, str(e))

main()
"""

FLOORMOD = r"""import math

def show(a, b):
    print(repr(a), repr(b), repr(a // b), repr(a % b), repr(divmod(a, b)))

def main():
    show(-0.0, 3.0)
    show(0.0, -3.0)
    show(-0.0, -3.0)
    show(5.0, 3.0)
    show(-5.0, 3.0)
    show(5.0, -3.0)
    show(-5.0, -3.0)
    show(3.0, float('-inf'))
    show(-3.0, float('inf'))
    show(float('inf'), 2.0)
    show(float('-inf'), 2.0)
    show(float('nan'), 2.0)
    show(2.0, float('nan'))
    show(1e308, 3.0)
    print(-0.0 // 3, 0.0 // -3, -0.0 % 3, 0.0 % -3)
    print(3 % 2, 3 % -2, -3 % 2, -3 % -2)

main()
"""

BADTYPES = r"""import math

def close(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))

def main():
    close('copysign_str', lambda: math.copysign('a', 1.0))
    close('copysign_none', lambda: math.copysign(None, 1.0))
    close('hypot_str', lambda: math.hypot('a', 1.0))
    close('hypot_none', lambda: math.hypot(None, 1.0))
    close('atan2_str', lambda: math.atan2('a', 1.0))
    close('fmod_str', lambda: math.fmod('a', 1.0))
    close('fmod_none', lambda: math.fmod(None, 1.0))
    close('pow_str', lambda: math.pow('a', 1.0))
    close('sin_str', lambda: math.sin('a'))
    close('cos_none', lambda: math.cos(None))
    close('fabs_str', lambda: math.fabs('a'))
    close('isnan_str', lambda: math.isnan('a'))
    close('sqrt_str', lambda: math.sqrt('a'))
    close('sqrt_none', lambda: math.sqrt(None))
    close('log2_str', lambda: math.log2('a'))
    print(math.copysign(3, True), math.hypot(3, 4), math.atan2(0, 1))
    print(math.fmod(7.5, 2), math.pow(2, 10), math.sin(0), math.fabs(-0.0))

main()
"""


FLOORINF = r"""import math


class Box:
    def __init__(self):
        self.f = 2.5
        self.n = -2.5


def show(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main():
    for v in (float('inf'), float('-inf'), float('nan')):
        show('floor ' + repr(v), lambda v=v: math.floor(v))
        show('ceil ' + repr(v), lambda v=v: math.ceil(v))
        show('trunc ' + repr(v), lambda v=v: math.trunc(v))
    for v in (-0.0, 0.5, -0.5, 3.7, -3.7, 7, -7, True, False):
        show('floor ' + repr(v), lambda v=v: math.floor(v))
        show('ceil ' + repr(v), lambda v=v: math.ceil(v))
    b = Box()
    d = {'a': 4.5, 'b': -4.5, 'i': 9}
    show('floor attr', lambda: math.floor(b.f))
    show('ceil attr', lambda: math.ceil(b.n))
    show('floor dict', lambda: math.floor(d['a']))
    show('ceil dictint', lambda: math.ceil(d['i']))
    show('floor str', lambda: math.floor('a'))
    show('ceil str', lambda: math.ceil('a'))
    show('floor none', lambda: math.floor(None))
    show('ceil none', lambda: math.ceil(None))


main()
"""

NUMERIC = r"""import math
from fractions import Fraction


class Num:
    def __init__(self, v):
        self.v = v

    def __float__(self):
        return self.v + 0.25


class Bad:
    pass


def show(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main():
    half = Fraction(1, 2)
    show('sin fraction', lambda: math.sin(half))
    show('sqrt fraction', lambda: math.sqrt(Fraction(1, 4)))
    show('fabs fraction', lambda: math.fabs(Fraction(-1, 2)))
    show('floor fraction', lambda: math.floor(Fraction(7, 2)))
    show('ceil fraction', lambda: math.ceil(Fraction(7, 2)))
    show('floor fraction near1', lambda: math.floor(Fraction(2 ** 53 + 1, 2 ** 53)))
    show('ceil fraction near1', lambda: math.ceil(Fraction(2 ** 53 + 1, 2 ** 53)))
    show('copysign fraction', lambda: math.copysign(half, -1.0))
    show('fsum fraction', lambda: math.fsum([half, Fraction(1, 3)]))
    n = Num(2.0)
    show('sin floatdunder', lambda: math.sin(n))
    show('sqrt floatdunder', lambda: math.sqrt(n))
    show('fabs floatdunder', lambda: math.fabs(n))
    show('floor floatdunder', lambda: math.floor(n))
    show('ceil floatdunder', lambda: math.ceil(n))
    show('copysign floatdunder', lambda: math.copysign(n, 1.0))
    show('fsum floatdunder', lambda: math.fsum([n]))
    show('sin bad object', lambda: math.sin(Bad()))
    show('fsum bad object', lambda: math.fsum([Bad()]))
    show('floor bad object', lambda: math.floor(Bad()))
    show('ceil bad object', lambda: math.ceil(Bad()))
    for bad in ('a', None):
        show('sin ' + repr(bad), lambda bad=bad: math.sin(bad))
        show('fsum ' + repr(bad), lambda bad=bad: math.fsum([bad]))


main()
"""


FLOOR_DUNDER = r"""import math


class Both:
    def __float__(self):
        return 2.5

    def __floor__(self):
        return 99

    def __ceil__(self):
        return 100


class FloorCeil:
    def __floor__(self):
        return 41

    def __ceil__(self):
        return 42


class FloatOnly:
    def __float__(self):
        return -2.5


class IndexOnly:
    def __index__(self):
        return 7


class Odd:
    def __floor__(self):
        return 1.9

    def __ceil__(self):
        return 2.9


class Box:
    def __init__(self):
        self.a = Both()
        self.b = FloorCeil()
        self.c = FloatOnly()
        self.d = IndexOnly()
        self.e = Odd()
        self.n = -2.5


def show(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def take(x):
    return math.floor(x), math.ceil(x)


def main():
    show('both', lambda: take(Both()))
    show('floorceil', lambda: take(FloorCeil()))
    show('floatonly', lambda: take(FloatOnly()))
    show('indexonly', lambda: take(IndexOnly()))
    show('odd', lambda: take(Odd()))
    b = Box()
    show('attr both', lambda: take(b.a))
    show('attr floorceil', lambda: take(b.b))
    show('attr floatonly', lambda: take(b.c))
    show('attr indexonly', lambda: take(b.d))
    show('attr odd', lambda: take(b.e))
    show('attr float', lambda: math.floor(b.n) + math.ceil(b.n))
    items = [Both(), FloorCeil(), FloatOnly(), IndexOnly(), Odd()]
    show('list', lambda: [take(x) for x in items])
    d = {'a': Both(), 'b': FloorCeil(), 'c': FloatOnly(), 'd': IndexOnly(), 'e': Odd()}
    show('dict', lambda: [take(d[k]) for k in ('a', 'b', 'c', 'd', 'e')])
    o = Both()
    show('alias', lambda: (math.floor(o), math.ceil(o), math.floor(o), math.ceil(o)))
    for v in (2.5, -2.5, 0.0, -0.0, 3, -3, True, False,
              float('inf'), float('-inf'), float('nan')):
        show('num ' + repr(v), lambda v=v: take(v))
    for v in ('a', [1], (1,), {1}, {1: 2}, range(3), None):
        show('floor ' + type(v).__name__, lambda v=v: math.floor(v))
        show('ceil ' + type(v).__name__, lambda v=v: math.ceil(v))


main()
"""

CLASSTYPE = r"""import math


class P:
    def __init__(self):
        self.x = 1


class Num:
    def __float__(self):
        return 1.5


class function:
    def __init__(self, v=2.25):
        self.v = v

    def __float__(self):
        return self.v

    def __floor__(self):
        return 71

    def __ceil__(self):
        return 81

    def __call__(self):
        return 5


class function_index:
    def __index__(self):
        return 4


class function_badfloat:
    def __float__(self):
        raise TypeError("inner boom")


class Box:
    def __init__(self):
        self.t = P
        self.n = Num()
        self.f = function()
        self.i = function_index()


def f():
    return 1


def show(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def take(x):
    return math.sin(x)


def main():
    show('sin type', lambda: math.sin(P))
    show('sin function', lambda: math.sin(f))
    show('sqrt type', lambda: math.sqrt(P))
    show('sqrt function', lambda: math.sqrt(f))
    show('fsum type', lambda: math.fsum([P]))
    show('fsum function', lambda: math.fsum([f]))
    show('floor type', lambda: math.floor(P))
    show('ceil function', lambda: math.ceil(f))
    show('copysign type', lambda: math.copysign(P, 1.0))
    show('pow function', lambda: math.pow(f, 2.0))
    show('isnan type', lambda: math.isnan(P))
    show('fabs function', lambda: math.fabs(f))
    b = Box()
    show('arg type', lambda: take(b.t))
    xs = [P, f, Num()]
    show('list', lambda: [take(v) for v in xs])
    d = {'t': P, 'n': Num()}
    show('dict', lambda: [take(d[k]) for k in ('t', 'n')])
    show('num still ok', lambda: take(b.n))
    show('num floor', lambda: math.floor(Num()))
    show('named function sin', lambda: math.sin(function()))
    show('named function floor', lambda: math.floor(function()))
    show('named function ceil', lambda: math.ceil(function()))
    show('named function arg', lambda: take(function()))
    show('named function list', lambda: take([function(), function(1.5)][0]))
    show('named function dict', lambda: take({'a': function(), 'b': function(3.5)}['a']))
    show('named function attr', lambda: take(b.f))
    show('named function index', lambda: take(function_index()))
    show('named function attr index', lambda: take(b.i))
    show('named function inner', lambda: take(function_badfloat()))


main()
"""


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class MathFuzz18(unittest.TestCase):
    def test_fsum_special_values_and_int_elements(self):
        check_program(self, 'fuzz18_fsum', FSUM)

    def test_float_floordiv_mod_and_divmod(self):
        check_program(self, 'fuzz18_floormod', FLOORMOD)

    def test_math_helpers_reject_wrong_types(self):
        check_program(self, 'fuzz18_badtypes', BADTYPES)

    def test_floor_ceil_infinity_and_nan(self):
        check_program(self, 'fuzz18_floorinf', FLOORINF)

    def test_helpers_convert_numeric_objects(self):
        check_program(self, 'fuzz18_numeric', NUMERIC)

    def test_floor_ceil_call_their_own_dunders(self):
        check_program(self, 'fuzz18_floor_dunder', FLOOR_DUNDER)

    def test_helpers_reject_class_and_function_by_name(self):
        check_program(self, 'fuzz18_classtype', CLASSTYPE)


if __name__ == '__main__':
    unittest.main()
