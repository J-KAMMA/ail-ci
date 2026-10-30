"""Per-function exact mode for the functions bigcap marks (unified.exact_enabled, docs/design/BIGINT.md section 14).

A function whose own code can make a big int (bigcap.own_marked) is no longer boxed whole on the general path, and its
callers are not marked at all: in the function an int expression is unboxed only when its bit bound is below 63, its
floats and bounded ints stay unboxed, and every value that crosses a call, a list or a field is the boxed exact int.

S1  the boundary: big values made by a marked function and crossing to unmarked code as a result, a list element, a field
    and an argument, in a loop; default build, AIL_UNIFIED_FORCE=1 and AIL_UNIFIED_EXACT=0 print what CPython prints
S2  shifts by 0, 63, 64, 200 and a negative count (ValueError caught and uncaught), int.from_bytes / to_bytes
S3  the plan: the marked function and its caller are not demoted whole (no `name:*`), and are with AIL_UNIFIED_EXACT=0
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CROSS = '''
import sys


class Box:
    def __init__(self, v):
        self.v = v


def grow(x, n):
    return x << n


def fill(xs, n):
    for k in range(n):
        xs.append((k + 1) << (k * 9))


def setf(b, n):
    b.v = 3 << n


def plain(a, b):
    s = 0
    for i in range(a):
        s += i * b
    return s


def main():
    data = sys.stdin.read().split()
    n = int(data[0])
    m = int(data[1])
    r = grow(5, n)
    print(r, r + 1, r > 10, plain(4, 7))
    xs = []
    fill(xs, m)
    t = 0
    for x in xs:
        t += x
    print(len(xs), t, xs[-1] if xs else -1)
    b = Box(0)
    setf(b, n)
    print(b.v, b.v - 1)
    acc = 0
    for i in range(2000):
        acc += grow(i, i % 70) & 0xFFFF
    print(acc)
    fl = 0.5
    for i in range(1000):
        fl = fl * 1.0001 + i
    print(round(fl, 3))


main()
'''

SHIFTS = '''
import sys


def sh(a, n):
    return a << n


def main():
    vals = [int(t) for t in sys.stdin.read().split()]
    a = vals[0]
    for n in vals[1:]:
        try:
            print(n, sh(a, n), sh(-a, n), (a << n) >> n, sh(a, n) & 0xFF)
        except ValueError as e:
            print("ValueError", e)
    print(sh(a, vals[-1]))


main()
'''

BYTES = '''
import sys


def dec(b, order, signed):
    return int.from_bytes(b, order, signed=signed)


def main():
    raw = sys.stdin.read().split()
    chunks = [bytes.fromhex(t) if t != "-" else b"" for t in raw]
    for c in chunks:
        for order in ("big", "little"):
            for signed in (False, True):
                v = dec(c, order, signed)
                print(len(c), order, signed, v, v.bit_length())
    x = int.from_bytes(b"\\xff" * 9, "big")
    print(x, x.to_bytes(9, "big").hex(), (255).to_bytes(2, "little").hex())
    try:
        print((256).to_bytes(1, "big"))
    except OverflowError as e:
        print("OverflowError", e)
    print((-1).to_bytes(3, "big", signed=True).hex())


main()
'''

# a marked function (a literal beyond int64) with a float loop and a caller that only passes values on
PLAN = '''
import sys


def mix(seed, n):
    x = seed
    total = 0.0
    for i in range(n):
        x = (x * 6364136223846793005 + 1442695040888963407) & 18446744073709551615
        total = total + float(x >> 40) / 3.0
    return x, total


def main():
    seed = int(sys.stdin.read().split()[0])
    x, total = mix(seed, 50)
    print(x, round(total, 3))


main()
'''


def build(directory, text, name, extra=None):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL', 'AIL_UNIFIED_EXACT'):
        env.pop(k, None)
    env.update(extra or {})
    env['AIL_NO_CACHE'] = '1'
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax', 'python',
                        '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if r.returncode:
        raise AssertionError('build failed: ' + r.stderr[-1500:])
    return source, exe


def run(cmd, data):
    r = subprocess.run(cmd, input=data, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout


MODES = {'default': {}, 'force': {'AIL_UNIFIED_FORCE': '1'}, 'exact_off': {'AIL_UNIFIED_EXACT': '0'}}


class BigcapSplit(unittest.TestCase):
    def check(self, text, inputs, modes=MODES):
        with tempfile.TemporaryDirectory() as d:
            for mode, extra in modes.items():
                source, exe = build(d, text, 'p_' + mode, extra)
                for data in inputs:
                    want = run([sys.executable, str(source)], data)
                    self.assertEqual(run([str(exe)], data), want, (mode, data))

    def test_s1_boundary(self):
        self.check(CROSS, ['3 4\n', '70 9\n', '200 12\n'])

    def test_s2_shifts(self):
        self.check(SHIFTS, ['5 0 1 63 64 200\n', '3 62 63\n', '7 -1 5\n', '1 -3\n'])

    def test_s2_bytes(self):
        self.check(BYTES, ['- 01 ff 7fff 8000 ffffffffffffffff 0102030405060708090a\n'], {'default': {}, 'force': MODES['force']})

    def test_s3_plan(self):
        self.check(PLAN, ['0\n', '18446744073709551615\n', '12345\n'], {'default': {}})
        with tempfile.TemporaryDirectory() as d:
            for mode, extra, demoted in (('on', {}, False), ('off', {'AIL_UNIFIED_EXACT': '0'}, True)):
                stats = Path(d, 'stats_' + mode)
                build(d, PLAN, 'q_' + mode, dict(extra, AIL_UNIFIED_STATS=str(stats)))
                if not stats.exists():
                    # the old rule marks <module> (it calls mix()), which turns the unboxing pass off altogether
                    self.assertTrue(demoted, mode)
                    continue
                entries = [json.loads(line) for line in stats.read_text().splitlines() if line.strip()]
                self.assertTrue(entries, mode)
                whole = {k for e in entries for key in ('demoted', 'float_locals_kept_boxed')
                         for k in e.get(key, ()) if k.endswith(':*')}
                self.assertEqual('mix:*' in whole, demoted, (mode, sorted(whole)))
                self.assertEqual('main:*' in whole, demoted, (mode, sorted(whole)))


if __name__ == '__main__':
    unittest.main()
