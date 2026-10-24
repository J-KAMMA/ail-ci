"""A pre-existing difference in generator expressions, against CPython 3.12 (job pre42).

The general path materialises a generator expression like a list comprehension.  An inner
generator expression is therefore evaluated when the outer one is built, where CPython creates it
only when its own element is reached; the order of side effects differs, and consuming the outer
generator elsewhere can end in the internal error
`AIL internal error: ail_it_next: unknown library iterator kind`.  The general path now refuses
the nested construct by name, while a generator expression that contains no other generator
expression still builds and matches CPython (a nested list/set/dict comprehension is eager in
CPython too and is not refused).
"""
import shutil
import unittest

from test_ail_silent1 import check_program, check_refused

ELEMENT = r"""def src(n: int):
    print("src", n)
    return range(n)


def main() -> None:
    g = ((y for y in src(x)) for x in [1, 2])
    print("made")
    print(next(next(g)))
    print("done")


main()
"""

UNUSED = r"""def src(n: int):
    print("src", n)
    return range(n)


def main() -> None:
    g = ((y for y in src(x)) for x in [1, 2])
    print("made")


main()
"""

ITERABLE = r"""def src():
    print("src")
    return [1, 2]


def main() -> None:
    g = (y for y in (z for z in src()))
    print("made")
    print(next(g))
    print("done")


main()
"""

DOUBLE_LOOP = r"""def src(n: int):
    print("src", n)
    return [n]


def main() -> None:
    g = (y for x in [1, 2] for y in (z for z in src(x)))
    print("made")
    print(list(g))


main()
"""

FOLD = r"""def src(row):
    print("src", row)
    return row


def main() -> None:
    rows = [[1, 2], [3, 4]]
    g = (sum(y for y in src(row)) for row in rows)
    print("made")
    print(list(g))


main()
"""

CONDITION = r"""def ok(n: int):
    print("ok", n)
    return n > 0


def main() -> None:
    g = (x for x in [1, -1] if any(y for y in [ok(x)]))
    print("made")
    print(list(g))


main()
"""

REFUSED = {
    'element': ELEMENT,
    'unused': UNUSED,
    'outer_iterable': ITERABLE,
    'second_for_clause': DOUBLE_LOOP,
    'fold_element': FOLD,
    'condition': CONDITION,
}

PLAIN = r"""def src(x: int):
    print("src", x)
    return x * 10


def main() -> None:
    xs = [1, 2, 3]
    print(next(src(x) for x in xs))
    print(list(src(x) for x in xs if x % 2))
    print(sum(src(x) for x in xs))
    g = (x * 2 for x in xs if x > 1)
    print("made")
    print(list(g))
    print([[y for y in range(x)] for x in xs])
    print(list([y for y in range(x)] for x in xs))
    print([sum(y for y in range(x)) for x in xs])


main()
"""

ALLOWED = {
    'plain': PLAIN,
}


@unittest.skipUnless(shutil.which('gcc'), 'needs gcc')
class NestedGeneratorExpression(unittest.TestCase):
    def test_nested_is_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            with self.subTest(name):
                check_refused(self, 'pre42_' + name, text, ['generator expression', 'nested'])

    def test_plain_generator_expression_matches_cpython(self):
        for name, text in sorted(ALLOWED.items()):
            with self.subTest(name):
                check_program(self, 'pre42_' + name, text)


if __name__ == '__main__':
    unittest.main()
