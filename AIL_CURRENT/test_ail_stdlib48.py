"""Library batch 6: `struct`, compared with CPython 3.12.

The built surface is `calcsize`, `pack`, `unpack` and `unpack_from` for a literal format string with an
explicit byte order ('<', '>' or '!') and the codes x c b B ? h H i I l L q Q s p. `calcsize` is folded at
compile time, `pack` becomes a join of per-field expressions and each format gets one generated unpack
helper with a fixed tuple annotation, so the typed path builds the programs (AIL_NO_GENERAL=1).

Every program below runs under CPython and under the compiled program (AIL_IR 0 and 1); the bytes, values
and exit status must agree. A spelling outside the surface is refused by name at compile time. The one
declared difference is AIL's 64-bit int: a Q value above 2**63-1 can be unpacked and printed, but packing
one from a negative expression can overflow where CPython would keep arbitrary precision.
"""
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import prelude_struct
import stdlib4


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900,
                           env=dict(os.environ, AIL_NO_GENERAL="1", **env))
    return built, source, exe


PROGRAM = r'''import struct


class Header:
    def __init__(self, magic: int, size: int) -> None:
        self.magic = magic
        self.size = size


def main() -> None:
    nums = [-2147483648, -32768, -129, -128, -1, 0, 1, 127, 128, 255, 256, 32767, 65535, 2147483647]
    for value in nums:
        b = struct.pack('<b', (value + 128) % 256 - 128)
        x, = struct.unpack('<b', b)
        print('b', value, b.hex(), x, len(b))
        u = struct.pack('<B', value % 256)
        y, = struct.unpack('<B', u)
        print('B', value, u.hex(), y)
    for value in nums:
        if -32768 <= value <= 32767:
            h = struct.pack('<h', value)
        else:
            h = struct.pack('<h', value % 65536 - 32768)
        hi, = struct.unpack('<h', h)
        hb = struct.pack('>H', value % 65536)
        hval, = struct.unpack('>H', hb)
        print('hH', value, h.hex(), hi, hb.hex(), hval)
    for value in [0, 1, 255, 256, 65535, 65536, 2147483647, 4294967295]:
        i = struct.pack('<I', value)
        x, = struct.unpack('<I', i)
        q = struct.pack('>Q', value)
        y, = struct.unpack('>Q', q)
        print('IQ', value, i.hex(), x, q.hex(), y)
    raw = struct.pack('<iqiq', -2, 3, -4, 5)
    m0, m1, m2, m3 = struct.unpack('<iqiq', raw)
    print('mix', raw.hex(), m0, m1, m2, m3, struct.calcsize('<iqiq'))
    raw = struct.pack('>2I4s2x?', 1, 2, b'hi', True)
    r0, r1, r2, r3 = struct.unpack('>2I4s2x?', raw)
    print(raw.hex(), r0, r1, r2.hex(), r3)
    text = struct.pack('<3s2p', b'abcdef', b'xyz')
    s, p = struct.unpack('<3s2p', text)
    print(text.hex(), s.hex(), p.hex())
    zero = struct.pack('<0s0i8x', b'hello')
    z, = struct.unpack('<0s0i8x', zero)
    print(len(zero), zero.hex(), z.hex())
    chars = struct.pack('<3c?', b'a', b'b', b'c', 0)
    c0, c1, c2, flag = struct.unpack('<3c?', chars)
    print(chars.hex(), c0.hex(), c1.hex(), c2.hex(), flag)
    padded = struct.pack('<2x3h2x', 1, -2, 3)
    h0, h1, h2 = struct.unpack('<2x3h2x', padded)
    print(padded.hex(), h0, h1, h2)
    data = b'zz' + struct.pack('<i', 123456) + b'qq'
    first, = struct.unpack_from('<i', data, 2)
    second, = struct.unpack_from('<i', data, -6)
    base = struct.pack('<2i', 7, 8) + b'\x00' * 10
    off = 0
    one, = struct.unpack_from('<i', base, off)
    off = 4
    two, = struct.unpack_from('<i', base, off)
    print(first, second, one, two)

    header = Header(0x4d5a, 4096)
    fields = {'flags': 7}
    values = [header.magic, header.size]
    blob = struct.pack('<2H', *values)
    print(blob.hex())
    blob = struct.pack('<H', header.magic)
    print(blob.hex())
    blob = struct.pack('<I', fields['flags'])
    print(blob.hex())
    built = struct.pack('<HI', header.magic, header.size) + struct.pack('<H', fields['flags'])
    magic, size, flags = struct.unpack('<HIH', built)
    print(built.hex(), magic, size, flags)
    args = [1, 2, 3]
    print(struct.pack('<3h', *args).hex())
    print(struct.calcsize('<3h2xQI'), struct.calcsize('<i h'), struct.pack('').hex(), struct.calcsize(''))


main()
'''

REFUSALS = {
    'float': ("import struct\nprint(struct.pack('<f', 1.5))\n", "format code 'f'"),
    'native order': ("import struct\nprint(struct.pack('i', 1))\n", "explicit byte order"),
    'native code': ("import struct\nprint(struct.pack('<n', 1))\n", "only valid in native mode"),
    'non-literal': ("import struct\nFMT = '<i'\nprint(struct.pack(FMT, 1))\n", "literal string"),
    'Struct': ("import struct\ns = struct.Struct('<i')\nprint(s.pack(1))\n", "struct.Struct is not built"),
    'pack_into': ("import struct\nbuf = bytearray(4)\nstruct.pack_into('<i', buf, 0, 1)\n", "struct.pack_into is not built"),
    'empty unpack': ("import struct\nprint(struct.unpack('', b''))\n", "format with no values"),
    'bad code': ("import struct\nprint(struct.pack('<z', 1))\n", "format code 'z' is not built"),
    'count space': ("import struct\nprint(struct.calcsize('< 2 i'))\n", 'whitespace between a repeat count'),
    'zero p unpack': ("import struct\nprint(struct.unpack('<0p', b''))\n", "'p' field with a zero count"),
}


class Prelude(unittest.TestCase):
    def test_scalar_helpers_match_struct(self):
        for value in (b'', b'a', b'ab', b'abcdef'):
            for count in (0, 1, 2, 4, 8):
                self.assertEqual(prelude_struct._ail_struct_pack_s(value, count), struct.pack('<%ds' % count, value))
                self.assertEqual(prelude_struct._ail_struct_pack_p(value, count), struct.pack('<%dp' % count, value))
        for value in (b'a', b'\x00', b'\xff'):
            self.assertEqual(prelude_struct._ail_struct_pack_c(value), struct.pack('<c', value))
        for value in (False, True, 0, 1, 7, ''):
            self.assertEqual(prelude_struct._ail_struct_bool(bool(value)),
                             struct.pack('<?', bool(value)))
        self.assertEqual(prelude_struct._ail_struct_arity(3, 3), b'')
        for value, size, signed, code in ((True, 1, False, 'B'), (-1, 4, True, 'i'),
                                          (4294967295, 4, False, 'I'), (0, 1, False, 'b')):
            self.assertEqual(prelude_struct._ail_struct_int_bytes(value, size, 'little', signed, code),
                             struct.pack('<' + code, value))
        for bad in (1.5, '5', None):
            with self.assertRaises(ValueError):
                prelude_struct._ail_struct_int_bytes(bad, 4, 'little', True, 'i')
        with self.assertRaises(ValueError):
            prelude_struct._ail_struct_int_bytes(-1, 4, 'little', False, 'I')


class Compiled(unittest.TestCase):
    def test_program_matches_cpython(self):
        for ir in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                built, source, exe = compile_python(directory, PROGRAM, "p", AIL_IR="1" if ir else "0")
                self.assertEqual(built.returncode, 0, "%s%s" % (built.stdout, built.stderr))
                oracle = Path(directory, "oracle.py")
                oracle.write_text(PROGRAM, encoding="utf-8")
                want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, got.stderr[-500:])
                self.assertEqual(got.stdout, want.stdout)

    def test_default_path_also_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, PROGRAM, "default")
            self.assertEqual(built.returncode, 0, "%s%s" % (built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(PROGRAM, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.stdout, want.stdout)

    def test_bad_values_and_buffer_lengths_stop(self):
        programs = {
            'float value': "import struct\nprint(struct.pack('<i', 3.9).hex())\n",
            'string value': "import struct\nprint(struct.pack('<i', '5').hex())\n",
            'negative unsigned': "import struct\nprint(struct.pack('<I', -1).hex())\n",
            'long unpack buffer': "import struct\nprint(struct.unpack('<i', b'abcde'))\n",
        }
        for name, text in programs.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                built, source, exe = compile_python(directory, text, "bad")
                if built.returncode != 0:
                    continue
                got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                self.assertNotEqual(got.returncode, 0, "ran but should stop: " + name)

    def test_refusals_name_the_use(self):
        for name, (text, wanted) in REFUSALS.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                built, source, exe = compile_python(directory, text, "refused")
                self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + name)
                self.assertIn(wanted, built.stdout + built.stderr)
                self.assertFalse(exe.exists())

    def test_unused_module_text_is_unchanged(self):
        text = "def main() -> None:\n    print('struct is only a word here')\n\nmain()\n"
        self.assertIs(stdlib4.rewrite_text(text, []), text)


if __name__ == "__main__":
    unittest.main()
