"""ex41: `@export` is an identity decorator in a plain Python-syntax program.

`from ail_ffi import export` is written for `ail build --lib`, but the decorator only checks
its annotations and returns the function unchanged on CPython, so the same file is also an
ordinary program. The compiler used to refuse the decorator even though
`language_examples/c_export/geometry.py` is written that way. The front end now validates the
same contract and drops the decorator on both builds; an invalid `@export`, or a read of the
runtime marking (`__ail_export__`, `exports()` and function introspection), is refused by name
instead of compiling to different behaviour. PEP 563 turns dataclass fields into strings, which
CPython's `@export` rejects, so such a parameter is refused too.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')
EXAMPLE = ROOT / 'language_examples' / 'c_export' / 'geometry.py'


def run_py(path):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    result = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, timeout=120, env=env)
    return result.returncode, result.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-ex41-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, source, general, path=None):
        if path is None:
            path = self.dir / 'p.py'
            path.write_text(source, encoding='utf-8')
        env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
        env.pop('AIL_UNIFIED_FORCE', None)
        if general:
            env['AIL_UNIFIED_FORCE'] = '1'
        exe = self.dir / ('exe_g' if general else 'exe_d')
        built = subprocess.run([sys.executable, '-B', CLI, 'compile', str(path), '--syntax', 'python',
                                '-o', str(exe)], cwd=self.dir, capture_output=True, text=True, env=env,
                               timeout=300)
        return built, exe

    def same(self, source):
        ref = self.dir / 'ref.py'
        ref.write_text(source, encoding='utf-8')
        code, out = run_py(ref)
        self.assertEqual(code, 0)
        for general in (False, True):
            built, exe = self.build(source, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual(ran.stdout, out, 'general' if general else 'default')
            self.assertEqual(ran.returncode, code)
        return out

    def refused(self, source):
        ref = self.dir / 'ref.py'
        ref.write_text(source, encoding='utf-8')
        code, _ = run_py(ref)
        self.assertNotEqual(code, 0)
        self.refused_by_name(source)

    def refused_by_name(self, source):
        for general in (False, True):
            built, _ = self.build(source, general)
            self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn('@export', built.stdout + built.stderr)

    def test_geometry_example_builds_and_matches(self):
        code, out = run_py(EXAMPLE)
        self.assertEqual(code, 0)
        for general in (False, True):
            built, exe = self.build(None, general, path=EXAMPLE)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual(ran.stdout, out, 'general' if general else 'default')
            self.assertEqual(ran.returncode, code)

    def test_values_and_empty_boundaries(self):
        self.same(r'''from ail_ffi import export


@export
def add(a: int, b: int) -> int:
    return a + b


@export()
def shout(text: str) -> str:
    return text.upper() + "!"


@export
def scale(x: float, k: int) -> float:
    return x * k


@export
def total(values: list[int]) -> int:
    t = 0
    for v in values:
        t += v
    return t


@export
def halves(values: list[float]) -> list[float]:
    return [v / 2.0 for v in values]


@export
def count_up(n: int) -> None:
    for i in range(n):
        print(i)


if __name__ == "__main__":
    print(add(-2, 5), add(0, 0))
    print(shout(""), shout("h\u00e9llo"))
    print(scale(1.5, -3), scale(-0.0, 2))
    print(total([]), total([-1, 0, 3]), total([2**62, -2**62]))
    print(halves([]), halves([-1.0, 0.0, 4.5]))
    count_up(3)
''')

    def test_decorator_forms_and_dataclass_routes(self):
        self.same(r'''import ail_ffi
from ail_ffi import *
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Point:
    x: int
    y: float
    visible: bool


@ail_ffi.export
def twice(x: int) -> int:
    return x * 2


@export
def weight(p: Point) -> float:
    if p.visible:
        return p.x * p.y
    return 0.0


@lru_cache(maxsize=None)
@export
def square(n: int) -> int:
    return n * n


class Box:
    def __init__(self, p):
        self.p = p


def main():
    p = Point(2, 1.5, True)
    print(twice(-4), twice(0))
    print(weight(p), weight(Point(-3, 2.0, False)))
    pts = [Point(1, 0.5, True), Point(7, 3.0, False)]
    print(weight(pts[1]), weight(pts[0]))
    d = {"p": Point(5, -2.0, True)}
    print(weight(d["p"]), weight(Box(p).p))
    print(square(-3) + square(4))


main()
''')

    def test_future_annotations_scalar_export_matches(self):
        self.same(r'''from __future__ import annotations
from ail_ffi import export


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def shout(text: str) -> str:
    return text + "!"


print(add(-2, 5), shout(""))
''')

    def test_invalid_export_is_refused_by_name(self):
        programs = [
            'from ail_ffi import export\n\n\n@export\ndef add(a, b: int) -> int:\n    return a + b\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int, b: int):\n    return a + b\n',
            'from ail_ffi import export\n\n\n@export\ndef keys(d: dict) -> int:\n    return len(d)\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int, b: int = 2) -> int:\n    return a + b\n',
            'from ail_ffi import export\n\n\n@export\nclass C:\n    pass\n',
            'from ail_ffi import export\n\n\n@export(3)\ndef add(a: int) -> int:\n    return a\n',
            'from functools import lru_cache\nfrom ail_ffi import export\n\n\n'
            '@export\n@lru_cache(maxsize=None)\ndef fib(n: int) -> int:\n    return n\n',
            'from dataclasses import dataclass\nfrom ail_ffi import export\n\n\n'
            '@dataclass\nclass Item:\n    name: str\n\n\n'
            '@export\ndef size(item: Item) -> int:\n    return 1\n',
            'from dataclasses import dataclass\nfrom ail_ffi import export\n\n'
            'int = str\n\n\n'
            '@dataclass\nclass Point:\n    x: int\n\n\n'
            '@export\ndef size(p: Point) -> int:\n    return 4\n',
            'from dataclasses import dataclass\nfrom ail_ffi import export\n\n\n'
            '@dataclass\nclass Point:\n    x: int\n\n\n'
            'Point = dict\n\n\n'
            '@export\ndef size(p: Point) -> int:\n    return len(p)\n',
            'from __future__ import annotations\nfrom dataclasses import dataclass\nfrom ail_ffi import export\n\n\n'
            '@dataclass\nclass Point:\n    x: int\n    y: float\n\n\n'
            '@export\ndef weight(p: Point) -> float:\n    return p.x * p.y\n',
            'from ail_ffi import export\n\n'
            'int = list\n\n\n'
            '@export\ndef size(x: int) -> int:\n    return 1\n',
        ]
        for source in programs:
            with self.subTest(source=source.splitlines()[-1]):
                self.refused(source)
                self.refused(source + '\nprint("ran")\n')

    def test_runtime_marking_is_refused_by_name(self):
        programs = [
            'from ail_ffi import export\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(add.__ail_export__)\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'funcs = [add]\nprint(funcs[0].__ail_export__)\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(getattr(add, "__ail_export__"))\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(hasattr(add, "__ail_export__"))\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(vars(add))\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(add.__dict__)\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'g = add\nprint(g.__dict__)\n',
            'from ail_ffi import export, exports\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(len(exports()))\n',
            'import ail_ffi\n\n\n@ail_ffi.export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(ail_ffi.exports())\n',
            'from ail_ffi import export, exports\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(len(exports()))\nexports = lambda: []\n',
            'from ail_ffi import export\nimport ail_ffi\n\n\n@export\ndef add(a: int) -> int:\n'
            '    return a\n\n\n'
            'print(len(ail_ffi.exports()))\nail_ffi = None\n',
        ]
        for source in programs:
            with self.subTest(source=source.splitlines()[-1]):
                self.refused_by_name(source)

    def test_deleting_the_imported_decorator_is_refused_by_name(self):
        source = ('from ail_ffi import export\n\n'
                  'del export\n\n\n'
                  '@export\n'
                  'def add(a: int) -> int:\n'
                  '    return a\n')
        for general in (False, True):
            built, _ = self.build(source, general)
            self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn('deleting the imported name export',
                          built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()
