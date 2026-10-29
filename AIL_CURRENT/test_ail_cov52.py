"""coverage cov52: a nested generator expression whose consumers drain it eagerly.

Both emitters materialise a generator expression as a list.  An inner generator expression used
to be refused unconditionally (pre41/pre42) because materialising it eagerly changes the order of
side effects whenever the outer expression is only partly consumed.  When the outer generator AND
every inner one are passed directly to a consumer that drains the whole iterable before returning
(`sum`, `list`, `tuple`, `sorted`, `min`, `max`, `set`, `dict`, or a literal str/bytes `.join`),
the inner one is drained exactly where CPython drains it and the list is observationally
identical.  That shape now builds on both paths and is compared with CPython below.

Everything else keeps the named refusal: an inner generator in a `for` iterable, an outer
generator assigned to a name or handed to `next()`/`any()`/`all()`, or a consumer that the
program shadows or defines itself.
"""
import unittest

from test_ail_silent1 import check_program, check_refused

ALLOWED = {
    'join_rows': '''rows = [[1, 2, 3], [], [-4, 5], [0]]
print("\\n".join(" ".join(str(v) for v in row) for row in rows))
print("|".join("".join(c for c in word) for word in ["ab", "", "cd"]))
print("\\n".join(" ".join(str(v) for v in row) for row in []))
''',
    'sum_rows': '''rows = [[1, 2, 3], [], [-5, 10], [0]]
print("\\n".join(str(sum(v for v in row)) for row in rows))
print("\\n".join(str(sum(v * 2 for v in row)) for row in rows))
values = [[2 ** 62, -(2 ** 62)], [1, 2, 3], []]
print("\\n".join(str(sum(v for v in row)) for row in values))
print("\\n".join(str(sum(v for v in row)) for row in [[1.5, 2.25], [-0.5, 0.25]]))
''',
    'reductions': '''rows = [[3, 1, 2], [], [-1, 5]]
print("\\n".join(str(sorted(v for v in row)) for row in rows))
print("\\n".join(str(list(v for v in row)) for row in rows))
print("\\n".join(str(tuple(v for v in row)) for row in rows))
nums = [[3, 1], [5, 9]]
print("\\n".join(str(min(v for v in row)) for row in nums))
print("\\n".join(str(max(v for v in row)) for row in nums))
print("\\n".join(str(sorted(set(v for v in row))) for row in rows))
''',
    'routes': '''def render(rows):
    return "\\n".join(" ".join(str(v) for v in row) for row in rows)


class Box:
    def __init__(self, rows):
        self.rows = rows


def main():
    rows = [[1, 2], [3]]
    alias = rows
    print(render(alias))
    box = Box([[4, 5]])
    print("\\n".join(" ".join(str(v) for v in row) for row in box.rows))
    table = {"k": [[6], [7, 8]]}
    print("\\n".join(" ".join(str(v) for v in row) for row in table["k"]))
    items = [[9], [10, 11]]
    print("\\n".join(" ".join(str(v) for v in row) for row in items[0:1]))


main()
''',
    'triple': '''cube = [[[1, 2], [3]], [[4]], []]
print("\\n".join("|".join(",".join(str(z) for z in cell) for cell in row) for row in cube))
print(";".join(" ".join(str(sum(z for z in cell)) for cell in row) for row in cube))
''',
}

REFUSED = {
    'inner_iterable': '''rows = [[1, 2], [3]]
print("\\n".join("\\n".join(str(x) for x in (y for y in row)) for row in rows))
''',
    'assigned_next': '''rows = [[1, 2], [3]]
g = (str(sum(y for y in row)) for row in rows)
print(next(g))
''',
    'assigned_list': '''rows = [[1, 2], [3]]
g = (str(sum(y for y in row)) for row in rows)
print(list(g))
''',
    'shadowed_sum': '''def sum(xs):
    return 0


rows = [[1, 2], [3]]
print("\\n".join(str(sum(v for v in row)) for row in rows))
''',
    'any_all': '''rows = [[0, 1], [2]]
print(any(x for x in (y for row in rows for y in row)))
''',
}

ALLOWED_WORDS = 'generator expression nested'


@unittest.skipUnless(__import__('shutil').which('gcc'), 'needs gcc')
class Cov52Tests(unittest.TestCase):
    def test_eager_nested_generator_expressions_match_cpython(self):
        for name, text in sorted(ALLOWED.items()):
            with self.subTest(name):
                check_program(self, 'cov52_' + name, text)

    def test_other_nested_generator_expressions_stay_refused(self):
        for name, text in sorted(REFUSED.items()):
            with self.subTest(name):
                check_refused(self, 'cov52_' + name, text, ALLOWED_WORDS)


if __name__ == '__main__':
    unittest.main()
