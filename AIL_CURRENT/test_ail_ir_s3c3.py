"""IR stage S3c-3: lists of scalar records, the stdin line loop and plain numeric sorts
(docs/design/IR_OWNERSHIP_DESIGN_v2.md section 19, python/pkg-v12/ir/).

A local `list[C]` of a struct whose fields are all int or float is held inline (`obj<list<tup<..>>>`, records one
after the other) and heapq on it (`heappush/heappop(h, x, key=lambda ..)`) is CPython's heapq algorithm over records;
a struct local that only receives a popped record is scalar-replaced; a struct local that only holds such lists is
split into one list per field. What this module pins:

* the new ops (`rec.push`, `rec.up`, `rec.pop`) print, parse and verify, malformed uses are rejected by name, and the
  C keeps the moves of the legacy `ail_oheap_*` (so the heap layout after every step equals CPython's);
* heap programs agree with CPython (a prelude gives 3.12's heapq a `key=`), the legacy build and both exception modes:
  keys covering every field and keys that do not (equal keys with different records pop in CPython's order), int and
  float fields, pushes while popping, an empty heap, a heap held in a struct local;
* `for line in sys.stdin` agrees with CPython for empty input, a last line without a newline, long lines, CRLF;
  the loop variable used after the loop keeps the function legacy;
* `xs.sort()` of int and float lists (NaN raises ValueError);
* what stays legacy; sanitizers report nothing.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'python' / 'pkg-v12'), str(ROOT)]

from ir import ir as I                       # noqa: E402
from ir import effects as E                  # noqa: E402
from ir import emit_c, text, verify          # noqa: E402
from test_ail_ir_s3 import Built, compile_program, run, last_line, HAVE_CC     # noqa: E402
from ail_testenv import ASAN_DETECT_LEAKS

REC = I.T('obj', I.T('list', I.T('tup', I.I64, I.I64, I.F64)))

HEAP = '''func @heap(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], owned = ["h"], sym = "heap"} {
  %h = local.alloc {name = "h"} : place<obj<list<tup<i64, i64, f64>>>>
  %zero = const {value = 0} : i64
  %one = const {value = 1} : i64
  %f = const {value = 0.5} : f64
  %r = list.ref %h : obj<list<tup<i64, i64, f64>>>
  rec.push %r, %n, %one, %f
  rec.up %r {key = [0, 1]}
  %r2 = list.ref %h : obj<list<tup<i64, i64, f64>>>
  %a, %b, %c = rec.pop %r2 {key = [0, 1]} : i64, i64, f64
  %len = list.len %r2 : i64
  return %a
}
'''


def fn_of(src):
    fn = text.parse_function(src)
    program = I.Program({fn.sym: fn})
    E.summarize_program(program)
    return fn, program


class OpTests(unittest.TestCase):
    def bad(self, src, message):
        fn = text.parse_function(src)
        program = I.Program({fn.sym: fn})
        errors = verify.verify_function(fn, program)
        self.assertTrue(any(message in e for e in errors), (message, errors))

    def test_round_trip_and_verify(self):
        fn, program = fn_of(HEAP)
        verify.check(fn, program)
        printed = text.print_function(fn)
        self.assertEqual(text.print_function(text.parse_function(printed)), printed)

    def test_malformed_uses_are_rejected_by_name(self):
        self.bad(HEAP.replace('rec.push %r, %n, %one, %f', 'rec.push %r, %n, %one, %one'), 'rec.push takes')
        self.bad(HEAP.replace('{key = [0, 1]}\n  %r2', '{key = [0, 7]}\n  %r2'), 'field indices')
        self.bad(HEAP.replace('%a, %b, %c = rec.pop %r2 {key = [0, 1]} : i64, i64, f64', '%a, %b = rec.pop %r2 {key = [0, 1]} : i64, i64'), 'one value per field')
        self.bad(HEAP.replace('owned = ["h"], ', ''), 'owned places')

    def test_effects(self):
        fn, program = fn_of(HEAP)
        by_op = {i.op: E.instr_effects(i, fn, program) for i in I.walk(fn.body)}
        self.assertIn('Spine(Own(heap,h))', by_op['rec.push'].writes)
        self.assertNotIn('Spine(Own(heap,h))', by_op['rec.up'].writes)
        self.assertIn('IndexError', by_op['rec.pop'].raises)

    def test_c_has_the_legacy_heap_moves_on_inline_records(self):
        fn, _ = fn_of(HEAP)
        _, c, needs = emit_c.emit_function(fn)
        self.assertIn('typedef struct { int64_t f0; int64_t f1; double f2; } ail_rec_IIF;', c)
        self.assertIn('ail_rl_IIF_free(&v_h);', c)
        self.assertIn('if (right < end && !ail_rh_lt_IIF_0_1(&p[child], &p[right])) child = right;', c)
        self.assertIn('ail_rh_pop_IIF_0_1(', c)
        self.assertEqual(c.count('#ifndef AIL_RL_IIF'), 1)


PRELUDE = '''import heapq
import sys


class _K:
    __slots__ = ('k', 'v')

    def __init__(self, k, v):
        self.k = k
        self.v = v

    def __lt__(self, o):
        return self.k < o.k


def heappush(h, x, key=None):
    heapq.heappush(h, _K(key(x), x) if key else x)


def heappop(h, key=None):
    r = heapq.heappop(h)
    return r.v if key else r


'''

HEAPS = '''import sys


class Item:
    def __init__(self, d: int, b: int, n: int):
        self.d = d
        self.b = b
        self.n = n


class Fl:
    def __init__(self, w: float, k: int):
        self.w = w
        self.k = k


class Q:
    def __init__(self, h: list[Item]):
        self.h = h


def full_key(k: int) -> int:
    h: list[Item] = []
    total = 0
    for i in range(k):
        heappush(h, Item((i * 7) % 5, (i * 3) % 4, i), key=lambda it: (it.d, it.b, it.n))
    while len(h) > 0:
        it = heappop(h, key=lambda it: (it.d, it.b, it.n))
        total = (total * 31 + it.n * 7 + it.d + it.b) % 1000003
        if it.n % 3 == 0 and it.d < 4:
            heappush(h, Item(it.d + 2, it.b, it.n + 1000), key=lambda it: (it.d, it.b, it.n))
    return total


def partial_key(k: int) -> int:
    # equal keys, different records: the pop order is CPython's sift order
    h: list[Item] = []
    total = 0
    for i in range(k):
        heappush(h, Item((i * 7) % 3, (i * 3) % 4, i), key=lambda it: it.d)
    while len(h) > 0:
        it = heappop(h, key=lambda it: it.d)
        total = (total * 31 + it.n) % 1000003
        if it.n % 4 == 0 and it.d < 2 and it.n < 500:
            heappush(h, Item(it.d, it.b, it.n + 500), key=lambda it: it.d)
    return total


def two_keys(k: int) -> int:
    h: list[Item] = []
    total = 0
    for i in range(k):
        heappush(h, Item((i * 5) % 3, (i * 7) % 3, i), key=lambda it: (it.d, it.b))
    while len(h) > 0:
        it = heappop(h, key=lambda it: (it.d, it.b))
        total = (total * 17 + it.n) % 1000003
    return total


def floats(k: int) -> float:
    h: list[Fl] = []
    acc = 0.0
    for i in range(k):
        heappush(h, Fl(((i * 13) % 7) / 4.0, i), key=lambda f: f.w)
    while len(h) > 0:
        f = heappop(h, key=lambda f: f.w)
        acc = acc * 0.5 + f.w + f.k
    return acc


def in_struct(k: int) -> int:
    q = Q([])
    total = 0
    for i in range(k):
        q.h.clear()
        for j in range(5):
            heappush(q.h, Item((i + j * 3) % 4, j, i * 10 + j), key=lambda it: (it.d, it.n))
        while len(q.h) > 0:
            it = heappop(q.h, key=lambda it: (it.d, it.n))
            total = (total * 3 + it.n) % 1000003
    return total


def main():
    for k in (0, 1, 2, 3, 10, 100, 700):
        print(full_key(k), partial_key(k), two_keys(k), floats(k), in_struct(k % 20))


main()
'''

EMPTY_POP = '''class Item:
    def __init__(self, d: int, n: int):
        self.d = d
        self.n = n


def pop_empty() -> int:
    h: list[Item] = []
    it = heappop(h, key=lambda it: it.d)
    return it.n


def main():
    print(pop_empty())


main()
'''

STDIN = '''import sys


def main():
    total = 0
    count = 0
    longest = 0
    for line in sys.stdin:
        parts = line.split()
        count += 1
        if len(line) > longest:
            longest = len(line)
        for p in parts:
            total += len(p)
    print(count, total, longest)


main()
'''

STDIN_AFTER = '''import sys


def main():
    last = "none"
    for line in sys.stdin:
        last = line
    print(len(last))


def other():
    for row in sys.stdin:
        pass
    print(len(row))


main()
'''

SORTS = '''def main():
    xs = [(i * 37) % 11 - 5 for i in range(40)]
    ys = [((i * 13) % 9) / 4.0 - 1.0 for i in range(40)]
    xs.sort()
    ys.sort()
    out: list[str] = []
    for v in xs:
        out.append(str(v))
    for v in ys:
        out.append(str(v))
    print(" ".join(out))
    zs = [1.0, 0.0, 2.0]
    nan = zs[1] / zs[1] if False else 0.0
    zs.sort()
    print(zs[0], zs[2])


main()
'''

STAY = '''class Item:
    def __init__(self, d: int, n: int):
        self.d = d
        self.n = n


def show(it: Item) -> int:
    return it.d + it.n


def escape(k: int) -> int:
    h: list[Item] = []
    for i in range(k):
        heappush(h, Item(i % 3, i), key=lambda it: it.d)
    it = heappop(h, key=lambda it: it.d)
    return show(it)


def peek(k: int) -> int:
    h: list[Item] = []
    for i in range(k):
        heappush(h, Item(i % 3, i), key=lambda it: it.d)
    return h[0].n


def main():
    print(escape(5), peek(5))


main()
'''


FIELDS = '''class T:
    def __init__(self, order: list[int], val: list[int], acc: list[int]):
        self.order = order
        self.val = val
        self.acc = acc


def total(t: T) -> int:
    s = 0
    for p in t.order:
        s = (s * 31 + t.val[p]) % 1000003
        t.acc.append(s)
    return s


def grows(t: T) -> int:
    s = 0
    for p in t.order:
        s += p
        if len(t.order) < 8:
            t.order.append(p + 1)
    return s


def main():
    t = T([3, 1, 2, 0], [10, 20, 30, 40], [])
    print(total(t), len(t.acc))
    g = grows(T([1], [1], []))
    if g < 0:
        print(g)


main()
'''


def cpython_run(directory, name, source, args=(), stdin=b'', prelude=''):
    path = Path(directory, name + '.py')
    path.write_text(prelude + source)
    r = subprocess.run([sys.executable, str(path), *map(str, args)], input=stdin, capture_output=True, timeout=300)
    return r.returncode, r.stdout.decode(), r.stderr.decode()


def run_in(exe, args=(), stdin=b''):
    r = subprocess.run([str(exe), *map(str, args)], input=stdin, capture_output=True, timeout=300)
    return r.returncode, r.stdout.decode(), r.stderr.decode()


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ProgramTests(unittest.TestCase):
    maxDiff = None

    def test_heaps_agree_with_cpython_and_the_legacy_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'heaps', HEAPS)
            for tag in ('ir', 'ir-checked'):
                self.assertLessEqual({'full_key', 'partial_key', 'two_keys', 'floats', 'in_struct', 'main'},
                                     built.ir[tag], built.fallback[tag])
            expected = cpython_run(tmp, 'heaps', HEAPS, prelude=PRELUDE)
            self.assertEqual(expected[0], 0, expected[2])
            for tag in built.exe:
                got = run_in(built.exe[tag])
                self.assertEqual(got[1], expected[1], tag)
                self.assertEqual(got[0], 0, tag)

    def test_an_empty_heap_raises_the_legacy_index_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'emptypop', EMPTY_POP)
            self.assertIn('pop_empty', built.ir['ir'])
            results = {tag: run_in(built.exe[tag]) for tag in built.exe}
            self.assertEqual(results['ir'], results['legacy'])
            self.assertEqual(results['ir-checked'], results['legacy'])
            self.assertEqual(results['ir'][0], 1)
            expected = cpython_run(tmp, 'emptypop', EMPTY_POP, prelude=PRELUDE)
            self.assertEqual(expected[0], 1)

    def test_the_stdin_line_loop(self):
        inputs = [b'', b'a', b'a b\n', b'x y z\n\nlast line without newline', b'one\r\ntwo\r\n',
                  b'q ' * 40000 + b'\n' + b'w' * 100000, b'\n\n\n', bytes(range(32, 127)) * 50 + b'\n']
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'stdin', STDIN)
            for tag in ('ir', 'ir-checked'):
                self.assertIn('main', built.ir[tag], built.fallback[tag])
            for data in inputs:
                expected = cpython_run(tmp, 'stdin', STDIN, stdin=data)
                for tag in built.exe:
                    got = run_in(built.exe[tag], stdin=data)
                    self.assertEqual(got[:2], expected[:2], (tag, data[:20]))

    def test_a_loop_variable_used_after_the_loop_stays_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'after', STDIN_AFTER)
            self.assertNotIn('other', built.ir['ir'])
            self.assertIn('optional or special', built.fallback['ir']['other'])
            for data in (b'a\nbb\n', b''):
                a, b = run_in(built.exe['ir'], stdin=data), run_in(built.exe['legacy'], stdin=data)
                self.assertEqual(a, b)

    def test_plain_numeric_sorts(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'sorts', SORTS)
            self.assertIn('main', built.ir['ir'], built.fallback['ir'])
            expected = cpython_run(tmp, 'sorts', SORTS)
            for tag in built.exe:
                self.assertEqual(run_in(built.exe[tag])[:2], expected[:2], tag)

    def test_records_that_escape_or_are_indexed_stay_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'stay', STAY)
            self.assertNotIn('escape', built.ir['ir'])
            self.assertNotIn('peek', built.ir['ir'])
            self.assertEqual(run_in(built.exe['ir']), run_in(built.exe['legacy']))

    def test_a_loop_over_a_numeric_field_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'fields', FIELDS)
            self.assertIn('total', built.ir['ir'], built.fallback['ir'])
            self.assertIn('resizes', built.fallback['ir']['grows'])      # the body resizes the list it walks
            expected = cpython_run(tmp, 'fields', FIELDS)
            for tag in built.exe:
                self.assertEqual(run_in(built.exe[tag])[:2], expected[:2], tag)

    def test_sanitizers_report_nothing_on_the_ir_builds(self):
        for name, source, stdin in (('heaps', HEAPS, b''), ('stdin', STDIN, b'a b\n' * 1000 + b'tail'),
                                    ('sorts', SORTS, b''), ('emptypop', EMPTY_POP, b'')):
            with self.subTest(program=name), tempfile.TemporaryDirectory() as tmp:
                results = {}
                for tag, env in (('legacy', {'AIL_IR': '0'}), ('ir', {'AIL_IR': 'verify'}),
                                 ('ir-checked', {'AIL_IR': 'verify', 'AIL_IR_EXC': 'checked'})):
                    built, _, _ = compile_program(tmp, name, source, tag, env, debug=True)
                    self.assertEqual(built.returncode, 0, built.stderr)
                    san = Path(tmp, name + '.' + tag + '.san')
                    cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined',
                                         '-fno-sanitize-recover=undefined', '-fno-omit-frame-pointer', '-pthread',
                                         str(Path(tmp, '%s.%s.d' % (name, tag), 'program.c')), '-lm', '-o', str(san)],
                                        capture_output=True, text=True)
                    self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
                    r = subprocess.run([str(san)], input=stdin, capture_output=True, timeout=300,
                                       env=dict(os.environ, ASAN_OPTIONS=ASAN_DETECT_LEAKS + ':abort_on_error=0',
                                                UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1'))
                    results[tag] = (r.returncode, r.stdout, r.stderr.decode(errors='replace'))
                for tag in ('ir', 'ir-checked'):
                    status, stdout, err = results[tag]
                    self.assertNotIn('runtime error', err, (name, tag))
                    self.assertNotIn('ERROR: AddressSanitizer', err, (name, tag, err[-800:]))
                    self.assertNotIn('ERROR: LeakSanitizer', err, (name, tag, err[-800:]))
                    self.assertEqual((status, stdout), results['legacy'][:2], (name, tag))


if __name__ == '__main__':
    unittest.main()
