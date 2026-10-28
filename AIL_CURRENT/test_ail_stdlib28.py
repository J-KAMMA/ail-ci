"""Library batch 5: `struct`, compared with CPython 3.12 on both builds.

`struct.pack`, `unpack`, `unpack_from`, `pack_into` and `calcsize` are lowered from a literal format string:
the compiler parses the format, `calcsize` becomes its integer size and the other calls become helpers
generated for that one format.  The integer codes b B h H i I l L q Q, bool ?, char c, fixed and pascal
strings s p, padding x, repeat counts, whitespace and the standard orders < > ! = are built; the float codes
e f d, the native order @ (also the default), n N P, Struct, iter_unpack, a non-literal format and a wrong
value count are refused by name.  `struct.error` is the exception the helpers raise, with CPython's messages.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


TYPES = r'''import struct


def main() -> None:
    print(struct.calcsize('<'), struct.calcsize('<0I'), struct.calcsize('<3s2xI'), struct.calcsize('>I'))
    print(struct.calcsize('<b'), struct.calcsize('<B'), struct.calcsize('<h'), struct.calcsize('<H'))
    print(struct.calcsize('<i'), struct.calcsize('<I'), struct.calcsize('<l'), struct.calcsize('<L'))
    print(struct.calcsize('<q'), struct.calcsize('<Q'), struct.calcsize('>b'), struct.calcsize('>H'))
    print(struct.calcsize('>I'), struct.calcsize('>q'), struct.calcsize('>Q'), struct.calcsize('=I'), struct.calcsize('!H'))
    print(struct.pack('<b', -128).hex(), struct.pack('<b', 127).hex())
    print(struct.pack('<B', 0).hex(), struct.pack('<B', 255).hex())
    print(struct.pack('<h', -32768).hex(), struct.pack('<h', 32767).hex())
    print(struct.pack('<H', 65535).hex())
    print(struct.pack('<i', -2147483648).hex(), struct.pack('<i', 2147483647).hex())
    print(struct.pack('<I', 4294967295).hex())
    print(struct.pack('<q', -9223372036854775807 - 1).hex(), struct.pack('<q', 9223372036854775807).hex())
    print(struct.pack('<Q', 9223372036854775807).hex())
    print(struct.pack('>q', -2).hex(), struct.pack('>Q', 3).hex(), struct.pack('=I', 4).hex(), struct.pack('!H', 5).hex())
    print(struct.unpack('<bBhHiIlLqQ', struct.pack('<bBhHiIlLqQ', -1, 2, -3, 4, -5, 6, -7, 8, -9, 10)))
    print(struct.unpack('>bBhHiIlLqQ', struct.pack('>bBhHiIlLqQ', -1, 2, -3, 4, -5, 6, -7, 8, -9, 10)))
    print(struct.pack('<?2c4s4p2x', 0, b'a', b'b', b'abcd', b'xy').hex())
    print(struct.unpack('<?2c4s4p2x', bytes.fromhex('00616261626364027879000000')))
    print(struct.pack('<0p', b'abc').hex(), struct.pack('<1p', b'abc').hex(), struct.pack('<4p', b'abcdef').hex())
    print(struct.unpack('<4p', struct.pack('<4p', b'abc')), struct.unpack('<4p', b'\xffabc'))
    print(struct.pack('<3s', b'a').hex(), struct.pack('<3s', b'abcdef').hex(), struct.pack('<3s', b'').hex())
    print(struct.pack('<0s', b'abc').hex(), struct.pack('<2I', 1, 2).hex(), struct.pack('<II', 1, 2).hex())
    print(struct.pack('<2x').hex(), struct.pack('<').hex(), struct.pack('>').hex())
    print(struct.calcsize(''), struct.calcsize(' '), struct.pack('').hex(), struct.unpack('', b''))
    print(struct.unpack_from('', b'abc', 2))
    b = bytearray(b'0123456789abcdef')
    struct.pack_into('>I', b, 3, 0x01020304)
    print(bytes(b).hex())
    print(struct.unpack_from('>I', b, 3), struct.unpack_from('<H', b))
    print(struct.unpack_from('<3s', b, 13))
    print(struct.unpack('<II', struct.pack('<II', 7, 8)))
    print(struct.unpack('>III', struct.pack('>III', 1, 2, 3)))


main()
'''

ROUTES = r'''import struct as st
from struct import pack, unpack, calcsize, unpack_from


class Box:
    def __init__(self, n: int, data: bytes) -> None:
        self.n = n
        self.data = data


def pack_arg(n: int) -> bytes:
    return st.pack('>I', n)


def make(n: int) -> bytes:
    return pack('<H', n)


def main() -> None:
    nums = [10, 20, 30]
    d = {'k': 40}
    box = Box(50, b'\x00\x00\x00\x33')
    print(st.pack('>I', nums[1]).hex())
    print(st.unpack('>I', box.data)[0])
    print(st.pack('<H', d['k']).hex())
    print(pack_arg(nums[2]).hex())
    print(make(d['k']).hex())
    print(pack('<H', box.n).hex())
    print(calcsize('<H'), calcsize('<I'))
    print(unpack('<H', b'\x00\x07')[0])
    print(unpack_from('<H', b'\x00\x07\x00\x08', 2)[0])
    print(struct_pack := st.pack('<H', 9))
    print(st.unpack('<H', struct_pack)[0])


main()
'''

ERRORS = r'''import struct


def show(fn) -> None:
    try:
        print(fn())
    except struct.error as e:
        print(type(e).__name__, str(e))
    except Exception as e:
        print(type(e).__name__, str(e))


def main() -> None:
    show(lambda: struct.pack('<B', 256))
    show(lambda: struct.pack('<B', -1))
    show(lambda: struct.pack('<b', 128))
    show(lambda: struct.pack('<b', -129))
    show(lambda: struct.pack('<H', 65536))
    show(lambda: struct.pack('<I', 4294967296))
    show(lambda: struct.pack('<Q', -1))
    show(lambda: struct.pack('<q', 9223372036854775807 + 1))
    show(lambda: struct.pack('<i', 'x'))
    show(lambda: struct.pack('<i', 1.5))
    show(lambda: struct.pack('<c', b''))
    show(lambda: struct.pack('<c', b'ab'))
    show(lambda: struct.pack('<c', 'a'))
    show(lambda: struct.pack('<c', bytearray(b'a')))
    show(lambda: struct.pack('<3s', 'abc'))
    show(lambda: struct.pack('<3s', 3))
    show(lambda: struct.unpack('<I', b'abc'))
    show(lambda: struct.unpack('<I', b'abcde'))
    show(lambda: struct.unpack_from('<I', b'abc'))
    show(lambda: struct.unpack_from('<I', b'abcd', -1))
    show(lambda: struct.unpack_from('<I', b'abcd', 4))
    show(lambda: struct.pack_into('<I', bytearray(2), 0, 1))
    show(lambda: struct.pack_into('<I', bytearray(4), -1, 1))
    show(lambda: struct.pack_into('<I', b'01234567', 0, 1))
    show(lambda: struct.pack_into('<I', '01234567', 0, 1))
    show(lambda: struct.pack('<B', True))
    show(lambda: struct.unpack('<?', b'\x02'))
    show(lambda: struct.unpack('<?', b'\x00'))


main()
'''

ERROR_ONLY = r'''import struct


def main() -> None:
    print(struct.calcsize('<I'))
    try:
        x = 1 // 0
    except struct.error as e:
        print('struct', e)
    except ZeroDivisionError as e:
        print('zero', str(e))


main()
'''

CASES = [
    ('types', TYPES),
    ('routes', ROUTES),
    ('errors', ERRORS),
    ('error_only', ERROR_ONLY),
]


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, ir):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(AIL_IR="1" if ir else "0")
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s" % (name, env["AIL_IR"], built.stdout, built.stderr))
            Path(directory, "oracle.py").write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))],
                                  capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s (AIL_IR=%s): %s" % (name, env["AIL_IR"], got.stderr[-400:]))
            if got.stdout != want.stdout:
                a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                for n, (x, y) in enumerate(zip(a, b)):
                    if x != y:
                        self.fail("%s (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                                  % (name, env["AIL_IR"], n + 1, x, y))
                self.fail("%s (AIL_IR=%s): %d lines against %d" % (name, env["AIL_IR"], len(a), len(b)))

    def test_programs_match_cpython(self):
        for name, text in CASES:
            for ir in (False, True):
                with self.subTest(program=name, ir=ir):
                    self.check(name, text, ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        head = "import struct\n\n\ndef main() -> None:\n"
        cases = {
            "float": (head + "    print(struct.pack('<f', 1.5))\n\n\nmain()\n", "the float format 'f' is not built"),
            "double": (head + "    print(struct.unpack('<d', b'\\x00' * 8))\n\n\nmain()\n",
                       "the float format 'd' is not built"),
            "native": (head + "    print(struct.pack('@I', 1))\n\n\nmain()\n", "native byte order"),
            "default_order": (head + "    print(struct.pack('I', 1))\n\n\nmain()\n", "native byte order"),
            "pointer": (head + "    print(struct.pack('<P', 1))\n\n\nmain()\n", "native-only"),
            "Struct": (head + "    s = struct.Struct('<I')\n    print(s.size)\n\n\nmain()\n",
                       "struct.Struct is not built"),
            "iter_unpack": (head + "    for x in struct.iter_unpack('<I', b'\\x00\\x00\\x00\\x01'):\n        print(x)\n\n\nmain()\n",
                            "struct.iter_unpack is not built"),
            "dynamic": (head + "    fmt = '<I'\n    print(struct.pack(fmt, 1))\n\n\nmain()\n",
                        "format string has to be a string literal"),
            "count": (head + "    print(struct.pack('<II', 1))\n\n\nmain()\n", "takes 2 value(s)"),
            "value": ("import struct\n\nf = struct.pack\nprint(f)\n", "struct.pack used here is not built"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


if __name__ == "__main__":
    unittest.main()
