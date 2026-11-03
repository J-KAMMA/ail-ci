"""Arena1 S4: append-only `list[str]` locals are dense `ail_pslist` values moved into the field.

A local that starts as `= []`, is only appended to and measured with `len`, and is stored once into
a `list[str]` struct field as its last mention is a packed string list for its whole lifetime: the
append copies text into the local, and `o.f = xs` moves the local's storage into the field instead
of building a second copy of the column. This module pins against CPython, the legacy emitter and
`AIL_UNIFIED_FORCE=1`:

* a reordered name column built from a field, with `len(xs)` inside the appends, a conditional
  append around an `if`, and a builder (`name += ...`) pushed by value;
* the source object stays independent after the field takes the local's storage;
* the C shape: `ail_pslist_*` for the moved local, the field-text hint on the reserve, and no
  `ail_bl_copy` of the builder before the packed push;
* the same programs in a shape that reads, returns or aliases the local stay on `ail_slist`, so
  the packed representation is chosen only where a view cannot escape;
* a whole-field store that repeats inside a `for`/`while` loop keeps `ail_slist`, because the move
  zeroes the local and later iterations would store an empty column.
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

from test_ail_ir_s3 import HAVE_CC, compile_program, cpython_run, run  # noqa: E402

MODES = (('legacy', {'AIL_IR': '0'}),
         ('ir', {'AIL_IR': 'verify'}),
         ('force', {'AIL_UNIFIED_FORCE': '1'}))

PROGRAM = '''class T:
    def __init__(self, nm: list[str], w: list[int]) -> None:
        self.nm = nm
        self.w = w


def reorder(src: T, order: list[int]) -> T:
    n = len(order)
    nm: list[str] = []
    ws: list[int] = []
    for k in range(n):
        i = order[k]
        nm.append(src.nm[i])
        ws.append(src.w[i] + len(nm))
    out = T([], [])
    out.nm = nm
    out.w = ws
    return out


def conditional(src: T, order: list[int], keep: list[bool]) -> T:
    nm: list[str] = []
    for i in order:
        if keep[i]:
            nm.append("x" + src.nm[i])
    out = T([], [])
    out.nm = nm
    return out


def builder(src: T, order: list[int]) -> T:
    nm: list[str] = []
    n = len(order)
    for i in range(n):
        name = src.nm[order[i]]
        if i % 2 == 0:
            name += "+"
            name += src.nm[order[(i + 1) % n]]
        nm.append(name)
    out = T([], [])
    out.nm = nm
    return out


def read_after(src: T, order: list[int]) -> T:
    nm: list[str] = []
    for i in order:
        nm.append(src.nm[i])
    out = T([], [])
    out.nm = nm
    print("read", nm[0])
    return out


def returned(src: T, order: list[int]) -> T:
    nm: list[str] = []
    for i in order:
        nm.append(src.nm[i])
    return T(nm, [])


def replace_self(t: T) -> None:
    n = len(t.nm)
    nm: list[str] = []
    for i in range(n):
        nm.append(t.nm[i])
    t.nm = nm


def empty_column() -> T:
    nm: list[str] = []
    out = T([], [])
    out.nm = nm
    return out


def iterate(src: T, order: list[int]) -> T:
    nm: list[str] = []
    for i in order:
        nm.append(src.nm[i])
    total = 0
    for s in nm:
        total += len(s)
    out = T([], [])
    out.nm = nm
    print("iterate", total)
    return out


def sorted_copy(src: T, order: list[int]) -> T:
    nm: list[str] = []
    for i in order:
        nm.append(src.nm[i])
    nm.sort()
    out = T([], [])
    out.nm = nm
    return out


def two_fields(src: T, order: list[int]) -> tuple[T, T]:
    nm: list[str] = []
    for i in order:
        nm.append(src.nm[i])
    a = T([], [])
    b = T([], [])
    a.nm = nm
    b.nm = nm
    return a, b


def first_name(nm: list[str]) -> str:
    return nm[0]


def passed(src: T, order: list[int]) -> str:
    nm: list[str] = []
    for i in order:
        nm.append(src.nm[i])
    out = T([], [])
    out.nm = nm
    return first_name(nm)


def explode(src: T, order: list[int]) -> T:
    nm: list[str] = []
    for i in order:
        nm.append(src.nm[i])
    if len(nm) > 0:
        raise ValueError("between")
    out = T([], [])
    out.nm = nm
    return out


def repeated_store(t: T, k: int) -> None:
    nm: list[str] = []
    nm.append("a")
    for i in range(k):
        t.nm = nm


def while_store(t: T, k: int) -> None:
    nm: list[str] = []
    nm.append("w")
    i = 0
    while i < k:
        t.nm = nm
        i += 1


def describe(t: T) -> str:
    return ",".join(t.nm) + ":" + ",".join(str(v) for v in t.w)


def main() -> int:
    src = T(["a", "bc", "d", "\\u65e5\\u672c"], [1, 2, 3, 4])
    order = [3, 0, 2, 1, 0]
    a = reorder(src, order)
    print("A", describe(a), describe(src))
    src.nm.append("tail")
    print("B", describe(a), describe(src))
    keep = [True, False, True, True, False]
    print("C", describe(conditional(src, order, keep)))
    print("D", describe(builder(src, order)))
    print("E", describe(read_after(src, [2, 0])))
    print("F", describe(returned(src, [1, 3, 0])))
    replace_self(src)
    print("G", describe(src))
    print("H", describe(empty_column()))
    small = [0, 2, 1]
    print("I", describe(iterate(src, small)))
    print("J", describe(sorted_copy(src, small)))
    a, b = two_fields(src, small)
    print("K", describe(a), describe(b))
    print("L", passed(src, small))
    try:
        explode(src, small)
    except ValueError as exc:
        print("M", exc)
    looped = T([], [])
    repeated_store(looped, 3)
    print("N", len(looped.nm), ",".join(looped.nm))
    whiled = T([], [])
    while_store(whiled, 3)
    print("O", len(whiled.nm), ",".join(whiled.nm))
    return 0


main()
'''


def body_of(c, name):
    match = re.search(r'\n[\w *]+ %s\([^)]*\) \{\n' % name, c)
    assert match, name
    return c[match.end():c.index('\n}\n', match.end())]


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class PackedStringListLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(prefix='ail-a1s4-')
        cls.exe = {}
        for tag, env in MODES:
            built, exe, _entries = compile_program(cls.dir.name, 'packed', PROGRAM, tag, env, debug=True)
            assert built.returncode == 0, '%s build failed:\n%s%s' % (
                tag, built.stdout.decode(errors='replace'), built.stderr.decode(errors='replace'))
            cls.exe[tag] = exe
        cls.c = Path(cls.dir.name, 'packed.legacy.d', 'program.c').read_text()

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_every_mode_matches_cpython(self):
        expected = cpython_run(self.dir.name, 'packed_reference', PROGRAM)
        self.assertEqual(expected[0], 0, expected[2])
        for tag, exe in self.exe.items():
            self.assertEqual(run(exe), expected, tag)

    def test_the_packed_local_is_pushed_reserved_and_moved(self):
        body = body_of(self.c, 'reorder')
        self.assertIn('ail_pslist_push(&v_nm,', body)
        self.assertRegex(body, r'ail_pslist_reserve\(&v_nm, [^;]*, \(v_src\)->f_nm\.tn\);')
        self.assertRegex(body, r'ail_pslist_move\(&v_[^;]*->f_nm, &v_nm\);')
        self.assertNotIn('ail_slist_push(&v_nm', body)
        self.assertNotIn('ail_obj_field_slist(', body)

    def test_a_conditional_append_and_a_builder_view_are_packed(self):
        cond = body_of(self.c, 'conditional')
        self.assertIn('ail_pslist_push(&v_nm,', cond)
        self.assertIn('ail_pslist_move(', cond)
        build = body_of(self.c, 'builder')
        self.assertIn('ail_pslist_push(&v_nm, v_name)', build)
        self.assertNotIn('ail_bl_copy(&v__sarena, v_name)', build)
        self.assertIn('ail_pslist_move(', build)

    def test_the_same_field_and_an_empty_column_are_packed(self):
        same = body_of(self.c, 'replace_self')
        self.assertIn('ail_pslist_push(&v_nm,', same)
        self.assertRegex(same, r'ail_pslist_reserve\(&v_nm, [^;]*, \(v_t\)->f_nm\.tn\);')
        self.assertRegex(same, r'ail_pslist_move\(&v_[^;]*->f_nm, &v_nm\);')
        empty = body_of(self.c, 'empty_column')
        self.assertIn('ail_pslist_move(', empty)

    def test_shapes_that_keep_the_local_alive_stay_slist(self):
        read = body_of(self.c, 'read_after')
        self.assertIn('ail_slist_push(&v_nm,', read)
        self.assertIn('ail_obj_field_slist(', read)
        self.assertNotIn('ail_pslist_move(', read)
        returned = body_of(self.c, 'returned')
        self.assertNotIn('ail_pslist_move(', returned)
        self.assertNotIn('ail_pslist_push(&v_nm,', returned)
        for name in ('iterate', 'sorted_copy', 'two_fields', 'passed'):
            body = body_of(self.c, name)
            self.assertNotIn('ail_pslist_push(&v_nm,', body, name)
            self.assertNotIn('ail_pslist_move(', body, name)

    def test_a_store_inside_a_loop_keeps_the_local_on_the_spine(self):
        for name in ('repeated_store', 'while_store'):
            body = body_of(self.c, name)
            self.assertIn('ail_slist_push(&v_nm,', body, name)
            self.assertNotIn('ail_pslist_push(&v_nm,', body, name)
            self.assertNotIn('ail_pslist_move(', body, name)

    def test_an_exception_between_appends_and_the_store_unwinds(self):
        body = body_of(self.c, 'explode')
        self.assertIn('ail_pslist_push(&v_nm,', body)
        self.assertRegex(body, r'ail_pslist_free\(&v_nm\);')

    def test_the_moved_local_owns_nothing_on_return(self):
        body = body_of(self.c, 'reorder')
        move = body.index('ail_pslist_move(')
        self.assertLess(move, body.rindex('ail_pslist_free(&v_nm);'))
        self.assertNotIn('ail_slist_free(&v_nm)', body)

    def test_sanitizers_report_nothing(self):
        san = Path(self.dir.name, 'packed.san')
        cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined',
                             '-fno-sanitize-recover=undefined', '-fno-omit-frame-pointer',
                             '-pthread', '-w', str(Path(self.dir.name, 'packed.legacy.d', 'program.c')),
                             '-lm', '-o', str(san)], capture_output=True, text=True)
        self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0',
                   UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')
        ran = subprocess.run([str(san)], capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(ran.returncode, 0, ran.stderr[-2000:])
        self.assertEqual(ran.stderr, '')


if __name__ == '__main__':
    unittest.main()
