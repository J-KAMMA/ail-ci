"""ex2: CPython's `__file__` binding, compared with CPython 3.12 on the general path
(AIL_UNIFIED_FORCE=1) and the default build, plus a previously refused language example.

* every program is compiled twice and must print what CPython prints (same stdout and exit code);
* the docstring case that shares its line with the first read (`"\"\"doc\"\"\"; print(__file__)`) is
  the minimal reproducer: a text-level binding inserted after the docstring used to land after the
  print it must precede;
* `language_examples/math.ail` (a module constant plus functions, no call) was refused by the
  default build ("the first parameter must be the sequence read from the file"); CPython runs its
  module body and prints nothing, and both builds must now match that;
* an imported module's `__file__` is its own path, and a namespace package's is None, as in CPython.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "language_examples"

PROGRAMS = {}
PROGRAMS["basic"] = '''import os
print(__file__)
print(os.path.isabs(__file__), os.path.basename(__file__), os.path.dirname(__file__))
print(type(__file__) is str)
'''
PROGRAMS["doc_same_line"] = '''"""doc"""; print(__file__)
'''
PROGRAMS["doc_multiline"] = '''"""first
second"""; print(__file__)
'''
PROGRAMS["doc_future"] = '''"""doc"""
from __future__ import annotations
def f(x: int) -> int:
    return x + 1
print(__file__, f(1))
'''
PROGRAMS["override"] = '''__file__ = "custom"
print(__file__)
'''
PROGRAMS["scope"] = '''before = __file__
def show(value):
    return value
print(show(__file__))
print([__file__][0])
print({"k": __file__}["k"])
class C:
    name = __file__
print(C.name, type(__file__).__name__)
'''
PROGRAMS["no_file"] = '''print(40 + 2)
'''
PROGRAMS["module_const_function"] = '''LIMIT = 6
def sum_to(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total
'''


def build(directory, source, name, **env):
    exe = Path(directory, name)
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source,
                            "--syntax", "python", "-o", str(exe)], cwd=directory, capture_output=True,
                           text=True, timeout=1800,
                           env=dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env))
    return built, exe


def compare(test, directory, source, name, **env):
    want = subprocess.run([sys.executable, "-X", "utf8", str(source)], cwd=directory,
                          capture_output=True, timeout=300)
    built, exe = build(directory, source, name, **env)
    test.assertEqual(built.returncode, 0, "%s: %s%s" % (name, built.stdout[-400:], built.stderr[-600:]))
    got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=300)
    test.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-300:]))
    test.assertEqual(got.stdout.decode(), want.stdout.decode(), name)
    return built


class FileDunder(unittest.TestCase):
    def test_general_path(self):
        for name, text in PROGRAMS.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                Path(directory, name + ".py").write_text(text, encoding="utf-8")
                compare(self, directory, name + ".py", "p_" + name, AIL_UNIFIED_FORCE="1")

    def test_default_build(self):
        for name, text in PROGRAMS.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                Path(directory, name + ".py").write_text(text, encoding="utf-8")
                compare(self, directory, name + ".py", "p_" + name)

    def test_imported_module_and_namespace(self):
        text = '''import helper
import nspkg
import nspkg.sub
print(helper.where() == helper.EXPOSED, helper.EXPOSED.endswith("helper.py"))
print(nspkg.sub.VALUE.endswith("sub.py"), nspkg.sub.__file__ == nspkg.sub.VALUE)
print(nspkg.__file__)
'''
        for env in ({"AIL_UNIFIED_FORCE": "1"}, {}):
            with self.subTest(general=bool(env)), tempfile.TemporaryDirectory() as directory:
                Path(directory, "helper.py").write_text('EXPOSED = __file__\ndef where():\n    return __file__\n',
                                                        encoding="utf-8")
                Path(directory, "nspkg").mkdir()
                Path(directory, "nspkg", "sub.py").write_text('VALUE = __file__\n', encoding="utf-8")
                Path(directory, "main.py").write_text(text, encoding="utf-8")
                compare(self, directory, "main.py", "p_ns", **env)


class Coverage(unittest.TestCase):
    """`math.ail` is a language example the default build refused; it must build and match CPython."""

    def test_math_example(self):
        for env in ({"AIL_UNIFIED_FORCE": "1"}, {}):
            with self.subTest(general=bool(env)), tempfile.TemporaryDirectory() as directory:
                shutil.copy(EXAMPLES / "math.ail", Path(directory, "math.ail"))
                compare(self, directory, "math.ail", "p_math", **env)

    def test_def_only_entry_convention_kept(self):
        # a def-only source keeps the function-entry convention's by-name refusal (no general scope)
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "d.py").write_text("def f(n):\n    return n\n", encoding="utf-8")
            built, _ = build(directory, "d.py", "d")
            self.assertNotEqual(built.returncode, 0)
            self.assertIn("the first parameter must be the sequence read from the file",
                          built.stdout + built.stderr)


if __name__ == "__main__":
    unittest.main()
