"""Method calls on the general (boxed) path dispatch on the run-time class, as CPython does (DIFFERENCES.md C27).

`self.m()` inside a method, `obj.m()` on a receiver whose class is known, `super().m()` and the special methods the
emitter binds statically (`==`, `<`, `in`, `[]`, `len`, `str`, `repr`) must reach the override of a subclass, and a class
attribute that a subclass does not redefine must be read through the base. A class whose methods nothing overrides keeps
a direct call (no run-time test), so a program without overrides costs the same as before.

V1  fixed programs against CPython 3.12: several levels, an override called from a base method, a super() chain, an
    override only in a grandchild, class attributes through self, different defaults per override, arguments
    evaluated once, special methods
V2  a diamond (multiple inheritance) is refused by name, never built with a wrong answer
V3  the typed path builds the same single-inheritance program (test_ail_typed_inherit.py has the rest)
V4  random single-inheritance hierarchies (generated, run through CPython and through AIL): the same output
V5  a class without overrides keeps its direct calls in the generated C
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


def build(directory, text, name, extra_env=None):
    """Compile `text` on the general path alone; returns (completed process, exe path)."""
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_g')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    env.pop('AIL_NO_GENERAL', None)
    env['AIL_IR'] = '0'
    env.update(extra_env or {})
    command = [sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only']
    return subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


def run_cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=120, encoding='utf-8')


def run_exe(exe):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120, encoding='utf-8')


PROG_LEVELS = r'''
class A:
    def f(self):
        return self.g()
    def g(self):
        return 1
    def h(self, x):
        return self.g() * x
class B(A):
    def g(self):
        return 2
class C(B):
    def g(self):
        return super().g() + 10
class D(C):
    pass
class E(A):
    pass
def call(o):
    return o.f()
def main():
    print(A().f(), B().f(), C().f(), D().f(), E().f())
    print(A().h(3), B().h(3), C().h(3), D().h(3), E().h(3))
    print(call(A()), call(B()), call(C()), call(D()), call(E()))
    objs = [A(), B(), C(), D(), E()]
    total = 0
    for o in objs:
        total += o.f() + o.h(2)
    print(total)
    d = D()
    print(d.g(), d.f(), d.h(4))
main()
'''

PROG_GRANDCHILD = r'''
class Base:
    def run(self):
        return self.step() + self.last()
    def step(self):
        return 1
    def last(self):
        return 100
class Mid(Base):
    def other(self):
        return self.step() * 3
class Leaf(Mid):
    def step(self):
        return 7
    def last(self):
        return super().last() + 1
def main():
    b = Base()
    m = Mid()
    l = Leaf()
    print(b.run(), m.run(), l.run())
    print(m.other(), l.other())
    for o in (b, m, l):
        print(o.run())
main()
'''

PROG_SUPER = r'''
class A:
    def name(self):
        return "A"
    def chain(self, k):
        return self.name() + str(k)
class B(A):
    def name(self):
        return "B" + super().name()
class C(B):
    def name(self):
        return "C" + super().name()
class D(C):
    def chain(self, k):
        return "D" + super().chain(k + 1)
def main():
    print(A().chain(0), B().chain(0), C().chain(0), D().chain(0))
    x = D()
    print(x.name(), x.chain(5))
main()
'''

PROG_CLASSATTR = r'''
class A:
    K = 10
    NAME = "a"
    def total(self):
        return self.K + len(self.NAME) + self.extra()
    def extra(self):
        return 0
class B(A):
    K = 20
class C(B):
    NAME = "ccc"
    def extra(self):
        return self.K
class D(A):
    pass
def main():
    print(A().total(), B().total(), C().total(), D().total())
    print(A().K, B().K, C().K, D().K, C().NAME, D().NAME, B().NAME)
main()
'''

PROG_SIGNATURES = r'''
class A:
    def go(self, x, y=1):
        return self.calc(x, y)
    def calc(self, x, y=5):
        return x + y
class B(A):
    def calc(self, x, y=50):
        return x * y
class C(B):
    def calc(self, x, y=7, z=3):
        return x - y - z
def main():
    for o in (A(), B(), C()):
        print(o.go(2), o.go(2, 4), o.go(x=3), o.calc(2), o.calc(2, y=9))
main()
'''

PROG_ONCE = r'''
log = []
def tick(v):
    log.append(v)
    return v
class A:
    def m(self, x):
        return x + 1
class B(A):
    def m(self, x):
        return x + 2
class C(B):
    def m(self, x):
        return x + 3
def main():
    a = A()
    b = B()
    c = C()
    print(a.m(tick(10)), b.m(tick(10)), c.m(tick(10)), c.m(x=tick(20)))
    print(log)
main()
'''

PROG_SPECIAL = r'''
class A:
    def __init__(self, v):
        self.v = v
    def __eq__(self, other):
        return self.v == other.v
    def __lt__(self, other):
        return self.v < other.v
    def __len__(self):
        return 1
    def __getitem__(self, i):
        return self.v + i
    def __contains__(self, x):
        return x == self.v
    def __str__(self):
        return "A(" + str(self.v) + ")"
    def __repr__(self):
        return "rA"
class B(A):
    def __eq__(self, other):
        return True
    def __lt__(self, other):
        return False
    def __len__(self):
        return 2
    def __getitem__(self, i):
        return -i
    def __contains__(self, x):
        return True
    def __str__(self):
        return "B"
class C(B):
    def __repr__(self):
        return "rC"
def main():
    a = A(1)
    b = B(1)
    c = C(2)
    print(a == A(1), a == A(2), a < A(2), len(a), a[3], 1 in a, 5 in a)
    print(b == B(2), b < B(2), len(b), b[3], 1 in b, 5 in b)
    print(c == C(2), c < C(0), len(c), c[3], 2 in c)
    print(str(a), str(b), str(c), repr(a), repr(b), repr(c))
    print(a, b, c)
main()
'''

PROG_STATIC = r'''
class A:
    @staticmethod
    def make(n):
        return n + 1
    def go(self):
        return self.make(1)
class B(A):
    @staticmethod
    def make(n):
        return n + 100
def main():
    print(A().go(), B().go())
main()
'''

FIXED = [('levels', PROG_LEVELS), ('grandchild', PROG_GRANDCHILD), ('super', PROG_SUPER),
         ('classattr', PROG_CLASSATTR), ('signatures', PROG_SIGNATURES), ('once', PROG_ONCE),
         ('special', PROG_SPECIAL), ('static', PROG_STATIC)]

PROG_DIAMOND = r'''
class A:
    def who(self):
        return "A"
class B(A):
    def who(self):
        return "B" + super().who()
class C(A):
    def who(self):
        return "C" + super().who()
class D(B, C):
    def who(self):
        return "D" + super().who()
print(D().who())
'''

PROG_TYPED = r'''
class A:
    def __init__(self, n: int):
        self.n = n
    def f(self) -> int:
        return self.g() + self.n
    def g(self) -> int:
        return 1
class B(A):
    def g(self) -> int:
        return 2
def main():
    print(B(1).f())
main()
'''


class Base(unittest.TestCase):
    def check_same(self, text, name):
        with tempfile.TemporaryDirectory() as d:
            ref = run_cpython(d, text, name)
            self.assertEqual(ref.returncode, 0, ref.stderr)
            res, exe = build(d, text, name)
            self.assertEqual(res.returncode, 0, name + ': ' + res.stdout + res.stderr)
            out = run_exe(exe)
            self.assertEqual(out.returncode, 0, name + ': ' + out.stderr)
            self.assertEqual(out.stdout, ref.stdout, name)


class TestFixed(Base):
    """V1"""

    def test_fixed_programs(self):
        for name, text in FIXED:
            with self.subTest(program=name):
                self.check_same(text, 'v1_' + name)


class TestRefusals(Base):
    """V2, V3"""

    def test_diamond_refused_by_name(self):
        with tempfile.TemporaryDirectory() as d:
            res, exe = build(d, PROG_DIAMOND, 'v2_diamond')
            self.assertNotEqual(res.returncode, 0, 'a diamond must not build on the general path')
            self.assertIn('multiple inheritance', res.stdout + res.stderr)
            self.assertFalse(exe.exists())

    def test_typed_path_builds_inheritance(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d, 'v3_typed.py')
            src.write_text(PROG_TYPED, encoding='utf-8')
            env = dict(os.environ, AIL_NO_GENERAL='1', AIL_IR='0')
            res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                                  '--syntax', 'python', '-o', 'v3_typed_exe'], cwd=d, capture_output=True,
                                 text=True, timeout=900, env=env)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            out = run_exe(Path(d, 'v3_typed_exe'))
            self.assertEqual(out.stdout, run_cpython(d, PROG_TYPED, 'v3_typed').stdout)


# ---------------------------------------------------------------------------------------------- random programs
def gen_program(seed, n_classes=None):
    """A random single-inheritance hierarchy.  Every method is `mI(self, x, y=D)`; mI may call only mJ with J > I (no
    recursion) through self or through super() (when a base class defines mI), and may read the class attribute K.
    Returns the program text."""
    rng = random.Random(seed)
    n = n_classes or rng.randint(3, 7)
    n_methods = 4
    parent = {}
    own = {}                       # class -> {method index: default}
    attr = {}
    for c in range(n):
        parent[c] = rng.randrange(c) if c else None      # one tree rooted at C0
        own[c] = {i: rng.randint(1, 9) for i in range(n_methods) if rng.random() < 0.45}
        attr[c] = rng.randint(1, 30) if (c == 0 or rng.random() < 0.3) else None
    own[0] = {i: own[0].get(i, rng.randint(1, 9)) for i in range(n_methods)}      # the root defines every method

    def has_super(c, i):
        p = parent[c]
        while p is not None:
            if i in own[p]:
                return True
            p = parent[p]
        return False

    lines = []
    for c in range(n):
        head = 'class C%d' % c + ('(C%d):' % parent[c] if parent[c] is not None else ':')
        lines.append(head)
        if attr[c] is not None:
            lines.append('    K = %d' % attr[c])
        if not own[c] and attr[c] is None:
            lines.append('    pass')
        for i, default in sorted(own[c].items()):
            lines.append('    def m%d(self, x, y=%d):' % (i, default))
            terms = ['x', 'y * %d' % rng.randint(1, 5)]
            if rng.random() < 0.5 and i + 1 < n_methods:
                j = rng.randint(i + 1, n_methods - 1)
                terms.append('self.m%d(x + %d)' % (j, rng.randint(0, 3)))
            if rng.random() < 0.3 and i + 1 < n_methods:
                j = rng.randint(i + 1, n_methods - 1)
                terms.append('self.m%d(%d, y=%d)' % (j, rng.randint(0, 5), rng.randint(0, 5)))
            if has_super(c, i) and rng.random() < 0.6:
                terms.append('super().m%d(x)' % i)
            if rng.random() < 0.4:
                terms.append('self.K')
            rng.shuffle(terms)
            lines.append('        return (%s) %% 1000003' % ' + '.join(terms))
    lines.append('def via(o, x):')
    lines.append('    return o.m0(x) + o.m1(x, 2)')
    lines.append('def main():')
    for c in range(n):
        lines.append('    o%d = C%d()' % (c, c))
        for i in range(n_methods):
            lines.append('    print(%d, %d, o%d.m%d(%d), o%d.m%d(%d, %d))' % (
                c, i, c, i, rng.randint(0, 9), c, i, rng.randint(0, 9), rng.randint(0, 9)))
        lines.append('    print(via(o%d, %d), o%d.K)' % (c, rng.randint(0, 9), c))
    lines.append('    objs = [%s]' % ', '.join('o%d' % c for c in range(n)))
    lines.append('    acc = 0')
    lines.append('    for o in objs:')
    lines.append('        acc = (acc + o.m0(3) + o.m%d(acc %% 17)) %% 1000003' % rng.randint(0, n_methods - 1))
    lines.append('    print(acc)')
    lines.append('main()')
    return '\n'.join(lines) + '\n'


class TestRandom(Base):
    """V4"""
    SEEDS = int(os.environ.get('AIL_VDISPATCH_SEEDS', '8'))

    def test_random_hierarchies(self):
        for seed in range(self.SEEDS):
            with self.subTest(seed=seed):
                self.check_same(gen_program(seed), 'v4_%d' % seed)

    def test_generator_is_deterministic_and_varied(self):
        self.assertEqual(gen_program(3), gen_program(3))
        self.assertNotEqual(gen_program(3), gen_program(4))
        # some program overrides a method below a class that calls it through self
        self.assertTrue(any('super().m' in gen_program(s) for s in range(8)))


class TestStaticKept(Base):
    """V5"""

    def c_of(self, text, name):
        with tempfile.TemporaryDirectory() as d:
            res, exe = build(d, text, name, {'AIL_KEEP_C': '1'})
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            c_files = list(Path(d).glob('*.c'))
            self.assertTrue(c_files, 'no C file kept')
            return c_files[0].read_text(encoding='utf-8', errors='replace')

    def test_no_override_means_no_runtime_class_test(self):
        plain = ("class P:\n    def a(self):\n        return 1\n    def b(self):\n        return self.a() + 1\n"
                 "class Q(P):\n    def c(self):\n        return self.b()\nprint(Q().c())\n")
        over = plain.replace('    def c(self)', '    def a(self):\n        return 5\n    def c(self)')
        n_plain = self.c_of(plain, 'v5_plain').count('ail_class_is_or_subclass(')
        n_over = self.c_of(over, 'v5_over').count('ail_class_is_or_subclass(')
        self.assertGreater(n_over, n_plain)


if __name__ == '__main__':
    unittest.main()
