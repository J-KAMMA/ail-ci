"""pre351: the rbrbrbrbrbpre33 review's first pre-existing difference, ``x = 10; x ** 40``.

CPython has unbounded ints and prints 10 ** 40; an AIL int is int64, so the exact result has
no representation.  On this tree the module-level local form is already folded by the
constant-power pass and refused by name at compile time, which the task allows, so no
compiler change is needed.  The other recorded items (``2 ** 63`` mixed with division,
multiplication or addition) are already refused by name too.  Values that reach the power
only at run time, or through a function body, keep the pre-existing runtime
``integer overflow`` stop; they are not changed by this job.  This test locks the named
refusals and the in-range powers that must keep matching CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_source(directory, name, source, general=False):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=600, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


REFUSALS = ('int64 constant out of range',
            'int64 constant expression out of range',
            'does not fit in a 64-bit signed integer',
            'outside the signed 64-bit range',
            'not in the subset')


class Pre351(unittest.TestCase):
    CASES = (
        ('local', 'x = 10\nprint(x**40)\n'),
        ('local_spaced', 'x = 10\nprint(x ** 40)\n'),
        ('negative_base', 'x = -10\nprint(x**40)\n'),
        ('wide_exponent', 'x = 2\nprint(x**64)\n'),
    )

    ROUTES = (
        ('module', 'X = 10\nprint(X**40)\n'),
        ('alias', 'x = 10\ny = x\nprint(y**40)\n'),
        ('computed_exponent', 'x = 10\nn = 40\nprint(x**n)\n'),
        ('nested', 'x = 10\nprint((x**40) + 1)\n'),
        ('right_operand', 'x = 10\nprint(1 + x**40)\n'),
        ('conditional', 'x = 10\nprint((x**40) if True else 0)\n'),
    )

    OTHER_CASES = (
        ('div_pow', 'print(2**63 / 2**63)\n'),
        ('div_half', 'print((2**63)/2)\n'),
        ('mul_float', 'print(2**63*1.0)\n'),
        ('add_float', 'print(2**63+0.0)\n'),
    )

    def _assert_refused(self, cases, prefix):
        for general in (False, True):
            for name, source in cases:
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, prefix + name, source, general=general)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertFalse(exe.exists())
                    self.assertTrue(any(message in built.stderr for message in REFUSALS), built.stderr)

    def test_first_item_is_refused_by_name(self):
        self._assert_refused(self.CASES, 'pre351_')

    def test_first_item_routes_are_refused_by_name(self):
        self._assert_refused(self.ROUTES, 'pre351_route_')

    def test_other_recorded_items_are_refused_by_name(self):
        self._assert_refused(self.OTHER_CASES, 'pre351_other_')

    def test_in_range_powers_match_cpython(self):
        source = '''def show_pow(v):
    print(v ** 40)


print(2 ** 62)
x = 2
print(x ** 62)
y = 10
print(y ** 18)
z = -1
print(z ** 40)
print(0 ** 40, 1 ** 40)
print(10 ** -1)
f = 10.0
print(f ** 40)
m = 10
m = 2
print(m ** 40)
print((2 ** 63 - 1) // 1)
print((2 ** 63 - 1) / (2 ** 63 - 1))
show_pow(0)
show_pow(1)
show_pow(-1)
print([1][0] ** 40)
class Box:
    v = 1
print(Box.v ** 40)
print({0: 1}[0] ** 40)
'''
        with tempfile.TemporaryDirectory() as directory:
            expected, status = run_cpython(directory, 'pre351_in_range', source)
        for general in (False, True):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_source(directory, 'pre351_in_range', source, general=general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                self.assertEqual(ran.returncode, status, ran.stderr)
                self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)


if __name__ == '__main__':
    unittest.main()
