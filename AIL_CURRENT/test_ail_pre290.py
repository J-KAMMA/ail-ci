"""pre290: int() of an out-of-int64 float through a chain of wrapper calls.

The pre39 review left this pre-existing difference (its probe r23): a value outside int64 passed
through more than one wrapper that eventually reaches int() still compiled and stopped at run
time with `integer overflow`, while CPython prints the exact big integer.  Wrapper parameters are
now followed through any depth of module-level wrapper calls (including an identity wrapper and
keyword arguments), and the call site is refused by name.

Values that fit int64, non-finite floats, shadowed names and run-time-only values keep their
previous behaviour.  Programs are built with the general path forced and with the default build;
stdout and the exit status must match CPython.
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
    with tempfile.TemporaryDirectory(prefix='ail-pre290-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertIn('big integer', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre290-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'chain_two': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(1e300))
''',
    'chain_three': '''
def take(x):
    return int(x)


def middle(y):
    return take(y)


def outer(z):
    return middle(z)


print(outer(1e300))
''',
    'chain_keyword': '''
def take(x):
    return int(x)


def outer(y):
    return take(x=y)


print(outer(y=1e300))
''',
    'chain_mixed_keyword': '''
def take(x):
    return int(x)


def middle(y):
    return take(x=y)


def outer(z):
    return middle(y=z)


print(outer(z=1e300))
''',
    'chain_identity': '''
def identity(x):
    return x


def take(x):
    return int(x)


def outer(y):
    return take(identity(y))


print(outer(1e300))
''',
    'chain_list_item': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer([1e300][0]))
''',
    'chain_dict_value': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer({"v": 1e300}["v"]))
''',
    'chain_tuple_item': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer((1e300,)[0]))
''',
    'chain_negative': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(-1e300))
''',
    'chain_module_constant': '''
x = 1e300


def take(v):
    return int(v)


def outer(y):
    return take(y)


print(outer(x))
''',
    'chain_ifexp': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(1e300 if True else 0.0))
''',
    'chain_upper_boundary': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(1e19))
''',
}

MATCH = {
    'chain_in_range': '''
items = [1.9, -1.9, 9.0e18]
d = {"v": -9.0e18}


def take(x):
    return int(x)


def outer(y):
    return take(y)


class Box:
    def __init__(self, v):
        self.v = v


print(outer(1.9), outer(-1.9), outer(0.0), outer(-0.0))
print(outer(items[0]), outer(items[1]), outer(d["v"]))
print(outer(Box(2.9).v))
print(outer(9223372036854774784.0), outer(-9223372036854774784.0))
''',
    'chain_nonfinite': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


for value in (float("inf"), float("-inf")):
    try:
        outer(value)
    except OverflowError as error:
        print(type(error).__name__)


def nan_outer(y):
    return take(y)


try:
    nan_outer(float("nan"))
except ValueError as error:
    print(type(error).__name__)
''',
    'chain_unknown_key': '''
k: str = "a"
x = {None: 1e300, "a": 1.5}[k]


def take(v):
    return int(v)


def outer(y):
    return take(y)


print(outer(x))
''',
    'chain_shadowed_take': '''
def take(x):
    return int(x)


def outer(y):
    take = lambda v: 7
    return take(y)


print(outer(1e300))
''',
    'chain_other_conversions': '''
def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(2.9), int("42"), int(True), int(False), int(7))
''',
    'chain_aliases': '''
a = [1.9]
b = a
d = {"v": -1.9}


def take(x):
    return int(x)


def outer(y):
    return take(y)


print(outer(b[0]), outer(d["v"]))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatOutsideInt64WrapperChain(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_conversions_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
