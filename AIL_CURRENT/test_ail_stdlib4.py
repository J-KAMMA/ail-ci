"""Library batch 4b: `struct.pack` and `struct.calcsize` on the integer codes, compared with CPython 3.12.

Ordinary Python programs are compiled with the Python syntax, once with the default build and once with
AIL_IR=1, run on generated stdin, and must print the same bytes as CPython (and exit with the same
status). The format has to be a string literal; the codes b B h H i I l L q Q, the repeat count
(including 0), `x` padding and whitespace between codes are built for the byte orders < > ! =, with
CPython's standard sizes. The bytes, the item count and the range errors are made by
`_ail_struct_pack`, a plain-Python helper that is added to the program (and runs under CPython too).

A use that is not built is refused by name at compile time: unpack / unpack_from / pack_into /
iter_unpack / Struct, a format that is not a literal, the native format (@ or no byte-order
character), the other codes, a `*values` argument and a module used as a value. `struct.error` in an
`except` clause is the helper's exception class; the message text is CPython's, only the printed class
name differs (declared in DIFFERENCES.md).
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}
PROGRAMS['routes'] = r"""import struct
import sys


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


def encode(a: int, b: int) -> bytes:
    return struct.pack(">I", a) + struct.pack("<H", b)


def main() -> None:
    data = [int(t) for t in sys.stdin.read().split()]
    if not data:
        return
    a = data[0]
    b = data[1] if len(data) > 1 else data[0]
    print(encode(a & 0xFFFFFFFF, b & 0xFFFF).hex())
    xs = [a & 0xFF, b & 0xFF, (a + b) & 0xFF]
    print(struct.pack(">3B", xs[0], xs[1], xs[2]).hex())
    print(struct.pack("<2H", xs[0], xs[1]).hex())
    box = Box(b)
    print(struct.pack(">h", box.v).hex())
    d = {"k": a}
    print(struct.pack(">q", d.get("k", 0)).hex())
    print(struct.calcsize(">I"), struct.calcsize("<2H3x"), struct.calcsize(">qQ"))
    print(struct.calcsize(">"), struct.calcsize("  "))
    print(struct.pack(">I I 2H", 1, 2, 3, 4).hex())
    print(struct.pack(">0I").hex(), struct.pack(">3x").hex())
    print(struct.pack(">2I", True, False).hex())


main()
"""

PROGRAMS['boundaries'] = r"""import struct
import sys


def main() -> None:
    vals = [int(t) for t in sys.stdin.read().split()]
    for v in vals:
        if 0 <= v <= 255:
            print("B", v, struct.pack(">B", v).hex())
        if -128 <= v <= 127:
            print("b", v, struct.pack(">b", v).hex())
        if 0 <= v <= 65535:
            print("H", v, struct.pack("<H", v).hex())
        if -32768 <= v <= 32767:
            print("h", v, struct.pack(">h", v).hex())
        if 0 <= v <= 4294967295:
            print("I", v, struct.pack(">I", v).hex(), struct.pack("<I", v).hex())
        if -2147483648 <= v <= 2147483647:
            print("i", v, struct.pack("<i", v).hex())
        print("q", v, struct.pack(">q", v).hex(), struct.pack("<q", v).hex())
        if 0 <= v:
            print("Q", v, struct.pack(">Q", v).hex())


main()
"""

PROGRAMS['from_import_errors'] = r"""from struct import pack, calcsize, error


def main() -> None:
    try:
        print(list(pack(">I", 7)))
    except error as e:
        print("E", str(e))
    try:
        pack(">B", 256)
    except error as e:
        print("E", str(e))
    try:
        pack(">B", -1)
    except error as e:
        print("E", str(e))
    try:
        pack(">b", 128)
    except error as e:
        print("E", str(e))
    try:
        pack(">h", -32769)
    except error as e:
        print("E", str(e))
    try:
        pack(">H", 65536)
    except error as e:
        print("E", str(e))
    try:
        pack(">i", 2147483648)
    except error as e:
        print("E", str(e))
    try:
        pack(">I", 4294967296)
    except error as e:
        print("E", str(e))
    try:
        pack(">Q", -1)
    except error as e:
        print("E", str(e))
    try:
        pack(">q", -9223372036854775808)
    except error as e:
        print("E", str(e))
    try:
        pack(">II", 1)
    except error as e:
        print("E", str(e))
    try:
        pack(">I", 1, 2)
    except error as e:
        print("E", str(e))
    try:
        pack(">I", 1.5)
    except error as e:
        print("E", str(e))
    print(calcsize(">hhl"), type(pack(">I", 1)).__name__)


main()
"""

PROGRAMS['alias_import'] = r"""import struct as st
import sys


def main() -> None:
    n = int(sys.stdin.read().split()[0])
    print(st.pack("<I", n & 0xFFFFFFFF).hex(), st.calcsize(">2H"))
    try:
        st.pack(">b", n)
    except st.error as e:
        print("E", str(e))


main()
"""


def route_inputs():
    rnd = random.Random(4)
    out = []
    for _ in range(6):
        out.append(" ".join(str(rnd.randint(-(2 ** 31), 2 ** 32)) for _ in range(2)) + "\n")
    out.append("0 0\n")
    return out


def boundary_inputs():
    seed = [0, 1, 127, 128, 255, 256, 32767, 32768, 65535, 65536, 2147483647, 2147483648,
            4294967295, 4294967296, 9223372036854775807, -1, -128, -129, -32768, -32769,
            -2147483648, -2147483649, -9223372036854775808]
    rnd = random.Random(5)
    return [" ".join(str(v) for v in seed) + "\n",
            " ".join(str(rnd.randint(-(2 ** 40), 2 ** 40)) for _ in range(20)) + "\n"]


CASES = [
    ("routes", PROGRAMS["routes"], route_inputs),
    ("boundaries", PROGRAMS["boundaries"], boundary_inputs),
    ("from_import_errors", PROGRAMS["from_import_errors"], lambda: ["0\n"]),
    ("alias_import", PROGRAMS["alias_import"], lambda: ["9\n", "-9\n", "300\n"]),
]


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
            built, _, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s"
                             % (name, env["AIL_IR"], built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            for k, stdin in enumerate(inputs):
                want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], input=stdin.encode(),
                                      capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode,
                                 "%s input %d: %s" % (name, k, got.stderr[-300:]))
                if got.stdout != want.stdout:
                    a = got.stdout.decode().splitlines()
                    b = want.stdout.decode().splitlines()
                    for n, (x, y) in enumerate(zip(a, b)):
                        if x != y:
                            self.fail("%s input %d (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                                      % (name, k, env["AIL_IR"], n + 1, x, y))
                    self.fail("%s input %d: %d lines against %d" % (name, k, len(a), len(b)))

    def test_programs_match_cpython(self):
        for name, text, inputs in CASES:
            for ir in (False, True):
                with self.subTest(program=name, ir=ir):
                    self.check(name, text, inputs(), ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            "unpack": ("import struct\n\nprint(struct.unpack('>I', b'\\x00\\x00\\x00\\x01'))\n",
                       "struct.unpack is not built"),
            "nonliteral": ("import struct\n\nfmt = '>I'\nprint(list(struct.pack(fmt, 1)))\n",
                           "the format has to be a string literal"),
            "native": ("import struct\n\nprint(list(struct.pack('I', 1)))\n",
                       "without a byte-order character"),
            "floatcode": ("import struct\n\nprint(list(struct.pack('>f', 1)))\n",
                          "the code 'f' of format '>f' is not built"),
            "struct_class": ("import struct\n\ns = struct.Struct('>I')\nprint(s.pack(1))\n",
                             "struct.Struct is not built"),
            "as_value": ("import struct\n\nf = struct.pack\nprint(f('>I', 1))\n",
                         "struct.pack used here is not built"),
            "star": ("import struct\n\nxs = [1]\nprint(list(struct.pack('>I', *xs)))\n",
                     "struct.pack with a *values argument is not built"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


if __name__ == "__main__":
    unittest.main()
