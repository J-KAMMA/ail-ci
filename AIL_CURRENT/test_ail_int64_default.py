"""The default int semantics: 64-bit ints that stop loudly, and the opt-in exact mode (owner decision 2026-10-31).

A Python-syntax program used to get CPython's arbitrary precision ints: the gate (bigcap.py / biggate.py) sent every program or
function that could leave int64 to the exact general path, 20-50x slower. Now the default is int64:

  * an operation that leaves int64 stops the program (exit 1) with an OverflowError-style message that names the operation, on the
    typed path and on the general path alike (AIL_UNIFIED_FORCE=1 forces the general path), never a wrapped or different number;
  * a value that fits prints exactly what CPython prints;
  * a program whose source needs a big int statically (an int literal outside int64, a constant expression such as `1 << 200`)
    is refused at compile time, naming the line and the flag;
  * `compile --exact-int` / AIL_EXACT_INT=1 restores the exact behaviour (docs/design/BIGINT.md), and the old exact tests set it.

I1  every operation at the +-2**63 boundaries, default / forced general / exact, against CPython
I2  compile-time refusal of a static big int; the in-range spellings still build
I3  the flag and the environment variable give exact results
I4  the default build leaves the general path for int-width reasons
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAXV = (1 << 63) - 1
MINV = -(1 << 63)
SUFFIX = ' (ints are 64-bit; --exact-int gives exact ints)'

OPS = r"""import sys
import math


def run(op, a, b, sa, f):
    if op == 0:
        print(a + b)
    elif op == 1:
        print(a - b)
    elif op == 2:
        print(a * b)
    elif op == 3:
        print(-a)
    elif op == 4:
        print(abs(a))
    elif op == 5:
        print(a // b)
    elif op == 6:
        print(a % b)
    elif op == 8:
        print(a << b)
    elif op == 9:
        print(a >> b)
    elif op == 11:
        print(int(sa))
    elif op == 12:
        print(sum([a, b]))
    elif op == 13:
        print(sum(range(a, b)))
    elif op == 14:
        print(math.factorial(b))
    elif op == 15:
        print(math.comb(a, b))
    elif op == 16:
        print(math.perm(a, b))
    elif op == 17:
        print(math.prod([a, b]))
    elif op == 18:
        print(math.lcm(a, b))
    elif op == 19:
        print(int(f))
    elif op == 20:
        print(round(f))
    elif op == 21:
        xs = [a, b]
        xs[0] += xs[1]
        print(xs[0])
    elif op == 22:
        d = {1: a}
        d[1] *= b
        print(d[1])
    elif op == 23:
        t = a
        t += b
        t += b
        print(t)
    elif op == 24:
        print(int(sa, 16))
    elif op == 25:
        print(int.from_bytes(bytes([a & 255, 1, 2, 3, 4, 5, 6, 7, b & 255]), "little"))
    elif op == 26:
        print(a * a * a)
    elif op == 27:
        print(math.floor(f) + 0)
    elif op == 30:
        print(math.isqrt(a if a > 0 else 0))
    elif op == 31:
        print(math.gcd(a, b))
    elif op == 32:
        print(a | b, a & b, a ^ b, ~a)
    elif op == 33:
        print(int(float(a)))
    elif op == 34:
        print(len(str(a)) + a)
    elif op == 35:
        print(-a // b)
    elif op == 36:
        print(sum([a, b, a]))
    elif op == 37:
        s = 0
        for v in [a, b, a, b]:
            s += v
        print(s)
    elif op == 38:
        print(math.ceil(f) + 0)
    elif op == 39:
        print(math.trunc(f) + 0)


def main():
    t = sys.stdin.read().split("\n")
    op = int(t[0])
    p = t[1].split()
    run(op, int(p[0]), int(p[1]), p[2], float(p[3]))


main()"""

OPSG = r"""import sys
import math


def run(op, a, b, sa, f):
    if op == 7:
        print(a ** b)
    elif op == 10:
        print(pow(a, b))
    elif op == 28:
        q, r = divmod(a, b)
        print(q)
    elif op == 29:
        print(pow(a, b, 1000003))


def main():
    t = sys.stdin.read().split("\n")
    op = int(t[0])
    p = t[1].split()
    run(op, int(p[0]), int(p[1]), p[2], float(p[3]))


main()"""

# the operation that must be named when the result leaves int64 (None: any OverflowError text is accepted)
NAMES = {0: '+', 1: '-', 2: '*', 3: 'unary - or abs()', 4: 'unary - or abs()', 5: '//', 7: '**', 8: '<<', 10: '**', 11: 'int()',
         12: '+', 14: '*', 15: '*', 16: '*', 17: '*', 18: ('*', 'unary - or abs()'), 19: 'int(float)', 20: 'round()', 21: '+', 22: '*', 23: '+',
         24: 'int()', 26: '*', 36: '+', 37: '+'}
GENERAL_ONLY = (7, 10, 28, 29)
PAIRS = [(0, 0), (1, 2), (MAXV, 1), (MAXV, 2), (MINV, 1), (MINV, -1), (MAXV, MAXV), (MINV, MINV), (3037000500, 3037000500),
         (3037000499, 3037000499), (2, 62), (2, 63), (2, 64), (-2, 63), (1, 62), (1, 63), (1, 64), (MAXV, 0), (5, 3), (-7, 2),
         (7, -2), (20, 20), (21, 21), (25, 12), (1 << 62, 2), (1 << 62, 1), (-(1 << 62), 2), (1 << 32, 1 << 31), (10, 18),
         (10, 19), (3, 39), (3, 40), (MAXV - 1, 2), (MINV + 1, -1)]
FLOATS = [1e18, 9.3e18, -9.3e18, 9.223372036854775e18, 1e19, 0.5, 2.5, -2.5, 1e300]


def oracle(op, a, b, sa, f):
    """What CPython prints (OPS and OPSG share one `run`), or None when it raises or the case is too big to compute."""
    if op == 13 and b - a > 10 ** 6:
        return None
    if op == 14 and not 0 <= b <= 200:
        return None
    if op in (15, 16) and not (0 <= a <= 2000 and 0 <= b <= 2000):
        return None
    if op in (7, 8, 10) and (b > 5000 or (op == 8 and b < 0)):
        return None
    ns = {}
    exec((OPSG if op in GENERAL_ONLY else OPS).rsplit('\nmain()', 1)[0], ns)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            ns['run'](op, a, b, sa, f)
    except Exception:
        return None
    return out.getvalue()


def fits(text):
    import re
    return all(MINV <= int(m) <= MAXV for m in re.findall(r'-?\d+', text))


def env_for(mode):
    env = dict(os.environ)
    for key in ('AIL_UNIFIED_FORCE', 'AIL_EXACT_INT', 'AIL_BIGINT', 'AIL_NO_GENERAL', 'AIL_UNIFIED', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    if mode == 'force':
        env['AIL_UNIFIED_FORCE'] = '1'
    if mode == 'exact':
        env['AIL_EXACT_INT'] = '1'
    env['AIL_NO_CACHE'] = '1'
    return env


def build(directory, text, name, mode='default', extra_args=()):
    source = Path(directory, name + '.py')
    exe = Path(directory, name + '_' + mode)
    source.write_text(text, encoding='utf-8')
    made = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax', 'python',
                           '-o', exe.name, *extra_args], cwd=directory, capture_output=True, text=True, timeout=900,
                          env=env_for(mode))
    return made, exe


def run(exe, text):
    r = subprocess.run([str(exe)], input=text, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def sample(op, a, b):
    sa = str(a)
    if op == 24:
        sa = format(a, 'x') if a >= 0 else '-' + format(-a, 'x')
    if op == 11 and (a + b) % 3 == 0:
        sa = str(a * 10 ** (1 + abs(b) % 3))        # beyond int64 for the larger values
    return sa, FLOATS[(a + b + op) % len(FLOATS)]


class Boundaries(unittest.TestCase):
    """I1"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.exe = {}
        for mode in ('default', 'force', 'exact'):
            typed, cls.exe[mode, 'ops'] = build(cls.tmp.name, OPS, 'ops', mode)
            general, cls.exe[mode, 'opsg'] = build(cls.tmp.name, OPSG, 'opsg', mode)
            for what, made in (('ops', typed), ('opsg', general)):
                if made.returncode:
                    raise AssertionError('%s %s did not build: %s' % (mode, what, made.stderr[-1500:]))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def cases(self):
        for op in range(40):
            for a, b in PAIRS:
                sa, f = sample(op, a, b)
                if op == 25:
                    sa = 'k%d' % a
                want = oracle(op, a, b, sa, f)
                if want is None:
                    continue
                yield op, a, b, sa, f, want

    def test_every_operation_at_the_int64_boundaries(self):
        checked = {'fits': 0, 'beyond': 0}
        stops = {}
        for op, a, b, sa, f, want in self.cases():
            kind = 'opsg' if op in GENERAL_ONLY else 'ops'
            data = '%d\n%d %d %s %r\n' % (op, a, b, sa, f)
            label = (op, a, b, sa, f)
            got = {mode: run(self.exe[mode, kind], data) for mode in ('default', 'force', 'exact')}
            self.assertEqual(got['exact'][:2], (0, want), ('exact', label))
            if fits(want):
                checked['fits'] += 1
                # an intermediate may leave int64 while the result fits (`-a // b` at INT64_MIN): then the stop is allowed
                for mode in ('default', 'force'):
                    code, out, err = got[mode]
                    if code == 0:
                        self.assertEqual(out, want, (mode, label))
                    else:
                        self.assertEqual((code, out), (1, ''), (mode, label))
                        self.assertTrue(err.startswith('OverflowError: integer overflow in '), (mode, label, err))
                        stops.setdefault('intermediate', []).append(label)
            else:
                checked['beyond'] += 1
                for mode in ('default', 'force'):
                    code, out, err = got[mode]
                    self.assertEqual((code, out), (1, ''), (mode, label, err))
                    if op == 20 and mode == 'force':
                        # (the general path's wide round() raises the ordinary OverflowError of integ's pre429, text unchanged)
                        self.assertEqual(err, 'OverflowError: integer overflow\n', label)
                        continue
                    self.assertTrue(err.startswith('OverflowError: integer overflow in '), (mode, label, err))
                    self.assertTrue(err.endswith(SUFFIX + '\n'), (mode, label, err))
                    if op in NAMES:
                        names = NAMES[op] if isinstance(NAMES[op], tuple) else (NAMES[op],)
                        self.assertIn(err, ['OverflowError: integer overflow in %s%s\n' % (n, SUFFIX) for n in names], (mode, label))
                # both paths agree on the message
                if op != 20:
                    self.assertEqual(got['default'][2], got['force'][2], label)
        self.assertGreater(checked['beyond'], 100)
        self.assertGreater(checked['fits'], 400)
        # the only results that fit but stop are an intermediate beyond int64 (-INT64_MIN), gcd/ceil at INT64_MIN
        for label in stops.get('intermediate', ()):
            self.assertIn(label[0], (31, 35, 38), label)


class Refusals(unittest.TestCase):
    """I2"""
    HEAD = 'import sys\n\n\ndef main():\n    k = int(sys.stdin.read().split()[0])\n'

    def build(self, body, mode='default', extra_args=()):
        with tempfile.TemporaryDirectory() as tmp:
            made, exe = build(tmp, self.HEAD + body + '\n\nmain()\n', 'p', mode, extra_args)
            if made.returncode:
                return made, None
            return made, run(exe, '5\n')

    def test_static_big_int_is_refused_with_line_and_flag(self):
        for body, line in (('    print(k + 9223372036854775808)', 6), ('    print(k + (1 << 200))', 6),
                           ('    print(k + 2 ** 64)', 6), ('    print(k - 9223372036854775809)', 6),
                           ('    x = 10 ** 30\n    print(k + x)', 6), ('    print(k * 18446744073709551616)', 6),
                           ('    import math\n    print(k + math.factorial(25))', 7),
                           ('    import math\n    print(k + math.comb(100, 50))', 7),
                           ('    print(k + int("123456789012345678901234567890"))', 6)):
            with self.subTest(body=body):
                made, ran = self.build(body)
                self.assertNotEqual(made.returncode, 0, made.stdout)
                self.assertIn('p.py:%d:' % line, made.stderr)
                self.assertIn('--exact-int', made.stderr)
                self.assertIn('AIL_EXACT_INT=1', made.stderr)

    def test_in_range_spellings_still_build(self):
        made, ran = self.build('    print(k + (-9223372036854775808) + (2 ** 63 - 1) + (1 << 62) + ((1 << 64) - (1 << 64)))')
        self.assertEqual(made.returncode, 0, made.stderr)
        self.assertEqual(ran[:2], (0, '%d\n' % (5 - (1 << 63) + (1 << 63) - 1 + (1 << 62))))
        self.assertNotIn('general path', made.stderr)

    def test_the_text_of_a_big_number_is_a_run_time_stop(self):
        made, ran = self.build('    print(int(str(k) + "123456789012345678901234567890"))')
        self.assertEqual(made.returncode, 0, made.stderr)
        self.assertEqual(ran[:2], (1, ''))
        self.assertEqual(ran[2], 'OverflowError: integer overflow in int()%s\n' % SUFFIX)


class OptIn(unittest.TestCase):
    """I3"""
    BIG = ('import sys\n\n\ndef main():\n    k = int(sys.stdin.read().split()[0])\n    print(k + 9223372036854775808, (1 << 100) + k,\n'
           '          9223372036854775807 * k, 2 ** 70)\n\n\nmain()\n')
    WANT = '%d %d %d %d\n' % (5 + (1 << 63), (1 << 100) + 5, MAXV * 5, 2 ** 70)

    def test_flag_and_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            made, exe = build(tmp, self.BIG, 'big', 'default', ('--exact-int',))
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertEqual(run(exe, '5\n'), (0, self.WANT, ''))
            made, exe = build(tmp, self.BIG, 'big', 'exact')
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertEqual(run(exe, '5\n'), (0, self.WANT, ''))
            made, exe = build(tmp, self.BIG, 'big', 'default')
            self.assertNotEqual(made.returncode, 0)


class LeavesTheGeneralPath(unittest.TestCase):
    """I4"""
    PROGRAM = '''import math
import sys


def digest(text):
    h = 0
    for i in range(len(text)):
        h = (h * 31 + ord(text[i])) % 1000000007
    return h


def main():
    words = sys.stdin.read().split()
    acc = 0
    total = 0
    for w in words:
        acc += int(w) << 3
        total += int(w)
    print(digest("".join(words)), acc, math.factorial(len(words)), total ** 2)


main()
'''

    def test_no_int_width_reason_for_the_general_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            made, exe = build(tmp, self.PROGRAM, 'q')
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertNotIn('general path', made.stderr)
            self.assertEqual(run(exe, '1 2 3\n')[:2], (0, '%d %d %d %d\n' % (
                ((((0 * 31 + 49) * 31 + 50) * 31 + 51) % 1000000007), (1 + 2 + 3) << 3, 6, 36)))
            self.assertEqual(os.path.getsize(exe) < 60000, True, os.path.getsize(exe))
            exact_made, exact_exe = build(tmp, self.PROGRAM, 'q', 'exact')
            self.assertEqual(exact_made.returncode, 0, exact_made.stderr)


class DecimalLibrary(unittest.TestCase):
    """Decimal/Fraction compute with exact ints internally in the default int64 mode; an int they hand back to the
    program follows the program's mode (int(d) beyond int64 stops loudly)."""

    PROGRAM = '''from decimal import Decimal, getcontext
from fractions import Fraction

print(Decimal(1) / Decimal(3))
print(Decimal("2").sqrt())
print(Decimal("10.50") * Decimal("3"))
print(Decimal(2) ** 100)
getcontext().prec = 50
print(Decimal(1) / Decimal(3))
print(Decimal("1e30") + 1)
print(Fraction(1, 3) + Fraction(1, 6))
print(Fraction(2, 1) ** 100)
'''
    WANT = ('0.3333333333333333333333333333\n'
            '1.414213562373095048801688724\n'
            '31.50\n'
            '1.267650600228229401496703205E+30\n'
            '0.33333333333333333333333333333333333333333333333333\n'
            '1000000000000000000000000000001\n'
            '1/2\n'
            '1267650600228229401496703205376\n')

    def test_library_internals_are_exact_in_both_modes(self):
        for mode in ('default', 'force', 'exact'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                made, exe = build(tmp, self.PROGRAM, 'dec', mode)
                self.assertEqual(made.returncode, 0, made.stderr)
                self.assertEqual(run(exe, ''), (0, self.WANT, ''))

    def test_visible_int_beyond_int64_stops(self):
        snippets = (
            ('int(Decimal(2) ** 100)', 'from decimal import Decimal\n'),
            ('int(Fraction(2) ** 100)', 'from fractions import Fraction\n'),
            ('(Decimal(2) ** 100).as_integer_ratio()', 'from decimal import Decimal\n'),
            ('(Fraction(2) ** 100).as_integer_ratio()', 'from fractions import Fraction\n'),
            ('(Fraction(2) ** 100).numerator', 'from fractions import Fraction\n'),
            ('(Fraction(1, 2) ** 200).denominator', 'from fractions import Fraction\n'),
            ('round(Decimal(2) ** 100)', 'from decimal import Decimal\n'),
            ('(Decimal(2) ** 100).__trunc__()', 'from decimal import Decimal\n'),
            ('round(Fraction(2) ** 100)', 'from fractions import Fraction\n'),
            ('(Fraction(2) ** 100) // 1', 'from fractions import Fraction\n'),
            ('math.floor(Decimal(2) ** 100)', 'import math\nfrom decimal import Decimal\n'),
            ('math.ceil(Decimal(2) ** 100)', 'import math\nfrom decimal import Decimal\n'),
            ('hash(Fraction(2) ** 100)', 'from fractions import Fraction\n'),
        )
        for expr, setup in snippets:
            with self.subTest(expr=expr), tempfile.TemporaryDirectory() as tmp:
                made, exe = build(tmp, setup + 'print(%s)\n' % expr, 'deci')
                self.assertEqual(made.returncode, 0, made.stderr)
                code, out, err = run(exe, '')
                self.assertEqual((code, out), (1, ''))
                self.assertEqual(err, 'OverflowError: integer overflow in int()%s\n' % SUFFIX)

    def test_read_only_property_assignment_stops(self):
        text = ('from fractions import Fraction\n'
                'f = Fraction(1, 2)\n'
                'f.numerator = 3\n')
        with tempfile.TemporaryDirectory() as tmp:
            made, exe = build(tmp, text, 'roprop')
            self.assertEqual(made.returncode, 0, made.stderr)
            code, out, err = run(exe, '')
            self.assertEqual((code, out), (1, ''))
            self.assertIn("AttributeError: property 'numerator' of 'Fraction' object has no setter", err)

    def test_exact_mode_hands_back_exact_ints(self):
        text = ('from decimal import Decimal\n'
                'from fractions import Fraction\n'
                'print((Decimal(2) ** 100).as_integer_ratio())\n'
                'print((Fraction(2) ** 100).numerator)\n'
                'print((Fraction(1, 2) ** 200).denominator)\n')
        want = ('(1267650600228229401496703205000, 1)\n'
                '1267650600228229401496703205376\n'
                '1606938044258990275541962092341162602522202993782792835301376\n')
        with tempfile.TemporaryDirectory() as tmp:
            made, exe = build(tmp, text, 'dece', 'exact')
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertEqual(run(exe, ''), (0, want, ''))


if __name__ == '__main__':
    unittest.main()