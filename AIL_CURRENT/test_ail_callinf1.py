"""Single-kind call-site inference of unannotated parameters (job callinf1), against CPython.

An unannotated parameter that every call site hands the same kind takes that kind: a flat
list[float] or list[str], one class instance or a list of one class (functions and methods, read
through the caller's typed context), and str / float / class / list[float] / list[str] for a
constructor parameter whose every call spells its argument's kind in the source. Call sites that
disagree (int and float, bool and int, a value and None) keep the old rule: the program falls back
to the general path and still prints what CPython prints.

T1  fixed programs on the typed path alone (AIL_NO_GENERAL=1) print what CPython prints
T2  the same programs with AIL_UNIFIED_FORCE=1 print what CPython prints
T3  disagreeing call sites are not unified: the typed path alone refuses them, and the default
    build and AIL_UNIFIED_FORCE=1 both print what CPython prints
T4  an int beyond int64 through an inferred parameter stops loudly (OverflowError, non-zero exit)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None


def build(directory, text, name, typed_only=True, force=False):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_t')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if typed_only:
        env['AIL_NO_GENERAL'] = '1'
    if force:
        env['AIL_UNIFIED_FORCE'] = '1'
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax',
                          'python', '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900,
                         env=env)
    return res, exe


def run_cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=300,
                          encoding='utf-8')


def run_exe(exe):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, encoding='utf-8')


FIXED = {}

FIXED['ctor_str'] = '''class Tok:
    def __init__(self, kind, n):
        self.kind = kind
        self.n = n


def main():
    toks = [Tok("W", 1), Tok("X", 2)]
    t = Tok(f"Y{3}", 3)
    toks.append(t)
    for x in toks:
        print(x.kind, x.n)


main()
'''

FIXED['flist_param'] = '''def total(xs, n):
    s = 0.0
    i = 0
    while i < n:
        s += xs[i]
        i += 1
    return s


def scale(xs, k):
    out = []
    for x in xs:
        out.append(x * k)
    return out


def main():
    a = [1.5, 2.25, 3.0]
    b = [0.5] * 4
    print(total(a, 3))
    print(total(b, 4))
    print(scale(a, 2.0))


main()
'''

FIXED['forwarded_lists'] = '''def dot(a, b, n):
    s = 0.0
    i = 0
    while i < n:
        s += a[i] * b[i]
        i += 1
    return s


def norm2(v, n):
    return dot(v, v, n)


def both(u, v, n):
    return norm2(u, n) + norm2(v, n)


def join(parts):
    out = ""
    for p in parts:
        out = out + p
    return out


def relay(parts):
    return join(parts)


def main():
    u = [1.0] * 4
    v = [0.5, 1.5, 2.5, 3.5]
    print(both(u, v, 4))
    print(relay(["a", "b"]))


main()
'''

FIXED['classes'] = '''class V:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def plus(self, o):
        return V(self.x + o.x, self.y + o.y)

    def scaled(self, k):
        return V(self.x * k, self.y * k)


class Ball:
    def __init__(self, centre, radius, tags, name):
        self.centre = centre
        self.radius = radius
        self.tags = tags
        self.name = name


def far(balls, d):
    n = 0
    for b in balls:
        if b.centre.x > d:
            n += 1
    return n


def main():
    b = Ball(V(1.0, 2.0), 0.5, ["a", "b"], f"b{1}")
    c = Ball(V(-1.0, 0.25), 1.5, ["c"], "c")
    w = b.centre.plus(c.centre).scaled(2.0)
    print(w.x, w.y, b.radius + c.radius, len(b.tags), c.tags[0], b.name, c.name)
    bs = [b, c]
    print(far(bs, 0.0))


main()
'''

# Disagreeing call sites: never unified. Each still matches CPython through the default pipeline.
MIXED = {}

MIXED['int_and_float'] = '''def twice(x):
    return x + x


def total(xs):
    s = 0
    for v in xs:
        s += v
    return s


def main():
    print(twice(3), twice(1.25))
    print(total([1, 2, 3]))
    print(total([1.5, 2.5]))


main()
'''

MIXED['bool_and_int'] = '''def show(x):
    print(x)


class Box:
    def __init__(self, v):
        self.v = v


def main():
    show(True)
    show(1)
    a = Box(True)
    b = Box(2)
    print(a.v, b.v)


main()
'''

MIXED['none_at_one_site'] = '''def total(xs):
    if xs is None:
        return 0.0
    s = 0.0
    for v in xs:
        s += v
    return s


class Tag:
    def __init__(self, name):
        self.name = name


def main():
    print(total([1.5, 2.0]))
    print(total(None))
    a = Tag("x")
    b = Tag(None)
    print(a.name, b.name)


main()
'''

MIXED['ctor_int_and_float'] = '''class Q:
    def __init__(self, a):
        self.a = a


def main():
    q1 = Q(1)
    q2 = Q(1.5)
    print(q1.a, q2.a)


main()
'''

MIXED['list_kinds'] = '''def first(xs):
    return xs[0]


def count(xs):
    n = 0
    for v in xs:
        n += 1
    return n


def main():
    print(first([1.5, 2.5]))
    print(first([1, 2]))
    print(count([0.5, 0.25]))
    print(count(["a", "b", "c"]))


main()
'''

MIXED['first_class'] = '''def total(xs):
    s = 0.0
    for v in xs:
        s += v
    return s


def apply(f, xs):
    return f(xs)


class W:
    def __init__(self, s):
        self.s = s


def make(k, v):
    return k(v)


def main():
    a = [1.5, 2.25]
    print(total(a))
    print(apply(total, a))
    print(W("x").s, make(W, 3).s)


main()
'''

BIG = '''import sys


def grow(x, k):
    return x * k


class Acc:
    def __init__(self, v):
        self.v = v


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 9223372036854775807
    print(grow(3, 4))
    a = Acc(n)
    print(a.v)
    print(grow(n, 2))


main()
'''


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class CallSiteInference(unittest.TestCase):
    def test_t1_typed_alone(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in FIXED.items():
                with self.subTest(name=name):
                    expected = run_cpython(d, text, name)
                    res, exe = build(d, text, name)
                    self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                    got = run_exe(exe)
                    self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout))

    def test_t2_unified_force(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in FIXED.items():
                with self.subTest(name=name):
                    expected = run_cpython(d, text, name)
                    res, exe = build(d, text, name + '_f', typed_only=False, force=True)
                    self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                    got = run_exe(exe)
                    self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout))

    def test_t3_disagreeing_sites_not_unified(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in MIXED.items():
                with self.subTest(name=name):
                    res, _ = build(d, text, name)
                    self.assertNotEqual(res.returncode, 0, 'typed path accepted disagreeing call sites')
                    expected = run_cpython(d, text, name)
                    for force in (False, True):
                        res, exe = build(d, text, name + ('_f' if force else '_d'), typed_only=False, force=force)
                        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                        got = run_exe(exe)
                        self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout))

    def test_t4_beyond_int64_stops(self):
        with tempfile.TemporaryDirectory() as d:
            for force in (False, True):
                with self.subTest(force=force):
                    res, exe = build(d, BIG, 'big%d' % force, typed_only=False, force=force)
                    self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                    got = run_exe(exe)
                    self.assertNotEqual(got.returncode, 0)
                    self.assertIn('OverflowError', got.stderr)
                    self.assertEqual(got.stdout, '12\n9223372036854775807\n')


if __name__ == '__main__':
    unittest.main()
