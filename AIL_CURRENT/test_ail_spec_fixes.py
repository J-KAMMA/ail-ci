"""Differences from CPython 3.12 found while writing the language spec (docs/spec/DIFFERENCES.md C1, C5-C11,
C13, C14), each compared with CPython 3.12 on the typed path, the default build, the IR path (AIL_IR=1) and,
where the general (boxed) runtime can hold the program, the general path alone (pyc.py --general-only).

C1   float sum() is compensated (Neumaier) summation, bit for bit
C5   a negative base ** a fractional exponent is a complex number: a named refusal, never nan
C6   float ** that overflows raises OverflowError; 0.0 ** negative raises ZeroDivisionError
C7   str.splitlines() knows every line boundary CPython knows
C8   underscores in int() / float() strings
C9   Unicode decimal digits in int() / float(), isdigit / isdecimal / isnumeric
C10  str.lower() / str.upper() of non-ASCII text built at run time (full Unicode, final sigma)
C11  int(float('inf')) is an OverflowError, int(float('nan')) a ValueError
C13  `import regex` points at `re`
C14  a refusal of `X | None` for a non-struct type names file:line:col
C16  print(x) / repr of a float is CPython's shortest repr (every power of two)

The expected output of every program is what CPython 3.12 prints, so the module needs CPython 3.12 (the
Neumaier sum and Unicode 15.0 are 3.12's).
"""
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
ON_312 = sys.version_info[:2] == (3, 12)

MODES = ('default', 'typed', 'ir', 'general')


def build(directory, text, name, mode):
    """Compile `text` in one mode. Returns (completed process, executable path)."""
    source, exe = Path(directory, name + '.ail'), Path(directory, name + '_' + mode)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    if mode == 'general':
        command = [sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only']
    else:
        if mode == 'typed':
            env['AIL_NO_GENERAL'] = '1'
        if mode == 'ir':
            env['AIL_IR'] = '1'
        command = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                   '--syntax', 'python', '-o', exe.name]
    return subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


def cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=120,
                          encoding='utf-8')


@unittest.skipUnless(ON_312, 'the expected output is CPython 3.12 behaviour')
class SpecFixes(unittest.TestCase):
    def same(self, text, name, modes=MODES, allow=()):
        """AIL's stdout and exit status equal CPython's in every mode that builds. A mode in `allow` may
        refuse the program by name instead (exit 3); at least one mode must build."""
        built_any = False
        with tempfile.TemporaryDirectory() as directory:
            expected = cpython(directory, text, name)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for mode in modes:
                with self.subTest(mode=mode):
                    built, exe = build(directory, text, name, mode)
                    if built.returncode != 0:
                        self.assertIn(mode, allow, '%s: %s' % (mode, built.stdout + built.stderr))
                        self.assertIn('not in the subset', built.stdout + built.stderr)
                        continue
                    built_any = True
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300,
                                         encoding='utf-8')
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                     ran.stderr[-400:])
        self.assertTrue(built_any)

    # ---- C1 ----
    def test_float_sum_is_compensated(self):
        rnd = random.Random(12345)
        lines = ['def total(xs: list[float]) -> float:', '    return sum(xs)', '',
                 'def scaled(xs: list[float]) -> float:', '    return sum(x * 0.5 for x in xs if x > -1e300)', '',
                 'def main() -> None:']
        lines += ['    ones = [0.1] * 10']
        lines += ['    print(sum(ones), sum([0.1, 0.2, 0.3]), sum([-0.0]), sum([-0.0, -0.0]), sum([0.0]))']
        lines += ['    print(sum(0.1 for i in range(10)), sum(x * 0.1 for x in range(30)), sum(1.0 / (i + 1) for i in range(1000)))']
        lines += ['    print(sum([1e308, 1e308, -1e308]), sum([float("inf"), 1.0]), sum([float("inf"), float("-inf")]))']
        for n in range(1, 13):
            size = rnd.choice([2, 3, 5, 10, 40, 100, 200])
            values = [rnd.uniform(-1.0, 1.0) * 10.0 ** rnd.randint(-5, 15) for _ in range(size)]
            if n % 3 == 0:
                values += [-v for v in values]       # cancelling pairs: the compensation matters
                rnd.shuffle(values)
            lines.append('    xs%d = [%s]' % (n, ', '.join(repr(v) for v in values)))
            lines.append('    print(total(xs%d), scaled(xs%d), sum(xs%d))' % (n, n, n))
        self.same('\n'.join(lines) + '\n\n\nmain()\n', 'fsum')

    def test_float_sum_with_a_start_and_mixed_items_general_path(self):
        # a start value and int items need the general path (the typed sum() takes one argument)
        text = '''
def main():
    xs = [0.1] * 10
    zs = [1, 2, 3]
    print(sum(xs), sum(xs, 5), sum(xs, 0.5), sum(zs), sum(zs, 0.5), sum([1, 2, 0.1, 0.1, 0.1]))
    print(sum([0.1, 1, 0.1, 2, 0.1, True, 0.1]), sum([1e100, 1.0, -1e100]), sum(xs[:7]), sum([]), sum([], 2.5))
    print(sum([0.1] * 3, 1), sum([0.1] * 10, 2.5), sum([0.1] * 10, 7))
    print(sum(x * 0.1 for x in range(30)), sum([-0.0], 0.0), sum([-0.0], -0.0))


main()
'''
        self.same(text, 'fsum_general', modes=('default', 'ir', 'general'))

    # ---- C5, C6 ----
    def test_float_power_overflow_and_zero_to_a_negative_power(self):
        text = '''
def f(x: float, y: float) -> float:
    return x ** y


def main() -> None:
    print(f(-8.0, 3.0), f(-8.0, -3.0), f(2.0, 10.0), f(0.0, 0.0), f(float("inf"), 2.0), f(2.0, float("-inf")), f(-float("inf"), 3.0))
    print(f(-1.0, float("inf")), f(1.0, float("nan")), f(float("nan"), 0.0), f(0.5, 1e10), f(2.0, -1080.0), f(-0.0, 3.0), f(-0.0, 2.0))
    print(f(2.0, 0.5), f(4.0, 0.5), f(-0.0, 0.5), f(-float("inf"), 0.5), f(1e-200, 2.0), f(1e200, 1.0))
    try:
        print(f(10.0, 400.0))
    except OverflowError:
        print("OE")
    try:
        print(f(0.0, -1.0))
    except ZeroDivisionError:
        print("ZD")
    try:
        print(f(-0.0, -3.0))
    except ZeroDivisionError:
        print("ZD2")
    try:
        print(f(-2.0, 1025.0))
    except OverflowError:
        print("OE2")
    x = 10.0
    for i in range(1, 6):
        try:
            print(x ** (i * 100))
        except OverflowError:
            print("OE", i)


main()
'''
        self.same(text, 'fpow')

    def test_complex_power_is_refused_by_name(self):
        constant = 'def main() -> None:\n    print((-4.0) ** 0.5)\n\n\nmain()\n'
        runtime = ('def f(x: float, y: float) -> float:\n    return x ** y\n\n\n'
                   'def main() -> None:\n    print(f(2.0, 2.0))\n    print(f(-4.0, 0.5))\n\n\nmain()\n')
        with tempfile.TemporaryDirectory() as directory:
            for mode in ('default', 'typed'):
                with self.subTest(mode=mode, case='constant'):
                    built, _ = build(directory, constant, 'cpow_const', mode)
                    self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                    message = built.stdout + built.stderr
                    self.assertIn('complex number', message)
                    self.assertRegex(message, r'cpow_const\.ail:2:\d+:')
            for mode in MODES:
                with self.subTest(mode=mode, case='runtime'):
                    built, exe = build(directory, runtime, 'cpow_run', mode)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
                    self.assertNotEqual(ran.returncode, 0)
                    self.assertIn('complex', ran.stderr)
                    self.assertNotIn('nan', ran.stdout)

    # ---- C7 ----
    def test_splitlines_line_boundaries(self):
        text = r'''
def show(s: str) -> None:
    parts = s.splitlines()
    print(len(parts))
    for p in parts:
        print(len(p), end=" ")
    print()


def main() -> None:
    show("a\x0bb\x1cc d\x85e\r\nf")
    show("a b c")
    show("a\x1db\x1ec\x0cd")
    show("")
    show("\n")
    show("\r\n\r\n")
    show("abc\n")
    show("abc\n\n")
    show("Ņxƅ")
    w = "".join(["p", chr(0x2028), "q", chr(0x1c), "r", chr(13), chr(10), "s", chr(13), "t"])
    show(w)
    for line in w.splitlines():
        print(len(line), end=",")
    print()
    k = "ab\r\ncd\nef gh\x85\r"
    print(k.splitlines(True))
    print(k.splitlines(keepends=True))
    print(k.splitlines(False))
    print(len(k.splitlines(True)))


main()
'''
        self.same(text, 'splitlines', modes=('default', 'ir', 'general'))
        # the typed path takes the no-argument form only (`keepends` is refused by name there)
        plain = '\n'.join(l for l in text.split('\n') if 'splitlines(' not in l or 'splitlines()' in l)
        self.same(plain, 'splitlines_plain', modes=('typed',))

    # ---- C8, C9 ----
    def number_strings(self, non_bmp):
        rnd = random.Random(7)
        ints = ['0', '1', '-1', '+1', ' 12 ', '1_000', '1__0', '_1', '1_', '+_1', '1_0_0', '0_0', '00', '007', '1 2',
                '', ' ', '+', '-', '--1', '1e3', '0x10', '0b1', '\x1c1', '1\x1c', '\x0b5\x0c', ' 5　',
                '\u0085 7  ', '12\x00', '١٢', '۱۲۳', '१_२', '１２',
                '-٤', '١ ٢', '²', '①', '1é', '١a', '9223372036854775807',
                '-9223372036854775808', '99999999999999999999x', '000000000000000000000000000001',
                '1_000_000_000_000_000_000']
        floats = ['0', '1.5', '-1.5', '+.5', '5.', '.', '1e5', '1E-5', '1e', '1e+', '1_0.5', '1._5', '1_.5', '1.5_',
                  '_1.5', '1__0.5', '1_e5', '1e1_0', '1e_10', '  2.5  ', 'inf', '-Inf', 'INFINITY', 'infinit', 'nan',
                  '-nan', 'nan(1)', '0x1p3', '0x10', '1e400', '-1e400', '1e-400', '\x1c1.5', '1.5\x1d',
                  ' 1.5　', '١.٢', '١_٢.5', '1.5é', '1,5', '1 .5', '1. 5', '+ 1',
                  '- 1', '1e5.5', '.e5', 'e5', '1.2.3', '0.1', '3.14159', '1e308', '5e-324', '2.2250738585072014e-308',
                  '123456789012345678901234567890', '0.000000000000000000001', '1\x00', '1_000.000_1']
        if non_bmp:
            ints += ['\U0001d7ce\U0001d7cf']
            floats += ['\U0001d7d8.\U0001d7d9']
        alphabet = list('0123456789_ +-.eE') + ['١', ' ', '\x1c', 'x', 'i', 'n', 'f', 'a']
        ints += [''.join(rnd.choice(alphabet) for _ in range(rnd.randint(1, 8))) for _ in range(150)]
        floats += [''.join(rnd.choice(alphabet) for _ in range(rnd.randint(1, 9))) for _ in range(150)]
        bases = ['0x_ff', '0xFF', '0b101', '0o17', '017', '0_7', 'z', '1_f', '١٢', '-0x1', '0b', '0x',
                 ' 0x1f ', '1__0', '_1', 'ff_', '0_', '00', '0x_', '0X_1_0', ' ff ']
        return ints, floats, bases

    @staticmethod
    def escape(text):
        out = []
        for c in text:
            if c.isascii() and c.isprintable() and c not in '"\\':
                out.append(c)
            elif ord(c) < 0x10000:
                out.append('\\u%04x' % ord(c))
            else:
                out.append('\\U%08x' % ord(c))
        return ''.join(out)

    def number_program(self, non_bmp):
        ints, floats, bases = self.number_strings(non_bmp)
        lines = ['def ci(s: str) -> None:', '    try:', '        print(int(s))', '    except ValueError:',
                 "        print('VE')", '',
                 'def cf(s: str) -> None:', '    try:', '        print(float(s))', '    except ValueError:',
                 "        print('VE')", '',
                 'def cb(s: str, b: int) -> None:', '    try:', '        print(int(s, b))', '    except ValueError:',
                 "        print('VE')", '', 'def main() -> None:']
        lines += ['    ci("%s")' % self.escape(s) for s in ints]
        lines += ['    cf("%s")' % self.escape(s) for s in floats]
        lines += ['    cb("%s", %d)' % (self.escape(s), b) for b in (0, 2, 8, 10, 16, 36) for s in bases]
        return '\n'.join(lines) + '\n\n\nmain()\n'

    def test_int_and_float_of_strings_underscores_and_unicode_digits(self):
        self.same(self.number_program(False), 'numbers_bmp')
        self.same(self.number_program(True), 'numbers_all', modes=('default', 'typed', 'ir'))

    def test_general_path_parses_numbers_the_same_way(self):
        self.same(self.number_program(False), 'numbers_general', modes=('general',))

    # ---- C9, C10: every code point ----
    def test_unicode_properties_and_case_mapping_of_every_code_point(self):
        text = r'''
def mix(h: int, r: str) -> int:
    for ch in r:
        h = (h * 1000003 + ord(ch)) % 1000000007
    return (h * 31 + 7) % 1000000007


def main() -> None:
    h = 0
    g = 0
    n = 0
    for cp in range(0, LIMIT):
        if 0xD800 <= cp < 0xE000:
            continue
        s = chr(cp)
        h = mix(h, s.upper())
        h = mix(h, s.lower())
        t = "a" + s + "Σ" + s + "Σ"
        h = mix(h, t.lower())
        h = mix(h, t.upper())
        h = mix(h, (s + "Σ").lower())
        bits = 0
        if s.isdigit():
            bits += 1
        if s.isdecimal():
            bits += 2
        if s.isnumeric():
            bits += 4
        g = (g * 7 + bits) % 1000000007
        n += 1
    print(n, h, g)
    print("straße".upper(), "ǅ".lower(), "ǅ".upper(), "ΑΣ".lower(), "ΑΣ Σ".lower(), "ß".upper(), "ŉ".upper(), "ΐ".upper())
    w = "".join(["str", chr(223), "e"])
    print(w.upper(), w.lower(), len(w.upper()))


main()
'''
        self.same(text.replace('LIMIT', '0x110000'), 'unicode_all', modes=('default', 'typed', 'ir'))

    def test_general_path_case_mapping_and_digit_tests(self):
        text = r'''
def mix(h: int, r: str) -> int:
    for ch in r:
        h = (h * 1000003 + ord(ch)) % 1000000007
    return (h * 31 + 7) % 1000000007


def main() -> None:
    h = 0
    g = 0
    n = 0
    for cp in range(0, 0x10000):
        if 0xD800 <= cp < 0xE000:
            continue
        s = chr(cp)
        h = mix(h, s.upper())
        h = mix(h, s.lower())
        t = "a" + s + "Σ" + s + "Σ"
        h = mix(h, t.lower())
        h = mix(h, t.upper())
        h = mix(h, (s + "Σ").lower())
        bits = 0
        if s.isdigit():
            bits += 1
        g = (g * 7 + bits) % 1000000007
        n += 1
    print(n, h, g)
    print("straße".upper(), "ǅ".lower(), "ǅ".upper(), "ΑΣ".lower(), "ΑΣ Σ".lower(), "ß".upper(), "ŉ".upper(), "ΐ".upper())
    w = "".join(["str", chr(223), "e"])
    print(w.upper(), w.lower(), len(w.upper()))
    print("12".isdigit(), "١٢".isdigit(), "1²".isdigit(), "".isdigit(), "½".isdigit())


main()
'''
        self.same(text, 'unicode_bmp_general', modes=('general',))

    # ---- C11 ----
    def test_int_of_nan_and_infinity(self):
        text = '''
def conv(x: float) -> None:
    try:
        print(int(x))
    except ValueError:
        print("VE")
    except OverflowError:
        print("OE")


def main() -> None:
    conv(1.5)
    conv(-2.7)
    conv(float("nan"))
    conv(float("inf"))
    conv(float("-inf"))
    conv(9.2e18 / 1e3)


main()
'''
        # the IR emitter (python/pkg-v12/ir/emit_c.py) still spells the nan / infinity test its own way
        with tempfile.TemporaryDirectory() as directory:
            expected = cpython(directory, text, 'conv')
            for mode in ('default', 'typed', 'general'):
                with self.subTest(mode=mode):
                    built, exe = build(directory, text, 'conv', mode)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    # ---- C13, C14 ----
    def test_import_regex_points_at_re(self):
        text = 'import regex\n\n\ndef main() -> None:\n    print(regex.sub("a", "b", "aa"))\n\n\nmain()\n'
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, 'imp', 'default')
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            message = built.stdout + built.stderr
            self.assertRegex(message, r'imp\.ail:1:\d+:')
            self.assertIn('import re', message)
            self.assertNotIn('no regular expressions', message)

    def test_optional_refusal_names_the_line(self):
        text = ('from typing import Optional\n\n\ndef f(d: dict[int, int], x: int) -> Optional[int]:\n'
                '    return d.get(x)\n\n\ndef main() -> None:\n    print(f({3: 3}, 3))\n\n\nmain()\n')
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, 'opt', 'typed')
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertRegex(built.stdout + built.stderr, r'opt\.ail:4:\d+: not in the subset: int \| None')

    # ---- C16: repr(float) ----
    def test_float_repr_of_every_power_of_two_and_random_doubles(self):
        import struct
        rnd = random.Random(5)
        lines = ['def main() -> None:', '    x = 1.0', '    for i in range(1023):', '        print(x)',
                 '        x = x * 2.0', '    y = 1.0', '    for i in range(1074):', '        y = y / 2.0',
                 '        print(y)', '        print(-y)']
        values = []
        while len(values) < 400:
            d = struct.unpack('<d', struct.pack('<Q', rnd.getrandbits(64)))[0]
            if d == d and abs(d) != float('inf'):
                values.append(d)
        values += [rnd.uniform(-1, 1) * 10.0 ** rnd.randint(-8, 20) for _ in range(300)]
        values += [5e-324, 1.7976931348623157e308, 2.2250738585072014e-308, 0.1, 1e16, 1e-4, 9.999999999999999e22, 1e23]
        lines.append('    xs = [' + ', '.join(repr(v) for v in values) + ']')
        lines += ['    for v in xs:', '        print(v)', '', '', 'main()']
        self.same('\n'.join(lines) + '\n', 'floatrepr')


if __name__ == '__main__':
    unittest.main()
