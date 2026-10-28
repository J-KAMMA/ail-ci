"""Struct-list element locals held without a reference (`_mark_borrowed_aliases`, pkg-v12/pyfunc.py).

`let e = s.evs[i]` and `for e in s.evs` retain the element, release the previous one in the slot and release it again at
exit; ticket_audit-2 did that for every record and for every event of every venue (26% of its instructions with the
reference-count helpers out of line). The analysis that lets a function hold the element without a reference required that
the whole function call nothing but a few builtins; it now accepts what cannot drop the last reference to an element:

* calls of a function that is given no struct, no list of structs and no callable (and returns none): it cannot reach the
  function's lists; builtins such as `read_bytes` and `set`; a method that takes elements out (`pop`, `clear`, `remove`) only
  on a receiver that holds no structs (an annotated int list, a dict or set field); the `key=` lambda of a sort;
* a store into a subscript whose base holds no structs (`s.caps[k] = v`);
* `for e in xs` as a binding, like `e = xs[i]`;
and it now also refuses a field list whose owning object is rebound (the old object, and with it the list, is freed).

What this module pins, against CPython in the legacy build and both IR modes and under ASan+UBSan+LSan (a borrow that
should have been refused is a use after free):

* a function with the accepted shapes holds `e` without a reference (plain assignment in the C, no store helper);
* each shape that can drop the element while `e` is alive keeps the reference: pop, an element store, `clear()`, `del`, a
  callee that is given the struct, a user method, the owner rebound, the field list reassigned, a pop through an alias of
  the list, a clear inside the loop that binds `e`.
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


class Ev:
    def __init__(self, num: int, cnt: int, price: int):
        self.num = num
        self.cnt = cnt
        self.price = price


class St:
    def __init__(self, evs: list[Ev], idx: dict[int, int], sold: set[int], rev: int):
        self.evs = evs
        self.idx = idx
        self.sold = sold
        self.rev = rev

    def reset(self) -> None:
        self.evs.clear()


def plain(a: int, b: int) -> int:
    return a * 3 + b


def drop_all(s: St) -> None:
    s.evs.clear()


def make(n: int) -> St:
    s = St([], {}, set(), 0)
    for i in range(n):
        s.idx[i * 7] = len(s.evs)
        s.evs.append(Ev(i * 7, i % 3, 10 + i))
    return s


def ok_bind(s: St, k: int) -> int:
    seats: list[int] = []
    seats.append(k)
    e = s.evs[s.idx[k]]
    e.cnt += 1
    s.rev += e.price + plain(e.cnt, k)
    s.sold.add(k)
    s.idx[k + 1] = s.idx[k]
    seats.clear()
    return e.cnt * 1000 + s.rev


def ok_loop(s: St) -> int:
    t = 0
    for e in s.evs:
        t += e.cnt * 3 + e.price
        e.cnt += 1
    top = s.evs
    top.sort(key=lambda g: (-g.cnt, g.num))
    for e in top:
        t = t * 31 % 1000003 + e.num
    return t


def no_pop(s: St) -> int:
    e = s.evs[1]
    s.evs.pop(1)
    e.cnt += 5
    return e.cnt * 100 + e.num


def no_store(s: St) -> int:
    e = s.evs[0]
    s.evs[0] = Ev(500, 5, 50)
    e.cnt += 7
    return e.cnt * 100 + s.evs[0].num + e.num


def no_clear(s: St) -> int:
    e = s.evs[0]
    s.evs.clear()
    e.cnt += 9
    return e.cnt * 100 + len(s.evs)


def no_callee(s: St) -> int:
    e = s.evs[0]
    drop_all(s)
    e.cnt += 11
    return e.cnt * 100 + len(s.evs)


def no_method(s: St) -> int:
    e = s.evs[0]
    s.reset()
    e.cnt += 13
    return e.cnt * 100 + len(s.evs)


def no_owner(n: int) -> int:
    s = make(n)
    e = s.evs[0]
    s = make(1)
    e.cnt += 17
    return e.cnt * 100 + e.num + len(s.evs)


def no_field(s: St) -> int:
    e = s.evs[0]
    s.evs = []
    e.cnt += 19
    return e.cnt * 100 + len(s.evs)


def no_alias(s: St) -> int:
    top = s.evs
    e = s.evs[0]
    top.pop(0)
    e.cnt += 23
    return e.cnt * 100 + len(s.evs)


def no_loop(s: St) -> int:
    t = 0
    for e in s.evs:
        t += e.cnt + 1
        if t > 2:
            s.evs.clear()
        t += e.price
    return t


def no_del(s: St) -> int:
    e = s.evs[0]
    del s.evs[0]
    e.cnt += 29
    return e.cnt * 100 + len(s.evs)


def main() -> int:
    n = int(sys.argv[1])
    s = make(n)
    print(ok_bind(s, 7), ok_bind(s, 14), s.rev, len(s.sold))
    print(ok_loop(s), ok_loop(s))
    for f in range(9):
        t = make(n)
        if f == 0:
            print(no_pop(t), len(t.evs))
        elif f == 1:
            print(no_store(t), len(t.evs))
        elif f == 2:
            print(no_clear(t))
        elif f == 3:
            print(no_callee(t))
        elif f == 4:
            print(no_method(t))
        elif f == 5:
            print(no_owner(n))
        elif f == 6:
            print(no_field(t))
        elif f == 7:
            print(no_alias(t), no_loop(make(n)))
        else:
            print(no_del(t))
    return 0


sys.exit(main())
'''

SAN_ENV = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0', UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')


def body_of(c, name):
    m = re.search(r'\n[\w *]+ %s\([^)]*\) \{\n' % name, c)
    assert m, name
    return c[m.end():c.index('\n}\n', m.end())]


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class BorrowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(prefix='ail-borrow-')
        cls.built = Built(cls.dir.name, 'borrow', PROGRAM, debug=True)
        cls.c = Path(cls.dir.name, 'borrow.legacy.d', 'program.c').read_text()

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_output_matches_cpython_in_every_mode(self):
        for n in (3, 4, 10, 60):
            expected = cpython_run(self.dir.name, 'borrow_cpython', PROGRAM, (n,))
            self.assertEqual(expected[0], 0, expected[2])
            for tag, exe in self.built.exe.items():
                self.assertEqual(run(exe, (n,))[:2], expected[:2], (tag, n))

    def test_the_accepted_shapes_hold_the_element_without_a_reference(self):
        for name in ('ok_bind', 'ok_loop'):
            body = body_of(self.c, name)
            self.assertRegex(body, r'v_e = ', name)
            self.assertNotIn('ail_obj_store_Ev(&v_e', body, name)

    def test_every_shape_that_can_drop_the_element_keeps_the_reference(self):
        for name in ('no_pop', 'no_store', 'no_clear', 'no_callee', 'no_method', 'no_owner', 'no_field', 'no_alias',
                     'no_loop', 'no_del'):
            body = body_of(self.c, name)
            self.assertIn('ail_obj_store_Ev(&v_e', body, name)

    def test_sanitizers_report_nothing(self):
        for tag in ('legacy', 'ir'):
            san = Path(self.dir.name, 'borrow.%s.san' % tag)
            cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
                                 '-fno-omit-frame-pointer', '-pthread', '-w',
                                 *map(str, sorted(Path(self.dir.name, 'borrow.%s.d' % tag).glob('program*.c'))), '-lm', '-o', str(san)],
                                capture_output=True, text=True)
            self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
            for n in (4, 40):
                r = subprocess.run([str(san), str(n)], capture_output=True, timeout=600, env=SAN_ENV)
                err = r.stderr.decode(errors='replace')
                self.assertEqual(r.returncode, 0, err[-1200:])
                self.assertNotIn('Sanitizer', err)
                self.assertNotIn('runtime error', err)
                expected = cpython_run(self.dir.name, 'borrow_cpython', PROGRAM, (n,))
                self.assertEqual(r.stdout.decode(), expected[1])


if __name__ == '__main__':
    unittest.main()
