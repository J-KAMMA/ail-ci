"""Deleting from a large dict or set costs O(1), and indexing a field list by a field read copies nothing.

Two LLM-written programs for new tasks passed every test and still timed out (2026-10-13):

* A ticket audit refunded 195k of 2.6M sales from a `dict[str, int]`: every `del` shifted the whole
  insertion-ordered entry array down and renumbered every hash slot, so the run was quadratic
  (> 120 s against 0.86 s for C). Every typed table had the same `del` -- str-keyed dicts and sets
  (`ail_stab`, with the str/bytes/float-valued dicts built on it) and int-keyed ones (`ail_tab`).
  A deletion now leaves a hole that the next walk of the insertion order closes in one pass.
* A tree fold ran `t.sub[t.par[i]] += t.sub[i]` over 3M nodes. An index that was itself a field read
  counted as impure, so every evaluation copied all of `t.sub` first (> 120 s, 940 MB). Reading an
  int list element by a pure index runs no code and changes no list, so it is pure too.

The holes must be invisible: insertion order, re-insertion moving a key to the end, `pop`, copies,
`sorted`, set algebra and every iteration form must give exactly CPython's results.
"""
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
struct Box { d: dict[str, int]; }

fn churn_sdict(n: int) -> int {
    let d: dict[str, int] = {};
    let acc = 0;
    for i in range(0, n) {
        d[str(i)] = i;
        if i % 3 == 1 and str(i - 1) in d { del d[str(i - 1)]; }
        if i % 7 == 0 and str(i // 2) in d { acc += d.pop(str(i // 2)); }
        if i % 50 == 0 { for k in d { acc += len(k); } }
    }
    for k, v in d.items() { acc = acc * 31 % 1000000007 + v + len(k); }
    let keys = sorted(d);
    print(len(d), len(keys), keys[0], keys[len(keys) - 1]);
    d["5"] = 99;
    del d["2"];
    d["2"] = 7;
    let s = 0;
    for v in d.values() { s = s * 7 % 1000003 + v; }
    print(s);
    return acc;
}

fn churn_field(b: Box, n: int) -> int {
    for i in range(0, n) {
        b.d[str(i % 97)] = i;
        if i % 2 == 0 and str((i * 7) % 97) in b.d { del b.d[str((i * 7) % 97)]; }
    }
    let t = 0;
    for k in b.d.keys() { t = t * 13 % 1000003 + len(k) + b.d[k]; }
    return t;
}

fn churn_smap(n: int) -> str {
    let d: dict[str, str] = {};
    for i in range(0, n) {
        d[str(i % 41)] = "v" + str(i);
        if i % 3 == 0 and str((i * 5) % 41) in d { del d[str((i * 5) % 41)]; }
    }
    let out = "";
    for k, v in d.items() { out = out + k + "=" + v + ","; }
    let c = d.copy();
    let ck = c.keys();
    del c[ck[0]];
    c["new"] = "x";
    return out + "|" + str(len(c)) + "|" + str(len(d));
}

fn churn_fdict(n: int) -> float {
    let d: dict[str, float] = {};
    for i in range(0, n) {
        d[str(i % 29)] = float(i) * 0.5;
        if i % 4 == 0 and str((i * 3) % 29) in d { del d[str((i * 3) % 29)]; }
    }
    let t = 0.0;
    for v in d.values() { t = t * 0.5 + v; }
    return t;
}

fn churn_sset(n: int) -> int {
    let s = set();
    for i in range(0, n) {
        s.add(str(i % 53));
        if i % 2 == 1 { s.discard(str((i * 11) % 53)); }
    }
    let t = 0;
    for k in s { t = t * 17 % 1000003 + int(k); }
    return t * 100 + len(s);
}

fn churn_bmap(n: int) -> int {
    let d: dict[str, bytes] = {};
    for i in range(0, n) {
        d[str(i % 37)] = b"ab" * (i % 5 + 1);
        if i % 3 == 2 and str((i * 7) % 37) in d { del d[str((i * 7) % 37)]; }
    }
    let t = 0;
    for k in d.keys() { t = t * 19 % 1000003 + int(k) * 10 + len(d[k]); }
    return t * 100 + len(d);
}

fn run_int(seed: int, n: int, span: int) -> int {
    let d = {};
    let s = set();
    let x = seed;
    let acc = 0;
    for i in range(0, n) {
        x = (x * 1103515245 + 12345) % 2147483648;
        let k = x % span;
        let op = (x // 7) % 10;
        if op < 4 { d[k] = i; s.add(k); }
        elif op < 7 {
            if k in d { del d[k]; }
            s.discard(k);
        } elif op == 7 {
            for kk in d { acc = (acc * 3 + kk) % 1000003; }
            for kk in s { acc = (acc * 5 + kk) % 1000003; }
        } elif op == 8 {
            if k in d { acc = (acc + d.pop(k)) % 1000003; d[k] = acc; }
        } else {
            for kk, vv in d.items() { acc = (acc * 7 + kk + vv) % 1000003; }
        }
    }
    let u = set();
    for i in range(0, 1500) { u.add(i * 2); }
    for kk in s & u { acc = (acc * 3 + kk) % 1000003; }
    for kk in s - u { acc = (acc * 5 + kk) % 1000003; }
    for kk in s | u { acc = (acc * 7 + kk) % 1000003; }
    for kk in d { acc = (acc * 3 + kk) % 1000003; }
    return acc * 10000 + len(d) * 10 + len(s) % 10;
}

fn run_str(seed: int, n: int, span: int) -> int {
    let d: dict[str, int] = {};
    let m: dict[str, str] = {};
    let x = seed;
    let acc = 0;
    for i in range(0, n) {
        x = (x * 1103515245 + 12345) % 2147483648;
        let k = str(x % span);
        let op = (x // 7) % 10;
        if op < 4 { d[k] = i; m[k] = "v" + str(i % 13); }
        elif op < 7 {
            if k in d { del d[k]; }
            if k in m { del m[k]; }
        } elif op == 7 {
            for kk in d { acc = (acc * 3 + len(kk) + d[kk]) % 1000003; }
        } elif op == 8 {
            if k in d { acc = (acc + d.pop(k)) % 1000003; d[k] = acc; }
        } else {
            for kk, vv in m.items() { acc = (acc * 7 + len(kk) + len(vv)) % 1000003; }
        }
    }
    for kk in d { acc = (acc * 3 + int(kk)) % 1000003; }
    for kk, vv in m.items() { acc = (acc * 5 + int(kk) + len(vv)) % 1000003; }
    return acc * 10000 + len(d) * 10 + len(m) % 10;
}

fn main() {
    print(churn_sdict(3000));
    let b = Box({});
    print(churn_field(b, 5000), len(b.d));
    print(churn_smap(500));
    print("%.4f" % churn_fdict(700));
    print(churn_sset(900));
    print(churn_bmap(800));
    let seeds = [1, 42, 12345];
    let spans = [5, 60, 3000, 200000, 900000000];
    for a in range(0, 3) {
        for b2 in range(0, 5) {
            print(run_int(seeds[a], 3000 + 500 * b2, spans[b2]), run_str(seeds[a], 2000 + 300 * b2, spans[b2]));
        }
    }
}
"""

PYTHON = """
class Box:
    def __init__(self, d): self.d = d

class OSet:
    # AIL keeps a set in insertion order; CPython's own set order is unspecified.
    def __init__(self, items=()):
        self.d = {}
        for x in items: self.add(x)
    def add(self, x): self.d.setdefault(x, None)
    def discard(self, x): self.d.pop(x, None)
    def __iter__(self): return iter(list(self.d))
    def __contains__(self, x): return x in self.d
    def __len__(self): return len(self.d)
    def __and__(self, o): return OSet(x for x in self if x in o)
    def __sub__(self, o): return OSet(x for x in self if x not in o)
    def __or__(self, o): return OSet(list(self) + list(o))

def churn_sdict(n):
    d = {}
    acc = 0
    for i in range(n):
        d[str(i)] = i
        if i % 3 == 1 and str(i - 1) in d: del d[str(i - 1)]
        if i % 7 == 0 and str(i // 2) in d: acc += d.pop(str(i // 2))
        if i % 50 == 0:
            for k in d: acc += len(k)
    for k, v in d.items(): acc = acc * 31 % 1000000007 + v + len(k)
    keys = sorted(d)
    print(len(d), len(keys), keys[0], keys[len(keys) - 1])
    d["5"] = 99
    del d["2"]
    d["2"] = 7
    s = 0
    for v in d.values(): s = s * 7 % 1000003 + v
    print(s)
    return acc

def churn_field(b, n):
    for i in range(n):
        b.d[str(i % 97)] = i
        if i % 2 == 0 and str((i * 7) % 97) in b.d: del b.d[str((i * 7) % 97)]
    t = 0
    for k in b.d.keys(): t = t * 13 % 1000003 + len(k) + b.d[k]
    return t

def churn_smap(n):
    d = {}
    for i in range(n):
        d[str(i % 41)] = "v" + str(i)
        if i % 3 == 0 and str((i * 5) % 41) in d: del d[str((i * 5) % 41)]
    out = ""
    for k, v in d.items(): out = out + k + "=" + v + ","
    c = d.copy()
    del c[list(c.keys())[0]]
    c["new"] = "x"
    return out + "|" + str(len(c)) + "|" + str(len(d))

def churn_fdict(n):
    d = {}
    for i in range(n):
        d[str(i % 29)] = float(i) * 0.5
        if i % 4 == 0 and str((i * 3) % 29) in d: del d[str((i * 3) % 29)]
    t = 0.0
    for v in d.values(): t = t * 0.5 + v
    return t

def churn_sset(n):
    s = OSet()
    for i in range(n):
        s.add(str(i % 53))
        if i % 2 == 1: s.discard(str((i * 11) % 53))
    t = 0
    for k in s: t = t * 17 % 1000003 + int(k)
    return t * 100 + len(s)

def churn_bmap(n):
    d = {}
    for i in range(n):
        d[str(i % 37)] = b"ab" * (i % 5 + 1)
        if i % 3 == 2 and str((i * 7) % 37) in d: del d[str((i * 7) % 37)]
    t = 0
    for k in d.keys(): t = t * 19 % 1000003 + int(k) * 10 + len(d[k])
    return t * 100 + len(d)

def run_int(seed, n, span):
    d = {}; s = OSet()
    x = seed; acc = 0
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        k = x % span
        op = (x // 7) % 10
        if op < 4:
            d[k] = i; s.add(k)
        elif op < 7:
            d.pop(k, None); s.discard(k)
        elif op == 7:
            for kk in d: acc = (acc * 3 + kk) % 1000003
            for kk in s: acc = (acc * 5 + kk) % 1000003
        elif op == 8:
            if k in d:
                acc = (acc + d.pop(k)) % 1000003; d[k] = acc
        else:
            for kk, vv in d.items(): acc = (acc * 7 + kk + vv) % 1000003
    u = OSet(i * 2 for i in range(1500))
    for kk in s & u: acc = (acc * 3 + kk) % 1000003
    for kk in s - u: acc = (acc * 5 + kk) % 1000003
    for kk in s | u: acc = (acc * 7 + kk) % 1000003
    for kk in d: acc = (acc * 3 + kk) % 1000003
    return acc * 10000 + len(d) * 10 + len(s) % 10

def run_str(seed, n, span):
    d = {}; m = {}
    x = seed; acc = 0
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        k = str(x % span)
        op = (x // 7) % 10
        if op < 4:
            d[k] = i; m[k] = "v" + str(i % 13)
        elif op < 7:
            d.pop(k, None); m.pop(k, None)
        elif op == 7:
            for kk in d: acc = (acc * 3 + len(kk) + d[kk]) % 1000003
        elif op == 8:
            if k in d:
                acc = (acc + d.pop(k)) % 1000003; d[k] = acc
        else:
            for kk, vv in m.items(): acc = (acc * 7 + len(kk) + len(vv)) % 1000003
    for kk in d: acc = (acc * 3 + int(kk)) % 1000003
    for kk, vv in m.items(): acc = (acc * 5 + int(kk) + len(vv)) % 1000003
    return acc * 10000 + len(d) * 10 + len(m) % 10

print(churn_sdict(3000))
b = Box({})
print(churn_field(b, 5000), len(b.d))
print(churn_smap(500))
print("%.4f" % churn_fdict(700))
print(churn_sset(900))
print(churn_bmap(800))
seeds = [1, 42, 12345]
spans = [5, 60, 3000, 200000, 900000000]
for a in range(3):
    for b2 in range(5):
        print(run_int(seeds[a], 3000 + 500 * b2, spans[b2]), run_str(seeds[a], 2000 + 300 * b2, spans[b2]))
"""

# 300k keys in each kind of table, then every other one deleted: quadratic before (minutes),
# well under a second now. The bound is loose on purpose -- it only has to catch O(n) per del.
SCALE = """
fn main() {
    let n = 300000;
    let d: dict[str, int] = {};
    let m: dict[str, str] = {};
    let e = {};
    let s = set();
    for i in range(0, n) {
        let k = (i * 7919) % 1000003;
        d[str(k)] = i; m[str(k)] = "v"; e[k] = i; s.add(k);
    }
    for i in range(0, n) {
        if i % 2 == 0 {
            let k = (i * 7919) % 1000003;
            del d[str(k)]; del m[str(k)]; del e[k]; s.discard(k);
        }
    }
    let t = 0;
    for ks in d { t = (t + len(ks)) % 1000003; }
    for ks, vs in m.items() { t = (t + len(ks) + len(vs)) % 1000003; }
    for ki in e { t = (t * 3 + ki) % 1000003; }
    for ki in s { t = (t * 5 + ki) % 1000003; }
    print(t, len(d), len(m), len(e), len(s));
}
"""

FIELD = """
struct T { par: list[int]; sub: list[int]; }

fn fold(t: T) -> int {
    let i = len(t.par) - 1;
    while i >= 1 {
        t.sub[t.par[i]] += t.sub[i];
        i -= 1;
    }
    return t.sub[0];
}

fn far(t: T, i: int) -> int {
    return t.sub[t.par[i]];
}

fn main() {
    let n = 200000;
    let par = [0] * n;
    let sub = [1] * n;
    for i in range(1, n) { par[i] = (i - 1) // 2; }
    let t = T(par, sub);
    print(fold(t), t.sub[1], t.sub[n - 1]);
    let u = T([0, 0, 7], [1, 2, 3]);
    print(far(u, 1));
    try { print(far(u, 2)); } except IndexError { print("index error"); }
    try { print(far(u, 3)); } except IndexError { print("index error"); }
}
"""

FIELD_PY = """
n = 200000
par = [0] * n
sub = [1] * n
for i in range(1, n): par[i] = (i - 1) // 2
i = n - 1
while i >= 1:
    sub[par[i]] += sub[i]
    i -= 1
print(sub[0], sub[1], sub[n - 1])
up, us = [0, 0, 7], [1, 2, 3]
print(us[up[1]])
for i in (2, 3):
    try: print(us[up[i]])
    except IndexError: print("index error")
"""


def build(directory, text, name="p"):
    source, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "-debug")
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


class DictDeleteTests(unittest.TestCase):
    def test_every_table_kind_matches_cpython_through_deletions(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(directory, SOURCE)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, text=True, timeout=120)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            # the generated walks of insertion order close holes first
            self.assertIn("ail_stab_dense(&", program)
            self.assertIn("ail_tab_order(&", program)

    def test_deleting_half_of_a_large_table_is_not_quadratic(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, _ = build(directory, SCALE)
            start = time.monotonic()
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            elapsed = time.monotonic() - start
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout.split()[1:], ["150000"] * 4)
            self.assertLess(elapsed, 20.0)

    def test_field_index_by_field_read_copies_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, program = build(directory, FIELD)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", FIELD_PY], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            self.assertNotIn("_snapshot(", body_of(program, "fold"))
            self.assertNotIn("_snapshot(", body_of(program, "far"))


if __name__ == "__main__":
    unittest.main()
