"""Library batch 6: `struct.pack` / `struct.unpack` / `struct.calcsize`, compared with CPython 3.12.

Every program below is ordinary Python. CPython runs it as the oracle; the compiled program prints the same bytes
and exits with the same status on BOTH compile paths:

  * the default build (`ail_chatgpt.py compile`, the typed path with its general fallback);
  * the general path (`AIL_UNIFIED_FORCE=1`).

The pass is structlib.py, run from ail_syntax.python_surface on the program text: the literal format is parsed at
compile time and each field becomes int.to_bytes / int.from_bytes over the bytes the compiler already builds.
Supported: a literal format with a '>' '<' '=' or '!' prefix and the codes b B h H i I l L q (and Q in pack;
unpack of Q can leave the signed 64-bit int and is refused) ? c s x (repeat counts included). CPython's
out-of-range, short-buffer and argument-type messages are reproduced through RuntimeError, a bytearray buffer or
's' argument is copied to bytes, and the programs read the messages with `except Exception`, so the text matches.

Anything else stays a named compile-time refusal, and these tests check the note for each: a dynamic format, the
native-aligned '@' mode (a format with no prefix), the float codes e f d, the native-size codes n N P, 'p', a bad
character, a starred or keyword call, a wrong value count, `Struct` / `pack_into` / `error`, a from-import of an
unbuilt name, and a call or comprehension as an unpack buffer.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")


def build(directory, text, name, general=False):
    source = Path(directory, name + ".py")
    source.write_text(text, encoding="utf-8")
    env = dict(os.environ)
    env.pop("AIL_NO_GENERAL", None)
    env["AIL_NO_CACHE"] = "1"
    env["AIL_QUIET_FALLBACK"] = "1"
    if general:
        env["AIL_UNIFIED_FORCE"] = "1"
    else:
        env.pop("AIL_UNIFIED_FORCE", None)
    built = subprocess.run([sys.executable, "-B", CLI, "compile", source.name, "--syntax", "python", "-o", name],
                           cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return built, Path(directory, name)


def cpython(directory, text, name):
    source = Path(directory, name + ".py")
    source.write_text(text, encoding="utf-8")
    return subprocess.run([sys.executable, "-B", str(source)], capture_output=True, timeout=300)


BASIC = r'''
import struct


def main() -> None:
    p = struct.pack(">b", -128)
    q = struct.pack(">B", 255)
    print(">b", list(p), list(struct.pack(">b", 127)), struct.unpack(">b", p))
    print(">B", list(struct.pack(">B", 0)), list(q), struct.unpack(">B", q))
    print(">h", list(struct.pack(">h", -32768)), list(struct.pack(">H", 65535)))
    print("<h", list(struct.pack("<h", -2)), list(struct.pack("<H", 65535)))
    print(">i", list(struct.pack(">i", -2147483648)), list(struct.pack(">I", 4294967295)))
    print("<i", list(struct.pack("<i", -1)), list(struct.pack("<I", 305419896)))
    print(">l", list(struct.pack(">l", -2147483648)), list(struct.pack("<L", 4294967295)))
    print(">q", list(struct.pack(">q", -9223372036854775808)), list(struct.pack(">Q", 9223372036854775807)))
    print("<q", list(struct.pack("<q", -1)))
    print(struct.calcsize(">I"), struct.calcsize("<3H"), struct.calcsize(">"), struct.calcsize(">0I"))
    print("many", list(struct.pack(">3I", 1, 2, 3)))
    print("mixed", list(struct.pack("<bHiQ", -1, 258, -3, 4)))
    print("empty", list(struct.pack(">")))
    packed = struct.pack("<bHiQ", -1, 258, -3, 4)
    print(struct.unpack("<bHiq", packed))
    data = b"\x01\x02\x03\x04\x05"
    print(struct.unpack(">I", data[0:4]))
    print("eq", list(struct.pack("=I", 305419896)))
    print("bang", list(struct.pack("!I", 305419896)))
    print("bool", list(struct.pack(">I", True)), list(struct.pack(">i", False)))
    mixed = struct.pack(">I4s2c?", 305419896, b"xy", b"a", b"b", True)
    print("mixed-tuple", struct.unpack(">I4s2c?", mixed))


main()
'''

BYTES = r'''
import struct


def main() -> None:
    print(list(struct.pack(">s", b"x")))
    print(list(struct.pack(">4s", b"ab")))
    print(list(struct.pack(">4s", b"abcdef")))
    print(list(struct.pack(">0s", b"abc")))
    print(list(struct.pack(">3x")))
    print(list(struct.pack(">xI", 7)))
    print(list(struct.pack(">2c", b"a", b"b")))
    print(struct.unpack(">4s", b"ab\x00\x00"), struct.unpack(">0s", b""))
    print(struct.unpack(">2c", b"ab"))
    print(struct.unpack(">xI", b"\x00\x00\x00\x00\x07"))
    a = struct.pack(">?", True)
    b = struct.pack(">?", False)
    c = struct.pack(">?", 3)
    d = struct.pack(">?", 0)
    print(list(a), list(b), list(c), list(d))
    print(struct.unpack(">?", a), struct.unpack(">?", b))
    print(struct.unpack(">???", b"\x00\x01\x02"))
    print(struct.calcsize(">4s2c3x?"))
    ba = bytearray(b"ab\x00\x00")
    got = struct.unpack(">4s", ba)
    print(type(got[0]).__name__, got)
    cb = bytearray(b"a")
    print(type(struct.unpack(">c", cb)[0]).__name__)
    live = bytearray(b"abcd")
    copy = struct.unpack(">4s", live)
    live[0] = 65
    print(copy, bytes(live))
    print(list(struct.pack(">4s", bytearray(b"ab"))))
    print(list(struct.pack(">c", b"a")))


main()
'''

ROUTES = r'''
import struct


class Box:
    data: bytes


def packer(value: int) -> bytes:
    return struct.pack(">I", value)


def unpacker(data: bytes):
    return struct.unpack(">I", data)


def main() -> None:
    value = 305419896
    packed = struct.pack(">I", value)
    print(struct.unpack(">I", packed))
    p2 = packer(value)
    print(struct.unpack(">I", p2))
    xs = [value]
    print(list(struct.pack(">I", xs[0])))
    box = Box()
    box.data = packed
    print(struct.unpack(">I", box.data))
    d = {"k": box.data}
    print(struct.unpack(">I", d["k"]))
    print(unpacker(d["k"]))
    print(list(struct.pack(">I", int("305419896"))))


main()
'''

FROM_IMPORT = r'''
from struct import pack, unpack, calcsize
import struct as st


def main() -> None:
    p = pack(">I", 305419896)
    print(list(p), unpack(">I", p), calcsize(">I"))
    q = st.pack("<hI", -7, 70000)
    print(list(q), st.unpack("<hI", q), st.calcsize("<hI"))


main()
'''

ERRORS = r'''
import struct


def main() -> None:
    try:
        struct.pack(">B", -1)
    except Exception as e:
        print("B-", str(e))
    try:
        struct.pack(">B", 256)
    except Exception as e:
        print("B+", str(e))
    try:
        struct.pack(">b", -129)
    except Exception as e:
        print("b-", str(e))
    try:
        struct.pack(">b", 128)
    except Exception as e:
        print("b+", str(e))
    try:
        struct.pack(">h", 32768)
    except Exception as e:
        print("h+", str(e))
    try:
        struct.pack(">H", 65536)
    except Exception as e:
        print("H+", str(e))
    try:
        struct.pack(">I", -1)
    except Exception as e:
        print("I-", str(e))
    try:
        struct.pack(">I", 4294967296)
    except Exception as e:
        print("I+", str(e))
    try:
        struct.pack(">i", 2147483648)
    except Exception as e:
        print("i+", str(e))
    try:
        struct.unpack(">I", b"\x01")
    except Exception as e:
        print("U1", str(e))
    try:
        struct.unpack(">I", b"\x01\x02\x03")
    except Exception as e:
        print("U3", str(e))
    try:
        struct.unpack(">3H", b"\x00\x00\x00\x00\x00")
    except Exception as e:
        print("U5", str(e))
    try:
        struct.pack(">c", b"ab")
    except Exception as e:
        print("c", str(e))
    try:
        struct.pack(">c", "a")
    except Exception as e:
        print("c-str", str(e))
    try:
        struct.pack(">c", bytearray(b"a"))
    except Exception as e:
        print("c-ba", str(e))
    try:
        struct.pack(">4s", "ab")
    except Exception as e:
        print("s-str", str(e))
    try:
        struct.pack(">4s", 1)
    except Exception as e:
        print("s-int", str(e))
    try:
        struct.pack(">I", "x")
    except Exception as e:
        print("I-str", str(e))
    try:
        struct.pack(">I", 1.5)
    except Exception as e:
        print("I-float", str(e))
    try:
        struct.unpack(">I", "abcd")
    except Exception as e:
        print("U-str", str(e))
    try:
        struct.unpack(">I", 4)
    except Exception as e:
        print("U-int", str(e))


main()
'''

IMPORT_ONLY = r'''
import struct


def main() -> None:
    print("ok")


main()
'''


def boundary_program():
    """A program with one literal call per code, value and byte order (CPython is the oracle)."""
    lines = ["import struct", "", "def main() -> None:"]
    codes = [("b", -128, 127), ("B", 0, 255), ("h", -32768, 32767), ("H", 0, 65535),
             ("i", -2147483648, 2147483647), ("I", 0, 4294967295),
             ("l", -2147483648, 2147483647), ("L", 0, 4294967295),
             ("q", -9223372036854775808, 9223372036854775807), ("Q", 0, 9223372036854775807)]
    for order in (">", "<"):
        for code, lo, hi in codes:
            for value in (lo, hi):
                fmt = order + code
                lines.append("    try:")
                lines.append('        p = struct.pack("%s", %d)' % (fmt, value))
                if code == "Q":
                    lines.append('        print("%s", %d, list(p))' % (fmt, value))
                else:
                    lines.append('        print("%s", %d, list(p), struct.unpack("%s", p))' % (fmt, value, fmt))
                lines.append("    except Exception as e:")
                lines.append('        print("%s", %d, str(e))' % (fmt, value))
    for fmt in (">2I", "<3H", ">xI", ">2c", ">4s", ">2s2x?", ">bBHI", ">0I", ">10x"):
        lines.append('    print(struct.calcsize("%s"))' % fmt)
    lines.extend(["", "", "main()", ""])
    return "\n".join(lines)


PROGRAMS = {
    "basic": BASIC,
    "bytes": BYTES,
    "routes": ROUTES,
    "from_import": FROM_IMPORT,
    "errors": ERRORS,
    "import_only": IMPORT_ONLY,
    "boundaries": boundary_program(),
}


class Same(unittest.TestCase):
    def check(self, name, general):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory() as directory:
            want = cpython(directory, text, "oracle")
            built, exe = build(directory, text, "p_" + name, general)
            self.assertEqual(built.returncode, 0, "%s: %s%s" % (name, built.stdout[-500:], built.stderr[-900:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-400:]))
            self.assertEqual(got.stdout.decode(), want.stdout.decode(), name)

    def test_general_path(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name, True)

    def test_default_build(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name, False)


REFUSALS = {
    "dynamic format": ('import struct\n\nf = ">I"\nprint(struct.pack(f, 1))\n',
                       "the format must be a string or bytes literal"),
    "native alignment": ('import struct\n\nprint(list(struct.pack("I", 1)))\n',
                         "native byte order and alignment"),
    "float format": ('import struct\n\nprint(list(struct.pack(">f", 1.5)))\n', "float format 'f'"),
    "native size": ('import struct\n\nprint(list(struct.pack(">n", 1)))\n', "native-size format 'n'"),
    "pascal string": ('import struct\n\nprint(list(struct.pack(">p", b"a")))\n', "Pascal string"),
    "bad char": ('import struct\n\nprint(list(struct.pack(">Z", 1)))\n', "bad char in struct format"),
    "wrong count": ('import struct\n\nprint(list(struct.pack(">I")))\n', "the format takes 1 value(s)"),
    "starred": ('import struct\n\nxs = [1]\nprint(list(struct.pack(">I", *xs)))\n',
                "starred argument is not built"),
    "keyword": ('import struct\n\nprint(list(struct.pack(">I", value=1)))\n',
                "keyword arguments are not built"),
    "Struct": ('import struct\n\ns = struct.Struct(">I")\nprint(s)\n', "struct.Struct is not built"),
    "pack_into": ('import struct\n\nb = bytearray(4)\nstruct.pack_into(">I", b, 0, 1)\n',
                  "struct.pack_into is not built"),
    "error class": ('import struct\n\ntry:\n    struct.pack(">I", -1)\nexcept struct.error:\n    print("x")\n',
                    "struct.error is not built"),
    "call buffer": ('import struct\n\ndef make() -> bytes:\n    return b"\\x00\\x00\\x00\\x01"\n\n'
                    'print(struct.unpack(">I", make()))\n',
                    "the buffer is read once per field"),
    "from unknown": ('from struct import Struct\n\nprint(Struct)\n',
                     "from 'struct': Struct is not built"),
    "star import": ('from struct import *\n\nprint(pack)\n', "name what you use"),
    "Q unpack": ('import struct\n\np = b"\\x00" * 8\nprint(struct.unpack(">Q", p))\n',
                 "the 'Q' code can yield a value above 2**63-1"),
}


class Refused(unittest.TestCase):
    def refused(self, text, word, general):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", general)
            self.assertNotEqual(built.returncode, 0, text)
            self.assertIn(word, built.stdout + built.stderr)

    def test_general_path(self):
        for name, (text, word) in REFUSALS.items():
            with self.subTest(case=name):
                self.refused(text, word, True)

    def test_default_build(self):
        for name, (text, word) in REFUSALS.items():
            with self.subTest(case=name):
                self.refused(text, word, False)


if __name__ == "__main__":
    unittest.main()
