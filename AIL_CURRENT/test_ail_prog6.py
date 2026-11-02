"""prog6: the hot functions of eight real programs on the CPython hybrid's typed path.

`fibonacci_mod` (g09_000), `card_value` (t402), `catalan_numbers` (g09_020) and
`count_no_adjacent_ones` (g09_014) used to stay in CPython: pymix could not follow the annotated
list/tuple locals, and the hybrid refused indexing/division/raise, pure builtin calls and list
results.  Each test builds the real program with `ail build --cpython`, checks the function is in
the accelerated set, and compares the packaged run with CPython.  Overflow, negative and invalid
input boundaries must either match CPython or fall back to it; the list-return clone returns -1
from its length probe when an int64 overflow is hit.
"""
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
HAVE_HEADERS = (Path(sysconfig.get_paths().get('include', '/nonexistent')) / 'Python.h').is_file()

PROGRAMS = {
    'g09_000': ('lab/census/programs/gdev/g09_000.py', ['fibonacci_mod']),
    'g09_014': ('lab/census/programs/gdev/g09_014.py', ['count_no_adjacent_ones']),
    'g09_020': ('lab/census/programs/gdev/g09_020.py', ['catalan_numbers']),
    't402': ('lab/corpus/programs/deepseek-v4.1-flash-free/t402.py', ['card_value']),
}

CATALAN = '''
def catalan_numbers(count: int) -> list[int]:
    if count <= 0:
        return []
    table: list[int] = [0] * count
    table[0] = 1
    for n in range(1, count):
        total = 0
        for i in range(n):
            total += table[i] * table[n - 1 - i]
        table[n] = total
    return table

print(catalan_numbers(%d))
'''

FIB = '''
def fibonacci_mod(n: int, mod: int) -> int:
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0
    dp: list[int] = [0] * (n + 1)
    dp[1] = 1 % mod
    for i in range(2, n + 1):
        dp[i] = (dp[i - 1] + dp[i - 2]) % mod
    return dp[n]

print(fibonacci_mod(__N__, __M__))
'''

COUNT = '''
def count_no_adjacent_ones(length: int) -> int:
    if length == 0:
        return 1
    ends_in_zero: int = 1
    ends_in_one: int = 0
    for _ in range(length):
        ends_in_zero, ends_in_one = ends_in_zero + ends_in_one, ends_in_zero
    return ends_in_zero + ends_in_one

print(count_no_adjacent_ones(%d))
'''

CARD = '''
def card_value(rank: str) -> int:
    if rank == "A":
        return 1
    if rank in "TJQK":
        return 10
    return int(rank)

print(card_value(%r))
'''

RANGE_STEP = '''
def loop(n: int, step: int) -> int:
    total = 0
    for i in range(0, n, step):
        total += i
    return total

def use(n: int, step: int) -> int:
    try:
        return loop(n, step)
    except ValueError:
        return -1

print(use(5, 1))
print(use(5, 0))
print(use(5, -1))
print(loop(10, 2))
'''

LIST_IDENT = '''
def ident(xs: list[int]) -> list[int]:
    return xs

def ident_alias(xs: list[int]) -> list[int]:
    ys = xs
    return ys

def local(n: int) -> list[int]:
    ys: list[int] = [0] * n
    for i in range(n):
        ys[i] = i + 1
    return ys

a = [1, 2]
b = ident(a)
print(ident(a) is a)
b[0] = 9
print(a, b)
print(ident_alias(a) is a)
c = ident_alias(a)
c[1] = 7
print(a, c)
print(local(3))
'''

TRAP_FLUSH = '''
def pick(xs: list[int], i: int) -> int:
    return xs[i]

def divide(a: int, b: int) -> int:
    return a // b

def check(n: int) -> int:
    if n < 0:
        raise ValueError("n must be non-negative")
    return n

print("before", pick([3, 4], 1), divide(9, 2), check(5))
print(pick([3], 5))
'''

ALIAS = '''
def mutate_item(rows: list[int]) -> int:
    zs: list[int] = []
    zs = rows
    zs[-1] = 7
    return zs[-1]

def local(n: int) -> list[int]:
    zs: list[int] = [0] * n
    for i in range(n):
        zs[i] = i + 1
    return zs

b = [3, 4]
print(mutate_item(b), b)
print(local(3))
'''

PURE_CALL = '''
def conv(s: str) -> float:
    return float(s)

def use(s: str) -> float:
    try:
        return conv(s)
    except ValueError:
        return -1.0

print(use("2.5"), use("x"))
'''

FALLTHROUGH = '''
def f(flag: int) -> int:
    if flag:
        return 5

print(f(1), f(0))
'''


def run(cmd, cwd=None, stdin='', env=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin.encode(), env=env,
                          capture_output=True, timeout=600)


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class Prog6Typed(unittest.TestCase):
    def build(self, tmp, name, text):
        src = Path(tmp) / (name + '.py')
        src.write_text(text, encoding='utf-8')
        out = Path(tmp) / 'out'
        env = dict(os.environ, AIL_NO_CACHE='1')
        built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)], tmp)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
        return src, out, report

    def compare(self, tmp, src, out, name, stdin=''):
        want = run([sys.executable, str(src)], tmp, stdin)
        got = run([str(out / name)], tmp, stdin)
        self.assertEqual(got.stdout, want.stdout)
        self.assertEqual(got.returncode, want.returncode)

    def test_real_programs(self):
        for name, (rel, accelerated) in PROGRAMS.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
                src = REPO / rel
                out = Path(tmp) / 'out'
                env = dict(os.environ, AIL_NO_CACHE='1')
                built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)],
                            REPO, env=env)
                self.assertEqual(built.returncode, 0, built.stderr[-3000:])
                report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
                for func in accelerated:
                    self.assertIn(func, report['accelerated'], report)
                if name == 't402':
                    for case in ('in0', 'in1', 'in2'):
                        data = (REPO / 'lab/corpus/tasks/t402' / (case + '.txt')).read_text(encoding='utf-8')
                        self.compare(REPO, src, out, name, data)
                else:
                    self.compare(REPO, src, out, name)

    def test_catalan_list_result_and_overflow_fallback(self):
        for count in (0, -1, 15, 37, 40):
            with self.subTest(count=count), tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
                src, out, report = self.build(tmp, 'catalan', CATALAN % count)
                self.assertIn('catalan_numbers', report['accelerated'], report)
                self.compare(tmp, src, out, 'catalan')

    def test_fibonacci_overflow_and_exceptions(self):
        cases = [(0, 7), (10, 1_000_000_007), (100, 1 << 62), (-1, 7), (10, 0)]
        for n, mod in cases:
            with self.subTest(n=n, mod=mod), tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
                src, out, report = self.build(tmp, 'fib', FIB.replace('__N__', str(n)).replace('__M__', str(mod)))
                self.assertIn('fibonacci_mod', report['accelerated'], report)
                self.compare(tmp, src, out, 'fib')

    def test_count_overflow_fallback(self):
        for length in (-5, 0, 20, 93, 100):
            with self.subTest(length=length), tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
                src, out, report = self.build(tmp, 'count', COUNT % length)
                self.assertIn('count_no_adjacent_ones', report['accelerated'], report)
                self.compare(tmp, src, out, 'count')

    def test_card_value_routes_and_invalid_input(self):
        for value in ('A', 'J', '9', '-2', ' 3 ', 'x', ''):
            with self.subTest(value=value), tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
                src, out, report = self.build(tmp, 'card', CARD % value)
                self.assertIn('card_value', report['accelerated'], report)
                self.compare(tmp, src, out, 'card')

    def test_uncaught_trap_flushes_python_stdout(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
            src, out, report = self.build(tmp, 'flush', TRAP_FLUSH)
            for func in ('pick', 'divide', 'check'):
                self.assertIn(func, report['accelerated'], report)
            self.compare(tmp, src, out, 'flush')

    def test_range_zero_step_caught_by_boxed_caller(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
            src, out, report = self.build(tmp, 'range_step', RANGE_STEP)
            self.assertNotIn('loop', report['accelerated'], report)
            self.compare(tmp, src, out, 'range_step')

    def test_list_parameter_return_stays_boxed(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
            src, out, report = self.build(tmp, 'list_ident', LIST_IDENT)
            self.assertNotIn('ident', report['accelerated'], report)
            self.assertNotIn('ident_alias', report['accelerated'], report)
            self.assertIn('local', report['accelerated'], report)
            self.compare(tmp, src, out, 'list_ident')

    def test_list_parameter_alias_mutation_stays_boxed(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
            src, out, report = self.build(tmp, 'alias', ALIAS)
            self.assertNotIn('mutate_item', report['accelerated'], report)
            self.assertIn('local', report['accelerated'], report)
            self.compare(tmp, src, out, 'alias')

    def test_untracked_pure_call_stays_boxed(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
            src, out, report = self.build(tmp, 'pure', PURE_CALL)
            self.assertNotIn('conv', report['accelerated'], report)
            self.compare(tmp, src, out, 'pure')

    def test_fallthrough_return_stays_boxed(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog6-') as tmp:
            src, out, report = self.build(tmp, 'fallthrough', FALLTHROUGH)
            self.assertNotIn('f', report['accelerated'], report)
            self.compare(tmp, src, out, 'fallthrough')


if __name__ == '__main__':
    unittest.main()
