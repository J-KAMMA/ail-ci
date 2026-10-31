"""A Python-syntax program's int64 overflow is a loud stop that no handler sees (zero silent differences).

CPython ints never overflow, so an `except OverflowError` / `except Exception` / bare `except` around int
arithmetic must never run for a value CPython computes exactly. On the legacy int64 emitter (AIL_IR=0, the typed-only
build, an `@extern` program linked typed-only, a function the tagged lowering refuses) the "integer overflow" trap used
to be mapped to a catchable OverflowError, so the compiled program printed the handler's output and exited 0 where
CPython printed the exact value. Now it ends the program: "integer overflow" on stderr, exit 1, the output written so
far kept. The OverflowErrors CPython raises too (int(<inf>), float `**` range error, math.exp, round(<inf>)) stay
catchable and CPython-identical, and a program in the AIL syntax keeps its catchable int64 OverflowError (A1,
test_ail_overflow_error).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_ail_ffi import CC, build_tiny, compile_cli, run_cpython

ROOT = Path(__file__).resolve().parent
BIG = "9223372036854775807"

# (name, a function body over a, b with a = INT64_MAX, b = 2): every operation leaves int64
OPS = (
    ("add", "a + b"),
    ("mul", "a * b"),
    ("shl", "a << 63"),
    ("pow", "a ** b"),
    ("abs", "abs(-a - b)"),
    ("neg", "-(-a - 1) if b > 1 else 0"),
)

HANDLERS = ("except OverflowError:", "except Exception:", "except:")

TEMPLATE = """
def f(a: int, b: int) -> int:
    return {expr}

def main():
    print("start")
    big = {big}
    try:
        print(f(big, 2))
    {handler}
        print("caught")
    print("end")

main()
"""

LEGIT = """
import math

def to_int(x: float) -> int:
    return int(x)

def power(x: float, y: float) -> float:
    return x ** y

def exp(x: float) -> float:
    return math.exp(x)

def main():
    inf = 1e308 * 10.0
    try:
        print(to_int(inf))
    except OverflowError:
        print("caught int(inf)")
    try:
        print(power(10.0, 400.0))
    except OverflowError:
        print("caught pow")
    try:
        print(exp(1000.0))
    except OverflowError:
        print("caught exp")
    try:
        print(round(inf))
    except OverflowError:
        print("caught round")
    try:
        print(to_int(1e30))
    except ValueError:
        print("no")
    print("end")

main()
"""

# a function the tagged lowering refuses (it reads e.errno) keeps the legacy int64 emitter in the default build
REFUSED = """
def work(a: int, b: int) -> int:
    try:
        open("/nonexistent/zz")
    except OSError as e:
        print(e.errno)
    return a * b

def main():
    try:
        print(work(9223372036854775807, 3))
    except Exception as ex:
        print("caught", type(ex).__name__)
    print("end")

main()
"""

FFI = """from ail_ffi import *

@extern(lib="./libtiny.so", header="tiny.h")
def tiny_add(a: c_int, b: c_int) -> c_int: ...

def grow(a: int, b: int) -> int:
    return a * b

def main():
    print(tiny_add(1, 2))
    try:
        print(grow(9223372036854775807, 2))
    except {handler}:
        print("caught")
    print("end")

main()
"""


def build_and_run(directory, name, source, env):
    path = Path(directory, name + ".py")
    path.write_text(source, encoding="utf8")
    out = Path(directory, name + ".out")
    if out.exists():
        out.unlink()
    environment = dict(os.environ, PYTHONPATH=str(ROOT), **env)
    for key in [k for k, v in env.items() if v is None]:
        environment.pop(key, None)
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(path), "-o", str(out), "--no-cache"],
                           cwd=directory, capture_output=True, text=True, timeout=600, env=environment)
    if built.returncode:
        return built, None
    return built, subprocess.run([str(out)], cwd=directory, capture_output=True, text=True, timeout=60)


class OverflowUncatchableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-ovf-test-")
        cls.dir = cls.temp.name

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def cpython(self, name, source):
        path = Path(self.dir, name + "_cpy.py")
        path.write_text(source, encoding="utf8")
        done = run_cpython(self.dir, str(path))
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def assert_loud_stop(self, ran, expected, label):
        """The exact CPython answer, or the loud stop with the output so far and no handler output."""
        self.assertNotIn("caught", ran.stdout, label)
        if ran.returncode == 0:
            self.assertEqual(ran.stdout, expected, label)
        else:
            self.assertEqual(ran.returncode, 1, label)
            self.assertIn("integer overflow", ran.stderr, label)
            self.assertTrue(expected.startswith(ran.stdout) and ran.stdout.startswith("start\n"), label)
            self.assertNotIn("end", ran.stdout, label)

    def test_legacy_emitter_overflow_is_not_catchable(self):
        for op, expr in OPS:
            for handler in HANDLERS:
                source = TEMPLATE.format(expr=expr, big=BIG, handler=handler)
                label = "%s %s" % (op, handler)
                expected = self.cpython("t_" + op, source)
                self.assertNotIn("caught", expected)
                built, ran = build_and_run(self.dir, "t_" + op, source, {"AIL_NO_GENERAL": "1", "AIL_IR": "0"})
                self.assertEqual(built.returncode, 0, built.stderr)
                self.assertEqual(ran.returncode, 1, label + ran.stdout)
                self.assert_loud_stop(ran, expected, label)

    def test_typed_only_build_on_the_ir(self):
        for op, expr in OPS:
            source = TEMPLATE.format(expr=expr, big=BIG, handler="except Exception:")
            expected = self.cpython("i_" + op, source)
            built, ran = build_and_run(self.dir, "i_" + op, source, {"AIL_NO_GENERAL": "1", "AIL_IR": "1"})
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assert_loud_stop(ran, expected, "ir " + op)

    def test_default_build_is_exact_or_loud(self):
        source = TEMPLATE.format(expr="a * b", big=BIG, handler="except OverflowError:")
        expected = self.cpython("d_mul", source)
        built, ran = build_and_run(self.dir, "d_mul", source, {"AIL_NO_GENERAL": None})
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assert_loud_stop(ran, expected, "default")

    def test_function_the_tagged_lowering_refuses(self):
        expected = self.cpython("refused", REFUSED)
        built, ran = build_and_run(self.dir, "refused", REFUSED, {"AIL_NO_GENERAL": None})
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertNotIn("caught", ran.stdout)
        if ran.returncode:
            self.assertEqual(ran.returncode, 1)
            self.assertIn("integer overflow", ran.stderr)
            self.assertEqual(ran.stdout, "2\n")
        else:
            self.assertEqual(ran.stdout, expected)

    @unittest.skipUnless(CC, "installed C compiler required")
    def test_ffi_program_linked_typed_only(self):
        build_tiny(self.dir)
        for ir in ("0", "1"):
            for handler in ("OverflowError", "Exception"):
                source = FFI.format(handler=handler)
                path = Path(self.dir, "ffi.py")
                path.write_text(source, encoding="utf8")
                built, exe = compile_cli(self.dir, "ffi.py", ir=ir, name="ffi.out")
                self.assertEqual(built.returncode, 0, built.stderr)
                ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60)
                expected = run_cpython(self.dir, "ffi.py").stdout
                label = "ffi ir=%s %s" % (ir, handler)
                self.assertTrue(expected.endswith("end\n"), expected)
                self.assertNotIn("caught", ran.stdout, label)
                if ran.returncode == 0:
                    self.assertEqual(ir, "1", label)          # the tagged lowering computed the exact value
                    self.assertEqual(ran.stdout, expected, label)
                else:                                          # the legacy int64 emitter: the loud stop
                    self.assertEqual(ran.returncode, 1, label)
                    self.assertIn("integer overflow", ran.stderr, label)
                    self.assertEqual(ran.stdout, "3\n", label)

    def test_overflow_errors_cpython_raises_stay_catchable(self):
        expected = self.cpython("legit", LEGIT)
        self.assertIn("caught int(inf)", expected)
        for label, env in (("typed-only legacy", {"AIL_NO_GENERAL": "1", "AIL_IR": "0"}),
                           ("typed-only ir", {"AIL_NO_GENERAL": "1", "AIL_IR": "1"})):
            built, ran = build_and_run(self.dir, "legit", LEGIT, env)
            self.assertEqual(built.returncode, 0, built.stderr)
            # 1e30 does not fit int64: the declared stop (A1), reached only after the four catchable ones
            self.assertTrue(ran.stdout.startswith("caught int(inf)\ncaught pow\ncaught exp\ncaught round\n"), label + ran.stdout + ran.stderr)
        built, ran = build_and_run(self.dir, "legit_d", LEGIT.replace("print(to_int(1e30))", "print(1)"), {"AIL_NO_GENERAL": "1", "AIL_IR": "0"})
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, self.cpython("legit_d", LEGIT.replace("print(to_int(1e30))", "print(1)")))


import os as _os_exact_int

_SAVED_EXACT_INT = None


def setUpModule():
    # these tests are about exact (arbitrary precision) ints: the opt-in mode (intmode.py, `--exact-int`)
    global _SAVED_EXACT_INT
    _SAVED_EXACT_INT = _os_exact_int.environ.get('AIL_EXACT_INT')
    _os_exact_int.environ['AIL_EXACT_INT'] = '1'


def tearDownModule():
    if _SAVED_EXACT_INT is None:
        _os_exact_int.environ.pop('AIL_EXACT_INT', None)
    else:
        _os_exact_int.environ['AIL_EXACT_INT'] = _SAVED_EXACT_INT


if __name__ == "__main__":
    unittest.main()
