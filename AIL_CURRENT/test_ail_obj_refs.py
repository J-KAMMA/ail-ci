"""The reference count of a struct object: retain, release and the per-class store helper (pkg-v12/pyfunc.py, the object
runtime).

Binding a struct element to a name (`e = s.evs[i]`), storing it in a field and releasing it at the end of a scope each
called an out-of-line function: a quarter of the instructions of an LLM-written ticket validator (audit-2, 6.39 G ->
6.19 G, -3.1%; 6.09 G, -4.7%, with the release inline too, which added 9% to the text of route_search-3). `ail_obj_retain`
is now inline (one compare and an increment; a count of 0 or a wrapped UINT32_MAX still aborts), the per-class
`ail_obj_store_<C>` is inline, and `ail_obj_release` is one out-of-line function whose first test is the release that does
not free. What this module pins, against CPython in the legacy
build and both IR modes and under ASan+UBSan+LSan (a missed release is a leak, a double release a use after free):

* names that keep an element alive while the list drops it (`e = s.evs[i]` then `s.evs.pop(i)`, an element store over it,
  `clear()`), elements shared by two lists, an element passed to a function that stores it, a swap, a sort by a key;
* the C shape: inline retain and store helper, one out-of-line release, and the iterative release (with its own
  `ail_obj_free_last`) when the struct can contain itself.
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


class Ev:
    def __init__(self, num: int, cnt: int):
        self.num = num
        self.cnt = cnt


class St:
    def __init__(self, evs: list[Ev], other: list[Ev], k: int):
        self.evs = evs
        self.other = other
        self.k = k


def bump(e: Ev, d: int) -> None:
    e.cnt += d


def keep(s: St, e: Ev) -> None:
    s.other.append(e)


def total(s: St) -> int:
    t = 0
    for e in s.evs:
        t += e.cnt * 3 + e.num
    return t


def main() -> int:
    r = Rng(int(sys.argv[1]))
    s = St([], [], 0)
    seen = 0
    for step in range(int(sys.argv[2])):
        op = r.next(12)
        n = len(s.evs)
        if op < 3:
            s.evs.append(Ev(r.next(1000), r.next(5)))
        elif op == 3 and n > 0:
            e = s.evs[r.next(n)]
            e.cnt += 1
            seen += e.num
        elif op == 4 and n > 0:
            i = r.next(n)
            e = s.evs[i]
            s.evs.pop(i)
            e.cnt += 100
            seen += e.cnt
        elif op == 5 and n > 0:
            i = r.next(n)
            e = s.evs[i]
            s.evs[i] = Ev(e.num + 1, e.cnt + 1)
            e.cnt += 1000
            seen += e.cnt + s.evs[i].cnt
        elif op == 6 and n > 3 and r.next(4) == 0:
            e = s.evs[0]
            s.evs.clear()
            seen += e.cnt
        elif op == 7 and n > 0:
            bump(s.evs[r.next(n)], 2)
        elif op == 8 and n > 0:
            keep(s, s.evs[r.next(n)])
        elif op == 9 and n > 1:
            i = r.next(n)
            j = r.next(n)
            a = s.evs[i]
            b = s.evs[j]
            s.evs[i] = b
            s.evs[j] = a
            seen += a.cnt - b.cnt
        elif op == 10 and n > 1:
            s.evs.sort(key=lambda g: (-g.cnt, g.num))
        elif op == 11:
            if len(s.other) > 0:
                o = s.other[len(s.other) - 1]
                o.cnt += 1
                seen += o.cnt
                if len(s.other) > 20:
                    s.other.pop(0)
        if step % 29 == 0:
            print(step, len(s.evs), len(s.other), total(s), seen)
    print("final", len(s.evs), len(s.other), total(s), seen)
    return 0


sys.exit(main())
'''

# a struct that can contain itself: the release is iterative and has its own last-release function
TREE = '''from __future__ import annotations
import sys


class Node:
    def __init__(self, v: int, kids: list[Node]):
        self.v = v
        self.kids = kids


def build(depth: int, v: int) -> Node:
    n = Node(v, [])
    if depth > 0:
        n.kids.append(build(depth - 1, v * 2))
        n.kids.append(build(depth - 1, v * 2 + 1))
    return n


def walk(n: Node) -> int:
    t = n.v
    for k in n.kids:
        t += walk(k)
    return t


def main() -> int:
    t = 0
    for i in range(int(sys.argv[1])):
        n = build(10, i + 1)
        t += walk(n)
    print(t)
    return 0


sys.exit(main())
'''

SAN_ENV = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0', UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')


def cc_san(src, exe):
    return subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
                           '-fno-omit-frame-pointer', '-pthread', '-w', str(src), '-lm', '-o', str(exe)],
                          capture_output=True, text=True)


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class RefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(prefix='ail-refs-')
        cls.built = Built(cls.dir.name, 'refs', PROGRAM, debug=True)
        cls.tree = Built(cls.dir.name, 'tree', TREE, debug=True)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_streams_match_cpython_in_every_mode(self):
        for seed, steps in ((1, 3000), (2, 3000), (3, 6000), (7, 800), (99, 5000)):
            expected = cpython_run(self.dir.name, 'refs_cpython', PROGRAM, (seed, steps))
            self.assertEqual(expected[0], 0, expected[2])
            for tag, exe in self.built.exe.items():
                self.assertEqual(run(exe, (seed, steps))[:2], expected[:2], (tag, seed))
        expected = cpython_run(self.dir.name, 'tree_cpython', TREE, (20,))
        for tag, exe in self.tree.exe.items():
            self.assertEqual(run(exe, (20,))[:2], expected[:2], tag)

    def test_the_c_shape(self):
        c = Path(self.dir.name, 'refs.legacy.d', 'program.c').read_text()
        self.assertIn('static inline __attribute__((always_inline)) void *ail_obj_retain(void *value)', c)
        self.assertIn('static __attribute__((noinline)) void ail_obj_release(void *value)', c)
        self.assertNotIn('ail_obj_free_last', c)
        self.assertIn('static inline ail_obj_Ev *ail_obj_store_Ev(', c)
        t = Path(self.dir.name, 'tree.legacy.d', 'program.c').read_text()
        self.assertIn('static void ail_obj_free_last(void *value)', t)          # the iterative release
        self.assertIn('ail_free_queue', t)

    def test_sanitizers_report_nothing(self):
        for name, args, source in (('refs', ('5', '3000'), PROGRAM), ('tree', ('12',), TREE)):
            for tag in ('legacy', 'ir'):
                san = Path(self.dir.name, '%s.%s.san' % (name, tag))
                cc = cc_san(Path(self.dir.name, '%s.%s.d' % (name, tag), 'program.c'), san)
                self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
                r = subprocess.run([str(san), *args], capture_output=True, timeout=600, env=SAN_ENV)
                err = r.stderr.decode(errors='replace')
                self.assertEqual(r.returncode, 0, err[-800:])
                self.assertNotIn('Sanitizer', err)
                self.assertNotIn('runtime error', err)
                expected = cpython_run(self.dir.name, name + '_cpython', source, args)
                self.assertEqual(r.stdout.decode(), expected[1])


if __name__ == '__main__':
    unittest.main()
