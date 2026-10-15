"""IR stage S0 (docs/design/IR_OWNERSHIP_DESIGN_v2.md, python/pkg-v12/ir/).

* The verifier accepts well-formed IR and rejects each kind of malformed IR by name: scope and
  SSA violations, terminators, yield/break/continue/return arity and types, operand types,
  arithmetic modes, ops and types of later stages, places, calls, effect summaries.
* The textual form round-trips (print -> parse -> print is the identity) and the parser rejects
  malformed text.
* Hand-written IR with loop-carried values and break values (shapes S0 lowering does not produce
  yet) is emitted to C, compiled and run.
* Generated numeric programs (int/float parameters and locals, + - * / // % & | ^ << >> ~, abs,
  min, max, int(), float(), chained comparisons, and/or/not, conditional expressions, if/while/
  for-range with break and continue, calls, recursion) compile with AIL_IR=verify, every generated
  function takes the IR path, and the output equals CPython's and the legacy build's.
* AIL_IR=1 falls back to the legacy emitter when the IR path fails; AIL_IR=verify raises.
"""
import contextlib
import io
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
from ir import emit_c, text, verify          # noqa: E402

GOOD = '''func @collatz(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], sym = "collatz"} effects {raises = ["OverflowError"]} {
  %steps = local.alloc {name = "steps"} : place<i64>
  %m = local.alloc {name = "m"} : place<i64>
  %zero = const {value = 0} : i64
  store %steps, %zero
  store %m, %n
  loop {
    %mv = load %m : i64
    %one = const {value = 1} : i64
    %go = cmp.ne %mv, %one : i1
    if %go {
      yield
    } {
      break
    }
    %two = const {value = 2} : i64
    %r = floormod %mv, %two {mode = "ck"} : i64
    %even = cmp.eq %r, %zero : i1
    if %even {
      %h = floordiv %mv, %two {mode = "ck"} : i64
      store %m, %h
      yield
    } {
      %three = const {value = 3} : i64
      %t = mul %three, %mv {mode = "ck"} : i64
      %u = add %t, %one {mode = "ck"} : i64
      store %m, %u
      yield
    }
    %s = load %steps : i64
    %s1 = add %s, %one {mode = "ck"} : i64
    store %steps, %s1
    continue
  }
  %out = load %steps : i64
  return %out
}
'''


def parse(src):
    return text.parse_function(src)


def errors_of(src, program=None):
    fn = parse(src)
    return verify.verify_function(fn, program or I.Program({fn.sym: fn}))


class VerifierTests(unittest.TestCase):
    def assertRejected(self, src, fragment, program=None):
        errs = errors_of(src, program)
        self.assertTrue(errs, 'accepted:\n' + src)
        self.assertTrue(any(fragment in e for e in errs), '%r not in %s' % (fragment, errs))

    def test_good_function_verifies(self):
        self.assertEqual(errors_of(GOOD), [])

    def test_use_out_of_scope(self):
        bad = GOOD.replace('  %out = load %steps : i64\n  return %out',
                           '  %out = load %steps : i64\n  %bad = add %out, %h {mode = "ck"} : i64\n  return %bad')
        self.assertRejected(bad, 'not defined in scope')

    def test_value_defined_twice(self):
        fn = parse(GOOD)
        dup = fn.body.instrs[2]                     # %zero = const
        fn.body.instrs.insert(3, dup)
        errs = verify.verify_function(fn, I.Program({fn.sym: fn}))
        self.assertTrue(any('defined more than once' in e for e in errs), errs)

    def test_missing_terminator(self):
        self.assertRejected(GOOD.replace('  return %out\n', ''), 'does not end in a terminator')

    def test_terminator_in_the_middle(self):
        self.assertRejected(GOOD.replace('  store %m, %n\n', '  store %m, %n\n  return %zero\n'),
                            'terminator in the middle')

    def test_empty_region(self):
        self.assertRejected(GOOD.replace('    if %go {\n      yield\n    } {', '    if %go {\n    } {'),
                            'empty region')

    def test_yield_outside_if(self):
        self.assertRejected(GOOD.replace('    continue\n  }', '    yield\n  }'), 'yield outside an if')

    def test_yield_arity(self):
        self.assertRejected(GOOD.replace('      store %m, %h\n      yield', '      store %m, %h\n      yield %h'),
                            'does not match the if results')

    def test_break_outside_loop(self):
        self.assertRejected(GOOD.replace('  return %out', '  break'), 'break outside a loop')

    def test_continue_arity(self):
        self.assertRejected(GOOD.replace('    continue\n', '    continue %s1\n'), 'continue values')

    def test_return_type(self):
        self.assertRejected(GOOD.replace('-> (i64)', '-> (f64)'), 'does not match the function results')

    def test_operand_types(self):
        self.assertRejected(GOOD.replace('%u = add %t, %one', '%f = const {value = 1.5} : f64\n'
                                         '      %u = add %t, %f'), 'operands must be the same type')

    def test_float_op_on_ints(self):
        self.assertRejected(GOOD.replace('%u = add %t, %one {mode = "ck"}', '%u = fadd %t, %one'),
                            'operands must be the same type')

    def test_bad_mode(self):
        self.assertRejected(GOOD.replace('%s1 = add %s, %one {mode = "ck"}', '%s1 = add %s, %one {mode = "fast"}'),
                            'mode must be one of')
        self.assertRejected(GOOD.replace('%h = floordiv %mv, %two {mode = "ck"}', '%h = floordiv %mv, %two {mode = "nsw"}'),
                            'mode must be one of ck')

    def test_condition_must_be_i1(self):
        self.assertRejected(GOOD.replace('if %go {', 'if %mv {'), 'if condition must be i1')

    def test_reserved_op_names_its_stage(self):
        self.assertRejected(GOOD.replace('  store %m, %n\n', '  store %m, %n\n  list.insert %m, %n\n'),
                            'belongs to stage S3')

    def test_type_outside_s0(self):
        self.assertRejected(GOOD.replace('%m = local.alloc {name = "m"} : place<i64>',
                                         '%m = local.alloc {name = "m"} : place<obj<set<i64>>>'),
                            'not in the S1 subset')
        bad = GOOD.replace('%m = local.alloc {name = "m"} : place<i64>',
                           '%m = local.alloc {name = "m"} : place<obj<list<i64>>>')
        self.assertTrue(any('not in the S0 subset' in e
                            for e in verify.verify_function(parse(bad), None, stage='S0')))

    def test_malformed_type(self):
        self.assertRejected(GOOD.replace('%m = local.alloc {name = "m"} : place<i64>',
                                         '%m = local.alloc {name = "m"} : place<obj<dict<i64>>>'),
                            'takes 2 type argument')
        self.assertEqual(I.type_errors(I.T('list', I.I64)), ['list must appear as obj<list<i64>>'])
        self.assertEqual(I.type_errors(I.T('obj', I.T('list', I.T('obj', I.class_type('Node'))))), [])

    def test_local_alloc_only_at_top(self):
        self.assertRejected(GOOD.replace('      %h = floordiv', '      %x = local.alloc {name = "x"} : place<i64>\n'
                                         '      %h = floordiv'), 'only in the function body')

    def test_store_type(self):
        self.assertRejected(GOOD.replace('  store %m, %n\n', '  %fl = const {value = 2.5} : f64\n  store %m, %fl\n'),
                            'store of f64 into place<i64>')

    def test_load_from_value(self):
        self.assertRejected(GOOD.replace('%mv = load %m : i64', '%mv = load %n : i64'), 'load from a non-place')

    def test_const_checks(self):
        self.assertRejected(GOOD.replace('%zero = const {value = 0} : i64', '%zero = const {value = 0.0} : i64'),
                            'integer constant expected')
        self.assertRejected(GOOD.replace('%zero = const {value = 0} : i64',
                                         '%zero = const {value = 9223372036854775808} : i64'),
                            'out of i64 range')

    def test_calls_are_checked_against_the_callee(self):
        call = GOOD.replace('  %out = load %steps : i64\n', '  %out0 = load %steps : i64\n'
                            '  %out = call %out0 {callee = "helper"} : i64\n')
        self.assertRejected(call, 'call to unknown function')
        fn = parse(call)
        program = I.Program({fn.sym: fn}, {'helper': I.fn_type([I.F64], [I.I64])})
        errs = verify.verify_function(fn, program)
        self.assertTrue(any('do not match' in e for e in errs), errs)
        program.externs['helper'] = I.fn_type([I.I64], [I.I64])
        fn.effects = E.Effects(unknown=True)
        self.assertEqual(verify.verify_function(fn, program), [])

    def test_effect_summary_must_cover_the_body(self):
        self.assertRejected(GOOD.replace(' effects {raises = ["OverflowError"]}', ' effects {}'),
                            'does not cover the body')
        self.assertRejected(GOOD.replace('effects {raises = ["OverflowError"]}', 'effects {raises = ["OverflowError"]}')
                            .replace('%r = floormod %mv, %two {mode = "ck"}', '%r = floormod %mv, %n {mode = "ck"}'),
                            'does not cover the body')
        fn = parse(GOOD)
        self.assertEqual(E.summarize(fn, I.Program({fn.sym: fn})).raises, frozenset(['OverflowError']))
        div = parse(GOOD.replace('%r = floormod %mv, %two', '%r = floormod %mv, %n'))
        self.assertEqual(E.summarize(div, I.Program({div.sym: div})).raises,
                         frozenset(['OverflowError', 'ZeroDivisionError']))

    def test_for_range_block_arguments(self):
        src = ('func @f(%n: i64) -> () attrs {names = ["n"], sym = "f"} {\n'
               '  %z = const {value = 0} : i64\n  %one = const {value = 1} : i64\n'
               '  for.range %z, %n, %one {\n  ^(%i: f64):\n    continue\n  }\n  return\n}\n')
        self.assertRejected(src, 'for.range body arguments')
        self.assertEqual(errors_of(src.replace('^(%i: f64)', '^(%i: i64)')), [])

    def test_unknown_op_is_a_parse_error(self):
        with self.assertRaises(text.ParseError):
            parse(GOOD.replace('cmp.ne', 'cmp.nope'))
        with self.assertRaises(text.ParseError):
            parse(GOOD.replace('%s1 = add %s, %one', '%s1 = add %s, %nowhere'))
        with self.assertRaises(text.ParseError):
            parse(GOOD.replace('%h = floordiv', '%steps = floordiv'))


class TextTests(unittest.TestCase):
    def test_round_trip_is_identity(self):
        once = text.print_function(parse(GOOD))
        self.assertEqual(text.print_function(parse(once)), once)
        self.assertIn('%2 = local.alloc {name = "m"} : place<i64>', once)

    def test_types_print_and_parse(self):
        for spelled in ('i64', 'place<f64>', 'obj<list<obj<list<i64>>>>', 'obj<dict<str, tup<i64, f64>>>',
                        'opt<obj<Node>>', 'fn<(i64, f64) -> (i1)>', 'closure<() -> ()>', 'cell<i64>'):
            parsed = text._Parser(spelled).parse_type()
            self.assertEqual(str(parsed), spelled)
            self.assertEqual(I.type_errors(parsed), [], spelled)

    def test_float_attributes_survive(self):
        src = GOOD.replace('%zero = const {value = 0} : i64', '%zero = const {value = 0} : i64\n'
                           '  %c1 = const {value = 0.1} : f64\n  %c2 = const {value = -1e-300} : f64\n'
                           '  %c3 = const {value = inf} : f64')
        fn = parse(src)
        values = [ins.attrs['value'] for ins in fn.body.instrs if ins.op == 'const']
        self.assertEqual(values[1:4], [0.1, -1e-300, float('inf')])
        once = text.print_function(fn)
        self.assertEqual(text.print_function(parse(once)), once)


CARRIED = '''func @sumsq(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], sym = "sumsq"} {
  %z = const {value = 0} : i64
  %one = const {value = 1} : i64
  %acc = for.range %z, %n, %one, %z : i64 {
  ^(%i: i64, %a: i64):
    %sq = mul %i, %i {mode = "nsw"} : i64
    %a2 = add %a, %sq {mode = "nsw"} : i64
    continue %a2
  }
  return %acc
}
func @gcd(%a: i64, %b: i64) -> (i64) attrs {linkage = "extern", names = ["a", "b"], sym = "gcd"} {
  %g = loop %a, %b : i64 {
  ^(%x: i64, %y: i64):
    %z = const {value = 0} : i64
    %done = cmp.eq %y, %z : i1
    if %done {
      break %x
    } {
      yield
    }
    %r = floormod %x, %y {mode = "ck"} : i64
    continue %y, %r
  }
  return %g
}
func @first_square_over(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], sym = "first_square_over"} {
  %lo = const {value = 0} : i64
  %hi = const {value = 100} : i64
  %st = const {value = 3} : i64
  %none = const {value = -1} : i64
  %found = for.range %lo, %hi, %st, %none : i64 {
  ^(%i: i64, %keep: i64):
    %sq = mul %i, %i {mode = "ck"} : i64
    %big = cmp.gt %sq, %n : i1
    if %big {
      break %i
    } {
      yield
    }
    continue %keep
  }
  return %found
}
'''

HARNESS = r'''
#include <stdio.h>
int main(void) {
    printf("%lld %lld %lld %lld %lld %lld\n", (long long)sumsq(10), (long long)gcd(84, 36),
           (long long)gcd(17, 5), (long long)first_square_over(50), (long long)first_square_over(100000),
           (long long)sumsq(0));
    return 0;
}
'''


class EmitTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('gcc'), 'gcc is not available')
    def test_carried_values_and_break_values_run(self):
        import pyfront
        program = text.parse_program(CARRIED)
        E.summarize_program(program)
        verify.check(program)
        self.assertEqual(text.print_program(text.parse_program(text.print_program(program))),
                         text.print_program(program))
        parts = ['#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n']
        needed = set()
        bodies = []
        for sym in ('sumsq', 'gcd', 'first_square_over'):
            sig, body, needs = emit_c.emit_function(program.functions[sym])
            needed |= needs['need'] | needs['floor']
            bodies.append(body)
            self.assertEqual(needs['parts'], {'RANGEITER'} if sym == 'first_square_over' else set())
        helpers = ''.join(pyfront.HELPERS[h] for h in pyfront.HELPER_ORDER if h in needed | {'ail_die'})
        rangeiter = ('#define ail_raise_named(x) ail_die("ValueError")\n'
                     + __import__('cruntime').RANGEITER)
        source = parts[0] + helpers + rangeiter + ''.join(bodies) + HARNESS
        with tempfile.TemporaryDirectory() as tmp:
            c, exe = Path(tmp, 'carried.c'), Path(tmp, 'carried')
            c.write_text(source)
            cc = subprocess.run(['gcc', '-O2', '-Wall', '-o', str(exe), str(c)], capture_output=True, text=True)
            self.assertEqual(cc.returncode, 0, cc.stderr + source)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual(ran.stdout, '285 12 1 9 -1 0\n')


# ---------------------------------------------------------------------------- generated programs

class _Gen(object):
    """Random numeric programs in the Python syntax, inside the S0 subset and without int64
    overflow or division by zero (values are kept bounded), so CPython is the oracle."""

    def __init__(self, seed):
        self.r = random.Random(seed)

    def pick(self, seq):
        return self.r.choice(seq)

    def int_leaf(self, scope):
        if self.r.random() < 0.35:
            return str(self.r.randint(-9, 20))
        return self.pick(scope['ints'])

    def int_expr(self, scope, depth=0):
        if depth >= 3 or self.r.random() < 0.25:
            return self.int_leaf(scope)
        a = self.int_expr(scope, depth + 1)
        k = self.r.randint(0, 15)
        if k == 0:
            return '(%s + %s)' % (a, self.int_expr(scope, depth + 1))
        if k == 1:
            return '(%s - %s)' % (a, self.int_expr(scope, depth + 1))
        if k == 2:
            return '(%s * %d)' % (a, self.r.randint(-6, 9))
        if k == 3:
            return '(%s // %d)' % (a, self.pick([1, 2, 3, 4, 7, 8, -2, -5, 16]))
        if k == 4:
            return '(%s %% %d)' % (a, self.pick([2, 3, 5, 8, 10, -3, -4, 64]))
        if k == 5:
            return '(%s // (abs(%s) %% 5 + 1))' % (a, self.int_leaf(scope))
        if k == 6:
            return '(%s %s %s)' % (a, self.pick(['&', '|', '^']), self.int_expr(scope, depth + 1))
        if k == 7:
            return '((%s %% 1024) << %d)' % (a, self.r.randint(0, 5))
        if k == 8:
            return '(%s >> %d)' % (a, self.r.randint(0, 7))
        if k == 9:
            return '%s(%s, %s)' % (self.pick(['min', 'max']), a, self.int_expr(scope, depth + 1))
        if k == 10:
            return 'abs(%s)' % a
        if k == 11:
            return '(-%s)' % a
        if k == 12:
            return '(~%s)' % a
        if k == 13:
            return '(%s if %s else %s)' % (a, self.cond(scope, depth + 1), self.int_expr(scope, depth + 1))
        if k == 14 and scope['floats']:
            return 'int(%s)' % self.float_expr(scope, depth + 1)
        if k == 15 and scope['callees']:
            name, params, ret = self.pick(scope['callees'])
            if ret == 'int':
                args = [self.int_leaf(scope) if p == 'int' else self.float_leaf(scope) for p in params]
                return '%s(%s)' % (name, ', '.join(args))
        return a

    def float_leaf(self, scope):
        if not scope['floats'] or self.r.random() < 0.3:
            return self.pick(['0.5', '2.25', '-1.75', '3.0', '0.125'])
        return self.pick(scope['floats'])

    def float_expr(self, scope, depth=0):
        if depth >= 3 or self.r.random() < 0.3:
            return self.float_leaf(scope)
        a = self.float_expr(scope, depth + 1)
        k = self.r.randint(0, 6)
        if k == 0:
            return '(%s + %s)' % (a, self.float_expr(scope, depth + 1))
        if k == 1:
            return '(%s - %s)' % (a, self.float_leaf(scope))
        if k == 2:
            return '(%s * %s)' % (a, self.pick(['0.5', '1.5', '-2.0']))
        if k == 3:
            return '(%s / %s)' % (a, self.pick(['4.0', '-3.0', '7.0']))
        if k == 4:
            return 'float(%s)' % self.int_expr(scope, depth + 1)
        if k == 5:
            return '(%s / (abs(%s) %% 7 + 1))' % (a, self.int_leaf(scope))
        if k == 6:
            return '(%s if %s else %s)' % (a, self.cond(scope, depth + 1), self.float_leaf(scope))
        return a

    def cond(self, scope, depth=0):
        k = self.r.randint(0, 6)
        ops = ['<', '<=', '>', '>=', '==', '!=']
        if k <= 1 or depth >= 2:
            return '%s %s %s' % (self.int_expr(scope, 2), self.pick(ops), self.int_expr(scope, 2))
        if k == 2:
            return '%s %s %s %s %s' % (self.int_leaf(scope), self.pick(ops[:4]), self.int_leaf(scope),
                                       self.pick(ops[:4]), self.int_leaf(scope))
        if k == 3:
            return '(%s) %s (%s)' % (self.cond(scope, depth + 1), self.pick(['and', 'or']),
                                     self.cond(scope, depth + 1))
        if k == 4:
            return 'not (%s)' % self.cond(scope, depth + 1)
        if k == 5 and scope['floats']:
            return '%s %s %s' % (self.float_expr(scope, 2), self.pick(ops[:4]), self.float_leaf(scope))
        return self.int_expr(scope, 2)

    def block(self, scope, indent, depth, loops):
        lines = []
        for _ in range(self.r.randint(1, 4 if depth else 6)):
            lines.extend(self.statement(scope, indent, depth, loops))
        return lines

    def statement(self, scope, indent, depth, loops):
        pad = '    ' * indent
        k = self.r.randint(0, 9 if depth < 2 else 3)
        if k <= 1:
            return [pad + 'acc = (acc * %d + %s) %% 1000003' % (self.r.randint(1, 31), self.int_expr(scope))]
        if k == 2:
            return [pad + 't = t * 0.5 + %s' % self.float_expr(scope)]
        if k == 3 and loops:
            return [pad + 'if %s:' % self.cond(scope), pad + '    ' + self.pick(['break', 'continue'])]
        if k == 3:
            return [pad + 'acc += %s' % self.int_leaf(scope)]
        if k in (4, 5):
            out = [pad + 'if %s:' % self.cond(scope)] + self.block(scope, indent + 1, depth + 1, loops)
            if self.r.random() < 0.4:
                out += [pad + 'elif %s:' % self.cond(scope)] + self.block(scope, indent + 1, depth + 1, loops)
            if self.r.random() < 0.6:
                out += [pad + 'else:'] + self.block(scope, indent + 1, depth + 1, loops)
            return out
        if k in (6, 7):
            var = 'i%d' % depth
            lo = self.pick(['0', '1', '-3', '%s %% 5' % self.pick(scope['params_int'] or ['3'])])
            hi = self.pick(['6', '9', '%s %% 11' % self.pick(scope['params_int'] or ['7'])])
            step = self.pick(['', '', ', 2', ', 3', ', -1', ', -2'])
            if step.startswith(', -'):
                lo, hi = hi, lo
            inner = dict(scope, ints=scope['ints'] + [var])
            body = self.block(inner, indent + 1, depth + 1, loops + 1)
            return [pad + 'for %s in range(%s, %s%s):' % (var, lo, hi, step)] + body
        if k == 8:
            var = 'c%d' % depth
            inner = dict(scope, ints=scope['ints'] + [var])
            body = self.block(inner, indent + 1, depth + 1, loops + 1)
            return ([pad + '%s = 0' % var, pad + 'while %s < %d and (%s):' % (var, self.r.randint(1, 7), self.cond(scope)),
                     pad + '    %s += 1' % var] + body)
        return [pad + 'if %s:' % self.cond(scope), pad + '    return %s' % ('acc' if scope['ret'] == 'int' else 't')]

    def function(self, name, callees):
        nparams = self.r.randint(1, 3)
        params = [(chr(ord('a') + k), self.pick(['int', 'int', 'float'])) for k in range(nparams)]
        ret = self.pick(['int', 'int', 'float'])
        ints = [p for p, t in params if t == 'int'] + ['acc']
        floats = [p for p, t in params if t == 'float'] + ['t']
        scope = {'ints': ints, 'floats': floats, 'callees': callees, 'ret': ret,
                 'params_int': [p for p, t in params if t == 'int']}
        lines = ['def %s(%s) -> %s:' % (name, ', '.join('%s: %s' % p for p in params), ret),
                 '    acc = %d' % self.r.randint(0, 9), '    t = %s' % self.pick(['0.0', '1.5', '-0.25'])]
        lines += self.block(scope, 1, 0, 0)
        lines.append('    return %s' % ('acc' if ret == 'int' else 't'))
        return lines, params, ret

    def program(self, nfuncs):
        """`rec` (recursive) is called from main only; f0 and f1 call nothing and every later
        function may call them, so run time stays small whatever the loops nest."""
        lines, callees, leaves = [], [], []
        rec = ['def rec(n: int) -> int:', '    if n <= 1:', '        return 1',
               '    return (rec(n - 1) * 3 + n % 7) % 1000003']
        lines += rec + ['']
        callees.append(('rec', ['int'], 'int'))
        for k in range(nfuncs):
            name = 'f%d' % k
            body, params, ret = self.function(name, list(leaves) if k >= 2 else [])
            lines += body + ['']
            callees.append((name, [t for _, t in params], ret))
            if k < 2:
                leaves.append(callees[-1])
        lines.append('def main():')
        for name, params, ret in callees:
            for args in range(3):
                values = [str(self.pick([-7, 0, 3, 12, 100, 25])) if p == 'int'
                          else self.pick(['0.5', '-2.25', '3.0']) for p in params]
                if name == 'rec':
                    values = [str(self.r.randint(0, 25))]
                lines.append('    print(%s(%s))' % (name, ', '.join(values)))
        lines += ['', '', 'main()', '']
        return '\n'.join(lines), [c[0] for c in callees]


def cpython_output(source):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(source, 'generated', 'exec'), {'__name__': 'generated'})
    return out.getvalue()


def build_and_run(directory, name, source, ir):
    path, exe = Path(directory, name + '.ail'), Path(directory, name + ('.ir' if ir else '.legacy'))
    stats = Path(directory, name + ('.ir' if ir else '.legacy') + '.stats')
    path.write_text(source)
    env = dict(os.environ, AIL_IR='verify' if ir else '0', AIL_IR_STATS=str(stats))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(path), '--syntax',
                            'python', '-o', str(exe)], capture_output=True, text=True, timeout=600, env=env)
    if built.returncode:
        return built, None, []
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
    entries = [json.loads(l) for l in stats.read_text().splitlines()] if stats.exists() else []
    return built, ran, entries


class GeneratedProgramTests(unittest.TestCase):
    SEEDS = (11, 23, 37)

    def test_generated_numeric_programs_match_cpython(self):
        with tempfile.TemporaryDirectory() as tmp:
            for seed in self.SEEDS:
                source, functions = _Gen(seed).program(7)
                with self.subTest(seed=seed):
                    expected = cpython_output(source)
                    built, ran, entries = build_and_run(tmp, 'gen%d' % seed, source, ir=True)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr + source)
                    self.assertEqual(ran.returncode, 0, ran.stderr)
                    self.assertEqual(ran.stdout, expected, source)
                    on_ir = {e['fn'] for e in entries if e['path'] == 'ir'}
                    self.assertEqual(set(functions) - on_ir, set(),
                                     [e for e in entries if e['path'] != 'ir'])
                    built, legacy, entries = build_and_run(tmp, 'gen%d' % seed, source, ir=False)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertEqual(legacy.stdout, expected)
                    self.assertEqual(entries, [])

    def test_overflow_and_zero_division_keep_their_messages(self):
        source = ('def grow(n: int) -> int:\n    x = n\n    for i in range(80):\n        x = x * 3\n    return x\n\n'
                  'def div(a: int, b: int) -> int:\n    return a // b\n\n'
                  'def main():\n    print(div(7, 2))\n    print(grow(5))\n\n\nmain()\n')
        with tempfile.TemporaryDirectory() as tmp:
            on = build_and_run(tmp, 'ovf', source, ir=True)
            off = build_and_run(tmp, 'ovf', source, ir=False)
        self.assertLessEqual({'grow', 'div'}, {e['fn'] for e in on[2] if e['path'] == 'ir'})
        self.assertEqual((on[1].returncode, on[1].stdout, on[1].stderr),
                         (off[1].returncode, off[1].stdout, off[1].stderr))
        self.assertNotEqual(on[1].returncode, 0)
        self.assertIn('overflow', on[1].stderr)


class SwitchTests(unittest.TestCase):
    SOURCE = ('fn sq(x: int) -> int { return x * x + 1; }\n'
              'fn total(xs: list[int]) -> int { let s = 0; for v in xs { s += v; } return s; }\n'
              'fn main() -> int { print(sq(4)); print(total([1, 2, 3])); return 0; }\n')

    def to_c(self, mode, **extra):
        import pyfunc
        from ail_syntax import translate
        from ir import driver
        saved = {k: os.environ.get(k) for k in ('AIL_IR', 'AIL_IR_FUNCS', 'AIL_IR_STATS')}
        try:
            os.environ['AIL_IR'] = mode
            os.environ.pop('AIL_IR_STATS', None)
            os.environ.pop('AIL_IR_FUNCS', None)
            os.environ.update(extra)
            del driver.STATS[:]
            return pyfunc.to_c(translate(self.SOURCE), name='run', strict=True), list(driver.STATS)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_off_is_the_legacy_output_and_on_changes_only_ir_functions(self):
        off, stats_off = self.to_c('0')
        on, stats_on = self.to_c('1')
        self.assertEqual(stats_off, [])
        paths = {e['fn']: e['path'] for e in stats_on}
        self.assertEqual(paths['sq'], 'ir')
        self.assertEqual(paths['total'], 'legacy')
        self.assertNotEqual(off, on)
        self.assertIn('int64_t ir1 = ', on)
        self.assertNotIn('int64_t ir1 = ', off)
        allow, stats_allow = self.to_c('1', AIL_IR_FUNCS='total')
        self.assertEqual(allow, off)
        self.assertEqual({e['path'] for e in stats_allow}, {'legacy'})

    def test_failure_falls_back_under_1_and_raises_under_verify(self):
        original = emit_c.emit_function

        def broken(fn):
            raise I.IRError('injected emitter failure')
        emit_c.emit_function = broken
        try:
            off, _ = self.to_c('0')
            fallback, stats = self.to_c('1')
            self.assertEqual(fallback, off)
            self.assertTrue(any('injected emitter failure' in e['reason'] for e in stats), stats)
            with self.assertRaisesRegex(Exception, 'injected emitter failure'):
                self.to_c('verify')
        finally:
            emit_c.emit_function = original


if __name__ == '__main__':
    unittest.main()
