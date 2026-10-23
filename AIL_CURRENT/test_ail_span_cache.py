"""A loop that only indexes a struct's numeric list fields keeps their pointers and counts in locals.

An n-body program written as a struct of parallel `list[float]` fields reloaded every field's data
pointer and count (and re-tested its bounds through a call GCC could not see past) at every element
access: 3.6x the instructions of the same program written as a list of structs. A `for` loop whose
body provably never resizes or replaces `x.f` (every use is `x.f[i]`, no call but the numeric
builtins, `x` never rebound) now loads `x.f.p` / `x.f.n` once; when every cached list has the same
length (the struct-of-arrays case) one count serves all of them. Every access stays bounds-checked
and negative indices wrap exactly as before. Loops that could resize a list keep the old code.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import os
# The C-text assertions below describe the legacy emitter; with AIL_IR set, functions in the IR's
# subset are emitted by the IR (same behaviour, different text), so only the behaviour is checked.
LEGACY_C = os.environ.get('AIL_IR', '0').strip().lower() in ('', '0', 'off', 'no')

ROOT = Path(__file__).resolve().parent

SOURCE = """
struct S { x: list[float]; v: list[float]; k: list[int]; }

fn step(s: S, n: int) -> void {
    for t in range(0, n) {
        for i in range(0, 4) {
            for j in range(i + 1, 4) {
                let d = s.x[i] - s.x[j];
                s.v[i] = s.v[i] - d * 0.5;
                s.v[j] = s.v[j] + d * 0.5;
                s.k[i] = s.k[i] + 1;
                s.k[-1] = s.k[-1] + s.k[j];
            }
        }
        for i in range(0, 4) { s.x[i] = s.x[i] + 0.1 * s.v[i]; }
    }
}

fn reach(s: S, n: int) -> float {
    let total = 0.0;
    for i in range(0, n) { total = total + s.x[i] + s.v[-1] + float(s.k[i % 4]); }
    return total;
}

fn grow(s: S, n: int) -> int {
    for i in range(0, n) { s.k.append(s.k[i] + 1); s.x[i % 2] = s.x[i % 2] + 1.0; }
    return len(s.k);
}

fn swap(s: S) -> float {
    let t = s;
    let total = 0.0;
    for i in range(0, 3) {
        t.x = [1.0, 2.0, 3.0, 4.0];
        total = total + s.x[i];
    }
    return total;
}

fn main() {
    let s = S([1.0, 2.5, -3.0, 4.25], [0.0, 0.5, 0.25, -1.0], [1, 2, 3, 4]);
    step(s, 3);
    print("%.6f %.6f %.6f %.6f" % (s.x[0], s.x[1], s.x[2], s.x[3]));
    print("%.6f %.6f %.6f %.6f" % (s.v[0], s.v[1], s.v[2], s.v[3]));
    print(s.k[0], s.k[1], s.k[2], s.k[3]);
    print("%.6f" % reach(s, 4));
    try { print("%.6f" % reach(s, 5)); } except IndexError { print("index error"); }
    print(grow(s, 3), s.k[4], s.k[5], s.k[6], "%.6f" % s.x[0]);
    print("%.6f" % swap(s));
    let u = S([1.0, 2.0, 3.0], [1.0, 2.0], [1, 2, 3]);
    try { print("%.6f" % reach(u, 2)); } except IndexError { print("index error"); }
    try { step(u, 1); print("stepped"); } except IndexError { print("index error"); }
    let e = S([], [], []);
    try { print("%.6f" % reach(e, 1)); } except IndexError { print("index error"); }
}
"""

PYTHON = """
class S:
    def __init__(self, x, v, k): self.x, self.v, self.k = x, v, k

def step(s, n):
    for t in range(n):
        for i in range(4):
            for j in range(i + 1, 4):
                d = s.x[i] - s.x[j]
                s.v[i] = s.v[i] - d * 0.5
                s.v[j] = s.v[j] + d * 0.5
                s.k[i] = s.k[i] + 1
                s.k[-1] = s.k[-1] + s.k[j]
        for i in range(4): s.x[i] = s.x[i] + 0.1 * s.v[i]

def reach(s, n):
    total = 0.0
    for i in range(n): total = total + s.x[i] + s.v[-1] + float(s.k[i % 4])
    return total

def grow(s, n):
    for i in range(n):
        s.k.append(s.k[i] + 1); s.x[i % 2] = s.x[i % 2] + 1.0
    return len(s.k)

def swap(s):
    t = s
    total = 0.0
    for i in range(3):
        t.x = [1.0, 2.0, 3.0, 4.0]
        total = total + s.x[i]
    return total

s = S([1.0, 2.5, -3.0, 4.25], [0.0, 0.5, 0.25, -1.0], [1, 2, 3, 4])
step(s, 3)
print("%.6f %.6f %.6f %.6f" % (s.x[0], s.x[1], s.x[2], s.x[3]))
print("%.6f %.6f %.6f %.6f" % (s.v[0], s.v[1], s.v[2], s.v[3]))
print(s.k[0], s.k[1], s.k[2], s.k[3])
print("%.6f" % reach(s, 4))
try: print("%.6f" % reach(s, 5))
except IndexError: print("index error")
print(grow(s, 3), s.k[4], s.k[5], s.k[6], "%.6f" % s.x[0])
print("%.6f" % swap(s))
u = S([1.0, 2.0, 3.0], [1.0, 2.0], [1, 2, 3])
try: print("%.6f" % reach(u, 2))
except IndexError: print("index error")
try:
    step(u, 1); print("stepped")
except IndexError: print("index error")
e = S([], [], [])
try: print("%.6f" % reach(e, 1))
except IndexError: print("index error")
"""


def build(directory, text):
    source, exe, debug = Path(directory, "p.ail"), Path(directory, "p"), Path(directory, "debug")
    source.write_text(text)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    return exe, (debug / "program.c").read_text()


def body_of(program, name):
    """The definition (not the prototype) of generated function `name`."""
    match = re.search(r"\n\w+ %s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


class SpanCacheTests(unittest.TestCase):
    def test_matches_cpython_and_hoists_only_where_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(directory, SOURCE)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            # step and reach only ever index the fields -> cached; grow appends to k and swap
            # rebinds t.x (which may be the same struct) -> not cached
            step = body_of(program, "step")
            if LEGACY_C:
                self.assertIn("_sp", step)
                self.assertIn("view_get", step)
                self.assertIn("view_set", step)
                self.assertIn("view_get", body_of(program, "reach"))
                self.assertNotIn("view_", body_of(program, "grow"))
                self.assertNotIn("view_", body_of(program, "swap"))

    def test_unequal_lengths_take_the_per_list_path(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(directory, SOURCE)
            if LEGACY_C:
                self.assertIn("_eq", program)
                self.assertIn("if (_sc", program)

    def test_uncaught_index_error_matches_before(self):
        text = """
struct S { x: list[float]; y: list[float]; }
fn run(s: S) -> float {
    let t = 0.0;
    for i in range(0, 5) { t = t + s.x[i] * s.y[i]; }
    return t;
}
fn main() {
    let s = S([1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 1.0, 1.0]);
    print("%.1f" % run(s));
}
"""
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(directory, text)
            self.assertIn("view_get", program)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertNotEqual(ran.returncode, 0)
            self.assertEqual(ran.stdout, "")
            self.assertIn("index", ran.stderr.lower())


# These tests pin the C text of the legacy emitter, the AIL_IR=0 opt-out (the IR is the default since
# 2026-10-19 and has its own text, pinned in test_ail_ir_*): the whole module builds with AIL_IR=0
# unless the caller set AIL_IR.
_SAVED_AIL_IR = []


def setUpModule():
    import os as _os
    _SAVED_AIL_IR.append(_os.environ.get('AIL_IR'))
    if _SAVED_AIL_IR[-1] is None:
        _os.environ['AIL_IR'] = '0'


def tearDownModule():
    import os as _os
    if _SAVED_AIL_IR.pop() is None:
        _os.environ.pop('AIL_IR', None)


if __name__ == "__main__":
    unittest.main()
