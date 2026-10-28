"""`@export` in an ordinary Python-syntax program is CPython's identity decorator.

The C-library build (`compile --lib`) already lowers `@export`; a normal `compile` used to refuse
the decorator before the rest of the program was looked at.  `geometry.py` is the language example:
it is also a CPython program (`if __name__ == "__main__": print(...)`).  Both builds must print the
same bytes and exit 0 as CPython, and an invalid export annotation is still refused by name.

A Python-syntax module of definitions and constants with no entry-point-shaped function also runs
as CPython does (bind the names, print nothing, exit 0) instead of being refused because its first
parameter is not the file sequence; `math.ail` is that language example.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
GEOMETRY = ROOT / 'language_examples' / 'c_export' / 'geometry.py'
MATH = ROOT / 'language_examples' / 'math.ail'

PROGRAM = '''from dataclasses import dataclass
import ail_ffi
from ail_ffi import export
from ail_ffi import export as mark


@dataclass
class Point:
    x: int
    y: float
    visible: bool


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def scaled(x: float) -> float:
    return x * 3 + 0.5


@export
def negate(flag: bool) -> bool:
    return not flag


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
def total(values: list[int]) -> int:
    return sum(values)


@export
def halves(values: list[float]) -> list[float]:
    return [v / 2.0 for v in values]


@export
def weight(p: Point) -> float:
    return p.x * p.y if p.visible else 0.0


@export
def count_up(n: int) -> None:
    if n < 0:
        raise ValueError("n must not be negative")


@mark
def via_alias(x: int) -> int:
    return x - 1


@ail_ffi.export
def via_module(x: int) -> int:
    return x + 1


if __name__ == "__main__":
    data = {"k": 7}
    values = [1, 2, 3]
    point = Point(2, 1.5, True)
    print(add(data["k"], values[1]), scaled(-2.0), negate(False))
    print(shout("h\u00e9llo"), reverse_bytes(b"\\x00\\x01\\xff").hex())
    print(total([]), total(values), halves([1.0, -2.5]))
    print(weight(point), weight(Point(2, 1.5, False)), count_up(3))
    print(via_alias(5), via_module(5))
'''


MODULE_PROGRAM = '''SCALE = 3


def scaled(n: int) -> int:
    return n * SCALE


def label(text: str) -> str:
    return text.upper()
'''


class ExportProgramTests(unittest.TestCase):
    def build_and_run(self, source, directory):
        cpython_env = dict(os.environ)
        cpython_env['PYTHONPATH'] = str(ROOT) + (
            os.pathsep + cpython_env['PYTHONPATH'] if cpython_env.get('PYTHONPATH') else '')
        expected = subprocess.run([sys.executable, str(source)], cwd=directory, env=cpython_env,
                                  capture_output=True, text=True, timeout=120)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        for label, general in (('default', False), ('general', True)):
            with self.subTest(build=label):
                exe = Path(directory) / ('exe_' + label)
                env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
                env.pop('AIL_UNIFIED_FORCE', None)
                if general:
                    env['AIL_UNIFIED_FORCE'] = '1'
                built = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                                        '-o', str(exe)], cwd=ROOT, capture_output=True, text=True,
                                       timeout=600, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True,
                                     timeout=60)
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                 ran.stderr)

    def test_export_decorator_and_value_routes(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex14-') as directory:
            source = Path(directory) / 'export_program.py'
            source.write_text(PROGRAM, encoding='utf-8')
            self.build_and_run(source, directory)

    def test_geometry_example_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex14-geometry-') as directory:
            self.build_and_run(GEOMETRY, directory)

    def test_module_definition_program_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex14-module-') as directory:
            source = Path(directory) / 'module_program.py'
            source.write_text(MODULE_PROGRAM, encoding='utf-8')
            self.build_and_run(source, directory)

    def test_math_module_example_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex14-math-') as directory:
            self.build_and_run(MATH, directory)

    def test_invalid_export_annotation_is_refused(self):
        text = ('from ail_ffi import export\n\n@export\n'
                'def bad(value: object) -> int:\n    return 1\n\nprint(bad(None))\n')
        with tempfile.TemporaryDirectory(prefix='ail-ex14-bad-') as directory:
            source = Path(directory) / 'bad_export.py'
            source.write_text(text, encoding='utf-8')
            cpython_env = dict(os.environ, PYTHONPATH=str(ROOT))
            cpython = subprocess.run([sys.executable, str(source)], cwd=directory, env=cpython_env,
                                     capture_output=True, text=True, timeout=60)
            self.assertNotEqual(cpython.returncode, 0)
            for label, general in (('default', False), ('general', True)):
                with self.subTest(build=label):
                    exe = Path(directory) / ('bad_' + label)
                    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
                    env.pop('AIL_UNIFIED_FORCE', None)
                    if general:
                        env['AIL_UNIFIED_FORCE'] = '1'
                    built = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                                            '-o', str(exe)], cwd=ROOT, capture_output=True,
                                           text=True, timeout=600, env=env)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertIn('unsupported type object', built.stdout + built.stderr)
                    self.assertFalse(exe.exists())


if __name__ == '__main__':
    unittest.main()
