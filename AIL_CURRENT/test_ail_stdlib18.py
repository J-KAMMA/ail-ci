"""Library batch 6: struct.pack / unpack / unpack_from / pack_into / calcsize, compared with CPython 3.12.

Ordinary Python programs (below) are compiled with the Python syntax, once with the default build and once
with AIL_IR=1, run on generated stdin, and must print the same bytes as CPython (and exit with the same
status). Only explicit byte orders (< > !) with the standard sizes are built; a use outside that surface
must be a named compile-time refusal. A program that does not import struct keeps the text it has.
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

PROGRAMS = {}
PROGRAMS['basic'] = r"""import struct as st
from struct import pack, unpack, calcsize


class Box:
    def __init__(self, v: int) -> None:
        self.v: int = v


def roundtrip(value: int) -> int:
    raw = pack('>i', value)
    return unpack('>i', raw)[0]


def main() -> None:
    values: list[int] = [-2147483648, -1, 0, 1, 127, -128, 255, 65535, 2147483647]
    for v in values:
        print(v, roundtrip(v), list(st.pack('>i', v)))
    print(roundtrip(values[3]))
    box = Box(-12345)
    print(roundtrip(box.v))
    d: dict[str, int] = {'k': 4000000000}
    print(st.unpack('>I', st.pack('>I', d['k'])))
    print(calcsize('>bBhHiIlLq'), st.calcsize('>4s3x2?'), st.calcsize('>0s'))
    print(list(st.pack('>b', -128)), list(st.pack('>B', 255)))
    print(list(st.pack('>h', -32768)), list(st.pack('>H', 65535)))
    print(list(st.pack('>i', -2147483648)), list(st.pack('>I', 4294967295)))
    print(list(st.pack('>q', -9223372036854775808)), list(st.pack('>q', 9223372036854775807)))
    print(list(st.pack('>4s', b'abcdef')), list(st.pack('>4s', b'ab')))
    print(list(st.pack('>2c', b'a', b'b')), st.unpack('>2c', b'ab'))
    print(list(st.pack('>3x2I', 1, 2)), st.unpack('>3x2I', st.pack('>3x2I', 1, 2)))
    print(st.pack('>?', 0), st.pack('>?', 3), st.unpack('>3?', b'\x00\x01\x02'))
    print(st.unpack('>0s', b''), st.unpack('>2s', b'ab'))
    print(st.unpack('>hIq', st.pack('>hIq', -1, 2, -3)))
    data = st.pack('>hI', -1, 2) + b'\x00\x00'
    print(st.unpack_from('>hI', data), st.unpack_from('>hI', data, 1))
    buf = bytearray(12)
    print(st.pack_into('>hI', buf, 0, -1, 2), list(buf))
    print(st.pack_into('>hI', buf, 6, 1, 2), list(buf))
    print(st.pack(''), st.unpack('', b''))
    print(pack('>H', 65535), unpack('>H', b'\xff\xff'))
    print(st.calcsize('!I'), list(st.pack('!I', 1)))


main()
"""

PROGRAMS['errors'] = r"""import struct


def main() -> None:
    try:
        struct.unpack('>I', b'abc')
    except struct.error as e:
        print('short', e)
    try:
        struct.unpack('>I', b'abcde')
    except struct.error as e:
        print('long', e)
    try:
        struct.pack('>B', 256)
    except struct.error as e:
        print('B', e)
    try:
        struct.pack('>b', -129)
    except struct.error as e:
        print('b', e)
    try:
        struct.pack('>H', 65536)
    except struct.error as e:
        print('H', e)
    try:
        struct.pack('>h', 32768)
    except struct.error as e:
        print('h', e)
    try:
        struct.pack('>I', 4294967296)
    except struct.error as e:
        print('I', e)
    try:
        struct.pack('>i', 2147483648)
    except struct.error as e:
        print('i', e)
    try:
        struct.pack('>q', 9223372036854775808)
    except struct.error as e:
        print('q', e)
    try:
        struct.pack('>b', 1.5)
    except struct.error as e:
        print('float', e)
    try:
        struct.pack('>s', 5)
    except struct.error as e:
        print('s', e)
    try:
        struct.pack('>c', b'ab')
    except struct.error as e:
        print('c', e)
    try:
        struct.unpack_from('>I', b'ab', 0)
    except struct.error as e:
        print('from short', e)
    try:
        struct.unpack_from('>I', b'abcdef', -1)
    except struct.error as e:
        print('from neg', e)
    try:
        struct.unpack_from('>I', b'abcdef', 4)
    except struct.error as e:
        print('from past', e)
    try:
        struct.pack_into('>I', bytearray(2), 0, 1)
    except struct.error as e:
        print('into short', e)
    try:
        struct.pack_into('>I', bytearray(8), -1, 1)
    except struct.error as e:
        print('into neg', e)
    try:
        struct.pack_into('>I', bytearray(4), 2, 1)
    except struct.error as e:
        print('into past', e)


main()
"""

CASES = [
    ("basic", PROGRAMS['basic'], [""]),
    ("errors", PROGRAMS['errors'], [""]),
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
                    self.check(name, text, inputs, ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            "float": ("import struct\n\nprint(struct.pack('>d', 1.5))\n", "float format 'd'"),
            "native": ("import struct\n\nprint(struct.pack('I', 1))\n", "native layout"),
            "Q": ("import struct\n\nprint(struct.pack('>Q', 1))\n", "unsigned 64-bit format 'Q'"),
            "Struct": ("import struct\n\nprint(struct.Struct('>I').size)\n", "struct.Struct is not built"),
            "iter_unpack": ("import struct\n\nfor x in struct.iter_unpack('>I', b'abcd'):\n    print(x)\n",
                            "struct.iter_unpack is not built"),
            "dynamic": ("import struct\n\nfmt = '>I'\nprint(struct.pack(fmt, 1))\n",
                        "format must be a string literal"),
            "star": ("import struct\n\nprint(struct.pack('>I', *[1]))\n", "starred argument"),
            "keyword": ("import struct\n\nprint(struct.pack('>I', v=1))\n", "keyword argument"),
            "star_import": ("from struct import *\n\nprint(pack('>I', 1))\n", "name what you use"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


class UnchangedPrograms(unittest.TestCase):
    def test_programs_without_the_import_keep_their_text(self):
        import structlib
        for text in ("print(1)\n", "# struct is only mentioned here\nprint(2)\n", "struct = 3\nprint(struct)\n"):
            with self.subTest(text[:30]):
                notes = []
                self.assertIs(structlib.rewrite_text(text, notes), text)
                self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
