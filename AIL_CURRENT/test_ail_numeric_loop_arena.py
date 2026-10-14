"""A loop that only computes numbers carries no per-iteration string-arena checkpoint.

`ail_sarena_keep_roots` runs at the top of every iteration of a loop that may allocate strings.
Float arithmetic, calls of fns that take and return numbers (their arena is their own), element
stores into number lists, nested range loops and `append` of a number allocate nothing, so such
loops (the inner loops of spectral-norm, mandelbrot, any float kernel) are emitted without it: 18-20%
fewer instructions, and a loop gcc can see through. A loop that builds a str keeps the checkpoint.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NUMERIC = """
fn cell(i: int, j: int) -> float {
    let s = i + j;
    return 1.0 / float(s * (s + 1) // 2 + i + 1);
}
fn rows(v: list[float], n: int) -> list[float] {
    let r: list[float] = [];
    for i in range(0, n) {
        let s = 0.0;
        for j in range(0, n) { s = s + cell(i, j) * v[j]; }
        r.append(s);
    }
    return r;
}
fn escape(cr: float, ci: float) -> int {
    let zr = 0.0; let zi = 0.0; let tr = 0.0; let ti = 0.0;
    let k = 0;
    while k < 50 and tr + ti <= 4.0 {
        zi = 2.0 * zr * zi + ci;
        zr = tr - ti + cr;
        tr = zr * zr;
        ti = zi * zi;
        k += 1;
    }
    return k;
}
fn main() {
    let n = 40;
    let v: list[float] = [];
    for i in range(0, n) { v.append(1.0 + float(i % 3)); }
    let r = rows(v, n);
    let total = 0.0;
    for i in range(0, n) { total += r[i] * 0.5; }
    let hits = 0;
    for y in range(0, 20) {
        for x in range(0, 30) { hits += escape(float(x) / 10.0 - 2.0, float(y) / 10.0 - 1.0); }
    }
    print(total, hits);
}
"""

PYTHON = """
def cell(i, j):
    s = i + j
    return 1.0 / float(s * (s + 1) // 2 + i + 1)
def escape(cr, ci):
    zr = zi = tr = ti = 0.0
    k = 0
    while k < 50 and tr + ti <= 4.0:
        zi = 2.0 * zr * zi + ci
        zr = tr - ti + cr
        tr = zr * zr
        ti = zi * zi
        k += 1
    return k
n = 40
v = [1.0 + float(i % 3) for i in range(n)]
r = []
for i in range(n):
    s = 0.0
    for j in range(n):
        s = s + cell(i, j) * v[j]
    r.append(s)
total = 0.0
for i in range(n):
    total += r[i] * 0.5
hits = 0
for y in range(20):
    for x in range(30):
        hits += escape(float(x) / 10.0 - 2.0, float(y) / 10.0 - 1.0)
print(total, hits)
"""

TEXT = """
fn main() {
    let out = "";
    for i in range(0, 5) { out = out + str(i) + ","; }
    print(out);
}
"""


def build(directory, name, source):
    path, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "_c")
    path.write_text(source)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(path), "-o", str(exe),
                            "--debug-dir", str(debug)], capture_output=True, text=True, timeout=300)
    return built, exe, (debug / "program.c").read_text() if built.returncode == 0 else ""


class NumericLoopArenaTests(unittest.TestCase):
    def test_number_loops_have_no_checkpoint_and_still_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c = build(directory, "num", NUMERIC)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertNotIn("ail_sarena_keep_roots(&v__sarena", c)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)

    def test_a_loop_that_builds_a_str_keeps_its_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c = build(directory, "text", TEXT)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn("ail_sarena_keep_roots(&v__sarena", c)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.stdout, "0,1,2,3,4,\n")


if __name__ == "__main__":
    unittest.main()
