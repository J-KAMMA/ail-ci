"""A set or dict key holding a materialised generator expression keeps CPython's identity.

Both emitters lower a generator expression to an eagerly built list that carries the
``from_generator`` flag and the shared ``next()`` cursor (pre166).  That list was still
unhashable, so ``{(x for x in [1, 2])}`` stopped with ``TypeError: unhashable type: 'list'``
where CPython's generator object is hashable by identity.  The runtime now hashes such a list
by its own address, so the same genexpr object keeps one bucket as its cursor advances and two
distinct genexprs with equal contents stay distinct.  Set/dict membership, additions, removals,
aliases and values reaching the container through an argument, a list item, an attribute and a
dict value therefore match CPython on both builds.
"""
import unittest

from test_ail_silent1 import check_program

CASES = {
    'set_literal': '''g = (x for x in [1, 2])
print(len({g}))
''',
    'set_literal_empty': '''print(len({(x for x in [])}))
''',
    'saved_membership_and_next': '''g = (x for x in [1, 2])
s = {g}
print(len(s))
print(g in s)
print(next(g, "end"))
''',
    'same_object_twice': '''g = (x for x in [1, 2])
s = {g, g}
print(len(s), g in s)
''',
    'alias': '''g = (x for x in [1, 2])
h = g
s = {h}
print(len(s), g in s, h in s)
''',
    'set_from_list': '''g = (x for x in [1, 2])
print(len(set([g])))
''',
    'add_and_discard': '''a = (x for x in [1, 2])
b = (x for x in [1, 2])
s = {a}
s.add(b)
print(len(s))
s.discard(a)
print(len(s), b in s)
''',
    'distinct_same_contents': '''a = (x for x in [1, 2])
b = (x for x in [1, 2])
s = {a, b}
print(len(s))
print(a in s, b in s, a is b)
''',
    'dict_key': '''g = (x for x in [1, 2])
d = {g: "v"}
print(len(d), d[g])
''',
    'dict_alias': '''g = (x for x in [1, 2])
d = {g: 1}
h = g
print(d[h])
d[h] = 2
print(len(d), d[g])
''',
    'dict_distinct_same_contents': '''a = (x for x in [1, 2])
b = (x for x in [1, 2])
d = {a: "a", b: "b"}
print(len(d), d[a], d[b])
''',
    'argument': '''def first_size(g):
    return len({g})


print(first_size(x for x in [1, 2]))
''',
    'attribute': '''class Box:
    def __init__(self):
        self.g = (x for x in [1, 2])


box = Box()
print(len({box.g}))
''',
    'list_item': '''box = [(x for x in [1, 2])]
print(len({box[0]}))
''',
    'dict_value': '''d = {"g": (x for x in [1, 2])}
print(len({d["g"]}))
''',
    'consumed_before_hashing': '''g = (x for x in [1, 2])
print(next(g))
s = {g}
print(len(s), g in s)
print(next(g, "end"))
''',
    'hash_builtin': '''g = (x for x in [1, 2])
print(isinstance(hash(g), int))
print(hash(g) == hash(g))
''',
    'mixed_elements': '''g = (x for x in [1, 2])
s = {g, 1, "a", (1, 2)}
print(len(s), g in s, 1 in s, "a" in s, (1, 2) in s)
''',
    'frozenset': '''g = (x for x in [1, 2])
fs = frozenset({g})
print(len(fs), g in fs)
print(fs == frozenset({g}))
''',
    'set_equality': '''a = (x for x in [1, 2])
b = (x for x in [1, 2])
print({a} == {a}, {a} == {b})
''',
}


@unittest.skipUnless(__import__('shutil').which('gcc'), 'needs gcc')
class GenexprHashable(unittest.TestCase):
    def test_matches_cpython_on_both_builds(self):
        for name, text in sorted(CASES.items()):
            with self.subTest(name):
                check_program(self, 'pre207_' + name, text)


if __name__ == '__main__':
    unittest.main()
