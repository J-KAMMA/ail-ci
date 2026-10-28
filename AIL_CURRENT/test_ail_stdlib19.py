"""Library batch 6: `struct` pack / unpack / unpack_from / calcsize, compared with CPython 3.12.

The prelude is plain Python, so its parser and encoder run next to CPython's `struct` on generated formats
(including the native '@' alignment, zero repeat counts, bytes formats, bytearray buffers, negative offsets and
the bytes / chars / bools). The compiled program below uses the same calls through the compiler, once with the
default build and once with AIL_IR=1. A constant float format and a computed unpack format are refused by name.
"""
import os
import random
import struct as pystruct
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


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, **env))
    return built, source, exe


PROGRAM = r"""import struct
import sys


class Index:
    def __index__(self) -> int:
        return 7


def main() -> None:
    print(struct.pack('<b', Index()).hex())
    print(struct.pack('>I', 0x01020304).hex())
    print(struct.pack('<q', -2).hex())
    print(struct.pack('=l', 1).hex(), struct.pack('@l', 1).hex())
    print(struct.pack('@bi', 1, 2).hex(), struct.calcsize('@bi'))
    print(struct.pack('@bhi', 1, 2, 3).hex(), struct.pack('@bh0qi', 1, 2, 3).hex())
    print(struct.pack('@b0h', 1).hex(), struct.pack('@b0hs', 1, b'z').hex(), struct.calcsize('@b0hs'))
    print(struct.calcsize('<16sHHIQQQIHHHHHH'), struct.calcsize('P'))
    print(struct.calcsize(b'<I'), struct.pack(b'<I', 9).hex())
    print(struct.unpack(b'<I', struct.pack(b'<I', 9)))
    data = struct.pack('<2sBH', b'abc', 7, 300)
    print(data.hex(), struct.unpack('<2sBH', data))
    print(struct.unpack_from('<H', b'xx\x01\x02', 2), struct.unpack_from('<H', b'abc', -2))
    print(struct.pack('0s4s', b'abc', bytearray(b'abcd')).hex())
    print(struct.unpack('<2s', bytearray(b'ab')), struct.unpack_from('<2c', bytearray(b'xxab'), 2))
    print(struct.unpack_from('0s', b'abc', -1), struct.unpack('', b''), struct.pack('').hex())
    one = struct.unpack('<I', struct.pack('<I', 513))
    print(one, type(one).__name__)
    print(struct.pack('>2c', b'a', b'b'), struct.unpack('>2c', b'ab'))
    print(struct.pack('<?', 2), struct.unpack('<?', b'\x01'))
    values = [int(t) for t in sys.stdin.read().split()]
    if values:
        blob = struct.pack('<' + 'q' * len(values), *values)
        print(blob.hex())
    for fmt, value in (('<B', 256), ('<b', -129), ('<h', 32768)):
        try:
            struct.pack(fmt, value)
        except struct.error as error:
            print(str(error))
    try:
        struct.unpack('<I', b'x')
    except struct.error as error:
        print(str(error))
    try:
        struct.unpack_from('<I', b'xx', 1)
    except struct.error as error:
        print(str(error))
    for offset in (-3, -5):
        try:
            struct.unpack_from('<I', b'xx', offset)
        except struct.error as error:
            print(str(error))


main()
"""


class PreludeStruct(unittest.TestCase):
    CODES = [('b', -128, 127), ('B', 0, 255), ('h', -32768, 32767), ('H', 0, 65535),
             ('i', -2147483648, 2147483647), ('I', 0, 4294967295), ('l', -2147483648, 2147483647),
             ('L', 0, 4294967295), ('q', -9223372036854775808, 9223372036854775807),
             ('Q', 0, 18446744073709551615), ('n', -9223372036854775808, 9223372036854775807),
             ('N', 0, 18446744073709551615), ('P', 0, 18446744073709551615)]

    def test_generated_formats_match_cpython(self):
        rng = random.Random(1906)
        for _ in range(600):
            prefix = rng.choice('@=<>!')
            parts = [prefix]
            values = []
            for _ in range(rng.randint(0, 5)):
                kind = rng.choice('int s c ? x')
                if kind == 'int':
                    code, low, high = rng.choice(self.CODES)
                    if prefix != '@' and code in 'nNP':
                        code = rng.choice('iIqQ')
                        low, high = (-2147483648, 2147483647) if code in 'iq' else (0, 4294967295)
                    count = rng.randint(0, 3)
                    parts.append((str(count) if count != 1 else '') + code)
                    values.extend(rng.randint(low, high) for _ in range(count))
                elif kind == 's':
                    count = rng.randint(0, 5)
                    parts.append((str(count) if count != 1 else '') + 's')
                    values.append(bytes(rng.randrange(256) for _ in range(rng.randint(0, 7))))
                elif kind == 'c':
                    count = rng.randint(0, 3)
                    parts.append((str(count) if count != 1 else '') + 'c')
                    values.extend(bytes([rng.randrange(256)]) for _ in range(count))
                elif kind == '?':
                    count = rng.randint(0, 3)
                    parts.append((str(count) if count != 1 else '') + '?')
                    values.extend(rng.choice((True, False, 0, 1, 7)) for _ in range(count))
                else:
                    count = rng.randint(0, 4)
                    parts.append((str(count) if count != 1 else '') + 'x')
            fmt = ''.join(parts)
            produced = pystruct.pack(fmt, *values)
            mine = bytes(prelude_struct._ail_struct_pack_list(fmt, values))
            self.assertEqual(mine, produced, fmt)
            self.assertEqual(prelude_struct._ail_struct_calcsize(fmt), pystruct.calcsize(fmt), fmt)
            self.assertEqual(tuple(prelude_struct._ail_struct_unpack_list(fmt, produced)),
                             pystruct.unpack(fmt, produced), fmt)
            offset = rng.randint(0, 3)
            padded = b'x' * offset + produced + b'y'
            self.assertEqual(tuple(prelude_struct._ail_struct_unpack_from_list(fmt, padded, offset)),
                             pystruct.unpack_from(fmt, padded, offset), fmt)

    def test_zero_counts_offsets_and_buffer_types(self):
        for fmt, values in [('@b0h', (1,)), ('@b0hs', (1, b'z')), ('@bhi0q', (1, 2, 3)),
                            ('@bi0i', (1, 2)), ('@b0c', (1,)), ('@b0?', (1,)), ('@b0s', (1, b'x')),
                            ('@0s', (b'',))]:
            produced = pystruct.pack(fmt, *values)
            self.assertEqual(bytes(prelude_struct._ail_struct_pack_list(fmt, values)), produced, fmt)
            self.assertEqual(prelude_struct._ail_struct_calcsize(fmt), pystruct.calcsize(fmt), fmt)
            self.assertEqual(tuple(prelude_struct._ail_struct_unpack_list(fmt, produced)),
                             pystruct.unpack(fmt, produced), fmt)
        self.assertEqual(bytes(prelude_struct._ail_struct_pack_list('<4s', [bytearray(b'abcd')])),
                         pystruct.pack('<4s', bytearray(b'abcd')))
        for fmt, data in (('<4s', bytearray(b'abcd')), ('<2c', bytearray(b'ab')),
                          ('<I', bytearray(b'\x01\x02\x03\x04'))):
            self.assertEqual(tuple(prelude_struct._ail_struct_unpack_list(fmt, data)),
                             pystruct.unpack(fmt, data), fmt)
        self.assertEqual(bytes(prelude_struct._ail_struct_pack_list(b'@b0hs', [1, b'z'])),
                         pystruct.pack(b'@b0hs', 1, b'z'))
        for bad in (123, None):
            with self.assertRaises(TypeError):
                prelude_struct._ail_struct_calcsize(bad)
        data = b'abc\x01\x02'
        for offset in (-6, -5, -4, -3, -2, -1, 0, 1, 2, 3):
            for fmt in ('<I', '<H', '0s', ''):
                try:
                    want = ('ok', pystruct.unpack_from(fmt, data, offset))
                except pystruct.error as error:
                    want = ('error', str(error))
                try:
                    got = ('ok', tuple(prelude_struct._ail_struct_unpack_from_list(fmt, data, offset)))
                except prelude_struct._AilStructError as error:
                    got = ('error', str(error))
                self.assertEqual(got, want, (fmt, offset))


class CompiledStruct(unittest.TestCase):
    def test_program_matches_cpython(self):
        inputs = [b'7 -3 0\n', b'\n']
        for ir in (False, True):
            with self.subTest(ir=ir), tempfile.TemporaryDirectory() as directory:
                built, _, exe = compile_python(directory, PROGRAM, 'p', AIL_IR='1' if ir else '0')
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                oracle = Path(directory, 'oracle.py')
                oracle.write_text(PROGRAM, encoding='utf-8')
                for data in inputs:
                    want = subprocess.run([sys.executable, str(oracle)], input=data, capture_output=True, timeout=300)
                    got = subprocess.run([str(exe)], input=data, capture_output=True, timeout=300)
                    self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout),
                                     got.stderr[-500:])

    def test_float_and_computed_unpack_are_refused(self):
        cases = {
            'float': ("import struct\n\nprint(struct.pack('<d', 1.5))\n", 'floating point'),
            'computed': ("import struct\n\nfmt = '<I' + 'I'\nprint(struct.unpack(fmt, b'12345678'))\n",
                         'format must be written'),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                built, _, exe = compile_python(directory, text, 'refused')
                self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                self.assertIn(wanted, built.stdout + built.stderr)
                self.assertFalse(exe.exists())


if __name__ == '__main__':
    unittest.main()
