"""IR coverage of two `main` shapes that stayed on the legacy emitter (design IR_OWNERSHIP_DESIGN_v2.md section 23).

* A struct local's field list taken into a local and the field rebound before anything reads it
  (`tmp = g.cur; g.cur = g.nxt; g.nxt = tmp`, a grid swap) is three moves (Rule M take), as for a struct
  parameter; `bs = r.bs` from a struct local that is not reassigned while `bs` is used is a field borrow
  (Rule B). The loads of a struct local that no instruction in a loop names are hoisted, so its field
  lists get spans.
* `b = a` for bytearrays (`ba.copyref`): one object with two names, as in Python and the legacy path.

The checks: results equal CPython's in AIL_IR=0, 1 and verify for the grid shape (Python syntax: CPython is
the oracle), for bytearray aliasing (a write through either name is seen through the other, a parameter
shared into a local, a swap, self-assignment), and for the shapes that must stay correct whichever path
takes them: a field read between the take and the rebinding, a struct local reassigned while a borrow of
its field is in use, a struct local given an object only in a branch before a loop that may run no
iteration. The brace-syntax grid (value semantics) agrees in AIL_IR=0, 1 and verify. `main` is on the IR
where it should be.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

GRID = '''
import sys


class Grid:
    def __init__(self, cur: list[int], nxt: list[int]):
        self.cur = cur
        self.nxt = nxt


class Rule:
    def __init__(self, b: list[int], s: list[int]):
        self.b = b
        self.s = s


def main() -> int:
    w = 13
    h = 9
    gens = int(sys.argv[1])
    ru = Rule([0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1], [0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0])
    bs = ru.b
    ss = ru.s
    gr = Grid([0 for i in range(w * h)], [0 for i in range(w * h)])
    seed = 99
    for i in range(w * h):
        seed = (seed * 1103515245 + 12345) % 2147483648
        if seed % 5 < 2:
            gr.cur[i] = 1
    for g in range(gens):
        na = 0
        ns = 0
        for y in range(h):
            u = ((y + h - 1) % h) * w
            m = y * w
            d = ((y + 1) % h) * w
            for x in range(w):
                l = (x + w - 1) % w
                r = (x + 1) % w
                wt = 0
                if gr.cur[u + x] == 1:
                    wt += 2
                if gr.cur[d + x] == 1:
                    wt += 2
                if gr.cur[m + l] == 1:
                    wt += 2
                if gr.cur[m + r] == 1:
                    wt += 2
                if gr.cur[u + l] == 1:
                    wt += 1
                if gr.cur[d + r] == 1:
                    wt += 1
                s = gr.cur[m + x]
                t = 0
                if s == 1:
                    if ss[wt] == 1:
                        t = 1
                        na += 1
                    else:
                        t = 2
                        ns += 1
                elif s == 0:
                    if bs[wt] == 1:
                        t = 1
                        na += 1
                gr.nxt[m + x] = t
        tmp = gr.cur
        gr.cur = gr.nxt
        gr.nxt = tmp
        print(g, na, ns)
    code = 0
    for i in range(w * h):
        code = (code * 3 + gr.cur[i]) % 1000000007
    print(code)
    print(len(gr.cur), len(gr.nxt), gr.nxt[0] + gr.nxt[w * h - 1])
    return 0


main()
'''

# the same grid in the brace syntax (value semantics: the swap is still three moves)
GRID_BRACE = '''
struct Gr { cur: list[int]; nxt: list[int]; }
struct Rules { b: list[int]; s: list[int]; }

fn main() {
    let gens = int(sys.argv[1]);
    let w = 11;
    let h = 7;
    let ru = Rules([0,0,0,1,0,0,1,0,0,0,0,0,1], [0,0,1,1,0,1,0,0,1,0,0,1,0]);
    let bs = ru.b;
    let gr = Gr([0 for i in range(w * h)], [0 for i in range(w * h)]);
    let seed = 7;
    for i in range(w * h) {
        seed = (seed * 1103515245 + 12345) % 2147483648;
        if seed % 3 == 0 { gr.cur[i] = 1; }
    }
    for g in range(gens) {
        let na = 0;
        for y in range(h) {
            for x in range(w) {
                let wt = 0;
                if gr.cur[((y + h - 1) % h) * w + x] == 1 { wt += 2; }
                if gr.cur[((y + 1) % h) * w + x] == 1 { wt += 2; }
                if gr.cur[y * w + (x + 1) % w] == 1 { wt += 1; }
                let t = 0;
                if gr.cur[y * w + x] == 1 {
                    if ru.s[wt] == 1 { t = 1; na += 1; }
                } elif bs[wt] == 1 { t = 1; na += 1; }
                gr.nxt[y * w + x] = t;
            }
        }
        let tmp = gr.cur; gr.cur = gr.nxt; gr.nxt = tmp;
        print(f"{g} {na}");
    }
    let total = 0;
    for i in range(w * h) { total += gr.cur[i] * (i + 1); }
    print(total);
    return 0;
}
'''

# Bytearray names in the brace syntax (the Python syntax refuses a second name that is written while the
# other is read, so the oracle is the Python twin below, run by CPython): a write through either name is
# seen through the other, a rebinding leaves the other name alone, a swap, a self-assignment, a parameter
# taken into a local.
BYTEARRAYS = '''
fn fill(b: bytearray, n: int) -> int {
    let c = b;
    for i in range(n) { c.append(65 + i % 26); }
    return len(b);
}

fn main() {
    let n = int(sys.argv[1]);
    let a = bytearray(n);
    let b = a;
    b[0] = 66;
    b.append(67);
    print(f"{a[0]} {len(a)} {len(b)}");
    a = bytearray(3);
    print(f"{len(a)} {len(b)} {b[0]}");
    let cur = bytearray(n);
    let nxt = bytearray(n);
    for i in range(n) { cur[i] = i % 3; }
    for g in range(5) {
        for i in range(n) { nxt[i] = (cur[i] + cur[(i + 1) % n] + g) % 4; }
        let tmp = cur;
        cur = nxt;
        nxt = tmp;
    }
    let total = 0;
    for i in range(n) { total = total * 7 + cur[i] - nxt[i]; }
    print(total);
    cur = cur;
    let f = fill(cur, 4);
    print(f"{len(cur)} {f} {len(nxt)}");
    let x = cur;
    cur = nxt;
    x.append(9);
    print(f"{len(x)} {len(cur)} {x[len(x) - 1]}");
    return 0;
}
'''

BYTEARRAYS_PY = '''
import sys


def fill(b, n):
    c = b
    for i in range(n):
        c.append(65 + i % 26)
    return len(b)


n = int(sys.argv[1])
a = bytearray(n)
b = a
b[0] = 66
b.append(67)
print(f"{a[0]} {len(a)} {len(b)}")
a = bytearray(3)
print(f"{len(a)} {len(b)} {b[0]}")
cur = bytearray(n)
nxt = bytearray(n)
for i in range(n):
    cur[i] = i % 3
for g in range(5):
    for i in range(n):
        nxt[i] = (cur[i] + cur[(i + 1) % n] + g) % 4
    tmp = cur
    cur = nxt
    nxt = tmp
total = 0
for i in range(n):
    total = total * 7 + cur[i] - nxt[i]
print(total)
cur = cur
f = fill(cur, 4)
print(f"{len(cur)} {f} {len(nxt)}")
x = cur
cur = nxt
x.append(9)
print(f"{len(x)} {len(cur)} {x[len(x) - 1]}")
'''

# Shapes the sharing rules must keep correct whichever path takes them (brace syntax, value semantics: the
# legacy build is the reference): a field read between the take and the rebinding, a list appended to after
# the swap, a struct local reassigned while a name for its field list is in use, a struct local given an
# object only in a branch before a loop that may run no iteration, and a second name for the struct.
EDGES = '''
struct Gr { cur: list[int]; nxt: list[int]; }

fn main() {
    let k = int(sys.argv[1]);
    let g = Gr([1, 2, 3], [4, 5]);
    let tmp = g.cur;
    print(f"{len(g.cur)} {len(tmp)}");
    g.cur = g.nxt;
    g.nxt = tmp;
    print(f"{len(g.cur)} {g.cur[0]} {len(g.nxt)} {g.nxt[0]} {len(tmp)}");
    tmp.append(6);
    print(f"{len(g.nxt)} {len(tmp)}");
    let h = Gr([7, 8], [9]);
    let bs = h.cur;
    h = Gr([10], [11]);
    print(f"{bs[0]} {len(bs)} {h.cur[0]}");
    let p = Gr([0], [0]);
    if k > 0 { p = Gr([5 for i in range(k)], [0]); }
    let t = 0;
    for i in range(k) { t += p.cur[i]; }
    print(t);
    let q = g;
    let tmp2 = g.cur;
    g.cur = q.nxt;
    g.nxt = tmp2;
    print(f"{len(g.cur)} {g.cur[0]} {len(g.nxt)} {g.nxt[0]} {len(q.cur)}");
    let r = Gr([1], [2]);
    for i in range(k) {
        let u = r.cur;
        r.cur = r.nxt;
        r.nxt = u;
        r.cur.append(i);
    }
    print(f"{len(r.cur)} {len(r.nxt)} {r.cur[0]} {r.nxt[0]}");
    return 0;
}
'''


def compile_exe(directory, text, name, ir, stats=None, syntax="python"):
    source = Path(directory, name + ".ail")
    source.write_text(text)
    exe = Path(directory, "%s_%s" % (name, ir))
    env = dict(os.environ, AIL_IR=ir)
    env.pop("AIL_IR_STATS", None)
    env.pop("AIL_IR_PASSES", None)
    env["AIL_NO_CACHE"] = "1"       # a cache hit would not write the stats
    if stats:
        env["AIL_IR_STATS"] = str(stats)
    cmd = [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source), "-o", str(exe)]
    if syntax:
        cmd += ["--syntax", syntax]
    built = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
    return built, exe


class IRCoverTests(unittest.TestCase):
    def check_oracle(self, text, name, runs):
        with tempfile.TemporaryDirectory() as directory:
            expected = [subprocess.run([sys.executable, "-c", text, *args], capture_output=True, text=True, timeout=120)
                        for args in runs]
            for ir in ("0", "1", "verify"):
                built, exe = compile_exe(directory, text, name, ir)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                for args, want in zip(runs, expected):
                    with self.subTest(ir=ir, args=args):
                        ran = subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=120)
                        self.assertEqual(ran.stdout, want.stdout)
                        self.assertEqual(ran.returncode, want.returncode, ran.stderr)

    def stats(self, text, name, syntax="python"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "stats.jsonl")
            built, _exe = compile_exe(directory, text, name, "1", path, syntax)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        return {r["fn"]: r for r in rows}

    def test_grid_swap_matches_cpython(self):
        self.check_oracle(GRID, "grid", (("0",), ("1",), ("6",)))

    def test_grid_main_is_lowered_with_moves_and_spans(self):
        row = self.stats(GRID, "grid")["main"]
        self.assertEqual(row["path"], "ir", row.get("reason"))
        self.assertGreaterEqual(row["sharing"]["takes"], 2)
        self.assertGreaterEqual(row["sharing"]["field_borrows"], 2)
        self.assertGreaterEqual(row["passes"]["spans"], 1)

    def test_brace_grid_agrees_in_every_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            outs = {}
            for ir in ("0", "1", "verify"):
                built, exe = compile_exe(directory, GRID_BRACE, "gridb", ir, syntax=None)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                outs[ir] = [subprocess.run([str(exe), n], capture_output=True, text=True, timeout=60)
                            for n in ("0", "1", "5")]
            for ir in ("1", "verify"):
                for a, b in zip(outs["0"], outs[ir]):
                    self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout), ir)
            self.assertIn("4 ", outs["0"][2].stdout)
        row = self.stats(GRID_BRACE, "gridb", syntax=None)["main"]
        self.assertEqual(row["path"], "ir", row.get("reason"))

    def modes_agree(self, text, name, runs, oracle=None):
        """Brace syntax: every mode gives the legacy build's stdout and exit code (and, with `oracle`,
        the stdout and exit code CPython gives for the Python twin)."""
        with tempfile.TemporaryDirectory() as directory:
            outs = {}
            for ir in ("0", "1", "verify"):
                built, exe = compile_exe(directory, text, name, ir, syntax=None)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                outs[ir] = [subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=60)
                            for args in runs]
            for ir in ("1", "verify"):
                for args, a, b in zip(runs, outs["0"], outs[ir]):
                    with self.subTest(ir=ir, args=args):
                        self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))
            if oracle is not None:
                for args, a in zip(runs, outs["0"]):
                    want = subprocess.run([sys.executable, "-c", oracle, *args], capture_output=True, text=True,
                                          timeout=60)
                    self.assertEqual((a.returncode, a.stdout), (want.returncode, want.stdout), args)
        return outs["0"]

    def test_bytearray_names_share_one_object(self):
        self.modes_agree(BYTEARRAYS, "bas", (("1",), ("6",)), BYTEARRAYS_PY)
        row = self.stats(BYTEARRAYS, "bas", syntax=None)
        self.assertEqual(row["main"]["path"], "ir", row["main"].get("reason"))
        self.assertEqual(row["fill"]["path"], "ir", row["fill"].get("reason"))

    def test_sharing_edges_agree_with_legacy(self):
        outs = self.modes_agree(EDGES, "edges", (("0",), ("3",)))
        self.assertEqual(outs[1].stdout.splitlines()[2], "3 4", outs[1].stdout)   # value semantics: tmp is its own
        self.assertEqual(outs[1].stdout.splitlines()[3], "7 2 10")


if __name__ == "__main__":
    unittest.main()
