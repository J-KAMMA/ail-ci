"""A float remainder of zero keeps the divisor's sign (operator chaining, against CPython 3.12).

`-0.0 % 1.0` is 0.0 and `0.0 % -1.0` is -0.0 in CPython: when fmod() is zero, `%` returns
copysign(0.0, divisor), not the sign fmod() happened to produce. The general path, the unified
fast path and the boxed runtime all returned the fmod() sign, so `print(-0.0 % 1.0)` showed -0.0
and `print(0.0 % -1.0)` showed 0.0 on both builds. Nonzero remainders and the sign of `//` were
already CPython's. The case below reaches `%` through literals, a function argument, a list item,
a dict value, an attribute and an augmented assignment, and keeps the nonzero boundaries.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ZERO_SIGN = r'''def main() -> None:
    print(-0.0 % 1.0, 0.0 % -1.0, -0.0 % -1.0, 0.0 % 1.0)
    print(-4.0 % 2.0, 4.0 % -2.0, -4.0 % -2.0, 4.0 % 2.0)
    print(-4.5 % 1.5, 4.5 % -1.5, -4.5 % -1.5, 4.5 % 1.5)
    print(-0.0 // 1.0, 0.0 // -1.0, -0.0 // -1.0, 0.0 // 1.0)
    print(divmod(-0.0, 1.0), divmod(0.0, -1.0), divmod(-0.0, -1.0))
    print(-5.5 % 2.0, 5.5 % -2.0, -5.5 % -2.0, 5.5 % 2.0)
main()
'''

ZERO_SOURCES = r'''class C:
    pass


def mod(a: float, b: float) -> float:
    return a % b


def main() -> None:
    c = C()
    c.a = -0.0
    c.b = 1.0
    xs = [-0.0, 1.0, 0.0, -1.0]
    d = {"a": -0.0, "b": -1.0}
    print(mod(-0.0, 1.0), mod(0.0, -1.0), mod(-0.0, -1.0), mod(0.0, 1.0))
    print(xs[0] % xs[1], xs[2] % xs[3], xs[0] % xs[3], xs[2] % xs[1])
    print(d["a"] % d["b"], -d["a"] % d["b"], d["a"] % -d["b"])
    print(c.a % c.b, -c.a % c.b, c.a % -c.b)
    print(-0.0 % 2, 0.0 % -2, -4 % 2.0, 4.0 % -2, -0.0 % -1, 0.0 % 1)
    print(-0.0 % 1.0 == 0.0, 0.0 % -1.0 == 0.0, repr(-0.0 % 1.0), repr(0.0 % -1.0))
    a = -0.0
    b = 1.0
    a %= b
    print(a)
    b = 0.0
    b %= -1.0
    print(b)
    print((xs[0] + 0.0) % (xs[1] * 1.0), -(xs[0] % xs[1]), +(xs[2] % xs[3]))
main()
'''

NONZERO = r'''def main() -> None:
    values = [-5.5, -2.0, -0.0, 0.0, 0.5, 5.5, 1e300, -1e300]
    divisors = [-2.0, -1.0, -0.5, 0.5, 1.0, 2.0, 1e300]
    for a in values:
        for b in divisors:
            r = a % b
            print(a, b, r, (1.0 / r) if r != 0.0 else "zero")
    print("done")
main()
'''

CHAINED = r'''def main() -> None:
    a = -0.0
    b = 1.0
    c = -1.0
    print(a % b % c, (a % b) % c, a % (b % (b + 1.0)))
    print(a % b + 0.0, (a % b) * -1.0, -(a % b))
    print(-0.0 % (1.0 + 0.0), (-0.0) % (1.0 * 1.0), (0.0 - 0.0) % -1.0)
    print((a or b) % b, (b if a else c) % b)
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


class Fuzz63Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz63-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_zero_sign(self):
        self.check('zero_sign', ZERO_SIGN)

    def test_zero_sign_sources(self):
        self.check('zero_sources', ZERO_SOURCES)

    def test_nonzero_boundaries(self):
        self.check('nonzero', NONZERO)

    def test_chained_remainders(self):
        self.check('chained', CHAINED)


if __name__ == '__main__':
    unittest.main()
