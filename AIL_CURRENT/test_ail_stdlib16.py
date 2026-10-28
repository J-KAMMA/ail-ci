"""Library batch 16: struct.pack, unpack, unpack_from and calcsize over a string-literal format.

Two layers:

* prelude_struct.py (the code the compiler adds) is plain Python, so it runs next to CPython's struct for
  generated formats and values: pack, unpack, unpack_from, sizes and error messages must agree;
* ordinary Python programs are compiled with the Python syntax, once with the default build and once with
  AIL_IR=1, run on generated stdin, and must print the same bytes as CPython 3.12 (and exit the same way).

The declared differences (DIFFERENCES.md C-series): the float codes (e f d) and run-time formats are refused;
struct.error is a ValueError on this path, so a program compares the message rather than the exception class.
"""
import os
import random
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROGRAM = r"""import struct
import sys


class Box:
    def __init__(self, v: int) -> None:
        self.v = v

    def plus(self, k: int) -> int:
        return self.v + k


def main() -> None:
    vals = [int(t) for t in sys.stdin.read().split()]
    a, b, c = vals[0], vals[1], vals[2]
    xs = [a, b, c]
    d = {'k': c}
    box = Box(b)
    print(struct.calcsize('>IhQ'), struct.calcsize('@bi'), struct.calcsize('<IIQQQQQQ'), struct.calcsize('P'))
    print(struct.calcsize('@ib'), struct.calcsize('@b0q'), struct.calcsize('@i0q'), struct.calcsize('4s'))
    raw = struct.pack('>IhQ', a, b, c)
    print(raw.hex(), len(raw))
    print(struct.unpack('>IhQ', raw))
    print(struct.unpack_from('>h', raw, 4), struct.unpack_from('>Q', raw, 8))
    print(struct.unpack_from('>I', b'....' + raw[0:4], 4))
    print(struct.unpack('>4s', b'abcd'), struct.unpack('>4p', b'\x02ab\x00\x00'))
    print(struct.unpack('>c?', b'Z\x01'))
    print(struct.pack('<4i', a + 1, xs[1], box.v, d['k']).hex())
    print(struct.pack('<2H', xs[0], box.plus(xs[2])).hex())
    print(struct.pack('@bi', a, b).hex(), struct.pack('@ib', a, b).hex())
    print(struct.pack('@ci', b'q', a).hex(), struct.pack('@ic', a, b'q').hex())
    print(struct.pack('>4s', b'abcdef').hex(), struct.pack('>4p', b'abcdef').hex())
    print(struct.pack('>?', a).hex(), struct.pack('>?', 0).hex())
    try:
        print('B', struct.pack('>B', a).hex())
    except Exception as e:
        print('B', e)
    try:
        print('b', struct.pack('>b', a).hex())
    except Exception as e:
        print('b', e)
    try:
        print('I', struct.pack('>I', a).hex())
    except Exception as e:
        print('I', e)
    try:
        print('q', struct.pack('>q', a).hex())
    except Exception as e:
        print('q', e)
    try:
        print(struct.pack('B', 256))
    except Exception as e:
        print(e)
    try:
        print(struct.pack('c', b'ab'))
    except Exception as e:
        print(e)
    try:
        print(struct.unpack('i', b'abc'))
    except Exception as e:
        print(e)
    try:
        print(struct.unpack_from('i', b'abcdefgh', 5))
    except Exception as e:
        print(e)
    try:
        print(struct.pack('ii', 1))
    except Exception as e:
        print(e)


main()
"""


def numbers():
    return [
        "1 2 3\n",
        "305419896 -2 18446744073709551615\n",
        "0 0 0\n",
        "255 127 4294967295\n",
        "-1 -128 0\n",
        "2147483647 -2147483648 9223372036854775807\n",
    ]


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


class PreludeStruct(unittest.TestCase):
    """prelude_struct.py against struct for generated formats and values."""

    def test_matches_struct(self):
        import prelude_struct as P
        rnd = random.Random(16)
        codes = 'xcbB?hHiIlLqQspPNn'
        orders = '@=<>!'
        for _ in range(6000):
            order = rnd.choice(orders)
            parts, fields = [], []
            for _ in range(rnd.randint(1, 6)):
                code = rnd.choice(codes)
                if code in 'nNP' and order != '@':
                    code = 'i'
                if code in 'sp':
                    count = rnd.randint(0, 8)
                    if code == 'p' and count == 0:
                        count = 1
                    parts.append(str(count) + code)
                    fields.append((code, count))
                elif code == 'x':
                    count = rnd.randint(0, 8)
                    parts.append(str(count) + 'x' if count != 1 else 'x')
                    fields.append((code, count))
                else:
                    count = rnd.randint(0, 4)
                    parts.append(str(count) + code if count != 1 else code)
                    fields.append((code, count))
            fmt = order + ''.join(parts)
            size = struct.calcsize(fmt)
            self.assertEqual(P._ail_struct_layout(fmt)[2], size, fmt)
            args = []
            for code, count in fields:
                if code == 'x':
                    continue
                if code in 'sp':
                    args.append(bytes(rnd.randrange(256) for _ in range(rnd.randint(0, 10))))
                else:
                    for _ in range(count):
                        if code == 'c':
                            args.append(bytes([rnd.randrange(256)]))
                        elif code == '?':
                            args.append(rnd.choice([True, False, 0, 1, 2]))
                        else:
                            width = struct.calcsize(order + code)
                            signed = code in 'bhilqn'
                            low = -(1 << (width * 8 - 1)) if signed else 0
                            high = (1 << (width * 8 - 1)) - 1 if signed else (1 << (width * 8)) - 1
                            args.append(rnd.randint(low, high))
            want = struct.pack(fmt, *args)
            got = P._ail_struct_pack(fmt, args)
            self.assertEqual(got, want, (fmt, args))
            self.assertEqual(P._ail_struct_unpack(fmt, want), struct.unpack(fmt, want), (fmt, want))
            offset = rnd.randint(0, 5)
            pad = bytes(rnd.randrange(256) for _ in range(offset))
            data = pad + want
            self.assertEqual(P._ail_struct_unpack_from(fmt, data, offset),
                             struct.unpack_from(fmt, data, offset), (fmt, offset))
            offsets = [rnd.randint(len(data) + 1, len(data) + 3)]
            if data:
                offsets.append(rnd.randint(-len(data), -1))
            for offset in offsets:
                try:
                    want_from = ('ok', struct.unpack_from(fmt, data, offset))
                except Exception as exc:
                    want_from = ('err', str(exc))
                try:
                    got_from = ('ok', P._ail_struct_unpack_from(fmt, data, offset))
                except Exception as exc:
                    got_from = ('err', str(exc))
                self.assertEqual(got_from, want_from, (fmt, data, offset))

    def test_unpack_from_offsets(self):
        import prelude_struct as P
        cases = [
            ('i', b'abcdefgh', -8), ('h', b'abc', -3), ('B', b'abc', -1), ('0s', b'abc', -3),
            ('i', b'abcdefgh', -1), ('i', b'abc', -3), ('B', b'abc', -4), ('0s', b'abc', 4),
            ('i', b'abc', 0), ('h', b'abcdefgh', 7), ('4s', b'abcdefgh', 5),
        ]
        for fmt, data, offset in cases:
            with self.subTest((fmt, data, offset)):
                try:
                    want = ('ok', struct.unpack_from(fmt, data, offset))
                except Exception as exc:
                    want = ('err', str(exc))
                try:
                    got = ('ok', P._ail_struct_unpack_from(fmt, data, offset))
                except Exception as exc:
                    got = ('err', str(exc))
                self.assertEqual(got, want)

    def test_unpack_from_non_integer_offset(self):
        import prelude_struct as P

        class Ix:
            def __init__(self, v):
                self.v = v

            def __index__(self):
                return self.v

        class Bad:
            def __index__(self):
                return 'x'

        class NoIx:
            pass

        def outcome(fn):
            try:
                return ('ok', fn())
            except TypeError as exc:
                return ('err', type(exc).__name__, str(exc))
            except Exception as exc:
                return ('err', '', str(exc))

        cases = [1.5, '1', None, b'1', [1], NoIx(), Bad(), Ix(1), Ix(-1), True, False]
        for offset in cases:
            with self.subTest(offset):
                want = outcome(lambda: struct.unpack_from('i', b'abcdefgh', offset))
                got = outcome(lambda: P._ail_struct_unpack_from('i', b'abcdefgh', offset))
                self.assertEqual(got, want)

    def test_error_messages(self):
        import prelude_struct as P
        cases = [
            (lambda: P._ail_struct_pack('B', [256]), lambda: struct.pack('B', 256)),
            (lambda: P._ail_struct_pack('b', [-129]), lambda: struct.pack('b', -129)),
            (lambda: P._ail_struct_pack('H', [-1]), lambda: struct.pack('H', -1)),
            (lambda: P._ail_struct_pack('c', [b'ab']), lambda: struct.pack('c', b'ab')),
            (lambda: P._ail_struct_pack('c', [bytearray(b'a')]), lambda: struct.pack('c', bytearray(b'a'))),
            (lambda: P._ail_struct_pack('4s', ['ab']), lambda: struct.pack('4s', 'ab')),
            (lambda: P._ail_struct_pack('4p', ['ab']), lambda: struct.pack('4p', 'ab')),
            (lambda: P._ail_struct_pack('ii', [1]), lambda: struct.pack('ii', 1)),
            (lambda: P._ail_struct_pack('i', [1.0]), lambda: struct.pack('i', 1.0)),
            (lambda: P._ail_struct_unpack('i', b'abc'), lambda: struct.unpack('i', b'abc')),
            (lambda: P._ail_struct_unpack('i', b'abcde'), lambda: struct.unpack('i', b'abcde')),
            (lambda: P._ail_struct_unpack_from('i', b'abcdefgh', 5),
             lambda: struct.unpack_from('i', b'abcdefgh', 5)),
            (lambda: P._ail_struct_unpack_from('i', b'abcdefgh', -1),
             lambda: struct.unpack_from('i', b'abcdefgh', -1)),
        ]
        for mine, ref in cases:
            with self.assertRaises(Exception) as got:
                mine()
            with self.assertRaises(Exception) as want:
                ref()
            self.assertIsInstance(got.exception, ValueError)
            self.assertEqual(str(got.exception), str(want.exception))


class CompiledPrograms(unittest.TestCase):
    def check(self, text, inputs, ir, **env):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(env, AIL_IR="1" if ir else "0")
            built, source, exe = compile_python(directory, text, "p_struct", **env)
            self.assertEqual(built.returncode, 0, "AIL_IR=%s\n%s%s" % (env["AIL_IR"], built.stdout, built.stderr))
            Path(directory, "oracle.py").write_text(text, encoding="utf-8")
            for k, stdin in enumerate(inputs):
                want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))], input=stdin.encode(),
                                      capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, "input %d: %s" % (k, got.stderr[-300:]))
                self.assertEqual(got.stdout, want.stdout, "input %d (AIL_IR=%s)" % (k, env["AIL_IR"]))

    def test_program_matches_cpython(self):
        for ir in (False, True):
            with self.subTest(ir=ir):
                self.check(PROGRAM, numbers(), ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            "float": ("import struct\n\nprint(struct.pack('<f', 1.5))\n", "single float"),
            "double": ("import struct\n\nprint(struct.unpack('<d', b'12345678'))\n", "double float"),
            "dynamic": ("import struct\n\nfmt = '<I'\nprint(struct.pack(fmt, 1))\n", "string literal"),
            "struct": ("import struct\n\ns = struct.Struct('<I')\nprint(s.pack(1))\n", "struct.Struct is not built"),
            "pack_into": ("import struct\n\nb = bytearray(4)\nstruct.pack_into('<I', b, 0, 1)\n", "struct.pack_into"),
            "iter_unpack": ("import struct\n\nprint(list(struct.iter_unpack('<I', b'12345678')))\n", "struct.iter_unpack"),
            "error": ("import struct\n\ntry:\n    struct.pack('B', 256)\nexcept struct.error:\n    print('bad')\n",
                      "struct.error"),
            "star": ("import struct\n\nprint(struct.pack('>I', *[1]))\n", "starred"),
            "zero_p": ("import struct\n\nprint(struct.unpack('0p', b''))\n", "repeats 'p' zero times"),
            "zero_p_from": ("import struct\n\nprint(struct.unpack_from('0p', b'abc', 0))\n",
                            "repeats 'p' zero times"),
            "zero_p_inner": ("import struct\n\nprint(struct.unpack('>i0p', b'1234'))\n",
                             "repeats 'p' zero times"),
            "shadow_global": ("import struct\n\n\nclass C:\n    def pack(self, fmt, v):\n        return 'custom'\n\n\n"
                              "struct = C()\nprint(struct.pack('>I', 1))\n", "is rebound here"),
            "shadow_param": ("import struct\n\n\ndef f(struct):\n    return struct.pack('>I', 1)\n\n\nprint(f(1))\n",
                             "is rebound here"),
            "shadow_alias": ("import struct as st\n\n\nclass C:\n    def pack(self, fmt, v):\n        return 'alias'\n\n\n"
                             "st = C()\nprint(st.pack('>H', 2))\n", "is rebound here"),
            "shadow_from": ("from struct import pack\n\n\npack = lambda fmt, v: 'x'\nprint(pack('>I', 1))\n",
                            "is rebound here"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


class UnchangedPrograms(unittest.TestCase):
    PLAIN = [
        "import sys\n\nfor i, line in enumerate(sys.stdin):\n    print(i, line.strip())\n",
        "# struct is only a word in a comment here\nprint(1)\n",
        "import zlib\n\nprint(zlib.crc32(b'x'))\n",
    ]

    def test_other_programs_keep_their_text(self):
        import structlib
        for text in self.PLAIN:
            with self.subTest(text[:30]):
                notes = []
                self.assertIs(structlib.rewrite_text(text, notes), text)
                self.assertEqual(notes, [])

    def test_mentions_do_not_raise(self):
        import structlib
        text = "structure = {'struct': 1}\nprint(structure)\n"
        self.assertIs(structlib.rewrite_text(text, []), text)


if __name__ == "__main__":
    unittest.main()
