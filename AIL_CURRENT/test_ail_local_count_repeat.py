"""A local int as the count of a list repeat (let n = 5; [0] * n) matches CPython, negative counts included.

Regression: the numeric-binding lowering took the whole expression for scalar arithmetic as soon as
one operand was a numeric local, and refused with "numeric binding requires a number".
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
fn main() {
    let n = 5;
    let m = -3;
    let z = 0;
    let k = 2;
    let xs = [0] * n;
    let ys = [1.5] * m;
    let ws = n * [7];
    let zs = [0] * z;
    let ss = "ab" * k;
    let ts = [0] * (n + k);
    let us = [2.5] * (k - n);
    n = n + 1;
    xs[n - 2] = 9;
    print(len(xs), xs[4], len(ys), len(ws), ws[3], len(zs), ss, len(ts), len(us), n);
}
"""

PYTHON = """
n = 5; m = -3; z = 0; k = 2
xs = [0] * n; ys = [1.5] * m; ws = n * [7]; zs = [0] * z; ss = "ab" * k
ts = [0] * (n + k); us = [2.5] * (k - n)
n = n + 1
xs[n - 2] = 9
print(len(xs), xs[4], len(ys), len(ws), ws[3], len(zs), ss, len(ts), len(us), n)
"""


class LocalCountRepeatTests(unittest.TestCase):
    def test_local_count_matches_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            source, exe = Path(directory, "p.ail"), Path(directory, "p")
            source.write_text(SOURCE)
            built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source), "-o", str(exe)],
                                   capture_output=True, text=True, timeout=300)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0)
            self.assertEqual(ran.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()
