"""F6: a Rust crate becomes an AIL/CPython FFI library in one step.

`ail_cargo.py build CRATE_DIR -o OUT` checks Cargo.toml (`cdylib` + `staticlib`,
`panic = "abort"`), runs `cargo build --release --offline --lib`, takes a header from cbindgen
or `--header`, runs `ail_bindgen.py`, and writes the cdylib, staticlib, header, stubs and
cargo's native-static-libs link line.  The stubs link `./libX.a`, so CPython uses a copy that
links the `.so` and a compiled AIL program uses the `.a`; both must print the same bytes.

A dependency is vendored from a local git repository (`cargo vendor`) so the build is offline.
`ail_rsgen.py NAME.h` emits a Rust binding crate (extern "C" block, Result-returning safe
wrappers that read NAME_last_error); a Rust host that uses it is compared with CPython calling
the same `@export` library.

Skipped when cargo (and a C compiler) is missing.  cbindgen is optional: tests use --header,
and a fake cbindgen checks the installed branch without it.
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
CARGO_TOOL = ROOT / "ail_cargo.py"
RSGEN = ROOT / "ail_rsgen.py"
CLI = ROOT / "ail_chatgpt.py"
CARGO = shutil.which("cargo")
GIT = shutil.which("git")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
sys.path.insert(0, str(ROOT))
from test_ail_ffi import compile_cli, run_cpython  # noqa: E402

CARGOTOML = """[package]
name = "{name}"
version = "0.1.0"
edition = "2021"

[lib]
path = "src/lib.rs"
crate-type = ["cdylib", "staticlib"]

[profile.release]
panic = "abort"
"""

NATIVE_SOURCE = r"""
#[no_mangle]
pub extern "C" fn nc_add(a: i64, b: i64) -> i64 { a.wrapping_add(b) }

#[no_mangle]
pub unsafe extern "C" fn nc_sum(xs: *const i64, n: usize) -> i64 {
    let mut total = 0i64;
    for i in 0..n { total = total.wrapping_add(*xs.add(i)); }
    total
}

#[no_mangle]
pub unsafe extern "C" fn nc_upper(p: *mut u8, n: usize) -> isize {
    for i in 0..n { *p.add(i) = (*p.add(i)).to_ascii_uppercase(); }
    n as isize
}

#[no_mangle]
pub unsafe extern "C" fn nc_fill(out: *mut u8, cap: usize, value: u8) -> isize {
    if cap < 3 { return -1; }
    for i in 0..cap { *out.add(i) = value; }
    cap as isize
}

pub struct Counter { next: i64 }

#[no_mangle]
pub extern "C" fn nc_counter_new(start: i64) -> *mut Counter {
    Box::into_raw(Box::new(Counter { next: start }))
}

#[no_mangle]
pub unsafe extern "C" fn nc_counter_next(counter: *mut Counter) -> i64 {
    let value = (*counter).next;
    (*counter).next += 1;
    value
}

#[no_mangle]
pub unsafe extern "C" fn nc_counter_free(counter: *mut Counter) { drop(Box::from_raw(counter)); }
"""

NATIVE_HEADER = """#include <stddef.h>
#include <stdint.h>
typedef struct Counter Counter;
int64_t nc_add(int64_t a, int64_t b);
int64_t nc_sum(const int64_t *xs, size_t n);
intptr_t nc_upper(uint8_t *p, size_t n);
intptr_t nc_fill(uint8_t *out, size_t cap, uint8_t value);
struct Counter *nc_counter_new(int64_t start);
int64_t nc_counter_next(struct Counter *counter);
void nc_counter_free(struct Counter *counter);
"""

NATIVE_PROGRAM = r"""
from ail_cbuf import get_i64, put_i64

def main():
    print(nc_add(2, 3), nc_add(-5, 7), nc_add(2147483000, 600))
    xs = bytearray(8 * 4)
    for index, value in enumerate([10, -4, 0, 99]):
        put_i64(xs, index * 8, value)
    print(nc_sum(bytes(xs)))
    text = bytearray(b"mixed Case 123")
    print(nc_upper(text), bytes(text).decode())
    out = bytearray(8)
    print(nc_fill(out, 65), bytes(out[0:5]).decode())
    small = bytearray(2)
    print(nc_fill(small, 66))
    counter = nc_counter_new(10)
    print(nc_counter_next(counter), nc_counter_next(counter), nc_counter_next(counter))
    nc_counter_free(counter)

main()
"""

VENDOR_SOURCE = r"""
use tinydep::twice;

#[no_mangle]
pub extern "C" fn vd_twice(x: i64) -> i64 { twice(x) }

#[no_mangle]
pub unsafe extern "C" fn vd_sum(xs: *const f64, n: usize) -> f64 {
    let mut total = 0.0;
    for i in 0..n { total += *xs.add(i); }
    total
}

#[no_mangle]
pub unsafe extern "C" fn vd_upper(p: *mut u8, n: usize) -> usize {
    for i in 0..n { *p.add(i) = (*p.add(i)).to_ascii_uppercase(); }
    n
}

pub struct Handle { next: i64 }

#[no_mangle]
pub extern "C" fn vd_new(start: i64) -> *mut Handle {
    Box::into_raw(Box::new(Handle { next: start }))
}

#[no_mangle]
pub unsafe extern "C" fn vd_next(handle: *mut Handle) -> i64 {
    let value = twice((*handle).next);
    (*handle).next += 1;
    value
}

#[no_mangle]
pub unsafe extern "C" fn vd_free(handle: *mut Handle) { drop(Box::from_raw(handle)); }
"""

VENDOR_HEADER = """#include <stddef.h>
#include <stdint.h>
typedef struct Handle Handle;
int64_t vd_twice(int64_t x);
double vd_sum(const double *xs, size_t n);
uintptr_t vd_upper(uint8_t *p, size_t n);
struct Handle *vd_new(int64_t start);
int64_t vd_next(struct Handle *handle);
void vd_free(struct Handle *handle);
"""

VENDOR_PROGRAM = r"""
from ail_cbuf import put_f64

def main():
    print(vd_twice(21), vd_twice(-4))
    xs = bytearray(8 * 3)
    put_f64(xs, 0, 1.5)
    put_f64(xs, 8, -2.25)
    put_f64(xs, 16, 10.0)
    print(vd_sum(bytes(xs)))
    text = bytearray(b"vendored Case")
    print(vd_upper(text), bytes(text).decode())
    handle = vd_new(7)
    print(vd_next(handle), vd_next(handle), vd_next(handle))
    vd_free(handle)

main()
"""

AIL_SOURCE = r"""
from dataclasses import dataclass
from ail_ffi import export

@dataclass
class Point:
    x: float
    y: float
    visible: bool

@export
def add(a: int, b: int) -> int:
    return a + b

@export
def scale(xs: list[float], k: float) -> list[float]:
    return [x * k for x in xs]

@export
def ints(xs: list[int]) -> list[int]:
    return [x * 2 + 1 for x in xs]

@export
def greet(name: str) -> str:
    return "hello, " + name + "!"

@export
def bump(data: bytes) -> bytes:
    out = bytearray(data)
    for i in range(len(out)):
        out[i] = (out[i] + 1) % 256
    return bytes(out)

@export
def length(p: Point) -> float:
    return p.x * p.x + p.y * p.y

@export
def flip(flag: bool) -> bool:
    return not flag

@export
def erode(x: int) -> int:
    if x < 0:
        raise ValueError("negative: " + str(x))
    return x

@export
def nothing(x: int) -> None:
    return
"""

RUST_HOST = r"""
use demo_bindings as d;

fn main() {
    println!("{}", d::add(2, 3).unwrap());
    println!("{}", d::add(-5, 7).unwrap());
    println!("{:?}", d::scale(&[1.0, -2.0, 0.5], 2.5).unwrap());
    println!("{:?}", d::scale(&[], 2.0).unwrap());
    println!("{:?}", d::ints(&[1, -2, 3]).unwrap());
    println!("{:?}", d::ints(&[]).unwrap());
    println!("{}", d::greet("wörld").unwrap());
    println!("{}", d::greet("").unwrap());
    println!("{:?}", d::bump(b"abc").unwrap());
    println!("{:?}", d::bump(b"").unwrap());
    let point = d::Point { x: 3.0, y: 4.0, visible: true };
    println!("{:?}", d::length(&point).unwrap());
    println!("{} {}", d::flip(true).unwrap(), d::flip(false).unwrap());
    println!("{}", d::erode(7).unwrap());
    match d::erode(-4) {
        Ok(value) => println!("ok {}", value),
        Err(error) => println!("error {} {} {}", error.code, error.kind, error.message),
    }
    d::nothing(9).unwrap();
}
"""


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run(command, cwd, env=None, timeout=1200):
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)


def crate(directory, name, source, manifest=None):
    directory = Path(directory)
    write(directory / "Cargo.toml", manifest if manifest is not None else CARGOTOML.format(name=name))
    write(directory / "src" / "lib.rs", source)
    return directory


@unittest.skipUnless(CARGO and CC, "cargo and a C compiler are required")
class CargoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-cargo-test-")
        cls.root = Path(cls.temp.name)
        shutil.copyfile(ROOT / "ail_cbuf.py", cls.root / "ail_cbuf.py")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def both(self, directory, stubs, program, name):
        """CPython against the cdylib and AIL against the staticlib, same stdout."""
        directory = Path(directory)
        shutil.copyfile(ROOT / "ail_cbuf.py", directory / "ail_cbuf.py")
        cpy = write(directory / (name + "_cpy.py"),
                    stubs.replace("./libnativecrate.a", "./libnativecrate.so")
                         .replace("./libvendcrate.a", "./libvendcrate.so") + program)
        expected = run_cpython(directory, cpy.name)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        ail = write(directory / (name + "_ail.py"), stubs + program)
        built, exe = compile_cli(directory, ail.name, name=name + ".out")
        self.assertEqual(built.returncode, 0, built.stderr)
        got = run([str(exe)], directory, timeout=120)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(expected.stdout, got.stdout)
        return got.stdout

    # ------------------------------------------------------------------ cargo build

    def test_cargo_build_writes_artifacts_and_both_sides_match(self):
        work = self.root / "native"
        built_dir = crate(work / "crate", "nativecrate", NATIVE_SOURCE)
        header = write(work / "nativecrate.h", NATIVE_HEADER)
        out = work / "out"
        done = run([sys.executable, str(CARGO_TOOL), "build", str(built_dir), "-o", str(out), "--header", str(header)],
                   self.root)
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        for name in ("libnativecrate.so", "libnativecrate.a", "nativecrate.h", "nativecrate_ffi.py",
                     "nativecrate.link.txt", "link.txt"):
            self.assertTrue((out / name).is_file(), name)
        stubs = (out / "nativecrate_ffi.py").read_text(encoding="utf-8")
        self.assertIn("link('./libnativecrate.a')", stubs.replace('"', "'"))
        link_line = (out / "nativecrate.link.txt").read_text(encoding="utf-8").strip()
        self.assertTrue(link_line.startswith("native-static-libs:"), link_line)
        self.assertIn("native-static-libs:", done.stdout)
        text = self.both(out, stubs, NATIVE_PROGRAM, "native")
        self.assertIn("2147483600", text)
        self.assertIn("MIXED CASE 123", text)
        self.assertIn("10 11 12", text)

    @unittest.skipUnless(GIT, "git is required to make a local dependency for cargo vendor")
    def test_vendored_dependency_builds_offline(self):
        work = self.root / "vendored"
        dep = work / "tinydep"
        write(dep / "Cargo.toml", CARGOTOML.format(name="tinydep").replace(
            'crate-type = ["cdylib", "staticlib"]\n', '').replace(
            '[profile.release]\npanic = "abort"\n', ''))
        write(dep / "src" / "lib.rs", "pub fn twice(x: i64) -> i64 { x.wrapping_mul(2) }\n")
        for command in (["git", "init", "-q"], ["git", "add", "."],
                        ["git", "-c", "user.email=a@example.com", "-c", "user.name=a", "commit", "-qm", "init"]):
            done = run(command, dep)
            self.assertEqual(done.returncode, 0, done.stderr)

        url = dep.as_uri()
        manifest = CARGOTOML.format(name="vendcrate") + '\n[dependencies]\ntinydep = { git = %s }\n' % json.dumps(url)
        app = crate(work / "crate", "vendcrate", VENDOR_SOURCE, manifest=manifest)
        vendored = run([CARGO, "vendor", "vendor"], app)
        self.assertEqual(vendored.returncode, 0, vendored.stderr)
        write(app / ".cargo" / "config.toml",
              '[source."git+%s"]\ngit = %s\nreplace-with = "vendored-sources"\n\n'
              '[source.vendored-sources]\ndirectory = "vendor"\n' % (url, json.dumps(url)))
        header = write(work / "vendcrate.h", VENDOR_HEADER)
        out = work / "out"
        done = run([sys.executable, str(CARGO_TOOL), "build", str(app), "-o", str(out), "--header", str(header)],
                   self.root)
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        stubs = (out / "vendcrate_ffi.py").read_text(encoding="utf-8")
        self.assertIn("link('./libvendcrate.a')", stubs.replace('"', "'"))
        text = self.both(out, stubs, VENDOR_PROGRAM, "vendored")
        self.assertIn("42 -8", text)
        self.assertIn("9.25", text)
        self.assertIn("VENDORED CASE", text)
        self.assertIn("14 16 18", text)

    def test_cargo_refuses_missing_crate_type_and_panic(self):
        work = self.root / "refusals"
        header = write(work / "refuse.h", "#include <stdint.h>\nint64_t refuse_value(void);\n")
        missing_kind = work / "kind"
        crate(missing_kind, "refusekind", '#[no_mangle] pub extern "C" fn refuse_value() -> i64 { 1 }\n',
              manifest=CARGOTOML.format(name="refusekind").replace(
                  'crate-type = ["cdylib", "staticlib"]', 'crate-type = ["staticlib"]'))
        done = run([sys.executable, str(CARGO_TOOL), "build", str(missing_kind), "-o", str(work / "out1"),
                    "--header", str(header)], self.root)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("crate-type", done.stderr)
        self.assertIn("cdylib", done.stderr)

        missing_panic = work / "panic"
        crate(missing_panic, "refusepanic", '#[no_mangle] pub extern "C" fn refuse_value() -> i64 { 1 }\n',
              manifest=CARGOTOML.format(name="refusepanic").replace(
                  '[profile.release]\npanic = "abort"\n', ''))
        done = run([sys.executable, str(CARGO_TOOL), "build", str(missing_panic), "-o", str(work / "out2"),
                    "--header", str(header)], self.root)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('panic = "abort"', done.stderr)

    @unittest.skipUnless(os.name != "nt", "the fake cbindgen is a shell script")
    def test_cbindgen_is_used_when_installed(self):
        work = self.root / "cbindgen"
        app = crate(work / "crate", "cbindgencrate",
                    '#[no_mangle] pub extern "C" fn cb_value() -> i64 { 41 }\n')
        bin_dir = work / "bin"
        fake = write(bin_dir / "cbindgen", """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--output" ]; then out=$2; shift 2; else shift; fi
done
cat > "$out" <<'HEADER'
#include <stdint.h>
int64_t cb_value(void);
HEADER
""")
        fake.chmod(0o755)
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        out = work / "out"
        done = run([sys.executable, str(CARGO_TOOL), "build", str(app), "-o", str(out)], self.root, env=env)
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        self.assertIn("int64_t cb_value(void);", (out / "cbindgencrate.h").read_text(encoding="utf-8"))
        self.assertIn("cb_value", (out / "cbindgencrate_ffi.py").read_text(encoding="utf-8"))

    def test_missing_cbindgen_names_the_header_option(self):
        if shutil.which("cbindgen"):
            self.skipTest("cbindgen is installed")
        work = self.root / "noheader"
        app = crate(work / "crate", "noheadercrate",
                    '#[no_mangle] pub extern "C" fn nh_value() -> i64 { 1 }\n')
        done = run([sys.executable, str(CARGO_TOOL), "build", str(app), "-o", str(work / "out")], self.root)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("cbindgen", done.stderr)
        self.assertIn("--header", done.stderr)

    # ------------------------------------------------------------------ AIL -> Rust

    def test_rsgen_binding_crate_calls_an_export_library_like_cpython(self):
        work = self.root / "rsgen"
        libdir = work / "lib"
        libdir.mkdir(parents=True)
        source = write(libdir / "libsrc.py", AIL_SOURCE)
        built = run([sys.executable, "-B", str(CLI), "compile", "--lib", "demo", str(source), "-o", str(libdir)],
                    libdir)
        self.assertEqual(built.returncode, 0, built.stderr + built.stdout)
        header = libdir / "demo.h"
        self.assertTrue(header.is_file())
        bindings = work / "bindings"
        done = run([sys.executable, str(RSGEN), str(header), "-o", str(bindings)], self.root)
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        rust = (bindings / "src" / "lib.rs").read_text(encoding="utf-8")
        self.assertIn('extern "C" {', rust)
        self.assertIn("pub fn add(a: i64, b: i64) -> Result<i64, Error>", rust)
        self.assertIn("pub fn greet(name: &str) -> Result<String, Error>", rust)
        self.assertIn("pub fn bump(data: &[u8]) -> Result<Vec<u8>, Error>", rust)
        self.assertIn("demo_last_error()", rust)

        host = work / "host"
        write(host / "Cargo.toml",
              '[package]\nname = "host"\nversion = "0.1.0"\nedition = "2021"\n\n'
              '[dependencies]\ndemo_bindings = { path = %s }\n' % json.dumps(str(bindings)))
        write(host / "src" / "main.rs", RUST_HOST)
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        built = run([CARGO, "run", "--release", "--offline"], host, env=env)
        self.assertEqual(built.returncode, 0, built.stderr + built.stdout)
        got = built.stdout.splitlines()

        oracle = r"""import sys
sys.path.insert(0, %s)
import libsrc
print(libsrc.add(2, 3))
print(libsrc.add(-5, 7))
print(libsrc.scale([1.0, -2.0, 0.5], 2.5))
print(libsrc.scale([], 2.0))
print(libsrc.ints([1, -2, 3]))
print(libsrc.ints([]))
print(libsrc.greet("wörld"))
print(libsrc.greet(""))
print(list(libsrc.bump(b"abc")))
print(list(libsrc.bump(b"")))
print(libsrc.length(libsrc.Point(3.0, 4.0, True)))
print("true" if libsrc.flip(True) else "false", "true" if libsrc.flip(False) else "false")
print(libsrc.erode(7))
try:
    libsrc.erode(-4)
except ValueError as error:
    print("error", 1, "ValueError", "ValueError: " + str(error))
libsrc.nothing(9)
""" % json.dumps(str(libdir))
        oracle_path = write(work / "oracle.py", oracle)
        expected = run([sys.executable, "-B", str(oracle_path)], work, env=env)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        self.assertEqual(expected.stdout.splitlines(), got)


if __name__ == "__main__":
    unittest.main()
