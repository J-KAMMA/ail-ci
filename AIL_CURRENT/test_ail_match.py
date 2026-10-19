"""The match statement (python/pkg-v12/matchlower.py, and the typed path's static isinstance), against CPython 3.12.

M1  fixed programs over int, str, list, tuple, dict and user classes (`__match_args__`, a dataclass): literal,
    capture, wildcard, or, as, sequence (with a star), mapping, class (keyword and positional, the
    self-matching builtins) patterns and guards. The typed path alone (AIL_NO_GENERAL=1, AIL_IR=0 and 1)
    prints what CPython prints, and so does the general path.
M2  shapes only the general path takes (a tuple whose length is known at run time, None/True patterns,
    an or-pattern that binds, a nested pattern, `**rest`): the default build prints what CPython prints.
M3  random match statements over int and list[int] subjects (`gen_program`): CPython == typed path
    (IR 0 and 1) == general path.
M4  the lowering leaves a program without `match` as written, and a shape it does not take (a class
    pattern of a class the program does not define) as a `match`, which the compiler refuses by name.
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from test_ail_nested_functions import build, build_general, run_cpython, run_exe   # noqa: E402

HAVE_CC = shutil.which('gcc') is not None
SEEDS = int(os.environ.get('AIL_MATCH_SEEDS', '10'))

SCALARS = '''def classify(n: int) -> str:
    match n:
        case 0:
            return "zero"
        case 1 | 2 | 3:
            return "small"
        case x if x < 0:
            return "neg %d" % x
        case x if x % 2 == 0:
            return "even"
        case _:
            return "odd"


def point(p: tuple[int, int]) -> str:
    match p:
        case (0, 0):
            return "origin"
        case (0, y):
            return "y=%d" % y
        case (x, 0):
            return "x=%d" % x
        case (x, y) if x == y:
            return "diag %d" % x
        case (x, y):
            return "%d,%d" % (x, y)


def word(s: str) -> int:
    match s:
        case "a" | "an" | "the":
            return 0
        case "":
            return -1
        case other:
            return len(other)


def main() -> None:
    for n in [0, 2, -5, 8, 9, 3]:
        print(n, classify(n))
    stack: list[int] = []
    for line in ["push 4", "push 7", "pop", "add 2 3", "sum 1 2 3", "x y x", "", "pop", "pop", "zz"]:
        words = line.split()
        match words:
            case ["push", n]:
                stack.append(int(n))
                print("pushed")
            case ["pop"]:
                print(str(stack.pop()) if stack else "empty")
            case ["add", a, b]:
                print(int(a) + int(b))
            case ["sum", *rest]:
                total = 0
                for r in rest:
                    total += int(r)
                print("sum %d of %d" % (total, len(rest)))
            case [first, *_, last] if first == last:
                print("same ends " + first)
            case []:
                print("nothing")
            case _:
                print("unknown " + words[0])
    for x0 in range(5):
        print(point((x0 % 3 - 1, (x0 * 7) % 3 - 1)))
    for s in ["the", "", "match"]:
        print(word(s))


main()
'''

OBJECTS = '''from dataclasses import dataclass


class Point:
    __match_args__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


@dataclass
class Circle:
    r: int
    name: str


def where(p: Point) -> str:
    match p:
        case Point(0, 0):
            return "origin"
        case Point(x=0, y=yy):
            return "on y at %d" % yy
        case Point(xx, 0):
            return "on x at %d" % xx
        case Point(x=a, y=b) if a == b:
            return "diagonal"
        case _:
            return "elsewhere"


def size(c: Circle) -> str:
    match c:
        case Circle(0, n):
            return n + " is a dot"
        case Circle(r, "unit") if r == 1:
            return "unit circle"
        case Circle(r=r):
            return "radius %d" % r


def lookup(d: dict[str, int]) -> str:
    match d:
        case {"x": 0, "y": 0}:
            return "zero point"
        case {"x": x, "y": y}:
            return "point %d %d" % (x, y)
        case {"r": r}:
            return "radius %d" % r
        case {}:
            return "something else %d" % len(d)


def kind(v: int) -> str:
    match v:
        case int(n) if n > 100:
            return "big int"
        case int():
            return "int"


def main() -> None:
    xs = [0, 0, 3, 2, 1]
    ys = [0, 4, 0, 2, 5]
    for i in range(len(xs)):
        print(where(Point(xs[i], ys[i])))
    print(size(Circle(0, "c0")), size(Circle(1, "unit")), size(Circle(4, "big")))
    d1: dict[str, int] = {"x": 0, "y": 0}
    d2: dict[str, int] = {"x": 1, "y": 2}
    d3: dict[str, int] = {"r": 3}
    d4: dict[str, int] = {"q": 1, "w": 2}
    print(lookup(d1), lookup(d2), lookup(d3), lookup(d4))
    print(kind(5), kind(500))


main()
'''

GENERAL = '''import sys


def run(lines):
    stack = []
    for line in lines:
        cmd = tuple(line.split())
        match cmd:
            case ("push", n):
                stack.append(int(n))
            case ("pop",):
                print(stack.pop() if stack else "empty")
            case ("dup",) if stack:
                stack.append(stack[-1])
            case ("swap",) | ("exch",):
                stack[-1], stack[-2] = stack[-2], stack[-1]
            case (("add" | "mul") as op, *args) if args:
                acc = 0 if op == "add" else 1
                for a in args:
                    acc = acc + int(a) if op == "add" else acc * int(a)
                stack.append(acc)
            case _:
                print("?", cmd)
    print(stack)


def describe(v):
    match v:
        case None:
            return "none"
        case True:
            return "true"
        case False:
            return "false"
        case int(n) | float(n) if n < 0:
            return "negative"
        case [x, [y, z]]:
            return "nested %s %s %s" % (x, y, z)
        case {"k": [a, *more], **rest}:
            return "k %s %d %s" % (a, len(more), sorted(rest))
        case (1, x) | (x, 1):
            return "has one %s" % x
        case str() as s:
            return "str " + s
        case _:
            return "other %r" % (v,)


def main() -> None:
    run(["push 3", "push 4", "dup", "swap", "pop", "add 1 2 3", "mul 2 5", "add", "noop x", "pop", "exch"])
    for v in [None, True, False, -3, -2.5, 7, [1, [2, 3]], {"k": [1, 2, 3], "z": 0, "a": 1}, (1, 9), (8, 1), "hi", [1]]:
        print(describe(v))


main()
'''


# one function given a dict, a range, a list, a tuple and a str; a Counter is a mapping
POLY = 'from collections import Counter\n\n\ndef kind(v):\n    match v:\n        case {"a": n}:\n            return "map a=%s" % n\n        case [x, y, z]:\n            return "seq3 %s" % (x + y + z)\n        case [*_]:\n            return "seq"\n        case _:\n            return "other"\n\n\ndef counts(c: Counter[str]) -> str:\n    match c:\n        case {"a": n}:\n            return "a=%d" % n\n        case _:\n            return "none"\n\n\ndef main():\n    print(kind({"a": 1}), kind({}))\n    print(kind(range(3)), kind([1, 2, 3]), kind((4, 5, 6)), kind("abc"))\n    print(counts(Counter("aab")), counts(Counter("bb")))\n\n\nmain()\n'

# a tuple passed to a function that also receives other kinds stays a tuple (the tuple pass refuses to
# turn it into a class there, where `isinstance(v, tuple)` and `len(v)` would not see a tuple)
TUPLE_ARG = 'def f(v):\n    if isinstance(v, tuple):\n        return "t%d" % len(v)\n    return "o"\n\n\ndef main():\n    print(f((1, 2)), f([1]), f("x"))\n\n\nmain()\n'


# a class pattern on an attribute some or all instances lack does not match (CPython), it does not raise
MISSING_SUB = 'class Shape:\n    def __init__(self, name: str) -> None:\n        self.name = name\n\n\nclass Circle(Shape):\n    def __init__(self, r: int) -> None:\n        super().__init__("circle")\n        self.r = r\n\n\nclass Square(Shape):\n    def __init__(self, side: int) -> None:\n        super().__init__("square")\n        self.side = side\n\n\ndef describe(s: Shape) -> str:\n    match s:\n        case Square(z=0):\n            return "never"\n        case Shape(r=r) if r > 5:\n            return "big round %d" % r\n        case Shape(side=side):\n            return "side %d" % side\n        case Shape(name=n):\n            return "shape " + n\n\n\ndef main() -> None:\n    print(describe(Circle(9)), describe(Circle(2)), describe(Square(3)), describe(Shape("blob")))\n\n\nmain()\n'
MISSING = 'class Point:\n    def __init__(self, x: int, y: int) -> None:\n        self.x = x\n        self.y = y\n\n\ndef f(p: Point) -> str:\n    match p:\n        case Point(z=0):\n            return "z"\n        case Point(x=0, w=1): return "w"\n        case Point(x=x):\n            return "x %d" % x\n\n\ndef main() -> None:\n    print(f(Point(0, 1)), f(Point(4, 1)))\n\n\nmain()\n'


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Fixed(unittest.TestCase):
    def test_typed_and_general_paths_print_what_cpython_prints(self):
        with tempfile.TemporaryDirectory(prefix='ail-match-') as tmp:
            for name, text in (('scalars', SCALARS), ('objects', OBJECTS)):
                with self.subTest(name=name):
                    want = run_cpython(tmp, text, name)
                    self.assertEqual(want.returncode, 0, want.stderr)
                    for ir in ('0', '1'):
                        res, exe = build(tmp, text, name, ir=ir)
                        self.assertEqual(res.returncode, 0, '%s IR=%s: %s' % (name, ir, res.stderr[-2000:]))
                        got = run_exe(exe)
                        self.assertEqual((got.returncode, got.stdout), (0, want.stdout), '%s IR=%s' % (name, ir))
                    res, exe = build_general(tmp, text, name)
                    self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                    got = run_exe(exe)
                    self.assertEqual((got.returncode, got.stdout), (0, want.stdout), name + ' general')

    def test_shapes_for_the_general_path(self):
        with tempfile.TemporaryDirectory(prefix='ail-match-') as tmp:
            ranges = ('def main():\n    r = range(3)\n    print(r, range(1, 9, 2), [range(2)], len(r), r[-1], '
                      'range(10, 0, -3)[1])\n\n\nmain()\n')
            for name, text in (('general', GENERAL), ('poly', POLY), ('tuplearg', TUPLE_ARG), ('ranges', ranges),
                               ('missing_sub', MISSING_SUB), ('missing', MISSING)):
                want = run_cpython(tmp, text, name)
                self.assertEqual(want.returncode, 0, want.stderr)
                for ir in ('0', '1'):
                    res, exe = build(tmp, text, name, ir=ir, typed_only=False)
                    self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                    got = run_exe(exe)
                    self.assertEqual((got.returncode, got.stdout), (0, want.stdout), '%s IR=%s' % (name, ir))


def gen_program(seed):
    rng = random.Random(seed)
    out = ['def f(n: int) -> str:', '    match n:']
    used_irrefutable = False
    for _ in range(rng.randint(2, 6)):
        r = rng.random()
        if r < 0.3:
            out.append('        case %d:' % rng.randint(-3, 6))
            out.append('            return "lit"')
        elif r < 0.5:
            vals = sorted({rng.randint(-3, 9) for _ in range(rng.randint(2, 4))})
            out.append('        case %s:' % ' | '.join(map(str, vals)))
            out.append('            return "or"')
        elif r < 0.8:
            out.append('        case x if x %% %d == %d:' % (rng.randint(2, 5), rng.randint(0, 1)))
            out.append('            return "guard %d" % (x * 2)')
        else:
            out.append('        case int(v) if v > %d:' % rng.randint(0, 6))
            out.append('            return "big %d" % v')
    out.append('        case _:')
    out.append('            return "rest"')
    out += ['', '', 'def g(xs: list[int]) -> str:', '    match xs:']
    for _ in range(rng.randint(3, 7)):
        r = rng.random()
        if r < 0.15:
            out.append('        case []:')
            out.append('            return "empty"')
        elif r < 0.3:
            out.append('        case [a]:')
            out.append('            return "one %d" % a')
        elif r < 0.45:
            out.append('        case [%d, b]:' % rng.randint(0, 3))
            out.append('            return "pair %d" % b')
        elif r < 0.6:
            out.append('        case [a, b, *rest] if a < b:')
            out.append('            return "up %d %d %d" % (a, b, len(rest))')
        elif r < 0.75:
            out.append('        case [*init, last] if last %% 2 == %d:' % rng.randint(0, 1))
            out.append('            return "last %d %d" % (last, len(init))')
        elif r < 0.9:
            out.append('        case [%d | %d, *_]:' % (rng.randint(0, 2), rng.randint(3, 5)))
            out.append('            return "head"')
        else:
            out.append('        case [a, b, c]:')
            out.append('            return "three %d" % (a + b + c)')
    out.append('        case _:')
    out.append('            return "other %d" % len(xs)')
    out += ['', '', 'def main() -> None:', '    for n in range(-4, 12):', '        print(n, f(n))']
    for _ in range(12):
        xs = [rng.randint(0, 5) for _ in range(rng.randint(0, 5))]
        out.append('    print(g(%r))' % xs)
    out += ['', '', 'main()', '']
    return '\n'.join(out)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Random(unittest.TestCase):
    def test_random_match_statements(self):
        with tempfile.TemporaryDirectory(prefix='ail-match-rand-') as tmp:
            for seed in range(SEEDS):
                text = gen_program(seed)
                name = 'm%d' % seed
                with self.subTest(seed=seed):
                    want = run_cpython(tmp, text, name)
                    self.assertEqual(want.returncode, 0, want.stderr + text)
                    for ir in ('0', '1'):
                        res, exe = build(tmp, text, name, ir=ir)
                        self.assertEqual(res.returncode, 0, 'seed %d IR=%s: %s\n%s' % (seed, ir, res.stderr[-1500:], text))
                        got = run_exe(exe)
                        self.assertEqual(got.stdout, want.stdout, 'seed %d IR=%s\n%s' % (seed, ir, text))
                    res, exe = build_general(tmp, text, name)
                    self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                    got = run_exe(exe)
                    self.assertEqual(got.stdout, want.stdout, 'seed %d general\n%s' % (seed, text))


class Lowering(unittest.TestCase):
    def test_left_as_written(self):
        import ail_syntax
        m = ail_syntax._matchlower()
        plain = 'def main() -> None:\n    match = 3\n    print(match)\n\n\nmain()\n'
        self.assertEqual(m.rewrite(plain), plain)
        foreign = ('from fractions import Fraction\n\n\ndef f(v):\n    match v:\n        case Fraction(1, 2):\n'
                   '            return 1\n    return 0\n')
        self.assertEqual(m.rewrite(foreign), foreign)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_an_unlowered_match_is_refused_by_name(self):
        text = ('class P:\n    def __init__(self, x: int) -> None:\n        self.x = x\n\n\n'
                'def f(p: P) -> int:\n    match p:\n        case P(1):\n            return 1\n    return 0\n\n\n'
                'def main() -> None:\n    print(f(P(1)))\n\n\nmain()\n')
        with tempfile.TemporaryDirectory(prefix='ail-match-') as tmp:
            res, _ = build(tmp, text, 'nomatchargs')
            self.assertEqual(res.returncode, 3, res.stderr)
            self.assertIn('match', res.stderr)


if __name__ == '__main__':
    unittest.main()
