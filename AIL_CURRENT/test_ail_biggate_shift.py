"""The size gate of bigcap for shifts and int.from_bytes (docs/design/BIGINT.md section 5, "Provable shifts").

A function is marked big-int capable (no typed path, exact general path) by `<<` with an amount that is not a constant. The
gate now lets such a shift through to the typed path only when it can prove, from the expression alone, that the amount is
within [0, 4096] and that the operand's bit length plus the amount is at most 62: a shift by a name that is stored once
(`SH = 22`) or counted up in a `for .. in range(constants)` loop (`shift += 7`), of a masked value (`b & 0x7F`). Anything
else stays marked. `int.from_bytes` is let through only for a bytes literal or a slice with constant bounds of at most 7
bytes. Every case compares with CPython in the default build and with AIL_UNIFIED_FORCE=1.

G1  the gate itself (bigcap.marked): what is let through and what stays marked, including 61..65, negative and input amounts
G2  results beyond int64 (shift by 61..65, 8 and 9 byte int.from_bytes, literals at +-2**63) match CPython
G3  a varint decoder and a masked fixed shift reach the typed path (no "general path" note) and match CPython
"""
import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))

VARINT = '''
import sys


def rv(data, pos):
    val = 0
    shift = 0
    for i in range(5):
        b = data[pos + i]
        val |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            break
    return val


def main():
    data = sys.stdin.buffer.read()
    n = len(data)
    pos = 0
    total = 0
    cnt = 0
    mx = 0
    while pos + 5 <= n:
        v = rv(data, pos)
        total += v
        cnt += 1
        if v > mx:
            mx = v
        pos += 5
    print(cnt, total, mx)


main()
'''

# the amount is the constant @SH@, the operand is masked to two bits: provable up to SH = 60
FIXED = '''
import sys


def main():
    data = sys.stdin.read().split()
    SH = @SH@
    t = 0
    last = 0
    for w in data:
        v = int(w) & 3
        x = v << SH
        t += x >> 60
        last = x
    print(t, last)


main()
'''

# the amount is read from the input: never provable
AMOUNT = '''
import sys


def main():
    data = sys.stdin.read().split()
    for i in range(0, len(data) - 1, 2):
        v = int(data[i])
        n = int(data[i + 1])
        try:
            print(v << n, (v << n) >> n)
        except ValueError as e:
            print("ValueError", e)


main()
'''

NEGCONST = '''
import sys


def main():
    SH = -1
    v = int(sys.stdin.read().split()[0])
    try:
        print(v << SH)
    except ValueError as e:
        print("ValueError", e)
    SH = 3
    print(v << SH)


main()
'''

FROM_BYTES = '''
import sys


def main():
    raw = sys.stdin.buffer.read()
    a = int.from_bytes(raw[@LO@:@HI@], "@ORDER@"@SIGNED@)
    print(a, a + 1, a * 3, a.bit_length())
    xs = [a, a + 1]
    xs.append(a)
    print(len(xs), xs[1] - xs[0])


main()
'''

LITERALS = '''
import sys


def main():
    k = int(sys.stdin.read().split()[0])
    a = 9223372036854775807
    b = -9223372036854775808
    c = 9223372036854775808
    d = -9223372036854775809
    print(a + k, b - k, c + k, d - k, a * 2, b * 2, -b, abs(b))
    print(a + 1 > a, b - 1 < b, c - 1 == a, d + 1 == b)


main()
'''


def build(directory, text, name, extra=None):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL', 'AIL_UNIFIED_EXACT', 'AIL_QUIET_FALLBACK',
              'AIL_BIGCAP_SHIFT', 'AIL_BIGCAP_FROM_BYTES'):
        env.pop(k, None)
    env.update(extra or {})
    env['AIL_NO_CACHE'] = '1'
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax', 'python',
                        '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if r.returncode:
        raise AssertionError('build failed: ' + r.stderr[-1500:])
    return source, exe, ('general path' in r.stderr)


def run(cmd, data):
    r = subprocess.run(cmd, input=data.encode() if isinstance(data, str) else data, capture_output=True, timeout=120)
    return r.returncode, r.stdout


MODES = {'default': {}, 'force': {'AIL_UNIFIED_FORCE': '1'}}


def marks(src):
    os.environ['AIL_SURFACE'] = 'python'
    import bigcap
    return bigcap.marked(ast.parse(src), local=False, typed=True)


class Gate(unittest.TestCase):
    """G1"""

    def setUp(self):
        self._saved = os.environ.get('AIL_SURFACE')

    def tearDown(self):
        if self._saved is None:
            os.environ.pop('AIL_SURFACE', None)
        else:
            os.environ['AIL_SURFACE'] = self._saved

    def test_fixed_amount_limit(self):
        # operand bits + amount <= 62 passes: (x & 3) is 2 bits
        for sh in (0, 1, 30, 60):
            self.assertEqual(marks(FIXED.replace('@SH@', str(sh))), {}, sh)
        for sh in (61, 62, 63, 64, 65, 200):
            self.assertIn('main', marks(FIXED.replace('@SH@', str(sh))), sh)

    def test_amount_forms(self):
        ok = [
            'def f(b):\n    s = 0\n    v = 0\n    for i in range(5):\n        v |= (b & 0x7F) << s\n        s += 7\n    return v\n',
            'def f(b):\n    for i in range(8):\n        x = (b & 255) << i\n    return x\n',
            'def f(b, k):\n    return (b & 255) << (k & 31)\n',
            'def f(b, k):\n    return (b % 1000) << (k % 40)\n',
            'def f(w):\n    SH = 22\n    v = int(w) & 3\n    return v << SH\n',
            'def f(b):\n    s = 0\n    for i in range(5):\n        s += 7\n    s += 1\n    return (b & 3) << s\n',
        ]
        for src in ok:
            self.assertEqual(marks(src), {}, src)

    def test_stays_marked(self):
        bad = [
            'def f(b, n):\n    return b << n\n',                                                 # input amount
            'def f(b):\n    s = 0\n    while b:\n        b >>= 1\n        s += 7\n    return (b & 255) << s\n',  # while loop
            'def f(b):\n    SH = 22\n    return b << SH\n',                                        # unbounded operand
            'def f(b):\n    SH = -1\n    return (b & 3) << SH\n',                                  # negative amount
            'def f(b):\n    SH = 5\n    SH = 6\n    return (b & 3) << SH\n',                       # stored twice
            'def f(b, SH):\n    return (b & 3) << SH\n',                                            # a parameter
            'def f(b):\n    global SH\n    SH = 2\n    return (b & 3) << SH\n',                    # global
            'def f(b):\n    s = 0\n    for i in range(500):\n        b = (b & 255) << s\n        s += 7\n    return b\n',  # 3500 + 8 > 62
            'def f(b):\n    s = 0\n    for i in range(5):\n        s += 7\n    for s in range(9):\n        pass\n    return (b & 3) << s\n',
            'def f(b):\n    SH = 3\n    b <<= SH\n    return b\n',                                  # augmented: operand unbounded
            'def f(b):\n    s = 0\n    for i in range(5):\n        s += -7\n    return (b & 3) << s\n',    # negative step
        ]
        for src in bad:
            self.assertIn('f', marks(src), src)

    def test_nested_def_may_rebind(self):
        src = ('def f(b):\n    s = 3\n    def g():\n        nonlocal s\n        s = 99\n    g()\n    return (b & 3) << s\n')
        self.assertIn('f', marks(src))

    def test_from_bytes_forms(self):
        for expr in ('raw[0:4]', 'raw[2:9]', 'b"\\x01\\x02"', 'raw[1:8]', 'raw[:4]'):
            self.assertEqual(marks('def f(raw):\n    return int.from_bytes(%s, "big")\n' % expr), {}, expr)
        for expr in ('raw', 'raw[1:]', 'raw[0:-1]', 'raw[:8]', 'raw[0:8]', 'raw[0:9]', 'raw[0:8:1]', 'raw[-4:]', 'raw[a:b]'):
            self.assertIn('f', marks('def f(raw, a, b):\n    return int.from_bytes(%s, "big")\n' % expr), expr)


class Results(unittest.TestCase):
    """G2 / G3"""

    def check(self, text, inputs, modes=MODES, typed=None):
        with tempfile.TemporaryDirectory() as d:
            for mode, extra in modes.items():
                source, exe, general = build(d, text, 'p_' + mode, extra)
                if typed is not None and mode == 'default':
                    self.assertEqual(general, not typed, 'route of the default build')
                for data in inputs:
                    want = run([sys.executable, str(source)], data)
                    self.assertEqual(run([str(exe)], data), want, (mode, data))

    def test_varint_typed(self):
        import random
        rnd = random.Random(7)
        inputs = [bytes(5), b'\xff' * 5, b'\x7f' * 5, b'\x80\x80\x80\x80\x7f', b'\xff\xff\xff\xff\x0f', b'\xff\xff\xff\xff\xff',
                  bytes(rnd.randrange(256) for _ in range(500))]
        self.check(VARINT, inputs, typed=True)

    def test_fixed_shift_boundary(self):
        data = ['0 1 2 3', '3 3 3', '1', '-1 -2 -3', '9223372036854775807 5']
        for sh in (0, 1, 30, 60):
            self.check(FIXED.replace('@SH@', str(sh)), data, typed=True)
        for sh in (61, 62, 63, 64, 65):
            self.check(FIXED.replace('@SH@', str(sh)), data, typed=False)

    def test_amount_from_input(self):
        self.check(AMOUNT, ['5 0 5 1 5 63 5 64 5 65 5 200 -3 70 7 -1\n', '9223372036854775807 1 -9223372036854775808 1\n',
                            '1 62 1 63 1 64 1 65 -1 64\n'], typed=False)

    def test_negative_constant_amount(self):
        self.check(NEGCONST, ['5\n', '-7\n', '9223372036854775807\n'], typed=False)

    def test_from_bytes_widths(self):
        raws = [b'', b'\x01', b'\xff' * 9 + b'\x01', bytes(range(1, 11)), b'\x80' + b'\x00' * 9, b'\x7f' + b'\xff' * 9,
                b'\xff' * 12, b'\x00\x00\x00\x80\xff\xff\xff\x7f\x01\x02']
        inputs = raws
        for lo, hi, typed in ((0, 4, True), (3, 7, True), (1, 8, True), (0, 8, False), (0, 9, False), (2, 11, False)):
            for order in ('big', 'little'):
                for signed in ('', ', signed=True'):
                    text = (FROM_BYTES.replace('@LO@', str(lo)).replace('@HI@', str(hi)).replace('@ORDER@', order)
                            .replace('@SIGNED@', signed))
                    wide = (lo, hi) in ((1, 8), (0, 9)) and not signed
                    self.check(text, inputs, MODES if wide else {'default': {}}, typed=None if signed else typed)

    def test_literals_at_int64(self):
        self.check(LITERALS, ['0\n', '1\n', '-1\n', '9223372036854775807\n', '-9223372036854775808\n'], typed=False)


if __name__ == '__main__':
    unittest.main()
