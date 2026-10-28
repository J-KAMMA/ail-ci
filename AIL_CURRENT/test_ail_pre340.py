"""pre340: int() of a float outside int64 stored through a constructor parameter.

The pre333 review recorded as pre-existing that ``int(Box(1e300).v)``, where ``__init__``
stores its parameter directly, overflowed on both builds while CPython prints the exact big
integer.  The class-attribute fold now binds a constructor call to its ``__init__`` parameters,
so this route (and the same value through a keyword argument, a default, a module constant, a
local instance, an alias, a list item, a dict value, a function argument or a wrapper) builds on
both builds and matches CPython under exact ints (it was refused for the int64 era).  In-range attributes, dynamic values and a later field store still match
CPython.
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


def cpython_last_line(directory, name, text):
    src = Path(directory) / (name + '_cpython_full.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    lines = done.stderr.decode('utf-8', 'replace').strip().splitlines()
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, (lines[-1] if lines else '')


def check_exact(test, name, text):
    """Exact ints: a value beyond int64 builds on both builds and matches CPython's stdout, exit code
    and last stderr line."""
    with tempfile.TemporaryDirectory(prefix='ail-pre340-') as directory:
        want = cpython_last_line(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, (name, general, (built.stdout + built.stderr)[-1200:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            err = got.stderr.decode('utf-8', 'replace')
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, err[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, err[-800:]))
            if want[2]:
                test.assertIn(want[2], err, (name, general))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre340-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'direct': '''
class Box:
    def __init__(self, v):
        self.v = v

print(int(Box(1e300).v))
''',
    'negative': '''
class Box:
    def __init__(self, v):
        self.v = v

print(int(Box(-1e300).v))
''',
    'keyword': '''
class Box:
    def __init__(self, v):
        self.v = v

print(int(Box(v=1e300).v))
''',
    'default': '''
class Box:
    def __init__(self, v=1e300):
        self.v = v

print(int(Box().v))
''',
    'second_positional': '''
class Box:
    def __init__(self, tag, v):
        self.v = v

print(int(Box("x", 1e300).v))
''',
    'module_constant_argument': '''
V = 1e300


class Box:
    def __init__(self, v):
        self.v = v

print(int(Box(V).v))
''',
    'list_item_argument': '''
class Box:
    def __init__(self, v):
        self.v = v

xs = [1e300]
print(int(Box(xs[0]).v))
''',
    'instance_name': '''
class Box:
    def __init__(self, v):
        self.v = v

b = Box(1e300)
print(int(b.v))
''',
    'alias': '''
class Box:
    def __init__(self, v):
        self.v = v

b = Box(1e300)
c = b
print(int(c.v))
''',
    'list_instance': '''
class Box:
    def __init__(self, v):
        self.v = v

items = [Box(1e300)]
print(int(items[0].v))
''',
    'dict_instance': '''
class Box:
    def __init__(self, v):
        self.v = v

items = {"b": Box(1e300)}
print(int(items["b"].v))
''',
    'through_argument': '''
class Box:
    def __init__(self, v):
        self.v = v


def f(x):
    return int(Box(x).v)

print(f(1e300))
''',
    'through_wrapper': '''
class Box:
    def __init__(self, v):
        self.v = v


def f(x):
    return int(Box(x).v)


def g(y):
    return f(y)

print(g(1e300))
''',
}

MATCH = {
    'in_range': '''
class Box:
    def __init__(self, v):
        self.v = v

print(int(Box(5).v), int(Box(-5).v), int(Box(1.5).v), int(Box(9.0e18).v))
''',
    'literal_attribute': '''
class Box:
    v = 1.5

print(int(Box().v), int(Box.v))
''',
    'mutated_after_construction': '''
class Box:
    def __init__(self, v):
        self.v = v

b = Box(1e300)
b.v = 1.5
print(int(b.v))
''',
    'dynamic_value': '''
class Box:
    def __init__(self, v):
        self.v = v


def make(v):
    b = Box(v)
    return int(b.v)

print(make(5.0))
''',
    'wrapper_in_range': '''
class Box:
    def __init__(self, v):
        self.v = v


def f(x):
    return int(Box(x).v)

print(f(5.0))
''',
    'non_conversion_use': '''
class Box:
    def __init__(self, v):
        self.v = v

b = Box(1e300)
print(b.v > 1.0, type(b.v).__name__)
''',
    'mutated_default': '''
class Box:
    def __init__(self, v=1e300):
        self.v = v

b = Box()
b.v = 1.5
print(int(b.v))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatConstructorAttributeOutsideInt64(unittest.TestCase):
    def test_values_beyond_int64_build_on_both_builds_and_match_cpython(self):
        for name, text in sorted(REFUSED.items()):
            check_exact(self, 'big_' + name, text)

    def test_conversions_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
