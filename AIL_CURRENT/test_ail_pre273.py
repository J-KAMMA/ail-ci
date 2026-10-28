"""A constant integer base raised to a computed exponent is refused by name at compile time.

CPython's int is unbounded, so `2 ** n` keeps an exact answer for every n; this compiler's int is
64-bit, so the same expression used to compile and then stop with `integer overflow` (or spin for
a huge exponent).  The exponent is not known while compiling, so the construct itself is refused
there, on the typed path and both general emitters.  A constant exponent is still folded (and
refused only when its exact result leaves int64), a constant base 0/1/-1 is admitted because every
int64 exponent keeps its result in range, and a variable base with a constant exponent still uses
`ail_ipow`'s existing run-time check.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = (
    ('local', 'def main():\n    n = 64\n    print(2 ** n)\n\n\nmain()\n', 'constant base 2'),
    ('argument', 'def take(n):\n    print(2 ** n)\n\n\ndef main():\n    take(64)\n\n\nmain()\n',
     'constant base 2'),
    ('list_item', 'def main():\n    ns = [64]\n    print(2 ** ns[0])\n\n\nmain()\n', 'constant base 2'),
    ('attribute', 'class Box:\n    def __init__(self):\n        self.n = 64\n\n\ndef main():\n'
                  '    box = Box()\n    print(2 ** box.n)\n\n\nmain()\n', 'constant base 2'),
    ('dict_value', 'def main():\n    d = {"n": 64}\n    print(2 ** d["n"])\n\n\nmain()\n',
     'constant base 2'),
    ('in_range_exponent', 'def main():\n    n = 62\n    print(2 ** n)\n\n\nmain()\n',
     'constant base 2'),
    ('negative_base', 'def main():\n    n = 64\n    print((-2) ** n)\n\n\nmain()\n', 'constant base -2'),
    ('base_ten', 'def main():\n    n = 30\n    print(10 ** n)\n\n\nmain()\n', 'constant base 10'),
)

FRACTION = r'''from fractions import Fraction


def main():
    print(Fraction(1, 2))
    print(Fraction("1.25"))
    print(Fraction("1e3"))
    print(Fraction("1.25e-3"))
    print(Fraction(3, 4) + Fraction(1, 8))
    print(round(Fraction(1, 3), 2))


main()
'''


SAFE = r'''def main():
    n = 5
    print(2 ** 10)
    print(2 ** (2 + 3))
    print(2 ** True, 2 ** False, 2 ** (True + True))
    print(0 ** n, 1 ** n, (-1) ** n)
    print(2.0 ** n)
    print(n ** 3)
    print(2 ** -1)
    b = 2
    print(b ** 5)


main()
'''


def build_run(directory, text, name, general):
    src = Path(directory) / ('%s.py' % name)
    exe = Path(directory) / ('%s_%s' % (name, 'g' if general else 'd'))
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return built.returncode, b'', built.stdout + built.stderr
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return ran.returncode, ran.stdout.replace(b'\r\n', b'\n'), built.stdout + built.stderr


class Pre273(unittest.TestCase):
    def test_computed_exponent_is_refused_by_name(self):
        # exact ints (bigint): a constant base with a computed exponent builds and matches CPython
        with tempfile.TemporaryDirectory(prefix='ail-pre273-') as directory:
            for name, text, wording in REFUSED:
                src = Path(directory) / ('%s_cpython.py' % name)
                src.write_text(text, encoding='utf-8')
                want = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                                      env=dict(os.environ, PYTHONUTF8='1'))
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        status, got, output = build_run(directory, text, name, general)
                        self.assertEqual((status, got), (want.returncode, want.stdout.replace(b'\r\n', b'\n')), output)

    def test_constant_exponent_and_safe_bases_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre273-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', SAFE], capture_output=True, timeout=120)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, SAFE, 'safe', general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)

    def test_library_prelude_power_still_builds(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre273-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', FRACTION], capture_output=True, timeout=120)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, FRACTION, 'fraction', general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)


if __name__ == '__main__':
    unittest.main()
