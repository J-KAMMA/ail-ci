"""`@export` in an ordinary compile: the dual Python/AIL library example runs like CPython.

`language_examples/c_export/geometry.py` is one file with two readers. `compile --lib` turns its
@export functions into a C library, but an ordinary `compile` used to stop at the decorator. The
front end now removes a plain @export (bare, called or `ail_ffi.export`) when CPython's own
decorator would accept the function: a top-level function, no defaults or special parameters, and
annotations of int/float/bool/str/bytes/list[int]/list[float], a dataclass of int/float/bool as a
parameter, and -> None as a result. @lru_cache/@cache may sit above it. Every other form is
refused by name, so a CPython TypeError at decoration time is never hidden by a running program.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
GEOMETRY = ROOT / "language_examples" / "c_export" / "geometry.py"

VALID = r'''from dataclasses import dataclass
from functools import lru_cache
from ail_ffi import export


@dataclass
class Point:
    x: int
    y: float


@export
def add(a: int, b: int) -> int:
    return a + b


@export()
def half(x: float) -> float:
    return x / 2.0


@lru_cache(maxsize=None)
@export
def cube(x: int) -> int:
    return x ** 3


@export
def weight(p: Point) -> float:
    return p.x * p.y


@export
def show() -> None:
    print("shown")


def call(fn, value: int) -> int:
    return fn(value)


print(add(2, 3), half(5.0), cube(3), weight(Point(2, 1.5)), call(cube, 4), [cube][0](5), {"f": cube}["f"](6))
show()
'''

MODULE_FORM = r'''import ail_ffi


@ail_ffi.export
def upper(text: str) -> str:
    return text.upper()


print(upper("hello"))
'''

STAR_FORM = r'''from ail_ffi import *


@export
def upper(text: str) -> bytes:
    return text.upper().encode()


print(upper("hello").hex())
'''

NO_EXPORT = r'''from ail_ffi import extern

print("plain")
'''

INVALID = [
    ("from ail_ffi import export\n\n@export\ndef f(x: int = 1) -> int:\n    return x\n\nprint(f())\n", "f"),
    ("from ail_ffi import export\n\n@export\ndef f(x) -> int:\n    return 1\n\nprint(f(1))\n", "f"),
    ("from ail_ffi import export\n\n@export\ndef f(x: int):\n    return x\n\nprint(f(1))\n", "f"),
    ("from ail_ffi import export\n\n@export\ndef f(x: list[str]) -> int:\n    return 1\n\nprint(f(['a']))\n", "f"),
    ("from ail_ffi import export\n\n@export\ndef f(x: int, /) -> int:\n    return x\n\nprint(f(1))\n", "f"),
    ("from dataclasses import dataclass\nfrom ail_ffi import export\n\n@dataclass\nclass P:\n    x: str\n\n"
     "@export\ndef f(p: P) -> int:\n    return 1\n\nprint(f(P('a')))\n", "f"),
    ("from dataclasses import dataclass\nfrom ail_ffi import export\n\n@dataclass\nclass P:\n    x: int\n\n"
     "@export\ndef f(x: int) -> P:\n    return P(x)\n\nprint(f(1).x)\n", "f"),
    ("from functools import lru_cache\nfrom ail_ffi import export\n\n@export\n@lru_cache(maxsize=None)\n"
     "def square(x: int) -> int:\n    return x * x\n\nprint(square(5))\n", "square"),
]


def clean_env(extra=None):
    env = dict(os.environ)
    for key in ("AIL_IR", "AIL_NO_GENERAL", "AIL_UNIFIED", "AIL_UNIFIED_FORCE"):
        env.pop(key, None)
    env["AIL_NO_CACHE"] = "1"
    env.update(extra or {})
    return env


def oracle_env():
    env = dict(os.environ, PYTHONUTF8="1", PYTHONPATH=str(ROOT))
    return env


class ExportOrdinaryCompile(unittest.TestCase):
    def build(self, directory, source, name, extra, path=None):
        exe = Path(directory) / (name + ".exe")
        if exe.exists():
            exe.unlink()
        target = str(path) if path is not None else str(Path(directory) / (name + ".py"))
        return subprocess.run([sys.executable, "-B", CLI, "compile", target, "--syntax", "python",
                               "-o", str(exe)], cwd=directory, capture_output=True, text=True,
                              timeout=900, env=clean_env(extra)), exe

    def compare(self, text, name, path=None):
        with tempfile.TemporaryDirectory(prefix="ail-ex35-") as directory:
            src = path
            if src is None:
                src = Path(directory) / (name + ".py")
                src.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, str(src)], cwd=directory, capture_output=True,
                                  text=True, timeout=300, env=oracle_env())
            self.assertEqual(want.returncode, 0, want.stderr)
            for tag, extra in (("general", {"AIL_UNIFIED_FORCE": "1"}), ("default", {})):
                built, exe = self.build(directory, text, name + "_" + tag, extra, path=src)
                self.assertEqual(built.returncode, 0, (tag, built.stdout[-800:] + built.stderr[-2000:]))
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True, timeout=300)
                self.assertEqual(got.stdout, want.stdout, tag)
                self.assertEqual(got.returncode, want.returncode, tag)

    def test_the_library_example_runs_as_an_ordinary_program(self):
        self.compare(None, "geometry", path=GEOMETRY)

    def test_plain_export_forms_and_routes(self):
        self.compare(VALID, "valid")
        self.compare(MODULE_FORM, "module_form")
        self.compare(STAR_FORM, "star_form")

    def test_no_export_is_unchanged(self):
        self.compare(NO_EXPORT, "no_export")

    def test_forms_cpython_rejects_are_refused_by_name(self):
        for index, (text, function) in enumerate(INVALID):
            with self.subTest(index=index), tempfile.TemporaryDirectory(prefix="ail-ex35-") as directory:
                source = Path(directory) / ("bad%d.py" % index)
                source.write_text(text, encoding="utf-8")
                for tag, extra in (("general", {"AIL_UNIFIED_FORCE": "1"}), ("default", {})):
                    built, exe = self.build(directory, text, "bad%d_%s" % (index, tag), extra, path=source)
                    self.assertNotEqual(built.returncode, 0, (index, tag, built.stdout[-800:]))
                    self.assertIn("@export " + function, built.stdout + built.stderr, (index, tag))
                    self.assertFalse(exe.exists(), (index, tag))

    def test_export_call_with_arguments_is_refused_not_dropped(self):
        text = ("from ail_ffi import export\n\n@export(undefined_name)\ndef f(x: int) -> int:\n"
                "    return x + 1\n\nprint(f(1))\n")
        with tempfile.TemporaryDirectory(prefix="ail-ex35-") as directory:
            source = Path(directory) / "arguments.py"
            source.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, str(source)], cwd=directory, capture_output=True,
                                  text=True, timeout=300, env=oracle_env())
            self.assertNotEqual(want.returncode, 0)
            for tag, extra in (("general", {"AIL_UNIFIED_FORCE": "1"}), ("default", {})):
                built, exe = self.build(directory, text, "arguments_" + tag, extra, path=source)
                self.assertNotEqual(built.returncode, 0, (tag, built.stdout[-800:]))
                self.assertIn("@export f", built.stdout + built.stderr, (tag, built.stdout[-800:]))
                self.assertFalse(exe.exists(), tag)


if __name__ == "__main__":
    unittest.main()
