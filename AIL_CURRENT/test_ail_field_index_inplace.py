"""A struct-field list indexed by integer arithmetic (st.xs[base + j]) reads in place and matches CPython.

Regression: only a bare name or constant index read the field in place; any other index copied the
whole list first, so a loop over st.xs[i * n + k] was quadratic (an LLM-written matmul took over
300 s instead of 2 s).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
struct S { xs: list[int]; fs: list[float]; }

fn main() {
    let st = S([], []);
    for i in range(0, 12) { st.xs.append(i * i); st.fs.append(i * 0.5); }
    let n = 3;
    let total = 0;
    let ftotal = 0.0;
    for i in range(0, 4) {
        let base = i * n;
        for j in range(0, n) {
            total += st.xs[base + j] * (j + 1);
            ftotal += st.fs[base + j];
        }
    }
    print(total, ftotal, st.xs[-n], st.xs[(n << 1) % 5], st.fs[-(n - 1)], st.xs[n * n & 7 | 1 ^ 2]);
    try { print(st.xs[n * 10]); }
    except IndexError as e { print("index error"); }
}
"""

PYTHON = """
xs = [i * i for i in range(12)]; fs = [i * 0.5 for i in range(12)]
n = 3; total = 0; ftotal = 0.0
for i in range(4):
    base = i * n
    for j in range(n):
        total += xs[base + j] * (j + 1)
        ftotal += fs[base + j]
print(total, ftotal, xs[-n], xs[(n << 1) % 5], fs[-(n - 1)], xs[n * n & 7 | 1 ^ 2])
try:
    print(xs[n * 10])
except IndexError:
    print("index error")
"""


class FieldIndexInPlaceTests(unittest.TestCase):
    def test_matches_cpython_without_copying_the_field(self):
        with tempfile.TemporaryDirectory() as directory:
            source, exe = Path(directory, "p.ail"), Path(directory, "p")
            debug = Path(directory, "debug")
            source.write_text(SOURCE)
            built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                                    "-o", str(exe), "--debug-dir", str(debug)],
                                   capture_output=True, text=True, timeout=300)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            program = (debug / "program.c").read_text()
            self.assertNotIn("->f_xs; ail_list _copy", program)
            self.assertNotIn("->f_fs; ail_flist _copy", program)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()
