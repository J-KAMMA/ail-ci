"""Library: `struct` pack / unpack / calcsize, compared with CPython 3.12.

A literal format with an explicit byte-order prefix (<, >, ! or =) and the codes x, c, b, B, h, H, i, I,
l, L, q, Q, s and ? is lowered to bytearray / int.to_bytes() / int.from_bytes(). The native layout (@, or
no prefix), the float codes e/f/d, p/n/N/P, a computed format string and unpack_from / pack_into / Struct /
iter_unpack are refused by name at compile time.

The default build is compared on AIL_IR=0 and 1. A pack/calcsize program is also compiled with
AIL_NO_GENERAL=1, so the typed path must take the lowering without the general path.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = r'''import struct
import struct as st
from struct import pack as sp, unpack as su, calcsize as sc, error as Bad


def main() -> None:
    print(struct.pack(">I", 305419896).hex(), struct.calcsize(">I"))
    print(struct.pack("<I", 305419896).hex(), struct.pack("!I", 305419896).hex())
    print(struct.pack("=I", 305419896).hex())
    print(struct.pack(">bBhHiIlLqQ", -1, 255, -2, 65535, -3, 4294967295, -4,
                      4294967295, -5, 7).hex())
    u = struct.unpack(">bBhHiIlLqQ", struct.pack(">bBhHiIlLqQ", -1, 255, -2, 65535, -3,
                                                4294967295, -4, 4294967295, -5, 7))
    print(u)
    print(struct.pack(">qQ", -1234567890123456789, 9223372036854775807).hex())
    print(struct.pack(">2I", 1, 4294967295).hex(), struct.calcsize(">2I"))
    print(struct.unpack(">2I", b"\x00\x00\x00\x01\xff\xff\xff\xff"))
    print(struct.pack(">4xH", 4660).hex(), struct.calcsize(">4xH"))
    print(struct.unpack(">4xH", b"abcd\x12\x34"))
    print(struct.pack(">c3s2s", b"A", b"hello", b"x").hex(), struct.calcsize(">c3s2s"))
    print(struct.unpack(">c3s2s", b"Ahelxy"))
    print(struct.pack(">???", True, False, 7).hex())
    print(struct.unpack(">???", b"\x01\x00\x02"))
    print(struct.pack("> H 2s", 258, b"ab").hex(), struct.calcsize("> H 2s"))
    print(struct.pack(">0I").hex(), struct.calcsize(">0I"))
    print(struct.pack(">0s", b"abc").hex(), struct.unpack(">0s", b""))
    print(struct.pack(">0x").hex(), struct.unpack(">0x", b""))
    print(struct.pack(">10s", b"abc").hex())
    print(struct.unpack(">10s", b"abc\0\0\0\0\0\0\0"))
    print(struct.calcsize(">I4xH"), struct.calcsize("=q"), struct.calcsize("<2s"))
    print(struct.pack(">I", struct.calcsize(">H")).hex())
    print(st.pack("<H", 258).hex(), sp("<H", 258).hex())
    print(su("<H", b"\x02\x01"), sc("<H"))
    try:
        struct.pack(">I", -1)
    except struct.error as e:
        print("E1", str(e))
    try:
        struct.pack(">I", 4294967296)
    except struct.error as e:
        print("E2", str(e))
    try:
        struct.pack(">B", 256)
    except struct.error as e:
        print("E3", str(e))
    try:
        struct.pack(">b", 128)
    except struct.error as e:
        print("E4", str(e))
    try:
        struct.pack(">Q", -1)
    except struct.error as e:
        print("E5", str(e))
    try:
        struct.unpack(">I", b"\x00\x01")
    except struct.error as e:
        print("E6", str(e))
    try:
        struct.pack(">c", b"ab")
    except struct.error as e:
        print("E7", str(e))
    try:
        struct.unpack(">2s", b"abcd")
    except struct.error as e:
        print("E8", str(e))
    try:
        sp(">H", 70000)
    except Bad as e:
        print("E9", str(e))


main()
'''

TYPED = r'''import struct


def main() -> None:
    print(struct.pack(">I4sH", 305419896, b"abcd", 258).hex())
    print(struct.pack(">2I4x?", 1, 4294967295, True).hex())
    print(struct.pack(">c3s", b"Z", b"ab").hex())
    print(struct.calcsize(">I4xH"), struct.calcsize(">0I"), struct.calcsize(">10s"))
    try:
        struct.pack(">I", -1)
    except struct.error as e:
        print("E", str(e))


main()
'''


def compile_python(directory, text, name, ir=0, general=True):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    env = dict(os.environ, AIL_IR="1" if ir else "0")
    if not general:
        env["AIL_NO_GENERAL"] = "1"
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=env)
    return built, source, exe


def build_and_run(directory, text, name, ir):
    built, source, exe = compile_python(directory, text, name, ir)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=60), expected


class Stdlib27Tests(unittest.TestCase):
    def check(self, text, name, ir=0, general=True):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name + ("_ir" if ir else ""), ir, general)
            expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def refused(self, text, wanted, name="prog"):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, name, general=False)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())

    def test_struct_default(self):
        self.check(PROGRAM, "struct_api")

    def test_struct_ir(self):
        self.check(PROGRAM, "struct_api", ir=1)

    def test_struct_pack_on_the_typed_path(self):
        self.check(TYPED, "struct_typed", general=False)

    def test_struct_refusals_are_named(self):
        head = "import struct\n\n\ndef main() -> None:\n"
        self.refused(head + "    print(struct.pack('>d', 1.5))\n\n\nmain()\n",
                     "struct.pack: the float format character 'd' is not built")
        self.refused(head + "    print(struct.calcsize('@I'))\n\n\nmain()\n",
                     "struct.calcsize: the native layout (@) is not built")
        self.refused(head + "    print(struct.calcsize('I'))\n\n\nmain()\n",
                     "struct.calcsize: the native layout (@, or no prefix) is not built")
        self.refused(head + "    fmt = '>I'\n    print(struct.calcsize(fmt))\n\n\nmain()\n",
                     "struct.calcsize: the format must be a string literal")
        self.refused(head + "    print(struct.unpack_from('>I', b'\\x00\\x00\\x00\\x01'))\n\n\nmain()\n",
                     "struct.unpack_from used here is not built")


if __name__ == "__main__":
    unittest.main()
