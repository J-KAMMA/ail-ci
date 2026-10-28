"""ex20: a def-only Python script with a scalar first parameter is not a file entry point.

`language_examples/math.ail` is Python syntax: a module constant and `def sum_to(n)`.  CPython
runs the module body, defines both names and exits 0 without output.  The typed path instead took
the first function as the program entry and refused it with "the first parameter must be the
sequence read from the file"; the general path already ran the module body (the top-level
constant keeps it off the array-entry route) and matched CPython.

`_main_for` now returns an inert `main` when the first parameter is not the file's int64
sequence, so both builds run the definitions and exit 0.  An array parameter keeps its existing
function entry point (read a file of int64 and print the result), which is checked here too.
A def-only source whose module body has definition-time work the module-body path does not
reproduce (class-body statements, annotation expressions, class decorators/metaclasses,
`__init_subclass__`/`__set_name__`, a supported decorator's argument) is refused by name on both
builds instead of silently dropping that work; class-body assignments, defaults and annotations
behind `from __future__ import annotations` still match CPython.

Every program is compared with CPython on the default build and the forced general build.
"""
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")


def run_py(path):
    r = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=60)
    return r.returncode, r.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-ex20-")
        self.dir = Path(self.tmp.name)
        self.counter = 0

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, src, general):
        path = self.dir / "p.py"
        path.write_text(src, encoding="utf-8")
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        self.counter += 1
        exe = self.dir / ("exe_%d_%s" % (self.counter, "g" if general else "d"))
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python",
                                "-o", str(exe)], cwd=self.dir, capture_output=True, text=True, env=env)
        return built, exe

    def same(self, src):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        code, out = run_py(path)
        self.assertEqual(code, 0)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, out, "general" if general else "default")
            self.assertEqual(ran.returncode, code)
        return out


MATH = r'''LIMIT = 6

def sum_to(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total
'''

INT = r'''LIMIT = 3

def scale(n: int) -> int:
    return n * LIMIT
'''

STR = r'''PREFIX = "x"

def label(s: str) -> str:
    return PREFIX + s
'''

BYTES = r'''def reverse(b: bytes) -> bytes:
    return b[::-1]
'''

FLOAT = r'''def half(x: float) -> float:
    return x / 2.0
'''

BOOL = r'''def flip(flag: bool) -> bool:
    return not flag
'''

ARRAY = r'''def total(values: list[int]) -> int:
    return sum(values)
'''

SIDE_EFFECT_MATCHING = {
    'class_assignment': '''class C:
    x = print("assign")

def f(n: int) -> int:
    return n
''',
    'default_call': '''def g(x=(print("d") or 1)):
    return x

def f(n: int) -> int:
    return n
''',
    'future_annotations': '''from __future__ import annotations

def g(x: (print("ga") or int) = 1):
    return x

def f(n: int) -> int:
    return n
''',
    'plain_annotations': '''class C:
    """doc"""
    K = 3

    def m(self, x: list[int]) -> int:
        return x[0] + self.K

def f(n: int) -> int:
    return n
''',
}

SIDE_EFFECT_REFUSED = {
    'class_body_print': ("""class C:
    print("class-body")

def f(n: int) -> int:
    return n
""", 'the class-body statement in class C'),
    'class_body_exit': ("""import sys
class C:
    sys.exit(4)

def f(n: int) -> int:
    return n
""", 'the class-body statement in class C'),
    'init_subclass': ("""class Base:
    def __init_subclass__(cls):
        print("sub")
class C(Base):
    pass
def f(n: int) -> int:
    return n
""", '__init_subclass__'),
    'annotation_call': ("""def g(x: (print("ga") or int) = 1):
    return x
def f(n: int) -> int:
    return n
""", 'the annotation on parameter x'),
    'class_decorator': ("""def deco(c):
    print("dec")
    return c
@deco
class C:
    pass
def f(n: int) -> int:
    return n
""", 'a decorator on class C'),
    'set_name': ("""class D:
    def __set_name__(self, owner, name):
        print("sn")
class C:
    x = D()
def f(n: int) -> int:
    return n
""", '__set_name__'),
    'class_annotation': ("""class C:
    x: (print("ca") or int) = 1
def f(n: int) -> int:
    return n
""", 'the class annotation on x'),
    'method_annotation': ("""class C:
    def m(self, x: (print("ma") or int)) -> int:
        return x
def f(n: int) -> int:
    return n
""", 'the annotation on parameter x'),
    'return_annotation': ("""def g() -> (print("ra") or int):
    return 1
def f(n: int) -> int:
    return n
""", 'the return annotation of def g'),
    'base_arguments': ("""class T:
    def __class_getitem__(cls, x):
        print("gi")
        return cls
class C(T[(print("arg") or 1)]):
    pass
def f(n: int) -> int:
    return n
""", 'the base-class type arguments of class C'),
    'lru_cache_argument': ("""import functools
@functools.lru_cache(maxsize=(print("lru") or 8))
def g(x):
    return x
def f(n: int) -> int:
    return n
""", 'an argument of the @lru_cache decorator on def g'),
}


class Ex20Tests(Base):
    def test_math_example_matches_cpython(self):
        out = self.same(MATH)
        self.assertEqual(out, b"")

    def test_scalar_first_parameters_are_inert(self):
        for src in (INT, STR, BYTES, FLOAT, BOOL):
            with self.subTest(src=src.splitlines()[-2]):
                self.assertEqual(self.same(src), b"")

    def test_definition_time_side_effects_match_cpython(self):
        for name, src in SIDE_EFFECT_MATCHING.items():
            with self.subTest(name=name):
                self.same(src)

    def test_definition_time_side_effects_are_refused_by_name(self):
        for name, (src, message) in SIDE_EFFECT_REFUSED.items():
            for general in (False, True):
                with self.subTest(name=name, general=general):
                    built, _ = self.build(src, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, output[-1200:])
                    self.assertIn('not in the subset', output, output[-1200:])
                    self.assertIn(message, output, output[-1200:])

    def test_array_first_parameter_still_reads_the_file(self):
        path = self.dir / "p.py"
        path.write_text(ARRAY, encoding="utf-8")
        data = self.dir / "data.bin"
        data.write_bytes(struct.pack("<3q", 1, 2, 3))
        for general in (False, True):
            built, exe = self.build(ARRAY, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe), str(data)], capture_output=True, timeout=60)
            self.assertEqual((ran.returncode, ran.stdout), (0, b"6\n"),
                             "general" if general else "default")


if __name__ == '__main__':
    unittest.main()
