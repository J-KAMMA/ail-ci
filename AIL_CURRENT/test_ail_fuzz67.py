"""fuzz67: class variables and instance variables.

A class-body assignment (`K = value`) was copied onto every instance when the instance was constructed.
A mutating class-level list was therefore per instance (`c.xs.append(1)` left `d.xs` untouched), class
attributes appeared in `vars(instance)`, and a class read or rebind (`C.x`, `cls.x += 1`, `C.items`)
failed with `'type' object has no attribute`.  The class object now owns its attribute table; an instance
reads it as a fallback (an instance assignment shadows one), and `C.x` / `cls.x = ...` use it directly.

Each program below is built both the default way and with the general path forced (as `tools/cmp.sh`
does) and must print what CPython 3.12 prints, with the same exit status.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'


SHARED_LIST = r'''class C:
    items = []

    def __init__(self):
        pass

    def add(self, x):
        self.items.append(x)


c = C()
d = C()
c.add(1)
d.add(2)
C.items.append(3)
print(C.items, c.items, d.items, C.items is c.items)
print(vars(c), vars(d))


C.add(c, 4)
print(c.items, d.items)
'''

CLASS_READ = r'''class Reg:
    data = {}

    def __init__(self, tag):
        self.tag = tag

    def put(self, k, v):
        self.data[k] = v
        return self.data


r = Reg('a')
s = Reg('b')
r.put('x', 1)
s.put('y', 2)
print(Reg.data, r.data, s.data)
regs = [r, s]
regs[0].put('z', 3)
print(Reg.data is r.data, sorted(Reg.data.items()))
'''

SHADOW = r'''class Bank:
    rate = 2

    def __init__(self, n):
        self.n = n

    def show(self):
        return self.n * self.rate


b = Bank(5)
print(b.show(), Bank.rate)
b.rate = 10
print(b.show(), Bank.rate, vars(b))
print('rate' in vars(b), Bank.rate)
'''

REBIND = r'''class C:
    n = 1
    label = 'a'

    def __init__(self):
        self.k = 1

    @classmethod
    def bump(cls, k):
        cls.n += k
        return cls.n


c = C()
print(C.n, c.n, C.label, c.label)
C.n += 4
print(C.bump(2), C.n, c.n)
c.n += 1
print(C.n, c.n, vars(c))
C.label = 'b'
print(C.label, c.label, vars(c))
'''

COUNTER_SUBCLASS = r'''class Counter:
    count = 0

    @classmethod
    def inc(cls, k=1):
        cls.count += k
        return cls.count


class Sub(Counter):
    pass


print(Counter.count, Sub.count)
print(Counter.inc(), Counter.inc(2), Counter.count)
print(Sub.inc(5), Sub.inc(-3), Sub.count, Counter.count)
c = Counter()
s = Sub()
print(c.count, s.count, type(c).__name__, type(s).__name__)
'''

NESTED = r'''class Nest:
    grid = [[1, 2], [], [3]]

    def __init__(self):
        pass


a = Nest()
b = Nest()
a.grid[1].append(9)
a.grid.append([4])
a.grid[0][-1] += 10
print(b.grid)
print(Nest.grid is b.grid, len(b.grid), b.grid[0][-1])
'''

INHERITANCE = r'''class Base:
    items = [1]
    label = 'base'

    def __init__(self):
        pass


class Child(Base):
    items = [2]
    label = 'child'


b = Base()
c = Child()
c.items.append(3)
print(Base.items, Child.items, b.items, c.items)
print(b.label, c.label, Base.label, Child.label)
Base.items.append(4)
print(b.items, c.items)
c.label = 'mine'
print(c.label, Child.label, c.__class__.__name__)
'''

VIA_ARGUMENT = r'''class Box:
    items = []

    def __init__(self, v):
        self.v = v


def grow(xs):
    xs.append(99)
    return xs


def show(o):
    return (o.v, o.items)


a = Box(1)
b = Box(2)
g = grow(a.items)
print(g is b.items, a.items, b.items)
boxes = [a, b]
d = {'first': a, 'second': b}
boxes[0].items.append(7)
d['second'].items.append(8)
print(a.items, b.items, Box.items)
print(show(a), show(b))
'''

EDGES = r'''class Acc:
    xs = []
    total = 0
    step = -2

    def __init__(self):
        pass

    def add(self, v):
        self.xs.append(v)
        Acc.total += self.step

    @classmethod
    def count(cls):
        return len(cls.xs)


a = Acc()
b = Acc()
print(a.xs, a.total, Acc.count())
a.add(0)
b.add(-5)
print(a.xs, b.xs, a.total, Acc.total, Acc.count())
a.xs[-1] = 7
print(b.xs, a.xs)
try:
    print(a.xs[10 ** 9])
except IndexError as e:
    print('IndexError', e)
try:
    Acc.total += 'x'
except TypeError:
    print('TypeError')
print(Acc.total, type(Acc.total).__name__)
a.xs.append('mixed')
print(a.xs, b.xs, Acc.count())
'''

ATTR_FALLBACK = r'''class Base:
    x = 5
    xs = [1]


class C(Base):
    def __init__(self):
        self.y = 2


c = C()
print(getattr(c, 'x', 'missing'), getattr(c, 'xs', 'missing'))
print(getattr(c, 'nope', 'missing'))
print(hasattr(c, 'x'), hasattr(c, 'y'), hasattr(c, 'z'))
print(getattr(c, 'x'))
print('{0.xs}'.format(c), '{0.y}'.format(c))
c.xs.append(9)
print(Base.xs, C.xs, c.xs)
C.x = {'a': 4, 'b': 5}
print(len(c.x), sorted(c.x), getattr(c, 'x'))
print('{0.x}'.format(c))
try:
    getattr(c, 'nope')
except AttributeError as e:
    print('AttributeError', e)


class D:
    v = [10, 20]


d = D()
D.v = 'ab'
print(len(d.v), d.v[0], d.v[1])
for ch in d.v:
    print(ch)
'''

CASES = [
    ('shared_list', SHARED_LIST),
    ('attr_fallback', ATTR_FALLBACK),
    ('class_read', CLASS_READ),
    ('shadow', SHADOW),
    ('rebind', REBIND),
    ('counter_subclass', COUNTER_SUBCLASS),
    ('nested', NESTED),
    ('inheritance', INHERITANCE),
    ('via_argument', VIA_ARGUMENT),
    ('edges', EDGES),
]


class Fuzz67(unittest.TestCase):
    def build(self, directory, name, text, general):
        source = Path(directory, name + '.ail')
        source.write_text(text, encoding='utf-8')
        exe = Path(directory, name + ('_g' if general else '_d'))
        env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
        env.pop('AIL_NO_GENERAL', None)
        if general:
            env['AIL_UNIFIED_FORCE'] = '1'
        else:
            env.pop('AIL_UNIFIED_FORCE', None)
        built = subprocess.run([sys.executable, '-B', str(CLI), 'compile', source.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
        return built, source, exe

    def test_class_variables_and_instance_variables(self):
        for name, text in CASES:
            with self.subTest(name):
                with tempfile.TemporaryDirectory(prefix='ail-fuzz67-') as directory:
                    src = Path(directory, name + '_cp.py')
                    src.write_text(text, encoding='utf-8')
                    want = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120)
                    for general in (False, True):
                        built, source, exe = self.build(directory, name, text, general)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        got = subprocess.run([str(exe)], capture_output=True, timeout=120)
                        self.assertEqual(got.stdout.decode('utf-8', 'replace'),
                                         want.stdout.decode('utf-8', 'replace'),
                                         '%s general=%s\n%s' % (name, general, got.stderr.decode('utf-8', 'replace')))
                        self.assertEqual(got.returncode, want.returncode, (name, general))


if __name__ == '__main__':
    unittest.main()
