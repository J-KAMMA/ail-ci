"""Out-of-int64 constant expressions outside a function body are refused by name (job pre184).

The fuzz47 reviewer left `corpus/gdev/g22_012.py` failing on both builds: a class body
`_MASK: int = (1 << 64) - 1` compiled and stopped at run time with `integer overflow`, while
CPython prints the result.  A default such as `def f(x=10**30)` did the same.  A constant integer
expression in a module/class assignment or a default argument now fails at compile time with
`int64 constant expression out of range`.  Expressions that fit int64 keep working, and an
out-of-int64 expression in a function body keeps its old runtime stop (see test_ail_pre160).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")


REFUSED = {
    "class_annassign": """class C:
    MASK: int = (1 << 64) - 1

print(C.MASK)
""",
    "class_assign": """class C:
    MASK = 1 << 64

print(C.MASK)
""",
    "class_pow": """class C:
    M = 2 ** 100

print(C.M)
""",
    "class_annassign_pow": """class C:
    M: int = 2 ** 100

print(C.M)
""",
    "module_assign": """MASK = (1 << 64) - 1
print(MASK)
""",
    "default_pow": """def f(x=10**30):
    return x

print(f())
""",
    "default_shift": """def f(x=1 << 64):
    return x

print(f())
""",
    "default_negative_pow": """def f(x=-(10 ** 30)):
    return x

print(f())
""",
}

IN_RANGE = {
    "class_arithmetic": """class C:
    A = 2 ** 62
    B = -(2 ** 62)
    C = (1 << 62) + 3

print(C.A, C.B, C.C)
""",
    "default_arithmetic": """def f(a=2 ** 62, b=-(2 ** 62), c=(1 << 62) + 3):
    return (a, b, c)

print(f())
""",
    "module_arithmetic": """A = 2 ** 62
B = -(2 ** 62)
C = (1 << 62) + 3
print(A, B, C)
""",
    "power_guard_boundaries": """print(0 ** 0, 0 ** 1, 0 ** 100000)
print(1 ** 100000, (-1) ** 100000, (-1) ** 100001)
print(-1 ** 100000)
print(0 << 0, 0 << 4097, 0 << 100000)
""",
    "guard_class_and_default": """class C:
    X = 0 ** 100000
    Y = 0 << 100000

def f(a=0 ** 100000, b=(-1) ** 100001, c=0 << 100000):
    return (a, b, c)

print(C.X, C.Y, f())
""",
}


def run_py(path):
    done = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=60)
    return done.returncode, done.stdout


class Pre184Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-pre184-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, name, source, general):
        path = self.dir / (name + ".py")
        path.write_text(source, encoding="utf-8")
        exe = self.dir / (name + ("_g" if general else "_d"))
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python",
                                "-o", str(exe)], cwd=self.dir, capture_output=True, text=True, env=env)
        return built, exe

    def test_out_of_int64_constant_is_refused(self):
        # exact ints (bigint)
        for name, source in REFUSED.items():
            path = self.dir / (name + "_ref.py")
            path.write_text(source, encoding="utf-8")
            want_code, want_out = run_py(path)
            for general in (False, True):
                built, exe = self.build(name, source, general)
                self.assertEqual(built.returncode, 0, name + " general=" + str(general) + "\n"
                                 + built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
                self.assertEqual((ran.stdout, ran.returncode), (want_out, want_code),
                                 name + " general=" + str(general))

    def test_in_range_constant_still_matches_cpython(self):
        for name, source in IN_RANGE.items():
            path = self.dir / (name + "_ref.py")
            path.write_text(source, encoding="utf-8")
            want_code, want_out = run_py(path)
            for general in (False, True):
                built, exe = self.build(name, source, general)
                self.assertEqual(built.returncode, 0, name + " general=" + str(general) + "\n"
                                 + built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
                self.assertEqual(ran.stdout, want_out, name + " general=" + str(general))
                self.assertEqual(ran.returncode, want_code, name + " general=" + str(general))


if __name__ == "__main__":
    unittest.main()
