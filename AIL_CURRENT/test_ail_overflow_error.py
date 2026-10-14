"""int64 overflow raises a catchable OverflowError once a program names it; wrapping_add/sub/mul wrap.

Before, overflow always ended the program, so one missed range check in an LLM-written calculator
killed every later line (experiment 3, calc-ail). Programs that never name OverflowError keep
their generated C byte for byte; uncaught overflow still exits 1.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CAUGHT = """
const MAXV = 9223372036854775807;

fn mul(a: int, b: int) -> int { return a * b; }

fn eval(op: int, a: int, b: int) -> str {
    try {
        if op == 0 { return str(a + b); }
        if op == 1 { return str(a - b); }
        if op == 2 { return str(mul(a, b)); }
        if op == 3 { return str(-a); }
        if op == 4 { return str(a // b); }
        return str(a << b);
    }
    except OverflowError { return "overflow"; }
    except ZeroDivisionError { return "zero"; }
}

fn main() {
    let mn = -MAXV - 1;
    print(eval(0, MAXV, 1), eval(0, MAXV, -1), eval(1, mn, 1), eval(2, 3037000500, 3037000500));
    print(eval(2, -3, 4), eval(3, mn, 0), eval(3, 5, 0), eval(4, mn, -1), eval(4, 7, 0));
    print(eval(5, 1, 63), eval(5, 1, 62));
    let total = 0;
    let lines = 0;
    for v in [MAXV, 1, -5, 7] {
        try { total = total + v; lines += 1; }
        except OverflowError as e { print("caught", e.kind); }
    }
    print(total, lines);
    try { assert total == 0, "not zero"; }
    except AssertionError as e { print("assert", e.message); }
    try { raise OverflowError("custom"); }
    except OverflowError as e { print(e.kind, e.message); }
}
"""

EXPECTED = """overflow 9223372036854775806 overflow overflow
-12 overflow -5 overflow zero
overflow 4611686018427387904
caught OverflowError
caught OverflowError
9223372036854775802 2
assert not zero
OverflowError custom
"""

UNCAUGHT = """
fn main() {
    let x = 9223372036854775807;
    try { print(x // 1); }
    except OverflowError { print("unreached"); }
    print(x + 1);
}
"""


WRAPPING = """
fn fnv(s: str) -> int {
    let x = -3750763034362895579;
    for c in s { x = wrapping_mul(x ^ ord(c), 1099511628211); }
    return x;
}
fn main() {
    print(wrapping_add(9223372036854775807, 1), wrapping_sub(-9223372036854775807 - 1, 1), wrapping_mul(3037000500, 3037000500));
    print(fnv("hello"), fnv(""));
    let acc = 0;
    for i in range(0, 1000) { acc = wrapping_add(wrapping_mul(acc, 6364136223846793005), 1442695040888963407); }
    print(acc);
}
"""

WRAPPING_PYTHON = """
def w(v):
    v &= (1 << 64) - 1
    return v - (1 << 64) if v >= 1 << 63 else v
def fnv(s):
    x = -3750763034362895579
    for c in s: x = w((x ^ ord(c)) * 1099511628211)
    return x
print(w(2**63), w(-2**63 - 1), w(3037000500**2))
print(fnv("hello"), fnv(""))
acc = 0
for i in range(1000): acc = w(acc * 6364136223846793005 + 1442695040888963407)
print(acc)
"""


def build(directory, name, source):
    path, exe = Path(directory, name + ".ail"), Path(directory, name)
    path.write_text(source)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(path), "-o", str(exe)],
                           capture_output=True, text=True, timeout=300)
    return built, exe


class OverflowErrorTests(unittest.TestCase):
    def test_overflow_is_catchable(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe = build(directory, "caught", CAUGHT)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, EXPECTED)

    def test_uncaught_overflow_still_exits_1(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe = build(directory, "uncaught", UNCAUGHT)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 1)
            self.assertEqual(ran.stdout, "9223372036854775807\n")
            self.assertIn("integer overflow", ran.stderr)

    def test_wrapping_ops_match_twos_complement(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe = build(directory, "wrapping", WRAPPING)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", WRAPPING_PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()
