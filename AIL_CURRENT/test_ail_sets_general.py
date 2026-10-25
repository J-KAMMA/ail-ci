"""Sets, frozensets and dicts on the general (boxed) path.

A set keeps its elements in insertion order on both paths (DIFFERENCES.md A2): iteration, repr, print, list(),
`pop()` (the first element in iteration order) and the result of `| & - ^`, their in-place forms and the named methods
(`a | b` is a's elements then b's new ones; `a & b` and `a - b` keep a's order; `a ^ b` is a's elements not in b
then b's elements not in a; a result has the type of the left operand). The output of a program must not depend
on which path built it, so the order is compared between paths, not with CPython. Where the order cannot show
(sorted forms, len, membership, comparisons) the answers are compared with CPython 3.12.

S1  the typed path, the default build (AIL_IR=0 / 1) and the general path print the same order
S2  random programs over set[int] (typed subset): the same on all five builds
S3  fixed expectations for the order on the general path
S4  operators and methods on values of unknown type, frozenset, errors, dict: against CPython (sorted forms)
S5  a set of str can be walked, printed and popped
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
ON_312 = sys.version_info[:2] == (3, 12)


def build(directory, text, name, mode):
    """Compile `text` in one mode: general (the boxed path alone), default and default_ir (typed path first, general on
    a refusal, AIL_IR=0 / 1), typed and typed_ir (no fallback)."""
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_' + mode)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    env.pop('AIL_NO_GENERAL', None)
    env['AIL_IR'] = '1' if mode.endswith('_ir') else '0'
    if mode == 'general':
        command = [sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only']
    else:
        if mode.startswith('typed'):
            env['AIL_NO_GENERAL'] = '1'
        command = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                   '--syntax', 'python', '-o', exe.name]
    return subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


def run_cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=120, encoding='utf-8')


def run_exe(exe, stdin=''):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120, encoding='utf-8', input=stdin)


ALL_MODES = ('typed', 'typed_ir', 'default', 'default_ir', 'general')
GENERAL_MODES = ('general', 'default', 'default_ir')


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
'''

PROG_FROZEN = r'''def norm(v):
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


e = frozenset()
f = frozenset([3, 1, 2, 2, 1])
g = frozenset({5, 6})
p(e, f, g, repr(sorted(f)), len(str(g)), len(e), len(f), bool(e), bool(f))
p(f | g, f & frozenset([1, 2, 9]), f - {1}, f ^ g, f.union([8, 9]), f.copy() is f, f.copy() == f)
p(1 in f, 7 in f, f == frozenset([1, 2, 3]), f == {1, 2, 3}, {1, 2, 3} == f, f != g, f <= {1, 2, 3, 4}, f < f, f >= {1}, f > frozenset())
p(f.issubset({1, 2, 3, 4}), f.issuperset([1]), f.isdisjoint(g), sorted(f), min(f), max(f), sum(f), sorted(list(f)), sorted(tuple(g)))
d = {frozenset([1, 2]): 'a', frozenset([2, 1]): 'b', frozenset(): 'c', frozenset([3]): 'd'}
s = {frozenset([1]), frozenset([2, 3]), frozenset([1]), frozenset(), frozenset([(1, 2)]), 5, (1, frozenset([4]))}
p({1, 2} in {frozenset({1, 2})}, frozenset({1, 2}) in {frozenset({1, 2})})
t = set()
t.add(frozenset([7, 8]))
t.discard({7, 8})
p(t)
t.add(frozenset([7, 8]))
t.remove(frozenset([8, 7]))
nested = frozenset([frozenset([1, 2]), frozenset([3]), frozenset()])
p(isinstance(f, frozenset), isinstance(f, set), isinstance({1}, frozenset), isinstance({1}, set))
x = {1, 2}
y = frozenset(x)
x.add(3)
p(x, y, set(y), frozenset(x), frozenset(y) is y, frozenset((1, 2, 3)) == x)
for q in sorted(frozenset([10, 20, 30, 5, 15])):
    print(q, end=' ')
p()
p(sorted([q * 2 for q in frozenset([4, 3, 2, 1])]), {q for q in frozenset([4, 3, 2, 1])})
fs = frozenset([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200])
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
k = {frozenset([1, 2]), frozenset([2, 3]), frozenset([3, 4]), frozenset([4, 5]), frozenset([5, 6]), frozenset([6, 7]), frozenset([7, 8]), frozenset([8, 9])}
'''

PROG_ERR = r'''def norm(v):
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


s = {1, 2, 3}
f = frozenset([1, 2])
for body in range(10):
    try:
        if body == 0:
            s.remove(99)
        elif body == 1:
            set().pop()
        elif body == 2:
            f.add(3)
        elif body == 3:
            f.discard(1)
        elif body == 4:
            f.pop()
        elif body == 5:
            f.update([3])
        elif body == 6:
            f.clear()
        elif body == 7:
            s.add([1])
        elif body == 8:
            s.add({1})
        elif body == 9:
            x = {1, 2} | [3]
    except KeyError as e:
        print('KeyError', e)
    except AttributeError as e:
        print('AttributeError', e)
    except TypeError as e:
        print('TypeError', e)
try:
    for v in s:
        s.add(v + 10)
except RuntimeError as e:
    print('RuntimeError', e)
p(sorted(s)[:3], len(s))
p(7 in {1: 2}, {1, 2} == {2, 1}, {1: 2} == {1: 2}, {1: 2, 3: 4} == {3: 4, 1: 2}, {1: 2} != {1: 3}, {} == {}, {1} == [1])
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
g = {(1, 2): 'a', (0, 0): 'b', 'k': [1, 2], 5: {1, 2}}
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

# the typed subset: the typed path builds it, so its order is the reference for every other build
PROG_TYPED_ORDER = r'''def dump(tag: str, s: set[int]) -> None:
    print(tag, len(s))
    for x in s:
        print(x, end=" ")
    print()


def sdump(tag: str, s: set[str]) -> None:
    print(tag, len(s))
    for x in s:
        print(x, end=" ")
    print()


def main() -> None:
    a: set[int] = set()
    for i in range(0, 60, 7):
        a.add(i)
    b: set[int] = {3, 1, 2, 100, 33, 7, 14}
    dump("a", a)
    dump("b", b)
    dump("or", a | b)
    dump("and", a & b)
    dump("minus", a - b)
    dump("xor", a ^ b)
    dump("ba", b - a)
    c: set[int] = set(a)
    c.discard(14)
    c.add(14)
    c.add(500)
    dump("readd", c)
    c |= b
    dump("ior", c)
    c &= {500, 3, 14, 100, 1}
    dump("iand", c)
    c -= {3}
    dump("isub", c)
    c ^= {9, 100, 8}
    dump("ixor", c)
    print(c.pop(), c.pop())
    dump("popped", c)
    d: set[int] = a.union(b)
    dump("union", d)
    dump("inter", a.intersection(b))
    dump("diff", a.difference(b))
    dump("sym", a.symmetric_difference(b))
    e: set[int] = set(b)
    e.update(a)
    dump("update", e)
    e.intersection_update(b)
    dump("iu", e)
    e.symmetric_difference_update(a)
    dump("sdu", e)
    e.difference_update(b)
    dump("du", e)
    s: set[str] = {"pear", "apple", "fig"}
    t: set[str] = {"fig", "kiwi", "plum", "apple"}
    sdump("s", s)
    sdump("or", s | t)
    sdump("and", s & t)
    sdump("minus", t - s)
    sdump("xor", s ^ t)
    s.add("zed")
    s.discard("pear")
    s.add("pear")
    sdump("s2", s)
    print(s.pop())
    big: set[int] = set()
    for i in range(300):
        big.add((i * 37) % 211)
    for i in range(0, 211, 3):
        big.discard(i)
    big.add(0)
    dump("big", big)


main()
'''

# order-free, and the typed path builds it too
PROG_TYPED = r'''
def uniq(xs: list[int]) -> int:
    seen: set[int] = set()
    for x in xs:
        seen.add(x)
    return len(seen)


def main() -> None:
    xs = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    s: set[int] = set(xs)
    t: set[int] = {2, 3, 5, 7}
    print(len(s), 4 in s, 8 in s, min(s), max(s), sum(s))
    for x in sorted(s | t):
        print(x, end=" ")
    print()
    for x in sorted(s & t):
        print(x, end=" ")
    print()
    for x in sorted(s - t):
        print(x, end=" ")
    print()
    for x in sorted(s ^ t):
        print(x, end=" ")
    print()
    print(uniq(xs))
    names: set[str] = {'pear', 'fig'}
    names.add('kiwi')
    print(len(names), 'fig' in names)
    for w in sorted(names):
        print(w)


main()
'''

PROG_A2 = r'''
s = {3, 1, 2, 100, 33}
print(s, list(s))
t = set([9, 8, 7, 8])
t.discard(9)
t.add(9)
print(t)
print(t.pop())
print(t)
print(s | {5, 1}, s & {33, 3}, s - {1}, s ^ {2, 7})
print(s.union([8, 3, 4]), s.intersection([33, 1, 77]), s.difference([1, 100]), s.symmetric_difference([2, 50, 50, 60]))
u = set(s)
u.update([7, 3, 6])
u.intersection_update([6, 7, 3, 33, 100])
print(u)
u.symmetric_difference_update([100, 9, 8])
print(u)
print(frozenset([3, 1, 2]), frozenset(), set(), frozenset([5, 4]) | {1}, {1} | frozenset([5, 4]))
w = {"pear", "apple", "fig"}
print(w, sorted(w))
for x in {7, 5, 6}:
    print(x, end=" ")
print()
print([x for x in {9, 2, 5}], {x % 4 for x in [10, 7, 5, 3, 6]}, list({40, 30, 20}), tuple({1, 0}))
d = {"k": 1, "j": 2}
print(set(d), set(d.keys()), set(d.values()), set("hello"))
n = {1, 2, 3}
n.discard(2)
n.add(2)
print(n, sorted(n))
while n:
    print(n.pop(), end=" ")
print()
'''

A2_EXPECTED = '''{3, 1, 2, 100, 33} [3, 1, 2, 100, 33]
{8, 7, 9}
8
{7, 9}
{3, 1, 2, 100, 33, 5} {3, 33} {3, 2, 100, 33} {3, 1, 100, 33, 7}
{3, 1, 2, 100, 33, 8, 4} {1, 33} {3, 2, 33} {3, 1, 100, 33, 50, 60}
{3, 100, 33, 7, 6}
{3, 33, 7, 6, 9, 8}
frozenset({3, 1, 2}) frozenset() set() frozenset({5, 4, 1}) {1, 5, 4}
{'pear', 'apple', 'fig'} ['apple', 'fig', 'pear']
7 5 6 
[9, 2, 5] {2, 3, 1} [40, 30, 20] (1, 0)
{'k', 'j'} {'k', 'j'} {1, 2} {'h', 'e', 'l', 'o'}
{1, 3, 2} [1, 2, 3]
1 3 2 
'''


def gen_typed_random(seed, nstmt=60):
    """A program over set[int] in the subset the typed path builds, printing its sets as it goes."""
    r = random.Random(seed)
    names = ['a', 'b', 'c']
    L = ['def dump(tag: str, s: set[int]) -> None:',
         '    print(tag, len(s))',
         '    for x in s:',
         '        print(x, end=" ")',
         '    print()',
         '',
         '',
         'def main() -> None:',
         '    a: set[int] = set()',
         '    b: set[int] = {%s}' % ', '.join(str(r.randint(0, 40)) for _ in range(r.randint(1, 8))),
         '    c: set[int] = set()']
    for i in range(r.randint(0, 30)):
        L.append('    c.add(%d)' % r.randint(-5, 300))
    for k in range(nstmt):
        x, y, z = r.choice(names), r.choice(names), r.choice(names)
        n = r.randint(-3, 120)
        ops = [
            '%s.add(%d)' % (x, n), '%s.add(%d)' % (x, n), '%s.add(%d)' % (x, n), '%s.discard(%d)' % (x, n),
            '%s.discard(%d)' % (x, r.randint(0, 40)),
            '%s |= %s' % (x, y), '%s &= %s' % (x, y), '%s -= %s' % (x, y), '%s ^= %s' % (x, y),
            '%s.update(%s)' % (x, y), '%s.intersection_update(%s)' % (x, y), '%s.difference_update(%s)' % (x, y),
            '%s.symmetric_difference_update(%s)' % (x, y),
            '%s = %s | %s' % (x, y, z), '%s = %s & %s' % (x, y, z), '%s = %s - %s' % (x, y, z), '%s = %s ^ %s' % (x, y, z),
            '%s = %s.union(%s)' % (x, y, z), '%s = %s.difference(%s)' % (x, y, z),
            'if len(%s) > 0:\n        print(%s.pop())' % (x, x),
            'if len(%s) > 0:\n        print(%s.pop())' % (x, x),
            '%s.clear()' % x if r.random() < 0.15 else '%s.add(%d)' % (x, n),
            'print(%s == %s, %s <= %s, %s.isdisjoint(%s), %d in %s)' % (x, y, x, y, x, y, n, x),
        ]
        L.append('    ' + r.choice(ops))
        if r.random() < 0.4:
            L.append('    dump("%d", %s)' % (k, r.choice(names)))
    for nm in names:
        L.append('    dump("end", %s)' % nm)
    L += ['', '', 'main()', '']
    return '\n'.join(L)


class SetsGeneral(unittest.TestCase):
    def outputs(self, text, name, modes):
        """Build `text` in every mode and return {mode: (returncode, stdout)}."""
        out = {}
        with tempfile.TemporaryDirectory() as directory:
            for mode in modes:
                built, exe = build(directory, text, name, mode)
                self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
                got = run_exe(exe)
                out[mode] = (got.returncode, got.stdout, got.stderr[-300:])
        return out

    def identical(self, text, name, modes=ALL_MODES):
        out = self.outputs(text, name, modes)
        first = out[modes[0]]
        for mode in modes:
            self.assertEqual(out[mode][:2], first[:2], '%s differs from %s: %s' % (mode, modes[0], out[mode][2]))
        return first[1]

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

    def test_s1_typed_default_and_general_print_the_same_order(self):
        out = self.identical(PROG_TYPED_ORDER, 'typed_order')
        lines = out.split('\n')
        # insertion order: a is 0, 7, 14, ... ; a | b appends b's new elements; pop takes the first
        self.assertEqual(lines[1], '0 7 14 21 28 35 42 49 56 ')
        self.assertIn('or 12', out)

    def test_s1_order_free_program_agrees_with_cpython_on_every_build(self):
        with tempfile.TemporaryDirectory() as directory:
            want = run_cpython(directory, PROG_TYPED, 'typed_free')
            for mode in ALL_MODES:
                built, exe = build(directory, PROG_TYPED, 'typed_free', mode)
                self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
                self.assertEqual(run_exe(exe).stdout, want.stdout, mode)

    def test_s2_random_set_int_programs_are_identical_on_all_builds(self):
        for seed in range(6):
            self.identical(gen_typed_random(seed), 'rnd%d' % seed)

    def test_s3_order_on_the_general_path(self):
        out = self.identical(PROG_A2, 'a2', modes=GENERAL_MODES)
        self.assertEqual(out, A2_EXPECTED)

    def test_s4_operators_and_methods_on_values_of_unknown_type(self):
        self.same_as_cpython(PROG_OPS, 'ops')

    def test_s4_frozenset(self):
        self.same_as_cpython(PROG_FROZEN, 'frozen')

    def test_s4_errors(self):
        self.same_as_cpython(PROG_ERR, 'err')

    def test_s4_dict_equality_and_order(self):
        self.same_as_cpython(PROG_DICT, 'dict')

    def test_s5_a_set_of_str_can_be_walked_printed_and_popped(self):
        text = '''
w = set(["pear", "apple", "fig", "kiwi"])
print(w)
for x in w:
    print(x, end=" ")
print()
print(list(w), tuple(w), [x.upper() for x in w], ",".join(w))
print(sum(len(x) for x in w), w.pop(), w)
print({"b", "a", "c"}, frozenset(["z", "y"]))
'''
        out = self.identical(text, 'strwalk', modes=GENERAL_MODES)
        self.assertEqual(out.split('\n')[0], "{'pear', 'apple', 'fig', 'kiwi'}")
        self.assertEqual(out.split('\n')[1], 'pear apple fig kiwi ')
        self.assertIn("pear {'apple', 'fig', 'kiwi'}", out)
        self.assertEqual(out.split('\n')[-2], "{'b', 'a', 'c'} frozenset({'z', 'y'})")

    def test_s5_the_old_refusal_is_gone(self):
        text = 'S = {"a", "b", "c"}\nn = 0\nfor w in S:\n    n += len(w)\nprint(n, len(list(S)))\n'
        self.assertEqual(self.identical(text, 'nofuss', modes=GENERAL_MODES), '3 3\n')


if __name__ == '__main__':
    unittest.main()
