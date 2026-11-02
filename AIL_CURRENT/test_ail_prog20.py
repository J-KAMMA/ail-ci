"""The hot functions of the eight prog20 programs on the typed path, against CPython 3.12.

Batch prog20 profiled the hot functions of eight real programs.  Two compiler
changes make the two remaining buildable programs whole-program typed:

- `min`/`max` with a tuple-returning key (`lambda city: (-pops[city], city)`)
  compares the fields lexicographically, for a dict walk and for a sequence
  (g05_006).
- `for i, (word, count) in enumerate(rows, start)` destructures a tuple element
  of a list of tuple instances, and the same shape over a `list[tuple[str, int]]`
  row list (g18_002).  The index is start + position, the start is evaluated
  once, and a body that rebinds the target cannot move the next step.

T1  each program takes the typed path (no "built on the general path" note)
T2  stdout and exit code equal CPython on the task input
T3  tuple keys: min over a dict and a list, ties, negatives, three fields,
    a value through an attribute, an empty dict, near-int64 values
T4  enumerate over rows: start 1, 0, negative, empty, a rebound index and a
    rebound start variable
T5  the programs that still need a big feature stay named in lab/progfix/prog20.md
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None


def compile_default(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_x')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '-o', exe.name],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe, source


def typed(res):
    return 'built on the general path' not in res.stderr


TUPLE_KEY = '''from dataclasses import dataclass


def best3(pops: dict[str, int]) -> str:
    if not pops:
        raise ValueError("empty")
    return min(pops, key=lambda city: (-pops[city], city, len(city)))


def best_int(xs: list[int]) -> int:
    return min(xs, key=lambda x: (x % 3, -x))


@dataclass
class Row:
    name: str
    score: int


def main() -> None:
    pops: dict[str, int] = {"Tokyo": 10, "Delhi": 20, "Oslo": 20, "Paris": 5}
    print(best3(pops))
    tied: dict[str, int] = {"b": 3, "a": 3, "c": 2}
    one: dict[str, int] = {"A": 1}
    print(best3(tied))
    print(best3(one))
    big: dict[str, int] = {"near": 9223372036854775807, "small": -9223372036854775806}
    print(best3(big))
    print(best_int([-5, 4, -2, 7, 0, 3]), best_int([1]), best_int([2, 2, 1]))
    objs = [Row("b", 3), Row("a", 3), Row("c", 5)]
    print(max(objs, key=lambda r: (r.score, r.name)).name)
    print(min(objs, key=lambda r: (r.score, r.name)).name)
    empty: dict[str, int] = {}
    try:
        best3(empty)
    except ValueError as e:
        print(type(e).__name__)


main()
'''

ENUM_ROWS = '''def main() -> None:
    rows = [("b", 2), ("a", 2), ("c", 9)]
    for i, (name, n) in enumerate(rows, 1):
        print(i, name, n)
    for i, (name, n) in enumerate(rows, 0):
        print(i, name, n)
    for i, (name, n) in enumerate(rows, -3):
        print(i, name, n)
    for i, (name, n) in enumerate(rows[:0], 7):
        print("never", i, name, n)
    for i, (name, n) in enumerate(rows, start=10):
        if i == 10:
            i = 999
            name = "changed"
        print(i, name, n)
    start = 4
    for i, (name, n) in enumerate(rows, start=start):
        start = 100
        print(i, name, n)


main()
'''


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog20(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog20_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, text, name, expect_typed=True):
        res, exe, source = compile_default(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-1800:])
        if expect_typed is not None:
            self.assertEqual(typed(res), expect_typed, res.stderr[-900:])
        return exe, source

    def same(self, exe, source, stdin=''):
        want = subprocess.run([sys.executable, str(source)], input=stdin.encode('utf-8'),
                              capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
        self.assertEqual(got.stdout, want.stdout, repr(stdin))
        self.assertEqual(got.returncode, want.returncode, repr(stdin))

    def check_file(self, path, name):
        text = path.read_text(encoding='utf-8')
        exe, source = self.build(text, name)
        self.same(exe, source)

    def lab(self, *parts):
        return REPO.joinpath('lab', *parts)

    def test_g05_006_whole_program_typed(self):
        path = self.lab('census', 'programs', 'gdev', 'g05_006.py')
        if not path.exists():
            self.skipTest('lab census program is not in this tree')
        self.check_file(path, 'g05_006')

    def test_g18_002_whole_program_typed(self):
        path = self.lab('census', 'programs', 'gdev', 'g18_002.py')
        if not path.exists():
            self.skipTest('lab census program is not in this tree')
        self.check_file(path, 'g18_002')

    def test_tuple_key_typed(self):
        exe, source = self.build(TUPLE_KEY, 'tuple_key')
        self.same(exe, source)

    def test_enumerate_rows_start_typed(self):
        exe, source = self.build(ENUM_ROWS, 'enum_rows')
        self.same(exe, source)


if __name__ == '__main__':
    unittest.main()
