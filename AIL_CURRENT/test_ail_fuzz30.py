"""A silent difference in iterators found by differential fuzzing (round 30), against CPython 3.12.

`next(genexpr, default)` evaluated the default only after walking the generator expression to its
first element. CPython evaluates the arguments first: the generator-expression object (which opens
its outermost iterable), then the default, then the first step. The default now runs first, and the
outermost iterator is opened before it, so side effects and exceptions keep CPython's order.
A generator expression saved in a name and passed to next() still hits a separate pre-existing
internal error and is not covered here.
"""
import unittest

from test_ail_silent1 import check_program

ORDER = r"""def src() -> list[int]:
    print("src")
    return [1, 2]


def dflt() -> int:
    print("default")
    return -1


def body(x: int) -> int:
    print("body", x)
    return x * 10


def main() -> None:
    print(next((body(x) for x in src()), dflt()))
    print(next((body(x) for x in src() if x > 5), dflt()))
    print(next((body(x) for x in []), dflt()))


main()
"""

EMPTY_AND_RAISE = r"""def body(x: int) -> int:
    print("body", x)
    return x


def main() -> None:
    try:
        print(next((body(x) for x in [1]), 1 // 0))
    except ZeroDivisionError:
        print("zero")
    try:
        print(next((body(x) for x in []), int("x")))
    except ValueError:
        print("value")
    try:
        print(next(body(x) for x in []))
    except StopIteration:
        print("stop")


main()
"""

MUTATES_OUTER = r"""def main() -> None:
    xs: list[int] = [1, 2]

    def clear() -> int:
        print("clear")
        xs.clear()
        return 9

    print(next((x for x in xs), clear()))
    ys: list[int] = [3]

    def grow() -> int:
        print("grow")
        ys.append(4)
        return 0

    print(next((x for x in ys), grow()))
    print(list(ys))


main()
"""

CONTAINERS = r"""class Box:
    def __init__(self, v):
        self.v = v


def main() -> None:
    arg: object = "fromarg"
    xs: list[object] = [None, False, 0.5, "item", 7]
    b = Box("attr")
    d: dict[str, object] = {"k": "dict"}
    print(next((x for x in []), arg))
    for i in range(len(xs)):
        print(next((x for x in []), xs[i]))
    print(next((x for x in []), b.v))
    print(next((x for x in []), d["k"]))
    print(next((x for x in [10]), xs[4]))


main()
"""

ONE_ARG = r"""def body(x: int) -> int:
    print("body", x)
    return x


def main() -> None:
    print(next(body(x) for x in [1, 2]))
    print(next(body(x) for x in [3]))
    try:
        print(next(body(x) for x in []))
    except StopIteration:
        print("stop")
    print(next((x for x in range(3) if x > 0)))


main()
"""

CASES = {
    'order': ORDER,
    'empty_and_raise': EMPTY_AND_RAISE,
    'mutates_outer': MUTATES_OUTER,
    'containers': CONTAINERS,
    'one_arg': ONE_ARG,
}


@unittest.skipUnless(__import__('shutil').which('gcc'), 'needs gcc')
class NextGenexprDefault(unittest.TestCase):
    def test_matches_cpython_on_both_builds(self):
        for name, text in sorted(CASES.items()):
            with self.subTest(name):
                check_program(self, 'fuzz30_' + name, text)


if __name__ == '__main__':
    unittest.main()
