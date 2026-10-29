"""Library batch 6: `struct` pack / unpack / unpack_from / calcsize with a literal format.

Each program below is ordinary Python. CPython 3.12 runs it as the oracle and the compiled program
must print the same bytes and exit with the same status, once with the default build and once with
AIL_IR=1. The supported surface is

* ``struct.pack(fmt, ...)``, ``struct.calcsize(fmt)`` and ``a, b, ... = struct.unpack(fmt, data)``
  / ``a, b, ... = struct.unpack_from(fmt, data[, offset])`` with a string literal ``fmt``;
* the codes ``x c b B ? h H i I l L q Q e f d s p P`` (``P`` only in the native ``@`` mode, as in
  CPython), the ``@ = < > !`` byte-order prefixes and native alignment/padding;
* ``struct.error`` (spelt RuntimeError inside the compiler), CPython's range and buffer messages,
  and OverflowError for a finite float too large for ``f`` / ``e``.

Everything else -- a computed format, ``Struct``, ``pack_into``, ``iter_unpack``, an unpack result
used as a value, a wrong value count or a wrong number of target names -- is refused at compile
time with a message that names the use. ``test_refusals_name_the_use`` checks that.
"""
import os
import struct as _struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def _literal(value):
    if isinstance(value, float):
        if value != value:
            return 'float("nan")'
        if value == float('inf'):
            return 'float("inf")'
        if value == float('-inf'):
            return 'float("-inf")'
        return repr(value)
    return repr(value)


PACK_CASES = [
    ('<b', (-128,)), ('<b', (127,)), ('<b', (0,)), ('<b', (-1,)),
    ('<B', (0,)), ('<B', (255,)), ('<B', (128,)),
    ('<h', (-32768,)), ('<h', (32767,)), ('<h', (-2,)),
    ('<H', (0,)), ('<H', (65535,)), ('<H', (0x1234,)),
    ('<i', (-2147483648,)), ('<i', (2147483647,)), ('<i', (-5,)),
    ('<I', (0,)), ('<I', (4294967295,)), ('<I', (0x01020304,)),
    ('<l', (-2147483648,)), ('<l', (2147483647,)),
    ('<L', (0,)), ('<L', (4294967295,)),
    ('<q', (-9223372036854775808,)), ('<q', (9223372036854775807,)), ('<q', (-2,)),
    ('<Q', (0,)), ('<Q', (9223372036854775807,)),
    ('>b', (-5,)), ('>B', (200,)), ('>h', (-300,)), ('>H', (60000,)),
    ('>i', (-70000,)), ('>I', (4000000000,)), ('>l', (-70000,)), ('>L', (4000000000,)),
    ('>q', (-9223372036854775807,)), ('>Q', (9223372036854775807,)),
    ('=hhl', (1, -2, 0x01020304)), ('>hhl', (1, -2, 0x01020304)),
    ('@hhl', (1, -2, 0x01020304)), ('!hhl', (1, -2, 0x01020304)),
    ('<f', (0.0,)), ('<f', (-0.0,)), ('<f', (1.5,)), ('<f', (-1.5,)),
    ('<f', (65504.0,)), ('<f', (1e-8,)), ('<f', (3.4028234663852886e38,)),
    ('<d', (0.0,)), ('<d', (-0.0,)), ('<d', (-2.25,)), ('<d', (3.141592653589793,)),
    ('<d', (1e-300,)), ('<d', (1.7976931348623157e308,)),
    ('<d', (float('inf'),)), ('<d', (float('-inf'),)),
    ('<e', (0.0,)), ('<e', (-0.0,)), ('<e', (1.5,)), ('<e', (-1.5,)),
    ('<e', (0.5,)), ('<e', (65504.0,)), ('<e', (5.960464477539063e-08,)),
    ('@e', (1.5,)), ('>e', (1.5,)),
    ('<4s', (b'',)), ('<4s', (b'a',)), ('<4s', (b'ab',)), ('<4s', (b'abcdef',)),
    ('4s', (b'ab',)), ('>4s', (b'ab',)), ('<0s', (b'x',)),
    ('<p', (b'',)), ('<p', (b'abc',)), ('<4p', (b'',)), ('<4p', (b'abc',)),
    ('<4p', (b'abcdef',)), ('<255p', (b'c' * 255,)), ('<256p', (b'c' * 256,)),
    ('<257p', (b'c' * 257,)), ('<300p', (b'c' * 300,)), ('>257p', (b'c' * 257,)),
    ('@257p', (b'c' * 257,)), ('<5p', (b'c' * 300,)), ('<c', (b'Z',)), ('>c', (b'Z',)),
    ('<2c', (b'a', b'b')),
    ('<?', (True,)), ('<?', (False,)), ('<?', (0,)), ('<?', (1,)), ('<?', (2,)), ('<?', (-1,)),
    ('2x', ()), ('x', ()), ('0x', ()), ('3x', ()),
    ('xci', (b'\x00', 5)), ('cxi', (b'A', 5)), ('2xi', (7,)),
    ('<3i', (1, -1, 256)), ('<2s3p', (b'ab', b'char')),
    ('@ci', (b'Z', 5)), ('@bi', (1, 5)), ('@lq', (1, 2)), ('@dI', (2.5, 3)),
    ('@hd', (1, 4.5)), ('@ch', (b'A', 2)), ('@hc', (2, b'A')), ('@bh', (1, 2)),
    ('<16sHHIQQQIHHHHHH', (b'ab', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)),
    ('<IIQQQQQQ', (1, 2, 3, 4, 5, 6, 7, 8)),
    ('>Ih2s', (7, -2, b'xy')),
]


def _pack_unpack_program(cases):
    lines = ['import struct', '', 'def main():']
    for index, (fmt, values) in enumerate(cases):
        call = 'struct.pack(%r%s)' % (fmt, ''.join(', ' + _literal(value) for value in values))
        lines.append('    p%d = %s' % (index, call))
        lines.append('    print("p%d", p%d.hex())' % (index, index))
        unpacked = _struct.unpack(fmt, _struct.pack(fmt, *values))
        if not unpacked:
            continue
        names = ['u%d_%d' % (index, field) for field in range(len(unpacked))]
        target = names[0] + ',' if len(names) == 1 else ', '.join(names)
        lines.append('    %s = struct.unpack(%r, p%d)' % (target, fmt, index))
        shown = [name + '.hex()' if isinstance(value, bytes) else name
                 for name, value in zip(names, unpacked)]
        lines.append('    print("u%d", %s)' % (index, ', '.join(shown)))
    lines += ['', 'main()', '']
    return '\n'.join(lines)


PACK_UNPACK = _pack_unpack_program(PACK_CASES)

CALC_FORMATS = [
    '', '<', '>', '=', '@', '!', '<bBhHiIlLqQefds', '>I', '<16sHHIQQQIHHHHHH',
    '<IIQQQQQQ', '3i', '2h', '10x', 'x', '0x', '0i', '0c', '0s', '@b', '@h', '@i',
    '@l', '@q', '@d', '@c', '@?', '@e', '@p', '@s', '@P', '=bBhHiIlLqQefds',
    '<2s3p', '<s', '<p', '<0s', '@ci', '@bi', '@lq', '@dI', '@hc', '@bh',
]
CALC = 'import struct\n\n\ndef main():\n%s\n\nmain()\n' % '\n'.join(
    '    print(%r, struct.calcsize(%r))' % (fmt, fmt) for fmt in CALC_FORMATS)

FLOAT_OVERFLOW = r'''import struct


def show(label: str, value: float) -> None:
    try:
        packed = struct.pack("<f", value)
        print(label, "f", packed.hex())
    except OverflowError as error:
        print(label, "f", str(error))
    try:
        packed = struct.pack("<e", value)
        print(label, "e", packed.hex())
    except OverflowError as error:
        print(label, "e", str(error))


def main() -> None:
    show("big", 1e300)
    show("fedge", 3.4028236e38)
    show("halfedge", 65520.0)
    show("halfbig", 70000.0)
    show("halfok", 65519.0)
    packed = struct.pack("<f", float("inf"))
    print("inf", packed.hex())
    packed = struct.pack("<e", float("inf"))
    print("halfinf", packed.hex())


main()
'''

ERRORS = r'''import struct


def main() -> None:
    try:
        struct.pack("<B", 256)
    except struct.error as error:
        print("b1", str(error))
    try:
        struct.pack("<B", -1)
    except struct.error as error:
        print("b2", str(error))
    try:
        struct.pack("<b", 128)
    except struct.error as error:
        print("b3", str(error))
    try:
        struct.pack("<h", 40000)
    except struct.error as error:
        print("b4", str(error))
    try:
        struct.pack("<H", 70000)
    except struct.error as error:
        print("b5", str(error))
    try:
        struct.pack("<i", 2147483648)
    except struct.error as error:
        print("b6", str(error))
    try:
        struct.pack("<I", 4294967296)
    except struct.error as error:
        print("b7", str(error))
    try:
        struct.pack("<l", 2147483648)
    except struct.error as error:
        print("b8", str(error))
    try:
        struct.pack("<L", 4294967296)
    except struct.error as error:
        print("b9", str(error))
    try:
        struct.pack("<Q", -1)
    except struct.error as error:
        print("b10", str(error))
    try:
        struct.pack("<c", b"ab")
    except struct.error as error:
        print("c1", str(error))
    try:
        struct.pack("<c", b"")
    except struct.error as error:
        print("c2", str(error))
    try:
        a1, = struct.unpack("<i", b"ab")
    except struct.error as error:
        print("u1", str(error))
    try:
        a2, = struct.unpack("<4s", b"ab")
    except struct.error as error:
        print("u2", str(error))
    try:
        a3, = struct.unpack("<I", b"")
    except struct.error as error:
        print("u3", str(error))
    try:
        a4, = struct.unpack("<I", b"\x01\x02\x03\x04\x05")
    except struct.error as error:
        print("u4", str(error))
    try:
        f1, = struct.unpack_from("<I", b"\x01\x02", 0)
    except struct.error as error:
        print("f1", str(error))
    try:
        f2, = struct.unpack_from("<I", b"\x01\x02\x03\x04", 2)
    except struct.error as error:
        print("f2", str(error))
    try:
        f3, = struct.unpack_from("<I", b"\x01\x02\x03\x04", -1)
    except struct.error as error:
        print("f3", str(error))
    try:
        f4, = struct.unpack_from("<I", b"\x01\x02\x03\x04", -5)
    except struct.error as error:
        print("f4", str(error))


main()
'''

UNPACK_FROM = r'''import struct


def main() -> None:
    data = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    a, = struct.unpack_from("<I", data, 0)
    b, = struct.unpack_from("<I", data, 1)
    c, = struct.unpack_from("<I", data, 2)
    d, = struct.unpack_from("<I", data, 4)
    print(a, b, c, d)
    x, y = struct.unpack_from("<II", data, 0)
    print(x, y)
    p, = struct.unpack_from("<H", data, -2)
    q, = struct.unpack_from("<H", data, -4)
    r, = struct.unpack_from("<I", data, -8)
    print(p, q, r)
    s, = struct.unpack_from("<I", data)
    print(s)
    m, = struct.unpack_from("<4p", data, 0)
    print(m.hex())
    n, o = struct.unpack_from(">4s4s", data, 0)
    print(n.hex(), o.hex())


main()
'''

ROUTES = r'''import struct


class Box:
    def __init__(self, v: int):
        self.v = v


def main() -> None:
    v = 300
    xs = [301, -302]
    d = {"k": 303}
    b = Box(-304)
    p1 = struct.pack("<h", v)
    p2 = struct.pack("<h", xs[0])
    p3 = struct.pack("<h", xs[1])
    p4 = struct.pack("<h", d["k"])
    p5 = struct.pack("<h", b.v)
    print(p1.hex(), p2.hex(), p3.hex(), p4.hex(), p5.hex())
    a, = struct.unpack("<h", p1)
    c, = struct.unpack_from("<h", p2, 0)
    print(a, c)


main()
'''

BUFFER = r'''import struct


def main() -> None:
    data = bytearray(b"\x01\x02\x03\x04")
    a, = struct.unpack("<I", data)
    print(a)
    b, = struct.unpack_from("<H", data, 1)
    print(b)
    other = bytearray(b"\x05\x06\x07\x08")
    c, = struct.unpack("<I", other)
    print(c)
    packed = struct.pack("<I", 16909060)
    print(packed.hex())


main()
'''

ALIAS = r'''import struct as st
from struct import pack, unpack, calcsize


def main() -> None:
    b = st.pack("<i", 12)
    si, = st.unpack("<i", b)
    print(b.hex(), si)
    p = pack("<h", 3)
    h, = unpack("<h", b"\x03\x00")
    print(p.hex(), h, calcsize("<i"))
    q = st.pack(">I", 1)
    r = pack(">I", 2)
    print(q.hex(), r.hex())


main()
'''

CORPUS = r'''import struct
import sys


def to_byte_list(value: int) -> list[int]:
    magnitude = abs(value)
    length = max(1, (magnitude.bit_length() + 7) // 8)
    data = magnitude.to_bytes(length, "big", signed=False)
    assert int.from_bytes(data, "big", signed=False) == magnitude
    return list(data)


def main() -> None:
    tokens = sys.stdin.read().split()
    n = int(tokens[0])
    numbers = [int(token) for token in tokens[1:n + 1]]
    for value in numbers:
        print(to_byte_list(value))
        if value < 2 ** 32:
            packed = struct.pack(">I", value)
            assert int.from_bytes(packed, "big", signed=False) == value
            print(list(packed))


main()
'''

PROGRAMS = [
    ('pack_unpack', PACK_UNPACK, ''),
    ('calc', CALC, ''),
    ('float_overflow', FLOAT_OVERFLOW, ''),
    ('errors', ERRORS, ''),
    ('unpack_from', UNPACK_FROM, ''),
    ('routes', ROUTES, ''),
    ('buffer', BUFFER, ''),
    ('alias', ALIAS, ''),
    ('corpus', CORPUS, '6 0 1 255 65535 4294967295 4294967296\n'),
]

REFUSALS = {
    'struct_class': ('import struct\n\ns = struct.Struct("<i")\nprint(s.size)\n', 'struct'),
    'computed_format': ('import struct\n\nfmt = "<i"\nprint(struct.pack(fmt, 5))\n',
                        'the format must be a string literal'),
    'unpack_value': ('import struct\n\nx = struct.unpack("<i", b"\\x01\\x00\\x00\\x00")\nprint(x)\n',
                     'an unpack result used as a value'),
    'pack_into': ('import struct\n\nbuf = bytearray(4)\nstruct.pack_into("<i", buf, 0, 5)\n', 'struct'),
    'iter_unpack': ('import struct\n\nfor item in struct.iter_unpack("<i", b"\\x01\\x00\\x00\\x00"):\n'
                    '    print(item)\n', 'struct'),
    'bad_format': ('import struct\n\nprint(struct.calcsize("<n"))\n', 'not a valid format'),
    'wrong_count': ('import struct\n\np = struct.pack("<ii", 1)\nprint(p.hex())\n',
                    'this format takes 2 values, not 1'),
    'wrong_names': ('import struct\n\na, b = struct.unpack("<i", b"\\x01\\x00\\x00\\x00")\n',
                    'gives 1 values, but 2 names are assigned'),
}


def build(directory, name, text, ir):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_ir' if ir else '_default'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1', AIL_IR='1' if ir else '0')
    env.pop('AIL_NO_GENERAL', None)
    done = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', source.name,
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)
    return exe, done


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, stdin, ir):
        with tempfile.TemporaryDirectory() as directory:
            exe, built = build(directory, name, text, ir)
            self.assertEqual(built.returncode, 0, '%s (AIL_IR=%s)\n%s%s'
                             % (name, int(ir), built.stdout, built.stderr))
            oracle = Path(directory) / 'oracle.py'
            oracle.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', str(oracle)], input=stdin.encode(),
                                  capture_output=True, timeout=300,
                                  env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
            got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, got.stderr[-500:])
            if got.stdout != want.stdout:
                a = got.stdout.decode('utf-8', 'replace').splitlines()
                b = want.stdout.decode('utf-8', 'replace').splitlines()
                for number, (left, right) in enumerate(zip(a, b)):
                    if left != right:
                        self.fail('%s input (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r'
                                  % (name, int(ir), number + 1, left, right))
                self.fail('%s (AIL_IR=%s): %d lines against %d'
                          % (name, int(ir), len(a), len(b)))

    def test_programs_match_cpython(self):
        for name, text, stdin in PROGRAMS:
            for ir in (False, True):
                with self.subTest(program=name, ir=ir):
                    self.check(name, text, stdin, ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'refused.py'
            source.write_text(text, encoding='utf-8')
            exe = Path(directory) / 'refused'
            env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
            env.pop('AIL_NO_GENERAL', None)
            for ir in ('0', '1'):
                built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', 'refused.py',
                                        '--syntax', 'python', '-o', exe.name], cwd=directory,
                                       capture_output=True, text=True, timeout=900,
                                       env=dict(env, AIL_IR=ir))
                self.assertNotEqual(built.returncode, 0, 'compiled but should be refused: ' + wanted)
                self.assertIn(wanted, built.stdout + built.stderr)
                self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        for name, (text, wanted) in REFUSALS.items():
            with self.subTest(case=name):
                self.refused(text, wanted)


if __name__ == '__main__':
    unittest.main()
