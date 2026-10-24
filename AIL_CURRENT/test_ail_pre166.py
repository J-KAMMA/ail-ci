"""Pre-existing difference fixed by job pre166: next() of a saved generator expression.

Both emitters materialise a generator expression as a list, so `next(g)` where `g` is not a
direct `next(<genexpr>)` argument (stored in a name, an argument, a list item, a dict value or
an attribute, or returned in a list) hit `AIL internal error: iterator: unknown kind`. The list
now carries its own cursor, shared by next() and iteration over that object like a real
generator's, so repeated next() calls advance it and exhaustion is StopIteration (or the
default). `next()` of a plain list/tuple/str/dict/set/number/None now raises CPython's
`TypeError: '<type>' object is not an iterator` instead of the same internal error.

The other shapes are unchanged and compared with CPython on both builds.
"""
import unittest

from test_ail_silent1 import check_program

CASES = {
    'attr_genexpr': '''class Box:
    def __init__(self):
        self.g = (x * 2 for x in [1, 2, 3])

def take(box):
    return next(box.g)

box = Box()
print(take(box), next(box.g), take(box))
try:
    next(box.g)
except StopIteration:
    print("stop")
print(next(box.g, "done"))
''',
    'list_item_slice': '''gs = [(x for x in [1, 2]), (x for x in [3, 4])]
t = gs[:]
print(next(t[0]), next(t[1]), next(gs[0]))
try:
    next(t[1])
except StopIteration:
    print("stop")
''',
    'lambda_and_return': '''def make():
    return [(x * x for x in [2, 3])]

g = (x + 1 for x in [10, 20])
f = lambda: next(g)
print(f(), f())
try:
    f()
except StopIteration:
    print("stop")
print(next(make()[0]), next(make()[0]))
''',
    'argument_and_dict': '''def first(it):
    return next(it)

d = {"g": (x for x in [5, 6])}
print(first(d["g"]), next(d["g"]))
try:
    first(d["g"])
except StopIteration:
    print("stop")
''',
    'alias_and_mix': '''g = (x * x for x in [1, 2, 3, 4])
h = g
print(next(g), next(h))
print([x for x in g])
print(next(g, "done"))
k = (x for x in [7, 8])
it = iter(k)
print(next(it), next(k))
print(list(k))
print(next(k, "after-list"))
''',
    'noniterator_types': '''for obj in ([1, 2], (1, 2), "ab", {"a": 1}, {1, 2}, 5, None, 3.5, True):
    try:
        next(obj)
    except TypeError as e:
        print(type(e).__name__, str(e))
try:
    next([x for x in [1]])
except TypeError as e:
    print(type(e).__name__, str(e))
''',
    'empty_and_iterators': '''def gen():
    yield 1
    yield 2

g = (x for x in [])
print(next(g, None), next(g, "again"))
try:
    next(g)
except StopIteration:
    print("stop")
it = iter([1, 2])
print(next(it), next(it), next(it, 9))
h = gen()
print(next(h), next(h), next(h, 9))
print(next(x for x in [5, 6]), next((x for x in []), 7))
''',
    'nested': '''def wrap():
    inner = (x for x in [1, 2])
    outer = (next(inner) for _ in range(2))
    return outer

w = wrap()
print(next(w), next(w))
try:
    next(w)
except StopIteration:
    print("stop")
inner = (x for x in [3, 4])
print(next(inner), next(inner), next(inner, "end"))
''',
    'rebind': '''g = (x for x in [1])
print(next(g))
g = iter([7])
print(next(g))
''',
    'shadow': '''def next(x):
    return 99


h = (x for x in [1])
print(next(h))
''',
}


@unittest.skipUnless(__import__('shutil').which('gcc'), 'needs gcc')
class SavedGenexprNext(unittest.TestCase):
    def test_matches_cpython_on_both_builds(self):
        for name, text in sorted(CASES.items()):
            with self.subTest(name):
                check_program(self, 'pre166_' + name, text)


if __name__ == '__main__':
    unittest.main()
