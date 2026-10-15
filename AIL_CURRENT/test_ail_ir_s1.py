"""IR stage S1 (docs/design/IR_OWNERSHIP_DESIGN_v2.md §9.2, python/pkg-v12/ir/passes/).

* Pass units on hand-written IR: mem2reg leaves no places and verifies; simplify folds, CSEs and
  removes dead carried values; the range pass proves `i + 1` under `for i in range(n)` and
  `d[i]` under `i < len(d)` but not an unbounded accumulator; LICM hoists list headers into spans
  and versions a loop (fast copy unchecked, slow copy unchanged).
* The new ops (bytes, numeric lists, struct fields, spans) print, parse and verify; malformed uses
  are rejected by name.
* Generated programs over bytes parameters, struct parameters with scalar and numeric-list
  fields, and read-only list parameters compile with AIL_IR=verify (the verifier runs after every
  pass) with every pass subset, every generated helper takes the IR path, and the output equals
  CPython's and the legacy build's.
* An index that goes out of range inside a versioned loop fails exactly as the legacy build does
  (same stdout before the failure, same exit code, same message).
"""
import json
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
from ir import effects as E                  # noqa: E402
from ir import text, verify                  # noqa: E402
from ir.passes import mem2reg, simplify, ranges, licm   # noqa: E402

from test_ail_ir_s0 import cpython_output     # noqa: E402

SUM = '''func @sum(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], sym = "sum"} {
  %s = local.alloc {name = "s"} : place<i64>
  %j = local.alloc {name = "j"} : place<i64>
  %zero = const {value = 0} : i64
  %one = const {value = 1} : i64
  store %s, %zero
  for.range %zero, %n, %one {args = 1} {
  ^(%i: i64):
    store %j, %i
    %sv = load %s : i64
    %i1 = add %i, %one {mode = "ck"} : i64
    %t = add %sv, %i1 {mode = "ck"} : i64
    store %s, %t
    continue
  }
  %r = load %s : i64
  return %r
}
'''

BYTES = '''func @scan(%d: bytes) -> (i64) attrs {linkage = "extern", names = ["d"], sym = "scan"} {
  %i = local.alloc {name = "i"} : place<i64>
  %zero = const {value = 0} : i64
  %one = const {value = 1} : i64
  %n = bytes.len %d : i64
  store %i, %zero
  loop {
    %iv = load %i : i64
    %go = cmp.lt %iv, %n : i1
    if %go {
      yield
    } {
      break
    }
    %iv2 = load %i : i64
    %c = bytes.get %d, %iv2 {mode = "ck"} : i64
    %stop = cmp.eq %c, %zero : i1
    if %stop {
      break
    } {
      yield
    }
    %nx = add %iv2, %one {mode = "ck"} : i64
    store %i, %nx
    continue
  }
  %r = load %i : i64
  return %r
}
'''

STRUCT = '''func @scale(%s: obj<S>, %k: i64) -> () attrs {linkage = "extern", names = ["s", "k"], sym = "scale"} {
  %zero = const {value = 0} : i64
  %one = const {value = 1} : i64
  %xs = field.list %s {cls = "S", name = "xs"} : obj<list<i64>>
  %n = list.len %xs : i64
  %m = sub %n, %one {mode = "ck"} : i64
  for.range %zero, %m, %one {args = 2} {
  ^(%i: i64):
    %xs2 = field.list %s {cls = "S", name = "xs"} : obj<list<i64>>
    %a = list.get %xs2, %i {mode = "ck"} : i64
    %i1 = add %i, %one {mode = "ck"} : i64
    %b = list.get %xs2, %i1 {mode = "ck"} : i64
    %c = add %a, %b {mode = "ck"} : i64
    list.set %xs2, %i, %c {mode = "ck"}
    continue
  }
  return
}
'''


def fn_of(src):
    fn = text.parse_function(src)
    program = I.Program({fn.sym: fn})
    E.summarize_program(program)
    return fn, program


def ops(fn):
    return [ins.op for ins in I.walk(fn.body)]


class PassTests(unittest.TestCase):
    def check(self, fn, program):
        verify.check(fn, program)
        printed = text.print_function(fn)
        self.assertEqual(text.print_function(text.parse_function(printed)), printed)

    def test_mem2reg_promotes_every_place(self):
        fn, program = fn_of(SUM)
        self.assertEqual(mem2reg.run(fn), 2)
        E.summarize_program(program)
        self.check(fn, program)
        self.assertNotIn('local.alloc', ops(fn))
        self.assertNotIn('load', ops(fn))
        loop = [i for i in I.walk(fn.body) if i.op == 'for.range'][0]
        self.assertEqual(len(loop.regions[0].args), 3)       # index + s + j

    def test_simplify_removes_dead_carried_values_and_folds(self):
        fn, program = fn_of(SUM)
        mem2reg.run(fn)
        simplify.run(fn)
        E.summarize_program(program)
        self.check(fn, program)
        loop = [i for i in I.walk(fn.body) if i.op == 'for.range'][0]
        self.assertEqual(len(loop.regions[0].args), 2)       # j was never read: gone

    def test_ranges_prove_the_index_step_but_not_the_accumulator(self):
        fn, program = fn_of(SUM)
        mem2reg.run(fn)
        simplify.run(fn)
        stats = ranges.run(fn, {})
        E.summarize_program(program)
        self.check(fn, program)
        adds = [i for i in I.walk(fn.body) if i.op == 'add']
        modes = sorted(i.attrs['mode'] for i in adds)
        self.assertEqual(modes, ['ck', 'nsw'])               # i + 1 proven, s + i1 not
        self.assertEqual(stats['ck_ssa_proven'], 1)

    def test_ranges_prove_bytes_index_under_the_loop_test(self):
        fn, program = fn_of(BYTES)
        mem2reg.run(fn)
        simplify.run(fn)
        ranges.run(fn, {})
        E.summarize_program(program)
        self.check(fn, program)
        get = [i for i in I.walk(fn.body) if i.op == 'bytes.get'][0]
        self.assertEqual(get.attrs['mode'], 'nck')
        add = [i for i in I.walk(fn.body) if i.op == 'add'][0]
        self.assertEqual(add.attrs['mode'], 'nsw')
        self.assertNotIn('IndexError', fn.effects.raises)

    def test_licm_hoists_spans_and_versions_the_loop(self):
        fn, program = fn_of(STRUCT)
        mem2reg.run(fn)
        simplify.run(fn)
        ranges.run(fn, {})
        stats = licm.run(fn)
        ranges.run(fn, {})
        simplify.run(fn)
        E.summarize_program(program)
        self.check(fn, program)
        self.assertEqual(stats['spans'], 1)
        self.assertEqual(stats['versioned'], 1)
        self.assertNotIn('list.get', ops(fn))
        loops = [i for i in I.walk(fn.body) if i.op == 'for.range']
        self.assertEqual(len(loops), 2)
        modes = [sorted(i.attrs['mode'] for i in I.walk(l.regions[0]) if i.op.startswith('span.'))
                 for l in loops]
        self.assertIn(['nck', 'nck', 'nck'], modes)          # fast copy
        self.assertIn(['ck', 'ck', 'ck'], modes)             # slow copy, unchanged
        fast = [l for l in loops if all(i.attrs.get('mode') != 'ck'
                                        for i in I.walk(l.regions[0]) if i.op.startswith('span.'))][0]
        self.assertTrue(all(i.attrs.get('mode') == 'nsw' for i in I.walk(fast.regions[0]) if i.op == 'add'
                            and i.operands[0] is fast.regions[0].args[0]))

    def test_a_while_loop_with_an_induction_variable_is_versioned(self):
        src = BYTES.replace('%go = cmp.lt %iv, %n : i1', '%go = cmp.lt %iv, %m : i1').replace(
            'func @scan(%d: bytes) -> (i64) attrs {linkage = "extern", names = ["d"]',
            'func @scan(%d: bytes, %m: i64) -> (i64) attrs {linkage = "extern", names = ["d", "m"]')
        fn, program = fn_of(src)
        mem2reg.run(fn)
        simplify.run(fn)
        ranges.run(fn, {})
        stats = licm.run(fn)
        ranges.run(fn, {})
        simplify.run(fn)
        E.summarize_program(program)
        verify.check(fn, program)
        self.assertEqual(stats['versioned'], 1)
        modes = sorted(i.attrs['mode'] for i in I.walk(fn.body) if i.op == 'bytes.get')
        self.assertEqual(modes, ['ck', 'nck'])

    def test_calls_block_spans_unless_the_summary_says_no_resize(self):
        src = STRUCT.replace('    list.set %xs2, %i, %c {mode = "ck"}\n',
                             '    list.set %xs2, %i, %c {mode = "ck"}\n    call {callee = "g"}\n')
        for summaries, spans in ((None, 0), ({'g': E.Effects(writes=['Elem(Field(S,xs))'])}, 1),
                                 ({'g': E.Effects(writes=['Spine(Field(S,xs))'])}, 0),
                                 ({'g': E.UNKNOWN}, 0)):
            fn = text.parse_function(src)
            program = I.Program({fn.sym: fn}, {'g': I.fn_type([], [])})
            mem2reg.run(fn)
            simplify.run(fn)
            stats = licm.run(fn, summaries)
            E.summarize_program(program)
            verify.check(fn, program)
            self.assertEqual(stats['spans'], spans, summaries)

    def test_a_resizing_loop_gets_no_span(self):
        src = STRUCT.replace('    list.set %xs2, %i, %c {mode = "ck"}\n',
                             '    list.set %xs2, %i, %c {mode = "ck"}\n    list.push %xs2, %c\n')
        fn, program = fn_of(src)
        mem2reg.run(fn)
        simplify.run(fn)
        stats = licm.run(fn)
        E.summarize_program(program)
        self.check(fn, program)
        self.assertEqual((stats['spans'], stats['versioned']), (0, 0))


class OpTests(unittest.TestCase):
    def errors(self, src):
        fn = text.parse_function(src)
        return verify.verify_function(fn, I.Program({fn.sym: fn}))

    def test_new_ops_verify_and_round_trip(self):
        for src in (BYTES, STRUCT):
            fn, program = fn_of(src)
            self.assertEqual(verify.verify_function(fn, program), [])
            printed = text.print_function(fn)
            self.assertEqual(text.print_function(text.parse_function(printed)), printed)

    def test_malformed_uses_are_rejected(self):
        cases = [
            (BYTES.replace('{mode = "ck"} : i64\n    %stop', '{mode = "maybe"} : i64\n    %stop'),
             'index mode must be one of'),
            (BYTES.replace('%c = bytes.get %d, %iv2', '%c = bytes.get %iv2, %d'), 'bytes.get takes'),
            (STRUCT.replace('list.set %xs2, %i, %c', 'list.set %xs2, %c'), 'wrong number of operands'),
            (STRUCT.replace('%n = list.len %xs : i64', '%n = list.len %k : i64'), 'list.len of a non-list'),
            (STRUCT.replace('%xs = field.list %s', '%xs = field.list %k'), 'field.list of a non-object'),
        ]
        for src, fragment in cases:
            errs = self.errors(src)
            self.assertTrue(any(fragment in e for e in errs), (fragment, errs))

    def test_verify_rejects_a_span_store_of_the_wrong_type(self):
        src = STRUCT.replace('    list.set %xs2, %i, %c {mode = "ck"}\n', '')
        fn, program = fn_of(src)
        mem2reg.run(fn)
        licm.run(fn)
        self.assertEqual(verify.verify_function(fn, program), [])
        bad = text.print_function(fn).replace('span<i64>', 'span<f64>', 1)
        errs = verify.verify_function(text.parse_function(bad), program)
        self.assertTrue(errs)


# ---------------------------------------------------------------------------- generated programs

class _Gen(object):
    """Programs (Python syntax) whose helpers take bytes, a struct with scalar and numeric-list
    fields, and read-only int lists; indices stay in range so CPython is the oracle."""

    def __init__(self, seed):
        self.r = random.Random(seed)

    def k(self, lo, hi):
        return self.r.randint(lo, hi)

    def bytes_fn(self, name):
        c1, c2 = self.k(0, 2), self.k(1, 9)
        body = [
            'def %s(d: bytes, a: int, b: int) -> int:' % name,
            '    hi = b',
            '    if hi > len(d) - %d:' % c1,
            '        hi = len(d) - %d' % c1,
            '    lo = a',
            '    if lo < 0:',
            '        lo = 0',
            '    acc = %d' % self.k(0, 5),
            '    for i in range(lo, hi):',
            '        acc = (acc * %d + d[i] + d[i + %d]) %% 1000003' % (c2, c1),
            '    j = 0',
            '    while j < len(d) and d[j] != %d:' % self.k(97, 122),
            '        j += 1',
            '    for c in d:',
            '        if c %% %d == 0:' % self.k(2, 5),
            '            acc += c',
            '    return acc + j',
        ]
        return body

    def struct_fn(self, name):
        off = self.k(1, 2)
        body = [
            'def %s(s: S, k: int) -> int:' % name,
            '    s.n += k',
            '    s.xs.append(k % 97 + s.n % 13)',
            '    for i in range(len(s.xs) - %d):' % off,
            '        s.xs[i] = (s.xs[i] * %d + s.xs[i + %d]) %% 10007' % (self.k(2, 7), off),
            '    for i in range(len(s.xs)):',
            '        for j in range(i + 1, len(s.xs)):',
            '            if s.xs[i] > s.xs[j]:',
            '                s.cnt += 1',
            '    total = 0',
            '    for i in range(len(s.fs)):',
            '        s.fs[i] = s.fs[i] * 0.5 + %d.25' % self.k(0, 3),
            '        total += int(s.fs[i])',
            '    if len(s.xs) > %d:' % self.k(6, 12),
            '        s.xs.pop()',
            '    s.ratio = s.ratio * 0.75 + float(total)',
            '    return total + s.cnt',
        ]
        return body

    def list_fn(self, name):
        body = [
            'def %s(xs: list[int], lo: int) -> int:' % name,
            '    best = -1',
            '    for i in range(lo, len(xs)):',
            '        if xs[i] > best:',
            '            best = xs[i]',
            '    t = 0',
            '    i = len(xs) - 1',
            '    while i >= 0:',
            '        t = (t * %d + xs[i]) %% 65521' % self.k(3, 11),
            '        i -= 1',
            '    return best * 7 + t',
        ]
        return body

    def program(self):
        lines = ['class S:',
                 '    def __init__(self, n: int, xs: list[int], fs: list[float]):',
                 '        self.n = n',
                 '        self.xs = xs',
                 '        self.fs = fs',
                 '        self.cnt = 0',
                 '        self.ratio = 1.5', '']
        names = []
        for k in range(2):
            for kind in ('bytes', 'struct', 'list'):
                name = '%s%d' % (kind[0], k)
                lines += getattr(self, kind + '_fn')(name) + ['']
                names.append((kind, name))
        data = bytes(self.r.randint(32, 126) for _ in range(self.k(20, 60)))
        lines.append('def main():')
        lines.append('    d = %r' % data)
        lines.append('    s = S(%d, [%s], [%s])' % (self.k(0, 9), ', '.join(str(self.k(0, 99)) for _ in range(self.k(3, 8))),
                                                    ', '.join('%d.5' % self.k(0, 9) for _ in range(self.k(1, 4)))))
        lines.append('    xs = [%s]' % ', '.join(str(self.k(-50, 500)) for _ in range(self.k(1, 12))))
        for rep in range(3):
            for kind, name in names:
                if kind == 'bytes':
                    lines.append('    print(%s(d, %d, %d))' % (name, self.k(-3, 10), self.k(5, 80)))
                elif kind == 'struct':
                    lines.append('    print(%s(s, %d))' % (name, self.k(0, 500)))
                else:
                    lines.append('    print(%s(xs, %d))' % (name, self.k(0, 3)))
        lines.append('    print(s.n, s.cnt, len(s.xs), s.ratio)')
        lines += ['', '', 'main()', '']
        return '\n'.join(lines), [n for _, n in names]


def build_and_run(directory, name, source, mode, passes=None, stdin=None):
    path = Path(directory, name + '.ail')
    tag = '%s-%s' % (mode, 'default' if passes is None else (passes or 'none').replace(',', '+'))
    exe = Path(directory, name + '.' + tag)
    stats = Path(directory, name + '.' + tag + '.stats')
    path.write_text(source)
    env = dict(os.environ, AIL_IR=mode, AIL_IR_STATS=str(stats))
    env.pop('AIL_IR_PASSES', None)
    if passes is not None:
        env['AIL_IR_PASSES'] = passes
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(path), '--syntax',
                            'python', '-o', str(exe)], capture_output=True, text=True, timeout=600, env=env)
    if built.returncode:
        return built, None, []
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
    entries = [json.loads(l) for l in stats.read_text().splitlines()] if stats.exists() else []
    return built, ran, entries


@unittest.skipUnless(shutil.which('gcc') or shutil.which('cc'), 'no C compiler')
class GeneratedProgramTests(unittest.TestCase):
    SEEDS = (5, 17)
    PASS_SETS = ('', 'mem2reg', 'mem2reg,simplify', 'mem2reg,simplify,ranges', None)

    def test_generated_programs_match_cpython_under_every_pass_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            for seed in self.SEEDS:
                source, helpers = _Gen(seed).program()
                expected = cpython_output(source)
                built, legacy, entries = build_and_run(tmp, 'g%d' % seed, source, '0')
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr + source)
                self.assertEqual(legacy.stdout, expected, source)
                self.assertEqual(entries, [])
                for passes in self.PASS_SETS:
                    with self.subTest(seed=seed, passes=passes):
                        built, ran, entries = build_and_run(tmp, 'g%d' % seed, source, 'verify', passes)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr + source)
                        self.assertEqual(ran.returncode, 0, ran.stderr)
                        self.assertEqual(ran.stdout, expected, source)
                        on_ir = {e['fn'] for e in entries if e['path'] == 'ir'}
                        self.assertEqual(set(helpers) - on_ir, set(),
                                         [e for e in entries if e['path'] != 'ir'])

    def test_out_of_range_in_a_versioned_loop_fails_like_the_legacy_build(self):
        source = '\n'.join([
            'class S:',
            '    def __init__(self, xs: list[int]):',
            '        self.xs = xs',
            '',
            'def shift(s: S, k: int) -> int:',
            '    t = 0',
            '    for i in range(len(s.xs)):',
            '        t += s.xs[i + k]',
            '        s.xs[i] = t % 1000',
            '    return t',
            '',
            'def scan(d: bytes, b: int) -> int:',
            '    t = 0',
            '    for i in range(b):',
            '        t = t * 3 + d[i]',
            '    return t',
            '',
            'def main():',
            '    s = S([1, 2, 3, 4, 5])',
            '    print(shift(s, 0))',
            '    print(scan(b"abcdef", 6))',
            '    print(shift(s, 2))',
            '    print(scan(b"abcdef", 9))',
            '',
            '',
            'main()', ''])
        with tempfile.TemporaryDirectory() as tmp:
            _, legacy, _ = build_and_run(tmp, 'oob', source, '0')
            _, ir, entries = build_and_run(tmp, 'oob', source, 'verify')
            second = source.replace('    print(shift(s, 2))\n', '')
            _, ir2, _ = build_and_run(tmp, 'oob2', second, 'verify')
            _, legacy2, _ = build_and_run(tmp, 'oob2', second, '0')
        self.assertLessEqual({'shift', 'scan'}, {e['fn'] for e in entries if e['path'] == 'ir'})
        self.assertNotEqual(legacy.returncode, 0)
        self.assertEqual((ir.returncode, ir.stdout, ir.stderr), (legacy.returncode, legacy.stdout, legacy.stderr))
        self.assertEqual((ir2.returncode, ir2.stdout, ir2.stderr),
                         (legacy2.returncode, legacy2.stdout, legacy2.stderr))
        self.assertNotEqual(legacy2.returncode, 0)


if __name__ == '__main__':
    unittest.main()
