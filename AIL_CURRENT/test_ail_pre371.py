"""pre371: an annotated ``self.attr: T = v`` constructor store is folded.

The pre357 review recorded as pre-existing that ``int(Box(1e300).v)``, where
``__init__`` stores its parameter with an annotation (``self.v: float = v``), overflowed on
both builds while CPython prints the exact big integer.  The constructor fold only collected
plain ``self.attr = value`` statements, so the annotated store left the attribute unknown and
the conversion ran at run time.  Annotated stores with a value are now collected like plain
ones; an annotation without a value is not a store and is still ignored.  The conversion is
refused by name through a keyword, a default, a second positional parameter, a module
constant, a list item, a dict value, a class attribute, an instance alias, a list/dict item,
a function argument and a wrapper.  In-range values, a later field store, a dynamic value, a
non-conversion read and an annotation-only store still match CPython.
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


def check_refused(test, name, text, message='int() of a float outside int64'):
    with tempfile.TemporaryDirectory(prefix='ail-pre371-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            output = built.stdout + built.stderr
            test.assertIn(message, output, (name, general, output[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre371-') as directory:
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
        self.v: float = v

print(int(Box(1e300).v))
''',
    'negative': '''
class Box:
    def __init__(self, v):
        self.v: float = v

print(int(Box(-1e300).v))
''',
    'keyword': '''
class Box:
    def __init__(self, v):
        self.v: float = v

print(int(Box(v=1e300).v))
''',
    'second_positional': '''
class Box:
    def __init__(self, tag, v):
        self.v: float = v

print(int(Box("x", 1e300).v))
''',
    'default': '''
class Box:
    def __init__(self, v=1e300):
        self.v: float = v

print(int(Box().v))
''',
    'module_constant': '''
BIG = 1e300


class Box:
    def __init__(self, v):
        self.v: float = v

print(int(Box(BIG).v))
''',
    'list_item': '''
XS = [1e300]


class Box:
    def __init__(self, v):
        self.v: float = v

print(int(Box(XS[0]).v))
''',
    'dict_value': '''
D = {"k": 1e300}


class Box:
    def __init__(self, v):
        self.v: float = v

print(int(Box(D["k"]).v))
''',
    'class_attribute': '''
class Config:
    big = 1e300


class Box:
    def __init__(self, v):
        self.v: float = v

print(int(Box(Config.big).v))
''',
    'alias': '''
class Box:
    def __init__(self, v):
        self.v: float = v


b = Box(1e300)
a = b
print(int(a.v))
''',
    'list_instance': '''
class Box:
    def __init__(self, v):
        self.v: float = v


items = [Box(1e300)]
print(int(items[0].v))
''',
    'dict_instance': '''
class Box:
    def __init__(self, v):
        self.v: float = v


items = {"b": Box(1e300)}
print(int(items["b"].v))
''',
    'through_argument': '''
class Box:
    def __init__(self, v):
        self.v: float = v


def f(x):
    return int(Box(x).v)

print(f(1e300))
''',
    'through_wrapper': '''
class Box:
    def __init__(self, v):
        self.v: float = v


def f(x):
    return int(Box(x).v)


def g(y):
    return f(y)

print(g(1e300))
''',
    'string_annotation': '''
class Box:
    def __init__(self, v):
        self.v: "float" = v

print(int(Box(1e300).v))
''',
}

REFUSED_CONVERSION = {
    'bigint_string': '''
class Box:
    def __init__(self, v):
        self.v: str = v

print(int(Box("9223372036854775808").v))
''',
}

MATCH = {
    'in_range': '''
class Box:
    def __init__(self, v):
        self.v: float = v

print(int(Box(5).v), int(Box(-5).v), int(Box(1.5).v), int(Box(9.0e18).v))
''',
    'keyword_in_range': '''
class Box:
    def __init__(self, v):
        self.v: float = v

print(int(Box(v=5).v), int(Box(v=-1.5).v))
''',
    'default_in_range': '''
class Box:
    def __init__(self, v=5):
        self.v: float = v

print(int(Box().v), int(Box(7).v), int(Box(v=1.25).v))
''',
    'dynamic_value': '''
class Box:
    def __init__(self, v):
        self.v: float = v


def make():
    return 5.0

print(int(Box(make()).v))
''',
    'mutated_after_construction': '''
class Box:
    def __init__(self, v):
        self.v: float = v


b = Box(1e300)
b.v = 1.5
print(int(b.v))
''',
    'non_conversion_use': '''
class Box:
    def __init__(self, v):
        self.v: float = v


b = Box(1e300)
print(b.v > 1.0, type(b.v).__name__)
''',
    'string_in_range': '''
class Box:
    def __init__(self, v):
        self.v: str = v

print(int(Box("42").v), int(Box("-7").v))
''',
    'int_boundary': '''
class Box:
    def __init__(self, v):
        self.v = v

print(int(Box(9223372036854775807).v))
''',
    'annotation_then_store': '''
class Box:
    def __init__(self, v):
        self.v: float
        self.v = v

print(int(Box(5).v))
''',
    'bool_values': '''
class Box:
    def __init__(self, v):
        self.v: float = v

print(int(Box(True).v), int(Box(False).v))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class AnnotatedConstructorAttributeOutsideInt64(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_big_integer_string_refused_by_name(self):
        for name, text in sorted(REFUSED_CONVERSION.items()):
            check_refused(self, 'reflect_' + name, text, 'int64 constant expression out of range')

    def test_conversions_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
