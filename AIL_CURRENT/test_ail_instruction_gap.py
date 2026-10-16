"""Instruction-count fixes found by comparing AIL against Nim/C on LLM-written benchmark programs.

Each class guards one change and runs the compiled program against CPython (or the same program
built the old way), so a faster path can never answer differently:

  * GuardedLoops   an innermost `for i in range(..)` / `while lo < hi` over plain int lists tests the
                   range once at loop entry and runs the same loop without per-access bounds
                   checks; the original loop is kept for when the test fails (negative index wrap,
                   an index past the end, a list shorter than the loop expects);
  * ObjectPool     struct objects come from size-class free lists, not malloc/free (binary_trees
                   spent half its instructions there); `-DAIL_NO_OBJ_POOL` goes back to malloc and
                   must print the same;
  * ShiftByLiteral `x << 2` is one range check, with the same overflow answer as ck_shl;
  * AppendOfCall   `out.append(f(c))` needs no retain/release of `out` around the call.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
# The C-text assertions below describe the legacy emitter; with AIL_IR set, functions in the IR's
# subset are emitted by the IR (same behaviour, different text), so only the behaviour is checked.
LEGACY_C = os.environ.get('AIL_IR', '0').strip().lower() in ('', '0', 'off', 'no')

ROOT = Path(__file__).resolve().parent


def build(source, directory, name='p', extra=()):
    src, exe, debug = Path(directory, name + '.ail'), Path(directory, name), Path(directory, name + '.d')
    src.write_text(source)
    built = subprocess.run([sys.executable, str(ROOT / 'ail_chatgpt.py'), 'compile', str(src), '-o', str(exe),
                            '--debug-dir', str(debug), *extra], capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    return exe, (debug / 'program.c').read_text()


def function_body(program, name):
    start = re.search(r'^[^\n;]*\b%s\([^\n;]*\) \{$' % re.escape(name), program, re.M)
    assert start, name
    return program[start.start():program.index('\n}\n', start.start())]


def run(exe, *args, stdin=None):
    return subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True, timeout=60,
                          input=stdin)


GUARDED = """
fn flip(n: int, k: int) -> int {
    let p = [0] * 8;
    for i in range(0, n) { p[i] = i * 3 + 1; }
    let lo = 0;
    let hi = k;
    while lo < hi {
        let t = p[lo];
        p[lo] = p[hi];
        p[hi] = t;
        lo += 1;
        hi -= 1;
    }
    let s = 0;
    for i in range(0, n) { s = (s * 7 + p[i]) % 100003; }
    return s;
}

fn shifted(n: int) -> int {
    let a = [0] * 8;
    for i in range(0, 8) { a[i] = i + n; }
    for i in range(0, 7) { a[i] = a[i + 1] * 2 - a[i]; }
    for i in range(1, 8) { a[i] = a[i] + a[i - 1]; }
    let t = 0;
    for i in range(0, 8) { t += a[i] * (i + 1); }
    return t;
}

fn wrapped(lo: int, hi: int) -> int {
    let a = [0] * 8;
    for i in range(0, 8) { a[i] = i * i; }
    let s = 0;
    for i in range(lo, hi) { s += a[i] * 3 + a[i + 1]; }
    return s;
}

fn stepped(k: int) -> int {
    let a = [0] * 9;
    for i in range(0, 9) { a[i] = i + 1; }
    let lo = 0;
    let hi = k;
    let s = 0;
    while lo < hi {
        s += a[lo] * 10 + a[hi];
        lo += 2;
        hi -= 3;
    }
    return s;
}

fn skippy(n: int) -> int {
    let a = [0] * 6;
    for i in range(0, 6) { a[i] = i + 2; }
    let s = 0;
    for i in range(0, n) {
        if a[i] == 5 { continue; }
        if a[i] > 6 { break; }
        s += a[i];
    }
    return s;
}

fn growing(n: int) -> int {
    let xs: list[int] = [];
    let s = 0;
    for i in range(0, n) {
        xs.append(i * 2);
        s += xs[i];
    }
    return s;
}

fn twice(n: int) -> int {
    let a = [0] * 6;
    let lo = 0;
    let hi = n;
    let s = 0;
    while lo < hi {
        lo += 1;
        s += a[lo];
        lo += 1;
    }
    return s;
}

fn show(label: str, v: int) -> void {
    print(label + " " + str(v));
}

fn main() {
    show("flip", flip(8, 7));
    show("flip", flip(5, 4));
    show("flip", flip(8, 0));
    show("shifted", shifted(3));
    show("wrapped", wrapped(0, 7));
    show("wrapped", wrapped(-3, 5));
    show("wrapped", wrapped(-2, 0));
    show("stepped", stepped(8));
    show("stepped", stepped(5));
    show("skippy", skippy(6));
    show("growing", growing(20));
    show("twice", twice(5));
    try { show("flip", flip(9, 2)); } except IndexError { print("flip n=9: index error"); }
    try { show("flip", flip(8, 8)); } except IndexError { print("flip hi=8: index error"); }
    try { show("wrapped", wrapped(0, 8)); } except IndexError { print("wrapped 8: index error"); }
    try { show("wrapped", wrapped(-9, 0)); } except IndexError { print("wrapped -9: index error"); }
    try { show("skippy", skippy(7)); } except IndexError { print("skippy 7: index error"); }
    try { show("stepped", stepped(12)); } except IndexError { print("stepped 12: index error"); }
    try { show("twice", twice(7)); } except IndexError { print("twice 7: index error"); }
}
"""

GUARDED_PY = """
def flip(n, k):
    p = [0] * 8
    for i in range(0, n): p[i] = i * 3 + 1
    lo = 0; hi = k
    while lo < hi:
        t = p[lo]; p[lo] = p[hi]; p[hi] = t
        lo += 1; hi -= 1
    s = 0
    for i in range(0, n): s = (s * 7 + p[i]) % 100003
    return s

def shifted(n):
    a = [0] * 8
    for i in range(0, 8): a[i] = i + n
    for i in range(0, 7): a[i] = a[i + 1] * 2 - a[i]
    for i in range(1, 8): a[i] = a[i] + a[i - 1]
    t = 0
    for i in range(0, 8): t += a[i] * (i + 1)
    return t

def wrapped(lo, hi):
    a = [0] * 8
    for i in range(0, 8): a[i] = i * i
    s = 0
    for i in range(lo, hi): s += a[i] * 3 + a[i + 1]
    return s

def stepped(k):
    a = [0] * 9
    for i in range(0, 9): a[i] = i + 1
    lo = 0; hi = k; s = 0
    while lo < hi:
        s += a[lo] * 10 + a[hi]
        lo += 2; hi -= 3
    return s

def skippy(n):
    a = [0] * 6
    for i in range(0, 6): a[i] = i + 2
    s = 0
    for i in range(0, n):
        if a[i] == 5: continue
        if a[i] > 6: break
        s += a[i]
    return s

def growing(n):
    xs = []; s = 0
    for i in range(0, n):
        xs.append(i * 2); s += xs[i]
    return s

def twice(n):
    a = [0] * 6
    lo = 0; hi = n; s = 0
    while lo < hi:
        lo += 1; s += a[lo]; lo += 1
    return s

def show(label, v): print(label + " " + str(v))
show("flip", flip(8, 7)); show("flip", flip(5, 4)); show("flip", flip(8, 0))
show("shifted", shifted(3))
show("wrapped", wrapped(0, 7)); show("wrapped", wrapped(-3, 5)); show("wrapped", wrapped(-2, 0))
show("stepped", stepped(8)); show("stepped", stepped(5))
show("skippy", skippy(6)); show("growing", growing(20)); show("twice", twice(5))
for label, call in (("flip n=9", lambda: flip(9, 2)), ("flip hi=8", lambda: flip(8, 8)),
                    ("wrapped 8", lambda: wrapped(0, 8)), ("wrapped -9", lambda: wrapped(-9, 0)),
                    ("skippy 7", lambda: skippy(7)), ("stepped 12", lambda: stepped(12)),
                    ("twice 7", lambda: twice(7))):
    try:
        show(label.split()[0], call())
    except IndexError:
        print(label + ": index error")
"""


class GuardedLoops(unittest.TestCase):
    def test_matches_cpython_and_emits_unchecked_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(GUARDED, directory)
            ran = run(exe)
            expected = subprocess.run([sys.executable, '-c', GUARDED_PY], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            # The fast copies exist for the loops that qualify ...
            for fn in ('flip', 'shifted', 'wrapped', 'stepped', 'skippy'):
                body = function_body(program, fn)
                self.assertIn('->p[', body, '%s: no unchecked copy emitted' % fn)
                if fn != 'shifted' and LEGACY_C:     # constant bounds over an 8-element list: rangecheck.py proves
                    self.assertTrue('ail_list_get(' in body or 'ail_list_set(' in body, fn)  # every access
            # ... and the loops that resize or step twice per iteration are not guarded (one loop,
            # no `else` copy). `growing` reads xs[i] right after xs.append(...), where
            # rangecheck.py knows len(xs) == i + 1, so that one read is unchecked without a guard.
            for fn in ('growing', 'twice'):
                body = function_body(program, fn)
                self.assertNotIn('} else {', body, '%s: must not be guarded' % fn)
            if LEGACY_C:
                self.assertNotIn('->p[', function_body(program, 'twice'))

    def test_swap_loop_runs_without_bounds_checks(self):
        source = """
fn main() {
    let n = int(sys.argv[1]);
    let p = [0] * 16;
    for i in range(0, 16) { p[i] = i; }
    let total = 0;
    for r in range(0, n) {
        let lo = 0;
        let hi = 15;
        while lo < hi {
            let t = p[lo];
            p[lo] = p[hi];
            p[hi] = t;
            lo += 1;
            hi -= 1;
        }
        total += p[r % 16];
    }
    print(total);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(source, directory)
            ran = run(exe, 1001)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            p = list(range(16)); total = 0
            for r in range(1001):
                p.reverse(); total += p[r % 16]
            self.assertEqual(ran.stdout.strip(), str(total))
            self.assertIn('->p[', program)

    def test_bytes_and_bytearray_reads(self):
        source = """
fn scan(data: bytes, lo: int, hi: int) -> int {
    let s = 0;
    for i in range(lo, hi) { s = (s * 31 + data[i]) % 1000003; }
    return s;
}

fn rolling(ba: bytearray, k: int) -> int {
    let key = 0;
    let hits = 0;
    for i in range(0, len(ba)) {
        key = ((key << 2) | (ba[i] & 3)) & 1023;
        if i >= k - 1 and key == 77 { hits += 1; }
    }
    return hits;
}

fn keep(data: bytes) -> bytearray {
    let out = bytearray();
    for i in range(0, len(data)) {
        if data[i] != 13 { out.append(data[i]); }
    }
    return out;
}

fn alias() -> int {
    let a = bytearray(b"abc");
    let b = a;
    for i in range(0, 3) { b.append(a[i]); }
    return len(a);
}

fn walk(ba: bytearray, n: int) -> int {
    let i = 0;
    let s = 0;
    while i < n { s = (s * 31 + ba[i]) % 1000003; i += 1; }
    return s;
}

fn main() {
    print(scan(b"hello, world", 0, 12));
    print(scan(b"hello, world", 3, 9));
    print(scan(b"hello, world", -4, 0));
    let ba = bytearray(b"ACGTTGCAACGTAC");
    print(rolling(ba, 2));
    print(len(keep(b"a\\r\\nb\\r\\n")));
    print(alias());
    try { print(scan(b"abc", 0, 4)); } except IndexError { print("bytes index error"); }
    try { print(scan(b"abc", -5, 0)); } except IndexError { print("bytes negative error"); }
    print(walk(ba, 14));
    print(walk(ba, 0));
    try { print(walk(ba, 15)); } except IndexError { print("walk error"); }
}
"""
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(source, directory)
            ran = run(exe)
            self.assertEqual(ran.returncode, 0, ran.stderr)

            def scan(data, lo, hi):
                s = 0
                for i in range(lo, hi):
                    s = (s * 31 + data[i]) % 1000003
                return s
            ba = bytearray(b"ACGTTGCAACGTAC")
            key = hits = 0
            for i in range(len(ba)):
                key = ((key << 2) | (ba[i] & 3)) & 1023
                if i >= 1 and key == 77:
                    hits += 1
            walked = 0
            for byte in ba:
                walked = (walked * 31 + byte) % 1000003
            expected = [scan(b"hello, world", 0, 12), scan(b"hello, world", 3, 9), scan(b"hello, world", -4, 0),
                        hits, len(b"a\nb\n"), 6, "bytes index error", "bytes negative error", walked, 0, "walk error"]
            self.assertEqual(ran.stdout.split("\n")[:11], [str(x) for x in expected])
            if LEGACY_C:
                # an access before the loop's step needs `n <= len`, not `n <= len - 1`
                self.assertIn('v_n <= ((int64_t)(v_ba)->n) - 0LL', function_body(program, 'walk'))
                self.assertIn('(v_data).p[', function_body(program, 'scan'))
                self.assertIn('->refs', function_body(program, 'rolling'))
                self.assertIn('(v_data).p[', function_body(program, 'keep'))
                self.assertNotIn('->refs &&', function_body(program, 'alias'))

    def test_struct_field_lists_and_list_parameters(self):
        source = """
struct Big { d: list[int]; }

fn addmul(a: Big, b: list[int], m: int) -> int {
    let n = len(a.d);
    for i in range(0, n) { a.d[i] = a.d[i] * m + b[i]; }
    let s = 0;
    for i in range(0, n) { s = (s * 3 + a.d[i]) % 1000003; }
    return s;
}

fn prefix(a: Big) -> int {
    for i in range(1, len(a.d)) { a.d[i] = a.d[i] + a.d[i - 1]; }
    return a.d[len(a.d) - 1];
}

fn grow(a: Big, b: list[int]) -> int {
    for i in range(0, 3) { a.d.append(a.d[i] + b[i]); }
    return len(a.d);
}

fn selfgrow(x: Big, y: Big) -> int {
    for i in range(0, 3) { x.d.append(y.d[i]); }
    return len(x.d) * 100 + x.d[5];
}

fn make(n: int) -> Big {
    let l: list[int] = [];
    for i in range(0, n) { l.append(i + 1); }
    return Big(l);
}

fn main() {
    let b = make(5);
    let c: list[int] = [10, 20, 30, 40, 50];
    print(addmul(b, c, 3));
    print(prefix(make(6)));
    print(grow(make(4), c));
    let z = make(3);
    print(selfgrow(z, z));
    try { print(addmul(make(6), c, 2)); } except IndexError { print("short parameter"); }
    try { print(prefix(make(0))); } except IndexError { print("empty"); }
}
"""
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(source, directory)
            ran = run(exe)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            d = [1, 2, 3, 4, 5]
            c = [10, 20, 30, 40, 50]
            for i in range(5):
                d[i] = d[i] * 3 + c[i]
            s = 0
            for v in d:
                s = (s * 3 + v) % 1000003
            e = [1, 2, 3, 4, 5, 6]
            for i in range(1, 6):
                e[i] += e[i - 1]
            z = [1, 2, 3]
            for i in range(3):
                z.append(z[i])
            expected = [s, e[-1], 7, len(z) * 100 + z[5], "short parameter", "empty"]
            self.assertEqual(ran.stdout.split('\n')[:6], [str(x) for x in expected])
            # span-cached field list reads in the guarded copy are raw `_spN[i]`; the checked copy
            # (the `else` branch) keeps the view's bounds check
            if LEGACY_C:
                addmul = function_body(program, 'addmul')
                self.assertEqual(addmul.count('} else {'), 2)
                for fast in re.findall(r'if \(v__t\d+ >= 0LL[^\n]*\n(.*?)\n        \} else \{', addmul, re.S):
                    self.assertRegex(fast, r'_sp\d\[ v_i\]')
                    self.assertNotIn('ail_list_view_', fast)
                    self.assertNotIn('ail_list_get', fast)
                self.assertIn('ail_list_view_get(_sp1', addmul)
                self.assertIn('->f_d.p[', function_body(program, 'prefix'))
                self.assertNotIn('->f_d.p[', function_body(program, 'grow'))
                self.assertNotIn('->f_d.p[', function_body(program, 'selfgrow'))


POOL = """
struct Node { left: Node | None; right: Node | None; }
struct Cell { value: int; next: Cell | None; }
struct Wide { a0: int; a1: int; a2: int; a3: int; a4: int; a5: int; a6: int; a7: int; a8: int; a9: int;
              b0: int; b1: int; b2: int; b3: int; b4: int; b5: int; b6: int; b7: int; b8: int; b9: int;
              c0: int; c1: int; c2: int; c3: int; c4: int; c5: int; c6: int; c7: int; c8: int; c9: int; }

fn make(d: int) -> Node {
    if d == 0 { return Node(None, None); }
    return Node(make(d - 1), make(d - 1));
}

fn check(t: Node | None) -> int {
    if t is None { return 0; }
    return 1 + check(t.left) + check(t.right);
}

fn chain(n: int) -> Cell | None {
    let head: Cell | None = None;
    for i in range(0, n) { head = Cell(i, head); }
    return head;
}

fn walk(c: Cell | None) -> int {
    let s = 0;
    let cur = c;
    while cur is not None {
        s += cur.value;
        cur = cur.next;
    }
    return s;
}

fn wide(n: int) -> int {
    let s = 0;
    for i in range(0, n) {
        let w = Wide(i, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, i);
        s += w.a0 + w.c9;
    }
    return s;
}

fn main() {
    let total = 0;
    for r in range(0, 30) {
        let t = make(10);
        total += check(t);
    }
    print(total);
    let keep = make(12);
    for r in range(0, 20) { total += check(make(9)); }
    print(total + check(keep));
    print(walk(chain(300000)));
    print(wide(1000));
}
"""


class ObjectPool(unittest.TestCase):
    def test_pool_and_malloc_builds_print_the_same(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(POOL, directory)
            ran = run(exe)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout.split(), [str(30 * 2047), str(30 * 2047 + 20 * 1023 + 8191),
                                                  str(sum(range(300000))), str(sum(2 * i for i in range(1000)))])
            self.assertIn('ail_pool_head', program)
            plain = Path(directory, 'plain')
            cc = subprocess.run(['cc', '-O1', '-DAIL_NO_OBJ_POOL', '-o', str(plain), str(Path(directory, 'p.d', 'program.c')), '-lm'],
                                capture_output=True, text=True)
            self.assertEqual(cc.returncode, 0, cc.stderr)
            again = run(plain)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(again.stdout, ran.stdout)

    def test_peak_memory_does_not_grow_with_repeated_builds(self):
        source = """
struct Node { left: Node | None; right: Node | None; }
fn make(d: int) -> Node {
    if d == 0 { return Node(None, None); }
    return Node(make(d - 1), make(d - 1));
}
fn check(t: Node | None) -> int {
    if t is None { return 0; }
    return 1 + check(t.left) + check(t.right);
}
fn main() {
    let total = 0;
    for r in range(0, 400) { total += check(make(12)); }
    print(total);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            exe, _ = build(source, directory)
            measure = ('import resource, subprocess, sys\n'
                       'subprocess.run([sys.argv[1]], stdout=subprocess.DEVNULL)\n'
                       'print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)')
            peak = int(subprocess.run([sys.executable, '-c', measure, str(exe)], capture_output=True,
                                      text=True, timeout=120).stdout)
            # 8191 nodes x 32 bytes is 256 KiB; 400 rebuilds that failed to reuse freed objects
            # would hold over 100 MiB. The measuring Python itself accounts for about 12 MiB.
            self.assertLess(peak, 40 * 1024, peak)
            ran = run(exe)
            self.assertEqual(ran.stdout.strip(), str(400 * 8191))


LOOP_LOCALS = """
struct Node { left: Node | None; right: Node | None; v: int; }

fn make(d: int, v: int) -> Node {
    if d == 0 { return Node(None, None, v); }
    return Node(make(d - 1, v + 1), make(d - 1, v + 2), v);
}

fn total(t: Node | None) -> int {
    if t is None { return 0; }
    return t.v + total(t.left) + total(t.right);
}

fn loops() -> int {
    let keep: list[Node] = [];
    let s = 0;
    for i in range(0, 6) {
        let t = make(3, i);
        if i == 2 { continue; }
        s += total(t);
        if i % 2 == 0 { keep.append(t); }
        let u = t;
        s += total(u);
    }
    for k in keep { s += total(k) * 3; }
    let w = 0;
    while w < 3 {
        let a = make(2, w);
        let b = make(2, w + 10);
        s += total(a) + total(b);
        w += 1;
        if w == 2 { break; }
    }
    return s;
}

fn guarded() -> int {
    let s = 0;
    for i in range(0, 4) {
        let t = make(2, i);
        try {
            if i == 2 { raise ValueError(); }
            s += total(t);
        } except ValueError {
            s += 100;
        }
    }
    return s;
}

fn carried() -> int {
    let t = make(1, 5);
    let s = 0;
    for i in range(0, 3) {
        s += total(t);
        t = make(1, i);
    }
    return s + total(t);
}

fn main() {
    print(loops());
    print(guarded());
    print(carried());
}
"""

LOOP_LOCALS_PY = """
class Node:
    def __init__(self, left, right, v): self.left, self.right, self.v = left, right, v

def make(d, v):
    if d == 0: return Node(None, None, v)
    return Node(make(d - 1, v + 1), make(d - 1, v + 2), v)

def total(t):
    if t is None: return 0
    return t.v + total(t.left) + total(t.right)

def loops():
    keep = []; s = 0
    for i in range(6):
        t = make(3, i)
        if i == 2: continue
        s += total(t)
        if i % 2 == 0: keep.append(t)
        u = t
        s += total(u)
    for k in keep: s += total(k) * 3
    w = 0
    while w < 3:
        a = make(2, w); b = make(2, w + 10)
        s += total(a) + total(b)
        w += 1
        if w == 2: break
    return s

def guarded():
    s = 0
    for i in range(4):
        t = make(2, i)
        try:
            if i == 2: raise ValueError()
            s += total(t)
        except ValueError:
            s += 100
    return s

def carried():
    t = make(1, 5); s = 0
    for i in range(3):
        s += total(t)
        t = make(1, i)
    return s + total(t)

print(loops()); print(guarded()); print(carried())
"""


class LoopLocalRelease(unittest.TestCase):
    def test_per_iteration_locals_match_cpython_and_are_released_early(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(LOOP_LOCALS, directory)
            ran = run(exe)
            expected = subprocess.run([sys.executable, '-c', LOOP_LOCALS_PY], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            loops = function_body(program, 'loops')
            for name in ('t', 'u', 'a', 'b'):
                self.assertIn('ail_obj_release(v_%s); v_%s = 0;' % (name, name), loops, name)
            # a value carried into the next iteration is not released after its last use in the body
            self.assertNotIn('ail_obj_release(v_t); v_t = 0;', function_body(program, 'carried'))
            plain = Path(directory, 'plain')
            cc = subprocess.run(['cc', '-O1', '-DAIL_NO_OBJ_POOL', '-o', str(plain), str(Path(directory, 'p.d', 'program.c')), '-lm'],
                                capture_output=True, text=True)
            self.assertEqual(cc.returncode, 0, cc.stderr)
            self.assertEqual(run(plain).stdout, ran.stdout)

    def test_tree_built_per_iteration_is_gone_before_the_next_is_built(self):
        source = """
struct Node { left: Node | None; right: Node | None; }
fn make(d: int) -> Node {
    if d == 0 { return Node(None, None); }
    return Node(make(d - 1), make(d - 1));
}
fn check(t: Node | None) -> int {
    if t is None { return 0; }
    return 1 + check(t.left) + check(t.right);
}
fn main() {
    let total = 0;
    for i in range(0, 6) {
        let t = make(18);
        total += check(t);
    }
    print(total);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            exe, _ = build(source, directory)
            measure = ('import resource, subprocess, sys\n'
                       'subprocess.run([sys.argv[1]], stdout=subprocess.DEVNULL)\n'
                       'print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)')
            peak = int(subprocess.run([sys.executable, '-c', measure, str(exe)], capture_output=True,
                                      text=True, timeout=120).stdout)
            # one tree is 524287 nodes x 24 bytes = 12 MiB; holding two at once would put the peak
            # at 37 MiB with the measuring Python's own ~12 MiB
            self.assertLess(peak, 30 * 1024, peak)
            self.assertEqual(run(exe).stdout.strip(), str(6 * 524287))


class ShiftByLiteral(unittest.TestCase):
    def test_boundaries_match_the_general_shift(self):
        source = """
fn main() {
    let v = int(sys.argv[1]);
    print(v << 2);
    print(v << 0);
    print(v << 62);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(source, directory)
            self.assertIn('ck_shlk(', program)
            for v in (0, 1, -1, 3, 2 ** 60, 2 ** 61 - 1, -2 ** 61):
                ran = run(exe, v)
                shifted = [v << 2, v << 0, v << 62]
                fits = all(-2 ** 63 <= x < 2 ** 63 for x in shifted)
                if fits:
                    self.assertEqual(ran.stdout.split(), [str(x) for x in shifted], v)
                else:
                    self.assertNotEqual(ran.returncode, 0, v)
                    self.assertIn('integer overflow', ran.stderr, v)
            for v in (2 ** 61, -2 ** 61 - 1, 2 ** 62):
                self.assertTrue(v << 2 >= 2 ** 63 or v << 2 < -2 ** 63)
                ran = run(exe, v)
                self.assertNotEqual(ran.returncode, 0, v)
                self.assertIn('integer overflow', ran.stderr, v)

    def test_last_representable_values(self):
        source = """
fn main() {
    let v = int(sys.argv[1]);
    print(v << 3);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            exe, _ = build(source, directory)
            for v in (2 ** 60 - 1, -2 ** 60):
                ran = run(exe, v)
                self.assertEqual(ran.stdout.strip(), str(v << 3), v)
            for v in (2 ** 60, -2 ** 60 - 1):
                ran = run(exe, v)
                self.assertNotEqual(ran.returncode, 0, v)
                self.assertIn('integer overflow', ran.stderr, v)


class AppendOfCall(unittest.TestCase):
    def test_append_of_a_call_needs_no_receiver_retain(self):
        source = """
fn code(c: int) -> int {
    let u = c & 223;
    if u == 65 { return 0; }
    if u == 67 { return 1; }
    return 3;
}

fn bad(c: int) -> int { return c * 100; }

fn build(data: bytes) -> bytearray {
    let out = bytearray();
    for i in range(0, len(data)) { out.append(code(data[i])); }
    return out;
}

fn main() {
    let ba = build(b"ACGTacgt");
    let s = 0;
    for i in range(0, len(ba)) { s = s * 4 + ba[i]; }
    print(s);
    let out = bytearray();
    try { out.append(bad(3)); } except ValueError { print("value error"); }
    out.append(bad(2));
    print(len(out));
}
"""
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(source, directory)
            ran = run(exe)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            codes = [{65: 0, 67: 1}.get(c & 223, 3) for c in b'ACGTacgt']
            s = 0
            for c in codes:
                s = s * 4 + c
            self.assertEqual(ran.stdout.split('\n')[:3], [str(s), 'value error', '1'])
            if LEGACY_C:
                self.assertIn('_receiver', function_body(program, 'build'))


if __name__ == '__main__':
    unittest.main()
