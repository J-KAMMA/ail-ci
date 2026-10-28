"""pre393: int() of an out-of-int64 default argument is refused by name.

The pre370 review recorded as pre-existing (its probe r09) that ``def f(x=1e300): return
int(x)`` followed by ``print(f())`` compiled and then stopped at run time with ``integer
overflow``, where CPython prints the big integer.  The wrapper check followed a value passed
at the call site but ignored the parameter default when the call omitted it; it now falls back
to the default expression.  The same fallback exposed a constant string outside int64 through
a wrapper, which now gets the direct ``int()`` conversion refusal instead of a run-time stop.

An in-range default, an in-range argument that overrides the default, a dead function and a
non-int read keep CPython's result.  Programs are built with the general path forced and with
the default build; stdout and the exit status must match CPython.
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

REFUSALS = ('int() of a float outside int64',
            'int64 constant expression out of range')


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
    with tempfile.TemporaryDirectory(prefix='ail-pre393-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertTrue(any(phrase in message for phrase in REFUSALS),
                            (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre393-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'default_float': '''
def f(x=1e300):
    return int(x)


print(f())
''',
    'default_kwonly': '''
def f(*, x=1e300):
    return int(x)


print(f())
''',
    'default_second_positional': '''
def f(a=0, x=1e300):
    return a + int(x)


print(f(0))
''',
    'default_negative': '''
def f(x=-1e300):
    return int(x)


print(f())
''',
    'default_module_constant': '''
K = 1e300


def f(x=K):
    return int(x)


print(f())
''',
    'default_list_item': '''
M = [1e300]


def f(x=M[0]):
    return int(x)


print(f())
''',
    'default_dict_value': '''
D = {"k": 1e300}


def f(x=D["k"]):
    return int(x)


print(f())
''',
    'default_attribute': '''
class C:
    v = 1e300


def f(x=C.v):
    return int(x)


print(f())
''',
    'default_string': '''
def f(x="9223372036854775808"):
    return int(x)


print(f())
''',
    'default_chain': '''
def take(x):
    return int(x)


def outer(y=-1e300):
    return take(y)


print(outer())
''',
    'argument_string': '''
def f(x):
    return int(x)


print(f("9223372036854775808"))
''',
}

MATCH = {
    'argument_overrides_default': '''
def f(x=1e300):
    return int(x)


print(f(1))
print(f(x=2))
''',
    'dead_function': '''
def f(x=1e300):
    return int(x)


print("ok")
''',
    'in_range_default': '''
def f(x=1.5):
    return int(x)


print(f())
print(f(2.9))
''',
    'in_range_boundary': '''
def f(x=9.2e18):
    return int(x)


print(f())
''',
    'non_int_read': '''
def f(x=1e300):
    return x


print(f())
''',
    'in_range_string': '''
def f(x="123"):
    return int(x)


print(f())
print(f("-45"))
''',
    'starred_argument': '''
def f(x=1e300):
    return int(x)


print(f(*[1]))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatOutsideInt64Default(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_matching_programs_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
