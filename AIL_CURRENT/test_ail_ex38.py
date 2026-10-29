"""ex38: `@export` is an identity decorator for a plain Python-syntax program.

`from ail_ffi import export` marks a function for `ail build --lib`; on CPython the decorator
checks its annotations and returns the function unchanged, so the file also runs as ordinary
Python. The compiler used to refuse the decorator on a plain `ail compile` even though
language_examples/c_export/geometry.py is written that way. The front end now validates the
annotations exactly as the library front end does and drops the decorator; every valid program
below is compared with CPython on the default build and on `AIL_UNIFIED_FORCE=1`, and an invalid
`@export` is refused by name instead of being ignored. The decorator's runtime marking
(`fn.__ail_export__`, `ail_ffi.exports()`) cannot be carried by a function value in a plain
compile, so a program that reads it is refused by name; PEP 563 turns dataclass field annotations
into strings, which CPython's `@export` rejects, so such a dataclass parameter is refused too.
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
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-ex38-')
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

    def test_runtime_marking_is_refused_by_name(self):
        programs = [
            'from ail_ffi import export\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(add.__ail_export__)\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'funcs = [add]\nprint(funcs[0].__ail_export__)\n',
            'from ail_ffi import export, exports\n\n\n@export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(len(exports()))\n',
            'import ail_ffi\n\n\n@ail_ffi.export\ndef add(a: int) -> int:\n    return a\n\n\n'
            'print(ail_ffi.exports())\n',
        ]
        for source in programs:
            with self.subTest(source=source.splitlines()[-1]):
                self.refused_by_name(source)

    def test_future_annotations_scalar_export_matches(self):
        self.same(r'''from __future__ import annotations
from ail_ffi import export


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def shout(text: str) -> str:
    return text + "!"


@export
def halves(values: list[float]) -> list[float]:
    return [v / 2.0 for v in values]


print(add(-2, 5), shout(""), halves([-1.0, 0.0, 4.5]))
''')

    def test_values_and_empty_boundaries(self):
        self.same(r'''from ail_ffi import export


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def scale(x: float, k: int) -> float:
    return x * k


@export
def negate(flag: bool) -> bool:
    return not flag


@export
def shout(text: str) -> str:
    return text.upper() + "!"


@export
def reverse_bytes(data: bytes) -> bytes:
    return data[::-1]


@export
def total(values: list[int]) -> int:
    return sum(values)


@export
def halves(values: list[float]) -> list[float]:
    return [v / 2.0 for v in values]


@export
def count_up(n: int) -> None:
    for i in range(n):
        print(i)


if __name__ == "__main__":
    print(add(-2, 5), add(0, 0))
    print(scale(1.5, -3), scale(-0.0, 2))
    print(negate(True), negate(False))
    print(shout(""), shout("h\u00e9llo"))
    print(reverse_bytes(b""), reverse_bytes(bytes([0, 1, 255])))
    print(total([]), total([-1, 0, 1]), total([2**62, -2**62]))
    print(halves([]), halves([-1.0, 0.0, 4.5]))
    count_up(3)
''')

    def test_dataclass_routes(self):
        self.same(r'''from dataclasses import dataclass
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
def shift(p: Point, n: int) -> int:
    return p.x + n


class Box:
    def __init__(self, p):
        self.p = p


def main():
    p = Point(2, 1.5, True)
    print(weight(p), weight(Point(-3, 2.0, False)))
    pts = [Point(1, 0.5, True), Point(7, 3.0, False)]
    print(weight(pts[1]), shift(pts[0], -2))
    d = {"p": Point(5, -2.0, True)}
    print(weight(d["p"]), shift(d["p"], 1))
    b = Box(Point(9, 0.25, True))
    print(weight(b.p), shift(b.p, -9))


main()
''')

    def test_alias_star_and_innermost_decorator(self):
        self.same(r'''import ail_ffi
from ail_ffi import *
from functools import lru_cache


@ail_ffi.export
def twice(x: int) -> int:
    return x * 2


@export
def join_values(values: list[int]) -> str:
    return "|".join(str(v) for v in values)


@lru_cache(maxsize=None)
@export
def square(n: int) -> int:
    return n * n


@export()
def identity(text: str) -> str:
    return text


print(twice(-4), twice(0))
print(join_values([]), join_values([-1, 2]))
print(square(-3) + square(4), identity(""))
''')

    def test_invalid_export_is_refused_by_name(self):
        programs = [
            'from ail_ffi import export\n\n\n@export\ndef add(a, b: int) -> int:\n    return a + b\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int, b: int):\n    return a + b\n',
            'from ail_ffi import export\n\n\n@export\ndef keys(d: dict) -> int:\n    return len(d)\n',
            'from ail_ffi import export\n\n\n@export\ndef add(a: int, b: int = 2) -> int:\n    return a + b\n',
            'from ail_ffi import export\n\n\n@export\nclass C:\n    pass\n',
            'from functools import lru_cache\nfrom ail_ffi import export\n\n\n'
            '@export\n@lru_cache(maxsize=None)\ndef fib(n: int) -> int:\n    return n\n',
            'from dataclasses import dataclass\nfrom ail_ffi import export\n\n\n'
            '@dataclass\nclass Item:\n    name: str\n\n\n'
            '@export\ndef size(item: Item) -> int:\n    return 1\n',
            'from dataclasses import dataclass\nfrom ail_ffi import export\n\n'
            'int = str\n\n\n'
            '@dataclass\nclass Point:\n    x: int\n\n\n'
            '@export\ndef size(p: Point) -> int:\n    return 4\n',
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

    def test_geometry_example_builds_and_matches(self):
        code, out = run_py(EXAMPLE)
        self.assertEqual(code, 0)
        for general in (False, True):
            built, exe = self.build(None, general, path=EXAMPLE)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual(ran.stdout, out, 'general' if general else 'default')
            self.assertEqual(ran.returncode, code)


if __name__ == '__main__':
    unittest.main()
