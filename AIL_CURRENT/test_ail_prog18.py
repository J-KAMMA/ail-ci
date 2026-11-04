"""The hot functions of the eight prog18 programs on the typed path, against CPython 3.12.

Batch prog18 profiled eight real programs and fixed the first reason that kept each hot function
off the typed path:

- t219 (`main`, 93% of own time): the typed entry was a generated helper, not `main`.  The Python
  front end appends helpers after the script, and `_script_entry` only looked for a top-level
  expression call, so a script ending with `if __name__ == '__main__': main()` found no entry and
  `fns[-1]` stayed a helper that returns a checked str -- "the entry function cannot return
  checked str", with no position.  The guard body is searched now.
- t219 (`visited: list[tuple[int, int]] = [(x, y)]`) and any annotated container whose literal
  names numeric locals: `_numeric_expression_needed` treated `[(x, y)]` as a numeric binding,
  so `_numeric_assign` declared the list as an int and refused it.
- g11_014 (`multi_source_bfs`, 54%, and its `max` generator, 33%): `max(xs, default=d)` over a
  generator, a list, a slice or a list of lists, and the nested f-string width `f"{v:>{width}}"`.

T1  each of the six buildable programs takes the typed path (no "built on the general path" note)
T2  stdout and exit code equal CPython on the task input
T3  `max`/`min` with default=: empty and non-empty, int and float, through an argument, a list
    item, an attribute and a dict value, near-int64 values, a default with a side effect
T4  a negative width is CPython's sign option, not a padding request (`format(9, '>-5')`)
T5  the two programs that still need a big feature stay named in lab/progfix/prog18.md
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


DEFAULTS = '''
class Limits:
    def __init__(self, low: int, high: int):
        self.low = low
        self.high = high


def pick(xs: list[int], d: int) -> int:
    return max(xs, default=d)


def clamp_low(xs: list[int], lim: Limits) -> int:
    return min(xs, default=lim.low)


def tag(n: int) -> int:
    print("tag", n)
    return n


def main() -> None:
    xs: list[int] = []
    ys: list[int] = [3, 9, 2]
    print(max(xs, default=-1))
    print(min(xs, default=7))
    print(max(ys, default=-1), min(ys, default=99))
    print(max((v * 2 for v in ys), default=0))
    print(min((v - 10 for v in ys), default=0))
    zs: list[float] = []
    print(max(zs, default=-1.5))
    print(min(zs, default=2.25))
    fs: list[float] = [1.25, -0.5]
    print(max(fs, default=0.0), min(fs, default=9.0))
    print(max([9223372036854775807], default=-9223372036854775808))
    print(min([-9223372036854775807], default=9223372036854775807))
    print(max(xs, default=-9223372036854775807))
    print(max([1], default=tag(5)))
    print(max([], default=tag(6)))
    print(pick(xs, 4), pick([2, 3], 4))
    lim = Limits(-3, 8)
    print(clamp_low(xs, lim), clamp_low([1, 2], lim))
    lim.low = -9
    print(clamp_low(xs, lim))
    defaults: list[int] = [11, 12]
    print(max(xs, default=defaults[0]), min(xs, default=defaults[1]))
    d: dict[str, int] = {"a": 4, "b": 8}
    print(max(d.values(), default=0), min(d.values(), default=0))
    grid: list[list[int]] = [[1, 2], [3]]
    print(max((max(row) for row in grid), default=0))
    empty_grid: list[list[int]] = []
    print(max((max(row) for row in empty_grid), default=-2))
    print(min((v for v in ys if v > 100), default=42))
    if not xs:
        print(max(xs, default=11) + min(xs, default=12))


main()
'''

WIDTHS = '''
class Box:
    def __init__(self, w: int):
        self.w = w


def pad(v: int, w: int) -> str:
    return f"[{v:>{w}}]"


def width_of(xs: list[int]) -> int:
    return max((len(str(x)) for x in xs), default=1)


def main() -> None:
    w = 6
    print(f"[{42:>{w}}]")
    print(f"[{42:<{w}}]")
    print(f"[{42:^{w}}]")
    print(f"[{42:{w}}]")
    print(f"[{-42:>{w}}]")
    print(f"[{42:0>{w}}]")
    print(f"[{42:*>{w}}]")
    print(f"[{42:>{w}d}]")
    print(f"[{42:>{0}}]")
    print(f"['{ 'ab' :>{w}}']")
    print(f"['{ 'ab' :*>{w}}']")
    print(f"[{3.14159:>{w}.2f}]")
    print(f"[{3.14159:^{w}.1f}]")
    print(f"[{3.14159:>{w}}]")
    print(pad(7, 4))
    widths: list[int] = [1, 4, 8]
    for q in widths:
        print(f"({q:>{q}})")
    print(f"[{9:>{widths[0]}}]", f"[{9:>{widths[2]}}]")
    box = Box(5)
    print(f"[{9:>{box.w}}]")
    box.w = 2
    print(f"[{9:>{box.w}}]")
    values: dict[str, int] = {"w": 5}
    print(f"[{9:>{values['w']}}]")
    print(f"[{9:>{w + 1}}]")
    print(f"[{9:>{len(widths)}}]")
    print(f"[{9:>{-1}}]", f"[{9:>{-5}}]", f"[{-9:>{-5}}]")
    print(f"[{9:<{-5}}]", f"[{9:^{-5}}]")
    print(f"[{9:>{-5}d}]")
    print(f"[{3.5:>{-6}.2f}]", f"[{-3.5:<{-7}.1f}]")
    for bad in (-1, -5):
        try:
            print(f"['ab':>{bad}]")
        except ValueError as e:
            print("ValueError", type(e).__name__)
    w = 3
    print(f"[{9:>{w}}][{9:>{w}}]")
    print(width_of([1, 22, 333]), width_of([]))


main()
'''

CONTAINERS = '''
class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y


def walk(dx: int, dy: int) -> None:
    x, y = 0, 0
    visited: list[tuple[int, int]] = [(x, y)]
    for _ in range(3):
        x += dx
        y += dy
        visited.append((x, y))
    print(visited)
    print(visited[:2])


def points(xs: list[int]) -> None:
    pts: list[Point] = [Point(v, v * 2) for v in xs]
    print(len(pts), pts[0].x)


def main() -> None:
    walk(1, 2)
    walk(-3, 0)
    points([1, 2, 3])
    empty: list[tuple[int, int]] = []
    print(empty)
    first = [(4, 5)]
    print(first)


main()
'''

ENTRY_GUARD = '''
def total(xs: list[int]) -> int:
    return sum(xs)


def main() -> None:
    data: list[int] = [4, 7]
    print(total(data))
    trail: list[tuple[int, str]] = [(1, "a"), (2, "b")]
    print(trail)
    print(trail[:1])


if __name__ == "__main__":
    main()
'''


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog18(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog18_')

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

    def check_probe(self, text, name):
        exe, source = self.build(text, name)
        self.same(exe, source)

    def lab(self, *parts):
        return REPO.joinpath('lab', *parts)

    def corpus_input(self, task):
        path = self.lab('corpus', 'tasks', task, 'in2.txt')
        if not path.exists():
            self.skipTest('corpus input is not in this tree')
        return path.read_text(encoding='utf-8')

    def test_t219_whole_program_typed(self):
        path = self.lab('corpus', 'programs', 'deepseek-v4.1-flash-free', 't219.py')
        if not path.exists():
            self.skipTest('lab corpus program is not in this tree')
        exe, source = self.build(path.read_text(encoding='utf-8'), 't219')
        self.same(exe, source, self.corpus_input('t219'))

    def test_g11_014_whole_program_typed(self):
        path = self.lab('census', 'programs', 'gdev', 'g11_014.py')
        if not path.exists():
            self.skipTest('lab census program is not in this tree')
        exe, source = self.build(path.read_text(encoding='utf-8'), 'g11_014')
        self.same(exe, source)

    def test_entry_guard_typed(self):
        exe, source = self.build(ENTRY_GUARD, 'entry_guard')
        self.same(exe, source)

    def test_annotated_container_literal_typed(self):
        exe, source = self.build(CONTAINERS, 'containers')
        self.same(exe, source)

    def test_max_min_default_typed(self):
        exe, source = self.build(DEFAULTS, 'defaults')
        self.same(exe, source)

    def test_nested_width_typed(self):
        exe, source = self.build(WIDTHS, 'widths')
        self.same(exe, source)

    def test_str_default_refused_by_name(self):
        res, _, _ = compile_default(self.tmp, 'def main() -> None:\n'
                                    '    xs: list[str] = ["a"]\n'
                                    '    print(max(xs, default="z"))\n\n\nmain()\n', 'refuse_str')
        self.assertIn('max() requires numeric elements', res.stderr)

    def test_float_width_refused_by_name(self):
        res, _, _ = compile_default(self.tmp, 'def main() -> None:\n'
                                    '    print(f"[{9:>{2.5}}]")\n\n\nmain()\n', 'refuse_width')
        self.assertIn('nested format-spec field has to be an int', res.stderr)

    def test_report(self):
        path = self.lab('progfix', 'prog18.md')
        if not path.exists():
            self.skipTest('lab/progfix/prog18.md is not in this tree')
        text = path.read_text(encoding='utf-8')
        for name in ('t391.py', 'g19_014.py'):
            self.assertIn(name, text)


if __name__ == '__main__':
    unittest.main()
