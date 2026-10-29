"""`__file__` is the implicit module-level binding of a Python-syntax program (reex26).

CPython binds `__file__` in a module's namespace before its body runs: the entry's is the path as
invoked, made absolute without normalising (`./p.py` keeps its dot); an imported module's is its own
absolute path; a namespace package has None. A read before a user assignment sees that value, and a
later assignment, `del`, parameter, lambda argument, `except ... as` binding or loop target follows
the ordinary name rules. The programs below are run by CPython 3.12 as the oracle and built with
`ail_chatgpt.py compile` on both builds (the default and AIL_UNIFIED_FORCE=1), with the same stdout
and exit status.

Every construct the implementation does not model is refused by name: `del __file__` in an imported
module and `m.__file__ = v` (a later read would be AttributeError in CPython), and an import that
binds the name (`from lib import __file__`).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
BUILDS = (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"}))


def write(directory, files):
    for name, text in files.items():
        path = Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class FileBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-reex26-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, files, entry="main.py"):
        write(self.dir, files)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        return subprocess.run([sys.executable, "-B", entry], cwd=self.dir, capture_output=True,
                              timeout=120, env=env)

    def build(self, entry, extra_env):
        exe = self.dir / ("out-" + extra_env.get("AIL_UNIFIED_FORCE", "0"))
        if exe.exists():
            exe.unlink()
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **extra_env)
        return subprocess.run([sys.executable, "-B", CLI, "compile", entry, "-o", str(exe)],
                              cwd=self.dir, capture_output=True, text=True, timeout=600, env=env), exe

    def same(self, files, entry="main.py"):
        """Both builds print exactly what CPython prints and exit the same way."""
        expected = self.cpython(files, entry)
        for name, extra in BUILDS:
            built, exe = self.build(entry, extra)
            self.assertEqual(built.returncode, 0, "%s: %s" % (name, built.stdout + built.stderr))
            ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, timeout=120)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                             "%s build\n%s" % (name, ran.stderr.decode(errors="replace")))
        return expected.stdout.decode()

    def refused(self, files, *needles, entry="main.py"):
        write(self.dir, files)
        for name, extra in BUILDS:
            built, exe = self.build(entry, extra)
            self.assertEqual(built.returncode, 2, "%s: %s" % (name, built.stdout + built.stderr))
            self.assertFalse(exe.exists())
            for needle in needles:
                self.assertIn(needle, built.stderr)
            self.assertIn("write instead", built.stderr)
            self.assertNotIn("Traceback", built.stderr)

    def test_entry_path_and_arithmetic(self):
        out = self.same({"main.py": """print(__file__)
x = __file__ + "!"
print(x.endswith("!"))
print(type(__file__).__name__, len(__file__) == len(x) - 1)
print(__file__.rsplit("/", 1)[-1])
""", "extra.txt": ""})
        self.assertTrue(out.splitlines()[0].endswith("/main.py"), out)

    def test_path_as_invoked_keeps_its_dot(self):
        # `python3 ./main.py` names "/dir/./main.py"; the build must bake the same text
        expected = self.cpython({"main.py": "print(__file__)\n"}, "./main.py")
        self.assertIn("/./main.py", expected.stdout.decode())
        for name, extra in BUILDS:
            built, exe = self.build("./main.py", extra)
            self.assertEqual(built.returncode, 0, "%s: %s" % (name, built.stdout + built.stderr))
            ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, timeout=120)
            self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout), name)

    def test_value_reaches_code_through_argument_list_item_attribute_and_dict(self):
        self.same({"main.py": """def take(p):
    return p
items = [__file__]
table = {'k': __file__}
class Box:
    def __init__(self, p):
        self.p = p
print(take(__file__).endswith('.py'))
print(items[0] == __file__)
print(table['k'] == __file__)
print(Box(__file__).p == __file__)
print(f'<{__file__}>' == '<' + __file__ + '>')
"""})

    def test_assignment_order_and_augmented_assignment(self):
        self.same({"main.py": """print(__file__.endswith('.py'))
__file__ = 'replaced'
print(__file__)
__file__ += '!'
print(__file__)
"""})
        self.same({"main.py": """__file__ = './kept'
print(__file__)
"""})
        self.same({"main.py": """for __file__ in ['a', 'b']:
    print(__file__)
print(__file__)
"""})

    def test_parameter_lambda_except_and_global(self):
        self.same({"main.py": """def f(__file__):
    return __file__
print(f('arg'))
print(__file__[-3:])
g = lambda __file__: __file__ + '?'
print(g('q'))
def read():
    global __file__
    return __file__
__file__ = 'set-from-global'
print(read())
"""})
        self.same({"main.py": """try:
    raise ValueError('boom')
except ValueError as __file__:
    print(__file__)
print('after')
"""})

    def test_delete_then_read_raises_name_error(self):
        expected = self.cpython({"main.py": "del __file__\nprint('gone')\nprint(__file__)\n"})
        self.assertEqual(expected.returncode, 1)
        stdout = self.same({"main.py": "del __file__\nprint('gone')\nprint(__file__)\n"})
        self.assertEqual(stdout, "gone\n")

    def test_imported_module_and_package_paths(self):
        self.same({"lib.py": "X = 41\ndef where():\n    return __file__\nprint(__file__)\n",
                   "main.py": "import lib\nprint(lib.__file__)\nprint(lib.where())\n"
                              "print(lib.where() == lib.__file__)\nprint(__file__)\nprint(lib.X)\n"})
        self.same({"pkg/__init__.py": "from . import b\nprint(__file__)\nV = b.W\n",
                   "pkg/b.py": "W = 7\nprint(__file__)\n",
                   "main.py": "import pkg\nprint(pkg.__file__)\nprint(pkg.b.__file__)\nprint(pkg.V)\n"})

    def test_imported_module_assignment_order(self):
        self.same({"lib.py": "print(__file__.endswith('lib.py'))\n__file__ = 'mine'\nprint(__file__)\n",
                   "main.py": "import lib\nprint(lib.__file__)\n"})

    def test_namespace_package_is_none(self):
        out = self.same({"pkg/a.py": "A = 1\n",
                         "main.py": "import pkg\nimport pkg.a\nprint(pkg.__file__)\n"
                                    "print(pkg.a.__file__)\nprint(pkg.a.A)\n"})
        self.assertEqual(out.splitlines()[0], "None")

    def test_refusals_are_named(self):
        self.refused({"lib.py": "del __file__\nX = 1\n", "main.py": "import lib\nprint(lib.X)\n"}, "__file__")
        self.refused({"lib.py": "X = 1\n", "main.py": "import lib\nlib.__file__ = 'x'\nprint(lib.X)\n"},
                     "__file__")
        self.refused({"lib.py": "X = 1\n", "main.py": "from lib import __file__\nprint(__file__)\n"},
                     "__file__")
        # CPython deletes a module-level handler name at the end of the handler, so `lib.__file__`
        # would be an AttributeError; the merged program would read an unbound variable instead.
        self.refused({"lib.py": "try:\n    raise ValueError('x')\nexcept ValueError as __file__:\n"
                                "    print(type(__file__).__name__)\n",
                      "main.py": "import lib\nprint(lib.__file__)\n"}, "__file__")


if __name__ == "__main__":
    unittest.main()
