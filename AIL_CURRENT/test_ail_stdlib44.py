"""Library batch 44: struct's integer, bool, char, string and padding formats, compared with CPython 3.12.

Every program below is ordinary Python. CPython runs it as the oracle, and the compiled program (with AIL_IR=0 and
AIL_IR=1) prints the same bytes and exits with the same status. A float format, a non-literal format, Struct /
iter_unpack, a keyword argument and a starred argument are refused by name at compile time.
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


PACK_PROGRAM = r"""import struct
import sys


def main() -> None:
    for token in sys.stdin.read().split():
        value = int(token)
        b = struct.pack("<q", value)
        print(b, struct.unpack("<q", b)[0])
        u = value % 4294967296
        print(struct.pack(">I", u), struct.unpack(">I", struct.pack(">I", u))[0])
        print(struct.pack("<H", u % 65536), struct.unpack("<H", struct.pack("<H", u % 65536))[0])


main()
"""

FIXED_PROGRAM = r"""from struct import pack as p, unpack as u, calcsize as cs, pack_into, unpack_from, error
import struct as s


def main() -> None:
    print(cs("<q"), cs("@bi"), cs("3x"), cs("0s"), cs("P"))
    text = p("<16sHHIQQQIHHHHHH", b"abc", 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)
    print(text)
    print(u("<16sHHIQQQIHHHHHH", text))
    print(p(">3s", b"abcdef"), p("3p", b"ab"), u("3p", p("3p", b"ab")))
    print(p("3c", b"a", b"b", b"c"), u("3c", b"abc"))
    print(p("?", 2), p("?", []), u("??", b"\x01\x00"))
    print(p("@bi", 1, 2), u("@bi", p("@bi", 1, 2)))
    print(p("=l", 5), s.pack("<Q", 123), s.unpack("<Q", s.pack("<Q", 123)))
    buf = bytearray(16)
    pack_into(">I", buf, 3, 0x12345678)
    print(buf, unpack_from(">I", buf, 3))
    print(s.pack("<b", -128), s.unpack("<b", s.pack("<b", -128)))
    print(s.pack("<l", -2147483648), s.unpack("<l", s.pack("<l", -2147483648)))
    print(s.pack("<2xI", 5), s.pack("<I2x", 5), s.pack("<0s", b"abc"))
    try:
        u("<q", b"")
    except error as exc:
        print("err", type(exc).__name__, str(exc))
    try:
        p("B", 256)
    except error as exc:
        print("err", type(exc).__name__, str(exc))
    try:
        unpack_from(">I", b"1234", -1)
    except error as exc:
        print("err", type(exc).__name__, str(exc))
    try:
        pack_into(">I", bytearray(4), -1, 1)
    except error as exc:
        print("err", type(exc).__name__, str(exc))


main()
"""


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, inputs, ir):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(AIL_IR="1" if ir else "0")
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s"
                             % (name, env["AIL_IR"], built.stdout, built.stderr))
            Path(directory, "oracle.py").write_text(text, encoding="utf-8")
            for k, stdin in enumerate(inputs):
                want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))],
                                      input=stdin.encode(), capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode,
                                 "%s input %d (AIL_IR=%s): %s" % (name, k, env["AIL_IR"], got.stderr[-300:]))
                if got.stdout != want.stdout:
                    a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                    for n, (x, y) in enumerate(zip(a, b)):
                        if x != y:
                            self.fail("%s input %d (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                                      % (name, k, env["AIL_IR"], n + 1, x, y))
                    self.fail("%s input %d: %d lines against %d"
                              % (name, k, len(a), len(b)))

    def test_dynamic_values_match_cpython(self):
        data = ["0 1 255 256 -1 -128 -32768 4294967295 123456789 -9223372036854775807\n"]
        for ir in (False, True):
            with self.subTest(ir=ir):
                self.check("dynamic", PACK_PROGRAM, data, ir)

    def test_fixed_formats_match_cpython(self):
        for ir in (False, True):
            with self.subTest(ir=ir):
                self.check("fixed", FIXED_PROGRAM, [""], ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            "float": ("import struct\n\nprint(struct.pack('<d', 1.5))\n", "'d' float format is not built"),
            "non_literal": ("import struct\n\nf = '<q'\nprint(struct.pack(f, 1))\n", "format must be a literal string"),
            "struct_class": ("from struct import Struct\n\nprint(Struct)\n", "struct.Struct is not built"),
            "keyword": ("import struct\n\nprint(struct.pack(format='<q', v=1))\n", "keyword arguments are not built"),
            "starred": ("import struct\n\nv = [1]\nprint(struct.pack('<q', *v))\n", "starred arguments are not built"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


class UnchangedPrograms(unittest.TestCase):
    def test_other_programs_keep_their_text(self):
        import structlib
        for text in ("import sys\n\nprint(sys.argv)\n",
                     "import json\n\nprint(json.dumps({'a': 1}))\n",
                     "# mentions struct only in a comment\nprint(1)\n"):
            with self.subTest(text[:30]):
                notes = []
                self.assertIs(structlib.rewrite_text(text, notes), text)
                self.assertEqual(notes, [])



if __name__ == "__main__":
    unittest.main()
