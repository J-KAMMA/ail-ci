"""Library batch 24: `struct` with a literal format string, over int.to_bytes / int.from_bytes.

The compiler reads the format at compile time (python/pkg-v12/structlib.py) and lowers each `struct.pack`,
`struct.unpack`, `struct.unpack_from`, `struct.pack_into` and `struct.calcsize` call onto the small helpers in
python/pkg-v12/prelude_struct.py.  The fields built are the integer codes (b B h H i I l L q Q n N P), bool (?),
char (c), pad (x), fixed string (s) and pascal string (p), in the native (@), standard (= < > !) and aligned
(native) layouts.  Float codes (e f d) are refused by name, as is a format that is not a literal.

The program tests below are compiled on the default build and with AIL_UNIFIED_FORCE=1 (the general path), run on
generated stdin where they read any, and compared byte for byte with CPython 3.12 (stdout, exit status).  A format
layout test compares structlib's reader and the prelude helpers directly with the `struct` module over generated
formats, and the refusal cases must name the use that is not built.

Known limits, shared with the rest of the subset: int is signed 64-bit, so a Q/N/P value or result above
2**63-1 is not representable (an out-of-int64 literal is refused by name); `struct.error` in an `except` clause is
spelt `ValueError` (as csv.Error is), and its other uses are refused by name; unpacking a '0p' field is refused
because CPython 3.12 raises SystemError for an empty buffer (`pack('0p', ...)` is built and returns b'').
Negative `unpack_from`/`pack_into` offsets count from the end of the buffer, and `s`/`p`/`c` results of a
`bytearray` buffer are bytes copies, as in CPython.
"""
import os
import random
import struct as _cpython
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

CORE = r"""import struct

print(struct.calcsize("i"), struct.calcsize("=i"), struct.calcsize("@bh"), struct.calcsize("<hL"), struct.calcsize("!q"))
print(struct.calcsize("@bhiq"), struct.calcsize("@bhlq"), struct.calcsize("=bhiq"))
print(struct.calcsize("f"), struct.calcsize("d"), struct.calcsize("e"), struct.calcsize("@bd"), struct.calcsize("0p"))
print(struct.pack("i", 12345).hex())
print(struct.pack(">i", -2).hex(), struct.pack("<I", 4294967295).hex())
v0 = struct.pack("b", 1)
print("b", struct.calcsize("b"), v0.hex(), struct.unpack("b", v0)[0])
v1 = struct.pack("B", 1)
print("B", struct.calcsize("B"), v1.hex(), struct.unpack("B", v1)[0])
v2 = struct.pack("h", 1)
print("h", struct.calcsize("h"), v2.hex(), struct.unpack("h", v2)[0])
v3 = struct.pack("H", 1)
print("H", struct.calcsize("H"), v3.hex(), struct.unpack("H", v3)[0])
v4 = struct.pack("i", 1)
print("i", struct.calcsize("i"), v4.hex(), struct.unpack("i", v4)[0])
v5 = struct.pack("I", 1)
print("I", struct.calcsize("I"), v5.hex(), struct.unpack("I", v5)[0])
v6 = struct.pack("l", 1)
print("l", struct.calcsize("l"), v6.hex(), struct.unpack("l", v6)[0])
v7 = struct.pack("L", 1)
print("L", struct.calcsize("L"), v7.hex(), struct.unpack("L", v7)[0])
v8 = struct.pack("q", 1)
print("q", struct.calcsize("q"), v8.hex(), struct.unpack("q", v8)[0])
v9 = struct.pack("Q", 1)
print("Q", struct.calcsize("Q"), v9.hex(), struct.unpack("Q", v9)[0])
v10 = struct.pack("n", 1)
print("n", struct.calcsize("n"), v10.hex(), struct.unpack("n", v10)[0])
v11 = struct.pack("N", 1)
print("N", struct.calcsize("N"), v11.hex(), struct.unpack("N", v11)[0])
lo0 = -(1 << (8 * struct.calcsize("b") - 1))
hi0 = (1 << (8 * struct.calcsize("b") - 1)) - 1
pl0 = struct.pack("b", lo0)
ph0 = struct.pack("b", hi0)
print("b-range", pl0.hex(), ph0.hex(), struct.unpack("b", pl0)[0], struct.unpack("b", ph0)[0])
lo1 = -(1 << (8 * struct.calcsize("h") - 1))
hi1 = (1 << (8 * struct.calcsize("h") - 1)) - 1
pl1 = struct.pack("h", lo1)
ph1 = struct.pack("h", hi1)
print("h-range", pl1.hex(), ph1.hex(), struct.unpack("h", pl1)[0], struct.unpack("h", ph1)[0])
lo2 = -(1 << (8 * struct.calcsize("i") - 1))
hi2 = (1 << (8 * struct.calcsize("i") - 1)) - 1
pl2 = struct.pack("i", lo2)
ph2 = struct.pack("i", hi2)
print("i-range", pl2.hex(), ph2.hex(), struct.unpack("i", pl2)[0], struct.unpack("i", ph2)[0])
lo3 = -(1 << (8 * struct.calcsize("l") - 1))
hi3 = (1 << (8 * struct.calcsize("l") - 1)) - 1
pl3 = struct.pack("l", lo3)
ph3 = struct.pack("l", hi3)
print("l-range", pl3.hex(), ph3.hex(), struct.unpack("l", pl3)[0], struct.unpack("l", ph3)[0])
lo4 = -(1 << (8 * struct.calcsize("q") - 1))
hi4 = (1 << (8 * struct.calcsize("q") - 1)) - 1
pl4 = struct.pack("q", lo4)
ph4 = struct.pack("q", hi4)
print("q-range", pl4.hex(), ph4.hex(), struct.unpack("q", pl4)[0], struct.unpack("q", ph4)[0])
lo5 = -(1 << (8 * struct.calcsize("n") - 1))
hi5 = (1 << (8 * struct.calcsize("n") - 1)) - 1
pl5 = struct.pack("n", lo5)
ph5 = struct.pack("n", hi5)
print("n-range", pl5.hex(), ph5.hex(), struct.unpack("n", pl5)[0], struct.unpack("n", ph5)[0])
uh0 = (1 << (8 * struct.calcsize("B"))) - 1
pu0 = struct.pack("B", uh0)
print("B-max", pu0.hex(), struct.unpack("B", pu0)[0])
uh1 = (1 << (8 * struct.calcsize("H"))) - 1
pu1 = struct.pack("H", uh1)
print("H-max", pu1.hex(), struct.unpack("H", pu1)[0])
uh2 = (1 << (8 * struct.calcsize("I"))) - 1
pu2 = struct.pack("I", uh2)
print("I-max", pu2.hex(), struct.unpack("I", pu2)[0])
uh3 = (1 << (8 * struct.calcsize("L"))) - 1
pu3 = struct.pack("L", uh3)
print("L-max", pu3.hex(), struct.unpack("L", pu3)[0])
print(struct.pack("?c4s", True, b"Z", b"ab").hex())
packed2 = struct.pack("?c4s", False, b"Q", b"abcdef")
print(struct.unpack("?c4s", packed2))
packed3 = struct.pack("5p", b"abcdefg")
print(packed3.hex(), struct.unpack("5p", packed3))
packed3b = struct.pack("5p", b"ab")
print(packed3b.hex(), struct.unpack("5p", packed3b))
packed4 = struct.pack("2h", 1, 2)
print(packed4.hex(), struct.unpack("2h", packed4))
print(struct.pack("hx h", 1, 2).hex(), struct.pack("3x").hex(), struct.pack("0s", b"abc").hex())
print(struct.calcsize("0s"), struct.calcsize("3x"), struct.calcsize(" "), struct.calcsize(""))
print(struct.pack("").hex(), struct.pack(" ").hex())
packed5 = struct.pack("<2i", 1, -1)
print(packed5.hex(), struct.unpack("<2i", packed5))
packed6 = struct.pack("@2i", 1, -1)
print(packed6.hex(), struct.unpack("@2i", packed6))
print(struct.pack("@bi", 1, 2).hex(), struct.pack("@hi", 1, 2).hex())
print(struct.pack("@bq", 1, 2).hex(), struct.pack("@biq", 1, 2, 3).hex())
buf = bytearray(12)
struct.pack_into(">i", buf, 4, 7)
print(bytes(buf).hex())
print(struct.unpack_from(">i", buf, 4))
print(struct.unpack_from(">i", buf, 0))
print(struct.unpack_from(">hh", buf, 2))
print(struct.unpack_from(">h", buf, 10))
inner = struct.pack("@bi", 1, 2)
print(struct.unpack_from("@bi", inner, 0))
"""

ROUTES = r"""import struct


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


class Buf:
    def __init__(self, data: bytearray) -> None:
        self.data = data


def via_arg(value: int) -> bytes:
    return struct.pack(">h", value)


def unpack_at(data: bytes, base: int) -> int:
    return struct.unpack_from(">h", data, base)[0]


def pack_at(target: bytearray, base: int, value: int) -> None:
    struct.pack_into(">h", target, base, value)


def main() -> None:
    values = [1, 2, 3, 4]
    d = {"v": 1, "b": struct.pack(">3h", 4, 5, 6), "buf": bytearray(6)}
    box = Box(2)
    target = Buf(bytearray(6))
    print(via_arg(7).hex())
    print(struct.pack(">h", values[0]).hex())
    print(struct.pack(">h", box.value).hex())
    print(struct.pack(">h", d["v"]).hex())
    buf = struct.pack(">3h", 10, 20, 30)
    two = struct.pack(">h", 5)
    print(struct.unpack(">h", two)[0])
    print(struct.unpack_from(">h", buf, 2)[0])
    print(struct.unpack_from(">h", d["b"], 1)[0])
    print(struct.unpack_from(">h", buf, values[1])[0])
    print(struct.unpack_from(">h", buf, box.value)[0])
    print(struct.unpack_from(">h", buf, d["v"])[0])
    print(unpack_at(d["b"], 0), unpack_at(buf, 4))
    pack_at(target.data, 2, 55)
    print(bytes(target.data).hex())
    pack_at(d["buf"], 4, 33)
    print(bytes(d["buf"]).hex())
    b2 = bytearray(8)
    struct.pack_into(">h", b2, values[1], 99)
    print(bytes(b2).hex())
    struct.pack_into(">h", b2, box.value, 88)
    print(bytes(b2).hex())
    struct.pack_into(">h", b2, d["v"], 77)
    print(bytes(b2).hex())
    print(struct.pack_into(">h", b2, 0, 11))
    print(bytes(b2).hex())


main()
"""

ERRORS = r"""import struct


def main() -> None:
    try:
        print(struct.pack("i", 2147483648))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("i", -2147483649))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("b", 128))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("B", -1))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("B", 256))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("H", 65536))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("c", b"ab"))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("c", b""))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.unpack("i", b"abc"))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.unpack("2h", b"abc"))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.unpack_from("i", b"abcd", 4))
    except struct.error as e:
        print("struct.error", e)
    neg = -1
    try:
        print(struct.unpack_from("i", b"abcd", neg))
    except struct.error as e:
        print("struct.error", e)
    buf = bytearray(4)
    try:
        print(struct.pack_into("i", buf, 2, 1))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack_into("i", buf, -1, 1))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("Q", -1))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("N", -1))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("P", -1).hex())
    except struct.error as e:
        print("struct.error", e)
    try:
        struct.pack("B", 999)
    except (struct.error, ValueError) as e:
        print("tuple", e)
    try:
        print(struct.pack("c", 65))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("s", 5))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("p", 5))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("0s", 5))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("0p", 5))
    except struct.error as e:
        print("struct.error", e)
    try:
        print(struct.pack("c", bytearray(b"Z")))
    except struct.error as e:
        print("struct.error", e)


main()
"""

ALIASES = r"""import struct as st
from struct import pack as p
from struct import unpack
from struct import error as err

print(p(">h", 2).hex(), st.calcsize("h"))
data = st.pack("<i", 300)
print(unpack("<i", data), st.unpack("<i", data))
try:
    p("b", 500)
except err as e:
    print("struct.error", e)
try:
    unpack("i", b"x")
except err as e:
    print("struct.error", e)
print(st.pack("?c", 3, b"c").hex())
"""

NEGATIVES = r"""import struct

buf = b"abcdefgh"
for off in [-8, -7, -5, -4, -2, -1]:
    try:
        print(off, struct.unpack_from(">h", buf, off))
    except struct.error as e:
        print(off, "err", e)
for off in [-12, -9]:
    try:
        print(off, struct.unpack_from(">i", buf, off))
    except struct.error as e:
        print(off, "err", e)
b = bytearray(8)
struct.pack_into(">i", b, -4, 0x01020304)
print(bytes(b).hex())
b = bytearray(8)
struct.pack_into(">h", b, -2, 0x0506)
print(bytes(b).hex())
for off in [-9, -2, -1, 5, 8]:
    b = bytearray(8)
    try:
        struct.pack_into(">i", b, off, 7)
        print(off, bytes(b).hex())
    except struct.error as e:
        print(off, "err", e)
b = bytearray(8)
print(struct.pack_into(">i", b, 0, 1))
print(struct.pack_into("0i", b, 8))
try:
    print(struct.pack_into("0i", b, 9))
except struct.error as e:
    print("err", e)
try:
    print(struct.pack_into(">i", b, -9, 1))
except struct.error as e:
    print("err", e)
"""

TYPES = r"""import struct

b = bytearray(b"abcd")
print(struct.unpack("4s", b))
pb = bytearray(b"\x02ab\x00")
cb = bytearray(b"Z")
print(struct.unpack("4p", pb))
print(struct.unpack("c", cb))
buf = bytearray(struct.pack(">3h", 1, 2, 3))
print(struct.unpack_from("2s", buf, 1))
t = struct.unpack("4s", b)
b[0] = 122
print(t)
u = struct.unpack_from("2s", b, 1)
b[2] = 113
print(u)
print(struct.pack("0p", b"x").hex(), struct.pack("0p", b"").hex())
print(struct.pack("0s", b"x").hex())
print(struct.pack("s", bytearray(b"ab")).hex(), struct.pack("p", bytearray(b"ab")).hex())
try:
    print(struct.unpack("4s", "abcd"))
except TypeError as e:
    print("TypeError", e)
try:
    print(struct.pack_into(">h", b"abcd", 0, 7))
except TypeError as e:
    print("TypeError", e)
"""

PROGRAMS = (("core", CORE), ("routes", ROUTES), ("errors", ERRORS), ("aliases", ALIASES),
            ("negatives", NEGATIVES), ("types", TYPES))
BUILDS = (("default", {}), ("general", {"AIL_UNIFIED_FORCE": "1"}))

REFUSALS = {
    "nonliteral": ("import struct\n\nfmt = 'i'\nprint(struct.pack(fmt, 1))\n",
                   "struct.pack needs a literal format string"),
    "float": ("import struct\n\nprint(struct.pack('f', 1.5))\n",
              "struct.pack: float format 'f' is not built"),
    "value": ("import struct\n\nf = struct.pack\nprint(f('i', 1))\n",
              "struct.pack is not built"),
    "zero_p": ("import struct\n\nprint(struct.unpack('0p', b''))\n",
               "unpack of a '0p' pascal-string field is not built"),
    "wildcard": ("from struct import *\n\nprint(pack('i', 1))\n",
                 "from struct import *: name what you use"),
    "error_value": ("import struct\n\ne = struct.error\nprint(e)\n",
                    "struct.error is built only as the type of an except clause"),
    "empty_unpack": ("import struct\n\nprint(struct.unpack('', b''))\n",
                     "struct.unpack of a format with no values is not built"),
}


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    base = dict(os.environ)
    base.pop("AIL_UNIFIED_FORCE", None)
    base.update(env)
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=base)
    return built, source, exe


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text):
        for tag, env in BUILDS:
            with self.subTest(program=name, build=tag):
                with tempfile.TemporaryDirectory() as directory:
                    built, source, exe = compile_python(directory, text, "p_" + name, **env)
                    self.assertEqual(built.returncode, 0, "%s (%s)\n%s%s" % (name, tag, built.stdout,
                                                                             built.stderr))
                    Path(directory, "oracle.py").write_text(text, encoding="utf-8")
                    want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))],
                                          capture_output=True, timeout=300)
                    got = subprocess.run([str(exe)], capture_output=True, timeout=300)
                    self.assertEqual(got.returncode, want.returncode, "%s (%s): %s" % (
                        name, tag, got.stderr[-400:]))
                    if got.stdout != want.stdout:
                        a = got.stdout.decode().splitlines()
                        b = want.stdout.decode().splitlines()
                        for n, (x, y) in enumerate(zip(a, b)):
                            if x != y:
                                self.fail("%s (%s) line %d:\n  compiled: %r\n  CPython:  %r" % (
                                    name, tag, n + 1, x, y))
                        self.fail("%s (%s): %d lines against %d" % (name, tag, len(a), len(b)))

    def test_programs_match_cpython(self):
        for name, text in PROGRAMS:
            self.check(name, text)


class Refusals(unittest.TestCase):
    def test_refusals_name_the_use(self):
        for name, (text, wanted) in REFUSALS.items():
            for tag, env in BUILDS:
                with self.subTest(name=name, build=tag):
                    with tempfile.TemporaryDirectory() as directory:
                        built, _, exe = compile_python(directory, text, "refused_" + name, **env)
                        self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
                        self.assertIn(wanted, built.stdout + built.stderr)
                        self.assertFalse(exe.exists())


class FormatLayout(unittest.TestCase):
    """structlib's format reader and the prelude helpers against CPython's struct over generated formats."""

    def test_sizes_and_pack_unpack_match_cpython(self):
        import prelude_struct as P
        import structlib as S
        orders = "@=<>!"
        codes = "xcbB?hHiIlLqQnNspP"
        checked = 0
        for order in orders:
            for code in codes:
                if code in "nNP" and order != "@":
                    continue
                for count in ("", "0", "1", "2", "3"):
                    fmt = order + count + code
                    fields, size = S._format(fmt)
                    self.assertEqual(size, _cpython.calcsize(fmt), fmt)
                    if any(f.code in "efd" for f in fields) or any(
                            f.code == "p" and f.total == 0 for f in fields):
                        continue
                    values = []
                    for field in fields:
                        if field.code == "x":
                            continue
                        if field.code == "s":
                            values.append(b"abcd")
                        elif field.code == "p":
                            values.append(b"abcdef")
                        elif field.code == "?":
                            for k in range(field.count):
                                values.append(1)
                        elif field.code == "c":
                            for k in range(field.count):
                                values.append(b"Z")
                        else:
                            low, high = S._bounds(field.unit, field.signed)
                            for k in range(field.count):
                                if low == 0 and high == 0:
                                    values.append(-1 if field.code == "P" else 1)
                                else:
                                    values.append(low if k % 2 == 0 else high)
                    want = _cpython.pack(fmt, *values)
                    got = []
                    at = 0
                    index = 0
                    for field in fields:
                        if field.offset > at:
                            got.append(b"\x00" * (field.offset - at))
                        at = field.offset
                        if field.code == "x":
                            got.append(b"\x00" * field.total)
                            at += field.total
                            continue
                        if field.code in "sp":
                            value = values[index]
                            index += 1
                            got.append(P._ail_struct_pack_s(value, field.total) if field.code == "s"
                                       else P._ail_struct_pack_p(value, field.total))
                            at += field.total
                            continue
                        for k in range(field.count):
                            value = values[index]
                            index += 1
                            if field.code == "?":
                                got.append(P._ail_struct_pack_bool(value))
                            elif field.code == "c":
                                got.append(P._ail_struct_pack_char(value))
                            else:
                                low, high = S._bounds(field.unit, field.signed)
                                got.append(P._ail_struct_pack_int(value, field.unit, field.signed,
                                                                  field.byteorder, low, high, field.code))
                            at += field.unit
                    self.assertEqual(b"".join(got), want, fmt)
                    back = []
                    for field in fields:
                        if field.code == "x":
                            continue
                        if field.code == "s":
                            back.append(P._ail_struct_unpack_s(want, field.offset, field.total, 0, size, True))
                        elif field.code == "p":
                            back.append(P._ail_struct_unpack_p(want, field.offset, field.total, 0, size, True))
                        else:
                            for k in range(field.count):
                                offset = field.offset + k * field.unit
                                if field.code == "?":
                                    back.append(P._ail_struct_unpack_bool(want, offset, 0, size, True))
                                elif field.code == "c":
                                    back.append(P._ail_struct_unpack_char(want, offset, 0, size, True))
                                else:
                                    back.append(P._ail_struct_unpack_int(want, offset, field.unit,
                                                                         field.signed, field.byteorder,
                                                                         0, size, True))
                    self.assertEqual(tuple(back), _cpython.unpack(fmt, want), fmt)
                    checked += 1
        self.assertGreater(checked, 300)


class UnchangedPrograms(unittest.TestCase):
    def test_programs_without_a_struct_import_keep_their_text(self):
        import structlib
        for text in ("# struct only in a comment\nprint(1)\n",
                     "structure = 3\nprint(structure)\n",
                     "import math\n\nprint(math.floor(2.5))\n"):
            with self.subTest(text[:30]):
                notes = []
                self.assertIs(structlib.rewrite_text(text, notes), text)
                self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
