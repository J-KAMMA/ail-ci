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

PROGRAMS['byteslike'] = r"""import struct


class Box:
    def __init__(self, v):
        self.v = v


def packed(v):
    return list(struct.pack('>4s', v))


def main() -> None:
    b = bytearray(b'ab')
    print(list(struct.pack('>4s', b)))
    print(list(struct.pack('>2s', b)))
    print(list(struct.pack('>1s', b)))
    print(packed(b))
    print(packed(bytearray(b'wxyz')))
    xs = [bytearray(b'cd')]
    print(list(struct.pack('>3s', xs[0])))
    box = Box(bytearray(b'ef'))
    print(list(struct.pack('>2s', box.v)))
    d = {'k': bytearray(b'gh')}
    print(list(struct.pack('>4s', d['k'])))
    print(struct.unpack('>2s', b), struct.unpack('>2s', bytes(b)))
    buf = bytearray(8)
    print(struct.pack_into('>4s', buf, 0, b), list(buf))
    print(struct.pack_into('>2s', buf, 2, xs[0]), list(buf))
    for bad in (5, 'ab', [97, 98]):
        try:
            struct.pack('>s', bad)
        except struct.error as e:
            print('s', type(e).__name__, e)
    for bad in (5, bytearray(b'a'), bytearray(b'ab'), b'ab'):
        try:
            struct.pack('>c', bad)
        except struct.error as e:
            print('c', type(e).__name__, e)
    print(list(struct.pack('>c', b'a')))


main()
"""

PROGRAMS['unpackbytes'] = r"""import struct


class Box:
    def __init__(self, v):
        self.v = v


def get(data):
    return struct.unpack('>2s', data)


def get_from(data, off):
    return struct.unpack_from('>2s', data, off)


def main() -> None:
    ba = bytearray(b'ab')
    print(struct.unpack('>2s', ba))
    print(struct.unpack('>2c', ba))
    print(struct.unpack_from('>2s', bytearray(b'abcd'), 1))
    print(get(ba), get(bytearray(b'xy')))
    print(get_from(bytearray(b'abcd'), 2))
    xs = [bytearray(b'pq')]
    print(struct.unpack('>2s', xs[0]))
    box = Box(bytearray(b'rs'))
    print(struct.unpack('>2s', box.v))
    d = {'k': bytearray(b'tu')}
    print(struct.unpack('>2s', d['k']))
    raw = struct.unpack('>2s', ba)[0]
    print(type(raw).__name__, isinstance(raw, bytes), isinstance(raw, bytearray))
    print(struct.unpack('>s', bytearray(b'z')))
    print(struct.unpack('>?c', bytearray(b'\x01q')))


main()
"""

PROGRAMS['errname'] = r"""import struct
from struct import error as E


def main() -> None:
    try:
        struct.unpack('>I', b'abc')
    except Exception as e:
        print(type(e).__name__, e)
    try:
        struct.pack('>B', 256)
    except Exception as e:
        print(type(e).__name__, e)
    try:
        struct.pack('>s', 5)
    except E as e:
        print(type(e).__name__, e)
    try:
        raise struct.error('custom')
    except Exception as e:
        print(type(e).__name__, str(e), repr(e))


main()
"""

PROGRAMS['offsets'] = r"""import struct


def uf0(n, off):
    try:
        return struct.unpack_from('>0I', bytes(n), off)
    except struct.error as e:
        return 'E ' + str(e)


def uf1(off):
    try:
        return struct.unpack_from('>I', bytes(range(8)), off)
    except struct.error as e:
        return 'E ' + str(e)


def uf2(off):
    try:
        return struct.unpack_from('>2I', bytes(range(8)), off)
    except struct.error as e:
        return 'E ' + str(e)


def pi0(n, off):
    b = bytearray(n)
    try:
        struct.pack_into('>0I', b, off)
        return list(b)
    except struct.error as e:
        return 'E ' + str(e)


def pi1(n, off):
    b = bytearray(n)
    try:
        struct.pack_into('>I', b, off, 0x01020304)
        return list(b)
    except struct.error as e:
        return 'E ' + str(e)


def pi2(n, off):
    b = bytearray(n)
    try:
        struct.pack_into('>2I', b, off, 1, 2)
        return list(b)
    except struct.error as e:
        return 'E ' + str(e)


def main() -> None:
    print('-- zero size unpack_from')
    ns = [0, 1, 4]
    offs = [-6, -5, -4, -1, 0, 1, 4, 5, 6]
    for n in ns:
        for off in offs:
            print('uf', n, off, uf0(n, off))
    print('-- zero size pack_into')
    for n in ns:
        for off in offs:
            print('pi', n, off, pi0(n, off))
    print('-- nonzero unpack_from')
    for off in [-10, -8, -5, -4, -1, 0, 1, 4, 8, 9]:
        print('uf >I', off, uf1(off))
    for off in [-10, -8, -5, -4, -1, 0, 1, 4, 8, 9]:
        print('uf >2I', off, uf2(off))
    print('-- nonzero pack_into')
    for n in [0, 4, 8, 12]:
        for off in [-10, -8, -5, -4, -1, 0, 1, 4, 8, 9]:
            print('pi >I', n, off, pi1(n, off))
    for n in [0, 4, 8, 12]:
        for off in [-10, -8, -5, -4, -1, 0, 1, 4, 8, 9]:
            print('pi >2I', n, off, pi2(n, off))


main()
"""

PROGRAMS['badinputs'] = r"""import struct


def uf(data):
    try:
        print(struct.unpack('>I', data))
    except Exception as e:
        print(type(e).__name__, e)


def uff(data):
    try:
        print(struct.unpack_from('>I', data, 0))
    except Exception as e:
        print(type(e).__name__, e)


def pi(buf):
    try:
        print(struct.pack_into('>I', buf, 0, 1))
    except Exception as e:
        print(type(e).__name__, e)


def main() -> None:
    uf(5)
    uf('abcd')
    uf([1, 2, 3, 4])
    uff(5)
    uff('abcd')
    uff([1, 2, 3, 4])
    pi(b'')
    pi(5)
    pi('abcd')
    pi([0, 0, 0, 0])


main()
"""

CASES = [
    ("basic", PROGRAMS['basic'], [""]),
    ("errors", PROGRAMS['errors'], [""]),
    ("byteslike", PROGRAMS['byteslike'], [""]),
    ("unpackbytes", PROGRAMS['unpackbytes'], [""]),
    ("errname", PROGRAMS['errname'], [""]),
    ("offsets", PROGRAMS['offsets'], [""]),
    ("badinputs", PROGRAMS['badinputs'], [""]),
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
