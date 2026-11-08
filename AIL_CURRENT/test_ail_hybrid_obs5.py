"""obs5 (`ail build --cpython`): more bodies go native, each compared with CPython byte for byte.

Division: `/`, `//` and `%` by a variable are native when the exact-kind pass proves both operands
are int/bool/float (a str `%` formats and stays in CPython).  The typed clone computes CPython's
floor division and modulo for ints and floats and a correctly rounded int `/`; a zero divisor or an
int64 overflow (`INT64_MIN // -1`) abandons the native call and CPython re-runs it, so the exact
ZeroDivisionError (message included) or the big int is what the caller sees.
"""
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
HAVE_HEADERS = (Path(sysconfig.get_paths().get('include', '/nonexistent')) / 'Python.h').is_file()
VECTORCALL = sys.version_info >= (3, 12)

DIVIDE = '''
def probe(table: list[int], keys: list[int], bits: int) -> int:
    hits = 0
    for k in keys:
        a = k % bits
        b = (k // 7 + 13) % bits
        if table[a] == 1 and table[b] == 1:
            hits += 1
    return hits


def mean(xs: list[float]) -> float:
    acc = 0.0
    for x in xs:
        acc += x
    return acc / len(xs)


def variance(xs: list[float]) -> float:
    m = mean(xs)
    acc = 0.0
    for x in xs:
        d = x - m
        acc += d * d
    return acc / len(xs)


def true_div(a: int, b: int) -> float:
    s = 0
    i = 0
    while i < 1:
        s += a
        i += 1
    return s / b


def floor_int(a: int, b: int) -> int:
    q = 0
    i = 0
    while i < 1:
        q += a // b
        i += 1
    return q


def mod_int(a: int, b: int) -> int:
    r = 0
    i = 0
    while i < 1:
        r += a % b
        i += 1
    return r


def floor_float(a: float, b: float) -> float:
    s = 0.0
    i = 0
    while i < 1:
        s += a // b
        i += 1
    return s


def mod_float(a: float, b: float) -> float:
    s = 0.0
    i = 0
    while i < 1:
        s += a % b
        i += 1
    return s


def mixed(a: int, b: float) -> float:
    return a / b + a // b + a % b


def aug(a: int, b: int) -> int:
    x = a
    x %= b
    x //= 1 + b
    return x


def scaled_total(vals: list[int], num: int, den: int) -> int:
    acc = 0
    for v in vals:
        acc += v * num // den
    return acc


def calls_div(a: int, b: int) -> int:
    t = 0
    i = 0
    while i < 3:
        t += floor_int(a + i, b)
        i += 1
    return t


def guarded(a: int, b: int) -> int:
    try:
        return floor_int(a, b)
    except ZeroDivisionError:
        return -1


def fmt(n: int) -> str:
    s = "%d"
    return s % n


def power(a: float, b: float) -> float:
    return a ** b


class Ratio:
    def __init__(self, num: int, den: int):
        self.num = num
        self.den = den

    def floor(self) -> int:
        t = 0
        i = 0
        while i < 2:
            t += self.num // self.den
            i += 1
        return t
'''

DIVIDE_RUNNER = r'''
import divide as m


def show(label, f, *args):
    try:
        r = f(*args)
        print(label, type(r).__name__, repr(r))
    except Exception as e:
        print(label, 'raised', type(e).__name__, str(e))


big = 2 ** 62 + 1
imin = -2 ** 63
show('probe', m.probe, [1, 0, 1, 1, 0, 1, 1], list(range(-50, 400, 3)), 7)
show('probe_neg', m.probe, [1, 0, 1, 1, 0, 1, 1], list(range(-50, 400, 3)), -7)
show('probe_zero', m.probe, [1, 0, 1], [1, 2, 3], 0)
show('probe_big', m.probe, [1, 0, 1], [1, 2, 3], 2 ** 64)
show('mean', m.mean, [1.5, 2.25, -3.0])
show('mean_empty', m.mean, [])
show('variance', m.variance, [1.5, 2.25, -3.0, 7.0])
show('variance_empty', m.variance, [])
for a, b in [(7, 2), (-7, 2), (7, -2), (-7, -2), (big, 3), (2 ** 53 + 1, 1), (big, big - 2),
             (imin, -1), (imin, 1), (1, 0), (0, 5), (True, True), (1, False), (10 ** 20, 3)]:
    show('true_div %r %r' % (a, b), m.true_div, a, b)
    show('floor_int %r %r' % (a, b), m.floor_int, a, b)
    show('mod_int %r %r' % (a, b), m.mod_int, a, b)
    show('aug %r %r' % (a, b), m.aug, a, b)
    show('calls_div %r %r' % (a, b), m.calls_div, a, b)
inf = float('inf')
nan = float('nan')
for a, b in [(7.5, 2.0), (-7.5, 2.0), (7.5, -2.0), (-0.0, 3.0), (0.0, -3.0), (1e308, 1e-308),
             (inf, 2.0), (2.0, inf), (-2.0, inf), (nan, 1.0), (1.0, 0.0), (-1.0, -0.0),
             (5e-324, 3.0), (0.1, 0.01)]:
    show('floor_float %r %r' % (a, b), m.floor_float, a, b)
    show('mod_float %r %r' % (a, b), m.mod_float, a, b)
for a, b in [(7, 2.0), (-7, 0.5), (big, 3.0), (1, 0.0), (3, -0.0)]:
    show('mixed %r %r' % (a, b), m.mixed, a, b)
show('scaled', m.scaled_total, list(range(-20, 30)), 3, 7)
show('scaled_neg', m.scaled_total, list(range(-20, 30)), 3, -7)
show('scaled_zero', m.scaled_total, list(range(-20, 30)), 3, 0)
show('scaled_ovf', m.scaled_total, [2 ** 62], 4, 3)
show('guarded', m.guarded, 5, 2)
show('guarded_zero', m.guarded, 5, 0)
show('fmt', m.fmt, 5)
show('power', m.power, -8.0, 1.0 / 3.0)
r = m.Ratio(17, 5)
show('ratio', r.floor)
r.den = 0
show('ratio_zero', r.floor)
r.den = -4
show('ratio_neg', r.floor)
r.num = imin
r.den = -1
show('ratio_ovf', r.floor)
for _ in range(2000):
    m.floor_int(9, 4)
    m.mod_float(9.0, 4.0)
print('loops-ok')
'''

DIVIDE_NATIVE = ('probe', 'mean', 'variance', 'true_div', 'floor_int', 'mod_int', 'floor_float',
                 'mod_float', 'mixed', 'aug', 'scaled_total', 'calls_div', 'Ratio.floor')
DIVIDE_REFUSED = ('fmt', 'power', 'guarded')


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=600)


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class Runs(unittest.TestCase):

    def build(self, tmp, name, text):
        src = Path(tmp) / (name + '.py')
        src.write_text(text, encoding='utf-8')
        out = Path(tmp) / 'out'
        built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)],
                    tmp, env=dict(os.environ, AIL_NO_CACHE='1'))
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        return out, json.loads((out / 'build.json').read_text(encoding='utf-8'))

    def compare(self, tmp, out, runner_text, native, refused, report, module):
        for name in native:
            self.assertIn(name, report['accelerated'], report['rejected'].get(name))
        for name in refused:
            self.assertNotIn(name, report['accelerated'])
        runner = Path(tmp) / 'runner.py'
        runner.write_text(runner_text, encoding='utf-8')
        want = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=tmp))
        got = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=str(out)))
        self.assertEqual(want.returncode, 0, want.stderr[-2000:])
        self.assertEqual(got.stdout.decode(), want.stdout.decode(), got.stderr[-2000:])
        self.assertEqual(got.returncode, want.returncode)
        self.assertIn(b'loops-ok', got.stdout)
        if VECTORCALL:
            probe = ('import %s as m\nnat = m._ail_hybrid_native\n'
                     'def get(n):\n'
                     '    o = m\n'
                     '    for p in n.split("."):\n'
                     '        o = getattr(o, p)\n'
                     '    return o\n'
                     'print([nat._ail_is_native(get(n)) for n in %r])\n' % (module, native))
            got = run([sys.executable, '-B', '-c', probe], str(out),
                      env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(got.stdout.strip(), repr([True] * len(native)).encode(),
                             got.stderr[-2000:])

    def test_division_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-obs5-div-') as tmp:
            out, report = self.build(tmp, 'divide', DIVIDE)
            self.compare(tmp, out, DIVIDE_RUNNER, DIVIDE_NATIVE, DIVIDE_REFUSED, report, 'divide')


if __name__ == '__main__':
    unittest.main()
