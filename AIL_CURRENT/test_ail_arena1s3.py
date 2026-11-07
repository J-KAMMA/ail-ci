"""Arena1 S3: reserve a loop's known trip count before its `grow` appends.

A `for` over `range()`, over a list local/parameter, or over `len(list field)` that appends to a
plain local list at most once on every path reserves the trip count before the first append. The
reserve is capacity only; the appended values, their order and every early exit stay the same.

This module pins: unconditional, conditional, `if`/`else` and `continue` appends reserve; a huge
constant `range(10**12)` reserves the fixed cap instead of a billion elements; runtime, negative
and empty ranges reserve `max(0, hi - lo)`; a side-effecting bound, two appends on one path, an
append inside an inner loop (the outer loop), iterating the target list while appending to it, and
a read of the target before the append never reserve; `len(list field)`/list parameters do; and
the legacy, `AIL_IR=verify` and `AIL_UNIFIED_FORCE=1` builds all agree with CPython.
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
    def __init__(self, w: list[int]) -> None:
        self.w = w


def build(n: int) -> list[int]:
    xs: list[int] = []
    for i in range(n):
        xs.append(i)
    return xs


def conditional(n: int, keep: list[bool]) -> list[int]:
    xs: list[int] = []
    for i in range(n):
        if keep[i]:
            xs.append(i * 2)
    return xs


def branches(n: int) -> list[int]:
    xs: list[int] = []
    for i in range(n):
        if i % 2 == 0:
            xs.append(i)
        else:
            xs.append(-i)
    return xs


def continued(n: int) -> list[int]:
    xs: list[int] = []
    for i in range(n):
        if i % 2 == 0:
            continue
        xs.append(i)
    return xs


def huge_break() -> list[str]:
    xs: list[str] = []
    for i in range(10**12):
        xs.append("v")
        break
    return xs


def countdown(a: int, b: int) -> list[int]:
    xs: list[int] = []
    for i in range(a, b):
        xs.append(i)
    return xs


def limit() -> int:
    return 3


def side_effect() -> list[int]:
    xs: list[int] = []
    for i in range(limit()):
        xs.append(i)
    return xs


def twice(n: int) -> list[int]:
    xs: list[int] = []
    for i in range(n):
        xs.append(i)
        xs.append(i + 1)
    return xs


def nested(n: int) -> list[int]:
    xs: list[int] = []
    for i in range(n):
        for j in range(3):
            xs.append(i + j)
    return xs


def self_append() -> list[int]:
    xs: list[int] = [1, 2, 3, 4]
    for v in xs:
        if len(xs) >= 8:
            break
        xs.append(v)
    return xs


def from_array(xs: list[int]) -> list[int]:
    ys: list[int] = []
    for v in xs:
        ys.append(v)
    return ys


def from_len_field(t: T) -> list[int]:
    ys: list[int] = []
    for i in range(len(t.w)):
        ys.append(i)
    return ys


def read_first() -> list[int]:
    xs: list[int] = [7, 8, 9]
    for i in range(len(xs)):
        v = xs[i]
        xs.append(v)
    return xs


def empty_range(a: int, b: int) -> list[int]:
    xs: list[int] = []
    for i in range(a, b):
        xs.append(i)
    return xs


def main() -> int:
    print(build(5))
    print(conditional(5, [True, False, True, False, True]))
    print(branches(5))
    print(continued(6))
    print(huge_break())
    print(countdown(-5, -2))
    print(countdown(4, 1))
    print(countdown(-3, 2))
    print(side_effect())
    print(twice(4))
    print(nested(3))
    print(self_append())
    print(from_array([3, 1, 4]))
    print(from_len_field(T([9, 8, 7])))
    print(read_first())
    print(empty_range(5, 5))
    print(empty_range(7, 2))
    return 0


main()
'''


def body_of(c, name):
    match = re.search(r'\n[\w *]+ %s\([^)]*\) \{\n' % name, c)
    assert match, name
    return c[match.end():c.index('\n}\n', match.end())]


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class AppendLoopReserveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(prefix='ail-a1s3-')
        cls.exe = {}
        for tag, env in MODES:
            built, exe, _entries = compile_program(cls.dir.name, 'reserve', PROGRAM, tag, env, debug=True)
            assert built.returncode == 0, '%s build failed:\n%s%s' % (
                tag, built.stdout.decode(errors='replace'), built.stderr.decode(errors='replace'))
            cls.exe[tag] = exe
        cls.c = Path(cls.dir.name, 'reserve.legacy.d', 'program.c').read_text()

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_every_mode_matches_cpython(self):
        expected = cpython_run(self.dir.name, 'reserve_reference', PROGRAM)
        self.assertEqual(expected[0], 0, expected[2])
        for tag, exe in self.exe.items():
            self.assertEqual(run(exe), expected, tag)

    def test_unconditional_conditional_and_branch_appends_reserve(self):
        for name in ('build', 'conditional', 'branches', 'continued'):
            body = body_of(self.c, name)
            self.assertRegex(body, r'ail_list_reserve\(&v_xs, [^;]*v_n[^;]*\);', name)
            reserve = body.index('ail_list_reserve(&v_xs,')
            self.assertLess(reserve, body.index('for ('), name)

    def test_a_huge_constant_range_reserves_the_cap(self):
        body = body_of(self.c, 'huge_break')
        self.assertIn('ail_slist_reserve(&v_xs, 4194304);', body)
        self.assertNotIn('1000000000000, ', body.split('for (')[0])
        self.assertLess(body.index('ail_slist_reserve(&v_xs,'), body.index('for ('))

    def test_runtime_and_empty_ranges(self):
        body = body_of(self.c, 'countdown')
        self.assertRegex(body, r'ail_list_reserve\(&v_xs, [^;]*v_b[^;]*v_a[^;]*\);')
        empty = body_of(self.c, 'empty_range')
        self.assertRegex(empty, r'ail_list_reserve\(&v_xs, [^;]*\(uint64_t\)0[^;]*v_b[^;]*v_a[^;]*\);')

    def test_a_side_effecting_bound_does_not_reserve(self):
        body = body_of(self.c, 'side_effect')
        self.assertNotIn('ail_list_reserve(&v_xs', body)

    def test_two_appends_and_a_nested_append_do_not_reserve_the_outer_trip(self):
        twice = body_of(self.c, 'twice')
        self.assertNotIn('ail_list_reserve(&v_xs', twice)
        nest = body_of(self.c, 'nested')
        self.assertNotRegex(nest, r'ail_list_reserve\(&v_xs, [^;]*v_n[^;]*\);')
        self.assertIn('ail_list_reserve(&v_xs, 3);', nest)

    def test_iterating_the_target_or_reading_it_first_does_not_reserve(self):
        for name in ('self_append', 'read_first'):
            body = body_of(self.c, name)
            self.assertNotIn('ail_list_reserve(&v_xs', body, name)

    def test_iterating_a_parameter_and_a_field_length_reserve(self):
        array = body_of(self.c, 'from_array')
        self.assertRegex(array, r'ail_list_reserve\(&v_ys, [^;]*v_xs_len[^;]*\);')
        field = body_of(self.c, 'from_len_field')
        self.assertRegex(field, r'ail_list_reserve\(&v_ys, [^;]*f_w\.n[^;]*\);')

    def test_sanitizers_report_nothing(self):
        san = Path(self.dir.name, 'reserve.san')
        cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined',
                             '-fno-sanitize-recover=undefined', '-fno-omit-frame-pointer',
                             '-pthread', '-w', str(Path(self.dir.name, 'reserve.legacy.d', 'program.c')),
                             '-lm', '-o', str(san)], capture_output=True, text=True)
        self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0',
                   UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')
        ran = subprocess.run([str(san)], capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(ran.returncode, 0, ran.stderr[-2000:])
        self.assertEqual(ran.stderr, '')


if __name__ == '__main__':
    unittest.main()
