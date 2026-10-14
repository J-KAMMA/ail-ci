"""Numeric loops compile to tight C and still match CPython.

Regressions guarded here (all found measuring the Benchmarks Game programs against C):
  * a loop that only does int/float arithmetic, int/float list indexing and calls to number-only
    functions carries no per-iteration str-arena checkpoint (`ail_sarena_keep_roots`), `for` or `while`;
  * a loop that really builds strings keeps its checkpoint;
  * struct-list element access (`ail_olist_get`) is inlined, so `b[i].x` in a hot loop is not a call;
  * an int list's length is not spelled `int64_t`, so an element store cannot alias it and the bound
    is not reloaded after every `xs[i] = v`;
  * the numeric struct-field list stores through a typed assignment, not `memcpy` (which aliases all).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NUMERIC = """
struct Body { x: float; v: float; }

fn weight(i: int, j: int) -> float {
    let s = i + j;
    return 1.0 / float(s * (s + 1) // 2 + i + 1);
}

fn mat(v: list[float], n: int) -> list[float] {
    let r: list[float] = [];
    for i in range(0, n) {
        let s = 0.0;
        for j in range(0, n) { s = s + weight(i, j) * v[j]; }
        r.append(s);
    }
    return r;
}

fn flips(n: int) -> int {
    let p = [0] * 8;
    let q = [0] * 8;
    for i in range(0, 8) { p[i] = (i * 5 + n) % 8; }
    let total = 0;
    let rounds = 0;
    while rounds < n {
        for i in range(0, 8) { q[i] = p[i]; }
        let lo = 0;
        let hi = 7;
        while lo < hi {
            let t = q[lo];
            q[lo] = q[hi];
            q[hi] = t;
            lo += 1;
            hi -= 1;
        }
        total += q[0] * 3 + q[7];
        p[rounds % 8] = (p[rounds % 8] + 1) % 8;
        rounds += 1;
    }
    return total;
}

fn escape(cr: float, ci: float) -> int {
    let zr = 0.0; let zi = 0.0; let tr = 0.0; let ti = 0.0;
    let i = 0;
    while i < 50 and tr + ti <= 4.0 {
        zi = 2.0 * zr * zi + ci;
        zr = tr - ti + cr;
        tr = zr * zr;
        ti = zi * zi;
        i += 1;
    }
    return i;
}

fn step(b: list[Body], dt: float) -> void {
    for i in range(0, 3) {
        let bi = b[i];
        for j in range(i + 1, 3) {
            let bj = b[j];
            let d = bj.x - bi.x;
            bi.v = bi.v + d * dt;
            bj.v = bj.v - d * dt;
        }
    }
    for i in range(0, 3) { let p = b[i]; p.x = p.x + p.v * dt; }
}

fn main() {
    let n = 12;
    let u: list[float] = [];
    for i in range(0, n) { u.append(1.0 + i * 0.25); }
    let w = mat(mat(u, n), n);
    let s = 0.0;
    for i in range(0, n) { s = s + w[i]; }
    print("%.9f" % (s,));
    print(flips(37));
    let c = 0;
    for y in range(0, 20) {
        for x in range(0, 20) { c += escape(x * 0.1 - 1.5, y * 0.1 - 1.0); }
    }
    print(c);
    let b: list[Body] = [];
    b.append(Body(0.0, 0.5)); b.append(Body(1.0, -0.25)); b.append(Body(3.0, 0.0));
    for k in range(0, 50) { step(b, 0.01); }
    print("%.9f %.9f %.9f" % (b[0].x, b[1].x, b[2].x));
}
"""

NUMERIC_PY = """
class Body:
    def __init__(self, x, v): self.x = x; self.v = v

def weight(i, j):
    s = i + j
    return 1.0 / float(s * (s + 1) // 2 + i + 1)

def mat(v, n):
    r = []
    for i in range(n):
        s = 0.0
        for j in range(n): s = s + weight(i, j) * v[j]
        r.append(s)
    return r

def flips(n):
    p = [0] * 8; q = [0] * 8
    for i in range(8): p[i] = (i * 5 + n) % 8
    total = 0; rounds = 0
    while rounds < n:
        for i in range(8): q[i] = p[i]
        lo = 0; hi = 7
        while lo < hi:
            t = q[lo]; q[lo] = q[hi]; q[hi] = t
            lo += 1; hi -= 1
        total += q[0] * 3 + q[7]
        p[rounds % 8] = (p[rounds % 8] + 1) % 8
        rounds += 1
    return total

def escape(cr, ci):
    zr = zi = tr = ti = 0.0
    i = 0
    while i < 50 and tr + ti <= 4.0:
        zi = 2.0 * zr * zi + ci
        zr = tr - ti + cr
        tr = zr * zr
        ti = zi * zi
        i += 1
    return i

def step(b, dt):
    for i in range(3):
        bi = b[i]
        for j in range(i + 1, 3):
            bj = b[j]
            d = bj.x - bi.x
            bi.v = bi.v + d * dt
            bj.v = bj.v - d * dt
    for i in range(3):
        p = b[i]; p.x = p.x + p.v * dt

n = 12
u = [1.0 + i * 0.25 for i in range(n)]
w = mat(mat(u, n), n)
s = 0.0
for i in range(n): s = s + w[i]
print("%.9f" % (s,))
print(flips(37))
c = 0
for y in range(20):
    for x in range(20): c += escape(x * 0.1 - 1.5, y * 0.1 - 1.0)
print(c)
b = [Body(0.0, 0.5), Body(1.0, -0.25), Body(3.0, 0.0)]
for k in range(50): step(b, 0.01)
print("%.9f %.9f %.9f" % (b[0].x, b[1].x, b[2].x))
"""

FIELD = """
struct Big { d: list[int]; }

fn scale(a: Big, m: int) -> void {
    let carry = 0;
    for i in range(0, len(a.d)) {
        let v = a.d[i] * m + carry;
        carry = v // 1000;
        a.d[i] = v - carry * 1000;
    }
    while carry > 0 { a.d.append(carry % 1000); carry = carry // 1000; }
}

fn main() {
    let a = Big([1, 999, 500]);
    for k in range(2, 9) { scale(a, k * 37); }
    print(a.d[0], a.d[1], a.d[2], len(a.d));
}
"""

FIELD_PY = """
d = [1, 999, 500]
def scale(d, m):
    carry = 0
    for i in range(len(d)):
        v = d[i] * m + carry
        carry = v // 1000
        d[i] = v - carry * 1000
    while carry > 0:
        d.append(carry % 1000); carry = carry // 1000
for k in range(2, 9): scale(d, k * 37)
print(d[0], d[1], d[2], len(d))
"""

STRINGY = """
fn main() {
    let out = "";
    let k = 0;
    while k < 6 {
        let line = "";
        for j in range(0, k) { line = line + str(j); }
        out = out + line + ";";
        k += 1;
    }
    print(out);
}
"""

STRINGY_PY = """
out = ""
k = 0
while k < 6:
    line = ""
    for j in range(k): line = line + str(j)
    out = out + line + ";"
    k += 1
print(out)
"""


def build(source_text, directory, name):
    source, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "-debug")
    source.write_text(source_text)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    return built, exe, debug


class NumericLoopTests(unittest.TestCase):
    def test_numeric_loops_match_cpython_and_carry_no_arena_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, debug = build(NUMERIC, directory, "numeric")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            program = (debug / "program.c").read_text()
            # The one checkpoint left is main's `for k` loop that calls `step` (it takes a struct list, so
            # a callee could hand back a view); weight, mat, flips, escape and step have none.
            self.assertEqual(program.count("ail_sarena_keep_roots(&v__sarena"), 1)
            # struct-list element access is inlined; int-list length cannot alias its elements;
            # the typed numeric-field store replaced memcpy.
            self.assertIn("static inline __attribute__((always_inline)) void *ail_olist_get(", program)
            self.assertIn("ail_len_t n, cap; } ail_list;", program)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", NUMERIC_PY], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)

    def test_struct_field_list_stores_are_typed_and_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, debug = build(FIELD, directory, "field")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            program = (debug / "program.c").read_text()
            self.assertIn("s->p[i] = value;", program)
            self.assertNotIn("memcpy(s->p + i, &value", program)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", FIELD_PY], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)

    def test_a_loop_that_builds_strings_keeps_its_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, debug = build(STRINGY, directory, "stringy")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn("ail_sarena_keep_roots(", (debug / "program.c").read_text())
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", STRINGY_PY], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()
