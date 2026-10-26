"""Five differences from CPython 3.12 that the unified-IR study found (docs/design/UNIFIED_IR.md 5.3), fixed on branch bugs7.

1. range() near the int64 limits (DIFFERENCES C71). The general runtime found the end of a range by comparing
   `idx >= stop` and added the step to an int64, so `range(2**63-1, -(2**63-1), -3074457345618258602)` wrapped round
   and never ended; its len(), indexing and reversed() subtracted in int64 as well. They now count in uint64 (a range
   has up to 2**64 - 1 items) and walk by the count. A len() above int64 is the declared overflow (A1), as the typed
   path already had it. `reversed(range(...))` and `x in range(...)` were TypeErrors on the general path; built.
2. One def used both as `map(f, ...)` and `sorted(key=f)` emitted its `pkf_f` C wrapper twice (C72).
3. The typed path took `bin(n)`, `oct(n)`, `format(...)`, `ascii(...)` for ints, so `b: str = bin(n)` was refused as
   "assigning int" (C73). bin and oct are built like hex; format and ascii are str-valued and refused by name.
4. An int64 overflow ended a typed clone (mixed mode) with exit 1 and `integer overflow`, and the boxed code with exit 3
   and `AIL limit: int_overflow` (C74). With big ints a result that does not fit int64 now promotes, so the default
   (tint) build prints CPython's exact integer and exits 0; the boxed code does the same.
5. UnboundLocalError's text was the pre-3.11 wording (C75). It is CPython 3.12's, and a name read from an
   enclosing function is a NameError with the free-variable wording.

Every program is built by pyc.py under AIL_IR=1 and AIL_IR=0, once as the default build (typed path, mixed clones,
general fallback) and once with --general-only, and must print what CPython prints with CPython's exit status; where
AIL's int64 limit applies (CPython has big ints) the expected text and `exit 1, integer overflow` are written out.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = str(ROOT / 'python' / 'pkg-v12' / 'pyc.py')

MODES = (('default', False, '1'), ('default', False, '0'), ('general', True, '1'), ('general', True, '0'))


def _cpython(directory, name, text, stdin):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], input=stdin.encode(), capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, ir, general, env=None):
    src = Path(directory) / ('%s_%s_%d.py' % (name, ir, general))
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_%s_%s_%d' % (name, ir, general))
    full = dict(os.environ, AIL_SURFACE='python', AIL_IR=ir)
    full.pop('AIL_NO_MIX', None)
    full.pop('AIL_NO_GENERAL', None)
    full.update(env or {})
    cmd = [sys.executable, '-B', PYC, str(exe), '--file', str(src)] + (['--general-only'] if general else [])
    return exe, subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=full)


class Bugs7(unittest.TestCase):
    def check(self, name, text, stdins=('',), want=None, mixed=None, stop=None, modes=MODES):
        """Build `text` in every mode; each stdin must give CPython's stdout and exit status (or `want[stdin]`, a
        (stdout, status) pair, where AIL's int64 limit ends the program and CPython has a big integer). `stop`:
        stdins whose run must end with exit 1 and no `AIL limit` line. `mixed`: True when the default build has to
        carry a typed clone, False when the general build must not."""
        want = dict(want or {})
        with tempfile.TemporaryDirectory(prefix='ail-bugs7-') as directory:
            for stdin in stdins:
                if stdin not in want:
                    want[stdin] = _cpython(directory, name, text, stdin)
            for mode, general, ir in modes:
                exe, built = build(directory, name, text, ir, general)
                with self.subTest(program=name, mode=mode, ir=ir, step='build'):
                    self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-1500:])
                if built.returncode:
                    continue
                if mixed is not None and not general:
                    clones = list(Path(directory).glob('exe_%s_%s_0_mix*.c' % (name, ir)))
                    with self.subTest(program=name, mode=mode, ir=ir, step='clone'):
                        self.assertEqual(bool(clones), mixed, 'typed clone attached: %r' % clones)
                for stdin in stdins:
                    with self.subTest(program=name, mode=mode, ir=ir, stdin=stdin):
                        try:
                            got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=30,
                                                 cwd=directory)
                        except subprocess.TimeoutExpired:
                            self.fail('did not end')
                        err = got.stderr.decode('utf-8', 'replace')
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[stdin][0], err[-300:])
                        self.assertEqual(got.returncode, want[stdin][1], err[-300:])
                        if stop and stdin in stop:
                            self.assertEqual(got.returncode, 1, err)
                            self.assertNotIn('AIL limit', err)
        return want

    # ---- 1. range near the int64 limits -----------------------------------------------------------------------

    def test_range_limits(self):
        loops = {
            'bug_report': 'print(show(M, -M, -3074457345618258602))',
            'up_step': 'print(show(-M, M, 3074457345618258602))',
            'min_to_max': 'print(show(N, M, M))',
            'max_to_min': 'print(show(M, N, N))',
            'down_one': 'print(show(M, M - 3, -1))',
            'up_one': 'print(show(N, N + 3, 1))',
            'up_to_max': 'print(show(M - 3, M, 1))',
            'down_to_min': 'print(show(N + 2, N, -1))',
            'empty': 'print(show(M, M, 1), show(0, N, 1), show(N, 0, -1), show(0, 5, -1))',
            'one_item_up': 'print(show(0, M, M), show(M - 1, M, M))',
            'one_item_down': 'print(show(0, N, N), show(1, N, N))',
            'lens': 'print(lens(M - 5, M, 1), lens(N, N + 5, 1), lens(0, M, M), lens(N + 1, 0, 1), lens(M, 0, -1))',
            'lens_steps': 'print(lens(-M, M, 3074457345618258602), lens(M, -M, -3074457345618258602), lens(N, M, M))',
            'at': 'print(at(0, M, M, 0), at(0, M, M, -1), at(M - 2, M, 1, 1), at(N, N + 3, 1, -1), at(M, N, -M, 2), '
                  'at(M, N, -M, -1))',
            'at_wide': 'print(at(N, M, 1, 0), at(N, M, 1, -1), at(N, M, 1, M), at(N, M, 1, -M))',
            'at_wide_steps': 'print(at(N, M, M, 1), at(N, M, M, -1), at(M, N, N, 1), at(M, N, N, -1))',
        }
        # CPython: len() above sys.maxsize is an OverflowError, an index outside is an IndexError (both exit 1)
        stops = {
            'len_min_to_max': 'print(lens(N, M, 1))',
            'len_max_to_min': 'print(lens(M, N, -1))',
            'len_wide': 'print(lens(-M, M, 1))',
            'len_2_63': 'print(lens(N, 0, 1))',
            'at_past_end': 'print(at(0, 5, 1, 5))',
            'at_before_start': 'print(at(0, 5, 1, -6))',
            'at_far': 'print(at(M - 3, M, 1, M))',
        }
        names = list(loops) + list(stops)
        body = ''.join('    %s k == %d:\n        %s\n' % ('if' if i == 0 else 'elif', i, stmt)
                       for i, stmt in enumerate(list(loops.values()) + list(stops.values())))
        text = RANGE_HEAD + body + '\nmain()\n'
        self.check('range_limits', text, stdins=tuple('%d\n' % i for i in range(len(names))),
                   stop=tuple('%d\n' % i for i in range(len(loops), len(names))))

    def test_range_views(self):
        """reversed(range) and `x in range` (the typed path does not build them: both builds run the general path)."""
        cases = {
            'rev_up': 'rev(N, N + 3, 1); rev(M - 2, M, 1); rev(0, M, M); rev(N, M, M)',
            'rev_down': 'rev(M, N, -M); rev(M, N, N); rev(5, 0, 1); rev(0, 0, 1); rev(3, 10, 3)',
            'rev_steps': 'rev(-M, M, 3074457345618258602); rev(M, -M, -3074457345618258602)',
            'member': 'print(member(0, 5, 1, 3), member(0, 5, 1, 5), member(M - 3, M, 1, M - 1), '
                      'member(M - 3, M, 1, M), member(N, N + 3, 1, N + 2), member(M, N, N, -1), member(M, N, N, 0))',
            'member_steps': 'print(member(N, M, 3, N + 3), member(N, M, 3, N + 4), member(M, 0, -2, M - 4), '
                            'member(M, 0, -2, M - 3), member(0, 10, 2, 4), member(0, 10, 2, 5), member(10, 0, -3, 1))',
            'member_kinds': 'print(3 in range(5), 3.0 in range(5), 3.5 in range(5), True in range(5), "x" in range(5), '
                            'None in range(5), 1e30 in range(5), (-5) in range(-10, 0, 5))',
        }
        body = ''.join('    %s k == %d:\n        %s\n' % ('if' if i == 0 else 'elif', i, stmt)
                       for i, stmt in enumerate(cases.values()))
        text = RANGE_VIEW_HEAD + body + '\nmain()\n'
        self.check('range_views', text, stdins=tuple('%d\n' % i for i in range(len(cases))))

    # ---- 2. one def as map() function and sorted() key ---------------------------------------------------------

    def test_key_function_used_twice(self):
        self.check('pkf_twice', KEY_TWICE)

    # ---- 3. bin / oct / hex / format / repr / chr on the typed path --------------------------------------------

    def test_str_builtins(self):
        self.check('str_builtins', STR_BUILTINS)
        self.check('repr_builtins', REPR_BUILTINS)

    def test_typed_path_builds_bin_oct(self):
        """AIL_NO_GENERAL=1 asks the typed path alone: bin and oct are built; format and ascii are refused by name,
        not as an int assigned to a str."""
        with tempfile.TemporaryDirectory(prefix='ail-bugs7-') as directory:
            for ir in ('1', '0'):
                exe, built = build(directory, 'typed_radix', STR_BUILTINS, ir, False, {'AIL_NO_GENERAL': '1'})
                self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-1500:])
                got = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=directory)
                want, _ = _cpython(directory, 'typed_radix', STR_BUILTINS, '')
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want)
            for call in ('format(n, "x")', 'format(n, ">4")'):
                text = 'def f(n: int) -> int:\n    b: str = %s\n    return len(b)\n\nprint(f(10))\n' % call
                exe, built = build(directory, 'typed_refused', text, '1', False, {'AIL_NO_GENERAL': '1'})
                self.assertNotEqual(built.returncode, 0)
                self.assertIn('call to %s()' % call.split('(')[0], built.stderr)
                self.assertNotIn('assigning int', built.stderr)
                # the default build falls back to the general path and prints CPython's text
                self.check('str_valued_%d' % len(call), text, modes=MODES[:2])

    # ---- 4. an int64 overflow ends the program the same way with or without a typed clone ---------------------

    def test_overflow_ends_alike(self):
        grow = 'def grow(n: int) -> int:\n    x = 1\n    for i in range(n):\n        x = x * 3\n    return x\n\n'
        clone_overflows = grow + '''def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(grow(10))
    print(grow(100))
    print("never")
main()
'''
        boxed_overflows = grow + '''def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(grow(10))
    y = 3
    for i in range(100):
        y = y * 3
        if i > 30:
            print(y)
    print("never")
main()
'''
        in_try = grow + '''def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    try:
        try:
            print(grow(10))
            y = 3
            for i in range(100):
                y = y * 3
            print("never")
        finally:
            print("finally")
    except Exception:
        print("except")
main()
'''
        with tempfile.TemporaryDirectory(prefix='ail-bugs7-') as directory:
            clone_exact = _cpython(directory, 'overflow_clone', clone_overflows, '')[0]
            boxed_exact = _cpython(directory, 'overflow_boxed', boxed_overflows, '')[0]
            try_exact = _cpython(directory, 'overflow_in_try', in_try, '')[0]
        # the default build's clone promotes through the boxed body (fix10 restores the clone); the general
        # build promotes directly: CPython's exact big int and exit 0 in both
        self.check('overflow_clone', clone_overflows, want={'': (clone_exact, 0)}, mixed=True)
        self.check('overflow_boxed', boxed_overflows, want={'': (boxed_exact, 0)}, mixed=True)
        self.check('overflow_in_try', in_try, want={'': (try_exact, 0)}, mixed=True)

    def test_overflow_text(self):
        """The tint/default build promotes a value beyond int64: CPython's exact text and exit 0, never `integer overflow`.
        The legacy emitter (AIL_IR=0) has no tint lowering and keeps its old loud int64 stop."""
        text = 'def main():\n    d = {"k": 1}\n    x = 3\n    for i in range(100):\n        x = x * 3\n    print(x)\nmain()\n'
        with tempfile.TemporaryDirectory(prefix='ail-bugs7-') as directory:
            exact = _cpython(directory, 'overflow_text', text, '')[0]
            for mode, general, ir in MODES:
                exe, built = build(directory, 'overflow_text', text, ir, general)
                self.assertEqual(built.returncode, 0, built.stderr[-1500:])
                got = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=directory)
                with self.subTest(mode=mode, ir=ir):
                    if not general and ir == '0':
                        # the legacy emitter has no tint: the typed int64 still stops loudly
                        self.assertEqual(got.returncode, 1, got.stderr)
                        self.assertEqual(got.stderr.decode().strip(), 'integer overflow')
                    else:
                        self.assertEqual(got.returncode, 0, got.stderr)
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), exact)
                        self.assertNotIn(b'integer overflow', got.stderr)

    # ---- 5. UnboundLocalError's wording -------------------------------------------------------------------------

    def test_unbound_local_message(self):
        self.check('unbound', UNBOUND)

    def test_unbound_uncaught(self):
        text = 'def f(a):\n    if a > 0:\n        z = {"k": a}\n    return z\n\nprint(f(1)["k"])\nprint(f(0))\n'
        with tempfile.TemporaryDirectory(prefix='ail-bugs7-') as directory:
            for mode, general, ir in MODES:
                exe, built = build(directory, 'unbound_uncaught', text, ir, general)
                self.assertEqual(built.returncode, 0, built.stderr[-1500:])
                got = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=directory)
                with self.subTest(mode=mode, ir=ir):
                    self.assertEqual(got.returncode, 1)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), b'1\n')
                    self.assertEqual(got.stderr.decode().strip().splitlines()[-1],
                                     "UnboundLocalError: cannot access local variable 'z' where it is not "
                                     "associated with a value")


RANGE_HEAD = '''M = 9223372036854775807
N = -9223372036854775807 - 1

def show(a: int, b: int, s: int) -> int:
    n = 0
    for i in range(a, b, s):
        print(i)
        n += 1
    return n

def lens(a: int, b: int, s: int) -> int:
    return len(range(a, b, s))

def at(a: int, b: int, s: int, i: int) -> int:
    return range(a, b, s)[i]

def main():
    k = int(input())
'''

RANGE_VIEW_HEAD = '''M = 9223372036854775807
N = -9223372036854775807 - 1

def rev(a: int, b: int, s: int) -> int:
    n = 0
    for v in reversed(range(a, b, s)):
        print(v)
        n += 1
    return n

def member(a: int, b: int, s: int, x: int) -> bool:
    return x in range(a, b, s)

def main():
    k = int(input())
'''

KEY_TWICE = '''def poly(x):
    return x * x - 4 * x

def neg(x):
    return -x

def main():
    xs = [3, 1, 2, 7, -5]
    print(list(map(poly, xs)))
    print(sorted(xs, key=poly))
    print(sorted(xs, key=poly, reverse=True))
    print(max(xs, key=poly), min(xs, key=poly))
    print(list(map(neg, xs)), sorted(xs, key=neg))
    print(list(filter(poly, [0, 4, 5])))
    ws = ["bb", "a", "ccc"]
    print(sorted(ws, key=len), list(map(len, ws)), sorted(ws, key=len, reverse=True))
main()
'''

STR_BUILTINS = '''def conv(n: int) -> int:
    b: str = bin(n)
    h: str = hex(n)
    o: str = oct(n)
    r: str = repr(n)
    c: str = chr(65 + n % 26)
    print(b, h, o, r, c)
    print(len(bin(n)), len(hex(n)), len(oct(n)), len(repr(n)), len(chr(66)))
    print(bin(n) + "!", hex(n)[2:], oct(n)[1:], repr(n) + "?", chr(67) * 2)
    print(bin(-n), hex(-n), oct(-n), repr(-n))
    return len(b)

def main():
    print(conv(10))
    print(conv(255))
    print(conv(0))
    print(conv(9223372036854775807))
    print(conv(-9223372036854775807))
    print(conv(1))
    print(bin(-9223372036854775807 - 1), hex(-9223372036854775807 - 1), oct(-9223372036854775807 - 1))
    print(sorted([bin(i) for i in range(5)]))
main()
'''

REPR_BUILTINS = '''def f(n: int) -> int:
    a: str = repr("ab")
    b: str = repr(1.5)
    c: str = repr(n)
    d: str = repr(True)
    print(a, b, c, d)
    print(len(repr("it's")), repr('say "hi"'), repr("tab\\t"))
    return len(a) + len(b) + len(c)

def main():
    print(f(12))
    print(f(-7))
main()
'''

# (`z` holds a dict: the typed path takes this too since DIFFERENCES C76, see test_ail_unbound)
UNBOUND = '''def f(a):
    if a > 0:
        z = {"k": a}
    return z

def g(n):
    try:
        return f(n)
    except UnboundLocalError as e:
        print("caught", e)
        print(repr(e), type(e).__name__, e.args)
    return -1

def h(n):
    def inner():
        return q + 1
    if n:
        q = 5
    try:
        return inner()
    except NameError as e:
        print("free", e, type(e).__name__, isinstance(e, UnboundLocalError))
    return -2

def k():
    x = 1
    del x
    try:
        print(x)
    except UnboundLocalError as e:
        print(e)

print(g(1))
print(g(0))
print(h(0))
print(h(1))
k()
'''


if __name__ == '__main__':
    unittest.main()
