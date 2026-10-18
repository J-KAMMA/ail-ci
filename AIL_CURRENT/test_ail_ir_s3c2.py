"""IR stage S3c-2: keyed sorts and comprehensions over lists (docs/design/IR_OWNERSHIP_DESIGN_v2.md section 18,
python/pkg-v12/ir/).

`xs.sort(key=lambda ..)` and `sorted(xs, key=lambda ..)` reach the IR as the legacy front end (sortkeys.py) leaves
them: key columns built by comprehensions, `_ail_sort_perm(perm, reverse, columns...)` and
`_ail_sort_apply(xs, perm)`. What this module pins:

* the two new ops (`list.sortperm`, `list.permute`) print, parse and verify, malformed uses are rejected by name,
  and the emitted C calls the legacy KEYSORT runtime;
* programs that sort lists of int, float and str by one or several keys, forwards and reversed, by the element or by
  a column of another list, with equal keys (stability), empty and one-element lists, and sorted() copies, agree
  with CPython and with the legacy build in both exception modes;
* a comprehension over an owned list (of int, float or str, with and without a filter) builds the same list;
* what stays legacy (sorting a parameter, a sort key over a struct field);
* sanitizers report nothing.
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

SORT = '''func @order(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], owned = ["p", "k", "xs"], sym = "order"} {
  %p = local.alloc {name = "p"} : place<obj<list<i64>>>
  %k = local.alloc {name = "k"} : place<obj<list<f64>>>
  %xs = local.alloc {name = "xs"} : place<obj<list<i64>>>
  %zero = const {value = 0} : i64
  %rp = list.ref %p : obj<list<i64>>
  %rk = list.ref %k : obj<list<f64>>
  %rx = list.ref %xs : obj<list<i64>>
  list.repeat %rx, %zero, %n
  list.sortperm %rp, %rk, %rx {rev = 0}
  list.permute %rx, %rp
  return %n
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
        fn, program = fn_of(SORT)
        verify.check(fn, program)
        printed = text.print_function(fn)
        self.assertEqual(text.print_function(text.parse_function(printed)), printed)

    def test_malformed_uses_are_rejected_by_name(self):
        self.bad(SORT.replace('{rev = 0}', '{rev = 2}'), 'needs rev = 0 or 1')
        self.bad(SORT.replace('list.sortperm %rp, %rk, %rx', 'list.sortperm %rk, %rk, %rx'), 'fills a list of int')
        self.bad(SORT.replace('list.permute %rx, %rp', 'list.permute %rx, %rk'), 'list.permute takes')
        self.bad(SORT.replace('list.permute %rx, %rp', 'list.permute %rx, %rx'), 'by itself')

    def test_effects(self):
        fn, program = fn_of(SORT)
        by_op = {i.op: E.instr_effects(i, fn, program) for i in I.walk(fn.body)}
        self.assertIn('Spine(Own(order,p))', by_op['list.sortperm'].writes)
        self.assertIn('Elem(Own(order,k))', by_op['list.sortperm'].reads)
        self.assertIn('ValueError', by_op['list.sortperm'].raises)
        self.assertIn('Elem(Own(order,xs))', by_op['list.permute'].writes)
        self.assertNotIn('Spine(Own(order,xs))', by_op['list.permute'].writes)

    def test_c_uses_the_legacy_keysort_runtime(self):
        fn, _ = fn_of(SORT)
        _, c, needs = emit_c.emit_function(fn)
        self.assertIn('ail_keycol _kc[2] = {{1, (const void *)(', c)
        self.assertIn('ail_keysort_perm(', c)
        self.assertIn('ail_perm_apply(', c)
        self.assertLessEqual({'LIST', 'KEYSORT', 'FLIST'}, needs['parts'])


SORTS = '''import sys


def fmt(xs: list[int]) -> str:
    out: list[str] = []
    for v in xs:
        out.append(str(v))
    return ",".join(out)


def by_value(n: int) -> str:
    xs = [(i * 37) % 11 - 5 for i in range(n)]
    xs.sort(key=lambda v: v)
    return fmt(xs)


def by_negative(n: int) -> str:
    xs = [(i * 37) % 11 - 5 for i in range(n)]
    xs.sort(key=lambda v: -v)
    return fmt(xs)


def reversed_keys(n: int) -> str:
    xs = [(i * 7) % 5 for i in range(n)]
    ids = [i for i in range(n)]
    ids.sort(key=lambda i: xs[i], reverse=True)
    return fmt(ids)


def pairs(n: int) -> str:
    a = [(i * 5) % 4 for i in range(n)]
    b = [(i * 3) % 7 for i in range(n)]
    ids = [i for i in range(n)]
    ids.sort(key=lambda i: (a[i], -b[i], i))
    return fmt(ids)


def floats(n: int) -> str:
    w = [((i * 13) % 9) / 4.0 for i in range(n)]
    ids = [i for i in range(n)]
    ids.sort(key=lambda i: w[i])
    return fmt(ids)


def words(text: str) -> str:
    ws = text.split()
    ws.sort(key=lambda s: (len(s), s))
    return "-".join(ws)


def by_str_key(n: int) -> str:
    names = [str((i * 17) % 23) for i in range(n)]
    ids = [i for i in range(n)]
    ids.sort(key=lambda i: names[i])
    return fmt(ids)


def copies(n: int) -> str:
    xs = [(i * 29) % 13 for i in range(n)]
    ys = sorted(xs, key=lambda v: -v)
    return str(len(xs)) + ":" + fmt(xs) + "|" + fmt(ys)


def filtered(n: int) -> str:
    shut = [i % 3 for i in range(n)]
    cand = [j for j in range(n) if shut[j] == 0]
    cand.sort(key=lambda j: (-shut[j], -j))
    doubled = [c * 2 for c in cand]
    return fmt(doubled)


def main():
    for n in (0, 1, 2, 3, 20, 64, 100):
        print(by_value(n))
        print(by_negative(n))
        print(reversed_keys(n))
        print(pairs(n))
        print(floats(n))
        print(by_str_key(n))
        print(copies(n))
        print(filtered(n))
    print(words("pear fig apple kiwi banana fig date"))
    print(words(""))


main()
'''

STAY = '''def sort_param(xs: list[int]) -> int:
    xs.sort(key=lambda v: -v)
    return xs[0]


def main():
    ys = [3, 1, 2]
    print(sort_param(ys), ys)


main()
'''


def cpython_run(directory, name, source, args=()):
    path = Path(directory, name + '.py')
    path.write_text(source)
    r = subprocess.run([sys.executable, str(path), *map(str, args)], capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout, r.stderr


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ProgramTests(unittest.TestCase):
    maxDiff = None

    def test_every_sort_agrees_with_the_legacy_build_and_cpython(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'sorts', SORTS)
            for tag in ('ir', 'ir-checked'):
                self.assertLessEqual({'fmt', 'by_value', 'by_negative', 'reversed_keys', 'pairs', 'floats', 'words',
                                      'by_str_key', 'copies', 'filtered', 'main'}, built.ir[tag],
                                     built.fallback[tag])
            expected = cpython_run(tmp, 'sorts', SORTS)
            for tag in built.exe:
                got = run(built.exe[tag])
                self.assertEqual(got[1], expected[1], tag)
                self.assertEqual(got[0], expected[0], tag)

    def test_sorting_a_parameter_stays_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'stay', STAY)
            self.assertNotIn('sort_param', built.ir['ir'])
            self.assertEqual(run(built.exe['ir']), run(built.exe['legacy']))

    def test_sanitizers_report_nothing_on_the_ir_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            for tag, env in (('ir', {'AIL_IR': 'verify'}), ('ir-checked', {'AIL_IR': 'verify', 'AIL_IR_EXC': 'checked'})):
                built, _, _ = compile_program(tmp, 'sorts', SORTS, tag, env, debug=True)
                self.assertEqual(built.returncode, 0, built.stderr)
                san = Path(tmp, 'sorts.' + tag + '.san')
                cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined',
                                     '-fno-sanitize-recover=undefined', '-fno-omit-frame-pointer', '-pthread',
                                     str(Path(tmp, 'sorts.%s.d' % tag, 'program.c')), '-lm', '-o', str(san)],
                                    capture_output=True, text=True)
                self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
                r = subprocess.run([str(san)], capture_output=True, timeout=300,
                                   env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0',
                                            UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1'))
                err = r.stderr.decode(errors='replace')
                self.assertEqual(r.returncode, 0, err[-800:])
                self.assertNotIn('Sanitizer', err)
                self.assertNotIn('runtime error', err)


if __name__ == '__main__':
    unittest.main()
