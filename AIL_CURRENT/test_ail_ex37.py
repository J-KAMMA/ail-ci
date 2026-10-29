"""ex37: plain `compile` accepts the @export marker, and `__file__` is the module's absolute path.

The Python-syntax example `language_examples/c_export/geometry.py` uses `@export` so the same file can
also be built as a C library.  On CPython the decorator only validates annotations and returns the
function unchanged; `compile` now does the same (and refuses by name the CPython-only marker attribute).
The other common refusal among the `.py` examples was `__file__`, which CPython sets before a module
body runs; the merged build now substitutes each module's absolute source path for read-only reads.

Every program below is ordinary Python.  CPython 3.12 is the oracle (with AIL_CURRENT on PYTHONPATH for
the `ail_ffi` import); the compiled program must print the same bytes and exit with the same status on
the general path (AIL_UNIFIED_FORCE=1) and the default build.  A named compile-time refusal is the only
other accepted outcome.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / "ail_chatgpt.py"


def build(directory, source, name, general):
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    if general:
        env["AIL_UNIFIED_FORCE"] = "1"
    exe = directory / (name + ("_g" if general else "_d"))
    built = subprocess.run([sys.executable, "-B", str(CLI), "compile", str(source), "--syntax", "python",
                            "-o", str(exe)], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def oracle(source, directory, extra_env=None):
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run([sys.executable, "-B", str(source)], cwd=directory, capture_output=True,
                          timeout=300, env=env)


class Base(unittest.TestCase):
    def compare(self, text, name="prog", files=(), extra_env=None):
        with tempfile.TemporaryDirectory(prefix="ail-ex37-") as tmp:
            directory = Path(tmp)
            for filename, content in files:
                (directory / filename).write_text(content, encoding="utf-8")
            source = directory / (name + ".py")
            source.write_text(text, encoding="utf-8")
            want = oracle(source, directory, extra_env)
            self.assertEqual(want.returncode, 0, want.stderr.decode("utf-8", "replace"))
            for general in (False, True):
                built, exe = build(directory, source, name, general)
                self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-3000:])
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, got.stderr.decode("utf-8", "replace"))
                self.assertEqual(got.stdout, want.stdout,
                                 "general" if general else "default")
            return want.stdout

    def refused(self, text, needle, extra_env=None):
        with tempfile.TemporaryDirectory(prefix="ail-ex37-") as tmp:
            directory = Path(tmp)
            source = directory / "prog.py"
            source.write_text(text, encoding="utf-8")
            for general in (False, True):
                built, exe = build(directory, source, "prog", general)
                self.assertNotEqual(built.returncode, 0, (built.stdout + built.stderr)[-3000:])
                self.assertFalse(exe.exists())
                self.assertIn(needle, built.stdout + built.stderr)
            return oracle(source, directory, extra_env)


EXPORT_PROGRAM = r'''from dataclasses import dataclass
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
def half(x: float) -> float:
    return x / 2.0


@export
def shout(text: str) -> str:
    return text.upper() + "!"


@export
def negate(flag: bool) -> bool:
    return not flag


@export
def reverse(data: bytes) -> bytes:
    return data[::-1]


@export
def squares(values: list[int]) -> list[int]:
    return [v * v for v in values]


@export
def halves(values: list[float]) -> list[float]:
    return [v / 2.0 for v in values]


@export
def weight(p: Point) -> float:
    return p.x * p.y if p.visible else 0.0


@export
def nothing(n: int) -> None:
    if n < 0:
        raise ValueError("negative")


if __name__ == "__main__":
    print(add(2, 3), half(7.0), shout("héllo"), negate(True), reverse(b"abc"),
          squares([1, 2, 3]), halves([2.0, 3.0]), weight(Point(2, 1.5, True)))
    nothing(1)
    try:
        nothing(-1)
    except ValueError as error:
        print(type(error).__name__, str(error))
'''

EXPORT_ALIAS = r'''import ail_ffi as ffi


@ffi.export
def double(x: int) -> int:
    return x * 2


@ffi.export()
def triple(x: int) -> int:
    return x * 3


if __name__ == "__main__":
    print(double(4), triple(4))
'''

EXPORT_STAR = r'''from ail_ffi import *


@export
def double(x: int) -> int:
    return x * 2


if __name__ == "__main__":
    print(double(5))
'''

FILE_ROUTES = r'''import os
from pathlib import Path


def where() -> str:
    return __file__


class Holder:
    here = __file__

    def __init__(self) -> None:
        self.here = __file__


def main() -> None:
    print(os.path.basename(__file__))
    print(os.path.isabs(__file__))
    print(Path(__file__).name)
    print(Path(__file__).resolve().parent.name)
    print(where())
    print(Holder.here)
    print(Holder().here)
    print(__file__ == where())
    print([__file__][0] == __file__)
    print({"k": __file__}["k"] == __file__)
    print(str(Path(__file__)) == __file__)


main()
'''

MODULE_MAIN = r'''import m

print(__file__)
print(m.__file__)
print(m.where())
print(m.where() == m.__file__)
'''

MODULE_M = r'''def where() -> str:
    return __file__


print("loaded", __file__)
'''


class ExportDecorator(Base):
    def test_export_is_identity_for_plain_compile(self):
        self.compare(EXPORT_PROGRAM, extra_env={"PYTHONPATH": str(ROOT)})

    def test_export_alias_and_call(self):
        self.compare(EXPORT_ALIAS, extra_env={"PYTHONPATH": str(ROOT)})

    def test_export_star_import(self):
        self.compare(EXPORT_STAR, extra_env={"PYTHONPATH": str(ROOT)})

    def test_unused_export_import_is_harmless(self):
        self.compare('from ail_ffi import export\n\n\ndef f(x: int) -> int:\n    return x + 1\n\n\n'
                     'if __name__ == "__main__":\n    print(f(4))\n',
                     extra_env={"PYTHONPATH": str(ROOT)})

    def test_export_invalid_annotations_are_refused(self):
        self.refused('from ail_ffi import export\n\n\n@export\ndef f(x: list[str]) -> int:\n    return len(x)\n\n'
                     'print(f(["a"]))\n',
                     "@export f: parameter x has an unsupported annotation",
                     extra_env={"PYTHONPATH": str(ROOT)})
        self.refused('from ail_ffi import export\n\n\n@export\ndef f(x: int):\n    return x\n\nprint(f(1))\n',
                     "@export f: the result needs an annotation",
                     extra_env={"PYTHONPATH": str(ROOT)})
        self.refused('from ail_ffi import export\n\n\n@export\ndef f(x: int = 1) -> int:\n    return x\n\nprint(f())\n',
                     "@export f: plain parameters without defaults only",
                     extra_env={"PYTHONPATH": str(ROOT)})
        self.refused('from dataclasses import dataclass\nfrom ail_ffi import export\n\n\n@dataclass\n'
                     'class Bad:\n    name: str\n\n\n@export\ndef f(p: Bad) -> int:\n    return 1\n\n'
                     'print(f(Bad("x")))\n',
                     "@export f: parameter p has an unsupported annotation",
                     extra_env={"PYTHONPATH": str(ROOT)})
        self.refused('from __future__ import annotations\nfrom dataclasses import dataclass\n'
                     'from ail_ffi import export\n\n\n@dataclass\nclass P:\n    x: int\n\n\n'
                     '@export\ndef f(p: P) -> int:\n    return p.x\n\nprint(f(P(1)))\n',
                     "@export f: parameter p has an unsupported annotation",
                     extra_env={"PYTHONPATH": str(ROOT)})
        self.refused('from dataclasses import dataclass\nfrom ail_ffi import export\n\n\n@dataclass\n'
                     'class Base:\n    name: str\n\n\n@dataclass\nclass P(Base):\n    x: int\n\n\n'
                     '@export\ndef f(p: P) -> int:\n    return p.x\n\nprint(f(P("a", 1)))\n',
                     "@export f: parameter p has an unsupported annotation",
                     extra_env={"PYTHONPATH": str(ROOT)})
        self.refused('from ail_ffi import export\n\nint = list[str]\n\n\n@export\ndef f(x: int) -> int:\n'
                     '    return len(x)\n\nprint(f(["a", "b"]))\n',
                     "@export f: parameter x has an unsupported annotation",
                     extra_env={"PYTHONPATH": str(ROOT)})
        self.refused('from ail_ffi import export\n\nint = list[str]\n\n\n@export\ndef f(x: list[int]) -> int:\n'
                     '    return len(x)\n\nprint(f([["a"], ["b"]]))\n',
                     "@export f: parameter x has an unsupported annotation",
                     extra_env={"PYTHONPATH": str(ROOT)})

    def test_export_marker_is_refused(self):
        self.refused('from ail_ffi import export\n\n\n@export\ndef f(x: int) -> int:\n    return x\n\n'
                     'print(f.__ail_export__)\n',
                     "__ail_export__", extra_env={"PYTHONPATH": str(ROOT)})

    def test_geometry_example_matches_cpython(self):
        source = ROOT / "language_examples" / "c_export" / "geometry.py"
        text = source.read_text(encoding="utf-8")
        self.compare(text, name="geometry", extra_env={"PYTHONPATH": str(ROOT)})


class FileDunder(Base):
    def test_reads_in_arguments_lists_attributes_and_dict_values(self):
        self.compare(FILE_ROUTES)

    def test_each_module_keeps_its_own_file(self):
        self.compare(MODULE_MAIN, name="main", files=(("m.py", MODULE_M),))

    def test_assignment_is_refused(self):
        self.refused('__file__ = "changed"\nprint(__file__)\n', "__file__ is assigned or bound here")

    def test_parameter_and_function_names_are_refused(self):
        self.refused('def f(__file__: str) -> str:\n    return __file__\n\nprint(f("x"))\n',
                     "__file__ is assigned or bound here")
        self.refused('def __file__() -> str:\n    return "x"\n\nprint(__file__())\n',
                     "__file__ is assigned or bound here")

    def test_import_alias_and_except_name_are_refused(self):
        self.refused('import os as __file__\nprint(__file__.path)\n', "__file__ is assigned or bound here")
        self.refused('try:\n    raise ValueError("x")\nexcept ValueError as __file__:\n    print(__file__)\n',
                     "__file__ is assigned or bound here")


if __name__ == "__main__":
    unittest.main()
