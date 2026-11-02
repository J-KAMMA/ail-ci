"""Hot functions of the prog22 programs that now take the typed path, against CPython 3.12.

The typed path is the default `compile --syntax python` build (the note "built on the general
path" means it was not taken).  A program that builds typed compiles every hot function in it.

T1  t366 (ranking records) builds typed after a local `list[tuple[str, float, str]]` annotation
    names the str-field rows `_mark_srow_lists` already builds from `.append()`; the sort key and
    `enumerate(records, start=1)` keep working on that kind.
T2  t347 (sieve) and t318 (Fenwick tree) stay on the typed path.
T3  stdout and exit status equal CPython on the task inputs, empty input, ties and boundaries.
T4  a str/int/float records list covers empty rows, negative `enumerate` starts and int64 edges.
T5  a NaN sort key is refused by name instead of silently differing (DIFFERENCES
    C?-job-refuzz95-10300605-1).
T6  g14 (students) builds typed after `max(students, key=lambda s: s.average())` learns the
    numeric-key fold over a list of class instances, on both an argument and a list field.
T7  that fold covers empty (CPython's catchable ValueError and text), ties, negative and
    int64-edge keys.
T8  a str-field row wider than `AIL_SROW_MAXK` (4) is not truncated: the program takes the
    general path and matches CPython.
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

MAXKEY = '''from dataclasses import dataclass


@dataclass
class Item:
    name: str
    score: float
    count: int


@dataclass
class Bucket:
    items: list[Item]


def best_score(items: list[Item]) -> Item:
    return max(items, key=lambda it: it.score)


def worst_count(items: list[Item]) -> Item:
    return min(items, key=lambda it: it.count)


def best_of_bucket(bucket: Bucket) -> Item:
    return max(bucket.items, key=lambda it: it.count)


def main() -> None:
    items = [
        Item("a", 1.5, 3),
        Item("b", 2.5, 2),
        Item("c", 2.5, 1),
        Item("d", -3.0, -7),
    ]
    print(best_score(items).name)
    print(worst_count(items).name)
    print(best_of_bucket(Bucket(items)).name)
    one = [Item("solo", -0.0, 9223372036854775807)]
    print(best_score(one).name, worst_count(one).name)
    edge = [Item("max", 0.0, 9223372036854775807),
            Item("min", 0.0, -9223372036854775808)]
    print(worst_count(edge).name, best_score(edge).name)
    ties = [Item("first", 0.0, 5), Item("second", 0.0, 5)]
    print(best_score(ties).name, worst_count(ties).name)


if __name__ == "__main__":
    main()
'''

EMPTYMAX = '''from dataclasses import dataclass


@dataclass
class Item:
    score: float


def main() -> None:
    items: list[Item] = []
    print(max(items, key=lambda it: it.score).score)


if __name__ == "__main__":
    main()
'''

CATCH_EMPTY = '''from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Student:
    name: str
    grades: list[float] = field(default_factory=list)

    def average(self) -> float:
        return sum(self.grades) / len(self.grades) if self.grades else 0.0


@dataclass
class Group:
    members: list[Student]


def build() -> list[Student]:
    return []


def main() -> None:
    xs = build()
    try:
        max(xs, key=lambda s: s.average())
    except ValueError as exc:
        print("max", exc)
    try:
        min(xs, key=lambda s: s.average())
    except ValueError as exc:
        print("min", exc)
    empty = Group([])
    try:
        min(empty.members, key=lambda s: s.average())
    except ValueError as exc:
        print("attr", exc)


if __name__ == "__main__":
    main()
'''

FIVEFIELD = '''def main() -> None:
    rows: list[tuple[str, int, float, str, int]] = []
    rows.append(("a", 1, 2.0, "x", 3))
    rows.append(("b", 0, -1.0, "y", 4))
    rows.sort(key=lambda r: (r[1], r[0]))
    for i, (a, b, c, d, e) in enumerate(rows, start=1):
        print(i, a, b, c, d, e)


if __name__ == "__main__":
    main()
'''

SROWS = '''import sys


def main() -> None:
    rows: list[tuple[str, int, float]] = []
    data = sys.stdin.read().split()
    i = 0
    while i + 2 < len(data):
        name = data[i]
        n = int(data[i + 1])
        score = float(data[i + 2])
        rows.append((name, n, score))
        rows.append((name.upper(), n, score + 0.5))
        i += 3
    rows.sort(key=lambda r: (r[1], r[0]))
    for pos, (name, n, score) in enumerate(rows, start=-2):
        print(pos, name, n, score)
    other: list[tuple[str, int, float]] = []
    other.append(("solo", 9223372036854775807, -1.5))
    other.append(("low", -9223372036854775808, 2.5))
    other.sort(key=lambda r: (r[1], r[0]))
    for pos, (name, n, score) in enumerate(other, start=0):
        print(pos, name, n, score)


if __name__ == "__main__":
    main()
'''


def compile_default(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_x')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_SERVER='0')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                          source.name, '-o', exe.name], cwd=directory, capture_output=True,
                         text=True, timeout=900, env=env)
    return res, exe, source


def typed(res):
    return 'built on the general path' not in res.stderr


def task_inputs(name):
    directory = LAB / 'corpus' / 'tasks' / name
    if not directory.is_dir():
        return ('',)
    return tuple(path.read_text(encoding='utf-8')
                 for path in sorted(directory.glob('in*.txt')))


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog22(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog22_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, text, name):
        res, exe, source = compile_default(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        self.assertTrue(typed(res), 'fell back to the general path: ' + res.stderr[-800:])
        return exe, source

    def same(self, exe, source, stdin=''):
        want = subprocess.run([sys.executable, str(source)], input=stdin.encode('utf-8'),
                              capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True,
                             timeout=300)
        self.assertEqual(got.stdout, want.stdout, repr(stdin))
        self.assertEqual(got.returncode, want.returncode, repr(stdin))

    def check_program(self, relative, name, inputs):
        path = LAB / relative
        if not path.is_file():
            self.skipTest('lab is not part of this tree')
        text = path.read_text(encoding='utf-8')
        exe, source = self.build(text, name)
        for stdin in inputs:
            self.same(exe, source, stdin)
        return exe, source

    def test_ranking_records_typed(self):
        extra = ('', '1 solo A 20 100\n',
                 '5 a A 1 50\nb B 1 50\nc C 1 50\nd D 1 50\ne E 1 50\n',
                 '4 neg A 1 -1.5\nzero B 1 -0.0\npos C 1 0.0\nbig D 1 1e308\n')
        self.check_program('census/programs/dev/t366.py', 't366',
                           task_inputs('t366') + extra)

    def test_sieve_typed(self):
        self.check_program('corpus/programs/deepseek-v4.1-flash-free/t347.py', 't347',
                           task_inputs('t347') + ('0\n', '1\n'))

    def test_fenwick_typed(self):
        self.check_program('census/programs/dev/t318.py', 't318',
                           task_inputs('t318') + ('',))

    def test_student_max_key_typed(self):
        self.check_program('census/programs/gdev/g14_034.py', 'g14_034', ('',))

    def test_max_key_over_instances_typed(self):
        exe, source = self.build(MAXKEY, 'maxkey')
        self.same(exe, source)

    def test_max_key_empty_is_value_error(self):
        exe, source = self.build(EMPTYMAX, 'maxkey_empty')
        want = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], capture_output=True, timeout=300)
        self.assertEqual(got.stdout, want.stdout)
        self.assertNotEqual(want.returncode, 0)
        self.assertNotEqual(got.returncode, 0)
        self.assertIn(b'ValueError', got.stderr)

    def test_max_key_empty_is_catchable_value_error(self):
        exe, source = self.build(CATCH_EMPTY, 'maxkey_catch')
        self.same(exe, source)

    def test_wide_str_row_is_not_truncated(self):
        res, exe, source = compile_default(self.tmp, FIVEFIELD, 'srows_five')
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        self.same(exe, source)

    def test_str_field_records_typed(self):
        exe, source = self.build(SROWS, 'srows')
        for stdin in ('', 'a 2 1.5 b 2 1.5 c -3 0.25',
                      'max 9223372036854775807 3.5 min -9223372036854775808 -4.5 tie 0 0',
                      'one 1 1'):
            self.same(exe, source, stdin)

    def test_nan_sort_key_is_refused(self):
        path = LAB / 'census' / 'programs' / 'dev' / 't366.py'
        if not path.is_file():
            self.skipTest('lab is not part of this tree')
        exe, source = self.build(path.read_text(encoding='utf-8'), 't366_nan')
        got = subprocess.run([str(exe)], input=b'1 nan A 20 nan\n',
                             capture_output=True, timeout=300)
        self.assertNotEqual(got.returncode, 0)
        self.assertIn(b'ValueError', got.stderr)


if __name__ == '__main__':
    unittest.main()
