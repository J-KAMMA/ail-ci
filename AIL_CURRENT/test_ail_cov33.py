"""Coverage 33: a nested generator expression that is consumed at once now builds.

The general path materialises a generator expression eagerly.  For a generator expression
nested inside another one, that moved the inner work to the point where the outer generator
was made, which is observable when the outer one is saved, walked lazily, used as an iterable
or a condition, or passed to a short-circuiting builtin.  Those shapes stay refused by name
("a generator expression nested inside another generator expression").

A nested generator expression whose outer expression and every inner expression are arguments
of a call that reads all elements before returning (``str.join``, ``list``, ``tuple``,
``set``, ``frozenset``, ``dict``, ``sorted``, ``sum``, ``min``, ``max``, ``bytes``,
``bytearray``) keeps the eager lowering, which is observationally the same point.  That is the
shape of the corpus's ``"\\n".join(" ".join(...) for row in rows)`` and
``"".join(f"{sum(...):>7}" for q in quarters)`` programs.

Every program is built with the general path forced (``AIL_UNIFIED_FORCE=1``) and with the
default build, and must print what CPython 3.12 prints with the same exit status.  The refused
shapes must fail to build and name the construct.
"""
import unittest

from test_ail_silent1 import check_program, check_refused

JOIN_NESTED = r'''def main() -> None:
    rows = [[1, 2], [3], []]
    print("\n".join(" ".join(str(v) for v in row) for row in rows))
    print("\n".join(" ".join(str(v) for v in row) for row in []))
    print("\n".join(f"{sum(v for v in row):>4}" for row in rows))
    vals = [[-1, 0, 2], [3.5, -2.5]]
    print("|".join(",".join(str(x) for x in row) for row in vals))
    print("\n".join(" ".join(str(v) for v in row) for row in [["a", "b"], ["c"]]))


main()
'''

JOIN_ROUTES = r'''class Box:
    def __init__(self) -> None:
        self.text = ""


def render(rows: list[list[int]]) -> str:
    return "\n".join(" ".join(str(v) for v in row) for row in rows)


def main() -> None:
    rows = [[1, 2], [3]]
    print(render(rows))
    xs = [""]
    xs[0] = "\n".join(" ".join(str(v) for v in row) for row in rows)
    print(xs[0])
    b = Box()
    b.text = "\n".join(" ".join(str(v) for v in row) for row in rows)
    print(b.text)
    d = {"k": "\n".join(" ".join(str(v) for v in row) for row in rows)}
    print(d["k"])
    alias = rows
    print("\n".join(" ".join(str(v) for v in row) for row in alias))
    copy = list(rows)
    print("\n".join(" ".join(str(v) for v in row) for row in copy))


main()
'''

SIDE_EFFECTS = r'''def emit(tag: str, v: int) -> int:
    print("emit", tag, v)
    return v


def main() -> None:
    rows = [[1, 2], [3]]
    print("\n".join(" ".join(str(emit("i", v)) for v in row) for row in rows))
    try:
        print("\n".join(" ".join(str(1 // v) for v in row) for row in [[1, 0]]))
    except ZeroDivisionError as e:
        print("caught", e)
    print("after")
    empty = []
    try:
        print("\n".join(" ".join(str(1 // v) for v in row) for row in empty))
    except ZeroDivisionError as e:
        print("never", e)


main()
'''

FULL_CONSUMERS = r'''def main() -> None:
    rows = [[3, 1], [2]]
    print(list(sum(v for v in r) for r in rows))
    print(tuple(sum(v for v in r) for r in rows))
    print(sorted((sum(v for v in r) for r in rows), reverse=True))
    print(sorted(set(sum(v for v in r) for r in rows)))
    print(dict((str(i), sum(v for v in r)) for i, r in enumerate(rows)))
    print(sum(sum(v for v in r) for r in rows))
    print(min(sum(v for v in r) for r in rows))
    print(max(sum(v for v in r) for r in rows))
    print("|".join(str(sum(v for v in r)) for r in rows))
    print(sorted(" ".join(str(v) for v in r) for r in rows))
    print(list((sum(v for v in r), sum(v for v in r)) for r in rows))


main()
'''

THREE_LEVEL = r'''def main() -> None:
    cube = [[["a", "b"], ["c"]], [["d"]]]
    print("\n".join("|".join("".join(ch for ch in word) for word in row) for row in cube))
    empty = []
    print("\n".join("|".join("".join(ch for ch in word) for word in row) for row in empty))


main()
'''

MATRIX_REPR = r'''class Matrix:
    def __init__(self, rows: list[list[int]]) -> None:
        self.rows = [list(row) for row in rows]
        self.n = len(self.rows)

    def __repr__(self) -> str:
        return "\n".join(" ".join(str(value) for value in row) for row in self.rows)


def main() -> None:
    a = Matrix([[1, 2], [3, 4]])
    print(a)
    print()
    print(Matrix([[5]]))


main()
'''

QUARTERS = r'''def main() -> None:
    quarters = ("q1", "q2", "q3", "q4")
    data = {"n": {"q1": 1, "q2": 2, "q3": 3, "q4": 4},
            "s": {"q1": 10, "q2": 20, "q3": 30, "q4": 40}}
    regions = sorted(data)
    print(f"{'region':<7}" + "".join(f"{q:>7}" for q in quarters) + f"{'total':>7}")
    for region in regions:
        row_total = sum(data[region][q] for q in quarters)
        print(f"{region:<7}" + "".join(f"{data[region][q]:>7}" for q in quarters) + f"{row_total:>7}")
    grand = sum(data[r][q] for r in regions for q in quarters)
    print(f"{'TOTAL':<7}" + "".join(f"{sum(data[r][q] for r in regions):>7}" for q in quarters) + f"{grand:>7}")


main()
'''

PLAIN = r'''def main() -> None:
    xs = [1, 2, 3]
    print("\n".join(str(x * 10) for x in xs))
    print(sum(x * x for x in xs))
    print(list(str(x) for x in xs))
    print([[y for y in range(x)] for x in xs])
    print(list([y for y in range(x)] for x in xs))


main()
'''

PROGRAMS = {
    'join_nested': JOIN_NESTED,
    'join_routes': JOIN_ROUTES,
    'side_effects': SIDE_EFFECTS,
    'full_consumers': FULL_CONSUMERS,
    'three_level': THREE_LEVEL,
    'matrix_repr': MATRIX_REPR,
    'quarters': QUARTERS,
    'plain': PLAIN,
}

REFUSED = {
    'saved_outer': 'def main():\n    rows = [[1, 2]]\n    g = (" ".join(str(v) for v in row) for row in rows)\n    print(list(g))\n\n\nmain()\n',
    'lazy_for': 'def main():\n    rows = [[1, 2], [3]]\n    for line in (" ".join(str(v) for v in row) for row in rows):\n        print(line)\n\n\nmain()\n',
    'inner_iterable': 'def main():\n    print(list(x for x in (y for y in [1, 2])))\n\n\nmain()\n',
    'inner_value': 'def main():\n    print(list((y for y in [1, 2]) for x in [0]))\n\n\nmain()\n',
    'next_argument': 'def main():\n    print(next((" ".join(str(v) for v in row) for row in [[1, 2]]), None))\n\n\nmain()\n',
}


class NestedGeneratorExpressionConsumedAtOnce(unittest.TestCase):
    def test_builds_and_matches_cpython_on_both_builds(self):
        for name, text in sorted(PROGRAMS.items()):
            with self.subTest(name):
                check_program(self, 'cov33_' + name, text)

    def test_unsafe_nested_shapes_stay_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            with self.subTest(name):
                check_refused(self, 'cov33_refuse_' + name, text,
                              ['generator expression', 'nested'])


if __name__ == '__main__':
    unittest.main()
