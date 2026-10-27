"""pre389: int() of an out-of-int64 float carried by a function parameter default.

The pre373 review recorded as pre-existing its p12, a function-with-defaults program.  A
module function whose parameter defaults to an out-of-int64 float, and whose every call
omits that parameter, compiled on both builds and then stopped with ``integer overflow``
where CPython prints the exact big integer: the int64 checker only looked at arguments a
call supplied, never at the default the callee then used.  A default that is a literal
(or a module constant assigned earlier) is now folded into the function's constant scope,
so ``int()`` of it is refused by name; the same holds for a flat list/tuple/dict default
read through a constant subscript.  A call that supplies the parameter, a body that
rebinds it, a container that escapes in the body, a callee reached through an alias or
``*args``/``**kwargs``, and defaults that name a module container keep their pre-existing
behaviour.  Generated C is unchanged for every program that still compiles.
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
    with tempfile.TemporaryDirectory(prefix='ail-pre389-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertIn('big integer', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre389-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'literal_scalar': '''
def f(a=1e300):
    return int(a)


print(f())
''',
    'keyword_only': '''
def f(*, a=1e300):
    return int(a)


print(f())
''',
    'negative_default': '''
def f(a=-1e300):
    return int(a)


print(f())
''',
    'list_default': '''
def f(a=[1e300]):
    return int(a[0])


print(f())
''',
    'dict_default': '''
def f(a={"k": 1e300}):
    return int(a["k"])


print(f())
''',
    'tuple_default': '''
def f(a=(1.5, 1e300)):
    return int(a[1])


print(f())
''',
    'keyword_call_omits': '''
def f(a=1e300, b=2):
    return int(a) + b


print(f(b=3))
''',
    'call_inside_function': '''
def f(a=1e300):
    return int(a)


def g():
    return f()


print(g())
''',
    'boundary': '''
def f(a=9.3e18):
    return int(a)


print(f())
''',
    'module_constant_name': '''
D = 1e300


def f(a=D):
    return int(a)


print(f())
''',
    'module_constant_chain': '''
BASE = 1e300
D = BASE


def f(a=D):
    return int(a)


print(f())
''',
}

MATCH = {
    'in_range': '''
def f(a=1.5):
    return int(a)


print(f())
''',
    'explicit_override': '''
def f(a=1e300):
    return int(a)


print(f(2.5))
''',
    'mutated_container': '''
def f(a=[1e300]):
    a[0] = 2.5
    return int(a[0])


print(f())
''',
    'rebound_parameter': '''
def f(a=1e300):
    a = 2.5
    return int(a)


print(f())
''',
    'shadowed_callee': '''
def f(a=1e300):
    return int(a)


def g():
    f = lambda: 0
    return f()


print(g())
''',
    'star_call_in_range': '''
def f(a=1.5):
    return int(a)


print(f(*()))
''',
    'keyword_override': '''
def f(*, a=1e300):
    return int(a)


print(f(a=2.5))
''',
    'in_range_container': '''
def f(a=[1.5, 2.5]):
    return int(a[1])


print(f())
''',
    'no_defaults': '''
items = [1, 2, 3]
print(sum(items), int(2.9))
''',
    'method_default': '''
class C:
    def f(self, a=[1.5]):
        return int(a[0])


print(C().f())
''',
    'argument_supplied': '''
def f(a=1e300):
    return int(a)


def g():
    return int(f(3.5))


print(g())
''',
    'shared_default_mutated_elsewhere': '''
items = [1e300]


def f(a=items):
    a[0] = 1.5


f()
print(int(items[0]))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class DefaultParameterIntFloat(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_other_routes_match_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
