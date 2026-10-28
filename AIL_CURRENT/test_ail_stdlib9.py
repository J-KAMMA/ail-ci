"""`struct` (pack, unpack, calcsize) lowered onto the integer and float codecs, compared with CPython 3.12.

* ordinary Python programs (below) are compiled with the Python syntax, once with the default build and once
  with AIL_IR=1, run on generated stdin, and must print the same bytes as CPython (and exit with the same
  status);
* a pack-only program is also built by the typed path alone (AIL_NO_GENERAL=1);
* every form that is not built (pack_into, Struct, a format that is not a literal string, a format character
  outside the built set, a non-native n/N/P, a wrong value count) is refused here, naming the use;
* programs that do not import struct keep the text they have (stdlib9 returns the same string).

The declared differences (DIFFERENCES.md C-series): int is 64-bit, so an unsigned 64-bit value above
INT64_MAX cannot be represented.
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

PROGRAMS = {}

PROGRAMS['s1'] = r"""import struct
import sys


def main() -> None:
    vals = [int(t) for t in sys.stdin.read().split()]
    if len(vals) >= 2:
        print(struct.pack(">i", vals[0]).hex(), struct.pack("<q", vals[1]).hex())
        print(struct.unpack(">i", struct.pack(">i", vals[0])), struct.unpack("<q", struct.pack("<q", vals[1])))
    print(struct.calcsize(">I"), struct.calcsize("@bi"), struct.calcsize("@bq"), struct.calcsize("=l"), struct.calcsize("@l"))
    print(struct.calcsize("@bqi"), struct.calcsize("@qB"), struct.calcsize("@bd"), struct.calcsize("@bhb"), struct.calcsize("0s"), struct.calcsize("2?"))
    print(struct.calcsize("@b0q"), struct.calcsize("@b0Q"), struct.calcsize("@b0d"), struct.calcsize("@b0i"), struct.calcsize("@b0h"), struct.calcsize("@b0P"), struct.calcsize("@b0n"), struct.calcsize("@b0L"), struct.calcsize("@b0l"))
    print(struct.pack("@b0q", 1).hex(), struct.pack("@b0Q", 1).hex(), struct.pack("@b0d", 1).hex(), struct.pack("@b0P", 1).hex())
    print(struct.calcsize("@2e0N2i2h"), struct.pack("@2e0N2i2h", -0.0, -2.25, 1219495918, 688296495, -14778, 28539).hex())
    print(struct.pack(">I", 305419896).hex())
    print(struct.pack("<hH", -2, 65535).hex())
    print(struct.pack("=bBhHiIlLqQ", -1, 255, -2, 65535, -3, 4294967295, -4, 4294967295, -5, 9223372036854775807).hex())
    print(struct.pack("@bq", 1, 2).hex(), struct.pack("@bqi", 1, 2, 3).hex(), struct.pack("@qB", 1, 2).hex(), struct.pack("@bd", 1, 2.0).hex())
    print(struct.pack("@b2xq", 1, 2).hex(), struct.pack(">b3xi", 1, 2).hex(), struct.pack("x").hex(), struct.pack("3x").hex())
    print(struct.pack("4s", b"ab").hex(), struct.pack("c", b"Z").hex(), struct.pack("?", 0).hex(), struct.pack("?", 3).hex())
    print(struct.pack(">f", 1.5).hex(), struct.pack(">e", 1.5).hex(), struct.pack(">d", 1.25).hex(), struct.pack("<d", -0.0).hex())
    print(struct.pack(">f", 1e-45).hex(), struct.pack(">f", 1e-46).hex(), struct.pack(">e", 1e-45).hex(), struct.pack(">f", float("inf")).hex())
    print(struct.pack(">f", 3.4028235e38).hex(), struct.pack(">e", 65504.0).hex(), struct.pack(">f", float("nan")).hex())
    print(struct.unpack(">I", b"\x12\x34\x56\x78"))
    print(struct.unpack("<bBhH", b"\xff\x00\xff\xfe\xff\xff"))
    print(struct.unpack(">fd", b"\x3f\xc0\x00\x00\x3f\xf4\x00\x00\x00\x00\x00\x00"))
    print(struct.unpack(">e", b"\x3c\x00"), struct.unpack(">f", b"\x00\x00\x00\x01"), struct.unpack(">f", b"\x7f\x80\x00\x00"))
    print(struct.unpack(">q", b"\xff\xff\xff\xff\xff\xff\xff\xff"), struct.unpack("<d", b"\x00\x00\x00\x00\x00\x00\x00\x80"))
    print(struct.unpack("4s", b"ab  "), struct.unpack("5p", b"\x03abc\x00"), struct.unpack("0s", b""))
    print(struct.unpack(">?", b"\x02"))
    print(struct.unpack("@b2xq", struct.pack("@b2xq", 1, 2)))
    try:
        struct.pack("B", 300)
    except ValueError:
        print("wrong")
    except struct.error as exc:
        print("struct.error", exc)
    try:
        struct.pack(">f", 1e300)
    except OverflowError as exc:
        print("overflow", exc)
    try:
        struct.unpack(">I", b"123")
    except struct.error as exc:
        print("unpack-error", exc)
    try:
        struct.pack("c", b"ab")
    except struct.error as exc:
        print("char-error", exc)
    print(struct.pack("4s", bytearray(b"ab")).hex())
    try:
        struct.pack("c", bytearray(b"Z"))
    except struct.error as exc:
        print("char-bytearray", exc)
    print(struct.pack("0s", b"x").hex(), struct.pack("").hex(), struct.unpack("", b""))
    print(struct.pack(">2?2h", 1, 0, -1, 2).hex())
    for v in (3, [1, 2], None):
        try:
            struct.pack("4s", v)
        except struct.error as exc:
            print("s-error", type(exc).__name__, exc)
        try:
            struct.pack("4p", v)
        except struct.error as exc:
            print("p-error", type(exc).__name__, exc)
    try:
        struct.pack("B", 2.5)
    except struct.error as exc:
        print("int-error", type(exc).__name__, exc)
    try:
        struct.pack("B", "3")
    except struct.error as exc:
        print("int-error", type(exc).__name__, exc)
    try:
        struct.pack("@P", None)
    except struct.error as exc:
        print("P-error", type(exc).__name__, exc)


main()
"""

PROGRAMS['alias'] = r"""import struct as st
from struct import calcsize, error, pack as pk


def main() -> None:
    print(st.pack(">H", 258).hex(), pk("<I", 1).hex(), calcsize(">3h"))
    try:
        st.unpack(">I", b"x")
    except error as exc:
        print(exc)


main()
"""

PACK_ONLY = r"""import struct


def main() -> None:
    print(struct.calcsize(">I"), struct.calcsize("@bq"))
    print(struct.pack(">I", 305419896).hex())
    print(struct.pack("<hH", -2, 65535).hex())
    print(struct.pack("4s", b"ab").hex(), struct.pack("c", b"Z").hex(), struct.pack("?", 0).hex())
    print(struct.pack(">f", 1.5).hex(), struct.pack(">e", 1.5).hex(), struct.pack(">d", 1.25).hex())
    print(struct.pack("@bq", 1, 2).hex(), struct.pack(">2?2h", 1, 0, -1, 2).hex())
    try:
        struct.pack("B", 300)
    except struct.error as exc:
        print(exc)


main()
"""


def struct_inputs():
    return ["7 -9\n", "0 9223372036854775807\n", "-2147483648 -9223372036854775808\n"]


CASES = [
    ("pack_unpack", PROGRAMS["s1"], struct_inputs),
    ("aliases", PROGRAMS["alias"], lambda: ["\n"]),
]


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, inputs, ir, **env):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(env, AIL_IR="1" if ir else "0")
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s" % (name, env["AIL_IR"], built.stdout, built.stderr))
            Path(directory, "oracle.py").write_text(text, encoding="utf-8")
            for k, stdin in enumerate(inputs):
                want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))], input=stdin.encode(),
                                      capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, "%s input %d: %s" % (name, k, got.stderr[-300:]))
                if got.stdout != want.stdout:
                    a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                    for n, (x, y) in enumerate(zip(a, b)):
                        if x != y:
                            self.fail("%s input %d (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r" % (name, k, env["AIL_IR"], n + 1, x, y))
                    self.fail("%s input %d: %d lines against %d" % (name, k, len(a), len(b)))

    def test_programs_match_cpython(self):
        for name, text, inputs in CASES:
            for ir in (False, True):
                with self.subTest(program=name, ir=ir):
                    self.check(name, text, inputs(), ir)

    def test_typed_path_builds_pack(self):
        for ir in (False, True):
            with self.subTest(path="typed", ir=ir):
                self.check("pack_only", PACK_ONLY, ["\n"], ir, AIL_NO_GENERAL="1")
            with self.subTest(path="default", ir=ir):
                self.check("pack_only", PACK_ONLY, ["\n"], ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused", AIL_NO_GENERAL="1")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            "pack_into": ("import struct\n\nd = bytearray(8)\nstruct.pack_into('>I', d, 0, 1)\n", "struct.pack_into"),
            "unpack_from": ("import struct\n\nprint(struct.unpack_from('>I', b'1234'))\n", "struct.unpack_from"),
            "struct_class": ("import struct\n\ns = struct.Struct('>I')\nprint(s.size)\n", "struct.Struct"),
            "iter_unpack": ("import struct\n\nfor part in struct.iter_unpack('>I', b'1234'):\n    print(part)\n", "struct.iter_unpack"),
            "nonliteral": ("import struct\n\nfmt = '>I'\nprint(struct.pack(fmt, 1))\n", "literal string"),
            "bad_char": ("import struct\n\nprint(struct.calcsize('>z'))\n", "format character"),
            "repeat": ("import struct\n\nprint(struct.calcsize('10'))\n", "repeat count"),
            "count": ("import struct\n\nprint(struct.pack('>I', 1, 2))\n", "needs 1 value"),
            "native_only": ("import struct\n\nprint(struct.calcsize('<n'))\n", "native mode"),
            "nested": ("def f() -> None:\n    import struct\n    print(struct.calcsize('>I'))\nf()\n", "top of the file"),
            "star": ("from struct import *\n\nprint(calcsize('>I'))\n", "from struct import *"),
            "zero_p": ("import struct\n\nprint(struct.unpack('0p', b''))\n", "zero-count 'p'"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


class UnchangedPrograms(unittest.TestCase):
    PLAIN = [
        "import sys\n\nfor i, line in enumerate(sys.stdin):\n    print(i, line.strip())\n",
        "class P:\n    def __init__(self, x: int) -> None:\n        self.x = x\n\nprint(P(3).x)\n",
        "# mentions struct only in a comment\nprint(1)\n",
    ]

    def test_other_programs_keep_their_text(self):
        import structlib
        for text in self.PLAIN:
            with self.subTest(text[:30]):
                notes = []
                self.assertIs(structlib.rewrite_text(text, notes), text)
                self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
