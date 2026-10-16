"""IR stage S3a: owned numeric lists and bytearrays (docs/design/IR_OWNERSHIP_DESIGN_v2.md section 12,
python/pkg-v12/ir/).

* The new ops (`list.ref`, `list.reset`, `list.repeat`, `list.lit`, `list.reserve`, `list.move`,
  `list.call`, `ba.new`, `ba.drop`, `ba.clear`, `ba.write`, `ba.extend_lit`, `field.ba`) print, parse and
  verify; malformed uses are rejected by name: a list loaded or stored through its place, a list
  reference carried by a loop or yielded (a second owner), a span used after the list was resized,
  a list moved into itself, a list place the function does not declare as owned.
* The emitted C frees every owned list at every exit, links a cleanup frame exactly when something in
  the function can raise (so a longjmp frees them too), and has none otherwise.
* Programs that own numeric lists and bytearrays (creation, element access, growth, comprehensions,
  list-returning functions, iteration, hidden temporaries, moves into struct fields) take the IR path
  (AIL_IR=verify) and agree with CPython, the legacy build and both exception modes on stdout, status
  and the last line of stderr.
* Sharing semantics (decided 2026-10-15): shapes that make a second name for a list (`ys = xs`, `ys =
  xs[:]`, `t.f = xs` with `xs` written afterwards) are refused by the IR -- the function stays on the
  legacy emitter, whose value semantics they were compiled with, so the IR never changes what a
  program prints. The shapes where a copy and the original cannot be told apart (`t.f = xs` with `xs`
  dead, or only read, afterwards) are taken, and agree with CPython.
* Drops: a list is freed at its last use (peak RSS equals the legacy build's on a pipeline of
  whole-array steps), at every return, and by the cleanup frame when an exception unwinds.
* ASan + UBSan + LSan: the IR builds of the programs here, including the ones that raise out of
  functions that own lists, report nothing the legacy build does not.
* With the switch off nothing of the S3a runtime is in the generated C.
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

FILL = '''func @fill(%n: i64) -> (obj<list<i64>>) attrs {linkage = "extern", names = ["n"], owned = ["a"], ret_list = "list", sym = "fill"} {
  %a = local.alloc {name = "a"} : place<obj<list<i64>>>
  %zero = const {value = 0} : i64
  %one = const {value = 1} : i64
  %r = list.ref %a : obj<list<i64>>
  list.repeat %r, %zero, %n
  %len = list.len %r : i64
  for.range %zero, %len, %one {args = 1} {
  ^(%i: i64):
    %r2 = list.ref %a : obj<list<i64>>
    %v = mul %i, %i {mode = "ck"} : i64
    list.set %r2, %i, %v {mode = "ck"}
    continue
  }
  %r3 = list.ref %a : obj<list<i64>>
  return %r3
}
'''

BUFFER = '''func @buffer(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], owned = ["out"], sym = "buffer"} {
  %out = local.alloc {name = "out"} : place<obj<bytearray>>
  %zero = const {value = 0} : i64
  %one = const {value = 1} : i64
  ba.new %out, %zero
  for.range %zero, %n, %one {args = 1} {
  ^(%i: i64):
    %b = load %out : obj<bytearray>
    ba.push %b, %i
    continue
  }
  %b2 = load %out : obj<bytearray>
  %len = ba.len %b2 : i64
  return %len
}
'''


def fn_of(src):
    fn = text.parse_function(src)
    program = I.Program({fn.sym: fn})
    E.summarize_program(program)
    return fn, program


def ops(fn):
    return [ins.op for ins in I.walk(fn.body)]


class OpTests(unittest.TestCase):
    def test_round_trip_and_verify(self):
        for src in (FILL, BUFFER):
            fn, program = fn_of(src)
            verify.check(fn, program)
            printed = text.print_function(fn)
            again = text.parse_function(printed)
            self.assertEqual(text.print_function(again), printed)
            verify.check(again, program)

    def bad(self, src, message):
        fn = text.parse_function(src)
        program = I.Program({fn.sym: fn})
        errors = verify.verify_function(fn, program)
        self.assertTrue(any(message in e for e in errors), (message, errors))

    def test_malformed_uses_are_rejected_by_name(self):
        # a list is changed by list.* operations, never loaded or stored through its place
        self.bad(FILL.replace('%r = list.ref %a : obj<list<i64>>\n  list.repeat',
                              '%r = load %a : obj<list<i64>>\n  list.repeat'), 'never loaded or stored')
        # the function must declare the lists it owns
        self.bad(FILL.replace('owned = ["a"], ', ''), 'owned places')
        self.bad(FILL.replace('ret_list = "list", ', ''), 'ret_list must be set')
        # list.ref names a local place only
        self.bad(FILL.replace('%r3 = list.ref %a : obj<list<i64>>', '%r3 = list.ref %n : obj<list<i64>>'),
                 'list.ref takes the place of an owned list')
        # element types
        self.bad(FILL.replace('list.repeat %r, %zero, %n', 'list.repeat %r, %n, %n').replace(
            '%v = mul %i, %i {mode = "ck"} : i64', '%v = const {value = 1.5} : f64'), 'list.set takes')
        # a bytearray place is replaced by ba.new, never stored
        self.bad(BUFFER.replace('ba.new %out, %zero', 'store %out, %zero'), 'store of')
        self.bad(BUFFER.replace('ba.new %out, %zero', 'ba.new %n, %zero'), 'ba.new takes')

    def test_a_list_reference_cannot_be_carried_or_yielded(self):
        src = FILL.replace('''  for.range %zero, %len, %one {args = 1} {
  ^(%i: i64):''', '''  for.range %zero, %len, %one, %r {args = 1} {
  ^(%i: i64, %c: obj<list<i64>>):''').replace('''    continue
  }
  %r3''', '''    continue %c
  }
  %r3''')
        self.bad(src, 'cannot be carried')

    def test_a_span_must_not_outlive_a_resize_of_its_list(self):
        src = '''func @bad(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], owned = ["a"], sym = "bad"} {
  %a = local.alloc {name = "a"} : place<obj<list<i64>>>
  %zero = const {value = 0} : i64
  %one = const {value = 1} : i64
  %r = list.ref %a : obj<list<i64>>
  list.repeat %r, %zero, %n
  %s = span.of %r : span<i64>
  list.push %r, %one
  %v = span.get %s, %zero {mode = "ck"} : i64
  return %v
}
'''
        self.bad(src, 'resizes Own(bad,a) while a span over it is still in use')
        ok = src.replace('''  list.push %r, %one
  %v = span.get %s, %zero {mode = "ck"} : i64''', '''  %v = span.get %s, %zero {mode = "ck"} : i64
  list.push %r, %one''')
        fn, program = fn_of(ok)
        verify.check(fn, program)

    def test_move_and_call_typing(self):
        src = '''func @mv(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], owned = ["a", "b"], sym = "mv"} {
  %a = local.alloc {name = "a"} : place<obj<list<i64>>>
  %b = local.alloc {name = "b"} : place<obj<list<f64>>>
  %ra = list.ref %a : obj<list<i64>>
  %rb = list.ref %b : obj<list<f64>>
  list.move %ra, %rb
  %zero = const {value = 0} : i64
  return %zero
}
'''
        self.bad(src, 'list.move takes two lists of one type')
        self.bad(src.replace('list.move %ra, %rb', 'list.move %ra, %ra'), 'into itself')
        self.bad(src.replace('list.move %ra, %rb', 'list.call %ra {callee = "nothing"}'), 'unknown function')

    def test_owned_places_are_freed_at_every_exit_and_the_frame_exists_only_when_something_can_raise(self):
        fn, _ = fn_of(FILL)
        sig, c, needs = emit_c.emit_function(fn)
        self.assertIn('int64_t fill(int64_t v_n, int64_t *_out, int64_t _cap)', sig)
        self.assertIn('ail_cleanup_frame', c)            # list.set in ck mode can raise IndexError
        self.assertIn('ail_list_return(', c)
        self.assertIn('ail_list_free(&v_a);', c)
        self.assertLess(c.index('ail_list_return('), c.rindex('ail_list_free(&v_a);'))
        quiet = FILL.replace('list.set %r2, %i, %v {mode = "ck"}', 'list.set %r2, %i, %v {mode = "nck"}').replace(
            '%v = mul %i, %i {mode = "ck"}', '%v = mul %i, %i {mode = "nsw"}')
        fn, _ = fn_of(quiet)
        sig, c, needs = emit_c.emit_function(fn)
        self.assertNotIn('ail_cleanup_frame', c)         # nothing can raise: nothing to unwind
        self.assertIn('ail_list_free(&v_a);', c)
        self.assertLessEqual({'LIST', 'IRLIST', 'LISTRET'}, needs['parts'])

    def test_bytearray_places_are_released_not_freed(self):
        fn, _ = fn_of(BUFFER)
        _, c, needs = emit_c.emit_function(fn)
        self.assertIn('ail_bytearray_store(&v_out, ail_bytearray_new(', c)
        self.assertIn('ail_bytearray_release(v_out);', c)
        self.assertIn('BYTEARRAY', needs['parts'])


# --------------------------------------------------------------------------------------------
# Building and running programs
# --------------------------------------------------------------------------------------------

MODES = (('legacy', {'AIL_IR': '0'}),
         ('ir', {'AIL_IR': 'verify'}),
         ('ir-checked', {'AIL_IR': 'verify', 'AIL_IR_EXC': 'checked'}))


def compile_program(directory, name, source, tag, env_extra, debug=False):
    path = Path(directory, name + '.ail')
    exe = Path(directory, '%s.%s' % (name, tag))
    stats = Path(directory, '%s.%s.stats' % (name, tag))
    path.write_text(source)
    env = dict(os.environ, AIL_IR_STATS=str(stats))
    env.pop('AIL_IR_EXC', None)
    env.update(env_extra)
    command = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(path), '--syntax', 'python',
               '-o', str(exe)]
    if debug:
        command += ['--debug-dir', str(Path(directory, '%s.%s.d' % (name, tag)))]
    built = subprocess.run(command, capture_output=True, text=True, timeout=600, env=env)
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
    """One program built in every mode; `ir` are the functions the IR build took."""

    def __init__(self, directory, name, source, debug=False):
        self.source = source
        self.exe = {}
        self.ir = {}
        self.fallback = {}
        for tag, env in MODES:
            built, exe, entries = compile_program(directory, name, source, tag, env, debug)
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
                      must_stay_legacy=()):
        """Build in every mode; every run agrees across the modes (stdout, stderr, status) and, when
        `cpython`, with CPython (stdout, status, last line of stderr)."""
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, name, source)
            for tag in ('ir', 'ir-checked'):
                self.assertEqual(set(must_be_ir) - built.ir[tag], set(), '%s: %s' % (tag, built.fallback[tag]))
                self.assertEqual(set(must_stay_legacy) & built.ir[tag], set(), tag)
            results = []
            for args in args_list:
                runs = {tag: run(built.exe[tag], args) for tag in built.exe}
                for tag in ('ir', 'ir-checked'):
                    self.assertEqual(runs[tag], runs['legacy'], '%s %s args=%s' % (name, tag, args))
                if cpython:
                    expected = cpython_run(tmp, name, source, args)
                    self.assertEqual(runs['legacy'][1], expected[1], '%s args=%s stdout' % (name, args))
                    self.assertEqual(runs['legacy'][0], expected[0], '%s args=%s status' % (name, args))
                    if stderr_with_cpython:
                        self.assertEqual(last_line(runs['legacy'][2]), last_line(expected[2]),
                                         '%s args=%s stderr' % (name, args))
                results.append(runs['legacy'])
            return results, built

    # ------------------------------------------------------------------ creation, access, drops
    def test_owned_lists_creation_access_growth_and_iteration(self):
        results, built = self.check_program('lists', LISTS, ['fill', 'evens', 'ramp', 'weights', 'pipeline', 'stack',
                                                              'mixed', 'neg', 'fibs'])
        self.assertEqual(results[0][0], 0)

    def test_list_returning_functions_chain_through_the_return_buffer(self):
        self.check_program('chain', CHAIN, ['base', 'doubled', 'tail', 'again', 'total'])

    def test_a_list_function_called_in_a_loop_leaks_nothing(self):
        # the return protocol copies through the spill slot each time; 20000 calls of a 200 element list
        # must not grow the process (LSan in the sanitizer test, RSS here)
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'loopcall', LOOPCALL)
            self.assertLessEqual({'make', 'once'}, built.ir['ir'])
            rss = {}
            for tag in ('legacy', 'ir'):
                r = subprocess.run(['/usr/bin/time', '-f', '%M', str(built.exe[tag])], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                rss[tag] = int(r.stderr.strip().splitlines()[-1])
                self.assertEqual(r.stdout, run(built.exe['legacy'])[1])
            self.assertLessEqual(rss['ir'], rss['legacy'] * 1.05 + 256)

    # ------------------------------------------------------------------ sharing semantics
    def test_shapes_that_make_a_second_name_for_a_list_stay_on_the_legacy_emitter(self):
        # CPython shares: `ys = xs; ys[0] = 9` changes xs. The legacy emitter copies (value semantics),
        # so this program prints a different number there -- the divergence the design (section 1.5)
        # prices and S3b removes. The IR must not pick a side: these functions are refused, and the IR
        # build prints exactly what the legacy build prints.
        results, built = self.check_program('alias', ALIAS, ['clean'], cpython=False,
                                            must_stay_legacy=['share', 'slice_copy', 'swap_in_place'])
        for fn in ('share', 'slice_copy', 'swap_in_place'):
            self.assertIn(fn, built.fallback['ir'])
        self.assertRegex(built.fallback['ir']['share'], 'second name|copy')
        with tempfile.TemporaryDirectory() as tmp:
            cpython = cpython_run(tmp, 'alias', ALIAS)
        self.assertNotEqual(cpython[1], results[0][1])        # the documented divergence (W-ALIAS), S3b
        self.assertEqual(results[0][1].splitlines()[-1], 'clean 15')

    def test_a_list_moved_into_a_struct_field_where_a_copy_cannot_be_told_apart(self):
        results, built = self.check_program('fieldmove', FIELDMOVE, ['dead_after', 'read_after', 'fresh_fields'])
        self.assertEqual(results[0][0], 0)
        # ... and the ones where it can: CPython shares, the legacy build copies, the IR refuses
        results, built = self.check_program('fieldshare', FIELDSHARE, [], cpython=False,
                                            must_stay_legacy=['written_after', 'called_after', 'element_after',
                                                              'alias_in_loop'])
        for fn in ('written_after', 'called_after', 'element_after', 'alias_in_loop'):
            self.assertRegex(built.fallback['ir'][fn], 'field|top level|moved')
        with tempfile.TemporaryDirectory() as tmp:
            cpython = cpython_run(tmp, 'fieldshare', FIELDSHARE)
        self.assertNotEqual(cpython[1], results[0][1])            # the documented divergence (W-ALIAS)

    # ------------------------------------------------------------------ exceptions
    def test_exceptions_unwind_through_functions_that_own_lists(self):
        out, built = self.check_program('unwind', UNWIND, ['grow', 'index_error', 'popper', 'catcher', 'guarded',
                                                             'finally_list', 'raiser'])
        self.assertTrue(out[0][1].strip())

    def test_uncaught_exception_out_of_an_owner_ends_like_the_legacy_build(self):
        cases = list(range(UNCAUGHT_CASES))
        results, _ = self.check_program('uncaught', UNCAUGHT, ['boom'], args_list=[(k,) for k in cases],
                                        cpython=False)
        for k, (status, stdout, stderr) in zip(cases, results):
            self.assertEqual(status, 1, (k, stderr))
            self.assertTrue(stdout.startswith('start %d\n' % k), (k, stdout))
            self.assertTrue(stderr.strip(), k)
        with tempfile.TemporaryDirectory() as tmp:
            for k in cases[:-1]:          # (the last one overflows int64, where Python has big integers)
                expected = cpython_run(tmp, 'uncaught', UNCAUGHT, (k,))
                self.assertEqual(results[k][:2], expected[:2], k)

    # ------------------------------------------------------------------ bytearrays
    def test_owned_bytearrays_in_calls_returns_and_fields(self):
        self.check_program('bytes', BYTES, ['put32', 'pack', 'frame', 'build', 'fold', 'tail'])

    # ------------------------------------------------------------------ drops and peak memory
    def test_a_pipeline_of_whole_array_steps_holds_two_arrays_at_a_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'pipe', PIPE)
            self.assertIn('steps', built.ir['ir'])
            rss = {}
            for tag in ('legacy', 'ir'):
                r = subprocess.run(['/usr/bin/time', '-f', '%M', str(built.exe[tag])], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                rss[tag] = int(r.stderr.strip().splitlines()[-1])
            self.assertEqual(run(built.exe['ir']), run(built.exe['legacy']))
            # 5 steps over 4M-element lists (32 MB each): all alive would be 160 MB, two at a time 64 MB
            self.assertLess(rss['legacy'], 100000)
            self.assertLessEqual(rss['ir'], rss['legacy'] * 1.05 + 256)

    # ------------------------------------------------------------------ the C
    def test_the_c_of_a_list_function_frees_before_the_next_step_and_links_a_frame_only_when_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            built, exe, entries = compile_program(tmp, 'pipe', PIPE, 'ir', {'AIL_IR': 'verify'}, debug=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            c = Path(tmp, 'pipe.ir.d', 'program.c').read_text()
        body = c[c.index('int64_t steps(void) {'):]
        body = body[:body.index('\n}\n')]
        self.assertGreaterEqual(body.count('ail_list_free('), 5)
        self.assertIn('ail_cleanup_frame', body)         # the checked adds in the steps can raise

    @unittest.skipUnless(shutil.which('gcc'), 'no gcc')
    def test_the_cleanup_frame_is_what_frees_the_lists_when_an_exception_unwinds(self):
        # control for the leak check: the same IR C with the unwind helpers emptied leaks (LSan reports it),
        # so the clean runs of the sanitizer test above are the frames' doing
        with tempfile.TemporaryDirectory() as tmp:
            built, exe, entries = compile_program(tmp, 'unwind', UNWIND, 'ir', {'AIL_IR': 'verify'}, debug=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            c = Path(tmp, 'unwind.ir.d', 'program.c').read_text()
            helpers = re.findall(r'static void ail_unwind_(\w+)\(void \*\*p\) \{ ail_list_free', c)
            self.assertTrue(helpers, c[:200])
            mutated = re.sub(r'(static void ail_unwind_\w+\(void \*\*p\) \{)[^\n]*\}', r'\1 (void)p; }', c)
            self.assertNotEqual(mutated, c)
            path = Path(tmp, 'mutated.c')
            path.write_text(mutated)
            env_run = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0')
            reports = {}
            for tag, text_ in (('intact', c), ('emptied', mutated)):
                path.write_text(text_)
                exe_san = Path(tmp, tag)
                cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address', '-pthread', str(path), '-lm', '-o', str(exe_san)],
                                    capture_output=True, text=True)
                self.assertEqual(cc.returncode, 0, cc.stderr[-1500:])
                r = subprocess.run([str(exe_san)], capture_output=True, text=True, env=env_run, timeout=120)
                reports[tag] = r.stderr
        self.assertNotIn('LeakSanitizer', reports['intact'])
        self.assertIn('LeakSanitizer', reports['emptied'])

    def test_switch_off_leaves_no_trace_of_the_s3a_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = {}
            for tag, mode in (('off', '0'), ('on', 'verify')):
                built, exe, _ = compile_program(tmp, 'lists', LISTS, tag, {'AIL_IR': mode}, debug=True)
                self.assertEqual(built.returncode, 0, built.stderr)
                sources[tag] = Path(tmp, 'lists.%s.d' % tag, 'program.c').read_text()
        for marker in ('ail_ir_list_get', 'ail_ir_view_get', 'ail_ir_list_fail'):
            self.assertNotIn(marker, sources['off'], marker)
            self.assertIn(marker, sources['on'], marker)

    # ------------------------------------------------------------------ sanitizers
    def sanitize(self, name, source, args_list=((),)):
        """ASan + UBSan + LSan builds of the legacy and the IR C; returns {tag: [(status, stdout, stderr)]}."""
        out = {}
        with tempfile.TemporaryDirectory() as tmp:
            for tag, env in (('legacy', {'AIL_IR': '0'}), ('ir', {'AIL_IR': 'verify'}),
                             ('ir-checked', {'AIL_IR': 'verify', 'AIL_IR_EXC': 'checked'})):
                built, exe, _ = compile_program(tmp, name, source, tag, env, debug=True)
                self.assertEqual(built.returncode, 0, built.stderr)
                san = Path(tmp, name + '.' + tag + '.san')
                cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
                                     '-fno-omit-frame-pointer', '-pthread',
                                     str(Path(tmp, '%s.%s.d' % (name, tag), 'program.c')), '-lm', '-o', str(san)],
                                    capture_output=True, text=True)
                self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
                env_run = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0',
                               UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')
                runs = []
                for args in args_list:
                    r = subprocess.run([str(san), *map(str, args)], capture_output=True, text=True, timeout=300,
                                       env=env_run)
                    runs.append((r.returncode, r.stdout, r.stderr))
                out[tag] = runs
        return out

    @unittest.skipUnless(shutil.which('gcc'), 'no gcc')
    def test_sanitizers_report_nothing_on_the_ir_builds(self):
        cases = [('lists', LISTS, ((),)), ('chain', CHAIN, ((),)), ('unwind', UNWIND, ((),)),
                 ('bytes', BYTES, ((),)), ('fieldmove', FIELDMOVE, ((),)), ('fieldshare', FIELDSHARE, ((),)),
                 ('uncaught', UNCAUGHT, tuple((k,) for k in range(UNCAUGHT_CASES)))]
        for name, source, args_list in cases:
            with self.subTest(program=name):
                runs = self.sanitize(name, source, args_list)
                for tag in ('ir', 'ir-checked'):
                    for k, (status, stdout, stderr) in enumerate(runs[tag]):
                        self.assertNotIn('runtime error', stderr, (name, tag, k))
                        self.assertNotIn('AddressSanitizer', stderr, (name, tag, k))
                        self.assertNotIn('LeakSanitizer', stderr.replace('LeakSanitizer is disabled', ''),
                                         (name, tag, k, stderr[-600:]))
                        self.assertEqual((status, stdout), runs['legacy'][k][:2], (name, tag, k))


# --------------------------------------------------------------------------------------------
# The programs (Python syntax: they run unchanged under CPython)
# --------------------------------------------------------------------------------------------

LISTS = '''
def fill(n: int) -> list[int]:
    a = [0] * n
    for i in range(n):
        a[i] = i * 3 - 7
    return a


def evens(n: int) -> list[int]:
    return [i * 2 + 1 for i in range(n) if i % 3 != 0]


def ramp(n: int) -> list[float]:
    f = [0.5] * n
    for i in range(n):
        f[i] = f[i] * (i + 1) + 0.25
    return f


def weights(n: int) -> int:
    w = [1, 2, 3, 5, 8]
    f = [0.5, 1.5]
    s = 0
    for v in w:
        s += v * n
    for x in f:
        s += int(x * 4)
    e = []
    for i in range(n):
        e.append(i % 5)
    for v in e:
        s += v
    return s + len(e) + len(w)


def pipeline(n: int) -> int:
    a = fill(n)
    b = evens(n)
    c = ramp(n)
    t = 0
    for v in a:
        t += v
    for v in b:
        t -= v
    for x in c:
        t += int(x)
    d = [q * q for q in range(n)]
    k = 0
    for v in d:
        k = (k + v) % 1000003
    return t + k + len(a) + len(b) + len(c) + len(d)


def stack(n: int) -> int:
    s = [n]
    t = 0
    steps = 0
    while len(s) > 0 and steps < 100000:
        v = s.pop()
        steps += 1
        t += v
        if v > 1:
            s.append(v // 2)
            s.append(v - v // 2 - 1)
    return t * 10 + steps


def mixed(n: int) -> int:
    xs = [0] * 8
    ys = [0.0] * 8
    for i in range(n):
        xs[i % 8] += i
        ys[(i * 3) % 8] += i * 0.5
    t = 0
    for i in range(8):
        t += xs[i] + int(ys[i])
    zs = [t]
    zs.append(t + 1)
    return zs[0] + zs[1] + len(zs)


def fibs(n: int) -> int:
    a = [n, n + 1]
    if n < 2:
        return a[0] + a[1]
    b = [0.5] * 2
    return fibs(n - 1) + fibs(n - 2) + len(a) + int(b[1])


def neg(n: int) -> int:
    a = fill(n)
    return a[-1] * 1000 + a[-n] + a[n - 1]


def csum(xs: list[int]) -> int:
    t = len(xs)
    for i in range(len(xs)):
        t = (t * 31 + xs[i]) % 1000003
    return t


def fsum(xs: list[float]) -> int:
    t = len(xs)
    for i in range(len(xs)):
        t = (t * 31 + int(xs[i] * 4)) % 1000003
    return t


def main():
    for n in (1, 2, 7, 21):
        print(n, weights(n), pipeline(n), stack(n), mixed(n), neg(n), fibs(n))
    print(fsum(ramp(4)), fsum(ramp(0)))
    print(csum(fill(5)), csum(evens(9)))


main()
'''

CHAIN = '''
def base(n: int) -> list[int]:
    out = []
    for i in range(n):
        out.append(i * i % 17)
    return out


def doubled(n: int) -> list[int]:
    a = base(n)
    b = [v * 2 for v in range(n)]
    for i in range(len(a)):
        b[i] += a[i]
    return b


def tail(n: int) -> list[int]:
    t = doubled(n)
    t = doubled(n + 3)
    return t


def again(n: int) -> list[int]:
    r = [0, 0]
    r = tail(n)
    r = tail(n + 1)
    return r


def total(n: int) -> int:
    a = again(n)
    s = 0
    for v in a:
        s += v
    return s + len(a)


def csum(xs: list[int]) -> int:
    t = len(xs)
    for i in range(len(xs)):
        t = (t * 31 + xs[i]) % 1000003
    return t


def main():
    for n in (0, 1, 5, 40):
        print(n, total(n))
    print(csum(again(6)), csum(tail(2)))


main()
'''

LOOPCALL = '''
def make(n: int) -> list[int]:
    a = [0] * n
    for i in range(n):
        a[i] = i
    return a


def once(k: int) -> int:
    a = make(200)
    return a[k % 200]


def main():
    s = 0
    for i in range(20000):
        s += once(i)
    print(s)


main()
'''

ALIAS = '''
def share(n: int) -> int:
    xs = [1, 2, 3]
    ys = xs
    ys[0] = n
    return xs[0]


def slice_copy(n: int) -> int:
    xs = [1, 2, 3]
    ys = xs[:]
    ys[0] = n
    return xs[0] * 100 + ys[0]


def swap_in_place(n: int) -> int:
    a = [1, 2, 3, 4]
    b = [0] * 4
    for g in range(n):
        for i in range(4):
            b[i] = a[(i + 1) % 4] + g
        a = b
    return a[0] * 10 + a[3]


def clean(n: int) -> int:
    xs = [n] * 5
    t = 0
    for v in xs:
        t += v
    return t


def main():
    print('share', share(9))
    print('slice', slice_copy(9))
    print('swap', swap_in_place(3))
    print('clean', clean(3))


main()
'''

FIELDMOVE = '''
class T:
    def __init__(self, n: int):
        self.n = n
        self.order = [0]
        self.depth = [0]
        self.seen = 0
        self.total = 0


def dead_after(t: T, n: int) -> int:
    order = []
    for i in range(n):
        order.append(i * 2 + 1)
    t.order = order
    t.seen = n
    return 0


def read_after(t: T, n: int) -> int:
    order = []
    cur = 0
    while cur < n:
        order.append(cur)
        cur += 3
    t.order = order
    total = 0
    for v in order:
        total += v
    t.total = total + len(order)
    t.seen = len(order) + order[0]
    return total


def fresh_fields(t: T, n: int) -> int:
    t.depth = [7] * n
    t.order = [x * x for x in range(n)]
    t.depth[0] = 1
    t.order[1] = 5
    return t.depth[0] + t.order[1] + len(t.depth)


def csum(xs: list[int]) -> int:
    r = len(xs)
    for i in range(len(xs)):
        r = (r * 31 + xs[i]) % 1000003
    return r


def main():
    t = T(5)
    print(dead_after(t, 6), csum(t.order), t.seen)
    print(read_after(t, 20), csum(t.order), t.total, t.seen)
    print(fresh_fields(t, 4), csum(t.depth), csum(t.order))


main()
'''

# Shapes where CPython shares the list between the local and the field and the program can tell.
# Legacy copies; the IR refuses them (and so prints what the legacy build prints).
FIELDSHARE = '''
class T:
    def __init__(self, n: int):
        self.n = n
        self.order = [0]


def written_after(t: T, n: int) -> int:
    order = [1, 2, 3]
    t.order = order
    t.order[0] = n
    return order[0]


def helper(t: T) -> int:
    t.order = [9, 9]
    return 0


def called_after(t: T, n: int) -> int:
    order = [1, 2, 3]
    t.order = order
    helper(t)
    return order[0]


def element_after(t: T, n: int) -> int:
    order = [1, 2, 3]
    t.order = order
    order[0] = n
    return t.order[0]


def alias_in_loop(t: T, n: int) -> int:
    s = 0
    for i in range(n):
        order = [i, i + 1]
        t.order = order
        s += order[0]
    return s


def csum(xs: list[int]) -> int:
    r = len(xs)
    for i in range(len(xs)):
        r = (r * 31 + xs[i]) % 1000003
    return r


def main():
    t = T(5)
    print(written_after(t, 8), csum(t.order))
    print(called_after(t, 8), csum(t.order))
    print(element_after(t, 8), csum(t.order))
    print(alias_in_loop(t, 4), csum(t.order))


main()
'''

UNWIND = '''
def grow(n: int) -> int:
    a = [0] * 4
    b = []
    for i in range(n):
        b.append(i)
        a[i] = i
    return len(b) + a[0]


def index_error(n: int) -> int:
    a = [1, 2, 3]
    s = 0
    for i in range(n):
        s += a[i]
    return s


def popper(n: int) -> int:
    a = [n]
    t = 0
    for i in range(n + 1):
        t += a.pop()
    return t


def raiser(n: int) -> int:
    a = [n] * 3
    f = [1.5] * 3
    if n > 2:
        raise ValueError("too big")
    return a[0] + int(f[1])


def catcher(n: int) -> int:
    a = [1, 2, 3]
    t = 0
    try:
        t += grow(n)
    except IndexError:
        t = -1
    for v in a:
        t += v
    return t


def guarded(n: int) -> int:
    a = [10, 20]
    r = 0
    try:
        r = index_error(n)
    except IndexError:
        r = -5
    except ValueError:
        r = -6
    return r + a[1]


def finally_list(n: int) -> int:
    a = [1, 2, 3, 4]
    t = 0
    try:
        t = raiser(n) + a[n]
    except ValueError:
        t = -9
    finally:
        t += 1000
    return t


def main():
    for n in range(0, 7):
        try:
            print(n, catcher(n), guarded(n), finally_list(n))
        except IndexError:
            print(n, 'I')
        try:
            print(popper(n))
        except IndexError:
            print('P')
    print(raiser(1))


main()
'''

UNCAUGHT_CASES = 6
UNCAUGHT = '''
import sys


def fill(n: int) -> list[int]:
    a = [n] * 3
    for i in range(3):
        a[i] = i
    return a


def boom(k: int) -> int:
    a = fill(k + 1)
    b = [1.5, 2.5]
    c: list[int] = []
    for i in range(3):
        c.append(a[i] + int(b[i % 2]))
    if k == 0:
        return a[7]
    if k == 1:
        return c[-9]
    if k == 2:
        c.clear()
        return c.pop()
    if k == 3:
        raise ValueError("boom")
    if k == 4:
        return a[1] // (k - 4)
    return c[2] * 9223372036854775807


def main():
    k = int(sys.argv[1])
    print("start", k)
    print(boom(k))


main()
'''

BYTES = '''
def put32(out: bytearray, v: int) -> None:
    out.append(v & 255)
    out.append((v >> 8) & 255)
    out.append((v >> 16) & 255)
    out.append((v >> 24) & 255)


def pack(d: bytes) -> int:
    n = len(d)
    out = bytearray()
    head = [-1] * 64
    prv = [-1] * (n + 1)
    i = 0
    while i < n:
        k = (d[i] * 31 + (d[i + 1] if i + 1 < n else 0)) % 64
        prv[i] = head[k]
        head[k] = i
        out.append(d[i])
        i += 1
    put32(out, n)
    put32(out, head[3])
    h = 0
    for j in range(len(out)):
        h = (h * 257 + out[j]) % 1000003
    return h + len(out)


def frame(n: int) -> bytearray:
    out = bytearray()
    for i in range(n):
        out.append(i * 7 % 256)
    out.extend(b"<end>")
    put32(out, n)
    return out


def build(n: int) -> int:
    a = frame(n)
    b = frame(n + 2)
    t = 0
    for i in range(len(a)):
        t += a[i]
    for i in range(len(b)):
        t -= b[i]
    return t


class W:
    def __init__(self):
        self.buf = bytearray()
        self.k = 0


def fold(w: W, n: int) -> int:
    for i in range(n):
        w.buf.append(i % 200)
    w.buf.extend(b"xy")
    w.k = len(w.buf) + w.buf[1]
    return w.k


def tail(n: int) -> int:
    tmp = bytearray(n)
    for i in range(n):
        tmp[i] = (i * 5) % 251
    tmp.clear()
    tmp.append(42)
    return tmp[0] + len(tmp)


def main():
    print(pack(b"hello hello hello world"), pack(b"a"))
    print(build(5), build(0))
    w = W()
    print(fold(w, 7), fold(w, 3), len(w.buf))
    print(tail(0), tail(9))
    x = frame(3)
    print(len(x), x[0], x[-1])


main()
'''

PIPE = '''
def step(n: int, k: int) -> list[int]:
    a = [0] * n
    for i in range(n):
        a[i] = i + k
    return a


def steps() -> int:
    n = 4000000
    a = [1] * n
    for i in range(n):
        a[i] = i % 7
    b = [x + 1 for x in range(n)]
    s = 0
    for i in range(0, n, 1000):
        s += a[i] + b[i]
    c = [2] * n
    for i in range(0, n, 997):
        s += c[i]
    d = [3] * n
    for i in range(0, n, 991):
        s += d[i]
    e = [4] * n
    for i in range(0, n, 983):
        s += e[i]
    return s


def main():
    print(steps())


main()
'''


# --------------------------------------------------------------------------------------------
# Generated programs: workers that own lists and bytearrays, list-returning helpers, moves into a field
# --------------------------------------------------------------------------------------------

class _Gen(object):
    def __init__(self, seed):
        self.r = random.Random(seed)
        self.q = 0

    def k(self, lo, hi):
        return self.r.randint(lo, hi)

    def helper(self, name):
        form = self.r.choice(('repeat', 'comp', 'append'))
        c0, c1, c2 = self.k(0, 9), self.k(1, 9), self.k(0, 50)
        if form == 'repeat':
            return ['def %s(n: int) -> list[int]:' % name, '    a = [%d] * n' % c0, '    for i in range(n):',
                    '        a[i] = (i * %d + %d) %% 97' % (c1, c2), '    return a']
        if form == 'comp':
            return ['def %s(n: int) -> list[int]:' % name,
                    '    return [(i * %d + %d) %% 97 for i in range(n) if i %% %d != 1]' % (c1, c2, self.k(3, 5))]
        return ['def %s(n: int) -> list[int]:' % name, '    a: list[int] = []', '    for i in range(n):',
                '        a.append((i * %d + %d) %% 89)' % (c1, c2), '    a.append(%d)' % c0, '    return a']

    def op(self, helpers):
        c = self.k(1, 40)
        self.q += 1
        q = 'q%d' % self.q
        choice = self.r.randint(0, 12)
        if choice == 0:
            return ['a.append((t + %d) %% 97)' % c]
        if choice == 1:
            return ['if len(a) > 1:', '    t += a.pop()']
        if choice == 2:
            return ['a[(t + %d) %% len(a)] += t %% 13' % c]
        if choice == 3:
            return ['t = (t * 31 + a[(t + %d) %% len(a)]) %% 1000003' % c]
        if choice == 4:
            return ['for v in a:', '    t = (t * 17 + v) % 1000003']
        if choice == 5:
            return ['a = %s((t + %d) %% 6 + 1)' % (self.r.choice(helpers), c)]
        if choice == 6:
            return ['b = [(%s * %d + t) %% 53 for %s in range((t + %d) %% 5 + 1)]' % (q, c, q, c)]
        if choice == 7:
            return ['f[t % len(f)] = f[t % len(f)] * 1.5 + 0.25', 't = (t + int(f[0] * 4)) % 1000003']
        if choice == 8:
            return ['out.append((t + %d) & 255)' % c, 't = (t + len(out)) % 1000003']
        if choice == 9:
            return ['put(out, t)']
        if choice == 10:
            return ['try:', '    t += a[t % 7 - 3]', 'except IndexError:', '    t += %d' % c]
        if choice == 11:
            return ['t = (t + total(a)) % 1000003']
        return ['f = [%d.5] * (t %% 4 + 1)' % self.k(0, 3)]

    def worker(self, name, helpers):
        lines = ['def %s(s: S, n: int) -> int:' % name, '    t = n %% %d' % self.k(5, 13),
                 '    a = %s(n %% 5 + 2)' % self.r.choice(helpers), '    b: list[int] = []',
                 '    for i in range(n % 6 + 1):', '        b.append((i * 7 + t) % 31)',
                 '    f = [0.5] * (n % 4 + 1)', '    out = bytearray()']
        for _ in range(self.k(5, 12)):
            for line in self.op(helpers):
                lines.append('    ' + line)
        lines += ['    s.cnt += len(a) + len(b) + len(out)']
        if self.r.random() < 0.5:
            lines.append('    s.xs = b')                      # b is not mentioned again: Rule M
        lines.append('    return t % 1000003 + int(f[0])')
        return lines

    def program(self):
        lines = ['class S:', '    def __init__(self, n: int):', '        self.n = n', '        self.xs = [0]',
                 '        self.cnt = 0', '', '',
                 'def total(xs: list[int]) -> int:', '    r = len(xs)', '    for i in range(len(xs)):',
                 '        r = (r * 31 + xs[i]) % 1000003', '    return r', '', '',
                 'def put(out: bytearray, v: int) -> None:', '    out.append(v & 255)', '    out.append((v >> 8) & 255)',
                 '', '']
        helpers = ['h%d' % i for i in range(3)]
        for h in helpers:
            lines += self.helper(h) + ['', '']
        workers = ['w%d' % i for i in range(4)]
        for w in workers:
            lines += self.worker(w, helpers) + ['', '']
        lines += ['def main():', '    s = S(3)']
        for rep in range(3):
            for w in workers:
                lines.append('    print(%s(s, %d))' % (w, self.k(0, 40)))
        lines += ['    print(s.cnt, total(s.xs))', '', '', 'main()', '']
        return '\n'.join(lines), helpers + workers + ['total', 'put']


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class GeneratedProgramTests(unittest.TestCase):
    SEEDS = (3, 11, 29)

    def test_generated_owner_programs_agree_with_cpython_the_legacy_build_and_both_exception_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for seed in self.SEEDS:
                with self.subTest(seed=seed):
                    source, taken = _Gen(seed).program()
                    built = Built(tmp, 'gen%d' % seed, source)
                    expected = cpython_run(tmp, 'gen%d' % seed, source)
                    self.assertEqual(expected[0], 0, expected[2])
                    runs = {tag: run(built.exe[tag]) for tag in built.exe}
                    self.assertEqual(runs['legacy'][1], expected[1], source)
                    for tag in ('ir', 'ir-checked'):
                        self.assertEqual(runs[tag], runs['legacy'], (tag, source))
                        self.assertEqual(set(taken) - built.ir[tag], set(),
                                         (tag, built.fallback[tag], source))

    def test_every_pass_subset_gives_the_same_output(self):
        source, taken = _Gen(7).program()
        with tempfile.TemporaryDirectory() as tmp:
            expected = cpython_run(tmp, 'subsets', source)
            self.assertEqual(expected[0], 0, expected[2])
            for k, passes in enumerate(('', 'mem2reg', 'mem2reg,simplify', 'mem2reg,simplify,ranges',
                                        'mem2reg,simplify,licm')):
                with self.subTest(passes=passes):
                    built, exe, entries = compile_program(tmp, 'subsets', source, 'p%d' % k,
                                                          {'AIL_IR': 'verify', 'AIL_IR_PASSES': passes})
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertEqual(run(exe)[1], expected[1], source)
                    self.assertEqual(set(taken) - {e['fn'] for e in entries if e['path'] == 'ir'}, set())


if __name__ == '__main__':
    unittest.main()
