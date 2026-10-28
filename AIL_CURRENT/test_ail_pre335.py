"""pre335: the rbrbrbrbpre33 review's first pre-existing difference, ``999... ** 0``.

CPython has unbounded ints, so the 20-digit base is exact and raising it to 0 gives 1.  With the
int64 ints this tree refused the construct by name on both builds; under exact ints both builds
build the program and match CPython's stdout, exit code and last stderr line.  The test covers
the direct form and the routes, the in-range power boundaries, and the other two items the
review recorded (``float(10 ** 400)`` and huge powers inside f-strings/maxsplit).
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


BIG = '99999999999999999999'


class Pre335(unittest.TestCase):
    CASES = (
        ('pow_zero', 'print(' + BIG + ' ** 0)\n'),
        ('pow_zero_nested', 'print((' + BIG + ' ** 0) + 1)\n'),
        ('pow_zero_negative', 'print((-' + BIG + ') ** 0)\n'),
        ('pow_one', 'print(' + BIG + ' ** 1)\n'),
        ('huge_literal', 'print(' + BIG + ')\n'),
        ('absorbing_multiply', 'print(' + BIG + ' * 0)\n'),
        ('cancel', 'print(' + BIG + ' - ' + BIG + ')\n'),
    )

    ROUTES = (
        ('argument', 'def show(x):\n    print(x)\n\nshow(' + BIG + ' ** 0)\n'),
        ('list', 'print([' + BIG + ' ** 0][0])\n'),
        ('dict', 'print({0: ' + BIG + ' ** 0}[0])\n'),
        ('attribute', 'class Box:\n    value = ' + BIG + ' ** 0\n\nprint(Box.value)\n'),
        ('returned', 'def show():\n    return ' + BIG + ' ** 0\n\nprint(show())\n'),
        ('local_base', 'value = ' + BIG + '\nprint(value ** 0)\n'),
    )

    OTHER_CASES = (
        ('float_overflow', 'print(float(10 ** 400))\n'),
        ('fstring_power', 'print(f"{10 ** 40}")\n'),
        ('maxsplit_power', 'print("a b c".split(" ", 10 ** 40))\n'),
    )

    def assert_matches_cpython(self, prefix, name, source, general):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (prefix + name + '_ref.py')
            path.write_text(source, encoding='utf-8')
            done = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True, timeout=120)
            lines = done.stderr.decode('utf-8', 'replace').strip().splitlines()
            built, exe = compile_source(directory, prefix + name, source, general=general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
            err = ran.stderr.decode('utf-8', 'replace')
            self.assertEqual(ran.returncode, done.returncode, err)
            self.assertEqual(ran.stdout.replace(b'\r\n', b'\n'), done.stdout.replace(b'\r\n', b'\n'), err)
            if lines:
                self.assertIn(lines[-1], err)

    def test_first_item_matches_cpython(self):
        for general in (False, True):
            for name, source in self.CASES:
                with self.subTest(name=name, general=general):
                    self.assert_matches_cpython('pre335_', name, source, general)

    def test_first_item_through_routes_matches_cpython(self):
        for general in (False, True):
            for name, source in self.ROUTES:
                with self.subTest(name=name, general=general):
                    self.assert_matches_cpython('pre335_route_', name, source, general)

    def test_other_recorded_items_match_cpython(self):
        for general in (False, True):
            for name, source in self.OTHER_CASES:
                with self.subTest(name=name, general=general):
                    self.assert_matches_cpython('pre335_other_', name, source, general)

    def test_module_assignment_and_in_range_boundaries_match_cpython(self):
        source = '''VALUE = %s ** 0
alias = VALUE
print(VALUE, alias)
print((10 ** 20) ** 0)
print(2 ** 0, 0 ** 0, (2 ** 63 - 1) ** 0, (-(2 ** 63)) ** 0, (2 ** 63) ** 0)
print((1 << 5000) ** 0, 0 ** (1 << 5000), 1 ** (1 << 5000), (-1) ** (1 << 5000))
''' % BIG
        with tempfile.TemporaryDirectory() as directory:
            expected, status = run_cpython(directory, 'pre335_in_range', source)
        for general in (False, True):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_source(directory, 'pre335_in_range', source, general=general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                self.assertEqual(ran.returncode, status, ran.stderr)
                self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)


if __name__ == '__main__':
    unittest.main()
