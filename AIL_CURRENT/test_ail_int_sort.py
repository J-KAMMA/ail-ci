"""`xs.sort()` and `sorted(xs)` of an int list (python/pkg-v12/cruntime.py SORT).

An int sort called qsort with a comparison function: 31% of the instructions of an LLM-written scheduler that sorts a million
ints went to the indirect call and the merge buffer. It is now an in-place introsort with the comparison inlined (median of
three, Hoare partition, insertion sort below 17, heapsort at the depth limit; no allocation, equal ints are
indistinguishable so the missing stability is unobservable; floats keep qsort because 0.0 and -0.0 compare equal and
print differently). What this module pins:

* a C harness runs the runtime's own sort against qsort on 6000 arrays (every length below 300, then up to 200,000)
  of nine shapes -- random, sorted, reversed, few distinct values, all equal, organ pipe, INT64_MIN/MAX neighbours, mostly
  sorted with random holes, wide random -- and finds no difference, under ASan+UBSan;
* a program that sorts lists of those shapes with `.sort()`, `sorted()`, `sort(reverse=True)` and a struct field's list prints what
  CPython prints, in the legacy build and both IR modes, and is clean under the sanitizers;
* the generated C calls the inlined sort and no longer qsort for an int list.
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

HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
%(runtime)s
static uint64_t rs = 88172645463325252ULL;
static uint64_t rnd(uint64_t m) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return rs %% m; }
static int cmp(const void *a, const void *b) { int64_t x = *(const int64_t *)a, y = *(const int64_t *)b; return (x > y) - (x < y); }
int main(void) {
    for (int round = 0; round < 6000; round++) {
        int64_t n = round < 300 ? round : (int64_t)rnd(round < 5000 ? 400 : 200000);
        int shape = (int)rnd(9);
        int64_t *a = malloc((size_t)(n + 1) * 8), *b = malloc((size_t)(n + 1) * 8);
        for (int64_t i = 0; i < n; i++) {
            int64_t v;
            switch (shape) {
            case 0: v = (int64_t)rnd(1000000); break;
            case 1: v = i; break;
            case 2: v = n - i; break;
            case 3: v = (int64_t)rnd(3); break;
            case 4: v = 7; break;
            case 5: v = (i < n / 2) ? i : n - i; break;
            case 6: v = (int64_t)(rnd(2) ? INT64_MIN + (int64_t)rnd(5) : INT64_MAX - (int64_t)rnd(5)); break;
            case 7: v = (i %% 7 == 0) ? (int64_t)rnd(1000) : i; break;
            default: v = (int64_t)rnd(1ULL << 62) - (int64_t)(1ULL << 61); break;
            }
            a[i] = b[i] = v;
        }
        ail_list L = {a, n, n};
        ail_list_sort(&L);
        qsort(b, (size_t)n, 8, cmp);
        for (int64_t i = 0; i < n; i++)
            if (a[i] != b[i]) { printf("MISMATCH round %%d n %%lld shape %%d at %%lld\n", round, (long long)n, shape, (long long)i); return 1; }
        free(a); free(b);
    }
    ail_list E = {0};
    ail_list_sort(&E);
    puts("ok");
    return 0;
}
'''

PROGRAM = '''import sys


class Rng:
    def __init__(self, s: int):
        self.s = s

    def next(self, m: int) -> int:
        self.s = (self.s * 1103515245 + 12345) % 2147483648
        return (self.s >> 8) % m


class Box:
    def __init__(self, xs: list[int]):
        self.xs = xs


def fill(r: Rng, shape: int, n: int) -> list[int]:
    xs: list[int] = []
    for i in range(n):
        if shape == 0:
            xs.append(r.next(1000000) - 500000)
        elif shape == 1:
            xs.append(i)
        elif shape == 2:
            xs.append(n - i)
        elif shape == 3:
            xs.append(r.next(3) - 1)
        elif shape == 4:
            xs.append(-9223372036854775807 - 1 if r.next(2) == 0 else 9223372036854775807)
        elif shape == 5:
            xs.append(i if i < n // 2 else n - i)
        else:
            xs.append(r.next(2000000000) * r.next(4000000000) - 4000000000000000000)
    return xs


def digest(xs: list[int]) -> int:
    h = 7
    for x in xs:
        h = (h * 31 + x % 1000003) % 1000000007
    return h


def main() -> int:
    r = Rng(int(sys.argv[1]))
    box = Box([])
    for round in range(int(sys.argv[2])):
        shape = r.next(7)
        n = r.next(50) if round % 3 == 0 else r.next(5000)
        xs = fill(r, shape, n)
        ys = sorted(xs)
        xs.sort()
        zs = fill(r, shape, n)
        zs.sort(reverse=True)
        box.xs = fill(r, shape, n)
        box.xs.sort()
        ok = 1
        for i in range(1, len(xs)):
            if xs[i - 1] > xs[i] or ys[i] != xs[i]:
                ok = 0
        for i in range(1, len(zs)):
            if zs[i - 1] < zs[i]:
                ok = 0
        print(round, shape, n, ok, digest(xs), digest(zs), digest(box.xs), xs[0] if n > 0 else 0, zs[0] if n > 0 else 0)
    return 0


sys.exit(main())
'''


def cc_san(src, exe):
    return subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
                           '-fno-omit-frame-pointer', '-pthread', '-w', str(src), '-lm', '-o', str(exe)],
                          capture_output=True, text=True)


SAN_ENV = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0', UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class RuntimeTests(unittest.TestCase):
    def test_the_inlined_sort_agrees_with_qsort_under_the_sanitizers(self):
        import cruntime
        with tempfile.TemporaryDirectory(prefix='ail-isort-') as tmp:
            src = Path(tmp, 'h.c')
            src.write_text(HARNESS % {'runtime': '#include <stdint.h>\n' + cruntime.emit({'SORT', 'LIST', 'DIE'})})
            exe = Path(tmp, 'h')
            cc = cc_san(src, exe)
            self.assertEqual(cc.returncode, 0, cc.stderr[-3000:])
            r = subprocess.run([str(exe)], capture_output=True, timeout=900, env=SAN_ENV)
            self.assertEqual(r.stdout.decode(), 'ok\n', r.stderr.decode(errors='replace')[-1500:])
            self.assertEqual(r.returncode, 0, r.stderr.decode(errors='replace')[-1500:])


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ProgramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(prefix='ail-isort-p-')
        cls.built = Built(cls.dir.name, 'isort', PROGRAM, debug=True)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_sorted_lists_match_cpython_in_every_mode(self):
        for seed, rounds in ((1, 60), (2, 60), (3, 90), (99, 40)):
            expected = cpython_run(self.dir.name, 'isort_cpython', PROGRAM, (seed, rounds))
            self.assertEqual(expected[0], 0, expected[2])
            for tag, exe in self.built.exe.items():
                got = run(exe, (seed, rounds))
                self.assertEqual(got[:2], expected[:2], (tag, seed))

    def test_the_c_sorts_ints_without_qsort(self):
        c = Path(self.dir.name, 'isort.legacy.d', 'program.c').read_text()
        self.assertIn('ail__sort_i64(L->p, L->n)', c)
        self.assertNotIn('qsort(L->p, (size_t)L->n, sizeof *L->p, ail_cmp)', c)

    def test_sanitizers_report_nothing(self):
        for tag in ('legacy', 'ir'):
            san = Path(self.dir.name, 'isort.%s.san' % tag)
            cc = cc_san(Path(self.dir.name, 'isort.%s.d' % tag, 'program.c'), san)
            self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
            r = subprocess.run([str(san), '5', '40'], capture_output=True, timeout=600, env=SAN_ENV)
            err = r.stderr.decode(errors='replace')
            self.assertEqual(r.returncode, 0, err[-800:])
            self.assertNotIn('Sanitizer', err)
            self.assertNotIn('runtime error', err)
            expected = cpython_run(self.dir.name, 'isort_cpython', PROGRAM, (5, 40))
            self.assertEqual(r.stdout.decode(), expected[1])


if __name__ == '__main__':
    unittest.main()
