"""Library batch 36: `struct` (stdlib/struct.py), compared with CPython 3.12.

The module is AIL source in `stdlib/struct.py`, so `import struct` in a compiled program finds it
last, after the program's own directory and modules, exactly where `zlib` lives. CPython runs the
same program with its own `struct`; both builds (`AIL_IR=0` and `AIL_IR=1`) must print the same
bytes. The cases cover every integer width and endianness, native alignment, `c ? x s p`, the three
float sizes, `calcsize`, `unpack` / `unpack_from` (including a negative offset and a buffer that is
too short), values reached through an argument, a list item, an attribute and a dict value, and
CPython's `struct.error` messages for range, type, format and length errors. `pack_into` and
`iter_unpack` are not built and are refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_python(directory, text, name, ir):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    env = dict(os.environ, AIL_IR="1" if ir else "0", AIL_NO_CACHE="1")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=env)
    return built, source, exe


FORMATS = r'''import struct


def put1(fmt: str, a: int) -> None:
    data = struct.pack(fmt, a)
    print(fmt, len(data), data.hex(), struct.calcsize(fmt), struct.unpack(fmt, data))


def put2(fmt: str, a: int, b: int) -> None:
    data = struct.pack(fmt, a, b)
    print(fmt, data.hex(), struct.unpack(fmt, data))


def put3(fmt: str, a: int, b: int, c: int) -> None:
    data = struct.pack(fmt, a, b, c)
    print(fmt, data.hex(), struct.unpack(fmt, data))


def put2f(fmt: str, a: float, b: float) -> None:
    data = struct.pack(fmt, a, b)
    print(fmt, data.hex(), struct.calcsize(fmt), struct.unpack(fmt, data))


def putbc(fmt: str, a: bool, b: bytes) -> None:
    data = struct.pack(fmt, a, b)
    print(fmt, data.hex(), struct.unpack(fmt, data))


def putb2(fmt: str, a: bool, b: bool) -> None:
    data = struct.pack(fmt, a, b)
    print(fmt, data.hex(), struct.unpack(fmt, data))


def putstr(fmt: str, a: bytes) -> None:
    data = struct.pack(fmt, a)
    print(fmt, data.hex(), struct.calcsize(fmt), struct.unpack(fmt, data))


def putpad(fmt: str) -> None:
    data = struct.pack(fmt)
    print(fmt, data.hex(), struct.calcsize(fmt), struct.unpack(fmt, data))


def putpack(fmt: str, a: bytes) -> None:
    data = struct.pack(fmt, a)
    print(fmt, data.hex(), struct.calcsize(fmt))


def sweep(fmt: str, values: list[int]) -> None:
    for value in values:
        try:
            data = struct.pack(fmt, value)
            print(fmt, value, data.hex(), struct.unpack(fmt, data)[0])
        except struct.error as error:
            print(fmt, value, "error", str(error))


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


def through(fmt: str, value: int) -> bytes:
    return struct.pack(fmt, value)


def main() -> None:
    print(struct.calcsize(""), struct.calcsize(" "), struct.calcsize("@"))
    print(struct.calcsize(">I"), struct.calcsize("<q"), struct.calcsize("@bi"), struct.calcsize("@bh"),
          struct.calcsize("@bq"), struct.calcsize("@ci"), struct.calcsize("@biq"), struct.calcsize("P"))
    print(struct.calcsize("<3s"), struct.calcsize("<3p"), struct.calcsize("<4x"), struct.calcsize("<2?"),
          struct.calcsize("@cq"), struct.calcsize("<HHIQQQIHHHHHH"))
    put1(">I", 1)
    put1("<q", -2)
    put1("<h", -32768)
    put1(">H", 65535)
    put1("<B", 255)
    put1("<b", -128)
    put1("<I", 4294967295)
    put1("<q", -9223372036854775808)
    put1("<Q", 1)
    put3("<3i", 1, -2, 3)
    put2("@bh", 1, 2)
    put2("@bi", 1, 2)
    data = struct.pack("@cq", b"a", 3)
    print("@cq", data.hex(), struct.unpack("@cq", data))
    putbc(">?c", True, b"Z")
    putb2("<2?", True, False)
    putstr("<3s", b"abcdef")
    putstr("<5s", b"ab")
    putstr("<0s", b"abcdef")
    putstr("<3s", bytearray(b"abcdef"))
    putstr("<3p", b"abcdef")
    putstr("<5p", b"ab")
    putstr("<s", b"abc")
    putpack("<0p", b"abcdef")
    putpack("<0s", b"abcdef")
    putstr("<2p", bytearray(b"abc"))
    putstr("<p", b"abc")
    putpad("<4x")
    putpad("<0x")
    put2f("<2f", 1.5, -2.25)
    put2f("<2d", 1.5, -2.25)
    put2f("<2e", 1.5, -2.25)
    put2f("@2d", -0.0, 1e-300)
    data = b"abcdefghijklmnop" + struct.pack("<HHIQQQIHHHHHH", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
    print(struct.unpack_from("<16sHHIQQQIHHHHHH", data))
    print(struct.unpack_from("<i", b"12345678", 0), struct.unpack_from("<i", b"12345678", 4),
          struct.unpack_from("<i", b"12345678", -4), struct.unpack_from("<2h", b"12345678", -4))
    values = [0, 1, -1, 127, 128, -128, -129, 255, 256, 32767, 32768, -32768, -32769,
              2147483647, 2147483648, -2147483648, -2147483649, 9223372036854775807, -9223372036854775808]
    for fmt in ("<b", ">b", "<B", ">B", "<h", ">h", "<H", ">H", "<i", ">i", "<I", ">I", "<q", ">q", "<Q", ">Q"):
        sweep(fmt, values)
    box = Box(-2)
    vals = [7, 8, 9]
    table = {"v": 10}
    print(through("<i", 5).hex(), through("<i", vals[1]).hex(), through("<i", box.value).hex(),
          through("<i", table["v"]).hex())


main()
'''

ERRORS = r'''import struct


def main() -> None:
    cases = ["<b 128", "<b -129", "<B -1", "<B 256", "<h 40000", "<H -1", "<i 2147483648",
             "<I -1", "<q 9223372036854775807", "<Q -1"]
    for case in cases:
        parts = case.split()
        try:
            struct.pack(parts[0], int(parts[1]))
            print(parts[0], "ok")
        except struct.error as error:
            print(parts[0], "error", str(error))
    for value in ("1.5", "text"):
        try:
            if value == "1.5":
                struct.pack("<i", float(value))
            else:
                struct.pack("<i", value)
        except struct.error as error:
            print("type", "error", str(error))
    try:
        struct.pack("<f", "3")
    except struct.error as error:
        print("float", "error", str(error))
    for value in (b"ab", b"", bytearray(b"a"), 65, [65], "a"):
        try:
            struct.pack("<c", value)
            print("char", "ok")
        except struct.error as error:
            print("char", "error", str(error))
    for value in ("a", 3, [97], None):
        try:
            struct.pack("<s", value)
            print("bytes", "ok")
        except struct.error as error:
            print("bytes", "error", str(error))
        try:
            struct.pack("<p", value)
            print("pascal", "ok")
        except struct.error as error:
            print("pascal", "error", str(error))
    try:
        struct.pack("<2i", 1)
    except struct.error as error:
        print("few", "error", str(error))
    try:
        struct.pack("<2i", 1, 2, 3)
    except struct.error as error:
        print("many", "error", str(error))
    try:
        struct.pack("z", 1)
    except struct.error as error:
        print("badchar", "error", str(error))
    try:
        struct.pack("0", 1)
    except struct.error as error:
        print("repeat", "error", str(error))
    try:
        struct.unpack("<i", b"ab")
    except struct.error as error:
        print("short", "error", str(error))
    try:
        struct.unpack_from("<i", b"12345678", 5)
    except struct.error as error:
        print("from", "error", str(error))
    try:
        struct.unpack_from("<i", b"12345678", -9)
    except struct.error as error:
        print("offset", "error", str(error))


main()
'''

REFUSED = '''import struct


def main() -> None:
    buffer = bytearray(8)
    struct.pack_into("<i", buffer, 0, 5)

main()
'''


class StructTests(unittest.TestCase):
    def check(self, name, text):
        for ir in (False, True):
            with self.subTest(program=name, ir=ir), tempfile.TemporaryDirectory() as directory:
                built, _, exe = compile_python(directory, text, name, ir)
                self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s"
                                 % (name, ir, built.stdout[-2000:], built.stderr[-2000:]))
                oracle = Path(directory, name + "_oracle.py")
                oracle.write_text(text, encoding="utf-8")
                want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], cwd=directory,
                                      capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=300)
                self.assertEqual(want.returncode, 0, want.stderr[-1000:])
                self.assertEqual(got.returncode, want.returncode, "%s (AIL_IR=%s): %s"
                                 % (name, ir, got.stderr[-1000:]))
                if got.stdout != want.stdout:
                    a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                    for n, (x, y) in enumerate(zip(a, b)):
                        if x != y:
                            self.fail("%s (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                                      % (name, ir, n + 1, x, y))
                    self.fail("%s (AIL_IR=%s): %d lines against %d" % (name, ir, len(a), len(b)))

    def test_formats_match_cpython(self):
        self.check("formats", FORMATS)

    def test_errors_match_cpython(self):
        self.check("errors", ERRORS)

    def test_pack_into_is_refused_by_name(self):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, REFUSED, "refused", False)
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused")
            self.assertIn("module 'struct' has no top-level name 'pack_into'", built.stdout + built.stderr)
            self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
