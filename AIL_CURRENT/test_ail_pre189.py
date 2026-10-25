"""Pre-189: run-time attribute lookups on instances and classes.

A method name computed at run time, `getattr(obj, "me" + "th")(...)`, now reaches the method the
way the literal spelling already did (including an override, a @staticmethod, a @classmethod and
the value arriving through an argument, a list item, an attribute and a dict value).  An
instance's `__class__` and `__dict__` are visible to `hasattr`, and `__dict__` reads the same
mapping `vars()` returns.

`getattr` / `hasattr` / `setattr` on a class value are refused at compile time by name on both
builds: a class object here keeps its methods and class attributes outside the instance table, so
there is no run-time mapping to read or write.  CPython accepts these, so the refusal is recorded
in DIFFERENCES rather than answered with a NotImplementedError at run time.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

DYNAMIC_METHOD = r'''class Base:
    def meth(self, a):
        return a + 1

    def other(self):
        return "base-other"


class M(Base):
    def __init__(self):
        self.x = 10

    def meth(self, a):
        return a + self.x

    def zero(self):
        return "zero"

    def two(self, a, b=3):
        return a + b

    @staticmethod
    def stat(v):
        return v * 2

    @classmethod
    def make(cls, v):
        return str(v) + "!"


class Holder:
    pass


def call(obj, name, a):
    return getattr(obj, name)(a)


def main():
    m = M()
    print(getattr(m, "me" + "th")(5))
    print(getattr(m, "meth")(6))
    print(getattr(m, "x"))
    print(getattr(m, "zer" + "o")())
    print(getattr(m, "oth" + "er")())
    print(getattr(m, "sta" + "t")(4))
    print(getattr(m, "mak" + "e")("z"))
    name = "met" + "h"
    print(getattr(m, name)(7))
    print(call(m, "met" + "h", 8))
    xs = [m]
    print(getattr(xs[0], "met" + "h")(9))
    d = {"m": m}
    print(getattr(d["m"], "met" + "h")(10))
    h = Holder()
    h.m = m
    print(getattr(h.m, "met" + "h")(11))
    print(getattr(m, "two")(1, 2))
    print(getattr(m, "two")(1))
    try:
        print(getattr(m, "nope"))
    except Exception as exc:
        print(type(exc).__name__, exc)
    try:
        print(getattr(m, "x" + "")())
    except Exception as exc:
        print(type(exc).__name__, exc)
    print(getattr(m, "x", "dflt"))


main()
'''

HASATTR = r'''class M:
    def __init__(self):
        self.x = 1
        self.y = "two"


class E(Exception):
    pass


def main():
    m = M()
    for name in ("__class__", "__dict__"):
        print(name, hasattr(m, name))
    print(hasattr(m, "__cl" + "ass__"), hasattr(m, "__di" + "ct__"))
    print(getattr(m, "__dict__"))
    print(getattr(m, "__dict__") == vars(m))
    print(getattr(m, "__cl" + "ass__") is M)
    print("__dict__" in getattr(m, "__dict__"), getattr(m, "__dict__")["x"])
    try:
        raise E("bad")
    except E as exc:
        print(hasattr(exc, "__class__"), hasattr(exc, "__dict__"), getattr(exc, "__dict__"))


main()
'''

CLASS_GETATTR = r'''class C:
    x = 5


name = "x"
print(getattr(C, name))
'''
CLASS_SETATTR = r'''class C:
    pass


name = "y"
setattr(C, name, 3)
print(C.y)
'''
CLASS_HASATTR = r'''class C:
    pass


name = "__class__"
print(hasattr(C, name))
'''
CLASS_CASES = (("getattr", CLASS_GETATTR), ("setattr", CLASS_SETATTR), ("hasattr", CLASS_HASATTR))


class Pre189Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-pre189-")
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

    def test_computed_method_name(self):
        self.check_output("dynamic_method", DYNAMIC_METHOD)

    def test_hasattr_class_and_dict(self):
        self.check_output("hasattr", HASATTR)

    def test_class_attribute_builtins_refused_by_name(self):
        for slug, text in CLASS_CASES:
            with self.subTest(slug=slug):
                want = self.cpython("class_" + slug, text)
                self.assertEqual(want.returncode, 0, want.stderr)
                for general in (False, True):
                    built = self.build("class_" + slug, text, general)
                    shown = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, "built a program whose output would differ")
                    self.assertIn("on the class C", shown)


if __name__ == "__main__":
    unittest.main()
