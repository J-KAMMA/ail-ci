"""Library batch 11: struct.pack / unpack / pack_into / unpack_from / calcsize, compared with CPython 3.12.

The prelude_struct.py helpers are plain Python; the program below is compiled once with AIL_IR=0 and once with
AIL_IR=1, run, and must print exactly CPython's bytes and exit status.  It covers every built code (signed and
unsigned integers of every width, bool, char, s, p, x pad, native alignment with @ and =, standard < > !),
empty and zero-count formats, negative and out-of-range values, an offset error and a short buffer (struct.error
is RuntimeError in the compiled program -- DIFFERENCES.md), pack_into / unpack_from on a bytearray whose earlier
bytes are read again (aliasing), and values passed as an argument, a list item, an attribute and a dict value.

Formats are checked by CPython's own struct at compile time.  A format known only at run time, Struct /
iter_unpack / float32 / half floats / doubles, keyword and starred arguments, and every other module attribute
are refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


PROGRAM = r"""import struct


class Box:
    def __init__(self, number: int) -> None:
        self.number = number


def pack_value(value: int) -> bytes:
    return struct.pack('<i', value)


def pack_box(box: Box) -> bytes:
    return struct.pack('<i', box.number)


def offset() -> int:
    return 2


def failures() -> None:
    try:
        struct.pack('>B', 300)
        print('pack no error')
    except struct.error:
        print('pack range')
    try:
        struct.unpack('>I', b'\x00')
        print('unpack no error')
    except struct.error:
        print('unpack short')
    try:
        struct.pack_into('>I', bytearray(2), 0, 1)
        print('into no error')
    except struct.error:
        print('into short')
    try:
        struct.unpack_from('>I', b'\x00\x00\x00\x01', -1)
        print('offset no error')
    except struct.error:
        print('offset negative')
    try:
        struct.pack('0s', 'x')
        print('zero s no error')
    except struct.error:
        print('zero s text')


def main() -> None:
    data = struct.pack('>bBhHiIlLqQ', -1, 255, -2, 65535, -3, 4000000000, -4, 3000000000, -5, 9000000000000000000)
    print(list(data))
    print(struct.unpack('>bBhHiIlLqQ', data))
    print(list(struct.pack('<bBhHiIlLqQ', -1, 255, -2, 65535, -3, 4000000000, -4, 3000000000, -5, 9000000000000000000)))
    print(struct.calcsize('>bBhHiIlLqQ'), struct.calcsize(''), struct.calcsize('@ci'), struct.calcsize('@0i'))
    print(list(struct.pack('')), struct.unpack('', b''))
    print(list(struct.pack('0s', b'')), struct.unpack('0s', b''))
    print(list(struct.pack('<2xI4x', 287454020)), struct.unpack('<2xI4x', struct.pack('<2xI4x', 287454020)))
    print(list(struct.pack('<3s', b'ab')), struct.unpack('<3s', struct.pack('<3s', b'ab')))
    print(list(struct.pack('<6p', b'hello')), struct.unpack('<6p', struct.pack('<6p', b'hello')))
    print(list(struct.pack('<6p', b'123456789')), struct.unpack('<6p', struct.pack('<6p', b'123456789')))
    print(list(struct.pack('<3c', b'a', b'b', b'c')), struct.unpack('<3c', struct.pack('<3c', b'a', b'b', b'c')))
    print(list(struct.pack('<?b?', True, -1, False)), struct.unpack('<?b?', struct.pack('<?b?', True, -1, False)))
    print(list(struct.pack('@2ci', b'a', b'b', 9)), struct.unpack('@2ci', struct.pack('@2ci', b'a', b'b', 9)))
    print(list(struct.pack('>3s2H', b'xyz', 1, 2)), struct.unpack('>3s2H', struct.pack('>3s2H', b'xyz', 1, 2)))
    buf = bytearray(20)
    struct.pack_into('<I', buf, 4, 287454020)
    struct.pack_into('>H', buf, 0, 4660)
    print(list(buf))
    print(struct.unpack_from('<I', buf, 4), struct.unpack_from('<2H', buf, 4), struct.unpack_from('>H', buf, 0))
    first = struct.unpack_from('<I', buf, 4)[0]
    struct.pack_into('<I', buf, 4, first + 1)
    print(struct.unpack_from('<I', buf, 4))
    buf2 = bytearray(12)
    struct.pack_into('<I', buf2, offset(), 7)
    print(list(buf2), struct.unpack_from('<I', buf2, offset()))
    print(list(pack_value(-3)), struct.unpack('<i', pack_value(1234)))
    print(list(struct.pack('<i', [10, 20][1])), list(pack_box(Box(99))))
    values = {'x': -7}
    print(list(struct.pack('<i', values['x'])))
    print(list(struct.pack('<2i', [5, -6][0], [5, -6][1])))
    failures()


main()
"""


class StructPrograms(unittest.TestCase):
    def test_matches_cpython_both_builds(self):
        for ir in ("0", "1"):
            with self.subTest(ir=ir), tempfile.TemporaryDirectory() as directory:
                built, _, exe = compile_python(directory, PROGRAM, "p_struct", AIL_IR=ir)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                oracle = Path(directory, "oracle.py")
                oracle.write_text(PROGRAM, encoding="utf-8")
                want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, got.stderr[-300:])
                self.assertEqual(got.stdout, want.stdout)


class StructRefusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            "struct_class": ("import struct\n\ns = struct.Struct('>I')\nprint(s.size)\n", "struct.Struct"),
            "dynamic_format": ("import struct\n\nfmt = '>I'\nprint(struct.pack(fmt, 1))\n", "string literal"),
            "double": ("import struct\n\nprint(struct.pack('<d', 1.0))\n", "double floats (d)"),
            "float32": ("import struct\n\nprint(struct.pack('<f', 1.0))\n", "float32 (f)"),
            "keyword": ("import struct\n\nprint(struct.unpack(data=b'\\x00\\x00\\x00\\x01', format='>I'))\n",
                        "keyword arguments"),
            "iter_unpack": ("import struct\n\nfor item in struct.iter_unpack('>I', b'\\x00\\x00\\x00\\x01'):\n"
                            "    print(item)\n", "struct.iter_unpack"),
            "from_import": ("from struct import Struct\n\ns = Struct('>I')\nprint(s.size)\n", "struct.Struct"),
            "zero_p": ("import struct\n\nprint(struct.unpack('0p', b''))\n", "zero-size p"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


if __name__ == "__main__":
    unittest.main()
