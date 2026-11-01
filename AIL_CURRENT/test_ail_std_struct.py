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
