"""Library batch 10: `struct` over the integer format subset, each spelling compared with CPython 3.12.

Two layers, as the other library batches:

* prelude_struct.py is plain Python, so it runs under CPython next to the struct module: tens of thousands of
  generated formats and values, and every error path, must agree (bytes, tuple values, and the exception
  class name `error` / message).
* ordinary Python programs (below) are compiled with the Python syntax, once with AIL_IR=0 and once with
  AIL_IR=1, run, and must print the same bytes and exit with the same status as CPython.

The declared difference (DIFFERENCES.md C-series): int is 64-bit, so unpacking a 'Q' whose value is at or
above 2**63 (or a 'q' below -2**63) stops with "integer overflow" where CPython makes a big integer.

The format is a constant string in a supported program; the native byte order ('@' or no prefix), the float
codes f / d / e, the pascal-string code p, unknown codes, Struct, iter_unpack and every other attribute,
keyword arguments and wrong arities are refused at compile time by name (test_struct_refusals_are_named).
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

import prelude_struct as P

PREFIXES = ('<', '>', '=', '!')
CODES = ('x', 'c', 'b', 'B', 'h', 'H', 'i', 'I', 'l', 'L', 'q', 'Q', 's', '?')
WIDTH = {'b': 1, 'B': 1, 'h': 2, 'H': 2, 'i': 4, 'I': 4, 'l': 4, 'L': 4, 'q': 8, 'Q': 8}
SIGNED = ('b', 'h', 'i', 'l', 'q')


def parse_format(fmt):
    """[(code, count)] for a format whose characters are valid (prefix skipped)."""
    out = []
    i = 1
    while i < len(fmt):
        if fmt[i] in ' \t\n':
            i += 1
            continue
        digits = ''
        while i < len(fmt) and '0' <= fmt[i] <= '9':
            digits += fmt[i]
            i += 1
        if i >= len(fmt):
            break
        out.append((fmt[i], int(digits) if digits else 1))
        i += 1
    return out


def random_format(rng):
    parts = []
    for _ in range(rng.randint(0, 4)):
        code = rng.choice(CODES)
        count = rng.choice([1, 1, 1, 2, 3, 0])
        parts.append((str(count) if (count != 1 or rng.random() < 0.2) else '') + code)
    return rng.choice(PREFIXES) + ''.join(parts)


def values_for(fmt, rng):
    values = []
    for code, count in parse_format(fmt):
        if code == 'x':
            continue
        if code == 's':
            values.append(rng.choice([b'', b'a', b'ab', b'abc', b'x' * 5]))
            continue
        if code == 'c':
            for _ in range(count):
                values.append(bytes([rng.randrange(97, 123)]))
            continue
        if code == '?':
            for _ in range(count):
                values.append(rng.choice([True, False, 0, 1, b'x', '']))
            continue
        width = WIDTH[code]
        if code in SIGNED:
            low, high = -(1 << (8 * width - 1)), (1 << (8 * width - 1)) - 1
        else:
            low = 0
            high = (1 << (8 * width)) - 1
            if width == 8:
                high = (1 << 63) - 1          # the language's int is 64-bit signed
        for _ in range(count):
            values.append(rng.choice([low, high, 0, 1, -1 if code in SIGNED else 0,
                                      rng.randint(max(low, -2 ** 63), min(high, 2 ** 63 - 1))]))
    return values


def outcome(call):
    try:
        return ('ok', call())
    except Exception as exc:
        return ('exc', type(exc).__name__, str(exc))


GRID = [
    '<I', '>I', '=I', '!I', '<b', '>B', '<h', '>H', '<i', '>I', '<l', '>L', '<q', '>Q',
    '<2I', '>3h', '<4b', '>2?', '<4s', '>2s', '<3c', '<0s', '<x', '<2x', '<?',
    '<hI', '>I2h4s', '<bBhHiI', '=2q', '<16sHHIQQQIHHHHHH', '<IIQQQQQQ',
    '< 2I', '>I ', '<0x', '<00I', '<01h', '<0c', '<0?',
]


def grid_cases(rng):
    cases = []
    for fmt in GRID:
        values = values_for(fmt, rng)
        cases.append((fmt, values))
    for _ in range(24):
        fmt = random_format(rng)
        cases.append((fmt, values_for(fmt, rng)))
    return cases


def struct_program(cases):
    lines = [
        "import struct",
        "from struct import unpack as U",
        "from struct import error",
        "",
        "",
        "class Holder:",
        "    def __init__(self):",
        "        self.value = 70000",
        "        self.fmt = '>I'",
        "",
        "",
        "def pack_one(value):",
        "    return struct.pack('>I', value)",
        "",
        "",
        "def pack_pair(values):",
        "    return struct.pack('<2H', values[0], values[1])",
        "",
        "",
        "def show(label, fn):",
        "    try:",
        "        print(label, fn())",
        "    except struct.error as e:",
        "        print(label, type(e).__name__, str(e))",
        "",
        "",
        "def main() -> None:",
        "    nums = [40000, 50000, 65535]",
        "    h = Holder()",
        "    d = {'v': 123456}",
        "    print(list(pack_one(300000)))",
        "    print(list(pack_one(nums[0])))",
        "    print(list(pack_one(h.value)))",
        "    print(list(pack_one(d['v'])))",
        "    print(pack_pair(nums))",
        "    print(U('<2H', struct.pack('<2H', nums[1], nums[2])))",
        "    print(struct.calcsize('<16sHHIQQQIHHHHHH'), struct.calcsize('>'), struct.calcsize('=3x'))",
        "    print(struct.unpack_from('>I', b'abcdefgh', -8))",
        "    print(struct.unpack_from('>I', b'abcdefgh', -4))",
        "    print(struct.unpack_from('>I', b'abcdefgh', offset=2))",
        "    print(struct.unpack('<0s', b''), struct.unpack('<0x', b''))",
        "    print(struct.unpack('>2?', b'\\x00\\x01'))",
        "    print(struct.unpack('>2c', b'ab'))",
        "    print(struct.unpack('<3s', b'xyz'), struct.unpack('<3s', b'x\\x00\\x00'))",
        "    print(struct.pack('<3s', b'x'), struct.pack('<3s', b'wxyz'))",
        "    out = bytearray(b'......')",
        "    struct.pack_into('<h', out, 1, 30000)",
        "    struct.pack_into('>I', out, -4, d['v'])",
        "    print(list(out))",
        "    show('range_I', lambda: struct.pack('>I', -1))",
        "    show('range_h', lambda: struct.pack('>h', 40000))",
        "    show('range_Q', lambda: struct.pack('<Q', -1))",
        "    show('few', lambda: struct.pack('>I'))",
        "    show('many', lambda: struct.pack('>I', 1, 2))",
        "    show('short', lambda: struct.unpack('>Q', b'abc'))",
        "    show('long', lambda: struct.unpack('>I', b'abcdef'))",
        "    show('char', lambda: struct.pack('>c', b'ab'))",
        "    show('sarg', lambda: struct.pack('>s', 5))",
        "    show('pinto_small', lambda: struct.pack_into('>I', bytearray(2), 0, 1))",
        "    show('pinto_neg', lambda: struct.pack_into('>I', bytearray(2), -1, 1))",
        "    show('upf_short', lambda: struct.unpack_from('>I', b'abcd', 2))",
        "    show('upf_neg', lambda: struct.unpack_from('>I', b'abcd', -1))",
        "    show('upf_range', lambda: struct.unpack_from('>I', b'abcd', -5))",
        "    try:",
        "        struct.pack_into('>I', b'abcd', 0, 1)",
        "    except TypeError as e:",
        "        print('pinto_bytes', type(e).__name__, str(e))",
        "    try:",
        "        U('>I', 'abcd')",
        "    except TypeError as e:",
        "        print('buf_type', type(e).__name__, str(e))",
        "    try:",
        "        struct.unpack_from('>I', b'abcd', '0')",
        "    except TypeError as e:",
        "        print('off_type', type(e).__name__, str(e))",
    ]
    for index, (fmt, values) in enumerate(cases):
        args = ', '.join(repr(value) for value in values)
        lines.append("    print(list(struct.pack(%r, %s)))" % (fmt, args))
        lines.append("    packed%d = struct.pack(%r, %s)" % (index, fmt, args))
        lines.append("    print(struct.unpack(%r, packed%d))" % (fmt, index))
        lines.append("    print(struct.unpack_from(%r, b'abc' + packed%d + b'xy', 3))" % (fmt, index))
        lines.append("    into%d = bytearray(struct.calcsize(%r) + 2)" % (index, fmt))
        lines.append("    struct.pack_into(%r, into%d, 1, %s)" % (fmt, index, args))
        lines.append("    print(list(into%d))" % index)
    lines.append("")
    lines.append("")
    lines.append("main()")
    return "\n".join(lines) + "\n"


def compile_python(directory, text, name, ir):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    env = dict(os.environ, AIL_IR="1" if ir else "0")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=env)
    return built, source, exe


class PreludeStruct(unittest.TestCase):
    """prelude_struct.py (the code the compiler adds) against the struct module."""

    def test_grid_matches_struct(self):
        rng = random.Random(10)
        for fmt, values in grid_cases(rng):
            with self.subTest(fmt=fmt):
                self.assertEqual(P._ail_struct_calcsize(fmt), struct.calcsize(fmt))
                self.assertEqual(outcome(lambda: P._ail_struct_pack(fmt, tuple(values))),
                                 outcome(lambda: struct.pack(fmt, *values)))
                packed = struct.pack(fmt, *values)
                self.assertEqual(outcome(lambda: P._ail_struct_unpack(fmt, packed)),
                                 outcome(lambda: struct.unpack(fmt, packed)))
                data = b'abc' + packed + b'xy'
                self.assertEqual(outcome(lambda: P._ail_struct_unpack_from(fmt, data, 3)),
                                 outcome(lambda: struct.unpack_from(fmt, data, 3)))
                target = bytearray(struct.calcsize(fmt) + 2)
                want = bytearray(struct.calcsize(fmt) + 2)
                got = outcome(lambda: P._ail_struct_pack_into(fmt, target, 1, tuple(values)))
                ref = outcome(lambda: struct.pack_into(fmt, want, 1, *values))
                self.assertEqual(got, ref)
                self.assertEqual(bytes(target), bytes(want))

    def test_random_formats_match_struct(self):
        rng = random.Random(11)
        for _ in range(3000):
            fmt = random_format(rng)
            values = values_for(fmt, rng)
            with self.subTest(fmt=fmt):
                self.assertEqual(P._ail_struct_calcsize(fmt), struct.calcsize(fmt))
                self.assertEqual(outcome(lambda: P._ail_struct_pack(fmt, tuple(values))),
                                 outcome(lambda: struct.pack(fmt, *values)))
                packed = struct.pack(fmt, *values)
                self.assertEqual(outcome(lambda: P._ail_struct_unpack(fmt, packed)),
                                 outcome(lambda: struct.unpack(fmt, packed)))

    def test_offset_and_type_errors_match_struct(self):
        for length in (0, 1, 4, 8):
            data = b'0123456789'[:length]
            for offset in range(-length - 2, length + 2):
                for fmt in ('>I', '<0x', '<2s'):
                    self.assertEqual(outcome(lambda: P._ail_struct_unpack_from(fmt, data, offset)),
                                     outcome(lambda: struct.unpack_from(fmt, data, offset)), (fmt, data, offset))
                    target = bytearray(length)
                    want = bytearray(length)
                    got = outcome(lambda: P._ail_struct_pack_into(fmt, target, offset, pack_args(fmt)))
                    ref = outcome(lambda: struct.pack_into(fmt, want, offset, *pack_args(fmt)))
                    self.assertEqual(got, ref, (fmt, length, offset))
                    self.assertEqual(bytes(target), bytes(want), (fmt, length, offset))
        for value in (b'abcd', 'abcd', 5):
            self.assertEqual(outcome(lambda: P._ail_struct_unpack('>I', value)),
                             outcome(lambda: struct.unpack('>I', value)))
        for value in (b'abcd', 'abcd'):
            self.assertEqual(outcome(lambda: P._ail_struct_pack_into('>I', value, 0, (1,))),
                             outcome(lambda: struct.pack_into('>I', value, 0, 1)))
        for offset in (True, False, '0', 1.0):
            self.assertEqual(outcome(lambda: P._ail_struct_unpack_from('>I', b'abcdefgh', offset)),
                             outcome(lambda: struct.unpack_from('>I', b'abcdefgh', offset)))

    def test_pack_value_errors_match_struct(self):
        for fmt, values in (('>I', (-1,)), ('>I', (2 ** 32,)), ('>h', (40000,)), ('>H', (-1,)),
                            ('>b', (128,)), ('>B', (256,)), ('>q', (2 ** 63,)), ('<Q', (-1,)),
                            ('>I', ()), ('>I', (1, 2)), ('>2I', (1,)), ('>c', (5,)), ('>c', (b'ab',)),
                            ('>c', (bytearray(b'a'),)), ('>s', (None,)), ('>s', (5,)), ('>?', ('x',))):
            self.assertEqual(outcome(lambda: P._ail_struct_pack(fmt, values)),
                             outcome(lambda: struct.pack(fmt, *values)), (fmt, values))


def pack_args(fmt):
    """Values for a format used only in pack_into error tests; conversions may still fail identically."""
    if fmt == '>I':
        return (1,)
    if fmt == '<2s':
        return (b'ab',)
    return ()


class CompiledPrograms(unittest.TestCase):
    def test_programs_match_cpython(self):
        text = struct_program(grid_cases(random.Random(12)))
        expected = subprocess.run([sys.executable, "-X", "utf8", "-c", text], capture_output=True, timeout=300)
        self.assertEqual(expected.returncode, 0, expected.stderr[-800:])
        for ir in (False, True):
            with self.subTest(ir=ir), tempfile.TemporaryDirectory() as directory:
                built, source, exe = compile_python(directory, text, "struct_grid", ir)
                self.assertEqual(built.returncode, 0, "%s%s" % (built.stdout, built.stderr))
                ran = subprocess.run([str(exe)], capture_output=True, timeout=900)
                self.assertEqual(ran.returncode, expected.returncode, ran.stderr[-800:])
                if ran.stdout != expected.stdout:
                    got, want = ran.stdout.decode().splitlines(), expected.stdout.decode().splitlines()
                    for number, (x, y) in enumerate(zip(got, want)):
                        if x != y:
                            self.fail("AIL_IR=%s line %d:\n  compiled: %r\n  CPython:  %r"
                                      % (ir, number + 1, x, y))
                    self.fail("AIL_IR=%s: %d lines against %d" % (ir, len(got), len(want)))

    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused", False)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_are_named(self):
        head = "import struct\n\n\ndef main():\n"
        self.refused(head + "    print(struct.pack('<d', 1.5))\n\n\nmain()\n", "float format code 'd'")
        self.refused(head + "    fmt = '>I'\n    print(struct.pack(fmt, 1))\n\n\nmain()\n",
                     "the format must be a constant string")
        self.refused(head + "    print(struct.pack('I', 1))\n\n\nmain()\n", "native byte order")
        self.refused(head + "    print(struct.Struct('>I').size)\n\n\nmain()\n", "struct.Struct is not built")
        self.refused(head + "    print(struct.pack('<p', b'a'))\n\n\nmain()\n",
                     "'p' is not a format code this compiler builds")
        self.refused("from struct import iter_unpack\n\n\ndef main():\n    print(iter_unpack('>I', b'abcd'))\n\n\nmain()\n",
                     "struct.iter_unpack is not built")


if __name__ == "__main__":
    unittest.main()
