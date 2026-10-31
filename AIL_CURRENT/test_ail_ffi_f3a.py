"""F3a: integer arguments of an @extern stub behave like CPython's (ail_ffi.py) shim.

The shim checks every int argument against the range of its C type and raises
`OverflowError("<stub>: <param> does not fit <ctype>")` (and `"length of <buffer> does not fit <ctype>"` for a `length`
parameter). Raw ctypes would wrap silently (`-1` to a `c_size_t` becomes 2**64-1, 128 to a `c_int8` becomes -128); the
compiled program used to do the same for 64-bit unsigned types and to stop with `ail_die("C int8 argument out of
range")` for narrow ones. Each program below runs under CPython (the shim) and as the compiled executable, in the default
build, in the typed-only build (`AIL_NO_GENERAL=1`) and with `AIL_UNIFIED_FORCE=1`, and stdout and exit code must be equal.

F3a was written when a program with @extern stubs held int64 only, so a 64-bit unsigned argument could only be too small
and a constant in 2**63 .. 2**64-1 was refused at compile time. F3b (test_ail_ffi_f3b.py) makes those values exact; the
cases below that used to pin the refusal now pin the exact value. bool and float arguments to an int parameter were
already refused at compile time; this module pins that.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

MODES = (("default", {}), ("typed", {"AIL_NO_GENERAL": "1", "AIL_IR": "0"}), ("general", {"AIL_UNIFIED_FORCE": "1"}))

# annotation -> (C type, bits, signed); aliases print under the shim's name (c_byte is c_int8)
TYPES = {
    "c_int8": ("int8_t", 8, True), "c_byte": ("int8_t", 8, True), "c_int16": ("int16_t", 16, True),
    "c_short": ("short", 16, True), "c_int32": ("int32_t", 32, True), "c_int": ("int", 32, True),
    "c_int64": ("int64_t", 64, True), "c_long": ("long", 64, True), "c_longlong": ("long long", 64, True),
    "c_ssize_t": ("ssize_t", 64, True), "c_uint8": ("uint8_t", 8, False), "c_ubyte": ("uint8_t", 8, False),
    "c_uint16": ("uint16_t", 16, False), "c_ushort": ("unsigned short", 16, False), "c_uint32": ("uint32_t", 32, False),
    "c_uint": ("unsigned int", 32, False), "c_uint64": ("uint64_t", 64, False), "c_ulong": ("unsigned long", 64, False),
    "c_ulonglong": ("unsigned long long", 64, False), "c_size_t": ("size_t", 64, False),
}

F3_H = "#include <stdint.h>\n#include <stddef.h>\n#include <sys/types.h>\n" + "".join(
    "int64_t f_%s(%s x);\n" % (name, spec[0]) for name, spec in TYPES.items()) + (
    "int64_t sum_bytes(const unsigned char *p, int8_t n);\n"
    "int64_t sum_ubytes(const unsigned char *p, uint8_t n);\n"
    "int64_t sum_shorts(const unsigned char *p, int16_t n);\n"
    "int64_t sum_ushorts(const unsigned char *p, uint16_t n);\n"
    "int64_t two(int8_t a, uint64_t b);\n")
F3_C = '#include "f3.h"\n' + "".join(
    "int64_t f_%s(%s x) { return (int64_t)x; }\n" % (name, spec[0]) for name, spec in TYPES.items()) + r"""
int64_t sum_bytes(const unsigned char *p, int8_t n) { int64_t s = n; for (int i = 0; i < n; i++) s += p[i]; return s; }
int64_t sum_ubytes(const unsigned char *p, uint8_t n) { int64_t s = n; for (int i = 0; i < n; i++) s += p[i]; return s; }
int64_t sum_shorts(const unsigned char *p, int16_t n) { int64_t s = n; for (int i = 0; i < n; i++) s += p[i]; return s; }
int64_t sum_ushorts(const unsigned char *p, uint16_t n) { int64_t s = n; for (int i = 0; i < n; i++) s += p[i]; return s; }
int64_t two(int8_t a, uint64_t b) { return a * 1000 + (int64_t)(b % 1000); }
"""

STUBS = "from ail_ffi import *\n\n" + "".join(
    '@extern(lib="./libf3.so", header="f3.h")\ndef f_%s(x: %s) -> c_int64: ...\n' % (name, name) for name in TYPES) + '''
@extern(lib="./libf3.so", header="f3.h")
def sum_bytes(p: cptr(c_uint8), n: length("p", c_int8)) -> c_int64: ...
@extern(lib="./libf3.so", header="f3.h")
def sum_ubytes(p: cptr(c_uint8), n: length("p", c_uint8)) -> c_int64: ...
@extern(lib="./libf3.so", header="f3.h")
def sum_shorts(p: cptr(c_uint8), n: length("p", c_int16)) -> c_int64: ...
@extern(lib="./libf3.so", header="f3.h")
def sum_ushorts(p: cptr(c_uint8), n: length("p", c_uint16)) -> c_int64: ...
@extern(lib="./libf3.so", header="f3.h")
def two(a: c_int8, b: c_uint64 = 5) -> c_int64: ...
'''

MIN64 = "(-9223372036854775807 - 1)"


def literal(v):
    return MIN64 if v == -(1 << 63) else str(v)


def probe_values(bits, signed):
    lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
    values = {lo - 1, lo, hi, hi + 1, -1, 0, 1, 127, 128, 255, 256, 32767, 32768, 65535, 65536, 2147483647, 2147483648,
              4294967295, 4294967296, 9223372036854775807, -(1 << 63), -128, -129, -32768, -32769, -2147483648, -2147483649}
    return sorted(v for v in values if -(1 << 63) <= v < (1 << 63))


def matrix_program():
    out = [STUBS]
    calls = []
    for name, (_, bits, signed) in TYPES.items():
        out.append('''
def t_%(n)s(v: int) -> None:
    try:
        r = f_%(n)s(v)
        print("%(n)s", v, r)
    except OverflowError as e:
        print("%(n)s", v, "OverflowError", e)
''' % {"n": name})
        calls += ["    t_%s(%s)" % (name, literal(v)) for v in probe_values(bits, signed)]
    out.append("\ndef main():\n" + "\n".join(calls) + "\n\nmain()\n")
    return "".join(out)


ARGS = STUBS + '''
def attempt(label: str, n: int) -> None:
    try:
        print(label, two(n))
    except OverflowError as e:
        print(label, "OverflowError", e)

def attempt_kw(label: str, a: int, b: int) -> None:
    try:
        print(label, two(b=b, a=a))
    except OverflowError as e:
        print(label, "OverflowError", e)

def main():
    attempt("a=7 default b", 7)
    attempt("a=128", 128)
    attempt("a=-129", -129)
    attempt_kw("kw", 1, 2)
    attempt_kw("kw a", 200, 2)
    attempt_kw("kw b", 1, -1)
    attempt_kw("kw b max", 1, 9223372036854775807)
    # both arguments bad: the first in parameter order is reported
    attempt_kw("both", 128, -1)
    k = 0
    while k < 3:
        attempt("loop", 125 + k * 2)
        k += 1

main()
'''

LENGTHS = STUBS + '''
def run(label: str, n: int) -> None:
    data = bytes(n)
    try:
        print(label, n, sum_bytes(data))
    except OverflowError as e:
        print(label, n, "OverflowError", e)
    try:
        print(label, n, sum_ubytes(data))
    except OverflowError as e:
        print(label, n, "OverflowError", e)
    try:
        print(label, n, sum_shorts(data))
    except OverflowError as e:
        print(label, n, "OverflowError", e)
    try:
        print(label, n, sum_ushorts(data))
    except OverflowError as e:
        print(label, n, "OverflowError", e)

def main():
    run("len", 0)
    run("len", 127)
    run("len", 128)
    run("len", 255)
    run("len", 256)
    run("len", 32767)
    run("len", 32768)
    run("len", 65535)
    run("len", 65536)

main()
'''

UNCAUGHT = STUBS + '''
def main():
    print("before")
    n = 0
    n = n - 1
    print(f_c_size_t(n))
    print("after")

main()
'''

ERRNO_KINDS = STUBS + '''
def main():
    n = 0
    n = n - 1
    try:
        print(f_c_size_t(n))
    except ValueError as e:
        print("ValueError", e)
    except OverflowError as e:
        print("OverflowError", e)
    try:
        print(f_c_int8(n * 200))
    except OverflowError as e:
        print("OverflowError", e)

main()
'''

CHECKED_AFTER = STUBS + '''
def main():
    print(f_c_size_t(0), f_c_size_t(9223372036854775807), f_c_ulong(1), f_c_uint64(2))
    print(f_c_int(-2147483648), f_c_int(2147483647), f_c_uint(4294967295))

main()
'''


def compile_cli(directory, source, mode, name):
    out = Path(directory) / name
    if out.exists():
        out.unlink()
    env = dict(os.environ, PYTHONPATH=str(ROOT), AIL_NO_CACHE="1")
    env.update(dict(MODES)[mode])
    done = subprocess.run([sys.executable, "-B", CLI, "compile", source, "-o", str(out)], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)
    return done, out


def run_cpython(directory, source):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-B", source], cwd=directory, capture_output=True, text=True, timeout=300, env=env)


def _exact_int(test):
    """The test is about exact (arbitrary precision) ints: it runs in the opt-in mode (intmode.py, `--exact-int`)."""
    import functools
    import os

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        saved = os.environ.get('AIL_EXACT_INT')
        os.environ['AIL_EXACT_INT'] = '1'
        try:
            return test(*args, **kwargs)
        finally:
            if saved is None:
                os.environ.pop('AIL_EXACT_INT', None)
            else:
                os.environ['AIL_EXACT_INT'] = saved
    return wrapper


@unittest.skipUnless(CC, "installed C compiler required")
class IntArgumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-ffi-f3a-")
        cls.dir = Path(cls.temp.name)
        (cls.dir / "f3.h").write_text(F3_H, encoding="utf8")
        (cls.dir / "f3.c").write_text(F3_C, encoding="utf8")
        done = subprocess.run([CC, "-shared", "-fPIC", "-O1", "-o", str(cls.dir / "libf3.so"), str(cls.dir / "f3.c")],
                              capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError(done.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf8")
        return name

    def same_as_cpython(self, name, text, expect_in=(), exit_code=0):
        source = self.write(name + ".py", text)
        cpython = run_cpython(self.dir, source)
        self.assertEqual(cpython.returncode, exit_code, cpython.stderr[-600:])
        for needle in expect_in:
            self.assertIn(needle, cpython.stdout)
        for mode, _ in MODES:
            with self.subTest(mode=mode):
                done, exe = compile_cli(self.dir, source, mode, "%s_%s" % (name, mode))
                self.assertEqual(done.returncode, 0, done.stderr[-1500:] + done.stdout[-500:])
                run = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=120)
                self.assertEqual(run.stdout, cpython.stdout)
                self.assertEqual(run.returncode, exit_code, run.stderr[-600:])
        return cpython

    def test_every_int_type_at_every_boundary(self):
        out = self.same_as_cpython("matrix", matrix_program(), expect_in=(
            "c_size_t -1 OverflowError f_c_size_t: x does not fit c_size_t\n",
            "c_int8 128 OverflowError f_c_int8: x does not fit c_int8\n",
            "c_byte 127 127\n", "c_uint8 -1 OverflowError f_c_uint8: x does not fit c_uint8\n",
            "c_ubyte 256 OverflowError f_c_ubyte: x does not fit c_uint8\n",     # the shim names the type c_uint8
            "c_byte -129 OverflowError f_c_byte: x does not fit c_int8\n"))
        # raw ctypes would have wrapped these; the shim (the oracle) and the compiled program raise instead
        self.assertNotIn("c_size_t -1 18446744073709551615", out.stdout)

    def test_defaults_keywords_and_the_first_bad_argument(self):
        self.same_as_cpython("args", ARGS, expect_in=("a=7 default b 7005\n", "kw b OverflowError two: b does not fit c_uint64\n",
                                                      "both OverflowError two: a does not fit c_int8\n"))

    def test_length_parameters_of_narrow_types(self):
        self.same_as_cpython("lengths", LENGTHS, expect_in=("len 128 OverflowError length of p does not fit c_int8\n",
                                                            "len 256 OverflowError length of p does not fit c_uint8\n",
                                                            "len 65536 OverflowError length of p does not fit c_uint16\n"))

    def test_uncaught_overflow_is_a_traceback_exit_one(self):
        source = self.write("uncaught.py", UNCAUGHT)
        cpython = run_cpython(self.dir, source)
        self.assertEqual(cpython.returncode, 1)
        self.assertEqual(cpython.stdout, "before\n")
        self.assertIn("OverflowError: f_c_size_t: x does not fit c_size_t", cpython.stderr)
        for mode, _ in MODES:
            with self.subTest(mode=mode):
                done, exe = compile_cli(self.dir, source, mode, "uncaught_" + mode)
                self.assertEqual(done.returncode, 0, done.stderr[-1500:])
                run = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60)
                self.assertEqual((run.stdout, run.returncode), (cpython.stdout, 1))
                self.assertIn("OverflowError", run.stderr)

    def test_overflow_error_is_not_a_value_error(self):
        # the compiled program used to stop with ValueError("C int8 argument out of range"); it is an OverflowError now
        out = self.same_as_cpython("kinds", ERRNO_KINDS, expect_in=("OverflowError f_c_size_t: x does not fit c_size_t\n",
                                                                    "OverflowError f_c_int8: x does not fit c_int8\n"))
        self.assertNotIn("ValueError", out.stdout)

    def test_in_range_values_still_pass(self):
        self.same_as_cpython("inrange", CHECKED_AFTER, expect_in=("0 9223372036854775807 1 2\n", "-2147483648 2147483647 4294967295\n"))

    def refused(self, name, text, *needles):
        source = self.write(name + ".py", text)
        for mode, _ in MODES:
            with self.subTest(mode=mode):
                done, exe = compile_cli(self.dir, source, mode, "%s_%s" % (name, mode))
                self.assertNotEqual(done.returncode, 0)
                self.assertFalse(exe.exists())
                for needle in needles:
                    self.assertIn(needle, done.stderr + done.stdout)

    def same_exact(self, name, text, expect_in=()):
        """A value above int64 is exact in the default and forced-general builds; the legacy int64 emitter (the "typed"
        mode) stops loudly instead: `integer overflow` on stderr, exit 1, stdout a prefix of CPython's, never a wrong number."""
        source = self.write(name + ".py", text)
        cpython = run_cpython(self.dir, source)
        self.assertEqual(cpython.returncode, 0, cpython.stderr[-600:])
        for needle in expect_in:
            self.assertIn(needle, cpython.stdout)
        for mode, _ in MODES:
            with self.subTest(mode=mode):
                done, exe = compile_cli(self.dir, source, mode, "%s_%s" % (name, mode))
                self.assertEqual(done.returncode, 0, done.stderr[-1500:] + done.stdout[-500:])
                run = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=120)
                if mode == "typed":
                    self.assertTrue(cpython.stdout.startswith(run.stdout))
                    self.assertEqual(run.returncode, 1, run.stderr[-600:])
                    self.assertIn("integer overflow", run.stderr)
                else:
                    self.assertEqual((run.stdout, run.returncode), (cpython.stdout, 0), run.stderr[-600:])
        return cpython

    @_exact_int

    def test_a_u64_constant_above_int64_is_exact_since_f3b(self):
        # F3a refused this at compile time (the program held int64 only); F3b passes it exactly, as CPython does
        self.same_exact("big_u64", STUBS + "\ndef main():\n    print(f_c_size_t(2**63))\n\nmain()\n",
                                   expect_in=("9223372036854775808\n",))

    @_exact_int

    def test_every_spelling_of_a_wide_u64_constant_is_exact(self):
        for index, spelling in enumerate(("0xFFFFFFFFFFFFFFFF", "(1 << 64) - 1", "18446744073709551615", "1 << 63", "2**64 - 2**63")):
            with self.subTest(spelling=spelling):
                self.same_exact("spell%d" % index, STUBS + "\ndef main():\n    print(f_c_ulong(%s))\n\nmain()\n" % spelling)

    def test_other_constants_beyond_int64_are_refused(self):
        self.refused("big_other", STUBS + "\ndef main():\n    print(f_c_int(x=2**64))\n\nmain()\n",
                     "big_other.py:", "f_c_int: argument x is the constant 18446744073709551616",
                     "OverflowError: x does not fit c_int", "write instead: a value inside the range of c_int")
        self.refused("big_neg", STUBS + "\ndef main():\n    print(f_c_int64(-2**63 - 1))\n\nmain()\n",
                     "constant -9223372036854775809", "write instead:")

    def test_constants_inside_int64_are_not_refused(self):
        # a narrow stub given 2**40 or a u64 stub given -1 is a run-time OverflowError, like CPython's
        self.same_as_cpython("const_ok", STUBS + '''
def main():
    try:
        print(f_c_uint32(2**40))
    except OverflowError as e:
        print(e)
    try:
        print(f_c_size_t(-1))
    except OverflowError as e:
        print(e)
    print(f_c_size_t(2**62), f_c_int64(-2**63), f_c_size_t(2**63 - 1), f_c_ulong(~(-1 << 62)))

main()
''', expect_in=("f_c_uint32: x does not fit c_uint32\n", "f_c_size_t: x does not fit c_size_t\n", "4611686018427387904 -9223372036854775808 9223372036854775807 4611686018427387903\n"))

    def test_bool_and_float_arguments_to_an_int_parameter_are_refused(self):
        self.refused("boolarg", STUBS + "\ndef main():\n    flag = 3 > 2\n    print(f_c_int(flag))\n\nmain()\n",
                     "declared int, but", "write instead:")
        self.refused("floatarg", STUBS + "\ndef main():\n    x = 7 / 2\n    print(f_c_int(x))\n\nmain()\n",
                     "annotated int", "write instead:")


if __name__ == "__main__":
    unittest.main()
