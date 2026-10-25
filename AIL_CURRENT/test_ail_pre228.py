"""Pre-228: an out-of-int64 expression built from a named constant is refused by name.

CPython's ints are unbounded, so ``N = 2**62; class C: X = N * 4`` makes ``X`` a bignum.  AIL
evaluates the arithmetic in int64, so the construct compiled and then stopped with
``integer overflow``.  A name cannot be folded into one literal, so a constant expression that
names a module or class constant and leaves int64 at a run-time operation is now refused at
compile time on both builds with ``int64 constant expression out of range: <value>``; literal
subexpressions are still folded as before and in-range named expressions still match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MESSAGE = 'int64 constant expression out of range'
BIG = '18446744073709551616'

REFUSALS = {
    'class': ('N = 2**62\nclass C:\n    X = N * 4\n\n\nprint(C.X)\n', BIG),
    'class_annassign': ('N = 2**62\nclass C:\n    X: int = N * 4\n\n\nprint(C.X)\n', BIG),
    'module': ('N = 2**62\nX = N * 4\nprint(X)\n', BIG),
    'negative': ('N = -2**62\nclass C:\n    X = N * 4\n\n\nprint(C.X)\n',
                 '-18446744073709551616'),
    'boundary_2_63': ('N = 2**62\nclass C:\n    X = N * 2\n\n\nprint(C.X)\n',
                      '9223372036854775808'),
    'intermediate': ('N = 2**62\nclass C:\n    X = (N * 4) // 4\n\n\nprint(C.X)\n', BIG),
    'shift': ('N = 2**62\nX = N << 2\nprint(X)\n', BIG),
    'argument': ('N = 2**62\nprint(N * 4)\n', BIG),
    'list_item': ('N = 2**62\nxs = [N * 4]\nprint(xs)\n', BIG),
    'dict_value': ('N = 2**62\nd = {"k": N * 4}\nprint(d)\n', BIG),
    'default': ('N = 2**62\n\n\ndef f(x=N * 4):\n    return x\n\n\nprint(f())\n', BIG),
    'pow': ('N = 2**2\nX = N ** 100\nprint(X)\n', 'too large'),
}

IN_RANGE = r'''N = 2**62
M = 2**63 - 1


class C:
    X = N // 4
    Y = N + 1
    Z = (M) // N


def f(N):
    return N * 4


def g():
    N = 1
    return N * 4


print(C.X, C.Y, C.Z)
print(N // 4, N >> 62, -N)
print(M - 1, (2**63 - 1) // N, N + 1)
print(f(1), g())


def h(a=2**62):
    return a // 4


print(h())
'''

LITERALS = r'''print(2**63 - 1)
print((1 << 63) - 1)
print(2**100 // 2**80)
print(2**65 - 2**65)
print((2**100) // (2**100) * (2**63 - 1))
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
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
    return built, exe


def _build_and_run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre228Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre228-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0),
                                 '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def refused(self, slug, text, value):
        """No executable in either build, exit 2, and the refusal names the value."""
        with tempfile.TemporaryDirectory(prefix='ail-pre228-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2,
                                 '%s (general=%s)\n%s' % (text[:2000], general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn(MESSAGE, output, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertIn(value, output, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertNotIn('integer overflow', output,
                                 '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def test_named_out_of_range_is_refused(self):
        for slug, (text, value) in REFUSALS.items():
            self.refused(slug, text, value)

    def test_in_range_named_expressions_match_cpython(self):
        self.check('in_range', IN_RANGE)

    def test_literal_expressions_are_unchanged(self):
        self.check('literals', LITERALS)


if __name__ == '__main__':
    unittest.main()
