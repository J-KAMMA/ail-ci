"""IR stage S3c-1: owned lists of str (docs/design/IR_OWNERSHIP_DESIGN_v2.md section 17,
python/pkg-v12/ir/).

A local `list[str]` is the legacy `ail_slist`: a spine of views over the function's text arena, owned by one
place. What this module pins:

* the new ops (`list.rt`, `list.has`, `list.sort`, `list.join`) print, parse and verify, and malformed uses are
  rejected by name; the emitted C frees the spine at every exit and links a cleanup frame when something can raise;
* every shape the lowering takes (split / split(sep) / splitlines, displays, append, sort, index, negative index,
  len, `for x in xs`, `for x in s.split()`, `in`, `not in`, join) agrees with the legacy build and CPython on
  stdout, status and the last line of stderr, with exceptions caught and uncaught, in both exception modes;
* the memory policy: a loop that allocates text resets the str arena at the top of each iteration only when no
  list of str written in the loop is live at the loop header (four live-across shapes are pinned, each of which
  would read freed text after a reset), and the iteration-local shape keeps the legacy build's peak memory;
* what stays legacy: sharing (`ys = xs`), a list handed to a call, a loop whose body resizes the list it
  iterates, and a function with a try in a loop (priced on tally_lang-ail-4: +20% of the function);
* sanitizers (ASan + UBSan + LSan) report nothing on the IR builds.
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

from ir import ir as I                       # noqa: E402
from ir import effects as E                  # noqa: E402
from ir import emit_c, rtc, text, verify     # noqa: E402
from test_ail_ir_s3 import Built, compile_program, run, last_line, HAVE_CC     # noqa: E402
from ail_testenv import ASAN_DETECT_LEAKS

LIST_STR = 'obj<list<strv>>'

# --------------------------------------------------------------------------------------------
# Op tests
# --------------------------------------------------------------------------------------------

SPLIT = '''func @parts(%s: strv) -> (i64) attrs {linkage = "extern", names = ["s"], owned = ["xs"], sym = "parts"} {
  %xs = local.alloc {name = "xs"} : place<obj<list<strv>>>
  %r = list.ref %xs : obj<list<strv>>
  %sep = str.lit {value = ","} : strv
  list.rt %r, %s, %sep {callee = "str_split_sep"}
  %zero = const {value = 0} : i64
  %first = list.get %r, %zero {mode = "ck"} : strv
  %has = list.has %r, %first : i1
  %joined = list.join %sep, %r : strv
  list.sort %r
  %n = list.len %r : i64
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
        fn, program = fn_of(SPLIT)
        verify.check(fn, program)
        printed = text.print_function(fn)
        again = text.parse_function(printed)
        self.assertEqual(text.print_function(again), printed)
        verify.check(again, program)

    def test_malformed_uses_are_rejected_by_name(self):
        self.bad(SPLIT.replace('"str_split_sep"', '"str_nothing"'), 'unknown runtime call')
        self.bad(SPLIT.replace('list.rt %r, %s, %sep', 'list.rt %r, %s'), 'list.rt str_split_sep takes')
        self.bad(SPLIT.replace('list.has %r, %first', 'list.has %r, %zero'), 'list.has takes')
        self.bad(SPLIT.replace('list.join %sep, %r', 'list.join %r, %sep'), 'list.join takes')
        self.bad(SPLIT.replace('list.sort %r', 'list.sort %zero'), 'list.sort takes a list of str')
        self.bad(SPLIT.replace('owned = ["xs"], ', ''), 'owned places')
        self.bad(SPLIT.replace('%r = list.ref %xs : obj<list<strv>>', '%r = load %xs : obj<list<strv>>'),
                 'never loaded or stored')

    def test_effects(self):
        fn, program = fn_of(SPLIT)
        eff = E.summarize(fn, program)
        self.assertIn('ValueError', eff.raises)              # an empty separator
        self.assertIn('IndexError', eff.raises)              # the checked read
        self.assertIn(rtc.ARENA, eff.allocs)                 # the join allocates in the str arena
        by_op = {i.op: E.instr_effects(i, fn, program) for i in I.walk(fn.body)}
        self.assertIn('Spine(Own(parts,xs))', by_op['list.rt'].writes)
        self.assertIn('Rebind(Own(parts,xs))', by_op['list.rt'].writes)
        self.assertEqual(by_op['list.has'].writes, frozenset())
        self.assertIn('Elem(Own(parts,xs))', by_op['list.sort'].writes)
        self.assertNotIn('Spine(Own(parts,xs))', by_op['list.sort'].writes)

    def test_c_frees_the_spine_at_every_exit_and_links_a_frame(self):
        fn, _ = fn_of(SPLIT)
        sig, c, needs = emit_c.emit_function(fn)
        self.assertIn('ail_slist v_xs = {0};', c)
        self.assertIn('ail_slist_free(&v_xs);', c)
        self.assertIn('ail_cleanup_frame', c)                # the checked read and the split can raise
        self.assertLessEqual({'STR', 'SLIST'}, needs['parts'])
        self.assertIn('ail_str_split_sep(', c)
        self.assertIn('ail_slist_has(', c)
        self.assertIn('ail_slist_sort(', c)
        self.assertIn('ail_str_join(&v__sarena,', c)


# --------------------------------------------------------------------------------------------
# Programs
# --------------------------------------------------------------------------------------------

SHAPES = '''import sys


def f1(text: str) -> int:
    n = 0
    for w in text.split():
        n += len(w)
    for a in [text, "x", text + "!"]:
        n += len(a)
    return n


def f2(k: int) -> str:
    acc: list[str] = []
    for i in range(k):
        acc.append(str(i * 7))
    acc.sort()
    if "14" in acc:
        acc.append("found")
    if "zzz" not in acc:
        acc.append("absent")
    return ",".join(acc) + "|" + acc[-1] + "|" + acc[0]


def f3(text: str) -> int:
    total = 0
    for line in text.splitlines():
        parts = line.split(",")
        total += len(parts)
        if len(parts) > 1:
            total += int(parts[1])
    return total


def f4(k: int) -> int:
    total = 0
    i = 0
    while i < k:
        xs = ("a b c " + str(i)).split()
        ys = xs[0] + xs[3]
        total += len(ys)
        i += 1
    return total


def f5() -> int:
    xs = ["q"]
    xs = []
    xs.append("\\u00e9")
    xs.append("\\u65e5\\u672c")
    return len(xs[0]) * 10 + len(xs[1])


def f6(k: int) -> int:
    xs = ["a", "bb"]
    return len(xs[k])


def f7(text: str) -> str:
    parts = text.split(" ")
    parts.sort()
    return "-".join(parts) + str(len(parts))


def f8(text: str) -> int:
    n = 0
    keep = ["a", "b", "\\u00e9"]
    for part in text.split(","):
        if part in keep:
            n += 1
        if part + "x" not in keep:
            n += 10
    return n


def main():
    print(f1("the quick  brown fox"))
    print(f2(12))
    print(f3("a,1\\nb\\nc,3,4\\n"))
    print(f4(1000))
    print(f5())
    try:
        print(f6(2))
    except IndexError:
        print("index")
    print(f6(-1))
    try:
        parts = "abc".split("")
        print(len(parts))
    except ValueError:
        print("value")
    print(f7("pear apple fig  kiwi"))
    print(f7(""))
    print(f8("a,b,c,,d"))
    print(f1(""), f1("   "), f3(""), f2(0))
    if len(sys.argv) > 1:
        print(f6(int(sys.argv[1])))


main()
'''

# the four shapes in which a list of str is live across the reset point of a loop that allocates text, and the
# two in which it is not: if the reset were wrong, ASan sees a read of a freed block (the sanitizer test), and the
# digest below changes with a corrupted element in the plain builds
LIVE = '''def accumulate(n: int) -> int:
    acc: list[str] = []
    for i in range(n):
        acc.append("item" + str(i))
    total = 0
    for s in acc:
        total += len(s) * 3 + ord(s[len(s) - 1]) - 48
    return total


def previous(n: int) -> int:
    prev = ["x"]
    total = 0
    for i in range(n):
        total += len(prev[0]) + ord(prev[0][0]) % 7
        junk = "junk" + str(i) + "junk"
        prev = [str(i) + "y" + junk[:2]]
    return total + len(prev[0])


def after_loop(n: int) -> int:
    last = ["none"]
    for i in range(n):
        last = [str(i) + "z"]
        junk = "junk" + str(i)
    return len(last[0]) * 100 + ord(last[0][0]) % 100


def while_after(n: int) -> int:
    i = 0
    cur = ["s"]
    while i < n:
        cur = [str(i) + "w"]
        junk = "j" + str(i)
        i += 1
    return len(cur[0]) * 100 + ord(cur[0][0]) % 100


def local(n: int) -> int:
    total = 0
    for i in range(n):
        parts = ("k" + str(i) + " v" + str(i)).split()
        total += len(parts[0]) + len(parts[1])
    return total


def read_only(n: int) -> int:
    base = ["a", "bb", "ccc"]
    total = 0
    for i in range(n):
        t = base[i % 3] + str(i)
        total += len(t)
    return total


def main():
    for n in (0, 1, 2, 50, 2000):
        print(accumulate(n), previous(n), after_loop(n), while_after(n), local(n), read_only(n))


main()
'''

# many iterations of an iteration-local list: the str arena must be reset (the legacy build keeps its peak)
MEMORY = '''import sys


def churn(n: int) -> int:
    total = 0
    for i in range(n):
        parts = ("field" + str(i) + ",value" + str(i) + ",more text to take up room in the arena").split(",")
        total += len(parts[0]) + len(parts[1]) + len(parts[2])
    return total


def main():
    print(churn(int(sys.argv[1])))


main()
'''

# statements that keep a function on the legacy emitter (it still builds, and agrees with CPython)
STAY = '''def share(n: int) -> int:
    xs = ["a", "b", "c"]
    ys = xs
    ys.append("d")
    return len(xs) * 10 + n


def lend(words: list[str]) -> int:
    return len(words)


def hand_over(n: int) -> int:
    xs = ["a", "b"]
    return lend(xs) + n


def resize_while_iterating(n: int) -> int:
    xs = ["a", "b"]
    total = 0
    for w in xs:
        total += len(w)
        if len(xs) < 5:
            xs.append(w + "!")
    return total + n


def main():
    print(share(1), hand_over(2), resize_while_iterating(3))


main()
'''

# a try inside a loop in a function with a list of str: the outlined try costs more than the legacy one
TRYLOOP = '''def run(n: int) -> int:
    pc = 0
    out: list[str] = []
    while pc < n:
        try:
            out.append(str(pc))
            if pc % 7 == 6:
                raise ValueError("e")
            pc += 1
        except ValueError:
            pc += 2
    return len(",".join(out))


def main():
    print(run(30))


main()
'''

UNCAUGHT = '''import sys


def pick(xs: list[str], k: int) -> str:
    return xs[k]


def main():
    words = "alpha beta gamma".split()
    k = int(sys.argv[1])
    print(words[k])
    print("after")


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

    def check(self, name, source, must_be_ir, args_list=((),), stay=(), cpython=True):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, name, source)
            for tag in ('ir', 'ir-checked'):
                self.assertEqual(set(must_be_ir) - built.ir[tag], set(), '%s: %s' % (tag, built.fallback[tag]))
                self.assertEqual(set(stay) & built.ir[tag], set(), tag)
            results = []
            for args in args_list:
                runs = {tag: run(built.exe[tag], args) for tag in built.exe}
                for tag in ('ir', 'ir-checked'):
                    named = runs[tag][:2] + (re.sub(r'(?m)^[A-Za-z]+Error: ', '', runs[tag][2]),)
                    self.assertEqual(named, runs['legacy'], '%s %s args=%s' % (name, tag, args))
                if cpython:
                    expected = cpython_run(tmp, name, source, args)
                    self.assertEqual(runs['ir'][1], expected[1], '%s args=%s stdout' % (name, args))
                    self.assertEqual(runs['ir'][0], expected[0], '%s args=%s status' % (name, args))
                    # (the legacy runtime prints the message without the exception name)
                    self.assertTrue(last_line(expected[2]).endswith(last_line(runs['ir'][2])),
                                    '%s args=%s stderr' % (name, args))
                results.append(runs['ir'])
            return results, built

    def test_every_shape_agrees_with_the_legacy_build_and_cpython(self):
        results, built = self.check('shapes', SHAPES, ['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'main'],
                                    args_list=((), (0,), (1,), (-1,), (-2,), (2,), (5,)))
        self.assertEqual(results[0][0], 0)
        self.assertEqual(results[5][0], 1)                    # the uncaught IndexError of xs[2]
        self.assertIn('list index out of range', results[5][2])

    def test_an_uncaught_index_error_leaves_with_the_legacy_message(self):
        results, built = self.check('uncaught', UNCAUGHT, ['main'], args_list=((0,), (2,), (-3,), (3,), (-4,)))
        self.assertEqual([r[0] for r in results], [0, 0, 0, 1, 1])
        self.assertEqual(results[3][1], '')

    def test_lists_live_across_the_reset_point_keep_their_text(self):
        results, built = self.check('live', LIVE, ['accumulate', 'previous', 'after_loop', 'while_after', 'local',
                                                   'read_only', 'main'])
        self.assertEqual(results[0][0], 0)

    def test_the_arena_is_reset_only_where_no_list_of_str_can_be_hurt(self):
        with tempfile.TemporaryDirectory() as tmp:
            Built(tmp, 'live', LIVE)
            c = Path(tmp, 'live.ir.stats').exists() and None
            compile_program(tmp, 'live2', LIVE, 'ir', {'AIL_IR': 'verify'}, debug=True)
            c = Path(tmp, 'live2.ir.d', 'program.c').read_text()

        def body(fn, nxt):
            start = c.index('int64_t %s(' % fn + '' if False else fn + '(int64_t v_n) {')
            return c[start:c.index(nxt, start)]
        for fn, nxt, resets in (('accumulate', 'int64_t previous(', False), ('previous', 'int64_t after_loop(', False),
                                ('after_loop', 'int64_t while_after(', False),
                                ('while_after', 'int64_t local(', False), ('local', 'int64_t read_only(', True),
                                ('read_only', 'void py_main(', True)):
            # (an unproven int parameter or result makes the signature tagged: `ail_tint fn(int64_t v_n)`)
            head = re.search(r'(?:int64_t|ail_tint) %s\((?:int64_t|ail_tint) v_n\) {' % fn, c)
            text_ = c[head.start():]
            tail = re.search(r'(?:int64_t|ail_tint) ' + re.escape(nxt[len('int64_t '):]), text_) if nxt.startswith('int64_t ') \
                else None
            text_ = text_[:tail.start()] if tail else (text_[:text_.index(nxt)] if nxt in text_ else text_)
            self.assertEqual('ail_sarena_keep_roots(' in text_, resets, fn)

    def test_an_iteration_local_list_keeps_the_legacy_peak_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'memory', MEMORY)
            self.assertIn('churn', built.ir['ir'])
            rss = {}
            for tag in ('legacy', 'ir'):
                r = subprocess.run(['/usr/bin/time', '-f', '%M', str(built.exe[tag]), '300000'],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                rss[tag] = int(r.stderr.strip().splitlines()[-1])
                self.assertEqual(r.stdout, run(built.exe['legacy'], ['300000'])[1])
            self.assertLessEqual(rss['ir'], rss['legacy'] * 1.1 + 512, rss)

    def test_shapes_with_a_second_name_a_call_or_a_resizing_loop_stay_legacy(self):
        # (typed path alone: the default build gives the function that shares a list to the general path, which
        # shares as Python does)
        import unittest.mock
        with unittest.mock.patch.dict(os.environ, {'AIL_NO_GENERAL': '1'}):
            results, built = self.check('stay', STAY, ['main'], stay=['share', 'hand_over', 'resize_while_iterating'],
                                        cpython=False)
        self.assertIn('list', built.fallback['ir']['share'])
        with tempfile.TemporaryDirectory() as tmp:
            expected = cpython_run(tmp, 'stay', STAY)
        # (the legacy emitter copies at `ys = xs`; Python shares, so only the other two lines can agree)
        self.assertEqual(results[0][1].split()[1:], expected[1].split()[1:])

    def test_a_try_in_a_loop_stays_legacy(self):
        results, built = self.check('tryloop', TRYLOOP, ['main'], stay=['run'])
        self.assertIn('try inside a loop', built.fallback['ir']['run'])

    def test_with_the_switch_off_the_generated_c_has_no_list_ops(self):
        with tempfile.TemporaryDirectory() as tmp:
            built, exe, entries = compile_program(tmp, 'off', SHAPES, 'off', {'AIL_IR': '0'}, debug=True)
            self.assertEqual(built.returncode, 0)
            c = Path(tmp, 'off.off.d', 'program.c').read_text()
            self.assertNotIn('ail_cleanup_frame v__cf', c)
            self.assertEqual([e for e in entries if e['path'] == 'ir'], [])

    def test_sanitizers_report_nothing_on_the_ir_builds(self):
        for name, source, args_list in (('shapes', SHAPES, ((), (5,), (-3,))), ('live', LIVE, ((),)),
                                        ('uncaught', UNCAUGHT, ((1,), (9,))), ('memory', MEMORY, ((2000,),)),
                                        ('stay', STAY, ((),))):
            with self.subTest(program=name), tempfile.TemporaryDirectory() as tmp:
                results = {}
                for tag, env in (('legacy', {'AIL_IR': '0'}), ('ir', {'AIL_IR': 'verify'}),
                                 ('ir-checked', {'AIL_IR': 'verify', 'AIL_IR_EXC': 'checked'})):
                    built, _, _ = compile_program(tmp, name, source, tag, env, debug=True)
                    self.assertEqual(built.returncode, 0, built.stderr)
                    san = Path(tmp, name + '.' + tag + '.san')
                    cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined',
                                         '-fno-sanitize-recover=undefined', '-fno-omit-frame-pointer', '-pthread',
                                         str(Path(tmp, '%s.%s.d' % (name, tag), 'program.c')), '-lm', '-o', str(san)],
                                        capture_output=True, text=True)
                    self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
                    env_run = dict(os.environ, ASAN_OPTIONS=ASAN_DETECT_LEAKS + ':abort_on_error=0',
                                   UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')
                    for args in args_list:
                        r = subprocess.run([str(san), *map(str, args)], capture_output=True, env=env_run, timeout=300)
                        results[(tag, args)] = (r.returncode, r.stdout, r.stderr.decode(errors='replace'))
                for args in args_list:
                    base = results[('legacy', args)]
                    for tag in ('ir', 'ir-checked'):
                        status, stdout, err = results[(tag, args)]
                        self.assertNotIn('runtime error', err, (name, tag))
                        self.assertNotIn('ERROR: AddressSanitizer', err, (name, tag, err[-800:]))
                        self.assertNotIn('ERROR: LeakSanitizer', err, (name, tag, err[-800:]))
                        if name != 'stay':
                            self.assertEqual((status, stdout), base[:2], (name, tag, args))


if __name__ == '__main__':
    unittest.main()
