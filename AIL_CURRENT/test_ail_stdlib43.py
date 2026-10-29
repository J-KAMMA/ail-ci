"""Library batch 43: `struct` with a literal format, compared with CPython 3.12.

The format is known when the program is built, so `calcsize` folds and `pack` / `unpack` / `pack_into` /
`unpack_from` become small generated functions. The integer, bool, char, string and padding codes are built
for every byte order (`< > = ! @`, with native alignment); float, double, half-float and Pascal-string codes
and a non-literal format are refused by name.

Every program is ordinary Python. CPython runs it as the oracle; the compiled program prints the same bytes
on the default build (which may use the general path for `int.from_bytes`) and on the forced general build.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_python(directory, text, name, general=False, typed_only=False):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    env = dict(os.environ)
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    env["AIL_NO_CACHE"] = "1"
    env["AIL_QUIET_FALLBACK"] = "1"
    if general:
        env["AIL_UNIFIED_FORCE"] = "1"
    if typed_only:
        env["AIL_NO_GENERAL"] = "1"
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=env)
    return built, source, exe


CASES = [
    ('<b', [-128]), ('<b', [127]), ('<b', [0]), ('<B', [0]), ('<B', [255]),
    ('<h', [-32768]), ('<h', [32767]), ('<H', [0]), ('<H', [65535]),
    ('<i', [-2 ** 31]), ('<i', [2 ** 31 - 1]), ('<I', [0]), ('<I', [2 ** 32 - 1]),
    ('<l', [-2 ** 31]), ('<l', [2 ** 31 - 1]), ('<L', [0]), ('<L', [2 ** 32 - 1]),
    ('<q', [-2 ** 63]), ('<q', [2 ** 63 - 1]), ('<Q', [0]), ('<Q', [2 ** 64 - 1]),
    ('>i', [-2 ** 31]), ('>i', [2 ** 31 - 1]), ('>q', [-2 ** 63]), ('>q', [2 ** 63 - 1]),
    ('@b', [-128]), ('@b', [127]), ('@h', [-32768]), ('@h', [32767]),
    ('@i', [-2 ** 31]), ('@i', [2 ** 31 - 1]), ('@l', [-2 ** 63]), ('@l', [2 ** 63 - 1]),
    ('@q', [-2 ** 63]), ('@q', [2 ** 63 - 1]), ('@n', [-2 ** 63]), ('@n', [2 ** 63 - 1]),
    ('@N', [0]), ('@N', [2 ** 64 - 1]), ('@P', [-1]), ('@P', [-2 ** 63]), ('@P', [2 ** 64 - 1]),
    ('<?', [0]), ('<?', [1]), ('<?', [2]), ('<?', [None]), ('<?', ['x']), ('<?', [[]]),
    ('<c', [b'a']), ('<c', [b'Z']), ('<2c', [b'a', b'b']),
    ('<s', [b'']), ('<s', [b'a']), ('<s', [b'abc']),
    ('<2s', [b'']), ('<2s', [b'a']), ('<2s', [b'ab']), ('<2s', [b'abc']),
    ('<2s', [bytearray(b'ab')]), ('<s', [bytearray(b'')]),
    ('<4x', []), ('<x', []), ('<0s', [b'']), ('<0s', [b'x']), ('<0i', []),
    ('@bi', [1, 2]), ('@ib', [1, 2]), ('@bq', [1, 2]), ('@qb', [1, 2]), ('@bh', [1, 2]), ('@hb', [1, 2]),
    ('@bI', [1, 2]), ('@I b', [2, 1]), ('@b3xi', [7, 9]), ('@b3x', [7]), ('@?b', [True, 7]), ('@b?', [7, True]),
    ('@bx', [7]), ('@xb', [7]), ('=bi', [1, 2]), ('=l', [-1]), ('=L', [2 ** 32 - 1]), ('!H', [258]),
    ('<2i', [1, 2]), ('>2i', [1, 2]), ('<3h', [1, 2, 3]), ('@3i', [1, 2, 3]), ('<i2s', [5, b'ab']),
]

ERROR_CASES = [
    ('pack_b_low', 'struct.pack("<b", -129)'),
    ('pack_b_high', 'struct.pack("<b", 128)'),
    ('pack_B_low', 'struct.pack("<B", -1)'),
    ('pack_B_high', 'struct.pack("<B", 256)'),
    ('pack_h_low', 'struct.pack("<h", -32769)'),
    ('pack_h_high', 'struct.pack("<h", 32768)'),
    ('pack_i_low', 'struct.pack("<i", -2**31-1)'),
    ('pack_i_high', 'struct.pack("<i", 2**31)'),
    ('pack_q_low', 'struct.pack("<q", -2**63-1)'),
    ('pack_q_high', 'struct.pack("<q", 2**63)'),
    ('pack_Q_low', 'struct.pack("<Q", -1)'),
    ('pack_Q_high', 'struct.pack("<Q", 2**64)'),
    ('pack_P_high', 'struct.pack("@P", 2**64)'),
    ('pack_P_low', 'struct.pack("@P", -2**63-1)'),
    ('pack_int_float', 'struct.pack("<i", 1.5)'),
    ('pack_int_str', 'struct.pack("<i", "x")'),
    ('pack_char_str', 'struct.pack("<c", "a")'),
    ('pack_char_bytearray', 'struct.pack("<c", bytearray(b"a"))'),
    ('pack_char_long', 'struct.pack("<c", b"ab")'),
    ('pack_s_str', 'struct.pack("<2s", "ab")'),
    ('pack_s_bytearray', 'struct.pack("<2s", bytearray(b"ab"))'),
    ('pack_toomany', 'struct.pack("<i", 1, 2)'),
    ('pack_toofew', 'struct.pack("<i")'),
    ('unpack_short', 'struct.unpack("<i", b"\\0\\0\\0")'),
    ('unpack_long', 'struct.unpack("<i", b"\\0"*5)'),
    ('unpack_from_short', 'struct.unpack_from("<i", b"\\0\\0\\0")'),
    ('unpack_from_neg', 'struct.unpack_from("<i", b"\\0"*20, -1)'),
    ('unpack_from_neg_range', 'struct.unpack_from("<i", b"\\0"*20, -21)'),
    ('unpack_from_big', 'struct.unpack_from("<i", b"\\0"*20, 100)'),
    ('unpack_from_float', 'struct.unpack_from("<i", b"\\0"*20, 1.0)'),
    ('unpack_from_str', 'struct.unpack_from("<i", b"\\0"*20, "1")'),
    ('unpack_from_none', 'struct.unpack_from("<i", b"\\0"*20, None)'),
    ('pack_into_bytes', 'struct.pack_into("<i", b"", 0, 1)'),
    ('pack_into_small', 'struct.pack_into("<i", bytearray(2), 0, 1)'),
    ('pack_into_neg', 'struct.pack_into("<i", bytearray(4), -1, 1)'),
    ('pack_into_neg_range', 'struct.pack_into("<i", bytearray(4), -5, 1)'),
    ('pack_into_float', 'struct.pack_into("<i", bytearray(8), 1.0, 1)'),
    ('pack_into_str', 'struct.pack_into("<i", bytearray(8), "1", 1)'),
]


def value_program():
    lines = ["import struct", "", "", "def main() -> None:"]
    for fmt, values in CASES:
        args = ", ".join(repr(value) for value in values)
        call = "struct.pack(%r%s)" % (fmt, (", " + args) if args else "")
        lines.append("    print(%r, struct.calcsize(%r))" % (fmt, fmt))
        lines.append("    print(list(%s))" % call)
        lines.append("    print(struct.unpack(%r, %s))" % (fmt, call))
    lines += ["", "", "main()"]
    return "\n".join(lines) + "\n"


def error_program():
    lines = ["import struct", "", "", "def main() -> None:"]
    for label, expression in ERROR_CASES:
        lines.append("    try:")
        lines.append("        print(%r, %s)" % (label, expression))
        lines.append("    except struct.error as e:")
        lines.append("        print(%r, type(e).__name__, str(e))" % label)
        lines.append("    except TypeError as e:")
        lines.append("        print(%r, 'TypeError', str(e))" % label)
    lines += ["", "", "main()"]
    return "\n".join(lines) + "\n"


PACK_INTO_PROGRAM = '''import struct


def main() -> None:
    buf = bytearray(12)
    struct.pack_into('<i', buf, 0, 7)
    struct.pack_into('<h', buf, 4, -2)
    struct.pack_into('<2s', buf, 6, b'ab')
    print(list(buf))
    print(struct.unpack_from('<i', buf, 0))
    print(struct.unpack_from('<h', buf, 4))
    print(struct.unpack_from('<2s', buf, 6))
    print(struct.unpack_from('<2s', buf, -6))
    print(struct.unpack_from('<2s', buf, -12))
    struct.pack_into('<2s', buf, -2, b'XY')
    print(list(buf))
    try:
        struct.pack_into('<i', buf, -1, 1)
    except struct.error as e:
        print('neg', type(e).__name__, str(e))
    try:
        struct.unpack_from('<i', buf, 10)
    except struct.error as e:
        print('big', type(e).__name__, str(e))


main()
'''

FROM_IMPORT_PROGRAM = '''import struct as s
from struct import pack as p, unpack, calcsize, error, unpack_from


def main() -> None:
    print(list(s.pack('<h', 258)))
    print(s.unpack('<h', b'\\x02\\x01'))
    print(s.calcsize('@bi'))
    print(list(p('<i', 1)))
    print(unpack('<h', b'\\x02\\x01'))
    print(calcsize('<i'))
    print(unpack_from('<h', b'\\x00\\x02\\x01', 1))
    try:
        unpack('<i', b'')
    except error as e:
        print(type(e).__name__, str(e))
    try:
        s.unpack('<i', b'')
    except s.error as e:
        print(type(e).__name__, str(e))


main()
'''

CALCSIZE_PROGRAM = '''import struct


def main() -> None:
    print(struct.calcsize('<i'), struct.calcsize('@bq'), struct.calcsize('=l'))
    print(struct.calcsize('<f'), struct.calcsize('<d'), struct.calcsize('<e'), struct.calcsize('<p'))
    print(struct.calcsize(b'<i'), struct.calcsize(''))


main()
'''

UNRELATED_PROGRAM = '''def main() -> None:
    struct = 3
    print(struct + 1)


main()
'''


class Stdlib43Tests(unittest.TestCase):
    def build(self, directory, text, name, general=False, typed_only=False):
        built, source, exe = compile_python(directory, text, name, general=general, typed_only=typed_only)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        oracle = Path(directory, name + "_oracle.py")
        oracle.write_text(text, encoding="utf-8")
        return exe, oracle

    def same_both(self, text, name, stdin=b""):
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, name + "_oracle.py")
            oracle.write_text(text, encoding="utf-8")
            expected = subprocess.run([sys.executable, str(oracle)], input=stdin, capture_output=True,
                                      timeout=300)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for general in (False, True):
                suffix = "_g" if general else "_d"
                exe, _ = self.build(directory, text, name + suffix, general=general)
                ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)
                self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout),
                                 ran.stderr[:800].decode("utf-8", "replace"))
            return expected.stdout

    def refused(self, text, wanted, name="prog"):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())

    def test_pack_unpack_and_calcsize_match_cpython(self):
        self.same_both(value_program(), "struct_values")

    def test_errors_match_cpython(self):
        self.same_both(error_program(), "struct_errors")

    def test_pack_into_and_unpack_from_match_cpython(self):
        self.same_both(PACK_INTO_PROGRAM, "struct_into")

    def test_from_import_and_alias_match_cpython(self):
        self.same_both(FROM_IMPORT_PROGRAM, "struct_import")

    def test_calcsize_only_takes_the_typed_path(self):
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "calcsize_oracle.py")
            oracle.write_text(CALCSIZE_PROGRAM, encoding="utf-8")
            expected = subprocess.run([sys.executable, str(oracle)], capture_output=True, timeout=300)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            exe, _ = self.build(directory, CALCSIZE_PROGRAM, "calcsize", typed_only=True)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout),
                             ran.stderr[:800].decode("utf-8", "replace"))

    def test_refusals_are_named(self):
        head = "import struct\n\n\ndef main() -> None:\n"
        self.refused(head + "    print(struct.pack('<f', 1.5))\n\n\nmain()\n",
                     "struct.pack: the format character 'f' (float) is not built")
        self.refused(head + "    print(struct.unpack('<d', b'\\0' * 8))\n\n\nmain()\n",
                     "struct.unpack: the format character 'd' (double) is not built")
        self.refused(head + "    fmt = '<i'\n    print(struct.pack(fmt, 1))\n\n\nmain()\n",
                     "struct.pack: the format must be a string literal")
        self.refused(head + "    s = struct.Struct('<i')\n    print(s.pack(1))\n\n\nmain()\n",
                     "struct.Struct is not built")
        self.refused(head + "    for item in struct.iter_unpack('<i', b'\\0' * 4):\n        print(item)\n\n\nmain()\n",
                     "struct.iter_unpack is not built")
        self.refused(head + "    print(struct.error)\n\n\nmain()\n",
                     "struct.error used here is not built")

    def test_a_name_struct_without_the_import_is_unchanged(self):
        self.same_both(UNRELATED_PROGRAM, "struct_unrelated")


if __name__ == "__main__":
    unittest.main()
