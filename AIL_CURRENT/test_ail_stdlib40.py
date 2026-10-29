"""Library batch 40: struct pack/unpack/unpack_from/calcsize against CPython 3.12.

Each program is ordinary Python. CPython runs it as the oracle; the compiled program runs it on the
typed path (AIL_NO_GENERAL=1) and on the forced general path (AIL_UNIFIED_FORCE=1), and both must print
the same bytes with the same exit code. The formats are literals: byte-order and native alignment,
the integer codes b B h H i I l L q Q n N P, x padding, repeats, unpack_from with an offset,
bytearray buffers, import aliases and `struct.error` are covered. Float, pascal, char, bool and
string formats, the Struct class, pack_into, a format that is not a literal, an unpack of a format
with no values and a literal non-bytes buffer are refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

BASIC = '''import struct


def main() -> None:
    print(struct.calcsize('<bBhHiIlLqQx'))
    data = struct.pack('<bBhHiIlLqQ', -1, 255, -2, 65535, -3, 4294967295, -4, 4294967294, -5,
                       9223372036854775807)
    print(len(data), data.hex())
    print(struct.unpack('<bBhHiIlLqQ', data))
    print(struct.pack('>I', 0x12345678).hex(), struct.unpack('>I', bytes.fromhex('12345678')))
    print(struct.pack('<4xH', 1).hex(), struct.unpack('<4xH', b'\\x00\\x00\\x00\\x00\\x01\\x00'))
    print(struct.calcsize('@bhiq'), struct.calcsize('=bhiq'), struct.calcsize('<bhiq'),
          struct.calcsize('>bhiq'))
    print(struct.calcsize('@nN'), struct.calcsize('@P'))
    print(struct.pack('=i', 1).hex(), struct.pack('@i', 1).hex(), struct.pack('!i', 1).hex())
    print(struct.unpack_from('<H', b'xx\\x01\\x00', 2), struct.unpack_from('<H', b'\\x01\\x00xx'))
    print(struct.pack('<q', -1).hex(), struct.pack('<Q', 9223372036854775807).hex())
    print(struct.pack('@P', -1).hex())


main()
'''

ROUTES = '''import struct as st
from struct import pack as p, unpack as u, calcsize as cs, error


def show(values: list[int]) -> None:
    data = p('<h', values[0])
    print(data.hex(), u('<h', data))


def main() -> None:
    show([258])
    v = [259]
    print(st.pack('>H', v[0]).hex())
    d = {'x': 260}
    print(st.unpack('>H', st.pack('>H', d['x'])))
    print(st.pack('<I', 7).hex(), st.unpack('<I', st.pack('<I', 7)), cs('@P'))
    try:
        u('<i', b'abc')
    except error as exc:
        print('bad:', exc)
    try:
        st.pack('<B', 256)
    except st.error as exc:
        print('bad:', exc)
    try:
        st.pack('<i', 1, 2)
    except error as exc:
        print('bad:', exc)
    try:
        st.unpack_from('<H', b'abc', 5)
    except st.error as exc:
        print('bad:', exc)


main()
'''

BUFFERS = '''import struct


def main() -> None:
    buf = bytearray(b'xx\\x01\\x02')
    print(struct.unpack_from('<H', buf, 2), struct.unpack_from('<H', buf, 0))
    try:
        struct.unpack_from('<H', b'abc', -1)
    except struct.error as exc:
        print('bad:', exc)
    try:
        struct.pack('<i', 1, 2)
    except struct.error as exc:
        print('bad:', exc)


main()
'''

NATIVE = '''import struct


def main() -> None:
    print(struct.calcsize('@bhiq'), struct.calcsize('@ib'), struct.calcsize('@qib'),
          struct.calcsize('@bq'), struct.calcsize('@hl'), struct.calcsize('@lh'))
    d = struct.pack('@bhiq', 1, 2, 3, 4)
    print(len(d), d.hex(), struct.unpack('@bhiq', d))
    d = struct.pack('@ib', 5, 6)
    print(len(d), d.hex(), struct.unpack('@ib', d))
    d = struct.pack('@qib', 7, 8, 9)
    print(len(d), d.hex(), struct.unpack('@qib', d))
    d = struct.pack('@bq', 1, 2)
    print(len(d), d.hex(), struct.unpack('@bq', d))
    d = struct.pack('@b3h', 1, 2, 3, 4)
    print(len(d), d.hex(), struct.unpack('@b3h', d))
    d = struct.pack('@bhlqNP', 1, 2, 3, 4, 5, 6)
    print(len(d), d.hex(), struct.unpack('@bhlqNP', d))
    d = struct.pack('@bxh', 1, 2)
    print(len(d), d.hex(), struct.unpack('@bxh', d))
    d = struct.pack('@b3xh', 1, 2)
    print(len(d), d.hex(), struct.unpack('@b3xh', d))
    d = struct.pack('@bqib', 1, 2, 3, 4)
    print(len(d), d.hex(), struct.unpack('@bqib', d))
    print(struct.pack('@bhiq', -1, -2, -3, -4).hex())


main()
'''

EDGES = '''import struct


def main() -> None:
    try:
        a, b = struct.unpack('<2H', b'\\x01\\x00\\x02')
        print('unexpected', a, b)
    except struct.error as exc:
        print('bad:', exc)
    try:
        a, b = struct.unpack('<2H', b'')
        print('unexpected', a, b)
    except struct.error as exc:
        print('bad:', exc)
    try:
        a, b = struct.unpack('<2H', b'\\x01\\x00\\x02\\x00\\x03')
        print('unexpected', a, b)
    except struct.error as exc:
        print('bad:', exc)
    for offset in (-4, -6, 0, 2):
        a, b = struct.unpack_from('<2H', b'abcdef', offset)
        print(offset, a, b)
    for offset in (-1, -2, -7, 3, 5):
        print(offset)
        try:
            a, b = struct.unpack_from('<2H', b'abcdef', offset)
            print('unexpected', a, b)
        except struct.error as exc:
            print('bad:', exc)
    try:
        print(struct.pack('<b', 128).hex())
    except struct.error as exc:
        print('b high:', exc)
    try:
        print(struct.pack('<b', -129).hex())
    except struct.error as exc:
        print('b low:', exc)
    try:
        print(struct.pack('<B', -1).hex())
    except struct.error as exc:
        print('B low:', exc)
    try:
        print(struct.pack('<h', 32768).hex())
    except struct.error as exc:
        print('h high:', exc)
    try:
        print(struct.pack('<H', -1).hex())
    except struct.error as exc:
        print('H low:', exc)
    try:
        print(struct.pack('<i', 2147483648).hex())
    except struct.error as exc:
        print('i high:', exc)
    try:
        print(struct.pack('<I', -1).hex())
    except struct.error as exc:
        print('I low:', exc)
    print(struct.pack('@P', -2).hex(), struct.pack('@P', -9223372036854775808).hex())
    print(struct.pack('<i', True).hex(), struct.pack('<i', False).hex())
    a, b = struct.unpack('<2H', bytearray(b'\\x01\\x00\\x02\\x00'))
    print(a, b)


main()
'''


def compile_env(extra):
    env = dict(os.environ)
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_UNIFIED', 'AIL_IR'):
        env.pop(key, None)
    env.update(extra)
    return env


class StructTests(unittest.TestCase):
    def compare(self, text, name):
        with tempfile.TemporaryDirectory(prefix='ail-struct-') as directory:
            source = Path(directory) / (name + '.py')
            source.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=300)
            self.assertEqual(want.returncode, 0, want.stderr.decode())
            self.assertTrue(want.stdout)
            for tag, extra in (('typed', {'AIL_NO_GENERAL': '1'}),
                               ('general', {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '0'})):
                exe = Path(directory) / ('exe-' + tag)
                built = subprocess.run([sys.executable, '-B', CLI, 'compile', source.name, '-o', exe.name,
                                        '--syntax', 'python'], cwd=directory, capture_output=True, text=True,
                                       timeout=900, env=compile_env(extra))
                self.assertEqual(built.returncode, 0, tag + ': ' + built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, tag + ': ' + got.stderr.decode()[:500])
                self.assertEqual(got.stdout, want.stdout, tag + ': ' + got.stderr.decode()[:500])

    def refused(self, text, wanted, name):
        with tempfile.TemporaryDirectory(prefix='ail-struct-') as directory:
            source = Path(directory) / (name + '.py')
            source.write_text(text, encoding='utf-8')
            for tag, extra in (('typed', {'AIL_NO_GENERAL': '1'}),
                               ('general', {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '0'})):
                exe = Path(directory) / ('exe-' + tag)
                built = subprocess.run([sys.executable, '-B', CLI, 'compile', source.name, '-o', exe.name,
                                        '--syntax', 'python'], cwd=directory, capture_output=True, text=True,
                                       timeout=900, env=compile_env(extra))
                self.assertNotEqual(built.returncode, 0, tag + ': ' + built.stdout + built.stderr)
                self.assertIn(wanted, built.stdout + built.stderr, tag)
                self.assertFalse(exe.exists(), tag)

    def test_pack_unpack_calcsize(self):
        self.compare(BASIC, 'basic')

    def test_import_forms_and_errors(self):
        self.compare(ROUTES, 'routes')

    def test_buffer_and_unpack_from(self):
        self.compare(BUFFERS, 'buffers')

    def test_native_alignment(self):
        self.compare(NATIVE, 'native')

    def test_errors_and_boundaries(self):
        self.compare(EDGES, 'edges')

    def test_float_is_refused_by_name(self):
        self.refused('''import struct


def main() -> None:
    print(struct.pack('<d', 1.5))


main()
''', "struct format code 'd' is not built", 'float')

    def test_string_and_bool_formats_are_refused_by_name(self):
        self.refused('''import struct


def main() -> None:
    print(struct.pack('<s', b'abc'))


main()
''', "only integer formats", 'string')
        self.refused('''import struct


def main() -> None:
    print(struct.pack('<?', True))


main()
''', "only integer formats", 'bool')

    def test_dynamic_format_is_refused_by_name(self):
        self.refused('''import struct


def main() -> None:
    fmt = '<i'
    print(struct.pack(fmt, 1))


main()
''', 'the format string must be a literal known at compile time', 'dynamic')

    def test_non_bytes_buffer_is_refused_by_name(self):
        self.refused('''import struct


def main() -> None:
    print(struct.unpack('<H', [1, 0]))


main()
''', 'the buffer must be bytes or a bytearray', 'listbuffer')
        self.refused('''import struct


def main() -> None:
    print(struct.calcsize('<h'), struct.pack('<h', 1), struct.unpack('<h', 'ab'))


main()
''', 'the buffer must be bytes or a bytearray', 'strbuffer')

    def test_struct_class_is_refused_by_name(self):
        self.refused('''import struct


def main() -> None:
    obj = struct.Struct('<i')
    print(obj.pack(1))


main()
''', 'struct.Struct is not built', 'structclass')


if __name__ == '__main__':
    unittest.main()
