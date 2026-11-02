"""Typed reach for the hot functions of eight real programs, against CPython 3.12.

`lab/progfix/prog28.md` records the cProfile hot functions.  t441, g04_012 and g22_020
already built on the typed path; this job makes t141 and g07_036 build there too:

* t141's hot `main` and key lambda bind `top_item = max(stock, key=lambda name: stock[name])`.
  The typed `min`/`max` lowering over a typed dict builds its key list first, but the
  pre-binding pass then read the holder subscript as an int, so the str key looked like a
  rebinding.  The typed key kind and the synthesized iterlower holder are now respected.
* g07_036's hot `trim_extremes` and `main` use `[value for index, value in enumerate(values)
  if ...]` and `excluded: set[int] = {min_index, max_index}`; both shapes now build typed.

The other three keep their recorded follow-ups: g25_040 needs typed Enum methods / module
lists, t489 needs `unicodedata.name` / `normalize`, and g01_002 needs the Counter use behind
`int(match.group("status"))` inside the `+=` key.
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
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

PROGRAMS = (
    ('t141', 'lab/corpus/programs/deepseek-v4.1-flash-free/t141.py', 'lab/corpus/tasks/t141'),
    ('g07_036', 'lab/census/programs/gdev/g07_036.py', None),
)
NEWLY_TYPED = ('t141', 'g07_036')

DICT_KEY = '''
class Box:
    def __init__(self, base: int) -> None:
        self.base = base


def top_name(stock: dict[str, int], cur: int) -> str:
    return max(stock, key=lambda k: abs(stock[k] - cur))


def low_name(stock: dict[str, int]) -> str:
    return min(stock, key=lambda k: stock[k])


def top_num(nums: dict[int, int], cur: int) -> int:
    return max(nums, key=lambda k: abs(nums[k] - cur))


def low_num(nums: dict[int, int]) -> int:
    return min(nums, key=lambda k: nums[k])


def top_box(stock: dict[str, int], b: Box) -> str:
    return max(stock, key=lambda k: abs(stock[k] - b.base))


def top_from_item(stock: dict[str, int], bounds: list[int]) -> str:
    return max(stock, key=lambda k: abs(stock[k] - bounds[0]))


def main() -> None:
    stock: dict[str, int] = {"a": 5, "b": -3, "c": 8, "d": -1}
    print(top_name(stock, 2), low_name(stock))
    only: dict[str, int] = {"only": 0}
    zed: dict[str, int] = {"z": -7}
    print(top_name(only, 99), low_name(zed))
    nums: dict[int, int] = {5: 50, -2: 20, 9: -90, -7: 0}
    print(top_num(nums, -3), low_num(nums))
    print(top_box(stock, Box(-1)))
    print(top_from_item(stock, [0, 1]))
    alias = stock
    print(top_name(alias, 8), low_name(alias))
    empty: dict[str, int] = {}
    print(max(empty, key=lambda k: empty[k], default="none"))
    print(min(empty, key=lambda k: empty[k], default="none"))
    try:
        print(max(empty, key=lambda k: empty[k]))
    except ValueError as exc:
        print(type(exc).__name__, exc)
    try:
        print(min(empty, key=lambda k: empty[k]))
    except ValueError as exc:
        print(type(exc).__name__, exc)


main()
'''

PAIR_COMP = '''
class Box:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs


def copy_all(xs: list[int]) -> list[int]:
    return [v for i, v in enumerate(xs)]


def indices_odd(xs: list[int]) -> list[int]:
    return [i for i, v in enumerate(xs) if v % 2 != 0]


def filtered(xs: list[int]) -> list[int]:
    return [v * 2 for i, v in enumerate(xs) if i > 0 and v < 0]


def from_slice(xs: list[int]) -> list[int]:
    return [v for i, v in enumerate(xs[1:]) if v > 0]


def from_attr(b: Box) -> list[int]:
    return [v for i, v in enumerate(b.xs) if v != 0]


def main() -> None:
    xs: list[int] = [4, -1, 0, 7, -5]
    print(copy_all(xs))
    print(copy_all([]))
    print(indices_odd(xs), indices_odd([]))
    print(filtered(xs), filtered([3]))
    print(from_slice(xs), from_slice([1]))
    print(from_attr(Box(xs)), from_attr(Box([])))
    print(copy_all(list(xs)), copy_all(xs))


main()
'''

SET_LITERAL = '''
def make(a: int, b: int) -> set[int]:
    s: set[int] = {a, b}
    return s


def main() -> None:
    a = 3
    b = -3
    s: set[int] = {a, b}
    print(len(s), a in s, b in s, 4 in s)
    print(len(make(7, 7)), 7 in make(7, 7))
    t: set[int] = {a, a}
    print(len(t))
    u: set[int] = {abs(b), a + 10}
    print(len(u), 3 in u, 13 in u)
    v = make(a, b)
    v.add(3)
    print(len(v), len(s), len(make(a, b)))


main()
'''

TRIM = '''
def trim(values: list[int]) -> list[int]:
    if not values:
        return []
    min_index: int = 0
    max_index: int = 0
    for index, value in enumerate(values):
        if value < values[min_index]:
            min_index = index
        if value >= values[max_index]:
            max_index = index
    excluded: set[int] = {min_index, max_index}
    return [value for index, value in enumerate(values) if index not in excluded]


def main() -> None:
    print(trim([42, 7, 19, 88, 3, 56, 3, 91, 27, 88, 14]))
    print(trim([]))
    print(trim([5]))
    print(trim([2, 2, 2]))
    print(trim([-1, -9, 0, -9, 4, 4]))
    print(trim([0, 1]))
    src = [3, 1, 2]
    print(src, trim(src), src, trim(src))


main()
'''


def run(cmd, cwd=None, stdin=b'', env=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, env=env, timeout=900)


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class TypedReach28(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ail-prog28-')
        self.env = dict(os.environ, AIL_NO_CACHE='1', AIL_SERVER='0')
        for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
            self.env.pop(key, None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, src, name, strict=False):
        out = Path(self.tmp) / (name + ('.strict' if strict else ''))
        cmd = [sys.executable, '-B', CLI, 'compile']
        if strict:
            cmd.append('--strict')
        cmd += [str(src), '--syntax', 'python', '-o', str(out)]
        return run(cmd, Path(self.tmp), env=self.env), out

    def cases(self, task_dir):
        if task_dir is None:
            return [b'']
        base = REPO / task_dir
        return [(base / ('in%d.txt' % i)).read_bytes() for i in range(3)]

    def compare(self, src, exe, task_dir):
        for stdin in self.cases(task_dir):
            want = run([sys.executable, str(src)], Path(self.tmp), stdin=stdin)
            got = run([str(exe)], Path(self.tmp), stdin=stdin)
            self.assertEqual(got.returncode, want.returncode, stdin[:200])
            self.assertEqual(got.stdout, want.stdout, stdin[:200])

    def test_newly_typed_match_cpython(self):
        for name, rel, task in PROGRAMS:
            src = REPO / rel
            built, exe = self.build(src, name)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, task)

    def test_newly_typed_build_strict(self):
        for name, rel, task in PROGRAMS:
            if name not in NEWLY_TYPED:
                continue
            src = REPO / rel
            built, exe = self.build(src, name, strict=True)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, task)

    def test_dict_key_min_max(self):
        src = Path(self.tmp) / 'dict_key.py'
        src.write_text(DICT_KEY, encoding='utf-8')
        built, exe = self.build(src, 'dict_key', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_enumerate_pair_listcomp(self):
        src = Path(self.tmp) / 'pair_comp.py'
        src.write_text(PAIR_COMP, encoding='utf-8')
        built, exe = self.build(src, 'pair_comp', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_set_literal_from_names(self):
        src = Path(self.tmp) / 'set_literal.py'
        src.write_text(SET_LITERAL, encoding='utf-8')
        built, exe = self.build(src, 'set_literal', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_trim_variants(self):
        src = Path(self.tmp) / 'trim.py'
        src.write_text(TRIM, encoding='utf-8')
        built, exe = self.build(src, 'trim', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)


if __name__ == '__main__':
    unittest.main()
