"""ex43: `@export` is accepted by the ordinary Python-syntax compile path.

`language_examples/c_export/geometry.py` is one Python file with two readers: CPython runs it
directly, and `ail build --lib` turns its `@export` functions into a C library.  Building the
same file as an ordinary executable used to be refused by ``the decorator on def add`` because
the compile path only knew the FFI lowering: `@export` from `ail_ffi` is an identity at run
time (it validates the signature and returns the function), so it is now blanked like the
`from ail_ffi import ...` line, and geometry runs and prints exactly what CPython prints.

CPython's decorator also validates the signature.  A form this front end does not model is a
named compile-time refusal (defaults, *args/**kwargs, a missing annotation, a dataclass return,
a dataclass under ``from __future__ import annotations``, or another decorator), never a silent
difference.  Each program is built with the general path forced and with the default build.
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
    path = str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', '')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore', PYTHONPATH=path))


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


PROGRAMS = {
    'bare': '''
from ail_ffi import export


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def shout(text: str) -> str:
    return text.upper() + "!"


print(add(2, 3), shout("hello"))
''',
    'call_form': '''
from ail_ffi import export


@export()
def twice(n: int) -> int:
    return n * 2


print(twice(21))
''',
    'module_form': '''
import ail_ffi


@ail_ffi.export
def total(values: list[int]) -> int:
    t = 0
    for v in values:
        t += v
    return t


print(total([1, 2, 3, 4]))
''',
    'star_form': '''
from ail_ffi import *


@export
def negate(flag: bool) -> bool:
    return not flag


print(negate(False), negate(True))
''',
    'dataclass_and_none': '''
from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Point:
    x: int
    y: float
    visible: bool


@export
def weight(p: Point) -> float:
    if p.visible:
        return p.x * p.y
    return 0.0


@export
def count_up(n: int) -> None:
    for i in range(n):
        print(i)


print(weight(Point(2, 1.5, True)), weight(Point(2, 1.5, False)))
count_up(3)
''',
}

REFUSED = [
    ('defaults', '''
from ail_ffi import export


@export
def scale(x: float, k: int = 2) -> float:
    return x * k


print(scale(1.5))
''', 'plain parameters without defaults only'),
    ('missing_annotation', '''
from ail_ffi import export


@export
def f(x) -> int:
    return 1


print(f(1))
''', '@export f: parameter x needs one of'),
    ('dataclass_result', '''
from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Point:
    x: int
    y: float


@export
def make(x: int) -> Point:
    return Point(x, 1.0)


print(make(3))
''', '@export make: the result must be'),
    ('future_dataclass_parameter', '''
from __future__ import annotations
from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Point:
    x: int
    y: float


@export
def weight(p: Point) -> float:
    return p.x * p.y


print(weight(Point(2, 1.5)))
''', '@export weight: parameter p needs one of'),
    ('other_decorator', '''
from ail_ffi import export
from functools import lru_cache


@export
@lru_cache
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


print(fib(10))
''', '@export fib: no other decorator'),
]


class Ex43Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-ex43-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_export_programs_match_cpython(self):
        for name, text in PROGRAMS.items():
            with self.subTest(name=name):
                self.check(name, text)

    def test_geometry_example_matches_cpython(self):
        self.check('geometry', (ROOT / 'language_examples' / 'c_export' / 'geometry.py').read_text(encoding='utf-8'))

    def test_invalid_export_is_refused_by_name(self):
        for name, text, needle in REFUSED:
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='ail-ex43-ref-') as directory:
                for general in (True, False):
                    exe, built = build(directory, name, text, general)
                    self.assertNotEqual(built.returncode, 0, (name, general, built.stdout))
                    self.assertIn(needle, built.stdout + built.stderr, (name, general, built.stdout + built.stderr))


if __name__ == '__main__':
    unittest.main()
