"""More programs reach the typed path by default (measure-float-refcount.md, 2026-10-30), against CPython 3.12.

Two proof gaps sent float programs to the general path (about 20 to 200 times more instructions, every float result boxed):

1. The int-overflow proof (bigcap.py) knew nothing about attributes and list items: `dx = b1.x - b2.x` of a dataclass with
   `x: float` looked like an unprovable int operation, and so did `round(acc.x, 6)`. The typed emitter has already typed the
   function when ir/driver.py asks, so the proof now takes the emitter's own float type for an attribute, an item or a call
   result (`bigcap._Defined.float_oracle`).
2. The counter of `for i in range(...)` was unbounded unless every argument was: `for i in range(n)` (n a parameter) made `i` an
   int the proof could not bound. A counter starts at a bounded start and moves by a constant step, so it is within 2**48
   steps of its start, the same physical limit the proof already uses for len(); `i + 1` is proven, `i * i` is still not.

T1  the forms that were refused now take the typed path (no "built on the general path" note, no float box in the C)
T2  output and exit code equal CPython for those programs
T3  boundaries: counters at and past the int64 edge (exact big results), empty range / empty list, aliasing, an exception
    inside the loop
T4  the proof itself: what the counter rule proves and what it leaves unproven
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

VEC = '''from dataclasses import dataclass

@dataclass
class Vec:
    x: float
    y: float
    z: float

def add(a: Vec, b: Vec) -> Vec:
    return Vec(a.x + b.x, a.y + b.y, a.z + b.z)

def scale(a: Vec, k: float) -> Vec:
    return Vec(a.x * k, a.y * k, a.z * k)

def dot(a: Vec, b: Vec) -> float:
    return a.x * b.x + a.y * b.y + a.z * b.z

def main():
    acc = Vec(0.0, 0.0, 0.0)
    v = Vec(0.5, 0.25, 0.125)
    d = 0.0
    for i in range(4000):
        w = scale(v, 1.0 / (i + 1))
        acc = add(acc, w)
        d += dot(acc, w)
    print(round(acc.x, 6), round(acc.y, 6), round(d, 6))

main()
'''

BODIES = '''from dataclasses import dataclass
from math import sqrt

@dataclass
class Body:
    x: float
    y: float
    m: float

def energy(bodies: list[Body]) -> float:
    e = 0.0
    nb = len(bodies)
    for i in range(nb):
        b = bodies[i]
        e += 0.5 * b.m * (b.x * b.x + b.y * b.y)
        for j in range(i + 1, nb):
            c = bodies[j]
            dx = b.x - c.x
            dy = b.y - c.y
            e -= b.m * c.m / sqrt(dx * dx + dy * dy)
    return e

def drift(bodies: list[Body], dt: float, n: int) -> None:
    for _ in range(n):
        for b in bodies:
            b.x += dt * b.m
            b.y -= dt * b.m

def main():
    bodies: list[Body] = []
    print(energy(bodies))
    bodies.append(Body(0.0, 0.0, 3.0))
    print(energy(bodies))
    bodies.append(Body(4.0, -1.0, 0.5))
    bodies.append(Body(8.0, 4.0, 0.25))
    print(round(energy(bodies), 9))
    drift(bodies, 0.01, 50)
    drift(bodies, 0.01, 0)
    print(round(energy(bodies), 9))

main()
'''

ALIAS = '''from dataclasses import dataclass

@dataclass
class P:
    x: float
    y: float

def bump(p: P, n: int) -> float:
    q = p
    for i in range(n):
        q.x += 0.5
        q.y = q.x * 2.0
    return p.x + p.y

def main():
    a = P(1.0, 2.0)
    b = a
    print(bump(a, 3), a.x, b.y)
    print(bump(a, 0), a.x)
    xs = [P(0.0, 1.0), P(2.0, 3.0)]
    ys = xs
    ys[0].x = 9.5
    print(xs[0].x, bump(xs[1], 2), xs[1].y)

main()
'''

RAISES = '''from dataclasses import dataclass

@dataclass
class R:
    a: float
    b: float

def ratios(rs: list[R], n: int) -> float:
    t = 0.0
    for i in range(n):
        r = rs[i]
        t += r.a / r.b
        print(i, t)
    return t

def main():
    rs = [R(1.0, 2.0), R(3.0, 4.0), R(5.0, 0.0), R(7.0, 8.0)]
    print(ratios(rs, 2))
    print(ratios(rs, 4))

main()
'''

# counters at the int64 edge: results past 2**63 must be exact (CPython ints), whichever path takes the program
EDGE = '''def walk(n: int) -> None:
    for i in range(4611686018427387900, n):
        print(i, i + i, i * 2, i * 4)

def walk2(a: int, n: int) -> int:
    t = 0
    for i in range(a, n):
        t += i * i
    return t

def count(n: int) -> int:
    c = 0
    for i in range(n):
        c += i + 1
    return c

def main():
    walk(4611686018427387904)
    walk(4611686018427387900)
    print(walk2(3037000498, 3037000503))
    print(walk2(0, 0), walk2(5, 3))
    print(count(0), count(-4), count(5))
    for k in range(9223372036854775805, 9223372036854775810):
        print(k, k + 1, k + 4)

main()
'''

FLOATLIST = '''def spread(xs: list[float], n: int) -> float:
    s = 0.0
    for i in range(n):
        d = xs[i] - xs[0]
        s += d * d
    return s

def main():
    print(spread([1.5, 2.5, 4.0], 3))
    print(spread([2.0], 0))
    print(spread([0.1, 0.2, 0.3, 0.4], 4))

main()
'''


def compile_default(directory, text, name):
    """Compile with the default pipeline; returns (result, exe, generated C text)."""
    source, exe, dbg = Path(directory, name + '.py'), Path(directory, name + '_x'), Path(directory, name + '_dbg')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '-o', exe.name,
                          '--debug-dir', str(dbg)], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    c_file = dbg / 'program.c'
    return res, exe, (c_file.read_text(encoding='utf-8', errors='replace') if c_file.exists() else '')


def run_cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=300, encoding='utf-8')


def typed(res):
    return 'built on the general path' not in res.stderr


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class TypedReach(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='typedreach1_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build_and_compare(self, text, name):
        res, exe, c_text = compile_default(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        want = run_cpython(self.tmp, text, name)
        got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, encoding='utf-8')
        self.assertEqual(got.stdout, want.stdout, name)
        self.assertEqual(got.returncode, want.returncode, name)
        if want.returncode != 0:
            self.assertTrue(got.stderr.strip(), name)      # the message goes to stderr (its wording is not compared)
        return res, c_text, want

    def assert_typed(self, text, name):
        res, c_text, _ = self.build_and_compare(text, name)
        self.assertTrue(typed(res), 'fell back to the general path: ' + res.stderr[-600:])
        # a typed build holds floats in C doubles: no call that boxes one
        self.assertEqual(len(re.findall(r'\bail_box_float\(', c_text)), 0, name)

    # T1 + T2
    def test_dataclass_float_fields_typed(self):
        self.assert_typed(VEC, 'vec')

    def test_attribute_differences_and_empty_list_typed(self):
        self.assert_typed(BODIES, 'bodies')

    def test_float_list_items_with_param_range_typed(self):
        self.assert_typed(FLOATLIST, 'floatlist')

    # T3
    def test_aliasing(self):
        self.build_and_compare(ALIAS, 'alias')

    def test_exception_inside_loop(self):
        _, _, want = self.build_and_compare(RAISES, 'raises')
        self.assertNotEqual(want.returncode, 0)       # CPython raises ZeroDivisionError at i == 2; so must the build

    def test_counters_at_and_past_int64_edge_stay_exact(self):
        # i * 4 for i near 2**62 and k + 4 for k near 2**63 pass int64: they must print exactly as CPython does
        _, _, want = self.build_and_compare(EDGE, 'edge')
        self.assertIn('18446744073709551612', want.stdout)


class ProofUnit(unittest.TestCase):
    """T4: the proof itself (no C compiler)."""

    @staticmethod
    def reason(src):
        import ast
        sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
        import bigcap
        fn = ast.parse(src).body[0]
        return bigcap._lp_reason([fn], None, bigcap._Defined({fn.name}))

    def test_counter_of_unbounded_stop_is_int64(self):
        self.assertIsNone(self.reason('def f(n):\n    for i in range(n):\n        print(i + 1)\n'))
        self.assertIsNone(self.reason('def f(n: int):\n    for i in range(3, n):\n        print(i - 5)\n'))

    def test_arithmetic_on_the_counter_is_still_checked(self):
        self.assertIsNotNone(self.reason('def f(n):\n    for i in range(n):\n        print(i * i)\n'))
        self.assertIsNotNone(self.reason('def f(n):\n    for i in range(n):\n        print(i << 20)\n'))

    def test_unbounded_start_or_step_stays_unproven(self):
        self.assertIsNotNone(self.reason('def f(a, n):\n    for i in range(a, n):\n        print(i)\n'))
        self.assertIsNotNone(self.reason('def f(n, s):\n    for i in range(0, n, s):\n        print(i)\n'))

    def test_a_float_oracle_is_needed_for_attributes(self):
        import ast
        sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
        import bigcap
        fn = ast.parse('def f(a, b):\n    d = a.x - b.x\n    return d * d\n').body[0]
        defined = bigcap._Defined({'f'})
        self.assertIsNotNone(bigcap._lp_reason([fn], None, defined))
        defined.float_oracle = lambda node: isinstance(node, ast.Attribute) and node.attr == 'x'
        self.assertIsNone(bigcap._lp_reason([fn], None, defined))


if __name__ == '__main__':
    unittest.main()
