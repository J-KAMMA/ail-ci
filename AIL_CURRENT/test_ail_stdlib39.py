"""`struct`: pack, unpack, unpack_from and calcsize over a literal format, against CPython 3.12.

The rewrite lives in `python/pkg-v12/structlib.py` and runs from `ail_syntax.python_surface`.  The
program below is compiled with the default build and with AIL_IR=1 and run on stdin; its bytes and
exit status must match CPython.  `struct.error` is ValueError in a compiled program, so the
program catches it through both `struct.error` and a from-imported `error`; the text is CPython's.

Declared differences: an int is 64-bit, so the unsigned 64-bit `Q` field cannot pack a value
above 2**63-1; `f`, `e` and `d` (16/32/64-bit floats), `p`, dynamic format strings, `Struct`,
`iter_unpack`, `pack_into` and every other name are refused here by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PROGRAM = r'''import struct as st
from struct import pack, unpack, unpack_from, calcsize, error
import sys


class Holder:
    def __init__(self, value: int) -> None:
        self.value = value


def enc_i(value: int) -> bytes:
    return st.pack('<i', value)


def enc_q(value: int) -> bytes:
    return st.pack('@q', value)


def enc_h(value: int) -> bytes:
    return st.pack('>h', value)


def dec_i(data: bytes) -> int:
    return unpack('<i', data)[0]


def main() -> None:
    tokens = [int(t) for t in sys.stdin.read().split()]
    if not tokens:
        return
    h = Holder(tokens[-1])
    table = {'a': tokens[0], 'b': tokens[-1]}
    values = [tokens[0], tokens[-1], -1, 0, 1, 127]
    print('sizes', calcsize('<bBhHiIqQ'), calcsize('>bBhHiIqQ'), calcsize('@bBhHiIqQnNP'),
          calcsize('=bBhHiIqQ'), calcsize('<4x3s2c?'))
    for v in values:
        hv = abs(v) % 100
        print('enc', v, list(enc_i(v)), dec_i(enc_i(v)), list(enc_q(v)))
        print('routes', list(enc_i(values[0])), list(enc_i(table['b'])), list(enc_i(h.value)))
        print('h', list(enc_h(hv)), unpack('>h', enc_h(hv))[0])
        print('bool', list(st.pack('<?', v)), st.unpack('<?', st.pack('<?', v)))
    print('native', list(st.pack('@bh', 1, 2)), st.unpack('@bh', st.pack('@bh', 1, 2)))
    print('native', list(st.pack('@bi', 1, 2)), st.unpack('@bi', st.pack('@bi', 1, 2)))
    print('native', list(st.pack('@bq', 1, 2)), st.unpack('@bq', st.pack('@bq', 1, 2)))
    print('native', list(st.pack('@b3sH', 1, b'x', 2)), st.unpack('@b3sH', st.pack('@b3sH', 1, b'x', 2)))
    print('native', list(st.pack('@2xI', 5)), st.unpack('@2xI', st.pack('@2xI', 5)))
    print('native', list(st.pack('@n', 7)), st.unpack('@n', st.pack('@n', 7)))
    print('native', list(st.pack('@N', 7)), st.unpack('@N', st.pack('@N', 7)))
    print('native', list(st.pack('@P', 7)), st.unpack('@P', st.pack('@P', 7)))
    b = st.pack('<4x3s2c?', b'ab', b'X', b'Y', True)
    print('bytes', list(b), st.unpack('<4x3s2c?', b))
    print('trunc', list(st.pack('<5s', b'ab')), list(st.pack('<2s', b'abcdef')))
    print('repeat', list(st.pack('<3i2s4x', 1, -2, 3, b'ab')), st.unpack('<3i2s4x', st.pack('<3i2s4x', 1, -2, 3, b'ab')))
    data = b'0123456789abcdef'
    print('from', st.unpack_from('<I', data, 0), st.unpack_from('<I', data, 4),
          st.unpack_from('<4s', data, 2), st.unpack_from('<I', data, -4), st.unpack_from('<I', data))
    try:
        st.unpack('<I', b'')
    except st.error as exc:
        print('bad', exc)
    try:
        st.unpack('<I', b'abc')
    except st.error as exc:
        print('bad', exc)
    try:
        st.unpack('<I', b'abcde')
    except st.error as exc:
        print('bad', exc)
    try:
        st.unpack_from('<I', data, 13)
    except error as exc:
        print('off', exc)
    try:
        st.unpack_from('<I', data, -2)
    except error as exc:
        print('off', exc)
    try:
        st.unpack_from('<I', b'abc', -4)
    except st.error as exc:
        print('off', exc)
    try:
        st.pack('<I', -1)
    except error as exc:
        print('range', exc)
    try:
        st.pack('<i', 2**31)
    except st.error as exc:
        print('range2', exc)
    try:
        st.pack('<c', b'')
    except st.error as exc:
        print('char', exc)
    try:
        st.pack('<c', 65)
    except st.error as exc:
        print('char', exc)
    try:
        st.pack('<2s', 65)
    except st.error as exc:
        print('str', exc)
    print('boolpack', list(st.pack('<b', True)), list(st.pack('<b', False)), list(st.pack('<I', True)))
    print('sbyte', list(st.pack('<2s', bytearray(b'abc'))))


main()
'''

INPUTS = (
    '1 2 3 -128 255 32767 -32768\n',
    '0 2147483647 -2147483648 42 -7\n',
)


def compile_python(directory, text, name, ir):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_IR='1' if ir else '0')
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=env)
    return built, source, exe


class StructPrograms(unittest.TestCase):
    def test_programs_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, 'oracle.py')
            oracle.write_text(PROGRAM, encoding='utf-8')
            for ir in (False, True):
                with self.subTest(ir=ir):
                    built, _, exe = compile_python(directory, PROGRAM, 'struct_ir' if ir else 'struct_default', ir)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    for index, data in enumerate(INPUTS):
                        want = subprocess.run([sys.executable, '-X', 'utf8', str(oracle)], input=data.encode(),
                                              capture_output=True, timeout=300)
                        got = subprocess.run([str(exe)], input=data.encode(), capture_output=True, timeout=300)
                        self.assertEqual(got.returncode, want.returncode, 'input %d: %s' % (index, got.stderr[-400:]))
                        if got.stdout != want.stdout:
                            a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                            for line, (x, y) in enumerate(zip(a, b)):
                                if x != y:
                                    self.fail('input %d line %d:\n  compiled: %r\n  CPython:  %r' % (index, line + 1, x, y))
                            self.fail('input %d: %d lines against %d' % (index, len(a), len(b)))

    def test_programs_without_struct_keep_their_text(self):
        import structlib
        for text in ('import sys\n\nprint(1)\n', '# struct is only named here\nprint(1)\n'):
            with self.subTest(text=text):
                notes = []
                self.assertIs(structlib.rewrite_text(text, notes), text)
                self.assertEqual(notes, [])


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, 'refused', False)
            self.assertNotEqual(built.returncode, 0, 'compiled but should be refused: ' + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            'float64': ('import struct\n\nprint(struct.pack("<d", 1.5))\n', "'d' (float64)"),
            'struct_class': ('from struct import Struct\n\ns = Struct("<I")\nprint(s.pack(1))\n', 'struct.Struct'),
            'pack_into': ('import struct\n\nprint(struct.pack_into("<I", bytearray(4), 0, 1))\n', 'struct.pack_into'),
            'dynamic': ('import struct\n\nfmt = "<I"\nprint(struct.pack(fmt, 1))\n', 'string literal format'),
            'keyword': ('import struct\n\nprint(struct.pack("<I", value=1))\n', 'keywords or *args'),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


if __name__ == '__main__':
    unittest.main()
