"""IR stage S4a: text at the boundary, so that `main` can be an IR function
(docs/design/IR_S4_STRINGS.md section 7, docs/design/IR_OWNERSHIP_DESIGN_v2.md section 14,
python/pkg-v12/ir/{rtc,lower_text,emit_text,flowtypes}.py).

* str and bytes are views over the function's arenas (the legacy policy); every operation is a call of
  the legacy runtime's own helper (`rt` entries of rtc.py), so the IR build prints what the legacy build
  prints, byte for byte: ints, floats, str, f-strings with format specs, `print` with sep/end/file,
  `sys.argv`, the stdin forms, int<->str conversions and their errors, non-ASCII text.
* `main` is an IR function: struct locals with the legacy reference counts, names that hold an int at one
  point and a float at another (one place per kind, `flowtypes.py`), loops that allocate text (the str arena
  is reset per iteration with every str place as a root).
* The IR build agrees with CPython on every program here (they are Python-syntax programs); the legacy
  build is compared too (stdout, status).
* Sanitizers (ASan + UBSan + LSan) on the IR builds; generated programs (>= 30 seeds).
* With AIL_IR unset the generated C has none of the S4a runtime (`ail_ir_char_at`).
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
from ir import rtc, text, verify             # noqa: E402
import test_ail_ir_s3 as S3                  # noqa: E402
from test_ail_ir_s3 import (Built, cpython_run, compile_program, last_line, HAVE_CC)   # noqa: E402
from ail_testenv import ASAN_DETECT_LEAKS


def run_with(exe, args=(), stdin=b'', env=None):
    r = subprocess.run([str(exe), *map(str, args)], input=stdin, capture_output=True, timeout=300,
                       env=dict(os.environ, **(env or {})))
    return r.returncode, r.stdout, r.stderr


def cpython_with(directory, name, source, args=(), stdin=b''):
    path = Path(directory, name + '.py')
    path.write_text(source)
    r = subprocess.run([sys.executable, str(path), *map(str, args)], input=stdin, capture_output=True, timeout=300)
    return r.returncode, r.stdout, r.stderr


# --------------------------------------------------------------------------------------------
# The programs (Python syntax: they run unchanged under CPython)
# --------------------------------------------------------------------------------------------

PRINTS = '''
import sys


def pad(s: str, k: int) -> str:
    return s + "." * k


def main():
    n = int(sys.argv[1])
    x = n / 7
    print(n)
    print(-n, n * 1000003, n - 100000)
    print(x)
    print(1.5, 100.0, 0.1, 1e16, 1.0e-5, x * 1e10)
    print("text", n, "\\u00e9", "\\u65e5\\u672c\\u8a9e", sep="|")
    print("a", "b", end="!\\n")
    print()
    print(f"{n}")
    print(f"n={n} x={x:.3f} s={'ab':>5}|{'cd':<5}|{'ef':^6}|{n:>8}|{n:<8}|{n:^8}|{n:08d}|{x:10.2f}|")
    print(f"{n * 2} and {n + 1}", file=sys.stderr)
    print("\\u00e9" + str(n) + "\\u65e5" + str(x))
    print("%d|%5d|%-5d|%05d|%.2f|%8.3f|%s|%5s|%-5s|" % (n, n, n, n, x, x, "ab", "cd", "ef"))
    print(pad("ab", n % 4), len(pad("\\u00e9\\u65e5", 3)))
    print(acc(n))
    return 0


def acc(n: int) -> str:
    t = ""
    for i in range(n % 6):
        t += str(i) + ","
    return t


sys.exit(main())
'''

ARGV = '''
import sys


def main():
    k = len(sys.argv)
    print(k)
    print(sys.argv[1])
    print(sys.argv[-1])
    print(len(sys.argv[1]))
    try:
        print(sys.argv[k + 3])
    except IndexError:
        print("index error")
    return 0


sys.exit(main())
'''

CONV = '''
import sys


def parse(s: str) -> int:
    try:
        return int(s)
    except ValueError:
        return -1


def parse_f(s: str) -> float:
    try:
        return float(s)
    except ValueError:
        return -1.0


def roundtrip(v: int) -> int:
    s = str(v)
    t = str(v * 3) + s
    return int(t[:len(t) // 2 + 1]) % 1000 + len(s)


def main():
    for s in ["12", " 7 ", "+3", "-0", "007", "x", "", "12a", "99999", "-45"]:
        print(parse(s))
    for s in ["2.5", "-1e3", " 4 ", "abc", "", ".5", "1e400", "-0.0"]:
        print(parse_f(s))
    for v in [0, 5, -5, 99, 100, -100, 123456789, -987654321]:
        print(str(v), roundtrip(v))
    for f in [0.0, -0.0, 1.5, 0.1, 100.0, 1e16, 1.0e-5, 123456.789]:
        print(str(f), f)
    n = int(sys.argv[1])
    print(int(str(n) + "0") // 10 == n, float(str(n)) + 0.5)
    try:
        v = int("not a number")
        print("unreachable", v)
    except ValueError as e:
        print("value error")
    return 0


sys.exit(main())
'''

TEXTOPS = '''
import sys


def digits(s: str) -> int:
    if len(s) == 0:
        return 0
    for ch in s:
        if not ch.isdigit():
            return 0
    return 1


def codes(s: str) -> int:
    t = 0
    for ch in s:
        t = (t * 31 + ord(ch)) % 1000003
    return t


def work(a: str, b: str) -> int:
    n = len(a)
    c = a[0]
    u = a[1:3]
    w = a[-2:]
    if a == b:
        n += 1
    if a < b:
        n += 2
    if a >= b:
        n += 3
    if c == "a":
        n += 5
    if "\\u00e9" in a:
        n += 7
    if "zz" not in a:
        n += 11
    if a.startswith("ab") or b.endswith("z"):
        n += 13
    z = a.strip() + "|" + u + "|" + w + "|" + b.lstrip("x") + "|" + b.rstrip("z")
    return n + len(z) + codes(z)


def main():
    a = sys.argv[1]
    b = sys.argv[2]
    print(work(a, b), digits(a), digits("12345"), digits(""), digits(b))
    print(codes(a + b))
    s = "caf\\u00e9 \\u65e5\\u672c\\u8a9e \\U0001f600!"
    print(len(s), s[3], s[-1], s[5:7], s[2:])
    print(s.strip(), len(s.strip("!")))
    print(build(40))
    return 0


def build(n: int) -> str:
    t = ""
    i = 0
    while i < n:
        t = t + chr_like(i)
        i += 1
    return t


def chr_like(i: int) -> str:
    if i % 3 == 0:
        return "x"
    if i % 3 == 1:
        return "\\u00e9"
    return str(i)


sys.exit(main())
'''

STDIN_BYTES = '''
import sys


def main():
    d = read_stdin_bytes(1 << 20)
    n = len(d)
    t = 0
    for c in d:
        t = (t * 257 + c) % 1000003
    s = d.decode()
    print(n, t, len(s), s[:5])
    out = bytearray()
    out.extend(d)
    out.extend(("[" + str(n) + "]").encode())
    write_stdout_bytes(out)
    print()
    return 0


sys.exit(main())
'''

STDIN_TEXT = '''
import sys


def main():
    a = input()
    b = sys.stdin.readline()
    c = sys.stdin.read()
    print(len(a), len(b), len(c))
    print(a + "|" + b.strip() + "|" + str(len(c.strip())))
    try:
        d = input()
        print("unreachable", d)
    except EOFError:
        print("eof")
    return 0


sys.exit(main())
'''

UNUSED_E = '''
import sys


def probe(k: int) -> int:
    try:
        if k == 0:
            raise ValueError("zero")
        if k == 1:
            return int("x")
        if k == 2:
            return int(sys.argv[5])
        return k
    except ValueError as e:
        return -1
    except IndexError as err:
        return -2


def main():
    for k in range(4):
        print(probe(k))
    return 0


sys.exit(main())
'''

# the int-or-float name: `c` holds an int in the first loop and a float in the second, and `x` depends on it
MIXED = '''
import sys


def main():
    s = sys.argv[1]
    n = int(sys.argv[2])
    x = 0
    for c in s.encode():
        x = (x * 10 + (c - 48)) % 1000003
    h = [0.0] * n
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        h[i] = float(x % 2001 - 1000) / 64.0
    t = 0.0
    for i in range(n):
        c = h[i]
        d = c * 0.5 + 1.0
        t = t + d
    total = 0
    for c in s.encode():
        total += c
    print(x, t, total)
    return 0


sys.exit(main())
'''

# an int-or-float name read where both kinds may reach: the function stays on the legacy emitter
AMBIGUOUS = '''
import sys


def pick(n: int) -> float:
    v = 1
    if n > 3:
        v = 2.5
    return v * 2


def main():
    print(pick(int(sys.argv[1])))
    return 0


sys.exit(main())
'''

STRUCTS = '''
import sys


class Acc:
    def __init__(self, xs: list[int], total: int):
        self.xs = xs
        self.total = total


class Pt:
    def __init__(self, x: int, y: float):
        self.x = x
        self.y = y


def add(a: Acc, v: int) -> int:
    a.xs.append(v)
    a.total += v
    return len(a.xs)


def norm(p: Pt) -> float:
    return p.x * 1.5 + p.y


def main():
    n = int(sys.argv[1])
    a = Acc([], 0)
    b = Acc([n, n + 1], 5)
    p = Pt(n, 0.25)
    q = p
    for i in range(n % 7 + 3):
        add(a, i * n)
        add(b, i)
    q.y = q.y + 1.0
    print(a.total, len(a.xs), b.total, len(b.xs), norm(p), norm(q))
    r = Acc([0] * n, n)
    print(len(r.xs), r.total, a.xs[1], b.xs[0])
    return 0


sys.exit(main())
'''

# a loop that allocates text every iteration and keeps one string across iterations
LOOPS = '''
import sys


def main():
    n = int(sys.argv[1])
    keep = "start"
    total = 0
    for i in range(n):
        s = "item-" + str(i) + "-" + str(i * i)
        t = s + s
        total += len(t)
        if i % 1000 == 7:
            keep = t[:20]
    print(total, keep, len(keep))
    k = 0
    last = ""
    while k < 50:
        last = "<" + str(k) + ">"
        k += 1
    print(last)
    return 0


sys.exit(main())
'''

FUNCS = '''
import sys


def label(i: int) -> str:
    if i % 2 == 0:
        return "even" + str(i)
    return "odd" + str(i)


def join3(a: str, b: str, c: str) -> str:
    return a + "/" + b + "/" + c


def main():
    t = 0
    for i in range(int(sys.argv[1])):
        s = join3(label(i), label(i + 1), "z")
        t += len(s)
        if i % 4 == 0:
            print(s)
    print(t)
    return 0


sys.exit(main())
'''

# where the legacy runtime and CPython disagree today (docs/design/IR_S4_STRINGS.md section 10, Q4): the IR build
# is pinned to the legacy build, not to CPython
DIVERGE = '''
import sys


def parse(s: str) -> int:
    try:
        return int(s)
    except ValueError:
        return -1


def main():
    print(parse("1_0"), parse("\\u0661\\u0662"), parse("1 2"), parse("0x1f"), parse("\\u00a0 5"))
    return 0


sys.exit(main())
'''

# text values and arenas across try/except (the function keeps its places and arenas in a frame)
TRYTEXT = '''
import sys


def risky(s: str, k: int) -> int:
    t = s + str(k)
    u = t[1:]
    if k == 3:
        raise ValueError("boom")
    return len(u) + int(sys.argv[k % 3 + 1])


def main():
    s = sys.argv[1]
    out = 0
    for i in range(5):
        try:
            t = s + str(i) + sys.argv[i + 2]
            out += len(t)
            print(t)
            out += risky(s, i)
        except IndexError:
            print("missing", i)
        except ValueError:
            print("bad", i, "x" + s)
    print(out)
    return out % 7


sys.exit(main())
'''

# exceptions nothing catches: the text printed so far, the status and the message are the legacy build's
UNCAUGHT = '''
import sys


def main():
    s = sys.argv[1]
    print("before", s, len(s))
    k = int(sys.argv[2])
    if k == 0:
        print(int(s))
    if k == 1:
        print(s[len(s) + 4])
    if k == 2:
        print(sys.argv[9])
    print("after", s + str(k))
    return 0


sys.exit(main())
'''

# a str-returning function that raises (the exception entry point returns a str too)
PICK = '''
import sys


def pick(s: str, k: int) -> str:
    t = s + str(k)
    if k == 3:
        raise ValueError("boom")
    return t[1:] + str(int(s))


def main():
    s = sys.argv[1]
    out = 0
    for i in range(5):
        try:
            u = pick(s, i)
            print(u)
            out += len(u)
        except ValueError:
            print("bad", i)
    print(out)
    return 0


sys.exit(main())
'''

# bytes search with names and literals, a comprehension variable named like an outer variable, loops over
# literal lists of every kind
MISC = '''
import sys


def main():
    d = b"ab\\ncd\\nef\\n"
    nl = d.find(b"\\n")
    nl2 = d.find(b"\\n", nl + 1)
    nl3 = d.find(b"\\n", 7, 9)
    r = d.rfind(b"\\n")
    missing = d.find(b"zz")
    print(nl, nl2, nl3, r, missing, len(d), d.find(b"cd"))
    k = int(sys.argv[1]) % 5
    s = d[k:]
    print(len(s), s.find(b"e"), d.rfind(b"e", 0, k + 1))
    i = 5
    xs = [i * 2 for i in range(3)]
    print(i, xs[2], len(xs))
    for i in range(2):
        ys = [i + j for j in range(3)]
        print(i, ys[1])
    zs = [i for i in range(4)]
    print(i, zs[3])
    t = 0
    for v in [3, -4, 5, 1000000007]:
        t += v
    f = 0.0
    for g in [0.5, -1.25, 100.0]:
        f += g
    out = ""
    for w in ["a", "bb", "\\u00e9"]:
        out = "<" + w + ">"
        print(w, len(w))
    print(t, f, out)
    return 0


sys.exit(main())
'''

# read_bytes(path) (an AIL builtin: no CPython run), including the OSError of a missing file
READ_BYTES = '''
import sys


def main():
    try:
        d = read_bytes(sys.argv[1])
    except OSError:
        print("no such file")
        return 3
    t = 0
    for c in d:
        t = (t * 31 + c) % 1000003
    print(len(d), t, d.decode()[:4])
    return 0


sys.exit(main())
'''

# bytes-returning functions cross the legacy protocol: the result is an owned copy that the caller adopts (a
# view of a parameter or of a literal must not reach the caller's arena)
BYTESFN = '''
import sys


def same(d: bytes) -> bytes:
    return d


def empty(n: int) -> bytes:
    if n == 0:
        return b""
    return b"xyz"[:n]


def cat(a: bytes, b: bytes) -> bytes:
    return a + b


def main():
    k = int(sys.argv[1])
    d = b"hello" + b"!"
    e = same(d)
    f = empty(k)
    g = cat(e, f)
    h = cat(g, empty(0))
    print(len(g), len(h), g.decode(), h.decode(), same(f).decode() + "|")
    return 0


sys.exit(main())
'''

PROGRAMS = {'prints': PRINTS, 'argv': ARGV, 'conv': CONV, 'textops': TEXTOPS, 'unused_e': UNUSED_E,
            'mixed': MIXED, 'structs': STRUCTS, 'loops': LOOPS, 'funcs': FUNCS}


# --------------------------------------------------------------------------------------------
# Unit tests of the table and the new ops
# --------------------------------------------------------------------------------------------

def parse_fn(src):
    return text.parse_function(src)


class TableTests(unittest.TestCase):
    def test_every_entry_is_typed_and_has_an_effect_record(self):
        from ir import effects as E
        for name, e in rtc.ENTRIES.items():
            self.assertIn(name, E.RUNTIME, name)
            params, results, eff = E.RUNTIME[name]
            self.assertEqual((params, results), (e['params'], e['results']))
            for t in params + results:
                self.assertEqual(I.type_errors(t), [], (name, t))
            for a in e['attrs']:
                # (`win`, the window cell of S4c-1, is spelled {W} in the template)
                self.assertIn('{' + ('W' if a == 'win' else a) + '}', e['c'], (name, a))
            if e['arena']:
                self.assertTrue(e['effects'].allocs, name)
            if e['pure']:
                eff = e['effects']
                self.assertFalse(eff.writes or eff.raises or eff.io or eff.allocs or eff.unknown, name)

    def test_text_ops_print_parse_and_verify(self):
        src = '''func @t(%0: strv, %1: i64) -> (i64) attrs {linkage = "extern", names = ["s", "n"], sym = "t"} {
  %2 = str.lit {value = "h\\u00e9llo"} : strv
  %3 = rt %0, %2 {callee = "str_eq"} : i1
  %4 = rt %0 {callee = "str_len"} : i64
  %5 = rt %0, %1 {callee = "str_index_cur", cur = 0} : strv
  %6 = bytes.lit {data = [1, 2, 255]} : bytes
  %7 = rt %6 {callee = "bytes_to_int"} : i64
  print %4, %5 {kinds = ["int", "str"], stream = "stdout"}
  return %4
}
'''
        fn = parse_fn(src)
        self.assertEqual(text.print_function(parse_fn(text.print_function(fn))), text.print_function(fn))
        verify.check(fn, I.Program({'t': fn}))

    def test_the_verifier_rejects_malformed_text_ops(self):
        def bad(src, message):
            fn = parse_fn(src)
            with self.assertRaises(I.IRError) as cm:
                verify.check(fn, I.Program({fn.sym: fn}))
            self.assertIn(message, str(cm.exception))
        head = 'func @t(%0: strv, %1: i64) -> (i64) attrs {linkage = "extern", names = ["s", "n"], sym = "t"} {\n'
        bad(head + '  %2 = rt %1, %1 {callee = "str_eq"} : i1\n  return %1\n}\n', 'runtime argument mismatch')
        bad(head + '  %2 = rt %0 {callee = "no_such"} : i64\n  return %1\n}\n', 'unknown runtime entry')
        bad(head + '  print %0 {kinds = ["int"], stream = "stdout"}\n  return %1\n}\n', 'print int argument')
        bad(head + '  print %0 {kinds = ["str"], stream = "stdout", parts = true, sep = true}\n  return %1\n}\n',
            'print takes its values')
        bad(head + '  %2 = rt %0 {callee = "fmt_int"} : strv\n  return %1\n}\n', 'runtime argument mismatch')
        bad(head + '  %2 = str.lit {value = 5} : strv\n  return %1\n}\n', 'str.lit yields a strv')


# --------------------------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------------------------

@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ProgramTests(unittest.TestCase):
    maxDiff = None

    def check(self, name, source, must_be_ir, args_list, stdin=b'', cpython=True, stderr_equal=True,
              must_stay_legacy=()):
        """Build in every mode; every run agrees across the modes (stdout, stderr, status) and with CPython
        (stdout, status, and the stderr of the program)."""
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, name, source)
            for tag in ('ir', 'ir-checked'):
                self.assertEqual(set(must_be_ir) - built.ir[tag], set(), '%s: %s' % (tag, built.fallback[tag]))
                self.assertEqual(set(must_stay_legacy) & built.ir[tag], set(), tag)
            results = []
            for args in args_list:
                runs = {tag: run_with(built.exe[tag], args, stdin) for tag in built.exe}
                for tag in ('ir', 'ir-checked'):
                    self.assertEqual(runs[tag], runs['legacy'], '%s %s args=%s' % (name, tag, args))
                if cpython:
                    expected = cpython_with(tmp, name, source, args, stdin)
                    self.assertEqual(runs['ir'][1], expected[1], '%s args=%s stdout' % (name, args))
                    self.assertEqual(runs['ir'][0], expected[0], '%s args=%s status' % (name, args))
                    if stderr_equal:
                        self.assertEqual(runs['ir'][2], expected[2], '%s args=%s stderr' % (name, args))
                results.append(runs['ir'])
            return results, built

    def test_print_formats_match_cpython(self):
        results, built = self.check('prints', PRINTS, ['main', 'pad'], [(3,), (123456,), (0,), (-9,)])
        self.assertIn(b'n=3 x=0.429', results[0][1])
        # an accumulating str local is a builder local: its owned buffer is stage S4c
        self.assertIn('builder', built.fallback['ir'].get('acc', ''))

    def test_argv_forms(self):
        self.check('argv', ARGV, ['main'], [('ab',), ('x', 'y', 'z'), ('é日',)])

    def test_int_float_str_conversions_and_their_errors(self):
        self.check('conv', CONV, ['main', 'parse', 'parse_f', 'roundtrip'], [(7,), (123,)], stderr_equal=False)

    def test_where_the_legacy_runtime_differs_from_cpython_the_ir_build_follows_the_legacy_build(self):
        results, built = self.check('diverge', DIVERGE, ['main', 'parse'], [()], cpython=False)
        self.assertEqual(results[0][0], 0)

    def test_text_operations_on_ascii_and_non_ascii(self):
        self.check('textops', TEXTOPS, ['main', 'work', 'digits', 'codes', 'chr_like'],
                   [('abc', 'abd'), ('xxéyy', 'a'), ('zzab', 'xxzz'), ('  ab ', 'xzx')])

    def test_stdin_bytes_form(self):
        data = 'héllo wörld\n12345'.encode()
        t = 0
        for c in data:
            t = (t * 257 + c) % 1000003
        s = data.decode()
        results, _ = self.check('stdinb', STDIN_BYTES, ['main'], [()], stdin=data, cpython=False)   # (AIL builtins)
        self.assertEqual(results[0][1], ('%d %d %d %s\n' % (len(data), t, len(s), s[:5])).encode() + data
                         + ('[%d]' % len(data)).encode() + b'\n')

    def test_read_bytes_of_a_file_and_of_a_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'in.bin')
            data = 'caf\u00e9 bytes\n'.encode() * 3
            path.write_bytes(data)
            t = 0
            for c in data:
                t = (t * 31 + c) % 1000003
            results, _ = self.check('readb', READ_BYTES, ['main'], [(str(path),), (str(Path(tmp, 'missing')),)],
                                    cpython=False)
            self.assertEqual(results[0][1], ('%d %d %s\n' % (len(data), t, data.decode()[:4])).encode())
            self.assertEqual((results[1][0], results[1][1]), (3, b'no such file\n'))

    def test_stdin_text_forms(self):
        self.check('stdint', STDIN_TEXT, ['main'], [()], stdin=b'first line\nsecond line\nthe rest\nof it\n')
        self.check('stdint2', STDIN_TEXT, ['main'], [()], stdin=b'only one line')

    def test_unused_exception_names(self):
        self.check('unused_e', UNUSED_E, ['main', 'probe'], [()], stderr_equal=False)

    def test_main_with_names_that_hold_an_int_and_then_a_float(self):
        results, built = self.check('mixed', MIXED, ['main'], [('12345', 50), ('7', 3), ('987', 1)])
        # the legacy build keeps these names in tagged cells; the IR build has plain int and float places
        with tempfile.TemporaryDirectory() as tmp:
            built, exe, entries = compile_program(tmp, 'mixed', MIXED, 'ir', {'AIL_IR': 'verify'}, debug=True)
            c = Path(tmp, 'mixed.ir.d', 'program.c').read_text()
            self.assertNotIn('_nb.floating', c)
            built, exe, entries = compile_program(tmp, 'mixed', MIXED, 'legacy', {'AIL_IR': '0'}, debug=True)
            self.assertIn('_nb', Path(tmp, 'mixed.legacy.d', 'program.c').read_text())

    def test_a_name_that_may_hold_either_kind_where_it_is_read_stays_legacy(self):
        results, built = self.check('ambiguous', AMBIGUOUS, ['main'], [(1,), (5,)], cpython=False,
                                    must_stay_legacy=['pick'])
        self.assertIn('int-or-float', built.fallback['ir']['pick'])

    def test_text_values_and_arenas_across_try_except(self):
        self.check('trytext', TRYTEXT, ['main', 'risky'], [('12', '7', '8'), ('12', '7', '8', '9', '10', '11', '12'),
                                                          ('12', '7', 'x')], stderr_equal=False)

    def test_a_str_function_that_raises_in_both_exception_modes(self):
        self.check('pick', PICK, ['main', 'pick'], [('12',), ('x',)], stderr_equal=False)

    def test_uncaught_exceptions_end_like_the_legacy_build(self):
        # (the messages are the legacy runtime's; CPython words some of them differently: stage S4e)
        with tempfile.TemporaryDirectory() as tmp:
            built = Built(tmp, 'uncaught', UNCAUGHT)
            self.assertEqual({'main'} - built.ir['ir'], set(), built.fallback['ir'])
            for args in [('ab', 5), ('ab', 0), ('ab', 1), ('ab', 2), ('7', 0), ('\u00e9\u65e5', 1)]:
                runs = {tag: run_with(built.exe[tag], args) for tag in built.exe}
                self.assertEqual(runs['ir'], runs['legacy'], args)
                self.assertEqual(runs['ir-checked'], runs['legacy'], args)
                expected = cpython_with(tmp, 'uncaught', UNCAUGHT, args)
                self.assertEqual(runs['ir'][:2], expected[:2], args)

    def test_bytes_search_comprehension_scope_and_literal_loops(self):
        results, built = self.check('misc', MISC, ['main'], [(2,), (9,)])
        self.assertIn(b'5 4 3', results[0][1])

    def test_bytes_returning_functions_hand_back_owned_copies(self):
        self.check('bytesfn', BYTESFN, ['main', 'same', 'empty', 'cat'], [(0,), (2,), (9,)])

    def test_struct_locals_with_the_legacy_reference_counts(self):
        self.check('structs', STRUCTS, ['main', 'add', 'norm'], [(3,), (10,), (0,)])

    def test_loops_that_allocate_text_reset_the_arena_each_iteration(self):
        results, built = self.check('loops', LOOPS, ['main'], [(10,), (3000,)])
        with tempfile.TemporaryDirectory() as tmp:
            built, exe, entries = compile_program(tmp, 'loops', LOOPS, 'ir', {'AIL_IR': 'verify'}, debug=True)
            c = Path(tmp, 'loops.ir.d', 'program.c').read_text()
            self.assertIn('ail_sarena_keep_roots', c.split("int64_t py_main(void) {")[1])
            # memory stays flat: a million iterations hold what a thousand do
            small = subprocess.run(['/usr/bin/time', '-f', '%M', str(exe), '2000'], capture_output=True, text=True)
            big = subprocess.run(['/usr/bin/time', '-f', '%M', str(exe), "200000"], capture_output=True, text=True)
            kb = lambda r: int(r.stderr.strip().splitlines()[-1])    # noqa: E731
            self.assertLess(kb(big), kb(small) + 4096, (kb(small), kb(big)))

    def test_str_returning_functions_cross_the_legacy_protocol(self):
        self.check('funcs', FUNCS, ['main', 'label', 'join3'], [(1,), (9,)])

    def test_switch_off_leaves_no_trace_of_the_s4a_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = {}
            for tag, mode in (('off', '0'), ('on', 'verify')):
                built, exe, _ = compile_program(tmp, 'textops', TEXTOPS, tag, {'AIL_IR': mode}, debug=True)
                self.assertEqual(built.returncode, 0, built.stderr)
                sources[tag] = Path(tmp, 'textops.%s.d' % tag, 'program.c').read_text()
        self.assertNotIn('ail_ir_char_at', sources['off'])
        self.assertIn('ail_ir_char_at', sources['on'])

    # ------------------------------------------------------------------ sanitizers
    def sanitize(self, name, source, args_list, stdin=b''):
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
                env_run = {'ASAN_OPTIONS': ASAN_DETECT_LEAKS + ':abort_on_error=0',
                           'UBSAN_OPTIONS': 'print_stacktrace=1:halt_on_error=1'}
                out[tag] = [run_with(san, args, stdin, env_run) for args in args_list]
        return out

    @unittest.skipUnless(shutil.which('gcc'), 'no gcc')
    def test_sanitizers_report_nothing_on_the_ir_builds(self):
        cases = [('prints', PRINTS, [(5,), (0,)], b''), ('argv', ARGV, [('a', 'b')], b''),
                 ('conv', CONV, [(7,)], b''), ('textops', TEXTOPS, [('abc', 'abd'), ('xé', 'zz')], b''),
                 ('stdinb', STDIN_BYTES, [()], b'abc\xc3\xa9def'), ('stdint', STDIN_TEXT, [()], b'a\nb\nc\nd\n'),
                 ('unused_e', UNUSED_E, [()], b''), ('mixed', MIXED, [('123', 20)], b''),
                 ('structs', STRUCTS, [(3,), (0,)], b''), ('loops', LOOPS, [(3000,)], b''),
                 ('funcs', FUNCS, [(9,)], b'')]
        for name, source, args_list, stdin in cases:
            with self.subTest(program=name):
                runs = self.sanitize(name, source, args_list, stdin)
                for tag in ('ir', 'ir-checked'):
                    for k, (status, stdout, stderr) in enumerate(runs[tag]):
                        err = stderr.decode(errors='replace')
                        self.assertNotIn('runtime error', err, (name, tag, k))
                        self.assertNotIn('AddressSanitizer', err, (name, tag, k, err[-600:]))
                        self.assertNotIn('LeakSanitizer', err.replace('LeakSanitizer is disabled', ''), (name, tag, k))
                        self.assertEqual((status, stdout), runs['legacy'][k][:2], (name, tag, k))


# --------------------------------------------------------------------------------------------
# Generated programs
# --------------------------------------------------------------------------------------------

class _TextGen(object):
    """Random text programs over the IR's text subset: strings built, sliced, compared, formatted, converted and
    printed from constants and argv. Locals (never parameters) are rebound; loops only print and count, so the
    legacy front end keeps no builder local and `go` is an IR function."""
    WORDS = ('a', 'bc', 'def', 'été', '日本', 'xyz', '', ' pad ', '007', '42', '-3')

    def __init__(self, seed):
        self.r = random.Random(seed)
        self.q = 0

    def k(self, lo, hi):
        return self.r.randint(lo, hi)

    def lit(self):
        return repr(self.r.choice(self.WORDS))

    def name(self):
        return self.r.choice(['s', 't', 'u'])

    def simple_int(self):
        return self.r.choice(['n', 'm', str(self.k(-20, 300)), 'len(%s)' % self.name()])

    def sx(self, depth=0):
        """A str expression over the names s, t, u (str) and n, m (int)."""
        c = self.k(0, 11 if depth < 2 else 3)
        if c == 0:
            return self.name()
        if c == 1:
            return self.lit()
        if c == 2:
            return 'str(%s)' % self.ix(depth + 1)
        if c == 3:
            return '(%s + %s)' % (self.sx(depth + 1), self.sx(depth + 1))
        if c == 4:
            return '%s[%s:%s]' % (self.name(), self.r.choice(['', '1', '-2', '0']), self.r.choice(['', '2', '-1', '3']))
        if c == 5:
            return '%s.strip()' % self.sx(depth + 1)
        if c == 6:
            return "f'{%s}-{%s}'" % (self.name(), self.simple_int())
        if c == 7:
            return "f'{%s:>6}|{%s:<4}|'" % (self.name(), self.name())
        if c == 8:
            return "f'{%s:05d}{%s}'" % (self.simple_int(), self.name())
        if c == 9:
            return "f'{%s:.2f}'" % self.fx(depth + 1)
        if c == 10:
            return '%s.lstrip(%s)' % (self.sx(depth + 1), self.lit())
        return '(%s if %s else %s)' % (self.sx(depth + 1), self.cond(depth + 1), self.sx(depth + 1))

    def ix(self, depth=0):
        c = self.k(0, 8 if depth < 2 else 3)
        if c == 0:
            return self.r.choice(['n', 'm'])
        if c == 1:
            return str(self.k(-20, 300))
        if c == 2:
            return 'len(%s)' % self.sx(depth + 1)
        if c == 3:
            return '(%s + %s)' % (self.ix(depth + 1), self.ix(depth + 1))
        if c == 4:
            return '(%s %% 11)' % self.ix(depth + 1)
        if c == 5:
            return 'ord(%s[0])' % self.name() if False else 'len(%s)' % self.name()
        if c == 6:
            return '(%s - %s)' % (self.ix(depth + 1), self.ix(depth + 1))
        if c == 7:
            return 'int(%s)' % self.r.choice(["'12'", "' -7 '", "'+5'", "'0'"])
        return '(%s * 3 // 2)' % self.ix(depth + 1)

    def fx(self, depth=0):
        c = self.k(0, 3)
        if c == 0:
            return 'float(%s)' % self.simple_int()
        if c == 1:
            return '(%s / 7)' % self.simple_int()
        if c == 2:
            return str(self.r.choice([0.5, 1.25, -3.75, 100.0]))
        return '(%s * 0.5)' % self.fx(depth + 1)

    def cond(self, depth=0):
        c = self.k(0, 8)
        if c == 0:
            return '%s == %s' % (self.sx(depth + 1), self.sx(depth + 1))
        if c == 1:
            return '%s < %s' % (self.sx(depth + 1), self.sx(depth + 1))
        if c == 2:
            return '%s in %s' % (self.lit(), self.sx(depth + 1))
        if c == 3:
            return '%s.startswith(%s)' % (self.sx(depth + 1), self.lit())
        if c == 4:
            return '%s > %s' % (self.ix(depth + 1), self.ix(depth + 1))
        if c == 5:
            return 'len(%s) != 0' % self.sx(depth + 1)
        if c == 6:
            return '%s != %s' % (self.sx(depth + 1), self.sx(depth + 1))
        if c == 7:
            return '%s.endswith(%s)' % (self.sx(depth + 1), self.lit())
        return '%s <= %s' % (self.sx(depth + 1), self.sx(depth + 1))

    def stmt(self):
        c = self.k(0, 9)
        if c == 0:
            return ['print(%s)' % self.sx()]
        if c == 1:
            return ['print(%s, %s)' % (self.ix(), self.sx())]
        if c == 2:
            return ['%s = %s' % (self.name(), self.sx())]
        if c == 3:
            return ['%s = %s' % (self.r.choice(['n', 'm']), self.ix())]
        if c == 4:
            return ['if %s:' % self.cond(), '    print(%s)' % self.sx(), 'else:', '    print(%s)' % self.ix()]
        if c == 5:
            self.q += 1
            return ['for i%d in range(%d):' % (self.q, self.k(0, 4)),
                    '    print(%s + str(i%d))' % (self.sx(), self.q),
                    '    n = n + len(%s)' % self.name()]
        if c == 6:
            return ['print(%s, sep=%s, end=%s)' % (self.sx(), self.lit(), repr(self.r.choice(['\n', '!\n'])))]
        if c == 7:
            return ['print(%s)' % self.fx()]
        if c == 8:
            return ['%s = %s + %s' % (self.name(), self.sx(), self.sx())]
        self.q += 1
        return ['for ch%d in %s:' % (self.q, self.sx()),
                '    if ch%d.isdigit():' % self.q, '        m += 1']

    def program(self):
        lines = ['import sys', '', '', 'def go(s0: str, t0: str, u0: str, n0: int, m0: int) -> int:',
                 '    s = s0', '    t = t0', '    u = u0', '    n = n0', '    m = m0']
        for _ in range(self.k(6, 14)):
            for line in self.stmt():
                lines.append('    ' + line)
        lines += ['    print(s, t, u, n, m)', '    return (n + m + len(s)) % 1000', '', '',
                  'def main():', '    a = sys.argv[1]', '    k = int(sys.argv[2])',
                  '    r = go(a, "x" + a, a[1:], k, k + 1)', '    print(r)', '    return 0', '', '',
                  'sys.exit(main())', '']
        return '\n'.join(lines)


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class GeneratedTests(unittest.TestCase):
    SEEDS = tuple(range(1, int(os.environ.get('AIL_IR_S4A_SEEDS', '8')) + 1))

    def test_generated_text_programs_agree_with_cpython_the_legacy_build_and_both_exception_modes(self):
        taken = 0
        with tempfile.TemporaryDirectory() as tmp:
            for seed in self.SEEDS:
                with self.subTest(seed=seed):
                    source = _TextGen(seed).program()
                    expected = cpython_with(tmp, 'g%d' % seed, source, ('Xyzé', 3))
                    if expected[0] != 0:
                        continue          # a program CPython itself rejects (a bad slice of an int, ...): not a test
                    built = Built(tmp, 'g%d' % seed, source)
                    args = ('Xyzé', 3)
                    runs = {tag: run_with(built.exe[tag], args) for tag in built.exe}
                    self.assertEqual(runs['ir'], runs['legacy'], source)
                    self.assertEqual(runs['ir'], runs['ir-checked'], source)
                    self.assertEqual(runs['ir'][1], expected[1], source)
                    self.assertEqual(runs['ir'][0], 0, source)
                    taken += 'go' in built.ir['ir']
        self.assertGreaterEqual(taken, len(self.SEEDS) * 2 // 3)


if __name__ == '__main__':
    unittest.main()
