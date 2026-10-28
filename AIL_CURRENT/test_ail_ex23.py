"""ex23: a module-constant plus function program runs no function, like CPython.

`math.ail` defines a module constant and a helper, but has no top-level call.  CPython runs the
assignment, defines the helper, prints nothing and exits 0.  The general path already built that
module-body shape; the typed path selected the last function as its file/argv entry and refused
`the first parameter must be the sequence read from the file`.  When the source keeps module
literal assignments and only defines functions/classes, the typed path now emits the same
do-nothing `main`, so both builds match CPython.  A top-level call still becomes the synthetic
entry and runs.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None

MATH = (ROOT / 'language_examples' / 'math.ail').read_text(encoding='utf-8')

PROGRAMS = {
    'minimal': '''
LIMIT = 6


def sum_to(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total
''',
    'math_example': MATH,
    'top_level_call': '''
LIMIT = 6


def sum_to(n):
    return sum(range(n + 1))


print(sum_to(LIMIT))
''',
    'if_main_guard': '''
LIMIT = 3


def twice(n):
    return n * 2


if __name__ == "__main__":
    print(twice(LIMIT))
''',
    'print_not_called': '''
X = 1


def noisy(n):
    print(n)
    return n
''',
    'types': '''
I = 3
F = 1.5
S = "x"
B = b"y"


def take_int(n):
    return n + 1


def take_float(x):
    return x * 2.0


def take_str(s):
    return s + "!"


def take_bytes(b):
    return b + b"?"
''',
    'class_helper': '''
LIMIT = 6


class Box:
    def __init__(self, v):
        self.v = v

    def get(self, n):
        return self.v + n


def helper(n):
    return Box(n).get(LIMIT)
''',
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(CLI), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=1200, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    ran = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (ran.stdout.replace(b'\r\n', b'\n'), ran.returncode), \
        ran.stderr.decode('utf-8', 'replace')[-1500:]


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class ModuleConstantTests(unittest.TestCase):
    def test_module_constant_programs_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex23-') as directory:
            for slug, text in PROGRAMS.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    where = '%s (general=%s)' % (slug, general)
                    self.assertIsNotNone(got, where + '\n' + build_err)
                    self.assertEqual(got, want, where + '\n' + text)


if __name__ == '__main__':
    unittest.main()
