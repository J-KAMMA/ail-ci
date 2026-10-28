"""Library batch 15: `struct.pack`, `struct.unpack` and `struct.calcsize` for integer layouts, compared with CPython.

`struct` is the next most-imported module still refused by the corpus (`lab/corpus/programs`: 2 programs) and by
`language_examples` (4 files) once the batches 1/3/4/5 modules, heapq/bisect, pathlib and the crypto modules are
built.  The supported spelling is a string-literal format with an explicit byte-order prefix (`<`, `>`, `!` or
`=`) and the integer codes `b B h H i I l L q Q` plus `x` (with repeat counts); the size and the field order are
CPython 3.12's, including `=`, zero counts and an empty format.  `struct.error` is spelt `ValueError` in an
`except` clause (the same mapping csv.Error uses), and the messages are CPython's.

Not built and refused by name: floating-point/string/pointer codes, `@` and native layouts, `unpack_from`,
`pack_into`, `iter_unpack`, a format that is not a string literal, starred or keyword arguments, and using
`struct.pack`/`unpack`/`calcsize` as a value.

Every program below is ordinary Python.  CPython runs it as the oracle; the compiled program is built on the
general path (`AIL_UNIFIED_FORCE=1`), the default path with AIL_IR=0 and with AIL_IR=1, and must print the same
bytes and exit with the same status.
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, **env))
    return built, source, exe


BASIC = r"""import struct


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


def pack_one(value: int) -> bytes:
    return struct.pack(">I", value)


def show(label: str, data: bytes) -> None:
    print(label, list(data), len(data))


def main() -> None:
    print(struct.calcsize(">B"), struct.calcsize(">b"), struct.calcsize(">H"), struct.calcsize(">h"))
    print(struct.calcsize(">I"), struct.calcsize(">i"), struct.calcsize(">L"), struct.calcsize(">l"))
    print(struct.calcsize(">Q"), struct.calcsize(">q"), struct.calcsize(">3x"), struct.calcsize(">"), struct.calcsize("<2H4xQ"))
    show("b", struct.pack(">b", -128))
    show("B", struct.pack(">B", 255))
    show("h", struct.pack(">h", -32768))
    show("H", struct.pack(">H", 65535))
    show("i", struct.pack(">i", -2147483648))
    show("I", struct.pack(">I", 4294967295))
    show("l", struct.pack(">l", -2147483648))
    show("L", struct.pack(">L", 4294967295))
    show("q", struct.pack(">q", -9223372036854775808))
    show("Q", struct.pack(">Q", 18446744073709551615))
    show("le", struct.pack("<IH", 0x01020304, 0x0506))
    show("be", struct.pack(">IH", 0x01020304, 0x0506))
    show("eq", struct.pack("=I", 0x01020304))
    show("bang", struct.pack("!I", 0x01020304))
    show("counts", struct.pack(">2B3xH", 1, 2, 0x0304))
    show("empty", struct.pack(">"))
    show("zero", struct.pack(">0I"))
    show("zero_x", struct.pack(">0x"))
    print(struct.unpack(">2B3xH", struct.pack(">2B3xH", 1, 2, 0x0304)))
    print(struct.unpack("<IH", struct.pack("<IH", 0x01020304, 0x0506)))
    print(struct.unpack(">", b""))
    print(struct.unpack(">0I", b""))
    print(struct.unpack(">q", struct.pack(">q", -5)))
    print(struct.unpack(">2H", bytearray([0, 1, 0, 2])))
    values = [11, 12]
    other = values
    table = {"x": 13}
    box = Box(7)
    show("arg", pack_one(values[0]))
    show("item", struct.pack(">I", values[1]))
    show("alias", struct.pack(">I", other[0]))
    show("attr", struct.pack(">I", box.value))
    show("dict", struct.pack(">I", table["x"]))
    print(struct.unpack(">I", bytes([0, 0, 0, 15])))
    print(struct.calcsize(">I") + struct.calcsize("<Q"))
    try:
        struct.pack(">I")
    except struct.error as e:
        print("caught", e)
    try:
        struct.unpack(">I", (0, 1, 0, 2))
    except TypeError as e:
        print("tuple", e)
    try:
        struct.unpack(">I", [0, 0, 0, 1])
    except TypeError as e:
        print("list", e)
    try:
        struct.unpack(">I", range(4))
    except TypeError as e:
        print("range", e)
    print("end")


main()
"""

FROM_IMPORT = r"""from struct import pack, unpack, calcsize, error


def main() -> None:
    print(calcsize(">I"), list(pack(">I", 7)), unpack(">I", pack(">I", 8)))
    try:
        pack(">I")
    except error as e:
        print("err", e)


main()
"""

ROUNDTRIP = r"""import struct
import sys


def main() -> None:
    lines = sys.stdin.read().split()
    i = 0
    while i + 2 < len(lines):
        fmt = lines[i]
        a = int(lines[i + 1])
        b = int(lines[i + 2])
        try:
            if fmt == "B":
                data = struct.pack(">B", a)
                print(fmt, list(data), struct.unpack(">B", data))
            elif fmt == "h":
                data = struct.pack("<h", a)
                print(fmt, list(data), struct.unpack("<h", data))
            elif fmt == "I":
                data = struct.pack(">I", a)
                print(fmt, list(data), struct.unpack(">I", data))
            elif fmt == "q":
                data = struct.pack("<q", a)
                print(fmt, list(data), struct.unpack("<q", data))
            elif fmt == "mix":
                data = struct.pack("<IhQ", a, b, a * b)
                print(fmt, list(data), struct.unpack("<IhQ", data))
            else:
                print("unknown")
        except struct.error as e:
            print(fmt, "error", e)
        i += 3
    print("end")


main()
"""

ERROR_CASES = [
    ("few", 'struct.pack(">I")'),
    ("many", 'struct.pack(">I", 1, 2)'),
    ("Bhi", 'struct.pack(">B", 256)'),
    ("Bne", 'struct.pack(">B", -1)'),
    ("bhi", 'struct.pack(">b", 128)'),
    ("bne", 'struct.pack(">b", -129)'),
    ("Hhi", 'struct.pack(">H", 65536)'),
    ("hhi", 'struct.pack(">h", 32768)'),
    ("Ihi", 'struct.pack(">I", 4294967296)'),
    ("Ine", 'struct.pack(">I", -1)'),
    ("ihi", 'struct.pack(">i", 2147483648)'),
    ("Lhi", 'struct.pack(">L", 4294967296)'),
    ("Qne", 'struct.pack(">Q", -1)'),
    ("Qhi", 'struct.pack(">Q", 18446744073709551616)'),
    ("qhi", 'struct.pack(">q", 9223372036854775808)'),
    ("qne", 'struct.pack(">q", -9223372036854775809)'),
    ("float", 'struct.pack(">I", 1.5)'),
    ("string", 'struct.pack(">I", "x")'),
    ("short", 'struct.unpack(">I", b"123")'),
    ("long", 'struct.unpack(">I", b"12345")'),
]


def errors_program():
    lines = ["import struct", "", ""]
    for name, expr in ERROR_CASES:
        lines += ["def case_%s() -> None:" % name, "    try:", "        print(%r, %s)" % (name, expr),
                  "    except struct.error as e:", "        print(%r, \"error\", e)" % name, "", ""]
    lines.append("def main() -> None:")
    for name, _ in ERROR_CASES:
        lines.append("    case_%s()" % name)
    lines += ["    print(\"end\")", "", "", "main()", ""]
    return "\n".join(lines)


def roundtrip_input(seed):
    rng = random.Random(seed)
    lines = []
    for _ in range(300):
        fmt = rng.choice(["B", "h", "I", "q", "mix", "bad"])
        if fmt in ("B", "I"):
            a = rng.choice([0, 1, 255, 256, -1, 4294967295, 4294967296, rng.randint(-1000, 1000)])
        elif fmt == "h":
            a = rng.choice([-32768, 32767, -32769, 32768, rng.randint(-40000, 40000)])
        elif fmt == "q":
            a = rng.choice([-9223372036854775808, 9223372036854775807, -9223372036854775809,
                            9223372036854775808, rng.randint(-10 ** 12, 10 ** 12)])
        else:
            a = rng.randint(0, 1000)
        b = rng.randint(-1000, 1000)
        lines.append("%s %d %d" % (fmt, a, b))
    return ("\n".join(lines) + "\n").encode()


class StructTests(unittest.TestCase):
    def check(self, name, text, stdin=b""):
        builds = (("general", {"AIL_UNIFIED_FORCE": "1"}),
                  ("default-ir0", {"AIL_IR": "0"}),
                  ("default-ir1", {"AIL_IR": "1"}))
        for label, env in builds:
            with self.subTest(program=name, build=label):
                with tempfile.TemporaryDirectory() as directory:
                    built, source, exe = compile_python(directory, text, name, **env)
                    self.assertEqual(built.returncode, 0, "%s (%s)\n%s%s" % (name, label, built.stdout, built.stderr))
                    expected = subprocess.run([sys.executable, "-X", "utf8", str(source)], input=stdin,
                                              capture_output=True, timeout=300)
                    ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)
                    self.assertEqual(expected.returncode, 0, expected.stderr[-400:])
                    self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout),
                                     "%s (%s) stderr: %s" % (name, label, ran.stderr[-400:]))

    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused", AIL_NO_GENERAL="1")
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())

    def test_pack_unpack_calcsize_match_cpython(self):
        self.check("struct_basic", BASIC)

    def test_from_import_matches_cpython(self):
        self.check("struct_from_import", FROM_IMPORT)

    def test_generated_roundtrips_match_cpython(self):
        for seed in (15, 16, 17):
            with self.subTest(seed=seed):
                self.check("struct_roundtrip_%d" % seed, ROUNDTRIP, roundtrip_input(seed))

    def test_errors_match_cpython(self):
        self.check("struct_errors", errors_program())

    def test_unbuilt_struct_forms_are_refused_by_name(self):
        self.refused('import struct\n\n\ndef main():\n    print(struct.pack(">f", 1.0))\n\n\nmain()\n',
                     "'f' is not built; only integer fields and x are")
        self.refused('import struct\n\n\ndef main():\n    fmt = ">I"\n    print(struct.pack(fmt, 1))\n\n\nmain()\n',
                     "needs a string-literal format")
        self.refused('import struct\n\n\ndef main():\n    print(struct.unpack_from(">I", b"\\0\\0\\0\\1"))\n\n\nmain()\n',
                     "struct.unpack_from() with these arguments is not built")

    def test_bad_format_characters_are_refused_by_name(self):
        self.refused(r'import struct' + '\n\n\ndef main():\n    print(struct.calcsize(">\x1cI"))\n\n\nmain()\n',
                     "bad char")
        self.refused(r'import struct' + '\n\n\ndef main():\n    print(struct.pack(">\u0661I", 7))\n\n\nmain()\n',
                     "bad char")


if __name__ == "__main__":
    unittest.main()
