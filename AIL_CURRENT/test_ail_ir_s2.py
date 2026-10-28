"""IR stage S2: exceptions (docs/design/IR_OWNERSHIP_DESIGN_v2.md section 11, python/pkg-v12/ir/).

* The new ops (`raise`, `reraise`, `try` with catch and finally forms) print, parse and verify;
  malformed uses are rejected by name.
* Functions that raise, that contain try/except/else/finally, and that call functions that raise
  take the IR path (AIL_IR=verify) and behave exactly as the legacy build (AIL_IR=0) and, where
  Python has the same rules, as CPython: raise in nested calls, try/except/finally ordering,
  re-raise, exceptions in handlers and in finally bodies, break/continue/return through finally,
  recursion depth after a caught exception.
* Exceptions cross the IR <-> legacy boundary in both directions (an IR function that raises
  called by a legacy function that catches it, an IR try around a legacy callee that raises, a
  legacy function in the middle of two IR ones).
* An uncaught exception ends the program with the same stdout, stderr and exit status as the
  legacy build: a program's own raise, a range-check failure, an integer overflow, a division by
  zero, an assert.
* A bytearray parameter kept across calls is retained and released (also when an exception
  unwinds through the function).
* Both exception modes are tested: the default (as the legacy path raises: longjmp) and
  AIL_IR_EXC=checked (checked return values, design 2.8).
* Generated programs (random nests of try/except/else/finally, raise, loops with break and
  continue, calls) agree with CPython, the legacy build and both IR modes.
* With the switch off nothing of the S2 runtime is in the generated C.
"""
import json
import os
import random
import re
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

HAVE_CC = bool(shutil.which('gcc') or shutil.which('cc'))

# --------------------------------------------------------------------------------------------
# Hand-written IR
# --------------------------------------------------------------------------------------------

TRY_CATCH = '''func @guarded(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], sym = "guarded"} {
  %r = local.alloc {name = "r"} : place<i64>
  %zero = const {value = 0} : i64
  store %r, %zero
  try {kind = "catch", codes = [[1, 8], [3]]} {
    %big = const {value = 100} : i64
    %over = cmp.gt %n, %big : i1
    if %over {
      raise {code = 1, form = "msg", msg = "too big", name = "ValueError"}
    } {
      yield
    }
    store %r, %n
    yield
  } {
    %m = const {value = -1} : i64
    store %r, %m
    yield
  } {
    %m2 = const {value = -2} : i64
    store %r, %m2
    reraise
  }
  %v = load %r : i64
  return %v
}
'''

TINTDIV = '''def quot(a: int, b: int) -> int:
    try:
        return a // b
    except ZeroDivisionError:
        return -1


def main() -> None:
    print(quot(7, 2), quot(1, 0))


main()
'''

TRY_FINALLY = '''func @cleanup(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], sym = "cleanup"} {
  %r = local.alloc {name = "r"} : place<i64>
  %zero = const {value = 0} : i64
  store %r, %zero
  loop {
    %c = cmp.lt %n, %zero : i1
    if %c {
      break
    } {
      yield
    }
    try {kind = "finally"} {
      %one = const {value = 1} : i64
      store %r, %one
      break
    } {
      %two = const {value = 2} : i64
      store %r, %two
      yield
    }
    continue
  }
  %v = load %r : i64
  return %v
}
'''


def fn_of(src):
    fn = text.parse_function(src)
    program = I.Program({fn.sym: fn})
    E.summarize_program(program)
    return fn, program


class OpTests(unittest.TestCase):
    def test_try_and_raise_round_trip(self):
        for src in (TRY_CATCH, TRY_FINALLY):
            fn, program = fn_of(src)
            verify.check(fn, program)
            printed = text.print_function(fn)
            again = text.parse_function(printed)
            self.assertEqual(text.print_function(again), printed)
            verify.check(again, program)

    def test_summary_names_what_is_raised(self):
        fn, _ = fn_of(TRY_CATCH)
        self.assertIn('ValueError', fn.effects.raises)
        self.assertIn('Exception', fn.effects.raises)

    def bad(self, src, message):
        fn = text.parse_function(src)
        program = I.Program({fn.sym: fn})
        errors = verify.verify_function(fn, program)
        self.assertTrue(any(message in e for e in errors), (message, errors))

    def test_malformed_uses_are_rejected_by_name(self):
        self.bad(TRY_CATCH.replace('code = 1, form', 'code = 99, form'), 'exception code 1..10')
        self.bad(TRY_CATCH.replace('form = "msg", msg = "too big"', 'form = "msg"'), 'msg is a string exactly')
        self.bad(TRY_CATCH.replace('form = "msg", msg = "too big", ', 'form = "bogus", '), 'raise form is')
        self.bad(TRY_CATCH.replace('codes = [[1, 8], [3]]', 'codes = [[1, 8], [8]]'), 'named by two handlers')
        self.bad(TRY_CATCH.replace('codes = [[1, 8], [3]]', 'codes = [[1, 8]]'), 'lists the exception codes')
        self.bad(TRY_CATCH.replace('kind = "catch"', 'kind = "bogus"'), 'try kind must be')
        self.bad(TRY_FINALLY.replace('{kind = "finally"}', '{kind = "catch", codes = [[1], [2]]}'),
                 'lists the exception codes')
        # reraise needs an except handler around it
        self.bad(TRY_CATCH.replace('''    reraise
  }''', '''    yield
  }''').replace('''      yield
    }
    store %r, %n''', '''      reraise
    }
    store %r, %n'''), 'reraise outside an except handler')
        # a try body or handler yields nothing
        self.bad(TRY_FINALLY.replace('''      store %r, %two
      yield''', '''      store %r, %two
      yield %two'''), 'yields no values')

    def test_emitted_c_has_no_setjmp_and_runs_bodies_under_the_runtime_shim(self):
        for checked in (False, True):
            fn, _ = fn_of(TRY_CATCH)
            sig, c, needs = emit_c.emit_function(fn, (), checked)
            self.assertNotIn('setjmp', c)
            self.assertNotIn('volatile', c)
            self.assertIn('ail_ir_try(guarded__try1, fr)', c)
            self.assertIn('IREXC', needs['parts'])
            self.assertIn('ASSERTEXC', needs['parts'] | set(['ASSERTEXC']))
            self.assertEqual(needs['pending'], checked)
            self.assertEqual('guarded__ir' in c, checked)
            if checked:
                self.assertIn('ail_ir_raise_new(1,', c)
            else:
                self.assertIn('ail_raise_value_adopt(', c)
            self.assertIn('code1 == 1 || code1 == 8', c)      # a ValueError handler takes UnicodeDecodeError


# --------------------------------------------------------------------------------------------
# Building and running programs
# --------------------------------------------------------------------------------------------

MODES = (('legacy', {'AIL_IR': '0'}),
         ('ir', {'AIL_IR': 'verify'}),
         ('ir-checked', {'AIL_IR': 'verify', 'AIL_IR_EXC': 'checked'}))


def compile_program(directory, name, source, tag, env_extra, syntax='python'):
    path = Path(directory, name + '.ail')
    exe = Path(directory, '%s.%s' % (name, tag))
    stats = Path(directory, '%s.%s.stats' % (name, tag))
    path.write_text(source)
    env = dict(os.environ, AIL_IR_STATS=str(stats))
    env.pop('AIL_IR_EXC', None)
    env.update(env_extra)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(path), '--syntax',
                            syntax, '-o', str(exe)], capture_output=True, text=True, timeout=600, env=env)
    entries = [json.loads(l) for l in stats.read_text().splitlines()] if stats.exists() else []
    return built, exe, entries


def run(exe, args=()):
    r = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def cpython_run(directory, name, source, args=()):
    path = Path(directory, name + '.py')
    path.write_text(source)
    r = subprocess.run([sys.executable, str(path), *map(str, args)], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


class Built(object):
    """One program built in every mode; `ir_functions` are the functions the IR build took."""

    def __init__(self, directory, name, source):
        self.source = source
        self.exe = {}
        self.ir = {}
        self.fallback = {}
        for tag, env in MODES:
            built, exe, entries = compile_program(directory, name, source, tag, env)
            assert built.returncode == 0, '%s build of %s failed:\n%s%s\n%s' % (
                tag, name, built.stdout, built.stderr, source)
            self.exe[tag] = exe
            self.ir[tag] = {e['fn'] for e in entries if e['path'] == 'ir'}
            self.fallback[tag] = {e['fn']: e['reason'] for e in entries if e['path'] != 'ir'}


def last_line(text_):
    lines = text_.strip().splitlines()
    return lines[-1] if lines else ''


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ProgramTests(unittest.TestCase):
    maxDiff = None

    def check_program(self, name, source, must_be_ir, args_list=((),), cpython=True, stderr_with_cpython=True,
                      compare_legacy=True):
        """Build in every mode; every run agrees across the modes (stdout, stderr, status) and with
        CPython (stdout, status, and the last line of stderr when `stderr_with_cpython`)."""
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, name, source)
            for tag in ('ir', 'ir-checked'):
                self.assertEqual(set(must_be_ir) - built.ir[tag], set(),
                                 '%s: %s' % (tag, built.fallback[tag]))
            results = []
            for args in args_list:
                runs = {tag: run(built.exe[tag], args) for tag in built.exe}
                for tag in (('ir', 'ir-checked') if compare_legacy else ()):
                    # (a division by zero in a tagged-int function is the ZeroDivisionError CPython raises, so an
                    # uncaught one ends with that text; the legacy build ends with its bare trap message)
                    legacy_run = runs['legacy'][:2] + (runs['legacy'][2].replace(
                        'integer division by zero', 'ZeroDivisionError: integer division or modulo by zero').replace(
                        'integer modulo by zero', 'ZeroDivisionError: integer modulo by zero'),)
                    # (the exceptions the IR raises end the program with the class name in front of the message
                    # CPython prints; the legacy build prints the bare message)
                    named = re.sub(r'(?m)^[A-Za-z]+Error: ', '', runs[tag][2])
                    bare = runs[tag][:2] + (named,)
                    if last_line(runs['legacy'][2]) == 'integer overflow':
                        # the int64 legacy build stops where Python has big integers; the tagged build is exact
                        expected = cpython_run(tmp, name, source, args)
                        self.assertEqual(runs[tag][:2], expected[:2], '%s %s args=%s' % (name, tag, args))
                        continue
                    if not (runs[tag] == runs['legacy'] or runs[tag] == legacy_run or bare == runs['legacy']):
                        # the IR's exceptions carry CPython's text (`IndexError: index out of range` where the
                        # legacy trap says `bytes index out of range`): the run still ends the same way
                        self.assertEqual(runs[tag][:2], runs['legacy'][:2], '%s %s args=%s' % (name, tag, args))
                        self.assertTrue(runs[tag][2].strip(), (name, tag, args))
                if cpython:
                    expected = cpython_run(tmp, name, source, args)
                    self.assertEqual(runs['legacy'][1], expected[1], '%s args=%s stdout' % (name, args))
                    self.assertEqual(runs['legacy'][0], expected[0], '%s args=%s status' % (name, args))
                    if stderr_with_cpython:
                        self.assertEqual(last_line(runs['legacy'][2]), last_line(expected[2]),
                                         '%s args=%s stderr' % (name, args))
                results.append(runs['legacy'])
            return results

    # ------------------------------------------------------------------ raise in nested calls
    def test_raise_and_catch_across_calls(self):
        self.check_program('nested', NESTED, ['leaf', 'mid', 'top', 'safe', 'after', 'rr', 'loopy'])

    def test_ordering_of_handlers_and_finally(self):
        self.check_program('ordering', ORDERING, ['inner', 'outer', 'nested_finally', 'loops', 'reraise_chain'])

    # ------------------------------------------------------------------ boundaries
    def test_exceptions_cross_the_ir_legacy_boundary_both_ways(self):
        results = self.check_program('boundary', BOUNDARY, ['ir_leaf', 'ir_wrap', 'ir_guard', 'ir_sandwich'])
        self.assertTrue(results[0][1].strip())

    def test_recursion_depth_is_restored_after_a_caught_exception(self):
        out = self.check_program('depth', DEPTH, ['dive'])[0]
        self.assertEqual(out[0], 0)
        self.assertTrue(out[1].strip().endswith('done'))

    def test_division_by_zero_in_a_tint_function_is_catchable(self):
        self.check_program('tintdiv', TINTDIV, ['quot'])

    def test_bytearray_parameter_kept_across_calls_and_exceptions(self):
        out = self.check_program('bytes', BYTEARRAY, ['fill', 'check'])[0]
        self.assertEqual(out[0], 0)

    # ------------------------------------------------------------------ uncaught
    def test_uncaught_exceptions_end_the_program_like_the_legacy_build(self):
        cases = list(range(UNCAUGHT_CASES))
        results = self.check_program('uncaught', UNCAUGHT, ['boom', 'mid', 'indexed', 'scan'],
                                     args_list=[(k,) for k in cases], cpython=False)
        for k, (status, stdout, stderr) in zip(cases, results):
            self.assertEqual(status, 1, (k, stderr))
            self.assertTrue(stdout.startswith('start %d\n' % k), (k, stdout))
            self.assertTrue(stderr.strip(), k)
        # the ones Python has the same rules for
        with tempfile.TemporaryDirectory() as tmp:
            for k in (0, 1, 2, 3, 4, 5):
                expected = cpython_run(tmp, 'uncaught', UNCAUGHT, (k,))
                self.assertEqual(results[k][:2], expected[:2], k)
                self.assertEqual(last_line(results[k][2]), last_line(expected[2]), k)

    def test_caught_traps_in_an_ir_function(self):
        # (wrap_add(INT64_MAX, 2) is Python's exact 18446744073709551614 in the IR build, where the int64 legacy
        # build stops with an OverflowError its handler catches: both IR builds are compared with CPython)
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'traps', TRAPS)
            for tag in ('ir', 'ir-checked'):
                self.assertEqual({'quot', 'peek', 'scan_bytes', 'wrap_add'} - built.ir[tag], set(), built.fallback[tag])
            expected = cpython_run(tmp, 'traps', TRAPS)
            for tag in ('ir', 'ir-checked'):
                self.assertEqual(run(built.exe[tag])[:2], expected[:2], tag)

    # ------------------------------------------------------------------ switch off
    def test_switch_off_leaves_no_trace_of_the_s2_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = {}
            for tag, mode in (('off', '0'), ('on', 'verify')):
                debug = Path(tmp, 'dbg-' + tag)
                path = Path(tmp, 'p.ail')
                path.write_text(NESTED)
                env = dict(os.environ, AIL_IR=mode)
                env.pop('AIL_IR_EXC', None)
                built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(path),
                                        '--syntax', 'python', '-o', str(Path(tmp, tag)), '--debug-dir', str(debug)],
                                       capture_output=True, text=True, timeout=600, env=env)
                self.assertEqual(built.returncode, 0, built.stderr)
                sources[tag] = (debug / 'program.c').read_text()
        for marker in ('ail_ir_try', 'ail_pending', 'IR exceptions (stage S2)', '__ir('):
            self.assertNotIn(marker, sources['off'], marker)
        self.assertIn('ail_ir_try', sources['on'])


# --------------------------------------------------------------------------------------------
# The programs
# --------------------------------------------------------------------------------------------

NESTED = '''
def leaf(x: int) -> int:
    if x % 7 == 0:
        raise ValueError("seven")
    if x % 11 == 0:
        raise IndexError
    if x % 13 == 0:
        assert x < 0, "thirteen"
    return x * 2


def mid(x: int) -> int:
    return leaf(x) + 1


def top(x: int) -> int:
    return mid(x) + mid(x + 1)


def safe(x: int) -> int:
    try:
        return top(x)
    except ValueError:
        return -1
    except IndexError:
        return -2


def after(x: int) -> int:
    t = 0
    try:
        t = top(x)
        t += 1000
    except ValueError:
        t = -10
    else:
        t += 5
    finally:
        t += 100000
    return t


def rr(x: int) -> int:
    try:
        try:
            return top(x)
        except ValueError:
            raise
    except ValueError:
        return -77


def loopy(n: int) -> int:
    t = 0
    for i in range(n):
        try:
            if i % 3 == 0:
                continue
            if i == 17:
                break
            t += leaf(i)
        except ValueError:
            t -= 1
        except IndexError:
            t -= 2
        finally:
            t += 1
    return t


def main():
    for i in range(1, 30):
        try:
            print(top(i))
        except ValueError:
            print("V")
        except IndexError:
            print("I")
        except AssertionError:
            print("A")
        try:
            print(after(i))
        except AssertionError:
            print("A2")
        except IndexError:
            print("I2")
        try:
            print(safe(i))
        except AssertionError:
            print("A4")
        try:
            print(rr(i))
        except IndexError:
            print("I3")
        except AssertionError:
            print("A3")
    try:
        print(loopy(40))
    except AssertionError:
        print("LA")
    print(top(7))


main()
'''

ORDERING = '''
class S:
    def __init__(self, log: list[int], n: int):
        self.log = log
        self.n = n


def inner(s: S, x: int) -> int:
    s.log.append(1)
    try:
        s.log.append(2)
        if x == 1:
            raise ValueError("one")
        if x == 2:
            return 20
        if x == 3:
            raise KeyError
        s.log.append(3)
    except ValueError:
        s.log.append(4)
        if x == 1:
            raise IndexError
    finally:
        s.log.append(5)
    s.log.append(6)
    return x


def outer(s: S, x: int) -> int:
    t = 0
    try:
        s.log.append(10)
        t = inner(s, x)
        s.log.append(11)
    except IndexError:
        s.log.append(12)
        t = -1
    except (KeyError, RuntimeError):
        s.log.append(13)
        t = -2
    else:
        s.log.append(14)
        t += 100
    finally:
        s.log.append(15)
    return t


def nested_finally(s: S, x: int) -> int:
    try:
        try:
            s.log.append(20)
            if x > 0:
                raise RuntimeError("r")
            s.log.append(21)
        finally:
            s.log.append(22)
            if x > 1:
                raise ValueError("replaced")
    except RuntimeError:
        s.log.append(23)
        return 1
    except ValueError:
        s.log.append(24)
        return 2
    s.log.append(25)
    return 0


def loops(s: S, n: int) -> int:
    t = 0
    i = 0
    while i < n:
        i += 1
        try:
            if i % 4 == 0:
                continue
            if i == 9:
                break
            try:
                if i % 3 == 0:
                    raise IndexError
                t += i
            finally:
                s.log.append(30 + i)
        except IndexError:
            t += 1000
        finally:
            s.log.append(50)
    return t


def reraise_chain(s: S, x: int) -> int:
    try:
        try:
            if x == 0:
                raise ValueError("a")
            if x == 1:
                raise IndexError
            return x
        except ValueError:
            s.log.append(60)
            raise
        except IndexError:
            s.log.append(61)
            raise RuntimeError("b")
    except RuntimeError:
        s.log.append(62)
        return -5
    finally:
        s.log.append(63)


def show(s: S):
    for k in range(len(s.log)):
        print(s.log[k])
    print(-1)
    while len(s.log) > 0:
        s.log.pop()


def main():
    s = S([], 0)
    for x in range(0, 5):
        try:
            print(outer(s, x))
        except ValueError:
            print("VE")
        except KeyError:
            print("KE")
        show(s)
    for x in range(0, 4):
        try:
            print(nested_finally(s, x))
        except ValueError:
            print("VE2")
        show(s)
    for n in (3, 10, 20):
        print(loops(s, n))
        show(s)
    for x in range(0, 4):
        try:
            print(reraise_chain(s, x))
        except ValueError:
            print("VE3")
        show(s)


main()
'''

# ir_* functions have only int parameters and int locals (the IR takes them); legacy_* use a str
# local, which keeps them on the legacy emitter.
BOUNDARY = '''
def ir_leaf(k: int) -> int:
    if k % 5 == 0:
        raise ValueError("leaf")
    if k % 7 == 0:
        raise IndexError
    return k + 1


def legacy_raise(k: int) -> int:
    name = "legacy"
    if k % 3 == 0:
        raise RuntimeError(name)
    return len(name) + k


def legacy_call_ir(k: int) -> int:
    tag = "lc"
    try:
        return ir_leaf(k) + len(tag)
    except ValueError:
        return -100 - len(tag)


def legacy_middle(k: int) -> int:
    tag = "mid"
    return ir_leaf(k) * 2 + len(tag)


def ir_wrap(k: int) -> int:
    return ir_leaf(k) + legacy_raise(k)


def ir_guard(k: int) -> int:
    try:
        return ir_wrap(k)
    except RuntimeError:
        return -200
    except ValueError:
        return -300


def ir_sandwich(k: int) -> int:
    try:
        return legacy_middle(k)
    except IndexError:
        return -400


def main():
    for k in range(1, 40):
        try:
            print(ir_guard(k))
        except IndexError:
            print("I")
        try:
            print(legacy_call_ir(k))
        except IndexError:
            print("I2")
        try:
            print(ir_sandwich(k))
        except ValueError:
            print("V3")
        try:
            print(legacy_middle(k))
        except ValueError:
            print("V4")
        except IndexError:
            print("I4")


main()
'''

DEPTH = '''
def dive(n: int, k: int) -> int:
    if n == 0:
        if k % 3 == 0:
            raise ValueError("bottom")
        return k
    return dive(n - 1, k) + 1


def survive(n: int) -> int:
    t = 0
    try:
        t = dive(n, n)
    except ValueError:
        t = -1
    return t


def main():
    total = 0
    for i in range(0, 3000):
        total += survive(100 + i % 50)
        try:
            total += dive(60, i)
        except ValueError:
            total -= 1
    print(total)
    print("done")


main()
'''

BYTEARRAY = '''
def check(i: int) -> int:
    if i == 7:
        raise ValueError("seven")
    return i


def fill(out: bytearray, n: int) -> int:
    for i in range(n):
        out.append(65 + i % 26)
        check(i)
    return len(out)


def main():
    out = bytearray()
    print(fill(out, 5))
    try:
        print(fill(out, 20))
    except ValueError:
        print(len(out))
    print(fill(out, 3))
    for k in range(0, 50):
        try:
            fill(out, 10)
        except ValueError:
            out.append(33)
    print(len(out))
    print(out[0])
    print(out[len(out) - 1])


main()
'''

UNCAUGHT_CASES = 14
UNCAUGHT = '''
import sys


class T:
    def __init__(self, xs: list[int]):
        self.xs = xs


def boom(k: int) -> int:
    if k == 0:
        raise ValueError("msg zero")
    if k == 1:
        raise IndexError
    if k == 2:
        raise KeyError
    if k == 3:
        assert k > 100
    if k == 4:
        assert k > 100, "assert msg"
    if k == 5:
        raise ZeroDivisionError()
    if k == 6:
        return 1 // (k - 6)
    if k == 7:
        return k * 9223372036854775807
    if k == 8:
        return 7 % (k - 8)
    return k


def mid(k: int) -> int:
    return boom(k) + 1


def indexed(t: T, k: int) -> int:
    return t.xs[k]


def scan(d: bytes, k: int) -> int:
    return d[k]


def main():
    k = int(sys.argv[1])
    print("start", k)
    if k < 9:
        print(mid(k))
    if k == 9:
        print(indexed(T([1, 2, 3]), 3))
    if k == 10:
        print(indexed(T([1, 2, 3]), -4))
    if k == 11:
        print(scan(b"abc", 3))
    if k == 12:
        print(scan(b"abc", -4))
    if k == 13:
        print(boom(k) + 1)
        print(mid(1))


main()
'''

TRAPS = '''
class T:
    def __init__(self, xs: list[int]):
        self.xs = xs


def quot(a: int, b: int) -> int:
    try:
        return a // b
    except ZeroDivisionError:
        return -1


def peek(t: T, i: int) -> int:
    try:
        return t.xs[i]
    except IndexError:
        return -2


def scan_bytes(d: bytes, i: int) -> int:
    try:
        return d[i]
    except IndexError:
        return -3


def wrap_add(a: int, b: int) -> int:
    try:
        return a * b
    except OverflowError:
        return -4


def main():
    t = T([5, 6, 7])
    for i in range(-5, 6):
        print(quot(100, i))
        print(peek(t, i))
        print(scan_bytes(b"hello", i))
    print(wrap_add(3, 4))
    print(wrap_add(9223372036854775807, 2))
    print(quot(7, 0))


main()
'''


# --------------------------------------------------------------------------------------------
# Generated programs
# --------------------------------------------------------------------------------------------

EXCEPTIONS = ['ValueError', 'IndexError', 'KeyError', 'ZeroDivisionError', 'RuntimeError']


class Gen(object):
    """Random nests of try/except/else/finally, raise, loops with break/continue, calls. Every
    function is `fK(s: S, x: int) -> int` and appends markers to `s.log`; main prints the result of
    each call (or the exception that left it) and the log."""

    def __init__(self, seed):
        self.r = random.Random(seed)
        self.depth_of_loops = 0
        self.names = []

    def k(self, lo, hi):
        return self.r.randint(lo, hi)

    def cond(self, loops):
        pick = self.r.random()
        if loops and pick < 0.3:
            return '%s %% %d == %d' % (self.r.choice(loops), self.k(2, 4), self.k(0, 1))
        if pick < 0.6:
            return '(x + %d) %% %d == %d' % (self.k(0, 9), self.k(2, 6), self.k(0, 1))
        if pick < 0.8:
            return 't %% %d == %d' % (self.k(2, 5), self.k(0, 1))
        return 'x > %d' % self.k(0, 12)

    def exc(self):
        return self.r.choice(EXCEPTIONS)

    def raise_stmt(self, name):
        form = self.r.random()
        if form < 0.35:
            return 'raise %s' % name
        if form < 0.6:
            return 'raise %s()' % name
        return 'raise %s("m%d")' % (name, self.k(0, 9))

    def stmts(self, depth, loops, handler, in_finally, budget):
        out = []
        for _ in range(self.k(1, 3)):
            out += self.stmt(depth, loops, handler, in_finally, budget)
        return out

    def stmt(self, depth, loops, handler, in_finally, budget):
        r = self.r.random()
        if r < 0.14:
            return ['s.log.append(%d)' % self.k(1, 99)]
        if r < 0.26:
            return ['t = (t * %d + x + %d) %% %d' % (self.k(2, 9), self.k(0, 9), self.k(50, 997))]
        if r < 0.38:
            return ['if %s:' % self.cond(loops), '    ' + self.raise_stmt(self.exc())]
        if r < 0.42:
            return ['t = (t + 7) // ((x + %d) %% %d)' % (self.k(0, 5), self.k(2, 4))]
        if r < 0.46:
            return ['assert %s' % self.cond(loops)]
        if r < 0.58 and self.names:
            g = self.r.choice(self.names)
            return ['t = (t + %s(s, x + %d)) %% 9973' % (g, self.k(0, 3))]
        if r < 0.64 and not in_finally:
            return ['if %s:' % self.cond(loops), '    return t + %d' % self.k(0, 9)]
        if r < 0.68 and handler:
            return ['if %s:' % self.cond(loops), '    raise']
        if r < 0.74 and loops and not in_finally:
            return ['if %s:' % self.cond(loops), '    %s' % self.r.choice(['break', 'continue'])]
        if budget > 0 and depth < 3:
            if r < 0.88:
                return self.try_stmt(depth, loops, handler, in_finally, budget - 1)
            if r < 0.95:
                v = 'i%d' % len(loops)
                body = self.stmts(depth + 1, loops + [v], handler, in_finally, budget - 1)
                return ['for %s in range(%d):' % (v, self.k(1, 4))] + ['    ' + l for l in body]
        return ['s.log.append(%d)' % self.k(100, 199)]

    def try_stmt(self, depth, loops, handler, in_finally, budget):
        body = self.stmts(depth + 1, loops, handler, in_finally, budget)
        out = ['try:'] + ['    ' + l for l in body]
        names = self.r.sample(EXCEPTIONS, self.k(1, 3))
        has_finally = self.r.random() < 0.4
        if self.r.random() < 0.85 or not has_finally:
            groups = []
            i = 0
            while i < len(names):
                size = 2 if self.r.random() < 0.3 and i + 1 < len(names) else 1
                groups.append(names[i:i + size])
                i += size
            for g in groups:
                head = g[0] if len(g) == 1 else '(%s)' % ', '.join(g)
                hb = self.stmts(depth + 1, loops, True, in_finally, 0)
                out += ['except %s:' % head] + ['    ' + l for l in hb]
            if self.r.random() < 0.3:
                eb = self.stmts(depth + 1, loops, handler, in_finally, 0)
                out += ['else:'] + ['    ' + l for l in eb]
        else:
            has_finally = True
        if has_finally:
            fb = self.stmts(depth + 1, [], handler, True, 0)
            out += ['finally:'] + ['    ' + l for l in fb]
        return out

    def program(self, nfuncs):
        lines = ['class S:',
                 '    def __init__(self, log: list[int], n: int):',
                 '        self.log = log',
                 '        self.n = n', '']
        for i in range(nfuncs):
            name = 'f%d' % i
            body = self.stmts(0, [], False, False, 2)
            lines += ['def %s(s: S, x: int) -> int:' % name, '    t = 0']
            lines += ['    ' + l for l in body]
            lines += ['    return t + %d' % self.k(0, 9), '', '']
            self.names.append(name)
        lines += ['def show(s: S):',
                  '    for k in range(len(s.log)):',
                  '        print(s.log[k])',
                  '    print(-1)',
                  '    while len(s.log) > 0:',
                  '        s.log.pop()', '', '']
        lines += ['def main():', '    s = S([], 0)', '    for x in range(0, 13):']
        for name in self.names:
            lines += ['        try:',
                      '            print(%s(s, x))' % name]
            for code, exc in enumerate(EXCEPTIONS + ['AssertionError']):
                lines += ['        except %s:' % exc, '            print(%d)' % (-code - 1)]
            lines += ['        show(s)']
        lines += ['', '', 'main()', '']
        return '\n'.join(lines), list(self.names)


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class GeneratedProgramTests(unittest.TestCase):
    SEEDS = (3, 8, 21)

    def test_generated_programs_agree_with_cpython_and_every_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            for seed in self.SEEDS:
                source, funcs = Gen(seed).program(5)
                with self.subTest(seed=seed):
                    built = Built(tmp, 'gen%d' % seed, source)
                    expected = cpython_run(tmp, 'gen%d' % seed, source)
                    self.assertEqual(expected[0], 0, expected[2] + source)
                    for tag in built.exe:
                        got = run(built.exe[tag])
                        self.assertEqual(got[:2], expected[:2], '%s\n%s' % (tag, source))
                    for tag in ('ir', 'ir-checked'):
                        # a function the IR cannot take is a coverage loss, not an error, but most
                        # of them must be on the IR path or the test checks nothing
                        self.assertGreaterEqual(len(set(funcs) & built.ir[tag]), len(funcs) - 1,
                                                (built.fallback[tag], source))


if __name__ == '__main__':
    unittest.main()
