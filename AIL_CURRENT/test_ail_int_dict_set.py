"""`dict[int, T]`, `set[int]` and `set[str]` annotations, everywhere a type is written.

LLM-written AIL reaches for `let idx: dict[int, int] = {};` and `let seen: set[int] = set();`, which
the syntax used to refuse; the workaround, `str(r.a)` as a dict key, made an LLM-written ledger 7.7x
slower than C (2026-10-14). These annotations now bind the int table every unannotated `{}` already
uses (ail_tab) and the str table (ail_stab): locals, parameters (read-only), results and struct
fields, with CPython's results for lookups, get/pop/setdefault/del, insertion-ordered iteration,
keys/values/items, sorted, and add/discard/remove and | & - ^ on sets. Sets keep AIL's insertion
order, so the CPython oracle below orders its sets the same way (OSet).
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
struct Index {
    pos: dict[int, int];
    w: dict[int, float];
    names: dict[int, str];
    blobs: dict[int, bytes];
    seen: set[int];
    tags: set[str];
}

fn total(d: dict[int, int]) -> int {
    let t = 0;
    for k, v in d.items() { t = t * 31 % 1000003 + k * 7 + v; }
    return t;
}

fn has_all(s: set[int], xs: list[int]) -> int {
    let c = 0;
    for x in xs { if x in s { c += 1; } }
    return c;
}

fn squares(n: int) -> dict[int, int] {
    let d: dict[int, int] = {};
    for i in range(n) { d[i * i % 17] = i; }
    return d;
}

fn evens(n: int) -> set[int] {
    let s: set[int] = set();
    for i in range(n) { if i % 2 == 0 { s.add(i); } }
    return s;
}

fn words(xs: list[str]) -> set[str] {
    let s: set[str] = set();
    for w in xs { s.add(w); }
    return s;
}

fn label(names: dict[int, str], k: int) -> str {
    return names.get(k, "?");
}

fn main() {
    let d: dict[int, int] = {3: 30, -1: 10};
    d[1000000007] = 5;
    d[-1] += 4;
    print(len(d), d[3], d[-1], d.get(42, -9), d.setdefault(8, 80), d.setdefault(3, 0));
    print(total(d));
    let ks = d.keys();
    let vs = d.values();
    print(len(ks), ks[0], ks[len(ks) - 1], vs[1]);
    let srt = sorted(d);
    print(srt[0], srt[len(srt) - 1], sum(d), min(d), max(d));
    print(d.pop(3), d.pop(77, -2), len(d));
    if 1000000007 in d.keys() { print("in keys"); }
    del d[8];
    d[3] = 1;
    for k in d { print(k, d[k]); }
    let e = d.copy();
    e[99] = 9;
    e.update(d);
    print(len(d), len(e));
    e.clear();
    if not e { print("empty"); }

    let sq = squares(40);
    let sk = sorted(sq.keys());
    print(len(sq), sk[0], sk[len(sk) - 1], total(sq));

    let f: dict[int, float] = {};
    for i in range(10) { f[i % 4] = float(i) * 0.25; }
    f[2] += 1.5;
    let fs = 0.0;
    for fv in f.values() { fs = fs * 2.0 + fv; }
    print("%.4f" % fs, "%.2f" % f.get(9, 0.5), "%.2f" % f.pop(0));

    let m: dict[int, str] = {};
    for i in range(12) { m[i % 5] = "v" + str(i); }
    m[3] += "!";
    del m[1];
    m[1] = "back";
    let out = "";
    for mk, mv2 in m.items() { out = out + str(mk) + "=" + mv2 + ","; }
    print(out, label(m, 4), label(m, 40), m.pop(0), len(m));
    let mv = m.values();
    print(len(mv), mv[0]);

    let b: dict[int, bytes] = {};
    for i in range(9) { b[i % 4] = b"ab" * (i % 3 + 1); }
    del b[2];
    let bl = 0;
    for bk, bv in b.items() { bl = bl * 10 + len(bv) + bk; }
    print(bl, len(b[1]), len(b.get(2, b"zz")));

    let s: set[int] = {5, 1, 5, 9};
    s.add(7);
    s.discard(1);
    s.discard(100);
    s.remove(9);
    let u = evens(12);
    let both = s | u;
    let common = s & u;
    let only = u - s;
    let either = s ^ u;
    print(len(s), len(u), len(both), len(common), len(only), len(either));
    let acc = 0;
    for x in both { acc = acc * 7 + x; }
    for x in common { acc = acc * 7 + x; }
    for x in only { acc = acc * 7 + x; }
    for x in either { acc = acc * 7 + x; }
    print(acc, has_all(u, [0, 1, 2, 3, 4]));
    print(sum(u), max(u));
    print(sorted(s)[0]);
    s |= {100, 5};
    s -= {7};
    print(len(s), 100 in s, 7 in s);
    let lst = set([4, 4, 2, 9]);
    print(len(lst));

    let t = words(["b", "a", "b", "c"]);
    let t2: set[str] = {"c", "d"};
    let tu = t | t2;
    let tw = "";
    for w in tu { tw = tw + w; }
    for w in t & t2 { tw = tw + w.upper(); }
    for w in sorted(t - t2) { tw = tw + "-" + w; }
    print(tw, len(t ^ t2), "a" in t, "z" in t);
    t.remove("a");
    print(len(t));
    try { t.remove("zz"); } except KeyError { print("key error"); }
    try { print(d[123456]); } except KeyError { print("key error"); }

    let ix = Index({}, {}, {}, {}, set(), set());
    for i in range(20) {
        ix.pos[i * 3] = i;
        ix.w[i] = float(i) / 4.0;
        ix.names[i % 6] = "n" + str(i);
        ix.blobs[i % 3] = b"x" * i;
        ix.seen.add(i % 7);
        ix.tags.add(str(i % 4));
    }
    del ix.pos[3];
    ix.seen.discard(0);
    ix.tags.remove("1");
    print(len(ix.pos), ix.pos[57], 3 in ix.pos, "%.2f" % ix.w[19], ix.names[5], len(ix.blobs[2]));
    print(len(ix.seen), 6 in ix.seen, len(ix.tags), "1" in ix.tags, total(ix.pos), has_all(ix.seen, [1, 2, 0]));
    let cp = ix.seen;
    cp.add(1000);
    print(len(cp), len(ix.seen));
    ix.seen = cp;
    print(len(ix.seen));
}
"""

PYTHON = """
class OSet:
    '''AIL keeps a set in insertion order; CPython's own set order is unspecified.'''
    def __init__(self, items=()):
        self.d = {}
        for x in items:
            self.add(x)
    def add(self, x): self.d.setdefault(x, None)
    def discard(self, x): self.d.pop(x, None)
    def remove(self, x): del self.d[x]
    def copy(self): return OSet(self)
    def __iter__(self): return iter(list(self.d))
    def __contains__(self, x): return x in self.d
    def __len__(self): return len(self.d)
    def __and__(self, o): return OSet(x for x in self if x in o)
    def __sub__(self, o): return OSet(x for x in self if x not in o)
    def __or__(self, o): return OSet(list(self) + list(o))
    def __xor__(self, o): return OSet([x for x in self if x not in o] + [x for x in o if x not in self])


class Index:
    def __init__(self, pos, w, names, blobs, seen, tags):
        self.pos, self.w, self.names, self.blobs, self.seen, self.tags = pos, w, names, blobs, seen, tags


def total(d):
    t = 0
    for k, v in d.items():
        t = t * 31 % 1000003 + k * 7 + v
    return t


def has_all(s, xs):
    return sum(1 for x in xs if x in s)


def squares(n):
    d = {}
    for i in range(n):
        d[i * i % 17] = i
    return d


def evens(n):
    return OSet(i for i in range(n) if i % 2 == 0)


def words(xs):
    return OSet(xs)


def label(names, k):
    return names.get(k, "?")


def main():
    d = {3: 30, -1: 10}
    d[1000000007] = 5
    d[-1] += 4
    print(len(d), d[3], d[-1], d.get(42, -9), d.setdefault(8, 80), d.setdefault(3, 0))
    print(total(d))
    ks = list(d.keys())
    vs = list(d.values())
    print(len(ks), ks[0], ks[len(ks) - 1], vs[1])
    srt = sorted(d)
    print(srt[0], srt[len(srt) - 1], sum(d), min(d), max(d))
    print(d.pop(3), d.pop(77, -2), len(d))
    if 1000000007 in d.keys():
        print("in keys")
    del d[8]
    d[3] = 1
    for k in d:
        print(k, d[k])
    e = d.copy()
    e[99] = 9
    e.update(d)
    print(len(d), len(e))
    e.clear()
    if not e:
        print("empty")

    sq = squares(40)
    sk = sorted(sq.keys())
    print(len(sq), sk[0], sk[len(sk) - 1], total(sq))

    f = {}
    for i in range(10):
        f[i % 4] = float(i) * 0.25
    f[2] += 1.5
    fs = 0.0
    for fv in f.values():
        fs = fs * 2.0 + fv
    print("%.4f" % fs, "%.2f" % f.get(9, 0.5), "%.2f" % f.pop(0))

    m = {}
    for i in range(12):
        m[i % 5] = "v" + str(i)
    m[3] += "!"
    del m[1]
    m[1] = "back"
    out = ""
    for mk, mv2 in m.items():
        out = out + str(mk) + "=" + mv2 + ","
    print(out, label(m, 4), label(m, 40), m.pop(0), len(m))
    mv = list(m.values())
    print(len(mv), mv[0])

    b = {}
    for i in range(9):
        b[i % 4] = b"ab" * (i % 3 + 1)
    del b[2]
    bl = 0
    for bk, bv in b.items():
        bl = bl * 10 + len(bv) + bk
    print(bl, len(b[1]), len(b.get(2, b"zz")))

    s = OSet([5, 1, 5, 9])
    s.add(7)
    s.discard(1)
    s.discard(100)
    s.remove(9)
    u = evens(12)
    both = s | u
    common = s & u
    only = u - s
    either = s ^ u
    print(len(s), len(u), len(both), len(common), len(only), len(either))
    acc = 0
    for x in both:
        acc = acc * 7 + x
    for x in common:
        acc = acc * 7 + x
    for x in only:
        acc = acc * 7 + x
    for x in either:
        acc = acc * 7 + x
    print(acc, has_all(u, [0, 1, 2, 3, 4]))
    print(sum(u), max(u))
    print(sorted(s)[0])
    s = s | OSet([100, 5])
    s = s - OSet([7])
    print(len(s), 100 in s, 7 in s)
    lst = OSet([4, 4, 2, 9])
    print(len(lst))

    t = words(["b", "a", "b", "c"])
    t2 = OSet(["c", "d"])
    tu = t | t2
    tw = ""
    for w in tu:
        tw = tw + w
    for w in t & t2:
        tw = tw + w.upper()
    for w in sorted(t - t2):
        tw = tw + "-" + w
    print(tw, len(t ^ t2), "a" in t, "z" in t)
    t.remove("a")
    print(len(t))
    try:
        t.remove("zz")
    except KeyError:
        print("key error")
    try:
        print(d[123456])
    except KeyError:
        print("key error")

    ix = Index({}, {}, {}, {}, OSet(), OSet())
    for i in range(20):
        ix.pos[i * 3] = i
        ix.w[i] = float(i) / 4.0
        ix.names[i % 6] = "n" + str(i)
        ix.blobs[i % 3] = b"x" * i
        ix.seen.add(i % 7)
        ix.tags.add(str(i % 4))
    del ix.pos[3]
    ix.seen.discard(0)
    ix.tags.remove("1")
    print(len(ix.pos), ix.pos[57], 3 in ix.pos, "%.2f" % ix.w[19], ix.names[5], len(ix.blobs[2]))
    print(len(ix.seen), 6 in ix.seen, len(ix.tags), "1" in ix.tags, total(ix.pos), has_all(ix.seen, [1, 2, 0]))
    cp = ix.seen.copy()
    cp.add(1000)
    print(len(cp), len(ix.seen))
    ix.seen = cp
    print(len(ix.seen))


main()
"""

EXTRA = """
struct Bag { s: set[int]; d: dict[int, int]; }
fn count(s: set[int]) -> int { return len(s); }
fn pick() -> set[int] { return {4, 2, 4}; }
fn none() -> dict[int, int] { return {}; }
fn twice(n: int) -> dict[int, int] { let d: dict[int, int] = {1: n}; d[2] = n * 2; return d; }
fn strs() -> set[str] { return set(["x", "y", "x"]); }
fn main() {
    print(count(set()), count({7, 8}), count(pick()), len(none()), twice(5)[2], len(strs()));
    let b = Bag({1, 2}, twice(3));
    b.s |= pick();
    b.d = none();
    print(len(b.s), len(b.d));
    let fromr: set[int] = set([1, 2, 2]);
    let xs = [3, 3, 1];
    print(len(fromr), len(set(xs)));
    let q: set[int] = set(xs);
    q &= {3};
    q ^= {9, 3};
    print(len(q), 9 in q, 3 in q);
}
"""


def build(directory, text, name="p", syntax=None):
    source, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "-debug")
    source.write_text(text)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug), *(["--syntax", syntax] if syntax else [])],
                           capture_output=True, text=True, timeout=300)
    return built, exe, debug / "program.c"


def body_of(program, name):
    """The definition (not the prototype) of generated function `name`."""
    match = re.search(r"\n[\w ]+ %s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


REFUSED = [
    'fn main() { let s: set[int] = set(); s.add(1); print(s[0]); }',
    'fn main() { let s: set[int] = {}; print(len(s)); }',
    'fn main() { let s: set[int] = set(); s.add(1); del s[1]; }',
    'fn f(s: set[int]) -> int { s.add(2); return len(s); } fn main() { let s: set[int] = set(); print(f(s)); }',
    'fn f(d: dict[int, int]) -> int { d[1] = 2; return len(d); } fn main() { let d: dict[int, int] = {}; print(f(d)); }',
    'fn main() { let d: dict[int, int] = {}; d["a"] = 1; }',
    'fn main() { let s: set[int] = set(); s.add("x"); }',
    'fn main() { let t: set[str] = set(); t.add(1); }',
    'fn main() { let d: dict[int, str] = {}; d[1] = 2; }',
    'fn main() { let s: set[int] = set(); print(s.get(1, 0)); }',
    'fn main() { let s: set[float] = set(); }',
    'fn main() { let s: set[int] = set(); let x = s.add(1); }',
    'fn f(s: set[int]) -> int { return len(s); } fn main() { let s = set(); s.add(1); print(f(s)); }',
]


# Few keys over a wide id range, cleared and refilled each round (term_rank's per-document
# id-to-count table): such tables spill from the dense array to the hash table on a sparse widen,
# and must still give CPython's results -- insertion order, re-adds after del, clear, and a table
# that spilled early and then fills densely. `wide` (a permutation written in stride order) spills
# on its second key and returns to the array once its keys fill the span.
SPARSE = """
fn main() {
    let x = 12345;
    let cur: dict[int, int] = {};
    let seen: set[int] = set();
    let acc = 0;
    for doc in range(300) {
        for t in range(1 + doc % 23) {
            x = (x * 1103515245 + 12345) % 2147483648;
            let id = x % 200000;
            if doc % 5 == 0 { id = id * 9973; }
            cur[id] = cur.get(id, 0) + 1;
            seen.add(id % 70001 * 31);
        }
        if doc % 7 == 0 and len(cur) > 2 {
            let ks = cur.keys();
            del cur[ks[1]];
            cur[ks[1]] = 5;
        }
        for k, v in cur.items() { acc = (acc * 131 + k * 3 + v) % 1000000007; }
        cur.clear();
    }
    print(acc, len(seen));
    let sx = 0;
    for v in seen { sx = (sx * 7 + v) % 1000000007; }
    print(sx);
    let grow: dict[int, int] = {5: 1, 900000: 2};
    for i in range(20000) { grow[i * 37 % 50000] = i; }
    let g = 0;
    for k, v in grow.items() { g = (g * 31 + k + v) % 1000000007; }
    print(len(grow), g, grow.get(900000, -1), grow.get(-3, -1));
    let wide: dict[int, int] = {};
    for i in range(30000) { wide[(i * 7919) % 30000 - 15000] = i; }
    let w = 0;
    for k, v in wide.items() { w = (w * 31 + k + v) % 1000000007; }
    print(len(wide), w);
}
"""

SPARSE_PYTHON = """
def main():
    x = 12345
    cur = {}
    seen = {}
    acc = 0
    for doc in range(300):
        for t in range(1 + doc % 23):
            x = (x * 1103515245 + 12345) % 2147483648
            id = x % 200000
            if doc % 5 == 0:
                id = id * 9973
            cur[id] = cur.get(id, 0) + 1
            seen.setdefault(id % 70001 * 31, None)
        if doc % 7 == 0 and len(cur) > 2:
            ks = list(cur.keys())
            del cur[ks[1]]
            cur[ks[1]] = 5
        for k, v in cur.items():
            acc = (acc * 131 + k * 3 + v) % 1000000007
        cur.clear()
    print(acc, len(seen))
    sx = 0
    for v in seen:
        sx = (sx * 7 + v) % 1000000007
    print(sx)
    grow = {5: 1, 900000: 2}
    for i in range(20000):
        grow[i * 37 % 50000] = i
    g = 0
    for k, v in grow.items():
        g = (g * 31 + k + v) % 1000000007
    print(len(grow), g, grow.get(900000, -1), grow.get(-3, -1))
    wide = {}
    for i in range(30000):
        wide[(i * 7919) % 30000 - 15000] = i
    w = 0
    for k, v in wide.items():
        w = (w * 31 + k + v) % 1000000007
    print(len(wide), w)
main()
"""


class IntDictSetTests(unittest.TestCase):
    def test_every_operation_matches_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, SOURCE)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            # int keys stay int64 in the int table: no key ever becomes a str
            program = c_file.read_text()
            for name, table in (("squares", "ail_idict_put("), ("evens", "ail_iset_add("),
                                ("total", "ail_idict_keys_snapshot("), ("has_all", "ail_iset_has(")):
                body = body_of(program, name)
                self.assertIn(table, body, name)
                for slow in ("ail_str_from_int", "ail_stab", "ail_sdict"):
                    self.assertNotIn(slow, body, name)

    def test_sparse_refills_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, _ = build(directory, SPARSE)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", SPARSE_PYTHON], capture_output=True, text=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)

    def test_literals_results_and_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, _ = build(directory, EXTRA)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, "0 2 2 0 10 2\n3 0\n2 2\n1 True False\n")

    def test_python_syntax_annotations(self):
        text = ("def main() -> int:\n    d: dict[int, int] = {}\n    s: set[str] = set()\n"
                "    d[7] = 1\n    s.add(\"a\")\n    print(len(d), d[7], len(s))\n    return 0\nmain()\n")
        with tempfile.TemporaryDirectory() as directory:
            built, exe, _ = build(directory, text, syntax="python")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.stdout, "1 1 1\n")

    def test_misuse_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, text in enumerate(REFUSED):
                with self.subTest(text=text):
                    built, exe, _ = build(directory, text, name="n%d" % index)
                    self.assertNotEqual(built.returncode, 0)
                    self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
