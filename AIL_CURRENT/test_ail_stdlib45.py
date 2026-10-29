"""Library batch 45: `struct`, lowered to prelude_struct.py by stdlib5.

The supported surface is pack, unpack, calcsize, unpack_from and pack_into over an explicit byte-order
prefix and the integer codes (b B h H i I l L q Q), x, ?, c and s. A program using it is compiled on the
default build and with AIL_UNIFIED_FORCE=1, run, and must print exactly what CPython 3.12 prints (and
exit the same way). Native alignment (no prefix or '@') and the float, Struct and iter_unpack APIs stay
named compile-time refusals.

The declared difference: `repr(struct.error)` names the prelude class `__main__.error`, while
`struct.error.__name__`, `isinstance` and the caught message match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = r'''import struct
from struct import pack, unpack, calcsize, error
import struct as st


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


def pack_it(value) -> bytes:
    return struct.pack(">I", value)


def unpack_it(data):
    return struct.unpack(">I", data)


rows = [10, 20]
d = {"x": 30}
box = Box(40)
print(calcsize(">I"), calcsize("<q"), calcsize(">2H"), calcsize(">4s"))
print(pack_it(5))
print(pack(">I", 305419896), unpack(">I", pack(">I", 305419896)))
print(struct.pack(">I", rows[1]), struct.pack(">I", d["x"]), struct.pack(">I", box.value))
print(unpack_it(b"\x00\x00\x00\x06"))
print(struct.pack("<hH", -2, 65535), struct.unpack("<hH", struct.pack("<hH", -2, 65535)))
print(struct.pack(">?c", True, b"Z"), struct.unpack(">?c", struct.pack(">?c", False, b"Q")))
print(struct.pack(">3s", b"ab"), struct.unpack(">3s", b"ab\x00"))
print(st.pack(">I", 7), st.unpack(">I", b"\x00\x00\x00\x07"), st.calcsize(">I"))
print(struct.calcsize("<I H"), struct.pack("< I\tH", 305419896, 4660), struct.unpack("> H", b"\x12\x34"))
print(struct.pack(">0I"), struct.unpack(">0I", b""), struct.calcsize(">0I"))
print(struct.pack(">"), struct.unpack(">", b""), struct.calcsize(">"))
print(struct.pack(">0s", b""), struct.unpack(">0s", b""), struct.pack(">2x"))
p = struct.pack("<b", -128)
print("<b", len(p), p, struct.unpack("<b", p))
p = struct.pack("<B", 255)
print("<B", len(p), p, struct.unpack("<B", p))
p = struct.pack("<h", -32768)
print("<h", len(p), p, struct.unpack("<h", p))
p = struct.pack("<H", 65535)
print("<H", len(p), p, struct.unpack("<H", p))
p = struct.pack("<i", -2147483648)
print("<i", len(p), p, struct.unpack("<i", p))
p = struct.pack("<I", 4294967295)
print("<I", len(p), p, struct.unpack("<I", p))
p = struct.pack("<l", -2147483648)
print("<l", len(p), p, struct.unpack("<l", p))
p = struct.pack("<L", 4294967295)
print("<L", len(p), p, struct.unpack("<L", p))
p = struct.pack("<q", -9223372036854775808)
print("<q", len(p), p, struct.unpack("<q", p))
p = struct.pack("<Q", 9223372036854775807)
print("<Q", len(p), p, struct.unpack("<Q", p))
print(struct.unpack(">bBhHiIlLqQ", bytes([255] * 38)))
print(struct.unpack_from(">H", b"12345678", -2), struct.unpack_from(">H", b"\x00\x01\x02\x03", 1))
buf = bytearray(8)
struct.pack_into(">HH", buf, 2, 258, 772)
print(buf, struct.unpack(">xHxH", bytes(buf[2:8])))
buf = bytearray(8)
struct.pack_into(">I", buf, -4, 16909060)
print(buf)
try:
    struct.unpack(">I", b"\x00")
except error:
    print("struct error caught")
try:
    struct.pack(">B", 300)
except struct.error:
    print("range caught")
for data, offset in ((b"123", 2), (b"123", 5), (b"123", -5), (b"1", -1)):
    try:
        print(struct.unpack_from(">H", data, offset))
    except struct.error as exc:
        print(type(exc).__name__, str(exc))
for offset in (2, -5):
    try:
        struct.pack_into(">I", bytearray(4), offset, 1)
    except struct.error as exc:
        print(type(exc).__name__, str(exc))
try:
    struct.pack_into(">I", b"abcd", 0, 1)
except TypeError as exc:
    print("TypeError", str(exc))
try:
    struct.pack(">c", bytearray(b"a"))
except struct.error as exc:
    print(type(exc).__name__, str(exc))
try:
    struct.pack(">2s")
except struct.error as exc:
    print(type(exc).__name__, str(exc))
try:
    struct.pack(">0s")
except struct.error as exc:
    print(type(exc).__name__, str(exc))
try:
    struct.unpack(">H", "ab")
except TypeError as exc:
    print("TypeError", str(exc))
for data, offset in ((b"", -1), (b"abc", -3), (b"abcd", -4), (b"abcd", -5), (b"abc", -5)):
    try:
        print(struct.unpack_from(">I", data, offset))
    except struct.error as exc:
        print(type(exc).__name__, str(exc))
for size, offset in ((1, -1), (4, -4), (4, -5), (4, 5), (0, 0), (0, -1)):
    try:
        struct.pack_into(">I", bytearray(size), offset, 1)
        print("packed")
    except struct.error as exc:
        print(type(exc).__name__, str(exc))
try:
    struct.pack_into(">2H", bytearray(4), 0, 1)
except struct.error as exc:
    print(type(exc).__name__, str(exc))
try:
    struct.pack_into(">2H", b"abcd", 0, 1)
except struct.error as exc:
    print(type(exc).__name__, str(exc))
try:
    struct.pack_into(">2H", b"abcd", 0, 1, 2)
except TypeError as exc:
    print("TypeError", str(exc))
try:
    struct.pack(">I", "x", 2)
except struct.error as exc:
    print(type(exc).__name__, str(exc))
try:
    struct.pack(">BI", 300)
except struct.error as exc:
    print(type(exc).__name__, str(exc))
try:
    struct.pack_into(">I", bytearray(0), 0, "x")
except struct.error as exc:
    print(type(exc).__name__, str(exc))
'''

NAMESPACE_PROGRAM = r'''import struct
from struct import error as struct_error


class error(Exception):
    def __init__(self, value: int) -> None:
        self.value = value


try:
    raise error(5)
except error as exc:
    print("user", type(exc).__name__, exc.value)
try:
    struct.pack(">B", 300)
except error:
    print("WRONG user class caught a struct error")
except struct_error as exc:
    print("struct", type(exc).__name__, str(exc))
try:
    raise error(6)
except struct_error:
    print("WRONG struct class caught a user error")
except error as exc:
    print("user2", type(exc).__name__, exc.value)
print(error.__name__, struct_error.__name__)
try:
    print(_ail_st_calcsize)
except NameError as exc:
    print("hidden calcsize", type(exc).__name__, str(exc))
try:
    print(_ail_st_pack)
except NameError as exc:
    print("hidden pack", type(exc).__name__, str(exc))
'''

HIDDEN_PROGRAM = r'''import struct
print(struct.calcsize(">I"))
try:
    print(error)
except NameError as exc:
    print("hidden error", type(exc).__name__, str(exc))
try:
    print(_ail_st_calcsize)
except NameError as exc:
    print("hidden calcsize", type(exc).__name__, str(exc))
try:
    print(_ail_st_codes)
except NameError as exc:
    print("hidden codes", type(exc).__name__, str(exc))
try:
    print(_ail_st_error_type)
except NameError as exc:
    print("hidden error_type", type(exc).__name__, str(exc))
print(struct.pack(">I", 7))
'''


def environment(**extra):
    env = {name: value for name, value in os.environ.items() if not name.startswith("AIL_")}
    env.update(extra)
    return env


def compile_python(directory, text, name, **extra):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=environment(**extra))
    return built, source, exe


class CompiledStruct(unittest.TestCase):
    def check(self, label, **extra):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, PROGRAM, "p_struct", **extra)
            self.assertEqual(built.returncode, 0, "%s\n%s%s" % (label, built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(PROGRAM, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s\n%s" % (label, got.stderr[-500:]))
            if got.stdout != want.stdout:
                a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                for n, (x, y) in enumerate(zip(a, b)):
                    if x != y:
                        self.fail("%s line %d:\n  compiled: %r\n  CPython:  %r" % (label, n + 1, x, y))
                self.fail("%s: %d lines against %d" % (label, len(a), len(b)))

    def test_default_build(self):
        self.check("default")

    def test_general_build(self):
        self.check("general", AIL_UNIFIED_FORCE="1")

    def check_program(self, label, program, **extra):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, program, "p_struct", **extra)
            self.assertEqual(built.returncode, 0, "%s\n%s%s" % (label, built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(program, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s\n%s" % (label, got.stderr[-500:]))
            self.assertEqual(got.stdout, want.stdout, label)

    def test_namespace_and_user_error_class(self):
        self.check_program("namespace", NAMESPACE_PROGRAM)
        self.check_program("namespace general", NAMESPACE_PROGRAM, AIL_UNIFIED_FORCE="1")

    def test_internal_names_are_hidden(self):
        self.check_program("hidden", HIDDEN_PROGRAM)
        self.check_program("hidden general", HIDDEN_PROGRAM, AIL_UNIFIED_FORCE="1")


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused", AIL_UNIFIED_FORCE="1")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_unsupported_uses_are_named(self):
        cases = {
            "float": ("import struct\n\nprint(struct.pack('<f', 1.5))\n", "format code 'f' is not built"),
            "struct_class": ("import struct\n\ns = struct.Struct('>I')\nprint(s.size)\n", "struct.Struct"),
            "native": ("import struct\n\nprint(struct.calcsize('I'))\n", "must start with"),
            "dynamic_format": ("import struct\n\nfmt = '>I'\nprint(struct.pack(fmt, 1))\n",
                               "format string must be a literal string"),
            "keywords": ("import struct\n\nprint(struct.calcsize(fmt='>I'))\n",
                         "does not take keyword arguments"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


if __name__ == "__main__":
    unittest.main()
