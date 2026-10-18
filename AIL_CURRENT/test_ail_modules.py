"""G1: a Python program may span several files in one directory (`import m`, `from m import f`).

Each program below is a set of files. CPython runs `python3 main.py` on them as the oracle, and the
program built by `ail_chatgpt.py compile main.py` prints the same bytes, with the legacy path
(AIL_IR=0) and the IR path (AIL_IR=1). The typed programs are built with AIL_NO_GENERAL=1, so the
fast typed path must take them; the others are allowed the general path (module-level code order
is what they pin). Refusals are checked by name, with their `write instead:` hint, and need no C
compiler.

* `import m`, `import m as x`, `from m import f, C, K`, `from m import f as g`; `m.f()`, `m.K`,
  `m.C(...)`, isinstance/inheritance across files, dataclasses from another file.
* Module-level code runs once, at the first import, in CPython's order; `__name__` is
  `__main__` only in the entry; `if __name__ == "__main__":` is false in an imported module;
  an imported module's uncalled `main` is a library function, the entry's is still refused.
* Names that clash across files (functions, variables, parameters, locals, comprehension
  variables) keep their meaning; a user function named like a builtin in another module stays
  that module's own.
* `.py` and `.ail` (Python syntax) sources, for the entry and the modules; both existing is refused.
* An import cycle that only meets in function bodies works; one that reads a name early is refused.
* Packages, relative and star imports, `_private` imports, imports below the top level, a module
  used as a value, `m.x = 1`, a rebound module name, a clashing class name are refused by name.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")


def write(directory, files):
    for name, text in files.items():
        (Path(directory) / name).write_text(text, encoding="utf-8")


def compile_program(directory, entry="main.py", ir="1", typed=False, extra=()):
    exe = Path(directory) / ("out_ir" + ir)
    if exe.exists():
        exe.unlink()
    env = dict(os.environ, AIL_IR=ir)
    env.pop("AIL_NO_GENERAL", None)
    if typed:
        env["AIL_NO_GENERAL"] = "1"
    built = subprocess.run([sys.executable, "-B", CLI, "compile", entry, "-o", str(exe), *extra], cwd=directory,
                           capture_output=True, text=True, timeout=600, env=env)
    return built, exe


class ModulesBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-modules-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def same_as_cpython(self, files, entry="main.py", typed=False, stdin=b"", irs=("0", "1")):
        write(self.dir, files)
        expected = subprocess.run([sys.executable, entry], cwd=self.dir, input=stdin, capture_output=True, timeout=60)
        self.assertEqual(expected.returncode, 0, expected.stderr.decode())
        for ir in irs:
            built, exe = compile_program(self.dir, entry, ir, typed)
            self.assertEqual(built.returncode, 0, "AIL_IR=%s: %s" % (ir, built.stderr))
            ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, expected.stdout, "AIL_IR=%s" % ir)
            self.assertEqual(ran.returncode, 0)
        return expected.stdout.decode()

    def refused(self, files, *needles, entry="main.py"):
        write(self.dir, files)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", entry, "-o", str(self.dir / "out")], cwd=self.dir,
                               capture_output=True, text=True, timeout=120)
        self.assertEqual(built.returncode, 2, built.stdout + built.stderr)
        self.assertFalse((self.dir / "out").exists())
        for needle in needles:
            self.assertIn(needle, built.stderr)
        self.assertIn("write instead", built.stderr)
        self.assertNotIn("Traceback", built.stderr)
        return built.stderr


TYPED = {
    "main.py": '''import util
import geom as g
from geom import Point, area, SCALE as S
from util import helper as h


def helper(x: int) -> int:
    return x + 1000


def main() -> int:
    p = Point(3, 4)
    print(g.area(p), area(p) * S, h(2), helper(2), util.helper(5))
    print(util.LIMIT, g.ORIGIN_X, p.x, util.NAME, S)
    q = g.Point(1, 2)
    print(q.x + q.y, q.x, q.y)
    return 0


if __name__ == "__main__":
    main()
''',
    "util.py": '''LIMIT = 10
NAME = "util"


def helper(x: int) -> int:
    return x * 2


def main() -> int:
    print("util main never runs on import")
    return 1


if __name__ == "__main__":
    main()
''',
    "geom.py": '''from dataclasses import dataclass
import util

SCALE = 3
ORIGIN_X = util.LIMIT - 10


@dataclass
class Point:
    x: int
    y: int


def area(p: Point) -> int:
    return p.x * p.y * util.helper(1)
''',
}


class ImportForms(ModulesBase):
    def test_import_forms_typed_path(self):
        out = self.same_as_cpython(TYPED, typed=True)
        self.assertIn("3 1 2", out)

    def test_py_entry_and_ail_entry_build_the_same_program(self):
        write(self.dir, TYPED)
        shutil.copy(self.dir / "main.py", self.dir / "app.ail")
        a, exe_py = compile_program(self.dir, "main.py", "1", True)
        b, exe_ail = compile_program(self.dir, "app.ail", "1", True)
        self.assertEqual((a.returncode, b.returncode), (0, 0), a.stderr + b.stderr)
        run = [subprocess.run([str(e)], capture_output=True).stdout for e in (exe_py, exe_ail)]
        self.assertEqual(run[0], run[1])

    def test_ail_suffix_modules_in_python_syntax(self):
        # CPython can only import util.py, so it runs a copy of the program with that spelling
        reference = self.dir / "reference"
        reference.mkdir()
        write(reference, TYPED)
        expected = subprocess.run([sys.executable, "main.py"], cwd=reference, capture_output=True).stdout
        files = dict(TYPED)
        files["util.ail"] = files.pop("util.py")
        write(self.dir, files)
        built, exe = compile_program(self.dir, "main.py", "1", True)
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertEqual(subprocess.run([str(exe)], capture_output=True).stdout, expected)

    def test_inheritance_and_isinstance_across_files(self):
        out = self.same_as_cpython({
            "main.py": '''from shapes import Shape, Square
import shapes


class Tall(Shape):
    def area(self) -> int:
        return self.w * 3


def main() -> int:
    items: list[Shape] = [Square(2), Tall(4), shapes.Square(5)]
    total = 0
    for it in items:
        total += it.area()
        print(it.name(), isinstance(it, Square), isinstance(it, shapes.Shape))
    print(total)
    return 0


main()
''',
            "shapes.py": '''class Shape:
    def __init__(self, w: int):
        self.w = w

    def area(self) -> int:
        return 0

    def name(self) -> str:
        return "shape"


class Square(Shape):
    def area(self) -> int:
        return self.w * self.w

    def name(self) -> str:
        return "square"
''',
        })
        self.assertIn("square True True", out)


class InitOrder(ModulesBase):
    def test_module_level_code_runs_once_in_cpython_order(self):
        out = self.same_as_cpython({
            "main.py": '''print("main 1")
import first
print("main 2", first.VALUE)
from second import twice
import first
import second as sec
print("main 3", twice(4), sec.COUNT)


def main():
    print("main body", __name__)


main()
''',
            "first.py": '''print("first starts", __name__)
import second
VALUE = second.COUNT * 10
print("first ends")
''',
            "second.py": '''print("second starts", __name__)
COUNT = 3


def twice(x):
    return x * 2


for i in range(2):
    print("second loop", i)
if __name__ == "__main__":
    print("never")
else:
    print("second is a library")
''',
        })
        self.assertEqual(out.splitlines()[:3], ["main 1", "first starts first", "second starts second"])
        self.assertEqual(out.count("second starts"), 1)

    def test_name_is_main_only_in_the_entry(self):
        out = self.same_as_cpython({
            "main.py": '''import lib
print(__name__, lib.where(), lib.NAME)
if __name__ == "__main__":
    print("entry runs")
''',
            "lib.py": '''NAME = __name__


def where():
    return __name__ + "!"


if __name__ == "__main__":
    print("lib as a script")
''',
        })
        self.assertEqual(out, "__main__ lib! lib\nentry runs\n")

    def test_uncalled_main_rule_is_entry_only(self):
        files = {
            "main.py": '''import lib
print(lib.f(2))
''',
            "lib.py": '''def main():
    print("lib main")


def f(x):
    return x + 1
''',
        }
        self.assertEqual(self.same_as_cpython(files), "3\n")
        # the entry's own uncalled main is still refused
        self.setUp()
        write(self.dir, {"main.py": "import lib\n\n\ndef main():\n    print(lib.f(1))\n", "lib.py": files["lib.py"]})
        built, _ = compile_program(self.dir)
        self.assertEqual(built.returncode, 2)
        self.assertIn("main() is defined but never called", built.stderr)


class NameClashes(ModulesBase):
    def test_same_names_in_every_file_keep_their_own_meaning(self):
        out = self.same_as_cpython({
            "main.py": '''import a
import b
from a import calc as a_calc

LIMIT = 100


def calc(x: int) -> int:
    return x + LIMIT


def main() -> int:
    total = 5
    print(calc(1), a.calc(1), b.calc(1), a_calc(2), LIMIT, a.LIMIT, b.LIMIT)
    print(sum([1, 2]), a.total_of([1, 2, 3]), b.total_of([4, 5]))
    print(a.doubled([1, 2]), LIMIT, total)
    return 0


main()
''',
            "a.py": '''LIMIT = 1


def calc(x: int) -> int:
    return x + LIMIT


def total_of(xs: list[int]) -> int:
    return sum(xs)


def doubled(xs: list[int]) -> list[int]:
    return [LIMIT * 2 for LIMIT in xs]
''',
            "b.py": '''LIMIT = 2


def calc(LIMIT: int) -> int:
    return LIMIT * 2


def total_of(xs: list[int]) -> int:
    total = 0
    for x in xs:
        total += x + LIMIT
    return total
''',
        })
        self.assertEqual(out.splitlines()[0], "101 2 2 3 100 1 2")
        self.assertEqual(out.splitlines()[1], "3 6 13")

    def test_classes_and_methods_named_like_functions_elsewhere(self):
        self.same_as_cpython({
            "main.py": '''import counter
from counter import Counter


class Box:
    def total(self) -> int:
        return 1


def total() -> int:
    return 99


def main() -> int:
    c = Counter()
    c.add(2)
    c.add(3)
    print(c.total(), counter.total(c), total(), Box().total())
    return 0


main()
''',
            "counter.py": '''class Counter:
    def __init__(self):
        self.n = 0

    def add(self, k: int) -> None:
        self.n += k

    def total(self) -> int:
        return self.n


def total(c: Counter) -> int:
    return c.total() * 10
''',
        })


class SharedStdlib(ModulesBase):
    def test_modules_that_import_the_same_standard_modules(self):
        out = self.same_as_cpython({
            "main.py": '''import math
from dataclasses import dataclass
import shapes
import more


@dataclass
class Dot:
    x: int


def main() -> int:
    print(math.sqrt(16.0), shapes.hyp(3.0, 4.0), more.circle(1.0) > 3.14, Dot(2).x)
    return 0


main()
''',
            "shapes.py": '''import math
from dataclasses import dataclass


def hyp(a: float, b: float) -> float:
    return math.sqrt(a * a + b * b)
''',
            "more.py": '''import math
from dataclasses import dataclass, field


def circle(r: float) -> float:
    return math.pi * r * r
''',
        })
        self.assertEqual(out, "4.0 5.0 True 2\n")

    def test_one_name_for_two_different_imports_is_refused(self):
        self.refused({"a.py": "import math as m\n\n\ndef f():\n    return m.pi\n",
                      "b.py": "import heapq as m\n\n\ndef g():\n    return m\n",
                      "main.py": "import a\nimport b\nprint(a.f())\n"}, "bound by an import")


class Cycles(ModulesBase):
    def test_cycle_through_function_bodies_works(self):
        out = self.same_as_cpython({
            "main.py": '''import ping


def main():
    print(ping.ping(3))


main()
''',
            "ping.py": '''import pong


def ping(n):
    if n == 0:
        return "done"
    return pong.pong(n - 1)
''',
            "pong.py": '''import ping


def pong(n):
    return ping.ping(n)
''',
        })
        self.assertEqual(out, "done\n")


class Refusals(ModulesBase):
    def test_package_dotted_and_relative_imports(self):
        (self.dir / "pkg").mkdir()
        (self.dir / "pkg" / "__init__.py").write_text("")
        self.refused({"main.py": "import pkg\nprint(1)\n"}, "package 'pkg'")
        self.refused({"main.py": "import pkg.sub\nprint(1)\n"}, "'pkg.sub'")
        self.refused({"main.py": "from pkg.sub import f\nprint(f)\n"}, "'pkg.sub'")
        self.refused({"main.py": "from . import m\nprint(m)\n"}, "relative import")
        self.refused({"main.py": "from .m import f\nprint(f)\n"}, "relative import")

    def test_star_and_private_imports(self):
        files = {"lib.py": "def f():\n    return 1\n\n\ndef _g():\n    return 2\n"}
        self.refused({**files, "main.py": "from lib import *\nprint(f())\n"}, "import *")
        self.refused({**files, "main.py": "from lib import _g\nprint(_g())\n"}, "private name")
        self.refused({**files, "main.py": "import lib\nprint(lib._g())\n"}, "private name")

    def test_imports_below_the_top_level(self):
        self.refused({"lib.py": "X = 1\n", "main.py": "def f():\n    import lib\n    return lib.X\n\n\nprint(f())\n"},
                     "below the top level")
        self.refused({"lib.py": "X = 1\n", "main.py": "if True:\n    import lib\nprint(lib.X)\n"}, "below the top level")

    def test_module_as_value_and_attribute_assignment(self):
        files = {"lib.py": "X = 1\n\n\ndef f():\n    return X\n"}
        self.refused({**files, "main.py": "import lib\nm = lib\nprint(m.f())\n"}, "used as a value")
        self.refused({**files, "main.py": "import lib\nprint(len([lib]))\n"}, "used as a value")
        self.refused({**files, "main.py": "import lib\nlib.X = 5\nprint(lib.f())\n"}, "assignment to another module")
        self.refused({**files, "main.py": "import lib\nprint(lib.nothing)\n"}, "no top-level name 'nothing'")
        self.refused({**files, "main.py": "from lib import nothing\nprint(nothing)\n"}, "no top-level name 'nothing'")

    def test_rebound_module_name(self):
        self.refused({"lib.py": "X = 1\nX = 2\n", "main.py": "import lib\nprint(lib.X)\n"}, "rebound")
        self.refused({"lib.py": "X = 1\n\n\ndef bump():\n    global X\n    X += 1\n",
                      "main.py": "from lib import X, bump\nbump()\nprint(X)\n"}, "rebound")
        self.refused({"lib.py": "def f():\n    return 1\n", "main.py": "from lib import f\n\n\ndef f():\n    return 2\n\n\nprint(f())\n"},
                     "imported and also")

    def test_ambiguous_and_brace_and_self_imports(self):
        self.refused({"lib.py": "X = 1\n", "lib.ail": "X = 2\n", "main.py": "import lib\nprint(lib.X)\n"}, "ambiguous")
        self.refused({"lib.ail": "fn f() -> int { return 1; }\n", "main.py": "import lib\nprint(lib.f())\n"},
                     "brace syntax")
        self.refused({"main.py": "import main\nprint(1)\n"}, "entry file a second time")

    def test_class_name_defined_twice(self):
        self.refused({"a.py": "class Item:\n    pass\n", "b.py": "class Item:\n    pass\n",
                      "main.py": "import a\nimport b\nprint(a.Item is b.Item)\n"}, "'Item'")

    def test_entry_name_that_hides_a_builtin_other_modules_use(self):
        self.refused({"lib.py": "def f(xs):\n    return sum(xs)\n",
                      "main.py": "import lib\n\n\ndef sum(xs):\n    return 0\n\n\nprint(lib.f([1, 2]), sum([1]))\n"},
                     "builtin")

    def test_cycle_that_reads_a_name_early(self):
        err = self.refused({"a.py": "import b\nTABLE = [1, 2]\n", "b.py": "import a\nFIRST = a.TABLE[0]\n",
                            "main.py": "import a\nprint(a.TABLE, 1)\n"}, "import cycle", "a.TABLE")
        self.assertIn("b.py:2:", err)
        self.refused({"a.py": "import b\n\n\ndef f():\n    return 1\n", "b.py": "from a import f\n\n\ndef g():\n    return f()\n",
                      "main.py": "import a\nprint(a.f())\n"}, "import cycle", "has defined f")

    def test_error_in_an_imported_file_names_that_file(self):
        write(self.dir, {"lib.py": "def f():\n    return 1\n\n\ndef g(x: int):\n    return x.nosuch(1)\n",
                         "main.py": "import lib\nprint(lib.f(), lib.g(2))\n"})
        built, _ = compile_program(self.dir, typed=True)
        self.assertEqual(built.returncode, 3, built.stderr)
        self.assertTrue(built.stderr.startswith("lib.py:6:5: not in the subset: x.nosuch()"), built.stderr)


class SingleFilePrograms(ModulesBase):
    def test_a_program_without_sibling_imports_is_not_touched(self):
        import ail_modules
        text = "import math\nfrom dataclasses import dataclass\n\n\ndef main():\n    print(math.sqrt(4.0))\n\n\nmain()\n"
        write(self.dir, {"main.py": text, "other.py": "X = 1\n"})
        self.assertIsNone(ail_modules.merge_program(self.dir / "main.py", text))

    def test_stdlib_name_is_shadowed_by_a_sibling_file_as_in_cpython(self):
        out = self.same_as_cpython({"main.py": "import heapq\nprint(heapq.VALUE)\n", "heapq.py": "VALUE = 5\n"})
        self.assertEqual(out, "5\n")

    def test_check_command_sees_the_whole_program(self):
        write(self.dir, TYPED)
        done = subprocess.run([sys.executable, "-B", CLI, "check", "main.py"], cwd=self.dir, capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(json.loads(done.stdout)["status"], "passed")
        write(self.dir, {"util.py": 'LIMIT = 10\nNAME = "u"\n\n\ndef helper(x: int) -> int:\n    return x * 2 + [1]\n'})
        done = subprocess.run([sys.executable, "-B", CLI, "check", "main.py"], cwd=self.dir, capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(done.returncode, 1)
        diagnostic = json.loads(done.stdout)["diagnostics"][0]
        self.assertTrue(diagnostic["path"].endswith("util.py"), diagnostic)
        self.assertEqual(diagnostic["line"], 5)


if __name__ == "__main__":
    unittest.main()
