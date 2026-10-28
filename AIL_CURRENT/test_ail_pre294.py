"""A constant ``pow(base, exp)`` whose exact result leaves int64 matches CPython.

CPython's int is unbounded, so ``pow(2, 63)`` prints the bignum.  With exact ints (bigint,
BIGINT.md) the Python surface builds the same call on both builds and prints the same integer
(it used to be refused by name while ints were 64-bit).  An in-range constant result keeps the
ordinary lowering and a negative exponent keeps CPython's float answer.
A program that binds its own ``pow`` is left alone.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = (
    ('direct', 'def main():\n    print(pow(2, 63))\n\n\nmain()\n'),
    ('ten', 'def main():\n    print(pow(10, 100))\n\n\nmain()\n'),
    ('negative_base', 'def main():\n    print(pow(-2, 64))\n\n\nmain()\n'),
    ('argument', 'def show(value):\n    print(value)\n\n\ndef main():\n    show(pow(2, 63))\n\n\nmain()\n'),
    ('list_item', 'def main():\n    print([pow(2, 63)][0])\n\n\nmain()\n'),
    ('attribute', 'class Box:\n    pass\n\n\ndef main():\n    box = Box()\n    box.value = pow(2, 63)\n    print(box.value)\n\n\nmain()\n'),
    ('dict_value', 'def main():\n    print({"value": pow(2, 63)}["value"])\n\n\nmain()\n'),
    ('alias', 'def main():\n    p = pow\n    print(p(2, 63))\n\n\nmain()\n'),
    ('module_constants', 'BASE = 2\nEXP = 63\n\n\ndef main():\n    print(pow(BASE, EXP))\n\n\nmain()\n'),
    ('local_constants', 'def main():\n    base = 2\n    exponent = 63\n    print(pow(base, exponent))\n\n\nmain()\n'),
    ('expressions', 'def main():\n    print(pow(2 ** 1, 2 ** 6 - 1))\n\n\nmain()\n'),
)

SAFE = r'''


def shadowed_pow(a, b):
    return 7


def main():
    print(pow(2, 62))
    print(pow(-2, 62))
    print(pow(-2, 63))
    print(pow(10, 18))
    print(pow(3, 39))
    print(pow(7, 20))
    print(pow(0, 0), pow(0, 5), pow(0, 1000000))
    print(pow(1, 1000000), pow(-1, 1000001), pow(-1, 1000000))
    print(pow(2, 0), pow(-2, 0), pow(5, 1))
    print(pow(True, 5), pow(2, True), pow(-1, True))
    print(pow(2, -1), pow(2, -2), pow(10, -2))
    print(pow(2.0, 3), pow(2.0, -1), pow(2.0, 0.5), pow(-2.0, 3))
    print(pow(2, 63, 7), pow(10, 100, 13), pow(2, -1, 5))
    for base, exponent in ((0, -1), (0, -5)):
        try:
            print(pow(base, exponent))
        except Exception as exc:
            print(type(exc).__name__)
    p = pow
    print(p(2, 10))
    base = 2
    exponent = 10
    print(pow(base, exponent))
    print(shadowed_pow(2, 63))


main()
'''

SHADOWED = r'''def pow(base, exponent):
    return 7


def main():
    print(pow(2, 63))


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


class Pre294(unittest.TestCase):
    def test_constant_pow_out_of_int64_matches_cpython(self):
        # exact ints (bigint): builds and matches CPython (stdout, exit code)
        with tempfile.TemporaryDirectory(prefix='ail-pre294-') as directory:
            for name, text in REFUSED:
                want = subprocess.run([sys.executable, '-B', '-c', text], capture_output=True, timeout=120)
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        status, got, output = build_run(directory, text, name, general)
                        self.assertEqual(
                            (status, got), (want.returncode, want.stdout.replace(b'\r\n', b'\n')), output)

    def test_in_range_float_and_modular_pow_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre294-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', SAFE], capture_output=True, timeout=120)
            self.assertEqual(want.returncode, 0, want.stderr)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, SAFE, 'safe', general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)

    def test_a_program_that_binds_its_own_pow_is_left_alone(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre294-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', SHADOWED], capture_output=True, timeout=120)
            self.assertEqual(want.returncode, 0, want.stderr)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, SHADOWED, 'shadowed', general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)


if __name__ == '__main__':
    unittest.main()
