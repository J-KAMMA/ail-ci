"""Struct-list element reads, field access through a struct parameter, and recursion depth after an
exception match CPython, and the generated C no longer retains the owner or links an empty frame.

Regression (perf): `let b = bs[i]` retained the list into a temp, the element into another, then
`b` again; every `a.xs[i]` retained `a` into a temp; every recursive function linked a cleanup frame
only to give its depth count back. An LLM-written n-body and binary-trees spent 55% of their
instructions on that.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
struct Node { v: int; w: float; }
struct Bag { items: list[Node]; counts: list[int]; }

fn bump(b: Bag, i: int) -> int {
    let n = b.items[i];
    n.v = n.v + 1;
    n.w = n.w * 2.0;
    b.counts[i] = b.counts[i] + n.v;
    b.counts.append(len(b.counts));
    return b.counts[i] + len(b.counts);
}

fn total(xs: list[Node]) -> float {
    let t = 0.0;
    for i in range(len(xs)) {
        let n = xs[i];
        for j in range(i + 1, len(xs)) {
            let m = xs[j];
            t = t + n.w * m.w + n.v - m.v;
        }
    }
    return t;
}

fn deep(d: int, lim: int) -> int {
    if d >= lim { raise ValueError; }
    return deep(d + 1, lim) + 1;
}

fn guarded(d: int, lim: int) -> int {
    if d >= lim { raise KeyError; }
    let r = 0;
    try { r = guarded(d + 1, lim) + 1; } except KeyError { r = -d; }
    return r;
}

fn cleaned(d: int, lim: int, log: Bag) -> int {
    if d >= lim { raise ValueError; }
    try { return cleaned(d + 1, lim, log) + 1; } finally { log.counts.append(d); }
}

fn main() {
    let b = Bag([], []);
    for i in range(4) { b.items.append(Node(i, i * 0.5)); b.counts.append(i * 10); }
    print(bump(b, 1), bump(b, 1), bump(b, 3), b.counts[1], len(b.counts), b.items[1].v, b.items[1].w);
    let first = b.items[0];
    b.items[0] = Node(77, 7.5);
    first.v = first.v + 5;
    print(first.v, b.items[0].v, b.items[-1].v, total(b.items));
    let alias = b.items[2];
    alias = b.items[3];
    alias.v = alias.v + 100;
    print(b.items[2].v, b.items[3].v);
    try { let bad = b.items[9]; print(bad.v); } except IndexError { print("index error"); }

    let hits = 0;
    for k in range(120) {
        let r = 0;
        try { r = deep(0, 700); } except ValueError { r = -1; hits += 1; }
        if k % 40 == 0 { print(r, hits); }
    }
    print(hits, guarded(0, 40), guarded(0, 5));
    let log = Bag([], []);
    let out = 0;
    try { out = cleaned(0, 6, log); } except ValueError { out = -2; }
    print(out, len(log.counts), log.counts[0], log.counts[5]);
    print(deep(0, 0) if false else deep(0, 49000) if false else 3);
}
"""

PYTHON = """
class Node:
    def __init__(self, v, w): self.v, self.w = v, w
class Bag:
    def __init__(self): self.items, self.counts = [], []
def bump(b, i):
    n = b.items[i]
    n.v = n.v + 1
    n.w = n.w * 2.0
    b.counts[i] = b.counts[i] + n.v
    b.counts.append(len(b.counts))
    return b.counts[i] + len(b.counts)
def total(xs):
    t = 0.0
    for i in range(len(xs)):
        n = xs[i]
        for j in range(i + 1, len(xs)):
            m = xs[j]
            t = t + n.w * m.w + n.v - m.v
    return t
def deep(d, lim):
    if d >= lim: raise ValueError
    return deep(d + 1, lim) + 1
def guarded(d, lim):
    if d >= lim: raise KeyError
    r = 0
    try: r = guarded(d + 1, lim) + 1
    except KeyError: r = -d
    return r
def cleaned(d, lim, log):
    if d >= lim: raise ValueError
    try: return cleaned(d + 1, lim, log) + 1
    finally: log.counts.append(d)
import sys
sys.setrecursionlimit(10000)
b = Bag()
for i in range(4):
    b.items.append(Node(i, i * 0.5)); b.counts.append(i * 10)
print(bump(b, 1), bump(b, 1), bump(b, 3), b.counts[1], len(b.counts), b.items[1].v, b.items[1].w)
first = b.items[0]
b.items[0] = Node(77, 7.5)
first.v = first.v + 5
print(first.v, b.items[0].v, b.items[-1].v, total(b.items))
alias = b.items[2]
alias = b.items[3]
alias.v = alias.v + 100
print(b.items[2].v, b.items[3].v)
try:
    bad = b.items[9]; print(bad.v)
except IndexError:
    print("index error")
hits = 0
for k in range(120):
    r = 0
    try: r = deep(0, 700)
    except ValueError: r = -1; hits += 1
    if k % 40 == 0: print(r, hits)
print(hits, guarded(0, 40), guarded(0, 5))
log = Bag()
out = 0
try: out = cleaned(0, 6, log)
except ValueError: out = -2
print(out, len(log.counts), log.counts[0], log.counts[5])
print(3)
"""


ALIAS_SOURCE = """
struct P { x: float; v: float; n: int; }

fn kernel(ps: list[P], steps: int) -> float {
    let e = 0.0;
    for s in range(steps) {
        for i in range(len(ps)) {
            let a = ps[i];
            for j in range(i + 1, len(ps)) {
                let b = ps[j];
                let d = a.x - b.x;
                a.v = a.v - d * 0.5;
                b.v = b.v + d * 0.5;
                a.n += 1;
            }
        }
        for i in range(len(ps)) {
            let q = ps[i];
            q.x = q.x + 0.1 * q.v;
            e = e + q.x;
        }
    }
    return e;
}

fn swap_ends(ps: list[P]) -> int {
    let first = ps[0];
    let last = ps[len(ps) - 1];
    ps[0] = last;
    ps[len(ps) - 1] = first;
    first.n = first.n + 10;
    return ps[0].n + ps[len(ps) - 1].n;
}

fn pop_keeps(ps: list[P]) -> int {
    let last = ps[len(ps) - 1];
    ps.pop();
    last.n = last.n + 1;
    return last.n + len(ps);
}

fn with_call(ps: list[P]) -> int {
    let p = ps[1];
    let total = kernel(ps, 1) > 0.0;
    p.n = p.n + 1;
    return p.n;
}

fn main() {
    let ps: list[P] = [];
    for i in range(5) { ps.append(P(i * 1.5, 0.25 * i, i)); }
    print(kernel(ps, 3));
    for i in range(len(ps)) { print(ps[i].x, ps[i].v, ps[i].n); }
    print(swap_ends(ps), ps[0].n, ps[4].n);
    print(pop_keeps(ps), len(ps));
    print(with_call(ps), ps[1].n);
}
"""

ALIAS_PYTHON = """
class P:
    def __init__(self, x, v, n): self.x, self.v, self.n = x, v, n
def kernel(ps, steps):
    e = 0.0
    for s in range(steps):
        for i in range(len(ps)):
            a = ps[i]
            for j in range(i + 1, len(ps)):
                b = ps[j]
                d = a.x - b.x
                a.v = a.v - d * 0.5
                b.v = b.v + d * 0.5
                a.n += 1
        for i in range(len(ps)):
            q = ps[i]
            q.x = q.x + 0.1 * q.v
            e = e + q.x
    return e
def swap_ends(ps):
    first = ps[0]
    last = ps[len(ps) - 1]
    ps[0] = last
    ps[len(ps) - 1] = first
    first.n = first.n + 10
    return ps[0].n + ps[len(ps) - 1].n
def pop_keeps(ps):
    last = ps[len(ps) - 1]
    ps.pop()
    last.n = last.n + 1
    return last.n + len(ps)
def with_call(ps):
    p = ps[1]
    total = kernel(ps, 1) > 0.0
    p.n = p.n + 1
    return p.n
ps = [P(i * 1.5, 0.25 * i, i) for i in range(5)]
print(kernel(ps, 3))
for p in ps: print(p.x, p.v, p.n)
print(swap_ends(ps), ps[0].n, ps[4].n)
print(pop_keeps(ps), len(ps))
print(with_call(ps), ps[1].n)
"""


FIELD_LIST_SOURCE = """
struct Q { xs: list[int]; fs: list[float]; }

fn grow(q: Q, n: int) -> int {
    for i in range(n) { q.xs.append(i * 3 - 7); q.fs.append(i * 0.25); }
    q.xs[0] = 99;
    q.fs[-1] = -1.5;
    return q.xs[n - 1] + q.xs[-2] + len(q.xs);
}

fn main() {
    let q = Q([], []);
    try { print(q.xs[0]); } except IndexError { print("empty"); }
    try { q.xs[0] = 1; } except IndexError { print("empty set"); }
    print(grow(q, 1000), q.xs[0], q.fs[999], q.fs[0], len(q.fs));
    try { print(q.xs[1000]); } except IndexError { print("past end"); }
    try { print(q.fs[-1001]); } except IndexError { print("before start"); }
    q.xs.pop();
    q.xs.append(5);
    print(q.xs[-1], len(q.xs));
}
"""

FIELD_LIST_PYTHON = """
class Q:
    def __init__(self): self.xs, self.fs = [], []
def grow(q, n):
    for i in range(n):
        q.xs.append(i * 3 - 7); q.fs.append(i * 0.25)
    q.xs[0] = 99
    q.fs[-1] = -1.5
    return q.xs[n - 1] + q.xs[-2] + len(q.xs)
q = Q()
try: print(q.xs[0])
except IndexError: print("empty")
try: q.xs[0] = 1
except IndexError: print("empty set")
print(grow(q, 1000), q.xs[0], q.fs[999], q.fs[0], len(q.fs))
try: print(q.xs[1000])
except IndexError: print("past end")
try: print(q.fs[-1001])
except IndexError: print("before start")
q.xs.pop()
q.xs.append(5)
print(q.xs[-1], len(q.xs))
"""


class BorrowedOwnerTests(unittest.TestCase):
    def build(self, directory, source_text):
        source, exe = Path(directory, "p.ail"), Path(directory, "p")
        debug = Path(directory, "debug")
        source.write_text(source_text)
        built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                                "-o", str(exe), "--debug-dir", str(debug)],
                               capture_output=True, text=True, timeout=300)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return exe, (debug / "program.c").read_text()

    def test_matches_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, program = self.build(directory, SOURCE)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)

    def test_struct_list_read_has_no_owner_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            _, program = self.build(directory, SOURCE)
            body = program[program.index("\ndouble total(ail_olist *v_xs) {"):]
            body = body[:body.index("\n}\n")]
            self.assertNotIn("ail_olist_store(", body)
            # the element locals are only read through, so they hold no reference at all
            self.assertNotIn("ail_obj_store_Node(", body)
            self.assertNotIn("ail_obj_retain(ail_olist_get", body)

    def test_param_field_access_does_not_retain_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            _, program = self.build(directory, SOURCE)
            body = program[program.index("\nint64_t bump(ail_obj_Bag *v_b, int64_t v_i) {"):]
            body = body[:body.index("\n}\n")]
            self.assertNotIn("ail_obj_store_Bag(", body)

    def test_recursive_function_without_resources_links_no_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            _, program = self.build(directory, SOURCE)
            body = program[program.index("\nint64_t deep(int64_t v_d, int64_t v_lim) {"):]
            body = body[:body.index("\n}\n")]
            self.assertNotIn("ail_cleanup_frame", body)
            self.assertIn("ail_depth--", body)

    def test_element_locals_match_cpython_and_borrow_only_when_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, program = self.build(directory, ALIAS_SOURCE)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", ALIAS_PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)

            def body(name):
                start = re.search(r"\n" + re.escape(name) + r"[^;{]*\{\n", program).start()
                text = program[start:]
                return text[:text.index("\n}\n")]

            kernel = body("double kernel(")
            self.assertNotIn("ail_obj_store_P(", kernel)
            self.assertNotIn("ail_obj_retain(ail_olist_get", kernel)
            for unsafe in ("int64_t swap_ends(", "int64_t pop_keeps(", "int64_t with_call("):
                self.assertIn("ail_obj_retain(ail_olist_get", body(unsafe), unsafe)

    def test_numeric_field_lists_grow_and_bound_check_like_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, _ = self.build(directory, FIELD_LIST_SOURCE)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", FIELD_LIST_PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()
