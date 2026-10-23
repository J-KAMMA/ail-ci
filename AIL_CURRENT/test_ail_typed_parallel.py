"""Typed parallelism without a lock (docs/design/TYPED_PARALLEL.md, typedpar.py), compared with CPython 3.12.

Owner decision 2026-10-19: code on the typed path drops the GIL and is kept free of data races at compile
time, with Python's own APIs. Built so far:

* `ThreadPoolExecutor(max_workers=k).map(f, xs[, ys])` and `multiprocessing.Pool(k).map(f, xs)` over a
  module-level function of int / float that only computes; results in order.
* `Thread(target=w, args=(k, ...))` for k in range(n), started and joined in the same block (scoped
  threads): `w` may read lists and scalars and write `out[k]` only.

Every program is built with the typed path alone (AIL_NO_GENERAL=1), run at several worker counts (the
program reads it from argv), and must print what CPython prints, with the same exit status.

* Differential: map over lists, ranges and two iterables, Pool.map under `if __name__`, the assignment
  form with shutdown/close/join, worker counts from a variable (and ValueError for 0), an exception in a
  worker (raised at the map in order, catchable), scoped threads in both spellings.
* Stress: many small maps and many threads, each result exact, at 1..16 workers, several runs.
* ThreadSanitizer (`setarch -R`, as test_ail_threads.py) and ASan/UBSan on a map and a thread program.
* Refusals: each rule's note with its `write instead:` line; the typed path alone refuses the program,
  the default build runs it on the general path under the lock with the same output.
* No cost: a program that names none of the modules is returned by the pass as written; a `parallel for`
  program has no PARN in its C.
"""
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
CORE = ROOT / "python" / "pkg-v12"


def oracle_env():
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    return env


def build(src, exe, typed_only=True, cwd=None):
    env = dict(os.environ)
    for key in ("AIL_NO_GENERAL", "AIL_TARGET", "AIL_IR", "AIL_THREADS"):
        env.pop(key, None)
    if typed_only:
        env["AIL_NO_GENERAL"] = "1"
    return subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "-o", str(exe)], cwd=cwd,
                          capture_output=True, text=True, timeout=900, env=env)


def typed_c(text):
    """The whole C file the typed path makes for a Python program (the compile command's front end, then
    pyc.py with the typed path alone)."""
    sys.path[:0] = [str(CORE), str(ROOT)]
    try:
        import ail_syntax
    finally:
        del sys.path[:2]
    source = ail_syntax.fold_constants(ail_syntax.python_surface(text, []))
    with tempfile.TemporaryDirectory(prefix="ail-tpar-c-") as tmp:
        (Path(tmp) / "p.ail").write_text(source, encoding="utf-8")
        env = dict(os.environ, AIL_NO_GENERAL="1")
        env.pop("AIL_IR", None)
        r = subprocess.run([sys.executable, "-B", str(CORE / "pyc.py"), "--file", str(Path(tmp) / "p.ail"),
                            str(Path(tmp) / "x"), "--strict"], capture_output=True, text=True, timeout=600, env=env)
        if r.returncode:
            raise AssertionError("the typed path refused it: " + r.stderr[-2000:])
        return (Path(tmp) / "x.c").read_text(encoding="utf-8")


class Base(unittest.TestCase):
    def compare(self, name, text, argvs=(("1",), ("3",), ("16",)), runs=1, rc=0):
        with tempfile.TemporaryDirectory(prefix="ail-tpar-") as tmp:
            src = Path(tmp) / (name + ".py")
            src.write_text(text, encoding="utf-8")
            exe = Path(tmp) / "exe"
            built = build(src, exe, cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.assertNotIn("general path", built.stderr)
            for argv in argvs:
                want = subprocess.run([sys.executable, str(src), *argv], cwd=tmp, capture_output=True, timeout=600,
                                      env=oracle_env())
                self.assertEqual(want.returncode, rc, want.stderr.decode()[-2000:])
                self.assertTrue(want.stdout, "the program prints nothing")
                for run in range(runs):
                    got = subprocess.run([str(exe), *argv], cwd=tmp, capture_output=True, timeout=600,
                                         env=oracle_env())
                    self.assertEqual(got.returncode, rc, "argv %s run %d: %s" % (argv, run, got.stderr.decode()[-2000:]))
                    self.assertEqual(got.stdout.decode(), want.stdout.decode(), "argv %s run %d" % (argv, run))

    def refused(self, text, *needles):
        """The typed path alone refuses it with the note; the default build runs it as CPython does."""
        with tempfile.TemporaryDirectory(prefix="ail-tpar-") as tmp:
            src = Path(tmp) / "prog.py"
            src.write_text(text, encoding="utf-8")
            built = build(src, Path(tmp) / "exe", cwd=tmp)
            self.assertNotEqual(built.returncode, 0, "accepted:\n" + text)
            for needle in needles + ("not run in parallel", "write instead:"):
                self.assertIn(needle, built.stderr)
            return built.stderr


# ------------------------------------------------------------------------------------- programs

MAPS = r'''
import sys
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures as cf


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


def mix(a: int, b: float) -> float:
    return a * b + 0.25


def halve(x: float) -> float:
    return x / 2.0


def helper(a: int) -> int:
    return a * 3 + 1


def outer(a: int) -> int:
    return helper(a) - helper(a - 1)


def main():
    w = int(sys.argv[1])
    xs = [i * 7 + 1 for i in range(3000)]
    with ThreadPoolExecutor(max_workers=w) as ex:
        a = list(ex.map(steps, xs))
        b = sum(ex.map(steps, range(1, 500)))
        c = list(ex.map(mix, range(4), [1.5, 2.5, 3.5, 4.5, 5.5]))
        d = sorted(ex.map(steps, [27, 3, 9]))
        d2 = list(ex.map(halve, [3.0, 1.0]))
        e = 0
        for v in ex.map(outer, range(10, 20)):
            e = e * 7 + v
        f = [v * 2 for v in ex.map(steps, [27, 97])]
        g = list(ex.map(steps, []))
        h = max(ex.map(steps, range(1, 1000)))
    print(len(a), a[0], a[1], a[2999], sum(a))
    print(b, c[0], c[3], len(c), d[0], d[2], d2[1], e, f[0], f[1], len(g), h)
    ex2 = cf.ThreadPoolExecutor(w)
    k = list(ex2.map(steps, range(2, 40, 1)))
    ex2.shutdown(wait=True)
    print(sum(k), k[0])
    with ThreadPoolExecutor() as ex3:
        print(sum(ex3.map(helper, range(100))))


main()
'''

POOLS = r'''
import sys
import multiprocessing
from multiprocessing import Pool


def sq(x: int) -> int:
    return x * x - 3


def f2(x: float) -> float:
    return x / 4.0 + 1.0


if __name__ == "__main__":
    n = int(sys.argv[1])
    with Pool(n) as p:
        r = p.map(sq, [3, 4, 5])
        s = p.map(sq, range(100), 7)
    print(r[0], r[1], r[2], len(s), sum(s))
    pool = multiprocessing.Pool(processes=n)
    q = pool.map(f2, [1.0, 2.0, 6.5])
    pool.close()
    pool.join()
    print(q[0] + q[1], q[2])
'''

WORKERS = r'''
import sys
from concurrent.futures import ThreadPoolExecutor


def dbl(x: int) -> int:
    return 2 * x


def main():
    w = int(sys.argv[1]) - 3
    try:
        with ThreadPoolExecutor(max_workers=w) as ex:
            print(sum(ex.map(dbl, range(50))))
    except ValueError as e:
        print("ValueError", e)


main()
'''

FAILS = r'''
import sys
from concurrent.futures import ThreadPoolExecutor


def inv(x: int) -> int:
    return 1000 // (x - 70)


def safe(n: int, w: int) -> int:
    try:
        with ThreadPoolExecutor(max_workers=w) as ex:
            return sum(ex.map(inv, range(n)))
    except ZeroDivisionError:
        return -1


def main():
    w = int(sys.argv[1])
    print(safe(50, w), safe(200, w), safe(5000, w))
    with ThreadPoolExecutor(max_workers=w) as ex:
        print(sum(ex.map(inv, range(60))))
        print(sum(ex.map(inv, range(100))))
        print("not reached")


main()
'''

THREADS = r'''
import sys
import threading
from threading import Thread


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


def work(k: int, stride: int, lim: int, weights: list[int], out: list[int]) -> None:
    total = 0
    i = k + 1
    while i < lim:
        total += steps(i) * weights[i % len(weights)]
        i += stride
    out[k] = total


def half(j: int, scale: float, res: list[float]) -> None:
    res[j] = j / 2 * scale


def rows(r: int, n: int, grid: list[int]) -> None:
    for c in range(0, n):
        grid[r * n + c] = (r + 1) * (c + 2) % 7


def main():
    T = int(sys.argv[1])
    weights = [1, 2, 3]
    out = [0] * T
    ts = [threading.Thread(target=work, args=(k, T, 20000, weights, out)) for k in range(T)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    total = 0
    for v in out:
        total += v
    print(total)
    res = [0.0] * 5
    threads = []
    for j in range(5):
        th = Thread(target=half, args=(j, 1.5, res))
        threads.append(th)
        th.start()
    for th in threads:
        th.join()
    print(res[0], res[1], res[4])
    n = 9
    grid = [0] * (n * n)
    gs = []
    for r in range(n):
        gs.append(Thread(target=rows, args=(r, n, grid), name="row%d" % r))
    for g in gs:
        g.start()
    for g in gs:
        g.join()
    print(sum(grid), grid[0], grid[80])


main()
'''

STRESS_MAP = r'''
import sys
from concurrent.futures import ThreadPoolExecutor


def mixf(i: int) -> int:
    x = i * 2654435761 % 4294967296
    x = (x ^ (x >> 13)) * 1274126177 % 4294967296
    return x % 1000003


def main():
    w = int(sys.argv[1])
    acc = 0
    with ThreadPoolExecutor(max_workers=w) as ex:
        for rep in range(300):
            n = 1 + rep * 37 % 2000
            r = list(ex.map(mixf, range(rep, rep + n)))
            s = 0
            for j in range(n):
                s = (s * 31 + r[j]) % 1000000007
            acc = (acc + s) % 1000000007
    print(acc)


main()
'''

STRESS_THREADS = r'''
import sys
import threading


def fill(k: int, n: int, out: list[int]) -> None:
    v = k
    for i in range(0, n):
        v = (v * 1103515245 + 12345) % 2147483648
    out[k] = v


def main():
    T = int(sys.argv[1]) * 4
    check = 0
    for rep in range(40):
        out = [0] * T
        ts = [threading.Thread(target=fill, args=(k, 50 + rep, out)) for k in range(T)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        for v in out:
            check = (check * 131 + v) % 1000000007
    print(check)


main()
'''


class Differential(Base):
    def test_executor_map(self):
        self.compare("maps", MAPS)

    def test_pool_map(self):
        self.compare("pools", POOLS)

    def test_worker_count(self):
        self.compare("workers", WORKERS, argvs=(("1",), ("3",), ("4",), ("19",)))

    def test_exceptions(self):
        self.compare("fails", FAILS, rc=1, argvs=(("1",), ("2",), ("16",)), runs=3)

    def test_threads(self):
        self.compare("threads", THREADS, argvs=(("1",), ("2",), ("7",), ("16",)))


class Stress(Base):
    def test_many_maps(self):
        self.compare("stress_map", STRESS_MAP, argvs=(("1",), ("2",), ("4",), ("8",), ("16",)), runs=3)

    def test_many_threads(self):
        self.compare("stress_threads", STRESS_THREADS, argvs=(("1",), ("4",), ("16",)), runs=3)


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("gcc"), "sanitizers: Linux gcc")
class Sanitizers(unittest.TestCase):
    """The typed C of a map and a thread program under ThreadSanitizer (no data race: the workers write
    disjoint elements and read what nobody writes during the region) and under ASan/UBSan."""

    def run_sanitized(self, text, flags, name, argv):
        c = typed_c(text)
        self.assertIn("ail_par_run_n", c)
        with tempfile.TemporaryDirectory(prefix="ail-tpar-san-") as tmp:
            cfile = Path(tmp) / (name + ".c")
            cfile.write_text(c, encoding="utf-8")
            exe = Path(tmp) / name
            cc = subprocess.run(["gcc", "-O1", "-g", *flags, "-o", str(exe), str(cfile), "-lm", "-pthread"],
                                capture_output=True, text=True, timeout=600)
            if cc.returncode:
                if "san" not in cc.stderr:
                    self.fail("gcc: " + cc.stderr[-1500:])
                self.skipTest("gcc cannot build with %s: %s" % (" ".join(flags), cc.stderr[-300:]))
            want = subprocess.run([sys.executable, "-c", text, argv], capture_output=True, timeout=600,
                                  env=oracle_env())
            # high-entropy ASLR can defeat TSan's shadow layout (it stops, or faults): run without ASLR
            norand = ["setarch", platform.machine(), "-R"] if shutil.which("setarch") else []
            for _ in range(20):
                got = subprocess.run(norand + [str(exe), argv], capture_output=True, timeout=600,
                                     env=dict(os.environ, TSAN_OPTIONS="halt_on_error=1", ASAN_OPTIONS="detect_leaks=0"))
                if b"unexpected memory mapping" not in got.stderr:
                    break
            else:
                self.skipTest("ThreadSanitizer cannot map its shadow memory on this kernel")
            err = got.stderr.decode("utf-8", "replace")
            self.assertNotIn("ThreadSanitizer", err)
            self.assertNotIn("AddressSanitizer", err)
            self.assertNotIn("runtime error", err)
            self.assertEqual(got.returncode, 0, err[-2000:])
            self.assertEqual(got.stdout, want.stdout)

    def test_tsan(self):
        self.run_sanitized(STRESS_MAP.replace("range(300)", "range(60)"), ["-fsanitize=thread"], "tsan_map", "8")
        self.run_sanitized(STRESS_THREADS.replace("range(40)", "range(10)"), ["-fsanitize=thread"], "tsan_threads", "4")
        self.run_sanitized(MAPS, ["-fsanitize=thread"], "tsan_maps", "5")

    def test_asan_ubsan(self):
        flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        self.run_sanitized(MAPS, flags, "asan_maps", "6")
        self.run_sanitized(THREADS, flags, "asan_threads", "6")


REFUSALS = [
    # (program, words the note must contain)
    (r'''
from concurrent.futures import ThreadPoolExecutor
total = 0
def add(x: int) -> int:
    global total
    total += x
    return total
def main():
    with ThreadPoolExecutor(max_workers=4) as ex:
        print(sum(ex.map(add, range(10))))
main()
''', ("not run in parallel", "add() cannot run without the lock")),
    (r'''
from concurrent.futures import ThreadPoolExecutor
def show(x: int) -> int:
    print(x)
    return x
def main():
    with ThreadPoolExecutor(max_workers=4) as ex:
        print(sum(ex.map(show, range(3))))
main()
''', ("show() cannot run without the lock", "write results into a list")),
    (r'''
from concurrent.futures import ThreadPoolExecutor
def first(s: str) -> int:
    return len(s)
def main():
    with ThreadPoolExecutor(max_workers=4) as ex:
        print(sum(ex.map(first, ["a", "bb"])))
main()
''', ("first() cannot run without the lock", "must be annotated int or float")),
    (r'''
from concurrent.futures import ThreadPoolExecutor
def dbl(x: int) -> int:
    return 2 * x
def main():
    with ThreadPoolExecutor(max_workers=4) as ex:
        it = ex.map(dbl, range(3))
        print(sum(it))
main()
''', ("the iterator executor.map returns is used as a value",)),
    (r'''
from concurrent.futures import ThreadPoolExecutor
def dbl(x: int) -> int:
    return 2 * x
def main():
    with ThreadPoolExecutor(max_workers=4) as ex:
        f = ex.submit(dbl, 3)
        print(f.done())
main()
''', ("the future 'f' is used other than as",)),
    (r'''
import threading
def grow(k: int, out: list[int]) -> None:
    out.append(k)
def main():
    out: list[int] = []
    ts = [threading.Thread(target=grow, args=(k, out)) for k in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(out))
main()
''', ("not run in parallel", "is not allowed")),
    (r'''
import threading
def put(k: int, out: list[int]) -> None:
    out[0] = k
def main():
    out = [0] * 4
    ts = [threading.Thread(target=put, args=(k, out)) for k in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(out[0] >= 0)
main()
''', ("'out' is written in the body, but not only at indexes that differ",)),
    (r'''
import threading
def put(k: int, out: list[int]) -> None:
    out[k] = k
def main():
    out = [0] * 4
    ts = [threading.Thread(target=put, args=(k, out)) for k in range(4)]
    for t in ts:
        t.start()
    print("working")
    for t in ts:
        t.join()
    print(out[3])
main()
''', ("are not joined right after they are started", "write instead:")),
    (r'''
import threading
lock = threading.Lock()
def put(k: int, out: list[int]) -> None:
    out[k] = k
def main():
    out = [0] * 4
    with lock:
        print(out[0])
main()
''', ("threading is used in a way",)),
    (r'''
from concurrent.futures import ThreadPoolExecutor
def dbl(x: int) -> int:
    return 2 * x
def main():
    with ThreadPoolExecutor(max_workers=2) as ex:
        print(sum(ex.map(dbl, range(3))))
    try:
        print(sum(ex.map(dbl, range(3))))
    except RuntimeError:
        print("shut down")
main()
''', ("the executor or pool 'ex' is used outside the block",)),
]


class Refusals(Base):
    def test_by_name(self):
        for text, needles in REFUSALS:
            with self.subTest(needles=needles):
                self.refused(text, *needles)

    def test_general_path_still_runs_them(self):
        """Without AIL_NO_GENERAL the refused program runs on the general path (G12, under the lock)."""
        text, _ = REFUSALS[0]
        with tempfile.TemporaryDirectory(prefix="ail-tpar-") as tmp:
            src = Path(tmp) / "prog.py"
            src.write_text(text, encoding="utf-8")
            built = build(src, Path(tmp) / "exe", typed_only=False, cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            self.assertIn("not run in parallel", built.stderr)
            got = subprocess.run([str(Path(tmp) / "exe")], capture_output=True, timeout=60)
            want = subprocess.run([sys.executable, str(src)], capture_output=True, timeout=60, env=oracle_env())
            self.assertEqual(got.stdout, want.stdout)

    def test_fallback_runs_the_plain_loop(self):
        """A lowered map in a program the typed path refuses for another reason (print of a list) runs as the
        plain loop on the general path."""
        text = MAPS.replace("print(sum(k), k[0])", "print(k[:3], sum(k))")
        with tempfile.TemporaryDirectory(prefix="ail-tpar-") as tmp:
            src = Path(tmp) / "prog.py"
            src.write_text(text, encoding="utf-8")
            built = build(src, Path(tmp) / "exe", typed_only=False, cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            got = subprocess.run([str(Path(tmp) / "exe"), "4"], capture_output=True, timeout=120)
            want = subprocess.run([sys.executable, str(src), "4"], capture_output=True, timeout=120, env=oracle_env())
            self.assertEqual(got.stdout, want.stdout)


class NoCost(unittest.TestCase):
    def test_pass_leaves_other_programs(self):
        sys.path.insert(0, str(CORE))
        try:
            import typedpar
        finally:
            sys.path.pop(0)
        for text in ("def main():\n    print(1)\nmain()\n",
                     "import threading\nlock = threading.Lock()\ndef main():\n    with lock:\n        print(1)\nmain()\n",
                     "def main():\n    threading = 3\n    print(threading)\nmain()\n"):
            self.assertIs(typedpar.rewrite_text(text, []), text)

    def test_parallel_for_keeps_its_runtime(self):
        text = ("def f(n: int) -> list[int]:\n    out = [0] * n\n    for i in par_range(0, n):\n"
                "        out[i] = i * i\n    return out\n\ndef main():\n    print(sum(f(100)))\n\nmain()\n")
        c = typed_c(text)
        self.assertIn("ail_par_run(", c)
        self.assertNotIn("ail_par_run_n", c)
        self.assertNotIn("ail_par_cap", c)


if __name__ == "__main__":
    unittest.main()
