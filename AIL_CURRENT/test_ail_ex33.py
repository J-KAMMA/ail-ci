"""ex33: a plain build accepts the @export marker of a language_examples Python program.

``language_examples/c_export/geometry.py`` is the reference program for the C-library export
feature.  ``ail build --lib`` reads its ``@export`` functions, but ``ail compile`` refused the
decorator outright, so the same file could not be built as the ordinary program its
``if __name__ == "__main__":`` block describes.  A plain build now checks the decorator's CPython
contract (annotation kinds, no defaults, a result annotation) and then drops the marker; the
function and the rest of the file compile normally on the typed and the general path.  Marker
reads (``f.__ail_export__``) and ``exports()`` remain refused by name because a plain executable
does not keep the CPython registry.
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


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore', PYTHONPATH=str(ROOT))
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


MATCHING = {
    'basic': '''from ail_ffi import export

@export
def add(a: int, b: int) -> int:
    return a + b

@export
def shout(text: str) -> str:
    return text.upper() + "!"

print(add(2, 3), shout("hi"))
''',
    'none_result': '''from ail_ffi import export

@export
def note(n: int) -> None:
    print("note", n)

note(7)
print("done")
''',
    'called': '''from ail_ffi import export

@export()
def double(n: int) -> int:
    return n * 2

print(double(21))
''',
    'module_attribute': '''import ail_ffi

@ail_ffi.export
def half(x: float) -> float:
    return x / 2.0

print(half(5.0))
''',
    'dataclass_parameter': '''from dataclasses import dataclass
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

print(weight(Point(2, 1.5, True)))
''',
    'numeric_list': '''from ail_ffi import export

@export
def squares(values: list[int]) -> list[int]:
    out = []
    for v in values:
        out.append(v * v)
    return out

print(squares([1, 2, 3]))
''',
    'lru_cache': '''from functools import lru_cache
from ail_ffi import export

@lru_cache
@export
def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)

print(fib(10))
''',
    'nested_function': '''from ail_ffi import export

def outer(n: int) -> int:
    @export
    def inner(x: int) -> int:
        return x + 1
    return inner(n)

print(outer(4))
''',
    'future_scalar': '''from __future__ import annotations
from ail_ffi import export

@export
def add(a: int, b: float) -> float:
    return a + b

print(add(2, 1.5))
''',
}

REFUSED = {
    'invalid_type': ('from ail_ffi import export\n\n@export\ndef bad(x: dict) -> int:\n    return 1\n\nprint(bad({}))\n',
                     'parameter x needs'),
    'default': ('from ail_ffi import export\n\n@export\ndef bad(x: int = 1) -> int:\n    return x\n\nprint(bad())\n',
                'plain parameters without defaults'),
    'no_result': ('from ail_ffi import export\n\n@export\ndef bad(x: int):\n    return x\n\nprint(bad(1))\n',
                  'needs a result annotation'),
    'star_args': ('from ail_ffi import export\n\n@export\ndef bad(*xs: int) -> int:\n    return len(xs)\n\nprint(bad(1, 2))\n',
                  'plain parameters without defaults'),
    'invalid_dataclass': ('''from dataclasses import dataclass
from ail_ffi import export

@dataclass
class Bad:
    name: str

@export
def take(x: Bad) -> int:
    return 1

print(take(Bad("a")))
''', 'parameter x needs'),
    'marker_read': ('from ail_ffi import export\n\n@export\ndef f(x: int) -> int:\n    return x\n\nprint(f.__ail_export__)\n',
                    '__ail_export__ marker'),
    'exports_registry': ('from ail_ffi import export, exports\n\n@export\ndef f(x: int) -> int:\n    return x\n\nprint([g.__name__ for g in exports()])\n',
                         "'exports' is not a known function/class/builtin"),
    'shadowed_marker': ('''from ail_ffi import export
def export(fn):
    def g(a):
        return fn(a) + 100
    return g
@export
def f(x: int) -> int:
    return x
print(f(1))
''', 'is rebound by this file'),
    'hasattr_marker': ('from ail_ffi import export\n\n@export\ndef f(x: int) -> int:\n    return x\n\nprint(hasattr(f, "__ail_export__"))\n',
                       '__ail_export__ marker'),
    'getattr_marker': ('from ail_ffi import export\n\n@export\ndef f(x: int) -> int:\n    return x\n\nprint(getattr(f, "__ail_export__"))\n',
                       '__ail_export__ marker'),
    'future_dataclass': ('''from __future__ import annotations
from dataclasses import dataclass
from ail_ffi import export

@dataclass
class Point:
    x: int

@export
def take(p: Point) -> int:
    return p.x

print(take(Point(1)))
''', 'rejects under `from __future__ import annotations`'),
    'forward_dataclass': ('''from dataclasses import dataclass
from ail_ffi import export

@export
def take(p: Point) -> int:
    return p.x

@dataclass
class Point:
    x: int

print(take(Point(1)))
''', 'before it is defined'),
    'lru_below_marker': ('''from functools import lru_cache
from ail_ffi import export

@export
@lru_cache
def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)

print(fib(10))
''', 'decorator below @export'),
    'staticmethod_below_marker': ('''from ail_ffi import export

@export
@staticmethod
def f(n: int) -> int:
    return n + 1

print(f(2))
''', 'decorator below @export'),
}


class Ex33Tests(unittest.TestCase):
    def compare(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-ex33-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, '%s_%s' % (name, 'g' if general else 'd'), text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                 (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))

    def test_export_forms_match_cpython(self):
        for name, text in MATCHING.items():
            with self.subTest(name=name):
                self.compare(name, text)

    def test_language_example_builds_and_matches_cpython(self):
        self.compare('geometry', GEOMETRY.read_text(encoding='utf-8'))

    def test_unsupported_export_contract_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex33-') as directory:
            for name, (text, needle) in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (name, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (name, general, output[-1200:]))
                    self.assertIn(needle, output, (name, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
