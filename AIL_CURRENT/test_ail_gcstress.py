"""GC-stress mode for the general (boxed) path (DIFFERENCES C84, branch gcroots).

The general runtime is a precise mark-and-sweep collector: only shadow-stack frame slots, the pending exception and
the builtin classes are roots. A runtime helper that keeps an object it allocated (a result list being filled, an
iterator, a key, a str whose text it copies after allocating the result) only in a C local loses it to a collection
inside the next allocation. With the normal 8 MiB threshold that is rare, so it shows only as an occasional
use-after-free; with `-DAIL_GC_STRESS` the runtime collects at EVERY allocation, and AddressSanitizer reports the
first use of anything freed.

Each program below is built with pyc.py --general-only and AIL_EXTRA_CFLAGS='-fsanitize=address,undefined
-DAIL_GC_STRESS', run, and compared with CPython (stdout and exit status); a sanitizer report fails the test. The
programs exercise the helpers the 2026-10-20 sweep found (dict.items, enumerate, itertools combinatorics, sorting
with tuple keys, str case mapping in a lambda, float tuple literals, ...) and the rest of the audited runtime
(collections, heapq with a user __lt__, copy.deepcopy, statistics, str.format / % formatting, generators).
Skipped when gcc has no sanitizers.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = str(ROOT / 'python' / 'pkg-v12' / 'pyc.py')
HAVE_CC = shutil.which('gcc') is not None
SAN = ['-fsanitize=address,undefined', '-fno-sanitize-recover=undefined', '-g', '-fno-omit-frame-pointer']

PROGRAMS = {
    'dicts_and_iterators': r'''
def main() -> None:
    d = {"b": 2, "a": 3, "c": 1, "d": 3}
    for k, v in d.items():
        print(k, v)
    items = d.items()
    print(sorted(items, key=lambda kv: (-kv[1], kv[0])))
    print(sorted(d, key=lambda k: (d[k], k)))
    print(list(enumerate("xyz", 1)))
    print(list(zip([1, 2, 3], "abc")))
    print(list(map(lambda s: s + "!", ["p", "q"])))
    print(list(filter(None, [0, 1, "", "a", None, 2.5])))
    print(list(reversed([1.5, 2.5])))
    pairs = [(i, str(i) * 2) for i in range(5)]
    print(dict(pairs))
    print(dict(zip("ab", [[1], [2]])))
    print([(k, v) for k, v in sorted({"x": 1.5, "y": 0.5}.items(), key=lambda t: t[1])])
    print(max(d.items(), key=lambda kv: (kv[1], kv[0])), min(["bb", "a", "ccc"], key=len))
    it = iter([3, 1, 2])
    print(next(it), list(it))
    print(sum(x * 0.5 for x in range(6)), any(x > 4 for x in range(6)), all([1, 1.0, "a"]))
    print(dict.fromkeys("abc", 0), sorted({3, 1, 2}))


main()
''',
    'itertools': r'''
import itertools


def main() -> None:
    print(list(itertools.combinations("abcd", 2)))
    print(list(itertools.permutations([1, 2, 3])))
    print(list(itertools.product("ab", [1.5, 2.5])))
    print(list(itertools.product([0, 1], repeat=3)))
    print(list(itertools.combinations_with_replacement("ab", 2)))
    print(list(itertools.chain([1, 2], (3.5, "x"))))
    print(list(itertools.islice(itertools.count(5), 2, 8, 2)))
    print(list(itertools.accumulate([1.5, 2.5, 3.0])))
    print([(k, list(g)) for k, g in itertools.groupby("aabbbc")])
    print(list(itertools.zip_longest("ab", [1.0, 2.0, 3.0], fillvalue="-")))
    print(list(itertools.pairwise("abcd")))
    print(list(itertools.islice(itertools.cycle(["p", "q"]), 5)))
    print(list(itertools.takewhile(lambda x: x < 3, [1, 2, 3, 1])))
    print(list(itertools.dropwhile(lambda x: x < 3, [1, 2, 3, 1])))
    print(list(itertools.starmap(lambda a, b: a * b, [(1, 2.5), (3, 4)])))


main()
''',
    'print_options': r'''
class C:
    def __init__(self) -> None:
        self.sep = None
        self.end = None


def show(sep, end) -> None:
    print("a", "b", sep=sep, end=end)


def main() -> None:
    print("x" * 100, "y" * 100, sep=None, end=None)
    print("x", "y", sep=None)
    print("x", "y", end=None)
    s = None
    e = None
    show(s, e)
    xs = [None, "-"]
    print("x", "y", sep=xs[0], end=xs[0])
    d = {"s": None}
    print("x", "y", sep=d["s"], end=d["s"])
    c = C()
    print("x", "y", sep=c.sep, end=c.end)
    print(*[], sep=None, end=None)
    print("done")


main()
''',
    'strings': r'''
def main() -> None:
    words = ["Éclair", "straße", "ΣΊΣΥΦΟΣ", "plain", "MiXeD"]
    print(sorted(words, key=lambda w: w.lower()))
    print([w.upper() for w in words])
    print("a=b=c".partition("="), "a=b=c".rpartition("="), "abc".partition("x"), "abc".rpartition("x"))
    print("a b  c ".rsplit(), "a,b,,c".rsplit(",", 1), "x\ny\r\nz".splitlines())
    print("%s and %r and %5.2f and %d%%" % ("s", "r", 3.14159, 42))
    print("-".join(str(i) for i in range(5)), "".join(["ab", "cd"]))
    print("hello".replace("l", "L"), "hello".replace("l", "", 1), "ab".center(7, "*"), "7".zfill(4))
    print(repr("quote's"), repr('tab\there'), repr("ünï"), "x" * 3, "ab" + "cd")
    print(f"{1.5:.3f} {'pad':>6} {12345:,} {[1, 2]!r}")
    print("Hello World".swapcase(), "hello world".title(), "hELLO".capitalize())
    print("a\tb".expandtabs(4), "abc".ljust(5, "."), "abc".rjust(5))
    print([c for c in "héllo" if c.isalpha()], "ab12".isalnum(), "  ".isspace())
    print(str(3.5), str([1, (2, "x")]), str({"k": None}))
    try:
        [1, 2].index(9)
    except ValueError as e:
        print("ValueError", e)


main()
''',
    'collections_heapq_copy': r'''
import heapq
from collections import Counter, defaultdict, deque


class Job:
    def __init__(self, prio, name):
        self.prio = prio
        self.name = name

    def __lt__(self, other):
        return (self.prio, self.name) < (other.prio, other.name)

    def __repr__(self):
        return "Job(" + str(self.prio) + ", " + self.name + ")"


def main() -> None:
    c = Counter("abracadabra")
    c.update("aaz")
    print(c.most_common(3), sorted(c.items()))
    print(sorted(Counter([1.5, 1.5, 2.5]).items()))
    dd = defaultdict(list)
    for i, w in enumerate("one two three four".split()):
        dd[len(w)].append((i, w))
    print(sorted(dd.items()))
    q = deque([1, 2])
    q.extend([3.5, "x"])
    q.appendleft(0)
    print(list(q), q.popleft(), q.pop())
    h = []
    for p, n in [(3, "c"), (1, "a"), (2, "b"), (1, "z")]:
        heapq.heappush(h, Job(p, n))
    print([heapq.heappop(h) for _ in range(len(h))])
    t = [(5, "e"), (1, "a"), (3, "c")]
    heapq.heapify(t)
    print(heapq.heappop(t), heapq.heappushpop(t, (2, "b")), heapq.heapreplace(t, (9, "z")), sorted(t))
    print(heapq.nlargest(2, [(1, "a"), (3, "c"), (2, "b")], key=lambda p: p[0]), heapq.nsmallest(2, "dacb"))


main()
''',
    'numbers_and_stats': r'''
def gen(n):
    for i in range(n):
        yield i * 1.5


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


def main() -> None:
    pts = [(0.5, 1.5), (2.5, 3.5), (1.0, -1.0)]
    print(pts, sorted(pts, key=lambda p: (p[1], p[0])))
    print(divmod(7.5, 2), divmod(-7, 2), mean(gen(6)), sorted(gen(4), reverse=True))
    print(min((3.5, "b"), (1.5, "a")), max([2.5, 1.5, 9.5]), float("2.25"), int(" 42 "))
    print([float(i) / 3 for i in range(4)], round(2.675, 2), abs(-1.5), 2 ** 0.5, 7 // 2.0)
    print({1.5: "a", 2.5: "b"}, sorted({0.25, 0.5, 0.125}), (1.5,) * 3, [0.5] * 2 + [1.5])
    grid = [[float(r * c) for c in range(3)] for r in range(3)]
    print(grid, [sum(row) for row in grid], list(zip(*grid)))


main()
''',
    'classes_generators_exceptions': r'''
from functools import reduce


class Countdown:
    def __init__(self, n):
        self.n = n

    def __iter__(self):
        return self

    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return (self.n, str(self.n) * 2)


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return "Point(" + repr(self.x) + ", " + repr(self.y) + ")"


class AppError(Exception):
    pass


def squares(n):
    for i in range(n):
        yield (i, i * i * 0.5)


def main() -> None:
    print(list(Countdown(3)), [p for p in squares(4)])
    print(sorted([Point(2.5, "b"), Point(1.5, "a")], key=lambda p: (p.x, p.y)))
    print(reduce(lambda acc, x: acc + [x * 1.5], [1, 2, 3], []), reduce(lambda a, b: a + b, ["x", "y", "z"]))
    try:
        raise AppError("bad", 3.5)
    except AppError as e:
        print("AppError", e.args)
    try:
        {"a": 1}["zz"]
    except KeyError as e:
        print("KeyError", e)
    a = [1]
    h = [a, a]
    h[1] += [3]
    d = {"k": [1]}
    alias = d["k"]
    d["k"] += [4.5]
    print(a, h, alias)
    ws = "p q".split()
    ws.append(7)
    for w in ws:
        try:
            print(w.upper(), w.find("q"))
        except AttributeError as e:
            print("AttributeError", e)


main()
''',
}


def _sanitizers_work():
    if not HAVE_CC:
        return False
    with tempfile.TemporaryDirectory(prefix='ail-san-') as d:
        c = Path(d, 't.c')
        c.write_text('int main(void){return 0;}\n')
        r = subprocess.run(['gcc'] + SAN + [str(c), '-o', str(Path(d, 't'))], capture_output=True)
        return r.returncode == 0 and subprocess.run([str(Path(d, 't'))], capture_output=True).returncode == 0


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


@unittest.skipUnless(HAVE_CC and _sanitizers_work(), 'no C compiler with sanitizers')
class GCStress(unittest.TestCase):
    """Every program, collecting at every allocation under ASan + UBSan, prints what CPython prints."""

    def check(self, name):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory(prefix='ail-gcstress-') as directory:
            want = _cpython(directory, name, text)
            self.assertEqual(want[1], 0, 'the program itself fails in CPython')
            src = Path(directory) / (name + '.py')
            src.write_text(text, encoding='utf-8')
            exe = Path(directory) / ('exe_' + name)
            env = dict(os.environ, AIL_SURFACE='python', AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1',
                       AIL_EXTRA_CFLAGS=' '.join(SAN + ['-DAIL_GC_STRESS']))
            env.pop('AIL_NO_GENERAL', None)
            built = subprocess.run([sys.executable, '-B', PYC, str(exe), '--file', str(src), '--general-only'],
                                   cwd=directory, capture_output=True, text=True, timeout=900, env=env)
            self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-1500:])
            c = Path(directory, 'exe_%s.c' % name).read_text(encoding='utf-8')
            self.assertIn('#ifdef AIL_GC_STRESS', c)
            run_env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:detect_stack_use_after_return=0',
                           UBSAN_OPTIONS='halt_on_error=1')
            got = subprocess.run([str(exe)], capture_output=True, timeout=600, cwd=directory, env=run_env)
            err = got.stderr.decode('utf-8', 'replace')
            self.assertNotIn('Sanitizer', err, err[-2500:])
            self.assertNotIn('runtime error', err, err[-2500:])
            self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), want, err[-1500:])

    def test_dicts_and_iterators(self):
        self.check('dicts_and_iterators')

    def test_itertools(self):
        self.check('itertools')

    def test_strings(self):
        self.check('strings')

    def test_print_options(self):
        self.check('print_options')

    def test_collections_heapq_copy(self):
        self.check('collections_heapq_copy')

    def test_numbers_and_stats(self):
        self.check('numbers_and_stats')

    def test_classes_generators_exceptions(self):
        self.check('classes_generators_exceptions')


class StressSwitch(unittest.TestCase):
    """The switch costs nothing in a normal build: the collector's test is unchanged without -DAIL_GC_STRESS."""

    def test_default_threshold_kept(self):
        sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
        try:
            import cruntime
        finally:
            sys.path.pop(0)
        text = cruntime.SOURCE['OBJ2'] if 'OBJ2' in cruntime.SOURCE else cruntime.OBJ2
        self.assertIn('#ifndef AIL_GC_INITIAL_THRESHOLD\n#define AIL_GC_INITIAL_THRESHOLD (8u * 1024u * 1024u)\n#endif', text)
        self.assertIn('if (cx->gc_bytes + incoming > cx->gc_threshold) ail_gc_collect(cx);', text)


if __name__ == '__main__':
    unittest.main()
