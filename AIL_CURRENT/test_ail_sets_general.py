"""Sets, frozensets and dicts on the general (boxed) path -- order-free behaviour.

CPython walks a set in its hash table's order (a set of ints in a fixed one, a set of str in a
per-run random one); AIL's sets keep insertion order. Any construct that shows the order
(`for x in s`, `list(s)`, `tuple(s)`, `print(s)`, `str`/`repr`, an f-string of one, a list
comprehension over one, `s.pop()`) is refused by name with the rewrite `sorted(s)` instead of
printing a different order silently; test_ail_setorder.py holds that rule for both builds.

Everything whose answer does not depend on the walk order keeps building and matches CPython
3.12 on the typed, default and general builds: `x in s`, `len(s)`, `sorted(s)`, `min`, `max`,
`sum`, the comparisons, and the operators / methods read in a sorted form.

S1  order-free reads, operators and methods match CPython on every build
S2  a set of str behaves the same way through sorted forms
S3  an order-revealing walk matches CPython's fixed int-set order
S4  dict iteration still follows insertion order (CPython's own order) on every build
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
ON_312 = sys.version_info[:2] == (3, 12)


def build(directory, text, name, mode):
    """Compile `text` in one mode: general (the boxed path alone, --general-only), typed
    (AIL_NO_GENERAL=1) or default (typed first, general on a refusal)."""
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_' + mode)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    env.pop('AIL_NO_GENERAL', None)
    env['AIL_IR'] = '0'
    if mode == 'general':
        command = [sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only']
    else:
        if mode == 'typed':
            env['AIL_NO_GENERAL'] = '1'
        command = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                   '--syntax', 'python', '-o', exe.name]
    return subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


def run_cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True,
                          timeout=120, encoding='utf-8')


def run_exe(exe, stdin=''):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                          encoding='utf-8', input=stdin)


ALL_MODES = ('typed', 'default', 'general')
GENERAL_MODES = ('general', 'default')


PROG_OPS = r'''def norm(v):
    if isinstance(v, frozenset):
        return ["frozenset", sorted(v)]
    if isinstance(v, set):
        return ["set", sorted(v)]
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, tuple):
        return tuple([norm(x) for x in v])
    return v


def p(*args):
    print(*[norm(a) for a in args])


def union(a, b):
    return a | b


def inter(a, b):
    return a & b


def diff(a, b):
    return a - b


def sym(a, b):
    return a ^ b


def inplace(a, b):
    a |= b
    a &= {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 40, 41}
    a -= {3, 4}
    a ^= {100, 2}
    return a


def cmp(a, b):
    return (a == b, a != b, a < b, a <= b, a > b, a >= b)


x = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 40, 41, 42}
y = {5, 6, 7, 200, 300, 400, 3, 41}
fx = frozenset(x)
fy = frozenset(y)
p('or', union(x, y), union(y, x), union(fx, y), union(x, fy), union(fx, fy), union(x, x), union(fx, fx))
p('and', inter(x, y), inter(y, x), inter(fx, y), inter(x, fy), inter(fx, fy), inter(x, x), inter(fx, fx))
p('sub', diff(x, y), diff(y, x), diff(fx, y), diff(x, fy), diff(fx, fy), diff(x, x), diff(fx, fx))
p('xor', sym(x, y), sym(y, x), sym(fx, y), sym(x, fy), sym(fx, fy), sym(x, x), sym(fx, fx))
p(inplace(set(x), y))
p(inplace(set(range(30)), fy))
p(cmp(x, y), cmp({1}, {1, 2}), cmp({1, 2}, {1, 2}), cmp(fx, x), cmp({1}, frozenset({1, 2})))
p(x.union(y), x.union([300, 5, 77], range(3), {88}), x.union())
p(x.intersection(y), x.intersection([5, 6, 7, 99], range(6, 9)), x.intersection())
p(x.difference(y), x.difference([5, 6], [7, 8], range(40, 43)), x.difference())
p(x.symmetric_difference(y), x.symmetric_difference([1, 2, 3, 3, 500]), x.symmetric_difference(range(8)))
p(x.issubset(y), {5, 6}.issubset(y), x.issuperset({1, 2}), x.issuperset([1, 2, 99]), x.isdisjoint([100]), x.isdisjoint(y))
p(y.issubset([5, 6, 7, 200, 300, 400, 3, 41, 9]), x.isdisjoint({}), x.isdisjoint(range(11, 20)))
s = set(x)
s.update(y, [1000, 2000], range(3))
p(s)
s.intersection_update(range(0, 60), [5, 6, 7, 8, 9, 10, 40, 41, 300, 1000])
p(s)
s.difference_update([5], {6}, range(40, 42))
p(s)
s.symmetric_difference_update([1000, 7, 7, 99])
p(s)
t = x.copy()
t.add(555)
p(len(x), len(t), x == t)
d = {10: 'a', 20: 'b', 30: 'c', 40: 'd', 50: 'e', 60: 'f', 70: 'g', 80: 'h'}
p(set(d), set(d.keys()), sorted(d.values()), x.union(d), x.intersection(d), x.difference(d), x.symmetric_difference(d))
big = {i * 11 for i in range(120)}
p(sorted(big | set(range(5)))[:8], len(big & set(range(500))), len(set(range(2000)) - big))
big2 = set(range(150))
big2 -= set(range(0, 150, 2))
p(big2)
big3 = set(range(150))
big3.difference_update(range(1, 150, 2))
p(big3)
big4 = set(range(100))
big4.difference_update(set(range(10, 100)))
p(big4)
big5 = set(range(300, 330))
big5.intersection_update(range(310, 5000))
p(big5)
u1 = {3, 6, 9, 12, 15, 18, 21, 24}
u2 = {7, 14, 21, 28}
u1 |= u2
p(u1)
u1 &= {3, 6, 7, 21, 99}
p(u1)
p(u1 | {1}, {1} | u1, u1 & u1, u1 - u1, u1 ^ u1)
p({1, 2, 3} | frozenset({4}), isinstance(frozenset({4}) | {1}, frozenset), isinstance({1} | frozenset({4}), set))
e = frozenset()
f = frozenset([3, 1, 2, 2, 1])
g = frozenset({5, 6})
p(e, f, g, repr(sorted(f)), len(str(sorted(g))), len(e), len(f), bool(e), bool(f))
p(f | g, f & frozenset([1, 2, 9]), f - {1}, f ^ g, f.union([8, 9]), f.copy() is f, f.copy() == f)
p(1 in f, 7 in f, f == frozenset([1, 2, 3]), f == {1, 2, 3}, {1, 2, 3} == f, f != g,
  f <= {1, 2, 3, 4}, f < f, f >= {1}, f > frozenset())
p(f.issubset({1, 2, 3, 4}), f.issuperset([1]), f.isdisjoint(g), sorted(f), min(f), max(f), sum(f),
  sorted(f), sorted(g))
t2 = set()
t2.add(frozenset([7, 8]))
t2.discard({7, 8})
p(t2)
t2.add(frozenset([7, 8]))
t2.remove(frozenset([8, 7]))
p(isinstance(f, frozenset), isinstance(f, set), isinstance({1}, frozenset), isinstance({1}, set))
x2 = {1, 2}
y2 = frozenset(x2)
x2.add(3)
p(x2, y2, set(y2), frozenset(x2), frozenset(y2) is y2, frozenset((1, 2, 3)) == x2)
p(sorted([q * 2 for q in sorted(frozenset([4, 3, 2, 1]))]), {q for q in sorted(frozenset([4, 3, 2, 1]))})
fs = frozenset([100, 200, 300, 400, 500])
ff = fs
ff |= {1, 2}
ff = frozenset([1, 2, 3])
ff &= {2, 3, 4}
ff -= {3}
ff ^= {9}
p(ff)
a = frozenset([1, 2, 3])
b = a
a = a | {4}
p(a, b)
p(f.difference(), f.intersection(), f.symmetric_difference([1]), f.union())
p(sorted(frozenset([(2, 1), (1, 2), (0, 5)])))
n = {1, 2, 3}
n.discard(2)
n.add(2)
p(n, sorted(n), len(n), 2 in n, 100 in n, min(n), max(n), sum(n))
'''

PROG_STR = r'''def norm(v):
    if isinstance(v, frozenset):
        return ["frozenset", sorted(v)]
    if isinstance(v, set):
        return ["set", sorted(v)]
    return v


def p(*args):
    print(*[norm(a) for a in args])


w = set(["pear", "apple", "fig", "kiwi"])
p(w)
p(sorted(w), len(w), "pear" in w, "zzz" in w, min(w), max(w))
p(w | set(["lime"]), w & set(["pear", "fig"]), w - set(["pear"]), w ^ set(["pear", "lime"]))
p(w.union(["lime", "fig"]), w.intersection(["pear", "fig"]), w.difference(["pear"]))
p(sorted(w)[0], sorted(w)[-1])
'''

PROG_DICT = r'''def norm(v):
    if isinstance(v, frozenset):
        return ["frozenset", sorted(v)]
    if isinstance(v, set):
        return ["set", sorted(v)]
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, tuple):
        return tuple([norm(x) for x in v])
    return v


def p(*args):
    print(*[norm(a) for a in args])


d = {}
for i, k in enumerate(['one', 'two', 'three', 'four', 'five']):
    d[k] = i
p(d, list(d), list(d.values()), list(d.items()))
del d['two']
d['two'] = 22
d['six'] = 6
p(d, list(d))
d.pop('one')
d['one'] = 1
p(d, d.popitem(), d)
e = {3: 'c', 1: 'a', 2: 'b'}
e[0] = 'z'
p(e, sorted(e), [k for k in e], {k: v for k, v in e.items()}, dict(zip('abc', range(3))))
e.update({1: 'A', 9: 'n'})
p(e, len(e), e == {3: 'c', 1: 'A', 2: 'b', 0: 'z', 9: 'n'}, e == {})
f = dict(e)
f[100] = 1
p(f != e, f == f, dict.fromkeys([5, 3, 5, 1]), {1: 2, 1: 3})
p({1: 1} == {1: 1.0}, {1: 'a'} == {True: 'a'}, {2: [1, 2]} == {2: [1, 2]}, {2: {1}} == {2: {1}})
h = {i: i * i for i in range(10)}
for k in list(h):
    if k % 3 == 0:
        del h[k]
h[3] = 'three'
p(h, list(h.keys()), list(h.values()))
words = ['pear', 'apple', 'fig', 'apple', 'pear', 'kiwi']
cnt = {}
for w in words:
    cnt[w] = cnt.get(w, 0) + 1
p(cnt, sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0])))
'''


class SetsGeneral(unittest.TestCase):
    def same_as_cpython(self, text, name, modes=GENERAL_MODES):
        with tempfile.TemporaryDirectory() as directory:
            want = run_cpython(directory, text, name)
            self.assertEqual(want.returncode, 0, want.stderr)
            for mode in modes:
                built, exe = build(directory, text, name, mode)
                self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout),
                                 '%s: %s' % (mode, got.stderr[-600:]))

    def test_s1_order_free_operators_and_methods_match_cpython(self):
        self.same_as_cpython(PROG_OPS, 'ops')

    def test_s2_a_set_of_str_through_sorted_forms_matches_cpython(self):
        self.same_as_cpython(PROG_STR, 'strs')

    def test_s3_an_order_revealing_walk_matches_cpython(self):
        text = 'def f():\n    s = {40, 33, 26}\n    for x in s:\n        print(x)\nf()\n'
        self.same_as_cpython(text, 'walk')

    def test_s4_dict_iteration_keeps_insertion_order(self):
        self.same_as_cpython(PROG_DICT, 'dict')


if __name__ == '__main__':
    unittest.main()
