"""Library batch 46: `struct` lowered onto bytes and int.to_bytes / int.from_bytes.

The program below is compiled with the default build and with AIL_IR=1, run on generated stdin, and
must print the same bytes as CPython (and exit with the same status). A second test checks that a use
outside the built subset is a named refusal.
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


PROGRAM = r"""import struct
import struct as st
import sys
from struct import pack, unpack as up, calcsize as cs


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


def pick(values: list[int], index: int) -> int:
    return values[index]


def main() -> None:
    values: list[int] = [int(token) for token in sys.stdin.read().split()]
    table: dict[str, int] = {"x": values[0], "y": values[1]}
    box = Box(values[2])
    print(struct.pack(">I", values[0]))
    print(st.pack("<I", pick(values, 1)))
    print(pack(">H", table["y"] % 65536))
    print(st.pack(">h", box.value % 32768 - 16384))
    print(struct.pack(">bBhHiIqQ", -1, 255, -2, 65535, -3, 4294967295, -4, 9223372036854775807))
    packed = struct.pack(">bBhHiIqQ", -1, 255, -2, 65535, -3, 4294967295, -4, 7)
    print(struct.unpack(">bBhHiIqQ", packed))
    print(struct.pack(">?c4s3p", True, b"Z", b"abcdef", b"hello"))
    print(struct.unpack(">?c4s3p", b"\x01Zabcd\x02he"))
    print(struct.pack(">3x2I", 1, 2), struct.calcsize(">3x2I"))
    print(struct.pack(""), struct.unpack("", b""))
    print(struct.pack(">0i"), struct.unpack(">0i", b""))
    print(struct.pack(">2c", b"a", b"b"), struct.unpack(">2c", b"ab"))
    pair = up("<2H", b"\x01\x00\x02\x00")
    print(pair, pair[0], pair[1])
    print(cs(">4H"), st.calcsize("<2I"))
    print(struct.pack(">4s", bytearray(b"ab")), struct.unpack(">4s", bytearray(b"abcd")))
    print(struct.pack("<q", -9223372036854775807 - 1))
    try:
        struct.pack(">i", 1.5)
    except struct.error as exc:
        print(type(exc).__name__, exc)
    try:
        struct.unpack(">I", "abcd")
    except TypeError as exc:
        print(type(exc).__name__, exc)
    try:
        raise struct.error("boom")
    except struct.error as exc:
        print(type(exc).__name__, exc)
    try:
        struct.pack(">I", -1)
    except struct.error as exc:
        print(type(exc).__name__, exc)
    try:
        struct.unpack(">I", b"abc")
    except struct.error as exc:
        print(type(exc).__name__, exc)
    try:
        struct.pack(">c", b"ab")
    except struct.error as exc:
        print(type(exc).__name__, exc)


main()
"""

INPUTS = [
    "0 0 0\n",
    "1 1 1\n",
    "305419896 305419896 -1\n",
    "4294967295 4294967295 2147483647\n",
]


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


class StructTests(unittest.TestCase):
    def check(self, text, name, inputs):
        for ir in (False, True):
            with self.subTest(ir=ir), tempfile.TemporaryDirectory() as directory:
                built, _source, exe = compile_python(directory, text, name, AIL_IR="1" if ir else "0")
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                oracle = Path(directory, "oracle.py")
                oracle.write_text(text, encoding="utf-8")
                for stdin in inputs:
                    want = subprocess.run([sys.executable, str(oracle)], input=stdin.encode(),
                                          capture_output=True, timeout=300)
                    got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
                    self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout),
                                     "%s (AIL_IR=%s)\n%s" % (name, ir, got.stderr[-500:]))

    def test_program_matches_cpython(self):
        self.check(PROGRAM, "prog_struct", INPUTS)

    def test_refusal_names_the_use(self):
        text = "import struct\n\nprint(struct.pack('I', 1))\n"
        with tempfile.TemporaryDirectory() as directory:
            built, _source, exe = compile_python(directory, text, "refused")
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn("native byte order", built.stderr)
            self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
