"""G5a: `import zlib` in a compiled program (stdlib/zlib.py, written over the C FFI) against CPython's own zlib.

The oracle is the real `zlib` module of `python3` (not the ail_ffi shim): both sides call the system zlib, so
every byte must agree. One program is compiled once and run for many (seed, size, kind, level, wbits)
tuples; error messages are compared through `{MSG}` (`str(e)` for CPython, `e.message` for the compiler,
whose typed path has no printable exception). `zlib.error` is spelt RuntimeError inside the compiler.

Also: the same stdlib/zlib.py runs under CPython through the ctypes `ail_ffi` shim (which builds zlib_glue.c
on the fly) and agrees with the real module, a program of its own may define `crc32` beside `import zlib`,
and `--no-ffi` refuses a program that imports zlib.
"""
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib as real_zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

ROUND_TRIP = r"""
import sys
import zlib

def make(seed: int, size: int, kind: int) -> bytes:
    buf = bytearray()
    x = seed
    for i in range(size):
        x = (x * 1103515245 + 12345) % 2147483648
        if kind == 0:
            buf.append((x >> 16) & 255)
        elif kind == 1:
            buf.append(97 + ((x >> 16) % 4))
        elif kind == 2:
            buf.append(0)
        else:
            buf.append(65 + (i // 17) % 5)
    return bytes(buf)

def main():
    seed = int(sys.argv[1])
    size = int(sys.argv[2])
    kind = int(sys.argv[3])
    level = int(sys.argv[4])
    wbits = int(sys.argv[5])
    data = make(seed, size, kind)
    c = zlib.compress(data, level, wbits)
    d = zlib.decompress(c, wbits)
    print(len(c), zlib.crc32(c), zlib.adler32(c), len(d), d == data)
    print(zlib.crc32(data), zlib.adler32(data), zlib.crc32(data, 123456), zlib.adler32(data, 7))
    if size < 200:
        print(c.hex())
    print(zlib.compress(data) == zlib.compress(data, -1, 15), zlib.compress(data, level) == zlib.compress(data, level, 15))

main()
"""

DEFAULTS = r"""
import zlib

def main():
    data = b"hello hello hello hello world " * 20
    c = zlib.compress(data)
    print(len(c), zlib.crc32(c), zlib.adler32(c), zlib.decompress(c) == data)
    print(zlib.crc32(b"abc"), zlib.crc32(b"abc", 7), zlib.adler32(b"abc", 5), zlib.crc32(b""), zlib.adler32(b""))
    print(zlib.decompress(zlib.compress(b"")) == b"", len(zlib.compress(b"")), zlib.compress(b"").hex())
    print(zlib.MAX_WBITS, zlib.Z_BEST_COMPRESSION, zlib.Z_BEST_SPEED, zlib.Z_DEFAULT_COMPRESSION, zlib.Z_NO_COMPRESSION)
    print(zlib.DEFLATED, zlib.DEF_MEM_LEVEL, zlib.DEF_BUF_SIZE, zlib.Z_FINISH, zlib.Z_SYNC_FLUSH)
    print(zlib.decompress(zlib.compress(data, 9, 31), 47) == data, zlib.decompress(zlib.compress(data, 1), wbits=15) == data)
    print(zlib.decompress(zlib.compress(data) + b"trailing junk") == data)
    print(zlib.decompress(zlib.compress(data), 15, 1) == data, zlib.decompress(zlib.compress(data), 15, 0) == data)

main()
"""

ERRORS = r"""
import sys
import zlib

def main():
    case = int(sys.argv[1])
    data = b"the quick brown fox jumps over the lazy dog " * 40
    good = zlib.compress(data)
    try:
        if case == 0:
            print(len(zlib.decompress(b"not zlib data")))
        elif case == 1:
            print(len(zlib.decompress(good[:len(good) - 3])))
        elif case == 2:
            print(len(zlib.decompress(good[:2])))
        elif case == 3:
            raw = zlib.compress(data, 6, -15)
            print(len(zlib.decompress(raw, 15)))
        elif case == 4:
            print(len(zlib.compress(data, 10)))
        elif case == 5:
            print(len(zlib.compress(data, -2)))
        elif case == 6:
            print(len(zlib.compress(data, 6, 100)))
        elif case == 7:
            print(len(zlib.decompress(good, 100)))
        elif case == 8:
            print(len(zlib.decompress(b"")))
        elif case == 9:
            print(len(zlib.decompress(zlib.compress(data, 6, 31), 15)))
        elif case == 10:
            print(len(zlib.decompress(good, 15, -1)))
        elif case == 11:
            bad = bytearray(good)
            bad[len(bad) // 2] = bad[len(bad) // 2] ^ 255
            print(len(zlib.decompress(bytes(bad))))
        elif case == 12:
            bad = bytearray(good)
            bad[len(bad) - 1] = bad[len(bad) - 1] ^ 1
            print(len(zlib.decompress(bytes(bad))))
        elif case == 13:
            print(len(zlib.decompress(good, -15)))
        elif case == 14:
            print(len(zlib.compress(data, 6, 8)))
        else:
            print(len(zlib.decompress(good, 31)))
    except zlib.error as e:
        print("error", {MSG})
    except ValueError as e:
        print("value", {MSG})

main()
"""

FUZZ = r"""
import sys
import zlib

def main():
    cut = int(sys.argv[1])
    flip = int(sys.argv[2])
    data = b"the quick brown fox jumps over the lazy dog " * 40
    good = bytearray(zlib.compress(data))
    if flip >= 0:
        good[flip % len(good)] = good[flip % len(good)] ^ 255
    packed = bytes(good[:len(good) - cut])
    try:
        print(len(zlib.decompress(packed)))
    except zlib.error as e:
        print("error", {MSG})

main()
"""

OWN_CRC = r"""
import zlib

def crc32(data: bytes) -> int:
    total = 0
    for b in data:
        total = (total * 31 + b) % 1000003
    return total

def adler32(data: bytes) -> int:
    return len(data)

def main():
    print(crc32(b"hello"), zlib.crc32(b"hello"), adler32(b"hello"), zlib.adler32(b"hello"))

main()
"""


def compile_program(directory, name, text, *flags):
    path = Path(directory) / (name + ".py")
    path.write_text(text, encoding="utf8")
    out = Path(directory) / (name + ".out")
    if out.exists():
        out.unlink()
    env = dict(os.environ, AIL_NO_GENERAL="1")
    env.pop("PYTHONPATH", None)
    done = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "-o", str(out), *flags], cwd=directory,
                          capture_output=True, text=True, timeout=600, env=env)
    return done, out


def run_cpython(directory, name, *args):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(Path(directory) / (name + ".py")), *map(str, args)],
                          cwd=directory, capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class ZlibTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-zlib-test-")
        cls.dir = Path(cls.temp.name)
        cls.exe = {}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def build(self, name, text):
        if name not in self.exe:
            done, out = compile_program(self.dir, name, text.replace("{MSG}", "e.message"))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertNotIn("general path", done.stderr)
            # the CPython oracle: the same program with str(e)
            (self.dir / (name + "_cpy.py")).write_text(text.replace("{MSG}", "str(e)"), encoding="utf8")
            self.exe[name] = out
        return self.exe[name]

    def compare(self, name, text, *args):
        exe = self.build(name, text)
        expected = run_cpython(self.dir, name + "_cpy", *args)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        ran = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, expected.stdout, "arguments %s" % (args,))
        return ran.stdout

    def test_versions_agree(self):
        if real_zlib.ZLIB_VERSION != real_zlib.ZLIB_RUNTIME_VERSION:
            self.skipTest("CPython was built against zlib %s but runs %s" % (real_zlib.ZLIB_VERSION, real_zlib.ZLIB_RUNTIME_VERSION))
        text = ('from ail_ffi import *\n\n@extern(lib="z", header="zlib.h", symbol="zlibVersion")\n'
                'def zver() -> c_char_p: ...\n\ndef main():\n    print(zver())\n\nmain()\n')
        done, out = compile_program(self.dir, "version", text)
        self.assertEqual(done.returncode, 0, done.stderr)
        ran = subprocess.run([str(out)], capture_output=True, text=True)
        self.assertEqual(ran.stdout.strip(), real_zlib.ZLIB_RUNTIME_VERSION)

    def test_defaults_constants_and_small_inputs(self):
        out = self.compare("defaults", DEFAULTS)
        self.assertIn("True", out)
        self.assertIn("15 9 1 -1 0", out)

    def test_random_data_all_levels_and_window_sizes(self):
        generator = random.Random(20261018)
        sizes = [0, 1, 2, 3, 17, 100, 199, 4096, 65535, 65536, 65537, 200000]
        cases = []
        for level in (-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
            cases.append((generator.randrange(1, 10 ** 6), generator.choice(sizes), generator.randrange(4), level, 15))
        for wbits in (9, 10, 12, 14, 15, -9, -12, -15, 25, 31):
            cases.append((generator.randrange(1, 10 ** 6), generator.choice(sizes), generator.randrange(4),
                          generator.choice((-1, 1, 6, 9)), wbits))
        for size in sizes:
            for kind in range(4):
                cases.append((size + kind, size, kind, 6, 15))
        for case in cases:
            with self.subTest(case=case):
                self.compare("roundtrip", ROUND_TRIP, *case)

    def test_a_few_megabytes(self):
        out = self.compare("roundtrip", ROUND_TRIP, 99, 3000000, 0, 6, 15)
        self.assertTrue(out.splitlines()[0].endswith("True"))
        self.compare("roundtrip", ROUND_TRIP, 5, 3000000, 3, 9, 31)

    def test_error_messages_are_cpythons(self):
        kinds = set()
        for case in range(16):
            with self.subTest(case=case):
                out = self.compare("errors", ERRORS, case)
                kinds.add(out.split(" ")[0])
        self.assertTrue({"error", "value"} <= kinds, kinds)
        self.assertEqual(self.compare("errors", ERRORS, 0), "error Error -3 while decompressing data: incorrect header check\n")
        self.assertEqual(self.compare("errors", ERRORS, 4), "error Bad compression level\n")
        self.assertEqual(self.compare("errors", ERRORS, 10), "value bufsize must be non-negative\n")

    def test_corrupted_streams_fuzz(self):
        generator = random.Random(7)
        for _ in range(40):
            cut, flip = generator.choice((0, 0, 1, 2, 4, 9)), generator.choice((-1, 0, 1, 2, 5, 20, 40, 100))
            with self.subTest(cut=cut, flip=flip):
                self.compare("fuzz", FUZZ, cut, flip)

    def test_a_program_may_define_crc32_beside_import_zlib(self):
        out = self.compare("owncrc", OWN_CRC)
        own = 0
        for b in b"hello":
            own = (own * 31 + b) % 1000003
        self.assertEqual(out, "%d %d 5 %d\n" % (own, real_zlib.crc32(b"hello"), real_zlib.adler32(b"hello")))

    def test_no_ffi_refuses_a_program_that_imports_zlib(self):
        path = self.dir / "forbid.py"
        path.write_text(DEFAULTS, encoding="utf8")
        done = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "-o", str(self.dir / "forbid.out"), "--no-ffi"],
                              cwd=self.dir, capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("forbidden by --no-ffi", done.stderr)
        self.assertIn("zlib.py", done.stderr)

    def test_check_ffi_lists_the_zlib_declarations(self):
        path = self.dir / "listing.py"
        path.write_text(DEFAULTS, encoding="utf8")
        done = subprocess.run([sys.executable, "-B", CLI, "check", str(path), "--ffi"], cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = json.loads(done.stdout)
        names = [row["name"] for row in report["ffi"]]
        self.assertEqual(names, ["zlib_crc32", "zlib_adler32", "zglue_deflate", "zglue_inflate", "zglue_size", "zglue_take",
                                 "zglue_errmsg"])
        self.assertTrue(all(row["header_checked"] for row in report["ffi"]))

    def test_the_bundled_module_runs_under_cpython_through_the_shim(self):
        sys.path.insert(0, str(ROOT))
        try:
            spec = importlib.util.spec_from_file_location("zlib_bundled", ROOT / "stdlib" / "zlib.py")
            bundled = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bundled)
        finally:
            sys.path.remove(str(ROOT))
        generator = random.Random(3)
        for size in (0, 1, 50, 1000, 70000):
            data = generator.randbytes(size) if size < 1000 else bytes(generator.choice(b"abcd") for _ in range(size))
            for level in (-1, 0, 1, 9):
                for wbits in (15, -15, 31):
                    packed = bundled.compress(data, level, wbits)
                    self.assertEqual(packed, real_zlib.compress(data, level, wbits))
                    self.assertEqual(bundled.decompress(packed, wbits), data)
            self.assertEqual(bundled.crc32(data), real_zlib.crc32(data))
            self.assertEqual(bundled.crc32(data, 99), real_zlib.crc32(data, 99))
            self.assertEqual(bundled.adler32(data), real_zlib.adler32(data))
            self.assertEqual(bundled.adler32(data, 99), real_zlib.adler32(data, 99))
        for bad, args in ((b"nope", ()), (real_zlib.compress(b"x" * 100)[:-2], ()), (real_zlib.compress(b"x"), (100,))):
            with self.assertRaises(real_zlib.error) as expected:
                real_zlib.decompress(bad, *args)
            with self.assertRaises(RuntimeError) as got:
                bundled.decompress(bad, *args)
            self.assertEqual(str(got.exception), str(expected.exception))


if __name__ == "__main__":
    unittest.main()
