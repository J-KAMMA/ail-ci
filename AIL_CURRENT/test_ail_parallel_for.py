"""`parallel for` runs independent iterations on threads and gives exactly the sequential result.

Each program here is run twice from one source: with `parallel for` and with the plain `for` it
stands for, at several thread counts. The outputs must be identical. Bodies that could observe each
other (a running total, a shifted write, a print, a container that grows) are refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = """
fn cell(i: int, j: int) -> float {
    let s = i + j;
    return 1.0 / float(s * (s + 1) // 2 + i + 1);
}
fn hypot2(a: float, b: float) -> float { return a * a + b * b; }

fn rows(v: list[float], n: int) -> list[float] {
    let r = [0.0] * n;
    FOR i in range(0, n) {
        let s = 0.0;
        for j in range(0, n) { s = s + cell(i, j) * v[j]; }
        r[i] = s;
    }
    return r;
}

fn main() {
    let n = 300;
    let w = 7;
    let v: list[float] = [];
    for i in range(0, n) { v.append(1.0 + float(i % 5)); }
    let r = rows(v, n);
    let acc = 0.0;
    for i in range(0, n) { acc = acc + r[i]; }

    let img = bytearray(n * w);
    FOR y in range(0, n) {
        for b in range(0, w) {
            let a = 0;
            for k in range(0, 8) {
                a = a * 2;
                if hypot2(float(y), float(b * 8 + k)) < 40000.0 { a += 1; }
            }
            img[y * w + b] = a;
        }
    }
    let sum = 0;
    for i in range(0, n * w) { sum = sum * 31 % 1000003 + img[i]; }

    let squares: list[int] = [0] * n;
    let halves: list[float] = [0.0] * n;
    let k = 3;
    FOR i in range(-5, n) {
        let t = i * i - k;
        if i >= 0 { squares[i] = t; halves[i] = float(t) / 2.0 + abs(float(i)); }
    }
    let pairs: list[int] = [0] * 64;
    FOR i in range(0, 32) { pairs[2 * i] = i; pairs[2 * i + 1] = -i; }
    let t = 0;
    for i in range(0, n) { t += squares[i] + len(halves); }
    for i in range(0, 64) { t += pairs[i] * (i + 1); }
    print(acc, sum, t, halves[n - 1], r[3]);
    let reps = 0;
    let tail = 0.0;
    for rep in range(0, 300) {
        let u = rows(v, 20 + rep % 90);
        reps += len(u);
        tail += u[len(u) - 1];
    }
    print(reps, tail);
}
"""

TRAPS = """
fn work(n: int, big: int, mode: int) -> int {
    let xs: list[int] = [0] * n;
    let ys: list[int] = [1, 2, 3];
    FOR i in range(0, n) {
        let t = i;
        if i >= 400 and mode == 0 { t = big + i; }
        if i >= 600 { t = ys[10]; }
        xs[i] = t;
    }
    return xs[5];
}
fn main() {
    try { print(work(1000, 9223372036854775807, 1)); }
    except IndexError as e { print("caught", e.kind); }
    try { print(work(1000, 9223372036854775807, 0)); }
    except OverflowError as e { print("caught", e.kind); }
    print(work(1000, 9223372036854775807, 0));
}
"""

REFUSED = {
    "a running total": ("fn main() { let t = 0; parallel for i in range(0, 10) { t += i; } print(t); }",
                        "'t' is read before the body assigns it"),
    "append": ("fn main() { let xs: list[int] = []; parallel for i in range(0, 10) { xs.append(i); } }",
               "not allowed; the body may only compute values"),
    "print": ("fn main() { parallel for i in range(0, 10) { print(i); } }", "not allowed"),
    "a str": ("fn main() { let s = \"a\"; parallel for i in range(0, 10) { let t = s + \"b\"; } }",
              "only int, float and bool constants"),
    "a shifted write": ("fn main() { let xs: list[int] = [0] * 20; parallel for i in range(0, 10) { xs[i + 1] = 1; } }",
                        "differ between iterations"),
    "a read of a neighbour": ("fn main() { let xs: list[int] = [0] * 20; parallel for i in range(0, 10) { xs[i] = xs[i - 1] + 1; } }",
                              "differ between iterations"),
    "a result read after the loop": ("fn main() { let last = 0; let xs: list[int] = [0] * 20; parallel for i in range(0, 10) { last = i; xs[i] = last; } print(last); }",
                                     "private to each iteration"),
    "the loop variable after the loop": ("fn main() { let xs: list[int] = [0] * 20; parallel for i in range(0, 10) { xs[i] = 1; } print(i); }",
                                         "private to each iteration"),
    "a nested parallel for": ("fn main() { let xs: list[int] = [0] * 100; parallel for i in range(0, 10) { parallel for j in range(0, 10) { xs[i * 10 + j] = 1; } } }",
                              "cannot be nested"),
    "return": ("fn f() -> int { parallel for i in range(0, 10) { return 1; } return 0; } fn main() { print(f()); }",
               "return is not allowed"),
    "try": ("fn main() { try { parallel for i in range(0, 10) { let x = i; } } except ValueError { print(1); } }",
            "cannot be inside try"),
    "a list argument": ("fn g(xs: list[int], i: int) -> int { return xs[i]; } fn main() { let xs: list[int] = [0] * 10; let t: list[int] = [0] * 10; parallel for i in range(0, 10) { t[i] = g(xs, i); } }",
                        "parameters must be annotated int or float"),
    "recursion": ("fn f(n: int) -> int { if n <= 0 { return 0; } return f(n - 1) + 1; } fn main() { let t: list[int] = [0] * 10; parallel for i in range(0, 10) { t[i] = f(i); } }",
                  "is recursive"),
    "a step": ("fn main() { parallel for i in range(0, 10, 2) { let x = i; } }", "a step is not available"),
}


ALIAS = """
fn main() {
    let a = bytearray(100);
    let b = a;
    parallel for i in range(0, 100) {
        a[i] = i;
        let t = b[i];
    }
    print(a[5]);
}
"""

UNITS = """
fn cell(i: int, j: int) -> float { return 1.0 / float(i + j + 1); }
fn rows(v: list[float], n: int) -> list[float] {
    let r = [0.0] * n;
    parallel for i in range(0, n) {
        let s = 0.0;
        for j in range(0, n) { s += cell(i, j) * v[j]; }
        r[i] = s;
    }
    return r;
}
fn cols(v: list[float], n: int) -> list[float] {
    let r = [0.0] * n;
    parallel for i in range(0, n) {
        let s = 0.0;
        for j in range(0, n) { s += cell(j, i) * v[j]; }
        r[i] = s;
    }
    return r;
}
fn main() {
    let n = 300;
    let v: list[float] = [];
    for i in range(0, n) { v.append(1.0 + float(i % 4)); }
    let w = cols(rows(v, n), n);
    print(w[0], w[n - 1]);
}
"""


def build(directory, name, source):
    path, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "_c")
    path.write_text(source)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(path), "-o", str(exe),
                            "--debug-dir", str(debug)], capture_output=True, text=True, timeout=300)
    return built, exe, debug


def run(exe, threads):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                          env=dict(os.environ, AIL_THREADS=str(threads)))


class ParallelForTests(unittest.TestCase):
    def test_matches_the_sequential_loop_at_every_thread_count(self):
        with tempfile.TemporaryDirectory() as directory:
            built, par, debug = build(directory, "par", PROGRAM.replace("FOR", "parallel for"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            built, seq, _ = build(directory, "seq", PROGRAM.replace("FOR", "for"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            c = (debug / "program.c").read_text()
            self.assertIn("ail_par_run(", c)
            self.assertGreaterEqual(c.count("static void "), 4, "each loop became a worker function")
            expected = run(seq, 1)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(len(expected.stdout.split()), 7)
            for threads in (1, 2, 3, 16):
                got = run(par, threads)
                self.assertEqual(got.returncode, 0, got.stderr)
                self.assertEqual(got.stdout, expected.stdout, "AIL_THREADS=%d" % threads)

    def test_a_trap_is_the_one_the_sequential_loop_reaches_first(self):
        with tempfile.TemporaryDirectory() as directory:
            built, par, _ = build(directory, "par", TRAPS.replace("FOR", "parallel for"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            built, seq, _ = build(directory, "seq", TRAPS.replace("FOR", "for"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            expected = run(seq, 1)
            self.assertEqual(expected.returncode, 1)
            self.assertIn("caught OverflowError", expected.stdout)
            for threads in (1, 4, 16):
                got = run(par, threads)
                self.assertEqual((got.returncode, got.stdout, got.stderr),
                                 (expected.returncode, expected.stdout, expected.stderr), "AIL_THREADS=%d" % threads)

    def test_unsafe_bodies_are_refused_by_name(self):
        with tempfile.TemporaryDirectory() as directory:
            for number, (name, (source, message)) in enumerate(REFUSED.items()):
                with self.subTest(name):
                    built, _, _ = build(directory, "refused%d" % number, source)
                    self.assertNotEqual(built.returncode, 0, name)
                    self.assertIn("parallel for", built.stdout + built.stderr)
                    self.assertIn(message, built.stdout + built.stderr)

    def test_two_names_for_one_bytearray_are_stopped_before_the_loop_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c = build(directory, "alias", ALIAS)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = run(exe, 4)
            self.assertEqual(got.returncode, 1)
            self.assertIn("two names refer to one bytearray", got.stderr)

    def test_functions_linked_as_separate_units_share_one_pool(self):
        sys.path[:0] = [str(ROOT / "python" / "pkg-v12"), str(ROOT)]
        try:
            import pyc
            from ail_syntax import translate
            with tempfile.TemporaryDirectory() as directory:
                exe = Path(directory, "units")
                pyc.build_link_units(translate(UNITS), exe, {"rows": 1, "cols": 2, "cell": 0})
                built, whole, _ = build(directory, "whole", UNITS)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                expected = run(whole, 1)
                for threads in (1, 4, 16):
                    got = run(exe, threads)
                    self.assertEqual((got.returncode, got.stdout), (0, expected.stdout), "AIL_THREADS=%d" % threads)
        finally:
            del sys.path[:2]

    def test_programs_without_it_carry_no_thread_code(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, debug = build(directory, "plain", "fn main() { let t = 0; for i in range(0, 10) { t += i; } print(t); }")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertNotIn("ail_par", (debug / "program.c").read_text())
            self.assertNotIn("pthread", (debug / "program.c").read_text())


if __name__ == "__main__":
    unittest.main()
