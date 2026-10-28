"""Library batch 3: struct (pack / unpack / unpack_from / calcsize / error) lowered onto bytes and compared
with CPython 3.12.

The format is parsed at compile time (python/pkg-v12/structlib.py, with the host's own struct.calcsize), so
offsets, native alignment, standard sizes and the error texts are CPython's.  Every program below is ordinary
Python with a literal format: CPython runs it as the oracle, the compiled program (the Python syntax, typed
path -- AIL_NO_GENERAL=1 -- so the typed path must take the lowering) prints the same bytes and exits the
same way, once with the default build and once with AIL_IR=1.  A format that is not a literal, a float format,
a starred argument, a format with no values at unpack time, a wrong value count and n/N/P outside the native
byte order are refused by name at compile time.

Declared differences (DIFFERENCES.md C-series): the format must be a literal; 'e', 'f', 'd' and 'p' are
refused; a value whose magnitude does not fit int64 cannot be packed or unpacked (so an unsigned 64-bit value
>= 2**63 is out of the subset); struct.error is the prelude's own class, not CPython's.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}

PROGRAMS['widths'] = r"""import struct


def main():
    p = struct.pack(">b", -128)
    print(len(p), list(p))
    u = struct.unpack(">b", p)
    print(u[0])
    p = struct.pack(">B", 255)
    print(len(p), list(p))
    p = struct.pack("<h", -32768)
    print(len(p), list(p))
    p = struct.pack(">H", 65535)
    print(len(p), list(p))
    p = struct.pack("<i", -2147483648)
    print(len(p), list(p))
    p = struct.pack(">I", 4294967295)
    print(len(p), list(p))
    p = struct.pack("<q", -9223372036854775808)
    print(len(p), list(p))
    p = struct.pack(">Q", 9223372036854775807)
    print(len(p), list(p))
    p = struct.pack("=l", -2147483648)
    print(len(p), list(p), struct.calcsize("=l"))
    p = struct.pack("@l", -9223372036854775808)
    print(len(p), list(p), struct.calcsize("@l"))
    p = struct.pack("<L", 4294967295)
    print(len(p), list(p))
    p = struct.pack("@n", -5)
    print(len(p), list(p))
    u = struct.unpack("@n", p)
    print(u[0])
    p = struct.pack("@N", 7)
    print(len(p), list(p))
    p = struct.pack("@P", 9)
    print(len(p), list(p))
    p = struct.pack(">BBH", 1, 2, 3)
    print(len(p), list(p))


main()
"""

PROGRAMS['align'] = r"""import struct


def main():
    p = struct.pack("@bi", 1, 2)
    print(struct.calcsize("@bi"), list(p))
    u = struct.unpack("@bi", p)
    print(u[0], u[1])
    p = struct.pack("<bi", 1, 2)
    print(struct.calcsize("<bi"), list(p))
    p = struct.pack("=bi", 1, 2)
    print(struct.calcsize("=bi"), list(p))
    p = struct.pack(">bi", 1, 2)
    print(struct.calcsize(">bi"), list(p))
    p = struct.pack("@bq", 1, 2)
    print(struct.calcsize("@bq"), list(p))
    p = struct.pack("@bh", 1, 2)
    print(struct.calcsize("@bh"), list(p))
    p = struct.pack("@ih", 1, 2)
    print(struct.calcsize("@ih"), list(p))
    p = struct.pack("@bI", 1, 2)
    print(struct.calcsize("@bI"), list(p))
    p = struct.pack("@2i", 1, 2)
    print(struct.calcsize("@2i"), list(p))
    p = struct.pack("@iii", 1, 2, 3)
    print(struct.calcsize("@iii"), list(p))
    p = struct.pack("@bhi", 1, 2, 3)
    print(struct.calcsize("@bhi"), list(p))
    p = struct.pack("@?i", 1, 2)
    print(struct.calcsize("@?i"), list(p))
    p = struct.pack("@cI", b"x", 5)
    print(struct.calcsize("@cI"), list(p))
    p = struct.pack("!H", 9)
    print(struct.calcsize("!H"), list(p))


main()
"""

PROGRAMS['mixed'] = r"""import struct


def main():
    packed = struct.pack(">16sHHIQQQIHHHHHH", b"name", 7, 3, 9, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    head = packed[:20]
    print(len(packed), list(head))
    parts = struct.unpack(">16sHHIQQQIHHHHHH", packed)
    name = parts[0]
    print(list(name), len(name), parts[1], parts[8], parts[12], parts[13])
    small = struct.pack("<c?x2s3xI", b"Z", 1, b"ab", 5)
    print(len(small), list(small))
    got = struct.unpack("<c?x2s3xI", small)
    c0 = got[0]
    s2 = got[2]
    print(list(c0), got[1], list(s2), got[3])
    print(struct.calcsize("<c?x2s3xI"))
    pad = struct.pack(">4xI", 7)
    print(list(pad), len(pad))
    both = struct.pack(">c?2s", b"Q", 0, b"hi")
    a, b, c = struct.unpack(">c?2s", both)
    print(list(a), b, list(c))


main()
"""

PROGRAMS['containers'] = r"""import struct


def main():
    values = [1, -2, 3]
    p0 = struct.pack("<q", values[0])
    p1 = struct.pack("<q", values[1])
    p2 = struct.pack("<q", values[2])
    print(len(p0), list(p0), list(p1), list(p2))
    three = struct.pack("<3q", values[0], values[1], values[2])
    got = struct.unpack("<3q", three)
    print(got[0], got[1], got[2])
    print(struct.calcsize("<3q"), struct.calcsize(">HHH"), struct.calcsize("4x"))


main()
"""

PROGRAMS['routes'] = r"""import struct as st


class Box:
    value: int = 11

    def __init__(self, value: int) -> None:
        self.value = value


def do(value: int) -> bytes:
    return st.pack(">I", value)


def check(data: bytes) -> int:
    return st.unpack("<i", data)[0]


import struct


def main():
    made0 = do(7)
    print(list(made0))
    items = [258, -2]
    p = st.pack(">H", items[1] + 4)
    print(list(p))
    vals = {"v": -2}
    p = struct.pack(">h", vals["v"])
    print(list(p))
    box = Box(12)
    p = struct.pack(">B", box.value)
    print(list(p))
    p = struct.pack(">B", Box.value)
    print(list(p))
    made = struct.pack("<i", -7)
    print(check(made))
    inner = do(1)
    first = inner[0]
    p = struct.pack(">I", first + 2)
    print(list(p))


main()
"""

PROGRAMS['strings'] = r"""import struct


def main():
    p = struct.pack(">4s", b"ab")
    print(len(p), list(p))
    p = struct.pack(">4s", b"abcdef")
    print(len(p), list(p))
    p = struct.pack("<3s2x", b"xy")
    print(len(p), list(p))
    p = struct.pack("<c3s", b"Q", b"hi")
    print(len(p), list(p))
    u = struct.unpack("<c3s", p)
    a = u[0]
    b = u[1]
    print(list(a), list(b))
    p = struct.pack(">?B?", True, 7, False)
    print(len(p), list(p))
    v = struct.unpack(">?B?", p)
    print(v[0], v[1], v[2])
    p = struct.pack("<16s", b"")
    print(len(p), list(p))


main()
"""

PROGRAMS['errors'] = r"""import struct


def main():
    try:
        struct.pack(">I", 4294967296)
        print("no error")
    except struct.error as e:
        print("error", e)
    try:
        struct.pack("<b", 128)
    except struct.error as e:
        print("error", e)
    try:
        struct.pack("<h", -32769)
    except struct.error as e:
        print("error", e)
    try:
        struct.pack(">Q", -1)
    except struct.error as e:
        print("error", e)
    try:
        struct.pack("c", b"ab")
    except struct.error as e:
        print("error", e)
    try:
        struct.unpack(">I", b"\x00\x00")
    except struct.error as e:
        print("error", e)
    try:
        struct.unpack_from(">I", b"abc", 5)
    except struct.error as e:
        print("error", e)
    print(struct.unpack_from(">I", b"abcdefgh", -4)[0])


main()
"""

PROGRAMS['from_import'] = r"""from struct import unpack, error, pack


def main():
    data = pack(">I", 305419896)
    print(list(data), unpack(">I", data)[0])
    try:
        pack(">I", 2 ** 32)
    except error as exc:
        print("caught", exc)
    try:
        unpack(">I", b"\x00")
    except ValueError as exc:
        print("wrong handler", exc)
    except error as exc:
        print("caught2", exc)


main()
"""

PROGRAMS['unpack_from'] = r"""from struct import pack, unpack_from, calcsize
import struct


def fields(data: bytes, index: int) -> tuple[int, int]:
    base = 8 + index * 12
    a = unpack_from("<I", data, base)[0]
    b = unpack_from("<Q", data, base + 4)[0]
    return a, b


def main():
    data = b"HEADER!!" + pack("<IQ", 7, 99) + pack("<IQ", 8, 100)
    print(fields(data, 0))
    print(fields(data, 1))
    print(unpack_from(">H", b"xx\x00\x09", 2)[0])
    print(unpack_from(">H", b"xx\x00\x09", -2)[0])
    print(calcsize("<IQ"), calcsize("P"), calcsize(""))
    print(pack("", ) == b"")
    try:
        unpack_from("<I", b"abc", 2)
    except struct.error as e:
        print("error", e)


main()
"""

# One representative program also goes through the general (default) path, where the same lowering runs.
CASES = ['widths', 'align', 'mixed', 'containers', 'routes', 'strings', 'errors', 'from_import', 'unpack_from']
DEFAULT_PATH = 'mixed'


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, ir, **env):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(env, AIL_IR="1" if ir else "0")
            built, _, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s" % (name, env["AIL_IR"], built.stdout, built.stderr))
            Path(directory, "oracle.py").write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))],
                                  capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-300:]))
            if got.stdout != want.stdout:
                a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                for n, (x, y) in enumerate(zip(a, b)):
                    if x != y:
                        self.fail("%s (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r" % (name, env["AIL_IR"], n + 1, x, y))
                self.fail("%s: %d lines against %d" % (name, len(a), len(b)))

    def test_typed_path_matches_cpython(self):
        for name in CASES:
            for ir in (False, True):
                with self.subTest(program=name, ir=ir):
                    self.check(name, PROGRAMS[name], ir, AIL_NO_GENERAL="1")

    def test_default_path_matches_cpython(self):
        for ir in (False, True):
            with self.subTest(program=DEFAULT_PATH, ir=ir):
                self.check(DEFAULT_PATH + "_default", PROGRAMS[DEFAULT_PATH], ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused", AIL_NO_GENERAL="1")
            self.assertEqual(built.returncode, 3, "not refused by name (%d): %s" % (built.returncode, wanted))
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            "dynamic": ("import struct\n\nfmt = '>I'\nprint(struct.pack(fmt, 1))\n",
                        "with a format that is not a string literal"),
            "float": ("import struct\n\nprint(struct.pack('<f', 1))\n",
                      "the float format 'f' is not built"),
            "starred": ("import struct\n\nxs = [1, 2]\nprint(struct.pack('<2I', *xs))\n",
                        "starred or keyword argument"),
            "empty_unpack": ("import struct\n\nprint(struct.unpack('4x', b'\\x00\\x00\\x00\\x00'))\n",
                             "unpacking a format with no values"),
            "count": ("import struct\n\nprint(struct.pack('<2I', 1))\n", "takes 2 values, not 1"),
            "nonnative": ("import struct\n\nprint(struct.pack('>n', 1))\n", "bad char in"),
            "badchar": ("import struct\n\nprint(struct.pack('<Z', 1))\n", "bad char in"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


if __name__ == "__main__":
    unittest.main()
