"""Stdlib rules, batch 1: the import-related rules that let CPython's own pure-Python modules compile.

Each program below is a set of files; CPython runs `python3 main.py` as the oracle and `ail_chatgpt.py compile`
builds the same bytes. The refusals are checked by name with their `write instead:` hint and a file:line.

* `try: from _bisect import * / import _heapq ... except ImportError:` for a C accelerator the compiler lacks: the
  handler (the pure-Python fallback CPython falls back to without the accelerator) is what runs. A handler that
  does more than define names, and an `else:` clause, are refused; any other ImportError guard is still refused.
* `try: import local_module except ImportError:` and `if <decidable test>: import local_module` (a constant,
  `sys.version_info >= (3, 8)`) at module level: the branch CPython takes is the one built, a module
  in the branch not taken is not loaded at all. A test the compiler cannot decide is refused.
* `from M import _name` / `M._name` between local modules (one leading underscore); two leading underscores are
  refused (CPython mangles them in a class body).
* `object()` as a sentinel, `isinstance(x, object)`, `class C(object)`; `object` or a builtin type used as a value
  is refused with the line of the use.
* a module-level `alias = function` of a function with defaults (`bisect = bisect_right`).
* CPython's own bisect.py and heapq.py, unmodified, as local modules, against a use program.
"""
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from test_ail_modules import CLI, ModulesBase, compile_program, write

STDLIB = Path(os.__file__).resolve().parent


class Rules(ModulesBase):
    IRS = ("1",)

    def same(self, files, **kw):
        return self.same_as_cpython(files, irs=kw.pop("irs", self.IRS), **kw)

    def refused_any(self, files, *needles, entry="main.py", codes=(2, 3)):
        """Like `refused`, for a refusal of the general path too (exit 3): the needles, a file:line, a write-instead."""
        write(self.dir, files)
        env = dict(os.environ)
        env.pop("AIL_PATH", None)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", entry, "-o", str(self.dir / "out")],
                               cwd=self.dir, capture_output=True, text=True, timeout=300, env=env)
        self.assertIn(built.returncode, codes, built.stdout + built.stderr)
        self.assertFalse((self.dir / "out").exists())
        for needle in needles:
            self.assertIn(needle, built.stderr)
        self.assertIn("write instead", built.stderr)
        self.assertNotIn("Traceback", built.stderr)
        return built.stderr

    # ------------------------------------------------------------------ accelerator fallbacks
    def test_accelerator_import_takes_the_fallback(self):
        lib = ('try:\n    from _bisect import *\nexcept ImportError:\n    pass\n\n\n'
               'def where(a, x):\n    lo, hi = 0, len(a)\n    while lo < hi:\n        mid = (lo + hi) // 2\n'
               '        if a[mid] < x:\n            lo = mid + 1\n        else:\n            hi = mid\n    return lo\n')
        out = self.same({"lib.py": lib, "main.py": "import lib\nprint(lib.where([1, 3, 5], 4))\n"})
        self.assertEqual(out, "2\n")

    def test_accelerator_fallback_handler_binds_names(self):
        # the shape of json.decoder: the module takes the C function when it exists, else its own Python one; both
        # give the same answer, which is what makes the pure-Python fallback a replacement (the handler's None is
        # a "no accelerator" marker the module itself tests)
        lib = ('try:\n    from _json import scanstring as c_scanstring\nexcept ImportError:\n    c_scanstring = None\n\n\n'
               'def py_scanstring(s):\n    return s.upper()\n\n\nscanstring = c_scanstring or py_scanstring\n')
        write(self.dir, {"lib.py": lib, "main.py": "import lib\nprint(lib.py_scanstring('x'))\n"})
        built, exe = compile_program(self.dir, "main.py", "1")
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertEqual(subprocess.run([str(exe)], capture_output=True).stdout, b"X\n")

    def test_accelerator_handler_that_does_more_is_refused(self):
        lib = 'try:\n    from _bisect import *\nexcept ImportError:\n    print("no accelerator")\n'
        err = self.refused({"lib.py": lib, "main.py": "import lib\n"}, "does more than define a fallback", "lib.py:4")
        self.assertIn("print", err)

    def test_accelerator_else_clause_is_refused(self):
        lib = ('try:\n    from _bisect import *\nexcept ImportError:\n    pass\nelse:\n    X = 1\n')
        self.refused({"lib.py": lib, "main.py": "import lib\n"}, "`else:`", "lib.py:6")

    def test_other_import_errors_are_still_refused(self):
        lib = 'try:\n    import readline\nexcept ImportError:\n    readline = None\n'
        err = self.refused_any({"lib.py": lib, "main.py": "import lib\nprint(1)\n"}, "guarded by `except ImportError`")
        self.assertIn("lib.py", err)
        # an accelerator guard that also does something with the accelerator is not a fallback pattern
        lib2 = 'try:\n    import _bisect\n    X = _bisect.bisect_left([1], 1)\nexcept ImportError:\n    X = 0\n'
        self.refused_any({"lib.py": lib2, "main.py": "import lib\nprint(lib.X)\n"}, "guarded by `except ImportError`")

    # ------------------------------------------------------------------ local imports under try / if
    def test_local_import_in_try(self):
        files = {"helper.py": "def f(x):\n    return x + 1\n",
                 "main.py": "try:\n    import helper\nexcept ImportError:\n    helper = None\n"
                            "print(helper.f(1))\n"}
        self.assertEqual(self.same(files), "2\n")
        files["main.py"] = ("try:\n    from helper import f\nexcept ImportError:\n    f = None\nelse:\n"
                            "    print('else')\nfinally:\n    print('finally')\nprint(f(2))\n")
        self.assertEqual(self.same(files), "else\nfinally\n3\n")

    def test_local_import_in_try_whose_module_can_raise_import_error(self):
        files = {"helper.py": "import os\n\n\ndef f(x):\n    return x\n\n\ntry:\n    import nothing_here\n"
                              "except ImportError:\n    pass\n",
                 "main.py": "try:\n    import helper\nexcept ImportError:\n    helper = None\nprint(1)\n"}
        err = self.refused_any(files, "mentions ImportError", "main.py:2")
        self.assertIn("helper", err)

    def test_local_import_in_try_missing_name_is_refused(self):
        files = {"helper.py": "def f(x):\n    return x\n",
                 "main.py": "try:\n    from helper import nothing\nexcept ImportError:\n    nothing = 0\nprint(nothing)\n"}
        self.refused(files, "no top-level name 'nothing'", "main.py:2")

    def test_conditional_local_import_takes_the_decidable_branch(self):
        files = {"new.py": "print('new body')\n\n\ndef f():\n    return 'new'\n",
                 "old.py": "print('old body')\n\n\ndef f():\n    return 'old'\n",
                 "main.py": "import sys\nif sys.version_info >= (3, 8):\n    import new as impl\nelse:\n"
                            "    import old as impl\nprint(impl.f())\n"}
        self.assertEqual(self.same(files), "new body\nnew\n")
        files["main.py"] = "if False:\n    import new\nprint('x')\n"
        self.assertEqual(self.same(files), "x\n")           # the module in the branch not taken never runs

    def test_conditional_local_import_with_an_undecidable_test_is_refused(self):
        files = {"new.py": "X = 1\n",
                 "main.py": "import sys\nif len(sys.argv) > 5:\n    import new\nprint(2)\n"}
        self.refused(files, "below the top level", "main.py:3")
        files["main.py"] = "import sys\nif sys.platform == 'win32':\n    import new\nprint(2)\n"
        self.refused(files, "below the top level", "main.py:3")

    def test_function_level_import_called_twice(self):
        files = {"helper.py": "COUNT = 7\n\n\ndef f():\n    return COUNT\n",
                 "main.py": "def use():\n    import helper\n    return helper.f()\n\n\nprint(use(), use())\n"}
        self.assertEqual(self.same(files), "7 7\n")

    def test_circular_import_inside_try(self):
        files = {"a.py": "try:\n    import b\nexcept ImportError:\n    b = None\n\n\ndef fa():\n    return 'a'\n",
                 "b.py": "import a\n\n\ndef fb():\n    return a.fa() + 'b'\n",
                 "main.py": "import a\nimport b\nprint(b.fb())\n"}
        self.assertEqual(self.same(files), "ab\n")

    # ------------------------------------------------------------------ private names
    def test_private_names_between_local_modules(self):
        files = {"lib.py": "def f():\n    return 1\n\n\ndef _g():\n    return 2\n\n\n_K = 5\n",
                 "main.py": "from lib import _g, _K as k\nimport lib\nprint(_g(), k, lib._g(), lib._K)\n"}
        self.assertEqual(self.same(files), "2 5 2 5\n")

    def test_private_name_star_import_listed_in_all(self):
        files = {"lib.py": "__all__ = ['_g', 'f']\n\n\ndef f():\n    return 1\n\n\ndef _g():\n    return 2\n",
                 "main.py": "from lib import *\nprint(f(), _g())\n"}
        self.assertEqual(self.same(files), "1 2\n")

    def test_private_name_that_does_not_exist(self):
        files = {"lib.py": "def f():\n    return 1\n", "main.py": "from lib import _nothere\nprint(1)\n"}
        self.refused(files, "no top-level name '_nothere'", "main.py:1")
        files["main.py"] = "import lib\nprint(lib._nothere)\n"
        self.refused(files, "no top-level name '_nothere'", "main.py:2")

    def test_double_underscore_names_stay_refused(self):
        files = {"lib.py": "def __g():\n    return 2\n", "main.py": "from lib import __g\nprint(__g())\n"}
        self.refused(files, "two leading underscores", "main.py:1")
        files["main.py"] = "import lib\nprint(lib.__g())\n"
        self.refused(files, "two leading underscores", "main.py:2")

    def test_private_function_in_a_cycle_member(self):
        files = {"a.py": "def _fa():\n    return 'a'\n",
                 "b.py": "from a import _fa\n\n\ndef _fb():\n    return _fa() + 'b'\n",
                 "main.py": "import b\nprint(b._fb())\n"}
        self.assertEqual(self.same(files), "ab\n")

    # ------------------------------------------------------------------ object
    def test_object_sentinel_and_isinstance(self):
        prog = ('_unset = object()\n\n\ndef pick(d, k, default=_unset):\n    v = d.get(k, _unset)\n'
                '    if v is _unset:\n        return "missing" if default is _unset else default\n    return v\n\n\n'
                'class Box(object):\n    def __init__(self):\n        self.v = 1\n\n\nm = object()\n'
                'print(pick({"a": 1}, "a"), pick({}, "b"), pick({}, "b", 7), m is m, m == m, object() is m, bool(m))\n'
                'print(isinstance(Box(), object), isinstance(3, object), isinstance("s", (int, object)))\n')
        self.assertEqual(self.same({"main.py": prog}), "1 missing 7 True True False True\nTrue True True\n")

    def test_object_sentinel_in_a_local_module(self):
        files = {"lib.py": "sentinel = object()\n\n\ndef first(xs):\n    for x in xs:\n        return x\n    return sentinel\n",
                 "main.py": "import lib\nprint(lib.first([4]), lib.first([]) is lib.sentinel)\n"}
        self.assertEqual(self.same(files), "4 True\n")

    def test_object_used_as_a_value_is_refused(self):
        err = self.refused_any({"main.py": "x = 1\nbase = object\nprint(base)\n"}, "main.py:2", "object")
        self.assertIn("class Marker", err)
        err = self.refused_any({"main.py": "def f(x):\n    return object.__new__(x)\nprint(1)\n"}, "main.py:2")
        err = self.refused_any({"main.py": "kind = int\nprint(kind('5'))\n"}, "main.py:1", "int")
        self.assertIn("isinstance", err)
        err = self.refused_any({"main.py": "print(complex(1, 2))\n"}, "main.py:1", "complex")

    def test_object_sentinel_whose_type_name_is_read_is_refused(self):
        self.refused_any({"main.py": "s = object()\nprint(type(s).__name__)\n"}, "main.py", "_ail_object")

    # ------------------------------------------------------------------ function aliases
    def test_alias_of_a_function_with_defaults(self):
        prog = ('def right(a, x, lo=0, hi=None):\n    hi = len(a) if hi is None else hi\n    return hi - lo\n\n\n'
                'alias = right\nprint(alias([1, 2, 3], 0), alias([1, 2, 3], 0, 1))\n')
        self.assertEqual(self.same({"main.py": prog}), "3 2\n")
        # read before the assignment: not rewritten (CPython raises NameError there)
        bad = prog.replace("alias = right\n", "print(alias)\nalias = right\n")
        write(self.dir, {"main.py": bad})
        built, _ = compile_program(self.dir, "main.py", "1")
        self.assertNotEqual(built.returncode, 0)


@unittest.skipUnless((STDLIB / "bisect.py").is_file() and (STDLIB / "heapq.py").is_file(),
                     "CPython's own bisect.py and heapq.py are not here")
class CPythonModules(ModulesBase):
    """CPython's own source, unmodified, as a local module beside a use program."""

    USES = {
        "bisect": ('import bisect\na = [1, 3, 5, 7, 9]\nprint(bisect.bisect_left(a, 5), bisect.bisect_right(a, 5), '
                   'bisect.bisect(a, 4))\nb = [1, 2, 4]\nbisect.insort(b, 3)\nbisect.insort_left(b, 0)\n'
                   'bisect.insort_right(b, 9)\nprint(b)\nprint(bisect.bisect_left(a, 5, 1, 3), '
                   'bisect.bisect_right(a, 5, 0, 2))\n'),
        "heapq": ('import heapq\nh = []\nfor x in [5, 1, 8, 3, 2, 9]:\n    heapq.heappush(h, x)\nprint(h)\n'
                  'out = []\nwhile h:\n    out.append(heapq.heappop(h))\nprint(out)\ndata = [9, 4, 7, 1, 3]\n'
                  'heapq.heapify(data)\nprint(data)\nprint(heapq.heappushpop(data, 2), data)\n'
                  'print(heapq.heapreplace(data, 6), data)\n'),
    }

    def check(self, name):
        shutil.copy(STDLIB / (name + ".py"), self.dir / (name + ".py"))
        (self.dir / "main.py").write_text(self.USES[name], encoding="utf-8")
        expected = subprocess.run([sys.executable, "-B", "main.py"], cwd=self.dir, capture_output=True, timeout=60)
        self.assertEqual(expected.returncode, 0, expected.stderr.decode())
        built, exe = compile_program(self.dir, "main.py", "1")
        self.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
        self.assertEqual(ran.returncode, 0, ran.stderr.decode())
        self.assertEqual(ran.stdout, expected.stdout)

    def test_bisect(self):
        self.check("bisect")

    def test_heapq(self):
        self.check("heapq")


if __name__ == "__main__":
    unittest.main()
