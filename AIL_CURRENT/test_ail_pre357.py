"""pre357: int() of a float outside int64 through a ``*args`` constructor is refused.

The pre340 review recorded as pre-existing that ``int(Box(1e300, 2).v)``, where
``__init__(self, v, *rest)`` stores its parameter directly, overflowed on both builds while
CPython prints the exact big integer.  Constructor binding skipped every call with more
positional arguments than named parameters; it now accepts the surplus when ``__init__`` has
``*args``.  The route is refused by name through a keyword, a default, a second positional
parameter, a module constant, a list item, a dict value, a class attribute, an instance, an
alias, a list/dict item, a function argument or a wrapper.  In-range values, surplus argument
types, a starred call, a later field store and non-conversion reads still match CPython.
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
    and last stderr line (the int64-era tests refused these programs by name)."""
    with tempfile.TemporaryDirectory(prefix='ail-pre357-') as directory:
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


def check_refused(test, name, text, message='int() of a float outside int64'):
    with tempfile.TemporaryDirectory(prefix='ail-pre357-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            output = built.stdout + built.stderr
            test.assertIn(message, output, (name, general, output[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre357-') as directory:
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
    def __init__(self, v, *rest):
        self.v = v

print(int(Box(1e300, 2).v))
''',
    'negative': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box(-1e300, 2).v))
''',
    'keyword': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box(v=1e300).v))
''',
    'second_positional': '''
class Box:
    def __init__(self, tag, v, *rest):
        self.v = v

print(int(Box("x", 1e300, 3).v))
''',
    'default': '''
class Box:
    def __init__(self, v=1e300, *rest):
        self.v = v

print(int(Box().v))
''',
    'many_surplus': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box(1e300, 2, 3, "x", [4], 5.5).v))
''',
    'module_constant_argument': '''
V = 1e300


class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box(V, 2).v))
''',
    'list_item_argument': '''
XS = [1e300]


class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box(XS[0], 2).v))
''',
    'dict_value_argument': '''
D = {"k": 1e300}


class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box(D["k"], 2).v))
''',
    'class_attribute_argument': '''
class C:
    V = 1e300


class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box(C.V, 2).v))
''',
    'instance_name': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

b = Box(1e300, 2)
print(int(b.v))
''',
    'alias': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

b = Box(1e300, 2)
c = b
print(int(c.v))
''',
    'list_instance': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

items = [Box(1e300, 2)]
print(int(items[0].v))
''',
    'dict_instance': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

items = {"b": Box(1e300, 2)}
print(int(items["b"].v))
''',
    'through_argument': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v


def f(x):
    return int(Box(x, 2).v)

print(f(1e300))
''',
    'through_wrapper': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v


def f(x):
    return int(Box(x, 2).v)


def g(y):
    return f(y)

print(g(1e300))
''',
}

REFUSED_CONVERSION = {
    'bigint_string': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box("9223372036854775808", 2).v))
''',
}

MATCH = {
    'in_range': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box(5, 2).v), int(Box(-5, "x").v), int(Box(1.5, [1]).v), int(Box(9.0e18, {}).v))
''',
    'keyword_in_range': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box(v=5).v), int(Box(v=-1.5).v))
''',
    'default_in_range': '''
class Box:
    def __init__(self, v=5, *rest):
        self.v = v

print(int(Box().v), int(Box(7).v), int(Box(8, 9).v), int(Box(v=1.25).v))
''',
    'starred_in_range': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

xs = [5, 2]
print(int(Box(*xs).v))
''',
    'second_positional_in_range': '''
class Box:
    def __init__(self, tag, v, *rest):
        self.v = v

print(int(Box("x", 5, 3).v), int(Box(v=6, tag="y").v))
''',
    'surplus_types': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v
        self.rest = rest

b = Box(1.5, "a", [1, 2], {"k": 3}, None, True, 2.5)
print(int(b.v), b.rest)
''',
    'mutated_after_construction': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

b = Box(1e300, 2)
b.v = 1.5
print(int(b.v))
''',
    'dynamic_value': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v


def make():
    return 5.0

print(int(Box(make(), 2).v))
''',
    'non_conversion_use': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

b = Box(1e300, 2)
print(b.v > 1.0, type(b.v).__name__)
''',
    'string_in_range': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v

print(int(Box("42", 2).v), int(Box("-7", 2).v))
''',
    'empty_rest': '''
class Box:
    def __init__(self, v, *rest):
        self.v = v
        self.rest = rest

a = Box(1.5)
b = Box(2.5, "x")
print(int(a.v), a.rest, int(b.v), b.rest)
''',
    'kwonly_vararg': '''
class Box:
    def __init__(self, v, *rest, k=2):
        self.v = v

print(int(Box(1.5, 3, k=9).v), int(Box(v=2.5).v))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class StarArgsConstructorAttributeOutsideInt64(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_exact(self, 'refuse_' + name, text)

    def test_big_integer_string_refused_by_name(self):
        for name, text in sorted(REFUSED_CONVERSION.items()):
            check_exact(self, 'reflect_' + name, text)

    def test_conversions_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
