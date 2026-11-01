"""Module system: the Python semantics that used to be refused by name (MODSYS).

Each program is a set of files compared with CPython 3.12 (`python3 main.py` is the oracle).

* `from m import _private`, `m._private`, `from m import *` with `__all__` listing a private name;
* `import main` in the entry file (CPython loads the file a second time as module `main`);
* `__file__` (the absolute source path at build time), `__package__` and `__name__`;
* `try: import m / except ImportError:` decided when the program is built: the body when the module is found, the
  handler when it is not (a C accelerator such as `_bisect` counts as not found, a module neither the search path
  nor the build machine's Python has is not found);
* function-level imports of modules with effects at import time (a print, a computed table): the module starts
  when the function first runs, as in CPython, including a function that the importing module itself calls while it
  starts.
"""
import os
import subprocess
import sys
import unittest

from test_ail_modules import ModulesBase, write, compile_program

ONE = ("1",)


class PrivateNames(ModulesBase):
    def test_private_names_are_plain_python(self):
        out = self.same_as_cpython({
            "lib.py": "_secret = 41\n\n\ndef _g():\n    return _secret + 1\n\n\nclass _Box:\n    def __init__(self, v):\n"
                      "        self.v = v\n\n\ndef make():\n    return _Box(7)\n",
            "main.py": "from lib import _g, _secret, _Box, make\nimport lib\nprint(_g(), _secret, lib._g(), lib._secret)\n"
                       "print(_Box(3).v, make().v, isinstance(make(), _Box))\n"}, irs=ONE)
        self.assertEqual(out, "42 41 42 41\n3 7 True\n")

    def test_star_import_binds_a_private_name_listed_in_all(self):
        out = self.same_as_cpython({
            "lib.py": "__all__ = ['_g', 'f']\n\n\ndef _g():\n    return 1\n\n\ndef f():\n    return 2\n\n\ndef _h():\n    return 3\n",
            "main.py": "from lib import *\nprint(_g(), f())\n"}, irs=ONE)
        self.assertEqual(out, "1 2\n")

    def test_private_name_in_a_package(self):
        out = self.same_as_cpython({
            "pkg/__init__.py": "",
            "pkg/_impl.py": "def _go(x):\n    return x * 2\n\n\nVALUE = 5\n",
            "pkg/api.py": "from pkg._impl import _go\nfrom . import _impl\n\n\ndef run():\n    return _go(_impl.VALUE)\n",
            "main.py": "from pkg import api\nfrom pkg._impl import _go\nprint(api.run(), _go(1))\n"}, irs=ONE)
        self.assertEqual(out, "10 2\n")


class EntryTwice(ModulesBase):
    def test_import_of_the_entry_file_runs_it_again_as_a_module(self):
        out = self.same_as_cpython({
            "main.py": "import main\nX = 5\nprint('body', __name__)\n"
                       "\n\ndef f():\n    return X\n\n\nprint(main.f(), f())\n"}, irs=ONE)
        self.assertEqual(out.count("body"), 2)

    def test_another_module_imports_the_entry(self):
        out = self.same_as_cpython({
            "main.py": "import helper\nCOUNT = 1\n\n\ndef bump():\n    global COUNT\n    COUNT += 1\n    return COUNT\n\n\n"
                       "if __name__ == '__main__':\n    print(bump(), helper.twice())\n",
            "helper.py": "def twice():\n    import main\n    return main.bump() * 10\n"}, irs=ONE)
        self.assertEqual(out, "2 20\n")


class ModuleAttributes(ModulesBase):
    def test_file_package_and_name(self):
        out = self.same_as_cpython({
            "pkg/__init__.py": "NAME = __name__\nPKG = __package__\nHERE = __file__.endswith('__init__.py')\n",
            "pkg/sub.py": "NAME = __name__\nPKG = __package__\nFILE = __file__.endswith('sub.py')\n",
            "top.py": "NAME = __name__\nPKG = repr(__package__)\nFILE = __file__.rsplit('/', 1)[1]\n",
            "main.py": "import pkg, pkg.sub, top\n"
                       "print(pkg.NAME, pkg.PKG, pkg.HERE, pkg.sub.NAME, pkg.sub.PKG, pkg.sub.FILE)\n"
                       "print(top.NAME, top.PKG, top.FILE, pkg.sub.__file__ == pkg.sub.__file__, top.__package__ == '')\n"
                       "print(__name__, __package__, __file__.endswith('main.py'), __file__ == __file__)\n"},
            irs=ONE)
        self.assertIn("pkg pkg True pkg.sub pkg True\n", out)

    def test_file_in_a_single_file_program(self):
        out = self.same_as_cpython({"main.py": "import os\nprint(os.path.basename(__file__), __name__, __package__)\n"},
                                   irs=ONE)
        self.assertEqual(out, "main.py __main__ None\n")


class Cycles(ModulesBase):
    """Import cycles run in CPython's order: the module that is still starting has the names defined so far."""

    def test_cycle_where_the_name_is_defined_before_the_import(self):
        out = self.same_as_cpython({
            "a.py": "print('a starts')\nX = 1\n\n\ndef fa():\n    return X + 1\n\n\nimport b\n\nprint('a ends', b.Y)\n",
            "b.py": "print('b starts')\nfrom a import X, fa\nY = X + 10\nprint('b sees', X, fa())\n",
            "main.py": "import a\nprint(a.X, a.b.Y)\n"}, irs=ONE)
        self.assertEqual(out, "a starts\nb starts\nb sees 1 2\na ends 11\n1 11\n")

    def test_cycle_that_reads_a_name_before_it_is_defined_is_refused(self):
        # CPython: ImportError (cannot import name 'X' from partially initialized module 'a')
        self.refused({"a.py": "import b\nX = 1\n", "b.py": "from a import X\n", "main.py": "import a\nprint(a.X)\n"},
                     "import cycle", "so CPython raises ImportError")

    def test_function_level_from_import_in_a_cycle(self):
        out = self.same_as_cpython({
            "a.py": "import b\n\n\ndef fa():\n    return 'a'\n",
            "b.py": "import a\n\n\ndef fb():\n    from a import fa\n    return fa() + 'b'\n",
            "main.py": "import a\nimport b\nprint(b.fb())\n"}, irs=ONE)
        self.assertEqual(out, "ab\n")


class GuardedImports(ModulesBase):
    def test_try_import_of_a_module_that_exists(self):
        out = self.same_as_cpython({
            "lib.py": "K = 11\n\n\ndef f():\n    return K\n",
            "main.py": "try:\n    import lib\nexcept ImportError:\n    lib = None\n\nprint(lib.f(), lib.K)\n"}, irs=ONE)
        self.assertEqual(out, "11 11\n")

    def test_try_import_of_a_missing_module_runs_the_handler(self):
        out = self.same_as_cpython({
            "main.py": "try:\n    import no_such_module_xyz\n    HAVE = True\nexcept ImportError:\n    HAVE = False\n"
                       "print(HAVE)\n"}, irs=ONE)
        self.assertEqual(out, "False\n")

    def test_try_from_import_falls_back_to_a_python_definition(self):
        out = self.same_as_cpython({
            "main.py": "try:\n    from _bisect_no_such import bisect_left\nexcept ImportError:\n"
                       "    def bisect_left(a, x):\n        lo = 0\n        while lo < len(a) and a[lo] < x:\n"
                       "            lo += 1\n        return lo\n\nprint(bisect_left([1, 3, 5], 4))\n"}, irs=ONE)
        self.assertEqual(out, "2\n")

    def test_c_accelerator_takes_the_python_fallback(self):
        out = self.same_as_cpython({
            "lib.py": "try:\n    from _bisect import *\nexcept ImportError:\n    pass\n\n\ndef where(a, x):\n"
                      "    return len([v for v in a if v < x])\n",
            "main.py": "import lib\nprint(lib.where([1, 2, 3], 3))\n"}, irs=ONE)
        self.assertEqual(out, "2\n")

    def test_first_import_missing_second_module_is_the_fallback(self):
        out = self.same_as_cpython({
            "alt.py": "def name():\n    return 'alt'\n",
            "main.py": "try:\n    import fancy_missing as impl\nexcept ImportError:\n    import alt as impl\n\n"
                       "print(impl.name())\n"}, irs=ONE)
        self.assertEqual(out, "alt\n")

    def test_function_level_try_with_other_code(self):
        out = self.same_as_cpython({
            "lib.py": "K = 3\n\n\ndef f(x):\n    return x * K\n",
            "main.py": "def run(x):\n    try:\n        import lib\n        return lib.f(x)\n    except ImportError:\n"
                       "        return -1\n\nprint(run(4))\n"}, irs=ONE)
        self.assertEqual(out, "12\n")

    def test_try_that_does_more_than_import_runs_the_code_before_the_failing_import(self):
        out = self.same_as_cpython({
            "main.py": "try:\n    X = 1\n    import no_such_module_xyz\n    X = 2\nexcept ImportError:\n    Y = 5\n"
                       "finally:\n    print('fin')\nprint(X, Y)\n"}, irs=ONE)
        self.assertEqual(out, "fin\n1 5\n")

    def test_c_module_without_a_python_fallback_is_refused(self):
        self.refused({"main.py": "try:\n    from _collections import deque\nexcept ImportError:\n    pass\nprint(1)\n"},
                     "no Python fallback")

    def test_conditions_on_the_platform_and_version_choose_the_import(self):
        out = self.same_as_cpython({
            "lib.py": "K = 3\n",
            "main.py": "import sys\nif sys.platform == 'win32':\n    import no_such_module_xyz as impl\n    NAME = 'win'\n"
                       "elif sys.version_info >= (3, 8) and not sys.platform.startswith('win'):\n    import lib as impl\n"
                       "    NAME = 'lib'\nelse:\n    import no_such_other_xyz as impl\n    NAME = 'old'\n"
                       "print(NAME, impl.K)\n"}, irs=ONE)
        self.assertEqual(out, "lib 3\n")

    def test_import_under_a_condition_the_build_cannot_decide(self):
        files = {"lib.py": "print('lib starts')\nK = 4\n",
                 "main.py": "import sys\n\nif len(sys.argv) %s 5:\n    import lib\n    print(lib.K)\nprint('done')\n"}
        for op, want in (("<", "lib starts\n4\ndone\n"), (">", "done\n")):
            with self.subTest(op=op):
                self.assertEqual(self.same_as_cpython({**files, "main.py": files["main.py"] % op}, irs=ONE), want)

    def test_missing_module_without_a_handler_for_it_is_refused(self):
        self.refused({"main.py": "try:\n    import no_such_module_xyz\nexcept KeyError:\n    pass\nprint(1)\n"},
                     "no handler of this `try` catches ImportError")

    def test_single_file_program_with_guarded_import(self):
        out = self.same_as_cpython({
            "main.py": "try:\n    import no_such_module_xyz as fast\nexcept ImportError:\n    fast = None\n"
                       "print(fast is None)\n"}, irs=ONE)
        self.assertEqual(out, "True\n")


class LazyStart(ModulesBase):
    LIB = ("import os\nprint('lib starts')\nSQ = [i * i for i in range(5)]\nCNT = len(SQ)\n"
           "HERE = os.path.dirname(os.path.abspath(__file__)) != ''\n\n\ndef table():\n    return SQ, CNT, HERE\n\n\n"
           "def helper(n):\n    return CNT + n\n")

    def test_module_with_effects_starts_when_the_function_runs(self):
        out = self.same_as_cpython({
            "lib.py": self.LIB,
            "main.py": "def get():\n    import lib\n    return lib.table()\n\n\ndef other():\n"
                       "    from lib import SQ, helper\n    return len(SQ) + helper(3)\n\n\n"
                       "print('start')\nprint(get())\nprint(other())\nprint(get())\n"}, irs=ONE)
        self.assertEqual(out, "start\nlib starts\n([0, 1, 4, 9, 16], 5, True)\n13\n([0, 1, 4, 9, 16], 5, True)\n")

    def test_function_never_called_never_starts_the_module(self):
        out = self.same_as_cpython({
            "lib.py": self.LIB,
            "main.py": "def get():\n    import lib\n    return lib.table()\n\n\nprint('no call')\n"}, irs=ONE)
        self.assertEqual(out, "no call\n")

    def test_module_that_imports_another_module_with_effects(self):
        out = self.same_as_cpython({
            "inner.py": "print('inner starts')\nVALUE = sum(range(10))\n",
            "outer.py": "import inner\nprint('outer starts')\nDOUBLE = inner.VALUE * 2\n\n\ndef get():\n    return DOUBLE\n",
            "main.py": "def run():\n    import outer\n    return outer.get()\n\n\nprint('start')\nprint(run())\n"},
            irs=ONE)
        self.assertEqual(out, "start\ninner starts\nouter starts\n90\n")

    def test_module_calling_its_own_function_that_imports_later(self):
        out = self.same_as_cpython({
            "dep.py": "print('dep starts')\nK = 6\n",
            "a.py": "def f():\n    import dep\n    return dep.K\n\n\nY = f() + 1\nprint('a', Y)\n",
            "main.py": "import a\nprint('main', a.Y, a.f())\n"}, irs=ONE)
        self.assertEqual(out, "dep starts\na 7\nmain 7 6\n")

    def test_two_functions_start_the_same_module_once(self):
        out = self.same_as_cpython({
            "lib.py": "print('once')\nN = 1\n",
            "main.py": "def a():\n    import lib\n    return lib.N\n\n\ndef b():\n    from lib import N\n    return N + 1\n\n\n"
                       "print(b(), a(), b())\n"}, irs=ONE)
        self.assertEqual(out, "once\n2 1 2\n")

    def test_package_with_effects_starts_parent_first(self):
        out = self.same_as_cpython({
            "pkg/__init__.py": "print('pkg starts')\nTOP = 1\n",
            "pkg/leaf.py": "print('leaf starts')\nVAL = 2\n",
            "main.py": "def get():\n    import pkg.leaf\n    return pkg.TOP + pkg.leaf.VAL\n\n\nprint(get())\n"},
            irs=ONE)
        self.assertEqual(out, "pkg starts\nleaf starts\n3\n")

    def test_cycle_through_function_level_from_import(self):
        out = self.same_as_cpython({
            "a.py": "import b\nprint('a starts')\n\n\ndef fa():\n    return 'a'\n\n\ndef both():\n    return fa() + b.fb()\n",
            "b.py": "print('b starts')\n\n\ndef fb():\n    from a import fa\n    return 'b' + fa()\n",
            "main.py": "import a\nprint(a.both())\n"}, irs=ONE)
        self.assertEqual(out, "b starts\na starts\naba\n")

    def test_function_that_returns_a_lazily_imported_module(self):
        out = self.same_as_cpython({
            "lib.py": "print('lib starts')\nK = 5\n\n\ndef f(x):\n    return x + K\n",
            "helper.py": "def L():\n    import lib\n    return lib\n\n\ndef twice():\n    return L().f(1) * 2\n",
            "main.py": "import helper\nfrom helper import L\n\nprint('go')\nprint(helper.L().f(2), helper.L().K)\n"
                       "print(L().f(1), helper.twice())\nL()\n"}, irs=ONE)
        self.assertEqual(out, "go\nlib starts\n7 5\n6 12\n")

    def test_one_name_bound_to_different_modules_in_two_branches(self):
        out = self.same_as_cpython({
            "lib_a.py": "print('a starts')\nNAME = 'a'\n\n\ndef run(x):\n    return x + 1\n",
            "lib_b.py": "print('b starts')\nNAME = 'b'\n\n\ndef run(x):\n    return x * 2\n",
            "main.py": "def pick(flag):\n    if flag:\n        import lib_a as impl\n    else:\n"
                       "        import lib_b as impl\n    return impl.run(10), impl.NAME\n\n\n"
                       "print(pick(True))\nprint(pick(False))\nprint(pick(True))\n"}, irs=ONE)
        self.assertEqual(out, "a starts\n(11, 'a')\nb starts\n(20, 'b')\n(11, 'a')\n")

    def test_function_level_from_import_of_a_name_the_module_body_assigns_twice(self):
        out = self.same_as_cpython({
            "lib.py": "print('lib starts')\nLIMIT = 1\nLIMIT = LIMIT + 4\nNAMES = ['a']\nNAMES = NAMES + ['b']\n",
            "main.py": "def run():\n    from lib import LIMIT, NAMES\n    return LIMIT, NAMES\n\n\nprint('go')\nprint(run())\n"},
            irs=ONE)
        self.assertEqual(out, "go\nlib starts\n(5, ['a', 'b'])\n")

    def test_constants_that_definitions_read_are_placed_with_the_definitions(self):
        out = self.same_as_cpython({
            "lib.py": "print('lib starts')\nSCALE = 3\nNAMES = ['a', 'b']\nCOUNT = len(NAMES)\nTOTAL = sum(range(5))\n\n\n"
                      "def scaled(x, k=SCALE):\n    return x * k + COUNT\n\n\nclass Box:\n    size = SCALE\n",
            "main.py": "def run():\n    import lib\n    return lib.scaled(2), lib.Box.size, lib.TOTAL\n\n\nprint('go')\n"
                       "print(run())\n"}, irs=ONE)
        self.assertEqual(out, "go\nlib starts\n(8, 3, 10)\n")

    def test_function_level_import_of_a_module_the_front_end_wants_at_the_top(self):
        out = self.same_as_cpython({
            "lib.py": "def leaf(p):\n    import pathlib\n    return pathlib.Path(p).name\n",
            "main.py": "import lib\n\nprint(lib.leaf('a/b/c.txt'))\n"}, irs=ONE)
        self.assertEqual(out, "c.txt\n")

    def test_constants_set_by_a_literal_unpacking(self):
        out = self.same_as_cpython({
            "lib.py": "print('lib starts')\nA, B = 'int', 'float'\n\n\ndef kind(x, k=A):\n    return k + str(x) + B\n",
            "main.py": "def run():\n    import lib\n    return lib.kind(1)\n\n\nprint(run())\n"}, irs=ONE)
        self.assertEqual(out, "lib starts\nint1float\n")

    def test_module_body_with_a_builtin_call_that_takes_keywords(self):
        out = self.same_as_cpython({
            "lib.py": "NUMS = sorted([3, 1, 2], reverse=True)\nTOP = max([4, 9, 2], default=0)\n\n\ndef first():\n"
                      "    return NUMS[0] + TOP\n",
            "main.py": "def run():\n    import lib\n    return lib.NUMS, lib.first()\n\n\nprint(run())\n"}, irs=ONE)
        self.assertEqual(out, "([3, 2, 1], 12)\n")

    def test_module_value_from_a_getter_is_refused(self):
        self.refused({"lib.py": "K = 5\n", "helper.py": "def L():\n    import lib\n    return lib\n",
                      "main.py": "import helper\nm = helper.L()\nprint(m.K)\n"},
                     "returned by a call and used as a value")

    def test_class_with_builtin_method_decorators(self):
        out = self.same_as_cpython({
            "lib.py": "print('lib starts')\nBASE = 10\n\n\nclass Shape:\n    count = 0\n\n    def __init__(self, n):\n"
                      "        self.n = n\n\n    @staticmethod\n    def twice(x):\n        return x * 2\n\n"
                      "    @classmethod\n    def make(cls, n):\n        return cls(n + BASE)\n\n"
                      "    @property\n    def double(self):\n        return self.n * 2\n",
            "main.py": "def run():\n    import lib\n    s = lib.Shape.make(1)\n    return lib.Shape.twice(3), s.double\n\n\n"
                       "print(run())\n"}, irs=ONE)
        self.assertEqual(out, "lib starts\n(6, 22)\n")

    def test_definition_that_needs_a_computed_value(self):
        out = self.same_as_cpython({"lib.py": "import os\nBASE = os.getcwd()\n\n\ndef f(x=BASE):\n    return x\n",
                                    "main.py": "def g():\n    import lib\n    return lib.f()\n\n\nprint(g() != '')\n"},
                                   irs=ONE)
        self.assertEqual(out, "True\n")

    def test_definition_that_needs_an_effectful_value_is_refused(self):
        self.refused({"lib.py": "def make():\n    print('making')\n    return 3\n\n\nN = make()\n\n\n"
                                "def f(x=N):\n    return x\n",
                      "main.py": "def g():\n    import lib\n    return lib.f()\n\n\nprint(g())\n"},
                     "function-level `import lib`")


if __name__ == "__main__":
    unittest.main()
