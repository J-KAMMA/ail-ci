"""A constant ``pow`` exponent built through a wide intermediate is refused by name.

The pre331 review recorded ``pow(2, (3**100)>>150)`` compiling and then stopping with
``integer overflow`` on both builds, where CPython prints the bignum.  The constant folder for
``pow`` could not see through the power ``3**100`` (its exponent is above the old 64-step
limit), so the shifted exponent (361) never became a static int.  The folder now falls back to
the shared exact-int folder, so the call is refused by name at compile time with
``int64 constant expression out of range``; the same fix follows a module or local name bound
to the expression.  In-range bases and exponents, a safe base, a negative exponent, the
three-argument form and a program that binds its own ``pow`` still match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = (
    ('direct', 'print(pow(2, (3**100)>>150))\n'),
    ('shift_beyond', 'print(pow(2, (3**100)>>151))\n'),
    ('negative_base', 'print(pow(-2, (3**100)>>150))\n'),
    ('argument', 'def show(value):\n    print(value)\n\n\nshow(pow(2, (3**100)>>150))\n'),
    ('list_item', 'print([pow(2, (3**100)>>150)][0])\n'),
    ('attribute', 'class Box:\n    pass\n\n\nbox = Box()\nbox.value = pow(2, (3**100)>>150)\nprint(box.value)\n'),
    ('dict_value', 'print({"value": pow(2, (3**100)>>150)}["value"])\n'),
    ('alias', 'p = pow\nprint(p(2, (3**100)>>150))\n'),
    ('module_constant', 'E = (3**100)>>150\nprint(pow(2, E))\n'),
    ('local_constant', 'def main():\n    e = (3**100)>>150\n    print(pow(2, e))\n\n\nmain()\n'),
    ('nested_expression', 'def main():\n    print(pow(2, ((3**100)>>150) + 0))\n\n\nmain()\n'),
)

SAFE = r'''def shadowed_pow(a, b):
    return 7


def main():
    print(pow((3**100)>>150, 2))
    print(pow(2, (3**100)>>159), pow(2, (3**100)>>158))
    print(pow(1, (3**100)>>150), pow(-1, (3**100)>>150))
    print(pow(True, (3**100)>>150), pow(2.0, (3**100)>>150))
    print(pow(2, -((3**100)>>150)))
    print(pow(2, (3**100)>>150, 1000))
    print(pow(2, 62), pow(-2, 63), pow(3, 39), pow(10, 18))
    print(pow((3**100)>>159, 5))
    p = pow
    print(p(2, 10))
    base = 2
    exponent = 10
    print(pow(base, exponent))
    print(shadowed_pow(2, (3**100)>>150))


main()
'''

SHADOWED = r'''def pow(base, exponent):
    return 7


def main():
    print(pow(2, (3**100)>>150))


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


class Pre331(unittest.TestCase):
    def test_a_wide_constant_exponent_builds_and_matches_cpython(self):
        # exact ints: the power is a big int on both builds, as in CPython (it was refused for the int64 era)
        with tempfile.TemporaryDirectory(prefix='ail-pre331-') as directory:
            for name, text in REFUSED:
                want = subprocess.run([sys.executable, '-B', '-c', text], capture_output=True, timeout=120)
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        status, got, output = build_run(directory, text, name, general)
                        self.assertEqual(status, want.returncode, output)
                        self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)
                        self.assertNotIn('Traceback', output)

    def test_in_range_and_shadowed_pow_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre331-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', SAFE], capture_output=True, timeout=120)
            self.assertEqual(want.returncode, 0, want.stderr)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, SAFE, 'safe', general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)

    def test_a_program_that_binds_its_own_pow_is_left_alone(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre331-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', SHADOWED], capture_output=True, timeout=120)
            self.assertEqual(want.returncode, 0, want.stderr)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, SHADOWED, 'shadowed', general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)


if __name__ == '__main__':
    unittest.main()
