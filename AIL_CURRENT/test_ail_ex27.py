"""ex27: `@export` on an ordinary build is CPython's checking no-op.

`AIL_CURRENT/language_examples/c_export/geometry.py` is an AIL Python-syntax example
(`ail build --lib` turns its `@export` functions into a C library).  Running the same file as a
program is also meaningful -- CPython applies `ail_ffi.export`, which checks the annotations and
returns the function unchanged -- but the general path refused the decorator, so the example
could not be built into an executable at all.  The `ail_ffi` front end now validates the decorator
with CPython's contract and removes it before either build path, so a valid file builds and runs
exactly like CPython and an invalid signature is refused by name (CPython raises TypeError).

Both builds (`AIL_UNIFIED_FORCE=1` and the default) are compared with CPython 3.12.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

VALID = r'''from dataclasses import dataclass
from ail_ffi import export

SCALE = 3


@dataclass
class Point:
    x: int
    y: float
    visible: bool


@dataclass
class Empty:
    pass


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def scaled(x: float) -> float:
    return x * SCALE + 0.5


@export
def flag(value: bool) -> bool:
    return not value


@export
def shout(text: str) -> str:
    return text.upper() + "!"


@export
def reverse_bytes(data: bytes) -> bytes:
    out = bytearray()
    i = len(data) - 1
    while i >= 0:
        out.append(data[i])
        i -= 1
    return bytes(out)


@export
def squares(values: list[int]) -> list[int]:
    return [v * v for v in values]


@export
def halves(values: list[float]) -> list[float]:
    return [v / 2.0 for v in values]


@export
def weight(p: Point) -> float:
    if p.visible:
        return p.x * p.y
    return 0.0


@export
def count_up(n: int) -> None:
    if n < 0:
        raise ValueError("n must not be negative")


@export
def describe(empty: Empty) -> int:
    return 0


def main():
    point = Point(2, 1.5, True)
    items = [1, 2, 3]
    values = {"scale": 2.5, "text": "h\u00e9llo", "data": bytes([1, 2, 3, 0, 255])}
    halves_in = [1.0, 2.0, 4.5]
    print(add(2, 3), scaled(values["scale"]), flag(point.visible), shout(values["text"]))
    print(reverse_bytes(values["data"]), squares(items), halves(halves_in))
    print(weight(point), weight(Point(2, 1.5, False)), add(-7, 4))
    print(squares([]), halves([]), reverse_bytes(b""), describe(Empty()))
    count_up(3)
    try:
        count_up(-1)
    except ValueError as error:
        print(type(error).__name__, error)
    doubles = [7, -2]
    print(add(doubles[0], doubles[1]))


main()
'''

FUTURE_SCALARS = r'''from __future__ import annotations
from ail_ffi import export


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def halves(values: list[int]) -> list[int]:
    return [value // 2 for value in values]


def main():
    print(add(2, 3), halves([2, 5, 8]), add(-7, 4))


main()
'''

INHERITED_DATACLASS = r'''from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Base:
    tag: int


@dataclass
class Point(Base):
    x: int
    y: float


@export
def total(p: Point) -> float:
    return p.tag + p.x + p.y


def main():
    print(total(Point(1, 2, 3.5)))


main()
'''

MODULE_ATTRIBUTE = r'''import ail_ffi


@ail_ffi.export
def twice(n: int) -> int:
    return n * 2


@ail_ffi.export()
def plus_one(n: int) -> int:
    return n + 1


def main():
    print(twice(4), plus_one(4), twice(-3), plus_one(0))


main()
'''

REFUSED = {
    'missing_result': '''from ail_ffi import export


@export
def f(x: int):
    return x


def main():
    print(f(1))


main()
''',
    'missing_parameter': '''from ail_ffi import export


@export
def f(x) -> int:
    return x


def main():
    print(f(1))


main()
''',
    'unsupported_parameter': '''from ail_ffi import export


@export
def f(x: dict) -> int:
    return 1


def main():
    print(f({}))


main()
''',
    'unsupported_result': '''from ail_ffi import export


@export
def f(x: int) -> dict:
    return {}


def main():
    print(f(1))


main()
''',
    'dataclass_result': '''from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Point:
    x: int


@export
def f(p: Point) -> Point:
    return p


def main():
    print(f(Point(1)))


main()
''',
    'dataclass_bad_field': '''from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Point:
    x: str


@export
def f(p: Point) -> int:
    return 1


def main():
    print(f(Point("x")))


main()
''',
    'default_parameter': '''from ail_ffi import export


@export
def f(x: int = 1) -> int:
    return x


def main():
    print(f())


main()
''',
    'star_parameter': '''from ail_ffi import export


@export
def f(*xs: int) -> int:
    return 1


def main():
    print(f(1, 2))


main()
''',
    'class_decorator': '''from ail_ffi import export


@export
class Point:
    x = 1


def main():
    print(Point.x)


main()
''',
    'decorator_below_export': '''from functools import lru_cache
from ail_ffi import export


@export
@lru_cache
def add(a: int, b: int) -> int:
    return a + b


def main():
    print(add(2, 2))


main()
''',
    'dataclass_future_annotations': '''from __future__ import annotations
from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Point:
    x: int
    y: int


@export
def add(p: Point) -> int:
    return p.x + p.y


def main():
    print(add(Point(2, 2)))


main()
''',
    'dataclass_inherited_bad_field': '''from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Base:
    tag: str


@dataclass
class Point(Base):
    x: int


@export
def add(p: Point) -> int:
    return p.x


def main():
    print(add(Point("a", 2)))


main()
''',
    'dataclass_defined_after_export': '''from dataclasses import dataclass
from ail_ffi import export


@export
def add(p: Point) -> int:
    return p.x


@dataclass
class Point:
    x: int


def main():
    print(add(Point(4)))


main()
''',
}

EXPORT_ATTRIBUTE = '''from ail_ffi import export


@export
def f(x: int) -> int:
    return x


def main():
    print(f.__ail_export__, f.__name__)


main()
'''

EXPORT_ATTRIBUTE_GETATTR = '''from ail_ffi import export


@export
def f(x: int) -> int:
    return x


def main():
    print(getattr(f, "__ail_export__", False))


main()
'''


def _cpython(directory, text):
    src = Path(directory) / 'prog.py'
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1')
    return subprocess.run([sys.executable, '-B', str(src)], cwd=directory,
                          capture_output=True, timeout=120, env=env)


def _build(directory, text, general):
    src = Path(directory) / ('prog_g.py' if general else 'prog_d.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_g' if general else 'exe_d')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True,
                           timeout=900, env=env)
    return built, exe


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-ex27-')
        self.directory = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def same(self, text):
        want = _cpython(self.directory, text)
        self.assertEqual(want.returncode, 0, want.stderr.decode('utf-8', 'replace'))
        self.assertTrue(want.stdout)
        for general in (False, True):
            with self.subTest(general=general):
                built, exe = _build(self.directory, text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], cwd=self.directory, capture_output=True, timeout=120)
                self.assertEqual(got.stdout, want.stdout)
                self.assertEqual(got.returncode, want.returncode)

    def refused(self, text):
        self.assertNotEqual(_cpython(self.directory, text).returncode, 0,
                            'CPython accepted a shape @export rejects')
        self.refused_by_name(text, '@export')

    def refused_by_name(self, text, element='@export'):
        for general in (False, True):
            with self.subTest(general=general):
                built, exe = _build(self.directory, text, general)
                self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertFalse(exe.exists())
                self.assertNotIn('Traceback', built.stdout + built.stderr)
                self.assertIn(element, built.stdout + built.stderr)

    def test_valid_export_builds_and_matches_cpython(self):
        self.same(VALID)

    def test_export_through_module_attribute_and_call(self):
        self.same(MODULE_ATTRIBUTE)

    def test_future_annotations_keep_scalar_and_list_annotations(self):
        self.same(FUTURE_SCALARS)

    def test_inherited_dataclass_with_scalar_fields(self):
        self.same(INHERITED_DATACLASS)

    def test_invalid_export_shapes_are_refused(self):
        for name, text in REFUSED.items():
            with self.subTest(name=name):
                self.refused(text)

    def test_export_attribute_is_refused_by_name(self):
        self.refused_by_name(EXPORT_ATTRIBUTE)
        self.refused_by_name(EXPORT_ATTRIBUTE_GETATTR)


if __name__ == '__main__':
    unittest.main()
