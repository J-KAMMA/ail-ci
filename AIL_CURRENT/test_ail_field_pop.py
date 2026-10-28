"""`pop()` on a numeric list held in a struct field (python/pkg-v12/cruntime.py NUMFIELDMUT).

A stack kept in a struct field (`st.stack.append(x)` ... `st.stack.pop()`) paid, for every pop, an out-of-line call, the
negative-index slow path (`pop()` is `pop(-1)`) and the layout check behind it: 34% of the instructions of an LLM-written
expression interpreter (tally_lang, 36.6 G to 24.3 G). The last element of a live list is now one compare and a decrement;
every other case (an index in the middle, an empty list, an index out of range, a damaged layout) takes the unchanged full
path. What this module pins, against CPython and in the legacy build and both IR modes:

* `pop()`, `pop(-1)`, `pop(len - 1)`, `pop(-len)`, `pop(i)` in the middle, from an int list and a float list, interleaved
  with appends, clears and slice stores, agree with CPython element by element;
* a pop from an empty list and a pop index out of range (both ends) raise IndexError with the list unchanged;
* the generated C reaches the fast path (`ail_numfield_list_pop` is the inline wrapper) and sanitizers report nothing.
"""
import os
import re
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


class St:
    def __init__(self, xs: list[int], fs: list[float]):
        self.xs = xs
        self.fs = fs


def top(st: St) -> int:
    return st.xs.pop()


def two(st: St) -> int:
    b = st.xs.pop()
    a = st.xs.pop()
    return a * 1000 + b


def main() -> int:
    r = Rng(int(sys.argv[1]))
    st = St([], [])
    out: list[int] = []
    errors = 0
    for step in range(int(sys.argv[2])):
        op = r.next(14)
        n = len(st.xs)
        if op < 4:
            st.xs.append(r.next(1000))
            st.fs.append(r.next(1000) / 8.0)
        elif op == 4 and n > 0:
            out.append(st.xs.pop())
        elif op == 5 and n > 0:
            out.append(st.xs.pop(-1))
        elif op == 6 and n > 0:
            out.append(st.xs.pop(n - 1))
        elif op == 7 and n > 0:
            out.append(st.xs.pop(-n))
        elif op == 8 and n > 2:
            out.append(st.xs.pop(r.next(n)))
        elif op == 9 and len(st.fs) > 0:
            out.append(int(st.fs.pop() * 8.0))
        elif op == 10 and n > 1:
            out.append(two(st))
        elif op == 11:
            try:
                out.append(st.xs.pop(n))
            except IndexError:
                errors += 1
            try:
                out.append(st.xs.pop(-n - 1))
            except IndexError:
                errors += 1
        elif op == 12 and n > 5 and r.next(4) == 0:
            st.xs.clear()
            st.fs.clear()
        elif op == 13 and n > 0:
            out.append(top(st))
        if step % 53 == 0:
            print(step, len(st.xs), len(st.fs), st.xs[-1] if len(st.xs) > 0 else -1)
    print("final", len(st.xs), sum(st.xs), len(st.fs))
    print("out", len(out), sum(out), out[len(out) - 1] if len(out) > 0 else -1)
    print("errors", errors)
    try:
        e: list[int] = []
        st.xs.clear()
        print(st.xs.pop())
    except IndexError:
        print("empty")
    return 0


sys.exit(main())
'''


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class PopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(prefix='ail-pop-')
        cls.built = Built(cls.dir.name, 'pop', PROGRAM, debug=True)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_streams_match_cpython_in_every_mode(self):
        for seed, steps in ((1, 3000), (2, 3000), (3, 6000), (7, 800), (99, 5000)):
            expected = cpython_run(self.dir.name, 'pop_cpython', PROGRAM, (seed, steps))
            self.assertEqual(expected[0], 0, expected[2])
            self.assertIn('empty', expected[1])
            for tag, exe in self.built.exe.items():
                got = run(exe, (seed, steps))
                self.assertEqual(got[:2], expected[:2], (tag, seed))

    def test_the_last_element_is_popped_inline(self):
        c = Path(self.dir.name, 'pop.legacy.d', 'program.c').read_text()
        # the field-list macro defines the inline wrapper and, under another name, the full path
        self.assertIn('static inline __attribute__((always_inline)) SCALAR PREFIX##pop(LISTTYPE *s, int64_t i)', c)
        self.assertIn('static SCALAR PREFIX##pop_slow(LISTTYPE *s, int64_t i)', c)
        self.assertIn('return s->p[--s->n];', c)
        self.assertRegex(c, r'ail_numfield_list_pop\(&\(v_st\)->f_xs')
        self.assertRegex(c, r'ail_numfield_flist_pop\(&\(v_st\)->f_fs')

    def test_sanitizers_report_nothing(self):
        for tag in ('legacy', 'ir'):
            san = Path(self.dir.name, 'pop.%s.san' % tag)
            cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
                                 '-fno-omit-frame-pointer', '-pthread', str(Path(self.dir.name, 'pop.%s.d' % tag, 'program.c')),
                                 '-lm', '-o', str(san)], capture_output=True, text=True)
            self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
            for seed in (1, 2):
                r = subprocess.run([str(san), str(seed), '3000'], capture_output=True, timeout=300,
                                   env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0',
                                            UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1'))
                err = r.stderr.decode(errors='replace')
                self.assertEqual(r.returncode, 0, err[-800:])
                self.assertNotIn('Sanitizer', err)
                self.assertNotIn('runtime error', err)


if __name__ == '__main__':
    unittest.main()
