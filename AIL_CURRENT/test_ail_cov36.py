"""Coverage cov36: a generator expression nested inside one that is consumed at once, against
CPython 3.12.

The general path lowers a generator expression to a list.  An inner generator expression was
therefore evaluated when the outer one was built, so every nested shape was refused by name.
When the outer expression is handed straight to a consumer that reads every element (``sum``,
``sorted``, ``list``, ``tuple``, ``str.join``) and every inner one is consumed the same way, the
eager lowering happens at the same point as CPython's lazy iteration.  Those shapes now build and
must print what CPython prints; a saved outer generator, an inner one used as a loop iterable, a
``for``/comprehension source (which can stop early) and ``min``/``max``/``set`` stay refused by
name on the general path.
"""
import shutil
import unittest

from test_ail_silent1 import check_program, check_refused

PROGRAMS = {}
PROGRAMS['join'] = r'''def main():
    rows = [["a", "b"], ["c"], []]
    print("|".join("-".join(str(v) for v in row) for row in rows))
    print("".join("".join(str(v) for v in row) for row in [[1, 2], [3]]))
    print("|".join(str(sum(v for v in row)) for row in [[1.5, 2.5], [], [-3]]))
main()
'''

PROGRAMS['routes'] = r'''class Box:
    def __init__(self, rows):
        self.rows = rows

def total(rows):
    return sum(sum(v for v in row) for row in rows)

def main():
    rows = [[1, 2], [3, -4], []]
    print(total(rows))
    print(sum(sum(v for v in row) for row in [rows[0], rows[1]]))
    b = Box(rows)
    print(sum(sum(v for v in r) for r in b.rows))
    d = {"rows": rows}
    print(sum(sum(v for v in r) for r in d["rows"]))
    alias = rows
    print(sum(sum(v for v in r) for r in alias))
    print(sum(sum(v for v in r) for r in ([] if False else rows)))
    print(sum(sum(float(v) for v in r) for r in [[True, False], [2]]))
main()
'''

PROGRAMS['consumers'] = r'''def main():
    rows = [[3, 1], [2], []]
    print(sorted(sum(v for v in r) for r in rows))
    print(tuple(sum(v for v in r) for r in rows))
    print(list(sum(v for v in r) for r in rows))
    print(sum(sum(v for v in r) for r in rows))
    print("|".join(str(sum(v for v in r)) for r in rows))
    a, b, c = (sum(v for v in r) for r in rows)
    print(a, b, c)
main()
'''

PROGRAMS['side_effects'] = r'''def mark(x):
    print("mark", x)
    return x

def main():
    print(sum(sum(mark(y) for y in [x]) for x in [1, 2]))
    print("|".join("".join(str(mark(y)) for y in [x]) for x in [3, 4]))
main()
'''

PROGRAMS['shadow'] = r'''def main():
    x = 10
    print(sum(x + sum(x for x in [1, 2]) for x in [3, 4]))
    print(x)
    y = 5
    print("".join(str(y) + "".join(str(y) for y in [7, 8]) for y in [1, 2]))
    print(y)
    print(sum(sum(x + z for z in [1, 2]) for x in [10, 20]))
main()
'''

PROGRAMS['condition'] = r'''def main():
    rows = [[1], [], [2, 3]]
    print(sum((sum(v for v in r) if r else -1) for r in rows))
    print(sum((0 and sum(v for v in r)) for r in rows))
    print(sum((sum(v for v in r) or 99) for r in rows))
main()
'''

PROGRAMS['empty_negative'] = r'''def main():
    print(sum(sum(i for i in range(a)) for a in [0, 1, 5]))
    print(sum(sum(i for i in range(a, 0, -1)) for a in [0, 1, 5]))
    print("".join("".join(str(i) for i in range(a)) for a in []))
    print(sum(sum(v for v in row) for row in [[], [], []]))
main()
'''

PROGRAMS['sorted_key'] = r'''def mark(x):
    print("mark", x)
    return x

def bad(v):
    print("key", v)
    raise ValueError("bad")

def main():
    try:
        print(sorted((sum(mark(y) for y in [x]) for x in [1, 2, 3]), key=bad))
    except ValueError as e:
        print("caught", e)
main()
'''

PROGRAMS['mutation'] = r'''def add(r):
    print("add", r)
    r.append(9)
    return sum(v for v in r)

def main():
    rows = [[1, 2], [3]]
    print(sum(add(row) for row in rows))
    print(rows)
    rows2 = [[1], [2]]
    print(sum(sum(v for v in row) for row in rows2))
    rows2[0].append(5)
    print(sum(sum(v for v in row) for row in rows2))
main()
'''

REFUSED = {
    'saved': r'''def main():
    rows = [[1, 2], [3]]
    g = (sum(v for v in row) for row in rows)
    print(list(g))
main()
''',
    'loop_iterable': r'''def main():
    rows = [[1, 2], [3]]
    print(sum(1 for row in rows for v in (x for x in row)))
main()
''',
    'for_source': r'''def main():
    out = []
    for v in (sum(y for y in [x]) for x in [1, 2, 3]):
        out.append(v)
    print(out)
main()
''',
    'inner_as_value': r'''def main():
    rows = [[1, 2], [3]]
    print(sum(sum(v for v in row) + (v for v in row) for row in rows))
main()
''',
}


@unittest.skipUnless(shutil.which('gcc'), 'needs gcc')
class NestedGeneratorExpressionConsumedAtOnce(unittest.TestCase):
    def test_consumed_nested_generator_matches_cpython(self):
        for name, text in sorted(PROGRAMS.items()):
            with self.subTest(name):
                check_program(self, 'cov36_' + name, text)

    def test_unsafe_nested_generator_is_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            with self.subTest(name):
                check_refused(self, 'cov36_' + name, text, ['generator expression', 'nested'])


if __name__ == '__main__':
    unittest.main()
