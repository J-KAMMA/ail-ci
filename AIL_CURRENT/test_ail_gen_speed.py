"""General-path speed (gen-speed): the size-class pool under the collector (on by default without threads; AIL_UNIFIED=0 and
AIL_UNIFIED_POOL=0 leave it out) and the immortal static boxes of float literals (AIL_FCONST).

Every program prints the same bytes with the pool, with AIL_UNIFIED_FORCE=1, with AIL_UNIFIED_POOL=0 and with AIL_UNIFIED=0,
and the same as CPython 3.12 where it is run: float reprs (-0.0, 5e-324, 1.7976931348623157e+308, 1e+16), the identity of a
literal repeated in a comprehension, containers and objects of every small size across many collections, floats made from
ints beyond int64 (read as text), and the exception texts of float arithmetic.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ON_312 = sys.version_info[:2] == (3, 12)

LITERALS = '''
import math

def lit():
    return [0.1, 1e16, 1e-7, 5e-324, 1.7976931348623157e308, -0.0, 2.5, 100.0, 1e22, 123456789.123456789, 0.30000000000000004]

def main():
    xs = lit()
    for x in xs:
        print(repr(x), x * 2.0, x + 0.1, -x, str(x), "%r %s %.3f" % (x, x, x))
    ys = [0.5 for _ in range(3)]
    print(ys, ys[0] is ys[1])
    z = -0.0
    print(z, repr(z), 0.0 == z, math.copysign(1.0, z), math.copysign(1.0, 0.0))
    t = (1.5, 0.5, 2.25)
    print(t, sum(t), max(t), min(t), sorted(t, reverse=True))
    d = {0.5: "a", 1.5: "b", 2.5: "c"}
    print(d[0.5], d.get(1.5), 2.5 in d, sorted(d))
    acc = 0.0
    for i in range(1000):
        acc += 0.1
    print(acc, acc == 100.0, round(acc, 6))

if __name__ == "__main__":
    main()
'''

ERRORS = '''
def f(a, b):
    return a / b

def g(a, b):
    return a * b + 0.5

def main():
    for a, b in ((1.0, 0.0), (1.0, 0), (1, 0.0), (0.0, 0.0), (5.5, 2.5)):
        try:
            print(f(a, b))
        except ZeroDivisionError as e:
            print("ZDE", e)
    for a, b in ((1.5, "x"), ("x", 2), (None, 1.5), ([1.5], 2.0), (2.0, [1]), (1.5, 2.5)):
        try:
            print(g(a, b))
        except TypeError as e:
            print("TE", e)
    try:
        print(10.0 ** 400)
    except OverflowError as e:
        print("OE", e)

if __name__ == "__main__":
    main()
'''

POOLED = '''
class P:
    def __init__(self, i):
        self.i = i
        self.f = i * 0.5
        self.name = "p%d" % i
        self.tags = [i, i + 1.5, str(i)]

def churn(n):
    keep = []
    d = {}
    for i in range(n):
        p = P(i)
        t = (i, i * 0.25, "s%d" % i, [i] * (i % 5))
        if i % 7 == 0:
            keep.append(p)
            d[i] = t
        if i % 11 == 0:
            keep.append(t)
        x = {i: [p.f, p.f * 2.0]}
        if i % 13 == 0:
            keep.append(x)
        s = set(range(i % 9))
        if i % 17 == 0:
            keep.append(s)
        u = "abc" * (i % 23)
        if i % 19 == 0:
            keep.append(u)
    return keep, d

def main():
    keep, d = churn(60000)
    print(len(keep), len(d))
    tot = 0.0
    cnt = 0
    for k in keep:
        if isinstance(k, P):
            tot += k.f + k.tags[1]
            cnt += 1
        elif isinstance(k, tuple):
            tot += k[1]
        elif isinstance(k, dict):
            for v in k.values():
                tot += v[0] + v[1]
        else:
            tot += len(k)
    print(cnt, tot)
    print(sorted(d)[:5], d[7][2], d[59997][1] if 59997 in d else None)
    big = [i * 0.5 for i in range(100000)]
    del big[::2]
    print(len(big), big[:3], big[-2:], sum(big))

if __name__ == "__main__":
    main()
'''

BIGINTS = '''
import sys

def main():
    xs = [int(t) for t in sys.stdin.read().split()]
    print(xs)
    for x in xs:
        print(x * 0.5, x + 0.25, float(x), x / 3, x / 2.5, -x * 1.5, abs(x) * 1.0)
    s = 0.0
    for x in xs:
        s += x * 0.1
    print(s)
    print(sum(xs) * 1.5, max(xs) / 7.0)
    ys = [x * 1.5 for x in xs]
    print(ys, sorted(ys))

if __name__ == "__main__":
    main()
'''
BIG_INPUT = ' '.join(['9223372036854775807', '-9223372036854775808', '9223372036854775808', '123456789012345678901234567890',
                      '-99999999999999999999', '4611686018427387904', '0', '7', '-1']) + '\n'

MODES = {'default': {}, 'force': {'AIL_UNIFIED_FORCE': '1'}, 'nopool': {'AIL_UNIFIED_POOL': '0'}, 'plain': {'AIL_UNIFIED': '0'}}


def _exact_int(test):
    """The test is about exact (arbitrary precision) ints: it runs in the opt-in mode (intmode.py, `--exact-int`)."""
    import functools
    import os

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        saved = os.environ.get('AIL_EXACT_INT')
        os.environ['AIL_EXACT_INT'] = '1'
        try:
            return test(*args, **kwargs)
        finally:
            if saved is None:
                os.environ.pop('AIL_EXACT_INT', None)
            else:
                os.environ['AIL_EXACT_INT'] = saved
    return wrapper


def build(directory, text, name, mode):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_' + mode)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for k in ('AIL_UNIFIED', 'AIL_UNIFIED_POOL', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL'):
        env.pop(k, None)
    env.update(MODES[mode])
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax', 'python',
                        '-o', exe.name, '--debug-dir', exe.name + '.d'], cwd=directory, capture_output=True, text=True,
                       timeout=900, env=env)
    return r, exe


class GenSpeed(unittest.TestCase):
    def check(self, name, text, stdin=''):
        with tempfile.TemporaryDirectory() as d:
            outs, cs = {}, {}
            for mode in MODES:
                r, exe = build(d, text, name, mode)
                self.assertEqual(r.returncode, 0, mode + '\n' + r.stdout + r.stderr)
                run = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True, timeout=300)
                outs[mode] = (run.returncode, run.stdout)
                cs[mode] = ''.join(p.read_text(encoding='utf-8', errors='replace')
                                   for p in sorted(Path(d, exe.name + '.d').glob('*.c')))
            for mode in MODES:
                self.assertEqual(outs[mode], outs['plain'], mode)
            if ON_312:
                src = Path(d, name + '.py')
                cp = subprocess.run([sys.executable, str(src)], input=stdin, capture_output=True, text=True, timeout=300)
                self.assertEqual(outs['default'], (cp.returncode, cp.stdout))
            self.assertIn('ail2u_pool', cs['default'])
            self.assertIn('ail2u_pool', cs['force'])
            self.assertNotIn('ail2u_pool', cs['nopool'])
            self.assertNotIn('ail2u_pool', cs['plain'])
            return cs

    def test_float_literals(self):
        cs = self.check('literals', LITERALS)
        self.assertIn('AIL_FCONST(', cs['default'])

    def test_float_error_texts(self):
        self.check('errors', ERRORS)

    def test_pooled_objects_across_collections(self):
        self.check('pooled', POOLED)

    @_exact_int

    def test_big_ints_into_floats(self):
        self.check('bigints', BIGINTS, BIG_INPUT)


if __name__ == '__main__':
    unittest.main()
