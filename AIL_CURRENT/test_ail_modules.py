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
* `_private` imports, imports below the top level, a module used as a value, a clashing class name
  are refused by name.

G2 (the classes after `SingleFilePrograms`) adds, each compared with CPython 3.12 on trees of files:

* packages with and without `__init__.py` (namespace packages, portions in two directories),
  `import p.m`, `import p.m as x`, `from p import m`, `from p.m import f`, relative imports at every
  level, init order and once-only initialisation, submodule attributes, cycles inside a package;
* `from m import *` with and without `__all__` (literal, `+=`, `.append`), the underscore rule, a
  package listing submodules, re-exports through star imports;
* module state: `global` in functions, `m.x = v` / `m.x += 1` from other modules and from functions,
  names created from outside, `from m import x` as a snapshot, re-exported snapshots;
* `AIL_PATH` (mirrored by PYTHONPATH for the oracle), the entry directory first, a local package that
  shadows a modelled module (with a note), a directory that does not shadow one;
* the named refusals (relative import without a package, missing module or name, ambiguous package,
  a submodule read before its import, star-import limits, writes that cannot be followed, imports in
  functions, `__file__`, `importlib`, `__import__`).
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
        path = Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def compile_program(directory, entry="main.py", ir="1", typed=False, extra=(), ail_path=None):
    exe = Path(directory) / ("out_ir" + ir)
    if exe.exists():
        exe.unlink()
    env = dict(os.environ, AIL_IR=ir)
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_PATH", None)
    if ail_path is not None:
        env["AIL_PATH"] = ail_path
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

    def same_as_cpython(self, files, entry="main.py", typed=False, stdin=b"", irs=("0", "1"), ail_path=None):
        """`ail_path` lists directories (relative to the test directory) for AIL_PATH, and for the
        oracle's PYTHONPATH, which is what AIL_PATH mirrors."""
        write(self.dir, files)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        search = None
        if ail_path:
            search = os.pathsep.join(str(self.dir / p) for p in ail_path)
            env["PYTHONPATH"] = search
        expected = subprocess.run([sys.executable, "-B", entry], cwd=self.dir, input=stdin, capture_output=True,
                                  timeout=60, env=env)
        self.assertEqual(expected.returncode, 0, expected.stderr.decode())
        for ir in irs:
            built, exe = compile_program(self.dir, entry, ir, typed, ail_path=search)
            self.assertEqual(built.returncode, 0, "AIL_IR=%s: %s" % (ir, built.stderr))
            ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, expected.stdout, "AIL_IR=%s" % ir)
            self.assertEqual(ran.returncode, 0)
        self.built_stderr = built.stderr
        return expected.stdout.decode()

    def refused(self, files, *needles, entry="main.py", ail_path=None):
        write(self.dir, files)
        env = dict(os.environ)
        env.pop("AIL_PATH", None)
        if ail_path:
            env["AIL_PATH"] = os.pathsep.join(str(self.dir / p) for p in ail_path)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", entry, "-o", str(self.dir / "out")], cwd=self.dir,
                               capture_output=True, text=True, timeout=120, env=env)
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
    def test_private_imports(self):
        files = {"lib.py": "def f():\n    return 1\n\n\ndef _g():\n    return 2\n"}
        self.refused({**files, "main.py": "from lib import _g\nprint(_g())\n"}, "private name")
        self.refused({**files, "main.py": "import lib\nprint(lib._g())\n"}, "private name")

    def test_imports_below_the_top_level(self):
        self.refused({"lib.py": "print(1)\nX = 1\n", "main.py": "def f():\n    import lib\n    return lib.X\n\n\nprint(f())\n"},
                     "function-level `import lib`", "lib.py:1")
        self.assertEqual(self.same_as_cpython({"lib.py": "X = 1\n", "main.py": "def f():\n    import lib\n    return lib.X\n\n\nprint(f())\n"}), "1\n")
        self.refused({"lib.py": "X = 1\n", "main.py": "if True:\n    import lib\nprint(lib.X)\n"}, "below the top level")

    def test_module_as_value_and_attribute_assignment(self):
        files = {"lib.py": "X = 1\n\n\ndef f():\n    return X\n"}
        self.refused({**files, "main.py": "import lib\nm = lib\nprint(m.f())\n"}, "used as a value")
        self.refused({**files, "main.py": "import lib\nprint(len([lib]))\n"}, "used as a value")
        self.refused({**files, "main.py": "import lib\nprint(lib.nothing)\n"}, "no top-level name 'nothing'")
        self.refused({**files, "main.py": "from lib import nothing\nprint(nothing)\n"}, "no top-level name 'nothing'")

    def test_imported_name_defined_again(self):
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

    def test_check_command_points_into_a_package_file(self):
        write(self.dir, SHOP)
        text = SHOP["shop/util/text.py"].replace("return s + ", "return 1 + [2] + ")
        write(self.dir, {"shop/util/text.py": text})
        done = subprocess.run([sys.executable, "-B", CLI, "check", "main.py"], cwd=self.dir, capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        diagnostic = json.loads(done.stdout)["diagnostics"][0]
        self.assertTrue(diagnostic["path"].replace("\\", "/").endswith("shop/util/text.py"), diagnostic)
        self.assertEqual(diagnostic["line"], 7)       # the def whose body is wrong, as for a flat module


# ------------------------------------------------------------------------------ G2: packages

SHOP = {
    "main.py": '''import shop.pricing
import shop.report as rep
from shop import models, TAX
from shop.models import Item, make_item
from shop.util.text import pad


def main() -> int:
    items: list[Item] = [make_item("a", 3), Item("b", 4)]
    print(shop.pricing.total(items), rep.render(items), pad("x", 3), TAX, models.DEFAULT)
    print(shop.models.DEFAULT, shop.util.text.WIDTH, Item("c", 1).name)
    return 0


if __name__ == "__main__":
    main()
''',
    "shop/__init__.py": '''TAX = 3
from .models import Item
''',
    "shop/models.py": '''from dataclasses import dataclass

DEFAULT = 5


@dataclass
class Item:
    name: str
    qty: int


def make_item(name: str, qty: int) -> Item:
    return Item(name, qty + DEFAULT)
''',
    "shop/pricing.py": '''from . import TAX
from .models import Item, DEFAULT


def total(items: list[Item]) -> int:
    t = 0
    for it in items:
        t += it.qty * TAX + DEFAULT
    return t
''',
    "shop/report.py": '''from .pricing import total
from .util.text import pad
from .models import Item


def render(items: list[Item]) -> str:
    return pad(str(total(items)), 2) + ":" + str(len(items))
''',
    "shop/util/__init__.py": "",
    "shop/util/text.py": '''from .. import models
from ..models import DEFAULT

WIDTH = 4


def pad(s: str, n: int) -> str:
    return s + "-" * (n + models.DEFAULT - DEFAULT)
''',
}


class Packages(ModulesBase):
    def test_package_import_forms_typed_path(self):
        out = self.same_as_cpython(SHOP, typed=True)
        self.assertEqual(out.splitlines()[1], "5 4 c")

    def test_init_files_run_once_parents_first(self):
        out = self.same_as_cpython({
            "main.py": '''print("main start")
import app
print("main 2", app.NAME)
import app.core.engine as eng
from app.core import helper_value
from app import settings
print(eng.run(), helper_value, settings.DEBUG)
import app.core


def main():
    print("main", __name__, app.core.__name__, eng.__name__, settings.__name__)


main()
''',
            "app/__init__.py": '''"""the app package"""
print("app init", __name__)
NAME = "app"
from . import settings
''',
            "app/settings.py": '''print("settings init", __name__)
DEBUG = True
''',
            "app/core/__init__.py": '''print("core init", __name__)
from .engine import run
helper_value = run()
''',
            "app/core/engine.py": '''print("engine init", __name__)
from .. import settings


def run():
    return 40 + (2 if settings.DEBUG else 0)
''',
        })
        self.assertEqual(out.splitlines()[:5], ["main start", "app init app", "settings init app.settings", "main 2 app",
                                                "core init app.core"])
        self.assertEqual(out.count("settings init"), 1)
        self.assertIn("main __main__ app.core app.core.engine app.settings", out)

    def test_namespace_packages_without_init_files(self):
        out = self.same_as_cpython({
            "main.py": '''import ns.alpha
from ns.sub import gamma
import ns.beta as b
print(ns.alpha.double(4), gamma.NAME, b.f(), ns.alpha.beta.f())
''',
            "ns/alpha.py": '''from . import beta


def double(x):
    return x * 2 + beta.f()
''',
            "ns/beta.py": '''def f():
    return 1
''',
            "ns/sub/gamma.py": '''NAME = "gamma:" + __name__
''',
        })
        self.assertEqual(out, "9 gamma:ns.sub.gamma 1 1\n")

    def test_namespace_package_spread_over_two_directories(self):
        out = self.same_as_cpython({
            "app/main.py": '''import ns.alpha
import ns.delta
from ns import delta
print(ns.alpha.A, ns.delta.D, delta.D, ns.alpha.D_SEEN)
''',
            "app/ns/alpha.py": '''from . import delta
A = 1
D_SEEN = delta.D
''',
            "libs/ns/delta.py": '''D = 40
''',
        }, entry="app/main.py", ail_path=["libs"])
        self.assertEqual(out, "1 40 40 40\n")

    def test_relative_imports_at_every_level(self):
        out = self.same_as_cpython({
            "main.py": '''import a.b
from a.b import c
print(a.b.AX, a.b.AY, c.Z, c.W, c.D4, a.x.X)
''',
            "a/__init__.py": "",
            "a/x.py": "X = 1\n",
            "a/y.py": "Y = 2\n",
            "a/b/__init__.py": '''from .. import x as ax
from ..y import Y as AY
from . import c
AX = ax.X
''',
            "a/b/c.py": '''from . import d
from .d import D
from .. import x
from ..x import X
Z = X + x.X
W = D + d.D
D4 = d.D * 4
''',
            "a/b/d.py": "D = 4\n",
        })
        self.assertEqual(out, "1 2 2 8 16 1\n")

    def test_submodule_attributes_follow_imports(self):
        out = self.same_as_cpython({
            "main.py": '''import pkg
import pkg.b


def g():
    return pkg.a.fa() + pkg.b.fb()


print(pkg.a.fa(), pkg.b.fb(), pkg.fa(), g())
''',
            "pkg/__init__.py": "from .a import fa\n",
            "pkg/a.py": "def fa():\n    return 1\n",
            "pkg/b.py": "def fb():\n    return 2\n",
        })
        self.assertEqual(out, "1 2 1 3\n")

    def test_cycles_between_package_modules(self):
        out = self.same_as_cpython({
            "main.py": '''import pkg
from pkg import a, run
print(run(), a.ping(2))
''',
            # core runs while pkg is still starting: `from . import util` finds no attribute yet and
            # imports the submodule, as CPython does
            "pkg/__init__.py": '''from .core import run
from . import util
''',
            "pkg/core.py": '''from . import util


def run():
    return util.val()
''',
            "pkg/util.py": '''def val():
    return 7
''',
            "pkg/a.py": '''from . import b


def ping(n):
    if n == 0:
        return "done"
    return b.pong(n - 1)
''',
            "pkg/b.py": '''from . import a


def pong(n):
    return a.ping(n)
''',
        })
        self.assertEqual(out, "7 done\n")

    def test_dunder_attributes_and_children_read_by_the_init(self):
        out = self.same_as_cpython({
            "main.py": '''import pkg
from pkg import __version__ as v
print(pkg.__version__, pkg.__name__, v, pkg.total)
''',
            "pkg/__init__.py": '''__version__ = "2.0"
from . import a, b
total = a.A + b.B
''',
            "pkg/a.py": "A = 1\n",
            "pkg/b.py": "from . import a\nB = a.A + 1\n",
        })
        self.assertEqual(out, "2.0 pkg 2.0 3\n")

    def test_entry_imports_under_the_main_guard(self):
        out = self.same_as_cpython({
            "main.py": '''print("before")
if __name__ == "__main__":
    from tools import util
    import tools.extra as ex
    print(util.hello(), ex.X)
''',
            "tools/__init__.py": 'print("tools init")\n',
            "tools/util.py": 'def hello():\n    return "hi"\n',
            "tools/extra.py": "X = 5\n",
        })
        self.assertEqual(out, "before\ntools init\nhi 5\n")


class StarImports(ModulesBase):
    def test_all_underscore_rule_and_submodules(self):
        out = self.same_as_cpython({
            "main.py": '''from plain import *
from listed import *
from lib import *
print(pub(), PUB_K, other(), KEEP, h(), one.f(), two.f())
''',
            # no __all__: every public name (not _private), imports included
            "plain.py": '''import math
SECRET = 3
_hidden = 4


def pub():
    return math.floor(2.5) + _hidden


PUB_K = SECRET
''',
            "listed.py": '''__all__ = ["other", "KEEP"]
__all__ += ["h"]
__all__.append("late")


def other():
    return "o"


def h():
    return "h"


def late():
    return "l"


def notlisted():
    return "n"


KEEP = 8
''',
            "lib/__init__.py": '''__all__ = ["one", "two"]
''',
            "lib/one.py": "def f():\n    return 1\n",
            "lib/two.py": "def f():\n    return 2\n",
        })
        self.assertEqual(out, "6 3 o 8 h 1 2\n")

    def test_reexport_with_star_in_init_files(self):
        out = self.same_as_cpython({
            "main.py": '''import pkg
from pkg import tool, VALUE
from pkg import *
print(tool(), VALUE, other(), pkg.tool(), core.tool())
''',
            "pkg/__init__.py": '''from .core import *
from .more import *
''',
            "pkg/core.py": '''__all__ = ["tool", "VALUE"]
VALUE = 11


def tool():
    return "tool"


def internal():
    return "internal"
''',
            "pkg/more.py": '''def other():
    return "other"
''',
        })
        self.assertEqual(out, "tool 11 other tool tool\n")


# ------------------------------------------------------------------------------ G2: module state

STATE = {
    "state.py": '''counter = 0
log = []
config = {"mode": "a"}


def bump(n=1):
    global counter
    counter += n
    log.append(n)
    return counter


def current():
    return counter


def set_mode(m):
    config["mode"] = m
''',
    "other.py": '''import state
from state import counter, log, config


def peek():
    return counter


def live():
    return state.counter


def bump_via():
    state.counter += 10
    return state.counter


def reset():
    state.counter = 0


def read_extra():
    return state.extra


def logged():
    return len(log), len(state.log), config["mode"]
''',
}


class ModuleState(ModulesBase):
    def test_global_statement_and_attribute_writes_share_one_variable(self):
        out = self.same_as_cpython({
            **STATE,
            "main.py": '''import state
import other
from state import bump, counter as c0, config

hits = 0


def hit():
    global hits
    hits += 1
    state.counter = state.counter + 100
    return hits


print(bump(), bump(2), state.counter, state.current(), c0, other.counter, other.peek())
print(other.live(), other.bump_via(), state.counter, state.current())
state.counter += 1
state.counter = state.counter * 2
print(state.current(), other.live(), hit(), hit(), state.counter, hits)
other.reset()
print(state.counter, state.current(), c0, other.peek())
state.extra = "new"
print(state.extra, other.read_extra())
state.set_mode("b")
print(config["mode"], other.logged(), state.log)
state.mark = state.counter + 1
print(state.counter, state.mark, state.current())
''',
        })
        lines = out.splitlines()
        self.assertEqual(lines[0], "1 3 3 3 0 0 0")
        self.assertEqual(lines[1], "3 13 13 13")

    def test_a_constant_that_a_loop_or_global_rebinds_is_not_folded(self):
        # single file: `b = a` was folded to the first value of `a` (a wrong-code bug before G2)
        out = self.same_as_cpython({
            "main.py": '''a = 0
for i in range(3):
    a += 1
b = a
print(a, b)
if b > 1:
    a = 10
c = a + 1
print(c)
n = 0


def bump(k):
    global n
    n += k
    return n


bump(2)
m = n * 2
bump(5)
print(n, m)
''',
        })
        self.assertEqual(out, "3 3\n11\n7 4\n")

    def test_from_import_takes_a_snapshot_at_import_time(self):
        out = self.same_as_cpython({
            **STATE,
            "pkg/__init__.py": '''from state import counter, bump
bump(5)
from state import counter as later
''',
            "main.py": '''import state
state.bump(2)
import pkg
from pkg import counter, later
from state import counter as direct
state.bump(1)
print(state.counter, pkg.counter, counter, later, direct, pkg.later)


def late_import_value():
    return counter, later, direct, state.counter


print(late_import_value())
''',
        })
        self.assertEqual(out.splitlines()[0], "8 2 2 7 7 7")
        self.assertEqual(out.splitlines()[1], "(2, 7, 7, 8)")

    def test_package_modules_that_update_one_shared_state_module(self):
        out = self.same_as_cpython({
            "main.py": '''from game import engine, rules
from game.state import score, history
import game.state

engine.play(3)
engine.play(4)
print(game.state.score, score, rules.verdict(), len(history), game.state.history)
engine.reset()
print(game.state.score, rules.verdict(), score)
''',
            "game/__init__.py": "",
            "game/state.py": '''score = 0
history = []
''',
            "game/engine.py": '''from . import state


def play(points):
    state.score += points
    state.history.append(points)


def reset():
    state.score = 0
''',
            "game/rules.py": '''from .state import score as start_score
from . import state


def verdict():
    return "win" if state.score > 5 else "keep going"
''',
        })
        self.assertEqual(out.splitlines()[0], "7 0 win 2 [3, 4]")

    def test_module_state_in_a_package_with_init_code(self):
        out = self.same_as_cpython({
            "main.py": '''import cfg
from cfg import settings
import cfg.use as use

cfg.settings.depth = 3
settings.name = "main"
print(use.describe(), cfg.level, cfg.settings.depth)
cfg.level = 9
print(use.describe(), use.level_now())
''',
            "cfg/__init__.py": '''class Settings:
    def __init__(self):
        self.name = "init"
        self.depth = 1


settings = Settings()
level = 1
''',
            "cfg/use.py": '''from . import settings
import cfg


def describe():
    return settings.name + str(settings.depth) + str(cfg.level)


def level_now():
    return cfg.level
''',
        })
        self.assertEqual(out, "main31 1 3\nmain39 9\n")


# ------------------------------------------------------------------------------ G2: search path

class SearchPath(ModulesBase):
    def test_ail_path_mirrors_pythonpath_and_the_entry_directory_wins(self):
        out = self.same_as_cpython({
            "app/main.py": '''import shared
import extra.tools as t
from extra import more
print(shared.WHERE, t.f(), more.G)
''',
            "app/shared.py": 'WHERE = "app"\n',
            "libs/shared.py": 'WHERE = "libs"\n',
            "libs/extra/__init__.py": "",
            "libs/extra/tools.py": "def f():\n    return 3\n",
            "libs/extra/more.py": "G = 4\n",
        }, entry="app/main.py", ail_path=["libs"])
        self.assertEqual(out, "app 3 4\n")

    def test_a_package_that_shadows_a_modelled_module_wins_with_a_note(self):
        out = self.same_as_cpython({
            "main.py": '''import json
print(json.TAG, json.dumps2([1]))
''',
            "json/__init__.py": '''TAG = "mine"
from .enc import dumps2
''',
            "json/enc.py": "def dumps2(x):\n    return str(x)\n",
        })
        self.assertEqual(out, "mine [1]\n")
        self.assertIn("shadows the standard library module json", self.built_stderr)

    def test_a_directory_named_like_a_standard_module_does_not_shadow_it(self):
        out = self.same_as_cpython({
            "main.py": '''import math
print(math.floor(2.5))
''',
            "math/readme.txt": "just data\n",
        })
        self.assertEqual(out, "2\n")


# ------------------------------------------------------------------------------ G2: refusals

class PackageRefusals(ModulesBase):
    def test_relative_imports_that_have_no_package(self):
        pkg = {"pkg/__init__.py": "", "pkg/m.py": "X = 1\n"}
        self.refused({**pkg, "main.py": "from . import m\nprint(m)\n"}, "entry file")
        self.refused({**pkg, "main.py": "from .m import X\nprint(X)\n"}, "entry file")
        self.refused({**pkg, "top.py": "from . import q\n", "q.py": "Q = 1\n", "main.py": "import top\n"},
                     "not inside a package")
        self.refused({**pkg, "pkg/deep.py": "from ... import m\n", "main.py": "import pkg.deep\n"},
                     "beyond the top-level package")

    def test_missing_modules_and_names(self):
        pkg = {"pkg/__init__.py": "A = 1\n", "pkg/m.py": "X = 1\n"}
        self.refused({**pkg, "main.py": "import pkg.nosuch\n"}, "no module named 'pkg.nosuch'")
        self.refused({**pkg, "main.py": "from pkg.nosuch import f\n"}, "no module named 'pkg.nosuch'")
        self.refused({**pkg, "main.py": "from pkg import nosuch\n"}, "no top-level name 'nosuch'")
        self.refused({**pkg, "main.py": "import pkg.m.deeper\n"}, "not a package")

    def test_package_and_module_with_the_same_name_are_ambiguous(self):
        self.refused({"pkg/__init__.py": "", "pkg.py": "X = 1\n", "main.py": "import pkg\n"}, "ambiguous")
        self.refused({"pkg/__init__.py": "", "pkg/__init__.ail": "", "main.py": "import pkg\n"}, "ambiguous")

    def test_submodule_read_before_the_import_that_binds_it(self):
        pkg = {"pkg/__init__.py": "", "pkg/a.py": "def f():\n    return 1\n"}
        self.refused({**pkg, "main.py": "import pkg\nprint(pkg.a.f())\nimport pkg.a\n"}, "before the import that binds it")
        self.refused({**pkg, "main.py": "import pkg\nprint(pkg.a.f())\n"}, "nothing imports it")

    def test_cycles_that_read_a_name_before_it_exists(self):
        pkg = {"pkg/__init__.py": ""}
        err = self.refused({**pkg, "main.py": "import pkg.a\n", "pkg/a.py": "from . import b\n\n\ndef f():\n    return 1\n",
                            "pkg/b.py": "from .a import f\n"}, "import cycle", "has defined f")
        self.assertIn("b.py:1:", err)
        self.refused({**pkg, "main.py": "import pkg.a\n", "pkg/a.py": "import pkg.b\n\n\ndef f():\n    return 1\n",
                      "pkg/b.py": "import pkg.a\nX = pkg.a.f()\n"}, "before the import that binds it")

    def test_two_star_imports_that_bind_one_name_differently(self):
        self.refused({"a.py": "def f():\n    return 1\n", "b.py": "def f():\n    return 2\n",
                      "main.py": "from a import *\nfrom b import *\nprint(f())\n"}, "bound to two different imports")

    def test_star_import_limits(self):
        pkg = {"pkg/__init__.py": "X = 1\n", "pkg/a.py": "def f():\n    return 1\n"}
        self.refused({**pkg, "main.py": "import pkg.a\nfrom pkg import *\nprint(X)\n"}, "without __all__")
        self.refused({"lib.py": "__all__ = [name for name in 'ab']\nA = 1\n", "main.py": "from lib import *\n"},
                     "cannot read")
        self.refused({"lib.py": "__all__ = ['_g']\n\n\ndef _g():\n    return 1\n", "main.py": "from lib import *\n"},
                     "private name")
        self.refused({"lib.py": "__all__ = ['nothing']\n", "main.py": "from lib import *\n"}, "nothing")

    def test_module_attribute_writes_that_cannot_be_followed(self):
        files = {"lib.py": "import math\nfrom heapq import heappush\nX = 1\n"}
        self.refused({**files, "main.py": "import lib\nlib.math = 3\n"}, "standard-library import")
        self.refused({**files, "main.py": "import lib\ndel lib.X\n"}, "del lib.X")
        self.refused({**files, "main.py": "import lib\nprint([1 for lib.X in range(2)])\n"}, "comprehension")
        self.refused({"pkg/__init__.py": "", "pkg/a.py": "A = 1\n", "main.py": "import pkg.a\npkg.a = 3\n"},
                     "a submodule")

    def test_import_in_a_function_of_a_package_module(self):
        self.assertEqual(self.same_as_cpython({"pkg/__init__.py": "", "pkg/a.py": "def f():\n    from . import b\n    return b.X\n",
                      "pkg/b.py": "X = 1\n", "main.py": "import pkg.a\nprint(pkg.a.f())\n"}), "1\n")

    def test_module_file_attributes_and_dynamic_imports(self):
        # `__file__` is the module's own source path (test_ail_ex18); the other module dunders stay refused.
        out = self.same_as_cpython({"lib.py": "X = 1\nVALUE = __file__\n",
                                    "main.py": "import lib\nprint(lib.__file__)\nprint(lib.VALUE)\n"})
        self.assertIn("lib.py", out)
        for dunder in ("__package__", "__path__", "__spec__", "__loader__", "__cached__", "__builtins__"):
            self.refused({"lib.py": "X = 1\n", "main.py": "import lib\nprint(lib.%s)\n" % dunder}, "not available")
        # the front end refuses these (exit 3) by name, with the same hint
        for source, needle in (("import importlib\nm = importlib.import_module('math')\nprint(m)\n", "importlib"),
                               ("m = __import__('math')\nprint(m)\n", "__import__")):
            write(self.dir, {"main.py": source})
            built, _ = compile_program(self.dir)
            self.assertEqual(built.returncode, 3, built.stderr)
            self.assertIn(needle, built.stderr)
            self.assertIn("write instead", built.stderr)

    def test_module_variable_written_in_a_class_body(self):
        self.refused({"lib.py": "X = 1\n", "main.py": "import lib\n\n\nclass K:\n    lib.X = 2\n\n\nprint(lib.X)\n"},
                     "class body")



PKG = {"pkg/__init__.py": "", "pkg/a.py": "X = 1\n\n\ndef f():\n    return \"fa\"\n", "pkg/b.py": "Y = 2\n"}


class ImportOrder(ModulesBase):
    """Import orders for which CPython raises AttributeError / ModuleNotFoundError or binds a different object.

    Each program is run by CPython first: the claim "CPython does something else here" is checked, not assumed.
    Then the compiler must refuse it by name (no program is built), or - for the orders that work - print what
    CPython prints."""

    def cpython(self, files, entry="main.py"):
        write(self.dir, files)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        return subprocess.run([sys.executable, "-B", entry], cwd=self.dir, capture_output=True, text=True,
                              timeout=60, env=env)

    def refusal_with_oracle(self, files, expected_out, expected_err, *needles):
        ran = self.cpython(files)
        self.assertEqual(ran.stdout, expected_out)
        if expected_err:
            self.assertNotEqual(ran.returncode, 0)
            self.assertIn(expected_err, ran.stderr)
        else:
            self.assertEqual(ran.returncode, 0, ran.stderr)
        return self.refused(files, *needles)

    def test_a_function_that_reads_a_submodule_defined_before_its_import(self):
        # CPython: the call before `import pkg.a` raises AttributeError (caught here), the one after prints 1
        main = ("import pkg\n\n\ndef get():\n    return pkg.a.X\n\n\ntry:\n    print(get())\nexcept AttributeError:\n"
                "    print(\"AttributeError\")\nimport pkg.a\nprint(get())\n")
        self.refusal_with_oracle({**PKG, "main.py": main}, "AttributeError\n1\n", "",
                                 "pkg.a is read inside a function that is defined before the import that binds it")
        # the order in the other direction is the same program as far as the compiler can tell
        main = "import pkg\n\n\ndef get():\n    return pkg.a.X\n\n\nimport pkg.a\nprint(get())\n"
        self.assertEqual(self.cpython({**PKG, "main.py": main}).stdout, "1\n")
        self.refused({**PKG, "main.py": main}, "defined before the import that binds it")

    def test_a_package_module_function_that_reads_a_sibling_imported_later(self):
        files = {**PKG, "pkg/a.py": "import pkg\n\n\ndef z():\n    return pkg.b.Y\n",
                 "main.py": ("import pkg.a\ntry:\n    print(pkg.a.z())\nexcept AttributeError:\n    print(\"AttributeError\")\n"
                             "import pkg.b\nprint(pkg.a.z())\n")}
        self.refusal_with_oracle(files, "AttributeError\n2\n", "", "pkg.b is read inside a function that is defined before")

    def test_functions_defined_after_the_import_still_work(self):
        main = ("import pkg\nimport pkg.a\n\n\ndef get():\n    return pkg.a.X\n\n\nprint(get())\n"
                "print(pkg.a.f())\n")
        self.assertEqual(self.same_as_cpython({**PKG, "main.py": main}), "1\nfa\n")
        # a package that imports its own submodules makes the attribute available to everyone
        files = {**PKG, "pkg/__init__.py": "from . import a\n",
                 "main.py": "import pkg\n\n\ndef get():\n    return pkg.a.X\n\n\nprint(get())\n"}
        self.assertEqual(self.same_as_cpython(files), "1\n")
        # a sibling that imports its sibling first
        files = {**PKG, "pkg/a.py": "import pkg.b\nimport pkg\n\n\ndef z():\n    return pkg.b.Y\n",
                 "main.py": "import pkg.a\nprint(pkg.a.z(), pkg.b.Y)\n"}
        self.assertEqual(self.same_as_cpython(files), "2 2\n")

    def test_module_level_reads_before_the_import_are_refused(self):
        for label, main, out, err, needle in (
                ("attribute of a package that imports nothing", "import pkg\nprint(pkg.a.X)\n", "", "AttributeError",
                 "package 'pkg' has no attribute 'a'"),
                ("caught and then imported", "import pkg\ntry:\n    print(pkg.a.X)\nexcept AttributeError:\n"
                 "    print(\"AttributeError\")\nimport pkg.a\nprint(pkg.a.X)\n", "AttributeError\n1\n", "",
                 "read before the import that binds it has run"),
                ("a sibling nobody imports", "import pkg.a\nprint(pkg.b.Y)\n", "", "AttributeError",
                 "package 'pkg' has no attribute 'b'"),
                ("a conditional import that does not run",
                 "import pkg\nif len(\"abc\") == 4:\n    import pkg.a\nprint(pkg.a.X)\n", "", "AttributeError",
                 "below the top level"),
                ("an alias bound before the import", "import pkg as p\nprint(p.a.X)\nimport pkg.a\n", "", "AttributeError",
                 "read before the import that binds it has run"),
                ("a class body", "import pkg\n\n\nclass C:\n    v = pkg.a.X\n\n\nimport pkg.a\nprint(1)\n", "",
                 "AttributeError", "read before the import that binds it has run")):
            with self.subTest(label):
                self.refusal_with_oracle({**PKG, "main.py": main}, out, err, needle)

    def test_a_namespace_package_has_no_submodule_attribute_either(self):
        files = {"nsp/a.py": "X = 1\n", "nsp/b.py": "Y = 2\n",
                 "main.py": "import nsp.a\nprint(nsp.a.X)\nprint(nsp.b.Y)\n"}
        self.refusal_with_oracle(files, "1\n", "AttributeError", "package 'nsp' has no attribute 'b'")

    def test_a_deeper_package_needs_the_import_of_every_level(self):
        files = {**PKG, "pkg/__init__.py": "from . import sub\n", "pkg/sub/__init__.py": "", "pkg/sub/c.py": "Z = 3\n",
                 "pkg/sub/d.py": "W = 4\n",
                 "main.py": "import pkg\nimport pkg.sub.c\nprint(pkg.sub.c.Z)\nprint(pkg.sub.d.W)\n"}
        self.refusal_with_oracle(files, "3\n", "AttributeError", "package 'pkg.sub' has no attribute 'd'")

    def test_a_package_name_that_the_submodule_import_would_rebind(self):
        # CPython: `import pkg.a` stores the module over the attribute `a` the package defined
        for label, init in (("a variable", "a = 5\n"), ("a function", "def a():\n    return \"func\"\n"),
                            ("a class", "class a:\n    pass\n"), ("an imported name", "from .b import Y as a\n")):
            with self.subTest(label):
                files = {**PKG, "pkg/__init__.py": init, "main.py": "import pkg\nimport pkg.a\nprint(pkg.a.X)\n"}
                ran = self.cpython(files)
                self.assertEqual((ran.returncode, ran.stdout), (0, "1\n"))
                self.refused(files, "is also a submodule that the program imports", "order of the imports")
        files = {**PKG, "pkg/__init__.py": "a = 5\n", "main.py": "import pkg\nprint(pkg.a)\nimport pkg.a\nprint(pkg.a.X)\n"}
        self.assertEqual(self.cpython(files).stdout, "5\n1\n")
        self.refused(files, "pkg.a")
        files = {**PKG, "pkg/__init__.py": "a = 5\n", "main.py": "from pkg.a import f\nimport pkg\nprint(pkg.a.X, f())\n"}
        self.assertEqual(self.cpython(files).stdout, "1 fa\n")
        self.refused(files, "is also a submodule that the program imports")

    def test_the_name_alone_is_fine_when_the_submodule_is_never_imported(self):
        files = {**PKG, "pkg/__init__.py": "a = 5\n", "main.py": "import pkg\nprint(pkg.a)\n"}
        self.assertEqual(self.same_as_cpython(files), "5\n")
        files = {**PKG, "pkg/__init__.py": "a = 5\n", "main.py": "from pkg import a\nprint(a)\n"}
        self.assertEqual(self.same_as_cpython(files), "5\n")
        # `from . import a` binds the module itself: not a clash
        files = {**PKG, "pkg/__init__.py": "from . import a\n", "main.py": "import pkg\nimport pkg.a\nprint(pkg.a.X)\n"}
        self.assertEqual(self.same_as_cpython(files), "1\n")

    def test_orders_that_work_in_cpython_print_the_same(self):
        cases = {
            "dotted imports then both attributes": ("import pkg.b\nimport pkg.a\nprint(pkg.a.X, pkg.b.Y)\n", PKG),
            "a sibling imported by a sibling": ("import pkg.a\nprint(pkg.b.Y)\n",
                                                {**PKG, "pkg/a.py": "import pkg.b\nX = 1\n"}),
            "a relative sibling import": ("import pkg.a\nprint(pkg.b.Y)\n",
                                          {**PKG, "pkg/a.py": "from . import b\nX = 1\n"}),
            "an import cycle between siblings": ("import pkg.a\nprint(pkg.a.X, pkg.b.Y)\n",
                                                 {**PKG, "pkg/a.py": "from . import b\nX = 1\n",
                                                  "pkg/b.py": "from . import a\nY = 2\n"}),
            "from-import of two submodules": ("from pkg import a, b\nprint(a.X, b.Y)\n", PKG),
            "the package binds the submodule": ("import pkg\nprint(pkg.a.X)\n", {**PKG, "pkg/__init__.py": "import pkg.a\n"}),
            "the alias is bound before and used after": ("import pkg as p\nimport pkg.a\nprint(p.a.X)\n", PKG),
        }
        for label, (main, files) in cases.items():
            with self.subTest(label):
                self.same_as_cpython({**files, "main.py": main})

    def test_an_import_of_a_module_that_does_not_exist_is_refused_even_when_unused(self):
        # CPython stops at the import with ModuleNotFoundError; a program that never used the name used to be built
        for label, main, needle in (("unused", "import nothere\nprint(1)\n", "import of 'nothere' is not available"),
                                    ("from", "from nothere import x\nprint(1)\n", "import of 'nothere' is not available"),
                                    ("dotted", "import nothere.sub as s\nprint(1)\n", "import of 'nothere.sub' is not available"),
                                    ("third party alias", "import numpy as np\nprint(1)\n", "import of 'numpy' is not available")):
            with self.subTest(label):
                ran = self.cpython({"main.py": main})
                self.assertNotEqual(ran.returncode, 0)
                self.assertIn("ModuleNotFoundError", ran.stderr)
                self.assertEqual(ran.stdout, "")
                stderr = self.refused({"main.py": main}, needle, "ModuleNotFoundError")
                self.assertIn("main.py:1:1", stderr)

    def test_standard_library_and_local_imports_are_not_mistaken_for_missing_ones(self):
        files = {"helper.py": "V = 7\n", "main.py": "import os\nimport sys\nimport helper\nimport collections.abc\nprint(helper.V)\n"}
        write(self.dir, files)
        built, exe = compile_program(self.dir, "main.py", "1")
        self.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
        self.assertEqual(ran.stdout, b"7\n")


if __name__ == "__main__":
    unittest.main()
