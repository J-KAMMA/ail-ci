"""F5: `@cstruct` layouts. A class of C-typed fields is a fixed-size bytearray read and written at the C offsets.

The same program runs on CPython (ail_ffi's ctypes shim) and as the executable `ail_chatgpt.py compile`
builds (typed path, AIL_NO_GENERAL=1). Every @cstruct field is checked against the header with
`_Static_assert(offsetof(...) == k && sizeof(...) == n)`, and a pointer to a struct no longer needs
`trust=True`. Covered: struct tm through gmtime_r/strftime/mktime (no trust for the struct pointers),
every scalar width, fixed arrays, a struct result, a writable struct (copy out) and a readonly one,
the CPython refusals (union, bitfield, nested struct, flexible array), the bindgen output, and a
`#[repr(C)]` Rust struct built with cargo (skipped when cargo is missing).
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from test_ail_ffi import CC, compile_cli, run_cpython  # noqa: E402

BINDGEN = ROOT / "ail_bindgen.py"
CARGO = shutil.which("cargo")
if CARGO and subprocess.run([CARGO, "--version"], capture_output=True).returncode:
    CARGO = None        # a rustup shim with no installed toolchain cannot build the crate

TIME = r"""
from ail_ffi import *
from ail_cbuf import put_i64

@cstruct(header="time.h", name="struct tm")
class Tm:
    tm_sec: c_int
    tm_min: c_int
    tm_hour: c_int
    tm_mday: c_int
    tm_mon: c_int
    tm_year: c_int
    tm_wday: c_int
    tm_yday: c_int
    tm_isdst: c_int
    tm_gmtoff: c_long
    tm_zone: c_char_p

@extern(header="time.h", symbol="gmtime_r")
def c_gmtime_r(timer: cptr(c_long), result: Tm) -> Tm: ...

@extern(header="time.h", symbol="strftime", trust=True)      # strftime takes char *, not unsigned char *
def c_strftime(out: bytearray, cap: length("out"), fmt: c_char_p, tm: cptr(Tm)) -> c_size_t: ...

@extern(header="time.h", symbol="mktime", check="minus1", exc=ValueError)
def c_mktime(tm: Tm) -> c_long: ...

def make(year: int, month: int, day: int, hour: int) -> Tm:
    tm = Tm()
    tm.tm_hour = hour
    tm.tm_mday = day
    tm.tm_mon = month - 1
    tm.tm_year = year - 1900
    tm.tm_isdst = -1
    return tm

def show(tm: Tm) -> None:
    out = bytearray(64)
    n = c_strftime(out, "%Y-%m-%d %H:%M:%S %a %j", tm)
    print(n, bytes(out[0:n]).decode())

def via_arg(tm: Tm) -> int:
    return c_strftime(bytearray(32), "%Y/%m/%d", tm)

def via_list(tms: list[Tm]) -> int:
    return c_strftime(bytearray(32), "%H:%M", tms[0])

class Box:
    def __init__(self, tm: Tm) -> None:
        self.tm = tm

def via_attr(b: Box) -> int:
    return c_strftime(bytearray(32), "%j", b.tm)

def main():
    raw = bytearray(8)
    put_i64(raw, 0, 1700000000)
    tm = c_gmtime_r(bytes(raw), Tm())
    print(tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour, tm.tm_yday, tm.tm_isdst)
    show(tm)
    local = make(2023, 11, 14, 12)
    show(local)
    t = c_mktime(local)
    print(local.tm_wday, local.tm_yday, local.tm_isdst)
    show(local)
    odd = make(2024, 1, 32, 25)
    c_mktime(odd)
    show(odd)
    print(via_arg(local))
    print(via_list([local]))
    print(via_attr(Box(local)))
    d: dict[str, int] = {"hour": 12}
    local.tm_hour = d["hour"]
    print(local.tm_hour)
    empty = Tm()
    print(empty.tm_sec, empty.tm_min, empty.tm_gmtoff, empty.tm_zone)
    neg = Tm()
    neg.tm_sec = -1
    neg.tm_year = -1900
    neg.tm_gmtoff = -3600
    print(neg.tm_sec, neg.tm_year, neg.tm_gmtoff)
    alias = local
    alias.tm_min = 7
    print(local.tm_min)

main()
"""

MIX_H = r"""
#include <stdint.h>
struct Mix {
    int8_t i8;
    uint8_t u8;
    int16_t i16;
    uint16_t u16;
    int32_t i32;
    uint32_t u32;
    int64_t i64;
    uint64_t u64;
    float f;
    double d;
    _Bool flag;
    int16_t arr[3];
};
void mix_fill(struct Mix *m);
int64_t mix_sum(const struct Mix *m);
struct Mix *mix_new(void);
void mix_free(struct Mix *m);
"""

MIX_C = r"""
#include "mix.h"
#include <stdlib.h>
void mix_fill(struct Mix *m) {
    m->i8 = -128; m->u8 = 255; m->i16 = -32768; m->u16 = 65535;
    m->i32 = -2147483647 - 1; m->u32 = 4294967295u;
    m->i64 = -9000000000000000000LL; m->u64 = 9000000000000000000ULL;
    m->f = 1.5f; m->d = -2.25; m->flag = 1;
    m->arr[0] = 10; m->arr[1] = -20; m->arr[2] = 30;
}
int64_t mix_sum(const struct Mix *m) {
    return (int64_t)m->i8 + m->u8 + m->i16 + m->u16 + m->i32 + m->u32 + m->i64 + (int64_t)m->u64
           + (int64_t)m->f + (int64_t)m->d + m->flag + m->arr[0] + m->arr[1] + m->arr[2];
}
struct Mix *mix_new(void) {
    struct Mix *m = calloc(1, sizeof *m);
    m->i8 = 7; m->u8 = 8; m->i16 = -9; m->u16 = 10; m->i32 = -11; m->u32 = 12;
    m->i64 = -13; m->u64 = 14; m->f = 2.5f; m->d = 3.5; m->flag = 1;
    m->arr[0] = 15; m->arr[1] = 16; m->arr[2] = 17;
    return m;
}
void mix_free(struct Mix *m) { free(m); }
"""

MIX_MAIN = r"""
{STUBS}

def main():
    m = Mix()
    print(m.i8, m.u8, m.i16, m.u16, m.i32, m.u32, m.i64, m.u64, m.f, m.d, m.flag)
    m.i8 = -128
    m.u8 = 255
    m.i16 = -32768
    m.u16 = 65535
    m.i32 = -2147483647
    m.u32 = 4294967295
    m.i64 = -9000000000000000000
    m.u64 = 9000000000000000000
    m.f = 1.5
    m.d = -2.25
    m.flag = True
    m.arr = [10, -20, 30]
    print(m.i8, m.u8, m.i16, m.u16, m.i32, m.u32, m.i64, m.u64, m.f, m.d, m.flag, m.arr[0], m.arr[1], m.arr[2])
    mix_fill(m)
    print(m.i8, m.u8, m.i16, m.u16, m.i32, m.u32, m.i64, m.u64, m.f, m.d, m.flag, m.arr[0], m.arr[1], m.arr[2])
    print(mix_sum(m))
    n = mix_new()
    print(n.i8, n.u8, n.i16, n.u16, n.i32, n.u32, n.i64, n.u64, n.f, n.d, n.flag, n.arr[0], n.arr[1], n.arr[2])
    n.arr[1] = 700
    print(mix_sum(n))

main()
"""

RUST_SOURCE = r"""
#[repr(C)]
pub struct AilPoint { pub x: i32, pub y: i32 }

#[no_mangle]
pub extern "C" fn ailpoint_new(x: i32, y: i32) -> *mut AilPoint {
    Box::into_raw(Box::new(AilPoint { x, y }))
}

#[no_mangle]
pub unsafe extern "C" fn ailpoint_move(p: *mut AilPoint, dx: i32, dy: i32) -> *mut AilPoint {
    (*p).x = (*p).x.wrapping_add(dx);
    (*p).y = (*p).y.wrapping_add(dy);
    p
}

#[no_mangle]
pub unsafe extern "C" fn ailpoint_sum(p: *const AilPoint) -> i32 {
    (*p).x.wrapping_add((*p).y)
}

#[no_mangle]
pub unsafe extern "C" fn ailpoint_free(p: *mut AilPoint) { drop(Box::from_raw(p)); }
"""

RUST_H = r"""
#include <stdint.h>
typedef struct AilPoint { int32_t x; int32_t y; } AilPoint;
struct AilPoint *ailpoint_new(int32_t x, int32_t y);
struct AilPoint *ailpoint_move(struct AilPoint *p, int32_t dx, int32_t dy);
int32_t ailpoint_sum(const struct AilPoint *p);
void ailpoint_free(struct AilPoint *p);
"""

RUST_MAIN = r"""
{STUBS}

def main():
    p = ailpoint_new(3, 4)
    print(p.x, p.y)
    q = ailpoint_move(p, 10, -2)
    print(p.x, p.y, q.x, q.y)
    print(ailpoint_sum(p))

main()
"""


def build_shared(directory, name, header, source):
    directory = Path(directory)
    (directory / (name + ".h")).write_text(header, encoding="utf8")
    (directory / (name + ".c")).write_text(source, encoding="utf8")
    done = subprocess.run([CC, "-shared", "-fPIC", "-O1", "-o", str(directory / ("lib%s.so" % name)),
                           str(directory / (name + ".c"))], capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(done.stderr)


def load_bindgen():
    spec = importlib.util.spec_from_file_location("ail_bindgen_cstruct", BINDGEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(CC, "installed C compiler required")
class CStructTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-cstruct-test-")
        cls.dir = Path(cls.temp.name)
        shutil.copyfile(ROOT / "ail_cbuf.py", cls.dir / "ail_cbuf.py")
        build_shared(cls.dir, "mix", MIX_H, MIX_C)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf8")
        return name

    def both(self, name, text, ir="0"):
        cpy = self.write(name + "_cpy.py", text.replace("{MSG}", "str(e)"))
        ail = self.write(name + "_ail.py", text.replace("{MSG}", "e.message"))
        expected = run_cpython(self.dir, cpy)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        built, exe = compile_cli(self.dir, ail, ir=ir, name=name + ".out")
        self.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(expected.stdout, ran.stdout)
        return ran.stdout

    def test_time_round_trip(self):
        out = self.both("time", TIME)
        for line in ("2023 11 14 22 317 0",
                     "27 2023-11-14 22:13:20 Tue 318",
                     "27 2023-11-14 12:00:00 Sun 001",
                     "27 2023-11-14 12:00:00 Tue 318",
                     "27 2024-02-02 01:00:00 Fri 033",
                     "10", "5", "3", "12",
                     "0 0 0 0", "-1 -1900 -3600", "7"):
            self.assertIn(line, out)

    def test_time_round_trip_under_the_ir(self):
        self.both("time_ir", TIME, ir="1")

    def test_all_widths_and_fixed_arrays(self):
        stubs = load_bindgen().generate(MIX_H, "mix.h", lib="./libmix.so")
        self.assertIn("@cstruct(header='mix.h', name='struct Mix')", stubs)
        self.assertIn("arr: c_array(c_int16, 3)", stubs)
        out = self.both("mix", MIX_MAIN.replace("{STUBS}", stubs))
        self.assertEqual(out.splitlines()[0], "0 0 0 0 0 0 0 0 0.0 0.0 False")
        self.assertIn("-128 255 -32768 65535 -2147483647 4294967295", out)
        self.assertIn("1.5 -2.25 True 10 -20 30", out)
        self.assertIn("7 8 -9 10 -11 12 -13 14 2.5 3.5 True 15 16 17", out)

    def test_a_wrong_field_type_is_a_compile_error(self):
        text = r"""
from ail_ffi import *

@cstruct(header="time.h", name="struct tm")
class TmBad:
    tm_sec: c_int64
    tm_min: c_int
    tm_hour: c_int
    tm_mday: c_int
    tm_mon: c_int
    tm_year: c_int
    tm_wday: c_int
    tm_yday: c_int
    tm_isdst: c_int
    tm_gmtoff: c_long
    tm_zone: c_char_p

def main():
    print(TmBad().tm_sec)

main()
"""
        self.write("wrong_type.py", text)
        built, _ = compile_cli(self.dir, "wrong_type.py", name="wrong_type.out")
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("ail_cstruct TmBad.tm_sec does not match its header", built.stderr)

    def test_a_wrong_field_offset_is_a_compile_error(self):
        text = r"""
from ail_ffi import *

@cstruct(header="time.h", name="struct tm")
class TmOff:
    tm_sec: c_int
    tm_mday: c_int
    tm_hour: c_int
    tm_min: c_int
    tm_mon: c_int
    tm_year: c_int
    tm_wday: c_int
    tm_yday: c_int
    tm_isdst: c_int
    tm_gmtoff: c_long
    tm_zone: c_char_p

def main():
    print(TmOff().tm_mday)

main()
"""
        self.write("wrong_offset.py", text)
        built, _ = compile_cli(self.dir, "wrong_offset.py", name="wrong_offset.out")
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("ail_cstruct TmOff.tm_mday does not match its header", built.stderr)

    def test_named_refusals(self):
        cases = {
            "union": ("@cstruct(union=True)\nclass U:\n    a: c_int", "refuses union U"),
            "bitfield": ("@cstruct(bitfield=True)\nclass B:\n    a: c_int", "refuses bitfield B"),
            "nested array": ("@cstruct()\nclass Inner:\n    a: c_int\n\n@cstruct()\nclass Outer:\n    row: c_array(Inner, 2)",
                             "nested by-value array of structs"),
            "flexible member": ("@cstruct()\nclass Flex:\n    n: c_int\n    data: c_array(c_int, 0)",
                                "flexible array member"),
        }
        for label, (body, message) in cases.items():
            with self.subTest(label):
                self.write("refuse.py", "from ail_ffi import *\n\n" + body + "\n\ndef main():\n    print(1)\n\nmain()\n")
                built, _ = compile_cli(self.dir, "refuse.py", name="refuse.out")
                self.assertNotEqual(built.returncode, 0)
                self.assertIn(message, built.stderr)

    def test_the_shim_refuses_the_same_structs(self):
        sys.path.insert(0, str(ROOT))
        try:
            import ail_ffi
        finally:
            sys.path.remove(str(ROOT))
        with self.assertRaises(TypeError):
            @ail_ffi.cstruct(union=True)
            class U:
                a: ail_ffi.c_int
        with self.assertRaises(TypeError):
            @ail_ffi.cstruct(bitfield=True)
            class B:
                a: ail_ffi.c_int

        @ail_ffi.cstruct()
        class Inner:
            a: ail_ffi.c_int

        with self.assertRaises(TypeError):
            @ail_ffi.cstruct()
            class Outer:
                row: ail_ffi.c_array(Inner, 2)
        with self.assertRaises(TypeError):
            @ail_ffi.cstruct()
            class Flex:
                n: ail_ffi.c_int
                data: ail_ffi.c_array(ail_ffi.c_int, 0)

    def test_bindgen_emits_cstruct(self):
        header = r"""
#include <stdint.h>
typedef struct Point { int32_t x; int32_t y; } Point;
struct Inner { int32_t a; int32_t b[3]; };
union U { int a; double b; };
struct Bad { unsigned x : 3; };
struct Flex { int n; int data[]; };
struct Outer { struct Inner inner; };
struct Point *point_new(int32_t x, int32_t y);
int32_t point_sum(const struct Point *p);
void point_move(struct Point *p, int32_t dx, int32_t dy);
"""
        text = load_bindgen().generate(header, "demo.h", lib="./libdemo.so")
        normalized = text.replace('"', "'")
        self.assertIn("@cstruct(header='demo.h', name='struct Point')\nclass Point:\n    x: c_int32\n    y: c_int32", normalized)
        self.assertIn("b: c_array(c_int32, 3)", normalized)
        self.assertIn("def point_new(x: c_int32, y: c_int32) -> Point: ...", normalized)
        self.assertIn("def point_sum(p: cptr(Point)) -> c_int32: ...", normalized)
        self.assertIn("def point_move(p: ptr(Point), dx: c_int32, dy: c_int32) -> None: ...", normalized)
        self.assertIn("@extern(lib='./libdemo.so', header='demo.h')\ndef point_sum", normalized)
        self.assertIn("# skipped struct Bad: bitfield", text)
        self.assertIn("# skipped struct U: union U is not supported", text)
        self.assertIn("# skipped struct Flex: flexible array member 'data'", text)
        self.assertIn("# skipped struct Outer: nested struct field 'inner' by value", text)

    @unittest.skipUnless(CARGO, "cargo required for the #[repr(C)] Rust case")
    def test_rust_repr_c_struct(self):
        rdir = self.dir / "rust"
        (rdir / "src").mkdir(parents=True)
        (rdir / "Cargo.toml").write_text(
            '[package]\nname = "ailpoint"\nversion = "0.1.0"\nedition = "2021"\n\n'
            '[lib]\ncrate-type = ["cdylib"]\n\n[profile.release]\npanic = "abort"\n', encoding="utf8")
        (rdir / "src" / "lib.rs").write_text(RUST_SOURCE, encoding="utf8")
        built = subprocess.run([CARGO, "build", "--release", "--offline"], cwd=rdir, capture_output=True,
                               text=True, timeout=600)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        shutil.copyfile(rdir / "target" / "release" / "libailpoint.so", self.dir / "libailpoint.so")
        stubs = load_bindgen().generate(RUST_H, "ailpoint.h", lib="./libailpoint.so")
        self.assertIn("@cstruct(header='ailpoint.h', name='struct AilPoint')", stubs)
        self.assertIn("def ailpoint_move(p: ptr(AilPoint), dx: c_int32, dy: c_int32) -> AilPoint: ...", stubs)
        self.assertNotIn("trust=True", stubs)
        out = self.both("rustpoint", RUST_MAIN.replace("{STUBS}", stubs))
        self.assertEqual(out, "3 4\n13 2 13 2\n15\n")


if __name__ == "__main__":
    unittest.main()
