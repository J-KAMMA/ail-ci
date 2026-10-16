"""Parallel assignment of owned values, block-scoped loop/except names, and refusal locations.

`cur, nxt = nxt, cur` on two lists bound both names to one buffer and freed it twice (exit 134).
A permutation of plain locals now moves the C values round with no copy; any other parallel
assignment (`a, b = b, a + b`, struct fields, mixed local/field) goes through hidden locals with
the ordinary one-name assignment, so ownership moves exactly once. Checked against CPython for
lists of int/float/str/bytes/struct, bytes, str, dicts, sets, structs, fields, rotations and loops,
and (when gcc has the sanitizers) under ASan+UBSan with leak detection. An unannotated
`[0 for i in range(n)]` that is later swapped is a list, not the int the pre-pass used to guess.

A loop variable reused with another kind in a later loop, and an `except ... as e` reusing an
existing name, are renamed per region when no read can observe the difference; otherwise the
refusal points at the loop or handler and says what to rename. Refusals raised outside a statement
still start with file:line, `str(bytes)` names `b.decode()` in a short message, and a refusal far
from any sort no longer carries the "with key= columns" prefix.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SWAPS = """
struct P { x: int; name: str; xs: list[int]; }
struct S { a: list[int]; b: list[int]; n: int; m: int; }
fn show(xs: list[int]) -> str { return ",".join([str(v) for v in xs]); }
fn showf(xs: list[float]) -> str { return ",".join([str(v) for v in xs]); }
fn evolve(n: int) -> int {
    let cur = [0 for i in range(n)];
    let nxt = [0 for i in range(n)];
    for g in range(5) {
        for x in range(n) { nxt[x] = cur[x] + x; }
        cur, nxt = nxt, cur;
    }
    let tmp = cur; cur = nxt; nxt = tmp;
    return cur[n - 1] + nxt[1];
}
fn main() {
    print(evolve(6));
    let a: list[int] = [1, 2, 3];
    let b = [4, 5];
    let c: list[int] = [6];
    for g in range(4) { a, b = b, a; a.append(g); a, b, c = b, c, a; }
    print(show(a), show(b), show(c));
    let fa: list[float] = [1.5];
    let fb: list[float] = [2.5, 3.5];
    for g in range(3) { fa, fb = fb, fa; fa.append(0.25); }
    print(showf(fa), showf(fb));
    let sa: list[str] = ["x", "y"];
    let sb: list[str] = ["z"];
    for g in range(3) { sa, sb = sb, sa; sa.append("w" + str(g)); }
    print(",".join(sa), ",".join(sb));
    let ba: list[bytes] = [b"p"];
    let bb: list[bytes] = [b"q", b"r"];
    for g in range(3) { ba, bb = bb, ba; ba.append(b"s"); }
    print(len(ba), len(bb), ba[0].decode(), bb[0].decode());
    let x = b"hi";
    let y = b"yo";
    for g in range(3) { x, y = y, x + b"!"; }
    print(x.decode(), y.decode());
    let s = "s";
    let t = "t";
    for g in range(3) { s, t = t, s + str(g); }
    print(s, t);
    let d: dict[str, int] = {"k": 1};
    let e: dict[str, int] = {};
    let di: dict[int, int] = {1: 2};
    let dj: dict[int, int] = {};
    let st: set[int] = {1, 2};
    let su: set[int] = set();
    for g in range(3) { d, e = e, d; d["n" + str(g)] = g; di, dj = dj, di; di[g] = g; st, su = su, st; st.add(10 + g); }
    print(len(d), len(e), d["n2"], len(di), len(dj), len(st), len(su));
    let p = P(1, "a", [1]);
    let q = P(2, "b", [2, 3]);
    let ps: list[P] = [p];
    let qs: list[P] = [q, p];
    for g in range(3) { p, q = q, p; p.xs.append(g); ps, qs = qs, ps; ps.append(P(g, "c", [])); }
    print(p.x, p.name, show(p.xs), q.x, show(q.xs), len(ps), len(qs), ps[0].x);
    let fib0: list[int] = [0];
    let fib1: list[int] = [1];
    for g in range(4) { fib0, fib1 = fib1, fib0 + fib1; }
    print(show(fib0), show(fib1));
    let w = S([1], [2, 3], 1, 2);
    for g in range(3) { w.a, w.b = w.b, w.a; w.a.append(g); }
    w.n, w.m = w.m, w.n;
    let loose: list[int] = [7];
    loose, w.a = w.a, loose;
    print(show(w.a), show(w.b), w.n, w.m, show(loose));
    let m = 0;
    let k = 1;
    for i in range(10) { m, k = k, m + k; }
    v, z = [i * i for i in range(4)], "z";
    print(m, k, show(v), z);
}
"""

SWAPS_PY = """
class P:
    def __init__(self, x, name, xs): self.x, self.name, self.xs = x, name, xs
class S:
    def __init__(self, a, b, n, m): self.a, self.b, self.n, self.m = a, b, n, m
def show(xs): return ",".join(str(v) for v in xs)
def evolve(n):
    cur = [0 for i in range(n)]; nxt = [0 for i in range(n)]
    for g in range(5):
        for x in range(n): nxt[x] = cur[x] + x
        cur, nxt = nxt, cur
    tmp = cur; cur = nxt; nxt = tmp
    return cur[n - 1] + nxt[1]
print(evolve(6))
a = [1, 2, 3]; b = [4, 5]; c = [6]
for g in range(4):
    a, b = b, a; a.append(g); a, b, c = b, c, a
print(show(a), show(b), show(c))
fa = [1.5]; fb = [2.5, 3.5]
for g in range(3):
    fa, fb = fb, fa; fa.append(0.25)
print(show(fa), show(fb))
sa = ["x", "y"]; sb = ["z"]
for g in range(3):
    sa, sb = sb, sa; sa.append("w" + str(g))
print(",".join(sa), ",".join(sb))
ba = [b"p"]; bb = [b"q", b"r"]
for g in range(3):
    ba, bb = bb, ba; ba.append(b"s")
print(len(ba), len(bb), ba[0].decode(), bb[0].decode())
x = b"hi"; y = b"yo"
for g in range(3):
    x, y = y, x + b"!"
print(x.decode(), y.decode())
s = "s"; t = "t"
for g in range(3):
    s, t = t, s + str(g)
print(s, t)
d = {"k": 1}; e = {}; di = {1: 2}; dj = {}; st = {1, 2}; su = set()
for g in range(3):
    d, e = e, d; d["n" + str(g)] = g; di, dj = dj, di; di[g] = g; st, su = su, st; st.add(10 + g)
print(len(d), len(e), d["n2"], len(di), len(dj), len(st), len(su))
p = P(1, "a", [1]); q = P(2, "b", [2, 3]); ps = [p]; qs = [q, p]
for g in range(3):
    p, q = q, p; p.xs.append(g); ps, qs = qs, ps; ps.append(P(g, "c", []))
print(p.x, p.name, show(p.xs), q.x, show(q.xs), len(ps), len(qs), ps[0].x)
fib0 = [0]; fib1 = [1]
for g in range(4):
    fib0, fib1 = fib1, fib0 + fib1
print(show(fib0), show(fib1))
w = S([1], [2, 3], 1, 2)
for g in range(3):
    w.a, w.b = w.b, w.a; w.a.append(g)
w.n, w.m = w.m, w.n
loose = [7]
loose, w.a = w.a, loose
print(show(w.a), show(w.b), w.n, w.m, show(loose))
m = 0; k = 1
for i in range(10):
    m, k = k, m + k
v, z = [i * i for i in range(4)], "z"
print(m, k, show(v), z)
"""

TRY_SWAP = """
fn main() {
    let a: list[int] = [1, 2];
    let b = [5];
    let d: dict[str, int] = {"x": 1};
    let e: dict[str, int] = {};
    for g in range(3) {
        try {
            a, b = b, a;
            d, e = e, d;
            a.append(int("7") + g);
            if g == 1 { let z = int("q"); print(z); }
        } except ValueError as err {
            print("bad", g);
        }
    }
    print(len(a), len(b), a[0], len(d), len(e));
}
"""

TRY_SWAP_PY = """
a = [1, 2]; b = [5]; d = {"x": 1}; e = {}
for g in range(3):
    try:
        a, b = b, a
        d, e = e, d
        a.append(int("7") + g)
        if g == 1:
            z = int("q"); print(z)
    except ValueError as err:
        print("bad", g)
print(len(a), len(b), a[0], len(d), len(e))
"""

REBIND = """
fn count(e: int) -> int {
    try { let v = int("x"); return v; } except ValueError as e { print("handler"); }
    return 0;
}
fn main() {
    let nums = [3, 1, 2];
    let words = "a bb ccc".split();
    let total = 0;
    for x in nums { total += x; }
    for x in words { print(x, len(x)); }
    for i in range(2) { print(i); }
    for i in words { print(i + "!"); }
    let fl = [0.5, 1.5];
    for x in fl { print(x * 2.0); }
    let e = 5;
    for e2 in nums { e = e + e2; }
    print(e, total, count(4));
    try { let y = int("q"); print(y); } except ValueError as e { print("bad"); }
    e = 3;
    print(e);
}
"""

REBIND_PY = """
def count(e):
    try:
        v = int("x"); return v
    except ValueError as e:
        print("handler")
    return 0
nums = [3, 1, 2]
words = "a bb ccc".split()
total = 0
for x in nums: total += x
for x in words: print(x, len(x))
for i in range(2): print(i)
for i in words: print(i + "!")
fl = [0.5, 1.5]
for x in fl: print(x * 2.0)
e = 5
for e2 in nums: e = e + e2
print(e, total, count(4))
try:
    y = int("q"); print(y)
except ValueError as e:
    print("bad")
e = 3
print(e)
"""

# (source, location line, words the refusal must contain)
REFUSED = [
    # Python unbinds `e` after the handler, so the later read would fail there
    ('fn main() {\n    let e = 5;\n    try { let x = int("q"); print(x); } except ValueError as e { print(1); }\n'
     '    print(e);\n}\n', 3, ['print(e)', 'after this handler', 'as e2']),
    # Python keeps the second loop's last value in `x`; the first loop has to be renamed
    ('fn main() {\n    let w = "a b".split();\n    for x in [1, 2] { print(x); }\n'
     '    for x in w { print(x); }\n    print(x);\n}\n', 3, ['print(x)', 'after this loop', 'for x2 in']),
    ('fn main() {\n    let b = b"ab";\n    print(str(b));\n}\n', 3, ['b.decode()']),
    ('fn main() {\n    let a: dict[str, int] = {"k": 1};\n    let b: dict[str, int] = {};\n'
     '    a, b = b, {"z": 2};\n}\n', 4, ['swap or rotate']),
]


def build(directory, text, name='p'):
    source, exe, debug = Path(directory, name + '.ail'), Path(directory, name), Path(directory, name + '-debug')
    source.write_text(text)
    built = subprocess.run([sys.executable, str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
                            '-o', str(exe), '--debug-dir', str(debug)],
                           capture_output=True, text=True, timeout=300)
    return built, exe, debug / 'program.c'


def python(directory, text):
    oracle = Path(directory, 'oracle.py')
    oracle.write_text(text)
    ran = subprocess.run([sys.executable, str(oracle)], capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0, ran.stderr
    return ran.stdout


def sanitized(directory, c_file):
    """Run the generated C under ASan+UBSan with leak checks; None when gcc lacks them."""
    gcc = shutil.which('gcc')
    if gcc is None:
        return None
    exe = Path(directory, c_file.parent.name + '-asan')
    made = subprocess.run([gcc, '-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                           '-w', str(c_file), '-o', str(exe), '-lm', '-lpthread'],
                          capture_output=True, text=True, timeout=300)
    if made.returncode:
        return None
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                          env={'ASAN_OPTIONS': 'detect_leaks=1',
                               'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})


class SwapTests(unittest.TestCase):
    def check_program(self, text, oracle, name):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, text, name)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, python(directory, oracle))
            checked = sanitized(directory, c_file)
            if checked is not None:
                self.assertEqual(checked.returncode, 0, checked.stderr[-3000:])
                self.assertNotIn('ERROR:', checked.stderr)
                self.assertNotIn('runtime error', checked.stderr)
                self.assertEqual(checked.stdout, ran.stdout)
            return c_file.read_text()

    def test_parallel_assignment_of_owned_values_matches_cpython(self):
        program = self.check_program(SWAPS, SWAPS_PY, 'swaps')
        # a swap of two plain lists is a move: no element copy, no extra list
        self.assertIn('__typeof__(v_nxt) _ail_sw0 = v_nxt;', program)
        self.assertIn('v_cur = _ail_sw0;', program)

    def test_swaps_inside_try(self):
        self.check_program(TRY_SWAP, TRY_SWAP_PY, 'tryswap')

    def test_loop_and_except_names_are_block_scoped(self):
        self.check_program(REBIND, REBIND_PY, 'rebind')

    def test_refusals_name_the_line_and_the_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, (text, line, words) in enumerate(REFUSED):
                with self.subTest(text=text):
                    built, exe, _ = build(directory, text, name='n%d' % index)
                    self.assertNotEqual(built.returncode, 0)
                    self.assertFalse(exe.exists())
                    message = (built.stdout + built.stderr).strip().splitlines()[-1]
                    self.assertRegex(message, r'n%d\.ail:%d:\d+: ' % (index, line))
                    for word in words:
                        self.assertIn(word, message)
                    self.assertLess(len(message), 400, message)

    def test_unrelated_refusal_carries_no_sort_prefix(self):
        text = ('fn main() {\n    let tot = [3, 1, 2];\n    let nm = ["a", "b", "c"];\n'
                '    let o: list[int] = [0, 1, 2];\n    o.sort(key=lambda i: (-tot[i], nm[i]));\n'
                '    let b = b"xy";\n    print(o[0], str(b));\n}\n')
        with tempfile.TemporaryDirectory() as directory:
            built, _, _ = build(directory, text)
            message = built.stdout + built.stderr
            self.assertIn('b.decode()', message)
            self.assertNotIn('with key= columns', message)
            self.assertRegex(message, r'p\.ail:7:\d+: ')

    def typed_build(self, directory, text):
        source, exe = Path(directory, 'q.ail'), Path(directory, 'q')
        source.write_text(text)
        env = dict(os.environ, AIL_NO_GENERAL='1')    # the typed path alone, not the fallback
        built = subprocess.run([sys.executable, str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
                                '-o', str(exe)], capture_output=True, text=True, timeout=300, env=env)
        return built, exe

    def test_scalar_parameter_rebinding_is_a_local_copy(self):
        text = ('def steps(n: int) -> int:\n    s: int = 0\n    while n != 1:\n'
                '        if n % 2 == 0:\n            n = n // 2\n        else:\n            n = 3 * n + 1\n'
                '        s += 1\n    return s\n\n'
                'def grow(n: int, rate: float = 1.5, up: bool = True) -> float:\n'
                '    """doc"""\n    for i in range(3):\n        n += i\n    rate = rate * 2.0\n'
                '    if up:\n        up = False\n    return n * rate + (1 if up else 0)\n\n'
                'v = 7\nprint(steps(v), v, steps(27), grow(v), grow(2, up=False), grow(n=1, rate=0.5))\n')
        with tempfile.TemporaryDirectory() as directory:
            expected = python(directory, text)
            built, exe = self.typed_build(directory, text)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.stdout, expected)

    def test_container_parameter_rebinding_stays_refused_on_the_typed_path(self):
        text = 'def f(xs: list[int]) -> int:\n    xs = [1, 2]\n    return len(xs)\n\nprint(f([9]))\n'
        with tempfile.TemporaryDirectory() as directory:
            built, _ = self.typed_build(directory, text)
            self.assertNotEqual(built.returncode, 0)
            self.assertIn("'xs' is a", built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()
