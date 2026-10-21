"""Constructs that sent LLM-written programs to the general path, now built on the typed path (TYPED_BLOCKERS).

Each test builds a program with the typed path alone (AIL_NO_GENERAL=1) under AIL_IR=0 and AIL_IR=1 and
compares it with CPython 3.12; a shape that stays refused on the typed path is refused by name there and
the default build (the general path) prints what CPython prints.

B1  a slice of a list of str (`rest = words[1:]`, `data[1:1 + n]`, a literal step, a slice of a
    slice, inline in join and in a loop)
B2  str.join over a generator expression, over reversed(...), over map(str, reversed(...))
B3  a slice with a literal step walked by a loop, a comprehension or sum()
B4  str.ljust / rjust / center (a one-character literal or module-constant fill)
B5  str.casefold (full case folding, every code point)
B6  a list concatenated with a repeated list (`[1] + [0] * n`)
B7  objects built in a list comprehension (a constructor, a static method)
B8  __init__ with statements other than field stores (a check before the fields, a loop after them,
    `self.a, self.b = a, b`), and `list(range(n))` / `[0] * n` fields
B9  enumerate(xs, start) in a for loop (DIFFERENCES C49: the typed path counted from 0)
B10 import gc (disable / enable / collect statements)
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-typed-blockers-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, source, stdin=''):
        path = self.dir / 'cpython_main.py'
        path.write_text(source, encoding='utf-8')
        return subprocess.run([sys.executable, '-B', str(path)], input=stdin.encode(), capture_output=True, timeout=120)

    def build(self, source, ir='0', typed=False):
        entry = self.dir / 'main.py'
        entry.write_text(source, encoding='utf-8')
        exe = self.dir / ('out_ir%s_%s' % (ir, 'typed' if typed else 'default'))
        if exe.exists():
            exe.unlink()
        env = dict(os.environ, AIL_IR=ir)
        env.pop('AIL_NO_GENERAL', None)
        if typed:
            env['AIL_NO_GENERAL'] = '1'
        built = subprocess.run([sys.executable, '-B', CLI, 'compile', str(entry), '--syntax', 'python', '-o', str(exe)],
                               cwd=self.dir, capture_output=True, text=True, timeout=900, env=env)
        return built, exe

    def same(self, source, typed=False, irs=('0', '1'), stdin=''):
        """Built (on the typed path alone, or by default), the program prints what CPython prints and exits alike."""
        expected = self.cpython(source, stdin)
        for ir in irs:
            built, exe = self.build(source, ir, typed)
            self.assertEqual(built.returncode, 0, 'AIL_IR=%s: %s' % (ir, built.stderr))
            ran = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=120)
            self.assertEqual(ran.stdout.decode(), expected.stdout.decode(), 'AIL_IR=%s' % ir)
            self.assertEqual(ran.returncode, expected.returncode, 'AIL_IR=%s' % ir)
            if expected.returncode:
                last = expected.stderr.decode().strip().splitlines()[-1].split(':')[0]
                self.assertIn(last, ran.stderr.decode(), 'AIL_IR=%s' % ir)
        return expected.stdout.decode()

    def typed(self, source, stdin=''):
        return self.same(source, typed=True, stdin=stdin)

    def refused(self, source, *needles, irs=('0', '1')):
        """The typed path refuses by name (exit 3, no traceback)."""
        for ir in irs:
            built, _ = self.build(source, ir, typed=True)
            self.assertEqual(built.returncode, 3, 'AIL_IR=%s: %s' % (ir, built.stdout + built.stderr))
            self.assertNotIn('Traceback', built.stderr)
            for needle in needles:
                self.assertIn(needle, built.stderr)

    def refused_everywhere(self, source, *needles):
        """Neither path builds it: the default build is refused by name too (exit 3, no traceback)."""
        built, _ = self.build(source, '0', typed=False)
        self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
        self.assertNotIn('Traceback', built.stderr)
        for needle in needles:
            self.assertIn(needle, built.stderr)

    def both(self, source, *needles, stdin=''):
        """Refused on the typed path, and the default build prints what CPython prints."""
        self.refused(source, *needles, irs=('0',))
        return self.same(source, stdin=stdin)


STR_SLICES = '''
import sys


def tail(words: list[str]) -> str:
    rest = words[1:]
    return '|'.join(rest)


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    values = data[1:1 + n]
    print(len(values), values[0] if values else '-')
    print(' '.join(data[1 + n:]))
    print(' '.join(data[::-1]), ' '.join(data[-2:]), ' '.join(data[::2]), ' '.join(data[5:1:-2]))
    print('|'.join(data[n:-n]), '|'.join(data[-n:n]), '|'.join(data[100:]), '|'.join(data[::-3]))
    print('|'.join(data[n::-1]), '|'.join(data[:n:-2]), '|'.join(data[-100::-1]))
    names = data[1::2][:n]
    print(' '.join(names), ' '.join(data[1:][::-1][1:]))
    xs = data[1:]
    xs = xs[1:]
    print(' '.join(xs))
    ys = data
    for i in range(3):
        ys = ys[1:]
        print(len(ys), ys[0] if ys else '')
    first, second = data[:2], data[2:]
    print(len(first), len(second))
    zs = data[2:5]
    zs.append('X')
    print(len(data), ' '.join(zs))
    for w in data[1:4]:
        print(w.upper())
    for w in data[::-2]:
        print(w, end=',')
    print()
    print(tail(data))


main()
'''


class StrListSliceTests(Base):
    def test_slices_of_a_list_of_str(self):
        for stdin in ('3 a b c d e f g\nh i', '-2 a b', '0', '9 q w e r t y u i o p'):
            self.typed(STR_SLICES, stdin=stdin)

    def test_a_step_that_is_not_a_literal_stays_on_the_general_path(self):
        source = ('import sys\n\ndef main() -> None:\n    data = sys.stdin.read().split()\n'
                  '    k = len(data) - 3\n    print(" ".join(data[::k]))\n\nmain()\n')
        self.both(source, 'not an int literal', stdin='a b c d e')
        self.both(source, 'not an int literal', stdin='a b c')


JOINS = '''
import sys


def tag(x: int) -> str:
    print('tag', x)
    return '<' + str(x) + '>'


def render(row: list[int]) -> str:
    return "".join("#" if cell else "." for cell in row)


def main() -> None:
    data = sys.stdin.read().split()
    xs = [int(w) for w in data]
    print(' '.join(str(x) for x in xs))
    print(' '.join(str(x * x) for x in xs if x % 2))
    print('-'.join(tag(x) for x in xs[:3]))
    print(render([1, 0, 1, 1, 0]))
    print(' -> '.join(map(str, reversed(xs))))
    words = [w + '!' for w in data]
    print(''.join(reversed(words)), ' '.join(reversed(' '.join(data).split())))
    print('|'.join(w.upper() for w in reversed(words)))
    out = ", ".join(f"{w}={len(w)}" for w in data)
    print(out)
    print(len(''.join(str(x) for x in range(0))))


main()
'''


class JoinTests(Base):
    def test_join_over_generators_and_reversed(self):
        self.typed(JOINS, stdin='3 1 4 1 5 9 2 6')
        self.typed(JOINS, stdin='')

    def test_a_join_whose_elements_call_a_function_keeps_the_reverse_iterator(self):
        # the element calls a user function, so the comprehension over reversed() is not rewritten
        source = ('def grow(xs: list[str], w: str) -> str:\n    xs.append(w)\n    return w\n\n'
                  'def main() -> None:\n    xs = ["a", "b", "c"]\n'
                  '    print("".join([grow(xs, w) for w in reversed(xs)]))\n    print(len(xs))\n\nmain()\n')
        self.same(source)


STEPS = '''
import sys


def main() -> None:
    data = sys.stdin.read().split()
    xs = [int(w) for w in data]
    for x in xs[::-1]:
        print(x, end=' ')
    print()
    for x in xs[::2]:
        xs.append(x)
    print(len(xs))
    print(sum(x for x in xs[1::3]), ' '.join([str(x * 2) for x in xs[-2::-2]]), sum(xs[::-1]))
    s = ' '.join(data)
    print(s[::-1], s[::2], s[-1:2:-3])
    ys = xs[::-1]
    print(' '.join(map(str, ys)))
    print(' '.join([str(v) for v in xs[2::3]]))


main()
'''


class SteppedSliceTests(Base):
    def test_stepped_slices_walked(self):
        self.typed(STEPS, stdin='3 1 4 1 5 9 2 6')
        self.typed(STEPS, stdin='')

    def test_a_zero_step_raises_value_error(self):
        source = 'def main() -> None:\n    xs = [1, 2, 3]\n    for x in xs[::0]:\n        print(x)\n\nmain()\n'
        self.typed(source)
        source = 'def main() -> None:\n    xs = "a b".split()\n    for x in xs[::0]:\n        print(x)\n\nmain()\n'
        self.typed(source)


PADS = '''
import sys

FILL = "_"


def main() -> None:
    words = sys.stdin.read().split()
    for w in words:
        print('[' + w.ljust(6) + ']', '[' + w.rjust(6, '.') + ']', '[' + w.center(7, '*') + ']')
        print('[' + w.center(6) + ']', '[' + w.ljust(2) + ']', '[' + w.rjust(-3) + ']', w.center(8, 'é') + '|')
        print(f"{w.ljust(10, '-')}|{len(w.center(9))}", w.ljust(8, FILL), w.center(5, FILL))
    for width in range(0, 9):
        print('[' + 'ab'.center(width) + ']', '[' + 'abc'.center(width, '0') + ']')


main()
'''


class PadTests(Base):
    def test_ljust_rjust_center(self):
        self.typed(PADS, stdin='a bb ccc héllo 日本語 longerword')

    def test_a_fill_of_two_characters_raises_on_the_general_path(self):
        # DIFFERENCES C50: the general path padded with the first character of the fill
        source = ('import sys\n\ndef main() -> None:\n    w = sys.stdin.readline().strip()\n'
                  '    fill = sys.stdin.readline().strip()\n'
                  "    print(w.ljust(8, fill) + '|', w.rjust(9, fill) + '|', w.center(9, fill) + '|')\n"
                  '    try:\n        print(w.ljust(5, fill + fill))\n    except TypeError as e:\n'
                  "        print('TypeError', e)\n    print(w.ljust(12, 7))\n\nmain()\n")
        self.both(source, 'not in the subset', stdin='héllo\n-\n')
        self.same('def main() -> None:\n    w = "ab"\n    print(w.ljust(5, "xy"))\n\nmain()\n')


FOLD = '''
import sys


def main() -> None:
    text = sys.stdin.read()
    print(text.casefold())
    for line in text.splitlines():
        words = line.split()
        print(line.lower() == line.casefold(), ' '.join(sorted(words, key=str.casefold)))


main()
'''


class CasefoldTests(Base):
    def test_casefold(self):
        self.typed(FOLD, stdin='Straße STRASSE Hello\nΣίσυφος ΣΊΣΥΦΟΣ ﬁne ǅ İstanbul ς\nplain ascii Text\n\n')

    def test_casefold_of_every_code_point(self):
        text = ''.join(chr(c) for c in range(1, 0x110000) if not 0xD800 <= c <= 0xDFFF and c != 13)
        source = 'import sys\n\ndef main() -> None:\n    print(sys.stdin.read().casefold())\n\nmain()\n'
        self.same(source, typed=True, irs=('0',), stdin=text)


REPEATS = '''
import sys


def main() -> None:
    n = int(sys.stdin.read())
    ways = [1] + [0] * n
    print(len(ways), ways[0], sum(ways))
    dp = [0] + [10 ** 9] * n
    print(len(dp), dp[-1])
    tail = [0] * n + [7]
    print(len(tail), tail[-1])
    both = [2, 3] * 2 + [5] * n + [8] * 0
    print(len(both), sum(both))
    total = 0
    for x in [3] * n:
        total += x
    print(total)
    neg = [9] + [1] * (n - 10)
    print(len(neg))


main()
'''


class RepeatConcatTests(Base):
    def test_concatenation_with_a_repeated_list(self):
        self.typed(REPEATS, stdin='4')
        self.typed(REPEATS, stdin='0')


OBJECTS = '''
import sys


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    @staticmethod
    def parse(text: str) -> "Point":
        a, b = text.split(",")
        return Point(int(a), int(b))


def main() -> None:
    lines = sys.stdin.read().split()
    pts = [Point.parse(t) for t in lines]
    far = [Point(p.x * 2, p.y) for p in pts if p.x > 1]
    print(len(pts), len(far))
    for p in far:
        print(p.x, p.y)
    t = 'keep'
    again: list[Point] = [Point(i, i) for i in range(3)]
    print(t, sum(q.x for q in again))


main()
'''


class ObjectComprehensionTests(Base):
    def test_objects_built_in_a_comprehension(self):
        self.typed(OBJECTS, stdin='1,2 3,4 5,-6')
        self.typed(OBJECTS, stdin='')

    def test_a_bad_element_raises_part_way(self):
        self.same(OBJECTS, stdin='1,2 x,4')


CTORS = '''
import sys


class Fenwick:
    def __init__(self, values: list[int]) -> None:
        self.n = len(values)
        self.tree = [0] * (self.n + 1)
        for i, v in enumerate(values, start=1):
            self._add(i, v)

    def _add(self, i: int, delta: int) -> None:
        while i <= self.n:
            self.tree[i] += delta
            i += i & (-i)

    def prefix(self, i: int) -> int:
        s = 0
        while i > 0:
            s += self.tree[i]
            i -= i & (-i)
        return s


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            x = self.parent[x]
        return x


class Box:
    def __init__(self, w: int, h: int) -> None:
        if w < 0 or h < 0:
            raise ValueError("negative size")
        print("making", w, h)
        self.w, self.h = w, h
        self.area = w * h
        if self.area > 10:
            self.area = 10


def main() -> None:
    data = [int(x) for x in sys.stdin.read().split()]
    f = Fenwick(data)
    print(f.prefix(len(data)), f.prefix(2))
    u = UnionFind(len(data))
    print(u.find(len(data) - 1), sum(u.size))
    boxes = [Box(x, x + 1) for x in data[:3]]
    print(sum(b.area for b in boxes))
    try:
        Box(-1, 2)
    except ValueError as e:
        print("error:", e)
    b = Box(data[0], -5)
    print(b.w)


main()
'''


class ConstructorTests(Base):
    def test_statements_around_the_field_stores(self):
        self.typed(CTORS, stdin='3 1 4 1 5')
        self.typed(CTORS, stdin='-3 1')

    def test_a_class_named_other_than_in_a_call_stays_on_the_general_path(self):
        source = CTORS.replace('    f = Fenwick(data)\n', '    f = Fenwick(data)\n    print(isinstance(f, Fenwick))\n')
        self.both(source, 'must consist only of', stdin='3 1 4 1 5')


ENUMERATE = '''
import sys


def main() -> None:
    data = [int(x) for x in sys.stdin.read().split()]
    for i, v in enumerate(data, start=1):
        print(i, v)
        i = 100
    for i, v in enumerate(data, -3):
        print(i, v)
    k = 10
    words = ["a", "b"]
    for j, w in enumerate(words, k * 2):
        print(j, w)
    fl = [0.5, 1.5]
    for j, f in enumerate(fl, start=7):
        print(j, f)


main()
'''


class EnumerateStartTests(Base):
    def test_enumerate_counts_from_its_start(self):
        self.typed(ENUMERATE, stdin='7 8 9')

    def test_a_start_inside_a_fold_is_refused_by_name(self):
        source = ('def main() -> None:\n    xs = [5, 6, 7]\n'
                  '    print(sum(i * v for i, v in enumerate(xs, start=1)))\n\nmain()\n')
        self.both(source, 'enumerate() with a start')


GC = '''
import gc
import sys


def main() -> None:
    gc.disable()
    n = int(sys.stdin.read())
    total = 0
    for i in range(n):
        total += i
        if i % 2:
            gc.collect()
    gc.enable()
    print(total)


main()
'''


class GcTests(Base):
    def test_gc_statements(self):
        self.typed(GC, stdin='10')

    def test_gc_used_as_a_value_stays_on_the_general_path(self):
        # gc.isenabled() has a value; neither path models the collector's state, so both refuse by name
        source = GC.replace('    gc.enable()\n', '    gc.enable()\n    print(gc.isenabled())\n')
        self.refused(source, "import of 'gc'", irs=('0',))
        self.refused_everywhere(source, 'gc.')


if __name__ == '__main__':
    unittest.main()
