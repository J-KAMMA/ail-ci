"""Typed reach for the hot functions of eight real programs (job prog15, 2026-11-02).

`lab/census/programs/gdev/g08_018.py` spent all its own time in `determinant` and `minor` and stayed
on the general path because the row comprehension bound a pair (`for j, value in enumerate(r)`).
The fold path already walked that pair shape; the list-comprehension path now does too, so the whole
program is typed.  The other five programs that do not reach the typed path are locked to their
current status (general path, output equal to CPython) with the reason recorded in
`lab/progfix/prog15.md`; the two that were already typed stay typed.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / 'lab'
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

JSON_IN = '{"b": 2, "a": [1, 2, {"z": null}], "c": "x"}\n'
NUMS_IN = '5\n2 3 0 4 5\n'

PROGRAMS = [
    ('g14_030', 'census/programs/gdev/g14_030.py', '', False),
    ('g17_008', 'census/programs/gdev/g17_008.py', '', False),
    ('t186', 'census/programs/dev/t186.py', JSON_IN, False),
    ('t012', 'corpus/programs/deepseek-v4.1-flash-free/t012.py', NUMS_IN, True),
    ('g25_024', 'census/programs/gdev/g25_024.py', '', False),
    ('g16_008', 'census/programs/gdev/g16_008.py', '', False),
    ('g02_000', 'census/programs/gdev/g02_000.py', '', True),
    ('g08_018', 'census/programs/gdev/g08_018.py', '', True),
]

PAIR = '''from dataclasses import dataclass

@dataclass
class Box:
    xs: list[int]

def doubled(xs: list[int], skip: int) -> list[int]:
    return [v * 2 for i, v in enumerate(xs) if i != skip]

def upper_even(xs: list[str]) -> list[str]:
    return [v.upper() for i, v in enumerate(xs) if i % 2 == 0]

def scaled(xs: list[float]) -> list[float]:
    return [v * 0.5 for i, v in enumerate(xs) if i % 2 == 0]

def zipped(a: list[int], b: list[int]) -> list[int]:
    return [x + y for x, y in zip(a, b)]

def zipped_float(a: list[float], b: list[int]) -> list[float]:
    return [x + y for x, y in zip(a, b)]

def zipped_str(a: list[str], b: list[int]) -> list[int]:
    return [y * 2 for x, y in zip(a, b)]

def zipped_str_value(a: list[str], b: list[str]) -> list[str]:
    return [y.upper() for x, y in zip(a, b)]

def items_untyped() -> list[str]:
    d = {"a": 1, "bb": 2, "ccc": 3}
    return [k for k, v in d.items() if v > 1]

def items_untyped_values() -> list[int]:
    d = {"a": 1, "bb": 2, "ccc": 3}
    return [v * 10 for k, v in d.items()]

def from_field(b: Box, skip: int) -> list[int]:
    return [v + 1 for i, v in enumerate(b.xs) if i != skip]

def from_item(rows: list[list[int]], k: int) -> list[int]:
    return [v for j, v in enumerate(rows[k]) if j != k]

def main() -> None:
    for x in doubled([], 0): print(x)
    for x in doubled([1, 2, 3, 4], 2): print(x)
    for x in doubled([-5, 0, 4611686018427387903], -1): print(x)
    for x in upper_even([]): print(x)
    for x in upper_even(["a", "bb", "ccc", "dd"]): print(x)
    for x in scaled([]): print(x)
    for x in scaled([1.5, 2.5, 3.5]): print(x)
    for x in zipped([1, 2, 3], [10, 20]): print(x)
    for x in zipped([], [1]): print(x)
    for x in zipped_float([], [1]): print(x)
    for x in zipped_float([1.5, 2.5], [10, 20]): print(x)
    for x in zipped_str(["a", "bb"], [10, 20]): print(x)
    for x in zipped_str_value(["a", "bb"], ["c", "dd"]): print(x)
    for x in items_untyped(): print(x)
    for x in items_untyped_values(): print(x)
    b = Box([7, 8, 9])
    for x in from_field(b, 1): print(x)
    rows = [[1, 2, 3], [4, 5]]
    for x in from_item(rows, 0): print(x)
    for x in from_item(rows, 1): print(x)
main()
'''


def compile_default(directory, source, name, strict=False):
    out = Path(directory) / (name + '_x')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    cmd = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
           '--syntax', 'python', '-o', str(out)]
    if strict:
        cmd.insert(4, '--strict')
    res = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, out


def run_cpython(source, stdin):
    return subprocess.run([sys.executable, str(source)], input=stdin.encode('utf-8'),
                          capture_output=True, timeout=300)


def typed(res):
    return 'built on the general path' not in res.stderr


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog15(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog15_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def compare(self, source, name, stdin=''):
        res, exe = compile_default(self.tmp, source, name)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        want = run_cpython(source, stdin)
        got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
        self.assertEqual(got.stdout, want.stdout, name)
        self.assertEqual(got.returncode, want.returncode, name)
        return res

    def test_eight_programs_match_cpython_and_keep_their_path(self):
        for name, rel, stdin, expect_typed in PROGRAMS:
            source = LAB / rel
            with self.subTest(program=name):
                res = self.compare(source, name, stdin)
                self.assertEqual(typed(res), expect_typed, name + ': ' + res.stderr[-600:])

    def test_pair_target_list_comprehensions_typed(self):
        source = Path(self.tmp) / 'pair.py'
        source.write_text(PAIR, encoding='utf-8')
        res = self.compare(source, 'pair')
        self.assertTrue(typed(res), res.stderr[-600:])



if __name__ == '__main__':
    unittest.main()
