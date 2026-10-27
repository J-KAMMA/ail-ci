"""pre372: an augmented power that overflows int64 is refused by name at compile time.

The rbrbrbrbrbpre33 review recorded `b = 10; b **= 40` compiling on both builds and then
stopping with `integer overflow`, where CPython prints the unbounded integer.  The module
constant-power pass folded `b ** e`, but the augmented spelling is a separate statement.  A
direct module or function body statement whose target has exactly one prior straight-line
constant binding is now folded; when the exact power leaves int64 it is refused with
`int64 constant expression out of range` before either emitter sees it.  The base and the
exponent may take a value through a list item, a dict value, a class attribute or a
passthrough call, and a later rebinding does not change the recorded base.

In-range powers, the safe bases 0/1/-1, a zero or negative exponent, a float or bool base,
a base rebound before the statement, and a base or exponent known only at run time still
match CPython.  Programs are built with the general path forced and with the default build;
stdout and the exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = (
    ('direct', 'b = 10\nb **= 40\nprint(b)\n'),
    ('exponent_name', 'b = 10\ne = 40\nb **= e\nprint(b)\n'),
    ('list_base', 'b = [10][0]\nb **= 40\nprint(b)\n'),
    ('dict_base', 'b = {"v": 10}["v"]\nb **= 40\nprint(b)\n'),
    ('attribute_base',
     'class Box:\n    v = 10\n\n\nb = Box.v\nb **= 40\nprint(b)\n'),
    ('argument_base',
     'def ident(v):\n    return v\n\n\nb = ident(10)\nb **= 40\nprint(b)\n'),
    ('list_exponent', 'b = 10\nb **= [40][0]\nprint(b)\n'),
    ('dict_exponent', 'e = {"e": 40}\nb = 10\nb **= e["e"]\nprint(b)\n'),
    ('alias_base', 'b = 10\na = b\na **= 40\nprint(a)\n'),
    ('later_rebinding', 'b = 10\nb **= 40\nb = 2\nprint(b)\n'),
    ('negative_base', 'b = -10\nb **= 40\nprint(b)\n'),
    ('int64_boundary', 'b = 2\nb **= 63\nprint(b)\n'),
    ('int64_width', 'b = 10\nb **= 19\nprint(b)\n'),
    ('negative_even', 'b = -2\nb **= 64\nprint(b)\n'),
    ('power_three', 'b = 3\nb **= 40\nprint(b)\n'),
    ('function_body', 'def main():\n    b = 10\n    b **= 40\n    print(b)\n\n\nmain()\n'),
)

MATCHING = '''
b = 2
b **= 40
print(b)
a = 2
a **= 62
print(a)
c = -2
c **= 63
print(c)
d = 10
d **= 18
print(d)
e = 3
e **= 39
print(e)
z = 0
z **= 1000
print(z)
o = 1
o **= 1000
print(o)
n = -1
n **= 1001
print(n)
q = 10
q **= 0
print(q)
r = 10
r **= -1
print(r)
u = 10
u **= 2
u = 3
print(u)
w = 10
w = 2
w **= 40
print(w)
v = True
v **= 2
print(v)
f = 10.0
f **= 40
print(f)
g = 2
g **= 3.0
print(g)
m = 9223372036854775807
m **= 0
print(m)


def function_local():
    h = 2
    h **= 40
    print(h)


def runtime_only(value):
    value **= 2
    print(value)


function_local()
runtime_only(3)
'''


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            src.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, text=True,
                         timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre372(unittest.TestCase):
    def test_augmented_power_overflow_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre372-') as directory:
            for name, text in REFUSED:
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        built, exe = build(directory, name, text, general)
                        output = built.stdout + built.stderr
                        self.assertNotEqual(built.returncode, 0, output)
                        self.assertFalse(exe.exists())
                        self.assertIn('int64 constant expression out of range', output)
                        self.assertNotIn('integer overflow', output)
                        self.assertNotIn('Traceback', output)

    def test_in_range_powers_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre372-') as directory:
            want, status = run_cpython(directory, 'matching', MATCHING)
        for general in (False, True):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built, exe = build(directory, 'matching', MATCHING, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                                     cwd=directory)
                self.assertEqual(ran.returncode, status, ran.stderr[-1200:])
                self.assertEqual(ran.stdout.replace('\r\n', '\n'), want)


if __name__ == '__main__':
    unittest.main()
