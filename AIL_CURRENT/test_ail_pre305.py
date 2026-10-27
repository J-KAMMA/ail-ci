"""A huge int power with a safe base no longer loops once per exponent (job pre305).

The general path's integer ``**``/``pow()`` multiplied once per exponent, so ``pow(-1, 10**12)``
never finished where CPython prints 1; the same loop ran for the bases 0 and 1 and for odd
exponents.  The boxed integer power now uses exponentiation by squaring, so the safe bases
finish, the sign of -1 follows the exponent's parity, and in-range powers keep CPython's value.
An out-of-int64 result keeps the existing run-time integer-overflow stop.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = r'''class Box:
    def __init__(self):
        self.n = 10**12


def power(base, exponent):
    return pow(base, exponent)


def main():
    n = 10**12
    print(pow(-1, n))
    print(pow(-1, n + 1))
    print(pow(0, n))
    print(pow(1, n))
    print(pow(-1, True), pow(-1, False))
    print(pow(-1, -1))
    print(pow(2, 62))
    print(pow(-2, 63))
    print(pow(3, 39))
    print(power(-1, n))
    xs = [n, n + 1]
    print(pow(-1, xs[0]), pow(-1, xs[1]))
    d = {"even": n, "odd": n + 1}
    print(pow(-1, d["even"]), pow(-1, d["odd"]))
    box = Box()
    print(pow(-1, box.n))
    alias = n
    print(pow(-1, alias))
    print((-1) ** n)
    print((-1) ** (n + 1))
    print(0 ** n, 1 ** n)


main()
'''


def build_run(directory, general):
    src = Path(directory) / ('probe_%s.py' % ('g' if general else 'd'))
    exe = Path(directory) / ('probe_%s' % ('g' if general else 'd'))
    src.write_text(PROGRAM, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return built.returncode, b'', built.stdout + built.stderr
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=30)
    return ran.returncode, ran.stdout.replace(b'\r\n', b'\n'), built.stdout + built.stderr


class Pre305(unittest.TestCase):
    def test_safe_bases_and_in_range_powers_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre305-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', PROGRAM], capture_output=True,
                                  timeout=30)
            self.assertEqual(want.returncode, 0, want.stderr)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)


if __name__ == '__main__':
    unittest.main()
