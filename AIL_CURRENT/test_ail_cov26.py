"""cov26: a nested generator expression whose elements are consumed at once matches CPython.

The general path materialises a generator expression eagerly.  That is only observable when the
generator is saved (created now, walked later) or when a consumer stops early, so a nested
generator expression was refused wholesale.  A nested generator is now accepted only where eager
materialisation cannot change which elements run at which point: the OUTER generator is the sole
argument of `list`/`tuple`/`sorted`/`sum`, or of `str.join` on a string literal with a provably-str
element, and every INNER one is too.  `sum` consumes element by element (not materialised), and
`join` with str elements cannot abort mid-way, so the corpus shapes (a join of joins, and a join
whose element sums an inner generator) match on both builds.

A saved outer generator, `next()` (one element), `any()`/`all()` (short-circuit), an inner
generator only handed on, a consumer that aborts on a bad element (`set`, `dict`, ...), a method
that may be the program's own (`.update`, `.join` on a non-literal), a call with extra arguments
(CPython evaluates them before it consumes the generator) and a join of a non-str keep the named
compile-time refusal.
"""
import unittest

from test_ail_silent1 import check_program, check_refused

MATCHING = {
    'join_nested_join': r'''rows = [[1, 2], [3], []]
print("\n".join(" ".join(str(v) for v in row) for row in rows))
''',
    'join_inner_sum': r'''data = {"a": {"q1": 1, "q2": 20}, "b": {"q1": 300, "q2": 4}}
quarters = ("q1", "q2")
print("".join(f"{sum(data[r][q] for r in data):>7}" for q in quarters))
''',
    'sum_inner_range': r'''print(sum(sum(j for j in range(i)) for i in range(5)))
print(sum(sum(j * i for j in range(3)) for i in range(0)))
''',
    'containers_inner': r'''print(list(list(j for j in range(i)) for i in range(4)))
print(tuple(tuple(j for j in range(i)) for i in range(3)))
print(sorted(sorted(j for j in range(i)) for i in range(3)))
''',
    'argument_route': r'''def render(rows):
    return "\n".join(" ".join(str(v) for v in row) for row in rows)


def total(rows):
    return sum(sum(v for v in row) for row in rows)


print(render([[1, 2], [3]]))
print(total([[1, 2], [3]]))
''',
    'list_item_route': r'''rows = [[[1], [2]], [[3, 4]]]
print("|".join(" ".join(str(v) for v in row) for row in rows[0]))
print(sum(sum(v for v in row) for row in rows[1]))
''',
    'attribute_and_dict_value_route': r'''class Box:
    def __init__(self, rows):
        self.rows = rows


box = Box([[5], [6, 7]])
d = {"rows": [[8, 9]]}
print("\n".join(" ".join(str(v) for v in row) for row in box.rows))
print(sum(sum(v for v in row) for row in d["rows"]))
''',
    'side_effects_and_negative': r'''def note(x):
    print("note", x)
    return -x


try:
    print(":".join(str(sum(note(y) for y in [x])) for x in [1, 2]))
    print(":".join(str(sum(note(y) for y in [x])) for x in [0]))
except ZeroDivisionError as e:
    print("caught", e)
''',
    'inner_sum_aborts_at_first_element': r'''def val(y):
    print("elem", y)
    return str(y)


try:
    print(":".join(f"{sum(val(y) for y in [x])}" for x in [1, 2]))
except TypeError as e:
    print("caught", e)
''',
}

REFUSED = {
    'saved_outer': r'''def src(n):
    print("src", n)
    return [n]


g = (sum(y for y in src(x)) for x in [1, 2])
print("made")
print(list(g))
''',
    'next_outer': r'''def src(n):
    print("src", n)
    return [n]


print(next((sum(y for y in src(x)) for x in [1, 2]), None))
''',
    'any_outer': r'''print(any((y for y in [x]) for x in [1, 2]))
''',
    'inner_only_handed_on': r'''def keep(g):
    return g


print("\n".join(str(keep(y for y in [1, 2])) for _ in range(2)))
''',
    'inner_second_for_clause': r'''def src(n):
    print("src", n)
    return [n]


print(sum(y for x in [1, 2] for y in (z for z in src(x))))
''',
    'set_outer_aborts_on_bad_element': r'''def val(x):
    print("elem", x)
    return x


try:
    print(set((sum(val(y) for y in [x]) for x in [[1], [2]])))
except TypeError as e:
    print("caught", e)
''',
    'dict_outer_aborts_on_bad_element': r'''def val(x):
    print("elem", x)
    return (x,)


try:
    print(dict((sum(val(y) for y in [x]) for x in [1, 2])))
except (TypeError, ValueError) as e:
    print("caught", e)
''',
    'update_may_be_the_program_method': r'''class Acc:
    def __init__(self):
        self.items = []

    def update(self, it):
        for x in it:
            self.items.append(x)
            break


acc = Acc()
acc.update((y for y in [x]) for x in [1, 2])
print(acc.items)
''',
    'join_may_be_the_program_method': r'''class Acc:
    def __init__(self):
        self.items = []

    def join(self, it):
        for x in it:
            self.items.append(x)
            break
        return ""


acc = Acc()
print(acc.join((y for y in [x]) for x in [1, 2]))
print(acc.items)
''',
    'sum_with_extra_argument': r'''def note(tag, v):
    print("arg", tag)
    return v


def val(x):
    print("elem", x)
    return x


print(sum((sum(val(y) for y in [x]) for x in [1, 2]), note("start", 10)))
''',
    'join_of_non_str': r'''def val(x):
    print("elem", x)
    return x


print("".join((y for y in [x]) for x in [1, 2]))
''',
    'starred_with_another_argument': r'''def tail(tag, v):
    print("arg", tag)
    return v


def val(x):
    print("elem", x)
    return [x]


print(*(sum(y for y in val(x)) for x in [1, 2]), tail("tail", 9))
''',
}


@unittest.skipUnless(__import__('shutil').which('gcc'), 'needs gcc')
class NestedGeneratorConsumedAtOnce(unittest.TestCase):
    def test_nested_generator_matches_cpython(self):
        for name, text in sorted(MATCHING.items()):
            with self.subTest(name):
                check_program(self, 'cov26_' + name, text)

    def test_not_fully_consumed_is_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            with self.subTest(name):
                check_refused(self, 'cov26_' + name, text, ['generator expression', 'nested'])


if __name__ == '__main__':
    unittest.main()
