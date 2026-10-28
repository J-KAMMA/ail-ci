"""Pre391: an augmented power whose base is a known binding is refused by name.

A reviewer of pre372 recorded as pre-existing that ``x = 10; print("hello"); x **= 40`` traps
with ``integer overflow`` on both builds where CPython prints the exact bignum.  The
constant-power checks only treat a name as known when it is stored once, and the augmented
target is itself a store, so the binding never reached them.  When the only other binding is
one plain module/function-level assignment with a known int value, and nothing in the program
can rebind the name (another store, ``global``/``nonlocal``, a parameter, import, definition,
handler or match capture), the base at the augmented statement is that value; a call in
between cannot change a name no code assigns.  A constant exponent whose exact result leaves
int64 is refused by name on both builds.  In-range powers, bases -1/0/1, negative or float
exponents, a later rebinding and a genuinely rebindable name keep their CPython behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


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
    with tempfile.TemporaryDirectory(prefix='ail-pre391-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int64 constant expression out of range', message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre391-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'recorded_call': '''
x = 10
print("hello")
x **= 40
print(x)
''',
    'no_call': '''
x = 10
x **= 40
print(x)
''',
    'function_call': '''
def f():
    x = 10
    print("hello")
    x **= 40
    print(x)


f()
''',
    'negative_base': '''
x = -10
print("hello")
x **= 39
print(x)
''',
    'computed_exponent': '''
x = 10
n = 40
print("hello")
x **= n
print(x)
''',
    'alias_binding': '''
y = 10
x = y
print("hello")
x **= 40
print(x)
''',
    'annassign': '''
x: int = 10
print("hello")
x **= 40
print(x)
''',
    'two_to_63': '''
x = 2
x **= 63
print(x)
''',
}

MATCH = {
    'global_rebind': '''
x = 2


def bump():
    global x
    x = 3


bump()
x **= 3
print(x)
''',
    'zero_then_power': '''
x = 10
x **= 0
print(x ** 40)
''',
    'boundaries': '''
x = 2
x **= 62
print(x)
y = -2
y **= 63
print(y)
a = 1
a **= 100000
print(a)
b = -1
b **= 100001
print(b)
c = 0
c **= 100000
print(c)
f = 10.0
f **= 40
print(f)
n = 10
n **= -1
print(n)
''',
    'rebind_after': '''
x = 10
x **= 2
print(x)
x = 1
print(x ** 40)
''',
    'min_boundary': '''
x = -2
x **= 63
print(x)
''',
    'loop_in_range': '''
x = 3
for i in range(2):
    x **= 2
print(x)
''',
    'param_elsewhere': '''
def g(x):
    return x


x = 10
print("hello")
x **= 2
print(x)
''',
}


class Pre391Tests(unittest.TestCase):
    def test_known_augmented_base_out_of_int64_is_refused(self):
        for slug, text in REFUSED.items():
            with self.subTest(case=slug):
                check_refused(self, slug, text)

    def test_in_range_and_rebindable_routes_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
