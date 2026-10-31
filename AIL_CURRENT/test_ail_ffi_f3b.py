"""F3b: exact unsigned 64-bit results and arguments of an @extern stub, and `check="allones"`.

Oracle: CPython 3.12 running the same file through the ctypes shim (`ail_ffi.py`). Each program below runs under CPython and
as the compiled executable; stdout and exit code must be equal.

* Results: a `c_uint64` / `c_ulong` / `c_ulonglong` / `c_size_t` result above 2**63 - 1 is the exact int (it used to come back
  as the negative int with the same bits).
* Arguments: the shim takes `0 .. 2**64 - 1` for those types and raises `OverflowError("<stub>: <param> does not fit <type>")`
  for anything else, so does the compiled program (a constant in `2**63 .. 2**64-1` is rebuilt from C bits; a computed one is
  an exact tagged int).
* `check="allones"` fires on the unsigned (T)-1 (for `size_t`, 18446744073709551615); `check="minus1"` and `"negative"` on an
  unsigned result never fire, so they are refused at compile time with `write instead: check="allones"`.

Builds: the default one (tagged ints, exact), `AIL_UNIFIED_FORCE=1` (same path for a program with stubs), `AIL_BIGINT=off` (the
switch of the general path; the stub path has no such switch, the value stays exact) and the legacy int64 emitter
(`AIL_NO_GENERAL=1 AIL_IR=0`), where a value above int64 is the loud stop of BIGINT.md A1: `integer overflow` on stderr,
stdout flushed, exit 1, no `except` runs, never a negative number.
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

EXACT = (("default", {}), ("general", {"AIL_UNIFIED_FORCE": "1"}), ("bigint-off", {"AIL_BIGINT": "off"}))
LEGACY = ("legacy", {"AIL_NO_GENERAL": "1", "AIL_IR": "0"})

# annotation -> (C type, bits)
UNSIGNED = {
    "c_uint8": ("uint8_t", 8), "c_ubyte": ("uint8_t", 8), "c_uint16": ("uint16_t", 16), "c_ushort": ("unsigned short", 16),
    "c_uint32": ("uint32_t", 32), "c_uint": ("unsigned int", 32), "c_uint64": ("uint64_t", 64), "c_ulong": ("unsigned long", 64),
    "c_ulonglong": ("unsigned long long", 64), "c_size_t": ("size_t", 64),
}
WIDE = [name for name, spec in UNSIGNED.items() if spec[1] == 64]

H = "#include <stdint.h>\n#include <stddef.h>\n#include <errno.h>\n" + "".join(
    "%s echo_%s(%s x);\n%s top_%s(void);\n" % (spec[0], name, spec[0], spec[0], name) for name, spec in UNSIGNED.items()) + (
    "uint64_t maxu(void);\nuint64_t topu(void);\nsize_t all_ones(void);\nsize_t all_ones_errno(void);\n"
    "uint64_t fnv1a(const unsigned char *p, size_t n, uint64_t seed);\nuint64_t add_u64(uint64_t a, uint64_t b);\n"
    "uint32_t all_ones32(void);\nuint8_t all_ones8(void);\nuint64_t just(uint64_t x);\n"
    "int64_t echo_i64(int64_t x);\nlong echo_long(long x);\n")
C = '#include "f3b.h"\n' + "".join(
    "%s echo_%s(%s x) { return x; }\n%s top_%s(void) { return (%s)0x8000000000000001ull; }\n"
    % (spec[0], name, spec[0], spec[0], name, spec[0]) for name, spec in UNSIGNED.items()) + r"""
uint64_t maxu(void) { return UINT64_MAX; }
uint64_t topu(void) { return (uint64_t)1 << 63; }
size_t all_ones(void) { return (size_t)-1; }
size_t all_ones_errno(void) { errno = ENOENT; return (size_t)-1; }
uint32_t all_ones32(void) { return UINT32_MAX; }
uint8_t all_ones8(void) { return UINT8_MAX; }
uint64_t just(uint64_t x) { return x; }
int64_t echo_i64(int64_t x) { return x; }
long echo_long(long x) { return x; }
uint64_t add_u64(uint64_t a, uint64_t b) { return a + b; }
uint64_t fnv1a(const unsigned char *p, size_t n, uint64_t seed) {
    uint64_t h = seed;
    for (size_t i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ull; }
    return h;
}
"""

STUBS = "from ail_ffi import *\n\n" + "".join(
    '@extern(lib="./libf3b.so", header="f3b.h")\ndef echo_%(n)s(x: %(n)s) -> %(n)s: ...\n'
    '@extern(lib="./libf3b.so", header="f3b.h")\ndef top_%(n)s() -> %(n)s: ...\n' % {"n": name} for name in UNSIGNED) + '''
@extern(lib="./libf3b.so", header="f3b.h")
def echo_i64(x: c_int64) -> c_int64: ...
@extern(lib="./libf3b.so", header="f3b.h")
def echo_long(x: c_long) -> c_long: ...
@extern(lib="./libf3b.so", header="f3b.h")
def maxu() -> c_uint64: ...
@extern(lib="./libf3b.so", header="f3b.h")
def topu() -> c_uint64: ...
@extern(lib="./libf3b.so", header="f3b.h")
def just(x: c_uint64) -> c_uint64: ...
@extern(lib="./libf3b.so", header="f3b.h")
def add_u64(a: c_uint64, b: c_uint64) -> c_uint64: ...
@extern(lib="./libf3b.so", header="f3b.h")
def fnv1a(p: bytes, n: length("p", c_size_t), seed: c_uint64) -> c_uint64: ...
@extern(lib="./libf3b.so", header="f3b.h", check="allones")
def all_ones() -> c_size_t: ...
@extern(lib="./libf3b.so", header="f3b.h", symbol="all_ones", check="allones", exc=ValueError)
def all_ones_exc() -> c_size_t: ...
@extern(lib="./libf3b.so", header="f3b.h", check="allones")
def all_ones32() -> c_uint32: ...
@extern(lib="./libf3b.so", header="f3b.h", check="allones")
def all_ones8() -> c_uint8: ...
@extern(lib="./libf3b.so", header="f3b.h", symbol="just", check="nonzero")
def just_nonzero(x: c_uint64) -> c_uint64: ...
@extern(lib="./libf3b.so", header="f3b.h", symbol="just", check="null")
def just_null(x: c_uint64) -> c_uint64: ...
@extern(lib="./libf3b.so", header="f3b.h", symbol="echo_c_size_t", check="allones")
def echo_checked(x: c_size_t) -> c_size_t: ...
@extern(lib="./libf3b.so", header="f3b.h", symbol="echo_c_uint8", check="allones")
def echo_checked8(x: c_uint8) -> c_uint8: ...
'''

# (label, expression); `top` is 2**63 and `maxv` is 2**64 - 1, both read from C
VALUES = (("0", "0"), ("1", "1"), ("255", "255"), ("256", "256"), ("65535", "65535"), ("65536", "65536"),
          ("2**32-1", "4294967295"), ("2**32", "4294967296"), ("2**63-1", "9223372036854775807"), ("2**63", "top"),
          ("2**63+1", "top + 1"), ("2**64-2", "maxv - 1"), ("2**64-1", "maxv"), ("2**64", "maxv + 1"), ("2**64+5", "maxv + 6"),
          ("-1", "0 - 1"), ("-2**63", "0 - top"), ("-2**64", "0 - maxv - 1"), ("-2**63-1", "0 - top - 1"))


def echo_program(names):
    out = [STUBS, "\ndef main():\n    top = topu()\n    maxv = maxu()\n"]
    for name in names:
        for label, expr in VALUES:
            out.append('''    try:
        v = %(expr)s
        r = echo_%(n)s(v)
        print("%(n)s", "%(label)s", r, hex(r), r %% 1000)
    except OverflowError as e:
        print("%(n)s", "%(label)s", "OverflowError", e)
''' % {"n": name, "label": label, "expr": expr})
    out.append("\nmain()\n")
    return "".join(out)


TOP_BIT = STUBS + '''
def main():
    print(top_c_uint64(), top_c_ulong(), top_c_ulonglong(), top_c_size_t())
    print(top_c_uint32(), top_c_uint(), top_c_uint16(), top_c_ushort(), top_c_uint8(), top_c_ubyte())
    t = top_c_size_t()
    print(t, t + 1, t - 1, t * 2 - 1, t // 7, t % 1000003, hex(t), -t, t == topu(), t > 5, t < maxu(), t != 0)
    m = maxu()
    print(m, m - t, m // 10, m % 10, m == t * 2 - 1, str(m), len(str(m)), m > t, m >= m, m <= 0)
    s = 0
    k = 0
    while k < 5:
        s = s + top_c_uint64()
        k += 1
    print(s, s - 4 * t)
    print(add_u64(t, t - 1), add_u64(m, 1), add_u64(1, m), add_u64(m, m))

main()
'''

CONSTANTS = STUBS + '''
def main():
    print(just(18446744073709551615), just(0x8000000000000000), just(9223372036854775808), just(x=9223372036854775809))
    print(just(2**63), just(2**64 - 1), just((1 << 64) - 1), just(2**63 + 2**62), just(9223372036854775807))
    print(echo_c_size_t(18446744073709551614), echo_c_ulong(0xFFFFFFFFFFFFFFFF) % 10, echo_c_ulonglong(2**63) // 2)
    print(add_u64(18446744073709551615, 0), add_u64(b=1, a=18446744073709551614))
    print(fnv1a(b"hello", 14695981039346656037), fnv1a(b"", 0xCBF29CE484222325), hex(fnv1a(b"abc", 2**63 + 5)))
    h = fnv1a(b"hello", 14695981039346656037)
    print(h, hex(h), h % 1000, h // 3, h >> 60, h & 255)
    k = 0
    while k < 4:
        h = fnv1a(b"x", h)
        print(k, h)
        k += 1
    try:
        print(just(-1))
    except OverflowError as e:
        print("OverflowError", e)

main()
'''

CHECKS = STUBS + '''
def main():
    try:
        print(all_ones())
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        print(all_ones_exc())
    except ValueError as e:
        print("ValueError", e)
    try:
        print(all_ones32())
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        print(all_ones8())
    except RuntimeError as e:
        print("RuntimeError", e)
    top = topu()
    maxv = maxu()
    # hit and miss: only (size_t)-1 fires, 2**63 and 2**64 - 2 do not, and -1 as an argument is an OverflowError first
    if True:
        print("misses", echo_checked(0), echo_checked(9223372036854775807), echo_checked(top), echo_checked(maxv - 1))
    try:
        print(echo_checked(maxv))
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        print(echo_checked(0 - 1))
    except OverflowError as e:
        print("OverflowError", e)
    except RuntimeError as e:
        print("RuntimeError", e)
    print(echo_checked8(254), echo_checked8(0), echo_checked8(128))
    try:
        print(echo_checked8(255))
    except RuntimeError as e:
        print("RuntimeError", e)
    # the failure text shows the unsigned value, also above 2**63 - 1
    try:
        print(just_nonzero(0), just_nonzero(top))
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        print(just_nonzero(maxv))
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        print(just_null(top))
        print(just_null(0))
    except RuntimeError as e:
        print("RuntimeError", e)

main()
'''

UNCAUGHT = STUBS + '''
def main():
    print("before")
    print(all_ones())
    print("after")

main()
'''


def compile_cli(directory, source, env_extra, name):
    out = Path(directory) / name
    if out.exists():
        out.unlink()
    env = dict(os.environ, PYTHONPATH=str(ROOT), AIL_NO_CACHE="1")
    env.update(env_extra)
    done = subprocess.run([sys.executable, "-B", CLI, "compile", source, "-o", str(out)], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)
    return done, out


def run_cpython(directory, source):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-B", source], cwd=directory, capture_output=True, text=True, timeout=300, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class ExactUnsignedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-ffi-f3b-")
        cls.dir = Path(cls.temp.name)
        (cls.dir / "f3b.h").write_text(H, encoding="utf8")
        (cls.dir / "f3b.c").write_text(C, encoding="utf8")
        done = subprocess.run([CC, "-shared", "-fPIC", "-O1", "-o", str(cls.dir / "libf3b.so"), str(cls.dir / "f3b.c")],
                              capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError(done.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf8")
        return name

    def same_as_cpython(self, name, text, expect_in=(), expect_out=(), exit_code=0, builds=EXACT):
        source = self.write(name + ".py", text)
        cpython = run_cpython(self.dir, source)
        self.assertEqual(cpython.returncode, exit_code, cpython.stderr[-800:])
        for needle in expect_in:
            self.assertIn(needle, cpython.stdout)
        for needle in expect_out:
            self.assertNotIn(needle, cpython.stdout)
        for mode, extra in builds:
            with self.subTest(mode=mode):
                done, exe = compile_cli(self.dir, source, extra, "%s_%s" % (name, mode))
                self.assertEqual(done.returncode, 0, done.stderr[-1500:] + done.stdout[-500:])
                run = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=120)
                self.assertEqual(run.stdout, cpython.stdout)
                self.assertEqual(run.returncode, exit_code, run.stderr[-600:])
        return cpython

    def loud_stop(self, name, text):
        """The legacy int64 emitter: stdout is a prefix of CPython's, then `integer overflow`, exit 1, nothing negative."""
        source = self.write(name + ".py", text)
        cpython = run_cpython(self.dir, source)
        self.assertEqual(cpython.returncode, 0, cpython.stderr[-800:])
        done, exe = compile_cli(self.dir, source, LEGACY[1], "%s_legacy" % name)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        run = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=120)
        self.assertTrue(cpython.stdout.startswith(run.stdout), (run.stdout[-300:], cpython.stdout[-300:]))
        if run.returncode == 0:
            self.assertEqual(run.stdout, cpython.stdout)
        else:
            self.assertEqual(run.returncode, 1)
            self.assertIn("integer overflow", run.stderr)
        return run

    # ---------------------------------------------------------------- results and arguments

    def test_every_wide_unsigned_type_at_every_boundary(self):
        out = self.same_as_cpython("wide", echo_program(WIDE), expect_in=(
            "c_size_t 2**64-1 18446744073709551615 0xffffffffffffffff 615\n",
            "c_uint64 2**63 9223372036854775808 0x8000000000000000 808\n",
            "c_ulong 2**63-1 9223372036854775807 0x7fffffffffffffff 807\n",
            "c_ulonglong 2**64 OverflowError echo_c_ulonglong: x does not fit c_ulonglong\n",
            "c_size_t -1 OverflowError echo_c_size_t: x does not fit c_size_t\n",
            "c_uint64 -2**63-1 OverflowError echo_c_uint64: x does not fit c_uint64\n"),
            expect_out=("-9223372036854775808 0x", "-1 0x"))
        self.assertEqual(out.stdout.count("OverflowError"), 4 * 6)

    def test_every_narrow_unsigned_type_at_every_boundary(self):
        self.same_as_cpython("narrow", echo_program([n for n in UNSIGNED if n not in WIDE]), expect_in=(
            "c_uint8 255 255 0xff 255\n", "c_ubyte 256 OverflowError echo_c_ubyte: x does not fit c_uint8\n",
            "c_ushort 65535 65535 0xffff 535\n", "c_uint 2**32-1 4294967295 0xffffffff 295\n",
            "c_uint 2**32 OverflowError echo_c_uint: x does not fit c_uint\n",
            "c_uint32 2**64-1 OverflowError echo_c_uint32: x does not fit c_uint32\n"))

    def test_results_with_the_top_bit_set(self):
        self.same_as_cpython("topbit", TOP_BIT, expect_in=(
            "9223372036854775809 9223372036854775809 9223372036854775809 9223372036854775809\n",
            "1 1 1 1 1 1\n"))

    def test_constants_in_the_upper_half_are_exact(self):
        self.same_as_cpython("constants", CONSTANTS, expect_in=(
            "18446744073709551615 9223372036854775808 9223372036854775808 9223372036854775809\n",
            "OverflowError just: x does not fit c_uint64\n"))

    def test_a_value_above_int64_is_a_loud_stop_on_the_legacy_emitter_never_a_negative_number(self):
        run = self.loud_stop("legacy_top", STUBS + "\ndef main():\n    print(1)\n    print(topu())\n    print(2)\n\nmain()\n")
        self.assertEqual((run.returncode, run.stdout), (1, "1\n"))
        self.assertTrue(run.stderr.strip().startswith("OverflowError: integer overflow in "), run.stderr)
        run = self.loud_stop("legacy_try", STUBS + '''
def main():
    print(1)
    try:
        print(maxu())
    except ValueError:
        print("caught")
    print(2)

main()
''')
        self.assertEqual((run.returncode, run.stdout), (1, "1\n"))             # no `except` runs
        self.loud_stop("legacy_small", STUBS + "\ndef main():\n    print(echo_c_size_t(5), echo_c_uint64(9223372036854775807), just(0))\n\nmain()\n")
        # a result at 2**63 - 1 still passes
        self.loud_stop("legacy_edge", STUBS + "\ndef main():\n    print(echo_c_ulong(9223372036854775807))\n\nmain()\n")

    def test_signed_64_bit_parameters_are_checked_against_int64(self):
        # a tagged int can be beyond int64 now; CPython raises the shim's OverflowError, the compiled program must too
        out = [STUBS, "\ndef main():\n    top = topu()\n    maxv = maxu()\n"]
        for name, stub in (("c_int64", "echo_i64"), ("c_long", "echo_long")):
            for label, expr in (("2**63-1", "9223372036854775807"), ("2**63", "top"), ("2**64-1", "maxv"), ("-2**63", "0 - top"),
                                ("-2**63-1", "0 - top - 1"), ("-2**64", "0 - maxv - 1"), ("0", "0")):
                out.append('''    try:
        v = %(expr)s
        print("%(n)s", "%(label)s", %(stub)s(v))
    except OverflowError as e:
        print("%(n)s", "%(label)s", "OverflowError", e)
''' % {"n": name, "label": label, "expr": expr, "stub": stub})
        out.append("\nmain()\n")
        self.same_as_cpython("signed64", "".join(out), expect_in=(
            "c_int64 2**63-1 9223372036854775807\n", "c_int64 2**63 OverflowError echo_i64: x does not fit c_int64\n",
            "c_long -2**63 -9223372036854775808\n", "c_long -2**63-1 OverflowError echo_long: x does not fit c_long\n"))

    def test_stubs_in_an_imported_module(self):
        self.write("u64mod.py", STUBS + '''
def mixed(x: int) -> int:
    y = just(x)
    return y % 1000 + y // 4
''')
        main = ("import u64mod\n\ndef main():\n    t = u64mod.topu()\n    print(u64mod.just(t), u64mod.maxu(), u64mod.mixed(t + 7))\n"
                "    try:\n        print(u64mod.just(u64mod.maxu() + 1))\n    except OverflowError as e:\n        print('OverflowError', e)\n\nmain()\n")
        self.same_as_cpython("modmain", main, expect_in=("9223372036854775808 18446744073709551615 2305843009213694768\n",
                                                          "OverflowError just: x does not fit c_uint64\n"))

    # ---------------------------------------------------------------- check="allones"

    def test_allones_hit_and_miss(self):
        self.same_as_cpython("allones", CHECKS, expect_in=(
            "RuntimeError all_ones failed with 18446744073709551615\n", "ValueError all_ones_exc failed with 18446744073709551615\n",
            "RuntimeError all_ones32 failed with 4294967295\n",
            "RuntimeError all_ones8 failed with 255\n", "misses 0 9223372036854775807 9223372036854775808 18446744073709551614\n",
            "RuntimeError echo_checked failed with 18446744073709551615\n",
            "OverflowError echo_checked: x does not fit c_size_t\n", "254 0 128\n", "RuntimeError echo_checked8 failed with 255\n",
            "RuntimeError just_nonzero failed with 18446744073709551615\n"))

    def test_allones_with_errno(self):
        # the OSError of an errno stub is raised in a helper of its own, so a u64 value above int64 still reaches the program
        text = STUBS + '''@extern(lib="./libf3b.so", header="f3b.h", check="allones", errno=True, exc=OSError)
def all_ones_errno() -> c_size_t: ...
@extern(lib="./libf3b.so", header="f3b.h", symbol="echo_c_size_t", check="allones", errno=True, exc=ValueError)
def echo_errno(x: c_size_t) -> c_size_t: ...

def main():
    t = topu()
    print(t, echo_errno(5), echo_errno(t))
    try:
        print(all_ones_errno())
    except OSError as e:
        print("OSError", e)
    try:
        print(echo_errno(t + t - 1))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(echo_errno(0 - 1))
    except OverflowError as e:
        print("OverflowError", e)

main()
'''
        self.same_as_cpython("allones_errno", text, expect_in=("9223372036854775808 5 9223372036854775808\n",
                                                              "OSError [Errno 2] No such file or directory\n",
                                                              "ValueError [Errno 0] Success\n",
                                                              "OverflowError echo_errno: x does not fit c_size_t\n"))

    def test_an_uncaught_allones_failure_is_a_traceback_exit_one(self):
        source = self.write("allones_uncaught.py", UNCAUGHT)
        cpython = run_cpython(self.dir, source)
        self.assertEqual((cpython.returncode, cpython.stdout), (1, "before\n"))
        for mode, extra in EXACT:
            with self.subTest(mode=mode):
                done, exe = compile_cli(self.dir, source, extra, "allones_uncaught_" + mode)
                self.assertEqual(done.returncode, 0, done.stderr[-1500:])
                run = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60)
                self.assertEqual((run.stdout, run.returncode), ("before\n", 1))
                self.assertIn("RuntimeError", run.stderr)
                self.assertIn("all_ones failed with 18446744073709551615", run.stderr)

    def refused(self, name, text, *needles):
        source = self.write(name + ".py", text)
        for mode, extra in EXACT + (LEGACY,):
            with self.subTest(mode=mode):
                done, exe = compile_cli(self.dir, source, extra, "%s_%s" % (name, mode))
                self.assertNotEqual(done.returncode, 0)
                self.assertFalse(exe.exists())
                for needle in needles:
                    self.assertIn(needle, done.stderr + done.stdout)

    def test_minus1_and_negative_on_an_unsigned_result_are_refused(self):
        for index, (check, ann, ctype) in enumerate((("minus1", "c_size_t", "size_t"), ("minus1", "c_uint64", "uint64_t"),
                                                     ("negative", "c_ulong", "unsigned long"), ("minus1", "c_uint8", "uint8_t"),
                                                     ("negative", "c_uint32", "uint32_t"))):
            with self.subTest(check=check, result=ann):
                text = 'from ail_ffi import *\n\n@extern(lib="./libf3b.so", header="f3b.h", symbol="echo_%s", check="%s")\n' \
                       'def bad(x: %s) -> %s: ...\n\nprint(bad(1))\n' % (ann, check, ann, ann)
                self.refused("refuse%d" % index, text, "refuse%d.py:3:" % index,
                             'check="%s" on a %s result never fires: the result is unsigned' % (check, ann),
                             'write instead: check="allones" (the C value (%s)-1' % ctype)

    def test_allones_on_a_signed_or_non_integer_result_is_refused(self):
        text = 'from ail_ffi import *\n\n@extern(lib="./libf3b.so", header="f3b.h", symbol="echo_c_size_t", check="allones")\n' \
               'def bad(x: c_size_t) -> c_int64: ...\n\nprint(bad(1))\n'
        self.refused("allones_signed", text, "allones_signed.py:3:", 'check="allones" needs an unsigned integer result',
                     'write instead: check="minus1"')
        text = text.replace("c_int64", "c_double")
        self.refused("allones_float", text, "allones_float.py:4:", "check= needs an integer or handle result")

    def test_the_shim_refuses_allones_on_a_signed_result(self):
        source = self.write("shim_signed.py", 'from ail_ffi import *\n\n@extern(lib="./libf3b.so", header="f3b.h", check="allones")\n'
                            'def echo_c_int64(x: c_int64) -> c_int64: ...\n')
        cpython = run_cpython(self.dir, source)
        self.assertEqual(cpython.returncode, 1)
        self.assertIn('check="allones" needs an unsigned integer result', cpython.stderr)

    # ---------------------------------------------------------------- the gate of PR #230 still holds

    def test_a_wide_literal_that_is_not_a_stub_argument_is_still_refused(self):
        self.refused("wide_literal", STUBS + "\ndef main():\n    x = 2**64\n    print(x)\n\nmain()\n", "can need an int beyond int64")

    def test_constants_that_are_out_of_range_for_their_parameter_are_refused_by_name(self):
        self.refused("const_range", STUBS + "\ndef main():\n    print(just(2**64))\n\nmain()\n",
                     "const_range.py:", "just: argument x is the constant 18446744073709551616",
                     "OverflowError: x does not fit c_uint64", "write instead: a value inside the range of c_uint64")
        self.refused("const_narrow", STUBS + "\ndef main():\n    print(echo_c_uint32(2**63))\n\nmain()\n",
                     "const_narrow.py:", "echo_c_uint32: argument x is the constant 9223372036854775808",
                     "OverflowError: x does not fit c_uint32")

    # ---------------------------------------------------------------- a program without a u64 stub is byte for byte what it was

    def test_programs_without_a_wide_stub_do_not_change(self):
        text = 'from ail_ffi import *\n\n@extern(lib="./libf3b.so", header="f3b.h")\ndef echo_c_uint32(x: c_uint32) -> c_uint32: ...\n' \
               '\ndef main():\n    print(echo_c_uint32(7))\n\nmain()\n'
        source = self.write("plain32.py", text)
        done, exe = compile_cli(self.dir, source, {}, "plain32")
        self.assertEqual(done.returncode, 0, done.stderr)
        text = Path(exe).read_bytes()
        self.assertNotIn(b"4611686018427387904", text)
        run = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60)
        self.assertEqual(run.stdout, "7\n")


if __name__ == "__main__":
    unittest.main()
