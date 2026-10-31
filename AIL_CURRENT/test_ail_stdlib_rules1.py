"""Stdlib rules, batch 1: the import-related rules that let CPython's own pure-Python modules compile.

Each program below is a set of files; CPython runs `python3 main.py` as the oracle and `ail_chatgpt.py compile`
builds the same bytes. The refusals are checked by name with their `write instead:` hint and a file:line.

* `try: from _bisect import * ... except ImportError:`: the bundled stdlib/_bisect.py and _heapq.py have the C modules'
  behaviour (error texts, argument checks), so the import succeeds as in CPython; the other accelerators are refused.
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
    def test_accelerator_import_succeeds_with_the_accelerators_own_behaviour(self):
        # `from _bisect import *` finds a bundled _bisect.py that has the C module's behaviour, so the try
        # succeeds as in CPython and the program prints what CPython prints (the C texts, not the Python ones)
        lib = ('try:\n    from _heapq import *\nexcept ImportError:\n    pass\n\n\n'
               'def first(h):\n    return heappop(h)\n')
        main = ('import lib\ntry:\n    lib.first([])\nexcept IndexError as e:\n    print("IE", e)\n'
                'try:\n    lib.first((1, 2))\nexcept TypeError as e:\n    print("TE", e)\n')
        out = self.same({"lib.py": lib, "main.py": main})
        self.assertEqual(out, "IE index out of range\nTE heappop() argument must be list, not tuple\n")

    def test_accelerators_without_a_model_are_refused(self):
        for name in ("_json", "_stat", "_functools", "_pickle", "_decimal"):
            lib = 'try:\n    from %s import *\nexcept ImportError:\n    pass\n' % name
            err = self.refused_any({"lib.py": lib, "main.py": "import lib\nprint(1)\n"}, "guarded by `except ImportError`")
            self.assertIn("lib.py", err)

    def test_other_import_errors_are_still_refused(self):
        lib = 'try:\n    import readline\nexcept ImportError:\n    readline = None\n'
        err = self.refused_any({"lib.py": lib, "main.py": "import lib\nprint(1)\n"}, "guarded by `except ImportError`")
        self.assertIn("lib.py", err)

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
        files = {"helper.py": "def f(x):\n    return x\n\n\nif f(1) == 1:\n    raise ImportError('x')\n",
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
        # the accelerators map the hidden class back: a sentinel passed as a heap says `object`
        out = self.same({"main.py": "import heapq\ntry:\n    heapq.heappop(object())\nexcept TypeError as e:\n    print(e)\n",
                         "heapq.py": (STDLIB / "heapq.py").read_text(encoding="utf-8")})
        self.assertEqual(out, "heappop() argument must be list, not object\n")

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

    @staticmethod
    def probe():
        """Every function the C modules export, with wrong types, empty input, negative / large lo and hi, key=,
        non-list heaps: each call prints its result or the exception's type and text."""
        out = ["import heapq", "import bisect", "", "", "def neg(v):", "    return -v", ""]

        def call(label, expr):
            out.append("try:")
            out.append("    print(%r, repr(%s))" % (label, expr))
            for ex in ("TypeError", "ValueError", "IndexError", "AttributeError"):
                out.append("except %s as e:" % ex)
                out.append("    print(%r, %r, e)" % (label, ex))
        for name in ("heappush", "heappop", "heapify", "heapreplace", "heappushpop"):
            two = name in ("heappush", "heapreplace", "heappushpop")
            for label, h in (("tuple", "(1, 2)"), ("none", "None"), ("str", "'ab'"), ("int", "5"), ("dict", "{}"),
                             ("empty", "[]"), ("cmp", "[3, 1]"), ("ok", "[1, 5, 3]"), ("one", "[7]")):
                extra = (", 'a'" if label == "cmp" else ", 2") if two else ""
                call(name + " " + label, "heapq.%s(%s%s)" % (name, h, extra))
        out += ["h = [5, 2, 8, 1, 9, 3]", "heapq.heapify(h)", "print(h, heapq.heappop(h), h)", "heapq.heappush(h, 0)",
                "print(h, heapq.heappushpop(h, 4), heapq.heapreplace(h, 6), h)"]
        for name in ("bisect_left", "bisect_right", "insort_left", "insort_right"):
            for label, args in (("plain", "[1, 3, 5], 3"), ("neglo", "[1, 3], 2, -1"), ("hi5", "[1, 3], 2, 0, 5"),
                                ("hilt", "[1, 3], 2, 2, 1"), ("hi-1", "[1, 3], 2, 0, -1"), ("hi-2", "[1, 3], 2, 0, -2"),
                                ("cmp", "[1, 3], 'a'"), ("nolen", "5, 1"), ("lostr", "[1, 3], 2, 'a'"),
                                ("histr", "[1, 3], 2, 0, 'b'"), ("lofloat", "[1, 3], 2, 1.5"),
                                ("hifloat", "[1, 3], 2, 0, 1.5"), ("lonone", "[1, 3], 2, None"),
                                ("hinone", "[1, 3], 2, 0, None"), ("lobool", "[1, 3], 2, True"),
                                ("tuple", "(1, 3), 2"), ("empty", "[], 1"), ("str", "'abc', 'b'"),
                                ("key", "[3, 2, 1], -2, key=neg"), ("keybad", "[1, 3], 2, key=1")):
                call(name + " " + label, "bisect.%s(%s)" % (name, args))
        return "\n".join(out) + "\n"

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

    def test_accelerator_behaviour_matches_the_c_modules(self):
        """The coordinator's case (heappop([]) says `index out of range`, the C text) and every other exported
        function against CPython, which runs the C modules."""
        shutil.copy(STDLIB / "bisect.py", self.dir / "bisect.py")
        shutil.copy(STDLIB / "heapq.py", self.dir / "heapq.py")
        (self.dir / "main.py").write_text(self.probe(), encoding="utf-8")
        expected = subprocess.run([sys.executable, "-B", "main.py"], cwd=self.dir, capture_output=True, timeout=60)
        self.assertEqual(expected.returncode, 0, expected.stderr.decode())
        self.assertIn(b"index out of range", expected.stdout)
        built, exe = compile_program(self.dir, "main.py", "1")
        self.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
        self.assertEqual(ran.returncode, 0, ran.stderr.decode())
        self.assertEqual(ran.stdout.decode(), expected.stdout.decode())

    def test_calls_the_c_modules_reject_by_arity_or_keyword_are_refused(self):
        shutil.copy(STDLIB / "heapq.py", self.dir / "heapq.py")
        for body in ("heapq.heappush([1])", "heapq.heappush(heap=[1], item=3)", "heapq.heappop()"):
            write(self.dir, {"main.py": "import heapq\ntry:\n    %s\nexcept TypeError as e:\n    print(e)\n" % body})
            built = subprocess.run([sys.executable, "-B", CLI, "compile", "main.py", "-o", str(self.dir / "out")],
                                   cwd=self.dir, capture_output=True, text=True, timeout=300)
            self.assertEqual(built.returncode, 3, built.stderr)
            self.assertIn("heappush" if "push" in body else "heappop", built.stderr)


if __name__ == "__main__":
    unittest.main()
