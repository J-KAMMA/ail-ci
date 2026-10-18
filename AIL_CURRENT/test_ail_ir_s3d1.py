"""IR stage S3d-1: owned dict[int, int] locals (docs/design/IR_OWNERSHIP_DESIGN_v2.md section 20,
python/pkg-v12/ir/).

A local `dict[int, int]` is the legacy `ail_idict` held in a local place and operated on by `dict.has`, `dict.need`,
`dict.get`, `dict.put`, `dict.len` and `dict.reset` (the legacy helpers, so insertion order, the table modes and the
messages are the legacy's). What this module pins: the ops print, parse and verify (malformed uses are rejected by
name); the C frees the dictionary at every exit; programs that use `in`, `not in`, `d[k]`, `d[k] = v`, `d[k] += v`,
`d.get(k, v)`, `len(d)` and `d = {}` agree with CPython and the legacy build in both exception modes, a missing key
fails like the legacy build, and sanitizers report nothing.
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
from test_ail_ir_s3 import Built, compile_program, HAVE_CC     # noqa: E402
from ail_testenv import ASAN_DETECT_LEAKS

DICT = '''func @tally(%k: i64) -> (i64) attrs {linkage = "extern", names = ["k"], owned = ["d"], sym = "tally"} {
  %d = local.alloc {name = "d"} : place<obj<dict<i64, i64>>>
  %one = const {value = 1} : i64
  dict.reset %d
  dict.put %d, %k, %one
  %h = dict.has %d, %k : i1
  %v = dict.need %d, %k : i64
  %g = dict.get %d, %one, %v : i64
  %n = dict.len %d : i64
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
        fn, program = fn_of(DICT)
        verify.check(fn, program)
        printed = text.print_function(fn)
        self.assertEqual(text.print_function(text.parse_function(printed)), printed)

    def test_malformed_uses_are_rejected_by_name(self):
        self.bad(DICT.replace('dict.has %d, %k : i1', 'dict.has %d, %k : i64'), 'yields i1')
        self.bad(DICT.replace('dict.put %d, %k, %one', 'dict.put %k, %k, %one'), 'takes the place of an int dictionary')
        self.bad(DICT.replace('owned = ["d"], ', ''), 'owned places')
        self.bad(DICT.replace('dict.reset %d', '%z = load %d : obj<dict<i64, i64>>'), 'never loaded or stored')

    def test_effects_and_c(self):
        fn, program = fn_of(DICT)
        by_op = {i.op: E.instr_effects(i, fn, program) for i in I.walk(fn.body)}
        self.assertIn('Local(tally,d)', by_op['dict.put'].writes)
        self.assertEqual(by_op['dict.has'].writes, frozenset())
        self.assertIn('Die', by_op['dict.need'].raises)
        _, c, needs = emit_c.emit_function(fn)
        self.assertIn('ail_idict v_d = {0};', c)
        self.assertIn('ail_idict_free(&v_d);', c)
        self.assertIn('ail_idict_need(&v_d,', c)
        self.assertIn('IDICT', needs['parts'])


DICTS = '''import sys


def count(xs: list[int]) -> str:
    d: dict[int, int] = {}
    order: list[int] = []
    for x in xs:
        if x in d:
            d[x] += 1
        else:
            d[x] = 1
            order.append(x)
    out: list[str] = []
    for k in order:
        out.append(str(k) + ":" + str(d[k]))
    return ",".join(out) + "|" + str(len(d))


def lookups(n: int) -> int:
    d: dict[int, int] = {}
    for i in range(n):
        d[i * 7 % 13 - 5] = i
    total = 0
    for k in range(-8, 12):
        total += d.get(k, -1)
        if k not in d:
            total += 100
    return total + len(d)


def rebuild(n: int) -> int:
    d: dict[int, int] = {}
    total = 0
    for r in range(3):
        d = {}
        for i in range(n):
            d[i + r] = i * r
        total += len(d) + d[n - 1 + r]
    return total


def big(n: int) -> int:
    d: dict[int, int] = {}
    for i in range(n):
        d[i * 2654435761 % 1000003] = i
    s = 0
    for i in range(n):
        s += d[i * 2654435761 % 1000003] % 7
    return s + len(d)


def missing(k: int) -> int:
    d: dict[int, int] = {}
    d[1] = 2
    return d[k]


def main():
    xs = [3, 1, 3, 2, 1, 3]
    ys: list[int] = []
    print(count(xs))
    print(count(ys))
    print(lookups(0), lookups(5), lookups(40))
    print(rebuild(0), rebuild(4))
    print(big(0), big(2000), big(30000))
    if len(sys.argv) > 1:
        print(missing(int(sys.argv[1])))


main()
'''


def cpython_run(directory, name, source, args=()):
    path = Path(directory, name + '.py')
    path.write_text(source)
    r = subprocess.run([sys.executable, str(path), *map(str, args)], capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout, r.stderr


def run_exe(exe, args=()):
    r = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout, r.stderr


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ProgramTests(unittest.TestCase):
    maxDiff = None

    def test_dictionaries_agree_with_cpython_and_the_legacy_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'dicts', DICTS)
            for tag in ('ir', 'ir-checked'):
                self.assertLessEqual({'count', 'lookups', 'rebuild', 'big', 'missing', 'main'}, built.ir[tag],
                                     built.fallback[tag])
            for args in ((), (1,), (7,)):
                expected = cpython_run(tmp, 'dicts', DICTS, args)
                results = {tag: run_exe(built.exe[tag], args) for tag in built.exe}
                self.assertEqual(results['ir'], results['legacy'], args)
                self.assertEqual(results['ir-checked'], results['legacy'], args)
                self.assertEqual(results['ir'][1], expected[1], args)
                self.assertEqual(results['ir'][0], expected[0], args)

    def test_sanitizers_report_nothing_on_the_ir_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = {}
            for tag, env in (('legacy', {'AIL_IR': '0'}), ('ir', {'AIL_IR': 'verify'}),
                             ('ir-checked', {'AIL_IR': 'verify', 'AIL_IR_EXC': 'checked'})):
                built, _, _ = compile_program(tmp, 'dicts', DICTS, tag, env, debug=True)
                self.assertEqual(built.returncode, 0, built.stderr)
                san = Path(tmp, 'dicts.%s.san' % tag)
                cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined',
                                     '-fno-sanitize-recover=undefined', '-fno-omit-frame-pointer', '-pthread',
                                     str(Path(tmp, 'dicts.%s.d' % tag, 'program.c')), '-lm', '-o', str(san)],
                                    capture_output=True, text=True)
                self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
                for args in ((), (7,)):
                    r = subprocess.run([str(san), *map(str, args)], capture_output=True, timeout=300,
                                       env=dict(os.environ, ASAN_OPTIONS=ASAN_DETECT_LEAKS + ':abort_on_error=0',
                                                UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1'))
                    results[(tag, args)] = (r.returncode, r.stdout, r.stderr.decode(errors='replace'))
            for args in ((), (7,)):
                for tag in ('ir', 'ir-checked'):
                    status, stdout, err = results[(tag, args)]
                    self.assertNotIn('runtime error', err, (tag, args))
                    self.assertNotIn('ERROR: AddressSanitizer', err, (tag, args, err[-800:]))
                    self.assertNotIn('ERROR: LeakSanitizer', err, (tag, args, err[-800:]))
                    self.assertEqual((status, stdout), results[('legacy', args)][:2], (tag, args))


if __name__ == '__main__':
    unittest.main()
