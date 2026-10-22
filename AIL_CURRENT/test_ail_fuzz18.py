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
    `isinstance(x, (int, float))` and raises CPython's TypeError instead.

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


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class MathFuzz18(unittest.TestCase):
    def test_fsum_special_values_and_int_elements(self):
        check_program(self, 'fuzz18_fsum', FSUM)

    def test_float_floordiv_mod_and_divmod(self):
        check_program(self, 'fuzz18_floormod', FLOORMOD)

    def test_math_helpers_reject_wrong_types(self):
        check_program(self, 'fuzz18_badtypes', BADTYPES)


if __name__ == '__main__':
    unittest.main()
