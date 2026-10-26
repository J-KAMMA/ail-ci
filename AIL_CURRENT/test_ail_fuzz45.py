"""fuzz45: float floor division and modulo follow CPython's float_divmod.

The general path computed `a // b` as C `floor(a / b)` and `a % b` from a bare
`fmod` with only a sign correction.  That disagrees with CPython near a rounded
division and for infinities: `1.0 // 0.1` printed 10.0 (CPython 9.0),
`-0.0 % 2.0` printed -0.0 (CPython 0.0), `-5.0 // inf` printed -0.0 (CPython
-1.0) and `inf // 2.0` printed inf (CPython nan).  Both general emitters now use
one CPython float_divmod helper for `//`, `%` and so `divmod` stays consistent.

The programs also keep the cases that already worked: negative ints, mixed
int/float operands, a value reaching the operation through an argument, a list
item, an attribute and a dict value, and a wide sweep of zeros, infinities and
NaNs.  Each program is built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FLOAT_DIVMOD = r'''def main():
    pairs = [(7.0, 2.0), (-7.0, 2.0), (7.0, -2.0), (-7.0, -2.0), (7.5, 2.0), (-7.5, 2.0),
             (7.5, -2.0), (-7.5, -2.0), (0.0, 2.0), (-0.0, 2.0), (1.0, 0.1), (-1.0, 0.1),
             (1e300, 3.0), (-1e300, 3.0), (5.0, float('inf')), (-5.0, float('inf')),
             (5.0, -float('inf')), (float('inf'), 2.0), (float('nan'), 2.0)]
    for a, b in pairs:
        print(a, b, a // b, a % b, divmod(a, b))


main()
'''

FLOAT_SOURCES = r'''class Box:
    def __init__(self, v):
        self.v = v


def calc(a, b):
    q, r = divmod(a, b)
    return a // b, a % b, q, r


def main():
    d = {"a": 1.0, "b": 0.1}
    xs = [-7.5, 2.0]
    box = Box(-5.0)
    print(calc(d["a"], d["b"]))
    print(calc(xs[0], xs[1]))
    print(calc(box.v, d["b"]))
    print(calc(7, 2.0), calc(-7.0, 2), calc(True, 2.0))
    print([x // 0.1 for x in [-1.0, 0.0, 1.0]])
    print({x: x % 0.1 for x in [-1.0, 0.0, 1.0]})
    print(max(x // 0.3 for x in [-1.0, 1.0]), min(x % 0.3 for x in [-1.0, 1.0]))


main()
'''

BOUNDARIES = r'''def main():
    pairs = [(1.0, 0.1), (-1.0, 0.1), (1.0, -0.1), (-1.0, -0.1),
             (0.3, 0.1), (0.7, 0.1), (3.0, 0.2), (-3.0, 0.2),
             (3.0, -0.2), (-3.0, -0.2), (2.0, 0.3), (-2.0, 0.3),
             (1e16, 3.0), (-1e16, 3.0), (1e16, -3.0), (-1e16, -3.0)]
    for a, b in pairs:
        print(a, b, a // b, a % b, divmod(a, b))


main()
'''

NEGATIVE_INTS = r'''def main():
    for a in [0, 7, -7, 13, -13, 10 ** 18, -(10 ** 18)]:
        for b in [1, 2, -2, 3, -3, 7, -7, 10 ** 18]:
            q, r = divmod(a, b)
            print(a, b, a // b, a % b, q, r, a == b * q + r)
    print(int(-2.9), int(2.9), int(-0.0), round(-2.5), round(-3.5), round(-7, -1))


main()
'''

SWEEP = r'''def main():
    nums = [0.0, -0.0, 1.0, -1.0, 0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.7, -0.7,
            1.5, -1.5, 2.5, -2.5, 3.0, -3.0, 7.0, -7.0, 1e-16, -1e-16,
            1e16, -1e16, 1e300, -1e300, float('inf'), float('-inf'), float('nan')]
    for i, a in enumerate(nums):
        for j, b in enumerate(nums):
            if (i * 31 + j) % 7 != 0:
                continue
            try:
                print(i, j, a // b, a % b)
            except ZeroDivisionError:
                print(i, j, "zero")
    print("done")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz45Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz45-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_float_divmod(self):
        self.check('float_divmod', FLOAT_DIVMOD)

    def test_float_sources(self):
        self.check('float_sources', FLOAT_SOURCES)

    def test_float_boundaries(self):
        self.check('float_boundaries', BOUNDARIES)

    def test_negative_ints(self):
        self.check('negative_ints', NEGATIVE_INTS)

    def test_float_sweep(self):
        self.check('float_sweep', SWEEP)


if __name__ == '__main__':
    unittest.main()
