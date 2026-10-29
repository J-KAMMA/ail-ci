"""struct batch: pack / unpack / calcsize / error for the integer formats, compared with CPython.

Every program is ordinary Python. CPython runs it as the oracle, the compiled program prints the same bytes
on the typed path (AIL_NO_GENERAL=1) and on the general path (AIL_UNIFIED_FORCE=1), or the spelling is
refused by name at compile time -- there is no third outcome where the numbers differ.

Built: pack, unpack and calcsize with a str literal format whose first character is "<", ">" or "!", and
the format characters x b B h H i I l L q Q ? (pack only for "?", whose unpack result would be a bool).
Refused by name: the native "@" / "=" byte order and alignment, floats, c s p, n N, Struct, pack_into,
unpack_from, iter_unpack, run-time formats, * arguments and keyword arguments.
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODES = (("typed", {"AIL_NO_GENERAL": "1"}), ("general", {"AIL_UNIFIED_FORCE": "1"}))
INFO = {"b": (1, -128, 127), "B": (1, 0, 255), "h": (2, -32768, 32767), "H": (2, 0, 65535),
        "i": (4, -2147483648, 2147483647), "I": (4, 0, 4294967295),
        "l": (4, -2147483648, 2147483647), "L": (4, 0, 4294967295),
        "q": (8, -9223372036854775808, 9223372036854775807), "Q": (8, 0, 9223372036854775807)}


def compile_python(directory, text, name, extra):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    env = dict(os.environ)
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    env.update(extra)
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=env)
    return built, source, exe


def integer_program(seed, count=60):
    rng = random.Random(seed)
    lines = ["import struct", "", "", "def main() -> None:"]
    for index in range(count):
        order = rng.choice("<>!")
        parts, values = [], []
        for _ in range(rng.randint(1, 4)):
            ch = rng.choice(sorted(INFO))
            repeat = rng.randint(1, 3)
            parts.append(str(repeat) + ch if repeat > 1 else ch)
            low, high = INFO[ch][1], INFO[ch][2]
            for _ in range(repeat):
                values.append(rng.choice([low, high, 0, 1, -1 if low < 0 else 0, rng.randint(low, high)]))
        if rng.random() < 0.2:
            parts.insert(rng.randrange(len(parts) + 1), str(rng.randint(1, 4)) + "x")
        fmt = order + "".join(parts)
        lines.append("    b%02d = struct.pack(%r, %s)" % (index, fmt, ", ".join(map(str, values))))
        lines.append("    print(b%02d.hex(), struct.unpack(%r, b%02d))" % (index, fmt, index))
    lines.extend(["", "", "main()"])
    return "\n".join(lines) + "\n"


BOUNDARIES_PROGRAM = r'''import struct


def main() -> None:
    print(struct.pack(">0I").hex(), struct.pack(">2x").hex(), struct.pack("> 2I", 3, 4).hex(), struct.pack(">2I ", 5, 6).hex())
    print(struct.calcsize(">0I"), struct.calcsize(">2x"), struct.calcsize("> 2I"))
    print(struct.pack(">I", 1).hex(), struct.pack(">2I", 2, 3).hex())
    print(struct.pack(">bBhHiIqQ", -1, 255, -2, 65535, -3, 4294967295, -4, 2 ** 63 - 1).hex())
    print(struct.unpack(">bBhHiIqQ", struct.pack(">bBhHiIqQ", -1, 255, -2, 65535, -3, 4294967295, -4, 2 ** 63 - 1)))
    print(struct.unpack("<Q", b"\x00\x00\x00\x00\x00\x00\x00\x7f"))
    try:
        print(struct.pack(">I").hex())
    except struct.error as e:
        print("missing", e)
    try:
        print(struct.pack(">I", 1, 2).hex())
    except struct.error as e:
        print("extra", e)
    try:
        print(struct.pack(">2I", 1).hex())
    except struct.error as e:
        print("short", e)
    try:
        print(struct.pack("<B", 256).hex())
    except struct.error as e:
        print("range", e)
    try:
        print(struct.unpack(">2I", b"\x00" * 7))
    except struct.error as e:
        print("buffer", e)



main()
'''

EXPRESSION_PROGRAM = r'''import struct
from struct import pack as pk, unpack, calcsize as cs, error as StructError


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


def packit(value: int) -> bytes:
    return struct.pack(">I", value)


def unpackit(data: bytes) -> int:
    return struct.unpack(">I", data)[0]


def main() -> None:
    xs = [10, 20]
    box = Box(30)
    table = {"k": 40}
    print(packit(xs[0]).hex(), packit(box.value).hex(), packit(table["k"]).hex())
    print(struct.pack(">I", unpackit(b"\x00\x00\x00\x07")).hex())
    print(pk("<H", 513).hex(), unpack("<H", b"\x01\x02"), cs("<H"))
    print(struct.pack(">I", 5).hex(), struct.unpack(">H", b"\x00\x09"), struct.calcsize("<Q"))
    try:
        pk(">B", 300)
    except StructError as e:
        print("caught", e)


main()
'''

REFUSALS = (
    ("native", 'import struct\n\n\ndef main() -> None:\n    print(struct.pack("I", 1))\n\n\nmain()\n',
     "struct.pack: the format 'I' has to start with"),
    ("float", 'import struct\n\n\ndef main() -> None:\n    print(struct.pack("<d", 1.5))\n\n\nmain()\n',
     "struct.pack: the format character 'd' in '<d' is not built"),
    ("dynamic", 'import struct\n\n\ndef main() -> None:\n    fmt = ">I"\n    print(struct.pack(fmt, 1))\n\n\nmain()\n',
     "struct.pack: the format has to be a str literal here"),
    ("unpack-question", 'import struct\n\n\ndef main() -> None:\n    print(struct.unpack(">?", b"\\x01"))\n\n\nmain()\n',
     "struct.unpack: the ? format is not built"),
    ("struct-object", 'import struct\n\n\ndef main() -> None:\n    s = struct.Struct(">I")\n    print(s.pack(1))\n\n\nmain()\n',
     "struct.Struct used here is not built"),
    ("pack-into", 'import struct\n\n\ndef main() -> None:\n    b = bytearray(4)\n    struct.pack_into(">I", b, 0, 1)\n    print(b)\n\n\nmain()\n',
     "struct.pack_into used here is not built"),
)


class StructTests(unittest.TestCase):
    def compare(self, text, name, stdin=b""):
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, name + "_oracle.py")
            oracle.write_text(text, encoding="utf-8")
            expected = subprocess.run([sys.executable, str(oracle)], input=stdin, capture_output=True, timeout=300)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for mode, extra in MODES:
                with self.subTest(mode=mode):
                    built, _, exe = compile_python(directory, text, name + "_" + mode, extra)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)
                    self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout), ran.stderr[:1000])

    def refused(self, text, wanted, name):
        with tempfile.TemporaryDirectory() as directory:
            for mode, extra in MODES:
                with self.subTest(mode=mode):
                    built, _, exe = compile_python(directory, text, name + "_" + mode, extra)
                    self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                    self.assertIn(wanted, built.stderr)
                    self.assertFalse(exe.exists())

    def test_pack_unpack_calcsize_integer_formats(self):
        self.compare(integer_program(42), "struct_integer")
        self.compare(integer_program(43, 40), "struct_integer2")

    def test_boundaries_errors_and_wide_unsigned(self):
        self.compare(BOUNDARIES_PROGRAM, "struct_boundaries")

    def test_from_import_alias_and_expressions(self):
        self.compare(EXPRESSION_PROGRAM, "struct_expressions")

    def test_refusals_name_the_use(self):
        for name, text, wanted in REFUSALS:
            with self.subTest(name=name):
                self.refused(text, wanted, "struct_refuse_" + name)


if __name__ == "__main__":
    unittest.main()
