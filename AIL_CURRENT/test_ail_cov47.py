"""Branch cov47: a generator expression nested inside another one when both are consumed in place.

The general path materialises a generator expression like a list comprehension, so a nested one
used to be refused by name: eager evaluation ran the inner body when the outer element was built,
where CPython may hold the inner generator lazily.  When the outer expression is itself an argument
of a call that first reads the whole iterable (str.join with a literal receiver, list(), tuple())
and every inner one is too, CPython reaches the same elements in the same order, so the nested
construct builds and must print what CPython prints on both builds.  A nested expression saved as
a value, used as an outer element, consumed by something that can stop early (any/all/next, a for
with break) or by an object's own join/update stays the named compile-time refusal.  sum() also
stays refused: it adds each value as it arrives, so a later element is never evaluated once an
addition has raised (even with no class in the program).
"""
import shutil
import unittest

from test_ail_silent1 import check_program, check_refused

PROGRAMS = {
    'join': r'''rows = [[1, 2, 3], [4, 5], [], [-6, 7]]
print("\n".join(" ".join(str(v) for v in row) for row in rows))
print("|".join(" ".join(str(v) for v in row) for row in []))
''',
    'list_tuple': r'''rows = [[1, 2], [3], []]
print(list(list(v * 2 for v in row) for row in rows))
print(tuple(tuple(v for v in row if v % 2) for row in rows))
print(list(list(v for v in row) for row in []))
''',
    'routes': r'''class Box:
    def __init__(self):
        self.data = [[2, 3], [4]]
    def run(self):
        return "/".join(" ".join(str(v) for v in row) for row in self.data)

def render(rows):
    return ",".join(" ".join(str(x) for x in row) for row in rows)

def outer(rows, label):
    return label + ":" + render(rows)

b = Box()
print(b.run())
d = {"k": [[5], [6, 7]]}
print(" ".join(" ".join(str(v) for v in row) for row in d["k"]))
print(outer([[1, 2], [3]], "a"))
print(outer([], "b"))
''',
    'filter_raise': r'''def mark(n):
    print("row", n)
    return [n, -n, n + 1]
def keep(n):
    print("keep", n)
    return n % 2 == 0
print("\n".join(" ".join(str(v) for v in mark(n) if v > 0) for n in [1, 2, 3] if keep(n)))
try:
    print("\n".join(" ".join(str(10 // v) for v in row) for row in [[1, 2], [3, 0], [4]]))
except ZeroDivisionError as e:
    print("ZeroDivisionError", e)
print(" ".join(" ".join(str(10 // v) for v in row) for row in [[2, 5], [10]]))
''',
    'types': r'''rows = [["a", "b"], ["c"]]
print(list("/".join(v.upper() for v in row) for row in rows))
print(tuple(" ".join(str(v) for v in row) for row in rows))
print(",".join("|".join(str(x) for x in row) for row in [[1.5, -2.25], [0.0], [1e300]]))
print(" ".join(" ".join(str(v) for v in row) for row in [[True, False], [2**62, 1]]))
''',
}

REFUSED = {
    'saved_outer': r'''g = (" ".join(str(v) for v in row) for row in [[1, 2]])
print("made")
print(next(g))
''',
    'sum_consumer': r'''print(" ".join(str(sum(x for x in row)) for row in [[1, 2]]))
''',
    'any_consumer': r'''print(any((y for y in [x]) for x in [0, 1]))
''',
    'outer_element': r'''rows = [[1, 2], [3]]
print(list((y for y in row) for row in rows))
''',
    'method_update': r'''class Sink:
    def __init__(self):
        self.got = []
    def update(self, it):
        for x in it:
            self.got.append(x)

rows = [[1, 2], [3, 4]]
s = Sink()
s.update(" ".join(str(x) for x in row) for row in rows)
print(s.got)
''',
}


@unittest.skipUnless(shutil.which('gcc'), 'needs gcc')
class NestedGeneratorConsumedInPlace(unittest.TestCase):
    def test_consumed_in_place_matches_cpython(self):
        for name, text in sorted(PROGRAMS.items()):
            with self.subTest(name):
                check_program(self, 'cov47_' + name, text)

    def test_nested_generator_outside_a_full_consumer_is_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            with self.subTest(name):
                check_refused(self, 'cov47_' + name, text, ['generator expression', 'nested'])


if __name__ == '__main__':
    unittest.main()
