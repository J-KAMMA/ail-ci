"""rdiff6: two general-path differences from CPython 3.12 found by realistic programs.

* `@functools.lru_cache` on a recursive function in a program the default build takes to the general
  path (its tagged-int lowering does not cover the memo object): the mixed-mode pass swapped a typed clone
  of the UNDECORATED body in at the call sites, so the cache was never consulted and `fib(90)` ran
  exponentially (it never finished). A decorated function is no longer a clone candidate.
* `+x` of a big int in a program with a class (the general path's operator-method runtime is on) raised
  "bad operand type for unary +: 'int'"; it is the value itself, as for a small int.
"""
from test_ail_pathlib import Base


CACHED_FIB = r'''import functools


@functools.lru_cache(maxsize=None)
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


@functools.cache
def ways(n: int) -> int:
    if n < 0:
        return 0
    if n == 0:
        return 1
    return ways(n - 1) + ways(n - 2) + ways(n - 3)


def main() -> None:
    print(fib(90))
    print([fib(i) for i in range(12)])
    print(ways(60), ways(3))


main()
'''

UNARY_PLUS_BIG = r'''class Box:
    def __init__(self, v: int) -> None:
        self.v = v


def main() -> None:
    big = Box(10 ** 30).v
    print(+big, +(-big), +3, +2.5, +True)
    print(+Box(2 ** 70).v - 1, -(+big) // 7)


main()
'''


class GeneralPathDifferences(Base):
    def test_cached_recursion_is_memoised_on_every_build(self):
        self.compare('rdiff6_fib_typed', CACHED_FIB, mode='typed')
        # (AIL_IR=1 takes the tagged-int lowering, which sends this program to the general path)
        self.compare('rdiff6_fib_default', CACHED_FIB, mode='default', irs=('1',))
        self.compare('rdiff6_fib_general', CACHED_FIB, mode='gonly')

    def test_unary_plus_of_a_big_int(self):
        self.compare('rdiff6_pos_default', UNARY_PLUS_BIG, mode='default')
