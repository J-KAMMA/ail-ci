"""Optional locals without an annotation (python/pkg-v12/optlib.py `annotate_none_locals`), against CPython 3.12.

`x = None` and, in the same function, `x = <one scalar kind>` (int, float, str, bool, told from constants,
annotated parameters, loops over annotated lists, builtin calls and arithmetic): the first binding is
annotated `x: <kind> | None` and the Optional lowering takes it on the typed path.

O1  fixed programs: best-so-far, first match, a label set in one branch, `if x:` / `is None` / `is not None`,
    printing a None: the typed path alone (AIL_IR=0 and 1) and the general path print what CPython prints.
O2  a use the lowering cannot prove present (`x + 1` where x may be None) is refused by name on the typed
    path and built on the general path with CPython's output (TypeError).
O3  random functions over random int lists: CPython == typed path (IR 0 and 1) == general path.
"""
import os
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from test_ail_nested_functions import build, build_general, run_cpython, run_exe   # noqa: E402

HAVE_CC = shutil.which('gcc') is not None
SEEDS = int(os.environ.get('AIL_OPTIONAL_SEEDS', '10'))

FIXED = '''def best_of(xs: list[int]) -> int:
    best = None
    for v in xs:
        if best is None or v > best:
            best = v
    if best is None:
        return -1
    return best


def first_word(words: list[str]) -> str:
    found = None
    for w in words:
        if len(w) > 3:
            found = w
            break
    if found:
        return found
    return "none"


def mean(xs: list[float]) -> float:
    total = None
    for x in xs:
        total = x if total is None else total + x
    return 0.0 if total is None else total / len(xs)


def main() -> None:
    print(best_of([3, 9, 2]), best_of([]))
    print(first_word(["a", "tree", "forest"]), first_word(["a"]))
    print(mean([1.5, 2.5]), mean([]))
    x = None
    for i in range(5):
        if i == 3:
            x = i * 10
    if x is not None:
        print("x", x + 1)
    label = None
    if x and x > 5:
        label = "big"
    print(label)
    other = None
    print(other, other is None)
    seen = None
    for i in range(3):
        if i == 1:
            seen = True
    print(seen, not seen)
    ratio = None
    ratio = 2.5
    print(ratio is None, ratio)


main()
'''

MAYBE = '''def main() -> None:
    x = None
    for i in range(3):
        if i > 5:
            x = i
    try:
        print(x + 1)
    except TypeError:
        print("TypeError")


main()
'''


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Fixed(unittest.TestCase):
    def test_typed_and_general_paths(self):
        with tempfile.TemporaryDirectory(prefix='ail-opt-') as tmp:
            want = run_cpython(tmp, FIXED, 'fixed')
            self.assertEqual(want.returncode, 0, want.stderr)
            for ir in ('0', '1'):
                res, exe = build(tmp, FIXED, 'fixed', ir=ir)
                self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout), 'IR=%s' % ir)
            res, exe = build_general(tmp, FIXED, 'fixed')
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            got = run_exe(exe)
            self.assertEqual((got.returncode, got.stdout), (0, want.stdout))

    def test_a_use_that_may_be_none_is_refused_on_the_typed_path(self):
        with tempfile.TemporaryDirectory(prefix='ail-opt-') as tmp:
            res, _ = build(tmp, MAYBE, 'maybe')
            self.assertEqual(res.returncode, 3, res.stderr)
            self.assertIn('may be None', res.stderr)
            want = run_cpython(tmp, MAYBE, 'maybe')
            res, exe = build(tmp, MAYBE, 'maybe', typed_only=False)
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            got = run_exe(exe)
            self.assertEqual(got.stdout, want.stdout)


SLOTS = """from heapq import heappush, heappop


def main() -> None:
    wait = [None, [], [], []]
    print(wait)
    print(wait[0] is None, wait[1] is None, wait[2] is not None, wait[3] is not None)
    w1, w2, w3 = wait[1], wait[2], wait[3]
    heappush(w1, 5)
    heappush(w2, 3)
    heappush(wait[3], 9)
    print(w1, w2, w3, wait)
    heappush(wait[1], 1)
    a = heappop(w1)
    b = heappop(w2)
    d = heappop(w3)
    print(w1, wait[1], a, b, d)
    print(wait)


main()
"""

ABSENT = """def main() -> None:
    wait = [None, [], [], []]
    print("before")
    print(len(wait[0]))
    print("after")


main()
"""

ABSENT_DYNAMIC = """from heapq import heappush


def main() -> None:
    wait = [None, [], []]
    i = 0
    print("go")
    heappush(wait[i], 1)
    print("no")


main()
"""

PLAIN_READ = """def main() -> None:
    wait = [None, [], [], []]
    x = wait[0]
    print(x)
    print(wait[2])


main()
"""

# Whole-list uses of a lowercased `[None, [], ...]` would see the stand-in `[]` where CPython has None, or
# would desynchronise the present bits.  Each is refused by name on the typed path and matches CPython on
# the general path.
WHOLE_USE = {
    'iter': """def main() -> None:
    wait = [None, [], [1], [2]]
    for w in wait:
        print(w)


main()
""",
    'iter_mut': """def main() -> None:
    wait = [None, [], []]
    for w in wait:
        w.append(1)
    print(wait)


main()
""",
    'unpack': """def main() -> None:
    wait = [None, [5], [6]]
    a, b, c = wait
    print(a, b, c)


main()
""",
    'argument': """def show(rows: list) -> None:
    print(rows, len(rows))


def main() -> None:
    wait = [None, [], [1, 2]]
    show(wait)


main()
""",
    'append': """def main() -> None:
    wait = [None, []]
    wait.append([7])
    print(wait, len(wait), wait[2] is None)


main()
""",
    'sort': """def main() -> None:
    wait = [None, [1], [2]]
    wait.sort()
    print(wait)


main()
""",
    'iadd': """def main() -> None:
    wait = [None, [1]]
    wait += [[2]]
    print(wait)


main()
""",
    'slice': """def main() -> None:
    wait = [None, [1], [2]]
    print(wait[:], wait[1:])


main()
""",
}

GUARDED = """def main() -> None:
    best = None
    w2 = [7, 4]
    if best is None or w2[0] < best:
        print("first")
    best = w2[0]
    if best is None or w2[1] < best:
        print("second", best)
    other = None
    if other is not None and other > 0:
        print("no")
    other = 3
    if other is not None and other > 0:
        print("yes", other)
    w1 = [5, 1]
    w2 = [3]
    best = None
    if w1:
        best = w1[0]
        bw = w1
    if w1 and (best is None or w1[0] < best):
        best = w1[0]
        bw = w1
    if w2 and (best is None or w2[0] < best):
        best = w2[0]
        bw = w2
    if best is None:
        return
    print(best, bw)
    x = None
    for i in range(5):
        if i == 3:
            x = i
        if x is None:
            break
        print("x", x)


main()
"""


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class NoneSlots(unittest.TestCase):
    def test_none_slots_and_row_aliases(self):
        with tempfile.TemporaryDirectory(prefix='ail-opt-slots-') as tmp:
            want = run_cpython(tmp, SLOTS, 'slots')
            self.assertEqual(want.returncode, 0, want.stderr)
            for ir in ('0', '1'):
                res, exe = build(tmp, SLOTS, 'slots', ir=ir)
                self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout), 'IR=%s' % ir)
            res, exe = build_general(tmp, SLOTS, 'slots')
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            got = run_exe(exe)
            self.assertEqual((got.returncode, got.stdout), (0, want.stdout))

    def test_absent_slot_read_exits_one_with_cpython_stdout(self):
        with tempfile.TemporaryDirectory(prefix='ail-opt-absent-') as tmp:
            want = run_cpython(tmp, ABSENT, 'absent')
            self.assertEqual(want.returncode, 1, want.stderr)
            for ir in ('0', '1'):
                res, exe = build(tmp, ABSENT, 'absent', ir=ir)
                self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                got = run_exe(exe)
                self.assertEqual(got.returncode, 1, 'IR=%s' % ir)
                self.assertEqual(got.stdout, want.stdout, 'IR=%s' % ir)
            res, exe = build_general(tmp, ABSENT, 'absent')
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            got = run_exe(exe)
            self.assertEqual((got.returncode, got.stdout), (1, want.stdout))

    def test_or_and_narrowing_and_guarded_binding(self):
        with tempfile.TemporaryDirectory(prefix='ail-opt-guard-') as tmp:
            want = run_cpython(tmp, GUARDED, 'guarded')
            self.assertEqual(want.returncode, 0, want.stderr)
            for ir in ('0', '1'):
                res, exe = build(tmp, GUARDED, 'guarded', ir=ir)
                self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout), 'IR=%s' % ir)
            res, exe = build_general(tmp, GUARDED, 'guarded')
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            got = run_exe(exe)
            self.assertEqual((got.returncode, got.stdout), (0, want.stdout))

    def test_dynamic_absent_slot_read_exits_one(self):
        with tempfile.TemporaryDirectory(prefix='ail-opt-dyn-') as tmp:
            want = run_cpython(tmp, ABSENT_DYNAMIC, 'dyn')
            self.assertEqual(want.returncode, 1, want.stderr)
            for ir in ('0', '1'):
                res, exe = build(tmp, ABSENT_DYNAMIC, 'dyn', ir=ir)
                self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                got = run_exe(exe)
                self.assertEqual(got.returncode, 1, 'IR=%s' % ir)
                self.assertEqual(got.stdout, want.stdout, 'IR=%s' % ir)
            res, exe = build_general(tmp, ABSENT_DYNAMIC, 'dyn')
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            got = run_exe(exe)
            self.assertEqual((got.returncode, got.stdout), (1, want.stdout))

    def test_plain_slot_read_falls_back_and_matches(self):
        with tempfile.TemporaryDirectory(prefix='ail-opt-plain-') as tmp:
            want = run_cpython(tmp, PLAIN_READ, 'plain')
            self.assertEqual(want.returncode, 0, want.stderr)
            for ir in ('0', '1'):
                res, exe = build(tmp, PLAIN_READ, 'plain', ir=ir, typed_only=False)
                self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout), 'IR=%s' % ir)

    def test_whole_list_uses_are_refused_by_name(self):
        self.maxDiff = None
        for name in sorted(WHOLE_USE):
            text = WHOLE_USE[name]
            with tempfile.TemporaryDirectory(prefix='ail-opt-whole-') as tmp:
                want = run_cpython(tmp, text, 'whole')
                res, _ = build(tmp, text, 'whole')
                self.assertEqual(res.returncode, 3, '%s: %s' % (name, res.stderr[-2000:]))
                self.assertIn('only read slot by slot', res.stderr, name)
                res, exe = build(tmp, text, 'whole', typed_only=False)
                self.assertEqual(res.returncode, 0, '%s: %s' % (name, res.stderr[-2000:]))
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout), name)


def gen_program(seed):
    rng = random.Random(seed)
    lines = []
    calls = []
    for k in range(rng.randint(2, 4)):
        kind = rng.choice(['int', 'str', 'float', 'bool'])
        name = 'f%d' % k
        cond = rng.choice(['v %% %d == %d' % (rng.randint(2, 4), rng.randint(0, 1)), 'v > %d' % rng.randint(0, 8),
                           'v < %d' % rng.randint(1, 5)])
        value = {'int': rng.choice(['v', 'v * 2 - 1', 'len(xs) + v']),
                 'str': rng.choice(['str(v)', '"v" + str(v)']),
                 'float': rng.choice(['v / 2', 'v * 1.5']),
                 'bool': rng.choice(['v > 3', 'True'])}[kind]
        mode = rng.choice(['first', 'last', 'fold'])
        lines.append('def %s(xs: list[int]) -> str:' % name)
        lines.append('    acc = None')
        lines.append('    for v in xs:')
        lines.append('        if %s:' % cond)
        if mode == 'first':
            lines.append('            if acc is None:')
            lines.append('                acc = %s' % value)
        elif mode == 'last':
            lines.append('            acc = %s' % value)
        else:
            if kind in ('int', 'float'):
                lines.append('            acc = %s if acc is None else acc + %s' % (value, value))
            else:
                lines.append('            acc = %s' % value)
        lines.append('    if acc is None:')
        lines.append('        return "none"')
        lines.append('    return str(acc)')
        lines.append('')
        lines.append('')
        calls.append(name)
    lines.append('def main() -> None:')
    for _ in range(6):
        xs = [rng.randint(0, 9) for _ in range(rng.randint(0, 6))]
        for c in calls:
            lines.append('    print(%s(%r))' % (c, xs))
    lines += ['', '', 'main()', '']
    return '\n'.join(lines)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Random(unittest.TestCase):
    def test_random_programs(self):
        with tempfile.TemporaryDirectory(prefix='ail-opt-rand-') as tmp:
            for seed in range(SEEDS):
                text = gen_program(seed)
                name = 'o%d' % seed
                with self.subTest(seed=seed):
                    want = run_cpython(tmp, text, name)
                    self.assertEqual(want.returncode, 0, want.stderr + text)
                    for ir in ('0', '1'):
                        res, exe = build(tmp, text, name, ir=ir)
                        self.assertEqual(res.returncode, 0, 'seed %d IR=%s: %s\n%s' % (seed, ir, res.stderr[-1500:], text))
                        got = run_exe(exe)
                        self.assertEqual(got.stdout, want.stdout, 'seed %d IR=%s\n%s' % (seed, ir, text))
                    res, exe = build_general(tmp, text, name)
                    self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                    got = run_exe(exe)
                    self.assertEqual(got.stdout, want.stdout, 'seed %d general\n%s' % (seed, text))


if __name__ == '__main__':
    unittest.main()
