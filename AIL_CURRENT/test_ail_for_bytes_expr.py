"""`for b in <bytes expression>`, `ba[i] += v` on a bytearray, and `return [0] * n` from `-> list[int]`."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
fn zeros(n: int) -> list[int] { return [0] * n; }
fn fzeros(n: int) -> list[float] { return [0.0] * n; }
fn main() {
    let db = b"acgtacgt";
    let n = 0;
    for b in db[2:6] { n += b; }
    for b in b"acgt" { n += b; }
    for c in "xyz".encode() { n += c; }
    for c in "h\\u00e9\\u00e9".encode() { n += c; }
    print(n);
    let ba = bytearray();
    ba.append(5); ba.append(250);
    ba[0] += 7;
    ba[0] -= 2;
    ba[0] *= 3;
    ba[1] //= 5;
    ba[1] |= 1;
    print(ba[0], ba[1]);
    try { ba[0] += 250; } except ValueError { print("range"); }
    print(ba[0]);
    let z = zeros(3);
    let f = fzeros(2);
    print(len(z), z[2], len(f), f[1]);
}
"""

PYTHON = """
db = b"acgtacgt"
n = 0
for b in db[2:6]: n += b
for b in b"acgt": n += b
for c in "xyz".encode(): n += c
for c in "h\\u00e9\\u00e9".encode(): n += c
print(n)
ba = bytearray([5, 250])
ba[0] += 7; ba[0] -= 2; ba[0] *= 3; ba[1] //= 5; ba[1] |= 1
print(ba[0], ba[1])
try:
    ba[0] += 250
except ValueError:
    print("range")
print(ba[0])
print(3, 0, 2, 0.0)
"""


class SmallGapTests(unittest.TestCase):
    def test_matches_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            src, exe = Path(directory, "p.ail"), Path(directory, "p")
            src.write_text(SOURCE)
            built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(src), "-o", str(exe)],
                                   capture_output=True, text=True, timeout=600)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()
