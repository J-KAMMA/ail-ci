"""AIL_UNIFIED=1: type inference and unboxing on the general path (docs/design/UNIFIED_IR.md, prototype).

U1  hand-written programs: the general path, AIL_UNIFIED=1 and AIL_UNIFIED=1 with AIL_NO_MIX=1 print the same
    bytes and exit the same way, and the same as CPython 3.12 where the output does not depend on the version
U2  random integer and float programs near the int64 edges (overflow, zero divisors, shifts, floor division and
    modulo of negative numbers): the same output, stderr and exit status on the general path and AIL_UNIFIED=1
U3  the inference proves what it should: unboxed locals, a specialised body behind an entry guard, a boxed
    variable where a value is not proven, and no unboxed code at all when the flag is off
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
ON_312 = sys.version_info[:2] == (3, 12)


def build(directory, text, name, env_extra):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL'):
        env.pop(k, None)
    env.update(env_extra)
    env['AIL_NO_CACHE'] = '1'
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                        '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True, text=True,
                       timeout=900, env=env)
    return r, exe


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding='utf-8')
    return r.returncode, r.stdout, r.stderr


MODES = {'general': {}, 'unified': {'AIL_UNIFIED': '1'}, 'unified_nomix': {'AIL_UNIFIED': '1', 'AIL_NO_MIX': '1'}}

PROGRAMS = {
    'numeric': '''
import json
CONFIG = json.loads('{"n": 2000, "label": "steps"}')
K = 7
F = 2.5


def collatz(n):
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps


def arith(a, b):
    return (a // b, a % b, a << 3, a >> 2, (a ^ b) & (a | b), -a, ~b, a / b)


def mixed(n):
    total = 0
    acc = 0.0
    for i in range(n):
        total += i * K
        acc += i / 3
        if i % 3 == 0 and i > 2 or i == 1:
            acc -= F
    return total, acc


def loops():
    out = []
    for i in range(10, 0, -3):
        out.append(i)
    for j in range(5):
        if j == 3:
            break
    else:
        out.append("no-break")
    m = 99
    for m in range(0):
        pass
    n = 0
    while n < 5:
        n += 2
    else:
        out.append(("while-else", n, m))
    return out


def floats():
    a = 0.1 + 0.2
    b = -0.0
    c = 1e308 * 10
    d = c - c
    return a, b, c, d, 7.0 // 2, -7.5 % 2, min(3.5, 2.25, 9.0), max(1, 5, 3), a == 0.3, d != d


def fdiv(a, b):
    try:
        x = a / b
    except ZeroDivisionError as e:
        print("zde", e)
        x = -1.0
    return x


def poly(x):
    y = x + x
    return y


def gen(limit: int):
    for k in range(limit):
        yield poly(k)


def count_down(n: int) -> int:
    if n <= 0:
        return 0
    return 1 + count_down(n - 1)


def lens(s):
    n = len(s)
    c = ord(s[0])
    k = int("12") + n
    f = float(n) / 4
    return n, c, k, f, "a" in s, round(2.675), abs(-4), abs(-2.5)


def bools(x):
    seen = False
    for i in range(x):
        if i == 2:
            seen = True
    return seen, seen and True, seen + 1, 1 if seen else 2


def main():
    best = 0
    arg = 0
    i = 1
    while i < CONFIG["n"]:
        s = collatz(i)
        if s > best:
            best = s
            arg = i
        i += 1
    print(CONFIG["label"], arg, best)
    print(arith(17, 5), arith(-17, 5), arith(17, -5), arith(-17, -5))
    print(mixed(10), loops(), floats())
    print(fdiv(1, 4), fdiv(3, 0), fdiv(2.5, 0.5))
    print(poly(2), poly(2.5), poly("z"), poly([1]), list(map(poly, [1, 2, 3])), list(gen(4)))
    f = count_down
    print(f(5), count_down(7), lens("hello"), bools(4), bools(1))
    total = 0
    for x in json.loads("[3, -7, 2.5]"):
        total = total + x
    print(total)


main()
''',
}


def random_program(rng):
    """Integer and float arithmetic in one function whose locals the inference unboxes, with operands near
    the int64 edges: every edge (overflow, zero divisor, negative shift) takes the general runtime's path."""
    edges = ['0', '1', '-1', '2', '-2', '7', '-7', '63', '64', '9223372036854775807', '-9223372036854775807',
             '4611686018427387904', '3037000499', '-3037000500']
    ops = ['+', '-', '*', '//', '%', '<<', '>>', '&', '|', '^']
    lines = ['def f(a, b, c):', '    x = a', '    y = b', '    z = 0.5']
    for i in range(12):
        op = rng.choice(ops)
        lhs, rhs = rng.choice(['x', 'y', 'c']), rng.choice(['x', 'y', 'c', rng.choice(edges)])
        if op in ('<<', '>>'):
            rhs = rng.choice(['0', '1', '3', '62', '63', '64', 'c'])
        lines.append('    x = %s %s %s' % (lhs, op, rhs))
        lines.append('    if x > y or x == c:')
        lines.append('        y = y - 1')
        lines.append('    z = z * 1.5 + x / 3 if y != 0 else z - 1.0')
        lines.append('    print(%d, x, y, z, x < z, -y)' % i)
    lines.append('    return x')
    calls = ['f(%s, %s, %s)' % (rng.choice(edges), rng.choice(edges), rng.choice(['0', '1', '-1', '5', '63']))
             for _ in range(3)]
    body = ['def main():'] + ['    try:\n        print(%s)\n    except ZeroDivisionError as e:\n        print("zde", e)'
                             % c for c in calls] + ['', 'main()']
    return '\n'.join(lines) + '\n\n\n' + '\n'.join(body) + '\n'


class Unified(unittest.TestCase):
    def test_u1_programs(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in PROGRAMS.items():
                outs = {}
                for mode, env in MODES.items():
                    r, exe = build(d, text, '%s_%s' % (name, mode), env)
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    outs[mode] = run([str(exe)])
                self.assertEqual(outs['general'], outs['unified'], name)
                self.assertEqual(outs['general'], outs['unified_nomix'], name)
                if ON_312:
                    src = Path(d, name + '_cpython.py')
                    src.write_text(text, encoding='utf-8')
                    self.assertEqual(run([sys.executable, str(src)])[:2], outs['unified'][:2], name)

    def test_u2_random_edges(self):
        rng = random.Random(20261020)
        with tempfile.TemporaryDirectory() as d:
            for k in range(int(os.environ.get('AIL_UNIFIED_FUZZ', '6'))):
                text = random_program(rng)
                outs = []
                for mode in ('general', 'unified_nomix'):
                    r, exe = build(d, text, 'r%d_%s' % (k, mode), MODES[mode])
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    outs.append(run([str(exe)]))
                self.assertEqual(outs[0], outs[1], text)

    def test_u3_plan(self):
        sys.path[:0] = [str(PKG), str(ROOT)]
        import pyboxed2
        import unified
        text = PROGRAMS['numeric']
        saved = os.environ.get('AIL_UNIFIED')
        try:
            os.environ.pop('AIL_UNIFIED', None)
            plain = pyboxed2.build(text, {}, allow_mix=False)
            self.assertNotIn('pfu_', plain)
            self.assertNotIn('int64_t u_', plain)
            os.environ['AIL_UNIFIED'] = '1'
            del unified.STATS[:]
            c = pyboxed2.build(text, {}, allow_mix=False)
        finally:
            if saved is None:
                os.environ.pop('AIL_UNIFIED', None)
            else:
                os.environ['AIL_UNIFIED'] = saved
        stats = unified.STATS[-1]
        self.assertIn('collatz', stats['specialised'])
        self.assertIn('static ail_st pfu_collatz(ail_ctx *cx, int64_t *out, int64_t pv_n)', c)
        self.assertIn('if (pv_n.tag == AIL_T_INT) {', c)          # the boxed body's entry guard
        self.assertIn('int64_t u_steps = 0;', c)
        self.assertIn('double u_acc = 0;', c)                    # mixed(): a float accumulator
        self.assertIn('int u_seen = 0;', c)                       # bools(): a bool
        self.assertEqual(stats['constants'], ['F', 'K'])
        self.assertNotIn('u_total', c.split('static ail_st pf_main(')[1].split('\n}\n')[0])  # json values stay boxed


if __name__ == '__main__':
    unittest.main()
