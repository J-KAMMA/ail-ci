"""Pre39: int() of an out-of-int64 float is refused through keyword wrapper calls too.

CPython has unbounded integers, so `int(1e300)` prints a 301-digit integer. This language's ints
are signed int64, so the front end refuses a conversion whose float value it can see is outside
int64, naming the construct and the value instead of compiling a program that stops with
`integer overflow`. The pre31 check covered positional arguments; this module pins the keyword
spellings as well (`take(x=...)`, an identity call and a keyword-only wrapper), beside the
positional and literal shapes it already handled. Values that fit int64, non-finite floats and
run-time-only floats are unchanged and still compared with CPython.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre39-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertIn('big integer', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre39-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'keyword_wrapper': 'def take(x):\n    return int(x)\n\n\nprint(take(x=1e300))\n',
    'positional_wrapper': 'def take(x):\n    return int(x)\n\n\nprint(take(1e300))\n',
    'negative_keyword_wrapper': 'def take(x):\n    return int(x)\n\n\nprint(take(x=-1e300))\n',
    'keyword_list_item': 'def take(x):\n    return int(x)\n\n\nprint(take(x=[1e300][0]))\n',
    'keyword_dict_value': 'def take(x):\n    return int(x)\n\n\nprint(take(x={"v": 1e300}["v"]))\n',
    'keyword_tuple_item': 'def take(x):\n    return int(x)\n\n\nprint(take(x=(1e300,)[0]))\n',
    'keyword_identity': 'def identity(x):\n    return x\n\n\nprint(int(identity(x=1e300)))\n',
    'keyword_only_wrapper': 'def take(*, x=0.0):\n    return int(x)\n\n\nprint(take(x=1e300))\n',
    'direct_literal': 'print(int(1e300))\n',
    'module_constant': 'x = 1e300\nprint(int(x))\n',
    'keyword_module_constant': 'x = 1e300\n\n\ndef take(v):\n    return int(v)\n\n\nprint(take(v=x))\n',
    'upper_bound': 'print(int(1e19))\n',
}

MATCH = {
    'keyword_in_range': '''
items = [1.9, -1.9]
d = {"v": 9.0e18}


def take(x):
    return int(x)


def identity(x):
    return x


def kwonly(*, x=1.0):
    return int(x)


print(take(x=items[0]), take(x=items[1]), take(x=d["v"]))
print(take(1.9), take(-1.9), take(0.0), take(-0.0))
print(identity(x=1.5), kwonly(x=1.9))
print(int(9.0e18), int(-9.0e18), int(9223372036854774784.0), int(-9223372036854774784.0))
''',
    'keyword_shadowing': '''
x = 1e300


def f(x):
    return int(x)


def g():
    x = 1.5
    return int(x)


def outer():
    x = 1.5

    def inner():
        return int(x)
    return inner()

print(f(x=1.5), g(), outer())
''',
    'keyword_expressions_that_fit': '''
x = 1e300


def take(x):
    return int(x)

print(take(x=1e300 * 0))
print(take(x=1e300 - 1e300))
print(take(x=0.0 if True else 1e300))
print(int(x * 0), int(x - x))
''',
    'nonfinite': '''
def take(x):
    return int(x)

for value in (float("inf"), float("-inf")):
    try:
        take(x=value)
    except OverflowError as error:
        print(type(error).__name__)

def nan_take(x):
    return int(x)

try:
    nan_take(x=float("nan"))
except ValueError as error:
    print(type(error).__name__)
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatOutsideInt64(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_conversions_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
