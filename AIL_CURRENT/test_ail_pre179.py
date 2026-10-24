"""Pre-179: a getattr-style read of an exception's chain attributes names the refusal.

The direct attribute forms (`e.__context__`, ...) were already refused by name because only one
exception is ever live.  The same read through `getattr`/`hasattr` still built and then raised
`AttributeError` (or returned the default / False) where CPython returns None, False or the
traceback.  Literal chain names are now refused by name on both builds, and a name computed at run
time reads CPython's values (context/cause None, suppress_context False, and hasattr True for all
four).  Ordinary getattr/hasattr/setattr of a program's own fields is unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

LITERAL_CASES = (
    ("context", 'print(getattr(e, "__context__"))', "__context__"),
    ("cause", 'print(getattr(e, "__cause__"))', "__cause__"),
    ("suppress", 'print(getattr(e, "__suppress_context__"))', "__suppress_context__"),
    ("traceback", 'print(getattr(e, "__traceback__"))', "__traceback__"),
    ("default", 'print(getattr(e, "__context__", "missing"))', "__context__"),
    ("hasattr", 'print(hasattr(e, "__context__"))', "__context__"),
    ("setattr", 'setattr(e, "__context__", None)\n        print(e)', "__context__"),
)

DYNAMIC = r'''class Holder:
    pass


def show(e, names) -> None:
    for name in names:
        print("get", name, repr(getattr(e, name)))
        print("getd", name, repr(getattr(e, name, "missing")))
        print("has", name, hasattr(e, name))


def f() -> None:
    try:
        int("x")
    except ValueError as e:
        show(e, ["__context__", "__cause__", "__suppress_context__"])
        items = [e]
        show(items[0], ["__context__", "__cause__"])
        h = Holder()
        h.e = e
        show(h.e, ["__suppress_context__", "__cause__"])
        d = {"e": e}
        show(d["e"], ["__context__", "__suppress_context__"])
        for name in ["__con" + "text__", "__ca" + "use__", "__suppress_" + "context__"]:
            print("computed", name, repr(getattr(e, name)), hasattr(e, name))
        for name in ["__context__", "__cause__", "__suppress_context__", "__traceback__"]:
            print("tb-has", name, hasattr(e, name))

f()
'''

ORDINARY = r'''class Box:
    pass


def read(obj, name) -> None:
    print(repr(getattr(obj, name, "missing")))
    print(hasattr(obj, name))


def f() -> None:
    b = Box()
    b.x = 1
    b.y = "two"
    read(b, "x")
    read(b, "y")
    read(b, "z")
    print(getattr(b, "x"), getattr(b, "z", "d"))
    setattr(b, "z", 3)
    print(b.z, hasattr(b, "z"))

f()
'''


def _program(body):
    return ('def f() -> None:\n    try:\n        int("x")\n    except ValueError as e:\n'
            '        ' + body + '\n\n\nf()\n')


class Pre179Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-pre179-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, name, text):
        path = self.dir / (name + "_cpython.py")
        path.write_text(text, encoding="utf-8")
        return subprocess.run([sys.executable, "-B", str(path)], cwd=self.dir,
                              capture_output=True, timeout=120,
                              env=dict(os.environ, PYTHONUTF8="1"))

    def build(self, name, text, general):
        path = self.dir / (name + ".py")
        path.write_text(text, encoding="utf-8")
        exe = self.dir / ("exe_" + name + ("_g" if general else "_d"))
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        return subprocess.run([sys.executable, "-B", CLI, "compile", path.name,
                               "--syntax", "python", "-o", exe.name],
                              cwd=self.dir, capture_output=True, text=True, timeout=900, env=env)

    def check_output(self, name, text):
        want = self.cpython(name, text)
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in (False, True):
            built = self.build(name, text, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(self.dir / ("exe_" + name + ("_g" if general else "_d")))],
                                 cwd=self.dir, capture_output=True, timeout=120)
            self.assertEqual((got.returncode, got.stdout), (0, want.stdout),
                             "%s (general=%s)\n%s" % (name, general, got.stderr.decode("utf-8", "replace")))

    def test_literal_chain_reads_refused_on_both_builds(self):
        for name, body, attr in LITERAL_CASES:
            with self.subTest(name=name):
                text = _program(body)
                want = self.cpython("literal_" + name, text)
                self.assertEqual(want.returncode, 0, want.stderr)
                for general in (False, True):
                    built = self.build("literal_" + name, text, general)
                    shown = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, "built a program whose output would differ")
                    self.assertIn(attr, shown)
                    self.assertIn("exception chaining", shown)

    def test_dynamic_chain_reads_match_cpython(self):
        self.check_output("dynamic", DYNAMIC)

    def test_ordinary_getattr_is_unchanged(self):
        self.check_output("ordinary", ORDINARY)


if __name__ == "__main__":
    unittest.main()
