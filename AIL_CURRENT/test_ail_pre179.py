"""Pre-179: getattr-style reads of an exception's chain attributes name the refusal.

The direct attribute forms (`e.__context__`, ...) were already refused by name because only one
exception is ever live.  The same read through `getattr`/`hasattr` still built and then raised
`AttributeError` (or returned the default / False) where CPython returns None, False or the
traceback.  Literal chain names are now refused by name at compile time on both builds, and a chain
name computed at run time is refused by name when it reaches an exception, so no fabricated value
is returned.  Ordinary getattr/hasattr/setattr of a program's own fields is unchanged (including a
computed write of a chain-named field, which the following read sees as usual).
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


def via(kind, e, name) -> None:
    try:
        if kind == "get":
            print("value", name, repr(getattr(e, name)))
        elif kind == "default":
            print("value", name, repr(getattr(e, name, "missing")))
        else:
            print("value", name, hasattr(e, name))
    except AttributeError as x:
        print("refused", kind, name, "exception chaining" in str(x))


def f() -> None:
    try:
        int("x")
    except ValueError as e:
        names = ["__con" + "text__", "__ca" + "use__", "__suppress_" + "context__", "__trace" + "back__"]
        for name in names:
            via("get", e, name)
            via("default", e, name)
            via("has", e, name)
        items = [e]
        via("get", items[0], "__ca" + "use__")
        h = Holder()
        h.e = e
        via("get", h.e, "__con" + "text__")
        d = {"e": e}
        via("get", d["e"], "__suppress_" + "context__")
        setattr(e, "__ca" + "use__", None)
        print("after-set", getattr(e, "__ca" + "use__"), hasattr(e, "__ca" + "use__"))

f()
'''

UNCAUGHT = r'''def f(name: str) -> None:
    try:
        int("x")
    except ValueError as e:
        print(getattr(e, name))

f("__con" + "text__")
'''

ORDINARY = r'''class Box:
    pass


def read(obj, name) -> None:
    print(repr(getattr(obj, name, "missing")))
    print(hasattr(obj, name))


def write(obj, name, value) -> None:
    setattr(obj, name, value)


def f() -> None:
    b = Box()
    b.x = 1
    b.y = "two"
    read(b, "x")
    read(b, "y")
    read(b, "z")
    read(b, "__context__")
    print(getattr(b, "x"), getattr(b, "z", "d"))
    setattr(b, "z", 3)
    print(b.z, hasattr(b, "z"))
    write(b, "w", 4)
    print(b.w, getattr(b, "w"), hasattr(b, "w"))

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

    def test_dynamic_chain_reads_refused_by_name(self):
        want = set()
        for attr in ("__context__", "__cause__", "__suppress_context__", "__traceback__"):
            for kind in ("get", "default", "has"):
                want.add("refused %s %s True" % (kind, attr))
        for general in (False, True):
            built = self.build("dynamic", DYNAMIC, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(self.dir / ("exe_dynamic" + ("_g" if general else "_d")))],
                                 cwd=self.dir, capture_output=True, text=True, timeout=120)
            self.assertEqual(got.returncode, 0, got.stderr)
            lines = got.stdout.splitlines()
            self.assertEqual(set(line for line in lines if line.startswith("refused ")), want)
            self.assertFalse([line for line in lines if line.startswith("value ")], lines)
            self.assertEqual(lines.count("after-set None True"), 1, lines)

    def test_uncaught_dynamic_chain_read_names_refusal(self):
        for general in (False, True):
            built = self.build("uncaught", UNCAUGHT, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(self.dir / ("exe_uncaught" + ("_g" if general else "_d")))],
                                 cwd=self.dir, capture_output=True, text=True, timeout=120)
            self.assertNotEqual(got.returncode, 0)
            self.assertIn("reading __context__", got.stderr)
            self.assertIn("exception chaining", got.stderr)

    def test_ordinary_getattr_is_unchanged(self):
        self.check_output("ordinary", ORDINARY)


if __name__ == "__main__":
    unittest.main()
