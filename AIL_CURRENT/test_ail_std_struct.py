"""The stdlib `struct` programs in lab/stdlib/struct, compared with CPython 3.12.

Each program is built by the default command (`ail_chatgpt.py compile X.py --syntax python`); the typed path
names the prelude's module-level format tables, so the build falls back to the general path, which is the
result recorded in lab/stdlib/struct/RESULTS.md.  stdout and the exit code must match CPython exactly.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "struct"


EDGE_PROGRAMS = {
    "pack_into_native": """import struct
buf = bytearray(8)
struct.pack_into('@f', buf, 0, 1e40)
print(buf[:4].hex())
try:
    struct.pack_into('<f', buf, 0, 1e40)
    print('no error', buf[:4].hex())
except Exception as e:
    print(type(e).__name__, e)
print(struct.pack('@f', 1e40).hex())
buf = bytearray(8)
try:
    struct.pack_into('<f', buf, 0, 1e40)
    print('no error', buf[:4].hex())
except Exception as e:
    print(type(e).__name__, e)
s = struct.Struct('@f')
s.pack_into(buf, 0, 1e40)
print(buf[:4].hex())
""",
    "pascal": """import struct
for fmt, data in [('5p', b'\\xffabcd'), ('3p', b'\\x05ab'), ('1p', b'\\xff'),
                  ('4p', b'\\x00abc'), ('4p', b'\\x03abc'), ('4p', b'\\x04abc')]:
    print(fmt, data, struct.unpack(fmt, data))
for n in [1, 2, 4]:
    fmt = str(n) + 'p'
    for value in [b'', b'a', b'abcd', b'abcdef']:
        packed = struct.pack(fmt, value)
        print(fmt, value, packed.hex(), struct.unpack(fmt, packed))
""",
    "negative_zero": """import math
import struct
for code in ['<d', '<f', '<e', '@d', '@f', '@e', '=d', '>d', '>f', '>e']:
    packed = struct.pack(code, -0.0)
    value = struct.unpack(code, packed)[0]
    print(code, packed.hex(), repr(value), math.copysign(1.0, value))
s = struct.Struct('<f')
print(repr(s.unpack(s.pack(-0.0))[0]))
packed = struct.pack('<d', -0.0)
print(repr(struct.unpack_from('<d', packed, 0)[0]))
print(repr(list(struct.iter_unpack('<d', packed))[0][0]))
""",
    "format_space": """import struct
for fmt in ['3 i', '3\\ti', '3\\ni', '3  i', '3i', ' 3i', '3', '3 ', '3\\ti4', ' 3 i4', '3@i']:
    try:
        print(repr(fmt), struct.calcsize(fmt))
    except Exception as e:
        print(repr(fmt), type(e).__name__, e)
""",
    "default_float": """import struct

class Box:
    def __init__(self, v):
        self.v = v

def pack_one(fmt, value):
    return struct.pack(fmt, value).hex()

box = Box(1e40)
items = [1e39]
table = {'x': 1e40}
for fmt in ['f', ' f', '1f', '@f', '=f', '<f', '>f', '!f']:
    for value in [1e40, 1e39, -1e40, 3.4028235e38, -0.0, 0.0]:
        try:
            print('p', fmt, value, pack_one(fmt, value))
        except Exception as exc:
            print('p', fmt, value, type(exc).__name__, exc)
for fmt in ['f', ' f', '@f', '=f']:
    for value in [1e40, 1e39, -1e40, -0.0, 0.0]:
        try:
            print('s', fmt, value, struct.Struct(fmt).pack(value).hex())
        except Exception as exc:
            print('s', fmt, value, type(exc).__name__, exc)
print('two', struct.pack('2f', 1e40, -1e40).hex())
print('ten', struct.pack('10f', *([1e40] * 10)).hex())
buf = bytearray(8)
struct.pack_into('f', buf, 0, 1e40)
print('into default', buf[:4].hex())
buf = bytearray(8)
struct.pack_into('@f', buf, 0, 1e40)
print('into native', buf[:4].hex())
buf = bytearray(8)
try:
    struct.pack_into('<f', buf, 0, 1e40)
    print('into standard ok', buf[:4].hex())
except Exception as exc:
    print('into standard', type(exc).__name__, exc)
print('routes', pack_one('f', 1e40), struct.pack('f', box.v).hex(),
      struct.pack('f', items[0]).hex(), struct.pack('f', table['x']).hex())
""",
    "subnormal_double": """import struct
for data in [b'\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00',
             b'\\x02\\x00\\x00\\x00\\x00\\x00\\x00\\x00',
             b'\\x00\\x00\\x00\\x00\\x00\\x00\\x10\\x00',
             b'\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00',
             b'\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x80',
             b'\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x80',
             b'\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08',
             b'\\x34\\x12\\x00\\x00\\x00\\x00\\xf0\\x00']:
    value = struct.unpack('<d', data)[0]
    print('d', data.hex(), value, struct.pack('<d', value).hex())
    value = struct.unpack('>d', data)[0]
    print('D', data.hex(), value, struct.pack('>d', value).hex())
for data in [b'\\x01\\x00\\x00\\x00', b'\\xff\\xff\\x7f\\x00', b'\\x01\\x00\\x80\\x00',
             b'\\x00\\x00\\x80\\x3f', b'\\x01\\x00\\x00\\x80']:
    value = struct.unpack('<f', data)[0]
    print('f', data.hex(), value, struct.pack('<f', value).hex())
for data in [b'\\x01\\x00', b'\\xff\\x03', b'\\x01\\x04', b'\\x00\\x3c', b'\\x01\\x80']:
    value = struct.unpack('<e', data)[0]
    print('e', data.hex(), value, struct.pack('<e', value).hex())
""",
    "pack_into_contract": """import struct
for call in ['module', 'class']:
    buffer = bytearray(4)
    try:
        if call == 'module':
            struct.pack_into('<i', buffer, 0)
        else:
            struct.Struct('<i').pack_into(buffer, 0)
    except Exception as exc:
        print(call, type(exc).__name__, exc)
for buffer in [b'0123', '0123', [1, 2, 3, 4], 5]:
    try:
        struct.pack_into('<i', buffer, 0, 1)
        print('buffer ok', buffer)
    except Exception as exc:
        print('buffer', type(exc).__name__, exc)
try:
    struct.Struct('<i').pack_into(b'0123', 0, 1)
except Exception as exc:
    print('struct buffer', type(exc).__name__, exc)
for fmt in ['4p', '4s']:
    try:
        struct.pack(fmt, 'abc')
    except Exception as exc:
        print(fmt, type(exc).__name__, exc)
try:
    struct.pack_into('<i', bytearray(4), -100)
except Exception as exc:
    print('count first', type(exc).__name__, exc)
try:
    struct.pack_into('<i', b'0123', -100, 1)
except Exception as exc:
    print('type first', type(exc).__name__, exc)
for fmt in ['999999999999999999999i', '2305843009213693951i',
            '2305843009213693952i', '9223372036854775807s',
            '9223372036854775808s', '999999999999999999999x',
            '999999999999999999999p', '00000000000000000000000000000003i']:
    try:
        print('size', fmt, struct.calcsize(fmt))
    except Exception as exc:
        print('size', fmt, type(exc).__name__, exc)
""",
    "pack_into_buffer_type": """import struct

class Foo:
    pass

class _AilArray:
    def __init__(self):
        self.typecode = 'B'
        self.itemsize = 1
        self.data = [0, 0, 0, 0]
    def __len__(self):
        return 4

class Box:
    def __init__(self, b):
        self.b = b
        self.items = [b]
        self.table = {'k': b}

def through_arg(b):
    return b

for buffer in [None, Foo(), Foo, 1, 1.0, True, 'x', b'0123', [], (), {},
               bytearray(8), _AilArray()]:
    for call in ['module', 'class']:
        try:
            if call == 'module':
                struct.pack_into('<i', buffer, 0, 7)
            else:
                struct.Struct('<i').pack_into(buffer, 0, 7)
            print(call, 'ok')
        except Exception as exc:
            print(call, type(exc).__name__, exc)
    if isinstance(buffer, bytearray):
        try:
            struct.pack_into('<i', through_arg(buffer), 0, 7)
            struct.pack_into('<i', Box(buffer).items[0], 0, 7)
            struct.Struct('<i').pack_into(Box(buffer).table['k'], 0, 7)
            print('routes ok', buffer.hex())
        except Exception as exc:
            print('routes', type(exc).__name__, exc)
""",
    "pack_into_array": """import array
import struct

class Box:
    def __init__(self, b):
        self.b = b
        self.items = [b]
        self.table = {'k': b}

def through_arg(b):
    return b

for tc in ['B', 'b', 'h', 'H', 'i', 'I', 'l', 'L', 'q', 'Q', 'd']:
    for fmt in ['<i', '>i', '<h', '=q']:
        a = array.array(tc, [0] * 4)
        try:
            struct.pack_into(fmt, a, 0, 0x01020304)
            print(tc, fmt, list(a))
        except Exception as exc:
            print(tc, fmt, type(exc).__name__, exc)

for off in [-40, -17, -16, -15, -8, -4, -1, 0, 1, 3, 12, 13, 16, 17]:
    a = array.array('i', [0] * 4)
    try:
        struct.pack_into('<i', a, off, 7)
        print('off', off, list(a))
    except Exception as exc:
        print('off', off, type(exc).__name__, exc)

a = array.array('B', [0] * 8)
struct.pack_into('<i', through_arg(a), 0, 7)
struct.pack_into('<i', Box(a).items[0], 4, 8)
struct.Struct('<i').pack_into(Box(a).table['k'], 0, 9)
print('routes', list(a), a)

a = array.array('b', [0] * 4)
struct.pack_into('<i', a, 0, -1)
print('signed', list(a))
a = array.array('d', [0.0] * 2)
struct.pack_into('<d', a, 0, 1.5)
print('double', list(a))
a = array.array('H', [0] * 4)
struct.pack_into('>H', a, 1, 0x1234)
print('unaligned', list(a))
""",
    "negative_offsets": """import struct
for offset in [-20, -11, -10, -5, -4, -1, 0, 6, 7]:
    try:
        print('uf', offset, struct.unpack_from('<i', b'0123456789', offset))
    except Exception as e:
        print('uf', offset, type(e).__name__, e)
for offset in [-20, -11, -10, -6, -5, -4, -1, 0, 7]:
    buf = bytearray(10)
    try:
        struct.pack_into('<i', buf, offset, 0x41424344)
        print('pi', offset, bytes(buf).hex())
    except Exception as e:
        print('pi', offset, type(e).__name__, e)
s = struct.Struct('<i')
for offset in [-20, -11, -10, -5, -4, -1, 0, 6, 7]:
    try:
        print('suf', offset, s.unpack_from(b'0123456789', offset))
    except Exception as e:
        print('suf', offset, type(e).__name__, e)
""",
}


class StructPrograms(unittest.TestCase):
    def compare_source(self, name, text):
        with tempfile.TemporaryDirectory() as directory:
            source, exe = Path(directory, name + ".py"), Path(directory, name)
            source.write_text(text, encoding="utf-8")
            built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                                    "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                                   text=True, timeout=1800, env=dict(os.environ, AIL_NO_CACHE="1"))
            self.assertEqual(built.returncode, 0, "%s\n%s%s" % (
                name, built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], cwd=directory,
                                  capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s\n%s" % (
                name, got.stderr.decode("utf-8", "replace")))
            if got.stdout != want.stdout:
                want_lines, got_lines = want.stdout.decode("utf-8", "replace").splitlines(), \
                    got.stdout.decode("utf-8", "replace").splitlines()
                for line, (a, b) in enumerate(zip(want_lines, got_lines), 1):
                    if a != b:
                        self.fail("%s line %d:\n  compiled: %r\n  CPython:  %r" % (name, line, b, a))
                self.fail("%s: output lengths differ" % name)

    def compare(self, program):
        self.compare_source(program.stem, program.read_text(encoding="utf-8"))

    def test_programs(self):
        programs = sorted(PROGRAMS.glob("*.py"))
        self.assertEqual(len(programs), 12)
        for program in programs:
            with self.subTest(program=program.name):
                self.compare(program)

    def test_review_edges(self):
        for name, text in sorted(EDGE_PROGRAMS.items()):
            with self.subTest(program=name):
                self.compare_source(name, text)


if __name__ == "__main__":
    unittest.main()
