"""cov31: a nested generator expression whose outer and inner generators are both read eagerly.

The general path materialises a generator expression as a list.  A generator expression nested in
another one used to be refused by name because materialising the inner one at the outer element
would run its elements too early (pre42).  It is now built when the outer generator is consumed at
once and the inner one is an argument of an eager consumer (`sum`, `join`, `list`, `sorted`, ...)
or the iterable of the outer comprehension, and the element/lazy clauses are side-effect free.
Then the inner list is made and read at the same point CPython creates and reads the inner
generator, so the values, order, exceptions and exit status match CPython 3.12 on both builds.

Every other nested shape stays a named compile-time refusal: a partial consumer (`next`, `any`,
`all`), a saved inner generator, a saved outer generator, a `for` loop that can break, a plain
tuple/list unpack (CPython stops it after `len(target) + 1` elements, not at exhaustion), and an
inner element with an observable side effect (a user function call such as `print`).  A starred
or otherwise exhaustive unpack reads every element, so that shape is built.

The first program is the shape of corpus t172 (an f-string in a `join` over a `sum` genexp), the
second that of corpus t432 (a `join` of a `join` in `__repr__`).
"""
import unittest

from test_ail_silent1 import check_program, check_refused

EAGER = {
    'corpus_report': r'''def main() -> None:
    quarters = ("q1", "q2", "q3")
    data = {"a": {"q1": 1, "q2": 2, "q3": 3}, "b": {"q1": 4, "q2": 5, "q3": 6}}
    regions = sorted(data)
    print("".join(f"{sum(data[r][q] for r in regions):>7}" for q in quarters))
    for region in regions:
        print(f"{region:<7}" + "".join(f"{data[region][q]:>7}" for q in quarters))

    grand = sum(data[r][q] for r in regions for q in quarters)
    print(grand)


main()
''',
    'corpus_matrix': r'''class Matrix:
    def __init__(self, rows):
        self.rows = rows

    def __repr__(self):
        return "\n".join(" ".join(str(value) for value in row) for row in self.rows)


def main() -> None:
    print(Matrix([[1, 2], [3, 4]]))
    print(Matrix([]))


main()
''',
    'consumers': r'''from collections import Counter


def main() -> None:
    print(tuple(x for x in (v for v in [1, 2])))
    print(frozenset(x for x in (v for v in [1, 2, 1])))
    print(sorted(x for x in (v for v in [3, 1, 2])))
    print(Counter(x for x in (v for v in ["a", "b", "a"])))
    print(bytes(x for x in (v for v in [65, 66, 67])))
    print(bytearray(x for x in (v for v in [65, 66])))
    xs = [1, 2]
    xs.extend(x for x in (v for v in [3, 4]))
    print(xs)
    d = {"a": 1}
    d.update((k, k * 2) for k in (v for v in ["b", "c"]))
    print(sorted(d.items()))


main()
''',
    'routes': r'''class Box:
    def __init__(self, xs):
        self.xs = xs


def take(xs):
    return sum(x for x in (v for v in xs))


def main() -> None:
    rows = [[1, 2, 3], [4, 5], [], [-2, 7]]
    print(sum(x * x for x in (v for v in [1, 2, 3])))
    print(sum(x for row in rows for x in (v for v in row)))
    print(",".join(s.upper() for s in (w for w in ["a", "bc", "d"])))
    print(list(x + 1 for x in (v for v in [])))
    print(list(x + 1 for x in (v for v in [0, -1, 9])))
    print(min(x for x in (v for v in [4, 2, 8])), max(x for x in (v for v in [4, 2, 8])))
    print(set(x % 3 for x in (v for v in [1, 2, 4, 5])))
    print(f"{sum(x for x in (v for v in [10, 20])):>6}")
    items = [[1, 2], [3, 4]]
    d = {"k": [5, 6]}
    b = Box([7, 8])
    print(take([9, 10]))
    print(sum(x for x in (v for v in items[0])))
    print(sum(x for x in (v for v in d["k"])))
    print(sum(x for x in (v for v in b.xs)))
    print(sum(x for x in (v for v in rows[-1])))
    print(list(sum(y for y in (w for w in row)) for row in rows))


main()
''',
    'starred_unpack': r'''class Box:
    def __init__(self, xs):
        self.xs = xs


def take(xs):
    first, *rest = (v for v in xs for _ in (x for x in [0]))
    return first, rest


def main() -> None:
    values = [10, -3, 7, 0]
    first, *rest = (v * 2 for v in values for _ in (x for x in [0]))
    print(first, rest)
    *head, last = (v + 1 for v in values for _ in (x for x in ["s"]))
    print(head, last)
    one, *mid, end = (v for v in [1, 2, 3, 4] for _ in (x for x in [0]))
    print(one, mid, end)
    print(take(values))
    data = {"k": [4, 5, 6]}
    a, *b = (v for v in data["k"] for _ in (x for x in [0]))
    print(a, b)
    box = Box([7, 8, 9])
    a, *b = (v for v in box.xs for _ in (x for x in [0]))
    print(a, b)


main()
''',
}

REFUSED = {
    'next_inner': r'''def main() -> None:
    rows = [[1, 2], [3, 4]]
    print(list(next(y for y in row) for row in rows))


main()
''',
    'saved_inner': r'''def main() -> None:
    rows = [[1, 2], [3, 4]]
    print(list((y for y in row) for row in rows))


main()
''',
    'any_inner': r'''def main() -> None:
    rows = [[0, 1], [2, 3]]
    print(list(any(y for y in (z for z in row)) for row in rows))


main()
''',
    'saved_outer': r'''def main() -> None:
    rows = [[1, 2], [3, 4]]
    g = (sum(y for y in (z for z in row)) for row in rows)
    print(list(g))


main()
''',
    'for_break': r'''def main() -> None:
    rows = [[1, 2], [3, 4]]
    for value in (sum(y for y in (z for z in row)) for row in rows):
        print(value)
        break


main()
''',
    'plain_unpack': r'''def main() -> None:
    xs = [10, 20, 30]
    try:
        a, b = (xs[i] + y for i in range(4) for y in (z for z in [0]))
    except ValueError:
        print("valueerror")
    except IndexError:
        print("indexerror")


main()
''',
    'side_effect_inner': r'''def mark(tag, value):
    print("mark", tag, value)
    return value


def main() -> None:
    rows = [[1, 2], [3]]
    print(list(sum(mark("i", y) for y in (mark("j", z) for z in row)) for row in rows))


main()
''',
}


@unittest.skipUnless(__import__('shutil').which('gcc'), 'needs gcc')
class NestedGeneratorExpression(unittest.TestCase):
    def test_eagerly_consumed_nested_matches_cpython(self):
        for name, text in sorted(EAGER.items()):
            with self.subTest(name):
                check_program(self, 'cov31_' + name, text)

    def test_other_nested_shapes_are_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            with self.subTest(name):
                check_refused(self, 'cov31_' + name, text, ['generator expression', 'nested'])


if __name__ == '__main__':
    unittest.main()
