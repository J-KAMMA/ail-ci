"""G4: the C FFI. `@extern` stubs (ail_ffi.py) run under CPython through ctypes and compile to native code.

A tiny C library is built in a temporary directory (a shared library for `lib="./libtiny.so"`, and the same
source for `sources=["tiny.c"]`). Each program below is run twice and the outputs are compared:

* by `python3 prog.py` with the ctypes implementation of `ail_ffi` (the CPython oracle), and
* by the executable `ail_chatgpt.py compile prog.py` builds (typed path only: AIL_NO_GENERAL=1).

Programs print error messages with `{MSG}`, which is `str(e)` for CPython and `e.message` for the compiler
(the typed path has no printable exception). Covered: every integer width at its edges, double, float,
bool, UTF-8 strings (empty, non-ASCII, NULL results), borrowed bytes (empty, NUL bytes, views), writable
bytearrays (one and two in a call, void results, length unchanged), out-parameters (`ptr(c_int)`), errno to
OSError, `check=` with `exc=`, opaque handles, stubs in an imported module, `sources=`, real libc and zlib.
Also: the prototype check (a wrong declaration is a compile error), `check --ffi`, `--no-ffi`, the named
refusals, and that a program without `ail_ffi` is not touched.
"""
import json
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

TINY_H = r"""
#include <stddef.h>
#include <stdint.h>
int tiny_add(int a, int b);
int8_t tiny_neg8(int8_t x);
uint16_t tiny_inc16(uint16_t x);
uint32_t tiny_mul32(uint32_t a, uint32_t b);
int64_t tiny_mul64(int64_t a, int64_t b);
long tiny_neg(long x);
unsigned long tiny_ul(unsigned long x);
uint64_t tiny_big(void);
double tiny_hyp(double a, double b);
float tiny_halve(float x);
_Bool tiny_flip(_Bool x);
_Bool tiny_odd(int x);
size_t tiny_len(const char *s);
const char *tiny_greet(const char *name);
const char *tiny_name(int which);
size_t tiny_count(const unsigned char *p, size_t n, unsigned char b);
int tiny_fill(unsigned char *buf, size_t n, unsigned char v);
void tiny_reverse(unsigned char *buf, size_t n);
void tiny_swap(unsigned char *a, unsigned char *b, size_t n);
int tiny_divmod(int a, int b, int *q, int *r);
int32_t tiny_sum32(const int32_t *xs, size_t n, int64_t *total);
int tiny_open(const char *path);
void *tiny_new(int start);
int tiny_next(void *h);
void tiny_free(void *h);
void *tiny_find(int k);
int tiny_fail(int k);
"""

TINY_C = r"""
#include "tiny.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int tiny_add(int a, int b) { return a + b; }
int8_t tiny_neg8(int8_t x) { return (int8_t)-x; }
uint16_t tiny_inc16(uint16_t x) { return (uint16_t)(x + 1u); }
uint32_t tiny_mul32(uint32_t a, uint32_t b) { return a * b; }
int64_t tiny_mul64(int64_t a, int64_t b) { return (int64_t)((uint64_t)a * (uint64_t)b); }
long tiny_neg(long x) { return -x; }
unsigned long tiny_ul(unsigned long x) { return x + 1ul; }
uint64_t tiny_big(void) { return 0x8000000000000001ull; }
double tiny_hyp(double a, double b) { return a * a + b * b; }
float tiny_halve(float x) { return x / 2; }
_Bool tiny_flip(_Bool x) { return !x; }
_Bool tiny_odd(int x) { return x & 1; }
size_t tiny_len(const char *s) { return strlen(s); }
const char *tiny_greet(const char *name) { static char buf[256]; snprintf(buf, sizeof buf, "hello, %s!", name); return buf; }
const char *tiny_name(int which) { return which ? "name" : NULL; }
size_t tiny_count(const unsigned char *p, size_t n, unsigned char b) { size_t c = 0; for (size_t i = 0; i < n; i++) c += p[i] == b; return c; }
int tiny_fill(unsigned char *buf, size_t n, unsigned char v) { memset(buf, v, n); return (int)n; }
void tiny_reverse(unsigned char *buf, size_t n) { for (size_t i = 0; i < n / 2; i++) { unsigned char t = buf[i]; buf[i] = buf[n - 1 - i]; buf[n - 1 - i] = t; } }
void tiny_swap(unsigned char *a, unsigned char *b, size_t n) { for (size_t i = 0; i < n; i++) { unsigned char t = a[i]; a[i] = b[i]; b[i] = t; } }
int tiny_divmod(int a, int b, int *q, int *r) { if (b == 0) { errno = EDOM; return -1; } *q = a / b; *r = a % b; return 0; }
int32_t tiny_sum32(const int32_t *xs, size_t n, int64_t *total) { int64_t t = 0; for (size_t i = 0; i < n; i++) t += xs[i]; *total = t; return (int32_t)n; }
int tiny_open(const char *path) { FILE *f = fopen(path, "rb"); if (!f) return -1; fclose(f); return 7; }
void *tiny_new(int start) { int *p = malloc(sizeof(int)); *p = start; return p; }
int tiny_next(void *h) { return (*(int *)h)++; }
void tiny_free(void *h) { free(h); }
void *tiny_find(int k) { static int cell = 5; return k >= 0 ? (void *)&cell : NULL; }
int tiny_fail(int k) { errno = 0; return k > 0 ? 0 : -k; }
"""

# stubs shared by the programs (the library sits in the program's directory)
STUBS = r"""
from ail_ffi import *

@extern(lib="./libtiny.so", header="tiny.h")
def tiny_add(a: c_int, b: c_int) -> c_int: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_neg8(x: c_int8) -> c_int8: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_inc16(x: c_uint16) -> c_uint16: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_mul32(a: c_uint32, b: c_uint32) -> c_uint32: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_mul64(a: c_int64, b: c_int64) -> c_int64: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_neg(x: c_long) -> c_long: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_ul(x: c_ulong) -> c_ulong: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_big() -> c_uint64: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_hyp(a: c_double, b: c_double) -> c_double: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_halve(x: c_float) -> c_float: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_flip(x: c_bool) -> c_bool: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_odd(x: c_int) -> c_bool: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_len(s: c_char_p) -> c_size_t: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_greet(name: c_char_p) -> c_char_p: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_name(which: c_int) -> c_char_p: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_count(p: bytes, n: length("p"), b: c_uint8) -> c_size_t: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_fill(buf: bytearray, n: length("buf"), v: c_uint8) -> c_int: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_reverse(buf: bytearray, n: length("buf")) -> None: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_swap(a: bytearray, b: bytearray, n: length("a")) -> None: ...
@extern(lib="./libtiny.so", header="tiny.h", check="negative", errno=True)
def tiny_divmod(a: c_int, b: c_int, q: ptr(c_int), r: ptr(c_int)) -> c_int: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_sum32(xs: cptr(c_int32), n: length("xs"), total: ptr(c_int64)) -> c_int32: ...
@extern(lib="./libtiny.so", header="tiny.h", check="negative", errno=True)
def tiny_open(path: c_char_p) -> c_int: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_new(start: c_int) -> c_void_p: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_next(h: c_void_p) -> c_int: ...
@extern(lib="./libtiny.so", header="tiny.h")
def tiny_free(h: c_void_p) -> None: ...
@extern(lib="./libtiny.so", header="tiny.h", check="null", exc=ValueError)
def tiny_find(k: c_int) -> c_void_p: ...
@extern(lib="./libtiny.so", header="tiny.h", check="nonzero")
def tiny_fail(k: c_int) -> c_int: ...
"""

SCALARS = STUBS + r"""
def main():
    print(tiny_add(2147483000, 600), tiny_add(-2147483647, -1), tiny_add(0, 0))
    print(tiny_neg8(100), tiny_neg8(-127), tiny_neg8(0))
    print(tiny_inc16(65535), tiny_inc16(0), tiny_inc16(255))
    print(tiny_mul32(65536, 65536), tiny_mul32(70000, 3), tiny_mul32(4294967295, 1))
    print(tiny_mul64(1 << 40, 3), tiny_mul64(-3000000000, 3000000000), tiny_mul64(0, 5))
    print(tiny_neg(5), tiny_neg(-9223372036854775807), tiny_ul(41), tiny_ul(4294967295))
    print(tiny_hyp(3.0, 4.0), tiny_hyp(0.1, 0.2), tiny_hyp(-1.5, 2.5))
    print(tiny_halve(3.0), tiny_halve(-0.5), tiny_halve(1.0))
    print(tiny_flip(True), tiny_flip(False), tiny_odd(3), tiny_odd(4), tiny_odd(-1))

main()
"""

STRINGS = STUBS + r"""
def main():
    print(tiny_len(""), tiny_len("abc"), tiny_len("wörld"), tiny_len("日本語"), tiny_len("a" * 1000))
    print(tiny_greet("world"))
    print(tiny_greet("wörld"))
    print(tiny_greet("日本語") + "|")
    print(tiny_greet(""))
    print(len(tiny_greet("x" * 200)))
    print("[" + tiny_name(0) + "]", "[" + tiny_name(1) + "]")

main()
"""

BUFFERS = STUBS + r"""
def main():
    data = b"abcabca\x00\x00z"
    print(tiny_count(data, 97), tiny_count(data, 0), tiny_count(data, 255), tiny_count(b"", 0))
    print(tiny_count(data[2:5], 97), tiny_count(data[8:], 0), tiny_count(b"\x00" * 10000, 0))
    ba = bytearray(5)
    print(tiny_fill(ba, 7), len(ba), ba[0], ba[4])
    empty = bytearray()
    print(tiny_fill(empty, 9), len(empty))
    text = bytearray(b"hello")
    tiny_reverse(text)
    print(text.decode(), len(text))
    a = bytearray(b"1234")
    b = bytearray(b"abcd")
    tiny_swap(a, b)
    print(a.decode(), b.decode(), len(a), len(b))
    big = bytearray(70000)
    for i in range(70000):
        big[i] = i % 251
    tiny_reverse(big)
    print(big[0], big[69999], big[1234], len(big))
    same = bytearray(b"xyz")
    tiny_reverse(same)
    tiny_reverse(same)
    print(same.decode())

main()
"""

OUT_PARAMS = STUBS + r"""
def le32(b: bytearray, at: int) -> int:
    v = b[at] | (b[at + 1] << 8) | (b[at + 2] << 16) | (b[at + 3] << 24)
    if v >= 2147483648:
        v -= 4294967296
    return v

def main():
    q = bytearray(4)
    r = bytearray(4)
    print(tiny_divmod(17, 5, q, r), le32(q, 0), le32(r, 0))
    print(tiny_divmod(-17, 5, q, r), le32(q, 0), le32(r, 0))
    xs = bytearray()
    for v in [1, -2, 300000, 7]:
        u = v + 4294967296 if v < 0 else v
        xs.append(u & 255)
        xs.append((u >> 8) & 255)
        xs.append((u >> 16) & 255)
        xs.append((u >> 24) & 255)
    total = bytearray(8)
    print(tiny_sum32(bytes(xs), total), total[0] | (total[1] << 8) | (total[2] << 16) | (total[3] << 24))
    try:
        tiny_sum32(bytes(xs[0:7]), total)
    except ValueError:
        print("whole number required")
    small = bytearray(3)
    try:
        tiny_divmod(1, 1, small, r)
    except ValueError:
        print("whole number of c_int required")

main()
"""

ERRORS = STUBS + r"""
def main():
    q = bytearray(4)
    r = bytearray(4)
    try:
        tiny_divmod(1, 0, q, r)
    except OSError as e:
        print("divmod", {MSG})
    try:
        tiny_open("/no/such/directory/file")
    except OSError as e:
        print("open", {MSG})
    print(tiny_open("tiny.h"))
    try:
        tiny_find(-1)
    except ValueError as e:
        print("find", {MSG})
    print(tiny_find(3) != 0)
    try:
        tiny_fail(-4)
    except RuntimeError as e:
        print("fail", {MSG})
    print(tiny_fail(1))

main()
"""

HANDLES = STUBS + r"""
def main():
    h = tiny_new(10)
    print(h != 0, tiny_next(h), tiny_next(h), tiny_next(h))
    g = tiny_new(100)
    print(tiny_next(g), tiny_next(h), h != g)
    tiny_free(h)
    tiny_free(g)

main()
"""

MODULE_STUBS = STUBS + r"""
def twice(x: int) -> int:
    return tiny_add(x, x)
"""

MODULE_MAIN = r"""
import tinymod
from tinymod import tiny_hyp

def main():
    print(tinymod.tiny_add(1, 2), tinymod.twice(21), tiny_hyp(3.0, 4.0))
    print(tinymod.tiny_len("héllo"))
    ba = bytearray(b"abc")
    tinymod.tiny_reverse(ba)
    print(ba.decode())

main()
"""

SOURCES = r"""
from ail_ffi import *

@extern(header="tiny.h", sources=["tiny.c"])
def tiny_add(a: c_int, b: c_int) -> c_int: ...
@extern(header="tiny.h", sources=["tiny.c"])
def tiny_greet(name: c_char_p) -> c_char_p: ...
@extern(header="tiny.h", sources=["tiny.c"], check="negative", errno=True)
def tiny_open(path: c_char_p) -> c_int: ...

def main():
    print(tiny_add(40, 2), tiny_greet("src"), tiny_open("tiny.h"))
    try:
        tiny_open("/no/such/file")
    except OSError as e:
        print({MSG})

main()
"""

LIBC = r"""
from ail_ffi import *

@extern(lib="c", header="string.h", symbol="strlen")
def c_strlen(s: c_char_p) -> c_size_t: ...
@extern(lib="c", header="stdlib.h", symbol="abs")
def c_abs(x: c_int) -> c_int: ...
@extern(lib="c", header="stdlib.h", symbol="labs")
def c_labs(x: c_long) -> c_long: ...
@extern(lib="c", header="stdlib.h", symbol="atoi")
def c_atoi(s: c_char_p) -> c_int: ...
@extern(lib="c", header="ctype.h", symbol="toupper")
def c_toupper(c: c_int) -> c_int: ...
@extern(lib="c", header="string.h", symbol="strcmp")
def c_strcmp(a: c_char_p, b: c_char_p) -> c_int: ...
@extern(lib="c", header="string.h", symbol="memcmp")
def c_memcmp(a: c_const_void_p, b: c_const_void_p, n: length("a", c_size_t)) -> c_int: ...
@extern(lib="c", header="string.h", symbol="strerror")
def c_strerror(code: c_int) -> c_mut_char_p: ...
@extern(lib="m", header="math.h", symbol="sqrt")
def c_sqrt(x: c_double) -> c_double: ...
@extern(lib="m", header="math.h", symbol="pow")
def c_pow(x: c_double, y: c_double) -> c_double: ...
@extern(lib="m", header="math.h", symbol="floor")
def c_floor(x: c_double) -> c_double: ...
@extern(lib="z", header="zlib.h", symbol="crc32")
def c_crc32(crc: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...
@extern(lib="z", header="zlib.h", symbol="adler32")
def c_adler32(adler: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...
@extern(lib="z", header="zlib.h", symbol="zlibVersion")
def c_zlib_version() -> c_char_p: ...
@extern(lib="z", header="zlib.h", symbol="compressBound")
def c_bound(n: c_ulong) -> c_ulong: ...

def main():
    print(c_strlen("hello"), c_strlen(""), c_abs(-7), c_abs(7), c_labs(-1234567890123), c_atoi("  -42xyz"))
    print(c_toupper(97), c_toupper(48), c_strcmp("a", "b") < 0, c_strcmp("b", "a") > 0, c_strcmp("x", "x"))
    print(c_memcmp(b"abc", b"abd") < 0, c_memcmp(b"", b""), c_memcmp(b"\x00\x01", b"\x00\x01"))
    print(c_strerror(2), c_strerror(13))
    print(c_sqrt(2.0), c_pow(2.0, 10.0), c_floor(-1.5))
    print(c_crc32(0, b"hello world"), c_crc32(5, b""), c_adler32(1, b"hello world"), c_adler32(9, b""))
    print(c_zlib_version(), c_bound(1000))

main()
"""

NO_FFI = r"""
def add(a: int, b: int) -> int:
    return a + b

def main():
    print(add(1, 2))

main()
"""


def build_tiny(directory):
    directory = Path(directory)
    (directory / "tiny.h").write_text(TINY_H, encoding="utf8")
    (directory / "tiny.c").write_text(TINY_C, encoding="utf8")
    done = subprocess.run([CC, "-shared", "-fPIC", "-O1", "-o", str(directory / "libtiny.so"), str(directory / "tiny.c")],
                          capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(done.stderr)


def compile_cli(directory, source, *flags, ir="0", name="prog.out", check=True):
    out = Path(directory) / name
    if out.exists():
        out.unlink()
    env = dict(os.environ, AIL_IR=ir, AIL_NO_GENERAL="1", PYTHONPATH=str(ROOT))
    done = subprocess.run([sys.executable, "-B", CLI, "compile", source, "-o", str(out), *flags], cwd=directory,
                          capture_output=True, text=True, timeout=600, env=env)
    return done, out


def run_cpython(directory, source):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-B", source], cwd=directory, capture_output=True, text=True,
                          timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class FFITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-ffi-test-")
        cls.dir = Path(cls.temp.name)
        build_tiny(cls.dir)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf8")
        return name

    def both(self, name, text, ir="0"):
        """(CPython output, compiled output) of one program; both must exit 0."""
        cpy = self.write(name + "_cpy.py", text.replace("{MSG}", "str(e)"))
        ail = self.write(name + "_ail.py", text.replace("{MSG}", "e.message"))
        expected = run_cpython(self.dir, cpy)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        built, exe = compile_cli(self.dir, ail, ir=ir, name=name + ".out")
        self.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        return expected.stdout, ran.stdout

    def same(self, name, text, expected=None, ir="0"):
        cpy, ail = self.both(name, text, ir)
        self.assertEqual(cpy, ail)
        if expected is not None:
            self.assertEqual(ail, expected)

    def test_scalars_every_width(self):
        self.same("scalars", SCALARS, (
            "2147483600 -2147483648 0\n"
            "-100 127 0\n"
            "0 1 256\n"
            "0 210000 4294967295\n"
            "3298534883328 -9000000000000000000 0\n"
            "-5 9223372036854775807 42 4294967296\n"
            "25.0 0.05000000000000001 8.5\n"
            "1.5 -0.25 0.5\n"
            "False True True False True\n"))

    def test_scalars_under_the_ir(self):
        cpy, ail = self.both("scalars_ir", SCALARS, ir="1")
        self.assertEqual(cpy, ail)

    def test_strings(self):
        self.same("strings", STRINGS, (
            "0 3 6 9 1000\n"
            "hello, world!\n"
            "hello, wörld!\n"
            "hello, 日本語!|\n"
            "hello, !\n"
            "208\n"
            "[] [name]\n"))

    def test_bytes_and_bytearrays(self):
        self.same("buffers", BUFFERS, (
            "3 2 0 0\n"
            "1 1 10000\n"
            "5 5 7 7\n"
            "0 0\n"
            "olleh 5\n"
            "abcd 1234 4 4\n"
            "{first} 0 {mid} 70000\n".format(first=69999 % 251, mid=(70000 - 1 - 1234) % 251)
            + "xyz\n"))

    def test_out_parameters(self):
        self.same("outs", OUT_PARAMS, (
            "0 3 2\n"
            "0 -3 -2\n"
            "4 300006\n"
            "whole number required\n"
            "whole number of c_int required\n"))

    def test_errors_errno_and_check(self):
        cpy, ail = self.both("errors", ERRORS)
        self.assertEqual(cpy, ail)
        self.assertEqual(ail, (
            "divmod [Errno 33] Numerical argument out of domain\n"
            "open [Errno 2] No such file or directory\n"
            "7\n"
            "find tiny_find failed with 0\n"
            "True\n"
            "fail tiny_fail failed with 4\n"
            "0\n"))

    def test_handles(self):
        self.same("handles", HANDLES, "True 10 11 12\n100 13 True\n")

    def test_uint64_above_int64_is_the_declared_difference(self):
        text = STUBS + "\ndef main():\n    print(tiny_big())\n    print(tiny_ul(9223372036854775807))\n\nmain()\n"
        cpy, ail = self.both("big", text)
        self.assertEqual(cpy, "9223372036854775809\n9223372036854775808\n")
        # the compiled program has 64 bit ints: the same bits, signed
        self.assertEqual(ail, "-9223372036854775807\n-9223372036854775808\n")

    def test_stubs_in_an_imported_module(self):
        self.write("tinymod.py", MODULE_STUBS)
        expected = run_cpython(self.dir, self.write("modmain.py", MODULE_MAIN))
        self.assertEqual(expected.returncode, 0, expected.stderr)
        built, exe = compile_cli(self.dir, "modmain.py", name="modmain.out")
        self.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, cwd=self.dir)
        self.assertEqual(ran.stdout, expected.stdout)
        self.assertEqual(ran.stdout, "3 42 25.0\n6\ncba\n")

    def test_c_source_beside_the_declaration(self):
        cpy, ail = self.both("sources", SOURCES)
        self.assertEqual(cpy, ail)
        self.assertEqual(ail, "42 hello, src! 7\n[Errno 2] No such file or directory\n")

    def test_libc_libm_and_zlib(self):
        self.same("libc", LIBC)
        cpy = run_cpython(self.dir, "libc_cpy.py").stdout
        import zlib
        lines = cpy.splitlines()
        self.assertEqual(lines[0], "5 0 7 7 1234567890123 -42")
        self.assertIn(str(zlib.crc32(b"hello world")), lines[5])
        self.assertIn(zlib.ZLIB_RUNTIME_VERSION, lines[6])

    def test_wrong_prototype_is_a_compile_error(self):
        text = STUBS.replace("def tiny_add(a: c_int, b: c_int) -> c_int", "def tiny_add(a: c_int, b: c_long) -> c_int")
        self.write("wrong.py", text + "\ndef main():\n    print(tiny_add(1, 2))\n\nmain()\n")
        built, _ = compile_cli(self.dir, "wrong.py", name="wrong.out")
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("does not match its C prototype", built.stderr)
        self.assertIn("tiny_add", built.stderr)

    def test_wrong_return_type_is_a_compile_error(self):
        text = STUBS.replace("def tiny_hyp(a: c_double, b: c_double) -> c_double", "def tiny_hyp(a: c_double, b: c_double) -> c_int")
        self.write("wrong2.py", text + "\ndef main():\n    print(tiny_hyp(1.0, 2.0))\n\nmain()\n")
        built, _ = compile_cli(self.dir, "wrong2.py", name="wrong2.out")
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("does not match its C prototype", built.stderr)

    def test_check_lists_declarations(self):
        self.write("listing.py", STUBS + "\ndef main():\n    print(tiny_add(1, 2))\n\nmain()\n")
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        done = subprocess.run([sys.executable, "-B", CLI, "check", "listing.py", "--ffi"], cwd=self.dir,
                              capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = json.loads(done.stdout)
        self.assertEqual(report["status"], "passed")
        rows = {row["name"]: row for row in report["ffi"]}
        self.assertEqual(len(rows), STUBS.count("@extern"))
        self.assertEqual(rows["tiny_add"]["prototype"], "int tiny_add(int, int)")
        self.assertTrue(rows["tiny_add"]["header_checked"])
        self.assertEqual(rows["tiny_fill"]["writes"], ["buf"])
        self.assertEqual(rows["tiny_divmod"]["errors"], {"check": "negative", "errno": True, "exception": "OSError"})
        self.assertEqual(rows["tiny_divmod"]["writes"], ["q", "r"])
        self.assertEqual(rows["tiny_count"]["prototype"], "size_t tiny_count(const unsigned char *, size_t, uint8_t)")

    def test_check_flags_a_trusted_declaration(self):
        text = ('from ail_ffi import *\n\n@extern(lib="c")\ndef labs(x: c_long) -> c_long: ...\n\n'
                'def main():\n    print(labs(-3))\n\nmain()\n')
        self.write("trusted.py", text)
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        done = subprocess.run([sys.executable, "-B", CLI, "check", "trusted.py", "--ffi"], cwd=self.dir,
                              capture_output=True, text=True, env=env)
        report = json.loads(done.stdout)
        self.assertEqual(report["status"], "passed", done.stdout)
        self.assertFalse(report["ffi"][0]["header_checked"])
        self.assertTrue(report["ffi"][0]["trusted_declaration"])

    def test_no_ffi_refuses_declarations(self):
        self.write("forbid.py", STUBS + "\ndef main():\n    print(tiny_add(1, 2))\n\nmain()\n")
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        done = subprocess.run([sys.executable, "-B", CLI, "check", "forbid.py", "--no-ffi"], cwd=self.dir,
                              capture_output=True, text=True, env=env)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("forbidden by --no-ffi", json.loads(done.stdout)["diagnostics"][0]["message"])
        built, _ = compile_cli(self.dir, "forbid.py", "--no-ffi", name="forbid.out")
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("forbidden by --no-ffi", built.stderr)
        self.assertIn("forbid.py:", built.stderr)

    def test_no_ffi_accepts_a_program_without_declarations(self):
        self.write("plain.py", NO_FFI)
        built, exe = compile_cli(self.dir, "plain.py", "--no-ffi", name="plain.out")
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertEqual(subprocess.run([str(exe)], capture_output=True, text=True).stdout, "3\n")

    def test_named_refusals(self):
        cases = {
            "missing parameter annotation": ('@extern(lib="c")\ndef f(a) -> c_int: ...', "needs an annotation"),
            "missing return annotation": ('@extern(lib="c")\ndef f(a: c_int): ...', "missing return annotation"),
            "plain int annotation": ('@extern(lib="c")\ndef f(a: int) -> c_int: ...', "unsupported FFI annotation"),
            "unknown option": ('@extern(lib="c", bogus=1)\ndef f(a: c_int) -> c_int: ...', "unknown @extern option"),
            "stub with a body": ('@extern(lib="c")\ndef f(a: c_int) -> c_int:\n    return a', "no body"),
            "errno without check": ('@extern(lib="c", errno=True)\ndef f(a: c_int) -> c_int: ...', "errno=True needs check"),
            "bad exception": ('@extern(lib="c", check="negative", exc=Exception)\ndef f(a: c_int) -> c_int: ...', "exc must be one of"),
            "length of nothing": ('@extern(lib="c")\ndef f(a: c_int, n: length("zzz")) -> c_int: ...', "must name a bytes or bytearray"),
            "check on a float": ('@extern(lib="c", check="negative")\ndef f(a: c_int) -> c_double: ...', "check= needs an integer or handle"),
            "another decorator": ('@extern(lib="c")\n@staticmethod\ndef f(a: c_int) -> c_int: ...', "no other decorator"),
        }
        for label, (stub, message) in cases.items():
            with self.subTest(label):
                self.write("refuse.py", "from ail_ffi import *\n\n" + stub + "\n\ndef main():\n    print(1)\n\nmain()\n")
                env = dict(os.environ, PYTHONPATH=str(ROOT))
                done = subprocess.run([sys.executable, "-B", CLI, "check", "refuse.py"], cwd=self.dir,
                                      capture_output=True, text=True, env=env)
                self.assertNotEqual(done.returncode, 0, done.stdout)
                self.assertIn(message, json.loads(done.stdout)["diagnostics"][0]["message"])

    def test_the_shim_refuses_the_same_declarations(self):
        sys.path.insert(0, str(ROOT))
        try:
            import ail_ffi
        finally:
            sys.path.remove(str(ROOT))
        with self.assertRaises(TypeError):
            @ail_ffi.extern(lib="c")
            def f(a) -> ail_ffi.c_int: ...
        with self.assertRaises(TypeError):
            @ail_ffi.extern(lib="c")
            def g(a: ail_ffi.c_int): ...
        with self.assertRaises(ValueError):
            @ail_ffi.extern(lib="c", errno=True)
            def h(a: ail_ffi.c_int) -> ail_ffi.c_int: ...

    def test_the_shim_range_checks_like_the_compiler_would(self):
        sys.path.insert(0, str(ROOT))
        try:
            import ail_ffi
        finally:
            sys.path.remove(str(ROOT))

        @ail_ffi.extern(lib="c", header="stdlib.h", symbol="abs")
        def c_abs(x: ail_ffi.c_int) -> ail_ffi.c_int: ...

        self.assertEqual(c_abs(-5), 5)
        with self.assertRaises(OverflowError):
            c_abs(2 ** 31)
        with self.assertRaises(TypeError):
            c_abs(1.5)

    def test_a_program_without_ail_ffi_is_untouched(self):
        sys.path.insert(0, str(ROOT))
        try:
            import ail_ffi_lower
        finally:
            sys.path.remove(str(ROOT))
        session = ail_ffi_lower.Session()
        text = NO_FFI + "\n# mentions nothing\n"
        self.assertIs(session.lower(self.dir / "plain.py", text), text)
        self.assertEqual(session.decls, [])
        self.assertIsNone(session.build(CLI))
        self.write("plain2.py", NO_FFI)
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        done = subprocess.run([sys.executable, "-B", CLI, "check", "plain2.py", "--ffi"], cwd=self.dir,
                              capture_output=True, text=True, env=env)
        self.assertEqual(json.loads(done.stdout)["ffi"], [])


if __name__ == "__main__":
    unittest.main()
