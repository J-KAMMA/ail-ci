"""Library batch 6: struct pack / unpack / unpack_from / calcsize / error, compared with CPython 3.12.

Three layers:

* prelude_struct.py is plain Python, so it runs under CPython next to the struct module: generated formats
  and values must agree byte for byte, and the exceptions must agree in type and message;
* ordinary Python programs are compiled with the Python syntax, once with AIL_IR=0 and once with AIL_IR=1,
  and must print the same bytes as CPython and exit with the same status;
* every use outside the built subset is refused by name at compile time (computed format, native alignment,
  floats, Pascal strings, pack_into / iter_unpack / Struct).

The generated compiled cases stay inside the signed 64-bit range only to keep the program text ordinary;
the prelude cases and the fixed program cover the full unsigned 64-bit range.
"""
import os
import random
import struct
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

import prelude_struct as P

CODES = {
    "b": (1, True), "B": (1, False),
    "h": (2, True), "H": (2, False),
    "i": (4, True), "I": (4, False),
    "l": (4, True), "L": (4, False),
    "q": (8, True), "Q": (8, False),
}


def normalise(fmt):
    if not fmt:
        return fmt
    if fmt[0] == "!":
        return ">" + fmt[1:]
    if fmt[0] == "=":
        return ("<" if sys.byteorder == "little" else ">") + fmt[1:]
    return fmt


def random_case(rng, safe):
    prefix = rng.choice("<>!=")
    parts = []
    values = []
    for _ in range(rng.randint(0, 5)):
        kind = rng.choice(["int", "x", "c", "s", "?"])
        if kind == "int":
            code = rng.choice(list(CODES))
            width, signed = CODES[code]
            bits = width * 8
            count = rng.randint(0, 3)
            parts.append((str(count) if count != 1 else "") + code)
            for _ in range(count):
                if signed:
                    low = -(1 << (bits - 1)) + (1 if safe and code == "q" else 0)
                    high = (1 << (bits - 1)) - 1
                else:
                    low = 0
                    high = (1 << bits) - 1
                    if safe:
                        high = min(high, (1 << 63) - 1)
                values.append(rng.randint(low, high))
        elif kind == "x":
            count = rng.randint(0, 4)
            parts.append((str(count) if count != 1 else "") + "x")
        elif kind == "c":
            count = rng.randint(0, 3)
            parts.append((str(count) if count != 1 else "") + "c")
            for _ in range(count):
                values.append(bytes([rng.randrange(256)]))
        elif kind == "s":
            count = rng.randint(0, 5)
            parts.append((str(count) if count != 1 else "") + "s")
            values.append(bytes(rng.randrange(256) for _ in range(rng.randint(0, 8))))
        else:
            count = rng.randint(0, 3)
            parts.append((str(count) if count != 1 else "") + "?")
            for _ in range(count):
                values.append(rng.choice([0, 1, 2, True, False]))
    return prefix + "".join(parts), values


def compiled_program(cases):
    lines = ["import struct", "", "", "def main() -> None:"]
    for fmt, values in cases:
        args = ", ".join(repr(value) for value in values)
        call = "struct.pack(%r%s)" % (fmt, (", " + args) if args else "")
        data = struct.pack(fmt, *values)
        offset = len(data) % 3
        blob = b"\xaa" * offset + data + b"\xbb" * 2
        lines.append("    data = %s" % call)
        lines.append("    print(data.hex())")
        lines.append("    print(struct.unpack(%r, data))" % fmt)
        lines.append("    print(struct.calcsize(%r))" % fmt)
        lines.append("    print(struct.unpack_from(%r, %r, %d))" % (fmt, blob, offset))
    lines.append("")
    lines.append("")
    lines.append("main()")
    return "\n".join(lines) + "\n"


FIXED = r"""from struct import pack, unpack, unpack_from, calcsize, error
import struct


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


def main() -> None:
    xs = [0x11223344]
    d = {'k': 0x55667788}
    b = Box(0x99AABBCC)
    print(pack('<I', xs[0]).hex(), pack('<I', d['k']).hex(), pack('<I', b.v).hex())
    print(unpack('<i', pack('<i', -12345)))
    print(unpack_from('<H', b'\x00\x01\x02', 1))
    print(unpack_from('<I', b'\x00\x01\x02\x03\x04\x05\x06', -4))
    print(unpack_from('<H', b'\x00\x01\x02\x03\x04\x05\x06', -5))
    print(unpack_from('', b'\x00\x01\x02', -3))
    print(calcsize('<q'), calcsize('>Q'), calcsize('<0I'), calcsize('<'))
    print(pack('').hex(), unpack('', b''))
    print(pack('<4s', b'ab').hex(), pack('<4s', bytearray(b'abcd')).hex(), pack('<4s', b'abcdef').hex())
    print(unpack('<4s', b'ab\x00\x00'))
    print(pack('<bBhHiIlLqQ', -1, 255, -2, 65535, -3, 4294967295, -4, 4294967295, -5, 2**63 - 1).hex())
    print(unpack('<bBhHiIlLqQ', pack('<bBhHiIlLqQ', -1, 255, -2, 65535, -3, 4294967295, -4, 4294967295, -5, 2**63 - 1)))
    print(pack('<?', 0).hex(), pack('<?', 3.5).hex(), pack('<?', []).hex(), pack('<?', [1]).hex())
    print(pack('<3c', b'a', b'b', b'c').hex(), pack('<3?', 0, 2, []).hex())
    print(calcsize('<3c'), calcsize('<3?'), calcsize('<0c3c3?0?s'))
    print(pack('=I', 0x01020304).hex(), unpack('!H', b'\x12\x34'))
    print(pack('>Q', 18446744073709551615).hex(), unpack('>Q', b'\xff' * 8))
    print(struct.calcsize('>16sHHIQQQIHHHHHH'))
    try:
        pack('<I', -1)
    except error as e:
        print(type(e).__name__, e)
    try:
        pack('<b', 128)
    except Exception as e:
        print(type(e).__name__, e)
    try:
        pack('<B', 256)
    except Exception as e:
        print(type(e).__name__, e)
    try:
        pack('<I', 1.5)
    except Exception as e:
        print(type(e).__name__, e)
    try:
        pack('<c', bytearray(b'a'))
    except Exception as e:
        print(type(e).__name__, e)
    try:
        pack('<s', 'a')
    except Exception as e:
        print(type(e).__name__, e)
    try:
        pack('<2I', 1)
    except Exception as e:
        print(type(e).__name__, e)
    try:
        unpack('<I', 'abcd')
    except Exception as e:
        print(type(e).__name__, e)
    try:
        unpack('<I', b'\x00\x00\x00')
    except Exception as e:
        print(type(e).__name__, e)
    try:
        unpack_from('<I', b'\x00\x00\x00\x00', -1)
    except Exception as e:
        print(type(e).__name__, e)
    try:
        unpack_from('<I', b'\x00\x00\x00\x00', -5)
    except Exception as e:
        print(type(e).__name__, e)
    try:
        unpack_from('<I', b'\x00\x00', 10)
    except Exception as e:
        print(type(e).__name__, e)
    try:
        unpack_from('', b'', 1)
    except Exception as e:
        print(type(e).__name__, e)


main()
"""


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


class PreludeStruct(unittest.TestCase):
    def test_pack_unpack_against_cpython(self):
        rng = random.Random(17)
        for _ in range(20000):
            fmt, values = random_case(rng, False)
            nf = normalise(fmt)
            want = struct.pack(fmt, *values)
            self.assertEqual(P._ail_struct_pack(nf, *values), want, (fmt, values))
            self.assertEqual(P._ail_struct_calcsize(nf), struct.calcsize(fmt), fmt)
            self.assertEqual(P._ail_struct_unpack(nf, want), struct.unpack(fmt, want), (fmt, values))
            pad = rng.randint(0, 3)
            blob = bytes(rng.randrange(256) for _ in range(pad)) + want + bytes(rng.randrange(256) for _ in range(2))
            if len(want) and rng.random() < 0.5:
                offset = rng.randint(-len(blob), -len(want))
            else:
                offset = rng.randint(0, len(blob) - len(want))
            self.assertEqual(P._ail_struct_unpack_from(nf, blob, offset), struct.unpack_from(fmt, blob, offset),
                             (fmt, blob, offset))

    def test_errors_match_cpython(self):
        def name(exc, kind):
            return "error" if isinstance(exc, kind) else type(exc).__name__

        cases = []
        for fmt, values in [("<I", ()), ("<2I", (1,)), ("<I", (1, 2)), (">H", (1, 2, 3)),
                            ("4s", (b"a", b"b")), ("c", (b"ab",))]:
            cases.append(("pack", fmt, values))
        for fmt, values in [("b", (128,)), ("b", (-129,)), ("B", (-1,)), ("B", (256,)), ("H", (65536,)),
                            ("h", (-32769,)), ("I", (-1,)), ("I", (1 << 32,)), ("q", (1 << 63,)),
                            ("Q", (-1,)), ("Q", (1 << 64,))]:
            cases.append(("pack", fmt, values))
        for fmt, values in [("<I", ("x",)), ("<I", (1.5,)), ("<I", (None,)), ("<c", (1,)),
                            ("<c", (b"",)), ("<c", (b"ab",)), ("<s", (1,)), ("<s", ("x",)), ("<2s", (b"a",))]:
            cases.append(("pack", fmt, values))
        for fmt, data in [("<I", b""), ("<I", b"\x00\x00\x00"), ("<2I", b"\x00" * 7),
                          (">H", b"\x00"), ("", b"x"), ("<0I", b"x")]:
            cases.append(("unpack", fmt, data))
        for fmt, data, offset in [("<I", b"\x00" * 4, -1), ("<I", b"\x00" * 4, -5),
                                  ("<I", b"\x00" * 4, 1), ("<I", b"\x00" * 4, 5), ("", b"", 1),
                                  ("", b"abcd", -1), ("", b"abcd", -4), ("", b"abcd", -5),
                                  ("<0I", b"", 0), ("<0I", b"", -1),
                                  ("<I", b"\x00" * 7, -4), ("<I", b"\x00" * 7, -5),
                                  ("<I", b"\x00" * 7, -6), ("<I", b"\x00" * 7, -7),
                                  ("<I", b"\x00" * 7, -8), ("<H", b"\x00" * 7, -2),
                                  ("<H", b"\x00" * 7, -1), ("", b"\x00" * 7, -7),
                                  ("", b"\x00" * 7, -8), ("<0I", b"\x00" * 7, -7),
                                  ("<I", b"", -3), ("<I", b"", -4), ("<Q", b"", -5),
                                  (">3H", b"", -4), (">3H", b"", -6), ("<I", b"\x00" * 2, -3),
                                  ("<I", b"\x00" * 2, -4), ("<Q", b"\x00" * 7, -7),
                                  ("<Q", b"\x00" * 7, -8)]:
            cases.append(("unpack_from", fmt, data, offset))
        for case in cases:
            kind = case[0]
            try:
                if kind == "pack":
                    _, fmt, values = case
                    want = ("ok", struct.pack(fmt, *values))
                elif kind == "unpack":
                    _, fmt, data = case
                    want = ("ok", struct.unpack(fmt, data))
                else:
                    _, fmt, data, offset = case
                    want = ("ok", struct.unpack_from(fmt, data, offset))
            except Exception as exc:
                want = (name(exc, struct.error), str(exc))
            try:
                if kind == "pack":
                    _, fmt, values = case
                    got = ("ok", P._ail_struct_pack(normalise(fmt), *values))
                elif kind == "unpack":
                    _, fmt, data = case
                    got = ("ok", P._ail_struct_unpack(normalise(fmt), data))
                else:
                    _, fmt, data, offset = case
                    got = ("ok", P._ail_struct_unpack_from(normalise(fmt), data, offset))
            except Exception as exc:
                got = (name(exc, P.error), str(exc))
            self.assertEqual(got, want, case)


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, ir):
        with tempfile.TemporaryDirectory() as directory:
            env = {"AIL_IR": "1" if ir else "0"}
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s" % (name, env["AIL_IR"], built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-300:]))
            if got.stdout != want.stdout:
                a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                for n, (x, y) in enumerate(zip(a, b)):
                    if x != y:
                        self.fail("%s (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r" % (name, env["AIL_IR"], n + 1, x, y))
                self.fail("%s: %d lines against %d" % (name, len(a), len(b)))

    def test_generated_program_matches_cpython(self):
        rng = random.Random(23)
        cases = [random_case(rng, True) for _ in range(30)]
        cases.append(("", []))
        cases.append(("<16sHHIQQQIHHHHHH", [b"abc", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]))
        text = compiled_program(cases)
        for ir in (False, True):
            with self.subTest(ir=ir):
                self.check("generated", text, ir)

    def test_fixed_program_matches_cpython(self):
        for ir in (False, True):
            with self.subTest(ir=ir):
                self.check("fixed", FIXED, ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            "computed": ("import struct\n\nfmt = '<I'\nprint(struct.pack(fmt, 1))\n", "literal format string"),
            "native": ("import struct\n\nprint(struct.pack('@I', 1))\n", "native alignment"),
            "no_prefix": ("import struct\n\nprint(struct.pack('I', 1))\n", "no byte-order prefix"),
            "float": ("import struct\n\nprint(struct.pack('<f', 1.5))\n", "floating-point format 'f'"),
            "pascal": ("import struct\n\nprint(struct.pack('<p', b'a'))\n", "Pascal-string format 'p'"),
            "native_code": ("import struct\n\nprint(struct.pack('<n', 1))\n", "native-only format 'n'"),
            "pack_into": ("import struct\n\nb = bytearray(4)\nstruct.pack_into('<I', b, 0, 1)\n", "pack_into"),
            "iter_unpack": ("import struct\n\nprint(list(struct.iter_unpack('<I', b'\\x00' * 4)))\n", "iter_unpack"),
            "struct_class": ("import struct\n\ns = struct.Struct('<I')\nprint(s.size)\n", "Struct"),
            "bind_error": ("import struct\n\nerror = 1\nprint(struct.pack('<I', 1))\n", "binds the name error"),
            "bind_except": ("import struct\n\ntry:\n    pass\nexcept Exception as error:\n    pass\nprint(struct.pack('<I', 1))\n", "binds the name error"),
            "bind_helper": ("import struct\n\n_ail_struct_x = 1\nprint(struct.pack('<I', 1))\n", "binds a name starting with _ail_struct_"),
            "bind_helper_arg": ("import struct\n\ndef f(_ail_struct_pack):\n    return _ail_struct_pack\nprint(struct.pack('<I', 1))\n", "binds a name starting with _ail_struct_"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


class UnchangedPrograms(unittest.TestCase):
    PLAIN = [
        "# mentions struct only in a comment\nprint(1)\n",
        "s = 'struct'\nprint(s)\n",
        "structure = 1\nprint(structure)\n",
        "import sys\n\nprint(sys.version_info[0])\n",
    ]

    def test_other_programs_keep_their_text(self):
        import structlib
        for text in self.PLAIN:
            with self.subTest(text[:30]):
                notes = []
                self.assertIs(structlib.rewrite_text(text, notes), text)
                self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
