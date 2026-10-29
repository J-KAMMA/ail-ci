"""fz201: an int ``**`` whose result leaves int64 stays exact instead of stopping at run time.

The daily fuzzer (seed 2075507942) found a program where ``assert v ** 3 == v`` ran on
``v = 850360125720``: CPython raises AssertionError (the handler prints -60), while the typed
path computed the power in int64 and stopped with ``integer overflow`` instead, skipping the
handler.  The local proof that should send such a program to the exact general path did see the
power, but ``_lp_reason`` returned the FIRST failure it met and a later benign one (``abs()`` of
a proven float, which can never need a big int) hid the power.  The IR build now asks for an int
failure when there is one, so the program takes the general path; the power follows CPython
through an argument, a list item, an attribute, a dict value and a call result as well.
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
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-fz201-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


PROGRAMS = {
    'fuzzer_min': '''
v10 = 850360125720
try:
    assert v10 ** 3 == v10, "boom"
except AssertionError:
    print(-60)
print(abs(1.5))
''',
    'function_local': '''
def f():
    v = 850360125720
    try:
        assert v ** 3 == v, "boom"
    except AssertionError:
        print(-60)
    print(abs(1.5))
f()
''',
    'module_alias': '''
x = 850360125720
y = x
try:
    assert y ** 3 == y, "boom"
except AssertionError:
    print(-60)
print(abs(1.5))
''',
    'argument': '''
def f(v):
    try:
        assert v ** 3 == v, "boom"
    except AssertionError:
        print(-60)
    print(abs(1.5))
f(850360125720)
''',
    'list_item': '''
def f(xs):
    try:
        assert xs[0] ** 3 == xs[0], "boom"
    except AssertionError:
        print(-60)
    print(abs(1.5))
f([850360125720])
''',
    'attribute': '''
class Box:
    def __init__(self, v):
        self.v = v
def f(b):
    try:
        assert b.v ** 3 == b.v, "boom"
    except AssertionError:
        print(-60)
    print(abs(1.5))
f(Box(850360125720))
''',
    'dict_value': '''
def f(d):
    try:
        assert d['k'] ** 3 == d['k'], "boom"
    except AssertionError:
        print(-60)
    print(abs(1.5))
f({'k': 850360125720})
''',
    'call_result': '''
def f(v):
    return int(v)
try:
    assert f("850360125720") ** 3 == f("850360125720"), "boom"
except AssertionError:
    print(-60)
print(abs(1.5))
''',
    'negative_base': '''
v = -850360125720
try:
    assert v ** 5 == v, "boom"
except AssertionError:
    print(-60)
print(abs(1.5))
''',
    'float_exponent': '''
v = 850360125720
try:
    assert v ** 3.0 == v, "boom"
except AssertionError:
    print(-60)
print(abs(1.5))
''',
    'negative_exponent': '''
v = 10
try:
    assert v ** -1 == v, "boom"
except AssertionError:
    print(-60)
print(abs(1.5))
''',
    'in_range': '''
v = 1000
try:
    assert v ** 3 != v, "boom"
except AssertionError:
    print(-60)
print(abs(1.5))
''',
    'safe_base': '''
for v in (0, 1, -1):
    try:
        assert v ** 1000 == v, "boom"
    except AssertionError:
        print(-60)
print(abs(1.5))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntPowerBeyondInt64(unittest.TestCase):
    def test_power_is_exact(self):
        for name, text in sorted(PROGRAMS.items()):
            with self.subTest(name):
                check_program(self, name, text)


if __name__ == '__main__':
    unittest.main()
