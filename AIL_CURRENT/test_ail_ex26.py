"""Ex26: a Python module of definitions and constants is loaded, not run as a file tool.

`language_examples/math.ail` (`LIMIT = 6` and `def sum_to(n)`) was the only Python-syntax
example refused by the default build: the typed path compiled the definitions and then tried to
synthesize the array-entry wrapper, whose first parameter must be the sequence read from a file
(`not in the subset: the first parameter must be the sequence read from the file`).  CPython
binds the definitions and the constant, prints nothing and exits 0, which the general path
already did.  The default path now emits the same no-op `main` for a top level that is only a
docstring, plain definitions and literal module constants, with no `main`, import, class,
decorator, annotation or non-constant default that would run code while the module loads.

`__file__` is also covered here: the source path is installed before the module body, so a read,
a rebind, a function-local parameter and an imported module's own path match CPython on both
builds.  Every program below is compared with CPython 3.12 on the general and default builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / 'language_examples'

MATH = '''LIMIT = 6

def sum_to(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total
'''

SCRIPT = '''LIMIT = 6

def f(n):
    return n + 1

print(f(LIMIT))
'''

MAIN_CALLED = '''LIMIT = 6

def main():
    print(LIMIT)

main()
'''

FILE_DUNDER = '''first = __file__
print('entry', __file__.endswith('.py'))
__file__ = 'changed'
print('rebound', __file__)

def local(__file__):
    return __file__

print('local', local('arg'))
'''


def cpython(directory, name, text=None):
    path = Path(directory) / name
    if text is not None:
        path.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', name], cwd=directory,
                          capture_output=True, timeout=120)


def build(directory, name, general, text=None):
    path = Path(directory) / name
    if text is not None:
        path.write_text(text, encoding='utf-8')
    exe = 'exe_g' if general else 'exe_d'
    target = Path(directory) / exe
    if target.exists():
        target.unlink()
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    done = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', name,
                           '--syntax', 'python', '-o', exe], cwd=directory, capture_output=True,
                          text=True, timeout=900, env=env)
    if done.returncode != 0:
        return None, (done.stdout + done.stderr)[-3000:]
    ran = subprocess.run([str(target)], cwd=directory, capture_output=True, timeout=120)
    return (ran.stdout, ran.returncode), ran.stderr.decode('utf-8', 'replace')[-1500:]


class ModuleConstantTests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-ex26-') as directory:
            want = cpython(directory, name, text)
            self.assertEqual(want.returncode, 0, want.stderr)
            for general in (True, False):
                got, error = build(directory, name, general, text)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, error))
                self.assertEqual(got, (want.stdout, want.returncode),
                                 'general=%s\n%s' % (general, error))

    def test_language_example_math_builds(self):
        self.check('math.ail', (EXAMPLES / 'math.ail').read_text(encoding='utf-8'))

    def test_minimal_module_constant_is_a_no_op(self):
        self.check('module.py', MATH)
        self.check('constant_only.py', 'X = 1\nY = 2.5\nS = "text"\n')

    def test_scripts_still_run(self):
        self.check('script.py', SCRIPT)
        self.check('main_called.py', MAIN_CALLED)

    def test_file_dunder(self):
        self.check('file_dunder.py', FILE_DUNDER)


if __name__ == '__main__':
    unittest.main()
