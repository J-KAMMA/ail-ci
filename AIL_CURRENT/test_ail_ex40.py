"""ex40: a Python-syntax example with `@export` builds as an ordinary program, like CPython.

`language_examples/c_export/geometry.py` is both the source of `libgeometry` (`ail build --lib`) and an
ordinary Python program (`python3 geometry.py`).  Compiling it directly used to stop with
``the decorator on def add (... only @staticmethod ..., @functools.lru_cache ...)`` because
`@export` is a marker for the C-library front end, not a run-time decorator in AIL.  The FFI lowering
now removes `@export` from a top-level function whose annotations CPython's `ail_ffi.export` accepts,
and refuses every other shape by name.  Both builds print what CPython prints, and a program that
does not use `@export` is unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
GEOMETRY = ROOT / 'language_examples' / 'c_export' / 'geometry.py'
MESSAGE = '@export marks a top-level function'

BARE = '''from ail_ffi import export


@export
def add(a: int, b: int) -> int:
    return a + b


print(add(2, 3))
'''

CALLED = '''from ail_ffi import export


@export()
def double(x: int) -> int:
    return x * 2


print(double(4))
'''

MODULE = '''import ail_ffi


@ail_ffi.export
def negate(x: int) -> int:
    return -x


print(negate(5))
'''

TYPES = '''from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Point:
    x: int
    y: float
    visible: bool


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def real(x: float) -> float:
    return x * 2.5


@export
def flag(x: bool) -> bool:
    return not x


@export
def text(s: str) -> str:
    return s.upper() + '!'


@export
def blob(data: bytes) -> bytes:
    return data[::-1]


@export
def ints(values: list[int]) -> list[int]:
    return [v + 1 for v in values]


@export
def floats(values: list[float]) -> list[float]:
    return [v / 2.0 for v in values]


@export
def weight(p: Point) -> float:
    return p.x * p.y if p.visible else 0.0


@export
def nothing(n: int) -> None:
    if n < 0:
        raise ValueError('negative')


print(add(2, 3), real(0.0), flag(True), text('hi'), blob(b'abc'))
print(ints([]), ints([1, -2]), floats([0.0, 1.5]), weight(Point(2, 1.5, True)))
print(add(-7, 4), real(-1.0), flag(False), text(''), blob(b''), floats([]))
try:
    nothing(-1)
except ValueError as error:
    print('caught', error)
nothing(1)
'''

SHADOW = '''from ail_ffi import export


def export(fn):
    def wrapper(x: int) -> int:
        return fn(x) + 1

    return wrapper


@export
def f(x: int) -> int:
    return x


print(f(2))
'''

NO_EXPORT = '''from ail_ffi import c_int, extern


def add(a: int, b: int) -> int:
    return a + b


print(add(20, 22))
'''

REFUSED = {
    'export_argument': '''from ail_ffi import export


@export(1)
def f(x: int) -> int:
    return x


print(f(1))
''',
    'export_default': '''from ail_ffi import export


@export
def f(x: int = 1) -> int:
    return x


print(f())
''',
    'export_unannotated': '''from ail_ffi import export


@export
def f(x):
    return x


print(f(1))
''',
    'export_class': '''from ail_ffi import export


@export
class C:
    pass


print(C)
''',
    'export_nested': '''from ail_ffi import export


def outer():
    @export
    def inner(x: int) -> int:
        return x

    return inner


print(outer()(1))
''',
    'export_dict_annotation': '''from ail_ffi import export


@export
def f(x: dict) -> int:
    return len(x)


print(f({'a': 1}))
''',
    'export_dataclass_result': '''from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Point:
    x: int


@export
def f() -> Point:
    return Point(1)


print(f())
''',
    'export_bad_dataclass_field': '''from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Bad:
    text: str


@export
def f(b: Bad) -> int:
    return len(b.text)


print(f(Bad('x')))
''',
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1', PYTHONWARNINGS='ignore')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120, env=env)
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class Ex40Tests(unittest.TestCase):
    def test_export_examples_match_cpython(self):
        cases = {
            'bare': BARE,
            'called': CALLED,
            'module': MODULE,
            'types': TYPES,
            'geometry': GEOMETRY.read_text(encoding='utf-8'),
            'no_export': NO_EXPORT,
        }
        with tempfile.TemporaryDirectory(prefix='ail-ex40-') as directory:
            for slug, text in cases.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_invalid_export_shapes_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex40-refused-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertIn(MESSAGE, output, (slug, general, output[-1200:]))

    def test_a_user_defined_export_is_not_the_marker(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex40-shadow-') as directory:
            for general in (True, False):
                _, built = build(directory, 'shadow_%s' % ('g' if general else 'd'), SHADOW, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, (general, output[-1200:]))
                self.assertIn('the decorator on def f', output, (general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
