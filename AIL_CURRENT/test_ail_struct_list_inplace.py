"""Struct-field list operations on a plain struct name run in place and match CPython.

Regression: every `h.keys[i]`, `h.keys[i] = v`, `h.keys.append(v)`, `h.keys.pop()` and `len(h.keys)`
retained and released the struct around the access and kept a cleanup-frame slot for it (a binary
heap kept in a struct spent most of its instructions on that). Also covers the fast paths of the
field-list helpers, loops that allocate no strings (no arena checkpoint), a list returned by a
function passed straight to a struct constructor, and `[0] * n` with a local count.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
struct Heap { keys: list[int]; vals: list[int]; top: int; }
struct G { head: list[int]; to: list[int]; }

fn mk(n: int, v: int) -> list[int] {
    let a = [0] * n;
    if v != 0 {
        for i in range(n) { a[i] = v; }
    }
    return a;
}

fn hpush(h: Heap, k: int, v: int) -> void {
    h.keys.append(k);
    h.vals.append(v);
    let i = len(h.keys) - 1;
    while i > 0 {
        let p = (i - 1) // 2;
        if h.keys[p] <= k { break; }
        h.keys[i] = h.keys[p];
        h.vals[i] = h.vals[p];
        i = p;
    }
    h.keys[i] = k;
    h.vals[i] = v;
}

fn hpop(h: Heap) -> void {
    h.top = h.keys[0];
    let lk = h.keys.pop();
    let lv = h.vals.pop();
    let n = len(h.keys);
    if n == 0 { return; }
    let i = 0;
    let c = 1;
    while c < n {
        if c + 1 < n and h.keys[c + 1] < h.keys[c] { c += 1; }
        if h.keys[c] >= lk { break; }
        h.keys[i] = h.keys[c];
        h.vals[i] = h.vals[c];
        i = c;
        c = 2 * i + 1;
    }
    h.keys[i] = lk;
    h.vals[i] = lv;
}

fn grow(h: Heap) -> int {
    for i in range(0, 100) { h.keys.append(i); }
    return len(h.keys);
}

fn parse(d: bytes, n: int) -> int {
    let i = 0;
    let v = 0;
    let total = 0;
    while i < n {
        let c = d[i];
        if c >= 48 and c <= 57 { v = v * 10 + (c - 48); }
        else { total += v; v = 0; }
        i += 1;
    }
    return total + v;
}

fn run() -> int {
    let raw = read_bytes(sys.argv[1]);
    print(parse(raw, len(raw)));
    let h = Heap([], [], 0);
    let seed = 7;
    for t in range(0, 40) {
        seed = (seed * 31 + 11) % 101;
        hpush(h, seed, t);
    }
    let out: list[int] = [];
    while len(h.keys) > 0 {
        hpop(h);
        out.append(h.top);
    }
    print(len(out), out[0], out[39], out[20]);
    h.keys.append(grow(h));
    print(len(h.keys), h.keys[100], h.keys[-1], h.keys[-101]);
    let g = G(mk(5, -1), mk(4, 3));
    g.head[2] = g.head[1] + 7;
    g.to[-1] = g.to[0] * 2;
    print(g.head[0], g.head[2], g.to[3], len(g.to));
    let m = [0] * len(g.to);
    m[1] = 5;
    print(m[0] + m[1], len(m));
    let e = Heap([], [], 0);
    try { e.keys.pop(); }
    except IndexError as x { print("pop empty"); }
    try { e.keys[0] = 1; }
    except IndexError as x { print("set empty"); }
    e.keys.append(4);
    try { print(e.keys[1]); }
    except IndexError as x { print("get past end"); }
    print(e.keys[-1], e.keys.pop(), len(e.keys));
    let s = 0;
    let acc = [0, 0, 0];
    for j in range(0, 10) {
        acc[j % 3] += j * 2;
        s += acc[j % 3];
    }
    print(s, acc[0], acc[1], acc[2]);
    return 0;
}

fn main() {
    try { return run(); }
    except (ValueError, IndexError, OSError) as e { return 1; }
}
"""

PYTHON = """
import sys
class Heap:
    def __init__(self): self.keys = []; self.vals = []; self.top = 0
def hpush(h, k, v):
    h.keys.append(k); h.vals.append(v)
    i = len(h.keys) - 1
    while i > 0:
        p = (i - 1) // 2
        if h.keys[p] <= k: break
        h.keys[i] = h.keys[p]; h.vals[i] = h.vals[p]; i = p
    h.keys[i] = k; h.vals[i] = v
def hpop(h):
    h.top = h.keys[0]
    lk = h.keys.pop(); lv = h.vals.pop()
    n = len(h.keys)
    if n == 0: return
    i = 0; c = 1
    while c < n:
        if c + 1 < n and h.keys[c + 1] < h.keys[c]: c += 1
        if h.keys[c] >= lk: break
        h.keys[i] = h.keys[c]; h.vals[i] = h.vals[c]; i = c; c = 2 * i + 1
    h.keys[i] = lk; h.vals[i] = lv
def grow(h):
    for i in range(100): h.keys.append(i)
    return len(h.keys)
def parse(d, n):
    i = 0; v = 0; total = 0
    while i < n:
        c = d[i]
        if 48 <= c <= 57: v = v * 10 + (c - 48)
        else: total += v; v = 0
        i += 1
    return total + v
raw = open(sys.argv[1], 'rb').read()
print(parse(raw, len(raw)))
h = Heap(); seed = 7
for t in range(40):
    seed = (seed * 31 + 11) % 101
    hpush(h, seed, t)
out = []
while len(h.keys) > 0:
    hpop(h); out.append(h.top)
print(len(out), out[0], out[39], out[20])
size = grow(h)
h.keys.append(size)
print(len(h.keys), h.keys[100], h.keys[-1], h.keys[-101])
head = [-1] * 5; to = [3] * 4
head[2] = head[1] + 7
to[-1] = to[0] * 2
print(head[0], head[2], to[3], len(to))
m = [0] * len(to); m[1] = 5
print(m[0] + m[1], len(m))
e = Heap()
try: e.keys.pop()
except IndexError: print("pop empty")
try: e.keys[0] = 1
except IndexError: print("set empty")
e.keys.append(4)
try: print(e.keys[1])
except IndexError: print("get past end")
print(e.keys[-1], e.keys.pop(), len(e.keys))
s = 0; acc = [0, 0, 0]
for j in range(10):
    acc[j % 3] += j * 2
    s += acc[j % 3]
print(s, acc[0], acc[1], acc[2])
"""

DATA = b"12 345,6789 0\n77 x 5"


class StructListInPlaceTests(unittest.TestCase):
    def test_matches_cpython_and_skips_the_owner_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            source, exe, data = Path(directory, "p.ail"), Path(directory, "p"), Path(directory, "d.bin")
            debug = Path(directory, "debug")
            source.write_text(SOURCE)
            data.write_bytes(DATA)
            built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                                    "-o", str(exe), "--debug-dir", str(debug)],
                                   capture_output=True, text=True, timeout=300)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            program = (debug / "program.c").read_text()
            start = program.index("void hpush(ail_obj_Heap *v_h, int64_t v_k, int64_t v_v) {")
            end = program.index("int64_t py_parse(", start) if "int64_t py_parse(" in program else start + 6000
            hot = program[start:end]
            self.assertNotIn("ail_obj_store_Heap(&", hot)
            ran = subprocess.run([str(exe), str(data)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", PYTHON, str(data)], capture_output=True,
                                      text=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()
