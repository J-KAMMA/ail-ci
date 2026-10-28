"""A builtin ``pow()`` that leaves int64 builds and matches CPython under exact ints (job pre299).

CPython's ``pow(2, 63)`` is the exact bignum 9223372036854775808.  With the int64 ints this was
refused by name at compile time (constant result, or a constant base with a run-time exponent);
under exact ints both builds build the program and match CPython's stdout, exit code and last
stderr line (``pow(2, 1 << 20)`` fails in CPython itself with the 4300-digit conversion limit).
In-range powers, bases 0/1/-1, float powers, the three-argument form and a program
that binds its own ``pow`` keep matching CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED_CONSTANT = (
    ('literal', 'print(pow(2, 63))\n', 'int64 constant expression out of range'),
    ('module_constant', 'n = 70\nprint(pow(2, n))\n', 'int64 constant expression out of range'),
    ('local_constant', 'def main():\n    n = 63\n    print(pow(2, n))\n\n\nmain()\n',
     'int64 constant expression out of range'),
    ('expression', 'print(pow(10, 18 + 1))\n', 'int64 constant expression out of range'),
    ('negative_base', 'print(pow(-2, 64))\n', 'int64 constant expression out of range'),
    ('other_base', 'print(pow(3, 40))\n', 'int64 constant expression out of range'),
    ('huge_exponent', 'print(pow(2, 1 << 20))\n', 'int64 constant expression out of range'),
)

REFUSED_COMPUTED = (
    ('argument', 'def take(n):\n    print(pow(2, n))\n\n\ndef main():\n    take(63)\n\n\nmain()\n'),
    ('small_argument', 'def take(n):\n    print(pow(2, n))\n\n\ndef main():\n    take(10)\n\n\nmain()\n'),
    ('module_alias', 'base = 2\n\n\ndef take(n):\n    print(pow(base, n))\n\n\n'
                     'def main():\n    take(63)\n\n\nmain()\n'),
    ('list_item', 'def main():\n    ns = [63]\n    print(pow(2, ns[0]))\n\n\nmain()\n'),
    ('attribute', 'class Box:\n    def __init__(self):\n        self.n = 63\n\n\n'
                  'def main():\n    box = Box()\n    print(pow(2, box.n))\n\n\nmain()\n'),
    ('dict_value', 'def main():\n    d = {"n": 63}\n    print(pow(2, d["n"]))\n\n\nmain()\n'),
    ('negative_base', 'def take(n):\n    print(pow(-2, n))\n\n\ndef main():\n    take(63)\n\n\nmain()\n'),
)

SAFE = r'''def neg(b, n):
    print(pow(b, n))


def main():
    print(pow(2, 62))
    print(pow(-2, 63))
    print(pow(2, 0))
    print(pow(3, 39))
    print(pow(0, 70))
    print(pow(1, 70))
    print(pow(-1, 71))
    print(pow(2, True))
    print(pow(True, 70))
    print(pow(2.0, 3))
    print(pow(2, 0.5))
    neg(1, -1)
    neg(-1, -1)
    neg(1, -7)
    neg(-1, -7)
    print(pow(2, 100, 1000000007))
    print(pow(5, 0, -5))
    print(pow(2, -1, 5))


main()
'''

ZERO_NEGATIVE = r'''def take(b, n):
    print(pow(b, n))


def main():
    take(0, -1)


main()
'''

SHADOWED = r'''def pow(a, b):
    return a + b


def main():
    n = 100
    print(pow(2, n))


main()
'''


def _build_and_run(directory, name, text, general, run=True):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
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
    if not run:
        return (b'', 0), ''
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


class Pre299(unittest.TestCase):
    def matches_cpython(self, cases):
        with tempfile.TemporaryDirectory(prefix='ail-pre299-') as directory:
            for name, text, *rest in cases:
                src = Path(directory) / (name + '_ref.py')
                src.write_text(text, encoding='utf-8')
                done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                                      env=dict(os.environ, PYTHONUTF8='1'))
                want_out = done.stdout.replace(b'\r\n', b'\n')
                lines = done.stderr.decode('utf-8', 'replace').strip().splitlines()
                want_err = lines[-1] if lines else ''
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        got, output = _build_and_run(directory, name + ('_g' if general else '_d'), text, general)
                        self.assertIsNotNone(got, output)
                        self.assertEqual(got, (want_out, done.returncode), output)
                        self.assertNotIn('integer overflow', output)
                        if want_err:
                            self.assertIn(want_err, output)

    def check_python(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre299-') as directory:
            want = _cpython(directory, name, text)
            for general in (False, True):
                with self.subTest(case=name, general=general):
                    got, output = _build_and_run(directory, name + ('_g' if general else '_d'), text, general)
                    self.assertIsNotNone(got, output)
                    self.assertEqual(got, want, output)

    def test_constant_pow_outside_int64_matches_cpython(self):
        self.matches_cpython(REFUSED_CONSTANT)

    def test_computed_exponent_pow_matches_cpython(self):
        self.matches_cpython(REFUSED_COMPUTED)

    def test_in_range_pow_matches_cpython(self):
        self.check_python('safe', SAFE)

    def test_zero_to_negative_power_matches_cpython(self):
        self.check_python('zero_negative', ZERO_NEGATIVE)

    def test_shadowed_pow_matches_cpython(self):
        self.check_python('shadowed', SHADOWED)


if __name__ == '__main__':
    unittest.main()
