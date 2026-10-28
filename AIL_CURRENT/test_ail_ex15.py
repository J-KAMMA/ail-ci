"""ex15: a Python-syntax module of definitions plus module constants executes only the constants.

CPython runs a script top to bottom: ``LIMIT = 6`` binds a module name and the following ``def``
statements bind functions, then the script ends without calling anything.  The general path took
that shape already once a module-level assignment existed, but the typed path handed the LAST
function to its command-line entry builder, which refused a scalar-only parameter with
"the first parameter must be the sequence read from the file" (the language_examples/math.ail
program, also the minimal ``LIMIT = 6`` reproducer below).  A module with at least one module
constant (and no ``main``) now emits a no-op entry instead, so stdout and the exit status match
CPython on both builds.  A file with only functions and no module statement keeps the language's
single-function entry convention, and a top-level call or ``__main__`` guard still runs.

Programs are built with the general path forced and with the default build; stdout and the
exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'int_constant': '''
LIMIT = 6

def sum_to(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total
''',
    'constant_types': '''
SCALE = 1.5
FLAG = True
NAME = "héllo"
DATA = b"four"
MIN = -9223372036854775808
MAX = 9223372036854775807

def scaled(x):
    if FLAG:
        return x * SCALE + MIN
    return x

def shout(text):
    return text.upper() + NAME

def clamp(n):
    return min(max(n, MIN), MAX)

def raw():
    return DATA
''',
    'several_functions': '''
A = 1
B = "two"

def first(n):
    return n + A

def second(s):
    return B + s

def third(x):
    return x * A
''',
    'import_and_constant': '''
import math

ROOT = 2

def area(r):
    return math.pi * r * r + ROOT
''',
    'top_level_call_still_runs': '''
LIMIT = 6

def double(n):
    return n * 2

print(double(LIMIT))
''',
    'main_guard_still_runs': '''
LIMIT = 2

def double(n):
    return n * 2

if __name__ == '__main__':
    print(double(LIMIT))
''',
}


def run_cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, text=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace('\r\n', '\n'), done.returncode


def build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class Ex15(unittest.TestCase):
    def check(self, name, text):
        want, status = run_cpython(self.directory, name, text)
        for general in (False, True):
            with self.subTest(case=name, general=general):
                built, exe = build(self.directory, name, text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                                     cwd=self.directory)
                self.assertEqual(ran.returncode, status, ran.stderr[-1200:])
                self.assertEqual(ran.stdout.replace('\r\n', '\n'), want, ran.stderr[-1200:])

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory(prefix='ail-ex15-')
        self.directory = self._temp.name

    def tearDown(self):
        self._temp.cleanup()

    def test_definitions_with_module_constants_match_cpython(self):
        for name, text in PROGRAMS.items():
            self.check(name, text)

    def test_language_example_math_ail_matches_cpython(self):
        text = (ROOT / 'language_examples' / 'math.ail').read_text(encoding='utf-8')
        self.check('language_example_math', text)


if __name__ == '__main__':
    unittest.main()
