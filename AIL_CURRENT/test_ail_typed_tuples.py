"""Tuples of ints / of floats into and out of typed parallel map workers (TYPED_PARALLEL 5.2), against CPython 3.12.

`ex.map(f, xs)` / `Pool.map(f, xs)` where `f` takes a tuple[int, ...] / tuple[float, ...] parameter (read as
`t[0]`, `t[1]` or unpacked `a, b = t`) and / or returns such a tuple (`return (a, b)` as its last statement). The
tuples are frozen values: the lowering splits the argument list into one list per element before the region and
rebuilds the result tuples after it, and the worker body runs inline in the parallel loop on scalars, so no tuple
object is shared or allocated by a worker. str, bytes and lists of them are not covered (see the design note).
"""
import sys
import unittest

import test_ail_typed_parallel as tp

TUPLES = r'''
import sys
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool


def steps(args: tuple[int, int]) -> tuple[int, int]:
    n, m = args
    best = 0
    arg = n
    for k in range(n, n + m):
        x = k
        s = 0
        while x != 1:
            if x % 2 == 0:
                x = x // 2
            else:
                x = 3 * x + 1
            s += 1
        if s > best:
            best = s
            arg = k
    return (best, arg)


def area(r: tuple[float, float, float]) -> float:
    return r[0] * r[1] + r[2]


def mix(a: int, t: tuple[int, int]) -> int:
    return a * t[0] + t[1]


def main():
    w = int(sys.argv[1])
    jobs = [(1 + i * 10, 10) for i in range(40)]
    with ThreadPoolExecutor(max_workers=w) as ex:
        res = list(ex.map(steps, jobs))
        print(len(res), res[3][0], res[3][1], res[39][1])
        tot = 0
        for b, a in ex.map(steps, jobs):
            tot += b * 3 + a
        print(tot)
        rs = [(0.5 * i, 2.0, 1.0) for i in range(8)]
        print(sum(ex.map(area, rs)))
        print(sum(ex.map(mix, range(10), [(i, i + 1) for i in range(10)])))
    with Pool(w) as p:
        r = p.map(steps, [(5 + i, 7) for i in range(20)])
        print(r[0][0], len(r), r[19][1])


main()
'''

FAILS = r'''
import sys
from concurrent.futures import ThreadPoolExecutor


def inv(t: tuple[int, int]) -> tuple[int, int]:
    a, b = t
    return (1000 // (a - 70), b + 1)


def safe(n: int, w: int) -> int:
    try:
        with ThreadPoolExecutor(max_workers=w) as ex:
            return len(list(ex.map(inv, [(i, i) for i in range(n)])))
    except ZeroDivisionError:
        return -1


def main():
    w = int(sys.argv[1])
    print(safe(50, w), safe(200, w))
    with ThreadPoolExecutor(max_workers=w) as ex:
        for a, b in ex.map(inv, [(i, 1) for i in range(60, 80)]):
            print(a, b)


main()
'''

STRESS = r'''
import sys
from concurrent.futures import ThreadPoolExecutor


def mixf(t: tuple[int, int]) -> tuple[int, int]:
    i, j = t
    x = (i * 2654435761 + j) % 4294967296
    x = (x ^ (x >> 13)) * 1274126177 % 4294967296
    return (x % 1000003, (x >> 7) % 1009)


def main():
    w = int(sys.argv[1])
    acc = 0
    with ThreadPoolExecutor(max_workers=w) as ex:
        for rep in range(150):
            n = 1 + rep * 37 % 1500
            s = 0
            for a, b in ex.map(mixf, [(j, rep) for j in range(n)]):
                s = (s * 31 + a + b) % 1000000007
            acc = (acc + s) % 1000000007
    print(acc)


main()
'''


class Differential(tp.Base):
    def test_tuples_in_and_out(self):
        self.compare("tuples", TUPLES, argvs=(("1",), ("2",), ("5",), ("16",)))

    def test_exceptions(self):
        self.compare("tfails", FAILS, rc=1, argvs=(("1",), ("2",), ("16",)), runs=3)


class Stress(tp.Base):
    def test_many_rounds(self):
        self.compare("tstress", STRESS, argvs=(("1",), ("2",), ("4",), ("8",), ("16",)), runs=3)


class Sanitizers(unittest.TestCase):
    run_sanitized = tp.Sanitizers.run_sanitized

    def test_tsan(self):
        self.run_sanitized(STRESS.replace("range(150)", "range(30)"), ["-fsanitize=thread"], "tsan_tup", "8")
        self.run_sanitized(TUPLES, ["-fsanitize=thread"], "tsan_tups", "5")

    def test_asan_ubsan(self):
        flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        self.run_sanitized(TUPLES, flags, "asan_tups", "6")


class Refusals(tp.Base):
    def test_tuple_used_whole(self):
        self.refused(r'''
from concurrent.futures import ThreadPoolExecutor
def f(t: tuple[int, int]) -> int:
    s = 0
    for v in t:
        s += v
    return s
def main():
    with ThreadPoolExecutor(max_workers=2) as ex:
        print(sum(ex.map(f, [(1, 2), (3, 4)])))
main()
''', "the tuple parameter 't' is used other than as")

    def test_early_return(self):
        self.refused(r'''
from concurrent.futures import ThreadPoolExecutor
def f(t: tuple[int, int]) -> int:
    if t[0] > 1:
        return 0
    return t[1]
def main():
    with ThreadPoolExecutor(max_workers=2) as ex:
        print(sum(ex.map(f, [(1, 2), (3, 4)])))
main()
''', "returns early")

    def test_comprehension_with_effects_over_map(self):
        self.refused(r'''
from concurrent.futures import ThreadPoolExecutor
def f(x: int) -> int:
    return 10 // (x - 3)
def show(v: int) -> int:
    print(v)
    return v
def main():
    with ThreadPoolExecutor(max_workers=2) as ex:
        print(len([show(v) for v in ex.map(f, range(6))]))
main()
''', "a call inside a comprehension over executor.map")

    def test_for_over_scalar_map_prints_before_the_failure(self):
        self.compare("sfor", r'''
import sys
from concurrent.futures import ThreadPoolExecutor
def f(x: int) -> int:
    return 100 // (x - 7)
def main():
    w = int(sys.argv[1])
    with ThreadPoolExecutor(max_workers=w) as ex:
        for v in ex.map(f, range(3, 12)):
            print(v)
main()
''', rc=1, argvs=(("1",), ("4",), ("16",)))

    def test_worker_that_allocates(self):
        self.refused(r'''
from concurrent.futures import ThreadPoolExecutor
def f(t: tuple[int, int]) -> tuple[int, int]:
    xs = [t[0], t[1]]
    return (xs[0], xs[1])
def main():
    with ThreadPoolExecutor(max_workers=2) as ex:
        for a, b in ex.map(f, [(1, 2), (3, 4)]):
            print(a, b)
main()
''', "cannot run without the lock")


if __name__ == "__main__":
    unittest.main()
