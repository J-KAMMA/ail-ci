"""Library batch 41: `struct.pack` / `struct.unpack` / `struct.calcsize`, compared with CPython 3.12.

The module is lowered by python/pkg-v12/structlib.py onto `int.to_bytes` / `int.from_bytes` (the code in
python/pkg-v12/prelude_struct.py).  The byte orders '<', '>', '=' and '!' are built; '=' is the native
little-endian order of the x86-64 targets.  The integer codes b B h H i I l L q, the bool code ?, the
char code c, the string codes s and p, the pad code x and repeat counts are built.  Native byte order
('@' or no prefix), the float codes e f d, the native-only codes n N P, the unsigned 64-bit code Q, a
zero-repeat p (CPython raises SystemError), `unpack_from`, `Struct`, `error`, keyword arguments and a
computed format for `unpack` stay named compile-time refusals.

The prelude is exercised directly against CPython's struct on generated formats and values; ordinary
Python programs are then compiled with the Python syntax, once with the default build and once with
AIL_IR=1, and must print the same bytes as CPython (and exit with the same status).
"""
import os
import random
import struct as pystruct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


PROGRAMS = {}
PROGRAMS["all_codes"] = r"""import struct


def main() -> None:
    print(struct.calcsize('<bBhHiIlLq'))
    print(struct.calcsize('>bBhHiIlLq'))
    print(struct.pack('<bBhHiIlLq', -1, 255, -2, 65535, -3, 4294967295, -4, 4294967295, -5))
    data = struct.pack('<bBhHiIlLq', -1, 255, -2, 65535, -3, 4294967295, -4, 4294967295, -5)
    print(struct.unpack('<bBhHiIlLq', data))
    print(struct.pack('>H', 0x1234), struct.unpack('>H', b'\x12\x34'))
    print(struct.pack('!I', 0x12345678), struct.unpack('!I', b'\x12\x34\x56\x78'))
    print(struct.pack('<i', -2147483648), struct.unpack('<i', b'\x00\x00\x00\x80'))
    print(struct.pack('>q', -9223372036854775808), struct.unpack('>q', b'\x80\x00\x00\x00\x00\x00\x00\x00'))
    print(struct.pack('<q', 9223372036854775807), struct.unpack('<q', b'\xff\xff\xff\xff\xff\xff\xff\x7f'))
    print(struct.pack('=I', 0x12345678).hex(), struct.unpack('=I', b'\x78\x56\x34\x12'))
    print(struct.pack('=H', 0x1234).hex(), struct.calcsize('=I'), struct.calcsize('=q'))
    for code, lo, hi in [('b', -128, 127), ('B', 0, 255), ('h', -32768, 32767), ('H', 0, 65535),
                         ('i', -2147483648, 2147483647), ('I', 0, 4294967295),
                         ('l', -2147483648, 2147483647), ('L', 0, 4294967295),
                         ('q', -9223372036854775808, 9223372036854775807)]:
        print(struct.pack('<' + code, lo).hex(), struct.pack('<' + code, hi).hex())


main()
"""

PROGRAMS["text_pad_bool"] = r"""import struct


def main() -> None:
    print(struct.pack('<4s', b'ab'), struct.unpack('<4s', b'ab\x00\x00'))
    print(struct.pack('<2s', b'abcdef'), struct.unpack('<2s', b'ab'))
    print(struct.pack('<5p', b'abcdef'), struct.unpack('<5p', b'\x04abcd'))
    print(struct.pack('<3p', b'ab'), struct.unpack('<3p', b'\x02ab'))
    print(struct.pack('<3p', b''), struct.unpack('<3p', b'\x00xy'))
    print(struct.pack('<3p', b'abcd'), struct.unpack('<3p', b'\xffab'))
    print(struct.pack('<3c', b'a', b'b', b'c'), struct.unpack('<3c', b'abc'))
    print(struct.pack('<4s', bytearray(b'xy')), struct.unpack('<4s', bytearray(b'xy\x00\x00')))
    print(struct.pack('<?', True), struct.pack('<?', False), struct.pack('<?', 0), struct.pack('<?', 7))
    print(struct.unpack('<?', b'\x00'), struct.unpack('<?', b'\x01'), struct.unpack('<?', b'\x02'))
    print(struct.pack('<3?', True, False, True), struct.unpack('<3?', b'\x01\x00\x01'))
    print(struct.pack('<2x3x'), struct.unpack('<5x', b'abcde'))
    print(struct.pack('<xHx', 7), struct.unpack('<xHx', b'\x00\x07\x00\x00'))
    print(struct.pack('<H', True).hex(), struct.pack('<H', False).hex())
    print(struct.calcsize(''), struct.pack(''), struct.unpack('', b''))
    print(struct.calcsize(' '), struct.pack(' '), struct.unpack(' ', b''))
    print(struct.calcsize('<'), struct.pack('<'), struct.calcsize('< '), struct.pack('< '))
    print(struct.calcsize('< H  I '), struct.pack('< H  I ', 1, 2))
    print(struct.calcsize('<H\tI\n'), struct.unpack('<H\tI\n', b'\x01\x00\x02\x00\x00\x00'))
    print(struct.calcsize('<0b'), struct.pack('<0b'), struct.unpack('<0b', b''))
    print(struct.calcsize('<0s'), struct.pack('<0s', b''), struct.unpack('<0s', b''))
    print(struct.calcsize('<0x'), struct.pack('<0x'), struct.unpack('<0x', b''))
    print(struct.calcsize('<3x'), struct.pack('<3x'), struct.unpack('<3x', b'\x00\x00\x00'))
    print(struct.pack(b'<H', 258).hex(), struct.unpack(b'<H', b'\x01\x02'), struct.calcsize(b'<2H'))


main()
"""

PROGRAMS["routes"] = r"""import struct
from struct import pack as p, unpack, calcsize


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


def pack_it(fmt: str, value: int) -> bytes:
    return struct.pack(fmt, value)


def unpack_it(data: bytes) -> tuple:
    return struct.unpack('<H', data)


def main() -> None:
    values = [258, 65535]
    d = {'v': 513}
    b = Box(772)
    alias = values[0]
    print(pack_it('<H', values[0]).hex())
    print(struct.pack('<H', values[1]).hex())
    print(struct.pack('<H', alias).hex())
    print(struct.pack('<H', d['v']).hex())
    print(struct.pack('<H', b.v).hex())
    print(struct.calcsize('<H'), struct.calcsize('>I'))
    print(unpack_it(b'\x01\x02'))
    print(struct.unpack('<H', pack_it('<H', 999)))
    print(p('<H', 258).hex(), unpack('<H', b'\x01\x02'), calcsize('<2H'))
    fmt = '<' + 'q' * 3
    vals = [1, -2, 3]
    print(struct.calcsize(fmt), struct.pack(fmt, vals[0], vals[1], vals[2]).hex())
    print(struct.unpack('<qqq', struct.pack(fmt, vals[0], vals[1], vals[2])))


main()
"""

PROGRAMS["runtime_errors"] = r"""import struct


def show(label: str, fn) -> None:
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main() -> None:
    show('range', lambda: struct.pack('<b', 128))
    show('range2', lambda: struct.pack('<B', -1))
    show('count', lambda: struct.pack('<2H', 1))
    show('count2', lambda: struct.pack('<H', 1, 2))
    show('char', lambda: struct.pack('<c', b'ab'))
    show('buffer', lambda: struct.unpack('<H', b'\x00'))
    show('int', lambda: struct.pack('<H', 1.5))
    show('str', lambda: struct.pack('<H', '1'))
    show('charint', lambda: struct.pack('<c', 97))


main()
"""

PROGRAMS["corpus_shape"] = r"""import struct
import sys


def to_bytes_list(x: int) -> list[int]:
    v = abs(x)
    length = (v.bit_length() + 7) // 8
    data = v.to_bytes(length, 'big')
    assert int.from_bytes(data, 'big') == v
    return list(data)


def main() -> None:
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    nums = [int(t) for t in tokens[1:1 + n]]
    out: list[str] = []
    for x in nums:
        out.append(str(to_bytes_list(x)))
        if abs(x) < 2 ** 32:
            out.append(str(list(struct.pack('>I', abs(x)))))
    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
"""

PROGRAMS["user_error_class"] = r"""import struct


class error(Exception):
    pass


def main() -> None:
    print(struct.pack('<H', 258).hex())
    try:
        raise error('mine')
    except Exception as e:
        print(type(e).__name__, str(e))


main()
"""

INPUTS = {
    "corpus_shape": "5 0 1 255 4294967295 4294967296\n",
}


class PreludeStruct(unittest.TestCase):
    """prelude_struct.py against CPython's struct on generated formats, values and errors."""

    CODES = "xcbB?hHiIlLqsp"
    WIDTHS = {"x": 0, "c": 1, "b": 1, "B": 1, "?": 1, "h": 2, "H": 2, "i": 4, "I": 4,
              "l": 4, "L": 4, "q": 8, "s": 1, "p": 1}

    def random_format(self, rnd):
        parts = []
        for _ in range(rnd.randint(0, 8)):
            code = rnd.choice(self.CODES)
            if code in "spx":
                count = rnd.randint(1, 5)
            else:
                count = rnd.randint(0, 4)
            parts.append((str(count) if count != 1 or rnd.random() < 0.5 else "") + code)
        return rnd.choice(["<", ">", "=", "!"]) + "".join(parts)

    def random_value(self, rnd, code):
        if code == "c":
            return bytes([rnd.randrange(256)])
        if code == "?":
            return rnd.choice([True, False, 0, 1, 2])
        if code in "sp":
            return bytes(rnd.randrange(256) for _ in range(rnd.randint(0, 6)))
        width = self.WIDTHS[code]
        if code in "bhlq":
            return rnd.randint(-(1 << (width * 8 - 1)), (1 << (width * 8 - 1)) - 1)
        return rnd.randint(0, (1 << (width * 8)) - 1)

    def values(self, P, fmt):
        plan = P._ail_struct_plan(fmt)
        out = []
        i = 0
        while i < plan[2]:
            code = P._STRUCT_CODES[plan[4 + 3 * i]]
            count = plan[5 + 3 * i]
            if code in "sp":
                out.append(self.random_value(self.rnd, code))
            elif code != "x":
                for _ in range(count):
                    out.append(self.random_value(self.rnd, code))
            i += 1
        return out

    def test_generated_formats_match_cpython(self):
        import prelude_struct as P
        self.rnd = random.Random(41)
        for _ in range(6000):
            fmt = self.random_format(self.rnd)
            try:
                size = pystruct.calcsize(fmt)
            except Exception:
                continue
            self.assertEqual(P._ail_struct_calcsize(fmt), size, fmt)
            values = self.values(P, fmt)
            try:
                packed = pystruct.pack(fmt, *values)
            except Exception:
                continue
            self.assertEqual(P._ail_struct_pack(fmt, *values), packed, (fmt, values))
            try:
                expected = pystruct.unpack(fmt, packed)
            except Exception:
                continue
            self.assertEqual(tuple(P._ail_struct_unpack_list(fmt, packed)), expected, (fmt, values))

    def test_runtime_errors_are_cpython_errors(self):
        import prelude_struct as P
        cases = [
            ("<b", (128,)), ("<B", (-1,)), ("<2H", (1,)), ("<H", (1, 2)),
            ("<c", (b"ab",)), ("<H", (1.5,)), ("<H", ("1",)),
        ]
        for fmt, values in cases:
            with self.assertRaises(pystruct.error) as want:
                pystruct.pack(fmt, *values)
            with self.assertRaises(P.error) as got:
                P._ail_struct_pack(fmt, *values)
            self.assertEqual(str(got.exception), str(want.exception))
        with self.assertRaises(P.error) as got:
            P._ail_struct_unpack_list("<H", b"\x00")
        self.assertEqual(str(got.exception), "unpack requires a buffer of 2 bytes")


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, stdin, ir, **env):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(env, AIL_IR="1" if ir else "0")
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s" % (name, env["AIL_IR"], built.stdout, built.stderr))
            Path(directory, "oracle.py").write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))],
                                  input=stdin.encode(), capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s (AIL_IR=%s): %s" % (name, env["AIL_IR"], got.stderr[-300:]))
            if got.stdout != want.stdout:
                a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                for n, (x, y) in enumerate(zip(a, b)):
                    if x != y:
                        self.fail("%s (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                                  % (name, env["AIL_IR"], n + 1, x, y))
                self.fail("%s (AIL_IR=%s): %d lines against %d" % (name, env["AIL_IR"], len(a), len(b)))

    def test_programs_match_cpython(self):
        for name, text in PROGRAMS.items():
            for ir in (False, True):
                with self.subTest(program=name, ir=ir):
                    self.check(name, text, INPUTS.get(name, ""), ir)

    def test_unbuilt_names_are_refused(self):
        cases = [
            ("native", "import struct\n\n\ndef main():\n    print(struct.pack('I', 1))\n\n\nmain()\n",
             "native byte order is not built"),
            ("float", "import struct\n\n\ndef main():\n    print(struct.pack('<f', 1.5))\n\n\nmain()\n",
             "float packing is not built"),
            ("unsigned64", "import struct\n\n\ndef main():\n    print(struct.pack('<Q', 1))\n\n\nmain()\n",
             "unsigned 64-bit value can leave int64"),
            ("unpack_from", "import struct\n\n\ndef main():\n    print(struct.unpack_from('<H', b'\\x00\\x01'))\n\n\nmain()\n",
             "only pack, unpack and calcsize are built"),
            ("computed_unpack", "import struct\n\n\ndef main():\n    fmt = '<H'\n    print(struct.unpack(fmt, b'\\x00\\x01'))\n\n\nmain()\n",
             "not a string literal is not built"),
        ]
        for name, text, wanted in cases:
            with self.subTest(case=name):
                with tempfile.TemporaryDirectory() as directory:
                    built, _, exe = compile_python(directory, text, "r_" + name)
                    self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                    self.assertIn(wanted, built.stderr)
                    self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
