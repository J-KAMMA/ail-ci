"""The reference count of a bytearray (`ail_bytearray_retain`, `_release`, `_store`; pkg-v12/cruntime.py BYTEARRAY).

A struct method that reads a bytearray field takes a reference to it for the call and gives it back (`self.arena` in a table
class, a name store in a tree parser): the retain, the release that does not free and the store helper were a third of the
instructions of ranking-2 (28.2 G -> 18.0 G, -36%) and a tree parser (10.4 G -> 7.3 G, -30%); each ran the full metadata
check. A live object now takes one compare and an increment inline in the retain, the store helper is inline, the release
is one out-of-line function whose first test is the release that does not free, and a dead object (a count of 0), a counter at
its limit and the last release (the small-object cache, `free`) take the unchanged full path. What this module pins, against
CPython in the legacy build and both IR modes and under ASan+UBSan+LSan (a missed
release is a leak, an early one a use after free):

* a bytearray shared by two names and by two fields shows a change made through either; the last holder frees it; empty
  and large (past the 4 KiB cache limit) bytearrays and more freed ones than the cache holds behave alike;
* a method that reads and extends `self.arena` many times, a field swapped between objects, a bytearray stored in a field and
  dropped from a local, cleared and refilled;
* the C shape: inline retain and store; one out-of-line release; the slow retain out of line.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'python' / 'pkg-v12'), str(ROOT)]

from test_ail_ir_s3 import Built, cpython_run, run, HAVE_CC     # noqa: E402

PROGRAM = '''import sys


class Rng:
    def __init__(self, s: int):
        self.s = s

    def next(self, m: int) -> int:
        self.s = (self.s * 1103515245 + 12345) % 2147483648
        return (self.s >> 8) % m


class Tab:
    def __init__(self, arena: bytearray, cur: bytearray, n: int):
        self.arena = arena
        self.cur = cur
        self.n = n

    def insert(self, k: int, w: int) -> int:
        start = len(self.arena)
        for i in range(w):
            self.arena.append((k + i * 7) % 256)
        self.n += 1
        return start

    def matches(self, start: int, k: int, w: int) -> int:
        if start + w > len(self.arena):
            return 0
        for i in range(w):
            if self.arena[start + i] != (k + i * 7) % 256:
                return 0
        return 1

    def stage(self, k: int) -> int:
        self.cur.clear()
        for i in range(5):
            self.cur.append((k + i) % 256)
        return self.cur[0] * 256 + self.cur[4]


def total(b: bytearray) -> int:
    t = 0
    for x in b:
        t = (t * 31 + x) % 1000003
    return t


def main() -> int:
    r = Rng(int(sys.argv[1]))
    a = Tab(bytearray(), bytearray(), 0)
    b = Tab(bytearray(), bytearray(), 0)
    starts: list[int] = []
    shared = bytearray()
    pool: list[int] = []
    out = 0
    for step in range(int(sys.argv[2])):
        op = r.next(10)
        if op < 3:
            w = 1 + r.next(9)
            k = r.next(256)
            starts.append(a.insert(k, w))
            starts.append(w)
            starts.append(k)
        elif op == 3 and len(starts) > 2:
            j = r.next(len(starts) // 3) * 3
            out += a.matches(starts[j], starts[j + 2], starts[j + 1])
        elif op == 4:
            out += a.stage(r.next(256)) + b.stage(r.next(256))
        elif op == 5:
            tmp = a.arena
            a.arena = b.arena
            b.arena = tmp
            starts.clear()
        elif op == 6:
            alias = shared
            alias.append(r.next(256))
            out += len(shared) + total(alias)
        elif op == 7:
            big = bytearray()
            for i in range(r.next(6000)):
                big.append(i % 251)
            out += total(big) + len(big)
            pool.append(len(big))
        elif op == 8:
            for i in range(r.next(12)):
                small = bytearray()
                small.append(i)
                out += small[0] + len(small)
        elif op == 9 and r.next(20) == 0:
            shared = bytearray()
            a.cur = shared
            shared.append(77)
            out += len(a.cur)
        if step % 41 == 0:
            print(step, out, len(a.arena), len(b.arena), len(shared), total(a.arena), total(b.cur))
    print("final", out, a.n, b.n, len(a.arena), len(b.arena), total(a.arena), len(pool), len(shared))
    return 0


sys.exit(main())
'''

SAN_ENV = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0', UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class BytearrayRefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(prefix='ail-barefs-')
        cls.built = Built(cls.dir.name, 'barefs', PROGRAM, debug=True)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_streams_match_cpython_in_every_mode(self):
        for seed, steps in ((1, 1500), (2, 1500), (3, 3000), (7, 300), (99, 2500)):
            expected = cpython_run(self.dir.name, 'barefs_cpython', PROGRAM, (seed, steps))
            self.assertEqual(expected[0], 0, expected[2])
            for tag, exe in self.built.exe.items():
                self.assertEqual(run(exe, (seed, steps))[:2], expected[:2], (tag, seed))

    def test_the_c_shape(self):
        c = Path(self.dir.name, 'barefs.legacy.d', 'program.c').read_text()
        self.assertIn('static inline __attribute__((always_inline)) ail_bytearray *ail_bytearray_retain(ail_bytearray *B)', c)
        self.assertIn('ail_bytearray_retain_slow(ail_bytearray *B)', c)
        self.assertIn('static __attribute__((noinline)) void ail_bytearray_release(ail_bytearray *B)', c)
        self.assertIn('static inline void ail_bytearray_store(', c)

    def test_sanitizers_report_nothing(self):
        for tag in ('legacy', 'ir'):
            san = Path(self.dir.name, 'barefs.%s.san' % tag)
            cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
                                 '-fno-omit-frame-pointer', '-pthread', '-w',
                                 str(Path(self.dir.name, 'barefs.%s.d' % tag, 'program.c')), '-lm', '-o', str(san)],
                                capture_output=True, text=True)
            self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
            for seed in (1, 5):
                r = subprocess.run([str(san), str(seed), '1500'], capture_output=True, timeout=600, env=SAN_ENV)
                err = r.stderr.decode(errors='replace')
                self.assertEqual(r.returncode, 0, err[-1200:])
                self.assertNotIn('Sanitizer', err)
                self.assertNotIn('runtime error', err)
                expected = cpython_run(self.dir.name, 'barefs_cpython', PROGRAM, (seed, 1500))
                self.assertEqual(r.stdout.decode(), expected[1])


if __name__ == '__main__':
    unittest.main()
