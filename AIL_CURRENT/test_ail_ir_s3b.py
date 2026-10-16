"""IR stage S3b: the sharing core on the IR (docs/design/IR_OWNERSHIP_DESIGN_v2.md section 13,
python/pkg-v12/ir/ownership.py).

* `ys = xs` has Python's meaning in the IR: one list, two names. The lowering records every such
  event as `list.share`; liveness and effects on the IR decide move (Rule M), take, move-then-borrow
  (M'), rename (B) or refusal (Rule X: a box is needed, stage S3e). The programs here agree with
  CPython in the IR build wherever the IR takes them -- including the ones the legacy build
  (value semantics) prints differently, listed as the documented divergence (W-ALIAS).
* Rule X sites keep the function on the legacy emitter, with the reason.
* Explicit copies (`xs[:]`, `list(xs)`, `xs.copy()`) are real copies; a copy of a dead source is a move.
* An IR function returns a list by value to an IR caller (`<sym>__irl`): no spill-slot copy.
* A list returned by a call and passed straight on is a temporary the caller drops.
* Drops on every edge, ASan + UBSan + LSan clean, both exception modes, generated programs.
* A `list.share` that survives lowering is a verifier error; `list.copy` verifies by type.
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'python' / 'pkg-v12'), str(ROOT)]

from ir import ir as I                       # noqa: E402
from ir import ownership, text, verify       # noqa: E402
from ir import emit_c                        # noqa: E402
import test_ail_ir_s3 as S3                  # noqa: E402
from test_ail_ir_s3 import (Built, cpython_run, run, last_line, compile_program, HAVE_CC)   # noqa: E402

# --------------------------------------------------------------------------------------------
# The programs (Python syntax: they run unchanged under CPython)
# --------------------------------------------------------------------------------------------

HEAD = '''
class S:
    def __init__(self, n: int):
        self.n = n
        self.xs = [0]
        self.ys = [0]
        self.cnt = 0


def total(xs: list[int]) -> int:
    r = len(xs)
    for i in range(len(xs)):
        r = (r * 31 + xs[i]) % 1000003
    return r
'''

# every function here is taken by the IR; CPython shares, the legacy build copies
SHARE = HEAD + '''

def alias_write(n: int) -> int:
    xs = [1, 2, 3]
    ys = xs
    ys[0] = n
    return xs[0]


def alias_push(n: int) -> int:
    xs = [1, 2, 3]
    ys = xs
    for i in range(n):
        ys.append(i)
    return len(xs) * 1000 + total(xs)


def alias_both(n: int) -> int:
    xs = [n] * 4
    ys = xs
    ys[1] = 7
    xs[2] = 9
    return total(xs) + total(ys) * 3


def alias_chain(n: int) -> int:
    a = [n, 2, 3]
    b = a
    c = b
    c[0] = 40
    b.append(5)
    return a[0] + b[0] + c[0] + len(a)


def loop_alias(n: int) -> int:
    t = 0
    for i in range(n):
        xs = [i, i + 1, i + 2]
        ys = xs
        ys[0] += 10
        t += xs[0] + ys[2]
    return t


def alias_try(n: int) -> int:
    xs = [1, 2, 3]
    ys = xs
    t = 0
    try:
        ys[n] = 9
        t = 1
    except IndexError:
        t = 2
    return t * 100 + xs[0] + xs[2]


def move_try(n: int) -> int:
    xs = [1, 2, 3]
    ys = xs
    try:
        ys[n] = 9
    except IndexError:
        return xs[0]
    return ys[1]


def swap3(n: int) -> int:
    a = [1] * n
    b = [2] * n
    t = a
    a = b
    b = t
    a[0] = 7
    return a[0] * 100 + b[0]


def swap_loop(n: int) -> int:
    a = [q for q in range(8)]
    b = [0] * 8
    for g in range(n):
        for i in range(8):
            b[i] = (a[(i + 1) % 8] + g) % 97
        tmp = a
        a = b
        b = tmp
    return total(a)


def field_move(s: S, n: int) -> int:
    a = []
    for i in range(n):
        a.append(i * 2 + 1)
    s.xs = a
    return len(s.xs)


def field_borrow_write(s: S, n: int) -> int:
    a = [1, 2, 3]
    s.xs = a
    a[0] = n
    s.xs[1] = n + 1
    a.append(7)
    return a[0] * 1000 + a[1] * 100 + len(s.xs) * 10 + s.xs[3]


def field_borrow_loop(s: S, n: int) -> int:
    a = [q for q in range(n)]
    s.xs = a
    t = 0
    for v in a:
        t += v
    return t + len(s.xs)


def take_swap(s: S, n: int) -> int:
    s.xs = [n, n + 1]
    s.ys = [7]
    tmp = s.xs
    s.xs = s.ys
    s.ys = tmp
    s.xs.append(1)
    return len(s.xs) * 100 + len(s.ys) * 10 + s.ys[0] + s.xs[1]


def field_alias_local(s: S, n: int) -> int:
    s.xs = [5, 6, 7]
    ys = s.xs
    ys[0] = n
    return s.xs[0] * 10 + len(ys)


def read_only_alias(n: int) -> int:
    xs = [n, 2, 3]
    ys = xs
    return total(xs) + total(ys)


def main():
    s = S(3)
    for n in (0, 1, 3, 5):
        print(alias_write(n), alias_push(n), alias_both(n), alias_chain(n), loop_alias(n))
        print(alias_try(n), alias_try(n + 9), move_try(n), move_try(n + 9), swap3(n + 1), swap_loop(n))
        print(field_move(s, n), total(s.xs), field_borrow_write(s, n), total(s.xs), field_borrow_loop(s, n),
              total(s.xs))
        print(take_swap(s, n), total(s.xs), total(s.ys), field_alias_local(s, n), total(s.xs),
              read_only_alias(n))


main()
'''
SHARE_FUNCS = ['alias_write', 'alias_push', 'alias_both', 'alias_chain', 'loop_alias', 'alias_try', 'move_try',
               'swap3', 'swap_loop', 'field_move', 'field_borrow_write', 'field_borrow_loop', 'take_swap',
               'field_alias_local', 'read_only_alias']

# Rule X: the second name outlives a change of the first, or two paths merge: two owners with
# overlapping lifetimes, a box (stage S3e). The functions stay on the legacy emitter.
REFUSED = HEAD + '''

def helper(s: S) -> int:
    s.xs = [9, 9]
    return 0


def called_after(s: S, n: int) -> int:
    a = [1, 2, 3]
    s.xs = a
    helper(s)
    return a[0]


def alias_in_branch(n: int) -> int:
    xs = [1, 2, 3]
    ys = [9, 9, 9]
    if n > 2:
        ys = xs
        ys[0] = 100
    ys[1] += 1
    return total(xs) * 10 + total(ys)


def rebind_while_live(n: int) -> int:
    xs = [1, 2, 3]
    ys = xs
    xs.append(n)
    xs = [0]
    return len(ys) * 10 + len(xs)


def loop_resize_alias(n: int) -> int:
    xs = [1, 2, 3]
    ys = xs
    t = 0
    for v in xs:
        t += v
        if len(ys) < 6:
            ys.append(v)
    return t


def double_buffer(n: int) -> int:
    a = [1, 2, 3, 4]
    b = [0] * 4
    for g in range(n):
        for i in range(4):
            b[i] = a[(i + 1) % 4] + g
        a = b
    return a[0] * 10 + a[3]


def two_fields(s: S, n: int) -> int:
    s.xs = [1, 2, 3]
    s.ys = s.xs
    s.ys[0] = n
    return s.xs[0]


def grow(s: S, xs: list[int]) -> int:
    s.xs.append(len(xs))
    return len(xs)


def lend_while_growing(s: S, n: int) -> int:
    a = [1, 2, 3]
    s.xs = a
    return grow(s, a)


def take_self_copy(s: S, n: int) -> int:
    s.xs = [1, 2, 3]
    tmp = s.xs
    s.xs = s.xs[:]
    tmp.append(n)
    return len(s.xs) * 10 + len(tmp)


def take_then_raise(s: S, n: int) -> int:
    s.xs = [1, 2, 3]
    s.ys = [4, 5]
    tmp = s.xs
    t = tmp[n]
    s.xs = [9]
    return t + len(tmp) + len(s.xs)


def main():
    s = S(3)
    print(called_after(s, 8), total(s.xs))
    print(alias_in_branch(1), alias_in_branch(5))
    print(rebind_while_live(4))
    print(loop_resize_alias(0))
    print(double_buffer(3))
    print(two_fields(s, 8))
    print(lend_while_growing(s, 1), total(s.xs))
    print(take_then_raise(s, 1), take_self_copy(s, 4))


main()
'''
REFUSED_FUNCS = ['called_after', 'alias_in_branch', 'rebind_while_live', 'loop_resize_alias', 'double_buffer',
                 'two_fields', 'lend_while_growing', 'take_then_raise', 'take_self_copy']

COPIES = HEAD + '''

def copies(n: int) -> int:
    xs = [1, 2, 3]
    ys = xs[:]
    zs = list(xs)
    ws = xs.copy()
    ys[0] = 10
    zs[1] = 20
    ws.append(4)
    xs[2] = n
    return total(xs) * 7 + total(ys) * 5 + total(zs) * 3 + total(ws)


def copy_dead(n: int) -> int:
    xs = [n] * 5
    ys = xs[:]
    ys[0] = 3
    return total(ys)


def copy_field(s: S, n: int) -> int:
    s.xs = [1, 2, 3]
    ys = s.xs.copy()
    ys[0] = n
    return s.xs[0] * 100 + ys[0]


def copy_param(xs: list[int], n: int) -> int:
    ys = list(xs)
    ys[0] = n
    ys.append(1)
    return total(ys)


def self_copy(n: int) -> int:
    xs = [1, 2, 3]
    xs = xs[:]
    xs[0] = n
    return total(xs)


def into_field(s: S, n: int) -> int:
    xs = [n, n, n]
    s.xs = xs[:]
    xs[0] = 1
    s.ys = xs[:]
    return len(s.xs) * 10 + s.ys[0] + s.xs[0]


def main():
    s = S(3)
    for n in (0, 4):
        print(copies(n), copy_dead(n), copy_field(s, n), copy_param([5, 6, 7], n), self_copy(n),
              into_field(s, n))


main()
'''
COPY_FUNCS = ['copies', 'copy_dead', 'copy_field', 'copy_param', 'self_copy', 'into_field']

LISTRET = HEAD + '''

def make(n: int) -> list[int]:
    a = [0] * n
    for i in range(n):
        a[i] = (i * 7 + 3) % 11
    return a


def twice(n: int) -> list[int]:
    a = make(n)
    b = make(n + 1)
    a.append(b[0])
    return a


def fmake(n: int) -> list[float]:
    f = [0.5] * n
    for i in range(n):
        f[i] = f[i] + i
    return f


def fsum(f: list[float]) -> int:
    t = 0.0
    for x in f:
        t += x
    return int(t * 4)


def arg_temp(n: int) -> int:
    return total(make(n)) + total(twice(n)) * 3 + fsum(fmake(n))


def relist(n: int) -> int:
    t = 0
    for i in range(n):
        a = twice(i)
        a = twice(len(a))
        t += total(a)
    return t


def main():
    for n in (0, 3, 8):
        print(arg_temp(n), relist(n))


main()
'''
LISTRET_FUNCS = ['make', 'twice', 'fmake', 'fsum', 'arg_temp', 'relist']


# --------------------------------------------------------------------------------------------
# Generated programs: sharing statements over three lists and a struct field
# --------------------------------------------------------------------------------------------

class _ShareGen(object):
    NAMES = ('a', 'b', 'c')

    def __init__(self, seed):
        self.r = random.Random(seed)
        self.q = 0

    def k(self, lo, hi):
        return self.r.randint(lo, hi)

    def name(self):
        return self.r.choice(self.NAMES)

    def op(self):
        c = self.k(1, 40)
        n, m = self.name(), self.name()
        choice = self.r.randint(0, 17)
        if choice == 0:
            return ['%s.append((t + %d) %% 97)' % (n, c)]
        if choice == 1:
            return ['if len(%s) > 1:' % n, '    t += %s.pop()' % n]
        if choice == 2:
            return ['%s[(t + %d) %% len(%s)] += t %% 13 + 1' % (n, c, n)]
        if choice == 3:
            return ['t = (t * 31 + %s[(t + %d) %% len(%s)]) %% 1000003' % (n, c, n)]
        if choice == 4:
            return ['t = (t + total(%s) + total(%s)) %% 1000003' % (n, m)]
        if choice in (5, 6, 7):
            return ['%s = %s' % (n, m)] if n != m else ['t += 1']
        if choice == 8:
            return ['w = %s' % n, '%s = %s' % (n, m), '%s = w' % m] if n != m else ['t += 2']
        if choice == 9:
            return ['%s = %s[:]' % (n, m)]
        if choice == 10:
            return ['%s = list(%s)' % (n, m)]
        if choice == 11:
            return ['s.xs = %s' % n]
        if choice == 12:
            return ['%s = s.xs' % n]
        if choice == 13:
            return ['s.xs[(t + %d) %% len(s.xs)] += 3' % c, 't += len(s.xs)']
        if choice == 14:
            return ['%s = mk((t + %d) %% 6 + 1)' % (n, c)]
        if choice == 15:
            self.q += 1
            return ['%s = [(q%d * %d + t) %% 53 for q%d in range((t + %d) %% 5 + 1)]' % (n, self.q, c, self.q, c)]
        if choice == 16:
            return ['s.xs = %s' % n, '%s[0] += %d' % (n, c)]
        return ['s.ys = s.xs', 's.xs = %s' % n] if False else ['t = (t + len(s.xs)) % 1000003']

    def worker(self, name):
        lines = ['def %s(s: S, n: int) -> int:' % name, '    t = n %% %d' % self.k(5, 13),
                 '    a = mk(n % 5 + 2)', '    b = mk(n % 3 + 1)', '    c = [1, 2, 3]', '    w = [0]']
        for _ in range(self.k(5, 12)):
            for line in self.op():
                lines.append('    ' + line)
        lines += ['    s.cnt += len(a) + len(b) + len(c)',
                  '    return (t + total(a) + total(b) * 3 + total(c) * 5 + total(s.xs)) % 1000003']
        return lines

    def program(self, keep=None):
        '''(source, workers). `keep` (a set of worker names) drops the others from the program: the
        workers are generated in the same order whatever is kept, so a seed names the same bodies.'''
        lines = [HEAD.strip('\n'), '', '',
                 'def mk(n: int) -> list[int]:', '    a = [0] * n', '    for i in range(n):',
                 '        a[i] = (i * 5 + 1) % 17', '    return a', '', '']
        workers = ['w%d' % i for i in range(4)]
        bodies = [self.worker(w) + ['', ''] for w in workers]
        args = [[self.k(0, 40) for w in workers] for rep in range(2)]
        for w, body in zip(workers, bodies):
            if keep is None or w in keep:
                lines += body
        lines += ['def main():', '    s = S(3)']
        for rep in range(2):
            for w, a in zip(workers, args[rep]):
                if keep is None or w in keep:
                    lines.append('    print(%s(s, %d))' % (w, a))
        lines += ['    print(s.cnt, total(s.xs))', '', '', 'main()', '']
        return '\n'.join(lines), workers


# --------------------------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------------------------

IR_COPY = '''func @cp(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], owned = ["a", "b"], sym = "cp"} {
  %a = local.alloc {name = "a"} : place<obj<list<i64>>>
  %b = local.alloc {name = "b"} : place<obj<list<i64>>>
  %ra = list.ref %a : obj<list<i64>>
  %zero = const {value = 0} : i64
  list.repeat %ra, %zero, %n
  %rb = list.ref %b : obj<list<i64>>
  %ra2 = list.ref %a : obj<list<i64>>
  list.copy %rb, %ra2
  %rb2 = list.ref %b : obj<list<i64>>
  %l = list.len %rb2 : i64
  return %l
}
'''


def fn_of(source):
    f = text.parse_function(source)
    prog = I.Program()
    prog.add(f)
    return f, prog


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class SharingTests(unittest.TestCase):
    maxDiff = None

    def build_all(self, tmp, name, source):
        built = Built(tmp, name, source)
        return built

    def entries(self, tmp, name, source, tag='ir'):
        built, exe, entries = compile_program(tmp, name, source, tag, {'AIL_IR': 'verify'})
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return exe, {e['fn']: e for e in entries}

    # ------------------------------------------------------------------ the IR itself
    def test_list_copy_verifies_prints_and_emits(self):
        f, prog = fn_of(IR_COPY)
        verify.check(f, prog)
        again = text.parse_function(text.print_function(f))
        self.assertEqual(text.print_function(again), text.print_function(f))
        _, c, needs = emit_c.emit_function(f)
        self.assertIn('ail_list_reserve(&ir', c)
        self.assertIn('ail_list_free(&v_b)', c)
        bad = IR_COPY.replace('list.copy %rb, %ra2', 'list.copy %rb, %zero')
        with self.assertRaisesRegex(I.IRError, 'list.copy takes'):
            verify.check(*fn_of(bad))

    def test_a_list_share_that_survives_lowering_is_a_verifier_error(self):
        f, prog = fn_of(IR_COPY.replace('list.copy', 'list.share'))
        with self.assertRaisesRegex(I.IRError, 'list.share is resolved'):
            verify.check(f, prog)

    def resolve_text(self, body):
        src = '''func @f(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], owned = ["a", "b"], sym = "f"} {
  %a = local.alloc {name = "a"} : place<obj<list<i64>>>
  %b = local.alloc {name = "b"} : place<obj<list<i64>>>
  %zero = const {value = 0} : i64
  %ra = list.ref %a : obj<list<i64>>
  list.repeat %ra, %zero, %n
@BODY@
}
'''.replace('@BODY@', body)
        f, prog = fn_of(src)
        r = ownership.resolve(f, prog)
        verify.check(f, prog)
        return f, r

    def test_a_dead_source_is_moved_and_a_live_one_is_renamed(self):
        dead = '''  %rb = list.ref %b : obj<list<i64>>
  %ra1 = list.ref %a : obj<list<i64>>
  list.share %rb, %ra1 {dst = "b", src = "a"}
  %rb2 = list.ref %b : obj<list<i64>>
  %l = list.len %rb2 : i64
  return %l'''
        f, r = self.resolve_text(dead)
        self.assertEqual((r.stats['moves'], r.stats['renames']), (1, 0))
        self.assertIn('list.move', text.print_function(f))
        live = '''  %rb = list.ref %b : obj<list<i64>>
  %ra1 = list.ref %a : obj<list<i64>>
  list.share %rb, %ra1 {dst = "b", src = "a"}
  %rb2 = list.ref %b : obj<list<i64>>
  list.push %rb2, %n
  %ra3 = list.ref %a : obj<list<i64>>
  %l = list.len %ra3 : i64
  return %l'''
        f, r = self.resolve_text(live)
        self.assertEqual((r.stats['moves'], r.stats['renames']), (0, 1))
        printed = text.print_function(f)
        self.assertNotIn('list.move', printed)
        self.assertNotIn('list.share', printed)
        self.assertEqual(r.walias[0]['differs'], True)

    def test_the_first_name_reassigned_while_the_second_lives_needs_a_box(self):
        src = '''  %rb = list.ref %b : obj<list<i64>>
  %ra1 = list.ref %a : obj<list<i64>>
  list.share %rb, %ra1 {dst = "b", src = "a"}
  %ra0 = list.ref %a : obj<list<i64>>
  list.push %ra0, %n
  %ra2 = list.ref %a : obj<list<i64>>
  list.lit %ra2, %n
  %rb2 = list.ref %b : obj<list<i64>>
  %l = list.len %rb2 : i64
  return %l'''
        with self.assertRaisesRegex(ownership.NeedsBox, 'reassigned while the second'):
            self.resolve_text(src)

    # ------------------------------------------------------------------ programs
    def check_ir_equals_cpython(self, name, source, funcs, differs_from_legacy=True):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, name, source)
            for tag in ('ir', 'ir-checked'):
                self.assertEqual(set(funcs) - built.ir[tag], set(), '%s: %s' % (tag, built.fallback[tag]))
            runs = {tag: run(built.exe[tag]) for tag in built.exe}
            expected = cpython_run(tmp, name, source)
            self.assertEqual(expected[0], 0, expected[2])
            self.assertEqual(runs['ir'], runs['ir-checked'])
            self.assertEqual(runs['ir'][1], expected[1], name)
            self.assertEqual(runs['ir'][0], 0)
            if differs_from_legacy is None:
                pass                      # the legacy build is not comparable (see the test)
            elif differs_from_legacy:
                # value semantics (legacy) and sharing (CPython, IR) tell these programs apart: the
                # documented divergence of design section 1.5, reported by W-ALIAS
                self.assertNotEqual(runs['legacy'][1], expected[1], 'legacy was expected to differ: %s' % name)
            else:
                self.assertEqual(runs['legacy'][1], expected[1])
            return built, runs

    def test_sharing_programs_in_the_ir_agree_with_cpython(self):
        self.check_ir_equals_cpython('share', SHARE, SHARE_FUNCS)

    def test_rule_x_sites_stay_on_the_legacy_emitter_with_the_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'refused', REFUSED)
            for tag in ('ir', 'ir-checked'):
                for fn in REFUSED_FUNCS:
                    if fn == 'helper':
                        continue
                    self.assertNotIn(fn, built.ir[tag], fn)
                for fn in ('called_after', 'alias_in_branch', 'rebind_while_live', 'loop_resize_alias',
                           'two_fields', 'lend_while_growing', 'take_then_raise', 'take_self_copy'):
                    self.assertIn('Rule X', built.fallback[tag][fn], (fn, built.fallback[tag][fn]))
            runs = {tag: run(built.exe[tag]) for tag in built.exe}
            self.assertEqual(runs['ir'], runs['legacy'])
            self.assertEqual(runs['ir-checked'], runs['legacy'])
            expected = cpython_run(tmp, 'refused', REFUSED)
            # where CPython and the legacy build differ the box would have made the IR equal CPython
            # (stage S3e); these are the sites W-ALIAS must name
            self.assertNotEqual(runs['legacy'][1], expected[1])

    def test_explicit_copies_are_copies_and_a_dead_source_is_a_move(self):
        # (the legacy build fails on `xs = xs[:]` at run time: "index out of range"; the IR build is right)
        _, runs = self.check_ir_equals_cpython('copies', COPIES, COPY_FUNCS, differs_from_legacy=None)
        with tempfile.TemporaryDirectory() as tmp:
            exe, entries = self.entries(tmp, 'copies', COPIES)
            self.assertEqual(entries['copy_dead']['sharing']['copies_moved'], 1)
            self.assertNotIn('copies_moved', {k for k, v in entries['copies'].get('sharing', {}).items() if v})

    def test_list_results_pass_between_ir_functions_by_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            built, runs = self.check_ir_equals_cpython('listret', LISTRET, LISTRET_FUNCS, differs_from_legacy=False)
            ir = Path(tmp, 'listret.ir.d')
            result, exe, entries = compile_program(tmp, 'listret', LISTRET, 'ir', {'AIL_IR': 'verify'}, debug=True)
            c = Path(tmp, 'listret.ir.d', 'program.c').read_text()
            self.assertIn('make__irl(', c)
            # the legacy entry point stays, as a wrapper over the by-value one
            self.assertRegex(c, r'int64_t make\(int64_t v_n, int64_t \*_out, int64_t _cap\)')
            body = c[c.index('ail_list twice__irl'):]
            body = body[:body.index('\n}\n')]
            self.assertNotIn('adopt_return', body)
            self.assertNotIn('ail_list_return(', body)

    def test_walias_names_the_sites_where_the_two_meanings_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe, entries = self.entries(tmp, 'share', SHARE)
        differs = dict((fn, [w for w in e.get('walias', ()) if w['differs']]) for fn, e in entries.items())
        for fn in ('alias_write', 'alias_push', 'alias_both', 'alias_chain', 'loop_alias', 'alias_try',
                   'field_borrow_write', 'field_alias_local'):
            self.assertTrue(differs[fn], fn)
        for fn in ('read_only_alias', 'swap3', 'swap_loop', 'field_move', 'take_swap'):
            self.assertFalse(differs.get(fn), fn)
        w = entries['alias_write']['walias'][0]
        self.assertEqual((w['dst'], w['src'], w['rule']), ('ys', 'xs', 'rename'))

    def test_walias_covers_functions_that_stay_on_the_legacy_emitter(self):
        # a double buffer written for value semantics (design section 1.5: grid_life-ail-2's `ga = gb`)
        src = HEAD + '''

def life(n: int) -> int:
    ga = [1, 2, 3, 4]
    gb = [0] * 4
    for g in range(n):
        for i in range(4):
            gb[i] = ga[(i + 1) % 4] + g
        ga = gb
    print(ga[0])
    return ga[3]


def tidy(n: int) -> int:
    ga = [1, 2, 3, 4]
    gb = ga[:]
    gb[0] = n
    print(ga[0])
    return gb[0]


def main():
    life(3)
    tidy(2)


main()
'''
        with tempfile.TemporaryDirectory() as tmp:
            exe, entries = self.entries(tmp, 'life', src)
        self.assertEqual(entries['life']['path'], 'legacy')
        notes = entries['life']['walias']
        self.assertEqual([(w['dst'], w['src'], w['line']) for w in notes if w['differs']][0][:2], ('ga', 'gb'))
        self.assertNotIn('walias', entries['tidy'])

    def test_sharing_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe, entries = self.entries(tmp, 'share', SHARE)
        sh = lambda fn: entries[fn]['sharing']
        self.assertEqual(sh('swap3')['moves'], 3)
        self.assertEqual(sh('alias_write')['renames'], 1)
        self.assertEqual(sh('alias_chain')['renames'], 2)
        self.assertEqual(sh('field_move')['field_moves'], 1)
        self.assertEqual((sh('field_borrow_write')['field_moves'], sh('field_borrow_write')['field_borrows']), (1, 1))
        self.assertEqual((sh('take_swap')['takes'], sh('take_swap')['field_moves']), (2, 1))   # tmp = s.xs; s.xs = s.ys; s.ys = tmp
        self.assertEqual(sh('field_alias_local')['field_borrows'], 1)
        for fn in SHARE_FUNCS:
            self.assertEqual(sh(fn)['boxes'], 0)

    def test_drops_follow_the_list_that_is_shared(self):
        # xs is dropped at its last mention by name; the list lives on through ys, so the drop must
        # not come first, and the list must still be freed (LSan below; here: no use after free)
        src = HEAD + '''

def late(n: int) -> int:
    xs = [n] * 6
    ys = xs
    t = 0
    for i in range(3):
        t += total(xs)
    for i in range(3):
        t += total(ys) + ys[i]
        ys[i] = t % 7
    return t + total(ys)


def main():
    print(late(4), late(9))


main()
'''
        self.check_ir_equals_cpython('late', src, ['late'], differs_from_legacy=False)

    # ------------------------------------------------------------------ sanitizers
    def sanitize(self, name, source):
        return S3.ProgramTests.sanitize(self, name, source)

    @unittest.skipUnless(shutil.which('gcc'), 'no gcc')
    def test_sanitizers_report_nothing_on_the_sharing_builds(self):
        for name, source in (('share', SHARE), ('refused', REFUSED), ('copies', COPIES), ('listret', LISTRET)):
            with self.subTest(program=name):
                runs = self.sanitize(name, source)
                for tag in ('ir', 'ir-checked'):
                    for k, (status, stdout, stderr) in enumerate(runs[tag]):
                        self.assertNotIn('runtime error', stderr, (name, tag, k))
                        self.assertNotIn('AddressSanitizer', stderr, (name, tag, k))
                        self.assertNotIn('LeakSanitizer', stderr.replace('LeakSanitizer is disabled', ''),
                                         (name, tag, k, stderr[-800:]))
                self.assertEqual(runs['ir'][0][:2], runs['ir-checked'][0][:2])
                if name in ('listret', 'refused'):
                    self.assertEqual(runs['ir'][0][:2], runs['legacy'][0][:2])


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class GeneratedSharingTests(unittest.TestCase):
    SEEDS = (2, 5, 13, 21, 34)

    def test_generated_sharing_programs_agree_with_cpython_wherever_the_ir_takes_them(self):
        taken = refused = 0
        with tempfile.TemporaryDirectory() as tmp:
            for seed in self.SEEDS:
                with self.subTest(seed=seed):
                    source, workers = _ShareGen(seed).program()
                    built = Built(tmp, 'g%d' % seed, source)
                    expected = cpython_run(tmp, 'g%d' % seed, source)
                    self.assertEqual(expected[0], 0, expected[2] + source)
                    runs = {tag: run(built.exe[tag]) for tag in built.exe}
                    self.assertEqual(runs['ir'], runs['ir-checked'], source)
                    out = built.fallback['ir']
                    boxed = [w for w in workers if w in out and 'Rule X' in out[w]]
                    other = [w for w in workers if w in out and 'Rule X' not in out[w]]
                    self.assertEqual(other, [], (out, source))
                    refused += len(boxed)
                    taken += len(workers) - len(boxed)
                    if boxed:
                        # a refused worker runs as legacy (value semantics) and the program may then
                        # differ from CPython, even fail: that is what Rule X reports. The same seed
                        # without the refused workers is compared instead.
                        source, _ = _ShareGen(seed).program(keep=set(workers) - set(boxed))
                        built = Built(tmp, 'k%d' % seed, source)
                        expected = cpython_run(tmp, 'k%d' % seed, source)
                        runs = {tag: run(built.exe[tag]) for tag in built.exe}
                        self.assertEqual(expected[0], 0, expected[2] + source)
                        self.assertEqual(runs['ir'], runs['ir-checked'], source)
                        self.assertEqual(set(workers) - set(boxed) - built.ir['ir'], set(), (built.fallback['ir'], source))
                    self.assertEqual(runs['ir'], (0, expected[1], ''), source)
        self.assertGreater(taken, 0)


if __name__ == '__main__':
    unittest.main()
