"""executor.submit / Future.result without the GIL (docs/design/TYPED_PARALLEL.md 5.1), compared with CPython 3.12.

Lowered by typedpar.py onto the region `map` uses: `futs = [ex.submit(f, ...) for v in xs]` (or a list made in a loop,
or consecutive `f1 = ex.submit(f, ...)` statements), then futures read only as `fu.result()` in a for / comprehension
over the list or `as_completed(list)`. If a task raised, each `.result()` runs its task again on the calling thread, in
order, so the exception arrives where CPython raises it, after the results before it were used.

Every program is built with the typed path alone and run at 1..16 workers (argv); stdout and exit status are
CPython's. Also: stress, ThreadSanitizer (setarch -R) and ASan/UBSan on the typed C, the refusals with their notes,
and the C of programs that do not use it.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_ail_typed_parallel as tp

SUBMITS = r'''
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed


def steps(n: int) -> int:
    s = 0
    x = n
    while x != 1:
        if x % 2 == 0:
            x = x // 2
        else:
            x = 3 * x + 1
        s += 1
    return s


def scale(x: float, k: int) -> float:
    return x * 1.5 + k


def main():
    w = int(sys.argv[1])
    with ThreadPoolExecutor(max_workers=w) as ex:
        futs = [ex.submit(steps, k + 1) for k in range(60)]
        rs = [f.result() for f in futs]
        print(len(rs), rs[7], sum(rs))
        print(sum(f.result() for f in as_completed(futs)), len(futs))
        print(max(f.result() * 2 for f in futs))
        total = 0
        for f in as_completed(futs):
            total += f.result()
        print(total)
        f1 = ex.submit(steps, 27)
        f2 = ex.submit(steps, 97)
        print(f1.result() + f2.result(), f2.result())
        xs = [0.5, 1.5, 2.5, 3.5]
        gs = []
        for j in range(len(xs)):
            gs.append(ex.submit(scale, xs[j], j))
        for g in gs:
            print(g.result())
        hs = [ex.submit(steps, v * v) for v in range(3, 9)]
        out = 0
        for h in hs:
            out = out * 3 + h.result()
        print(out)
    ex2 = ThreadPoolExecutor(max_workers=w)
    one = ex2.submit(steps, 871)
    print(one.result())
    ex2.shutdown()


main()
'''

MODULE_SPELLING = r'''
import sys
import concurrent.futures as cf


def sq(x: int) -> int:
    return x * x + 1


w = int(sys.argv[1])
with cf.ThreadPoolExecutor(w) as pool:
    fs = [pool.submit(sq, i) for i in range(1, 40)]
    acc = 0
    for fu in cf.as_completed(fs):
        acc += fu.result()
    print(acc, len(fs))
    print(sorted([fu.result() for fu in fs])[5])
'''

FAILS = r'''
import sys
from concurrent.futures import ThreadPoolExecutor


def inv(x: int) -> int:
    return 1000 // (x - 70)


def total(n: int, w: int) -> int:
    with ThreadPoolExecutor(max_workers=w) as ex:
        futs = [ex.submit(inv, i) for i in range(n)]
        try:
            return sum(f.result() for f in futs)
        except ZeroDivisionError:
            return -1


def main():
    w = int(sys.argv[1])
    print(total(50, w), total(200, w), total(3000, w))
    with ThreadPoolExecutor(max_workers=w) as ex:
        futs = [ex.submit(inv, i) for i in range(60, 100)]
        seen = 0
        for f in futs:
            try:
                print(f.result())
            except ZeroDivisionError:
                print("zero")
            seen += 1
        print(seen)
        a = ex.submit(inv, 69)
        b = ex.submit(inv, 70)
        c = ex.submit(inv, 71)
        print(a.result())
        print(c.result())
        print(b.result())
        print("not reached")


main()
'''

STRESS = r'''
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed


def mixf(i: int) -> int:
    x = i * 2654435761 % 4294967296
    x = (x ^ (x >> 13)) * 1274126177 % 4294967296
    return x % 1000003


def main():
    w = int(sys.argv[1])
    acc = 0
    with ThreadPoolExecutor(max_workers=w) as ex:
        for rep in range(200):
            n = 1 + rep * 37 % 1500
            fs = [ex.submit(mixf, j) for j in range(rep, rep + n)]
            s = 0
            for f in as_completed(fs):
                s = (s + f.result()) % 1000000007
            acc = (acc * 31 + s) % 1000000007
    print(acc)


main()
'''


class Differential(tp.Base):
    def test_submit_result(self):
        self.compare("submits", SUBMITS, argvs=(("1",), ("2",), ("5",), ("16",)))

    def test_module_spelling(self):
        self.compare("modspell", MODULE_SPELLING, argvs=(("1",), ("3",), ("16",)))

    def test_exceptions_in_order(self):
        self.compare("fails", FAILS, rc=1, argvs=(("1",), ("2",), ("16",)), runs=3)


class Stress(tp.Base):
    def test_many_rounds(self):
        self.compare("stress", STRESS, argvs=(("1",), ("2",), ("4",), ("8",), ("16",)), runs=3)


class Sanitizers(unittest.TestCase):
    run_sanitized = tp.Sanitizers.run_sanitized

    def test_tsan(self):
        self.run_sanitized(STRESS.replace("range(200)", "range(40)"), ["-fsanitize=thread"], "tsan_sub", "8")
        self.run_sanitized(SUBMITS, ["-fsanitize=thread"], "tsan_subs", "5")

    def test_asan_ubsan(self):
        flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        self.run_sanitized(SUBMITS, flags, "asan_subs", "6")


class Refusals(tp.Base):
    def test_future_used_as_value(self):
        self.refused(r'''
from concurrent.futures import ThreadPoolExecutor
def f(x: int) -> int:
    return x + 1
def main():
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(f, i) for i in range(4)]
        for fu in futs:
            print(fu.done(), fu.result())
main()
''', "the future 'fu' is used other than as")

    def test_different_functions_in_a_group(self):
        self.refused(r'''
from concurrent.futures import ThreadPoolExecutor
def f(x: int) -> int:
    return x + 1
def g(x: int) -> int:
    return x + 2
def main():
    with ThreadPoolExecutor(max_workers=2) as ex:
        a = ex.submit(f, 1)
        b = ex.submit(g, 1)
        print(a.result() + b.result())
main()
''', "different functions")

    def test_function_that_prints(self):
        self.refused(r'''
from concurrent.futures import ThreadPoolExecutor
def f(x: int) -> int:
    print(x)
    return x
def main():
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(f, i) for i in range(4)]
        print(sum(fu.result() for fu in futs))
main()
''', "cannot run without the lock")

    def test_submit_in_other_shape(self):
        self.refused(r'''
from concurrent.futures import ThreadPoolExecutor
def f(x: int) -> int:
    return x + 1
def main():
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(f, i): i for i in range(4)}
        print(len(futs))
main()
''', "shape that is not lowered")


class NoCost(unittest.TestCase):
    def test_other_programs_unchanged(self):
        sys.path.insert(0, str(tp.CORE))
        try:
            import typedpar
        finally:
            sys.path.pop(0)
        for text in ("def main():\n    print(1)\nmain()\n",
                     "def f(x):\n    return x\nsubmit = 3\nprint(submit)\n"):
            self.assertIs(typedpar.rewrite_text(text, []), text)


if __name__ == "__main__":
    unittest.main()
