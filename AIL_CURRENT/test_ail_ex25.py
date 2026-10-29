"""ex25: a normal build of a file that imports ail_ffi's `@export` decorator.

`@export` marks a function for the C library built by `--lib`, and on CPython it checks the
function's C signature and returns the function unchanged.  A normal `compile` therefore runs the
decorated function as an ordinary function.  The failure was that the general path refused every
decorator it did not know, so `language_examples/c_export/geometry.py` could not be compiled as a
program although CPython runs it and prints its demo line.  The decorator, including `@export()`,
an alias and `@ail_ffi.export`, is now a no-op on a non-method function; an invalid export
signature is still refused by name instead of being silently accepted.
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

HEADER = '''from dataclasses import dataclass
from ail_ffi import export as mark
import ail_ffi as ffi


@dataclass
class Point:
    x: int
    y: float


@mark
def add(a: int, b: int) -> int:
    return a + b


@mark()
def shout(text: str) -> str:
    return text.upper() + "!"


@ffi.export
def weight(p: Point) -> float:
    return p.x * p.y


print(add(2, 3), shout("hello"), weight(Point(2, 1.5)))
'''

MATCHING = {
    'alias_call_and_attribute': HEADER,
    'module_attribute_only': '''import ail_ffi

@ail_ffi.export
def double(x: int) -> int:
    return x * 2

print(double(21))
''',
    'import_without_use': '''from ail_ffi import export

print("unused import")
''',
    'extern_import_word_export': '''from dataclasses import dataclass
from ail_ffi import extern

@dataclass
class Point:
    x: int

print("export", Point(3).x)
''',
    'extern_call_word_export': '''from ail_ffi import extern, c_char_p, c_size_t

@extern(lib="c", header="string.h", symbol="strlen")
def c_strlen(s: c_char_p) -> c_size_t: ...

def main():
    print("export", c_strlen("abc"))

main()
''',
    'star_import_word_export': '''from dataclasses import dataclass
from ail_ffi import *

@dataclass
class Point:
    x: int

print("export", Point(4).x)
''',
}

INVALID = {
    'list_str_parameter': '''from ail_ffi import export

@export
def f(x: list[str]) -> int:
    return 1

print(f([]))
''',
    'default_parameter': '''from ail_ffi import export

@export
def f(x: int = 1) -> int:
    return x

print(f())
''',
    'missing_parameter_annotation': '''from ail_ffi import export

@export
def f(x) -> int:
    return 1

print(f(1))
''',
    'missing_result_annotation': '''from ail_ffi import export

@export
def f(x: int):
    return x

print(f(1))
''',
    'second_decorator': '''from functools import lru_cache
from ail_ffi import export

@export
@lru_cache
def f(x: int) -> int:
    return x

print(f(1))
''',
    'export_flag_introspection': '''from ail_ffi import export

@export
def f(x: int) -> int:
    return x

print(getattr(f, "__ail_export__", None))
''',
    'method': '''from ail_ffi import export

class C:
    @export
    def f(self, x: int) -> int:
        return x

print(C().f(1))
''',
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore',
               PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', ''))
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=env)
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


class ExportDecoratorTests(unittest.TestCase):
    def test_decorator_programs_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex25-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                       text, general)
                    self.assertEqual(built.returncode, 0,
                                     (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                         cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1],
                                     (slug, general, got.stderr[-800:]))

    def test_geometry_example_matches_cpython(self):
        text = GEOMETRY.read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory(prefix='ail-ex25-geometry-') as directory:
            want = cpython(directory, 'geometry', text)
            for general in (True, False):
                exe, built = build(directory, 'geometry_%s' % ('g' if general else 'd'),
                                   text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                     cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                 (general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want[1], (general, got.stderr[-800:]))

    def test_invalid_export_contract_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex25-invalid-') as directory:
            for slug, text in INVALID.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                     text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertTrue('unsupported type' in output or 'without defaults' in output
                                    or 'needs a type annotation' in output
                                    or 'annotate the result' in output
                                    or 'only @export' in output
                                    or 'reading __ail_export__' in output
                                    or 'the decorator on def' in output,
                                    (slug, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
